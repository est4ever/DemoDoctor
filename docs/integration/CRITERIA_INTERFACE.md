# Proposed interface: task-criterion assessments and evidence requirements

**Archived original proposal.** The integrated interface is now v2; see
[CRITERIA_INTEGRATED.md](CRITERIA_INTEGRATED.md) and
[CRITERIA_REVIEW.md](CRITERIA_REVIEW.md). Citation-existence checks, automatic
view association and the orientation/count assumptions below were corrected.
Do not use this original proposal as the current implementation contract.

Status: **proposal only**. Branch `feat/claude-failure-analysis` adds isolated modules and does not edit
shared files (`app.py`, `live_api.py`, `live_pipeline.py`, `demo_replay.py`, `evidence_fusion.py`,
`failures.py`, `verification.py`, `web/`). Nothing here changes a frozen verdict or a saved artifact.

## What exists on this branch

| File | Role | Reads references? |
|---|---|---|
| `task_criteria.py` | Pure rules: four criterion states, evidence requirements, mechanism candidates | No |
| `saved_investigations.py` | Read-only adapters: saved artifacts → `InvestigationEvidence` | No |
| `data/tasks/criteria/*.json` | Declared criteria per task (separate from `data/tasks/botfails_dish.json`) | No |
| `diagnostic_eval.py` | Standalone evaluation and report writer | Yes (only here) |
| `data/evaluation/reference_mechanisms.json` | Evaluation-only references with quoted sources | — |
| `data/evaluation/diagnostic_eval_v1/` | Generated `REPORT.md` and `evaluation.json` | — |

## Proposed `criteria` block for `analysis.json` (live and replay)

Additive and optional. Consumers that ignore it are unaffected. Existing `pipeline_verdict`/`task_outcome`
stay authoritative for the current UI; `criteria.completion` is a stricter, separately labeled view.

```jsonc
"criteria": {
  "schema": "demodoctor.criteria/v1",
  "task_criteria": "data/tasks/criteria/botfails_dish.json",
  "completion": "unverified",               // supported | contradicted | unverified | not_assessed
  "abstention_explanation": "Abstains: required criteria ... Evidence that could resolve them: ...",
  "assessments": [{
    "criterion_id": "containment", "kind": "containment", "required": true,
    "state": "unverified",
    "basis": "At final frame 2075, 3 of 3 region(s) are unknown ...",
    "evidence_ids": ["E4"],                 // must exist in evidence_catalog
    "objects": {"green plate:0": "unknown"},
    "requirements": [{"kind": "additional_viewpoint", "criterion_id": "containment",
                      "reason": "...", "objects": ["green plate:0"], "frames": [2075, 2076]}],
    "blocking": []                          // completion only
  }],
  "mechanisms": [{"mechanism": "released_outside_target", "category": "placement_outside_target",
                  "status": "inferred", "verifier": "supported", "objects": ["green plate:1"],
                  "frames": [1293, 1351], "evidence_ids": ["E0", "E1", "E2"],
                  "alternatives": ["..."], "criterion_id": "grasp_release",
                  "resolving_evidence": [{"kind": "gripper_measurement", "...": "..."}]}],
  "evidence_requirements": [ /* deduplicated requirements of required, unverified criteria */ ]
}
```

Producing it is one call: `task_criteria.assess(task, evidence).to_dict()`. Requirement kinds:
`additional_viewpoint`, `final_state_observation`, `gripper_measurement`, `destination_mask`,
`continuous_tracking`, `orientation_measurement`, `task_specification`.

## Hooks for multi-camera work (Codex)

No change to camera processing is needed to adopt this. When per-camera results exist:

1. Emit one `ObjectObservation(object_id, concept, region, frame, evidence_ids, view="<camera id>")` per
   object per camera at the final frame, and set `InvestigationEvidence.viewpoints` to the camera ids.
2. `combine_views` is conservative: agreement → that region; inside-vs-outside disagreement → `unknown`;
   `unknown` in one view defers to the other view. Object ids must already be associated across cameras;
   this module does not do cross-view identity.
3. An `additional_viewpoint` requirement with `objects`/`frames` tells the multi-camera pipeline which
   objects and frames a second view would resolve. A UI can show it as "a wrist/side view of frame 2075
   would settle containment of green plate:0".
4. `OrientationObservation(object_id, satisfies, frame, evidence_ids, view)` is the slot for a future
   orientation predicate (e.g. from a side view). Until such a measured source exists, orientation stays
   `unverified`, never inferred from model text.

## Suggested UI change (not made here)

`web/src/components/DiagnosticDetails.tsx` currently renders fixed text for "Task-criterion coverage"
(location/orientation/inventory/completion/grasp). Once `criteria` is exported, that panel can render
`assessments[].state`, `basis`, `evidence_ids` (existing citation buttons) and `requirements[].reason`.
Keep the existing "Missing evidence never implies success or failure" copy.

## Integration steps

1. Merge this branch after Codex's multi-camera branch (no overlapping files expected; verify with
   `git diff --stat main...feat/claude-failure-analysis`).
2. Run `pytest tests/test_task_criteria.py tests/test_diagnostic_eval.py` and `python diagnostic_eval.py --check`.
3. Optional, separately reviewed: call `task_criteria.assess` from the replay exporter / live pipeline and
   add the `criteria` block above; then update the panel.
4. If a criteria file changes, regenerate with `python diagnostic_eval.py` and review the diff of
   `data/evaluation/diagnostic_eval_v1/`.
