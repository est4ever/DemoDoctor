"""Keyframe probe tests. SAM is stubbed; nothing is sent."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import sam_api
import tracking as T

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_videos" / "sample.mp4"
pytestmark = pytest.mark.skipif(not SAMPLE.is_file(), reason="sample video not downloaded")
BOX = (245, 302, 316, 614)


@pytest.fixture(scope="module")
def video():
    return SAMPLE.read_bytes()


def test_prepare_builds_request_without_sending(video, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("prepare must not call the API")

    monkeypatch.setattr(sam_api, "segment_image_bytes", boom)
    req = T.prepare_box_probe(video, frame_index=660, box=BOX, selected_by="test")
    assert req.timestamp_s == 22.0 and req.box == BOX
    assert req.prompt_text == "<0f>0<|box;x1=245;y1=302;x2=315;y2=613;w=1280;h=720|>"
    assert req.image_png[:8] == b"\x89PNG\r\n\x1a\n"
    preview = T.probe_preview(video, req)
    assert preview.shape == (720, 1280, 3) and tuple(preview[302, 280]) == (255, 140, 0)  # box edge drawn
    with pytest.raises(ValueError):
        T.prepare_box_probe(video, frame_index=660, box=(300, 300, 300, 400))


def test_probe_result_is_stored_separately_and_not_stitched(video, monkeypatch, tmp_path):
    monkeypatch.setattr(T, "PROBE_ROOT", tmp_path)
    monkeypatch.setattr(T, "load_model_api_key", lambda: "stub")
    sent = []

    async def fake_image(image, prompt, *, mime, usage_out):
        sent.append((prompt, mime))
        usage_out["usage"] = {"images_processed": 1}
        box = SimpleNamespace(kind="box", object_id="0", frame=None, left=250.0, top=305.0, right=312.0,
                              bottom=611.0, confidence=0.9)
        return SimpleNamespace(records=[box], outcome=SimpleNamespace(status="completed"))

    monkeypatch.setattr(sam_api, "segment_image_bytes", fake_image)
    req = T.prepare_box_probe(video, frame_index=660, box=BOX)
    record = T.run_box_probe(req)
    assert sent == [(req.prompt_text, "image/png")] and record["status"] == "completed"
    assert "not stitched" in record["linking"]
    T.run_box_probe(T.prepare_box_probe(video, frame_index=660, box=BOX))  # cached: no second request
    assert len(sent) == 1

    probes = T.load_probe_observations(video, "screwdriver")
    assert [(o.object_id, o.frame_index, o.prompt_mode) for o in probes] == [("screwdriver:probe-f660", 660, "image_box")]
    assembled = T.assemble_from_chunk_cache(video, ["screwdriver", "white box"])
    assert all(o.frame_index != 660 for o in assembled.observations if o.concept == "screwdriver")
    assert assembled.diagnostics.per_concept["screwdriver"]["global_tracks"] == ["screwdriver:0"]

    import events as E

    inputs = E.SampleInputs(video, assembled, __import__("proprio").load_episode(), probes)
    tl = E.timeline_from_inputs(inputs)
    placement = [e for e in tl.events if e.event_type == "final_placement_candidate"][0]
    assert placement.status == "uncertain"  # one keyframe cannot show stationarity
    det = placement.evidence[0].claims[0]
    assert det["count"] == 1 and det["track_ids"] == ["screwdriver:probe-f660"]


def test_failed_probe_is_not_cached(video, monkeypatch, tmp_path):
    monkeypatch.setattr(T, "PROBE_ROOT", tmp_path)
    monkeypatch.setattr(T, "load_model_api_key", lambda: "stub")

    async def failing(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(sam_api, "segment_image_bytes", failing)
    record = T.run_box_probe(T.prepare_box_probe(video, frame_index=660, box=BOX))
    assert record["status"] == "failed" and not list(tmp_path.rglob("*.json"))
