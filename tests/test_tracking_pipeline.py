"""Tracking pipeline tests. No network: SAM calls are replaced with stubs, and
real-data tests read only the local sample video and existing cache."""

from __future__ import annotations

import asyncio
import io
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import sam_api
import tracking
from track_stitch import ChunkSpec

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_videos" / "sample.mp4"
LEGACY_KEY = "5fe4489e918f460248ade412"  # full-video screwdriver + white box run

needs_sample = pytest.mark.skipif(not SAMPLE.is_file(), reason="sample video not downloaded")
needs_cache = pytest.mark.skipif(
    not (tracking.TRACKING_ROOT / LEGACY_KEY / "summary.json").is_file(),
    reason="legacy SAM cache not present",
)


def _box(obj_id, frame, x=10.0):
    return SimpleNamespace(
        kind="box", object_id=obj_id, frame=SimpleNamespace(frame_index=frame),
        left=x, top=20.0, right=x + 30.0, bottom=80.0, confidence=0.7,
    )


def _run_call(monkeypatch, tmp_path, result, *, chunk, force=False):
    monkeypatch.setattr(tracking, "CHUNK_CACHE_ROOT", tmp_path)
    calls = []

    async def fake_segment_video(file_id, prompt, **_):
        calls.append((file_id, prompt))
        return result

    async def fake_upload():
        return "file-test"

    monkeypatch.setattr(sam_api, "segment_video", fake_segment_video)
    coro = tracking.Sam31Tracker()._run_chunk_call(
        chunk=chunk, concept="screwdriver", prompt_text="screwdriver", prompt_mode="concept",
        tag="", digest="abc", fps=30.0, ensure_uploaded=fake_upload, force_refresh=force,
    )
    obs, call = asyncio.run(coro)
    return obs, call, calls


# --- chunk call: offsets, outcome, cache ------------------------------

def test_chunk_call_maps_local_frames_to_global_and_records_outcome(monkeypatch, tmp_path):
    result = SimpleNamespace(
        records=[_box("0", 0), _box("0", 5), _box("0", 99)],
        outcome=SimpleNamespace(status="completed"),
        diagnostics=(),
    )
    chunk = ChunkSpec(2, 240, 361, 360)
    obs, call, sent = _run_call(monkeypatch, tmp_path, result, chunk=chunk)
    assert sent == [("file-test", "screwdriver")]
    assert [o.frame_index for o in obs] == [240, 245, 339]
    assert [o.timestamp_s for o in obs] == [8.0, 8.167, 11.3]
    assert {(o.chunk_index, o.local_object_id) for o in obs} == {(2, "0")}
    assert (call.status, call.n_records, call.n_observations) == ("completed", 3, 3)


def test_incomplete_empty_response_is_not_treated_as_empty(monkeypatch, tmp_path):
    result = SimpleNamespace(
        records=[], outcome=SimpleNamespace(status="incomplete", reason="eof", detail=None), diagnostics=()
    )
    chunk = ChunkSpec(0, 0, 121, 120)
    obs, call, _ = _run_call(monkeypatch, tmp_path, result, chunk=chunk)
    assert obs == [] and call.status == "incomplete" and "eof" in call.reason
    from track_stitch import concept_frame_states
    assert set(concept_frame_states(obs, [chunk], [call], "screwdriver", 121)) == {"unknown"}
    # Incomplete entries are written for audit but never reused as a cache hit.
    _, _, sent_again = _run_call(monkeypatch, tmp_path, result, chunk=chunk)
    assert len(sent_again) == 1


def test_completed_chunk_is_reused_without_new_call(monkeypatch, tmp_path):
    result = SimpleNamespace(records=[_box("0", 1)], outcome=SimpleNamespace(status="completed"), diagnostics=())
    chunk = ChunkSpec(0, 0, 121, 120)
    _run_call(monkeypatch, tmp_path, result, chunk=chunk)
    obs, call, sent = _run_call(monkeypatch, tmp_path, result, chunk=chunk)
    assert sent == [] and call.from_cache and [o.frame_index for o in obs] == [1]


def test_records_outside_chunk_are_dropped_and_reported(monkeypatch, tmp_path):
    result = SimpleNamespace(records=[_box("0", 3), _box("0", 500)], outcome=SimpleNamespace(status="completed"), diagnostics=())
    obs, call, _ = _run_call(monkeypatch, tmp_path, result, chunk=ChunkSpec(0, 0, 10, 10))
    assert [o.frame_index for o in obs] == [3]
    assert "outside chunk" in call.reason


# --- seeding -------------------------------------------------------------

def test_seed_prompt_uses_official_box_format():
    text = tracking.build_seed_prompt((1280, 720), 0, (863, 307, 918, 606))
    assert text == "<0f>0<|box;x1=863;y1=307;x2=917;y2=605;w=1280;h=720|>"


def test_seed_boxes_only_for_objects_lost_on_overlap_frame():
    chunk = ChunkSpec(2, 240, 361, 360)
    prev = [tracking.ObjectTrackObservation(8.0, "s:0", "s", 240, (863.0, 313.0, 918.0, 606.0), None, local_object_id="0")]
    assert tracking._seed_boxes(prev, [], chunk) == [("0", (863, 313, 918, 606))]
    refound = [tracking.ObjectTrackObservation(8.0, "s:0", "s", 240, (862.0, 312.0, 918.0, 606.0), None)]
    assert tracking._seed_boxes(prev, refound, chunk) == []


# --- timestamp alignment on real video ---------------------------------

def _decode(video_bytes, upto):
    import av
    frames = []
    with av.open(io.BytesIO(video_bytes)) as c:
        for i, f in enumerate(c.decode(video=0)):
            frames.append(f.to_ndarray(format="gray").astype(np.int16))
            if i + 1 >= upto:
                break
    return frames


@needs_sample
def test_frame_range_clip_starts_at_requested_global_frame():
    video = SAMPLE.read_bytes()
    clip = tracking.extract_frame_range_mp4(video, start_frame=240, end_frame=246)
    clip_frames = _decode(clip, 10)
    assert len(clip_frames) == 6
    original = _decode(video, 247)
    diffs = {i: float(np.abs(clip_frames[0] - original[i]).mean()) for i in (236, 238, 240, 242, 244)}
    assert min(diffs, key=diffs.get) == 240


# --- regression on existing cached SAM data ---------------------------

@needs_sample
@needs_cache
def test_legacy_cache_loads_deduped_stitched_and_honest():
    video = SAMPLE.read_bytes()
    r = tracking.load_cached_tracking(video, ["screwdriver", "white box"], media_kind="video")
    assert r is not None and r.from_cache
    keys = Counter((o.concept, o.object_id, o.frame_index) for o in r.observations)
    assert max(keys.values()) == 1
    assert len(r.observations) == 978  # 985 stored minus 7 overlap duplicates
    sd = r.diagnostics.per_concept["screwdriver"]
    assert (sd["frames_detected"], sd["frames_not_detected"], sd["frames_unknown"]) == (241, 0, 496)
    assert [(x["state"], x["start_frame"], x["end_frame"]) for x in sd["state_runs"]] == [
        ("detected", 0, 241), ("unknown", 241, 737)
    ]
    assert sd["global_tracks"] == ["screwdriver:0"]
    link = [l for l in r.chunk_log["links"] if l["concept"] == "screwdriver" and l["chunk_index"] == 1][0]
    assert link["decision"] == "linked" and link["mean_iou"] > 0.9 and link["shared_frames"] == [120]
    wb = r.diagnostics.per_concept["white box"]
    assert wb["frames_detected"] == 737 and wb["global_tracks"] == ["white box:0"]
    # Frame 120 comes from its owning chunk (1); frame 240 from chunk 1 since chunk 2 found nothing.
    by_frame = {o.frame_index: o for o in r.observations if o.concept == "screwdriver"}
    assert by_frame[120].chunk_index == 1 and by_frame[240].chunk_index == 1
    assert all(o.timestamp_s == round(o.frame_index / 30.0, 3) for o in r.observations)


@needs_sample
@needs_cache
def test_backfill_and_dry_run_plan(monkeypatch, tmp_path):
    monkeypatch.setattr(tracking, "CHUNK_CACHE_ROOT", tmp_path)
    video = SAMPLE.read_bytes()
    assert tracking.backfill_chunk_cache(video) == 14
    assert tracking.backfill_chunk_cache(video) == 0  # never overwrites
    plan = tracking.plan_tracking_calls(video, ["screwdriver", "white box", "robot gripper"])
    paid = sorted((r["chunk"], r["concept"]) for r in plan if r["action"] == "PAID CALL")
    assert paid == sorted(
        [(i, "screwdriver") for i in range(2, 7)] + [(i, "robot gripper") for i in range(7)]
    )
