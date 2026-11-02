# Windows launcher verification

## Dedicated Real Analysis command — November 1, 2026

`DemoDoctor-RealAnalysis` is now registered alongside the three original profile
functions. It dispatches to `scripts/start-demodoctor-real-analysis.ps1`, which
forwards explicitly supplied options to the existing `start-demodoctor.ps1
-RealAnalysis` path. Normal `DemoDoctor` remains offline by default. No new
inference pipeline, provider retry or browser credential storage was added.

Verified with fresh, profile-enabled Windows PowerShell **5.1.26100.9818**
processes starting in `%TEMP%`, rather than dot-sourcing a function into the
testing session:

- The real-analysis command resolved from the current-user Windows PowerShell
  profile and cold-started both services on loopback ports 8765 and 5173.
- The existing private credentials file was loaded by the backend only. Actual
  configuration checks reported Meta and Fireworks configured. This checks
  presence, not provider authentication, credit or availability.
- An ignored, process-local QA hook replaced only inference with the existing
  synthetic-provider fixtures and blocked outbound Python connections. It used
  isolated jobs and a separate $10/$2.10 test ledger. It is not installed or
  imported by ordinary launcher sessions. No real provider calls were made.
- gstack Chromium displayed both configured badges, Real-analysis session
  enabled, and Dry Run selected by default. Preparing a synthetic MP4 and
  reviewing the estimate made no provider calls. Explicit approval executed
  the mocked SAM-video, SAM-image and Muse sequence, opened the visibly labeled
  synthetic investigation, and recovered that result after refresh. No browser
  console errors occurred.
- A repeat command reused both service PIDs. The ordinary launcher refused to
  reuse a real-analysis backend as an offline session. Managed shutdown released
  both ports; another fresh process successfully started ordinary offline mode.
- The original ledger remained at $10 total/$1 per run with zero spending and
  reservations. The test hook was absent from the restored offline process.
- Targeted Python/PowerShell regression tests: **20 passed**. Frontend import
  workflow tests: **8 passed**. New regression tests cover parameter forwarding,
  invalid budgets, preserving an omitted budget, idempotent profile registration,
  unrelated profile functions and loading the registered function in another
  PowerShell process.

Screenshots and machine-readable receipts are local, ignored files under
`qa-browser-artifacts/real-analysis-command-20261101/`. Credentials were never
printed or copied into those artifacts. The app was left running offline after
testing. To start a personal real-provider session explicitly:

```powershell
DemoDoctor-Stop
DemoDoctor-RealAnalysis -CredentialsFile 'C:\private\providers.env' -PerRunBudgetUsd 2.10
```

The explicit cap changes only the existing ledger's per-run limit, not its total,
spending or reservations. Omit it to retain the existing cap. Estimates are not
provider-enforced billing guarantees. In Import Footage, choose Real Analysis,
review the exact file/window and estimate, and approve Analyze personally.

## Original offline launcher verification

Verified on October 31, 2026, using Windows PowerShell **5.1.26100.9818**
(Desktop edition), with a **non-administrator** Windows token. Execution policy
remained `RemoteSigned`; no PATH, global Python or browser settings changed.

## Results

| Check | Result |
|---|---|
| Fresh terminal, arbitrary working directory | Passed: new profile-enabled PowerShell sessions invoked `DemoDoctor` from `%TEMP%` and `C:\Windows\Temp`. |
| Cold startup | Passed: both standard ports were free, then FastAPI and Vite started automatically on loopback ports 8765 and 5173. |
| Python discovery | Passed: no checkout-local environment existed; the documented sibling `DemoDoctor\venv\Scripts\python.exe` was selected without installation. |
| Browser opening | Passed: the default HTTP handler was `ChromeHTML`; Chrome displayed **DemoDoctor — demo diagnosis** at the launcher URL. |
| All recorded investigations | Passed: PILOT, EP010, EP005, EP003, EP013 and EP006 loaded their expected titles, evidence inspectors, synchronized timelines and decoded videos in Chromium. |
| Repeat launch | Passed: a second fresh-session command reused both original service PIDs. |
| Status | Passed: both live services reported `Running`, `Managed=True` and their actual PIDs; after shutdown both reported `Stopped`, `Managed=False`. |
| Backend recovery | Passed: stopping the managed backend and starting again created a new backend instance while preserving the frontend PID. |
| Managed shutdown | Passed: both ports were released. Windows venv redirector and actual service PIDs were handled separately. |
| Port conflicts | Passed: unrelated test listeners on each standard port were refused with a clear error and left alive. |
| Unrelated PID safety | Passed: a PID ownership record pointing at the test PowerShell process did not authorize termination. |
| Manual-service reuse | Passed before migration: the original matching manual services were reused and never adopted or stopped by `DemoDoctor-Stop`. |
| Profile registration | Passed: all three functions loaded in new terminals; repeat registration produced identical profile content. |
| Offline guard | Passed with a stub: paid-mode dispatch raised HTTP 403 before any pipeline/provider invocation; dry-run and cache-only dispatch remained available. |

The owner explicitly authorized migration from the existing manual services.
Before stopping them, their identities and console memberships were checked.
Ctrl+C was sent only to the verified DemoDoctor service consoles; the two
parent PowerShell sessions remained alive. No unrelated application was stopped.

## Replay checks

Startup checks the application HTML, backend health, PILOT analysis through the
frontend proxy, a ranged PILOT video response, all five cached analysis JSON
files and their videos. It makes no inference requests.

The separate browser pass opened each investigation and verified the actual
video source, decoded dimensions/readiness, expected analysis title, evidence
inspector and matching video/timeline time. All six videos reached
`readyState=4`; no page exceptions occurred. External browser requests were
blocked during this test.

The real PILOT displayed two independently checked claims, the 609.01-pixel
box-center endpoint difference, the hatched frames 433–537 observation gap,
and an uncertain outcome. No scientific results or application source files
were changed.

## Automated checks

- `scripts/test-demodoctor-launcher.ps1 -OpenBrowser`: all integration checks
  passed, including cold/repeat launch, backend recovery, replays, shutdown,
  both port conflicts and unrelated PID protection.
- `python -m pytest tests/test_launcher_offline.py -q`: passed again after
  cold-launch verification; the provider/pipeline dispatch was stubbed.
- `python -m pytest tests -q`: **234 passed** in the preceding implementation
  pass. No launcher code changed between that run and this final verification.
- Frontend suite: **22 passed**; TypeScript and production Vite build passed
  in the implementation pass. Frontend source/configuration remained unchanged.
- All launcher PowerShell files parsed under installed PowerShell 5.1;
  `node --check scripts/launcher_frontend.mjs` passed.
- `git diff --check`: passed.

The initial unscoped Python discovery included duplicate tests in ignored local
tool/check-out copies and failed collection. The explicit repository `tests`
directory run above passed; those local artifacts were not added to Git.

## Repeating the checks

Stop launcher-managed services with `DemoDoctor-Stop`. Ensure manual services
have been stopped separately, then run:

```powershell
.\scripts\test-demodoctor-launcher.ps1 -OpenBrowser
```

The integration script refuses to run while either standard port is occupied.
It shuts down its managed services after the main checks. Use `DemoDoctor` again
to reopen the app. Local logs, ownership records, browser observations and the
PILOT screenshot remain in ignored `.demodoctor/` storage and are not committed.

PowerShell 7 and other machines were not separately tested. Preparation of
dependencies remains an explicit owner action; the launcher never installs them.
