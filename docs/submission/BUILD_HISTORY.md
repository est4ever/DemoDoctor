# Hackathon build-history disclosure

This separate public snapshot imports no private Git history. Commit IDs and
timestamps below are documentary references to the original development records,
not commits reachable in this new repository. A new initial commit does not
establish that the October 24 foundation was built during the event.

Initial public-release functional freeze: **736e4e1fdbf1c4d90414047d5226c7c37ef66829**.
Subsequent owner-authorized changes are documented below through
**097f8e1e6509b512886fc8eebe564007758bb759**.
Audit cutoff: **November 1, 2026**. Advertised event window: October 26–November 4.
No future November 2–4 work is claimed at this cutoff.

## Pre-existing foundation

**1a97715 — October 24, 2026** predates the hackathon. It introduced 15 files
(2,983 inserted lines): the Streamlit application, Muse baseline/client,
diagnosis/evaluation and dataset-selection code, initial labels, sample/import
utilities, and the tracking scaffold. The project name, problem framing and this
foundation must be disclosed as pre-existing, not work created during the event.

## Substantial changes committed during the event

| Area | Evidence in integrated history | Scope and limits |
|---|---|---|
| Working SAM 3.1 integration | f06d9ac, Oct 26 | Builds on the earlier tracking scaffold; not a claim that all tracking code was newly written |
| Physical-event evidence and independent verification | e7b460e, 2842f82, 6216a60, Oct 26–27 | Measurements, inferred events and claim checks, not new robot hardware or a controller |
| Evidence-grounded Muse and frozen comparisons | 7c4ca0a, 84866ae through c60e070, Oct 27 | Bounded packages, automatic windows/final-state checks and small held-out workflow evaluation |
| Offline React workstation and optional viewer | a037418, 44a46e7, 5597a9b, 398f860, Oct 29–30 | Camera/timeline/evidence investigation UI; optional Rerun and unvalidated legacy 3D mapping kept separate |
| Upload workflow and bounded inference infrastructure | 99cc849, 8ea6984, Oct 30 | Submission UI uses dry run, providers skipped; backend capabilities are distinct |
| Real-pilot recorded evidence | 80657a5, 7d307b0, Oct 30 | 609.01 px endpoint/coverage checks, explicit 105-frame gap, missing tray mask; original Muse is not rerun on reconstructed evidence |
| Credential-free public replay package | 05d64b7, Oct 31 | Six attributed compact replays, portable setup, dependency snapshot and distribution checks |
| First release audit and documentation | f3ca4b5, Oct 31 | Documentation and ignore rules at that checkpoint |
| Viewport-fitted investigation workspace | bdfe0c3, Oct 31 | Video, playback, timeline and selected evidence visible together; scientific results unchanged |
| One-command Windows launcher | 0ee4cdb, Oct 31 | PowerShell 5.1 startup/status/stop, safe ownership, offline guard and recovery checks; no new models |
| Source inspector and exact paused-frame seeking | 9e310a5, 8049b92, Oct 31 | Visible provenance for timed/untimed evidence and corrected paused-frame synchronization; saved results unchanged |
| API security and independent evidence correctness | 7a4f5f2, 9418627, Oct 31 | Artifact/request boundaries, explicit local-input permissions and stricter new validation; frozen outputs retained |
| Navigation, job recovery and viewer error visibility | af06807, Oct 31 | History recovery, current-tab job recovery and visible optional Rerun errors |
| Adjustable viewport panels | 736e4e1, Oct 31 | Independently collapsible/resizable panels, local preferences, accessible controls and narrow-screen drawer |
| Self-service local Real Analysis | f60965f, Nov 1 | Existing pipeline connected to prepare/approve/results UI; explicit startup opt-in, ledger checks and zero paid retries; new mocked-provider tests, not a new paid pilot |
| Saved diagnostic hypotheses and criterion coverage | 097f8e1, Nov 1 | Existing Muse suggestions restored as Unverified with original citations; EP005 outcome unchanged; no new orientation detector |
| Approved Apache notices and audit records | 171ecf9, 94e060c, 5582886, Oct 31 | License/docs and confirmed repair evidence; not additional model/scientific results |

The final three-minute video was assembled locally after the original replay
checkpoint and before the later viewport/launcher improvements; production files
remain ignored. The owner approved keeping this video unchanged at functional
freeze. The earlier `0ee4cdb` freeze was followed by owner-authorized inspection,
security, correctness, recovery and panel work listed above. The final freeze is
recorded for the first release at `736e4e1`. The owner subsequently authorized
the November 1 workflow and presentation changes above. They change application
behavior but do not modify frozen scientific results or the final video. The video combines authentic project
assets, supplied ElevenLabs Hope narration and DemoDoctor Resolve. No generated
robot actions, missing observations or new inference calls were added in editing.

## Recorded integrated ancestry

This table uses all 39 commits reachable from the final frozen integrated application checkpoint,
not duplicate UI commits on other branches or stash/index commits. Merge commits
are listed for provenance, not counted as independent feature implementations.

| Commit | Author timestamp | Committer timestamp | Subject |
|---|---|---|---|
| `1a97715` | 2026-10-24T20:14:28-04:00 | 2026-10-24T20:14:28-04:00 | Initial DemoDoctor: Muse baseline, eval set, SAM tracking scaffold |
| `f06d9ac` | 2026-10-26T21:05:19-04:00 | 2026-10-26T21:05:19-04:00 | Add working SAM 3.1 object tracking |
| `e7b460e` | 2026-10-26T23:46:20-04:00 | 2026-10-26T23:46:20-04:00 | Reconstruct and verify physical events from SAM tracks and SO-101 joint data |
| `2842f82` | 2026-10-27T00:38:21-04:00 | 2026-10-27T00:38:21-04:00 | Add failure-localization engine, BotFails ep010 experiment, annotations and handoff |
| `6216a60` | 2026-10-27T01:02:52-04:00 | 2026-10-27T01:02:52-04:00 | Add relative-rise gripper opening detector and ep010 v2 experiment. |
| `7c4ca0a` | 2026-10-27T02:37:05-04:00 | 2026-10-27T02:37:05-04:00 | Ship evidence-grounded Muse fusion, held-out eval, and offline DemoDoctor Analysis. |
| `3e501a7` | 2026-10-27T20:37:08-04:00 | 2026-10-27T20:37:08-04:00 | docs: portable README setup path and public-release path strategy |
| `84866ae` | 2026-10-27T21:08:22-04:00 | 2026-10-27T21:08:22-04:00 | Add automatic window proposals and conservative dish-rack final-state checks. |
| `0ffec23` | 2026-10-27T21:20:06-04:00 | 2026-10-27T21:20:06-04:00 | Freeze window/final-state params after offline real-data validation and prepare expanded BotFails eval. |
| `397c6b5` | 2026-10-27T21:47:36-04:00 | 2026-10-27T21:47:36-04:00 | Add efficient window profile, verify expanded eval episodes, and dry-run pilots. |
| `92e6e3c` | 2026-10-27T22:28:58-04:00 | 2026-10-27T22:28:58-04:00 | Freeze inference pipeline with near-rack final-state fallback and top-K windows. |
| `5c516c0` | 2026-10-27T22:54:59-04:00 | 2026-10-27T22:54:59-04:00 | Checkpoint held-out SAM evaluation and prepare Muse Spark dry-run pairs. |
| `c60e070` | 2026-10-27T23:22:52-04:00 | 2026-10-27T23:22:52-04:00 | Record eight Muse Spark held-out comparison runs and evaluation report. |
| `21859dd` | 2026-10-27T23:31:39-04:00 | 2026-10-27T23:31:39-04:00 | Prepare final hackathon submission: extend Analysis demos and docs. |
| `ab57775` | 2026-10-27T23:40:20-04:00 | 2026-10-27T23:40:20-04:00 | Merge pull request #1 from est4ever/feat/event-reconstruction |
| `7fc46c5` | 2026-10-27T23:40:35-04:00 | 2026-10-27T23:40:35-04:00 | Merge branch 'main' of https://github.com/est4ever/DemoDoctor into feat/auto-windows-finalstate |
| `21c371d` | 2026-10-27T23:46:43-04:00 | 2026-10-27T23:46:43-04:00 | Merge pull request #2 from est4ever/feat/auto-windows-finalstate |
| `a037418` | 2026-10-29T21:05:00-04:00 | 2026-10-29T21:05:00-04:00 | Add offline React DemoDoctor replay for frozen BotFails episodes. |
| `44a46e7` | 2026-10-29T22:22:46-04:00 | 2026-10-29T22:22:46-04:00 | Fix SO-100 wrist joint mapping in 3D replay. |
| `5597a9b` | 2026-10-30T01:48:54-04:00 | 2026-10-30T01:48:54-04:00 | Add lazy Advanced Robotics Viewer for optional ep010 Rerun. |
| `f3ce6c6` | 2026-10-30T02:43:35-04:00 | 2026-10-30T02:43:35-04:00 | docs: prepare Codex engineering handoff |
| `99cc849` | 2026-10-30T21:59:08-04:00 | 2026-10-30T21:59:08-04:00 | Checkpoint browser-tested upload workflow and optional Rerun viewer |
| `8ea6984` | 2026-10-30T22:16:10-04:00 | 2026-10-30T22:16:10-04:00 | Checkpoint bounded real-inference workflow and evidence safety |
| `80657a5` | 2026-10-30T22:58:27-04:00 | 2026-10-30T22:58:27-04:00 | Verify video-only endpoint evidence and preserve observation gaps |
| `398f860` | 2026-10-30T23:21:10-04:00 | 2026-10-30T23:26:50-04:00 | feat(ui): build robotics investigation workstation |
| `7d307b0` | 2026-10-30T23:42:22-04:00 | 2026-10-30T23:42:22-04:00 | Integrate recorded pilot evidence into React workstation |
| `05d64b7` | 2026-10-31T00:03:32-04:00 | 2026-10-31T00:03:32-04:00 | Prepare reproducible credential-free hackathon submission |
| `f3ca4b5` | 2026-10-31T16:50:21-04:00 | 2026-10-31T16:50:21-04:00 | Audit public-release readiness and document hackathon provenance |
| `bdfe0c3` | 2026-10-31T17:15:28-04:00 | 2026-10-31T17:15:28-04:00 | Fit investigation workspace to desktop viewport |
| `0ee4cdb` | 2026-10-31T18:08:59-04:00 | 2026-10-31T18:08:59-04:00 | Add verified one-command Windows launcher |
| `171ecf9` | 2026-10-31T18:45:52-04:00 | 2026-10-31T18:45:52-04:00 | Prepare Apache-2.0 public hackathon release |
| `9e310a5` | 2026-10-31T19:06:46-04:00 | 2026-10-31T19:06:46-04:00 | Open evidence sources and preserve untimed inspection |
| `8049b92` | 2026-10-31T19:22:16-04:00 | 2026-10-31T19:22:16-04:00 | fix(qa): AUD-001 synchronize paused camera frame seeks |
| `94e060c` | 2026-10-31T19:26:27-04:00 | 2026-10-31T19:26:27-04:00 | docs: record independent project bug audit and remaining risks |
| `7a4f5f2` | 2026-10-31T20:01:18-04:00 | 2026-10-31T20:01:18-04:00 | fix(qa): restrict local API requests and artifact access |
| `9418627` | 2026-10-31T20:02:52-04:00 | 2026-10-31T20:02:52-04:00 | fix(qa): enforce evidence identity and independent claim support |
| `af06807` | 2026-10-31T20:02:52-04:00 | 2026-10-31T20:02:52-04:00 | fix(qa): recover investigation routes and jobs and surface viewer failures |
| `5582886` | 2026-10-31T20:04:00-04:00 | 2026-10-31T20:04:00-04:00 | docs: record focused repair verification and remaining release decisions |
| `736e4e1` | 2026-10-31T20:34:43-04:00 | 2026-10-31T20:34:43-04:00 | feat(ui): add persistent collapsible and resizable workstation panels |
| `f60965f` | 2026-11-01T00:37:12-04:00 | 2026-11-01T00:37:12-04:00 | feat: enable explicit local real analysis from Import Footage |
| `097f8e1` | 2026-11-01T01:19:09-04:00 | 2026-11-01T01:19:09-04:00 | Restore saved diagnostic hypotheses and criterion coverage |

Git timestamps and messages document repository history, not independent proof
of when every line was authored. The owner must disclose any other earlier or
external work known to them and confirm eligibility under the accepted rules.
Dataset creation, Meta models, public robot assets and dependencies are
third-party/pre-existing work, never hackathon-created contributions.
