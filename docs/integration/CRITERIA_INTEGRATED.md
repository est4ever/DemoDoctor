# Integrated task-criterion assessment

Claude's additive commit `3d09778` was independently reviewed after multi-camera
checkpoint `bd148db`, then cherry-picked as `43190d2`. Scientific corrections
are documented in [CRITERIA_REVIEW.md](CRITERIA_REVIEW.md). The original Claude
worktree remains unchanged.

## Runtime boundaries

| Module / files | Role | Reads reference outcomes? |
|---|---|---|
| `task_criteria.py` | Pure four-state rules, scoped predicates, requirements, candidates | No |
| `saved_investigations.py` | Read-only structured inference-artifact adapters | No |
| `criteria_presentation.py` | Additive saved/live presentation | No |
| `data/tasks/criteria/` | Task inputs; exact count / physical pose unspecified | No |
| `web/public/criteria/` | Six separate offline presentations | No |
| `diagnostic_eval.py` | Evaluation only; predicts before loading references | Yes |
| `data/evaluation/diagnostic_eval_v1/` | Original Claude evaluation, archived unchanged | Historical evaluation |
| `data/evaluation/diagnostic_eval_v2/` | Corrected evaluation; candidates/abstention are not identified mechanisms | Yes |

Neither the API nor live inference imports the evaluator. Reference mechanisms,
episode labels, Muse prose and lexical categories cannot produce criterion
predicates. The original saved verdicts, model responses and citation packages
are unchanged.

## Additive result block

Live `analysis.json` contains optional `criteria` with schema
`demodoctor.criteria/v2`. For recordings, React attaches `/criteria/<episode>.json`
only when its investigation ID and used catalog records match the displayed
package (source, bounds and statement as well as ID). A missing optional file
does not break replay. These files do not replace frozen analysis JSON.

- `assessments`: criterion name/kind, Supported, Contradicted, Unverified or
  Not assessed; scoped basis, original evidence IDs, structured source records
  and resolving observations.
- `completion`: a separate physical-completion assessment. It never overwrites
  `pipeline_verdict` or `task_outcome`. Supported 2D containment cannot certify
  complete physical execution, even if a checklist is labeled complete.
- `mechanisms`: inferred or unverified candidates, original verifier status,
  citations, alternatives and resolving observations. Event names and a
  supported verifier entry alone cannot create observed physical facts.
- `notes`, `abstention_explanation`, `evidence_requirements` and, for cached
  presentations, `catalog_binding` and relative `source_artifacts`.

## Source entailment and time

`SourcePredicate` is created by trusted adapters from structured measurements,
not a Muse statement or arbitrary existing evidence ID. A decisive predicate
matches citation, object, native frame, camera, package, value and source
artifact. Held-out geometry is numerically rechecked against reliable interior
or clearly separated footprint rules and scoped to its original keyframe
catalog. JSON pointers resolve to the original object records.

EP003 retains **Supported 2D containment at sampled frame 2075**. That sample is
not the final frame of its 2090-frame recording. Later frames, physical pose,
inventory and full physical completion remain unverified. EP013's outside
object is likewise a supported contradiction at the sampled 2D frame; a later
recovery and causal mechanism remain unverified. Existing replay verdicts are
preserved and separately labeled.

Final-state criteria require each relevant object's own valid final frame.
Only the explicitly scoped saved `sampled_keyframe_2d` criterion permits the
late sample (within one second); it requires in-range, coincident per-object
frames. A recent observation of another object cannot validate a stale or
future observation. Orientation requires an explicit pose input and an
independently measured final-frame predicate; none of the six recordings has
one. Task anomaly vocabulary and singular wording do not supply pose or count.
Unspecified orientation is displayed as an unresolved diagnostic question,
not silently declared a required success condition.

## Live and camera behavior

`live_pipeline.run_analyze` adds assessments to ordinary single-camera results
and dry runs. `multicamera.run` adds one parent assessment using the existing
per-camera result catalogs. Dry runs are **Not assessed**, explicitly
provider-skipped, with no physical conclusions.

Current new-video inputs do not supply a calibrated final interior, declared
inventory or independently measured physical pose / holding-sensitive signal.
Their physical criteria remain unverified. A raw SAM destination footprint
does not establish calibrated containment. Camera-specific observations,
masks, timestamps and source-citation mappings remain unchanged.
Live containment is explicitly **unassessed**, not falsely classified as
missing segmentation when a raw footprint may be present. PILOT's recorded
`empty_result` remains a separate, actual missing-mask diagnostic.

Cross-view combination requires **both validated time alignment and explicit
physical-object association**, in addition to scoped source predicates. Shared
track strings are insufficient. Conflicts remain unknown. The current camera
pipeline provides no validated cross-view physical associations, so this
assessment layer does not fuse its cameras into physical facts. It does not
implement 3D reconstruction or orientation detection.

## Recompute and verify without inference

```powershell
python scripts/export-criteria.py
python scripts/export-criteria.py --check
python diagnostic_eval.py
python diagnostic_eval.py --check
python -m pytest tests -q
cd web
npm test -- --run
npm run build
```

`export-criteria.py` writes only new presentation files. `diagnostic_eval.py`
writes only v2; v1 and reference files remain unchanged. Natural-language
entailment is not independently evaluated by this report: valid-cited prose
is listed as `entailment_unverified`. Citation counts and keyword mentions are
not accuracy guarantees. Six recordings do not establish generalization.
