# Combined defensive-integrity and usability release candidate

Prepared November 2, 2026. **GO for final independent review; publication remains
unapproved.** This is a selective incremental update on the public repository's
own history, not an import of private development commits.

Public parent: `27375223d2740e4a3570c5212632a8be15bf008c`.
Local branch: `release/combined-integrity-usability-final`.
Development checkpoint: `bb5c509ac2dff14b3c1c0dcc2afdbe5d9407cebf`.

## Included work and exclusions

The parent already contains the reviewed defensive subsets from `8c55a9f`,
`9f0c681`, `2db0059` and `c0f28c3`: source/camera/crop/frame provenance validation,
strict historical citation binding, missing-evidence abstention and locally
selected original-frame temporal inspection. Their existing public adaptations,
registry hashes and history are preserved.

This update selectively includes:

- `70a0a67`: useful paused initial position, readable investigation summaries,
  preserved intentional seeks including zero, and independent timeline markers.
- `6674f8a`: source-grounded observed prose, synchronous episode navigation and
  focused keyboard/focus/form improvements. Unverified displacement proposals
  remain hypotheses rather than recorded measurements.
- `6ec15cf`: memory-only upload draft retention, unload/discard protection,
  field-specific multi-camera errors/focus and explicit synchronization offsets.
- `f5de6d5`, `14ba306`, `bb5c509`: strict JSON numeric validation at preparation,
  saved-record/API and React result/seek boundaries. Approved metadata comparison
  remains exact; citation time tolerances are unchanged.

The source transfer includes only required code, regression tests and the numeric
repair explanation. Experimental `visual_motion`/`visual_actions` detectors,
their profile dispatch, UI components and response types are absent. Public
`task_criteria.py` and `task_actions.py` remain the previously reviewed defensive
subset, without experimental detector registration. No new physical-action
recognition, model, calibration or 3D reconstruction is introduced.

## Numeric reproduction and behavior

The original unchanged independent synchronization test returned 200 after
changing a saved numeric zero offset to JSON false. Python's ordinary dictionary
comparison treats False as equal to zero. Before this repair, the original suite
was **11 passed / 1 failed**. It now passes **12/12 unchanged**.

Supplied offsets, native/shared timestamps, native frame indices, mapping entries,
crop pixels, dimensions, FPS and duration use actual finite JSON numbers, with
integer-only fields remaining integers. Booleans, null, empty strings and numeric
strings cannot stand in for these numbers. Metadata equality is exact and typed;
int/float numeric zero remains equivalent. A tiny changed offset is still a
mismatch. Legitimate uncropped `crop: null` and omitted optional legacy fields
retain their meanings; no missing value becomes zero.

Invalid provenance quarantines with HTTP 409. Camera/root track aliases and
analysis copies retain the same checks. React validates camera numbers before
video arithmetic as well as before temporal-frame seeking. No historical file is
rewritten to make it valid. Matching content hashes are separate from validating
the entire source/crop/frame/citation binding. Local consistency is not provider
authentication against an owner replacing every authoritative local artifact.

## Draft and workstation behavior

Draft File references, task, prompts, windows, analysis mode and camera settings
survive in-app navigation in memory. Blob URLs are recreated and preview decoding
is required again. Restoring a manual crop does not replace it with a fresh layout
suggestion. No credential, approval token, draft text or file is serialized into
browser storage. Existing session storage contains only job recovery identity.

Refresh/close warns before discarding meaningful work; cancelling retains it.
Confirmed discard or Reset creates a fresh draft. Reset does not remove saved
investigations and is disabled while job state is active/unknown. Returning never
starts upload/inference and never restores paid approval. This is not crash-safe
autosave: native prompts can be suppressed without activation or on OS eviction.

Camera errors are inline, announced and focus their visible correction control,
including repeated identical submissions. Empty offsets stay empty and block
preparation. Explicit zero still needs approved separate-source alignment and a
stated basis. Composite cameras inherit common-source zero with crop confirmation.

Fresh investigations are paused at one second, or the shorter available end.
Intentional source/saved seeks, including zero, take precedence. The timeline
still begins at zero; original timestamps, outcomes and citations are unchanged.

## Executed candidate checks

| Gate on this separate public candidate | Result |
| --- | --- |
| Full public Python suite, existing project-local environment | **533 passed, 45 skipped** |
| Full public React suite | **259 passed** |
| Unchanged independent frontend/workflow assertions | **94 passed**: 74 earlier + 20 workflows |
| Unchanged independent backend assertions | **72 passed**, including original 12 synchronization cases |
| Production TypeScript/Vite build | **Passed** |
| Native Chromium workstation regression | **89 checks passed** |
| Native Chromium upload/draft/focus regression | **29 checks passed** |
| Original saved DROID reopen, E4 zero and refresh | **Passed** |
| Two/three-camera decoding, shared playback and zero seek | **Passed** |
| Numeric corruption and React response quarantine/recovery | **Passed** |

Groups overlap and must not be summed as unique videos or recognition accuracy.
The backend independent group contains 3 citation, 26 earlier adversarial,
18 citation-adversarial, 13 temporal-provenance and 12 synchronization assertions.
The two project temporal/coverage files that complete the earlier 39-case
provenance command are also included in the full project run. The seven original
citation failures remain covered unchanged: 3 backend and 4 actual-App assertions.
Independent source/expectation hashes are checked against the evaluator commits.

The 45 skips are the same optional research inputs: 6 sample/joint, 3 calibration,
1 original reference audit, 17 joint/seeded-chunk, 4 retrospective original SAM,
7 sample/SAM-cache, 5 undownloaded sample videos and 2 legacy caches. None is
required for six bundled replays. No fresh dependency installation, GPU or paid
provider run is claimed. Dependency files and prior advisory disclosures remain
unchanged.

All browser services used this checkout's actual backend and production build on
isolated localhost ports. Credentials/dotenv loading and external backend network
connections were disabled; real provider dispatch was forbidden. Native uploads
used Dry Run. Synthetic camera layouts deliberately reused one original replay
as multiple separate inputs or panel crops; they are software controls, not
different genuine viewpoints or new SAM/Muse experiments. Their results correctly
state that providers were skipped and contain no physical findings. Real-analysis
approval and failure workflows were tested with mocked transports only.

Native checks include all six recorded investigations, numbered markers with
mouse/keyboard, playback/frame stepping/overlays, exact zero seeking, corrupted
citation quarantine, refresh, three desktop sizes, resizable panels, genuine
decoded saved DROID, cancellation/reset dialogs and focused camera correction.
The original DROID outcome remains Uncertain; pickup, placement and drawer closure
remain Unverified. Original E4 still seeks to zero. It is not bundled publicly.

Local receipts/screenshots remain outside this public checkout under the
development workspace's ignored `qa-browser-artifacts/numeric-integrity-final`
and `qa-browser-artifacts/vercel-guidelines` directories. No private job,
recording, ledger or browser screenshot is committed as a release artifact.

## Integrity and remaining limits

The release scan checks the explicit file allowlist, source transfer hashes,
unchanged nonapproved baseline files, LICENSE/NOTICE/attribution/build-history
disclosure, 19 replay asset hashes, all source-inventory entries and known secret
patterns. No private Git objects are imported. Original local jobs/ledgers,
provider outputs, six frozen investigations and final video remain unchanged.
README presentation assets and existing development-history disclosure remain.

No new release-blocking defect was reproduced by these executed gates. Final
independent review is still pending. This is not full guideline/accessibility
certification or a claim of generalized failure-detection accuracy.

Six earlier P2 findings remain: inspector context not fully in URLs; adjacent
content not inert during resizing; playhead `left` positioning; inconsistent
`translate="no"`; no durable idempotency key for unpaid preparations; and eager
hidden temporal-preview initialization. Existing paid-start locks, single-use
approval, budget limits, origin protection and zero paid retries remain.

Actual browser-menu 125%/200% zoom, real screen-reader speech, Safari/Firefox,
physical mobile/hybrid/IME input, constrained-device performance and embedded
Rerun accessibility are not certified. Research detector cases for modules absent
from this release are not represented as passing production action recognition.
Pickup, physical release, calibrated 3D containment/orientation and mechanical
closure still require independent evidence. Extra local temporal frames are not
described as images originally received by Muse.

The existing three-minute video is unchanged and still describes the baseline
prototype. It does not demonstrate these new defensive checks or validate new
action-recognition claims. No push, merge, deployment, paid inference, public
visibility change or hackathon submission occurred. Proposed PR after approval:
**Harden numeric provenance and complete investigation usability**.

## Exact changed files relative to public parent

```text
README.md
docs/integration/COMBINED_RELEASE_REVIEW.md
docs/integration/NUMERIC_PROVENANCE_REPAIR.md
docs/submission/SNAPSHOT.md
docs/submission/SNAPSHOT_PROVENANCE.json
docs/submission/SOURCE_MANIFEST.json
live_api.py
multicamera.py
saved_provenance.py
tests/test_multicamera.py
tests/test_saved_provenance.py
web/index.html
web/src/App.regression-1.test.tsx
web/src/App.tsx
web/src/components/CameraInputs.tsx
web/src/components/CriterionCoverage.tsx
web/src/components/DiagnosticDetails.tsx
web/src/components/ImportFootage.tsx
web/src/components/InvestigationDesk.inspection.test.tsx
web/src/components/InvestigationDesk.panels.test.tsx
web/src/components/InvestigationDesk.tsx
web/src/components/InvestigationOverview.test.tsx
web/src/components/InvestigationOverview.tsx
web/src/components/LiveAnalyzePanel.test.tsx
web/src/components/LiveAnalyzePanel.tsx
web/src/components/RecordedEvidence.tsx
web/src/components/UploadDraft.test.tsx
web/src/components/VideoPane.tsx
web/src/components/Workstation.accessibility.test.tsx
web/src/components/ui.tsx
web/src/lib/citationIntegrity.test.ts
web/src/lib/citationIntegrity.ts
web/src/lib/criterionContext.test.ts
web/src/lib/criterionContext.ts
web/src/lib/playbackIntent.ts
web/src/lib/readableEvidence.test.ts
web/src/lib/readableEvidence.ts
web/src/lib/recordedNavigation.json
web/src/lib/timelineNavigation.ts
web/src/lib/types.ts
web/src/lib/uploadDraft.ts
web/src/lib/workstationNavigation.test.ts
web/src/workstation.css
```
