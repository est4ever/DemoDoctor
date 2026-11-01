"""verify_failure_report tests on synthetic inputs (no datasets).

Observations carry real box-local masks (all-ones RLE) so region checks recompute
from pixels, exactly as on real data.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np

import container as C
import failures as F
import verification as V
from tracking import ObjectTrackObservation, mask_in_frame

FPS, N, SHAPE = 30.0, 300, (240, 320)
CONTAINER = np.zeros(SHAPE, bool)
CONTAINER[20:120, 200:310] = True  # the "rack" on the right
TASK = F.TaskSpec("t", "t", (F.ObjectSpec("plate"),), "rack")
CAL = F.GripperCalibration("test", "test: closed reading identical with/without object", holding_detectable=False)


def obs(frame, cx, cy, s=20, tid="plate:0"):
    x1, y1 = int(cx - s // 2), int(cy - s // 2)
    return ObjectTrackObservation(frame / FPS, tid, "plate", frame, (x1, y1, x1 + s, y1 + s), None,
                                  mask_rle={"size": [s, s], "counts": [0, s * s]})


def scenario(last_frame=299):
    """Plate rests at (60,180), is carried to (150,180) (outside the rack), rests there."""
    o = [obs(f, 60, 180) for f in range(0, 61)]
    o += [obs(f, x, 180) for f, x in zip(range(61, 91), np.linspace(63, 150, 30))]
    o += [obs(f, 150, 180) for f in range(91, last_frame + 1)]
    return o


def to_tracks(observations):
    by = {}
    for o in observations:
        om = mask_in_frame(o.mask_rle, o.bbox, SHAPE)
        region = F.classify_region(C.assess_containment(om, CONTAINER, None, None))
        x1, y1, x2, y2 = o.bbox
        by.setdefault(o.object_id, []).append(F.TrackObs(o.frame_index, (x1 + x2) / 2, (y1 + y2) / 2,
                                                         float(np.hypot(x2 - x1, y2 - y1)), region))
    return [F.ObjectTrack(k, "plate", v) for k, v in by.items()]


def gripper():
    g = np.full(N, 1.0)
    g[40:60] = 30.0  # approach opening (before the move)
    g[85:140] = 30.0  # opening during the move
    return g


def make(last_frame=299):
    o = scenario(last_frame)
    g = gripper()
    r = F.localize_failures(TASK, to_tracks(o), fps=FPS, n_frames=N, gripper=F.GripperSignal(g, g.copy(), CAL))
    return o, g, r.to_dict()


def verify(o, g, rep):
    return V.verify_failure_report(rep, observations=o, container_mask=CONTAINER, gripper_measured=g,
                                   fps=FPS, n_frames=N, frame_shape=SHAPE)


def errors(v, check=None):
    return [f for f in v.findings if f.severity == "error" and (check is None or f.check == check)]


def test_honest_report_verifies():
    o, g, rep = make()
    assert rep["physical_events"][0]["subtype"] == "released_outside_target"
    v = verify(o, g, rep)
    assert errors(v) == [] and set(v.event_verdicts.values()) == {"supported"} and v.claims_failed == 0


def test_tampered_displacement_and_region_are_flagged():
    o, g, rep = make()
    bad = copy.deepcopy(rep)
    ev = bad["physical_events"][0]["evidence"]
    ev[0]["claims"][0]["value_px"] *= 3
    v = verify(o, g, bad)
    assert {f.check for f in errors(v)} >= {"claim:displacement"}
    # Claim the rest frames are outside while the plate actually sits in the rack outline:
    moved = [obs(f, 250, 60) if f >= 91 else x for f, x in zip(range(len(o)), o)]
    assert errors(verify(moved, g, rep), "claim:rest_region")


def test_opening_without_measured_crossing_is_flagged():
    o, g, rep = make()
    bad = copy.deepcopy(rep)
    for ev in bad["physical_events"][0]["evidence"]:
        for c in ev["claims"]:
            if c["type"] == "gripper_open":
                c["frame"] = 200
    v = verify(o, g, bad)
    assert errors(v, "claim:gripper_open") and errors(v, "status_support")


def test_slip_cannot_be_inferred_when_holding_is_undetectable():
    o, g, rep = make()
    bad = copy.deepcopy(rep)
    bad["physical_events"][0]["subtype"] = "no_measured_release"
    assert errors(verify(o, g, bad), "status_support")


def test_partial_clip_final_outcome_and_verdict_flips_are_flagged():
    o, g, rep = make(last_frame=150)  # observations stop half-way through the episode
    assert rep["verdict"] == "uncertain" and rep["object_outcomes"][0]["final_region"] == "unknown"
    assert errors(verify(o, g, rep)) == []
    bad = copy.deepcopy(rep)
    bad["verdict"] = "failure"
    bad["object_outcomes"][0]["final_region"] = "outside"
    checks = {f.check for f in errors(verify(o, g, bad))}
    assert {"final_outcome"} <= checks


def test_earliest_failure_must_match_inferred_events():
    o, g, rep = make()
    bad = copy.deepcopy(rep)
    bad["earliest_failure"]["frame_start"] = 10
    assert errors(verify(o, g, bad), "earliest_failure")


def test_pipeline_never_reads_annotations_or_anomaly_flags():
    import ast

    root = Path(__file__).resolve().parents[1]
    for name in ("failure_inputs.py", "failures.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {
            n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not {"event_labels", "annotation_ui", "evaluation"} & imported, name
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and not (n.value.startswith('"""') or "\n" in n.value)]
        assert not any("event_labels.json" in s or "_labels.csv" in s or "labels.json" in s for s in strings), name
