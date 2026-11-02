"""Adversarial regression cases found in independent review of 3d09778."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import pytest
import task_criteria as T
import saved_investigations as S
import criteria_presentation as P
import diagnostic_eval as D


def evidence(obs=(), **kw):
    return T.InvestigationEvidence("new", "task", 100, 30, frozenset({"E0"}),
        final_observations=list(obs), destination="available", **kw)


TASK = T.TaskCriteria.from_dict({"task_id": "task", "target": "tray", "objects": [{"concept": "object"}],
    "criteria": [{"criterion_id": "containment", "kind": "containment"},
                 {"criterion_id": "orientation", "kind": "orientation", "params": {"required_pose": "upright"}}]})


def test_existing_id_does_not_establish_orientation_or_containment():
    ev = evidence([T.ObjectObservation("object:0", "object", "inside", 99, ("E0",))],
        orientation_observations=[T.OrientationObservation("object:0", True, 99, ("E0",))])
    report = T.assess(TASK, ev)
    assert report.by_id("containment").state == report.by_id("orientation").state == "unverified"


@pytest.mark.parametrize("frame", [-1, 40, 98, 100, 1000])
def test_each_object_requires_its_own_valid_final_frame(frame):
    obs = [T.ObjectObservation("object:0", "object", "outside", frame, ("E0",)),
           T.ObjectObservation("object:1", "object", "inside", 99, ("E0",))]
    predicates = tuple(T.SourcePredicate("E0", "containment_2d", o.object_id, o.frame, o.region,
                       source_ref="real#/geometry", package_id="pkg") for o in obs)
    assert T.assess(TASK, evidence(obs, predicates=predicates, package_id="pkg")).by_id("containment").state == "unverified"


@pytest.mark.parametrize("aligned,associated", [(False, frozenset()), (True, frozenset()), (False, frozenset({"object:0"}))])
def test_time_alignment_and_object_association_both_required(aligned, associated):
    obs = [T.ObjectObservation("object:0", "object", "inside", 99, ("E0",), view=v) for v in ("cam1", "cam2")]
    assert T.combine_views(obs, aligned=aligned, associated=associated)["object:0"][0] == "unknown"


def test_valid_association_does_not_override_conflict():
    obs = [T.ObjectObservation("object:0", "object", r, 99, ("E0",), view=v)
           for r, v in (("inside", "cam1"), ("outside", "cam2"))]
    assert T.combine_views(obs, aligned=True, associated=frozenset({"object:0"}))["object:0"][0] == "unknown"


@pytest.mark.parametrize("field,value", [("view", "cam2"), ("package_id", "earlier-package"),
    ("frame", 98), ("object_id", "different"), ("kind", "detection"), ("source_ref", "")])
def test_predicate_must_match_source_scope(field, value):
    obs = T.ObjectObservation("object:0", "object", "inside", 99, ("E0",))
    p = T.SourcePredicate("E0", "containment_2d", obs.object_id, 99, "inside", source_ref="real#/geometry", package_id="pkg")
    ev = evidence([obs], predicates=(replace(p, **{field: value}),), package_id="pkg")
    assert T.assess(TASK, ev).by_id("containment").state == "unverified"


def test_failed_verifier_and_unknown_citation_never_observed_mechanism():
    e = T.EventRecord("failed_grasp", "", "observed", "object:0", 10, 20, ("E999",), "failed")
    (m,) = T.assess(TASK, evidence(events=[e])).mechanisms
    assert m.status == "unverified" and m.verifier == "failed"


def test_task_inputs_do_not_assume_count_or_pose():
    assert S.load("pilot").task.objects[0].count is None
    for ep in ("ep003", "ep005", "ep006", "ep010", "ep013"):
        inv = S.load(ep)
        assert inv.task.objects[0].count is None
        assert not next(s for s in inv.task.criteria if s.kind == "orientation").params.get("required_pose")
        assert not next(s for s in inv.task.criteria if s.kind == "orientation").required


def test_ep003_geometry_supported_but_completion_not_certified():
    inv = S.load("ep003")
    r = T.assess(inv.task, inv.evidence)
    c = r.by_id("containment")
    assert c.state == "supported" and c.evidence_ids == ["E4"]
    assert "sampled keyframe 2075" in c.basis and "later frames unobserved" in c.basis
    assert r.completion == "unverified" and r.by_id("orientation").state == "unverified"
    # A saved verdict cannot manufacture a measured predicate.
    inv.evidence.predicates = ()
    assert T.assess(inv.task, inv.evidence).by_id("containment").state == "unverified"


@pytest.mark.parametrize("count", [1, 2, 3])
@pytest.mark.parametrize("dry", [False, True])
def test_new_video_and_camera_count_no_physical_conclusions(count, dry):
    a = {"episode_key": "job", "task": "Move an object", "evidence_catalog": [
        {"evidence_id": f"E{i}", "camera_id": f"cam{i+1}", "kind": "detection", "source": "sam:video"} for i in range(count)]}
    if count > 1:
        a["multicamera"] = {"cameras": [{"camera_id": f"cam{i+1}"} for i in range(count)]}
    c = P.for_analysis(a, n_frames=100, fps=30, object_concept="object", destination="tray", dry_run=dry)
    assert c["completion"] == ("not_assessed" if dry else "unverified")
    assert not c["mechanisms"] and not any(x["state"] in ("supported", "contradicted") for x in c["assessments"])
    if not dry:
        location = next(a for a in c["assessments"] if a["kind"] == "containment")
        assert location['state'] == 'not_assessed' and not location['required']
        assert next(a for a in c['assessments'] if a['kind'] == 'action')['state'] == 'not_assessed'
    if count > 1:
        assert "No cross-camera" in c["notes"][-1]


def test_cited_prose_is_not_independently_certified_by_evaluator():
    m = S.ModelOutput("evidence_grounded", "uncertain", {"factual_claims": [
        {"text": "The robot released it correctly. It was not occluded.", "evidence_ids": ["E0"]}]}, frozenset({"E0"}))
    audit = D.claim_audit(m)
    assert len(audit["entailment_unverified"]) == 1


def test_reference_changes_cannot_change_predictions(monkeypatch):
    original = D.run()["predictions"]
    monkeypatch.setattr(D, "load_references", lambda: {})
    assert D.run()["predictions"] == original


def test_source_record_pointers_resolve_to_actual_geometry():
    root = Path(__file__).resolve().parents[1]
    for key in S.HELDOUT:
        for p in S.load(key).evidence.predicates:
            artifact, pointer = p.source_ref.split("#")
            record = json.loads((root / artifact).read_text(encoding="utf-8"))
            for part in pointer.strip("/").split("/"):
                record = record[int(part)] if isinstance(record, list) else record[part]
            assert record["object_id"] == p.object_id
            if p.kind == "containment_2d":
                assert record["region"] == p.value
                assert p.measurement["geometry_rule"] == record["assessment"]["geometry_rule"]


def test_every_unresolved_saved_criterion_has_its_own_resolving_observations():
    for inv in S.load_all():
        report = T.assess(inv.task, inv.evidence)
        for a in report.assessments:
            if a.state == "unverified":
                assert a.requirements, (inv.investigation_id, a.kind)
        completion = report.by_id("completion")
        assert any("operator-approved complete task checklist" in r.reason for r in completion.requirements)
        assert all(r.criterion_id == "completion" for r in completion.requirements)


def test_completion_requirements_reuse_sources_without_mutating_child_criteria():
    a = T.CriterionAssessment("inventory", "inventory", True, "unverified", "count unknown",
        requirements=[T.EvidenceRequirement("task_specification", "inventory", "Declare object count")])
    report = T.assess_completion(T.CriterionSpec("completion", "completion", True, "Complete task"), [a])
    assert report.requirements[0].reason == a.requirements[0].reason
    assert a.requirements[0].criterion_id == "inventory"
    assert report.state == "unverified" and report.evidence_ids == []


def test_generated_presentations_are_current_and_original_artifacts_untouched():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("export_criteria", root / "scripts/export-criteria.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for key, text in module.exports().items():
        assert (root / f"web/public/criteria/{key}.json").read_text(encoding="utf-8") == text
        assert json.loads(text)["investigation_id"] == key
