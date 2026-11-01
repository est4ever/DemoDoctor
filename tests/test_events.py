"""Event-candidate tests.

Synthetic arrays below are hand-built test inputs for the rules only; they are
not tracking data and never reach the app. The last test runs on the real
sample (cache + joint data) when present.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import events as E

N = 300
FPS = 30.0


def gripper_profile(*segments):
    """segments: (length, value) plateaus joined by 6-frame linear ramps."""
    out = []
    for i, (length, value) in enumerate(segments):
        if i:
            out += list(np.linspace(out[-1], value, 7)[1:])
        out += [value] * length
    return np.array(out[:N] + [out[-1]] * max(0, N - len(out)))


# Measured: closed 1, open 20 at ~40, closes to 6 (stall) at ~120, opens at ~200, closes empty ~260.
G = gripper_profile((40, 1.0), (75, 20.0), (75, 6.0), (55, 22.0), (40, 1.0))
CMD = gripper_profile((40, 1.0), (75, 20.0), (75, 0.5), (55, 22.0), (40, 0.5))


def arm(moving_ranges):
    a = np.zeros((N, 5))
    pos = 0.0
    for f in range(N):
        if any(s <= f < e for s, e in moving_ranges):
            pos += 1.0
        a[f, 0] = pos
    return a


ARM = arm([(50, 110), (130, 190), (215, 250)])


CAL_REF = {"file": "test_calibration.json", "sha256": "test", "calibration_frame": 0}


def interior(fraction, reliable=True):
    return {"interior_fraction": fraction, "reliable": reliable, "footprint_iou": 0.99 if reliable else 0.6,
            "polygon_in_footprint": 1.0, "raw_mask_fraction": 0.0, "footprint_fraction": 1.0,
            "reason": None if reliable else "container footprint differs from calibration"}


def obj_signal(detected, x, bottom=None, area=None, containment=None, ring=None):
    """containment: per-frame interior fraction array (NaN = no assessment)."""
    states = ["detected" if d else "not_detected" for d in detected]
    x = np.where(detected, x, np.nan)
    bottom = np.where(detected, 600.0 if bottom is None else bottom, np.nan)
    area = np.where(detected, 9000.0 if area is None else area, np.nan)
    ids = ["tool:0" if d else None for d in detected]
    detail = None
    if containment is not None:
        detail = {f: interior(float(containment[f])) for f in range(N) if detected[f] and np.isfinite(containment[f])}
    return E.ObjectSignal("tool", states, x.astype(float), bottom.astype(float), area.astype(float), ids,
                          detail, ring, CAL_REF if containment is not None else None)


RING = np.where(np.arange(N) >= 70, 0.5, 0.0)  # neighborhood changes from frame 70


def pick_place_object(*, end_detected=True, end_contained=0.95, end_moving=False, ring=RING):
    f = np.arange(N)
    det = np.ones(N, dtype=bool)
    x = np.full(N, 500.0)
    x[130:190] = np.linspace(500, 200, 60)  # carried with the arm
    x[190:] = 200.0
    if end_moving:
        x[260:] = np.linspace(200, 260, N - 260)
    bottom = np.full(N, 600.0)
    area = np.where((f >= 90) & (f < 120), 6000.0, 9000.0)  # partly hidden before closing
    if not end_detected:
        det[200:] = False
    cont = np.full(N, end_contained)
    return obj_signal(det, x, bottom, area, cont, ring)


def timeline(obj, g=G, cmd=CMD, arm_state=ARM):
    return E.build_timeline(gripper=g, gripper_cmd=cmd, arm_state=arm_state, obj=obj, fps=FPS, target_concept="box")


def by_type(tl, kind):
    return [e for e in tl.events if e.event_type == kind]


# --- gripper ----------------------------------------------------------------

def test_gripper_transitions_detected_with_stall_flag():
    trs = E.gripper_transitions(G, CMD, E.EventParams())
    assert [(t.kind, t.stalled) for t in trs] == [("open", False), ("close", True), ("open", False), ("close", False)]
    assert all(t.start <= t.crossing <= t.end for t in trs)


def test_command_without_measured_motion_is_not_a_closure():
    measured_open = gripper_profile((40, 1.0), (260, 20.0))
    cmd_closes = gripper_profile((40, 1.0), (75, 20.0), (185, 0.5))
    tl = timeline(pick_place_object(), g=measured_open, cmd=cmd_closes)
    assert by_type(tl, "gripper_close") == []
    assert by_type(tl, "grasp_candidate") == []


def test_closure_reaching_command_is_not_a_grasp():
    g = gripper_profile((40, 1.0), (75, 20.0), (185, 0.6))
    cmd = gripper_profile((40, 1.0), (75, 20.0), (185, 0.5))
    tl = timeline(pick_place_object(), g=g, cmd=cmd)
    assert [e.status for e in by_type(tl, "gripper_close")] == ["observed"]
    assert by_type(tl, "grasp_candidate") == []


# --- full sequence ------------------------------------------------------------

def test_clean_pick_place_yields_inferred_candidates_never_observed_grasp():
    tl = timeline(pick_place_object())
    status = {e.event_type: e.status for e in tl.events}
    assert status["approach_candidate"] == "inferred"
    assert status["grasp_candidate"] == "inferred"
    assert status["coordinated_movement_candidate"] == "inferred"
    assert status["final_placement_candidate"] == "inferred"
    assert status["release_candidate"] == "inferred"  # object stays still while the arm moves away
    assert {e.status for e in by_type(tl, "gripper_open") + by_type(tl, "gripper_close")} == {"observed"}
    assert "observed" not in {e.status for e in tl.events if e.event_type.endswith("_candidate")}


def test_every_event_has_evidence_and_consistent_times():
    tl = timeline(pick_place_object())
    for e in tl.events:
        assert e.evidence and e.status in ("observed", "inferred", "uncertain")
        assert e.frame_start <= e.frame_end
        assert e.t_start == round(e.frame_start / FPS, 3) and e.t_end == round(e.frame_end / FPS, 3)
        assert all(r.source and r.kind and r.summary and r.claims for r in e.evidence)


def test_observations_inference_and_uncertainty_are_separated():
    tl = timeline(pick_place_object())
    for e in tl.events:
        assert {r.kind for r in e.evidence} <= {"measurement", "detection", "absence", "comparison"}
        if e.status == "observed":
            assert e.inference is None  # a measurement needs no inference
        if e.status == "inferred":
            assert e.inference and e.uncertainties
        if e.status == "uncertain":
            assert e.inference is None and e.uncertainties


# --- approach / grasp / empty-gripper wording -------------------------------

def test_approach_without_spatial_evidence_is_uncertain():
    tl = timeline(pick_place_object(ring=np.zeros(N)))  # nothing changes near the object
    assert by_type(tl, "approach_candidate")[0].status == "uncertain"
    tl = timeline(pick_place_object(ring=None))  # no pixel measurement at all
    assert by_type(tl, "approach_candidate")[0].status == "uncertain"


def test_full_closure_never_claims_empty_gripper():
    tl = timeline(pick_place_object())
    last_close = by_type(tl, "gripper_close")[-1]
    text = " ".join(last_close.uncertainties).lower()
    assert "does not prove the gripper is empty" in text
    assert last_close.inference is None


def test_coordinated_movement_is_described_as_coincidence():
    cm = by_type(timeline(pick_place_object()), "coordinated_movement_candidate")[0]
    assert any("coincidence" in u and "not measured" in u for u in cm.uncertainties)


# --- missing detections ------------------------------------------------------

def test_missing_detections_are_uncertain_not_failures():
    tl = timeline(pick_place_object(end_detected=False))
    assert by_type(tl, "release_candidate")[0].status == "uncertain"
    placement = by_type(tl, "final_placement_candidate")[0]
    assert placement.status == "uncertain" and placement.evidence[0].kind == "absence"
    assert not any("fail" in e.event_type or "drop" in e.event_type for e in tl.events)
    assert any(g["state"] == "not_detected" for g in tl.tracking_gaps)


def test_object_never_detected_gives_no_grasp_inference():
    obj = obj_signal(np.zeros(N, dtype=bool), np.zeros(N))
    tl = timeline(obj)
    assert by_type(tl, "grasp_candidate")[0].status == "uncertain"
    assert by_type(tl, "coordinated_movement_candidate") == []


def test_object_moving_without_arm_motion_is_not_coordinated():
    still_arm = arm([(50, 110)])
    tl = timeline(pick_place_object(), arm_state=still_arm)
    assert by_type(tl, "coordinated_movement_candidate")[0].status == "uncertain"
    assert by_type(tl, "grasp_candidate")[0].status == "uncertain"


# --- placement -----------------------------------------------------------------

def keyframes(frames, fractions, reliable=True):
    """Object undetected after release except at isolated keyframes (separate probe tracks)."""
    obj = pick_place_object(end_detected=False)
    for f, frac in zip(frames, fractions):
        obj.states[f] = "detected"
        obj.x_center[f], obj.bottom[f], obj.area[f], obj.track_ids[f] = 200.0, 600.0, 9000.0, f"tool:probe-f{f}"
        obj.containment_detail[f] = interior(frac, reliable)
    return by_type(timeline(obj), "final_placement_candidate")[0]


def test_two_separated_inside_observations_give_inferred_placement_without_stability_claim():
    p = keyframes([250, 280], [1.0, 0.97])
    assert p.status == "inferred"
    assert "observed" not in p.status and "stayed" not in p.inference and "remained" not in p.inference
    assert any("discrete observations" in u and "not observed" in u for u in p.uncertainties)
    assert any("separate tracks" in u for u in p.uncertainties)
    claims = [c for r in p.evidence for c in r.claims if c["type"] == "interior_containment"]
    assert [c["frame"] for c in claims] == [250, 280]


def test_single_keyframe_is_not_enough_for_placement():
    p = keyframes([280], [1.0])
    assert p.status == "uncertain" and any("needs >= 2" in u for u in p.uncertainties)


def test_observations_too_close_together_are_not_enough():
    assert keyframes([270, 280], [1.0, 1.0]).status == "uncertain"


def test_outside_or_partial_interior_is_not_placement():
    assert keyframes([250, 280], [1.0, 0.3]).status == "uncertain"
    assert by_type(timeline(pick_place_object(end_contained=0.3)), "final_placement_candidate")[0].status == "uncertain"


def test_unreliable_interior_estimate_is_uncertain():
    p = keyframes([250, 280], [1.0, 1.0], reliable=False)
    assert p.status == "uncertain" and any("could not be estimated reliably" in u for u in p.uncertainties)


def test_no_calibration_means_no_placement_assessment():
    obj = pick_place_object()
    obj.calibration_ref = None
    p = by_type(timeline(obj), "final_placement_candidate")[0]
    assert p.status == "uncertain" and any("No container interior estimate" in u for u in p.uncertainties)


# --- real sample -----------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    not ((ROOT / "sample_videos" / "sample.mp4").is_file()
         and (ROOT / "data" / "lerobot" / "ankithreddy__so101_pickplace_uno" / "SOURCE.json").is_file()
         and list((ROOT / "data" / "tracking" / "chunks").glob("*/f000360-000481/screwdriver__box_seed_*.json"))),
    reason="needs sample video, joint data, and seeded chunk caches",
)
def test_sample_timeline_matches_video_review():
    tl = E.timeline_for_sample()
    got = [(e.event_type, e.status) for e in tl.events]
    assert got == [
        ("gripper_open", "observed"),
        ("approach_candidate", "inferred"),
        ("gripper_close", "observed"),
        ("grasp_candidate", "inferred"),
        ("coordinated_movement_candidate", "inferred"),
        ("gripper_open", "observed"),
        ("release_candidate", "uncertain"),
        # Window starts at release end (frame 520). Inferred only with both approved probes.
        ("final_placement_candidate",
         "inferred" if [p["frame_index"] for p in tl.sources["probes"]] == [660, 720] else "uncertain"),
        ("gripper_close", "observed"),
    ]
    approach = by_type(tl, "approach_candidate")[0]
    # Ring around the resting screwdriver is unchanged until ~frame 168 (checked on decoded frames).
    assert 168 <= approach.frame_start <= 200
    grasp = by_type(tl, "grasp_candidate")[0]
    # Reviewed in video: fingers close around the handle at ~10.5-10.8 s.
    assert 10.3 <= grasp.t_start <= grasp.t_end <= 11.0
    move = by_type(tl, "coordinated_movement_candidate")[0]
    assert move.frame_end == 433  # last screwdriver detection is frame 432
    gaps = [(g["state"], g["frame_start"], g["frame_end"]) for g in tl.tracking_gaps]
    probe_frames = [p["frame_index"] for p in tl.sources["probes"]]
    if probe_frames == [660, 720]:  # approved keyframe probes at 22.0 s and 24.0 s (separate tracks)
        assert gaps == [("not_detected", 433, 481), ("unknown", 481, 660), ("unknown", 661, 720), ("unknown", 721, 737)]
        placement = by_type(tl, "final_placement_candidate")[0]
        assert placement.status == "inferred"
        interior = [c for r in placement.evidence for c in r.claims if c["type"] == "interior_containment"]
        assert [(c["frame"], c["track_id"], c["reliable"]) for c in interior] == [
            (660, "screwdriver:probe-f660", True), (720, "screwdriver:probe-f720", True)]
        assert all(c["interior_fraction"] >= 0.99 and c["raw_mask_fraction"] < 0.01 for c in interior)
        assert any("whether the object stayed in place between or after them is not observed" in u
                   for u in placement.uncertainties)
    elif probe_frames == [660]:  # approved keyframe probe at 22.0 s (separate track)
        assert gaps == [("not_detected", 433, 481), ("unknown", 481, 660), ("unknown", 661, 737)]
        placement = by_type(tl, "final_placement_candidate")[0]
        assert placement.status == "uncertain"
        assert placement.evidence[0].claims[0]["track_ids"] == ["screwdriver:probe-f660"]
    else:
        assert gaps == [("not_detected", 433, 481), ("unknown", 481, 737)]
