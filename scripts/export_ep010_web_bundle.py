"""Export read-only ep010 joints + frozen analysis for the React 3D replay prototype.

Uses local parquet + frozen failure_report only. No paid APIs.
Writes under web/public/data/ep010/ (video is NOT copied; Vite serves eval_videos).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proprio import load_episode  # noqa: E402
OUT = ROOT / "web" / "public" / "data" / "ep010"
DATASET = ROOT / "data" / "lerobot" / "kantine__BotFails" / "test" / "domotic_dishTidyUp_anomaly"
FAILURE = ROOT / "data" / "experiments" / "botfails_ep010_w1260_v2" / "failure_report.json"
MUSE_PILOT = ROOT / "data" / "experiments" / "botfails_ep010_w1260_v2_muse_pilot" / "validated_explanation.json"
MUSE_PILOT_REPORT = ROOT / "data" / "experiments" / "botfails_ep010_w1260_v2_muse_pilot" / "pilot_report.json"
MUSE_ONLY = (
    ROOT
    / "data"
    / "experiments"
    / "botfails_ep010_muse_only_matched_frames"
    / "structured_prediction.json"
)

# URDF joint order matches TheRobotStudio SO100 so100.urdf
URDF_JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# Dataset → URDF mapping for visualization (see mapping.json).
# Motor values are degrees (LeRobot use_degrees-style BotFails recordings).
# Foxglove-style pan negation; elbow_flex and wrist_flex negated so BotFails
# motor ranges land in stock SO-100 URDF limits (no limit widening).
# Gripper treated as 0–100 open fraction → radians.
LIMITS = {
    "shoulder_pan": (-2.0, 2.0),
    "shoulder_lift": (0.0, 3.5),
    "elbow_flex": (-3.14158, 0.0),
    "wrist_flex": (-2.5, 1.2),
    "wrist_roll": (-3.14158, 3.14158),
    "gripper": (-0.2, 2.0),
}


def motor_to_urdf_rad(state_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (urdf_rad_clamped, urdf_rad_raw) shape (N, 6)."""
    d = state_deg
    raw = np.stack(
        [
            -np.deg2rad(d[:, 0]),  # shoulder_pan
            np.deg2rad(d[:, 1]),  # shoulder_lift
            -np.deg2rad(d[:, 2]),  # elbow_flex (URDF upper=0)
            -np.deg2rad(d[:, 3]),  # wrist_flex (must match elbow sign for BotFails)
            np.deg2rad(d[:, 4]),  # wrist_roll
            (d[:, 5] / 100.0) * math.pi,  # gripper open fraction → rad
        ],
        axis=1,
    )
    clamped = raw.copy()
    for i, name in enumerate(URDF_JOINTS):
        lo, hi = LIMITS[name]
        clamped[:, i] = np.clip(raw[:, i], lo, hi)
    return clamped, raw


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ep = load_episode(DATASET, 10)
    assert ep.joint_names == [
        "main_shoulder_pan",
        "main_shoulder_lift",
        "main_elbow_flex",
        "main_wrist_flex",
        "main_wrist_roll",
        "main_gripper",
    ]
    clamped, raw = motor_to_urdf_rad(ep.state)
    ool = {
        name: int(np.sum((raw[:, i] < LIMITS[name][0]) | (raw[:, i] > LIMITS[name][1])))
        for i, name in enumerate(URDF_JOINTS)
    }

    # Downsample for web: keep every frame (2090 is fine as float32 JSON ~100KB gzipped)
    # Use float32 lists for compactness
    joints = {
        "episode_key": "ep010",
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
    (OUT / "joints.json").write_text(json.dumps(joints), encoding="utf-8")

    fr = json.loads(FAILURE.read_text(encoding="utf-8"))
    muse = json.loads(MUSE_PILOT.read_text(encoding="utf-8")) if MUSE_PILOT.is_file() else {}
    pilot = (
        json.loads(MUSE_PILOT_REPORT.read_text(encoding="utf-8"))
        if MUSE_PILOT_REPORT.is_file()
        else {}
    )
    muse_only = json.loads(MUSE_ONLY.read_text(encoding="utf-8")) if MUSE_ONLY.is_file() else {}

    events = []
    evidence_catalog = []
    eid = 0
    for ev in fr.get("physical_events") or []:
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
                "evidence_ids": [f"E{eid + i}" for i in range(len(ev.get("evidence") or []))],
            }
        )
        for block in ev.get("evidence") or []:
            fs = block.get("frame_start")
            t_s = float(fs) / ep.fps if isinstance(fs, int) else None
            evidence_catalog.append(
                {
                    "evidence_id": f"E{eid}",
                    "source": block.get("source"),
                    "kind": block.get("kind"),
                    "status_context": ev.get("status"),
                    "frame_start": fs,
                    "frame_end": block.get("frame_end"),
                    "t_start": t_s,
                    "t_end": (
                        float(block["frame_end"]) / ep.fps
                        if isinstance(block.get("frame_end"), int)
                        else None
                    ),
                    "summary": block.get("summary"),
                    "claims": block.get("claims") or [],
                }
            )
            eid += 1

    # Match Muse package IDs E3/E4 (limitations / uncertainties) when present
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

    frame_catalog = (pilot.get("package") or {}).get("frame_refs") or []

    # Timeline markers for UI (seek targets)
    timeline_markers = [
        {
            "id": "release_start",
            "label": "Inferred release starts",
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
            "id": "release_end",
            "label": "Rest outside target",
            "t": 45.033,
            "kind": "inferred_event",
            "evidence_ids": ["E0", "E1"],
        },
    ]

    diagnosis_summary = (
        "Around 43–45s the green plate is moved and comes to rest outside the dish rack. "
        "A measured gripper opening at 44.5s supports an inferred release outside the target. "
        "Task outcome remains uncertain — holding and intent are not measurable."
    )

    analysis = {
        "episode_key": "ep010",
        "title": "Dish tidy-up · development episode",
        "task": "Store green plates in the dish rack",
        "split": "development",
        "available_episodes": [
            {
                "key": "ep010",
                "label": "ep010 — inferred release (dev)",
                "enabled": True,
            },
            {
                "key": "ep003",
                "label": "ep003 — supported success",
                "enabled": False,
                "note": "Coming after ep010 review",
            },
            {
                "key": "ep013",
                "label": "ep013 — supported failure",
                "enabled": False,
                "note": "Coming after ep010 review",
            },
            {
                "key": "ep005",
                "label": "ep005 — Muse-only false success",
                "enabled": False,
                "note": "Coming after ep010 review",
            },
        ],
        "source_failure_report": str(FAILURE.relative_to(ROOT)).replace("\\", "/"),
        "pipeline_verdict": fr.get("verdict"),
        "task_outcome": muse.get("task_outcome") or fr.get("verdict"),
        "outcome_label": "Uncertain — insufficient to certify success or failure",
        "diagnosis_headline": "Inferred plate release outside the rack",
        "diagnosis_summary": diagnosis_summary,
        "earliest_failure": fr.get("earliest_failure"),
        "physical_events": events,
        "release_interval": {
            "t_start": 43.1,
            "t_end": 45.033,
            "label": "inferred released_outside_target",
            "status": "inferred",
            "note": (
                "Frozen pipeline interval from botfails_ep010_w1260_v2. "
                "Not a verified contact event; gripper opening is measured, release is inferred."
            ),
        },
        "timeline_markers": timeline_markers,
        "evidence_catalog": evidence_catalog,
        "frame_catalog": frame_catalog,
        "observed": [
            {
                "text": "Measured gripper opening at 44.5s (frame 1335).",
                "evidence_ids": ["E2"],
                "t": 44.5,
            },
            {
                "text": "SAM track displacement ~86px during 43.1–45.0s.",
                "evidence_ids": ["E0"],
                "t": 43.1,
            },
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
        "video": {
            "rel": "eval_videos/botfails/botfails_dish_test_ep010.mp4",
            "dev_url": "/media/botfails_dish_test_ep010.mp4",
            "primary_evidence": True,
        },
        "disclaimer": (
            "3D view is a joint-driven visualization from measured proprioception. "
            "It does not reconstruct plate poses, contacts, collisions, or task outcome. "
            "Trust the camera footage and frozen evidence package for physical claims."
        ),
    }
    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")

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
            "units": "degrees for arm joints; gripper ~0–100 open fraction (dataset undeclared; empirically degrees-like)",
            "names": ep.joint_names,
        },
        "transform": [
            {"dataset": "main_shoulder_pan", "urdf": "shoulder_pan", "formula": "urdf = -deg2rad(motor)"},
            {"dataset": "main_shoulder_lift", "urdf": "shoulder_lift", "formula": "urdf = deg2rad(motor)"},
            {"dataset": "main_elbow_flex", "urdf": "elbow_flex", "formula": "urdf = -deg2rad(motor)"},
            {"dataset": "main_wrist_flex", "urdf": "wrist_flex", "formula": "urdf = -deg2rad(motor)"},
            {"dataset": "main_wrist_roll", "urdf": "wrist_roll", "formula": "urdf = deg2rad(motor)"},
            {"dataset": "main_gripper", "urdf": "gripper", "formula": "urdf = (motor/100)*pi"},
        ],
        "known_limitations": [
            "Experimental BotFails→URDF mapping: absolute zero offsets vs stock SO-100 URDF are unknown.",
            "elbow_flex and wrist_flex use -deg2rad so BotFails motor ranges fit stock URDF limits (no limit widening).",
            "Gripper URDF is revolute; LeRobot gripper is ~0–100 open fraction — jaw opening is approximate.",
            "No scene meshes or plate poses — 3D is joint-driven visualization only; trust the camera for physical claims.",
        ],
        "out_of_limit_frames": ool,
    }
    (OUT / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

    # Local-only video copy for Vite static serve (gitignored).
    video_src = ROOT / "eval_videos" / "botfails" / "botfails_dish_test_ep010.mp4"
    video_dst = OUT / "video.mp4"
    if video_src.is_file():
        import shutil

        if not video_dst.is_file() or video_dst.stat().st_size != video_src.stat().st_size:
            shutil.copy2(video_src, video_dst)
            print("copied video", video_dst.stat().st_size, "bytes")
        else:
            print("video already present")
    else:
        print("WARNING: video missing at", video_src)

    print("wrote", OUT)
    print("ool", ool)


if __name__ == "__main__":
    main()
