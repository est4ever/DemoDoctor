> Historical milestone/proposal. A private owner-initiated one-view SAM/Muse run was later completed; no new video/job/provider records are bundled. Proposed inputs/crops below are not a current approved quote. Use the actual prepared manifest and review the UI estimate. Current capabilities and limits are in ../../README.md and ../submission/FINAL_UPDATE_20261101.md.

# Proposed first genuine UI-initiated validation

**Prepared, not approved or executed.** No paid request is authorized by this
document. Existing [three-view proposal](MULTICAMERA_REAL_EXPERIMENT.md) remains
an alternative, not an additional authorized run.

## Exact input and scope

Use the user's existing DROID composite file at
`<project-root>\data\live_jobs\20261031T233708Z_5816831d\video.mp4`.
SHA256: `eaec1033f19cf7fce385b0a120fa80edda4d78a9a171cb9462a0af5351961f53`.
It has 158 frames at 15 FPS, 3872×736 pixels. Choose **one camera**, **Fixed-panel
composite MP4**, crop **x=8, y=8, width=1280, height=720** (External left).
Confirm that preview personally; the crop is performed by DemoDoctor, not
manually outside the UI. Motion: stationary if personally confirmed, otherwise
unknown. Source timestamps/frame mapping and the original video stay retained.

Task input: **Pick up the blue block, put it in the open drawer, then close the drawer.**
Object prompt: **blue block**. Destination prompt: **open drawer**.
Window: **0–10.533333333333333 seconds**, native frames **[0,158)**.
Question: **What possible placement, incomplete-execution or occlusion mechanism
could explain this demonstration? Keep explanations as hypotheses when unverified.**

The dataset success label is not ground truth for this run. No exact object
inventory or physical pose condition is inferred from that label or question.
Before approval, independently review the whole clip and record any reference
observations and their frames separately from the inference input. Unknown is
an acceptable reference if the view cannot establish completion.

## Maximum paid sequence and approval

1. At most one Meta file upload for this cropped view.
2. One Meta SAM 3.1 object-video operation over frames [0,158).
3. One destination-image operation at native frame 0.
4. One Muse Spark Open call, model `accounts/fireworks/models/muse-spark-open`,
   low reasoning effort, at most 2048 output tokens and two context images:
   native frames 0 and 157, plus camera-labeled evidence and source references.

Configured local estimate: SAM video **$0.0316**, destination image **$0.0025**,
Muse reservation **$1.3200**; combined **$1.3541**. Proposed admission cap
**$1.50**, retaining existing **$10 total ledger**, past spend and reservations.
Estimates/local controls are not a provider-enforced billing guarantee. Actual
account pricing, credit and model access have not been verified by a paid call.

Zero automatic paid retries. Stop before any call if the file/crop/window,
quote, request list or cap differs. Stop remaining calls on provider, usage,
budget or strict citation failure. Keep unresolved reservations for manual
reconciliation. Never substitute mocked evidence after real inference fails.

## Personal UI procedure, only after explicit approval

Restart the backend to load the latest source; the ordinary launcher remains
offline and Dry Run stays the UI default. The explicit local option is:

```powershell
DemoDoctor-Stop
DemoDoctor-RealAnalysis -CredentialsFile '<private-inputs>\.env' -PerRunBudgetUsd 1.50
```

Credentials stay backend-only. Provider presence does not certify account
access or credit. Opening the app and uploading/previewing do not start paid
analysis. Select the exact file/crop/task/window above; first verify Dry Run if
desired. Then choose **Real Analysis**, **Review real analysis estimate**, check
all inputs and the displayed request count, and personally click
**Analyze — approve estimated cost** once. Recover the same job if the response
is lost; do not repeat Analyze or clear its reservation automatically.

## What to retain and score separately

- New job ID, original/derived source hashes, crop, native PTS/frame mapping.
- Whether real providers were invoked (not dry-run/cache-only); usage, cost
  reservations and terminal statuses. Never copy credentials into the report.
- Actual tracking frames, masks/boxes, missing detections and identity gaps.
- Original evidence package, strict citation verification and source seeking.
- Four-state criteria, specific Unverified hypotheses and resolving observations.
- Predicted outcome versus the separately recorded reference; abstention,
  false physical statements and tracking coverage are separate scores.
- Browser refresh opens the same result without new provider calls.

Keep artifacts in the ignored local job directory. DROID redistribution rights
remain unestablished here; do not commit or publish the clip, new outputs,
public repository changes or video changes. This run would establish one real
workflow execution, not generalization or reliable orientation detection.
