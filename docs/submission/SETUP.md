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

Rebuilding the compact media is maintainer-only:
`scripts/prepare_submission_replays.py --help`. It requires the original recorded
inputs and refuses to overwrite an existing distribution. Ordinary judges never
need the original private job directory or the reconstruction script.
