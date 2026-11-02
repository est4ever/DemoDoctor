# Multi-camera MVP

Current UI: one unified **Camera count (1, 2, 3)** workflow. The previous separate
multi-camera form/controller has been removed. See [current guide](CAMERA_WORKFLOW.md).
An ordinary single recording retains its established pipeline and rules; a
camera-set manifest may contain one selected crop or up to three views.

Implementation (November 1, 2026): shared import/approval/progress controller;
validated 1–3 source/crop manifests; constant-rate,
presentation-timestamp-preserving FFmpeg crops; explicit alignment approval for
separate sources; sequential calls to `live_pipeline.run_analyze`; one combined
strict Muse evidence package; camera-scoped source inspection and synchronized
playback in the existing workstation.

Reuse `AnalyzeRequest`, SAM tracking/destination adapters, `live_budget`,
`EvidencePackage`, `validate_muse_explanation`, job/status endpoints,
`LiveAnalyzePanel`, `VideoPane`, shared playback, `InvestigationDesk` and
`EvidenceSource`. Add isolated `multicamera.py`, `multicamera_api.py` and focused
React components. Single-camera defaults and frozen results stay unchanged.

Scientific boundary: multi-camera analysis publishes independent image-space
detections and diagnostics only. Physical-event reconstruction is disabled for
all views in this first version, including moving/unknown cameras. No track-ID
association, calibrated 3D, orientation, grasp/release or cross-view task-outcome
verification is implemented. Combined verdict remains uncertain. Muse prose and
cross-view associations remain unverified; factual claims must copy catalog
summaries under the existing strict verifier.

Separate videos require user-approved alignment and a written basis. Convention:
source elapsed seconds = shared seconds + camera offset. Only the common valid
time interval is playable/analyzable. Crops inherit their source frame indices
and presentation timestamps. Variable-rate or malformed timing is rejected by
the MVP instead of resampling frames. Original source bytes are retained in the
ignored job directory. Lossy H.264 crop encoding is disclosed and verified for
frame-count/timestamp equality; no frames are interpolated.

Cost plan: up to one SAM object-video and one destination-image operation per
camera, sequentially, followed by one Muse request with at most two context
frames per camera. File uploads are included in the displayed plan. Explicit
local real-analysis launch and one file-bound, expiring approval cover the full
plan. All reservations share the parent job budget ID. Zero automatic paid
retries; first failure stops subsequent views and Muse. Estimates are not
provider-enforced billing guarantees.

Validation: private existing DROID composite crop/time audit, synthetic
provider end-to-end tests, missing/disagreeing views, citation isolation,
approval/hash/origin/budget guards, reload, provider failures, single-camera
regression suite, production build and gstack browser interactions. No paid
inference is authorized during development.

## Local use

Restart after updating: `DemoDoctor-Stop`, then ordinary `DemoDoctor` for an
offline review. An already running backend does not hot-load new endpoints.

FFmpeg must already be installed and on the backend process PATH, or supplied
through the backend-only `DEMODOCTOR_FFMPEG` environment variable. Nothing is
downloaded automatically. PyAV validates decoded frame timestamps. Existing
single-camera inputs do not require the external FFmpeg executable.

Choose optional multi-camera mode in Import Footage. Confirm camera names,
prompts, movement type and alignment. For a composite, edit and visually confirm
each fixed pixel rectangle against the original video before preparation.
Start with Dry Run; it performs extraction and synchronized replay without SAM
or Muse or physical conclusions. Real Analysis requires the explicit local
launcher opt-in and cost approval. Keep uploaded sources and generated private
jobs out of Git and public exports.

For the existing 3872×736 DROID source, **Preview DROID panel boundaries** fills
the rectangles `(8,8,1280,720)`, `(1296,8,1280,720)`, and
`(2584,8,1280,720)`. These are a layout preset, not a detector. Review every
rectangle and the camera labels/movement types before confirming. The preset
does not establish the demonstration's outcome. Source overlays/axes burned
into the original video remain part of the source, not reconstructed geometry.

Separately supplied recordings require an operator-approved alignment basis;
DemoDoctor validates finite offsets and an overlapping native-frame interval,
not the physical correctness of that alignment. Browser playback uses a shared
software clock with ordinary decoder tolerances, not a hardware synchronization
or calibration guarantee. At smaller desktop sizes, expand the primary view
or collapse a side panel to inspect fine visual details. Narrow windows stack
views and intentionally scroll.

## Initial MVP verification (before unified-count revision)

- Final complete Python suite: **310 passed** in 202.90s; **23** tests in
  `tests/test_multicamera.py` cover the new API/orchestration. Final frontend
  suite: **79 passed** across 14 files; production TypeScript/Vite build passed.
  `git diff --check` passed. Real provider calls: **zero**.
- The private DROID source hash remains
  `eaec1033f19cf7fce385b0a120fa80edda4d78a9a171cb9462a0af5351961f53`.
  Each 1280×720 crop retains all **158 frames**, **15 FPS**, and timestamps
  **0 through 10.466666667s**, with a one-to-one source-frame mapping.
- Dry Run has zero observed/inferred/physical findings and an uncertain outcome.
  SAM and Muse are provider-skipped. Three real DROID camera videos decoded
  together in Chromium; shared seeking and a native **1/15s** frame step passed.
- The real-analysis execution path was tested with synthetic providers only:
  three sequential SAM video/image pairs, then one strict Muse request.
  No provider ran at upload or estimate review. Example approved window
  **0.5–4s**, native frames **[8,60)** per camera: SAM total **$0.0387** plus
  Muse reservation **$1.32**, combined estimate **$1.3587**. This is a local
  estimate, not authenticated pricing or a billing guarantee.
- Per-camera source inspection preserved original evidence IDs and showed
  camera-local measurements. Wrong-camera factual citations were rejected.
  Untimed diagnostics did not seek; late source responses could not replace
  another camera's measurements. One-frame source tables no longer duplicate
  the same endpoint row.
- Missing detections remained missing evidence, not object absence. A synthetic
  cross-view disagreement remained an **Unverified** hypothesis with an
  uncertain outcome. First-provider failure visibly stopped later cameras and
  Muse without retries or a substituted result. Unresolved synthetic charge
  reservations were retained in the isolated test ledger.
  If actual usage raises the remaining estimate above the approved plan, the
  runner rechecks immediately after each SAM charge and stops before the next
  provider operation, including before destination segmentation.
- Separate-view uploads with an explicitly approved test offset of **0.2s**
  played with that offset. This checks arithmetic and user approval, not an
  independently established real-world synchronization measurement.
- The three videos, timeline and selected evidence fit simultaneously at
  **1920×1080**, **1440×900**, and **1366×768**. Primary expansion, actual canvas
  overlay pixels, reload recovery and navigation to all six single-camera
  replays passed. No browser console errors occurred in those completed runs.
- Regression coverage includes backend approval/origin/offline/hash/budget
  guards; crop boundaries, timestamps and original source retention; missing
  detections; fail-stop; strict citations; stale camera source responses;
  native frame seeking; and the unchanged single-camera default.

Local evidence is ignored under `qa-browser-artifacts/multicamera/`:
`browser-real-result.json`, `browser-edges-result.json`, `droid-dry-run.json`,
`combined-quote.json`, `cam2-source.json` and the viewport screenshots.
Synthetic outputs are visibly marked **QA MOCK PROVIDERS** and are never
packaged as genuine SAM/Muse results. No new real-provider generalization claim
is made. Redistribution rights for the private DROID input are unestablished;
the source, crops and recordings remain private/ignored.

## Remaining experimental limitations

- No automatic alignment, audio matching, camera calibration, 3D reconstruction,
  cross-camera object matching, physical orientation detector or sensor-based
  grasp/release verification.
- No whole-task success/failure fusion. Every combined outcome remains uncertain.
  Abstention is not successful identification of a failure mechanism.
- Constant-rate, zero-origin MP4 only for camera sets; 1–3 views; 200 MiB/source; five-minute
  source duration; at most 30 shared seconds analyzed. No source frame synthesis,
  time stretching or automatic timestamp rebasing.
- FFmpeg is an optional external local prerequisite for composite crops, not a
  new bundled binary. Its installed build's license remains separate from this
  project's source license. PyAV and the existing model dependencies are reused.
- The self-service Real Analysis UI is connected, but no genuine multi-camera
  provider run or outcome-accuracy validation has been authorized or executed.
