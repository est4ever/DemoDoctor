# DemoDoctor

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
this incremental update transfers validated changes through
`097f8e1e6509b512886fc8eebe564007758bb759` without importing private commits.
The October 24 prototype predates the October 26 event start. See
[build history](docs/submission/BUILD_HISTORY.md) and
[snapshot provenance](docs/submission/SNAPSHOT.md). Public release commits
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

Optional registration for `DemoDoctor`, `DemoDoctor-Status` and `DemoDoctor-Stop`
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

## Analyze new footage locally

After one-time provider setup, each new video is handled entirely in **Import
footage**: choose **Real Analysis**, review the selected file/hash and exact
frame window, then click **Analyze — approve estimated cost**. Upload preparation,
refresh and startup never start paid inference. Results open automatically in the
investigation workstation; its `#job/<id>` URL restores them on refresh.

Ordinary `DemoDoctor` remains offline. To opt into real analysis for a local session:

```powershell
.\scripts\stop-demodoctor.ps1
# Credentials stay in an existing private file or the backend environment.
# Only the explicit limit changes the existing ledger's per-run cap; spend and total stay intact.
.\scripts\start-demodoctor.ps1 -RealAnalysis -CredentialsFile C:\private\providers.env -PerRunBudgetUsd 2.10
```

The registered `DemoDoctor` commands accept the same flags when this checkout
is the one explicitly registered.

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

This public update was validated with synthetic providers only. A fresh real-provider
run on a genuinely unseen video has not been executed for this release; implementation
and mocked end-to-end tests are not evidence of generalization accuracy.

## Manual startup and tests

For manual backend/frontend startup, alternate ports and production preview, use
[SETUP.md](docs/submission/SETUP.md). Both Vite modes proxy to the local backend;
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
[VALIDATION.md](docs/submission/VALIDATION.md) and the
[November 1 update report](docs/submission/UPDATE_20261101.md). The update report
records unresolved development-tool advisories. No skipped test is counted as passed.
macOS/Linux setup is documented but not independently validated in this release.

## Scope, provenance and licenses

Original code/documentation: [Apache-2.0](LICENSE), with [NOTICE](NOTICE).
BotFails and the separately identified SO-101 dataset have their own pinned
publisher-declared Apache-2.0 licenses. Dependencies, robot assets, model-output
terms and supplied final-video audio remain separate; see
[THIRD_PARTY.md](docs/submission/THIRD_PARTY.md). No model weights, environment,
compiled build, private jobs, source-video corpus or final-video production files
are distributed. Compact licensed display replays are intentional source assets.

Selected dataset-derived regression fixtures are retained. Exported copies omit
provider-operation metadata and use relative provenance paths; scientific values,
source IDs, citation bindings and the 19 distributable manifest files are unchanged.
See [SNAPSHOT.md](docs/submission/SNAPSHOT.md) for exact exclusions and hash records.

The legacy Streamlit interface and research modules remain in source; reproducing
all historical experiments requires additional original fixtures and separate
explicit provider setup. They are not needed for the React judge path. The local
API is not an authenticated multi-user public service; this release does not
deploy it. Results are a small research workflow demonstration, not large-scale
accuracy, causal proof or a robot safety certification.

[Project and submission text](docs/submission/FINAL_SUBMISSION.md) ·
[Architecture](docs/submission/ARCHITECTURE.md) ·
[Results and limitations](docs/submission/RESULTS.md) ·
[Publication approval procedure](docs/submission/PUBLICATION.md)
