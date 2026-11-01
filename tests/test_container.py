"""Container-interior geometry tests.

Synthetic masks emulate SAM's behavior: the container mask covers only *visible*
container pixels, so an object on top of it cuts a hole. They are test inputs
only. Real-data tests use the stored calibration and the frame-660 probe.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

import container as C

H = W = 200
# Container footprint 40..159 (walls 10px); interior floor 50..149.
FOOTPRINT = np.zeros((H, W), bool)
FOOTPRINT[40:160, 40:160] = True
CAL = C.InteriorCalibration(concept="box", calibration_frame=0, video_sha256="test",
                            polygon=[[50, 50], [149, 50], [149, 149], [50, 149]], method="test")


def rect(y0, y1, x0, x1):
    m = np.zeros((H, W), bool)
    m[y0:y1, x0:x1] = True
    return m


def visible_container(*occluders):
    m = FOOTPRINT.copy()
    for o in occluders:
        m &= ~o
    return m


def assess(obj, container_mask):
    return C.assess_containment(obj, container_mask, CAL, FOOTPRINT)


def test_fill_holes_restores_enclosed_regions_only():
    hole = rect(80, 120, 80, 120)
    edge = rect(90, 110, 140, 190)  # touches the outside: not a hole
    filled = C.fill_holes(visible_container(hole, edge))
    assert filled[100, 100] and not filled[100, 170] and not filled[100, 150]


def test_object_inside_interior():
    obj = rect(60, 140, 80, 120)
    r = assess(obj, visible_container(obj))
    assert r["reliable"] and r["interior_fraction"] == 1.0
    assert r["raw_mask_fraction"] == 0.0  # why the raw SAM mask cannot be used


def test_object_outside_container():
    obj = rect(20, 60, 170, 190)
    r = assess(obj, visible_container(obj))
    assert r["reliable"] and r["interior_fraction"] == 0.0 and r["footprint_fraction"] == 0.0


def test_object_partially_overlapping():
    obj = rect(90, 110, 130, 180)  # x 130..149 inside interior, the rest on wall / outside
    r = assess(obj, visible_container(obj))
    # The object hides part of the container edge; that self-occlusion is not evidence
    # the container moved, so the estimate stays reliable.
    assert r["reliable"]
    assert r["interior_fraction"] == pytest.approx(0.4, abs=0.01)


def test_object_on_rim_is_in_footprint_but_not_interior():
    obj = rect(80, 120, 41, 49)
    r = assess(obj, visible_container(obj))
    assert r["footprint_fraction"] == 1.0 and r["interior_fraction"] == 0.0


def test_object_obscuring_container_boundary_is_unreliable():
    arm = rect(30, 110, 20, 180)  # covers the container's top edge from outside
    obj = rect(60, 100, 80, 120)
    r = assess(obj, visible_container(arm, obj))
    assert not r["reliable"] and "footprint differs" in r["reason"]


def test_missing_container_or_calibration_is_unreliable():
    obj = rect(60, 140, 80, 120)
    assert C.assess_containment(obj, None, CAL, FOOTPRINT)["reason"] == "container not detected on this frame"
    r = C.assess_containment(obj, visible_container(obj), None, None)
    assert not r["reliable"] and r["interior_fraction"] is None and r["raw_mask_fraction"] == 0.0


def test_moved_container_is_unreliable():
    moved = np.roll(FOOTPRINT, 25, axis=1)
    obj = rect(60, 140, 80, 120)
    r = C.assess_containment(obj, moved & ~obj, CAL, FOOTPRINT)
    assert not r["reliable"]


# --- real calibration ----------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
real = pytest.mark.skipif(
    not ((ROOT / "sample_videos" / "sample.mp4").is_file() and C.SAMPLE_CALIBRATION.is_file()),
    reason="needs sample video and stored calibration",
)


@real
def test_stored_calibration_is_reproducible_from_frame0():
    stored = C.InteriorCalibration.load(C.SAMPLE_CALIBRATION)
    fresh = C.calibrate_sample(save=False)
    assert np.allclose(np.array(fresh.polygon), np.array(stored.polygon), atol=0.5)
    assert stored.video_sha256 == hashlib.sha256((ROOT / "sample_videos" / "sample.mp4").read_bytes()).hexdigest()
    assert max(stored.measurements["max_fit_residual_px"].values()) <= 3.0


@real
def test_calibrated_interior_lies_inside_empty_container_footprint():
    import tracking as T

    video = (ROOT / "sample_videos" / "sample.mp4").read_bytes()
    cal = C.InteriorCalibration.load(C.SAMPLE_CALIBRATION)
    box0 = next(o for o in T.assemble_from_chunk_cache(video, ["white box"]).observations if o.frame_index == 0)
    fp = C.fill_holes(T.mask_in_frame(box0.mask_rle, box0.bbox, (720, 1280)))
    interior = C.polygon_mask(cal.polygon, (720, 1280))
    assert (interior & fp).sum() / interior.sum() >= 0.99
    assert 0.5 < interior.sum() / fp.sum() < 0.85  # strictly smaller than the footprint (walls excluded)


@real
def test_frame660_probe_is_inside_interior_while_raw_mask_says_outside():
    import tracking as T

    video = (ROOT / "sample_videos" / "sample.mp4").read_bytes()
    probes = [o for o in T.load_probe_observations(video, "screwdriver") if o.frame_index == 660]
    if not probes:
        pytest.skip("frame-660 probe not present")
    cal = C.InteriorCalibration.load(C.SAMPLE_CALIBRATION)
    boxes = {o.frame_index: o for o in T.assemble_from_chunk_cache(video, ["white box"]).observations}
    fp0 = C.fill_holes(T.mask_in_frame(boxes[0].mask_rle, boxes[0].bbox, (720, 1280)))
    om = T.mask_in_frame(probes[0].mask_rle, probes[0].bbox, (720, 1280))
    cm = T.mask_in_frame(boxes[660].mask_rle, boxes[660].bbox, (720, 1280))
    r = C.assess_containment(om, cm, cal, fp0)
    assert r["reliable"] and r["interior_fraction"] >= 0.99
    assert r["raw_mask_fraction"] < 0.01  # the flaw this module fixes
