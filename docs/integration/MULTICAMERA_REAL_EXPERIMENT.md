# Proposed first real multi-camera experiment — approval required

**Status: prepared only. No real provider calls have been executed.**

This is one local validation experiment, not a generalization/accuracy claim or
authorization for repeated runs. Reconfirm the quote after any implementation
changes, including task-criterion integration. Do not start if the file, layout,
window, model plan or budget differs from the approved plan.

## Exact input

- Existing user-supplied DROID composite MP4; local saved source:
  `data/live_jobs/20261031T233708Z_5816831d/video.mp4`.
- Original SHA256:
  `eaec1033f19cf7fce385b0a120fa80edda4d78a9a171cb9462a0af5351961f53`.
- Native source: **3872×736**, **158 frames**, **15 FPS**; frame timestamps
  **0–10.466666667s**. Full file interval **[0, 158/15)** seconds.
- Count **3**, composite input. Upload the original MP4; no external cropping.
  The generic preview heuristic suggests these regions on this source. The
  operator must inspect and confirm them before extraction:

| Camera | Name | Crop x,y,width,height | Motion declaration |
|---|---|---|---|
| cam1 | External left | 8,8,1280,720 | Stationary, operator reviewed |
| cam2 | Wrist camera | 1296,8,1280,720 | Moving |
| cam3 | External right | 2584,8,1280,720 | Stationary, operator reviewed |

The three regions share original source PTS; offsets are **0s**. Derived files
retain all 158 frame indices and timestamps. FFmpeg H.264 spatial cropping is
lossy and disclosed; no interpolation or time stretching is used. Burned-in
axes/captions come from the source and are not DemoDoctor geometry estimates.

Task: **Pick up the blue block, put it in the open drawer, then close the drawer.**
Every view uses object prompt **blue block** and destination prompt **open drawer**.

Questions: **Is placement supported? Could orientation, incomplete drawer closure
or occlusion explain uncertainty? Do not treat visibility as verified grasp or release.**

The dataset collection label is not an independently established outcome for
this evaluation. Record your own reference observations separately, including
which frames support them. The system must be allowed to abstain.

## Approved request sequence to review

Before Analyze, upload/crop/probe/quote are local only. After explicit approval:

1. cam1: at most one Meta file upload, one SAM 3.1 object-video request over
   native frames **[0,158)**, one destination-image segmentation at frame **0**.
2. cam2: the same independent operations and native frame window.
3. cam3: the same independent operations and native frame window.
4. One Muse Spark Open evidence-grounded explanation, model
   `accounts/fireworks/models/muse-spark-open`, low reasoning effort,
   maximum **2048 output tokens**, **6 context images maximum**: each view's
   original frames **0 and 157**. Camera IDs, original evidence IDs and source
   mappings accompany the package. The existing strict verifier remains active.

Maximum model operations: **3 SAM video + 3 SAM image + 1 Muse**. Meta media
uploads: **at most 3**. Cache hits may reduce requests; retain their provenance.
No automatic paid retries. Run sequentially; no speculative extra view calls.

## Budget and stop rules

Configured local estimate:

| Item | Estimate/reservation |
|---|---:|
| SAM video per view: 158 × $0.20/1000 | $0.0316 |
| SAM destination image per view | $0.0025 |
| SAM total across three views | $0.1023 |
| One Muse conservative reservation | $1.3200 |
| **Combined** | **$1.4223** |

Proposed explicit **$1.50 per-run admission cap**, retaining the existing
**$10 total ledger limit**, spending history and reservations. These are local
estimates/controls, not provider-enforced billing guarantees or authenticated
account pricing. Credential presence does not verify credit or model access.

Stop before starting if the displayed estimate exceeds $1.50, the real ledger
has unresolved charges/reservations, a provider is not configured, or extraction
changes frame counts/PTS. Stop remaining operations on the first provider,
verification or usage-reporting failure. Recheck the remaining estimate after
every SAM charge; do not continue above the approved plan. Retain unknown
reservations for reconciliation. No automatic rerun, alternative model or mock
substitution on failure.

## Personal execution steps — only after approval

```powershell
DemoDoctor-Stop
DemoDoctor-RealAnalysis -CredentialsFile '<private-inputs>\.env' -PerRunBudgetUsd 1.50
```

1. Import Footage → count **3** → **Fixed-panel composite MP4**. Upload the
   original file. Inspect the automatically suggested regions and confirm the
   exact rectangles above. Set names, motion declarations and prompts.
2. Enter the task/questions. Select custom window **0** to
   **10.533333333333333** seconds. Whole-task physical completion is not certified
   merely because this window includes every file frame.
3. Initially use **Dry Run** to inspect source/extraction/playback locally.
4. Re-upload/setup if needed, select **Real Analysis**, and review the hash,
   every native frame range, request counts, questions and combined estimate.
5. Click **Analyze — approve estimated cost** personally exactly once.
   If the start response is lost, recover that job's status; do not resubmit.

Record separately: per-view returned observations/mask quality and missing
frames; destination diagnostics; citation integrity; unverified hypotheses;
criterion coverage; abstention; predicted outcome versus independently reviewed
reference observations. Multi-view visibility is not physical identity, 3D,
orientation, grasp/release or completed drawer closure verification.

Store outputs only under the ignored local job directory. Do not alter frozen
experiments, the six demonstrations, public release or final video. The private
DROID media's redistribution rights remain unestablished; do not publish it.
