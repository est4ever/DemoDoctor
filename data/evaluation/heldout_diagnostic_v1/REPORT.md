# Retrospective held-out diagnostic evaluation

Retrospective frozen held-out split, already inspected during development; not a prospective unseen-video or generalization study.

Predictions and source-frame counts are computed before reference outcomes are loaded. Frozen outputs are unchanged; no new inference. EP010 development and PILOT are context only; EP006's disputed reference is excluded. Three scorable episodes are too few for accuracy claims.

## Outcomes and diagnosis

| Episode | Evaluation role | Reference | Pipeline | Criteria completion | Grounded Muse | Muse-only | Mechanism evidence |
|---|---|---|---|---|---|---|---|
| ep003 | scored retrospective held-out | success | success | uncertain | success | success | No reconstructed physical mechanism |
| ep005 | scored retrospective held-out | failure | uncertain | uncertain | uncertain | success | No reconstructed physical mechanism |
| ep006 | disputed reference | success | uncertain | uncertain | uncertain | success | No reconstructed physical mechanism |
| ep010 | development or no independent reference | failure | uncertain | uncertain | uncertain | failure | released_outside_target (inferred) |
| ep013 | scored retrospective held-out | failure | failure | uncertain | failure | failure | object_outside_target_at_sample (unverified) |
| pilot | development or no independent reference | unknown | uncertain | uncertain | uncertain | not run | No reconstructed physical mechanism |

| System | Correct definitive | Wrong definitive | Abstain | Scorable |
|---|---|---|---|---|
| pipeline | 2 | 0 | 1 | 3 |
| criteria_completion | 0 | 0 | 3 | 3 |
| evidence_grounded_muse | 2 | 0 | 1 | 3 |
| muse_only | 2 | 1 | 0 | 3 |

EP013 reconstructs an outside-target **2D sample**, not the cause or unobserved later recovery. EP005's saved flat-orientation suggestion is a plausible **Unverified hypothesis**, not measured orientation. Zero independently verified physical mechanisms; abstention is not failure identification.

## Actual inspectable tracking coverage

| Episode | Video frames | Requested frames | Inspectable unique frames | Observation records | Mask records | Video fraction | Cache-bound discrepancies |
|---|---|---|---|---|---|---|---|
| ep003 | 2090 | 240 | 120 | 360 | 360 | 5.74% | [] |
| ep005 | 2090 | 240 | 120 | 360 | 360 | 5.74% | [] |
| ep006 | 2090 | 240 | 120 | 360 | 360 | 5.74% | [] |
| ep010 | 2090 | 121 | 121 | 363 | 363 | 5.79% | [] |
| ep013 | 2090 | 120 | 120 | 360 | 360 | 5.74% | [] |
| pilot | 737 | 737 | 632 | 632 | 0 | 85.75% | [] |

Some frozen runs requested two 120-frame windows but distribute only the later observation artifact. The report counts actual unique frame indices, not observations divided by three or provider-processed frames. A final segmentation image is not continuous tracking. Missing inspectable artifacts are not proof the provider missed a detection. EP010's actual raw-cache window is [1260,1381), including its recorded frame 1380. PILOT has 632/737 observed frames, with frames 433–537 unobserved. Coverage is not mask quality, object recall or identity continuity.

## False claims and citation reliability

- Mask counts refer only to retained artifacts. PILOT's packaged track export has boxes/centers and no mask payloads; zero retained masks does not mean the provider returned zero masks.
- Muse-only EP005 success disagrees with the documented failure reference. This is an outcome error, not a per-statement semantic audit.
- Semantic false-claim count: **not established**. Existing cited prose remains entailment-unverified by this retrospective evaluator; zero citation errors must not be called zero false claims.
- ep003: 17 evidence + 3 frame references; 0 invalid IDs; historical package=False.
- ep005: 19 evidence + 4 frame references; 0 invalid IDs; historical package=False.
- ep006: 15 evidence + 2 frame references; 0 invalid IDs; historical package=False.
- ep010: 16 evidence + 2 frame references; 0 invalid IDs; historical package=False.
- ep013: 16 evidence + 4 frame references; 0 invalid IDs; historical package=False.
- pilot: 4 evidence + 0 frame references; 0 invalid IDs; historical package=True.

All criteria and hypotheses keep their original evidence package. Predictions do not read references. No new measurements, failure labels, 3D estimates or cross-camera physical associations were created.

## Resolving observations and reproducibility

Each episode's JSON includes verbatim saved hypotheses, scoped criteria, per-criterion resolving observations, source paths/hashes and citation diagnostics. Orientation needs an approved pose definition plus an independent measurement; inventory needs an explicit expected count; final placement needs final-frame geometry; release needs holding-sensitive data and continuous object association. Additional views can reduce occlusion, but do not automatically establish 3D or identity.

Run `python heldout_diagnostic_eval.py --check` to reproduce. This report is never imported by runtime prediction. A prospective newly uploaded robot-video run still requires separate explicit paid-inference approval.
