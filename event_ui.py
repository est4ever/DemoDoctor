"""Streamlit sections for the reconstructed event timeline and keyframe probes.

Everything here reads local caches; the only paid action is the explicit
"Send 1 paid SAM image request" button in the probe section.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import tracking as T

ROOT = Path(__file__).parent
LEROBOT_SOURCE = ROOT / "data" / "lerobot" / "ankithreddy__so101_pickplace_uno" / "SOURCE.json"
OBJECT, TARGET = "screwdriver", "white box"
STATUS_LABEL = {"observed": ":green[observed]", "inferred": ":orange[inferred]", "uncertain": ":gray[uncertain]"}


def paired_with_joint_data(video_bytes: bytes) -> bool:
    """Only the downloaded SO-101 episode has synchronized joint data."""
    if not LEROBOT_SOURCE.is_file():
        return False
    expected = json.loads(LEROBOT_SOURCE.read_text(encoding="utf-8")).get("paired_video", {}).get("sha256")
    return expected == hashlib.sha256(video_bytes).hexdigest()


def _cache_signature(video_bytes: bytes) -> str:
    """Changes whenever chunk entries or probe results change, so caches refresh."""
    digest = T._video_digest(video_bytes)
    files = sorted((T.CHUNK_CACHE_ROOT / digest).glob("f*/*.json")) + sorted((T.PROBE_ROOT / digest).glob("*.json"))
    return hashlib.sha256("".join(f"{p.name}:{p.stat().st_size}" for p in files).encode()).hexdigest()[:12]


@st.cache_resource(max_entries=2)
def _inputs(signature: str) -> Any:
    import events

    del signature  # cache key only
    return events.load_sample_inputs()


@st.cache_data(max_entries=4)
def _timeline_and_report(signature: str) -> tuple[dict[str, Any], dict[str, Any]]:
    import events
    import verification

    inputs = _inputs(signature)
    timeline = events.timeline_from_inputs(inputs).to_dict()
    report = verification.verify_timeline(timeline, tracking=inputs.tracking, proprio=inputs.proprio,
                                          probes=inputs.probes, video_bytes=inputs.video_bytes)
    return timeline, report.to_dict()


@st.cache_data(max_entries=64)
def _frame_with_masks(signature: str, frame_index: int) -> np.ndarray:
    inputs = _inputs(signature)
    rgb = T.extract_frame_rgb(inputs.video_bytes, frame_index).copy()
    for o in list(inputs.tracking.observations) + list(inputs.probes):
        if o.frame_index == frame_index and o.mask_rle and o.bbox:
            color = T.CONCEPT_COLORS.get(o.concept, (255, 160, 0))
            T._paint_rle(rgb, o.mask_rle, color, o.bbox)
    return rgb


def render_event_timeline(video_bytes: bytes) -> None:
    st.subheader("Physical event timeline (reconstructed)")
    if not paired_with_joint_data(video_bytes):
        st.info("Event reconstruction needs synchronized joint data; it is available only for the SO-101 sample episode.")
        return
    st.caption(
        "Built from cached SAM 3.1 tracks and SO-101 joint data; no API calls. "
        "**observed** = a direct measurement · **inferred** = consistent independent observations · "
        "**uncertain** = evidence missing or insufficient. Missing detections are never treated as failures."
    )
    signature = _cache_signature(video_bytes)
    with st.spinner("Reconstructing events from cached evidence..."):
        timeline, report = _timeline_and_report(signature)
    events, verdicts = timeline["events"], report["event_verdicts"]
    rows = [
        {"#": i, "start (s)": e["t_start"], "end (s)": e["t_end"], "frames": f"{e['frame_start']}-{e['frame_end'] - 1}",
         "event": e["event_type"], "status": e["status"], "verification": verdicts.get(str(i), verdicts.get(i))}
        for i, e in enumerate(events)
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, alt="Reconstructed event timeline")
    c1, c2, c3 = st.columns(3)
    c1.metric("Claims checked", report["claims_checked"])
    c2.metric("Claims contradicted", report["claims_failed"])
    c3.metric("Claims unverifiable", report["claims_unverifiable"])
    if timeline["tracking_gaps"]:
        st.caption("Tracking gaps (not interpreted): " + "; ".join(
            f"{g['concept']} {g['state']} frames {g['frame_start']}-{g['frame_end'] - 1} "
            f"({g['t_start']:.2f}-{g['t_end']:.2f}s)" for g in timeline["tracking_gaps"]))

    choice = st.selectbox(
        "Inspect event", options=list(range(len(events))), key="event_inspect",
        format_func=lambda i: f"#{i} {events[i]['event_type']} · {events[i]['status']} · "
                              f"{events[i]['t_start']:.2f}-{events[i]['t_end']:.2f}s",
    )
    e = events[choice]
    with st.container(border=True):
        st.markdown(f"**{e['event_type']}** — {STATUS_LABEL[e['status']]} · frames {e['frame_start']}-{e['frame_end'] - 1}")
        if e.get("inference"):
            st.info(e["inference"], title="Inference")
        for u in e.get("uncertainties") or []:
            st.warning(u)
        st.markdown("**Observations cited as evidence**")
        st.dataframe(pd.DataFrame([
            {"source": r["source"], "kind": r["kind"], "frames": f"{r['frame_start']}-{r['frame_end'] - 1}",
             "summary": r["summary"], "claims": len(r.get("claims") or [])} for r in e["evidence"]
        ]), hide_index=True, alt="Evidence for the selected event")
        findings = [f for f in report["findings"] if f["event_index"] == choice]
        if findings:
            for f in findings:
                (st.error if f["severity"] == "error" else st.warning)(f"{f['check']}: {f['message']}")
        else:
            st.success("Every cited claim was recomputed from raw data and matched.", icon=":material/verified:")

        inputs = _inputs(signature)
        ep = inputs.proprio
        a = max(0, e["frame_start"] - 30)
        b = min(timeline["n_frames"], e["frame_end"] + 30)
        g = ep.joint_names.index("gripper.pos")
        st.markdown("**Joint measurements around the event** (measured vs commanded gripper.pos)")
        st.line_chart(pd.DataFrame({
            "Time (s)": np.arange(a, b) / ep.fps,
            "measured (observation.state)": ep.state[a:b, g],
            "commanded (action)": ep.action[a:b, g],
        }), x="Time (s)", y=["measured (observation.state)", "commanded (action)"])

        obs = [o for o in list(inputs.tracking.observations) + list(inputs.probes)
               if o.frame_index is not None and e["frame_start"] <= o.frame_index < e["frame_end"]]
        st.markdown(f"**SAM observations in the event window** ({len(obs)})")
        if obs:
            st.dataframe(pd.DataFrame([
                {"frame": o.frame_index, "t (s)": o.timestamp_s, "track": o.object_id, "prompt": o.prompt_mode or "concept",
                 "bbox": [round(v) for v in o.bbox], "confidence": o.confidence} for o in obs
            ]), hide_index=True, height=220, alt="SAM observations in the event window")
        else:
            st.caption("No SAM observations in this window.")

        frames = sorted({e["frame_start"], (e["frame_start"] + e["frame_end"] - 1) // 2, max(e["frame_start"], e["frame_end"] - 1)})
        st.markdown("**Supporting frames** (real SAM masks painted where detected)")
        cols = st.columns(len(frames))
        for col, f in zip(cols, frames):
            col.image(_frame_with_masks(signature, f), caption=f"frame {f} · {f / ep.fps:.2f}s", width="stretch",
                      alt=f"Video frame {f}")


def render_placement_probe(video_bytes: bytes) -> None:
    st.subheader("Final-placement keyframe probe")
    if not paired_with_joint_data(video_bytes):
        return
    if not st.toggle("Prepare a manual-box SAM image probe", key="probe_toggle"):
        st.caption("Select a box on one frame and prepare a single SAM 3.1 image request. Nothing is sent until you click send.")
        return
    fps, n_frames = T.probe_video(video_bytes)
    frame_index = st.number_input("Frame index", min_value=0, max_value=n_frames - 1, value=660, step=1, key="probe_frame")
    rgb = T.extract_frame_rgb(video_bytes, int(frame_index))
    h, w = rgb.shape[:2]
    xs = st.slider("Box x range (px)", 0, w, (245, 316), key="probe_x")
    ys = st.slider("Box y range (px)", 0, h, (302, 614), key="probe_y")
    if xs[0] >= xs[1] or ys[0] >= ys[1]:
        st.error("The box is empty; widen the ranges.")
        return
    request = T.prepare_box_probe(video_bytes, frame_index=int(frame_index), box=(xs[0], ys[0], xs[1], ys[1]),
                                  concept=OBJECT, selected_by="manual (Streamlit sliders)")
    preview = T.probe_preview(video_bytes, request)
    st.image(preview, caption=f"Frame {request.frame_index} ({request.timestamp_s:.2f}s) with selected box {request.box}",
             width="stretch", alt="Frame with the selected bounding box")
    st.code(request.prompt_text, language=None)
    if request.cached:
        record = json.loads(request.path.read_text(encoding="utf-8"))
        st.success(f"Cached probe result: status={record['status']} · {len(record.get('observations') or [])} observation(s) · "
                   f"track ids {[o['object_id'] for o in record.get('observations') or []]}", title="Already run")
        st.caption(record.get("linking", ""))
        return
    approved = st.checkbox("I approve one paid SAM 3.1 image request for this frame and box", key="probe_approve")
    ready = T.model_api_key_available() and approved
    if st.button("Send 1 paid SAM image request", disabled=not ready, key="probe_send", type="secondary"):
        with st.spinner("SAM 3.1 image request..."):
            record = T.run_box_probe(request)
        st.write({k: v for k, v in record.items() if k != "observations"})
        st.rerun()
