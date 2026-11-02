# Local prototype: first run and release checklist

Use the [README quick start](../../README.md#quick-start). Windows PowerShell 5.1,
Python 3.12 and Node 22.12+ are the supported setup. Install locked Python and
React dependencies explicitly; the launcher never installs them. The six replays
require no API keys, personal .env, additional dataset downloads or new inference.
The dependency installation needs Internet access; replay afterwards is local.

## Start, explore, stop

From the repository root after installing dependencies:

```powershell
.\scripts\start-demodoctor.ps1
# Browser opens http://127.0.0.1:5173/
.\scripts\status-demodoctor.ps1
.\scripts\stop-demodoctor.ps1
```

1. Open EP005. Findings shows the saved possible flat plate-orientation hypothesis
   as **Unverified**. Outcome remains **Uncertain**.
2. Open EP010, Evidence, and the measured gripper entry. Inspect source reveals
   the original sample; gripper opening is not proof of release or grasp.
3. Select a numbered timeline marker, step a frame, and play/pause. The timeline
   starts at zero. A fresh investigation starts paused near one second; an
   intentional source seek or restored playback position takes precedence.
4. Open PILOT and its untimed E2 source. No seek is invented. Inspect the gap and
   missing usable destination mask; endpoint separation is not continuous travel.
5. Try Import Footage in **Dry Run** with your own non-sensitive video. It prepares
   video without providers or physical conclusions. A completed job appears under
   Recent Investigations and reopens offline. A fresh install has no personal jobs.
6. Keep unfinished drafts by navigating within the app. Refresh/close asks before
   discarding meaningful work; this is memory-only retention, not crash-safe autosave.
7. Stop with the command above. Saved jobs remain; only this launcher's owned
   processes stop. Manually started services require stopping their own terminal.

For blocked scripts, use the process-only PowerShell exception in the README.
Do not change global execution policy or run as administrator. If 5173/8765 are
occupied, status identifies the conflict; no unrelated service is stopped. The
[setup guide](SETUP.md#production-frontend-locally) documents alternate ports and
manual start. Stop manual servers with Ctrl+C in their own terminals.

Desktop: collapse/expand panels and drag or keyboard-resize dividers; Enter resets
a divider. Narrow windows use drawers and intentional scrolling. Tab/Shift+Tab
stay within an open drawer, including links; Escape closes it and restores focus.

## Read the mode before interpreting a result

| Visible mode | Meaning |
| --- | --- |
| Saved analysis replay | Recorded demonstration or cache-only output; viewing makes no new provider calls. |
| Dry Run · no inference | SAM/Muse skipped. Preparation success is not robot-task success. |
| Real Analysis · saved outputs | Local records report completed SAM and Muse provider execution. Reopening is still replay, not another paid analysis. This label is not remote provider authentication or scientific validation. |
| Experimental · execution unconfirmed | Recorded provider flags do not establish real execution; never treat generated test data as genuine robot inference. |
| Saved analysis · mode unconfirmed | Legacy/missing execution metadata. Sources remain inspectable if their integrity checks pass; absence of metadata is not proof of fraud or successful inference. |

The local backend computes these descriptions without rewriting saved artifacts.
An outcome or `dry_run: false` alone does not prove provider execution. The
inspector and job history retain the distinction. Unverified hypotheses, inferred
mechanisms and scoped visual measurements remain separate from physical events.

Two-/three-camera workflow integration is **experimental/mock-tested**. It does
not establish cross-camera object identity, calibrated geometry or action accuracy.
One private unfamiliar-video run completed with real providers and an Uncertain
outcome. It does not validate generalized failure detection and is not bundled.

## Optional paid Real Analysis

Do not enable it to explore the six demonstrations. If deliberately needed,
follow [the README](../../README.md#optional-real-analysis): configure your own
backend-only provider credentials, stop managed offline services, explicitly
start the Real Analysis launcher, review the selected video/window/camera plan
and estimate, then personally approve Analyze. No paid work starts on upload,
restoration or startup. Readiness means configuration presence, not account credit.
Estimates are not provider-enforced billing guarantees. Local budget limits,
origin protection, single-use approval and zero paid retries remain required.

## Deployment boundary and recovery

This is an **unauthenticated localhost API**, not a production public service.
Keep FastAPI and Vite on `127.0.0.1`. Do not expose them through port forwarding,
public tunnels or a publicly bound host. Origin checks are not user authentication.

- Missing/corrupt saved results: use the visible error and return to a bundled
  replay; never silently rerun inference. Keep the original files for diagnosis.
- Unavailable local history: check backend status, then Refresh investigations.
- Video decoding error: restore the tracked asset, or use an H.264 MP4 upload.
  A visible media error must not be interpreted as an empty physical scene.
- Outside the SAM window: original footage may be visible, but no detections
  are invented. The single wrapping notice is outside the footage.
- Optional Rerun: return to the normal investigation if loading fails. It is
  not needed for the six replays or for inspecting evidence.

## Release checklist

- [ ] Review the exact local candidate diff and commit; preserve public history.
- [ ] Verify source inventory/replay hashes, licenses, attribution and build-history disclosure.
- [ ] Exclude credentials, jobs/recordings, ledgers, QA receipts and personal environments.
- [ ] Review focused regression results; retain the accepted baseline evidence.
- [ ] Keep scientific limits and dev-dependency advisory disclosure visible.
- [ ] Obtain explicit owner approval before push/PR, merge, tag or publication.
- [ ] At publication time recheck remote main/CI/mergeability; no force-push or private history import.
- [ ] Smoke-test the published README and six replay asset links after authorized publication.

## Remaining limitations

Physical pickup, release, orientation, mechanical closure and complete task
success often remain unverified. There is no new action detector in this release.
Original citations and source/camera/crop quarantine remain mandatory.

Five P2 items remain deferred: incomplete URL inspector context, adjacent content
not inert while resizing, playhead left-position updates, inconsistent translation
exclusion on technical tokens, and no durable unpaid-preparation idempotency key.
The sixth item, eager hidden temporal previews, is corrected: previews initialize
only when Technical Details is open. None grants permission for duplicate paid calls.

Development-only Vitest/mocker/tinypool advisories remain disclosed; keep tooling
local. Production-only npm audit was zero at acceptance. A separate tested tooling
upgrade is preferable to an unverified dependency change during release freeze.

Chromium desktop/narrow keyboard and reflow checks are available. Real screen-reader
speech, actual browser-menu 125%/200% zoom, Safari/Firefox/Edge, physical mobile/IME,
and full optional Rerun GPU/accessibility behavior are not certified. A resized
viewport does not count as native browser zoom. See the local release-preparation
report for the exact tests executed; no full accessibility-conformance claim is made.
