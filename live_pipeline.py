"""Live analysis orchestration: SAM → events → Muse (reuses existing modules).

Explicit jobs only. Budget-gated. Joints optional. Does not mutate frozen
experiment trees under data/experiments/ held-out / pilot folders.
"""
from __future__ import annotations

import json
import math
import os
import time
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

import ai_analysis as AI
import evidence_fusion as EF
import failure_inputs as FI
import failures as F
import live_budget as budget
import tracking as T
import verification as V

ROOT = Path(__file__).resolve().parent
JOBS_ROOT = ROOT / "data" / "live_jobs"
DEFAULT_TASK = ROOT / "data" / "tasks" / "botfails_dish.json"

JOB_IO_LOCK = threading.RLock()
MUSE_RESERVATION_USD = 1.32  # Entire model context + 2048 output tokens, Standard pricing.

ProgressCb = Callable[[str, dict[str, Any]], None]


@dataclass
class AnalyzeRequest:
    job_id: str
    video_path: Path
    task_description: str
    object_concept: str
    destination_concept: str
    window_start_s: float | None = None
    window_end_s: float | None = None
    max_window_s: float = 4.0
    joint_dir: Path | None = None
    episode_index: int | None = None
    gripper_calibration: Path | None = None
    run_muse: bool = True
    force_sam_refresh: bool = False
    dry_run: bool = True
    cache_only: bool = False
    complete_demonstration: bool = False
    # Optional multi-camera orchestration; defaults retain single-camera behavior.
    image_observations_only: bool = False
    budget_job_id: str | None = None
    investigation_questions: str = ""

    def __post_init__(self) -> None:
        if not all(s.strip() for s in (self.task_description, self.object_concept, self.destination_concept)):
            raise ValueError("Task, object and destination must be nonempty")
        if not math.isfinite(self.max_window_s) or not 0 < self.max_window_s <= 30:
            raise ValueError("max_window_s must be between 0 and 30 seconds")
        if (self.window_start_s is None) != (self.window_end_s is None):
            raise ValueError("Supply both window_start_s and window_end_s")
        if self.window_start_s is not None:
            a, b = self.window_start_s, self.window_end_s
            if not math.isfinite(a) or not math.isfinite(b) or a < 0 or not 0 < b - a <= 30:
                raise ValueError("Window must be finite, nonnegative, ordered, and at most 30 seconds")


def _progress(cb: ProgressCb | None, stage: str, **kw: Any) -> None:
    if cb:
        cb(stage, kw)


def _write_job(job_dir: Path, name: str, payload: Any) -> Path:
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, indent=2, default=str)
    # Provider errors are untrusted text and may echo an Authorization value.
    # Keep credentials out of status, traceback and raw-response artifacts too.
    for name in ("MODEL_API_KEY", "FIREWORKS_API_KEY"):
        secret = (os.environ.get(name) or "").strip()
        if secret:
            serialized = serialized.replace(json.dumps(secret)[1:-1], "[REDACTED]")
    temporary.write_text(serialized + "\n", encoding="utf-8")
    with JOB_IO_LOCK:
        # Windows scanners/readers can briefly hold an otherwise valid artifact.
        # Retry only this local atomic rename, never an inference operation.
        for attempt in range(5):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if os.name != "nt" or attempt == 4:
                    raise
                time.sleep(0.025)
    return path


def _choose_window(
    fps: float,
    n_frames: int,
    start_s: float | None,
    end_s: float | None,
    max_window_s: float,
) -> tuple[int, int]:
    if not math.isfinite(fps) or fps <= 0 or n_frames <= 0:
        raise ValueError("Video must contain frames and a finite positive frame rate")
    if start_s is not None and end_s is not None:
        a = max(0, int(round(start_s * fps)))
        b = min(n_frames, int(round(end_s * fps)))
        if b <= a:
            raise ValueError("window_end_s must be after window_start_s")
        return a, b
    # Default: first max_window_s of the video (short-clip workflow)
    a = 0
    b = min(n_frames, max(1, int(round(max_window_s * fps))))
    return a, b


def _apply_analysis_scope(report: F.FailureReport, *, complete: bool,
                          start: int, end: int, n_frames: int) -> dict[str, Any]:
    """A file boundary alone is not proof that the demonstrated task ended."""
    whole_task = complete and start == 0 and end == n_frames
    scope = {"complete_demonstration": whole_task, "declared_complete": complete,
             "frame_start": start, "frame_end": end, "source_frames": n_frames}
    report.inputs["analysis_scope"] = scope
    if not whole_task or not report.physical_events:
        report.verdict = "uncertain"
        report.failure_type = None
        report.earliest_failure = None
    if not whole_task:
        report.object_outcomes = []
        report.recoveries = []
        report.uncertainties.append("Task-final state is not independently established: the window is partial "
                                    "or complete-demonstration scope was not declared; whole-task outcome remains uncertain.")
    return scope


def _verification_accepted(result: dict[str, Any]) -> bool:
    return (not result.get("claims_failed") and not result.get("claims_unverifiable")
            and not any(f.get("severity") == "error" for f in result.get("findings", []))
            and all(v == "supported" for v in result.get("event_verdicts", {}).values()))


def _obs_to_tracks_json(
    observations: list[T.ObjectTrackObservation],
    *,
    fps: float,
    image_size: tuple[int, int],
    t_start: float,
    t_end: float,
    source: str,
) -> dict[str, Any]:
    by_track: dict[str, list[dict[str, Any]]] = {}
    frames: dict[str, list[dict[str, Any]]] = {}
    colors = [
        [255, 0, 200],
        [255, 210, 0],
        [80, 120, 255],
        [0, 220, 180],
        [255, 120, 80],
    ]
    for o in observations:
        if o.frame_index is None or o.centroid is None or o.bbox is None:
            continue
        if not o.observation_returned:
            continue
        pt = {
            "frame_index": int(o.frame_index),
            "t": round(float(o.timestamp_s), 4),
            "centroid": [round(float(o.centroid[0]), 1), round(float(o.centroid[1]), 1)],
            "bbox": [round(float(v), 1) for v in o.bbox],
        }
        by_track.setdefault(o.object_id, []).append(pt)
        frames.setdefault(str(o.frame_index), []).append(
            {
                "object_id": o.object_id,
                "centroid": pt["centroid"],
                "bbox": pt["bbox"],
                "confidence": float(o.confidence or 0.0),
                "track_status": o.track_status,
                "mask": ({"size": o.mask_rle["size"], "counts": T._coco_counts(o.mask_rle["counts"])}
                         if o.mask_rle else None),
            }
        )
    legend = []
    tracks_out = {}
    for i, (oid, pts) in enumerate(sorted(by_track.items())):
        color = colors[i % len(colors)]
        pts.sort(key=lambda p: p["frame_index"])
        legend.append({"object_id": oid, "color_rgb": color, "label": oid})
        tracks_out[oid] = {
            "object_id": oid,
            "color_rgb": color,
            "n_observations": len(pts),
            "points": pts,
        }
    return {
        "episode_key": "live",
        "source": source,
        "provenance": "observed",
        "note": (
            "Live SAM observations only. No interpolation across missing frames."
        ),
        "image_size": [int(image_size[0]), int(image_size[1])],
        "fps": float(fps),
        "t_start": t_start,
        "t_end": t_end,
        "frame_start": min((p["frame_index"] for pts in by_track.values() for p in pts), default=None),
        "frame_end": max((p["frame_index"] for pts in by_track.values() for p in pts), default=None),
        "legend": legend,
        "tracks": tracks_out,
        "frames": frames,
    }


def _paint_overlay_video(
    video_path: Path,
    observations: list[T.ObjectTrackObservation],
    out_path: Path,
    *,
    start_frame: int,
    end_frame: int,
) -> dict[str, Any]:
    """Paint observed masks/bboxes onto a full-length copy; blanks outside window."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"available": False, "reason": "cannot open video"}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

    by_frame: dict[int, list[T.ObjectTrackObservation]] = {}
    for o in observations:
        if o.frame_index is None:
            continue
        by_frame.setdefault(int(o.frame_index), []).append(o)

    colors = {
        0: (255, 0, 200),
        1: (0, 210, 255),
        2: (255, 120, 80),
    }
    id_to_color: dict[str, tuple[int, int, int]] = {}
    fi = 0
    painted = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if start_frame <= fi < end_frame and fi in by_frame:
            for o in by_frame[fi]:
                if o.object_id not in id_to_color:
                    id_to_color[o.object_id] = colors[len(id_to_color) % 3]
                color = id_to_color[o.object_id]
                if o.mask_rle and o.bbox:
                    try:
                        mask = T.mask_in_frame(o.mask_rle, o.bbox, (h, w))
                        if mask is not None and mask.any():
                            overlay = frame.copy()
                            overlay[mask] = (
                                0.45 * overlay[mask] + 0.55 * np.array(color, dtype=np.float32)
                            ).astype(np.uint8)
                            frame = overlay
                            painted += 1
                    except Exception:
                        pass
                if o.bbox:
                    x1, y1, x2, y2 = [int(round(v)) for v in o.bbox]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = o.object_id.replace("green plate:", "plate:")
                    cv2.putText(
                        frame,
                        label,
                        (x1, max(16, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        1,
                        cv2.LINE_AA,
                    )
        writer.write(frame)
        fi += 1
    cap.release()
    writer.release()
    return {
        "available": True,
        "video": out_path.name,
        "painted_mask_applications": painted,
        "t_start": start_frame / fps,
        "t_end": end_frame / fps,
        "frame_start": start_frame,
        "frame_end": end_frame,
        "legend": [
            {"object_id": oid, "color_rgb": list(col)}
            for oid, col in id_to_color.items()
        ],
        "note": "Masks painted only on frames with cached/live SAM observations — no invented detections.",
    }


def _analysis_bundle_from_pipeline(
    *,
    job_id: str,
    task_description: str,
    report: F.FailureReport,
    verification: dict[str, Any],
    muse: dict[str, Any] | None,
    tracks_meta: dict[str, Any],
    overlay_meta: dict[str, Any],
    joint_limitations: list[str],
    window: tuple[int, int],
    fps: float,
    package: dict[str, Any] | None = None,
    video_duration_s: float | None = None,
) -> dict[str, Any]:
    fr = report.to_dict()
    raw_validation = (muse or {}).get("validated") or {}
    validated = raw_validation
    if not validated.get("ok"):
        validated = {}
    events = (package or {}).get("physical_events", fr.get("physical_events")) or []
    markers = []
    for i, ev in enumerate(events):
        markers.append(
            {
                "id": ev.get("id") or f"event_{i}",
                "label": ev.get("subtype") or ev.get("kind") or "physical event",
                "t": float(ev["t_start"] if ev.get("t_start") is not None else window[0] / fps),
                "kind": "inferred_event"
                if (ev.get("status") or "").startswith("inferred")
                else "observed_measurement" if ev.get("status") == "observed" else "uncertain_event",
                "evidence_ids": ev.get("evidence_ids") or [],
            }
        )
    highlight = None
    if events:
        e0 = events[0]
        highlight = {
            "t_start": float(e0["t_start"] if e0.get("t_start") is not None else window[0] / fps),
            "t_end": float(e0["t_end"] if e0.get("t_end") is not None else window[1] / fps),
            "label": "suspected event interval",
            "status": e0.get("status") or "inferred",
            "note": e0.get("inference") or "",
        }

    evidence_catalog = []
    pkg = muse.get("package") if muse else None
    # Prefer fusion items from a rebuilt package stored alongside
    return {
        "episode_key": f"live_{job_id[:8]}",
        "title": f"Live analysis · {job_id[:8]}",
        "task": task_description,
        "split": "live",
        "available_episodes": [],
        "has_joint_animation": False,
        "pipeline_verdict": fr.get("verdict") or "uncertain",
        "analysis_scope": (fr.get("inputs") or {}).get("analysis_scope"),
        "task_outcome": validated.get("task_outcome") or fr.get("verdict") or "uncertain",
        "outcome_label": (
            validated.get("task_outcome") or fr.get("verdict") or "uncertain"
        ),
        "diagnosis_headline": (
            (validated.get("explanation") or "")[:120]
            or ((events[0].get("inference") or "Observed image-space change; task outcome remains uncertain.")
                if events else "No timed physical event localized")
        ),
        "diagnosis_summary": validated.get("explanation")
        or ((events[0].get("inference") or "Only observed image-space endpoints were compared; no grasp or release is established.")
            if events else "Evidence insufficient for a confident failure diagnosis."),
        "earliest_failure": fr.get("earliest_failure"),
        "physical_events": events,
        "highlight_interval": highlight,
        "timeline_markers": markers,
        "evidence_catalog": evidence_catalog,
        "frame_catalog": [],
        "observed": [],
        "inferred": [
            {
                "text": ev.get("inference"),
                "evidence_ids": ev.get("evidence_ids") or [],
                "t": ev.get("t_start"),
                "status": ev.get("status"),
            }
            for ev in events
            if ev.get("inference")
        ],
        "hypotheses": validated.get("hypotheses") or [],
        "unknowns": list(fr.get("uncertainties") or []) + joint_limitations,
        "muse_explanation": validated.get("explanation"),
        "factual_claims": validated.get("factual_claims") or [],
        "visual_interpretations": validated.get("visual_interpretations") or [],
        "limitations": list(validated.get("limitations") or []) + joint_limitations
        + (["Muse output rejected by evidence validation; showing deterministic findings."]
           if muse and not (muse.get("validated") or {}).get("ok") else []),
        "muse_only": None,
        "evidence_muse_outcome": validated.get("task_outcome"),
        "comparison_note": None,
        "highlight_muse_comparison": False,
        "sam_overlay": {
            "available": bool(overlay_meta.get("available")),
            "source": "live_pipeline",
            "concept": tracks_meta.get("legend", [{}])[0].get("object_id", "object")
            if tracks_meta.get("legend")
            else "object",
            "frame_start": overlay_meta.get("frame_start"),
            "frame_end": overlay_meta.get("frame_end"),
            "t_start": overlay_meta.get("t_start"),
            "t_end": overlay_meta.get("t_end"),
            "video": overlay_meta.get("video"),
            "note": overlay_meta.get("note"),
            "legend": overlay_meta.get("legend") or tracks_meta.get("legend"),
        },
        "video": {"rel": "video.mp4", "primary_evidence": True, "duration_s": video_duration_s},
        "disclaimer": (
            "Live DemoDoctor analysis. Camera is primary evidence. "
            "3D kinematics (if shown) remain unvalidated."
        ),
        "initial_seek_s": highlight["t_start"] if highlight else window[0] / fps,
        "live_job": {
            "job_id": job_id,
            "verification_ok": verification.get("ok"),
            "muse_validation_ok": raw_validation.get("ok"),
            "muse_validation_errors": raw_validation.get("validation_errors") or [],
        },
        "live": True,
    }


def run_analyze(req: AnalyzeRequest, progress: ProgressCb | None = None) -> dict[str, Any]:
    job_dir = JOBS_ROOT / req.job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "job_id": req.job_id,
        "status": "running",
        "created_at": time.time(),
        "stages": [],
        "errors": [],
        "cost": {"estimated_usd": 0.0, "spent_usd": 0.0, "events": []},
        "dry_run": req.dry_run,
    }
    _write_job(job_dir, "status.json", state)

    def stage(name: str, **info: Any) -> None:
        state["stages"].append({"name": name, "ts": time.time(), **info})
        _write_job(job_dir, "status.json", state)
        _progress(progress, name, **info)

    try:
        video_bytes = req.video_path.read_bytes()
        # Persist copy for replay
        dest_video = job_dir / "video.mp4"
        if not dest_video.exists():
            dest_video.write_bytes(video_bytes)

        fps, n_frames = T.probe_video(video_bytes)
        w, h = T.probe_video_size(video_bytes)
        start_f, end_f = _choose_window(
            fps, n_frames, req.window_start_s, req.window_end_s, req.max_window_s
        )
        stage(
            "probed_video",
            fps=fps,
            n_frames=n_frames,
            window=[start_f, end_f],
            size=[w, h],
        )

        skip_providers = req.dry_run or req.cache_only
        if not T.model_api_key_available() and not skip_providers:
            raise RuntimeError("MODEL_API_KEY missing — cannot run live SAM")
        if req.run_muse and not skip_providers:
            AI.load_fireworks_api_key()  # Preflight before any SAM spend.
        if not skip_providers:
            planned = (budget.estimate_sam_window_usd(end_f - start_f, fps)
                       + budget.estimate_sam_image_usd()
                       + (MUSE_RESERVATION_USD if req.run_muse else 0))
            available = budget.status()
            if planned > min(available["remaining_usd"], available["per_run_budget_usd"]):
                raise RuntimeError(f"Full request plan requires ${planned:.4f} budget headroom; "
                                   "no provider was called")

        tracker = T.Sam31Tracker() if not skip_providers else None
        usage_events: list[dict[str, Any]] = []

        # --- SAM object window ---
        sam_est = budget.estimate_sam_window_usd(end_f - start_f, fps)
        rid = None
        if not skip_providers:
            rid = budget.reserve(
                req.budget_job_id or req.job_id, sam_est, note=f"sam_window {req.object_concept}"
            )
        stage("sam_window_start", estimated_usd=sam_est, dry_run=req.dry_run)
        if skip_providers:
            chunk, obs, calls = None, [], []
            stage("sam_window_dry_run_skipped")
            if rid:
                budget.release(rid)
        else:
            chunk, obs, calls = tracker.track_window(
                video_bytes,
                start_frame=start_f,
                end_frame=end_f,
                concepts=[req.object_concept],
                force_refresh=req.force_sam_refresh,
            )
            if not calls and rid:
                budget.release(rid, note="sam_window_no_calls")
                rid = None
            for c in calls:
                from_cache = bool(c.from_cache)
                if rid:
                    budget.commit(
                        rid,
                        provider="meta_sam",
                        kind="video_window",
                        actual_usd=0.0 if from_cache else (
                            float((c.usage or {}).get("usage", {}).get("video_frames_processed")) * .20 / 1000
                            if (c.usage or {}).get("usage", {}).get("video_frames_processed") is not None else None),
                        usage=c.usage or {},
                        from_cache=from_cache,
                        note=f"status={c.status} obs={c.n_observations}",
                    )
                    rid = None
                usage_events.append(
                    {
                        "provider": "meta_sam",
                        "kind": "video_window",
                        "from_cache": from_cache,
                        "usage": c.usage,
                        "status": c.status,
                        "n_observations": c.n_observations,
                        "estimated_usd": 0.0 if from_cache else sam_est,
                    }
                )
                stage(
                    "sam_window_done",
                    status=c.status,
                    from_cache=from_cache,
                    n_observations=c.n_observations,
                )
                if c.status != "completed":
                    raise RuntimeError(f"SAM window status={c.status}; stopped without retry")
                if not from_cache and (c.usage or {}).get("usage", {}).get("video_frames_processed") is None:
                    raise RuntimeError("SAM billed-frame usage unknown; reconcile before another request")
            if not calls:
                raise RuntimeError("SAM returned no completed window call")

        # --- SAM destination image ---
        img_est = budget.estimate_sam_image_usd()
        rid_img = None
        rack_obs: list[Any] = []
        if not skip_providers:
            rid_img = budget.reserve(
                req.budget_job_id or req.job_id, img_est, note=f"sam_image {req.destination_concept}"
            )
            jpeg = T.extract_frame_jpeg(
                video_bytes, timestamp_s=start_f / fps, quality=95
            )
            rack_res = tracker.segment_image(
                jpeg,
                concept=req.destination_concept,
                force_refresh=req.force_sam_refresh,
            )
            rack_obs = list(rack_res.observations)
            from_cache = bool(rack_res.from_cache)
            budget.commit(
                rid_img,
                provider="meta_sam",
                kind="image",
                actual_usd=0.0 if from_cache else img_est,
                usage=(rack_res.diagnostics.usage if rack_res.diagnostics else {}) or {},
                from_cache=from_cache,
            )
            usage_events.append(
                {
                    "provider": "meta_sam",
                    "kind": "destination_image",
                    "from_cache": from_cache,
                    "n_observations": len(rack_obs),
                    "estimated_usd": 0.0 if from_cache else img_est,
                }
            )
            stage(
                "sam_destination_done",
                from_cache=from_cache,
                n_observations=len(rack_obs),
            )
            image_usage = (rack_res.diagnostics.usage if rack_res.diagnostics else {}) or {}
            terminal = (image_usage.get(req.destination_concept) or {}).get("terminal_event")
            if terminal != "response.completed":
                raise RuntimeError("SAM destination stream completion unverified; stopped without retry")
        else:
            stage("sam_destination_dry_run_skipped")

        # Build task spec (prefer dish JSON when concepts match; else ad-hoc)
        if (
            req.object_concept == "green plate"
            and req.destination_concept == "dish rack"
            and DEFAULT_TASK.is_file()
        ):
            task = FI.load_task(DEFAULT_TASK)
            if req.task_description:
                task = F.TaskSpec(
                    task_id=task.task_id,
                    description=req.task_description,
                    objects=task.objects,
                    target=task.target,
                    success=task.success,
                )
        else:
            task = F.TaskSpec(
                task_id="live_custom",
                description=req.task_description,
                objects=(F.ObjectSpec(concept=req.object_concept, count=None),),
                target=req.destination_concept,
                success="all_objects_in_target",
            )

        joint_limitations: list[str] = []
        if req.joint_dir is None:
            joint_limitations.append(
                "No joint-state data: gripper open/close and proprioceptive "
                "release timing cannot be measured."
            )

        if req.dry_run and not req.cache_only:
            report = F.FailureReport(
                task_id=task.task_id,
                verdict="uncertain",
                failure_type=None,
                earliest_failure=None,
                physical_events=[],
                recoveries=[],
                object_outcomes=[],
                uncertainties=joint_limitations
                + ["dry_run: SAM/Muse not executed"],
                inputs={"window": [start_f, end_f], "dry_run": True},
            )
            vdict = {"ok": True, "dry_run": True}
            muse_out = None
            tracks_meta = {
                "legend": [],
                "tracks": {},
                "frames": {},
                "fps": fps,
                "image_size": [w, h],
                "frame_start": start_f,
                "frame_end": end_f,
                "t_start": start_f / fps,
                "t_end": end_f / fps,
            }
            overlay_meta = {"available": False, "reason": "dry_run"}
            analysis = _analysis_bundle_from_pipeline(
                job_id=req.job_id, task_description=req.task_description,
                report=report, verification=vdict, muse=None,
                tracks_meta=tracks_meta, overlay_meta=overlay_meta,
                joint_limitations=joint_limitations, window=(start_f, end_f), fps=fps, video_duration_s=n_frames / fps,
            )
            analysis.update(dry_run=True,
                diagnosis_headline="Dry run ? no paid inference",
                diagnosis_summary="Upload and replay verified. SAM and Muse were skipped; no physical findings were produced.")
            from criteria_presentation import for_analysis
            analysis["criteria"] = for_analysis(analysis, n_frames=n_frames, fps=fps,
                object_concept=req.object_concept, destination=req.destination_concept, dry_run=True)
            _write_job(job_dir, "analysis.json", analysis)
            _write_job(job_dir, "tracks.json", tracks_meta)
            _write_job(job_dir, "sam_overlay.json", overlay_meta)
            _write_job(job_dir, "failure_report.json", report.to_dict())
            _write_job(job_dir, "verification.json", vdict)
        else:
            inputs = FI.build_window_inputs(
                dest_video,
                start_frame=start_f,
                end_frame=end_f,
                object_concept=req.object_concept,
                container_concept=req.destination_concept,
                container_frame=start_f,
                joint_dir=req.joint_dir,
                episode_index=req.episode_index,
                gripper_calibration=req.gripper_calibration,
            )
            if req.cache_only and (not inputs.call or not inputs.observations or not inputs.container_source.get("cached")):
                raise ValueError("Cache-only regression requires reusable object-window and destination-image caches; no providers were called")
            if inputs.gripper is None and "No joint-state" not in " ".join(
                joint_limitations
            ):
                joint_limitations.append(
                    "Gripper signal unavailable for this job — release inferred "
                    "from tracks alone is weaker."
                )
            if req.image_observations_only:
                report = F.FailureReport(task_id=task.task_id, verdict="uncertain",
                    failure_type=None, earliest_failure=None, physical_events=[],
                    recoveries=[], object_outcomes=[], uncertainties=[
                        "Multi-camera MVP: camera-local image observations only; no static-camera physical-event assumptions.",
                        f"Destination segmentation: {inputs.container_source.get('status', 'unknown')}; a returned footprint does not verify placement."],
                    inputs={"fps": fps, "n_frames": n_frames, "sources": inputs.sources})
                if not inputs.observations:
                    report.uncertainties.append("No object detections returned in this camera window; physical absence is not established.")
            else:
                report = FI.localize_window(inputs, task, include_observation_events=True)
            scope = _apply_analysis_scope(report, complete=req.complete_demonstration,
                                          start=start_f, end=end_f, n_frames=n_frames)
            for u in joint_limitations:
                if u not in report.uncertainties:
                    report.uncertainties.append(u)
            vrep = V.verify_failure_report(
                report.to_dict(),
                observations=inputs.observations,
                container_mask=inputs.container_mask,
                gripper_measured=inputs.gripper.measured if inputs.gripper else None,
                fps=inputs.fps,
                n_frames=inputs.n_frames,
                frame_shape=inputs.frame_shape,
            )
            vdict = vrep.to_dict()
            vdict["ok"] = _verification_accepted(vdict)
            _write_job(job_dir, "failure_report.json", report.to_dict())
            _write_job(job_dir, "verification.json", vdict)
            if not vdict["ok"]:
                raise RuntimeError("Physical evidence verification failed; Muse was not called")
            stage(
                "events_localized",
                verdict=report.verdict,
                n_events=len(report.physical_events),
                verification_ok=vdict.get("ok"),
            )

            tracks_meta = _obs_to_tracks_json(
                inputs.observations,
                fps=fps,
                image_size=(w, h),
                t_start=start_f / fps,
                t_end=end_f / fps,
                source=f"live_job/{req.job_id}",
            )
            if req.image_observations_only:
                for frame_index, detections in tracks_meta["frames"].items():
                    for detection in detections:
                        original = next((o for o in inputs.observations if o.object_id == detection["object_id"] and o.frame_index == int(frame_index)), None)
                        if original is not None:
                            detection["confidence"] = original.confidence
                _write_job(job_dir, "provider_observations.json", {
                    "observations": [asdict(o) for o in inputs.observations],
                    "destination_observations": [asdict(o) for o in rack_obs],
                    "provider_calls": [asdict(c) if is_dataclass(c) else vars(c) for c in calls],
                    "usage_events": usage_events,
                    "coordinate_space": "native camera image pixels; no cross-camera object association"})
            _write_job(job_dir, "tracks.json", tracks_meta)

            overlay_meta = {"available": False, "note":
                            "Use the original video and observed canvas tracks; "
                            "painted-video browser decoding has not been verified."}
            _write_job(job_dir, "sam_overlay.json", overlay_meta)

            pkg = EF.build_evidence_package(
                task_description=req.task_description,
                failure_report=report.to_dict(),
                experiment_id=req.job_id,
                verification=vdict,
                strict_grounding=True,
                analysis_scope=scope,
                context_frames=[start_f, (start_f + end_f - 1) // 2, end_f - 1],
                observations=inputs.observations,
            )
            if req.investigation_questions:
                pkg.provenance["investigation_questions"] = req.investigation_questions
                pkg.tracking_notes.append("Investigation questions are not evidence or success criteria. Address unsupported orientation, placement, completion or grasp/release suggestions only as unverified hypotheses or limitations.")
            _write_job(job_dir, "evidence_package.json", pkg.to_muse_text_dict())

            muse_out = None
            if req.run_muse and not skip_providers:
                if not AI.load_fireworks_api_key():
                    state["errors"].append(
                        "FIREWORKS_API_KEY missing — skipped Muse"
                    )
                    stage("muse_skipped_no_key")
                else:
                    frames = EF.load_package_frames(pkg, dest_video)
                    if not frames:
                        state["errors"].append(
                            "Muse skipped: evidence package has no frame refs"
                        )
                        raise RuntimeError("No context frames could be decoded; Muse was not called")
                    else:
                        muse_est = MUSE_RESERVATION_USD
                        rid_m = budget.reserve(
                            req.budget_job_id or req.job_id, muse_est, note="muse_evidence"
                        )
                        stage(
                            "muse_start",
                            n_frames=len(frames),
                            estimated_usd=muse_est,
                        )
                        muse_out = AI.analyze_with_evidence(
                            pkg, frames, dry_run=False, reasoning_effort="low"
                        )
                        usage = muse_out.get("usage") or {}
                        actual = AI.estimate_cost_usd(usage)
                        budget.commit(
                            rid_m,
                            provider="fireworks_muse",
                            kind="evidence_grounded",
                            actual_usd=actual,
                            usage=usage,
                            from_cache=False,
                            note="analyze_with_evidence",
                        )
                        usage_events.append(
                            {
                                "provider": "fireworks_muse",
                                "kind": "evidence_grounded",
                                "usage": usage,
                                "estimated_usd": actual
                                if actual is not None
                                else muse_est,
                                "paid_call": muse_out.get("paid_call"),
                            }
                        )
                        muse_out["package"] = pkg.to_muse_text_dict()
                        _write_job(
                            job_dir,
                            "muse_result.json",
                            {
                                k: v
                                for k, v in muse_out.items()
                                if k != "package"
                            },
                        )
                        stage(
                            "muse_done",
                            ok=(muse_out.get("validated") or {}).get("ok"),
                            cost_usd=actual,
                        )
                        if actual is None:
                            raise RuntimeError("Muse usage unknown; reconcile charge before another request")

            # Attach evidence catalog from package
            analysis = _analysis_bundle_from_pipeline(
                job_id=req.job_id,
                task_description=req.task_description,
                report=report,
                verification=vdict,
                muse=muse_out,
                tracks_meta=tracks_meta,
                overlay_meta=overlay_meta,
                joint_limitations=joint_limitations,
                window=(start_f, end_f),
                fps=fps,
                package=pkg.to_muse_text_dict(),
                video_duration_s=n_frames / fps,
            )
            text_dict = pkg.to_muse_text_dict()
            cat = []
            for item in text_dict.get("evidence_catalog") or []:
                cat.append(
                    {
                        "evidence_id": item.get("evidence_id") or item.get("id"),
                        "source": item.get("source"),
                        "kind": item.get("kind"),
                        "status_context": item.get("status_context")
                        or item.get("status"),
                        "frame_start": item.get("frame_start"),
                        "frame_end": item.get("frame_end"),
                        "t_start": item.get("t_start"),
                        "t_end": item.get("t_end"),
                        "summary": item.get("summary") or item.get("text"),
                        "claims": item.get("claims") or [],
                    }
                )
            analysis["evidence_catalog"] = cat
            analysis["observed"] = [
                {"text": e["summary"], "evidence_ids": [e["evidence_id"]], "t": e["t_start"]}
                for e in cat if e["kind"] in ("detection", "measurement", "comparison")
                and e["status_context"] == "observed" and e["summary"]
            ]
            analysis["frame_catalog"] = text_dict.get("frame_catalog") or []
            if skip_providers:
                analysis["limitations"].append("Cache-only regression: Muse was not called.")
            from criteria_presentation import for_analysis
            analysis["criteria"] = for_analysis(analysis, n_frames=n_frames, fps=fps,
                object_concept=req.object_concept, destination=req.destination_concept)
            _write_job(job_dir, "failure_report.json", report.to_dict())
            _write_job(job_dir, "verification.json", vdict)
            _write_job(job_dir, "analysis.json", analysis)
            _write_job(job_dir, "tracks.json", tracks_meta)

        bstat = budget.status()
        spent_job = sum(
            float(e.get("estimated_usd") or 0)
            for e in usage_events
            if not e.get("from_cache")
        )
        state.update(
            {
                "status": "completed",
                "finished_at": time.time(),
                "usage_events": usage_events,
                "cost": {
                    "job_estimated_usd": round(spent_job, 6),
                    "ledger": bstat,
                },
                "result_paths": {
                    "analysis": "analysis.json",
                    "tracks": "tracks.json",
                    "overlay": overlay_meta.get("video"),
                    "video": "video.mp4",
                },
                "joint_limitations": joint_limitations,
                "window_frames": [start_f, end_f],
            }
        )
        _write_job(job_dir, "status.json", state)
        stage("completed")
        return state

    except Exception as e:
        state["status"] = "failed"
        state["errors"].append(str(e))
        state["traceback"] = traceback.format_exc()
        state["finished_at"] = time.time()
        state["cost"]["ledger"] = budget.status()
        _write_job(job_dir, "status.json", state)
        _progress(progress, "failed", error=str(e))
        return state


def new_job_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
