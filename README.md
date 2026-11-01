# DemoDoctor

**Evidence-grounded robot failure analysis** for the Meta Global AI Developer
Hackathon. Intended track: **Indie Developer**; theme: **Push the Frontier**.
Eligibility for the disclosed pre-event foundation still needs organizer confirmation.

DemoDoctor connects robot video to SAM 3.1 object observations, measured robot
joints when available, independent claim verification and cited Muse Spark Open
explanations. Video, playback, timeline and evidence remain visible together;
side panels resize/collapse independently. Source inspection distinguishes
observed geometry, measured signals, inferred events and unknown outcomes.

This is a **new public-release snapshot**, not the original development Git
history. It derives from checkpoint `05b175db352ae306c8607e6e08f06036f330b55b`.
The October 24 prototype predates the October 26 event start. See
[build history](docs/submission/BUILD_HISTORY.md) and
[snapshot provenance](docs/submission/SNAPSHOT.md). A single new release commit
does not mean the whole project was built during the event.

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
paid providers are rejected by the launcher backend.

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
| EP005 | Illustrative Muse-only/evidence-grounded comparison; not a controlled scientific ablation |
| EP003 | Saved 2D containment criterion met; upright orientation unverified |
| EP013 | Saved end-state-supported failure; no invented timed failure event |
| EP006 | Evidence abstention from insufficient geometry |

Replays use saved real analysis and make no new model calls. The five cached
BotFails investigations also work with the frontend alone. PILOT requires the
local read-only API, started by the launcher. New uploads are explicitly dry-run
preparation: SAM/Muse are skipped, no physical findings are fabricated, and the
result remains uncertain. Dry run is not a demonstration of fresh real inference.

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
annotation modes preserve original frame timing. The optional EP010 Rerun viewer
lazy-loads about 67 MB of installed viewer Wasm; it is not required for offline
investigation. Legacy 3D mappings are not validated hardware ground truth.

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
[VALIDATION.md](docs/submission/VALIDATION.md). No skipped test is counted as passed.
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
