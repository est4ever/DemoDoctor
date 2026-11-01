# DemoDoctor investigation UI

React, Vite, and TypeScript workstation for inspecting robot demonstrations. The graphite-and-lime interface keeps real footage, source evidence, and one synchronized playback clock together. Streamlit remains the supported fallback.

For the submission-ready setup, follow [the judge guide](../docs/submission/SETUP.md).
It includes a local backend and six recorded demonstrations without credentials.

## Views and evidence

- **Overview:** featured real footage, six recorded demonstrations (five cached BotFails episodes and the SO-101 pilot), and an import entry point.
- **Investigation:** large uncropped camera footage, Original / SAM Overlay / Annotated views when available, a shared timeline, and an evidence inspector.
- **Evidence inspector:** readable findings and timestamps, search and provenance filters, selected evidence, original technical records, findings, and unknowns. Evidence references and event buttons seek the camera.
- **Import footage:** local video preview and preparation progress. This UI locks dry run on and sends `run_muse=false`; there is no paid-inference toggle.
- **Advanced Robotics Viewer:** optional lazy-loaded Rerun for the existing frozen ep010 event-window recording. It has its own recording timeline and returns to the primary investigation.

The primary investigation uses normal document scrolling. Selected evidence stays visible while scrolling on desktop; the workspace stacks on smaller screens. Space toggles playback and arrow keys step frames when focus is outside a form control.

Observed image measurements, inferred interpretations, and uncertain task outcomes have separate meanings. A measured change does not establish a grasp, release, successful placement, or task completion. The UI preserves explicit evidence context and does not upgrade labels from the wording of a claim.

## Run the prototype

From the repository root:

```powershell
cd web
npm ci
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Open `http://127.0.0.1:5174/` for the overview or `http://127.0.0.1:5174/#ep010` for the investigation. Cached episodes are **ep010**, **ep005**, **ep003**, **ep013**, and **ep006**. Browsing these episodes does not call SAM or Muse.

### Media in a fresh checkout

Episode JSON is tracked under `public/data/`. Compact camera and SAM overlay videos
are tracked under `public/replays/`, with Apache-2.0 attribution and modification
notices. The recorded PILOT is served by the local backend from the tracked
`data/submission_demo/` package. No local media restoration or export is needed
for the primary React judge path. Full research media under `public/data/` remain
ignored and are not used by this path.

The repository's `scripts/export_web_demo_bundles.py` and `scripts/export_ep010_web_bundle.py` are separate export workflows. Their prerequisites and outputs should be reviewed before use; they are not required frontend setup commands when the existing media is available.

### Optional local dry run

Run the existing local analysis service separately from the repository root:

```powershell
.\venv\Scripts\python.exe live_api.py
```

In **Import footage**, choose a browser-supported video, describe the task, and use **Check local service**. When the video decodes and the service is available, **Prepare dry run** becomes available. The UI shows returned job states and service-reported stages. Completed results are available in the investigation; selecting a cached episode returns to its frozen replay.

Vite development proxies `/api` and `/live-data` to `http://127.0.0.1:8765`. No keys are needed for dry run; it exercises transport and rendering, not model quality. The default preparation window is the first four seconds, or an explicitly selected custom window. The backend remains responsible for its request limits and validation.

Production hosting needs equivalent API/media routes. The current `vite preview`
configuration proxies `/api` and `/live-data` to the same backend target as the
development server; keep that local backend running for PILOT. This is local
preview, not production hosting. `DEMODOCTOR_API_URL` selects the backend origin.

## Frontend verification

```powershell
cd web
npm test
npm run build
```

With the dev server running on port 5174 and the installed gstack browser available:

```powershell
node scripts/ui-smoke.cjs
node scripts/refinement-check.cjs verify
```

Both browser scripts support `GSTACK_BROWSER` and `UI_BASE_URL` environment overrides. The smoke pass uses synthetic browser transport responses for preparation-progress checks; it does not submit a real inference job. The refinement pass captures 1440×900 and 1920×1080 screenshots at verified 100% zoom and checks evidence seeking, playback, SAM switching, responsive layouts, and Rerun navigation.

Current separate-snapshot validation is in [VALIDATION.md](../docs/submission/VALIDATION.md); panel behavior is documented in [PANEL_LAYOUT.md](../docs/ui-review/PANEL_LAYOUT.md).

## Robot assets and optional visualization limits

URDF and STL assets under `public/robots/so100/` come from [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100), licensed Apache-2.0. See `public/robots/SO-ARM100_LICENSE` and each episode's `mapping.json` for provenance and mapping caveats.

The approximate Three.js workspace source remains in the repository but is not imported by the primary workstation. Joint/URDF mapping is not physically validated. Rerun remains ep010-specific and has a large optional Wasm payload; graphics capability affects its performance. Trust camera footage and source evidence for physical claims.
