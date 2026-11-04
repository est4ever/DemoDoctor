# Assisted final-placement assessment

This optional offline feature computes a narrow, source-backed finding in the existing DemoDoctor investigation workstation. It is **assisted final-state detection**, not general autonomous failure recognition or failure-onset localization.

## Install and use

Follow [portable setup](PORTABLE_PLACEMENT_SETUP.md). Explicitly provision the two original publisher recordings once, using the pinned downloads or exact original-file import. No credentials, developer cache, historical jobs or private registry are needed. The existing six bundled replays still work without this optional download.

Open EP010, select Findings, and click **Assess final placement offline**. The original recording opens in a new saved investigation. Select BF000 development recording to run the control. Source frames, masks, numerical measurements and uncertainty remain inspectable. The finding and timeline seek the original source footage. Refresh or reopen from Recent Investigations without repeating the calculation or calling a provider.

The packaged template is a sanitized subset of a genuine SAM rack response, not fresh inference. Source hashes, original frame 1260, its reconstructed JPEG request and the unchanged mask establish its provenance. A fixed green-plate appearance prior assists object classification. Each assessed frame requires its own pixel-based rack registration; failed registration abstains. No reference outcome, final object coordinates or failure timestamp is supplied to the detector.

## Observed development results

| Recording | Result | Evidence interval |
|---|---|---|
| BotFails EP010 / BF010 | Plate-like green region visibly outside the registered rack at recording end | Original frames 2074–2089; 69.133333–69.633333 seconds |
| BotFails BF000 | No supported failure finding; abstention does not prove success | No failure interval |

The BF010 minimum lateral separation is **93 pixels**, with a per-frame range of **93–97 pixels**. There are **39 persistent features**. The **0.0583735555-pixel** componentwise-median translation diameter is not a maximum displacement of every feature, a calibrated physical measurement, or an absolute error bound. Original images visually corroborate the far-right plate outside the rack; 2D separation alone is not a general 3D containment test.

The final half-second is selected from native timestamps. This is the time of **final-state failure evidence**, not the earlier onset. Onset is **Unknown**. Physical cause, contact, grasp, release and calibrated 3D containment remain **Unverified**. Overall physical-task outcome remains **Uncertain**, separately from the narrower visible-placement contradiction. Possible causes and confirmed physical events are empty.

Muse is **provider_skipped** for this computation. The new deterministic explanation cites new measurements; no historical Muse response is claimed to have received them. Arbitrary uploads cannot automatically receive this task-specific classification.

The [BF010 result](placement-results/ep010-result.json) and [BF000 result](placement-results/bf000-result.json) are historical product-development receipts, not detector inputs. Their job IDs are local run identifiers, not public links. Fresh assessments create their own jobs. These two previously exposed development recordings do not establish held-out accuracy, event F1, onset accuracy or general failure-diagnosis reliability.

## Integrity and distribution

- Original measurement videos are provisioned from the publisher or verified user files. They are not committed to Git. The bundled lossy display re-encode cannot substitute for an original.
- Both original byte hashes and complete native frame/RGB index digests are pinned. The packaged manifest and template have separate pinned hashes. See [asset notices](../../placement_assessment/assets/NOTICE.md).
- Default portable registration is relative to the checkout. Optional legacy registry overrides require an explicit path and approved digest; the browser cannot submit paths, ROIs, source observations or event intervals.
- New jobs have a local HMAC seal covering the complete artifact set, source video/index, template receipt, masks, measurements, images, result and citations. Added, missing or altered artifacts are quarantined across history, reopening and media/evidence access.
- Back up the local assessment key together with saved jobs. Losing it prevents trusted reopening. This mechanism does not protect against a local administrator replacing the server, key and records.
- Original provider outputs, billing records, six bundled investigations and source recordings are not rewritten. The API is for localhost use, not an authenticated public Internet service.

## Independent acceptance, November 4, 2026

Candidate `cbbfdd54f538e8f780b48f5c211c430a5689452b` was exported from tracked files into a fresh directory. A new Python environment installed `requirements-lock.txt`; `npm ci` installed the committed frontend lockfile. Both pinned public videos downloaded successfully. No private cache, developer registry or historical job was copied.

- **159 focused Python tests passed**, with no skips: portable setup, new real-artifact assessment, saved jobs, provenance, citations, API security and task criteria. The fixture was generated by the clean app itself.
- **269 React tests passed**; production build passed.
- **19 Chromium checks passed** on the actual built app, including both explicit offline assessments, decoded original video, frame-2074 seeking, timeline interaction, source/overlay images, refresh/reopening, and all six existing investigations. No provider operations occurred.
- Independent checking reproduced all 16 evidence-frame hashes/timestamps and the 93–97 pixel measurements. Both complete 2,090-frame source indexes validated. All 50 protected original records retained their hashes.
- Supplying the actual bundled derivative to the original-file importer exited with an explicit hash-mismatch rejection.

The clean-run server blocked external connections and access to development/private dataset roots. This establishes a portable Windows test, not cross-platform or exhaustive security/accessibility certification. Other browsers and decoder environments remain untested; do not relax source hashes if a different decoder changes pixels.

## Reproduce focused checks

After portable setup and one new BF010 assessment, from the checkout root:

```powershell
$env:DEMODOCTOR_PLACEMENT_FIXTURE = (Resolve-Path data/live_jobs/<your-new-placement-job-id>).Path
.venv\Scripts\python -m pytest -q tests/test_portable_placement.py tests/test_placement_integration.py tests/test_saved_jobs.py tests/test_saved_provenance.py tests/test_citation_integrity.py tests/test_live_api_security.py tests/test_task_criteria.py
npm --prefix web test -- --reporter=dot
npm --prefix web run build
.venv\Scripts\python scripts/check-placement-browser.py --portable --url http://127.0.0.1:18890 --output qa-browser-artifacts/placement-review
```

Use a new browser output directory. Start the server using the portable guide before the browser check. Chrome and Python `websockets` are QA requirements, not new application dependencies. Artifact mutation tests copy the supplied fixture; they do not rewrite original jobs. Missing real-artifact fixtures skip explicitly instead of counting as passing.

The published README videos remain accurate demonstrations of their recorded versions; neither is a recording of this new final-placement feature. Public publication still requires the owner's explicit approval of the final staged commit.
