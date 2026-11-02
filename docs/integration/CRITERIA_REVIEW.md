# Independent review of Claude commit 3d09778

Reviewed after stable multi-camera checkpoint
`bd148dba46018c38c18a5d394b1b453157a59d64`, November 1, 2026.
Original branch/worktree remained unchanged. Original test result: **33 passed**.
These passing tests did not cover the following counterexamples.

## Confirmed findings before integration

| Severity | Location | Reproduction / actual behavior | Required correction |
|---|---|---|---|
| P1 scientific | `task_criteria.py::_check_citations`, `assess_orientation`, `assess_containment` | Supply any existing `E0` with an arbitrary `satisfies=True` orientation record: orientation becomes supported without a measured orientation predicate. Citation existence is the only decisive-state check | Bind decisive assessments to typed source claims, object identity, frame, camera/package and measurement kind; reject unsupported predicates |
| P1 scientific | `task_criteria.py::_final_frame_ok`, containment/inventory/orientation assessors | An outside observation at frame 40 plus another object at frame 99 of 100 makes containment contradicted; frame 1000 is also accepted as final | Validate every relevant object's own frame and source scope; reject out-of-range/future frames; no intermediate observation becomes a final task state |
| P1 scientific | `task_criteria.py::combine_views` | Same track ID in two cameras yields supported containment without any alignment or object-association evidence | Require explicit valid time alignment and physical-object association before cross-view fusion; preserve conflicts/unknowns |
| P1 presentation/scientific | `task_criteria.py::mechanism_candidates` | A failed-grasp record with `verifier='failed'` and nonexistent citation remains an observed mechanism | Demote unsupported event candidates to Unverified; mechanism names and statuses cannot establish physical facts |
| P2 task definition | `data/tasks/criteria/botfails_dish.json` | The dataset's task-level “wrong way” anomaly wording is converted to a required `upright_in_slot` physical predicate | Do not silently turn anomaly vocabulary into an approved orientation success criterion; require explicit pose specification |
| P2 task definition | `data/tasks/criteria/pilot_screwdriver_tray.json` | Definite singular “the screwdriver” is interpreted as exactly one expected object | Keep expected count undeclared unless supplied as task input; detections/wording do not establish complete inventory |
| P1 if used as verification | `diagnostic_eval.py::claim_audit`, `_mechanism_level` | Existing citation IDs plus keyword/hedge matching are treated as a claim audit; generic unverified criteria are described as localized mechanisms | Distinguish lexical mentions from verified claims and inferred candidates; never count abstention as successful mechanism identification |

Reproduction receipt (local/ignored):
`qa-browser-artifacts/criteria-review/original-reproductions.json`.

## Ground-truth separation

`task_criteria.py` is pure rules with no file reads. `saved_investigations.py`
reads recorded inference/model artifacts and criteria specifications, not
`reference_mechanisms.json`, reference outcomes, event labels or evaluation
scores. `diagnostic_eval.run()` computes its predictions before loading
references. This is a useful separation and must remain in the product.

Dataset-level anomaly wording in a criteria specification is not per-episode
label leakage, but it is still an unsupported success-criterion assumption.
Reference labels, mechanism keywords and model prose must never be promoted into
runtime criterion evidence. Evaluation-only imports must remain outside runtime
result generation and the API.

## Integration requirements

- Preserve Claude's original commit and archived v1 evaluation artifacts and
  reference file. Correct the new assessment layer locally; do not edit frozen
  research outputs or reference outcomes to satisfy new tests.
- Preserve EP003's recorded supported **2D** containment finding separately from
  full physical completion, inventory and orientation uncertainty.
- Preserve every saved verdict, original evidence ID and historical PILOT Muse
  package binding. Add a separately versioned, optional assessment block.
- No current investigation has an independently measured physical orientation
  predicate. Do not invent one from masks, model text or a reference mechanism.
- For current live/multi-camera videos, absent calibrated destination interior,
  inventory, orientation, sensor and cross-view associations remain explicit
  missing evidence. Valid source timestamps alone do not establish object identity.
- Product UI must show the four states, their actual scoped basis/citations,
  resolving observations and labeled inferred/unverified mechanism candidates.
- Corrected evaluation outputs must be separate from the original v1 snapshots.
  Keyword categories are evaluation annotations, not verification or predictions.

The findings above were reported before cherry-picking Claude's additive commit.
No paid inference is authorized by this review or integration.

## Corrections applied

- Typed source predicates bind object, frame, camera and package to structured
  source records. Held-out geometry is checked numerically, with resolvable
  JSON pointers. Citation existence cannot establish orientation or an event.
- Per-object checks reject stale, mismatched and future frames. EP003's 2D
  finding is scoped to its sampled late frame. EP013's sample does not
  establish that no later recovery occurred.
- View combination requires both validated alignment and explicit physical
  object associations. Current camera adapters supply no such associations;
  conflicts and physical criteria remain uncertain.
- Unbound or verifier-failed event candidates remain Unverified; valid inferred
  releases remain Inferred, not observed physical events.
- Expected counts and approved poses are undeclared. Physical completion is
  not certified by 2D containment or a checklist-completeness flag.
  Unspecified orientation is diagnostic, not a required success predicate.
- Corrected evaluation v2 distinguishes candidate mechanisms, abstention,
  lexical mentions, citations and semantic-entailment limits. Original v1 and
  reference files are unchanged.
- Additive presentations are connected to ordinary live generation, camera
  parent results and all six workstations. Original citation controls are
  reused. Dry Run produces Not assessed and no physical conclusions.

Original positive synthetic tests now supply typed source fixtures. New
adversarial tests cover the reproduced failures, source-scope mismatches,
conflicting views, missing count/pose, source-pointer resolution and invariance
of predictions to evaluation-reference changes. No verification rule was
weakened to make a test pass.
