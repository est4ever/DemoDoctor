# README media attribution and provenance

These are genuine captures of the public DemoDoctor application at commit
`96caf60efeff214ab4550bba6be6f0cf96480bb9`. No application text, detections,
robot events or results were composited into the screenshots. Lossless WebP
preserves screenshot pixels; the criterion image is a crop of the visible inspector.
The GIF scales actual screen captures and reduces their color palette; timestamp
jumps come from deliberate evidence selection and seeking, not continuous playback.
There is no audio. Files contain no private DROID imagery, API credentials,
personal file paths or original private job identifiers.

| Asset | Actual source and qualification |
|---|---|
| `workstation.webp` | Bundled EP010 replay at 43.100 s, Annotated mode, E0 source open. Image-space calculations are not proof of release or placement. |
| `evidence-workflow.gif` | Bundled EP010; selects evidence including the measured gripper signal at 44.500 s, seeks the timeline, opens source details and steps one frame. The saved inferred classification remains unchanged. |
| `task-criteria.webp` | Bundled EP003 inspector: sampled 2D containment Supported, physical orientation Unverified, with resolving evidence. Cropped to the first two criteria for readability. |
| `multicamera-mock.webp` | Real three-camera UI with three generated calibration videos and existing mocked providers. Every view and the task header visibly say MOCK. No real robot inference or validated multi-camera diagnosis is represented; the original-view display does not present mock SAM masks as real. |
| `architecture.svg` | Original documentation diagram, not an application screenshot or experimental observation. |

The EP010 and EP003 footage derives from **kantine/BotFails**, pinned dataset
revision `3478e49d91e1737eb76dfee2d81bb22617039c13`, under its publisher-declared
Apache-2.0 license. The screenshots and GIF are edited display derivatives of the
already bundled replays. Preserve [NOTICE](../../NOTICE) and the
[full third-party notices](../submission/THIRD_PARTY.md), including dataset citation,
license and modification records. BotFails: Quentin Rolland, Fabrice Mayran de
Chamisso and Jean-Baptiste Mouret, *Failure Identification in Imitation Learning via
Statistical and Semantic Filtering*, ICRA 2026.

Original DemoDoctor UI, documentation, generated calibration graphics and the
architecture diagram are covered by the repository's [Apache-2.0 license](../../LICENSE).
Separate model/provider and dependency terms are unchanged. The SO-101 PILOT's
separate dataset notices remain in the project documentation, although its footage
is not used in these images. The linked finished YouTube video is not repackaged;
its narration/music permissions are separate and unchanged.

[CAPTURES.json](CAPTURES.json) records dimensions, transformations and SHA-256 hashes.
No generated calibration recordings, local QA servers or private job artifacts are
distributed with the README. Image capture and mock analysis made zero paid calls.
