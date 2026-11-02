"""Synthetic rules for task_criteria: four states, missing evidence never becomes failure."""
import pytest

import task_criteria as TC

TASK = TC.TaskCriteria.from_dict({
    "task_id": "t", "target": "rack", "objects": [{"concept": "plate", "count": 2}],
    "criteria": [
        {"criterion_id": "containment", "kind": "containment"},
        {"criterion_id": "inventory", "kind": "inventory"},
        {"criterion_id": "grasp_release", "kind": "grasp_release", "required": False},
        {"criterion_id": "completion", "kind": "completion", "params": {"complete_scope": "physical"}},
    ]})


def _ev(regions=("inside", "inside"), frame=99, **kw):
    obs = [TC.ObjectObservation(f"plate:{i}", "plate", r, frame, ("E1",)) for i, r in enumerate(regions)]
    base = dict(investigation_id="x", task_id="t", n_frames=100, fps=30.0, evidence_ids=frozenset({"E1", "E2"}),
                final_observations=obs, destination="available", destination_evidence_ids=("E1",),
                tracking_windows=[(0, 100)], package_id="synthetic-measurements")
    predicates = [TC.SourcePredicate("E1", kind, o.object_id, o.frame, value, o.view,
        "synthetic-measurements#/objects", "synthetic-measurements") for o in obs
        for kind, value in (("containment_2d", o.region), ("detection", o.concept))]
    for o in kw.get("orientation_observations", []):
        predicates += [TC.SourcePredicate(o.evidence_ids[0], kind, o.object_id, o.frame, value, o.view,
            "synthetic-measurements#/pose", "synthetic-measurements") for kind, value in
            (("orientation", str(o.satisfies)), ("orientation_pose", "upright"))]
    for e in kw.get("events", []):
        predicates += [TC.SourcePredicate(e.evidence_ids[0], kind, e.track_id, e.frame_start, e.subtype,
            source_ref="synthetic-measurements#/sensor-event", package_id="synthetic-measurements")
            for kind in ("event_inference", "physical_release")]
    base["predicates"] = tuple(predicates)
    base.update(kw)
    return TC.InvestigationEvidence(**base)


def _state(report, cid):
    return report.by_id(cid).state


def test_all_inside_and_count_met_is_supported():
    r = TC.assess(TASK, _ev())
    assert _state(r, "containment") == "supported" and _state(r, "inventory") == "supported"
    assert r.completion == "unverified" and r.abstention_explanation  # 2D containment is not full physical completion
    assert _state(r, "orientation") == "not_assessed"  # undeclared criterion


def test_outside_contradicts_and_yields_end_state_mechanism():
    r = TC.assess(TASK, _ev(("inside", "outside")))
    assert _state(r, "containment") == "contradicted" and r.completion == "unverified"
    (m,) = r.mechanisms
    assert m.mechanism == "object_left_outside_target" and m.status == "end_state" and m.objects == ["plate:1"]
    assert {q.kind for q in m.resolving_evidence} == {"continuous_tracking"}


def test_unknown_region_is_unverified_not_failure_and_requests_viewpoint():
    r = TC.assess(TASK, _ev(("inside", "unknown")))
    c = r.by_id("containment")
    assert c.state == "unverified" and r.completion == "unverified"
    assert [q.kind for q in c.requirements] == ["additional_viewpoint"] and c.requirements[0].objects == ("plate:1",)
    assert "containment" in r.abstention_explanation and "additional_viewpoint" in r.abstention_explanation


def test_missing_destination_requests_mask():
    r = TC.assess(TASK, _ev(destination="unavailable", destination_evidence_ids=("E2",)))
    c = r.by_id("containment")
    assert c.state == "unverified" and [q.kind for q in c.requirements] == ["destination_mask"]


def test_non_final_outside_observation_is_not_failure():
    r = TC.assess(TASK, _ev(("outside", "unknown"), frame=40))
    c = r.by_id("containment")
    assert c.state == "unverified" and "recovery remains possible" in c.basis
    assert {q.kind for q in c.requirements} == {"final_state_observation", "continuous_tracking"}
    assert r.completion == "unverified"


def test_no_observations_at_all_is_unverified():
    r = TC.assess(TASK, _ev(regions=()))
    assert _state(r, "containment") == "unverified" and _state(r, "inventory") == "unverified"
    assert r.completion == "unverified"


def test_undeclared_count_requests_task_specification():
    task = TC.TaskCriteria(TASK.task_id, "", "rack", (TC.ObjectRequirement("plate", None),), TASK.criteria)
    inv = TC.assess(task, _ev()).by_id("inventory")
    assert inv.state == "unverified" and [q.kind for q in inv.requirements] == ["task_specification"]


def test_fewer_objects_than_required_is_unverified_with_viewpoint_and_tracking():
    inv = TC.assess(TASK, _ev(("inside",))).by_id("inventory")
    assert inv.state == "unverified"
    assert {q.kind for q in inv.requirements} == {"additional_viewpoint", "continuous_tracking"}


def test_gripper_without_holding_signal_stays_unverified():
    ev = _ev(gripper="measured", gripper_open_frames=(50,), holding_detectable=False, gripper_evidence_ids=("E2",))
    g = TC.assess(TASK, ev).by_id("grasp_release")
    assert g.state == "unverified" and {q.kind for q in g.requirements} == {"gripper_measurement", "continuous_tracking"}
    assert g.requirements[0].frames == (50, 51)


def test_no_gripper_requests_measurement_and_gap_tracking():
    g = TC.assess(TASK, _ev(tracking_missing_ranges=[(30, 60)])).by_id("grasp_release")
    assert g.state == "unverified"
    assert [(q.kind, q.frames) for q in g.requirements] == [("gripper_measurement", None), ("continuous_tracking", (30, 60))]


def test_inferred_outside_release_is_mechanism_not_contradiction():
    event = TC.EventRecord("dropped_in_transport", "released_outside_target", "inferred", "plate:0", 10, 20,
                           ("E2",), "supported")
    ev = _ev(gripper="measured", gripper_open_frames=(15,), holding_detectable=False, gripper_evidence_ids=("E2",),
             events=[event])
    r = TC.assess(TASK, ev)
    assert r.by_id("grasp_release").state == "unverified"
    (m,) = r.mechanisms
    assert (m.category, m.status, m.verifier) == ("placement_outside_target", "inferred", "supported")


def test_observed_release_with_holding_signal_contradicts():
    event = TC.EventRecord("dropped_in_transport", "released_outside_target", "observed", "plate:0", 10, 20,
                           ("E2",), "supported")
    ev = _ev(gripper="measured", holding_detectable=True, gripper_evidence_ids=("E2",), events=[event])
    assert TC.assess(TASK, ev).by_id("grasp_release").state == "contradicted"


def test_decisive_state_with_unknown_citation_is_demoted():
    ev = _ev(evidence_ids=frozenset({"E2"}))  # observations cite E1, which is not in the catalog
    r = TC.assess(TASK, ev)
    c = r.by_id("containment")
    assert c.state == "unverified" and set(c.objects.values()) == {"unknown"}
    assert r.completion == "unverified"


@pytest.mark.parametrize("views,expected", [
    (("inside", "inside"), "inside"), (("inside", "outside"), "unknown"), (("unknown", "outside"), "outside")])
def test_multi_view_combination_is_conservative(views, expected):
    obs = [TC.ObjectObservation("plate:0", "plate", r, 99, (f"E{i}",), view=f"cam{i}") for i, r in enumerate(views)]
    region, eids, cams = TC.combine_views(obs, aligned=True, associated=frozenset({"plate:0"}))["plate:0"]
    assert region == expected and cams == ["cam0", "cam1"] and len(eids) == 2


def test_orientation_declared_but_unmeasured_is_unverified_with_requirements():
    task = TC.TaskCriteria("t", "", "rack", TASK.objects, TASK.criteria + (
        TC.CriterionSpec("orientation", "orientation", True, "upright", params={"required_pose": "upright"}),))
    r = TC.assess(task, _ev())
    o = r.by_id("orientation")
    assert o.state == "unverified" and {q.kind for q in o.requirements} == {"orientation_measurement", "additional_viewpoint"}
    assert r.completion == "unverified" and r.by_id("completion").blocking == ["orientation"]


def test_orientation_measurement_interface():
    task = TC.TaskCriteria("t", "", "rack", TASK.objects, TASK.criteria + (
        TC.CriterionSpec("orientation", "orientation", True, "upright", params={"required_pose": "upright"}),))
    good = [TC.OrientationObservation(f"plate:{i}", True, 99, ("E1",)) for i in range(2)]
    assert TC.assess(task, _ev(orientation_observations=good)).by_id("orientation").state == "supported"
    assert TC.assess(task, _ev(orientation_observations=good)).completion == "unverified"
    bad = [good[0], TC.OrientationObservation("plate:1", False, 99, ("E2",))]
    r = TC.assess(task, _ev(orientation_observations=bad))
    assert r.by_id("orientation").state == "contradicted" and r.by_id("orientation").evidence_ids == ["E2"]
    assert any(m.category == "incorrect_orientation" for m in r.mechanisms)
