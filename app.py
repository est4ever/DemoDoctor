"""DemoDoctor: hardware-free robot demonstration explorer + AI diagnosis UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ai_analysis import (
    DEFAULT_MODEL,
    REASONING_EFFORTS,
    FireworksConfigError,
    analyze_demonstration,
    estimate_cost_usd,
    load_fireworks_api_key,
)
from diagnosis import Diagnosis, merge_tracking_context
from evaluation import (
    VERDICTS,
    build_comparison_rows,
    compute_stats,
    example_id_for_video,
    list_demo_videos,
    load_labels,
    load_predictions,
    relative_video_path,
    save_prediction,
    upsert_label,
)
from tracking import (
    DEFAULT_SO101_CONCEPTS,
    extract_clip_mp4,
    extract_frame_jpeg,
    get_default_tracker,
    load_assembled_tracking,
    load_cached_tracking,
    model_api_key_available,
    observations_for_display,
    timeline_series,
)
from annotation_ui import render_event_annotation
from demo_replay import render_demo_replay
from event_ui import render_event_timeline, render_placement_probe
from vision import SampledFrame, gallery_frames, inspect_video, select_representative_frames

ROOT = Path(__file__).parent
SAMPLE_FILE = ROOT / "sample_videos" / "sample.mp4"
FRAME_CHOICES = (4, 8, 12, 16)

st.set_page_config(page_title="DemoDoctor", page_icon="🩺", layout="wide")
st.title("DemoDoctor")
st.caption(
    "Evidence-grounded diagnosis for robot demonstrations · "
    "SAM 3.1 tracks · joint openings · verified events · Muse Spark explanations"
)
st.info(
    "**Start here for judges:** open the **DemoDoctor Analysis** tab (cached ep010 / ep001 / ep011 — "
    "no API keys). AI verdicts elsewhere are **provisional**; model confidence ≠ accuracy. "
    "BotFails anomaly flags are **not** automatic task failures. "
    "Evidence-grounded Muse often returns **uncertain** when physical events are unsupported — that is intentional."
)


@st.cache_data(show_spinner=False)
def cached_inspect(video_bytes: bytes):
    return inspect_video(video_bytes)


def render_diagnosis(diagnosis: Diagnosis) -> None:
    colors = {"success": "🟢", "failure": "🔴", "uncertain": "🟡"}
    st.subheader("AI diagnosis (provisional)")
    st.markdown(
        f"{colors.get(diagnosis.verdict, '🟡')} **Verdict:** `{diagnosis.verdict}` "
        f"{'· provisional' if diagnosis.provisional else ''}"
    )
    if diagnosis.confidence is not None:
        st.warning(
            f"Model-reported confidence: **{diagnosis.confidence:.0%}** — "
            "unreliable self-estimate (models often stick near ~90%+). "
            "**Ignore this number** until you have verified labels and empirical accuracy."
        )
    st.write(diagnosis.summary)

    if diagnosis.observed_actions:
        st.markdown("**Observed actions**")
        for action in diagnosis.observed_actions:
            st.write(f"- {action}")

    if diagnosis.failure_mode:
        st.markdown(f"**Possible failure mode:** {diagnosis.failure_mode}")

    if diagnosis.evidence:
        st.markdown("**Evidence**")
        for item in diagnosis.evidence:
            stamp = f"{item.timestamp_s:.1f}s" if item.timestamp_s is not None else "n/a"
            st.write(f"- [{item.kind}] t={stamp}: {item.description}")

    if diagnosis.assumptions:
        st.markdown("**Assumptions** (not directly observed)")
        for item in diagnosis.assumptions:
            st.write(f"- {item}")

    if diagnosis.uncertainty_notes:
        st.markdown("**Uncertainty**")
        for item in diagnosis.uncertainty_notes:
            st.write(f"- {item}")

    if diagnosis.usage:
        cost = estimate_cost_usd(diagnosis.usage)
        tokens = diagnosis.usage
        usage_line = (
            f"Tokens — prompt: {tokens.get('prompt_tokens')}, "
            f"completion: {tokens.get('completion_tokens')}, "
            f"total: {tokens.get('total_tokens')}"
        )
        if cost is not None:
            usage_line += f" · ~${cost:.4f} (list rates)"
        st.caption(usage_line)

    st.caption(
        f"Model: `{diagnosis.model_name or 'n/a'}` · "
        f"Tracking used: {'yes' if diagnosis.tracking_used else 'no'}"
    )


def render_submitted_frames(frames: list[SampledFrame]) -> None:
    st.subheader("Frames submitted to Muse")
    st.caption("These are the exact timestamped frames sent for this diagnosis.")
    cols = st.columns(min(4, max(1, len(frames))))
    for index, frame in enumerate(frames):
        with cols[index % len(cols)]:
            st.image(
                frame.rgb,
                caption=f"#{index} · {frame.timestamp_s:.1f}s",
                use_container_width=True,
            )


def run_analysis(
    *,
    video_bytes: bytes,
    video_name: str,
    source_kind: str,
    task_description: str,
    frame_count: int,
    reasoning_effort: str,
    max_tokens: int,
    vision_frames: list[SampledFrame],
    example_id: str | None = None,
) -> tuple[Diagnosis, list[SampledFrame], Path]:
    selected = select_representative_frames(vision_frames, frame_count)
    # Muse stays independent: only annotate if a *cached* SAM result already exists.
    cached_tracks = load_cached_tracking(video_bytes, list(DEFAULT_SO101_CONCEPTS))
    diagnosis = analyze_demonstration(
        selected,
        task_description,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
    )
    diagnosis = merge_tracking_context(
        diagnosis, bool(cached_tracks and cached_tracks.available)
    )
    eid = example_id or example_id_for_video(
        video_name,
        "sample" if source_kind == "sample" else ("batch" if source_kind == "batch" else "upload"),
    )
    pred_path = save_prediction(
        diagnosis,
        example_id=eid,
        video_name=video_name,
        frame_count=len(selected),
        frame_timestamps_s=[f.timestamp_s for f in selected],
        reasoning_effort=reasoning_effort,
        source="streamlit" if source_kind != "batch" else "batch",
    )
    return diagnosis, selected, pred_path


def render_eval_panel() -> None:
    stats = compute_stats()
    st.write(stats.message)
    st.caption(
        f"Independent examples on disk: {stats.n_labeled} · Verified: {stats.n_verified} · "
        f"Compared: {stats.n_compared} (one prediction per example_id)"
    )
    if not stats.show_metrics:
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Empirical accuracy", f"{stats.accuracy:.0%}" if stats.accuracy is not None else "n/a")
    c2.metric(
        "Abstention rate",
        f"{stats.abstention_rate:.0%}" if stats.abstention_rate is not None else "n/a",
        help="Share of predictions that were 'uncertain'.",
    )
    c3.metric("Correct / compared", f"{stats.n_correct}/{stats.n_compared}")

    st.markdown("**Confusion matrix** (rows = your label, columns = model verdict)")
    st.dataframe(stats.confusion, use_container_width=True)

    if stats.by_frame_count:
        st.markdown("**Accuracy by frame count** (same episodes, different Muse runs)")
        st.dataframe(stats.by_frame_count, use_container_width=True)
        st.caption(
            "Frame-count rows are re-tests of the same videos — they do not increase "
            "the number of independent ground-truth examples."
        )


def label_lookup() -> dict[str, object]:
    return {ex.example_id: ex for ex in load_labels()}


def sync_text_field(key: str, source_token: str, new_value: str) -> None:
    """Update a Streamlit text widget when its source episode/source changes.

    Streamlit keeps the previous value in session state once a keyed widget exists,
    so `value=` alone will not refresh when the episode dropdown changes.
    """
    token_key = f"_sync_token_{key}"
    if st.session_state.get(token_key) != source_token:
        st.session_state[key] = new_value
        st.session_state[token_key] = source_token


# --- Sidebar ---
with st.sidebar:
    st.header("AI settings")
    api_ready = False
    try:
        load_fireworks_api_key()
        api_ready = True
        st.success("FIREWORKS_API_KEY loaded from .env")
    except FireworksConfigError as err:
        st.warning(str(err))

    frame_count = st.radio(
        "Frames sent to Muse",
        options=FRAME_CHOICES,
        index=0,
        horizontal=True,
        help="Start with 4, then try 8. 12/16 only if needed — more frames cost more.",
    )
    reasoning_effort = st.selectbox(
        "Reasoning effort",
        options=list(REASONING_EFFORTS),
        index=0,
        help="Higher effort thinks longer and costs more. Start with low.",
    )
    max_tokens = st.slider("Max output tokens", min_value=512, max_value=4096, value=2048, step=256)
    st.caption(f"Model: `{DEFAULT_MODEL}`")

    st.divider()
    st.subheader("Empirical evaluation")
    render_eval_panel()

tab_demo, tab_analyze, tab_label, tab_compare, tab_batch, tab_history = st.tabs(
    [
        "DemoDoctor Analysis",
        "Analyze",
        "Ground-truth labels",
        "Comparison",
        "Batch (manual)",
        "Prediction history",
    ]
)

with tab_demo:
    render_demo_replay()

# --- Analyze tab ---
with tab_analyze:
    source = st.radio(
        "Video source",
        ["Eval set episode", "Hugging Face SO-101 sample", "Upload an MP4"],
        horizontal=True,
    )
    video_bytes = None
    video_name = "sample.mp4"
    source_kind = "sample"
    video_path_for_label = "sample_videos/sample.mp4"
    selected_example_id: str | None = None
    default_task = "Pick up the screwdriver and place it inside the box"

    if source == "Eval set episode":
        labels = load_labels()
        choices = [ex for ex in labels if (ROOT / ex.video_path).is_file()]
        if not choices:
            st.warning(
                "No local eval videos yet. Run: "
                "`python import_botfails.py --download`"
            )
        else:
            # Prefer BotFails episodes in the list; keep a stable widget key so the
            # selection does not silently snap back to the SO-101 sample on rerun.
            labels_by_id = {ex.example_id: ex for ex in choices}
            option_ids = list(labels_by_id.keys())
            selected_example_id = st.selectbox(
                "Episode",
                options=option_ids,
                key="analyze_episode_id",
                format_func=lambda eid: (
                    f"{eid} · suggested={labels_by_id[eid].suggested_label} · "
                    f"verified={labels_by_id[eid].verified}"
                ),
            )
            ex = labels_by_id[selected_example_id]
            path = ROOT / ex.video_path
            video_bytes = path.read_bytes()
            video_name = path.name
            video_path_for_label = ex.video_path.replace("\\", "/")
            source_kind = "batch"
            default_task = ex.task_description
            st.caption(
                f"Source: `{ex.source_dataset or 'local'}` · "
                f"anomaly_present={ex.anomaly_present} (≠ task failure) · "
                f"needs_manual_review={ex.needs_manual_review}"
            )
            if ex.notes:
                st.caption(ex.notes[:300] + ("…" if len(ex.notes) > 300 else ""))
    elif source == "Hugging Face SO-101 sample":
        if SAMPLE_FILE.is_file():
            video_bytes = SAMPLE_FILE.read_bytes()
            selected_example_id = "sample_hf_episode_000000"
            st.success("Loaded SO-101 pick-and-place sample.")
        else:
            st.warning("No sample found yet. Run: python download_sample.py")
    else:
        source_kind = "upload"
        uploaded = st.file_uploader("Select a robot demonstration video", type=["mp4", "mov", "mkv"])
        if uploaded is not None:
            video_bytes = uploaded.getvalue()
            video_name = uploaded.name
            video_path_for_label = f"uploads/{uploaded.name}"
            selected_example_id = example_id_for_video(video_name, "upload")

    sync_text_field(
        "task_analyze",
        source_token=f"{source}:{selected_example_id or video_name}",
        new_value=default_task,
    )
    task_description = st.text_input("Task description", key="task_analyze")

    current_id = selected_example_id or example_id_for_video(
        video_name, "sample" if source_kind == "sample" else "upload"
    )
    # Drop stale diagnosis / tracking UI when the selected episode changes.
    if st.session_state.get("_analyze_bound_id") != current_id:
        st.session_state.pop("last_diagnosis", None)
        st.session_state.pop("last_submitted_frames", None)
        st.session_state.pop("last_pred_path", None)
        st.session_state.pop("last_tracking", None)
        st.session_state["_analyze_bound_id"] = current_id

    if video_bytes is not None:
        st.subheader("Video")
        st.video(video_bytes)
        try:
            with st.spinner("Extracting frames and measuring visual changes..."):
                vision = cached_inspect(video_bytes)
        except Exception as error:
            st.error(f"Unable to decode the video: {error}")
            st.stop()

        planned = select_representative_frames(vision.frames, frame_count)
        st.success(
            f"**Will analyze** `{current_id}` · file `{video_path_for_label}` · "
            f"{len(vision.frames)}s sampled · Muse frames at "
            f"{[f.timestamp_s for f in planned]}s · task: _{task_description}_"
        )
        # Sanity check: SO-101 sample is ~25s; BotFails dish clips are ~70s.
        if current_id.startswith("botfails_") and vision.frames[-1].timestamp_s < 40:
            st.error(
                "This does not look like a BotFails dish episode (too short). "
                "Re-select the episode before spending API credits."
            )
        if current_id == "sample_hf_episode_000000" and "dish" in task_description.lower():
            st.error(
                "Episode is the SO-101 screwdriver sample, but the task mentions dishes. "
                "Pick `botfails_dish_test_ep000` from the Episode dropdown."
            )

        st.metric("Frames sampled (approximately 1/second)", len(vision.frames))
        if frame_count > len(vision.frames):
            st.warning(
                f"Only {len(vision.frames)} sampled frames available; "
                f"analysis will use all of them (requested {frame_count})."
            )

        gallery = gallery_frames(vision.frames, 12)
        st.subheader("Robot demonstration timeline")
        columns = st.columns(3)
        for index, frame in enumerate(gallery):
            with columns[index % 3]:
                st.image(frame.rgb, caption=f"{frame.timestamp_s:.1f} seconds", use_container_width=True)

        if vision.change_chart:
            st.subheader("Visual change between sampled frames")
            st.line_chart(vision.change_chart, x="Time (s)", y="Visual change")

        st.subheader("SAM 3.1 object tracking (optional)")
        st.caption(
            "Meta Model API (`MODEL_API_KEY`) + official `meta_sam_parser`. "
            "Paid calls run **only** when you click a button below. Results cache under `data/tracking/`."
        )
        sam_ready = model_api_key_available()
        if sam_ready:
            st.success("MODEL_API_KEY loaded from .env")
        else:
            st.warning("MODEL_API_KEY not set — cannot run SAM until it is in `.env`.")

        concepts = st.text_input(
            "SAM concepts (comma-separated; one API call each)",
            value="screwdriver, white box",
            key="sam_concepts",
        )
        concept_list = [c.strip() for c in concepts.split(",") if c.strip()] or list(
            DEFAULT_SO101_CONCEPTS[:2]
        )
        sam_mode = st.radio(
            "Tracking scope",
            ["Single frame (cheap)", "Short clip ~4s", "Full video"],
            horizontal=True,
            key="sam_mode",
            help="Validate on one frame first, then a short clip, then the full demo.",
        )
        force_sam = st.checkbox("Force refresh (ignore cache)", value=False, key="sam_force")
        run_sam = st.button("Run SAM Tracking", type="secondary", disabled=not sam_ready, key="sam_run")

        if run_sam and sam_ready:
            tracker = get_default_tracker()
            if sam_mode.startswith("Single"):
                with st.spinner("SAM 3.1 image segmentation (screwdriver frame)..."):
                    jpeg = extract_frame_jpeg(video_bytes, timestamp_s=0.5)
                    tracking = tracker.segment_image(
                        jpeg,
                        concept=concept_list[0],
                        force_refresh=force_sam,
                    )
            elif sam_mode.startswith("Short"):
                with st.spinner("Uploading short clip + SAM 3.1 video tracking..."):
                    clip = extract_clip_mp4(video_bytes, start_s=0.0, duration_s=4.0)
                    tracking = tracker.track_video(
                        clip,
                        object_prompts=concept_list,
                        force_refresh=force_sam,
                        media_kind="clip",
                    )
            else:
                with st.spinner("Uploading full video + SAM 3.1 (may take several minutes)..."):
                    tracking = tracker.track_video(
                        video_bytes,
                        object_prompts=concept_list,
                        force_refresh=force_sam,
                        media_kind="video",
                    )
            st.session_state["last_tracking"] = tracking
        elif not run_sam:
            media_kind = (
                "image"
                if sam_mode.startswith("Single")
                else ("clip" if sam_mode.startswith("Short") else "video")
            )
            payload = video_bytes
            lookup_concepts = concept_list
            if media_kind == "image":
                # Single-frame runs segment only the first concept, so they are
                # cached under that concept alone.
                lookup_concepts = concept_list[:1]
                try:
                    payload = extract_frame_jpeg(video_bytes, timestamp_s=0.5)
                except Exception:
                    payload = video_bytes
            elif media_kind == "clip":
                try:
                    payload = extract_clip_mp4(video_bytes, start_s=0.0, duration_s=4.0)
                except Exception:
                    payload = video_bytes
            cached = None
            if media_kind == "video":
                # Latest stitched chunk cache (incl. box-seeded recoveries) when it
                # covers every concept; otherwise the full-video summary cache.
                cached = load_assembled_tracking(video_bytes, concept_list)
            if cached is None:
                cached = load_cached_tracking(payload, lookup_concepts, media_kind=media_kind)
            if cached is not None:
                st.session_state["last_tracking"] = cached

        if "last_tracking" in st.session_state:
            tr = st.session_state["last_tracking"]
            st.write(tr.notes)
            if tr.diagnostics:
                d = tr.diagnostics
                st.markdown("**Tracking diagnostics** (not task-success confidence)")
                c1, c2, c3 = st.columns(3)
                c1.metric("Source frames", d.frames_in_source if d.frames_in_source is not None else "n/a")
                c2.metric("Frames with detection", d.frames_with_any_detection)
                c3.metric("Observations", d.observations_total)
                st.json(d.per_concept)
                if d.missing_concepts:
                    st.warning(f"No detections for: {', '.join(d.missing_concepts)}")
            if tr.available:
                st.caption(
                    f"provider={tr.provider} · kind={tr.media_kind} · from_cache={tr.from_cache} · "
                    f"cache={tr.cache_dir}"
                )
                series = timeline_series(tr)
                if series:
                    st.markdown("**Centroid timeline**")
                    concepts_seen = sorted({row["concept"] for row in series})
                    for concept_name in concepts_seen:
                        sub = [
                            {
                                "Time (s)": row["Time (s)"],
                                "centroid_x": row["centroid_x"],
                                "centroid_y": row["centroid_y"],
                            }
                            for row in series
                            if row["concept"] == concept_name
                        ]
                        st.caption(concept_name)
                        st.line_chart(sub, x="Time (s)", y=["centroid_x", "centroid_y"])
                st.dataframe(observations_for_display(tr, limit=80), use_container_width=True)
                if tr.overlay_paths:
                    st.markdown("**Segmentation overlays** (real SAM masks/boxes)")
                    cols = st.columns(3)
                    for i, path in enumerate(tr.overlay_paths[:12]):
                        with cols[i % 3]:
                            st.image(path, use_container_width=True)
            else:
                st.info("No SAM tracks available yet (empty match or API error). Nothing was fabricated.")

        render_event_timeline(video_bytes)
        render_placement_probe(video_bytes)

        st.subheader("Analyze with AI")
        st.caption("Paid Fireworks / Muse call runs only when you click the button below.")

        analyze = st.button(
            f"Analyze with AI · {current_id} · {frame_count} frames",
            type="primary",
            disabled=not api_ready,
        )
        if not api_ready:
            st.warning("Add FIREWORKS_API_KEY to a local `.env` file to enable analysis.")

        if analyze and api_ready:
            with st.spinner(
                f"Calling Muse Spark Open on {current_id} "
                f"({frame_count} frames @ { [f.timestamp_s for f in planned] }s)..."
            ):
                diagnosis, selected, pred_path = run_analysis(
                    video_bytes=video_bytes,
                    video_name=video_name,
                    source_kind=source_kind,
                    task_description=task_description,
                    frame_count=frame_count,
                    reasoning_effort=reasoning_effort,
                    max_tokens=max_tokens,
                    vision_frames=vision.frames,
                    example_id=current_id,
                )
            st.session_state["last_diagnosis"] = diagnosis
            st.session_state["last_submitted_frames"] = selected
            st.session_state["last_pred_path"] = str(pred_path)
            st.session_state["last_example_id"] = current_id
            st.session_state["last_video_path"] = video_path_for_label
            st.session_state["last_task"] = task_description
            st.session_state["_analyze_bound_id"] = current_id

        if (
            st.session_state.get("last_example_id") == current_id
            and "last_submitted_frames" in st.session_state
        ):
            render_submitted_frames(st.session_state["last_submitted_frames"])
        if (
            st.session_state.get("last_example_id") == current_id
            and "last_diagnosis" in st.session_state
        ):
            st.caption(
                f"Showing diagnosis for `{current_id}` · `{video_path_for_label}` · "
                f"Muse times {[f.timestamp_s for f in st.session_state['last_submitted_frames']]}s"
            )
            render_diagnosis(st.session_state["last_diagnosis"])
            if "last_pred_path" in st.session_state:
                st.caption(f"Saved prediction: `{st.session_state['last_pred_path']}`")
                if "sample_hf_episode_000000" in st.session_state["last_pred_path"] and current_id.startswith(
                    "botfails_"
                ):
                    st.error(
                        "Prediction filename is still the SO-101 sample — this run did not "
                        "save under the BotFails episode id. Re-run after refresh."
                    )

# --- Ground-truth labeling tab ---
with tab_label:
    st.subheader("Manual ground-truth labels")
    st.write(
        "Watch each video, then set the outcome. "
        "**Do not** treat BotFails `anomaly_present=true` as automatic failure. "
        "Ambiguous cases should stay `uncertain` until you are sure."
    )

    labels = load_labels()
    default_id = st.session_state.get("last_example_id", labels[0].example_id if labels else "")
    id_options = [ex.example_id for ex in labels] or [default_id]
    label_example_id = st.selectbox(
        "Example ID",
        options=id_options,
        index=id_options.index(default_id) if default_id in id_options else 0,
        key="label_example_id",
    )
    current = next((ex for ex in labels if ex.example_id == label_example_id), None)
    sync_text_field(
        "label_video_path",
        source_token=label_example_id,
        new_value=(current.video_path if current else st.session_state.get("last_video_path", "")),
    )
    sync_text_field(
        "task_label",
        source_token=label_example_id,
        new_value=(current.task_description if current else ""),
    )
    sync_text_field(
        "label_notes",
        source_token=label_example_id,
        new_value=(current.notes if current else ""),
    )
    label_video_path = st.text_input("Video path", key="label_video_path")
    label_task = st.text_input("Task description", key="task_label")
    if current and current.suggested_label:
        st.caption(
            f"Dataset-suggested draft: `{current.suggested_label}` · "
            f"anomaly_present={current.anomaly_present} · "
            f"currently verified={current.verified}"
        )
    # Refresh outcome radios when the example changes (same Streamlit quirk).
    if st.session_state.get("_label_verdict_for") != label_example_id:
        st.session_state["label_verdict"] = current.label if current else "uncertain"
        st.session_state["_label_verdict_for"] = label_example_id
    label_verdict = st.radio(
        "Ground-truth outcome (after watching)",
        options=list(VERDICTS),
        horizontal=True,
        key="label_verdict",
    )
    label_notes = st.text_area("Notes (optional)", key="label_notes")
    label_verified = st.checkbox("I watched this video and verify this label", value=False)

    preview = ROOT / label_video_path if label_video_path else None
    if preview is not None and preview.is_file():
        st.video(str(preview))

    if st.button("Save ground-truth label", type="primary"):
        if not label_verified:
            st.error("Check verification only after watching — leave unchecked to avoid saving.")
        else:
            path = upsert_label(
                example_id=label_example_id.strip(),
                video_path=label_video_path.strip(),
                task_description=label_task.strip(),
                label=label_verdict,  # type: ignore[arg-type]
                notes=label_notes.strip(),
                verified=True,
            )
            st.success(f"Saved verified label to `{path}`")

    st.markdown("**Current labels**")
    st.dataframe(
        [
            {
                "example_id": ex.example_id,
                "suggested_label": ex.suggested_label,
                "label": ex.label,
                "verified": ex.verified,
                "anomaly_present": ex.anomaly_present,
                "needs_manual_review": ex.needs_manual_review,
                "task_description": ex.task_description,
                "video_path": ex.video_path,
                "source_dataset": ex.source_dataset,
            }
            for ex in load_labels()
        ],
        use_container_width=True,
    )

    render_event_annotation(load_labels())

# --- Comparison tab ---
with tab_compare:
    st.subheader("Verified outcome vs Muse prediction")
    st.write(
        "One row per independent episode. Filter by frame count to compare 4-frame vs 8-frame "
        "runs of the **same** videos — those are not separate ground-truth cases."
    )
    compare_frames = st.selectbox(
        "Show Muse predictions for frame count",
        options=["latest any", 4, 8, 12, 16],
        index=0,
    )
    fc = None if compare_frames == "latest any" else int(compare_frames)
    rows = build_comparison_rows(frame_count=fc)
    st.dataframe(rows, use_container_width=True)
    n_verified = sum(1 for r in rows if r["verified"])
    n_correct = sum(1 for r in rows if r["correct"] is True)
    n_wrong = sum(1 for r in rows if r["correct"] is False)
    st.caption(
        f"Verified rows: {n_verified} · Correct: {n_correct} · Incorrect: {n_wrong} · "
        f"Unreviewed / no prediction: {len(rows) - n_verified}"
    )

# --- Batch tab (opt-in paid calls) ---
with tab_batch:
    st.subheader("Batch evaluation (manual trigger)")
    st.warning(
        "This spends Fireworks credits. Import videos first with "
        "`python import_botfails.py --download`. Nothing is auto-analyzed."
    )
    demos = list_demo_videos()
    labels_map = label_lookup()
    if not demos:
        st.warning("No videos in sample_videos/ or eval_videos/.")
    else:
        demo_labels = []
        for path in demos:
            eid = example_id_for_video(path.name, "batch")
            ex = labels_map.get(eid)
            demo_labels.append(
                {
                    "file": relative_video_path(path),
                    "example_id": eid,
                    "task": getattr(ex, "task_description", ""),
                    "suggested_label": getattr(ex, "suggested_label", None),
                    "verified": getattr(ex, "verified", False),
                }
            )
        st.dataframe(demo_labels, use_container_width=True)

    selected_ids = st.multiselect(
        "Episodes to analyze (leave empty to analyze none)",
        options=[example_id_for_video(p.name, "batch") for p in demos],
        default=[],
    )
    use_label_tasks = st.checkbox("Use each episode's stored task description", value=True)
    fallback_task = st.text_input(
        "Fallback task description",
        value="Complete the demonstrated manipulation task",
        key="task_batch",
    )
    run_batch = st.button(
        f"Run Muse on {len(selected_ids)} selected episode(s) × {frame_count} frames",
        type="primary",
        disabled=not api_ready or not selected_ids,
    )
    if run_batch and api_ready and selected_ids:
        id_to_path = {example_id_for_video(p.name, "batch"): p for p in demos}
        progress = st.progress(0.0)
        results = []
        for index, eid in enumerate(selected_ids):
            path = id_to_path[eid]
            progress.progress(index / max(len(selected_ids), 1), text=path.name)
            ex = labels_map.get(eid)
            task = (
                ex.task_description
                if use_label_tasks and ex and ex.task_description
                else fallback_task
            )
            raw = path.read_bytes()
            vision = cached_inspect(raw)
            diagnosis, selected, pred_path = run_analysis(
                video_bytes=raw,
                video_name=path.name,
                source_kind="batch",
                task_description=task,
                frame_count=frame_count,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
                vision_frames=vision.frames,
                example_id=eid,
            )
            results.append(
                {
                    "example_id": eid,
                    "verdict": diagnosis.verdict,
                    "model_confidence": diagnosis.confidence,
                    "frames": len(selected),
                    "cost_usd": estimate_cost_usd(diagnosis.usage),
                    "prediction": str(pred_path),
                }
            )
        progress.progress(1.0, text="Done")
        st.dataframe(results, use_container_width=True)
        st.info("Verify labels in **Ground-truth labels**, then open **Comparison**.")

    st.divider()
    render_eval_panel()

# --- History tab ---
with tab_history:
    st.subheader("Saved predictions")
    preds = load_predictions()
    if not preds:
        st.write("No predictions saved yet.")
    else:
        rows = []
        for row in reversed(preds):
            rows.append(
                {
                    "saved_at_utc": row.get("saved_at_utc"),
                    "example_id": row.get("example_id"),
                    "video_name": row.get("video_name"),
                    "model": row.get("model"),
                    "frame_count": row.get("frame_count"),
                    "verdict": row.get("verdict") or (row.get("diagnosis") or {}).get("verdict"),
                    "model_confidence": row.get("model_confidence"),
                    "cost_estimate_usd": row.get("cost_estimate_usd"),
                    "reasoning_effort": row.get("reasoning_effort"),
                    "timestamps": row.get("frame_timestamps_s"),
                }
            )
        st.dataframe(rows, use_container_width=True)
        st.caption(
            "Multiple frame-count rows can share one example_id. "
            "Accuracy counts each verified example once."
        )
