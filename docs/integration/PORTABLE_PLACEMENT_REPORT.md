# Distribution-blocker correction: independent-review handoff

**GO for Agent 1's bounded distribution acceptance.** A clean checkout reproduced
the actual product feature using publisher downloads and the packaged approved
template, without a developer registry, private cache, prior investigation or
provider account. No detector predicate, threshold, frame-selection rule or UI
architecture changed. No merge, push, paid inference or publication occurred.

Parent candidate: `72612c17a6f233e140c1647e0d78f3c4598093dd` (preserved).
Correction branch: `fix/portable-placement-assets`.
Frozen correction: `cbbfdd54f538e8f780b48f5c211c430a5689452b`.
This is the original correction handoff. The subsequent independent acceptance
is documented in [product integration](PRODUCT_FINAL_PLACEMENT_INTEGRATION.md).

## Minimal correction

- A 3,217-byte public manifest pins the two original videos, their exact lengths,
  SHA-256 and canonical full decoded-frame/native-time index digests.
- A 3,375-byte whitelisted record packages the **unchanged approved SAM rack mask**,
  its bbox, model/query/request identity and completed terminal status. Private
  paths and unused diagnostics were removed; the original record hash and this
  explicit modification are documented. No video, source image, API key, account
  identifier, paid billing history or model weights were added to Git.
- `python -m placement_assessment.portable --download` obtains only the pinned
  originals from the official publisher (63,245,876 bytes total). Explicit original
  import is supported when network access is unavailable. Both routes verify all
  native frame identities and the original template request binding.
- The existing backend discovers the verified repository-relative registration.
  No private absolute path or manually prepared ignored research file is required.
  Existing explicit startup-pinned developer overrides remain supported.
- Missing setup produces instructions; altered, stale, partial, unapproved or
  re-encoded inputs fail closed. An existing valid install cannot hide an invalid
  explicitly supplied replacement. Downloads never occur automatically at startup.

Asset sources, rights, hashes, sizes and fresh-install commands are in
[PORTABLE_PLACEMENT_SETUP.md](PORTABLE_PLACEMENT_SETUP.md), with the complete
[asset notice](../../placement_assessment/assets/NOTICE.md) and
[machine-readable inventory](../../placement_assessment/assets/manifest.json).
The publisher's pinned README declares Apache-2.0. Meta's current terms permit
output incorporation and allocate customer output ownership subject to their
terms and third-party rights. This specific public robot-scene output is attributed
and labeled AI-generated; this is not permission to distribute arbitrary private
datasets or Meta software.

## Clean-install execution

Clean test root (local QA artifact, not a dependency):
`qa-browser-artifacts/portable-clean-install/checkout`.

The snapshot contained only the tracked candidate and intended distributable
correction files. It initially had **no `.demodoctor`, no provisioned assets, no
job store, no `.env`, and no node_modules**. A fresh Python 3.12 virtual environment
used `include-system-site-packages = false`. Existing public locked dependencies
were installed with pip (public wheel cache used) and `npm ci`; no virtualenv or
node_modules junction was reused. Package locks and application dependencies were
not changed. The public originals were downloaded anew from pinned Hugging Face
URLs, not copied from a developer data directory.

Executed from that checkout:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
npm --prefix web ci --no-audit --no-fund
.venv\Scripts\python -m placement_assessment.portable --download
npm --prefix web run build
.venv\Scripts\python scripts/serve-placement-candidate.py --port 18892
```

No `DEMODOCTOR_PLACEMENT_REGISTRY` override was used. Both recordings were
assessed by clicking the actual application's Findings control. Existing video
playback, timeline/citation navigation and investigation storage were used.

| Original source | Product result | Evidence |
|---|---|---|
| BF010 | Visible final-placement failure | Frames 2074–2089, 69.133333–69.633333 s; 93–97 px separation; 39 persistent features; median feature-translation diameter 0.0583735555 px |
| BF000 | No supported failure claim | No failure interval; task success is not established by abstention |

Both remain **Assisted**. Original onset and physical cause are Unknown/Unverified;
no grasp, release or 3D placement confirmation. Muse remains `provider_skipped`.
The detector did not receive reference outcomes or failure times. These are
previously exposed development recordings, not new generalization accuracy data.

The clean saved-job video is the verified original, not the bundled lossy H.264
derivative. Original RGB hashes belong only to original decoded frames. The real
bundled derivative was explicitly offered to the import command and rejected with
`Original video size/hash mismatch`, even with correctly provisioned originals
already present. No source-to-derivative substitution/mapping was introduced.

## Verification evidence

- **159 focused Python tests passed** in the clean environment: portable admission,
  source integrity, citations, API security, task criteria and saved reopening.
- **269 React tests passed** with freshly installed dependencies; existing UI
  expectations unchanged. Production TypeScript/Vite build passed.
- **19 Chromium checks passed** in the clean application: exactly two provisioned
  sources; actual button-driven assessments; visible decoded original footage;
  source images/overlays; 69.133333-second seeking via both finding and existing
  timeline marker; refresh/reopen; BF000 control; all six bundled investigations.
  Only two explicit offline assessment POSTs; no provider requests.
- Additional direct assessment denied Python-level opens of the original private
  cache/video/research directories and denied all network connections. Registered
  input paths were independently required to reside within the clean checkout.
  SAM/Muse client entry points were forbidden (no fake outputs supplied).
  BF010 still matched and BF000 abstained.
- Original-file import into a separate empty store passed using the newly
  downloaded public originals. Interrupted download, stale registration, modified
  manifest/template, wrong source and decoder-identity mismatches are rejected.
- Download verification checked **4,180 original frames** across the two videos,
  including native PTS/time bases and every decoded RGB hash. Both are 640×480,
  30 FPS, 2,090 frames. The template reconstructs frame 1260's JPEG95/request key.
- Original ledger SHA remains
  `ffbf0d41454d9262e45aff0ad1f86555acd36ff969c52b68c5545a5ec93ac7ff`.
  Original provider responses and accepted historical jobs were not changed.

Local QA receipts: `qa-browser-artifacts/portable-clean-install/` contains install,
provision, build and test logs; `isolation-results.json`; `derivative-rejection.log`;
and `browser-final/{browser-results.json,ep010-result.json,bf000-result.json,ep010.png,ep010-masks.png}`.
The only acquisition is the two declared public originals; reference labels were
not downloaded. The original full SAM response remains private and immutable;
the public record is explicitly sanitized, not claimed byte-identical to it.

## Reproduce the focused checks

After provisioning, launching, and creating a BF010 saved job:

```powershell
$env:DEMODOCTOR_PLACEMENT_FIXTURE = (Resolve-Path data/live_jobs/YOUR_BF010_JOB_ID).Path
.venv\Scripts\python -m pytest -q tests/test_portable_placement.py tests/test_placement_integration.py tests/test_saved_jobs.py tests/test_saved_provenance.py tests/test_citation_integrity.py tests/test_live_api_security.py tests/test_task_criteria.py
npm --prefix web test -- --reporter=dot
npm --prefix web run build
.venv\Scripts\python scripts/check-placement-browser.py --url http://127.0.0.1:18892 --portable --output qa-browser-artifacts/agent1-portable-check
```

Use a new browser output directory. Mutation tests copy fixtures first. No model
calls are necessary for acceptance. All provisioning instructions use only files
included in the candidate plus the official download URLs.

## Exact correction files

- `.gitignore`, `README.md`, `NOTICE`
- `placement_assessment/portable.py`, `placement_assessment/service.py`
- `placement_assessment/assets/manifest.json`, `placement_assessment/assets/NOTICE.md`
- `placement_assessment/assets/rack/27ae50fe53698423265d1ac9/summary.json`
- `scripts/check-placement-browser.py` (two-source portable QA mode)
- `tests/test_portable_placement.py`, `tests/test_placement_integration.py`
- `docs/integration/PORTABLE_PLACEMENT_SETUP.md`, this report

## Remaining acceptance boundary

The distribution blocker is resolved on the tested Windows/Python 3.12 setup.
Agent 1 must independently accept the frozen correction before staging/merging.
Internet availability is needed for first-time publisher acquisition; exact-file
import is the fallback. Other platforms are not independently tested. Strict
RGB/JPEG identity checks deliberately block decoder/build differences rather than
silently accepting changed measurements. No general autonomous failure-recognition
claim is justified. No further feature development is included.
