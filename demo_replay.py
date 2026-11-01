"""Cached DemoDoctor experiment replay (no paid API calls).

Loads frozen failure reports, Muse responses, preview frames, optional local
video + SAM chunk cache + joint opens for the hackathon demo set
(ep010 / ep003 / ep013 / ep005 / ep006; prior ep001/ep011 retained).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import streamlit as st

import tracking as T

ROOT = Path(__file__).parent

STATUS_STYLE = {
    "observed": "🟢 observed",
    "inferred": "🟠 inferred",
    "uncertain": "⚪ uncertain",
}

# Primary judge path first; prior held-out examples kept for continuity.
PRIMARY_DEMO_KEYS = ("ep010", "ep003", "ep013", "ep005", "ep006")


@dataclass
class EpisodeDemo:
    """Paths and metadata for one cached hackathon demonstration."""

    key: str
    title: str
    split: str  # development | held-out
    role: str
    video_rel: str
    frozen_exp: str
    evidence_muse_dir: str
    muse_only_dir: str
    window: tuple[int, int]
    matched_frames: list[int]
    fps: float = 30.0
    episode_index: int | None = None
    joint_dir_rel: str = "data/lerobot/kantine__BotFails/test/domotic_dishTidyUp_anomaly"
    # heldout_v2: failure_report synthesized from run_report (no separate JSON)
    layout: str = "classic"  # classic | heldout_v2


EPISODES: dict[str, EpisodeDemo] = {
    "ep010": EpisodeDemo(
        key="ep010",
        title="ep010 — development: inferred release localization",
        split="development",
        role=(
            "Development example. Deterministic report: uncertain with one inferred "
            "released_outside_target event — main timed localization demo."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep010.mp4",
        frozen_exp="data/experiments/botfails_ep010_w1260_v2",
        evidence_muse_dir="data/experiments/botfails_ep010_w1260_v2_muse_pilot",
        muse_only_dir="data/experiments/botfails_ep010_muse_only_matched_frames",
        window=(1260, 1381),
        matched_frames=[1293, 1335, 1350, 1380],
        episode_index=10,
    ),
    "ep003": EpisodeDemo(
        key="ep003",
        title="ep003 — held-out: evidence-supported success",
        split="held-out",
        role=(
            "Held-out success. End-state 2D containment = inside for all plates; "
            "Muse-only and evidence-grounded both predicted success. No timed events."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep003.mp4",
        frozen_exp="data/experiments/heldout_four_v2/botfails_dish_test_ep003",
        evidence_muse_dir="data/experiments/heldout_four_muse_comparison/ep003/evidence_grounded",
        muse_only_dir="data/experiments/heldout_four_muse_comparison/ep003/muse_only",
        window=(1845, 1965),
        matched_frames=[1845, 1875, 1964, 2075],
        episode_index=3,
        layout="heldout_v2",
    ),
    "ep013": EpisodeDemo(
        key="ep013",
        title="ep013 — held-out: evidence-supported failure",
        split="held-out",
        role=(
            "Held-out failure. One green plate remains outside the rack; both Muse paths "
            "predicted failure. Empty physical-event catalog (end-state geometry)."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep013.mp4",
        frozen_exp="data/experiments/heldout_four_v2/botfails_dish_test_ep013",
        evidence_muse_dir="data/experiments/heldout_four_muse_comparison/ep013/evidence_grounded",
        muse_only_dir="data/experiments/heldout_four_muse_comparison/ep013/muse_only",
        window=(1498, 1618),
        matched_frames=[1498, 1528, 1617, 2075],
        episode_index=13,
        layout="heldout_v2",
    ),
    "ep005": EpisodeDemo(
        key="ep005",
        title="ep005 — held-out: orientation failure vs false success",
        split="held-out",
        role=(
            "Held-out orientation failure. Muse-only falsely claimed upright success; "
            "evidence-grounded abstained (2D containment cannot verify orientation)."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep005.mp4",
        frozen_exp="data/experiments/heldout_four_v2/botfails_dish_test_ep005",
        evidence_muse_dir="data/experiments/heldout_four_muse_comparison/ep005/evidence_grounded",
        muse_only_dir="data/experiments/heldout_four_muse_comparison/ep005/muse_only",
        window=(1607, 1727),
        matched_frames=[1607, 1637, 1726, 2075],
        episode_index=5,
        layout="heldout_v2",
    ),
    "ep006": EpisodeDemo(
        key="ep006",
        title="ep006 — held-out: conservative abstention tradeoff (optional)",
        split="held-out",
        role=(
            "Held-out visual success with partial geometry. Muse-only success; "
            "evidence-grounded uncertain — shows abstention cost of conservatism."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep006.mp4",
        frozen_exp="data/experiments/heldout_four_v2/botfails_dish_test_ep006",
        evidence_muse_dir="data/experiments/heldout_four_muse_comparison/ep006/evidence_grounded",
        muse_only_dir="data/experiments/heldout_four_muse_comparison/ep006/muse_only",
        window=(1500, 1620),
        matched_frames=[1500, 1530, 1619, 2075],
        episode_index=6,
        layout="heldout_v2",
    ),
    "ep001": EpisodeDemo(
        key="ep001",
        title="ep001 — prior held-out success (archive)",
        split="held-out",
        role=(
            "Earlier held-out success control. Deterministic uncertain, zero events; "
            "evidence Muse abstained; Muse-only predicted success."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep001.mp4",
        frozen_exp="data/experiments/botfails_ep001_w1203_heldout",
        evidence_muse_dir="data/experiments/botfails_ep001_heldout_muse_comparison/evidence_grounded",
        muse_only_dir="data/experiments/botfails_ep001_heldout_muse_comparison/muse_only",
        window=(1203, 1324),
        matched_frames=[1203, 1233, 1323, 2061],
        episode_index=1,
    ),
    "ep011": EpisodeDemo(
        key="ep011",
        title="ep011 — prior held-out failure cand. (archive)",
        split="held-out",
        role=(
            "Earlier held-out failure candidate. Deterministic uncertain, zero events; "
            "evidence Muse abstained; Muse-only predicted failure."
        ),
        video_rel="eval_videos/botfails/botfails_dish_test_ep011.mp4",
        frozen_exp="data/experiments/botfails_ep011_w1518_heldout",
        evidence_muse_dir="data/experiments/botfails_ep011_heldout_muse_comparison/evidence_grounded",
        muse_only_dir="data/experiments/botfails_ep011_heldout_muse_comparison/muse_only",
        window=(1518, 1639),
        matched_frames=[1518, 1548, 1638, 2058],
        episode_index=11,
    ),
}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@dataclass
class ReplayBundle:
    """All local artifacts needed for one episode replay (API-free)."""

    demo: EpisodeDemo
    failure_report: dict[str, Any]
    verification: dict[str, Any] | None
    run_report: dict[str, Any] | None
    frozen_config: dict[str, Any] | None
    evidence_muse: dict[str, Any] | None
    evidence_raw: str | None
    muse_only: dict[str, Any] | None
    muse_only_raw: str | None
    package_snapshot: dict[str, Any] | None
    preview_paths: list[Path] = field(default_factory=list)
    video_path: Path | None = None
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failure_report is not None and not any(
            m.startswith("required:") for m in self.missing
        )


def _synthesize_heldout_v2_failure(run: dict[str, Any]) -> dict[str, Any]:
    """Build a FailureReport-like dict from heldout_four_v2 run_report (read-only view)."""
    windows = run.get("window_reports") or []
    if not windows:
        return {
            "verdict": (run.get("prediction") or {}).get("verdict") or "uncertain",
            "physical_events": [],
            "uncertainties": [],
            "object_outcomes": [],
            "earliest_failure": None,
            "failure_type": None,
            "inputs": {},
        }
    latest = max(windows, key=lambda w: w["frames"][0])
    fr = dict(latest.get("failure_report") or {})
    pred = run.get("prediction") or {}
    fr["verdict"] = pred.get("verdict") or fr.get("verdict") or "uncertain"
    if fr["verdict"] == "failure" and not fr.get("failure_type"):
        fr["failure_type"] = "incorrect_final_placement"
    fr["physical_events"] = list(fr.get("physical_events") or [])
    fr["earliest_failure"] = pred.get("earliest_failure_latest") or fr.get("earliest_failure")
    notes = list(fr.get("uncertainties") or [])
    notes.append(
        f"Held-out v2 episode prediction basis={pred.get('basis')}; "
        f"end_state_verdict={pred.get('end_state_verdict')}; "
        "2D containment ≠ verified plate orientation."
    )
    fr["uncertainties"] = notes
    return fr


def load_replay_bundle(key: str, root: Path | None = None) -> ReplayBundle:
    """Load frozen experiment + Muse artifacts. Never calls Fireworks or Meta APIs."""
    root = root or ROOT
    demo = EPISODES[key]
    frozen = root / demo.frozen_exp
    ev_dir = root / demo.evidence_muse_dir
    mo_dir = root / demo.muse_only_dir
    missing: list[str] = []

    run_report = _read_json(frozen / "run_report.json")
    frozen_config = _read_json(frozen / "frozen_config.json")
    verification = _read_json(frozen / "verification.json")

    if demo.layout == "heldout_v2":
        if run_report is None:
            missing.append("required: run_report.json")
            failure: dict[str, Any] = {}
        else:
            failure = _synthesize_heldout_v2_failure(run_report)
            # Prefer latest window verification summary when present
            windows = run_report.get("window_reports") or []
            if windows and verification is None:
                latest = max(windows, key=lambda w: w["frames"][0])
                verification = (latest.get("verification") or {}).get("summary") or (
                    latest.get("verification") or {}
                ).get("report")
            # Normalize end_state plates → plate_observations for UI
            es = run_report.get("end_state")
            if isinstance(es, dict) and es.get("plates") and not es.get("plate_observations"):
                run_report = {
                    **run_report,
                    "end_state": {
                        **es,
                        "plate_observations": es["plates"],
                        "note": es.get("note")
                        or (
                            "2D image-plane containment only; orientation not verified. "
                            f"regions={es.get('regions')}"
                        ),
                    },
                }
        if frozen_config is None:
            frozen_config = _read_json(
                root / "data/experiments/inference_freeze_v2/frozen_config.json"
            )
    else:
        failure = _read_json(frozen / "failure_report.json")
        if failure is None:
            missing.append("required: failure_report.json")
            failure = {}

    # Evidence Muse: pilot_report (ep010) or run_report / validated_explanation (held-out)
    evidence_muse = (
        _read_json(ev_dir / "validated_explanation.json")
        or _read_json(ev_dir / "pilot_report.json")
        or _read_json(ev_dir / "run_report.json")
    )
    if evidence_muse and "validated" in evidence_muse and "task_outcome" not in evidence_muse:
        evidence_muse = {**evidence_muse["validated"], "usage": evidence_muse.get("usage"),
                         "estimated_cost_usd": evidence_muse.get("estimated_cost_usd")}
    evidence_raw = None
    raw_path = ev_dir / "raw_model_response.txt"
    if raw_path.is_file():
        evidence_raw = raw_path.read_text(encoding="utf-8")
    else:
        missing.append("optional: evidence raw_model_response.txt")

    muse_only = _read_json(mo_dir / "structured_prediction.json") or _read_json(mo_dir / "run_report.json")
    muse_only_raw = None
    mo_raw = mo_dir / "raw_model_response.txt"
    if mo_raw.is_file():
        muse_only_raw = mo_raw.read_text(encoding="utf-8")

    package_snapshot = _read_json(ev_dir / "package_snapshot.json")
    if package_snapshot is None and (ev_dir / "pilot_report.json").is_file():
        # ep010 pilot embeds package summary only; build a light catalog from pilot
        pilot = _read_json(ev_dir / "pilot_report.json") or {}
        package_snapshot = {
            "evidence_catalog": [],
            "frame_catalog": (pilot.get("package") or {}).get("frame_refs") or [],
            "physical_events": [],
            "deterministic_pipeline": {
                "verdict": (pilot.get("package") or {}).get("deterministic_verdict"),
                "n_physical_events": (pilot.get("package") or {}).get("n_physical_events"),
            },
        }

    previews: list[Path] = []
    for d in (mo_dir, ev_dir):
        previews.extend(sorted(d.glob("preview_req*_f*.jpg")))
    # de-dupe by name preferring muse_only
    by_name: dict[str, Path] = {}
    for p in previews:
        by_name.setdefault(p.name, p)
    preview_paths = [by_name[k] for k in sorted(by_name)]

    video_path = root / demo.video_rel
    if not video_path.is_file():
        video_path = None
        missing.append(f"optional: video missing at {demo.video_rel}")

    return ReplayBundle(
        demo=demo,
        failure_report=failure,
        verification=verification,
        run_report=run_report,
        frozen_config=frozen_config,
        evidence_muse=evidence_muse,
        evidence_raw=evidence_raw,
        muse_only=muse_only,
        muse_only_raw=muse_only_raw,
        package_snapshot=package_snapshot,
        preview_paths=preview_paths,
        video_path=video_path,
        missing=missing,
    )


def _frame_overlay_from_cache(
    video_bytes: bytes,
    frame_index: int,
    window: tuple[int, int],
    concept: str = "green plate",
) -> np.ndarray | None:
    """Paint SAM masks for one frame from local chunk cache (no API)."""
    digest = T._video_digest(video_bytes)
    chunk = T.window_chunk(window[0], window[1])
    entries = T.cached_chunk_entries(digest, chunk, concept)
    if not entries:
        return None
    rgb = T.extract_frame_rgb(video_bytes, frame_index).copy()
    painted = False
    for entry in entries:
        for rec in entry.get("observations") or []:
            if int(rec.get("frame_index", -1)) != frame_index:
                continue
            mask_rle = rec.get("mask_rle")
            bbox = rec.get("bbox")
            if not mask_rle or not bbox:
                continue
            color = T.CONCEPT_COLORS.get(concept, (80, 200, 120))
            T._paint_rle(rgb, mask_rle, color, tuple(bbox))
            painted = True
    return rgb if painted else T.extract_frame_rgb(video_bytes, frame_index)


def _centroid_series_from_cache(
    video_bytes: bytes,
    window: tuple[int, int],
    concept: str = "green plate",
) -> list[dict[str, Any]]:
    digest = T._video_digest(video_bytes)
    chunk = T.window_chunk(window[0], window[1])
    entries = T.cached_chunk_entries(digest, chunk, concept)
    rows: list[dict[str, Any]] = []
    for entry in entries:
        for rec in entry.get("observations") or []:
            bbox = rec.get("bbox")
            fi = rec.get("frame_index")
            if not bbox or fi is None:
                continue
            x1, y1, x2, y2 = bbox
            rows.append({
                "frame": int(fi),
                "Time (s)": round(int(fi) / 30.0, 3),
                "object_id": rec.get("object_id") or concept,
                "centroid_x": (x1 + x2) / 2.0,
                "centroid_y": (y1 + y2) / 2.0,
            })
    return rows


def _gripper_opens(bundle: ReplayBundle) -> list[dict[str, Any]]:
    opens = (bundle.run_report or {}).get("opens_near_window") or []
    if opens:
        return opens
    # fall back to package evidence measurements
    catalog = (bundle.package_snapshot or {}).get("evidence_catalog") or []
    out = []
    for e in catalog:
        if e.get("kind") == "measurement" and e.get("frame_start") is not None:
            out.append({
                "frame": e["frame_start"],
                "t": e.get("t_start"),
                "summary": e.get("summary"),
                "evidence_id": e.get("evidence_id"),
            })
    return out


def _evidence_catalog(bundle: ReplayBundle) -> list[dict[str, Any]]:
    snap = bundle.package_snapshot or {}
    catalog = snap.get("evidence_catalog") or []
    if catalog:
        return catalog
    # Reconstruct minimal catalog from failure_report evidence blocks (ep010)
    items = []
    eid = 0
    for ev in bundle.failure_report.get("physical_events") or []:
        for block in ev.get("evidence") or []:
            items.append({
                "evidence_id": f"E{eid}",
                "source": block.get("source"),
                "kind": block.get("kind"),
                "status_context": ev.get("status"),
                "frame_start": block.get("frame_start"),
                "frame_end": block.get("frame_end"),
                "summary": block.get("summary"),
                "note": None,
            })
            eid += 1
    for note in bundle.failure_report.get("uncertainties") or []:
        items.append({
            "evidence_id": f"E{eid}",
            "source": "pipeline:report",
            "kind": "derived",
            "status_context": "uncertain",
            "frame_start": None,
            "frame_end": None,
            "summary": str(note)[:400],
            "note": "report-level uncertainty",
        })
        eid += 1
    return items


def _frame_catalog(bundle: ReplayBundle) -> list[dict[str, Any]]:
    snap = bundle.package_snapshot or {}
    frames = snap.get("frame_catalog") or snap.get("frame_refs") or []
    if frames:
        return frames
    # Fall back to matched frame list
    demo = bundle.demo
    return [
        {
            "frame_ref": f"F{i}",
            "frame_index": fr,
            "timestamp_s": round(fr / demo.fps, 3),
            "tied_evidence_ids": [],
            "role": "matched_frame",
        }
        for i, fr in enumerate(demo.matched_frames)
    ]


def render_demo_replay() -> None:
    """Streamlit: DemoDoctor Analysis — cached experiment replay."""
    st.subheader("DemoDoctor Analysis")
    st.markdown(
        """
**What this is:** DemoDoctor diagnoses robot manipulation demos using **physical evidence** —
SAM 3.1 object tracks, gripper joint openings, and verified event logic — then asks Meta **Muse Spark**
to explain only what that evidence supports.

**What this is not:** A black-box video classifier. We do **not** claim higher success/failure accuracy
than Muse-only. On held-out episodes the evidence path often **abstains** (`uncertain`) when
events are unsupported — that is intentional.
"""
    )
    st.caption(
        "This tab replays **frozen** results. **No Fireworks or Meta API calls.** "
        "Muse-only vs evidence-grounded uses different prompts/schemas (workflow comparison, not a pure SAM A/B). "
        "Need videos/caches? Run `python setup_hackathon_demo.py`."
    )
    st.info(
        "Status legend — 🟢 **observed** = direct measurement · "
        "🟠 **inferred** = supported by combining observations (not raw proof of intent) · "
        "⚪ **uncertain** = insufficient evidence. "
        "Clicking an evidence ID shows the cited measurement/frame; it does **not** certify every narrative detail. "
        "An **uncertain** task outcome is an honest abstention, not a broken demo."
    )

    options = [k for k in PRIMARY_DEMO_KEYS if k in EPISODES] + [
        k for k in EPISODES if k not in PRIMARY_DEMO_KEYS
    ]
    labels = {k: EPISODES[k].title for k in options}
    key = st.selectbox(
        "Choose a recorded demonstration",
        options=options,
        format_func=lambda k: labels[k],
        key="demo_replay_episode",
        help=(
            "Primary path: ep010 (localization) → ep003 (success) → ep013 (failure) → "
            "ep005 (orientation / false success) → ep006 (abstention tradeoff)."
        ),
    )
    bundle = load_replay_bundle(key)
    demo = bundle.demo

    split_badge = "🧪 development" if demo.split == "development" else "🔒 held-out"
    st.markdown(f"**{split_badge}** · {demo.role}")

    # At-a-glance comparison for judges
    mo = bundle.muse_only or {}
    ev = bundle.evidence_muse or {}
    events = bundle.failure_report.get("physical_events") or []
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Pipeline verdict", bundle.failure_report.get("verdict") or "n/a")
    g2.metric("Physical events", str(len(events)))
    g3.metric("Evidence-grounded Muse", ev.get("task_outcome") or "n/a")
    g4.metric("Muse-only baseline", mo.get("verdict") or "n/a")

    with st.expander("How to read this demo (60 seconds)", expanded=(key == "ep010")):
        st.markdown(
            """
1. Watch the video (or key frames) — what did the arm do with the green plates?
2. Check **SAM masks / trajectories** — what was tracked in the analysis window?
3. Check **gripper openings** — measured joint rises (holding cannot be sensed).
4. Read **physical events** — empty list means we refuse to invent a failure.
5. Compare **evidence-grounded Muse** (cites E0, E1, …) vs **Muse-only** (frames alone).
6. Click an evidence ID to inspect the supporting frame or measurement.
"""
        )

    if bundle.missing:
        with st.expander("Missing optional assets", expanded=False):
            for m in bundle.missing:
                st.write(f"- {m}")
    if not bundle.ok:
        st.error("Required failure report missing — cannot replay.")
        return

    # --- Video ---
    st.markdown("### 1. Robot demonstration video")
    if bundle.video_path is not None:
        st.video(str(bundle.video_path))
        st.caption(
            f"`{demo.video_rel}` · analysis window frames "
            f"**{demo.window[0]}–{demo.window[1] - 1}** "
            f"({demo.window[0] / demo.fps:.1f}s–{(demo.window[1] - 1) / demo.fps:.1f}s)"
        )
    else:
        st.warning(
            "Local MP4 not found. Run `python setup_hackathon_demo.py` to download BotFails "
            "videos (Apache-2.0). Preview frames below still work."
        )

    # --- Matched frames / masks ---
    st.markdown("### 2. SAM masks & key frames")
    st.caption("Matched Muse frames. Overlays use **local** SAM chunk cache when available.")
    cols = st.columns(min(4, max(1, len(demo.matched_frames))))
    for i, fr in enumerate(demo.matched_frames):
        with cols[i % len(cols)]:
            overlay = None
            if bundle.video_path is not None and demo.window[0] <= fr < demo.window[1]:
                try:
                    overlay = _frame_overlay_from_cache(
                        bundle.video_path.read_bytes(), fr, demo.window
                    )
                except Exception as exc:  # noqa: BLE001 — show frame without mask
                    st.caption(f"overlay skip: {type(exc).__name__}")
            preview = next((p for p in bundle.preview_paths if f"_f{fr}." in p.name), None)
            if overlay is not None:
                st.image(overlay, caption=f"f{fr} · {fr / demo.fps:.1f}s (SAM overlay)", use_container_width=True)
            elif preview is not None:
                st.image(str(preview), caption=f"f{fr} · preview", use_container_width=True)
            else:
                st.write(f"Frame {fr} — no preview")

    if bundle.video_path is not None:
        series = _centroid_series_from_cache(bundle.video_path.read_bytes(), demo.window)
        if series:
            st.markdown("**Object trajectories (window centroids from cached SAM)**")
            import pandas as pd

            df = pd.DataFrame(series)
            for oid in sorted(df["object_id"].unique()):
                sub = df[df["object_id"] == oid][["Time (s)", "centroid_x", "centroid_y"]]
                st.caption(str(oid))
                st.line_chart(sub, x="Time (s)", y=["centroid_x", "centroid_y"])
        else:
            st.caption("No cached SAM observations found for trajectory plot.")

    # --- Joints ---
    st.markdown("### 3. Robot joint measurements (gripper)")
    opens = _gripper_opens(bundle)
    if opens:
        st.write("Measured gripper openings near the analysis window (holding is **not** detectable):")
        for op in opens:
            st.write(
                f"- frame **{op.get('frame')}** @ **{op.get('t')}**s"
                + (f" · measured={op.get('measured')}" if op.get("measured") is not None else "")
                + (f" · {op.get('evidence_id')}" if op.get("evidence_id") else "")
            )
            if op.get("summary"):
                st.caption(op["summary"][:240])
    else:
        st.caption("No gripper openings recorded in the frozen run report for this window.")
    cal = (bundle.failure_report.get("inputs") or {}).get("gripper_calibration") or {}
    if cal:
        st.caption(
            f"Detector: `{cal.get('detector')}` · holding_detectable={cal.get('holding_detectable')} "
            f"· open_rise_frac={cal.get('open_rise_frac')}"
        )

    # --- Events ---
    st.markdown("### 4. Reconstructed physical events")
    events = bundle.failure_report.get("physical_events") or []
    verdict = bundle.failure_report.get("verdict")
    st.metric("Deterministic pipeline verdict", verdict or "n/a")
    if not events:
        st.warning(
            "No supported physical failure events in this window. "
            "DemoDoctor does **not** invent drops or placements to force a diagnosis."
        )
    else:
        for i, ev in enumerate(events):
            status = ev.get("status") or "uncertain"
            st.markdown(
                f"**Event {i}:** `{ev.get('kind')}` / `{ev.get('subtype')}` · "
                f"{STATUS_STYLE.get(status, status)} · "
                f"t={ev.get('t_start')}–{ev.get('t_end')}s · track=`{ev.get('track_id')}`"
            )
            if ev.get("inference"):
                st.caption(f"Inference note: {ev['inference']}")
            for u in ev.get("uncertainties") or []:
                st.caption(f"Uncertainty: {u}")

    # --- Failure interval ---
    st.markdown("### 5. Suspected failure interval")
    ef = bundle.failure_report.get("earliest_failure")
    ev_muse = bundle.evidence_muse or {}
    interval = ev_muse.get("earliest_failure_interval")
    if ef:
        st.success(
            f"Pipeline earliest failure: t={ef.get('t_start')}–{ef.get('t_end')}s "
            f"(frames {ef.get('frame_start')}–{ef.get('frame_end')}) · type=`{ef.get('failure_type')}`"
        )
    elif interval:
        st.info(
            f"Evidence-grounded Muse interval: t={interval.get('t_start')}–{interval.get('t_end')}s "
            f"· evidence={interval.get('evidence_ids')} · {interval.get('note') or ''}"
        )
    else:
        st.info("No supported failure interval (pipeline and evidence-grounded Muse abstained).")

    # --- Evidence-grounded Muse ---
    st.markdown("### 6. Evidence-grounded Muse explanation")
    if not ev_muse:
        st.warning("Evidence-grounded Muse artifact missing.")
    else:
        outcome = ev_muse.get("task_outcome") or ev_muse.get("verdict") or "n/a"
        if outcome == "uncertain":
            st.warning(f"Task outcome: **uncertain** (honest abstention — not a UI error)")
        else:
            st.write(f"Task outcome: **{outcome}**")
        st.write(ev_muse.get("explanation") or "(no explanation)")

        claims = ev_muse.get("factual_claims") or []
        if claims:
            st.markdown("**Factual claims** (must cite evidence — ID validity ≠ semantic truth)")
            for c in claims:
                st.write(f"- {c.get('text')} · `{c.get('evidence_ids')}`")

        hyps = ev_muse.get("hypotheses") or []
        if hyps:
            st.markdown("**Hypotheses** (not verified measurements)")
            for h in hyps:
                st.write(f"- {h.get('text')} · related `{h.get('related_evidence_ids')}`")

        vis = ev_muse.get("visual_interpretations") or []
        if vis:
            st.markdown("**Unverified visual interpretations**")
            for v in vis:
                flag = " · not verified by pipeline" if v.get("not_verified_by_pipeline") else ""
                st.write(f"- [{v.get('frame_ref')}] {v.get('text')}{flag}")

        lims = ev_muse.get("limitations") or []
        if lims:
            st.markdown("**Limitations**")
            for L in lims:
                st.write(f"- {L}")

        usage = ev_muse.get("usage")
        if usage:
            st.caption(
                f"Tokens prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')} "
                f"· est. ${ev_muse.get('estimated_cost_usd') or 'n/a'}"
            )

    # --- Muse-only ---
    st.markdown("### 7. Muse-only comparison (baseline)")
    mo = bundle.muse_only or {}
    if not mo:
        st.caption("Muse-only artifact missing.")
    else:
        left, right = st.columns(2)
        with left:
            st.markdown("**Muse-only** (frames + task text)")
            st.write(f"Verdict: `{mo.get('verdict')}`")
            conf = mo.get("confidence")
            if isinstance(conf, (int, float)):
                st.caption(f"Model-reported confidence {conf:.0%} — not empirical accuracy.")
            st.write(mo.get("summary") or "")
            if mo.get("failure_mode"):
                st.caption(f"Failure mode: {mo['failure_mode']}")
            notes = mo.get("uncertainty_notes") or []
            if notes:
                for n in notes:
                    st.write(f"- {n}")
            elif mo.get("verdict") in ("success", "failure"):
                st.caption("No uncertainty_notes provided by Muse-only.")
        with right:
            st.markdown("**Evidence-grounded** (same frames + package)")
            st.write(f"Outcome: `{(bundle.evidence_muse or {}).get('task_outcome')}`")
            st.write((bundle.evidence_muse or {}).get("explanation") or "")
            st.caption(
                "Different system prompt + schema. This compares the full evidence workflow, "
                "not the isolated effect of adding SAM. See evaluation report for unfavorable findings too."
            )

    # --- Clickable evidence ---
    st.markdown("### 8. Evidence references (inspect)")
    catalog = _evidence_catalog(bundle)
    frames = _frame_catalog(bundle)
    if not catalog and not frames:
        st.caption("No evidence catalog available.")
    else:
        eid_options = [e.get("evidence_id") for e in catalog if e.get("evidence_id")]
        fid_options = [f.get("frame_ref") for f in frames if f.get("frame_ref")]
        pick_kind = st.radio("Inspect", ["Evidence ID (E…)", "Frame ref (F…)"], horizontal=True, key=f"insp_kind_{key}")
        if pick_kind.startswith("Evidence") and eid_options:
            eid = st.selectbox("Evidence", eid_options, key=f"insp_eid_{key}")
            item = next(e for e in catalog if e.get("evidence_id") == eid)
            st.json({k: item.get(k) for k in (
                "evidence_id", "source", "kind", "status_context",
                "frame_start", "frame_end", "t_start", "t_end", "summary", "note",
            )})
            fs = item.get("frame_start")
            if isinstance(fs, int) and bundle.video_path is not None:
                try:
                    rgb = T.extract_frame_rgb(bundle.video_path.read_bytes(), fs)
                    if demo.window[0] <= fs < demo.window[1]:
                        ov = _frame_overlay_from_cache(bundle.video_path.read_bytes(), fs, demo.window)
                        st.image(ov if ov is not None else rgb, caption=f"Supporting frame {fs}", use_container_width=True)
                    else:
                        st.image(rgb, caption=f"Supporting frame {fs}", use_container_width=True)
                except Exception as exc:  # noqa: BLE001
                    st.caption(f"Could not decode frame: {exc}")
            elif isinstance(fs, int):
                prev = next((p for p in bundle.preview_paths if f"_f{fs}." in p.name), None)
                if prev:
                    st.image(str(prev), caption=f"Preview f{fs}", use_container_width=True)
        elif fid_options:
            fid = st.selectbox("Frame", fid_options, key=f"insp_fid_{key}")
            fr = next(f for f in frames if f.get("frame_ref") == fid)
            st.json(fr)
            fi = fr.get("frame_index")
            if isinstance(fi, int):
                prev = next((p for p in bundle.preview_paths if f"_f{fi}." in p.name), None)
                if bundle.video_path is not None:
                    try:
                        rgb = T.extract_frame_rgb(bundle.video_path.read_bytes(), fi)
                        st.image(rgb, caption=f"{fid} · f{fi} · {fr.get('timestamp_s')}s", use_container_width=True)
                    except Exception:
                        if prev:
                            st.image(str(prev), use_container_width=True)
                elif prev:
                    st.image(str(prev), use_container_width=True)

    # --- Verification / uncertainties ---
    st.markdown("### 9. Verification, uncertainties, limitations")
    ver = bundle.verification or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Claims checked", ver.get("claims_checked", "n/a"))
    c2.metric("Claims failed", ver.get("claims_failed", "n/a"))
    c3.metric("Unverifiable", ver.get("claims_unverifiable", "n/a"))
    if ver.get("event_verdicts"):
        st.write("Event verdicts:", ver["event_verdicts"])
    for u in bundle.failure_report.get("uncertainties") or []:
        st.write(f"- ⚪ {str(u)[:350]}{'…' if len(str(u)) > 350 else ''}")
    end = (bundle.run_report or {}).get("end_state")
    if end:
        with st.expander("End-state SAM snapshot (separate request; ids not matched to window tracks)"):
            st.write(end.get("note"))
            st.json({"frame": end.get("frame"), "plates": end.get("plate_observations")})

    with st.expander("Method & evaluation honesty"):
        st.markdown(
            """
- **Observed** measurements (e.g. gripper joint open) are not by themselves drops.
- **Inferred** events combine measurements; intent is not proven.
- **Visual interpretations** from Muse are labeled unverified when the pipeline did not check them.
- **2D containment ≠ plate orientation** — ep005 Muse-only falsely claimed upright success;
  evidence-grounded abstained.
- New held-out four (ep003/005/006/013): Muse-only **75%** among 4 decisions (1 false success);
  evidence-grounded **100%** among 2 decisions with **50%** abstention. **n is small** — not
  statistical proof that SAM alone improves Muse accuracy (different prompts/schemas).
- ep010 (development) remains the main **timed event localization** example.
- Full reports: `data/experiments/heldout_four_muse_comparison/FINAL_MUSE_COMPARISON_REPORT.md`
  and `data/experiments/HELD_OUT_EVALUATION_REPORT.md`.
"""
        )
