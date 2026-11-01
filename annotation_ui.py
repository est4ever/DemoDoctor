"""Streamlit section for manually annotating failure events (writes data/event_labels.json)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import streamlit as st

import event_labels as L
import tracking as T

ROOT = Path(__file__).parent
NOT_SET = "— not set —"
# Dataset anomaly flags are shown for reference only (never saved as our annotation).
ANOMALY_CSV = {
    "botfails_dish_test_ep000": "data/lerobot/kantine__BotFails/labels/domotic_dishTidyUp_anomaly/episode_000000_labels.csv",
    "botfails_dish_test_ep010": "data/lerobot/kantine__BotFails/labels/domotic_dishTidyUp_anomaly/episode_000010_labels.csv",
}


@st.cache_data(max_entries=48)
def _frame(video_path: str, frame_index: int) -> np.ndarray:
    return T.extract_frame_rgb((ROOT / video_path).read_bytes(), frame_index)


@st.cache_data(max_entries=8)
def _probe(video_path: str) -> tuple[float, int]:
    return T.probe_video((ROOT / video_path).read_bytes())


def render_event_annotation(examples: list) -> None:
    st.subheader("Failure-event annotation (manual)")
    st.caption("Record what you see after watching. Fields left unset stay unset; nothing is pre-filled.")
    choices = {ex.example_id: ex for ex in examples if (ROOT / ex.video_path).is_file()}
    if not choices:
        st.info("No local videos to annotate.")
        return
    example_id = st.selectbox("Episode to annotate", list(choices), key="ann_episode")
    ex = choices[example_id]
    fps, n_frames = _probe(ex.video_path)
    frame = st.slider("Frame", 0, n_frames - 1, 0, key=f"ann_frame_{example_id}")
    st.image(_frame(ex.video_path, frame), caption=f"frame {frame} · {frame / fps:.2f}s", width="stretch",
             alt=f"Frame {frame} of {example_id}")

    ref = ANOMALY_CSV.get(example_id)
    onset = L.dataset_anomaly_onset(ROOT / ref) if ref else None
    if onset:
        first = onset["first_flagged_frame"]
        st.caption(
            "Dataset reference (BotFails anomaly flag, not a verified failure time): "
            + (f"first flagged frame {first} ({first / fps:.2f}s), {onset['flagged_frames']} frames flagged."
               if first is not None else "no frames flagged.")
        )

    existing = L.get_event_label(example_id) or {}
    fm = existing.get("first_mishandling") or {}
    key = f"ann_mis_{example_id}"
    if key not in st.session_state:
        st.session_state[key] = fm.get("frame")
    c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
    if c1.button("Use current frame as first visible mishandling", key=f"ann_use_{example_id}"):
        st.session_state[key] = frame
    if c2.button("Clear mishandling frame", key=f"ann_clear_{example_id}"):
        st.session_state[key] = None
    chosen = st.session_state[key]
    st.write(f"First visible mishandling: **{'not set' if chosen is None else f'frame {chosen} ({chosen / fps:.2f}s)'}**")

    with st.form(f"ann_form_{example_id}"):
        obj = st.text_input("Object involved (e.g. 'front green plate')", value=fm.get("object", ""))
        description = st.text_input("What is visible at that frame", value=fm.get("description", ""))
        rec_opts = [NOT_SET, *L.RECOVERED]
        recovered = st.selectbox("Did the robot recover afterwards?", rec_opts,
                                 index=rec_opts.index(existing.get("recovered") or NOT_SET))
        out_opts = [NOT_SET, *L.OUTCOMES]
        outcome = st.selectbox("Final task outcome", out_opts, index=out_opts.index(existing.get("final_outcome") or NOT_SET))
        notes = st.text_area("Notes", value=existing.get("notes", ""))
        verified = st.checkbox("I watched the video and this annotation is verified", value=bool(existing.get("verified")))
        submitted = st.form_submit_button("Save failure-event annotation")
    if submitted:
        record = {
            "example_id": example_id,
            "video_path": ex.video_path,
            "first_mishandling": None if chosen is None else {
                "frame": int(chosen), "t_s": round(chosen / fps, 3), "object": obj.strip(), "description": description.strip()},
            "recovered": None if recovered == NOT_SET else recovered,
            "final_outcome": None if outcome == NOT_SET else outcome,
            "notes": notes.strip(),
            "verified": verified,
        }
        try:
            L.upsert_event_label(record, n_frames=n_frames, fps=fps)
            st.success(f"Saved annotation for {example_id}.")
        except ValueError as err:
            st.error(f"Not saved: {err}")
