"""Deterministic unit tests for failures.py. No datasets, no network.

Tracks and gripper signals here are hand-built test inputs for the rules only.
"""

from __future__ import annotations

import numpy as np
import pytest

import failures as F

FPS = 30.0
N = 300
TASK = F.TaskSpec("t", "put the item in the box", (F.ObjectSpec("item", 1),), "box")
CAL_HOLD = F.GripperCalibration("test", "test: holding visible", holding_detectable=True)
CAL_NOHOLD = F.GripperCalibration("test", "test: closed reading identical with/without object", holding_detectable=False)


def segment(frames, start, end, region, size=100.0):
    """Linear motion from start to end (x, y) over the given frames."""
    frames = list(frames)
    xs = np.linspace(start[0], end[0], len(frames))
    ys = np.linspace(start[1], end[1], len(frames))
    return [F.TrackObs(f, float(x), float(y), size, region) for f, x, y in zip(frames, xs, ys)]


def track(*segments, track_id="item:0"):
    return F.ObjectTrack(track_id, "item", [o for s in segments for o in s])


def gripper(open_ranges, cal=CAL_HOLD):
    g = np.full(N, 1.0)
    for a, b in open_ranges:
        g[a:b] = 30.0
    return F.GripperSignal(g, g.copy(), cal)


def run(tracks, scale=1.0, **kw):
    return F.localize_failures(TASK, tracks, fps=FPS, n_frames=N, **kw)


def pick_place(end_region, *, scale=1.0):
    s = scale
    return track(
        segment(range(0, 61), (100 * s, 100 * s), (100 * s, 100 * s), "outside", 100 * s),
        segment(range(61, 101), (110 * s, 100 * s), (500 * s, 100 * s), "unknown", 100 * s),
        segment(range(101, 300), (500 * s, 100 * s), (500 * s, 100 * s), end_region, 100 * s),
    )


# --- verdicts ------------------------------------------------------------------

def test_clean_placement_is_success_with_no_failure_events():
    r = run([pick_place("inside")], gripper=gripper([(40, 60), (95, 140)]))
    assert r.verdict == "success" and r.failure_type is None and r.physical_events == []
    assert r.object_outcomes[0].final_region == "inside" and r.object_outcomes[0].status == "inferred"


def test_drop_with_measured_opening_is_localized():
    r = run([pick_place("outside")], gripper=gripper([(40, 60), (95, 140)]))
    assert r.verdict == "failure" and r.failure_type == "dropped_in_transport"
    e = r.physical_events[0]
    assert (e.kind, e.subtype, e.status) == ("dropped_in_transport", "released_outside_target", "inferred")
    # Last rest frame before the move (60) to the first frame at rest afterwards (100), exclusive end.
    assert r.earliest_failure["frame_start"] == 60 and r.earliest_failure["frame_end"] == 101
    assert any(ev.kind == "measurement" and "opened" in ev.summary for ev in e.evidence)


def test_video_only_drop_is_uncertain_but_final_outcome_still_failure():
    r = run([pick_place("outside")])
    e = r.physical_events[0]
    assert e.status == "uncertain" and e.subtype == "cause_undetermined" and e.inference is None
    assert r.verdict == "failure" and r.failure_type == "incorrect_final_placement"
    assert r.earliest_failure is None  # no *supported* physical failure event
    assert any("video-only" in u.lower() for u in r.uncertainties)


def test_no_release_and_holding_not_detectable_is_uncertain():
    # The only opening (frames 40-60) is before the move begins: it is the approach, not a release.
    r = run([pick_place("outside")], gripper=gripper([(40, 60)], CAL_NOHOLD))
    e = r.physical_events[0]
    assert e.subtype == "no_measured_release" and e.status == "uncertain"


def test_no_release_with_detectable_holding_is_inferred_slip():
    r = run([pick_place("outside")], gripper=gripper([(40, 60)], CAL_HOLD))
    e = r.physical_events[0]
    assert e.subtype == "no_measured_release" and e.status == "inferred" and "slipping" in e.inference


# --- recovery ------------------------------------------------------------------

def drop_then_retry(final_region):
    return track(
        segment(range(0, 41), (100, 100), (100, 100), "outside"),
        segment(range(41, 71), (110, 100), (300, 100), "unknown"),
        segment(range(71, 151), (300, 100), (300, 100), "outside"),
        segment(range(151, 181), (310, 100), (600, 100), "unknown"),
        segment(range(181, 300), (600, 100), (600, 100), final_region),
    )


def test_successful_recovery_after_drop():
    r = run([drop_then_retry("inside")], gripper=gripper([(20, 40), (65, 120), (175, 220)]))
    assert r.physical_events[0].kind == "dropped_in_transport"
    assert [(x.outcome, x.after_event) for x in r.recoveries] == [("succeeded", 0)]
    assert r.verdict == "success"  # task completed after recovery; the drop is still reported
    assert r.earliest_failure is not None


def test_failed_recovery_keeps_failure_verdict():
    r = run([drop_then_retry("outside")], gripper=gripper([(20, 40), (65, 120), (175, 220)]))
    assert [x.outcome for x in r.recoveries] == ["failed"]
    assert r.verdict == "failure" and r.failure_type == "dropped_in_transport"


# --- insufficient evidence -------------------------------------------------------

def test_disappearing_object_is_never_a_failure():
    t = track(segment(range(0, 61), (100, 100), (100, 100), "outside"),
              segment(range(61, 90), (110, 100), (400, 100), "unknown"))  # then no detections
    r = run([t], gripper=gripper([(40, 60), (85, 140)]))
    assert r.physical_events == [] and r.verdict == "uncertain"
    assert r.object_outcomes[0].final_region == "unknown"


def test_partial_clip_never_gives_a_final_outcome():
    # Observations stop at frame 150 of a 300-frame episode: the drop is localized,
    # but the object's final position (and the task verdict) stay unknown.
    t = track(segment(range(0, 61), (100, 100), (100, 100), "outside"),
              segment(range(61, 101), (110, 100), (500, 100), "unknown"),
              segment(range(101, 151), (500, 100), (500, 100), "outside"))
    r = run([t], gripper=gripper([(40, 60), (95, 140)]))
    assert r.physical_events[0].status == "inferred" and r.earliest_failure is not None
    assert r.object_outcomes[0].final_region == "unknown" and r.verdict == "uncertain"
    assert "final position is not established" in r.object_outcomes[0].uncertainties[0]


def test_single_final_observation_is_not_an_outcome():
    t = track(segment(range(0, 61), (100, 100), (100, 100), "outside"),
              segment(range(61, 100), (110, 100), (500, 100), "unknown"),
              segment(range(100, 112), (500, 100), (500, 100), "inside"))  # 12 frames < 0.5 s span
    r = run([t])
    assert r.object_outcomes[0].status == "uncertain" and r.verdict == "uncertain"


def test_expected_count_not_met_is_uncertain():
    task = F.TaskSpec("t", "two items", (F.ObjectSpec("item", 2),), "box")
    r = F.localize_failures(task, [pick_place("inside")], fps=FPS, n_frames=N)
    assert r.verdict == "uncertain" and any("1/2" in u for u in r.uncertainties)


def test_motion_across_an_observation_gap_is_not_interpreted():
    t = track(segment(range(0, 100), (100, 100), (100, 100), "outside"),
              segment(range(200, 300), (600, 100), (600, 100), "outside"))  # 100-frame gap
    r = run([t], gripper=gripper([(120, 150)]))
    assert r.physical_events == []


# --- failed grasp ----------------------------------------------------------------

def test_failed_grasp_needs_joint_data_and_proximity():
    still = track(segment(range(0, 300), (100, 100), (100, 100), "outside"))
    g = gripper([(0, 50), (80, 300)])  # closes at 50, reopens at 80
    r = run([still], gripper=g, proximity={"item:0": {45, 50, 55}})
    assert [(e.kind, e.status) for e in r.physical_events] == [("failed_grasp", "inferred")]
    assert run([still], gripper=g).physical_events == []  # no proximity evidence
    assert run([still], proximity={"item:0": {50}}).physical_events == []  # no joint data


def test_failed_grasp_then_successful_pickup_is_a_recovery():
    t = track(segment(range(0, 151), (100, 100), (100, 100), "outside"),
              segment(range(151, 181), (110, 100), (600, 100), "unknown"),
              segment(range(181, 300), (600, 100), (600, 100), "inside"))
    g = gripper([(0, 50), (80, 140), (175, 220)])
    r = run([t], gripper=g, proximity={"item:0": {50}})
    assert r.physical_events[0].kind == "failed_grasp"
    assert [(x.outcome, x.after_event) for x in r.recoveries] == [("succeeded", 0)]
    assert r.verdict == "success"


# --- generality ------------------------------------------------------------------

def test_rules_are_scale_invariant():
    g = gripper([(40, 60), (95, 140)])
    small = run([pick_place("outside", scale=1.0)], gripper=g)
    large = run([pick_place("outside", scale=4.0)], gripper=g)
    key = lambda r: [(e.kind, e.subtype, e.status, e.frame_start, e.frame_end) for e in r.physical_events]  # noqa: E731
    assert key(small) == key(large) and small.verdict == large.verdict


@pytest.mark.parametrize("assessment,expected", [
    (None, "unknown"),
    ({"reliable": True, "interior_fraction": 0.95, "footprint_fraction": 1.0}, "inside"),
    ({"reliable": False, "interior_fraction": 0.95, "footprint_fraction": 1.0}, "unknown"),
    ({"reliable": False, "interior_fraction": None, "footprint_fraction": 0.0}, "outside"),
    ({"reliable": True, "interior_fraction": 0.4, "footprint_fraction": 0.6}, "unknown"),
])
def test_classify_region(assessment, expected):
    assert F.classify_region(assessment) == expected


def test_report_serializes():
    r = run([pick_place("outside")], gripper=gripper([(40, 60), (95, 140)]))
    d = r.to_dict()
    assert d["verdict"] == "failure" and d["inputs"]["joint_data"] is True
