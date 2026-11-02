# Unified camera workflow: 1, 2 or 3 views

The integrated checkout has one Import Footage workflow, with **Camera count**
set to **1** by default. There is one Dry Run/Real Analysis selector, one task
and window form, one preparation/approval controller, one progress/recovery
loop, and the existing investigation workstation. Selecting more cameras is
input configuration, not another inference system.

## Behavior by selected count

| Views | Individual recordings | Fixed-layout composite | Analysis and limitations |
|---|---|---|---|
| 1 | Existing upload, preview, format support, task/object/destination controls and inference rules remain the default | Select and confirm one native-pixel crop | Ordinary upload retains the existing verdict rules and original evidence IDs. A selected composite crop uses the conservative camera-set adapter; its outcome remains uncertain |
| 2 | Upload and preview both MP4s; approve offsets and their alignment basis | Confirm two disjoint camera rectangles | Independent SAM video/destination analysis per view, followed by one camera-labeled Muse request. No cross-camera physical identity or fused success/failure verdict |
| 3 | Upload and preview all three MP4s; approve offsets and their alignment basis | Confirm three disjoint rectangles; a DROID layout preset is available | Same adapter and rules as two views; up to six context images total for the one Muse request |

Camera-set inputs publish observations in their original camera coordinates,
with source-video IDs, hashes, timestamps, native dimensions and frame mappings.
The same track ID in two cameras is not a physical-object correspondence. Each
display evidence ID maps back to its camera's original package and evidence ID.
Untimed diagnostics do not seek. Source inspection loads only the selected
camera's observations, including when an earlier response arrives late.

All camera views use one shared software clock. Selecting evidence seeks the
shared time and identifies its supporting camera. Any view in a set of two or
three can become the expanded primary view; the others remain available. A
one-crop investigation already occupies the full video area. Original ordinary
single-camera playback, SAM controls and the six recorded investigations remain
available. Dry replay now carries its native FPS metadata for correct stepping;
this adds no observations or physical conclusions.

Composite regions are suggested automatically from the decoded preview using
generic dark-gutter geometry, with an explicitly labeled equal-panel fallback.
This is a layout heuristic, not camera recognition. It handles side-by-side or
stacked panels; dark scene edges can be ambiguous. Inspect/edit and confirm the
regions inside DemoDoctor. No pre-upload crop or external editor is required.
The original proposal and final confirmed crop rectangles are retained separately.

The **Camera display** control selects all views, one individual view, or the
original composite. SAM/annotation modes are independent for each camera.
Original-composite overlays use a display-only crop-origin translation and
camera-scoped labels. They do not merge observations or infer identity/geometry.
Optional **Questions to investigate** reach Muse as diagnostic questions, not
new success criteria or observed facts. Unsupported orientation, placement,
completion or occlusion explanations remain unverified hypotheses/limitations.

## Architecture and compatibility

- `ImportFootage` mounts one `LiveAnalyzePanel`. `CameraInputs` manages only
  camera count, previews, crop rectangles, prompts and alignment inputs. It
  performs no fetch, approval or job polling.
- `LiveAnalyzePanel` owns all upload preparation, the immutable estimate,
  confirmation, cancellation, progress, failure display and reload recovery.
  Changing count, source layout or input parameters invalidates the estimate.
  Changing count and back preserves the original single-camera form state.
- A plain single-camera recording uses the existing `/api/analyze` and
  `/api/jobs/{id}/start` compatibility endpoints. Their inference rules are
  unchanged. Camera sets (including one composite crop) use the existing
  generic camera-manifest adapter, now accepting 1–3 cameras. Both call
  `live_pipeline.run_analyze` and the same SAM/Muse adapters, verifier and ledger.
- The adapter runs cameras sequentially. It does not construct another model
  pipeline or match track identities. One combined evidence package labels
  each original camera source and supplies at most two context frames per view
  to the existing strict Muse verifier.
- The original individual packages and provider observations remain saved.
  The existing `multicamera` result/schema names and URLs are retained for
  compatibility, including a camera-set result containing one crop.

## Personally test without paid inference

The existing running backend must be restarted to load new code. In a new
Windows PowerShell terminal:

```powershell
DemoDoctor-Stop
DemoDoctor
```

This starts the ordinary offline session. No credentials are needed for Dry Run.

1. Open **Import Footage**. Leave **Camera count: 1**, upload a normal camera
   recording, preview it and select **Prepare dry run**. The existing behavior
   remains the default.
2. Return to Import and select **2** or **3**. For individual recordings, choose
   **Separate synchronized camera MP4s**, preview every source, name the views
   and set their object/destination prompts.
3. Enter offsets and describe their alignment basis, then explicitly approve
   that alignment. Source elapsed seconds = shared seconds + offset. Matching
   filenames, equal frame rates or zero offsets do not establish synchronization.
4. Alternatively select **Fixed-panel composite MP4**, upload the original,
   preview it and set native-pixel crop rectangles. Confirm the rectangles
   before preparation. To select only one panel, choose count **1** with the
   composite layout and define just that crop.
5. For the existing 3872×736 DROID composite at count **3**, **Preview DROID panel
   boundaries** fills `(8,8,1280,720)`, `(1296,8,1280,720)`, and
   `(2584,8,1280,720)`. Review the preset and camera-motion fields yourself;
   the layout does not determine the task outcome or camera motion.
6. Keep **Dry Run** selected, choose a shared time window, and prepare. Inspect
   all views, primary expansion, timeline seeking and frame stepping. There
   should be no SAM observations, physical events or Muse findings in a dry run.

Real Analysis is connected to the existing pipeline but has only been validated
with **mocked providers** for these new camera-set workflows. No genuine new
multi-camera inference or task-outcome accuracy claim is made. After review,
explicitly launching `DemoDoctor-RealAnalysis` with backend-only credentials is
still required. Upload and estimate review do not start paid inference; only
the final **Analyze — approve estimated cost** button authorizes the displayed
plan. There is no automatic inference on startup, selection or refresh.

## Cost and safety

The confirmation shows every selected camera, its hash/native frame window,
its SAM operations, the total SAM estimate and one Muse reservation. A 15 FPS
0–4s camera-set window currently estimates $0.0145 SAM per view plus a $1.32
Muse reservation: $1.3345, $1.3490 or $1.3635 for 1, 2 or 3 views respectively.
These are local configured estimates, not authenticated pricing or
provider-enforced billing guarantees. Review the actual quote for your video.

The existing total/per-run ledger limits, origin protection and explicit local
opt-in remain in force. The full plan must fit before start. Reservations share
one parent run ID; updated estimates are checked after each SAM charge before
another provider operation. There are zero automatic paid retries. Failures
stop later views/Muse and never substitute mock results. Unresolved charge
reservations require reconciliation before another real run.

## Scientific and format limits

- Camera sets (including one crop) produce image-space evidence and diagnostics
  only. Their combined outcome is always uncertain. This is abstention, not
  successful diagnosis of an actual failure mechanism.
- No automatic synchronization, camera calibration, 3D geometry, cross-view
  object matching, verified orientation, grasp/release or drawer-closure detector.
  Moving-camera pixels are not interpreted as physical object travel.
- Muse hypotheses and cross-view interpretations remain **Unverified**. Factual
  claims must match camera-labeled catalog summaries under the existing strict
  verifier. Missing observations are not proof of object absence.
- Camera-set inputs currently require constant-rate, zero-origin MP4s; 200 MiB
  per source; at most five minutes per source and 30 shared seconds per window.
  Unsupported timing is rejected rather than silently rebased or interpolated.
  Composite extraction requires an already installed FFmpeg executable.
- Normal one-camera format support and inference remain unchanged; they do not
  acquire the camera-set adapter's stricter format requirements.
- The DROID sources/crops remain private and ignored. Their redistribution rights
  are unestablished. No media or synthetic inference results were added to Git.

## Validation evidence

Current multi-camera checkpoint checks: **321 Python tests passed** (including 32 camera-set tests and 18
single-camera real/dry contract tests); **90 frontend tests passed** across 17
files; production TypeScript/Vite build passed; `git diff --check` passed.
All provider execution during these tests used explicit synthetic fixtures.
**Zero real paid provider calls** were made. The public release, frozen results,
six bundled demonstrations, final video and real budget ledger were preserved.

The local mock browser matrix exercised six input combinations: original
single-camera upload, one selected composite crop, separate 2/3-camera uploads,
and 2/3 composite views. Every real-mode fixture required estimate confirmation,
executed exactly one SAM video/image pair per camera followed by one Muse call,
and recovered its camera count after refresh. Expansion kept other views present.
Separate-view offsets were checked without asserting physical calibration.

A second six-case browser matrix exercised Dry Run, zero provider operations,
zero physical findings, native 15 FPS stepping, camera-specific source inspection,
overlays, desktop viewport fit, visible provider failure and reload without retry.
No browser console errors occurred in these completed runs. Tests also cover
changing count invalidating approval, retaining single-camera inputs, unsupported
counts, strict citations and one-camera operation without a synchronization claim.

Local ignored receipts/screenshots:
`qa-browser-artifacts/camera-count-unified/camera-matrix.json`,
`dry-matrix.json`, `dry-failure-result.json`, `one-original.png`,
`2-separate-expanded.png`, `3-composite-expanded.png`, and `fit-1366x768.png`.
The final count-aware screenshots are `final-1-dry.png`,
`final-2-expanded.png` and `final-3-expanded-1366.png`. Expanded secondary views
hide repeated mode toolbars so footage stays visible. Select a camera as primary
to change its own mode. Each secondary camera remains selectable.

Final composite browser evidence is under `qa-browser-artifacts/composite-mvp-final/`:
`automatic-layout.json`, `RESULT.json`, `automatic-layout-unconfirmed.png`,
`full-run-approval.png`, `original-composite-overlays.png`, and
`camera-source-inspection.png`. DROID's automatically suggested rectangles were
confirmed as `(8,8,1280,720)`, `(1296,8,1280,720)`, `(2584,8,1280,720)`;
each crop retained all 158 original frame timestamps. Full-window mocked analysis
used exactly three SAM video/image pairs and one Muse explanation.

The [proposed one-run real experiment](integration/MULTICAMERA_REAL_EXPERIMENT.md)
requires separate user approval and has not been executed.
