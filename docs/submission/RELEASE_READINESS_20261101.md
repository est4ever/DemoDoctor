# Frozen release-readiness report — November 1, 2026

**Local review candidate only. No push, merge, deployment or submission.**

Integrated application freeze: `de5009f26818d6d8a6cc0b15ba87fd89004095b6` (clean). This public candidate descends
from `c1cebf3f353eb62422cabacce3922bda1b166609` and preserves public commits 26a8a9f, 35b0050 and c1cebf3. Source
files were transferred without private Git history. The October 24 foundation
and later contributions remain disclosed in BUILD_HISTORY.md. Exact paths are
listed in RELEASE_CHANGES_20261101.txt.

## Final product scope

- One UI workflow for ordinary single-camera footage, confirmed 1/2/3-panel
  composites and separately aligned 2/3-camera recordings. Cameras keep independent
  native times, crops, hashes, observations, masks, track namespaces and citations.
- Self-service Real Analysis uses the existing SAM 3.1/Muse pipeline, backend-only
  credentials, immutable quotes, explicit cost approval, budget reservations,
  origin/Host/path restrictions, zero paid retries and stop-on-provider-failure.
  Ordinary startup stays offline and Dry Run remains the default.
- Explicit task subgoals use Supported/Contradicted/Unverified/Not assessed with
  scoped sources and resolving observations. Criteria open by default in Findings;
  technical evidence remains expandable. No orientation, 3D or new inference model.
- Saved original hypotheses and interpretations remain Unverified. The temporal
  context panel displays up to six actual original frames, sorted chronologically,
  with native time/camera provenance. Saved Muse input references are distinguished
  from local context. Missing SAM detections are not invented or interpolated.
- Camera-labelled Muse interpretation links now select the cited camera through
  the existing validated frame handler. This was reproduced in a regression before
  the presentation fix and verified with synthetic camera-labelled Muse output.
- Recent Investigations reopens completed saved jobs offline without new upload
  or inference. Missing/incomplete artifacts are reported, not silently rerun.
- The secure Windows launcher, source inspection, viewport fitting, adjustable
  panels and optional Rerun navigation remain intact.

## Real-provider evidence versus mocked validation

Real retained results include the original SO-101 pilot and an owner-initiated
private one-view DROID SAM/Muse UI run. The DROID saved analysis has 97 returned
detections; its two hypotheses match the saved validated Muse response. Its
Uncertain verdict and pickup/place/close subgoals remain Unverified. The existing
privately reviewed near-end drawer appearance is labelled visually consistent
with closed, not verified mechanical closure. It is a separate, hash/frame-bound
local analyst note, never added to original provider outputs or criterion facts.
Private notes/jobs/media are excluded from this public repository.

The public 1/2/3-camera upload/approval/results regressions use synthetic providers.
They are not genuine multi-camera provider validation or accuracy evidence. Shared
timing cannot establish physical object identity, calibrated geometry, grasp,
release, orientation or full task completion. Context previews cannot prove that
Muse received unlisted frames or interpreted listed inputs correctly. No new paid
provider call was made in this release work.

## Executed acceptance checks retained across the PC restart

| Check | Actual result |
|---|---|
| Complete integrated Python suite | 448 passed |
| Full public Python suite | 403 passed, 45 skipped |
| Fresh Python 3.12 environment from unchanged lockfile | Install + pip check passed; 403 passed, 45 skipped |
| Integrated, public and clean-export frontend tests | 131 passed, 24 files |
| Fresh npm ci --offline | Passed; 227 packages installed from unchanged lockfile |
| TypeScript + production build | Passed, including clean export |
| All six bundled investigations in actual Chromium | Videos, criteria, sources, hypotheses, overlays and Unknowns passed |
| All expected temporal thumbnails | Decoded; native source seeking checked in every episode |
| Private DROID after restart | Offline reopen, six decoded frames, original citations, three Unverified subgoals and qualified local review passed |
| One-camera and confirmed composite 1/2/3-view mock workflows | Explicit quote approval, completion and reload passed |
| Separate aligned 2/3-camera mock files | Completion, independent source data and reload passed |
| Camera-two Muse interpretation with camera one selected | Correct cited camera selected; remains Unverified |
| Provider failure | One synthetic SAM attempt; no retry, Muse follow-on or fabricated result |
| Spending protection | Zero provider operations before UI approval; existing budget/admission regression tests passed |
| Saved three-camera investigation reopened offline | Passed; no additional synthetic provider calls |
| EP010 measured gripper and untimed PILOT source | Correct 44.50s seek; untimed source does not seek |
| Desktop viewport sizes | Video, timeline and selected evidence fit at 1366x768, 1440x900, 1920x1080 |
| Optional Rerun | Return to investigation passed; full graphics-session retest not claimed |

These successful runs were not needlessly repeated after restart: their source
checkpoint, test receipts and artifacts were checked. The post-restart checks
re-exercised local startup/reuse, DROID reopening/frame previews and targeted
security requests. No application code changed after the freeze.

The 45 skips are not passes: 40 require excluded original full-video/joint/cache
fixtures; four reproduce raw tracking coverage using optional original SAM caches;
one cross-checks an optional original reference audit. Full-data checks remain
enabled and passed in development. Core/synthetic source-entailment, reference
separation, camera, budget, failure and history tests run in the public tree.
No private inputs were copied merely to obtain a passing public suite. The
retrospective coverage CLI intentionally explains its missing optional inputs.

## Reported generic Bad Request — bounded investigation

The owner reported a command exit 1 with `{"detail":"Bad Request"}`. That exact
original command, request and response were **not found** in retained release
logs or the associated DemoDoctor Codex tool records. Its origin cannot be
conclusively classified as application, test-driver or external-service error
without the missing original command/log. It is not falsely declared fixed.

The HTTP 400 records that were found are intentional security checks:

- `python qa-browser-artifacts/public-update-20261101/offline_api_check.py`
  sent GET `http://127.0.0.1:8795/api/health` with `Host: attacker.invalid`, no
  body or credentials. Expected 400; body `Invalid host header`.
- The earlier traversal test sent GET `/api/jobs/..%5Cneighbor/analysis`.
  Expected 400; body `{"detail":"Invalid job ID"}`.

Both were rerun against the frozen public code in an isolated TestClient with
provider dispatch forbidden. They matched the expected responses. Normal health
returned 200, hostile Origin returned 403, and an offline paid-start request was
rejected 403 before dispatch. The targeted test process exited 0. No case emitted
the owner's exact generic JSON. The original security script catches expected
HTTPError statuses; its successful rejection is not an application failure.

Post-restart actual DROID API and Chromium reopening also succeeded (HTTP 200).
No current failing application workflow or release-blocking defect is confirmed,
and no speculative application fix was applied. Attribution of the historic
generic error remains an explicit traceability limitation pending its original
command/log. Publication stays approval-gated; do not claim that incident resolved.

## Security, integrity and video

Exact exported-file scans found no credential candidates, private workstation
metadata, sensitive files, image EXIF or broken local Markdown links. Original
licenses/notices and sanitized scientific fixtures remain byte-identical. All 19
replay asset hashes match. All 33 original job/ledger hashes remain unchanged.
Runtime source matches the frozen integrated files modulo established newlines.
No private Git objects or personal review files are in this public snapshot.

Unchanged dependency inventories: npm production audit has zero findings; OSV
querybatch has zero affected packages among 64 Python pins. The development test
chain still has three disclosed package advisories: vitest and tinypool critical,
@vitest/mocker moderate. Their exploitability in this app is not established;
passing tests does not resolve advisories. No upgrade is hidden in the freeze.
Pattern/advisory checks cannot guarantee absence of every unknown vulnerability.

The final video retains SHA256
`7c921aa387c3921f8220ad5a4ea4e63b3d80af79cf7b24d0662d5a4b37a86efd` and its
validated 180-second duration. Existing final transcript and production validation
were reviewed, not regenerated. Measured gripper opening vs inferred release,
illustrative EP005 comparison, approximately 609-pixel endpoints, 105-frame gap,
missing usable tray mask, uncertain pilot and explicitly dry-run upload example
remain accurate. The film shows an earlier interface and original replay scope;
it does not demonstrate newer multi-camera, task-context, history or private
DROID capabilities. It is not a comprehensive walkthrough of the latest UI or
evidence of multi-camera/diagnostic accuracy. No fresh real-time listening review
is claimed. The MP4, audio, captions and scientific records were not changed.

## Decisions before publication

1. Owner review of this exact local commit/file inventory and the unattributed
   historic generic-error limitation; supply the original command/log if available.
2. Explicit decision on the unchanged development-tool advisories or a separately
   authorized dependency-only repair; no automatic repair/publication.
3. Organizer confirmation of Indie-track eligibility for the disclosed October 24
   foundation remains outside these technical tests. Video hosting/submission and
   audio permissions remain owner tasks; no host URL or entry is submitted here.

No confirmed current critical application defect was left unrepaired. Mechanical
closure, grasp/release, full placement, orientation, cross-view identity and broad
generalization remain scientifically unverified, not silently converted to facts.
Publish only after explicit owner approval, using PUBLICATION.md from this separate
repository. Preserve the private repository and its PR #3; never import its history.
