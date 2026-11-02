# Explicit task-action coverage

Implemented locally on `feat/integrated-demo`, November 1, 2026. No new paid
inference, reference-label changes, public-release changes or video edits.

## Root cause and Claude integration

The previous live adapter replaced task text with a fixed containment,
inventory, grasp/release and completion checklist. It never represented
"close the drawer". The composite route also uses image-only reconstruction
for one camera, fixes its overall outcome to Uncertain, and formerly supplied
only camera endpoints to Muse. An empty physical-claim set passing verification
did not establish action coverage.

Claude commit `3d09778` was already reviewed and cherry-picked as `43190d2`,
then corrected in `fbb7a4a` and `0e64573`. It must not be merged again. The
reviewed engine's source predicates, four states, citation checks and
conservative completion rules are reused. The archived original interface
is not the current contract; see [CRITERIA_REVIEW.md](CRITERIA_REVIEW.md).

## Changes

- `task_actions.py`: deterministic, limited English clause parser. Explicit
  pickup, put/place/store-in and close/shut instructions become named required
  subgoals. Negative, conditional and unsupported clauses remain visible as
  Not assessed and block completion. An adjective such as "open drawer" does
  not invent an opening action. No count, orientation or other requirement is
  added from a dataset label or model suggestion.
- `task_criteria.py`: an action assessor runs through the existing engine.
  Missing action measurements produce Unverified. Scoped 2D articulation can
  be Supported, Contradicted or Unverified, independently of full physical
  completion. EP003's original sampled 2D containment remains separate.
- `criteria_presentation.py`: displays actual explicit subgoals, their
  contextual citations, missing measurements and resolving observations.
  Undeclared generic categories are Not assessed, not extra required subgoals.
- `multicamera.py`: bounded original-frame context includes intermediate
  coverage/gap frames when capacity permits. **The existing maximum remains
  six images total:** up to six for one camera, three each for two, two each
  for three. Therefore three-camera reasoning still has endpoint-only visual
  context. Requests remain sequential, with the same budget reservation and
  zero automatic paid retries. Muse receives explicit subgoals but may not
  promote its visual interpretation into a verified fact.
- Per-camera reports distinguish the approved native processing interval,
  returned observations, missing spans and frames outside analysis. Camera,
  original source, crop and derived hashes remain explicit. The approval UI
  now shows actual crop coordinates, source/derived hashes and explicit task
  clauses. Crop extraction also rejects dimension mismatches.
- `task_coverage.py` and the analysis GET route: older completed camera jobs
  receive a read-only current presentation after source/crop/approval integrity
  checks. Existing provider outputs, task verdicts and E/F citations are not
  overwritten. New local context uses **C references**, never historical Muse
  F references. A provenance failure produces a visible error and no stale
  criterion fallback.
- React context controls seek the native timestamp on the correct camera.
  Repeated clicks restore that camera even after a manual view change.
  Existing resizable panels, single-camera playback and source controls remain.

## What can make closure decisive

The current SAM adapter supplies **no articulation measurement**. A raw drawer
mask or a Muse description is insufficient. Consequently this change does
not automatically detect drawer closure in the DROID footage.

The pure engine's independently sourced articulation interface requires:

1. Citable structured before/after records bound to the same target, camera,
   package and source records, within the analyzed interval.
2. A stationary camera; moving/unknown-camera inputs are not accepted by this
   simple 2D comparison. No static-camera assumption is applied to wrist video.
3. An independently established reference geometry and normalized extension
   measurements, with declared finite open/closed thresholds. The initial
   measurement must actually support open; final data must be at the native
   final source frame. Intermediate or out-of-window data cannot stand in.
4. Agreement of the typed value with the numeric comparison. Existing citation
   IDs, model prose, event names and boolean "verified" tags are insufficient.
5. Explicit time alignment and target association before combining views.
   Conflicting views remain Unverified; matching track strings do not associate
   physical objects.

Supported/Contradicted here applies to the **2D articulation predicate**, not
force, latching, 3D geometry, grasp, release or whole-task completion. The
positive/negative measurements in regression tests are synthetic fixtures,
not newly observed DROID measurements. Pickup and placement also remain
Unverified without independently validated event/holding/interior inputs.
No automatic pickup or placement verifier is introduced by this patch.

## DROID reassessment from the existing job

Original job: `<private-local-job>`. All 18 original files remain
byte-for-byte unchanged against the preceding audit's SHA256 manifest.

| Explicit subgoal | Current assessment | Existing contextual source | Independent action support |
|---|---|---|---|
| Pick up the blue block | Unverified | Original cam1/E4 detections | No bound pickup/holding event |
| Put it in the open drawer | Unverified | Original cam1/E1 destination footprint | No validated interior placement/final-state event |
| Close the drawer | Unverified | Original frames available for inspection | No articulated-state measurement |

Overall recorded verdict remains **Uncertain**. No reference success label is
used as a prediction. This is improved task coverage and explanation, not
successful failure identification or an automatic success judgement.

Actual approved crop is `[0,0,1280,720]`, not the earlier written proposal's
`[8,8,1280,720]`. The historical job is not corrected in place. Processing was
`[0,155)` at 15 FPS, with returned detections at `[0,93)` and `[124,128)`, gaps
`[93,124)` and `[128,155)`, and unprocessed tail `[155,158)`.

Candidate local context references, in selection order, are native frames
**0, 154, 92, 124, 108, 46**, retaining original source timestamps. Frame 108 is
available footage inside the analyzed interval but has no returned SAM object
observation. It is not relabeled as a detection. Frame 154 shows an apparently
closed drawer, as noted by the earlier human audit; this remains visual context,
not a newly computed geometry predicate. No new Muse response was generated.

The separate private report is written under
`qa-browser-artifacts/task-coverage/droid-reassessment/`. It and the screenshots
remain Git-ignored; the DROID footage is not bundled in source changes.

```powershell
python scripts/reassess-task-coverage.py `
  data/live_jobs/<private-local-job> `
  --output qa-browser-artifacts/task-coverage/droid-reassessment
```

The command refuses output inside the original job and rejects modified source,
camera or approved-manifest provenance. It imports no inference providers.
After restarting the backend to load this code, the normal investigation GET
also supplies this read-only assessment. Opening/refreshing it does not start
inference. The ordinary launcher remains offline by default and is unchanged.

## Validation

- Complete repository Python suite (`pytest tests -q`): **425 passed**.
- Frontend suite, preserving all existing tests: **109 passed**, 20 files.
- TypeScript check and production Vite build: passed.
- Synthetic cases cover supported/open/ambiguous closure, incomplete multi-step
  tasks, undeclared/conditional instructions, absent initial/intermediate
  evidence, future/out-of-window frames, missing/mismatched citations, numeric
  inconsistency, moving cameras, missing association and cross-view conflict.
- Mocked one-, two- and three-camera upload/approval/results and refresh
  recovery were exercised through gstack Chromium. Crop readback, cost review,
  subgoals, correct-camera context seeking and zero real calls were checked.
- All six recorded investigations were opened in the browser; Findings,
  Evidence, Unknowns, source inspection and frame stepping were checked against
  their saved packages. The five cached episodes retained SAM switching;
  bundled PILOT uses its existing annotated box view without mask assets.
  EP010's measured-gripper E2 and EP003's sampled frame-2075 2D scope remain.
- DROID video, timeline and selected inspector remained visible at 1920×1080,
  1440×900 and 1366×768; frame-154 context seeking and untimed E2 inspection
  were exercised. The latter does not seek to zero.

Evidence/logs: `qa-browser-artifacts/task-coverage/`. Initial browser-probe
selector/route assumptions and unrestricted pytest discovery of ignored
dependency copies failed; those are retained in logs. The reported passing
checks use actual rendered controls/routes and the complete repository `tests/`
suite. No tests or thresholds were removed to obtain these results.

## Remaining limits and paid-test recommendation

The parser is a transparent controlled subset, not general natural-language
planning. Context selection is deterministic sampling, not action recognition.
No current adapter supplies decisive closure geometry, physical pickup or
placement measurements. The image-only route's overall uncertainty guard is
retained. These remain diagnostic-capability limits.

Repeating the same SAM request would mostly reproduce the same evidence; the
three omitted tail frames alone do not address the missing action measurement.
More original frames sent to Muse could yield new **hypotheses**, not independent
verification. A second/third view may supply genuinely new observations around
the occlusion, but cannot by itself certify cross-view identity or drawer closure.
Review the already-recorded alternative views without payment first, establish
the measurement/reference protocol, then separately approve a targeted experiment
if it answers an unresolved question. No further paid run is recommended yet.
