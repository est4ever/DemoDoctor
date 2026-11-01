"""Deterministic tests for conservative dish-rack final-state verification."""

from __future__ import annotations

import numpy as np
import pytest

import container as C
import final_state as FS


def _rect(shape, x0, y0, x1, y1):
    m = np.zeros(shape, dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


def test_outside_without_interior_calibration():
    shape = (200, 200)
    rack = _rect(shape, 20, 20, 100, 160)
    plate = _rect(shape, 140, 40, 180, 100)  # clearly outside
    r = FS.assess_object_placement(plate, rack, calibration=None, calibration_footprint=None)
    assert r.region == "outside"
    assert r.reliable is False
    assert "footprint" in r.method.lower() or "outside" in " ".join(r.notes).lower()


def test_unknown_when_overlapping_rim_without_reliable_interior():
    shape = (200, 200)
    rack = _rect(shape, 20, 20, 120, 160)
    # Plate straddles the rack edge → footprint_fraction mid-range → unknown
    plate = _rect(shape, 90, 60, 150, 120)
    r = FS.assess_object_placement(plate, rack, calibration=None, calibration_footprint=None)
    assert r.region == "unknown"


def test_eroded_interior_supports_clear_inside():
    shape = (240, 240)
    rack = _rect(shape, 30, 30, 200, 200)
    fp = C.fill_holes(rack)
    cal = FS.approximate_interior_from_footprint(
        fp, concept="dish rack", calibration_frame=0, video_sha256="test", erode_px=10
    )
    # Object deep inside eroded region
    plate = _rect(shape, 90, 90, 140, 140)
    r = FS.assess_object_placement(
        plate, rack, calibration=cal, calibration_footprint=fp,
        inside_frac=0.85,
    )
    assert r.reliable is True
    assert r.region == "inside"
    assert r.assessment["interior_fraction"] is not None
    assert r.assessment["interior_fraction"] >= 0.85


def test_eroded_interior_rim_stays_unknown_not_inside():
    shape = (240, 240)
    rack = _rect(shape, 30, 30, 200, 200)
    fp = C.fill_holes(rack)
    cal = FS.approximate_interior_from_footprint(
        fp, concept="dish rack", calibration_frame=0, video_sha256="test", erode_px=15
    )
    # Thin plate on the outer band of the footprint (likely outside eroded interior)
    plate = _rect(shape, 32, 100, 50, 140)
    r = FS.assess_object_placement(
        plate, rack, calibration=cal, calibration_footprint=fp, inside_frac=0.85
    )
    assert r.region in ("unknown", "outside")
    assert r.region != "inside"


def test_missing_container_is_unknown():
    plate = _rect((100, 100), 10, 10, 40, 40)
    r = FS.assess_object_placement(plate, None)
    assert r.region == "unknown"
    assert "container" in (r.reason or "").lower() or not r.reliable


def test_empty_object_mask_unknown():
    rack = _rect((100, 100), 10, 10, 80, 80)
    plate = np.zeros((100, 100), dtype=bool)
    r = FS.assess_object_placement(plate, rack)
    assert r.region == "unknown"


def test_approximate_interior_rejects_over_erosion():
    tiny = _rect((50, 50), 20, 20, 28, 28)
    with pytest.raises(ValueError):
        FS.approximate_interior_from_footprint(
            tiny, concept="dish rack", calibration_frame=0, video_sha256="x", erode_px=20
        )


def test_assess_many_preserves_order():
    shape = (200, 200)
    rack = _rect(shape, 20, 20, 100, 160)
    outs = FS.assess_many(
        [_rect(shape, 140, 40, 180, 80), _rect(shape, 30, 40, 50, 80)],
        rack,
    )
    assert len(outs) == 2
    assert outs[0].region == "outside"


def test_near_rack_low_overlap_is_unknown_not_outside():
    """Upright-in-slot style: thin mask just outside filled footprint → unknown.

    Does not assert inside — only that we abstain instead of false outside.
    """
    shape = (240, 240)
    rack = _rect(shape, 40, 40, 160, 200)
    # Thin vertical strip immediately to the right of the rack (slot-like)
    plate = _rect(shape, 160, 80, 172, 180)
    r = FS.assess_object_placement(plate, rack, calibration=None)
    assert r.assessment.get("footprint_fraction", 1) <= 0.05 or r.region != "inside"
    assert r.region == "unknown"
    assert r.geometry_rule == "near_rack_proximity_unknown"
    assert r.assessment.get("near_container_fraction", 0) >= FS.DEFAULT_NEAR_RACK_FRAC
    assert "near container" in (r.reason or "").lower() or any(
        "near" in n.lower() for n in r.notes
    )


def test_far_from_rack_still_outside():
    shape = (240, 240)
    rack = _rect(shape, 20, 20, 100, 160)
    plate = _rect(shape, 180, 40, 220, 100)  # clearly separated
    r = FS.assess_object_placement(plate, rack, calibration=None)
    assert r.region == "outside"
    assert r.geometry_rule == "footprint_outside_clearly_separated"
    assert r.assessment.get("near_container_fraction", 1) < FS.DEFAULT_NEAR_RACK_FRAC


def test_near_rack_ambiguity_with_eroded_interior_stays_unknown():
    shape = (240, 240)
    rack = _rect(shape, 30, 30, 180, 200)
    fp = C.fill_holes(rack)
    cal = FS.approximate_interior_from_footprint(
        fp, concept="dish rack", calibration_frame=0, video_sha256="test", erode_px=12
    )
    # Thin strip just outside filled footprint (x>=180; rack ends at 180 exclusive)
    # so footprint_fraction≈0 → outside path, then proximity → unknown.
    plate = _rect(shape, 180, 80, 192, 160)
    r = FS.assess_object_placement(
        plate, rack, calibration=cal, calibration_footprint=fp, inside_frac=0.85
    )
    assert r.region == "unknown"
    assert r.region != "outside"
    assert r.region != "inside"
    assert r.geometry_rule == "near_rack_proximity_unknown"


def test_proximity_never_yields_inside():
    """≥50% of mask in 20px-dilated rack with low footprint overlap → unknown only."""
    shape = (240, 240)
    rack = _rect(shape, 40, 40, 160, 200)
    # Adjacent to rack edge (no footprint overlap); proximity must not promote to inside.
    plate = _rect(shape, 160, 70, 175, 170)
    r = FS.assess_object_placement(plate, rack, calibration=None)
    assert r.region != "inside"
    assert r.geometry_rule != "reliable_interior_inside"
    near = FS.near_container_fraction(plate, rack, dilate_px=FS.DEFAULT_NEAR_RACK_DILATE_PX)
    assert near >= FS.DEFAULT_NEAR_RACK_FRAC
    assert r.region == "unknown"
    assert r.geometry_rule == "near_rack_proximity_unknown"


def test_partial_footprint_overlap_stays_unknown():
    """Mid-range footprint overlap (neither outside nor inside) → unknown."""
    shape = (200, 200)
    rack = _rect(shape, 20, 20, 120, 160)
    plate = _rect(shape, 90, 60, 150, 120)  # straddles edge
    r = FS.assess_object_placement(plate, rack, calibration=None)
    assert r.region == "unknown"
    assert r.geometry_rule in (
        "insufficient_geometry_unknown",
        "near_rack_proximity_unknown",
    )


def test_unreliable_segmentation_blocks_inside():
    """Even high interior_fraction cannot become inside when assessment is unreliable."""
    shape = (240, 240)
    rack = _rect(shape, 30, 30, 200, 200)
    fp = C.fill_holes(rack)
    cal = FS.approximate_interior_from_footprint(
        fp, concept="dish rack", calibration_frame=0, video_sha256="test", erode_px=10
    )
    # Drift the live footprint so IoU vs calibration fails reliability
    drifted = _rect(shape, 80, 30, 230, 200)
    plate = _rect(shape, 110, 90, 150, 140)
    r = FS.assess_object_placement(
        plate, drifted, calibration=cal, calibration_footprint=fp, inside_frac=0.85
    )
    assert r.reliable is False
    assert r.region != "inside"
    if r.geometry_rule == "inside_blocked_unreliable":
        assert r.region == "unknown"


def test_geometry_rule_recorded_for_clear_inside():
    shape = (240, 240)
    rack = _rect(shape, 30, 30, 200, 200)
    fp = C.fill_holes(rack)
    cal = FS.approximate_interior_from_footprint(
        fp, concept="dish rack", calibration_frame=0, video_sha256="test", erode_px=10
    )
    plate = _rect(shape, 90, 90, 140, 140)
    r = FS.assess_object_placement(
        plate, rack, calibration=cal, calibration_footprint=fp, inside_frac=0.85
    )
    assert r.region == "inside"
    assert r.geometry_rule == "reliable_interior_inside"
    assert r.to_dict()["geometry_rule"] == "reliable_interior_inside"
