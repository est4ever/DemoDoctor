"""Verifier tests: the real sample timeline must verify, and tampered copies of it
must be flagged (the verifier recomputes claims from raw data)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not ((ROOT / "sample_videos" / "sample.mp4").is_file()
         and (ROOT / "data" / "lerobot" / "ankithreddy__so101_pickplace_uno" / "SOURCE.json").is_file()
         and list((ROOT / "data" / "tracking" / "chunks").glob("*/f000360-000481/screwdriver__box_seed_*.json"))),
    reason="needs sample video, joint data, and seeded chunk caches",
)


@pytest.fixture(scope="module")
def real():
    import events as E

    inputs = E.load_sample_inputs()
    return inputs, E.timeline_from_inputs(inputs).to_dict()


def verify(real, timeline, video=True):
    import verification as V

    inputs, _ = real
    return V.verify_timeline(timeline, tracking=inputs.tracking, proprio=inputs.proprio,
                             probes=inputs.probes, video_bytes=inputs.video_bytes if video else None)


def idx(tl, event_type, n=0):
    return [i for i, e in enumerate(tl["events"]) if e["event_type"] == event_type][n]


def claim(tl, event_type, ctype, n=0):
    e = tl["events"][idx(tl, event_type)]
    return [c for r in e["evidence"] for c in r["claims"] if c["type"] == ctype][n]


def checks(report, i):
    return {f.check for f in report.findings if f.event_index == i and f.severity == "error"}


def test_real_timeline_verifies_completely(real):
    r = verify(real, real[1])
    assert r.errors == [] and r.claims_failed == 0 and r.claims_unverifiable == 0
    assert set(r.event_verdicts.values()) == {"supported"}
    assert r.claims_checked >= 30


def test_real_inferred_placement_passes_physical_support_checks(real):
    tl = real[1]
    p = tl["events"][idx(tl, "final_placement_candidate")]
    if p["status"] != "inferred":
        pytest.skip("placement not inferred on current data")
    r = verify(real, tl)
    i = idx(tl, "final_placement_candidate")
    assert r.event_verdicts[i] == "supported" and checks(r, i) == set()
    # Same evidence, but claim continuity: must be rejected.
    bad = copy.deepcopy(tl)
    bad["events"][i]["inference"] = "The screwdriver remained in the box throughout."
    assert "status_support" in checks(verify(real, bad), i)


def test_pixel_claims_are_unverifiable_without_video(real):
    r = verify(real, real[1], video=False)
    i = idx(real[1], "approach_candidate")
    assert r.event_verdicts[i] in ("partially_verifiable", "unsupported")
    assert any(f.check == "claim:ring_change" and f.severity == "warning" for f in r.findings)


def test_shifted_frames_and_timestamps_are_flagged(real):
    tl = copy.deepcopy(real[1])
    i = idx(tl, "grasp_candidate")
    tl["events"][i]["t_start"] += 1.0
    j = idx(tl, "gripper_open")
    tl["events"][j]["frame_end"] = 10_000
    r = verify(real, tl)
    assert "timestamp" in checks(r, i) and "frames" in checks(r, j)


def test_wrong_joint_value_is_flagged(real):
    tl = copy.deepcopy(real[1])
    claim(tl, "gripper_close", "joint_value")["value"] += 2.0
    r = verify(real, tl)
    assert "claim:joint_value" in checks(r, idx(tl, "gripper_close"))


def test_nonexistent_track_id_is_flagged(real):
    tl = copy.deepcopy(real[1])
    claim(tl, "coordinated_movement_candidate", "max_displacement_px")["track_id"] = "screwdriver:7"
    r = verify(real, tl)
    i = idx(tl, "coordinated_movement_candidate")
    assert "claim:max_displacement_px" in checks(r, i) and r.event_verdicts[i] == "unsupported"


def test_inflated_geometry_is_flagged(real):
    tl = copy.deepcopy(real[1])
    claim(tl, "coordinated_movement_candidate", "max_displacement_px")["value"] *= 2
    claim(tl, "approach_candidate", "mask_area")["value"] -= 500
    r = verify(real, tl)
    assert "claim:max_displacement_px" in checks(r, idx(tl, "coordinated_movement_candidate"))
    assert "claim:mask_area" in checks(r, idx(tl, "approach_candidate"))


def test_absence_claim_contradicted_by_detections(real):
    tl = copy.deepcopy(real[1])
    ref = tl["events"][idx(tl, "release_candidate")]["evidence"][-1]
    assert ref["kind"] == "absence"
    ref["frame_start"], ref["frame_end"] = 300, 360  # screwdriver *is* detected here
    ref["claims"][0].update(frame_start=300, frame_end=360)
    r = verify(real, tl)
    assert "claim:detection_count" in checks(r, idx(tl, "release_candidate"))


def test_status_upgrades_without_support_are_flagged(real):
    tl = copy.deepcopy(real[1])
    g = idx(tl, "grasp_candidate")
    tl["events"][g]["status"] = "observed"
    p = idx(tl, "final_placement_candidate")
    _keep_one_interior_observation(tl)
    tl["events"][p]["status"] = "inferred"
    tl["events"][p]["inference"] = "placed"
    rel = idx(tl, "release_candidate")
    tl["events"][rel]["inference"] = "released"  # uncertain events must not carry an inference
    r = verify(real, tl)
    assert "status" in checks(r, g)
    assert "status_support" in checks(r, p)
    assert "inference" in checks(r, rel)


def test_grasp_without_coordinated_movement_is_unsupported(real):
    tl = copy.deepcopy(real[1])
    e = tl["events"][idx(tl, "grasp_candidate")]
    e["evidence"] = [r for r in e["evidence"] if not r["source"].startswith("event:")]
    r = verify(real, tl)
    assert "status_support" in checks(r, idx(tl, "grasp_candidate"))


def test_unknown_source_and_dangling_event_ref(real):
    tl = copy.deepcopy(real[1])
    e = tl["events"][idx(tl, "grasp_candidate")]
    e["evidence"][0]["source"] = "lidar:points"
    claim(tl, "grasp_candidate", "event_ref")["frame_start"] = 1
    r = verify(real, tl)
    assert {"provenance", "claim:event_ref"} <= checks(r, idx(tl, "grasp_candidate"))


def _interior_claims(tl):
    p = tl["events"][idx(tl, "final_placement_candidate")]
    return p, [c for r in p["evidence"] for c in r["claims"] if c["type"] == "interior_containment"]


def test_interior_containment_is_recomputed_independently(real):
    tl = copy.deepcopy(real[1])
    p, claims = _interior_claims(tl)
    if not claims:
        pytest.skip("no post-release probe observation")
    claims[0]["interior_fraction"] = 0.2
    claims[0]["footprint_iou"] = 0.5
    r = verify(real, tl)
    msgs = [f.message for f in r.findings if f.check == "claim:interior_containment"]
    assert msgs and "interior fraction" in msgs[0] and "footprint IoU" in msgs[0]


def test_changed_calibration_or_fabricated_observation_is_flagged(real):
    tl = copy.deepcopy(real[1])
    p, claims = _interior_claims(tl)
    if not claims:
        pytest.skip("no post-release probe observation")
    claims[0]["calibration_sha256"] = "0" * 64
    fake = dict(claims[0], frame=700, track_id="screwdriver:probe-f700", calibration_sha256=claims[0]["calibration_sha256"])
    p["evidence"][1]["claims"].append(fake)
    r = verify(real, tl)
    msgs = " | ".join(f.message for f in r.findings if f.check == "claim:interior_containment")
    assert "sha256 mismatch" in msgs and msgs.count("evidence") >= 2


def _keep_one_interior_observation(tl):
    """Reduce placement evidence to a single interior observation (and matching count)."""
    p, claims = _interior_claims(tl)
    for r in p["evidence"]:
        inter = [c for c in r["claims"] if c["type"] == "interior_containment"]
        if inter:
            r["claims"] = [c for c in r["claims"] if c["type"] != "interior_containment"] + inter[:1]


def test_placement_upgrade_needs_physical_support_not_just_valid_numbers(real):
    tl = copy.deepcopy(real[1])
    _keep_one_interior_observation(tl)
    p, claims = _interior_claims(tl)
    p["status"] = "inferred"
    p["inference"] = "The screwdriver stayed in the box."
    r = verify(real, tl)
    i = idx(tl, "final_placement_candidate")
    msgs = [f.message for f in r.findings if f.event_index == i and f.check == "status_support"]
    assert any(">= 2 verified" in m for m in msgs)
    assert any("continuity" in m for m in msgs)
    assert r.event_verdicts[i] == "unsupported"


def test_raw_mask_overlap_cannot_support_placement(real):
    tl = copy.deepcopy(real[1])
    p = tl["events"][idx(tl, "final_placement_candidate")]
    p["evidence"] = [r for r in p["evidence"] if not any(c["type"] == "interior_containment" for c in r["claims"])]
    p["evidence"].append({"source": "sam:screwdriver+sam:white box", "kind": "comparison", "frame_start": 660,
                          "frame_end": 721, "summary": "raw overlap", "claims": [
                              {"type": "containment", "concept": "screwdriver", "target": "white box",
                               "frames": [660, 720], "value": 0.95}]})
    p["status"], p["inference"] = "inferred", "placed"
    r = verify(real, tl)
    i = idx(tl, "final_placement_candidate")
    assert "status_support" in checks(r, i) and r.event_verdicts[i] == "unsupported"


def test_failure_from_missing_detections_is_flagged(real):
    tl = copy.deepcopy(real[1])
    release = tl["events"][idx(tl, "release_candidate")]
    fake = copy.deepcopy(release)
    fake["evidence"] = [copy.deepcopy(r) for r in release["evidence"] if r["kind"] == "absence"]
    assert fake["evidence"]
    fake.update(event_type="dropped_object", status="inferred", inference="object dropped")
    tl["events"].append(fake)
    r = verify(real, tl)
    assert {"absence", "event_type"} <= checks(r, len(tl["events"]) - 1)
