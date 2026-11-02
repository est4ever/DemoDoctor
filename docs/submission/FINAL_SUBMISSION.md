# Final submission packet

Initially prepared October 31, 2026 from `736e4e1`; updated November 1
with owner-authorized validated changes through `097f8e1`.
Documentation only; no publication or submission has occurred.

## Project title

**DemoDoctor: Evidence-Grounded Robot Failure Analysis**

Track: **Indie Developer**, subject to accepted registration and organizer
confirmation of the pre-event foundation. Theme: **Push the Frontier**.

## Short description

DemoDoctor connects robot footage to inspectable physical evidence. Meta SAM 3.1
supplies object observations; independent checks ground Muse Spark Open's cited
explanations. A synchronized video, timeline and evidence inspector help builders
separate measurements, inferred events and unknown outcomes. Six replayable
demonstrations work without API credentials.

## Project description

Robot demonstrations can look successful while hiding a failed release, missing
measurement or unobserved interval. DemoDoctor helps robotics builders investigate
what the available evidence supports before trusting a fluent explanation.

It reconstructs evidence from Meta SAM 3.1 masks and boxes, combining paired robot
joint measurements when available. Deterministic rules and independent claim
checks separate observed geometry, measured gripper opening, inferred events and
unverified outcomes. Muse Spark Open, accessed through Fireworks, produces cited
explanations from a bounded evidence package. The React workstation synchronizes
recorded video, SAM overlays, event timing and inspectable source details. Its
panels resize/collapse independently; Rerun is an optional recorded viewer.

The deliverable includes six credential-free recorded investigations and a safe
Windows launcher. Replays use saved real analysis; opening them makes no new
provider calls. Uploads default to a dry run that skips SAM/Muse. The owner can
explicitly enable local Real Analysis, configure providers and approve each video
and cost estimate to use the existing inference pipeline. This update validates
that workflow with synthetic providers, not a new paid generalization experiment.
Saved diagnostic hypotheses are exposed as Unverified with original citations.
EP005 remains uncertain; physical orientation is not independently verified. The FastAPI backend is a local workstation service,
not an authenticated public multi-user deployment.

## Architecture and Meta-model contribution

`video → SAM 3.1 observations + optional paired joints → physical-event rules →
independent verification → bounded evidence package → Muse Spark Open explanation
→ recorded artifacts → React video/timeline/source inspector`

SAM provides visual evidence rather than a task verdict. Muse supplies grounded
language rather than measurements. DemoDoctor contributes evidence reconstruction,
verification, provenance handling and an inspection workflow around those models;
it does not claim to create/train Meta's models or the source datasets.

The video-only PILOT has a special historical boundary: its original Muse response
was generated from its original evidence package. Later offline endpoint/coverage
checks were **not** sent back to Muse. Original citation IDs stay bound to the
original package; the diagram must not imply Muse evaluated the later checks.

## Demonstrated results and limitations

- **PILOT:** two independently checked image-space claims. Recorded box centers
  are approximately **609 pixels apart (609.01 px)**. Coverage is 632/737 frames,
  with **105 unobserved frames, 433–537 inclusive**. This is not continuous tracking
  or confirmed physical travel across the gap. Destination segmentation returned
  **no usable tray mask**, not evidence that the tray was physically absent.
  No measured gripper opening or robot joints are available here. Object identity,
  release, placement and final task outcome remain qualified/unverified; task
  verdict is uncertain.
- **EP010:** paired measured gripper opening supports an inferred release event
  at 44.50 seconds. Opening is measured; actual release is inferred. Holding,
  intent and successful placement are not thereby established.
- **EP003:** saved 2D containment criterion met; upright plate orientation remains
  unverified. Do not describe this as complete physical-task verification.
- **EP013 / EP006:** recorded end-state-supported failure / evidence abstention.
- **EP005:** illustrative comparison, not a controlled scientific ablation.
  The tiny held-out workflow comparison has differing prompts/schemas and
  abstention coverage; no broad accuracy or statistical-superiority claim.

See RESULTS.md for the frozen comparison numbers and EVIDENCE.md for source
bindings. No new inference is needed to inspect any bundled demonstration.

## Hackathon-era contribution disclosure (paste with submission)

DemoDoctor builds on a pre-existing October 24, 2026 foundation: the project
framing, Streamlit application, Muse baseline/client, evaluation and data utilities,
and an initial tracking scaffold. We do not claim that the whole project was
created from scratch during the hackathon. Git history records substantial
October 26–31 additions: working SAM 3.1 integration; physical evidence
reconstruction and independent verification; evidence-grounded Muse workflows;
the React/Rerun workstation; upload/dry-run infrastructure; real-pilot checks;
six attributed replay packages; Windows launcher; source-inspection and precise
playback fixes; security/correctness/recovery repairs; and adjustable viewport
panels. These extend the earlier foundation. The final video uses genuine recorded
project artifacts. No November 1–4 implementation is claimed in advance. Models,
datasets and external software are credited separately. BUILD_HISTORY.md provides
commit timestamps; those records are not independent proof of authorship time.

## Real-world impact

DemoDoctor aims to reduce time spent debugging robot demonstrations and make
unsupported success/failure narratives easier to challenge. Inspectable unknowns
help builders decide what to reobserve or measure next. This is a research
prototype and local investigation tool, not a validated autonomous robot safety
system, general causal diagnosis engine or large-scale performance result.

## Frozen three-minute video

Title suggestion: **DemoDoctor — Evidence-Grounded Robot Failure Analysis**.
Exactly **180 seconds**, 1920×1080, 30 fps, H.264/AAC; existing 10-second intro,
genuine application recordings, English narration, music and readable captions.
The user reports the participant guide requires three minutes; its actual guide
URL/text is still needed for independent verification. Do not regenerate.

File: `qa-browser-artifacts/final-video-release/DemoDoctor-Final-3min-1080p.mp4`.
SHA256: `7c921aa387c3921f8220ad5a4ea4e63b3d80af79cf7b24d0662d5a4b37a86efd`.
Hosting/upload has not been approved or performed. Match host visibility/access
to the accepted guide; verify the final URL logged out before submission.
Use full dataset/model/audio credits in the published description, retaining
THIRD_PARTY.md and supplied ElevenLabs Hope / DemoDoctor Resolve permissions.

## Links and manual fields

| Item | Prepared value or remaining action |
|---|---|
| Official deadline | November 4, 2026, 9 PM Eastern (November 5, 02:00 UTC) |
| Submission portal | https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit |
| GitHub URL | https://github.com/est4ever/DemoDoctor — public initial release exists; incremental update pending owner approval |
| Public source revision | Initial published root 26a8a9f; record the approved incremental update SHA after publication |
| Video URL | Pending rights/host approval and upload; no URL invented |
| Live app URL | None; primary deliverable is source and local offline replay |
| Track / theme | Indie Developer / Push the Frontier, subject to eligibility confirmation |
| Team representative and teammates | Owner must supply actual accepted registration details; waiver requires listing team members |
| Required final-form fields/limits | Cannot verify behind portal sign-in; owner must open accepted form |
| Declarations/consents | Owner must review actual rules, asset permissions and final declarations |

Public GitHub and an accessible video link are the planned delivery targets.
Their precise mandatory visibility/host rules, field limits and any live-demo
requirement must be checked against the participant guide/form; they are not
inferred from the application page. Do not invent thumbnail, word-count, privacy,
AI-disclosure, contact or category requirements merely because other hackathons
use them. Prepare those items only if the actual form asks.

## Eligibility question requiring organizer confirmation

The public waiver permits compliant open-source components and describes Indie
teams of up to four, but does not resolve use of this owner's pre-event project
foundation against any additional Indie-track new-work rule in the participant
guide. Original ownership and Apache licensing do not establish contest eligibility.
Ask organizers, without hiding or rewriting history:

> Our Indie-track project has a disclosed October 24 prototype (commit 1a97715:
> Streamlit app, Muse baseline, evaluation/data utilities and tracking scaffold).
> Substantial SAM integration, reconstruction/verification, React inspection,
> recorded pilots and reliability work were committed October 26–31, documented
> in BUILD_HISTORY.md. Is this eligible in Indie Developer, and how should we
> identify the pre-existing foundation in the submission? If not, is a track
> change allowed under our accepted registration?

This question is prepared only; no message was sent. Do not select a different
track or assert eligibility automatically. Retain the organizer's written answer
with the submission record. Final submit approval remains separate.
