"""Diagnostic evaluation over the six saved investigations: separation, citations, regression."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

import diagnostic_eval as D
import saved_investigations as S
import task_criteria as TC

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def result():
    return D.run()


def _pred(result, key):
    return next(p for p in result["predictions"] if p["investigation_id"] == key)


def _crit(pred, cid):
    return next(a for a in pred["criteria"]["assessments"] if a["criterion_id"] == cid)


def _code_tokens(path):
    """Imported module names and non-docstring string literals (prose may mention references)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(n) is not None}
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            out.append(n.module or "")
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
            out.append(n.value)
    return out


def test_inference_modules_never_read_references():
    for name in ("task_criteria.py", "saved_investigations.py", "criteria_presentation.py"):
        tokens = _code_tokens(ROOT / name)
        for forbidden in ("VERIFIED_OUTCOMES", "event_labels", "reference_mechanisms", "labels",
                          "diagnostic_eval", "evaluation", "EVALUATION_SCORE", "tasks.jsonl"):
            assert not any(forbidden in t for t in tokens), (name, forbidden)


def test_loaders_do_not_modify_saved_artifacts():
    invs = S.load_all()
    paths = sorted({ROOT / p for inv in invs for p in inv.sources})
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    D.run()
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_expected_criterion_states(result):
    states = {p["investigation_id"]: {a["criterion_id"]: a["state"] for a in p["criteria"]["assessments"]}
              for p in result["predictions"]}
    assert states["ep013"]["containment"] == "contradicted" and states["ep013"]["completion"] == "unverified"
    assert states["ep003"]["containment"] == "supported" and states["ep003"]["completion"] == "unverified"
    assert states["ep005"]["containment"] == "unverified" and states["ep005"]["orientation"] == "unverified"
    assert states["ep010"]["containment"] == "unverified"  # outside rest at frame 1380 is not the final state
    assert states["pilot"]["containment"] == "unverified" and states["pilot"]["orientation"] == "not_assessed"
    assert all(s != "contradicted" for k in ("ep003", "ep005", "ep006", "pilot") for s in states[k].values())


def test_missing_evidence_is_explained(result):
    for p in result["predictions"]:
        for a in p["criteria"]["assessments"]:
            if a["state"] == "unverified" and a["kind"] != "completion":
                assert a["requirements"], (p["investigation_id"], a["criterion_id"])
        if p["outcomes"]["criteria_completion"] == "uncertain":
            assert p["criteria"]["abstention_explanation"] and p["criteria"]["evidence_requirements"]
    kinds = lambda key, cid: {r["kind"] for r in _crit(_pred(result, key), cid)["requirements"]}
    assert kinds("pilot", "containment") == {"destination_mask"}
    assert kinds("ep010", "containment") == {"final_state_observation", "continuous_tracking"}
    assert kinds("ep005", "orientation") == {"orientation_measurement", "task_specification"}
    assert "gripper_measurement" in kinds("pilot", "grasp_release")


def test_mechanisms_come_from_pipeline_evidence(result):
    ep010 = _pred(result, "ep010")["mechanisms"]["pipeline"]
    assert [(m["mechanism"], m["status"], m["verifier"]) for m in ep010] == [("released_outside_target", "inferred", "supported")]
    ep013 = _pred(result, "ep013")["mechanisms"]["pipeline"]
    assert [(m["mechanism"], m["status"], m["objects"]) for m in ep013] == [("object_outside_target_at_sample", "unverified", ["green plate:2"])]
    for key in ("ep003", "ep005", "ep006", "pilot"):
        assert _pred(result, key)["mechanisms"]["pipeline"] == []


def test_citations_valid(result):
    s = result["scores"]["citation_summary"]
    assert s["model_invalid"] == 0 and s["model_citations"] > 0
    assert s["criteria_invalid"] == 0 and s["criteria_decisive_without_citation"] == 0


def test_citation_check_flags_unknown_ids():
    m = S.ModelOutput("evidence_grounded", "uncertain",
                      {"factual_claims": [{"text": "x", "evidence_ids": ["E9"]}],
                       "visual_interpretations": [{"frame_ref": "F7", "not_verified_by_pipeline": True}]},
                      frozenset({"E0"}), frozenset({"F0"}))
    c = D.citation_check(m)
    assert c["invalid"] == 2 and c["invalid_ids"] == ["E9", "F7"]
    a = D.claim_audit(m)
    assert [u["reason"] for u in a["unsupported"]] == ["cites unknown evidence"]


@pytest.mark.parametrize("text,flag", [
    ("plate is upright in the rack", True), ("2D containment does not verify upright orientation", False),
    ("Robot successfully stored dishes", True), ("gripper opening measured at frame 10", False)])
def test_unhedged_physical(text, flag):
    assert D.unhedged_physical(text) is flag


def test_scores(result):
    sc = result["scores"]
    ms = sc["mechanism_summary"]
    assert (ms["reference_mechanisms"], ms["identified"], ms["localized_unverified"], ms["missed"]) == (3, 0, 0, 3)
    assert ms["false_mechanisms_on_reference_success"] == []
    assert sc["outcome_summary"]["criteria_completion"].get("wrong", 0) == 0
    assert sc["outcome_summary"]["muse_only"]["wrong"] == 1  # ep005 false success
    assert sc["claims_summary"]["evidence_grounded_unsupported"] == 0
    rows = {r["investigation_id"]: r for r in sc["outcome_rows"]}
    assert rows["ep006"]["classes"]["pipeline"] == "disputed" and rows["pilot"]["classes"]["pipeline"] == "no_reference"


@pytest.mark.skipif(not (ROOT / "data/experiments/expanded_eval_prep/VERIFIED_OUTCOMES.json").is_file(), reason="optional original reference audit is not bundled with public replay")
def test_reference_outcomes_match_existing_labels():
    refs = D.load_references()
    verified = {e["example_id"]: e["verified_outcome"] for e in json.loads(
        (ROOT / "data/experiments/expanded_eval_prep/VERIFIED_OUTCOMES.json").read_text(encoding="utf-8"))["episodes"]}
    events = {e["example_id"]: e["final_outcome"] for e in json.loads(
        (ROOT / "data/event_labels.json").read_text(encoding="utf-8"))["episodes"]}
    for key in ("ep003", "ep005", "ep006", "ep013"):
        assert refs[key]["reference_outcome"] == verified[f"botfails_dish_test_{key}"]
    assert refs["ep010"]["reference_outcome"] == events["botfails_dish_test_ep010"]
    assert refs["pilot"]["reference_outcome"] is None and refs["ep006"]["status"] == "disputed"


def test_committed_report_is_current():
    assert D.main(["--check"]) == 0


def test_criteria_report_round_trips_to_json():
    inv = S.load("ep013")
    json.dumps(TC.assess(inv.task, inv.evidence).to_dict())
