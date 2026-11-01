"""Offline smoke checks for multi-episode web demo sync contracts.

Validates frozen bundles under web/public/data/{ep}/:
- required assets present
- empty physical_events for held-out where expected
- marker/evidence timestamps allow seek sync
- joints length matches timestamps
- ep010 marker label wording

No paid APIs. Does not modify the Python inference pipeline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data"
EPISODES = ["ep010", "ep005", "ep003", "ep013", "ep006"]
HELD_OUT_EMPTY = {"ep003", "ep013", "ep005", "ep006"}


def fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def main() -> None:
    problems: list[str] = []
    for key in EPISODES:
        d = DATA / key
        for name in ("analysis.json", "joints.json", "mapping.json", "video.mp4"):
            p = d / name
            if not p.is_file():
                problems.append(f"{key}: missing {name}")
                continue
            if name == "video.mp4" and p.stat().st_size < 1_000_000:
                problems.append(f"{key}: video suspiciously small ({p.stat().st_size})")

        sam_meta_path = d / "sam_overlay.json"
        if sam_meta_path.is_file():
            sam_meta = json.loads(sam_meta_path.read_text(encoding="utf-8"))
            if sam_meta.get("available"):
                ov = d / "overlay.mp4"
                if not ov.is_file() or ov.stat().st_size < 500_000:
                    problems.append(f"{key}: sam_overlay available but overlay.mp4 missing/small")
                analysis_probe = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
                if not (analysis_probe.get("sam_overlay") or {}).get("available"):
                    problems.append(f"{key}: analysis.sam_overlay.available should be true")
        else:
            problems.append(f"{key}: missing sam_overlay.json")

        analysis = json.loads((d / "analysis.json").read_text(encoding="utf-8"))
        joints = json.loads((d / "joints.json").read_text(encoding="utf-8"))
        mapping = json.loads((d / "mapping.json").read_text(encoding="utf-8"))

        if analysis.get("episode_key") != key:
            problems.append(f"{key}: episode_key mismatch")
        if len(joints["timestamps_s"]) != len(joints["urdf_rad"]):
            problems.append(f"{key}: joints length mismatch")
        if not mapping.get("available", True):
            problems.append(f"{key}: mapping.available false but joints present")

        # Wrist flex must use BotFails negation (regression for folded-down 3D bug).
        by_urdf = {t["urdf"]: t.get("formula", "") for t in (mapping.get("transform") or [])}
        if by_urdf.get("wrist_flex") != "urdf = -deg2rad(motor)":
            problems.append(
                f"{key}: wrist_flex formula expected 'urdf = -deg2rad(motor)', "
                f"got {by_urdf.get('wrist_flex')!r}"
            )
        if (mapping.get("out_of_limit_frames") or {}).get("wrist_flex", 0) != 0:
            problems.append(
                f"{key}: wrist_flex still reports URDF clamping "
                f"({mapping['out_of_limit_frames']['wrist_flex']})"
            )

        events = analysis.get("physical_events") or []
        if key in HELD_OUT_EMPTY and events:
            problems.append(f"{key}: fabricated physical_events ({len(events)})")

        markers = analysis.get("timeline_markers") or []
        if not markers:
            problems.append(f"{key}: no timeline markers")
        for m in markers:
            if not isinstance(m.get("t"), (int, float)):
                problems.append(f"{key}: marker {m.get('id')} missing t")
            for eid in m.get("evidence_ids") or []:
                if not any(e["evidence_id"] == eid for e in analysis["evidence_catalog"]):
                    problems.append(f"{key}: marker {m.get('id')} refs missing {eid}")

        # Sync contract: every evidence with a frame/time can seek
        seekable = 0
        for e in analysis["evidence_catalog"]:
            if e.get("t_start") is not None or e.get("frame_start") is not None:
                seekable += 1
        if seekable < 1:
            problems.append(f"{key}: no seekable evidence")

        init_t = analysis.get("initial_seek_s")
        if init_t is None:
            problems.append(f"{key}: missing initial_seek_s")
        elif joints["timestamps_s"] and (
            init_t < 0 or init_t > joints["timestamps_s"][-1] + 0.5
        ):
            problems.append(f"{key}: initial_seek_s out of range: {init_t}")

        if key == "ep010":
            labels = [m["label"] for m in markers]
            if "Suspected event interval begins" not in labels:
                problems.append("ep010: missing renamed interval-start marker")
            if any("Inferred release starts" in (m.get("label") or "") for m in markers):
                problems.append("ep010: old 'Inferred release starts' label still present")
            if not events:
                problems.append("ep010: expected non-empty physical_events")

        if key == "ep005":
            if analysis.get("task_outcome") != "uncertain":
                problems.append("ep005: evidence outcome should remain uncertain")
            mo = (analysis.get("muse_only") or {}).get("verdict")
            if mo != "success":
                problems.append(f"ep005: muse_only verdict expected success, got {mo}")
            if not analysis.get("highlight_muse_comparison"):
                problems.append("ep005: highlight_muse_comparison should be true")

        if key == "ep006":
            if analysis.get("task_outcome") != "uncertain":
                problems.append("ep006: abstention should remain uncertain")
            if events:
                problems.append("ep006: must keep empty physical_events")

        print(
            f"OK {key}: markers={len(markers)} events={len(events)} "
            f"seekable_evidence={seekable} joints={joints['n_frames']} "
            f"outcome={analysis.get('task_outcome')} "
            f"muse_only={(analysis.get('muse_only') or {}).get('verdict')}"
        )

    if problems:
        for p in problems:
            print("FAIL:", p)
        raise SystemExit(1)
    print("All smoke sync contracts passed.")


if __name__ == "__main__":
    main()
