"""Additive, provenance-bound criterion presentation; no outcome labels or model interpretation.

This module never imports the diagnostic evaluator. New video inputs do not yet
provide final geometry, inventory or orientation measurements, so it abstains.
"""
from __future__ import annotations

from dataclasses import asdict
import task_criteria as TC


def bundle(task: TC.TaskCriteria, evidence: TC.InvestigationEvidence) -> dict:
    report = TC.assess(task, evidence).to_dict()
    names = {"containment": "Object location / containment", "orientation": "Object orientation",
             "inventory": "Required objects accounted for", "grasp_release": "Grasp or release",
             "completion": "Physical task-completion conditions"}
    for a in report["assessments"]:
        spec = next((s for s in task.criteria if s.criterion_id == a['criterion_id']), None)
        a["name"] = spec.description if a['kind'] == 'action' and spec else names.get(a["kind"], a["kind"].replace("_", " ").capitalize())
        if a['kind'] == 'action' and spec:
            a['instruction_basis'] = spec.basis
            a['action'] = spec.params.get('action')
        kinds = {"containment": {"containment_2d"}, "inventory": {"detection"},
                 "orientation": {"orientation", "orientation_pose"},
                 "grasp_release": {"physical_release", "event_inference"}, "action": {"articulation_2d"}}
        a["sources"] = [asdict(p) for p in evidence.predicates
                        if p.evidence_id in a["evidence_ids"] and p.kind in kinds.get(a["kind"], set())]
    return {"schema": "demodoctor.criteria/v2", **report,
            "scope": "Independent criterion assessment; recorded verdicts and model citations are unchanged.",
            "notes": list(evidence.notes)}


def for_analysis(analysis: dict, *, n_frames: int, fps: float, object_concept: str,
                 destination: str, dry_run: bool = False) -> dict:
    """Video-only live adapter. Detection/footprint != calibrated containment or physical events.

    Camera-local catalogs remain intact and citable. No cross-view object
    associations are supplied by the current pipeline, so there is no fusion.
    """
    catalog = analysis.get("evidence_catalog") or []
    from task_actions import parse_task
    task = parse_task(analysis.get('task', ''), object_concept, destination)
    cameras = (analysis.get("multicamera") or {}).get("cameras") or []
    notes = ["Dry run: providers skipped; no physical conclusions." if dry_run else
             "Video-only evidence: no calibrated final interior, complete inventory, pose or holding-sensitive sensor measurement."]
    if cameras:
        notes.append("Camera-local evidence only. Time alignment does not establish physical object association. No cross-camera geometry or identity fusion is assessed.")
    ev = TC.InvestigationEvidence(analysis.get("episode_key", "uploaded"), task.task_id, n_frames, fps,
        frozenset(e["evidence_id"] for e in catalog),
        destination="unassessed", destination_evidence_ids=tuple(e["evidence_id"] for e in catalog
            if e.get("source") == "pipeline:report" and "segmentation" in str(e.get("summary", "")).lower()),
        tracking_evidence_ids=tuple(e['evidence_id'] for e in catalog if e.get('kind') == 'detection' and e.get('source') == 'sam:video'),
        tracking_missing_ranges=[tuple(r) for r in (analysis.get('analysis_coverage') or [{}])[0].get('missing_ranges', [])] if len(cameras) == 1 else [],
        viewpoints=tuple(c["camera_id"] for c in cameras) or ("primary",), notes=tuple(notes),
        analyzed_ranges=tuple((c['camera_id'], c['frame_start'], c['frame_end']) for c in cameras if 'frame_start' in c and 'frame_end' in c),
        camera_motion={c['camera_id']: c.get('motion', 'unknown') for c in cameras})
    result = bundle(task, ev)
    result['scope'] = 'Explicit user-task subgoals. Supported/Contradicted requires independently sourced evidence within the stated scope; model hypotheses and context frames are not verification. Recorded outcomes are unchanged.'
    result['coverage'] = analysis.get('analysis_coverage', [])
    result['context_frames'] = analysis.get('criterion_frame_context', [])
    result['task_text'] = task.description
    if dry_run:
        for a in result["assessments"]:
            a.update(state="not_assessed", basis="Dry run: SAM and Muse were skipped; no physical criterion was assessed.", evidence_ids=[], sources=[])
        result.update(completion="not_assessed", mechanisms=[], evidence_requirements=[], abstention_explanation=None)
    return result
