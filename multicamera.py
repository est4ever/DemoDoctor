"""Local multi-view preparation and orchestration of the existing inference pipeline.

No cross-camera object matching or physical-event reconstruction is performed.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import time

import av
from pydantic import BaseModel, ConfigDict, Field, model_validator

import live_pipeline as lp
import live_budget as budget
import evidence_fusion as ef
from vision import SampledFrame


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    object_concept: str = Field(min_length=1, max_length=200)
    destination_concept: str = Field(min_length=1, max_length=200)
    motion: str = Field(default="unknown", pattern="^(static|moving|unknown)$")
    offset_s: float = Field(default=0, ge=-60, le=60, allow_inf_nan=False)
    crop: tuple[int, int, int, int] | None = None


class LayoutProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str = Field(pattern="^(dark-gutters|equal-panels)$")
    axis: str = Field(pattern="^(horizontal|vertical)$")
    rectangles: list[tuple[int,int,int,int]] = Field(min_length=1,max_length=3)
    preview_time_s: float = Field(default=0,ge=0,allow_inf_nan=False)
    note: str = Field(max_length=1000)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_mode: str = Field(pattern="^(composite|separate)$")
    cameras: list[Camera] = Field(min_length=1, max_length=3)
    task_description: str = Field(min_length=1, max_length=2000)
    alignment_confirmed: bool = False
    alignment_basis: str = Field(default="", max_length=1000)
    crops_confirmed: bool = False
    layout_proposal: LayoutProposal | None = None
    investigation_questions: str = Field(default="",max_length=2000)
    window_start_s: float = Field(default=0, ge=0, allow_inf_nan=False)
    window_end_s: float = Field(default=4, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_plan(self):
        if not 0 < self.window_end_s - self.window_start_s <= 30:
            raise ValueError("Select a shared window of at most 30 seconds")
        if not self.task_description.strip() or any(not c.name.strip() or not c.object_concept.strip() or not c.destination_concept.strip() for c in self.cameras):
            raise ValueError("Names, task and prompts must not be blank")
        if len({c.name.strip().casefold() for c in self.cameras}) != len(self.cameras):
            raise ValueError("Camera names must be distinct")
        if self.source_mode == "composite":
            if not self.crops_confirmed or any(c.crop is None or c.offset_s != 0 for c in self.cameras):
                raise ValueError("Composite crops must be confirmed and inherit zero offsets")
            for i, a in enumerate(self.cameras):
                ax, ay, aw, ah = a.crop
                for b in self.cameras[i+1:]:
                    bx, by, bw, bh = b.crop
                    if max(ax,bx)<min(ax+aw,bx+bw) and max(ay,by)<min(ay+ah,by+bh):
                        raise ValueError("Composite camera panels must not overlap")
        elif len(self.cameras)>1 and (not self.alignment_confirmed or len(self.alignment_basis.strip()) < 8):
            raise ValueError("Separate sources require explicitly approved alignment and its basis")
        elif any(c.crop is not None for c in self.cameras):
            raise ValueError("Separate sources are already individual camera views")
        return self


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path):
    """Decoded PTS, not nominal duration, defines the retained frame mapping."""
    with av.open(str(path)) as media:
        stream = media.streams.video[0]
        fps = float(stream.average_rate or 0)
        width, height = stream.width, stream.height
        if not math.isfinite(fps) or not 0 < fps <= 120 or not 0 < width <= 8192 or not 0 < height <= 4320:
            raise ValueError("Unsupported frame rate or native video dimensions")
        pts = []
        for frame in media.decode(stream):
            if frame.pts is None:
                raise ValueError("Source frame has no presentation timestamp")
            pts.append(float(frame.pts * frame.time_base))
            if len(pts) > 36000:
                raise ValueError("MVP source limit: 36,000 frames")
        if not pts or pts[-1] - pts[0] > 300:
            raise ValueError("Use a complete source of at most five minutes")
        if abs(pts[0]) > 1e-6:
            raise ValueError("MVP requires zero-origin source PTS; nonzero timestamps are not silently rebased")
        if any(abs((b-a)-1/fps) > max(1e-5, 1/fps * .001) for a, b in zip(pts, pts[1:])):
            raise ValueError("MVP requires constant-rate, monotonic PTS; no frames will be interpolated")
        return {"width": width, "height": height, "fps": fps, "n_frames": len(pts),
                "timestamps_s": pts, "duration_s": pts[-1] + 1/fps,
                "time_base": str(stream.time_base), "time_base_denominator": stream.time_base.denominator}


def crop_video(source: Path, target: Path, rect, meta):
    x, y, w, h = rect
    if min(x, y) < 0 or min(w, h) < 16 or any(v % 2 for v in rect) or x+w > meta["width"] or y+h > meta["height"]:
        raise ValueError("Crop must use even pixel boundaries within the native source image, minimum 16×16")
    ffmpeg = os.environ.get("DEMODOCTOR_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg or not Path(ffmpeg).is_file():
        raise ValueError("Composite extraction needs an installed FFmpeg executable on backend PATH or DEMODOCTOR_FFMPEG")
    result = subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-y", "-noautorotate",
        "-copyts", "-i", str(source), "-map", "0:v:0", "-an", "-vf", f"crop={w}:{h}:{x}:{y}:exact=1",
        "-fps_mode", "passthrough", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-video_track_timescale", str(meta["time_base_denominator"]),
        "-movflags", "+faststart", str(target)], capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError("FFmpeg crop failed; no providers were called")
    out = probe(target)
    if (out['width'],out['height']) != (w,h) or out["n_frames"] != meta["n_frames"] or any(abs(a-b) > 1e-6 for a, b in zip(out["timestamps_s"], meta["timestamps_s"])):
        target.unlink(missing_ok=True)
        raise ValueError("Crop dimensions/frame-count/PTS mismatch; extraction rejected")
    return out


def prepare(directory: Path, plan: Manifest, filenames: list[str]):
    sources = []
    for i, filename in enumerate(filenames):
        path = directory/f"source{i+1}.mp4"
        sources.append({"source_video_id": f"source{i+1}", "filename": filename,
                        "sha256": digest(path), **probe(path)})
    cameras = []
    for i, config in enumerate(plan.cameras):
        cid = f"cam{i+1}"
        source = sources[0 if plan.source_mode == "composite" else i]
        camera_dir = directory/cid
        camera_dir.mkdir()
        source_path = directory/(source["source_video_id"]+".mp4")
        video = camera_dir/"video.mp4"
        if config.crop:
            meta = crop_video(source_path, video, config.crop, source)
        else:
            shutil.copyfile(source_path, video)
            meta = {k: source[k] for k in ("width", "height", "fps", "n_frames", "timestamps_s", "duration_s", "time_base")}
        camera = {"camera_id": cid, **config.model_dump(), **meta,
                  "source_video_id": source["source_video_id"], "source_sha256": source["sha256"],
                  "sha256": digest(video), "encoding": "FFmpeg H.264 CRF18; lossy spatial crop, no frame interpolation" if config.crop else "Original source bytes",
                  "track_identity": "camera-local only; never matched across cameras"}
        cameras.append(camera)
    shared_start = max(0., *[-c["offset_s"] for c in cameras])
    shared_end = min(c["duration_s"]-c["offset_s"] for c in cameras)
    duration = shared_end-shared_start
    if duration <= 0 or plan.window_end_s > duration + 1e-6:
        raise ValueError(f"Selected window exceeds common aligned interval ({max(0,duration):.3f}s)")
    for c in cameras:
        c["playback_offset_s"] = shared_start+c["offset_s"]
        # No resampling: include only native frames whose timestamp is in the approved shared window.
        start = math.ceil((plan.window_start_s+c["playback_offset_s"])*c["fps"]-1e-7)
        end = math.ceil((plan.window_end_s+c["playback_offset_s"])*c["fps"]-1e-7)
        if not 0 <= start < end <= c["n_frames"]:
            raise ValueError("Empty or invalid aligned camera frame window")
        c["frame_start"], c["frame_end"] = start, end
        c["sam_estimate_usd"] = budget.estimate_sam_window_usd(end-start, c["fps"])+budget.estimate_sam_image_usd()
        c["operations"] = ["At most 1 Meta file upload", "1 SAM object-video request", "1 SAM destination-image request"]
        c["frame_mapping"] = [{"camera_frame": j, "source_frame": j, "source_timestamp_s": ts,
                               "shared_timestamp_s": ts-c["playback_offset_s"]} for j, ts in enumerate(c["timestamps_s"])]
        lp._write_job(directory/c["camera_id"], "provenance.json", c)
    manifest = {"schema_version": 1, "source_mode": plan.source_mode, "sources": sources,
        "cameras": cameras, "duration_s": duration, "shared_origin_s": shared_start,
        "alignment": {"kind": "shared source PTS" if plan.source_mode == "composite" else "user-approved alignment, not independently certified",
                      "basis": plan.alignment_basis, "convention": "camera elapsed = player shared time + playback_offset_s"},
        "task_description": plan.task_description, "investigation_questions": plan.investigation_questions,
        "layout_proposal": plan.layout_proposal.model_dump() if plan.layout_proposal else None,
        "window_start_s": plan.window_start_s, "window_end_s": plan.window_end_s,
        "limitations": ["Independent camera-local image-space evidence only; no cross-camera object identity.",
                       "No calibrated 3D, verified orientation, grasp, release or whole-task outcome.",
                       "Moving/unknown camera motion does not establish physical object travel.",
                       "Cross-view agreement or disagreement is an unverified interpretation, not a physical measurement."]}
    if plan.source_mode == "separate" and len({s["sha256"] for s in sources}) < len(sources):
        manifest["limitations"].append("At least two uploaded sources have identical bytes; these are not independent camera angles.")
    lp._write_job(directory, "multicamera.json", manifest)
    return manifest


def combined_package(directory, manifest, dry_run):
    from task_actions import select_context_frames, parse_task
    items, refs, frames, citations, frame_sources = [], [], [], {}, {}
    for c in manifest["cameras"]:
        cid = c["camera_id"]
        child = directory/cid
        original = read(child/"evidence_package.json") if not dry_run else {"evidence_catalog": []}
        id_map = {}
        for e in original["evidence_catalog"]:
            eid = f"E{len(items)}"
            id_map[e["evidence_id"]] = eid
            citations[eid] = {"camera_id": cid, "camera_name": c["name"], "original_evidence_id": e["evidence_id"],
                             "source_video_id": c["source_video_id"], "package": f"{cid}/evidence_package.json"}
            original_e = copy.deepcopy(e)
            original_e["evidence_id"] = eid
            original_e["summary"] = f"[{cid} — {c['name']}] {e['summary']}"
            original_e["note"] = f"Original {cid}/{e['evidence_id']}; source timestamps/frames are camera-local; see provenance.json"
            # Package times are shared; original numeric measurement claims remain untouched.
            for k in ("t_start", "t_end"):
                if original_e.get(k) is not None:
                    original_e[k] -= c["playback_offset_s"]
            items.append(ef.EvidenceItem(**original_e))
        if not dry_run:
            observed = read(child/'provider_observations.json').get('observations', [])
            for frame_index in select_context_frames(c, observed, 6 // len(manifest['cameras'])):
                fref = f"F{len(refs)}"
                original_time = c["timestamps_s"][frame_index]
                refs.append(ef.FrameRef(fref, frame_index, original_time-c["playback_offset_s"],
                    list(id_map.values()), f"context camera={cid} name={c['name']} original_frame={frame_index} source_time={original_time}"))
                rgb = lp.T.extract_frame_rgb((child/"video.mp4").read_bytes(), frame_index)
                # Match the existing bounded context-image preparation.
                import cv2
                if rgb.shape[1] > 768:
                    rgb = cv2.resize(rgb, (768, max(1, round(rgb.shape[0]*768/rgb.shape[1]))))
                frames.append(SampledFrame(timestamp_s=refs[-1].timestamp_s, rgb=rgb))
                frame_sources[fref] = {"camera_id": cid, "source_video_id": c["source_video_id"],
                                      "original_frame": frame_index, "original_timestamp_s": original_time}
    pkg = ef.EvidencePackage(task_id="multicamera_image_space", task_description=manifest["task_description"],
        experiment_id=directory.name, provenance={"strict_grounding": True, "analysis_scope": {"complete_demonstration": False},
            "camera_citations": citations, "frame_sources": frame_sources, "alignment": manifest["alignment"],
            "task_subgoals": [asdict(s) for s in parse_task(manifest['task_description'], manifest['cameras'][0]['object_concept'], manifest['cameras'][0]['destination_concept']).criteria if s.kind == 'action'],
            "investigation_questions": manifest.get("investigation_questions", "")},
        deterministic_verdict="uncertain", failure_type=None, earliest_failure=None, physical_events=[],
        evidence_items=items, uncertainties=manifest["limitations"], final_state=None, frame_refs=refs,
        tracking_notes=["Do not associate camera-local track IDs across views. Describe candidate cross-view consistency/disagreement only as unverified hypotheses.",
                        "Address every explicit task_subgoal, including actions such as closing a drawer. Cite original frame_refs for candidate visual interpretations; missing intermediate frames or articulated-state measurements leave the subgoal unverified. Context is not a verified action predicate.",
                        "Address investigation_questions about placement, orientation, incomplete manipulation and missing observations conservatively. A question is not a success criterion or evidence; unsupported mechanisms belong only in hypotheses or limitations.",
                        "Factual claims must exactly copy one cited camera-labeled evidence summary."],
        identity_caveat="Track IDs belong only to their camera and SAM request; cross-camera physical identity is unverified.")
    return pkg, frames


def run(directory: Path, manifest, dry_run, progress=None):
    state = {"job_id": directory.name, "status": "running", "dry_run": dry_run, "stages": [], "errors": []}
    def stage(name, **info):
        state["stages"].append({"name": name, **info})
        lp._write_job(directory, "status.json", state)
    try:
        approved_total = sum(c["sam_estimate_usd"] for c in manifest["cameras"])+lp.MUSE_RESERVATION_USD
        def check_remaining_estimate(remaining_sam):
            if dry_run:
                return
            ledger = budget.load_ledger()
            spent = sum(float(e.get("actual_usd") if e.get("actual_usd") is not None else e.get("estimated_usd",0))
                        for e in ledger.get("events",[]) if e.get("job_id")==directory.name and not e.get("from_cache"))
            if spent+remaining_sam+lp.MUSE_RESERVATION_USD > approved_total+1e-6:
                raise RuntimeError("Updated remaining estimate exceeds the approved plan; stopped before another provider request")
        # Each child uses the unchanged SAM adapter/pipeline, never parallel paid requests.
        original_root = lp.JOBS_ROOT
        for i, c in enumerate(manifest["cameras"]):
            check_remaining_estimate(sum(v["sam_estimate_usd"] for v in manifest["cameras"][i:]))
            cid = c["camera_id"]
            # The pipeline uses job_id for its directory. Camera directories are children of the parent job.
            req = lp.AnalyzeRequest(job_id=f"{directory.name}/{cid}", video_path=directory/cid/"video.mp4",
                task_description=f"Camera {cid} ({c['name']}, motion={c['motion']}): {manifest['task_description']}",
                object_concept=c["object_concept"], destination_concept=c["destination_concept"],
                window_start_s=c["frame_start"]/c["fps"], window_end_s=c["frame_end"]/c["fps"],
                run_muse=False, dry_run=dry_run, image_observations_only=True, budget_job_id=directory.name)
            if directory.parent != original_root:
                raise RuntimeError("Multi-camera job root mismatch")
            def camera_progress(name, info):
                stage(f"{cid}: {name}", camera_id=cid)
                remaining_sam = sum(v["sam_estimate_usd"] for v in manifest["cameras"][i+1:])
                # Recheck immediately after each charge, before the next provider.
                if name == "sam_window_done":
                    check_remaining_estimate(remaining_sam+budget.estimate_sam_image_usd())
                elif name == "sam_destination_done":
                    check_remaining_estimate(remaining_sam)
            result = lp.run_analyze(req, camera_progress)
            if result["status"] != "completed":
                raise RuntimeError(f"{cid} stopped: {'; '.join(result['errors'])}; remaining cameras and Muse skipped")
            tracks = read(directory/cid/"tracks.json")
            tracks["camera_id"], tracks["source_video_id"] = cid, c["source_video_id"]
            tracks["camera_provenance"] = c
            lp._write_job(directory/cid, "tracks.json", tracks)
            raw_path = directory/cid/"provider_observations.json"
            if raw_path.is_file():
                raw = read(raw_path)
                raw["provenance"] = c
                for o in raw["observations"]:
                    o.update(camera_id=cid, source_video_id=c["source_video_id"],
                             source_frame=o["frame_index"], original_timestamp_s=o["timestamp_s"],
                             native_image_dimensions=[c["width"],c["height"]])
                lp._write_job(directory/cid, "provider_observations.json", raw)
            stage(f"{cid}: completed", camera_id=cid)
        pkg, frames = combined_package(directory, manifest, dry_run)
        lp._write_job(directory, "evidence_package.json", pkg.to_muse_text_dict())
        muse = None
        if not dry_run:
            check_remaining_estimate(0)
            rid = budget.reserve(directory.name, lp.MUSE_RESERVATION_USD, note="multi-camera Muse evidence explanation")
            stage("Muse combined camera-labeled evidence")
            muse = lp.AI.analyze_with_evidence(pkg, frames, dry_run=False, reasoning_effort="low")
            actual = lp.AI.estimate_cost_usd(muse.get("usage") or {})
            budget.commit(rid, provider="fireworks_muse", kind="multicamera_evidence", actual_usd=actual, usage=muse.get("usage") or {})
            lp._write_job(directory, "muse_result.json", muse)
            if actual is None or not (muse.get("validated") or {}).get("ok"):
                raise RuntimeError("Muse usage or strict citation validation failed; no combined result published")
        # Preserve the original camera packages; display IDs are explicitly mapped back to them.
        a = read(directory/"cam1/analysis.json")
        validated = (muse or {}).get("validated") or {}
        catalog = [asdict(e) | pkg.provenance["camera_citations"][e.evidence_id] for e in pkg.evidence_items]
        camera_unknowns = [f"[{c['camera_id']} — {c['name']}] {text}" for c in manifest["cameras"] for text in read(directory/c["camera_id"]/"analysis.json").get("unknowns", [])]
        from task_actions import camera_coverage
        coverage = [camera_coverage(c, read(directory/c['camera_id']/'provider_observations.json').get('observations', [])) for c in manifest['cameras']] if not dry_run else []
        context = [{**asdict(f), **pkg.provenance['frame_sources'][f.frame_ref], 'shared_timestamp_s': f.timestamp_s,
                    'scope': 'Original frame context only; not independent criterion verification'} for f in pkg.frame_refs]
        a.update(episode_key="multicamera", title="Multi-camera image-space investigation", dry_run=dry_run,
            task=manifest["task_description"], task_outcome="uncertain", pipeline_verdict="uncertain", outcome_label="Uncertain",
            diagnosis_headline="Dry run · providers skipped" if dry_run else "Independent camera observations · outcome uncertain",
            diagnosis_summary="No physical conclusions: SAM/Muse were skipped." if dry_run else "Camera-local detections and one strictly cited Muse explanation. Cross-view identity and task completion remain unverified.",
            physical_events=[], inferred=[], earliest_failure=None, highlight_interval=None, release_interval=None,
            evidence_catalog=catalog, frame_catalog=[asdict(f) | pkg.provenance["frame_sources"][f.frame_ref] for f in pkg.frame_refs],
            observed=[{"text": e["summary"], "evidence_ids": [e["evidence_id"]], "t": e["t_start"]} for e in catalog if e["kind"]=="detection" and e["status_context"]=="observed"],
            timeline_markers=[{"id": e["evidence_id"], "label": e["summary"], "kind": e["kind"], "t": e["t_start"], "evidence_ids": [e["evidence_id"]]} for e in catalog if e["t_start"] is not None],
            hypotheses=validated.get("hypotheses", []), visual_interpretations=validated.get("visual_interpretations", []),
            factual_claims=validated.get("factual_claims", []), muse_explanation=validated.get("explanation"),
            unknowns=manifest["limitations"]+camera_unknowns, limitations=manifest["limitations"]+validated.get("limitations", []),
            initial_seek_s=manifest["window_start_s"], multicamera=manifest,
            analysis_coverage=coverage, criterion_frame_context=context,
            video={"rel": "", "duration_s": manifest["duration_s"], "primary_evidence": True})
        from criteria_presentation import for_analysis
        a["criteria"] = for_analysis(a, n_frames=manifest["cameras"][0]["n_frames"],
            fps=manifest["cameras"][0]["fps"], object_concept=manifest["cameras"][0]["object_concept"],
            destination=manifest["cameras"][0]["destination_concept"], dry_run=dry_run)
        lp._write_job(directory, "analysis.json", a)
        lp._write_job(directory, "tracks.json", read(directory/"cam1/tracks.json"))
        state["status"] = "completed"
        stage("completed")
    except Exception as exc:
        state["status"] = "failed"
        state["errors"].append(str(exc))
        lp._write_job(directory, "status.json", state)
    return state
