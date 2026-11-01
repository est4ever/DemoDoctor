"""Tests for evidence packages and Muse evidence-reference validation (no paid APIs)."""

from __future__ import annotations

import json
from pathlib import Path

import evidence_fusion as EF

ROOT = Path(__file__).resolve().parents[1]
TASK = "store dishes in a dish rack (BotFails domotic_dishTidyUp)"


def _load(name: str) -> EF.EvidencePackage:
    return EF.load_experiment_package(ROOT / "data/experiments" / name, task_description=TASK)


def test_ep010_v2_package_has_inferred_release_evidence():
    pkg = _load("botfails_ep010_w1260_v2")
    assert pkg.deterministic_verdict in ("uncertain", "failure", "success")
    assert pkg.physical_events, "ep010 v2 should have a physical event"
    assert any(e["subtype"] == "released_outside_target" for e in pkg.physical_events)
    assert any(e.status_context == "inferred" for e in pkg.evidence_items)
    assert any("gripper" in e.source for e in pkg.evidence_items)
    ids = pkg.evidence_id_set()
    assert ids and all(i.startswith("E") for i in ids)
    # No labels / anomaly in muse text
    text = json.dumps(pkg.to_muse_text_dict())
    assert "event_labels" not in text
    assert "anomaly" not in text.lower() or "anomaly" not in text  # provenance must not cite anomaly CSVs
    assert "ground-truth" not in text.lower()
    assert "labels.json" not in text


def test_ep001_and_ep011_empty_events_do_not_fabricate():
    for name in ("botfails_ep001_w1203_heldout", "botfails_ep011_w1518_heldout"):
        path = ROOT / "data/experiments" / name
        if not (path / "failure_report.json").is_file():
            continue
        pkg = _load(name)
        assert pkg.physical_events == []
        dry = EF.dry_run_muse_payload(pkg)
        assert dry["n_physical_events"] == 0
        assert dry["paid_call"] is False
        # Muse inventing a drop must fail validation
        fake = {
            "explanation": "The robot dropped a plate.",
            "earliest_failure_interval": {"t_start": 50.0, "t_end": 51.0, "evidence_ids": ["E999"]},
            "task_outcome": "failure",
            "outcome_evidence_ids": ["E999"],
            "factual_claims": [{"text": "plate dropped", "evidence_ids": ["E999"]}],
            "hypotheses": [],
            "visual_interpretations": [],
            "limitations": [],
        }
        v = EF.validate_muse_explanation(fake, pkg)
        assert v.ok is False
        assert any("unknown evidence_id" in e or "unsupported failure" in e for e in v.validation_errors)


def test_valid_explanation_with_real_evidence_ids_passes():
    pkg = _load("botfails_ep010_w1260_v2")
    eid = pkg.evidence_items[0].evidence_id
    good = {
        "explanation": "A plate moved and rested outside the rack with a measured gripper opening.",
        "earliest_failure_interval": {
            "t_start": pkg.earliest_failure["t_start"],
            "t_end": pkg.earliest_failure["t_end"],
            "evidence_ids": [eid],
        },
        "task_outcome": "uncertain",
        "outcome_evidence_ids": [eid],
        "factual_claims": [{"text": pkg.evidence_items[0].summary, "evidence_ids": [eid]}],
        "hypotheses": [{"text": "Opening may have been intentional", "related_evidence_ids": [eid]}],
        "visual_interpretations": [{
            "text": "Plate looks green in the frame",
            "frame_ref": pkg.frame_refs[0].frame_ref if pkg.frame_refs else None,
            "not_verified_by_pipeline": True,
        }] if pkg.frame_refs else [],
        "limitations": ["Windowed analysis; final state may be incomplete."],
    }
    v = EF.validate_muse_explanation(good, pkg)
    assert v.ok, v.validation_errors
    assert v.task_outcome == "uncertain"


def test_contradiction_success_without_inside_is_rejected():
    pkg = _load("botfails_ep001_w1203_heldout")
    bad = {
        "explanation": "All dishes are stored successfully.",
        "earliest_failure_interval": None,
        "task_outcome": "success",
        "outcome_evidence_ids": [pkg.evidence_items[0].evidence_id] if pkg.evidence_items else [],
        "factual_claims": (
            [{"text": "success", "evidence_ids": [pkg.evidence_items[0].evidence_id]}]
            if pkg.evidence_items else [{"text": "success", "evidence_ids": ["E0"]}]
        ),
        "hypotheses": [],
        "visual_interpretations": [],
        "limitations": [],
    }
    v = EF.validate_muse_explanation(bad, pkg)
    assert v.ok is False
    assert any("success" in e for e in v.validation_errors)


def test_dry_run_ep010_lists_frames_without_api(tmp_path):
    pkg = _load("botfails_ep010_w1260_v2")
    dry = EF.dry_run_muse_payload(pkg)
    assert dry["n_frames"] >= 1
    assert dry["n_evidence_items"] >= 1
    assert "user_text_preview" in dry
    # analyze_with_evidence dry_run path
    from ai_analysis import analyze_with_evidence

    result = analyze_with_evidence(pkg, frames=[], dry_run=True)
    assert result["dry_run"] is True and result["paid_call"] is False
    assert result["validated"] is None
