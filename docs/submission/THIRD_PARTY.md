# Third-party materials and licenses

This folder records the sources and redistribution basis checked on October 31,
2026. It does not apply one blanket license to third-party work or model outputs.
Original DemoDoctor code and documentation use the root [Apache-2.0 license](../../LICENSE).
The root [NOTICE](../../NOTICE) preserves the distinction from third-party work,
recorded model outputs and separately licensed video audio.

## Included recorded media

| Source | License shown by publisher | Included subset |
|---|---|---|
| [kantine/BotFails](https://huggingface.co/datasets/kantine/BotFails) | Apache-2.0 | Five dish-tidy-up test episodes, compact display transcodes and recorded SAM overlays |
| [ankithreddy/so101_pickplace_uno](https://huggingface.co/datasets/ankithreddy/so101_pickplace_uno) | Apache-2.0 | Episode 000000 top camera, compact transcode for the real SAM pilot |
| SO-ARM100 robot assets | Apache-2.0 as retained in the asset directory | Existing optional legacy assets; `web/public/robots/NOTICE` and license files retained |

Revision identifiers, source/distribution SHA-256 hashes, dimensions and frame
counts are recorded in `data/submission_demo/MANIFEST.json`. All transcodes carry
a modification comment; adjacent NOTICE files describe the changes. The full
[Apache-2.0 text](../../data/submission_demo/LICENSE-APACHE-2.0.txt) accompanies the
package. The source datasets' attribution metadata is retained under data/lerobot.
No dataset license is being asserted for unrelated files or private user uploads.

## Model outputs and hosted services

SAM results and Muse explanations are AI-generated/AI-assisted recorded outputs,
not human observations of unmeasured actions. No model weights are distributed.

- [Meta Model API terms](https://dev.meta.ai/legal/terms-of-service), last updated
  October 9, 2026: §4.1 retains users' rights in inputs/outputs as between the
  parties; §1 permits incorporating outputs into integrated products. Applicable
  use restrictions and third-party rights still apply. This package only replays
  existing results; it does not train competing models or expose API credentials.
- [Fireworks terms](https://fireworks.ai/terms-of-service), §4.3 in the indexed
  official terms: lawful output use is subject to provider/model restrictions,
  accuracy review and AI-generation disclosure. The site's current direct URL
  redirects to a PDF that the web reader could not fetch. Owner should retain
  the terms applicable to the original account if publishing the historical
  output outside the hackathon. The compact pilot export omits raw transport/usage data; older frozen research
  records elsewhere may retain usage/request metadata. See the release audit
  before approving public history exposure.
- Historical published Muse text is exported only from the original saved
  analysis, with its original package. The raw provider payload is omitted.

## Software dependencies

| Layer | Principal dependencies | Declared licenses |
|---|---|---|
| React UI/build | React, React DOM, Vite, TypeScript, Tailwind, Vitest, clsx | MIT; TypeScript Apache-2.0 |
| Optional robotics UI | Rerun viewer, Three.js, React Three Fiber/Drei, urdf-loader | MIT as declared by installed npm packages; see inventory |
| Backend/UI fallback | FastAPI, uvicorn, Streamlit, python-multipart | MIT, BSD-3-Clause, Apache-2.0, Apache-2.0 respectively |
| Analysis | NumPy, pandas, OpenCV Python, PyAV, PyArrow | BSD-3-Clause, BSD-3-Clause, Apache-2.0, BSD-3-Clause, Apache-2.0 |
| Service adapters/testing | OpenAI SDK, Hugging Face Hub, python-dotenv, HTTPX, pytest | Apache-2.0/MIT/BSD as declared per package; inventory is authoritative for installed versions |
| SAM result parser dependency | meta-sam-parser 0.1.0 | **SAM License**, last updated November 19, 2025, as retained in the Python inventory; not Apache-2.0 |

Exact versions and package-declared license metadata: [Python inventory](licenses/python.json)
and [npm inventory](licenses/npm.json). npm includes optional platform dependencies
that may not be installed on this OS. A missing license field is marked explicitly;
it is not treated as permission or silently changed to MIT.

The `webgl-constants` 1.1.1 lockfile entry has no license field. Its installed
package includes an MIT `LICENSE`, copyright 2019 Tim van Scherpenzeel; a
[retained copy](licenses/webgl-constants-LICENSE.txt) documents that evidence.
The npm inventory continues to report the lockfile's missing field truthfully.

The original development tree also contained dataset-derived assets: the 11 Parquet
subsets and metadata under `data/lerobot`, research frame previews under
`data/experiments`, optional EP010 Rerun recordings under `prototypes/rerun_ep010`
and `web/public/recordings`, and the prototype event-window video. Their source
datasets are the two separately identified publishers above. The prototype
README/exporter describes its transformations; recorded SAM output is not a new
dataset license or proof of unobserved actions. The public snapshot excludes prototype recordings and unused research files. Retained fixture metadata is sanitized only as disclosed in SNAPSHOT.md; the original private artifacts remain unchanged.

Text-file SHA256 values in legacy SOURCE.json records describe downloaded bytes.
Git and Windows checkout line endings can change those byte hashes. All 11 tracked
Parquet files match their recorded source hashes exactly; the six tracked dataset
JSON/JSONL/CSV files were compared with their exact pinned upstream files and
match after CRLF/LF normalization. This is a text serialization difference,
not changed labels, measurements or scientific results. Those upstream text
comparisons are the earlier recorded checks; the new public snapshot separately
sanitizes SOURCE.json provenance metadata as documented in SNAPSHOT.md. No
scientific value is changed.

The lockfiles reproduce dependency versions; installers fetch the actual packages
and their license texts. PyAV/OpenCV wheels include native codec components with
their own notices; codec/library licenses must be retained if distributing those
binaries. This source package distributes neither a Python environment nor an
FFmpeg executable. The optional npm Rerun Wasm ships through npm on installation.

Before distributing a compiled frontend outside the hackathon, retain its bundled
dependency notices. This work does not deploy or redistribute a compiled build.

## Final public-release verification

Both publisher APIs were re-fetched without authentication for the exact pinned
revisions and returned `apache-2.0`:

- [BotFails pinned metadata](https://huggingface.co/api/datasets/kantine/BotFails/revision/3478e49d91e1737eb76dfee2d81bb22617039c13).
- [SO-101 pinned metadata](https://huggingface.co/api/datasets/ankithreddy/so101_pickplace_uno/revision/f47dcf21b0bf8bd0f83cec8fd74755c65dfc012b).

All 19 files in the submission manifest match their recorded SHA256 hashes.
The five BotFails camera/overlay pairs and the SO-101 pilot camera constitute
the six bundled demonstrations. Retained Apache-2.0 texts, source attribution
and modification notices accompany them. This is the publisher-declared license
basis, not a warranty about every upstream right or a blanket grant for model
outputs and unrelated media. Apache redistribution conditions are stated in the
[official license](https://www.apache.org/licenses/LICENSE-2.0).

The BotFails publisher requests this research citation: Quentin Rolland,
Fabrice Mayran de Chamisso and Jean-Baptiste Mouret, “Failure Identification in
Imitation Learning via Statistical and Semantic Filtering,” ICRA 2026.
The SO-101 source card attributes its creation to LeRobot.

The completed video uses the owner's supplied ElevenLabs Hope / Eleven v4
narration and DemoDoctor Resolve soundtrack. They are not dataset assets or
bundled source dependencies. Retain the owner's applicable voice/music export
permissions before public upload; the audit did not inspect private account
contracts. No new voice, music, model output or paid call was generated.
