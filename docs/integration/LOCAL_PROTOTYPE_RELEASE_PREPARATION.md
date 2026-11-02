# Local-prototype release preparation

November 2, 2026. **GO for owner review of this focused follow-up. Publication
remains unapproved.** Parent: `d9b9bb4ffff86349c23f8fba688516f7e22bfd21`.
Prepared on local branch `fix/local-prototype-release`, in an isolated clone of
the public repository's history. The existing development and public-release
workspaces are unchanged. No benchmark files, independent expectations,
scientific records or video-production files were edited.

## Priorities and reproduced corrections

| Finding | Before | After and evidence |
| --- | --- | --- |
| Narrow navigation keyboard access | Tab from the home link jumps back to Reset navigation width. The drawer's focus list omitted anchors. | Include enabled visible links/selects/textareas in the existing trap. Native Tab reaches Overview; only the true last control wraps. Escape returns focus. |
| Ambiguous saved execution | Mock camera fixtures show only Uploaded footage; dry_run=false alone is insufficient to prove real inference. | Read-only backend execution descriptions distinguish dry/cache, completed local SAM/Muse records, explicit provider-skipped/experimental, and missing legacy metadata. Inspector, header and history show the distinction. |
| Narrow SAM warning | Duplicate DOM/badge/canvas warnings overlap the video; legacy CSS also shrinks the text. | One wrapping DOM notice outside the footage, at least 12px. Canvas still draws no unsupported detections outside the window. |
| Hidden temporal-preview resource use | Returning to Findings initializes four EP005 video decoders with Technical Details closed. | Zero hidden decoder creations; four previews initialize only on expansion. Closing releases them. Original frame references and source seeking remain unchanged. |

Execution descriptions are computed on read and do not rewrite jobs. A real label
requires recorded completed SAM operations for every camera and an explicit paid,
non-dry Muse Spark Open record. It describes **local records**, not provider
authentication, billing proof, correct masks, or verified physical events. Missing
historical metadata stays unconfirmed rather than being rejected or called real.
Supplied numeric/source/crop/citation quarantine checks still precede result use.

Dry Run remains the default. Nothing restores approval tokens, enables providers
or automatically starts inference. Two-/three-camera integration is explicitly
experimental/mock-tested. Unverified hypotheses remain in their existing category;
no new detector or change to criterion states/outcomes is included.

## Six previously deferred P2 issues

| Priority for first visit | Issue | Disposition |
| --- | --- | --- |
| Highest | Hidden temporal previews compete with visible playback | Reproduced and corrected above. |
| Medium | Unpaid preparations have no durable idempotency key | Deferred; local duplicate preparations are possible, while paid approval/locking safeguards remain. |
| Medium | Adjacent content not inert during divider dragging | Deferred; keyboard resizing and normal pointer resizing work. |
| Lower | Inspector/search/tab context incomplete in URLs | Deferred; navigation, bound playback restoration and source links work. |
| Lower | Playhead uses left positioning | Deferred; no user-visible playback regression reproduced. |
| Lower | Inconsistent translate=no on technical tokens | Deferred; preserve original records; machine translation is not certified. |

## Executed tests and reused evidence

The previous full acceptance is retained, **not repeated**: fresh locked pip/npm
installation, 533 Python passes/45 optional research-fixture skips, 259 React
passes, independent integrity suites and full workstation/upload acceptance.
Requirements and lockfiles are unchanged. Existing fresh isolated dependencies
were reused for the checks below; a second dependency installation is not claimed.

| Focused final check | Result |
| --- | --- |
| Saved jobs, execution descriptions, provenance, API security, live workflow, multi-camera, temporal backend regressions | **186 passed**, no skips; one benign pre-import anyio pytest rewrite warning |
| React regressions including added mode/focus/preview/notice checks | **267 passed** |
| TypeScript check and production build | **Passed** |
| Actual production Chromium first-user flow | **38 checks passed** |
| On-demand preview browser probe | **Passed**: hidden creations 4 to 0, four previews on expansion, original F1607 seek 53.566666s |
| Documented manual production startup | **Passed** on 8767/4173: all six videos decode; genuinely empty new-user history; no credentials; real mode disabled |
| Manual shutdown | **Passed**: Ctrl+C in the task-owned terminals; Uvicorn reports complete application shutdown |
| README status/stop in fresh Windows PowerShell 5.1 | **Passed safe status/refusal/ownership behavior**; existing normal ports remain occupied by unmanaged services |
| New standard-port launcher cold start | **Not repeated / environment-blocked**; no unrelated services stopped. Use documented alternate ports or free only owned services. |

Browser checks cover 1920x1080, 1440x900, 1366x768, 390x844, 768x1024 and
effective 1152x720/960x540 reflow. They include keyboard drawer navigation and
focus return, tabs, explicit source-zero seeking/refresh, untimed E2, playback and
frame stepping, visible decoding errors and recovery, corrupted-citation
quarantine/recovery, invalid upload and provider-skipped completion, history
503/recovery, and saved real versus mock two/three-camera mode labels.

The original private DROID job was tested only through an isolated copy. Its
outcome remains Uncertain and all three actions Unverified. No private recording
or QA screenshot is distributed with this follow-up.

During development, two test failures were a stale old Dry Run copy assertion
and an incorrect path in the new notice test; these were corrected, not hidden.
One browser rerun initially lacked an out-of-window warning because a previous
intentional source seek was correctly restored. The helper now supplies an
explicit one-second precondition; no app restoration rule was weakened.
Independent benchmark tests/reference labels were not changed or rerun as a
substitute for these actual-browser checks.

Local receipts are kept outside this repository in the maintainer's ignored
`qa-browser-artifacts/local-release-preparation` directory: `python.xml`,
`react.json`, `browser-results.json`, `preview-results.json`, `readme-smoke.json`,
before/after screenshots, and security/file-integrity receipts. The exact changed
file list is the diff from the parent; source inventory is updated for this tree.

## Installation, locality and remaining risks

The README now contains an exploration sequence, mode explanations, owned-service
shutdown, port-conflict guidance and a process-only PowerShell script exception.
[LOCAL_PROTOTYPE.md](../submission/LOCAL_PROTOTYPE.md) supplies the short user
guide, recovery instructions and publication checklist. No global profile,
Python setting, execution policy or dependency installation was changed here.

The API is **unauthenticated and localhost-only**, not production Internet-ready.
Origin restrictions do not replace authentication. Do not bind publicly,
port-forward or expose it through tunnels. Development tooling advisories remain
disclosed from acceptance; no dependency update was attempted. Production npm
audit was zero at acceptance, not a guarantee against undisclosed vulnerabilities.

Native Windows computer-use initialization failed with a kernel-asset path error.
Consequently **actual browser-menu 125%/200% zoom and screen-reader speech were
not tested**. Effective viewport reflow is not a substitute for browser zoom.
Only automated Chromium was tested; branded Chrome/Edge, Firefox, Safari,
physical mobile/hybrid/IME and full optional Rerun GPU/accessibility behavior
remain untested. No full accessibility-conformance or new physical-action
recognition claim is made. Historical unattributed Bad Request remains
unattributed; no claim of root cause or repair is introduced.

No new release blocker was reproduced. Before publication: review this small
diff, approve the candidate, recheck current public main/CI and authorize the
push/PR separately. No push, merge, tag, deployment or submission occurred.

## Exact changed files relative to accepted parent

```text
README.md
docs/integration/LOCAL_PROTOTYPE_RELEASE_PREPARATION.md
docs/submission/LOCAL_PROTOTYPE.md
docs/submission/SNAPSHOT.md
docs/submission/SOURCE_MANIFEST.json
live_api.py
saved_jobs.py
tests/test_execution_presentation.py
web/src/App.regression-1.test.tsx
web/src/components/AnnotatedVideoOverlay.tsx
web/src/components/CameraInputs.tsx
web/src/components/DiagnosticDetails.tsx
web/src/components/InvestigationDesk.tsx
web/src/components/LocalPrototypeUsability.test.tsx
web/src/components/RecentInvestigations.test.tsx
web/src/components/RecentInvestigations.tsx
web/src/components/TemporalContext.test.tsx
web/src/components/TemporalContext.tsx
web/src/components/VideoPane.tsx
web/src/lib/investigationMode.test.ts
web/src/lib/investigationMode.ts
web/src/lib/types.ts
web/src/workstation.css
```
