"""Mask decoding and rendering against real cached SAM masks."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

import tracking

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_videos" / "sample.mp4"
SUMMARY = tracking.TRACKING_ROOT / "5fe4489e918f460248ade412" / "summary.json"
pytestmark = pytest.mark.skipif(
    not (SAMPLE.is_file() and SUMMARY.is_file()), reason="sample video / SAM cache not present"
)


@pytest.fixture(scope="module")
def cached():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))["observations"]


@pytest.fixture(scope="module")
def frame0():
    import av
    with av.open(io.BytesIO(SAMPLE.read_bytes())) as c:
        return next(c.decode(video=0)).to_ndarray(format="rgb24")


def _first(cached, concept, frame=0):
    return next(o for o in cached if o["concept"] == concept and o["frame_index"] == frame)


def test_decoder_matches_official_parser_bit_for_bit(cached):
    from meta_sam_parser._mask_conversion import RLEObject, _decode  # cross-check only

    for o in cached[::50]:
        rle = o["mask_rle"]
        h, w = rle["size"]
        ref = _decode(RLEObject(size=(h, w), counts=rle["counts"]))
        ref_hw = np.frombuffer(ref.data, dtype=np.uint8).reshape((w, h)).T.astype(bool)
        assert np.array_equal(tracking.decode_mask_rle(rle), ref_hw)


def test_masks_are_box_local_and_paste_at_bbox_origin(cached, frame0):
    o = _first(cached, "screwdriver")
    local = tracking.decode_mask_rle(o["mask_rle"])
    x1, y1, x2, y2 = o["bbox"]
    assert local.shape == (y2 - y1, x2 - x1) != frame0.shape[:2]  # box-local raster
    full = tracking.mask_in_frame(o["mask_rle"], tuple(o["bbox"]), frame0.shape[:2])
    ys, xs = np.nonzero(full)
    assert xs.min() >= x1 and xs.max() < x2 and ys.min() >= y1 and ys.max() < y2
    assert full.sum() == local.sum()


def test_mask_pixels_land_on_the_object(cached, frame0):
    gray = frame0.mean(axis=2)
    for concept, darker in (("screwdriver", True), ("white box", False)):
        o = _first(cached, concept)
        full = tracking.mask_in_frame(o["mask_rle"], tuple(o["bbox"]), gray.shape)
        x1, y1, x2, y2 = (int(v) for v in o["bbox"])
        box = np.zeros_like(full)
        box[y1:y2, x1:x2] = True
        inside, rest = gray[full].mean(), gray[box & ~full].mean()
        assert (inside < rest - 30) if darker else (inside > rest + 30), (concept, inside, rest)


def test_size_mismatch_is_refused_not_guessed(cached):
    o = _first(cached, "screwdriver")
    x1, y1, x2, y2 = o["bbox"]
    assert tracking.mask_in_frame(o["mask_rle"], (x1, y1, x2 + 5, y2), (720, 1280)) is None


def test_paint_changes_pixels_only_near_mask(cached, frame0):
    o = _first(cached, "screwdriver")
    canvas = frame0.copy()
    assert tracking._paint_rle(canvas, o["mask_rle"], (0, 200, 255), tuple(o["bbox"]))
    changed = np.any(canvas != frame0, axis=2)
    x1, y1, x2, y2 = (int(v) for v in o["bbox"])
    assert changed[y1:y2, x1:x2].sum() > 1000
    outside = changed.copy()
    outside[y1 - 2 : y2 + 2, x1 - 2 : x2 + 2] = False
    assert not outside.any()
    assert not tracking._paint_rle(canvas, o["mask_rle"], (0, 0, 0), None)


def test_cached_result_renders_mask_overlays_without_touching_originals(tmp_path):
    video = SAMPLE.read_bytes()
    r = tracking.load_cached_tracking(video, ["screwdriver", "white box"], media_kind="video")
    original = sorted((Path(r.cache_dir) / "overlays").glob("*.png"))
    before = [p.stat().st_mtime for p in original]
    r.cache_dir = str(tmp_path)
    paths = tracking.render_cached_mask_overlays(video, r)
    assert len(paths) == 12 and all(p.parent == tmp_path / "overlays_masks" for p in paths)
    assert [p.stat().st_mtime for p in original] == before


def test_uncompressed_counts_still_supported():
    rle = {"size": [2, 3], "counts": [1, 2, 3]}  # column-major: 0, 1, 1, 0, 0, 0
    assert tracking.decode_mask_rle(rle).tolist() == [[False, True, False], [True, False, False]]
