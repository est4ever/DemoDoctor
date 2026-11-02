# DemoDoctor technical reference

Detailed operating instructions and historical validation context for the published
application baseline. Start with the [visual project overview](../README.md).
This reference preserves the longer technical content formerly on the landing page.

**Evidence-grounded robot failure analysis** for the Meta Global AI Developer
Hackathon. Intended track: **Indie Developer**; theme: **Push the Frontier**.
Eligibility for the disclosed pre-event foundation still needs organizer confirmation.

DemoDoctor connects robot video to SAM 3.1 object observations, measured robot
joints when available, independent claim verification and cited Muse Spark Open
explanations. Video, playback, timeline and evidence remain visible together;
side panels resize/collapse independently. Source inspection distinguishes
observed geometry, measured signals, inferred events and unknown outcomes.

This repository has its own public Git history, separate from private development.
The initial snapshot derived from `05b175db352ae306c8607e6e08f06036f330b55b`;
the application update transferred validated changes through
`de5009f26818d6d8a6cc0b15ba87fd89004095b6` without importing private commits.
The October 24 prototype predates the October 26 event start. See
[build history](../docs/submission/BUILD_HISTORY.md) and
[snapshot provenance](../docs/submission/SNAPSHOT.md). Public release commits
do not mean the whole project was built during the event.

## Offline judge quick start

Tested on Windows PowerShell 5.1, Python 3.12 and Node 24.19. Use Python 3.12 and
Node 22.12+ (or compatible newer). Install dependencies explicitly; the launcher
never installs them. No `.env`, credentials, dataset download or paid inference
is needed for these six recorded demonstrations.

From the checkout root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Push-Location web
npm ci
Pop-Location
.\scripts\start-demodoctor.ps1
```

The launcher starts FastAPI at `127.0.0.1:8765`, Vite at `127.0.0.1:5173`, checks
readiness and the six recorded demonstrations, opens the default browser and
returns control. It defaults to offline/cache replay and dry-run uploads;
paid providers are rejected by the ordinary offline launcher backend.
Real Analysis requires the separate explicit local opt-in described below.

```powershell
.\scripts\status-demodoctor.ps1
.\scripts\stop-demodoctor.ps1
```

Repeat starts reuse verified services. Unknown port occupants cause a clear
error and are never killed. Stop acts only on launcher-owned processes. Logs
and ownership state are Git-ignored under `.demodoctor/`. Keep that directory
until services have stopped. The launcher prefers this checkout's `.venv`, then
`venv`, then a legacy sibling `../DemoDoctor/venv`; use a local `.venv` for a
portable installation or pass `-Python <python.exe>` explicitly.

Optional registration for `DemoDoctor`, `DemoDoctor-RealAnalysis`,
`DemoDoctor-Status` and `DemoDoctor-Stop`
from any directory in a new Windows PowerShell session:

```powershell
.\scripts\register-demodoctor.ps1
```

Registration changes only the current user's PowerShell profile and backs up
existing content. Do not run it if you want to keep another checkout registered;
calling these scripts directly requires no profile change or administrator rights.
No execution-policy or global Python changes are required.

## Six replayable investigations

After startup, open **http://127.0.0.1:5173/** and choose a demonstration.

| Demonstration | Evidence and limitation |
|---|---|
| PILOT | Genuine recorded SO-101 SAM/Muse artifacts; two independently checked image-space claims; uncertain task outcome |
| EP010 | Measured gripper opening at 44.50s supports an inferred release; holding, intent and placement remain unverified |
| EP005 | Unverified saved flat-orientation hypothesis and original citations; outcome remains uncertain; comparison is illustrative |
| EP003 | Saved 2D containment criterion met; upright orientation unverified |
| EP013 | Saved end-state-supported failure; no invented timed failure event |
| EP006 | Evidence abstention from insufficient geometry |

Replays use saved real analysis and make no new model calls. The five cached
BotFails investigations also work with the frontend alone. PILOT requires the
local read-only API, started by the launcher. New uploads default to explicitly
labeled Dry Run preparation: SAM/Muse are skipped, no physical findings are
fabricated, and the result remains uncertain. Real Analysis is implemented but
requires provider configuration, explicit local opt-in and per-job cost approval.
Dry run is not a demonstration of fresh real inference.

In the video-only PILOT, recorded box centers are approximately **609 pixels
apart (609.01 px)**. There is a **105-frame observation gap, 433-537 inclusive**;
this does not establish continuous tracking or confirmed physical travel across
the gap. Destination segmentation returned **no usable tray mask**, not proof
that the tray was absent. No measured gripper/joint signals exist for this clip.
Object identity, physical release, placement and task outcome remain qualified
or unverified. Original Muse citations retain their original evidence package;
later offline reconstruction was never fed back into that historical Muse response.

Select evidence to inspect its source. Timed evidence seeks the video; untimed
evidence opens its explanation without inventing a timestamp. SAM overlay and
annotation modes preserve original frame timing. Findings now exposes saved
diagnostic hypotheses and visual interpretations, all explicitly Unverified,
plus task-criterion coverage. Supported assessment sources do not establish
criterion satisfaction; orientation is unassessed and missing evidence never
changes an outcome. Missing citations/frame references are explicit.
The optional EP010 Rerun viewer
lazy-loads about 67 MB of installed viewer Wasm; it is not required for offline
investigation. Legacy 3D mappings are not validated hardware ground truth.

## Reopen a saved local investigation

Open **Import footage → Recent Investigations** to see locally saved jobs,
separate from the six bundled demonstrations. Each entry shows its task, original
filename (when recorded), analysis date, camera count, analysis type, status and
qualified saved outcome. Choose **Open Investigation** to restore the saved video,
camera views, SAM evidence, Muse citations and task criteria. This works after a
browser or backend restart with ordinary offline `DemoDoctor`, without provider
credentials, another upload or another inference charge. Bookmark the
`http://127.0.0.1:5173/#job/<job-id>` URL to open the same investigation directly.

History comes from the current backend's `data/live_jobs` directory, not browser
storage or the bundled demonstration library. Keep this Git-ignored directory to
retain personal investigations; it is not included in a fresh checkout. The list
shows the latest 50 job identifiers. Older jobs remain available by their URLs.
Missing, unreadable or incomplete results show an explicit error and never trigger
automatic inference. Dry Run entries remain provider-skipped preparation with no
physical conclusions. Original saved results are not overwritten when reopening;
historical camera jobs can receive a read-only task-coverage presentation.

Completed investigations with criterion assessments open **Findings** with
**Task-criterion coverage** expanded first. Each criterion shows its assessment,
basis and missing resolving evidence. Source records, citations, context frames
and processing provenance remain expandable. These presentations preserve the
original saved outcome; Dry Run criteria remain explicitly Not assessed.

## Analyze new footage locally

After one-time provider setup, each new video is handled entirely in **Import
footage**: choose **Real Analysis**, review the selected file/hash and exact
frame window, then click **Analyze — approve estimated cost**. Upload preparation,
refresh and startup never start paid inference. Results open automatically in the
investigation workstation; its `#job/<id>` URL restores them on refresh.

Ordinary `DemoDoctor` remains offline. To opt into real analysis for a local session:

```powershell
DemoDoctor-Stop
# Credentials stay in an existing private file or the backend environment.
# Only the explicit limit changes the existing ledger's per-run cap; spend and total stay intact.
DemoDoctor-RealAnalysis -CredentialsFile C:\private\providers.env -PerRunBudgetUsd 2.10
```

If the dedicated command is missing in an older installation, run
`.\scripts\register-demodoctor.ps1` from this checkout in Windows PowerShell 5.1,
then open a **new** terminal. The command wraps the existing
`DemoDoctor -RealAnalysis` implementation; it does not create another inference
pipeline or automatically stop an existing session. It supports `-Python`,
`-NoBrowser` and `-TimeoutSeconds` as well. Omitting `-PerRunBudgetUsd` preserves
the current ledger limit; the example explicitly requests $2.10 per run while
retaining the total budget, spending history and reservations. To return offline:

```powershell
DemoDoctor-Stop
DemoDoctor
```

The credentials file contains `MODEL_API_KEY` for Meta and `FIREWORKS_API_KEY` for
Fireworks. An ignored project-local `.env` or existing process environment also
works; omit `-CredentialsFile` in that case. Keys never enter the browser or its
storage. Readiness indicates configuration presence, **not** successful account
authentication, sufficient credits or guaranteed model availability. Missing
configuration has visible setup instructions. No dependencies are installed by
the launcher. No developer or terminal is needed for each subsequent video.

The default $1 run cap is smaller than the $1.32 full-context Muse reservation
before SAM. Explicitly configuring an adequate run cap is required; neither the
UI nor a normal launch raises it. Existing spend, reservations, unknown-charge
reconciliation and total limits remain enforced. Estimates use standard published
rates and are **not provider-enforced billing guarantees**. Account pricing must
be checked before spending. There are zero automatic paid retries. A lost start
response recovers the same job; approval is single-use and expires after 15 minutes.
Interrupted jobs are marked on backend restart and never resumed automatically.

Use a single-camera MP4 that both browser and backend can decode. Analyze an
explicit window of at most 30 seconds; the default is only the first four seconds.
Declare a complete task only when the full attempt is present and selected.
The pipeline supplies video-only observations, not measured gripper opening,
contact, force or release. Raw destination footprints have no calibrated interior
and assume a stationary camera/target. The outcome rule is `all_objects_in_target`,
not arbitrary task-language verification; drawer closure and similar articulated
goals cannot be certified. An uncertain outcome is valid. Missing segmentation
does not mean the destination was physically absent. Failures do not substitute
mock evidence. Repeated identical media may reuse genuine cached SAM observations,
which remain labeled by their provenance.

The setup guide is also available from Import at `/real-analysis-setup.html`.
Keep the API bound to loopback; do not deploy it as a public inference endpoint.
Stop the enabled session before returning to ordinary offline `DemoDoctor`.

## One workflow for 1–3 camera views (camera sets experimental)

After updating this checkout, restart launcher-managed services with
`DemoDoctor-Stop` followed by `DemoDoctor` to load the new backend in offline mode.

Import Footage has one **Camera count** selector: **1**, **2** or **3**, with one
Dry Run/Real Analysis selector, progress display and cost-approval panel. The
default is one ordinary camera recording using the established single-camera
analysis. Select separate synchronized MP4 recordings with explicitly approved
offsets/alignment for multiple views, or confirm one, two or three crops in one
composite MP4. FFmpeg must already be on the backend PATH (or configured through
`DEMODOCTOR_FFMPEG`). The app suggests regions from the preview, labels uncertain
layout suggestions and requires confirmation before extraction. No external
cropping is needed. FFmpeg is not installed automatically. All crops are checked
against decoded source frame counts and presentation timestamps. The MVP accepts
constant-rate, zero-origin sources of at most five minutes and analyzes a shared
window of at most 30 seconds. Unsupported timing is rejected rather than silently
resampled. Each source is limited to 200 MiB.

Start with **Dry Run** to inspect crop boundaries, synchronized views, the primary
view and independent camera provenance without providers, using
the same workflow for all counts. The Camera display control switches between
all views, one view and the original composite; SAM modes are camera-specific.
Questions about placement, orientation, completion and occlusion are passed to
Muse as questions, not verified facts. Real Analysis requires
the same explicit local launch, a complete per-camera operation/cost plan and
personal approval. Requests run sequentially, followed by one camera-labeled
Muse explanation; the first failure stops later operations with zero paid retries.
The combined estimate and actual reservations share one per-run budget.

Camera-set results (including one selected composite crop) retain camera-local tracks, masks, original source IDs,
frames and citations. They do **not** match physical objects across cameras or
verify 3D, orientation, grasp, release, drawer closure or task completion. Physical
event reconstruction is disabled for camera sets in this MVP, including for wrist cameras.
The combined outcome remains **Uncertain**, even when views appear consistent.
Muse diagnostic hypotheses remain **Unverified**. These new-video capabilities
have been tested with mocked providers; they are not a new real-inference
validation result. Normal one-camera inference rules are preserved. See the
[unified workflow guide](../docs/CAMERA_WORKFLOW.md) and
[scope, setup and validation](../docs/MULTICAMERA_MVP.md).

Computed task criteria use Supported, Contradicted, Unverified and Not assessed,
with original source bindings and the observations needed to resolve uncertainty.
Explicit pickup, placement and close instructions are parsed using a controlled
English subset, not a general planner. Context frames and Muse hypotheses are not
independent verification. EP003's sampled 2D containment remains distinct from
full physical completion; EP005's orientation hypothesis remains Unverified and
its saved outcome Uncertain. No orientation or 3D detector is implemented.

The unified workflow has mocked one-, two- and three-camera validation. The owner
also performed one private genuine one-view SAM/Muse UI run; it returned an
Uncertain outcome and does not establish diagnostic accuracy or generalization.
That video's media, jobs and provider records are not distributed. No genuine
multi-camera provider run or validated cross-camera identity is claimed.

See [camera setup and limitations](../docs/CAMERA_WORKFLOW.md),
[criterion semantics](../docs/integration/CRITERIA_INTEGRATED.md) and
[explicit action coverage](../docs/integration/TASK_ACTION_COVERAGE.md).
The retrospective [held-out report](../data/evaluation/heldout_diagnostic_v1/REPORT.md)
was generated in development; reproducing its raw tracking counts requires
optional original SAM caches, deliberately not bundled. The public test suite
reports those data-dependent checks as skips and still executes synthetic
coverage, prediction/reference separation and citation regressions. It does not
substitute invented observations for missing caches.

## Manual startup and tests

For manual backend/frontend startup, alternate ports and production preview, use
[SETUP.md](../docs/submission/SETUP.md). Both Vite modes proxy to the local backend;
`DEMODOCTOR_API_URL` overrides that target for an isolated instance.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -rs
Push-Location web
npm test
npm run build
Pop-Location
```

The Python suite marks tests requiring original full videos/SAM caches as
`real_data`; those fixtures are intentionally absent and corresponding tests may
skip. Actual snapshot counts and browser checks are in
[VALIDATION.md](../docs/submission/VALIDATION.md) and the
[November 1 update report](../docs/submission/UPDATE_20261101.md). The update report
records unresolved development-tool advisories. No skipped test is counted as passed.
macOS/Linux setup is documented but not independently validated in this release.

## Scope, provenance and licenses

Original code/documentation: [Apache-2.0](../LICENSE), with [NOTICE](../NOTICE).
BotFails and the separately identified SO-101 dataset have their own pinned
publisher-declared Apache-2.0 licenses. Dependencies, robot assets, model-output
terms and supplied final-video audio remain separate; see
[THIRD_PARTY.md](../docs/submission/THIRD_PARTY.md). No model weights, environment,
compiled build, private jobs, source-video corpus or final-video production files
are distributed. Compact licensed display replays are intentional source assets.

Selected dataset-derived regression fixtures are retained. Exported copies omit
provider-operation metadata and use relative provenance paths; scientific values,
source IDs, citation bindings and the 19 distributable manifest files are unchanged.
See [SNAPSHOT.md](../docs/submission/SNAPSHOT.md) for exact exclusions and hash records.

The legacy Streamlit interface and research modules remain in source; reproducing
all historical experiments requires additional original fixtures and separate
explicit provider setup. They are not needed for the React judge path. The local
API is not an authenticated multi-user public service; this release does not
deploy it. Results are a small research workflow demonstration, not large-scale
accuracy, causal proof or a robot safety certification.

[Project and submission text](../docs/submission/FINAL_SUBMISSION.md) ·
[Architecture](../docs/submission/ARCHITECTURE.md) ·
[Results and limitations](../docs/submission/RESULTS.md) ·
[Publication approval procedure](../docs/submission/PUBLICATION.md)

## Published baseline validation

Dated verification and remaining decisions: [final update report](../docs/submission/FINAL_UPDATE_20261101.md). This report records the earlier release gate. The validated application was subsequently merged into public main; historical approval language is not a current pending-publication status.

## Original temporal evidence and diagnostic context

Findings keeps task-criterion coverage expanded and displays a small chronological
set of original video frames. Each retains its native time and camera/source ID.
Saved Muse catalog inputs are distinguished from locally selected context, and
missing SAM observations are identified without inventing motion or measurements.
Original hypotheses remain Unverified. Camera-labelled interpretation links select
their own validated view and timestamp.

Optional local analyst interpretations are separate, hash/frame-bound and always
Unverified. They do not change original results or certify mechanical closure.
Private review notes, DROID jobs and media are excluded from this repository.
See [diagnostic context and provenance](../docs/integration/DIAGNOSTIC_CONTEXT.md).

## Frozen application baseline

Current acceptance results, exact file inventory, real-versus-mocked scope, video review and unresolved publication decisions are in [release readiness](../docs/submission/RELEASE_READINESS_20261101.md). The validated application was merged into public main as `96caf60efeff214ab4550bba6be6f0cf96480bb9`. Dated reports retain their original review context.
