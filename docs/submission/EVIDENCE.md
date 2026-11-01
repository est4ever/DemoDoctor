# How evidence-grounded analysis works

**Observed** means a bounded measurement from supplied data, such as an exact
SAM box or paired gripper-joint reading. **Inferred** means an interpretation
supported by explicit observations and rules. **Uncertain** means available data
cannot support the relevant conclusion. These labels must not be upgraded by
the narrative or by a display component.

Structured claims are independently recomputed from the observations. Evidence
IDs link each claim to its source and timestamp. Muse receives an evidence
package; its accepted factual claims must obey that package's contract. This
does not semantically verify arbitrary natural language or prove task success.

## Real video-only pilot

For recorded SAM track `screwdriver:0`, actual endpoint frames 0 and 736 have
image-space box centers (891,457) and (282,460.5). Their Euclidean difference is
609.010057... px, displayed as **609.01 px**. The second independently checked
claim verifies coverage: 632 of 737 frames have returned detections.

Frames **433 through 537 inclusive** are **105 unobserved frames**. The interval
is represented as **[433,538)**, or 14.433333–17.933333 seconds. Trails stop and
restart at returned detections. Missing detection is not proof of absence, and
no continuous trajectory or physical identity guarantee is inferred across it.

Destination-tray segmentation returned zero observations (`empty_result`).
Containment and placement cannot be established. The video-only analysis has no
measured gripper or robot joint data. The final task verdict remains uncertain;
the endpoint comparison establishes neither grasp nor release nor task completion.

Historical Muse citations refer to the original `before` package. The reconstructed
`after` catalog has different meanings for its E IDs and no new Muse response.
The UI links these contexts separately. Numerical equality of an ID is never a
license to rebind a historical claim to regenerated evidence.

## Media fidelity

Included MP4s are explicitly labeled lossy display transcodes of public dataset
footage, preserving frame count, frame rate and native dimensions. The manifest
retains both input and output SHA-256 values. Measurements were made on the
original recordings, not silently recomputed from compressed display pixels.
