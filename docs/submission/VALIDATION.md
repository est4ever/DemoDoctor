# Executed public-snapshot validation

For the current incremental update, executed results and dependency findings, see
[UPDATE_20261101.md](UPDATE_20261101.md). The October 31 record below is historical.

Validated October 31, 2026 (Eastern), in the separate release directory. Source
checkpoint: 05b175db352ae306c8607e6e08f06036f330b55b. Original development worktrees,
private history, PR #3, application and final video were not modified. Only the
original shared remote URL was updated to its canonical private repository name.

## Executed checks

| Check | Observed result |
|---|---|
| Fresh Python 3.12 venv, system packages disabled | Created locally; locked dependency installation succeeded |
| pip check | No broken requirements |
| Full Python suite, after exclusions | **228 passed, 40 skipped**; final tracked-only run 5.97 seconds |
| Clean React dependency installation | npm ci succeeded; 227 packages installed |
| Frontend suite | **47 passed, 10 files** |
| Production TypeScript/Vite build | Passed |
| Provider configuration | No personal .env; provider keys removed; health reports SAM/Muse absent |
| Snapshot backend and production frontend | Started in isolation on loopback 8795/4173; offline provider guard enabled |
| Replay manifest | All 19 entries match their recorded SHA256; native dimensions, frame counts and rates checked by Python suite |
| gstack actual recorded videos | PILOT, EP010, EP005, EP003, EP013 and EP006 all decoded, not just rendered |
| Recorded SAM overlays | All five BotFails overlay MP4s decoded |
| PILOT E0-E5 source inspection | Source details opened; E0 calculation, E2 unavailable joints and E4 empty tray mask retained |
| Untimed PILOT inspection | E2/E4 selection preserved the current 24.533333-second frame; no invented seek |
| EP010 source/seek | Actual recorded gripper 10.6586 motor_deg at frame 1335 / 44.50 seconds |
| Playback and frame stepping | Playback advanced; one-frame step is 1/30 second |
| Timeline keyboard seeking | Native keyboard activation sought the measured event to 44.50 seconds |
| Optional Rerun | Actual retained recording reached viewer-ready; returned to camera investigation |
| Viewport fit | 1440x900, 1920x1080, 1366x768; footage/timeline visible without vertical page overflow |
| Resource origins in tested browser flow | Only the isolated localhost origin observed |
| Licensing | Both exact pinned dataset publisher revisions returned apache-2.0; root Apache text matches official text after newline normalization; separate notices retained |
| Security/file audit | No credential-pattern candidates, personal path/name matches, sensitive filenames, image EXIF or broken local Markdown links in the audited release source |

The 40 skips require deliberately undistributed original sample/full videos or
SAM caches. Skips are not passes; this is not full research reproduction. The
228+40 suite is the complete collected Python suite, unchanged from source.
No paid provider call, new model output or fabricated robot event was used.
Initial tooling attempts had a PowerShell warning-handling error and a Unicode
log-print error; those are not counted as successful checks. The subprocess
receipts above record actual test/build exit codes and runner summaries.

## Known existing limitation preserved by the development freeze

At 1440x900, the center of EP010's 44.50-second timeline marker overlaps the
neighboring rest marker: hit testing targets that neighbor, and gstack could not
click the measured marker directly. Native keyboard activation of the measured
marker and selection through E2 both seek correctly to 44.50 seconds. This is a
confirmed UI limitation, not a claim of complete mouse-target coverage. No UI
repair was made during snapshot preparation.

## Audit and portability limits

The file audit checks common token/private-key/credential-assignment/URL-userinfo
patterns and private workstation paths. It does not certify unknown encoded
secrets or every visual detail inside binary media. Image EXIF and binary bytes
were checked; current browser evidence captures were also visually inspected. Publisher license
metadata is not a warranty of upstream ownership or unrelated audio rights.
Original provider account permissions and Indie-track reuse eligibility remain
owner/organizer decisions. No authenticated public hosting audit is claimed.

Windows is tested. macOS/Linux, screen readers, exhaustive security/load testing
and fresh paid inference are not claimed. Dependency installation needs network
access or a prepared cache; replay afterward uses local files. The optional
Rerun dependency is large and subject to graphics support. Normal replay works
without it. A complete cold launcher/profile registration was not rerun here;
launcher code is unchanged and its Python offline regressions passed. Profile
registration was intentionally not executed, preserving the owner's current setup.

See SNAPSHOT.md, SNAPSHOT_PROVENANCE.json and SOURCE_MANIFEST.json for exact public
contents and metadata-only modifications. Local logs, screenshots, environments
and browser state are untracked and are not part of the source release. Public
GitHub creation, push, release, visibility changes, deployment, upload and final
submission have not been performed. Approval remains required.

## Exact staged-file checkout check

After staging the audited source, a separate checkout was materialized using
Git checkout-index with no inherited .git, .env, venv, installed frontend packages,
private data or research cache. All 19 manifest hashes matched. Its full Python
suite ran using the freshly installed isolated release venv (228 passed, 40 skipped).
A new npm ci, all 47 frontend tests and the production build also passed from that
tracked-only tree. Only the final validation notes/source inventory were added
afterward; application, test and replay files did not change.
