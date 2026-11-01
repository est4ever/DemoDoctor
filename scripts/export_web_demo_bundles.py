"""Export read-only web demo bundles for ep010 / ep003 / ep005 / ep013 / ep006.

Frozen experiment artifacts only. No paid APIs. Videos copied locally (gitignored).
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proprio import load_episode  # noqa: E402

DATASET = ROOT / "data" / "lerobot" / "kantine__BotFails" / "test" / "domotic_dishTidyUp_anomaly"
OUT_ROOT = ROOT / "web" / "public" / "data"

URDF_JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
LIMITS = {
    "shoulder_pan": (-2.0, 2.0),
    "shoulder_lift": (0.0, 3.5),
    "elbow_flex": (-3.14158, 0.0),
    "wrist_flex": (-2.5, 1.2),
    "wrist_roll": (-3.14158, 3.14158),
    "gripper": (-0.2, 2.0),
}

AVAILABLE = [
    {"key": "ep010", "label": "ep010 — suspected release (dev)", "enabled": True},
    {
        "key": "ep005",
        "label": "ep005 — Muse-only false success vs evidence uncertainty",
        "enabled": True,
    },
    {"key": "ep003", "label": "ep003 — evidence-supported success", "enabled": True},
    {"key": "ep013", "label": "ep013 — evidence-supported failure", "enabled": True},
    {"key": "ep006", "label": "ep006 — optional abstention example", "enabled": True},
]


def motor_to_urdf_rad(state_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """BotFails motor degrees → stock SO-100 URDF radians.

    Dataset motors are degrees (LeRobot-style). Stock URDF zeros/signs differ from
    LeRobot mid-range calibration (see TheRobotStudio/SO-ARM100#94, Foxglove notes).

    For this BotFails encoding we keep Foxglove's shoulder_pan negation, map
    shoulder_lift / wrist_roll with +deg2rad, and negate both elbow_flex and
    wrist_flex so values land in the stock URDF limit ranges without widening
    limits. Gripper is treated as ~0–100 open fraction → [0, π] rad.
    Absolute zero offsets remain unknown without a BotFails URDF calibration.
    """
    d = state_deg
    raw = np.stack(
        [
            -np.deg2rad(d[:, 0]),  # shoulder_pan
            np.deg2rad(d[:, 1]),  # shoulder_lift
            -np.deg2rad(d[:, 2]),  # elbow_flex (URDF upper=0)
            -np.deg2rad(d[:, 3]),  # wrist_flex (was +; caused mass clamping)
            np.deg2rad(d[:, 4]),  # wrist_roll
            (d[:, 5] / 100.0) * math.pi,  # gripper open fraction
        ],
        axis=1,
    )
    clamped = raw.copy()
    for i, name in enumerate(URDF_JOINTS):
        lo, hi = LIMITS[name]
        clamped[:, i] = np.clip(raw[:, i], lo, hi)
    return clamped, raw


def export_joints(episode_index: int, episode_key: str, out: Path) -> dict[str, Any]:
    ep = load_episode(DATASET, episode_index)
    clamped, raw = motor_to_urdf_rad(ep.state)
    ool = {
        name: int(np.sum((raw[:, i] < LIMITS[name][0]) | (raw[:, i] > LIMITS[name][1])))
        for i, name in enumerate(URDF_JOINTS)
    }
    joints = {
        "episode_key": episode_key,
        "robot_type": "so100",
        "fps": ep.fps,
        "n_frames": int(len(ep.timestamp_s)),
        "dataset_joint_names": ep.joint_names,
        "urdf_joint_names": URDF_JOINTS,
        "timestamps_s": ep.timestamp_s.astype(float).tolist(),
        "motor_deg": ep.state.astype(float).round(4).tolist(),
        "urdf_rad": clamped.astype(float).round(5).tolist(),
        "urdf_rad_unclamped_stats": {
            name: {
                "min": float(raw[:, i].min()),
                "max": float(raw[:, i].max()),
                "out_of_limit_frames": ool[name],
                "limits": list(LIMITS[name]),
            }
            for i, name in enumerate(URDF_JOINTS)
        },
    }
    (out / "joints.json").write_text(json.dumps(joints), encoding="utf-8")
    mapping = {
        "urdf_source": {
            "repo": "https://github.com/TheRobotStudio/SO-ARM100",
            "path": "Simulation/SO100/so100.urdf",
            "license": "Apache-2.0",
            "local": "web/public/robots/so100/",
        },
        "dataset": {
            "robot_type": "so100",
            "repo": "kantine/BotFails",
            "units": "degrees for arm joints; gripper ~0–100 open fraction",
            "names": ep.joint_names,
        },
        "transform": [
            {"dataset": "main_shoulder_pan", "urdf": "shoulder_pan", "formula": "urdf = -deg2rad(motor)"},
            {"dataset": "main_shoulder_lift", "urdf": "shoulder_lift", "formula": "urdf = deg2rad(motor)"},
            {"dataset": "main_elbow_flex", "urdf": "elbow_flex", "formula": "urdf = -deg2rad(motor)"},
            {
                "dataset": "main_wrist_flex",
                "urdf": "wrist_flex",
                "formula": "urdf = -deg2rad(motor)",
            },
            {"dataset": "main_wrist_roll", "urdf": "wrist_roll", "formula": "urdf = deg2rad(motor)"},
            {"dataset": "main_gripper", "urdf": "gripper", "formula": "urdf = (motor/100)*pi"},
        ],
        "known_limitations": [
            "Experimental BotFails→URDF mapping: absolute zero offsets vs stock SO-100 URDF are unknown.",
            "elbow_flex and wrist_flex use -deg2rad so BotFails motor ranges fit stock URDF limits (no limit widening).",
            "Gripper URDF is revolute; LeRobot gripper is ~0–100 open fraction.",
            "No scene meshes or plate poses — 3D is joint-driven visualization only; trust the camera for physical claims.",
        ],
        "out_of_limit_frames": ool,
        "available": True,
    }
    (out / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    return {"fps": ep.fps, "ool": ool, "n_frames": len(ep.timestamp_s)}


def copy_video(episode_index: int, out: Path) -> None:
    src = ROOT / "eval_videos" / "botfails" / f"botfails_dish_test_ep{episode_index:03d}.mp4"
    dst = out / "video.mp4"
    if not src.is_file():
        print("WARNING: missing video", src)
        return
    if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
        print("copied", src.name, dst.stat().st_size, "bytes")
    else:
        print("video ok", src.name)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


# High-contrast palette for green-plate scenes (avoid camouflage greens).
_SAM_STYLE_VERSION = 2
_SAM_CONTRAST_COLORS = [
    (0, 220, 255),  # cyan
    (255, 0, 200),  # magenta
    (255, 210, 0),  # gold
    (80, 120, 255),  # blue
    (255, 110, 40),  # orange
]


def _object_color(object_id: str | None, palette: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    key = object_id or "object"
    return palette[sum(ord(c) for c in key) % len(palette)]


def _paint_contrast_mask(
    rgb: Any,
    mask_rle: dict[str, Any],
    bbox: tuple[float, float, float, float],
    color: tuple[int, int, int],
    *,
    label: str,
    confidence: float | None,
) -> bool:
    """Tint + thick outline + ID label from frozen RLE (web demo viz only)."""
    import cv2
    import numpy as np

    import tracking as T

    try:
        mask = T.mask_in_frame(mask_rle, bbox, rgb.shape[:2])
    except Exception:  # noqa: BLE001
        return False
    if mask is None or not mask.any():
        return False
    alpha = 0.55
    tint = np.array(color, dtype=np.float32)
    rgb[mask] = ((1 - alpha) * rgb[mask].astype(np.float32) + alpha * tint).astype(np.uint8)
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    cv2.drawContours(rgb, contours, -1, color, 2, cv2.LINE_AA)
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    cv2.rectangle(rgb, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
    conf_txt = f" {confidence:.2f}" if isinstance(confidence, (int, float)) else ""
    text = f"{label}{conf_txt}"
    tx, ty = x1, max(14, y1 - 4)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(rgb, (tx - 2, ty - th - 4), (tx + tw + 2, ty + 2), (0, 0, 0), -1)
    cv2.putText(
        rgb,
        text,
        (tx, ty),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )
    return True


def export_sam_overlay(episode_key: str, episode_index: int, out: Path, fps: float) -> dict[str, Any]:
    """Paint frozen demo_cache SAM window masks onto the camera video (no API).

    Writes overlay.mp4 (full length; masks only on cached frames) + sam_overlay.json.
    Uses high-contrast per-object colors so green plates stay distinguishable.
    """
    import cv2

    cache = ROOT / "data" / "demo_cache" / episode_key / "sam_window" / "green_plate.json"
    video_src = out / "video.mp4"
    overlay_path = out / "overlay.mp4"
    meta_path = out / "sam_overlay.json"
    unavailable = {
        "available": False,
        "reason": "no frozen SAM window cache",
        "source": str(cache.relative_to(ROOT)).replace("\\", "/"),
    }
    if not cache.is_file() or not video_src.is_file():
        meta_path.write_text(json.dumps(unavailable, indent=2) + "\n", encoding="utf-8")
        print("sam overlay unavailable", episode_key)
        return unavailable

    payload = _read(cache)
    obs = payload.get("observations") or []
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for rec in obs:
        fi = rec.get("frame_index")
        if not isinstance(fi, int):
            continue
        by_frame.setdefault(fi, []).append(rec)
    if not by_frame:
        unavailable["reason"] = "SAM cache has no observations"
        meta_path.write_text(json.dumps(unavailable, indent=2) + "\n", encoding="utf-8")
        return unavailable

    frames = sorted(by_frame)
    f0, f1 = frames[0], frames[-1]
    object_ids = sorted(
        {str(r.get("object_id") or "object") for rows in by_frame.values() for r in rows}
    )
    legend = [
        {
            "object_id": oid,
            "color_rgb": list(_object_color(oid, _SAM_CONTRAST_COLORS)),
        }
        for oid in object_ids
    ]
    existing_meta = _read(meta_path) if meta_path.is_file() else {}
    # Skip rebuild when contrast-styled H.264 overlay is current
    if (
        overlay_path.is_file()
        and existing_meta.get("available")
        and existing_meta.get("codec") == "libx264"
        and existing_meta.get("style_version") == _SAM_STYLE_VERSION
        and overlay_path.stat().st_mtime >= cache.stat().st_mtime
        and overlay_path.stat().st_mtime >= video_src.stat().st_mtime
        and overlay_path.stat().st_size > 1_000_000
    ):
        existing_meta["skipped_rebuild"] = True
        existing_meta["legend"] = legend
        meta_path.write_text(json.dumps(existing_meta, indent=2) + "\n", encoding="utf-8")
        print("sam overlay ok (cached contrast)", episode_key, f0, f1)
        return existing_meta

    import av

    cap = cv2.VideoCapture(str(video_src))
    if not cap.isOpened():
        unavailable["reason"] = "could not open video.mp4"
        meta_path.write_text(json.dumps(unavailable, indent=2) + "\n", encoding="utf-8")
        return unavailable
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or fps)
    tmp = out / "_overlay_tmp.mp4"
    container = av.open(str(tmp), mode="w")
    stream = container.add_stream("libx264", rate=int(round(src_fps)) or 30)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "23", "preset": "veryfast"}
    painted_frames = 0
    idx = 0
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        if idx in by_frame:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            for rec in by_frame[idx]:
                mask_rle = rec.get("mask_rle")
                bbox = rec.get("bbox")
                if not mask_rle or not bbox:
                    continue
                oid = str(rec.get("object_id") or "object")
                short = oid.replace("green plate:", "plate:")
                color = _object_color(oid, _SAM_CONTRAST_COLORS)
                _paint_contrast_mask(
                    rgb,
                    mask_rle,
                    tuple(bbox),
                    color,
                    label=short,
                    confidence=rec.get("confidence"),
                )
            # Corner banner: in-window only
            cv2.rectangle(rgb, (8, 8), (292, 36), (0, 0, 0), -1)
            cv2.putText(
                rgb,
                "SAM window (frozen cache)",
                (14, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 220, 255),
                1,
                cv2.LINE_AA,
            )
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            painted_frames += 1
        frame = av.VideoFrame.from_ndarray(bgr, format="bgr24")
        for packet in stream.encode(frame):
            container.mux(packet)
        idx += 1
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    cap.release()
    if tmp.is_file():
        if overlay_path.is_file():
            overlay_path.unlink()
        tmp.replace(overlay_path)
    meta = {
        "available": True,
        "source": str(cache.relative_to(ROOT)).replace("\\", "/"),
        "concept": "green plate",
        "frame_start": f0,
        "frame_end": f1,
        "t_start": float(f0) / fps,
        "t_end": float(f1) / fps,
        "n_observations": len(obs),
        "n_frames_with_masks": len(by_frame),
        "painted_frames": painted_frames,
        "total_frames_written": idx,
        "video": "overlay.mp4",
        "codec": "libx264",
        "style_version": _SAM_STYLE_VERSION,
        "legend": legend,
        "note": (
            "High-contrast masks painted from frozen data/demo_cache SAM window only "
            "(cyan/magenta/gold — not object color). Outside this window there is no "
            "segmentation: the overlay matches the original camera."
        ),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(
        "sam overlay wrote",
        episode_key,
        painted_frames,
        "painted /",
        idx,
        "frames",
        overlay_path.stat().st_size,
        "bytes",
        "contrast-h264",
    )
    return meta


def export_ep010() -> None:
    out = OUT_ROOT / "ep010"
    out.mkdir(parents=True, exist_ok=True)
    meta = export_joints(10, "ep010", out)
    fps = meta["fps"]
    fr = _read(ROOT / "data/experiments/botfails_ep010_w1260_v2/failure_report.json")
    muse = _read(ROOT / "data/experiments/botfails_ep010_w1260_v2_muse_pilot/validated_explanation.json")
    muse_only = _read(ROOT / "data/experiments/botfails_ep010_muse_only_matched_frames/structured_prediction.json")

    evidence_catalog = []
    eid = 0
    events = []
    for ev in fr.get("physical_events") or []:
        eids = []
        for block in ev.get("evidence") or []:
            fs = block.get("frame_start")
            evidence_catalog.append(
                {
                    "evidence_id": f"E{eid}",
                    "source": block.get("source"),
                    "kind": block.get("kind"),
                    "status_context": ev.get("status"),
                    "frame_start": fs,
                    "frame_end": block.get("frame_end"),
                    "t_start": float(fs) / fps if isinstance(fs, int) else None,
                    "t_end": float(block["frame_end"]) / fps if isinstance(block.get("frame_end"), int) else None,
                    "summary": block.get("summary"),
                    "claims": block.get("claims") or [],
                }
            )
            eids.append(f"E{eid}")
            eid += 1
        events.append(
            {
                "id": f"event_{len(events)}",
                "kind": ev.get("kind"),
                "subtype": ev.get("subtype"),
                "status": ev.get("status"),
                "t_start": ev.get("t_start"),
                "t_end": ev.get("t_end"),
                "frame_start": ev.get("frame_start"),
                "frame_end": ev.get("frame_end"),
                "inference": ev.get("inference"),
                "uncertainties": ev.get("uncertainties") or [],
                "evidence_ids": eids,
            }
        )
    for note in (fr.get("uncertainties") or [])[:2]:
        evidence_catalog.append(
            {
                "evidence_id": f"E{eid}",
                "source": "pipeline:report",
                "kind": "derived",
                "status_context": "uncertain",
                "frame_start": None,
                "frame_end": None,
                "t_start": None,
                "t_end": None,
                "summary": str(note)[:400],
                "claims": [],
            }
        )
        eid += 1

    analysis = {
        "episode_key": "ep010",
        "title": "Dish tidy-up · development episode",
        "task": "Store green plates in the dish rack",
        "split": "development",
        "available_episodes": AVAILABLE,
        "has_joint_animation": True,
        "pipeline_verdict": fr.get("verdict"),
        "task_outcome": muse.get("task_outcome") or fr.get("verdict"),
        "outcome_label": "Uncertain — insufficient to certify success or failure",
        "diagnosis_headline": "Suspected plate release outside the rack",
        "diagnosis_summary": (
            "Around 43–45s the green plate is moved and comes to rest outside the dish rack. "
            "A measured gripper opening at 44.5s supports an inferred release outside the target. "
            "Task outcome remains uncertain — holding and intent are not measurable."
        ),
        "earliest_failure": fr.get("earliest_failure"),
        "physical_events": events,
        "highlight_interval": {
            "t_start": 43.1,
            "t_end": 45.033,
            "label": "suspected event interval",
            "status": "inferred",
            "note": (
                "Frozen pipeline interval from botfails_ep010_w1260_v2. "
                "Supported interval combining track motion + rest outside target + measured open; "
                "not a directly measured release onset."
            ),
        },
        "timeline_markers": [
            {
                "id": "interval_start",
                "label": "Suspected event interval begins",
                "t": 43.1,
                "kind": "inferred_event",
                "evidence_ids": ["E0"],
            },
            {
                "id": "gripper_open",
                "label": "Measured gripper open",
                "t": 44.5,
                "kind": "observed_measurement",
                "evidence_ids": ["E2"],
            },
            {
                "id": "interval_end",
                "label": "Rest outside target",
                "t": 45.033,
                "kind": "inferred_event",
                # E1 (rest outside) is primary at this timestamp; E0 is the move span.
                "evidence_ids": ["E1", "E0"],
            },
        ],
        "evidence_catalog": evidence_catalog,
        "frame_catalog": [],
        "observed": [
            {"text": "Measured gripper opening at 44.5s (frame 1335).", "evidence_ids": ["E2"], "t": 44.5},
            {"text": "SAM track displacement ~86px during 43.1–45.0s.", "evidence_ids": ["E0"], "t": 43.1},
            {
                "text": "Plate rest observations outside target for 31 frames after 45.0s.",
                "evidence_ids": ["E1"],
                "t": 45.0,
            },
        ],
        "inferred": [
            {
                "text": "released_outside_target for green plate:1 (43.1–45.0s).",
                "evidence_ids": ["E0", "E1", "E2"],
                "t": 43.1,
                "status": "inferred",
            }
        ],
        "hypotheses": muse.get("hypotheses") or [],
        "unknowns": [
            "Whether the gripper was holding the plate (holding not detectable).",
            "Whether the opening was intentional.",
            "Final inside-rack placement for all plates (not established).",
        ],
        "muse_explanation": muse.get("explanation"),
        "factual_claims": muse.get("factual_claims") or [],
        "visual_interpretations": muse.get("visual_interpretations") or [],
        "limitations": muse.get("limitations") or fr.get("uncertainties") or [],
        "muse_only": {
            "verdict": muse_only.get("verdict"),
            "confidence": muse_only.get("confidence"),
            "summary": muse_only.get("summary"),
            "failure_mode": muse_only.get("failure_mode"),
        }
        if muse_only
        else None,
        "evidence_muse_outcome": muse.get("task_outcome"),
        "comparison_note": None,
        "highlight_muse_comparison": False,
        "video": {"rel": "eval_videos/botfails/botfails_dish_test_ep010.mp4", "primary_evidence": True},
        "disclaimer": (
            "3D view is joint-driven visualization only. Trust camera footage and frozen evidence "
            "for physical claims."
        ),
        "initial_seek_s": 43.1,
        "initial_marker_id": "interval_start",
        "initial_evidence_id": "E0",
    }
    # keep release_interval alias for older UI fields
    analysis["release_interval"] = analysis["highlight_interval"]
    copy_video(10, out)
    analysis["sam_overlay"] = export_sam_overlay("ep010", 10, out, float(fps))
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print("exported ep010")


def _heldout_bundle(
    *,
    key: str,
    episode_index: int,
    title: str,
    diagnosis_headline: str,
    diagnosis_summary: str,
    outcome_label: str,
    comparison_note: str | None,
    highlight_muse_comparison: bool = False,
) -> None:
    out = OUT_ROOT / key
    out.mkdir(parents=True, exist_ok=True)
    export_joints(episode_index, key, out)

    run = _read(ROOT / f"data/experiments/heldout_four_v2/botfails_dish_test_{key}/run_report.json")
    muse = _read(
        ROOT / f"data/experiments/heldout_four_muse_comparison/{key}/evidence_grounded/validated_explanation.json"
    )
    pkg = _read(
        ROOT / f"data/experiments/heldout_four_muse_comparison/{key}/evidence_grounded/package_snapshot.json"
    )
    muse_only = _read(
        ROOT / f"data/experiments/heldout_four_muse_comparison/{key}/muse_only/structured_prediction.json"
    )
    pred = run.get("prediction") or {}
    fps = 30.0
    es = run.get("end_state") or {}
    plates = es.get("plates") or es.get("plate_observations") or []

    evidence_catalog = []
    for e in pkg.get("evidence_catalog") or []:
        fs = e.get("frame_start")
        fe = e.get("frame_end")
        t_start = e.get("t_start")
        t_end = e.get("t_end")
        if t_start is None and isinstance(fs, int):
            t_start = float(fs) / fps
        if t_end is None and isinstance(fe, int):
            t_end = float(fe) / fps
        evidence_catalog.append(
            {
                "evidence_id": e.get("evidence_id"),
                "source": e.get("source"),
                "kind": e.get("kind"),
                "status_context": e.get("status_context"),
                "frame_start": fs,
                "frame_end": fe,
                "t_start": t_start,
                "t_end": t_end,
                "summary": e.get("summary"),
                "claims": e.get("claims") or [],
            }
        )

    frame_catalog = pkg.get("frame_catalog") or pkg.get("frame_refs") or []
    markers = []
    for fr in frame_catalog:
        role = fr.get("role") or "frame"
        label = {
            "window_start": "Analysis window starts",
            "gripper_open_measured": "Measured gripper open",
            "window_end_last_obs": "Analysis window ends",
            "end_state": "End-state snapshot",
        }.get(role, role.replace("_", " ").title())
        kind = "observed_measurement" if "gripper" in role else "analysis_frame"
        markers.append(
            {
                "id": fr.get("frame_ref") or f"f{fr.get('frame_index')}",
                "label": label,
                "t": float(fr.get("timestamp_s") or 0),
                "kind": kind,
                "evidence_ids": list(fr.get("tied_evidence_ids") or []),
            }
        )

    # Observed / inferred from frozen facts — no invented physical events
    observed = []
    for fr in frame_catalog:
        if fr.get("role") == "gripper_open_measured":
            observed.append(
                {
                    "text": f"Measured gripper opening near {fr.get('timestamp_s')}s (frame {fr.get('frame_index')}).",
                    "evidence_ids": list(fr.get("tied_evidence_ids") or []),
                    "t": fr.get("timestamp_s"),
                }
            )
    end_det = next(
        (
            e
            for e in evidence_catalog
            if e.get("kind") == "detection"
            and "end" in (e.get("source") or "").lower()
        ),
        None,
    )
    empty_ev = next(
        (
            e
            for e in evidence_catalog
            if "n_physical_events=0" in (e.get("summary") or "")
            or "no supported physical" in (e.get("summary") or "").lower()
        ),
        None,
    )
    if plates:
        regions = [p.get("region") for p in plates]
        observed.append(
            {
                "text": f"End-state 2D plate regions: {', '.join(str(r) for r in regions)} (frame {es.get('frame')}).",
                "evidence_ids": [end_det["evidence_id"]]
                if end_det
                else ([evidence_catalog[0]["evidence_id"]] if evidence_catalog else []),
                "t": float(es.get("frame") or 0) / fps if es.get("frame") else None,
            }
        )
    observed.append(
        {
            "text": "Pipeline physical-event catalog is empty for this episode (n_physical_events=0).",
            "evidence_ids": [empty_ev["evidence_id"]]
            if empty_ev
            else (
                [e["evidence_id"] for e in evidence_catalog if "physical" in (e.get("summary") or "").lower()][:1]
                or ([evidence_catalog[0]["evidence_id"]] if evidence_catalog else [])
            ),
        }
    )

    inferred: list[dict[str, Any]] = []
    unknowns: list[str] = [
        "No timed physical-event localization in this episode.",
        "2D containment does not establish plate orientation.",
    ]
    if pred.get("verdict") == "success":
        inferred.append(
            {
                "text": "End-state geometry supports success (plates assessed inside rack footprint).",
                "evidence_ids": [end_det["evidence_id"]]
                if end_det
                else [e["evidence_id"] for e in evidence_catalog if e.get("kind") == "detection"][:1],
                "status": "supported_by_end_state",
            }
        )
    elif pred.get("verdict") == "failure":
        inferred.append(
            {
                "text": "End-state geometry supports failure (at least one plate outside rack).",
                "evidence_ids": [end_det["evidence_id"]]
                if end_det
                else [e["evidence_id"] for e in evidence_catalog if e.get("kind") == "detection"][:1],
                "status": "supported_by_end_state",
            }
        )
    else:
        unknowns.insert(0, "Pipeline abstains: insufficient inside/outside geometry for a definitive verdict.")

    if key == "ep005":
        unknowns.insert(
            0,
            "Orientation failure is the visual ground truth, but is not verified by 2D containment.",
        )

    highlight = None
    if markers:
        # soft highlight spanning window start→end when available
        wins = [m for m in markers if m["id"] in ("F0", "F2") or "window" in m["label"].lower()]
        if len(markers) >= 2:
            highlight = {
                "t_start": markers[0]["t"],
                "t_end": markers[2]["t"] if len(markers) > 2 else markers[-1]["t"],
                "label": "analysis window",
                "status": "observed_window",
                "note": "Matched Muse analysis frames — not a reconstructed physical failure interval.",
            }

    analysis = {
        "episode_key": key,
        "title": title,
        "task": "Store green plates in the dish rack",
        "split": "held-out",
        "available_episodes": AVAILABLE,
        "has_joint_animation": True,
        "pipeline_verdict": pred.get("verdict") or "uncertain",
        "task_outcome": muse.get("task_outcome") or pred.get("verdict") or "uncertain",
        "outcome_label": outcome_label,
        "diagnosis_headline": diagnosis_headline,
        "diagnosis_summary": diagnosis_summary,
        "earliest_failure": None,
        "physical_events": [],  # intentionally empty — do not invent
        "highlight_interval": highlight,
        "release_interval": highlight,  # alias for UI
        "timeline_markers": markers,
        "evidence_catalog": evidence_catalog,
        "frame_catalog": frame_catalog,
        "observed": observed,
        "inferred": inferred,
        "hypotheses": muse.get("hypotheses") or [],
        "unknowns": unknowns,
        "muse_explanation": muse.get("explanation"),
        "factual_claims": muse.get("factual_claims") or [],
        "visual_interpretations": muse.get("visual_interpretations") or [],
        "limitations": muse.get("limitations") or [],
        "muse_only": {
            "verdict": muse_only.get("verdict"),
            "confidence": muse_only.get("confidence"),
            "summary": muse_only.get("summary"),
            "failure_mode": muse_only.get("failure_mode"),
        }
        if muse_only
        else None,
        "evidence_muse_outcome": muse.get("task_outcome"),
        "comparison_note": comparison_note,
        "highlight_muse_comparison": highlight_muse_comparison,
        "video": {
            "rel": f"eval_videos/botfails/botfails_dish_test_ep{episode_index:03d}.mp4",
            "primary_evidence": True,
        },
        "disclaimer": (
            "3D view is joint-driven visualization only. Empty physical-event catalogs are shown "
            "honestly — no fabricated timed releases."
        ),
        "initial_seek_s": markers[-1]["t"] if markers else 0.0,  # end-state often most informative
        "initial_marker_id": markers[-1]["id"] if markers else None,
        "initial_evidence_id": (markers[-1]["evidence_ids"] or [None])[0]
        if markers
        else (evidence_catalog[0]["evidence_id"] if evidence_catalog else None),
    }
    # For success/failure, prefer seeking to end-state; for uncertain ep005 also end-state
    copy_video(episode_index, out)
    analysis["sam_overlay"] = export_sam_overlay(key, episode_index, out, float(fps))
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print("exported", key)


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    export_ep010()
    _heldout_bundle(
        key="ep003",
        episode_index=3,
        title="Dish tidy-up · held-out success",
        diagnosis_headline="Evidence-supported successful placement",
        diagnosis_summary=(
            "No timed physical failure events were reconstructed. End-state SAM geometry places "
            "all three green plates inside the rack footprint; evidence-grounded Muse and Muse-only "
            "both report success."
        ),
        outcome_label="Success — supported by end-state 2D containment",
        comparison_note="Muse-only and evidence-grounded agree on success.",
    )
    _heldout_bundle(
        key="ep013",
        episode_index=13,
        title="Dish tidy-up · held-out failure",
        diagnosis_headline="Evidence-supported failed placement",
        diagnosis_summary=(
            "No timed physical failure events were reconstructed. End-state geometry shows at least "
            "one green plate outside the rack; evidence-grounded Muse and Muse-only both report failure."
        ),
        outcome_label="Failure — supported by end-state outside plate",
        comparison_note="Muse-only and evidence-grounded agree on failure (no invented timed event).",
    )
    _heldout_bundle(
        key="ep005",
        episode_index=5,
        title="Dish tidy-up · held-out orientation / false success",
        diagnosis_headline="Evidence abstains; Muse-only false success",
        diagnosis_summary=(
            "Pipeline and evidence-grounded Muse remain uncertain: 2D containment cannot verify "
            "plate orientation. Muse-only incorrectly claims upright success — a false definitive verdict."
        ),
        outcome_label="Uncertain (evidence) vs Muse-only success @0.68 — false success on orientation",
        comparison_note=(
            "False-success example: Muse-only asserts upright success; evidence-grounded abstains. "
            "Do not treat 2D inside/outside as orientation."
        ),
        highlight_muse_comparison=True,
    )
    _heldout_bundle(
        key="ep006",
        episode_index=6,
        title="Dish tidy-up · held-out abstention",
        diagnosis_headline="Evidence abstains — insufficient end-state geometry",
        diagnosis_summary=(
            "No timed physical failure events were reconstructed. End-state 2D geometry leaves "
            "plates unconfirmed inside/outside, so the pipeline and evidence-grounded Muse abstain. "
            "Muse-only still claims success — shown as a secondary comparison, not a verified outcome."
        ),
        outcome_label="Uncertain / abstain — insufficient inside/outside geometry",
        comparison_note=(
            "Optional abstention example: evidence-grounded remains uncertain; Muse-only claims "
            "success. Prefer abstention over an unsupported definitive verdict."
        ),
        highlight_muse_comparison=False,
    )
    index = {
        "episodes": [e["key"] for e in AVAILABLE],
        "generated_by": "scripts/export_web_demo_bundles.py",
        "paid_api_calls": False,
    }
    (OUT_ROOT / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
