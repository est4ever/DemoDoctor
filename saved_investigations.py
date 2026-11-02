"""Read-only adapters: saved investigation artifacts -> task_criteria.InvestigationEvidence.

Inputs are frozen inference outputs only (run reports, failure reports, verifier outputs, evidence
packages and saved Muse responses). Reference outcomes / human labels are never read here; they live in
diagnostic_eval.py. Nothing is written.

Covered investigations (the six in DIAGNOSTIC_COVERAGE_AUDIT.md):
- ep003, ep005, ep006, ep013: held-out, inference_freeze_v2 (heldout_four_v2 + heldout_four_muse_comparison)
- ep010: development episode, botfails_ep010_w1260_v2 (+ Muse pilot and matched Muse-only baseline)
- pilot: recorded SO-101 screwdriver/tray offline reconstruction (submission_demo/pilot/audit/after);
  its only Muse output is historical and bound to the separate 'before' package.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import task_criteria as TC

ROOT = Path(__file__).parent
EXP = ROOT / "data" / "experiments"
CRITERIA_DIR = ROOT / "data" / "tasks" / "criteria"

HELDOUT = ("ep003", "ep005", "ep006", "ep013")
INVESTIGATIONS = ("ep003", "ep005", "ep006", "ep010", "ep013", "pilot")


@dataclass
class ModelOutput:
    """One saved Muse response plus the package it was allowed to cite."""
    kind: str  # evidence_grounded | muse_only
    outcome: str
    raw: dict[str, Any]
    package_evidence_ids: frozenset[str] = frozenset()
    package_frame_refs: frozenset[str] = frozenset()
    historical: bool = False  # bound to a different (earlier) package than the current evidence
    source: str = ""


@dataclass
class SavedInvestigation:
    investigation_id: str
    example_id: str
    split: str
    task: TC.TaskCriteria
    evidence: TC.InvestigationEvidence
    pipeline_verdict: str
    models: list[ModelOutput] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_task_criteria(name: str) -> TC.TaskCriteria:
    return TC.TaskCriteria.from_dict(_read(CRITERIA_DIR / f"{name}.json"))


def _ids(catalog: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    return [e for e in catalog if str(e.get("source") or "").startswith(prefix)]


# --- held-out (inference_freeze_v2) ---------------------------------------------------

def _load_heldout(key: str) -> SavedInvestigation:
    example = f"botfails_dish_test_{key}"
    run_p = EXP / "heldout_four_v2" / example / "run_report.json"
    base = EXP / "heldout_four_muse_comparison" / key
    pkg_p = base / "evidence_grounded" / "package_snapshot.json"
    run, pkg = _read(run_p), _read(pkg_p)
    catalog = pkg["evidence_catalog"]
    end_items = _ids(catalog, "sam:green plate (end keyframe)")
    grip_items = _ids(catalog, "proprio:")
    track_items = [e for e in _ids(catalog, "sam:green plate (window") if e.get("frame_start") is not None]
    end_eids = tuple(e["evidence_id"] for e in end_items)
    end = run["end_state"]
    windows = run["window_reports"]
    calib = windows[0]["failure_report"]["inputs"]["gripper_calibration"]
    inputs = windows[0]["failure_report"]["inputs"]
    rack_ok = bool(end.get("approx_ok")) and all(w.get("rack_available") for w in run["sam"]["windows"])
    events: list[TC.EventRecord] = []
    for w in windows:
        verdicts = w["verification"]["report"].get("event_verdicts") or {}
        for i, e in enumerate(w["failure_report"]["physical_events"]):
            events.append(TC.EventRecord(e["kind"], e["subtype"], e["status"], e["track_id"], e["frame_start"],
                                         e["frame_end"], (), verdicts.get(str(i)), tuple(e.get("uncertainties") or ())))
    ev = TC.InvestigationEvidence(
        investigation_id=key, task_id="botfails_dish", n_frames=int(inputs["n_frames"]), fps=float(inputs["fps"]),
        evidence_ids=frozenset(e["evidence_id"] for e in catalog),
        final_observations=[TC.ObjectObservation(p["object_id"], "green plate", p["region"], int(end["frame"]),
                                                 end_eids, note=p.get("geometry_rule") or "") for p in end["plates"]],
        destination="available" if rack_ok else "unavailable",
        destination_evidence_ids=end_eids,
        tracking_windows=[(int(w["frames"][0]), int(w["frames"][1])) for w in windows],
        tracking_evidence_ids=tuple(e["evidence_id"] for e in track_items),
        gripper="measured" if inputs.get("joint_data") else "unavailable",
        gripper_open_frames=tuple(int(e["frame_start"]) for e in grip_items),
        holding_detectable=bool(calib.get("holding_detectable")),
        gripper_evidence_ids=tuple(e["evidence_id"] for e in grip_items),
        events=events,
    )
    # Bind the saved geometric assessments to their exact original source/package.
    # No model prose, prediction verdict or reference outcome is used here.
    ev.package_id = _rel(pkg_p)
    predicates = []
    for index, p in enumerate(end["plates"]):
        frame = int(end["frame"])
        scoped = [e for e in end_items if e.get("frame_start") == frame
                  and e.get("frame_end") == frame + 1 and e.get("kind") == "detection"]
        for item in scoped:
            source = f"{_rel(run_p)}#/end_state/plates/{index}"
            predicates.append(TC.SourcePredicate(item["evidence_id"], "detection", p["object_id"],
                frame, "green plate", source_ref=source, package_id=ev.package_id))
            geom = p.get("assessment") or {}
            # Recheck the numerical geometry, not the end_state_verdict or summary.
            inside = (p.get("region") == "inside" and p.get("reliable") is True and geom.get("reliable") is True
                      and geom.get("geometry_rule") == "reliable_interior_inside"
                      and _fraction(geom.get("interior_fraction"), minimum=.95))
            outside = (p.get("region") == "outside" and p.get("reliable") is True and geom.get("reliable") is True
                       and geom.get("geometry_rule") == "footprint_outside_clearly_separated"
                       and _fraction(geom.get("footprint_fraction"), maximum=.05)
                       and _fraction(geom.get("near_container_fraction"), maximum=.5))
            if rack_ok and (inside or outside):
                predicates.append(TC.SourcePredicate(item["evidence_id"], "containment_2d", p["object_id"],
                    frame, p["region"], source_ref=source, package_id=ev.package_id,
                    measurement={k: geom[k] for k in ("interior_fraction", "footprint_fraction", "near_container_fraction", "geometry_rule") if k in geom}))
    ev.predicates = tuple(predicates)
    grounded_p = base / "evidence_grounded" / "validated_explanation.json"
    only_p = base / "muse_only" / "structured_prediction.json"
    grounded, only = _read(grounded_p), _read(only_p)
    frame_refs = frozenset(f["frame_ref"] for f in pkg.get("frame_refs") or pkg.get("frame_catalog") or [])
    models = [
        ModelOutput("evidence_grounded", grounded["task_outcome"], grounded["raw"], ev.evidence_ids, frame_refs,
                    source=_rel(grounded_p)),
        ModelOutput("muse_only", only["verdict"], only, source=_rel(only_p)),
    ]
    return SavedInvestigation(key, example, "held-out", load_task_criteria("botfails_dish"), ev,
                              run["prediction"]["verdict"], models,
                              [_rel(run_p), _rel(pkg_p), _rel(grounded_p), _rel(only_p)])


def _fraction(value: Any, *, minimum: float = 0, maximum: float = 1) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and minimum <= value <= maximum


# --- ep010 (development) ----------------------------------------------------------------

def _ep010_catalog(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Same numbering the recorded replay and Muse pilot package use: event evidence, then uncertainties."""
    items: list[dict[str, Any]] = []
    for ev in report.get("physical_events") or []:
        for block in ev.get("evidence") or []:
            items.append({**block, "evidence_id": f"E{len(items)}"})
    for note in report.get("uncertainties") or []:
        items.append({"evidence_id": f"E{len(items)}", "source": "pipeline:report", "summary": note, "claims": []})
    return items


def _load_ep010() -> SavedInvestigation:
    base = EXP / "botfails_ep010_w1260_v2"
    fr_p, ver_p = base / "failure_report.json", base / "verification.json"
    report, ver = _read(fr_p), _read(ver_p)
    catalog = _ep010_catalog(report)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in catalog:
        for c in item.get("claims") or []:
            by_type.setdefault(c["type"], []).append({**c, "evidence_id": item["evidence_id"]})
    inputs = report["inputs"]
    window = tuple(inputs["sources"]["window"])
    rest = {c["track_id"]: c for c in by_type.get("rest_region", [])}
    final_obs = []
    for o in report["object_outcomes"]:
        r = rest.get(o["track_id"])
        last = int(o["frames"][-1])
        if r and last in r["frames"]:
            final_obs.append(TC.ObjectObservation(o["track_id"], o["concept"], r["region"], last, (r["evidence_id"],)))
        else:
            final_obs.append(TC.ObjectObservation(o["track_id"], o["concept"], "unknown", last, ()))
    events = []
    verdicts = ver.get("event_verdicts") or {}
    for i, e in enumerate(report["physical_events"]):
        eids = tuple(item["evidence_id"] for item in catalog
                     if any(item.get("summary") == b.get("summary") for b in e["evidence"]))
        events.append(TC.EventRecord(e["kind"], e["subtype"], e["status"], e["track_id"], e["frame_start"],
                                     e["frame_end"], eids, verdicts.get(str(i)), tuple(e.get("uncertainties") or ())))
    grip = by_type.get("gripper_open", [])
    ev = TC.InvestigationEvidence(
        investigation_id="ep010", task_id="botfails_dish", n_frames=int(inputs["n_frames"]), fps=float(inputs["fps"]),
        evidence_ids=frozenset(i["evidence_id"] for i in catalog),
        final_observations=final_obs,
        destination="available" if inputs["sources"].get("container", {}).get("n_observations") else "unavailable",
        destination_evidence_ids=tuple(c["evidence_id"] for c in by_type.get("rest_region", [])),
        tracking_windows=[(int(window[0]), int(window[1]))],
        tracking_evidence_ids=tuple(c["evidence_id"] for c in by_type.get("displacement", [])),
        gripper="measured" if inputs.get("joint_data") else "unavailable",
        gripper_open_frames=tuple(int(c["frame"]) for c in grip),
        holding_detectable=bool(inputs["gripper_calibration"].get("holding_detectable")),
        gripper_evidence_ids=tuple(c["evidence_id"] for c in grip),
        events=events,
    )
    ev.package_id = _rel(fr_p)
    ev.predicates = tuple(TC.SourcePredicate(eid, "event_inference", e.track_id, e.frame_start,
        e.subtype or e.kind, source_ref=f"{_rel(fr_p)}#/physical_events/{i}", package_id=ev.package_id)
        for i, e in enumerate(events) if e.verifier_verdict == "supported" and e.status == "inferred"
        for eid in e.evidence_ids if any(c.get("type") in ("gripper_open", "rest_region", "displacement")
            for item in catalog if item["evidence_id"] == eid for c in item.get("claims") or []))
    pilot_p = EXP / "botfails_ep010_w1260_v2_muse_pilot" / "pilot_report.json"
    grounded_p = EXP / "botfails_ep010_w1260_v2_muse_pilot" / "validated_explanation.json"
    only_p = EXP / "botfails_ep010_muse_only_matched_frames" / "structured_prediction.json"
    pkg = _read(pilot_p)["package"]
    grounded, only = _read(grounded_p), _read(only_p)
    models = [
        ModelOutput("evidence_grounded", grounded["task_outcome"], grounded["raw"], frozenset(pkg["evidence_ids"]),
                    frozenset(f["frame_ref"] for f in pkg["frame_refs"]), source=_rel(grounded_p)),
        ModelOutput("muse_only", only["verdict"], only, source=_rel(only_p)),
    ]
    return SavedInvestigation("ep010", "botfails_dish_test_ep010", "development", load_task_criteria("botfails_dish"),
                              ev, report["verdict"], models,
                              [_rel(fr_p), _rel(ver_p), _rel(pilot_p), _rel(grounded_p), _rel(only_p)])


# --- recorded pilot (screwdriver -> white tray) -----------------------------------------

def _load_pilot() -> SavedInvestigation:
    base = ROOT / "data" / "submission_demo" / "pilot" / "audit"
    an_p, pkg_p, ver_p = base / "after" / "analysis.json", base / "after" / "evidence_package.json", base / "after" / "verification.json"
    analysis, pkg, ver = _read(an_p), _read(pkg_p), _read(ver_p)
    catalog = analysis["evidence_catalog"]
    prov = pkg["provenance"]
    cov = prov["observation_coverage"]
    coverage = [e for e in catalog if any(c.get("type") == "observation_coverage" for c in e.get("claims") or [])]
    detections = [e for e in catalog if e["source"] == "sam:video"]
    no_joint = [e for e in catalog if e["source"] == "pipeline:report" and "joint" in e["summary"].lower()]
    no_target = [e for e in catalog if e["source"] == "pipeline:report" and "segmentation" in e["summary"].lower()]
    last = int(cov["frame_end"]) - 1
    final_obs = [TC.ObjectObservation(e["track_id"], "screwdriver", "unknown", int(e["frame_end"]) - 1,
                                      (e["evidence_id"],)) for e in detections if int(e["frame_end"]) - 1 == last]
    verdicts = ver.get("event_verdicts") or {}
    events = [TC.EventRecord(e["kind"], e["subtype"], e["status"], e["track_id"], e["frame_start"], e["frame_end"],
                             tuple(e.get("evidence_ids") or ()), verdicts.get(str(e.get("event_index", i))),
                             tuple(e.get("uncertainties") or ()))
              for i, e in enumerate(analysis["physical_events"])]
    ev = TC.InvestigationEvidence(
        investigation_id="pilot", task_id="live_custom", n_frames=int(prov["inputs"]["n_frames"]),
        fps=float(prov["inputs"]["fps"]), evidence_ids=frozenset(e["evidence_id"] for e in catalog),
        final_observations=final_obs,
        destination="available" if prov["target_segmentation"].get("status") == "available" else "unavailable",
        destination_evidence_ids=tuple(e["evidence_id"] for e in no_target),
        tracking_windows=[(int(cov["frame_start"]), int(cov["frame_end"]))],
        tracking_missing_ranges=[(int(r["frame_start"]), int(r["frame_end"])) for r in cov["missing_ranges"]],
        tracking_evidence_ids=tuple(e["evidence_id"] for e in coverage),
        gripper="measured" if prov["inputs"].get("joint_data") else "unavailable",
        gripper_evidence_ids=tuple(e["evidence_id"] for e in no_joint),
        events=events,
    )
    hist_p, hist_pkg_p = base / "before" / "muse_result.json", base / "before" / "evidence_package.json"
    hist, hist_pkg = _read(hist_p), _read(hist_pkg_p)
    outcome = hist.get("task_outcome") or ("uncertain" if "Task outcome: uncertain" in hist.get("explanation", "") else "unknown")
    models = [ModelOutput("evidence_grounded", outcome, hist,
                          frozenset(e["evidence_id"] for e in hist_pkg["evidence_catalog"]),
                          frozenset(f["frame_ref"] for f in hist_pkg.get("frame_catalog") or []),
                          historical=True, source=_rel(hist_p))]
    return SavedInvestigation("pilot", analysis["episode_key"], "recorded", load_task_criteria("pilot_screwdriver_tray"),
                              ev, analysis["pipeline_verdict"], models,
                              [_rel(an_p), _rel(pkg_p), _rel(ver_p), _rel(hist_p), _rel(hist_pkg_p)])


def load(key: str) -> SavedInvestigation:
    if key in HELDOUT:
        return _load_heldout(key)
    if key == "ep010":
        return _load_ep010()
    if key == "pilot":
        return _load_pilot()
    raise KeyError(key)


def load_all() -> list[SavedInvestigation]:
    return [load(k) for k in INVESTIGATIONS]
