# Portable assisted final-placement setup

This opt-in feature computes a narrow final-placement finding from original video
pixels. It is **Assisted**, using an approved saved SAM rack template and a green
plate task prior. It is not arbitrary-video failure recognition. No SAM/Muse calls,
API credentials, developer caches, historical jobs or reference labels are needed.

## Fresh checkout

From the repository root, using Python 3.12 and Node 22 (Windows commands shown):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
npm --prefix web ci --no-audit --no-fund
.venv\Scripts\python -m placement_assessment.portable --download
npm --prefix web run build
.venv\Scripts\python scripts/serve-placement-candidate.py --port 18890
```

On Linux/macOS replace `.venv\Scripts\python` with `.venv/bin/python`.
The setup downloads **only 63,245,876 bytes** (two originals) from the official
publisher, verifies both and registers the approved packaged rack template.
Network access is used only for dependency installation and explicit asset setup;
assessment and reopening are offline. No automatic downloads occur at app startup.

Open **http://127.0.0.1:18890/#ep010** → Findings → **Assess final placement offline**.
For the comparison, return to EP010, select **BF000 development recording**, then
assess. The selected source opens in a separate saved investigation with its own
original video; it is not substituted into the bundled derivative replay.

The standard DemoDoctor backend also discovers this registration automatically.
Do not set `DEMODOCTOR_PLACEMENT_REGISTRY` or its SHA variable for portable setup.
Those variables are optional explicit legacy/developer overrides, not prerequisites.

## Import exact originals instead

If downloads are unavailable, obtain the originals using the pinned publisher URLs
in `placement_assessment/assets/manifest.json`, then run:

```powershell
.venv\Scripts\python -m placement_assessment.portable --bf010 C:\downloads\episode_000010.mp4 --bf000 C:\downloads\episode_000000.mp4
```

Arbitrary uploads, renamed re-encodes and the bundled H.264 EP010 are rejected.
No ROI, outcome or failure time is accepted. If an interrupted acquisition leaves a
`.mp4.part` file, setup stops. Inspect/remove that specific incomplete file before
explicitly running setup again. No automatic retry or silent overwrite occurs.
Existing originals are reverified on repeated setup; no new download is necessary.

## Assets and authority

| Asset | Size | Identity / source | Distribution |
|---|---:|---|---|
| BF010 original | 31,591,660 B | `8f61d8613e820992f7db8f9c9cb930fb067a8fa39497b852ebfc23202fbb349a` | Publisher download or verified import; Apache-2.0 |
| BF000 original | 31,654,216 B | `cea576db2d2a9b48ddf95c5cb6dbee38c032030459c28cb48f411f547bd54c99` | Publisher download or verified import; Apache-2.0 |
| Approved rack response subset | 3,375 B | `95289fe1d800f05a26cc1a133d522723183c26de32388c6b5bf819c869e3b199` | Packaged, explicitly sanitized; genuine unchanged mask and request binding |
| Portable manifest | 3,217 B | `57bd664ad24112c9f89edeb4ec3e710c33617a731eb4705b4979c407903e200a` | Packaged and pinned in setup code |
| Native source indices | Generated locally | Digest pinned separately for each full decoded recording in manifest | No historical research database required |
| Source-frame images, SIFT features, registrations and final measurements | Recomputed locally | Derived exclusively from verified originals and approved template | No precomputed failure answer distributed as detector input |
| Robot state, historical Muse, other SAM masks, API credentials | Not required | Not read by this detector | Not provisioned |

Both originals contain **2,090 frames, 640×480, 30 FPS**, ending at frame 2089,
69.633333 seconds. Setup verifies native PTS/time bases, dimensions, frame count,
and the SHA-256 of a canonical index including **every decoded RGB-frame hash**.
It also reconstructs original BF010 frame 1260's JPEG95 bytes and the SAM image
request cache key, validates the approved response hash and completed status,
and decodes its mask. An alternate mask or derivative is not authorized.

The files live under ignored `data/placement_assets/`; paths are constructed
relative to the checkout, with no developer username, drive or private cache.
Registration contains no keys. The checked-in manifest is the authority, not a
self-asserted local receipt. Asset or mapping changes fail closed on admission.
Generated assessment jobs retain the existing integrity seal and citation checks.

The original measurement source and displayed saved-job video remain byte-identical.
The historical bundled derivative is a different asset and is never assigned the
original's RGB hashes. No derivative substitution or new mapping is introduced.

See [asset notices](../../placement_assessment/assets/NOTICE.md) for attribution,
modification details and provider-output rights. The [publisher license declaration](https://huggingface.co/datasets/kantine/BotFails/blob/3478e49d91e1737eb76dfee2d81bb22617039c13/README.md)
and [Meta output terms](https://dev.meta.ai/legal/terms-of-service) were checked on
2026-11-04. The original response's private paths and unused metadata are not shipped.

## Expected scope

BF010: visible final-placement condition contradicted, frames 2074–2089,
69.133333–69.633333 s, 93–97 px lateral separation. BF000: no supported failure
claim; this is not proof of success. These are disclosed development checks,
not generalization accuracy. Onset is Unknown, physical cause Unverified, and
Muse `provider_skipped`. Source indices, setup manifest and detector inputs contain
no reference outcome or failure timestamp.

If setup cannot complete, Findings displays the setup requirement. No assessment
success or inference is claimed. Decoder/library differences that change native
RGB bytes or reconstructed JPEGs must be investigated; do not relax their hashes.
Other operating systems have not been independently validated by this Windows test.
