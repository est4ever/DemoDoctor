# Diagnostic context presentation

Completed investigations already open Findings with Task-criterion coverage
expanded. States, scoped basis and resolving observations remain separate from
the recorded task verdict and physical completion. Source records and technical
details stay expandable. No inference or verification rule changes are introduced.

## Original temporal context

The workstation now shows at most six chronological original-frame previews,
using existing task context, saved frame catalogs, or original evidence-catalog
frame boundaries. It does not synthesize tracking observations or select a new
failure label. Preview images are decoded locally from the existing original
camera/replay video; the synchronized main video changes only when a frame is
clicked. Native frames, source times and camera/source IDs remain attached.

Camera context is limited to the approved processing interval. Frames in an
observation gap remain viewable original footage, explicitly marked as having no
returned SAM observation. A saved Muse catalog reference is shown only when the
same camera/source/frame is in that analysis's saved input catalog and a saved
Muse explanation exists. Inclusion is not evidence that Muse interpreted it
correctly. Other frames are labelled local context, not claimed Muse inputs.
PILOT's offline reconstruction never borrows the historical Muse package bindings.

Saved hypotheses and visual interpretations remain verbatim and Unverified.
Camera-labelled interpretation links now select their own validated camera and
source time, rather than seeking whichever camera was previously visible. Missing
or mismatched frame provenance produces an unavailable reference, never frame zero.

## Optional local analyst review

An optional `web/public/local-reviews/<job-id>.json` can retain a separately
reviewed visual interpretation. This directory is Git-ignored and must not be
copied into public releases. There is no new model, detector, editor or automatic
annotation generation. The note is presentation context, never an inference input,
verified observation, source predicate or change to the original saved job.

Schema: `demodoctor.local-visual-review/v1`. Required top-level fields are
`job_id`, `reviewer`, `method`, and one to six `observations`. Each observation
contains `text`, `limitation`, `camera_id`, `source_video_id`, `camera_sha256`,
`source_sha256`, `frame`, and `original_timestamp_s`. It must match the job,
approved camera/source hashes, processing interval, native FPS and an existing
task-context frame. A missing note is optional; mismatched provenance is visibly
withheld. All accepted notes are forcibly labelled **Unverified analyst visual
interpretation**; a supplied status cannot promote them to verified claims.

The existing privately reviewed drawer appearance is retained as visually
consistent with closed near the end. It is not independently verified mechanical
closure, a new Muse output or a calibrated measurement. The original outcome and
three action subgoals remain Uncertain/Unverified. The private note, media and job
are not distributed in the public snapshot. Public regression tests use synthetic
review metadata only.

## Limits and validation

The controlled task parser, absence of independently measured pickup/placement/
closure, unverified orientation, object identity, occlusion and cross-camera
geometry remain scientific limitations. Temporal context and hypotheses help
inspection; neither establishes a verified failure mechanism. Reference outcomes
are not predictions, and abstention is not successful failure identification.

Tests cover native timing, source/camera mismatches, absent/invalid review data,
missing observations, historical citation separation, unchanged original analysis,
camera-specific interpretation seeking and explicit Unverified labels. JSDOM media
methods are stubbed because it cannot decode video; real frame previews and seeking
must also pass Chromium QA. No paid inference is required for these checks.
