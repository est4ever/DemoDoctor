"""Unit tests for chunk planning, identity stitching, and frame states.

Inputs here are small hand-built observations used only to exercise the
algorithms; they are not tracking results and never reach the app.
"""

from __future__ import annotations

from tracking import ObjectTrackObservation
from track_stitch import (
    ChunkCall,
    ChunkSpec,
    assign_legacy_chunks,
    bbox_iou,
    concept_frame_states,
    legacy_chunk_log,
    plan_chunks,
    state_runs,
    stitch_tracks,
)

A = (100.0, 100.0, 150.0, 300.0)
B = (600.0, 100.0, 650.0, 300.0)


def obs(frame, chunk, local, bbox, concept="tool", conf=None):
    return ObjectTrackObservation(
        timestamp_s=frame / 30,
        object_id=f"{concept}:{local}",
        concept=concept,
        frame_index=frame,
        bbox=bbox,
        centroid=None,
        track_status="visible",
        confidence=conf,
        chunk_index=chunk,
        local_object_id=str(local),
    )


TWO_CHUNKS = [ChunkSpec(0, 0, 11, 10), ChunkSpec(1, 10, 20, 20)]


# --- plan_chunks ---------------------------------------------------------

def test_plan_matches_legacy_inclusive_end_chunks():
    chunks = plan_chunks(737, 120, overlap_frames=1)
    assert [(c.start_frame, c.end_frame, c.owned_end_frame) for c in chunks] == [
        (0, 121, 120), (120, 241, 240), (240, 361, 360), (360, 481, 480),
        (480, 601, 600), (600, 721, 720), (720, 737, 737),
    ]


def test_owned_ranges_partition_all_frames_exactly_once():
    for n, size, overlap in [(737, 120, 1), (100, 30, 0), (95, 30, 5), (10, 30, 1)]:
        chunks = plan_chunks(n, size, overlap_frames=overlap)
        owned = [f for c in chunks for f in range(c.start_frame, c.owned_end_frame)]
        assert owned == list(range(n))
        assert all(c.end_frame <= n for c in chunks)


def test_tiny_tail_folds_into_previous_chunk():
    chunks = plan_chunks(125, 120, overlap_frames=1, min_last_chunk_frames=15)
    assert [(c.start_frame, c.end_frame) for c in chunks] == [(0, 125)]


def test_bbox_iou():
    assert bbox_iou(A, A) == 1.0
    assert bbox_iou(A, B) == 0.0
    assert bbox_iou(A, None) == 0.0
    assert 0.0 < bbox_iou(A, (125.0, 100.0, 175.0, 300.0)) < 1.0


# --- stitch_tracks: identity -------------------------------------------

def test_same_local_id_for_different_objects_is_not_merged():
    # Chunk 0 local "0" is object A; chunk 1 local "0" is a different object B.
    data = [obs(f, 0, 0, A) for f in range(0, 11)] + [obs(f, 1, 0, B) for f in range(10, 20)]
    out, links = stitch_tracks(data, TWO_CHUNKS)
    assert {o.object_id for o in out if o.frame_index < 10} == {"tool:0"}
    assert {o.object_id for o in out if o.frame_index > 10} == {"tool:1"}
    assert [l["decision"] for l in links] == ["new_track", "new_track"]


def test_swapped_local_ids_are_linked_by_overlap():
    data = (
        [obs(f, 0, 0, A) for f in range(11)]
        + [obs(f, 0, 1, B) for f in range(11)]
        + [obs(f, 1, 1, A) for f in range(10, 20)]  # A now reported as local 1
        + [obs(f, 1, 0, B) for f in range(10, 20)]
    )
    out, _ = stitch_tracks(data, TWO_CHUNKS)
    ids_at_a = {o.object_id for o in out if o.bbox == A}
    ids_at_b = {o.object_id for o in out if o.bbox == B}
    assert ids_at_a == {"tool:0"} and ids_at_b == {"tool:1"}


def test_gap_produces_new_track_not_silent_merge():
    chunks = [ChunkSpec(0, 0, 11, 10), ChunkSpec(1, 10, 21, 20), ChunkSpec(2, 20, 30, 30)]
    data = [obs(f, 0, 0, A) for f in range(11)] + [obs(f, 2, 0, A) for f in range(20, 30)]
    out, _ = stitch_tracks(data, chunks)
    assert {o.object_id for o in out if o.frame_index <= 10} == {"tool:0"}
    assert {o.object_id for o in out if o.frame_index >= 20} == {"tool:1"}


# --- stitch_tracks: overlap dedupe -------------------------------------

def test_overlap_frame_kept_once_preferring_owning_chunk():
    data = [obs(f, 0, 0, A, conf=0.1) for f in range(11)] + [obs(f, 1, 0, A, conf=0.9) for f in range(10, 20)]
    out, _ = stitch_tracks(data, TWO_CHUNKS)
    frames = [o.frame_index for o in out]
    assert frames == list(range(20))
    assert [o.confidence for o in out if o.frame_index == 10] == [0.9]  # chunk 1 owns frame 10


def test_overlap_detection_kept_when_owner_missed_it():
    data = [obs(f, 0, 0, A) for f in range(11)]  # chunk 1 returned nothing
    out, _ = stitch_tracks(data, TWO_CHUNKS)
    assert [o.frame_index for o in out] == list(range(11))


# --- frame states ------------------------------------------------------

def test_states_distinguish_detected_not_detected_unknown():
    chunks = [ChunkSpec(0, 0, 10, 10), ChunkSpec(1, 10, 20, 20), ChunkSpec(2, 20, 30, 30)]
    calls = [
        ChunkCall(0, "tool", "completed"),
        ChunkCall(1, "tool", "completed"),
        ChunkCall(2, "tool", "unverified"),
    ]
    data = [obs(f, 0, 0, A) for f in range(10)]
    states = concept_frame_states(data, chunks, calls, "tool", 30)
    assert states[:10] == ["detected"] * 10
    assert states[10:20] == ["not_detected"] * 10
    assert states[20:] == ["unknown"] * 10
    assert [(r["state"], r["start_frame"], r["end_frame"]) for r in state_runs(states)] == [
        ("detected", 0, 10), ("not_detected", 10, 20), ("unknown", 20, 30)
    ]


def test_failed_incomplete_and_unqueried_are_unknown():
    chunks = [ChunkSpec(0, 0, 10, 10), ChunkSpec(1, 10, 20, 20)]
    calls = [ChunkCall(0, "tool", "failed"), ChunkCall(1, "tool", "incomplete")]
    data = [obs(12, 1, 0, A)]  # partial result from the incomplete call
    states = concept_frame_states(data, chunks, calls, "tool", 25)
    assert states[12] == "detected"
    assert set(states[:12] + states[13:]) == {"unknown"}
    assert concept_frame_states([], chunks, calls, "other", 5) == ["unknown"] * 5


# --- legacy cache parsing ----------------------------------------------

LEGACY_NOTES = [
    "Chunked full-video tracking (24.6s @ 30.0fps).",
    "chunk0: t=0.0-4.0s file_id=file-1",
    "chunk0/tool: ok observations=121",
    "chunk1: t=4.0-8.0s file_id=file-2",
    "chunk1/tool: ok observations=0",
    "chunk1/box: FAILED ResponsesStreamSourceError: boom",
    "chunk2: t=8.0-8.6s file_id=file-3",
]


def test_legacy_chunked_notes():
    chunks, calls = legacy_chunk_log(LEGACY_NOTES, fps=30.0, n_frames=259, concepts=["tool", "box"])
    assert [(c.start_frame, c.end_frame, c.owned_end_frame) for c in chunks] == [
        (0, 121, 120), (120, 241, 240), (240, 259, 259)
    ]
    assert [(c.chunk_index, c.concept, c.status, c.n_observations) for c in calls] == [
        (0, "tool", "unverified", 121), (1, "tool", "unverified", 0), (1, "box", "failed", 0)
    ]


def test_legacy_single_request_notes():
    notes = ["Uploaded x.mp4 as file-9", "video concept='tool'", "tool: outcome=completed records=242"]
    chunks, calls = legacy_chunk_log(notes, fps=30.0, n_frames=121, concepts=["tool", "box"])
    assert chunks == [ChunkSpec(0, 0, 121, 121)]
    assert [(c.concept, c.status) for c in calls] == [("tool", "completed"), ("box", "unverified")]


def test_assign_legacy_chunks_uses_stable_order_for_duplicate_frames():
    first = obs(120, None, 0, A, conf=0.78)
    second = obs(120, None, 0, A, conf=0.81)
    chunks = [ChunkSpec(0, 0, 121, 120), ChunkSpec(1, 120, 241, 240)]
    out = assign_legacy_chunks([first, second], chunks)
    assert [(o.confidence, o.chunk_index) for o in out] == [(0.78, 0), (0.81, 1)]
