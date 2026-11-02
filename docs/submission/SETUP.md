# Judge setup: recorded replay, no credentials

Tested platform: Windows, Python 3.12, Node 24.19. Use Python 3.12 and Node
22.12+ (or a compatible newer release). npm ships with Node. macOS/Linux commands
are included but were not independently tested in this submission run.

## Windows PowerShell

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe live_api.py
```

Leave that terminal running. In a second terminal:

```powershell
cd web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open **http://127.0.0.1:5173/**. Choose EP010 for the featured investigation,
PILOT for the real SO-101 endpoint evidence, or EP005 for the Muse-only comparison.
No personal `.env` or provider account is needed. Do not enter API credentials.

## macOS/Linux equivalents

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python live_api.py
# second terminal
cd web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## Production frontend locally

Keep the backend running. From `web`: `npm run build`, then
`npm run preview -- --host 127.0.0.1 --port 4173 --strictPort`.
Open http://127.0.0.1:4173/. This is local preview, not a deployed site.

Both Vite modes proxy API/media requests to `http://127.0.0.1:8765`.
For a different backend port, set `DEMODOCTOR_API_URL` before starting Vite;
for example `$env:DEMODOCTOR_API_URL='http://127.0.0.1:8767'` in PowerShell.
Start that backend with `python -m uvicorn live_api:app --host 127.0.0.1 --port 8767`.

## What is available offline?

| Demonstration | What to inspect | Requires backend? |
|---|---|---|
| EP010 | SAM annotations, 43–46s interval, 44.50s measured opening, inferred release | No |
| EP003 | Saved 2D containment criterion met; orientation unverified | No |
| EP013 | Recorded end-state-supported failure | No |
| EP005 | Evidence abstains; Muse-only false success | No |
| EP006 | Evidence abstention | No |
| PILOT | Real endpoint comparison, 105-frame gap, missing tray mask | Yes, local only |

The optional ep010 Rerun viewer downloads about 67 MB from the installed npm
package on first open; it makes no inference calls. Main React replay works
without opening it. Do not make it part of the critical recording sequence.

All network access needed for setup is dependency installation. Demo media and
results are tracked. After installation, localhost replay needs no external
service. For a machine with no internet at all, prepare dependency caches before
the event. Do not distribute someone else's `.venv` or `node_modules` as source.

## Checks and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd web
npm test
npm run build
```

Optional scientific tests that need the original sample video/full SAM caches may
skip in a clean checkout. They are separate from the distributable replay tests.
For legacy Streamlit research data only, use `python setup_hackathon_demo.py`;
that downloader is not needed for React and can fetch additional large files.

If PILOT says unavailable, start the backend and check `/api/health`. The error
screen offers a cached EP010 recovery button. If 5173 is occupied, choose another
Vite port; relative proxy requests still work. Do not solve media problems by
enabling paid providers or substituting mock results.

Rebuilding compact media requires original licensed inputs and the private
maintainer packaging workflow, intentionally omitted from this public tree.
Ordinary judges need only the tracked replays; no private job directory or
reconstruction script is required.

## Optional local Real Analysis

Self-service Real Analysis is implemented; offline replay and Dry Run remain the
defaults. After one-time backend-only credential configuration, stop managed
services and explicitly start `scripts/start-demodoctor.ps1 -RealAnalysis` with
an adequate per-run limit. See the README Real Analysis section and the built-in
`/real-analysis-setup.html` guide for approval, budgeting and limitations.
No personal environment file is needed for offline replay. Do not register this
checkout globally if another working checkout is already registered.

## Current local investigation workflow

Use Import Footage → Recent Investigations to reopen completed local jobs after a
restart without credentials or new inference. Personal jobs are Git-ignored and
are not included in a fresh checkout. Findings opens task criteria by default;
technical sources remain expandable. Dry Run produces no physical conclusions.

Register the PowerShell commands with `scripts/register-demodoctor.ps1` and open
a new Windows PowerShell 5.1 terminal. Normal `DemoDoctor` remains offline.
`DemoDoctor-RealAnalysis -CredentialsFile C:\private\providers.env -PerRunBudgetUsd 2.10`
is an explicit local opt-in; it never automatically starts provider work. Stop
managed servers before switching modes. Review the actual quote in the UI and
approve Analyze personally. Estimates are not provider billing guarantees.

For composite crops or separate 2/3-camera MP4s, install FFmpeg explicitly and
make it available on PATH or through `DEMODOCTOR_FFMPEG`. No automatic installation.
Confirm crop regions and time alignment before preparing a camera set. Limits,
camera-local coordinates and uncertainty are documented in
[CAMERA_WORKFLOW.md](../CAMERA_WORKFLOW.md). Do not deploy the inference API.

Public tests use mocks and do not require credentials. Original full research
videos, raw SAM coverage caches and the original reference-audit file are optional
development inputs; tests requiring those exact inputs report skips. The six
replay investigations, criterion presentation and synthetic inference/history
regressions do not require those excluded inputs.
