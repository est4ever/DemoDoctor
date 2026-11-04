# Defensive provenance and citation-integrity release candidate

Prepared November 2, 2026. **GO for a reviewed defensive-only release.** No push,
merge, paid inference, deployment or submission has been performed.

## Public history and exact source scope

Public parent: `0e2e69690a81b8188b8fdcd5b367dc60673fc696` (published README PR #2).
Local branch: `release/defensive-integrity-final`. Files are selectively transferred;
no private commits, Git objects or evaluation branch history are imported.

| Development checkpoint | Included | Excluded |
|---|---|---|
| `8c55a9f0e6a46690a8626b33010229f599a4ceb2` | Source/camera/window/task-object bounds, measured-holding requirement, independent-reference alias checks in task_criteria/task_actions, 14 defensive regressions | Pixel/action experimental modules and their conflict aggregators; no public consumer exists for them |
| `9f0c681e03b12ea4e973f4cce582d19aa107d58c` | Original-frame temporal selection and presentation needed by provenance repair | No physical-action recognition claim or detector |
| `2db00596baead65001ecc6e576afe4f6ea40b4bf` | Fresh authoritative source/camera/crop/frame validation, safe aliases, cache replacement/quarantine, frontend temporal guards and tests | Experimental API/UI dependencies |
| `c0f28c3eb370355750dd34fe86fed7c58924265e` | Original E-package/ID/span/time/claim binding, guarded source inspection and seek, explicit missing-metadata state, regressions | Experimental detector fixture changes for modules absent here |

Entire experimental feature commits `f00941c` and `f044466` are not imported.
No visual_motion/visual_actions modules, profile dispatch, assessor registrations,
components or response types are shipped. The previously published trusted-adapter
articulation contract remains narrow; it does not become a visual closure detector.

The 33 source/test transfers are listed below. README has one documentation-table
link; snapshot/source inventories are updated. LICENSE, NOTICE, dataset notices,
replays, provider outputs, media and dependency files are unchanged.

- Backend: live_api.py, multicamera_api.py, saved_jobs.py, saved_provenance.py,
  task_coverage.py, temporal_evidence.py, task_criteria.py, task_actions.py.
- Metadata exporter: scripts/export_citation_bindings.py.
- Python tests: test_saved_jobs.py, test_saved_provenance.py,
  test_task_coverage_report.py, test_temporal_evidence.py, test_citation_integrity.py,
  test_defensive_evidence_contracts.py (all under tests/).
- React: web/src/App.tsx; components/CriterionCoverage.tsx, DiagnosticDetails.tsx,
  TemporalContext.tsx, EvidenceSource.tsx, InvestigationDesk.tsx; lib/citationIntegrity.ts,
  recordedCitationBindings.json, criterionContext.ts, temporalContext.ts,
  savedInvestigations.ts and types.ts (components/lib paths under web/src/).
- React tests: components/CriterionCoverage.test.tsx, TemporalContext.test.tsx,
  MultiCameraImport.test.tsx; lib/citationIntegrity.test.ts, criterionContext.test.ts,
  temporalContext.test.ts (under web/src/).

## Integrity behavior

Saved evidence is checked against current approved source bytes, derived-camera
bytes, crop/clock/analysis-window records, original packages and original citation
maps. A correct content hash does not by itself validate that entire binding.
Unknown IDs, changed spans/times, camera/package mismatches, changed claims and
classifications fail closed. Cached authority cannot certify its own mutations.
Media and raw-analysis aliases use the same guard; dynamic responses are no-store.

The React workstation rejects mismatched records before presenting their footage
or measurement tables. Valid evidence selection uses original, validated source
timing. Untimed evidence never acquires a zero-time seek. Missing historical
binding metadata remains explicitly Unverifiable; raw records remain inspectable,
but trusted measurements/seeking are withheld. It is not treated as proof of
corruption, absence, success or failure. Missing camera maps cannot be silently
downgraded to certified single-camera authority.

Local consistency is not provider authentication against an owner replacing all
source media, approval records and packages. Matching a historical record also
does not establish the physical truth or semantic entailment of that record.

## Snapshot adaptations

The same tested defensive functions are retained. The only code exclusions remove
experimental API dispatch, component mounts and response types. Existing public
code line endings are preserved to keep the diff reviewable; byte-preserving Git
attributes remain unchanged. Public criterion/action modules use the previously
reviewed defensive subset, without experimental assessor registration.

The citation registry is regenerated from this public checkout's original source
artifacts. One copied EP010 package hash initially failed the registry regression
because development and public source bytes differ. The public original was not
changed: the registry now hashes the public original. Scientific catalog content,
frames and outcomes are unchanged. The initial failed receipt is retained locally.

## Executed tests on this public candidate

| Group | Result |
|---|---|
| Full public Python suite, project-local environment | **495 passed, 45 skipped**, no failures |
| Full public React suite | **173 passed**, no failures |
| Production TypeScript + Vite build | Passed |
| Targeted provenance/citation/criterion project regressions | 73 passed |
| Unchanged independent backend probes | **86 passed**: 3 citation + 26 earlier adversarial + 18 new adversarial + 39 provenance command |
| Unchanged independent React probes | **45 passed**: 4 citation + 8 provenance + 19 replay/context + 14 new adversarial |
| Applicable independent criterion/Muse/raw-verifier contracts | **71 passed**, 30 experimental pixel cases explicitly deselected |

Groups overlap and must not be summed as independent examples. The seven original
citation failures pass unchanged (3 backend and 4 React). The public suite has six
fewer React cases than the 179-case research tree because the two experimental
three-test detector components are absent. The private research tree's 663 tests
and the independent detached tree's 623 passes/40 skips are not public-candidate
counts. No evaluator assertion, reference outcome or threshold was changed.

All 45 public skips concern optional, nonbundled research inputs: 6 sample/joint,
3 sample/calibration, 1 original reference audit, 17 sample/joint/seeded chunk cache,
4 retrospective original SAM-cache cases, 7 sample/SAM cache, 5 undownloaded sample
videos and 2 legacy caches. They are not required by the six bundled replays.
Thirty generated-pixel detector cases are not applicable to this reduced release;
they are deselected, not counted as passes or physical-action evaluation.

Existing installed dependencies were used; no fresh installation, GPU validation
or independent native-browser execution by Codex 2 is claimed. One QA wrapper
initially omitted Vitest globals, so its eight-probe suite could not load. Enabling
the required harness setting, without editing probes, produced 45/45 passes.
A Windows console encoding error occurred after a successful React process;
the retained receipt and log show exit 0. It was a logging-wrapper issue.

## Native browser regression on the actual public build

Isolated gstack Chromium used this public checkout's FastAPI and production React
build, with original private artifacts copied only to Git-ignored QA storage
outside the public repository. Providers and external backend networking were
blocked. Normal launcher ports/processes were not used or stopped.

Verified interactions, rather than rendering alone:

- All six recordings: decoded original playback, pause, native frame stepping,
  Findings/Evidence/Unknowns, every E source entry, and available SAM-mask video or
  annotated-box overlay decoding. No missing mask asset is represented as a mask.
- Saved real DROID: offline reopening, refresh, original camera decoding, all five
  citations and source inspection. After selecting temporal frame 80 at 5.333333 s,
  valid E4 seeks to original frame 0 / 0 s. Its original catalog and outcome remain
  unchanged. Pickup, placement and drawer closure remain Unverified.
- EP010: original measured gripper source at frame 1335 / 44.5 s.
- PILOT: E2 and E4 retain a deliberately nonzero 0.166666 s clock while exposing
  missing-joint and empty-destination-mask explanations. Historical Muse links
  remain attached to the historical package.
- Three altered-citation copies: API aliases reject with HTTP 409 and React has a
  visible error without the previous video's footage. An isolated browser-only
  response mutation is also rejected; restoring normal GETs and refreshing recovers
  the valid investigation.
- Two-/three-camera mocked jobs generated through the existing pipeline: labeled
  synthetic input/providers, camera-specific source packages, synchronized seeking
  at 0.1 s, real video play/pause, frame stepping, single-view selection, primary
  expansion and refresh. Playback clocks match (two views 0.35 s; three views
  0.3334 s). These are software regression controls, not real multi-camera inference.
- Video/timeline/inspector fit at 1920×1080, 1440×900 and 1366×768.

Local receipts/screenshots remain under the development worktree's ignored
qa-browser-artifacts/defensive-release-final directory, outside this release.
No private DROID media or screenshot is committed.

## Scientific and remaining validation limits

No improvement in genuine-video physical-action recognition is claimed. Pickup,
release, placement, 3D containment, physical orientation and mechanical closure
still require independently sufficient observations or measurements. Additional
locally selected frames are not described as images originally supplied to Muse.
Cross-camera track IDs do not establish physical identity or calibrated geometry.

The six replay outcomes and original provider artifacts are preserved. The real
DROID job stays private and Uncertain with all three physical subgoals Unverified.
No new real multi-camera provider run is validated by these mocked controls.
Optional Rerun/GPU behavior was not re-exercised in this patch; its integration and
assets are unchanged and its lazy production build succeeds. Browser verification
uses local Chromium, not a cross-browser or cross-device certification.

The existing three-minute video remains a description of the recorded baseline;
this release adds defensive checks and does not validate new action-recognition
claims or require regenerating that video. Original attribution, Apache-2.0 terms,
third-party licenses and October 24 foundation/hackathon contribution disclosure
remain intact.

## Proposed publication, not executed

Proposed PR title: **Validate saved evidence provenance and citation bindings**.
Head: release/defensive-integrity-final. Base: main. This is a normal incremental
commit on public history. It does not include private development history.

After explicit approval, push that branch normally and open a review PR. Review
its full diff and available checks before a separately approved merge. No force
push, automatic merge, deployment or hackathon submission is part of this task.
