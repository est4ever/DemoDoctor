> Historical local audit. Private QA receipts and optional original reference inputs are intentionally excluded from this public snapshot; their names below document provenance, not downloadable assets. Current release verification is in docs/submission/FINAL_UPDATE_20261101.md.

# Diagnostic coverage audit — all six investigations

Assessed November 1, 2026. Starting integrated revision: `097f8e1e6509b512886fc8eebe564007758bb759`.
Status: **complete with documented limitations**. Presentation repairs only; no new inference or failure detector.
The separate public candidate remains clean at `35b00505608db9f975a13414dc8e4998238bb82d`; this audit and its additional fixes are **not** copied into it or published.

## Conclusions

All eight saved hypotheses and fifteen visual interpretations from the five cached evidence-grounded Muse responses now appear in Findings, verbatim, as **Unverified**. Their explanations, factual-claim text and limitations also survive the export. No additional cached hypothesis-text omission was found. The exporter adds a `label: hypothesis` field; this explains a literal-object comparison difference, not missing model content.

This does not establish broad failure-diagnosis accuracy. EP010 reconstructs an **inferred** release outside the target; EP013 identifies an outside-object end state but not a timed drop cause. EP005 exposes the existing orientation hypothesis, without verifying it. EP003's success is a narrower recorded 2D criterion. EP006 has conflicting reference interpretations. PILOT has two checked image-space claims, not a verified grasp/release or task outcome. Abstention is not counted as failure identification.

Three presentation defects were reproduced and repaired: the loss of EP003/EP013's explicit end-state-support classification; EP010's omitted original frame-reference metadata; insufficient distinction between saved reference-context notes and pipeline findings. All frozen outputs, verdicts and original citations remain unchanged.

## Method and evidence boundaries

- Fully decoded all five original BotFails MP4s: 2,090 frames each, 30 FPS, last source frame 2089 at 69.633333s. Their original SHA256 values match the distributable manifest's source hashes. Reviewed distributed five-second samples, task-relevant intermediate frames, frame 2075 and the actual last frame. This is sampled visual review plus complete decoding, **not** a claim that every instant was manually watched or annotated.
- Inspected the true original authorized PILOT video: 737 frames, 30 FPS, SHA256 `bd3f7a4df11b9249f7ac5c2473aef44c6da9f2c06c01534ab11062e5457b5018`. It matches the manifest's original source hash. Its compact public re-encoding has a different hash (`8369c23f…`), intentionally; it is not claimed byte-identical. Reviewed both endpoints, gap boundaries and the final arrangement.
- Read local task definitions, dataset task-band metadata, local visual-reference annotations, reconstructed reports, original raw/parsed/validated Muse outputs, independent verifier outputs and current replay JSON. Checked both original and reconstructed PILOT contexts separately. Original private jobs were read-only inputs.
- Decoded **2,883 saved BotFails masks** across eight requested windows: all nonempty, no missing frames inside those windows. This establishes returned segmentation coverage, not correct instance identity, physical pose or task success. Outside selected windows, lack of tracking remains lack of evidence.
- Used an isolated gstack Chromium profile against the integrated offline app at localhost:5173/8765. No credentials entered, services restarted or provider operations requested. Actual clicks, video decoding/playback, source details, seeking, resize controls and refresh were checked. The public checkout was read-only throughout.
- Local visual annotations are references, not motion-capture ground truth or independent verifier measurements. Dataset anomaly flags/bands alone do not establish task outcome. No reference file is used by the new presentation helpers to produce a prediction.

Core sources: [task specification](data/tasks/botfails_dish.json), local visual references (original local receipt/input not distributed: `data/experiments/expanded_eval_prep/VERIFIED_OUTCOMES.json`), [EP010 event reference](data/event_labels.json), [dataset task-band metadata](data/lerobot/kantine__BotFails/test/domotic_dishTidyUp_anomaly/meta/tasks.jsonl), [recorded source configuration](demo_replay.py), source inventory (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/original-source-inventory.json`), mask audit (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/sam-cache-audit.json`), original video review (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/video-review.json`), original PILOT video receipt (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-original-video.json`).

## Outcome, mechanism and verification matrix

“Checked claims” below means the independent numerical/event-claim verifier, not successful JSON parsing or acceptance of model citations. Held-out end-state geometry is a saved rule assessment; zero checked event claims is not proof of orientation, nor proof that no physical failure occurred.

| Episode | Task and documented reference | Displayed prediction | Visible/reference failure or behavior | Reconstructed mechanism | Independently checked claims | Missing evidence / conclusion boundary |
|---|---|---|---|---|---|---|
| EP010 | Store dishes in rack. Local `event_labels.json`: verified visual reference **failure**, no exact first-mishandling frame; dataset band describes dropping | **Uncertain**, unchanged | Plate visibly moves/lifts then rests outside at ~45s; plates remain outside at the true end | One `released_outside_target` / `dropped_in_transport` event, **inferred**, frames 1293–1351 (end exclusive), 43.1–45.033s | **3 supported**: ~85.87px displacement, 31 outside-rest observations, measured opening frame1335 / 44.5s | Only 121 tracked frames in selected window; no proven holding/intent/contact; complete final placements not reconstructed. Abstention misses definitive final failure, although one plausible mechanism is localized |
| EP005 | Store dishes in rack. Local sampled-video visual reference **orientation failure**; dataset wrong-way band is corroborative, not the decision | **Uncertain**, unchanged | At F2075 AND F2089 plates lie face-on/lean across the rack rather than separately upright in slots; intermediate placement is not alone final proof | No physical events. End regions unknown/unknown/unknown. Existing Muse flat-orientation candidate only | **0 event claims checked** across both windows; historical model/citation validation accepted | No independent orientation predicate, gravity/slot pose, complete inventory or broad temporal reconstruction. This is **not** successful orientation-failure identification |
| EP003 | Local visual reference **success**; normal/expert band. Final plates appear upright in slots with other dishes in rack | **Success under recorded 2D criterion**, unchanged and now visibly qualified | No task failure apparent in sampled sequence/endpoints; does not prove no transient failures anywhere | No timed events; end regions inside/inside/inside; end-state-supported assessment | **0 event claims checked**; saved end-image geometry supports narrower 2D assessment | Orientation and full required-object inventory not independently measured. Do not equate 2D containment with complete physical-task certification |
| EP013 | Local visual reference **failure/incomplete placement**; dropping band does not establish the causal mechanism | **Failure under end-state outside-object criterion**, unchanged | One plate remains on table at F2075/F2089, two in rack | No timed drop event; end regions unknown/inside/outside; outside plate supports incomplete placement | **0 event claims checked**; saved end-image rule assessment | Cannot distinguish never-placed from placed-then-displaced, exact drop time, or causal grasp/release. Outcome supported; causal diagnosis incomplete |
| EP006 | Local visual reference says **success** (medium-high confidence); dataset band suggests wrong-way. **Reference conflict requires adjudication** | **Uncertain**, unchanged | Objects end in/near rack; several plate faces are visible/leaned. This single view does not independently settle correct slot orientation | No timed events; end regions unknown/unknown/inside | **0 event claims checked** | Geometry insufficient; local reference is not an unquestionable gold label. No failure identified; abstention is not credited as a correct mechanism diagnosis |
| PILOT | Place screwdriver in white tray. No independent binary outcome annotation in retained package; original pipeline/Muse uncertainty is a prediction, not reference truth | **Uncertain**, unchanged | Screwdriver appears on right initially and within tray at end; gripper occludes the relevant interval | Observed **image-position change only**, not physical release | **2 image-space claims checked** in later reconstruction; original package checked **0** event claims | 632/737 observed frames; gap433–537 inclusive; no usable tray mask; no measured joints/holding; identity across gap and placement unverified. Apparent visual placement is not a verified task-success measurement |

## Saved model diagnostics versus interface matrix

H = hypotheses; V = visual interpretations. Counts exclude experimental Muse-only baselines. All current-package H/V remain unverified; evidence/frame references are contextual provenance, not verification of the hypothesis itself.

| Episode | Saved H / V → displayed H / V | Main saved diagnostic candidates | Original bindings and source inspection | Omission / false-promotion assessment |
|---|---|---|---|---|
| EP010 | 1 / 2 → **1 / 2** | Intentional release vs unintended drop; apparent mid-air movement | Hypothesis E0/E1/E2. **Fixed:** original F0–F3 metadata retained in pilot_report was absent from replay frame_catalog. F0=1293/43.1s, F1=1335/44.5s, F2=1350/45s, F3=1380/46s; direct F0/F1 controls tested | No remaining H/V text loss. All Unverified; measured opening remains distinct from inferred release |
| EP005 | 2 / 4 → **2 / 4** | Possible placement attempt; geometry inconclusive OR incorrectly oriented flat | E7/E5 and E4/E3/E1; F0=1607, F1=1637, F2=1726, F3=2075. Untimed E3 opens source and keeps playback | All original candidates visible. The local reference note is identified as saved/reference context, not a detector prediction |
| EP003 | 2 / 3 → **2 / 3** | Opening may correspond to release; inside in 2D could still be wrong orientation | E5/E7/E4 and E3/E4; explicit F0/F1/F3 references tested | **Fixed:** `supported_by_end_state` was incorrectly grouped as Uncertain. It is now End-state supported, never Observed/verified orientation |
| EP013 | 2 / 4 → **2 / 4** | Never placed vs displaced later; unknown plate might be occluded/at edge | E4/E6 and E4; F0–F3 tested; E4 seeks end frame2075 | Same end-state label repair as EP003. No invented drop cause or onset |
| EP006 | 1 / 2 → **1 / 2** | Apparent placement 50–54s not a verified release | E5/E7/E4; F0/F1 tested | No H/V omission or promotion. Local-success/band conflict remains an evaluation problem |
| PILOT | Current 0 / 0 → **0 / 0**; historical 1 / 3 available in explicit original-analysis link | Historical pick/place possibility and three visual impressions | Historical E0 means unavailable joints; current E0 means endpoint difference. These remain separate. All three historical artifact links returned valid original-context data | Intentional package separation, **not** missing current Muse output: no Muse response exists for the reconstruction. Historical H/V are available as JSON, not rendered inline in the current Findings list; discoverability limitation remains |

All cached `muse_explanation`, `factual_claims` and `limitations` arrays match their original parsed model responses. They are accessible in the model-explanation section and Unknowns respectively. Original grounded citation-validator `ok=true` means the historical output passed that validator; it does **not** independently validate every visual assertion. Experimental Muse-only baseline summaries for non-highlighted episodes are not all rendered inline; they are different experimental contexts, not current verified findings. EP005's visible comparison remains illustrative, not a controlled scientific ablation.

## Episode-specific observations and failure coverage

### EP010

The visible attempt includes lifting/moving a green plate and subsequent rest on the table outside the rack, followed by further attempts that do not clear the plates by the final frame. F1293 (43.1s), F1335 (44.5s), F1350 (45s), F1380 (46s) support the bounded event narrative; F2075 and F2089 support the separate final incomplete-task visual assessment. The three checked claims support numerical motion/rest/opening, not physical identity/contact or intent. The current whole-task Uncertain verdict is conservative relative to the visual failure reference, because the saved reconstruction is window-limited. It must not be described as a correct whole-task verdict or a proven accidental drop.

The original saved F1 visual text still says “appears … mid-air.” It is visible as Unverified. Restoring a clickable F1 source does not upgrade that visual interpretation. The original package-derived catalog is bound to the exact recorded EP010 video, development context and measured-gripper source, and never used for another video or PILOT.

### EP005

At F1392/1422 a plate is still being handled; those frames alone do not establish final failure. F1511 shows an early low/face-on arrangement, but recovery remains possible. F1800 lies outside the two tracked windows and includes later handling. F1950, F2010, F2075 and F2089 retain the wrong-way final arrangement. Both video windows have complete returned detections/masks (720 in total); insufficient final inside/outside geometry is not the same as a provider failure.

The rule only consumes 2D position/size/containment, not independently verified orientation or slot engagement. `botfails_dish.json` declares all_objects_in_target, expected count unset, plates only; cups/whisk are explicitly outside its tracking scope. The saved Muse-only model incorrectly describes upright success (0.68); grounded Muse proposes flat orientation without establishing it. Displaying that hypothesis improves explanation coverage, not detector accuracy. The curated “visual ground truth” note originates in the exporter, not the inference result.

### EP003

F1845/1875/1964 show the last placement sequence; F2075 and F2089 show three narrower edge-on plates standing in the rack with other dishes present. That supports the local visual success reference. The saved inside/inside/inside result is a narrower geometric assessment with an approximate calibrated interior, not independent 3D orientation verification. The former Uncertain group label for this explicitly end-state-supported finding was a presentation error; the saved verdict and 2D rule were not changed to repair it.

### EP013

F1498–1617 shows the selected window, including a measured opening and later whisk handling; it does not establish a timed plate-drop event. One plate remains outside through F2075 and F2089. Detecting this final outside plate is a meaningful incomplete-placement finding. “Never placed” and “placed then displaced” remain alternative unverified hypotheses. The dropping dataset band does not select between them. Empty reconstructed-event catalogs do not prove there was no physical failure.

### EP006

F1500/1530 and F2075/F2089 show plates being placed and later in/near the rack. The local annotation calls the final state successful, whereas task-band metadata calls episodes5–9 wrong-way. Several final faces are prominent/leaned; exact correct orientation/slot engagement cannot be adjudicated from the retained single view in this audit. The human reference is therefore flagged as a disputed evaluation label, not fed into prediction or silently “corrected.” Its all-objects final geometry remains unknown/unknown/inside. Neither false-negative failure diagnosis nor correct success diagnosis can be established against an unresolved reference definition.

### PILOT

The authorized source and compact replay preserve 737 frames at 30 FPS. SAM returned 632 detections and no usable white-tray segmentation. The numerical endpoint calculation (~609.01px) compares returned boxes at frames0 and736; it is not measured continuous physical travel across missing frames433–537. The video itself still contains images during that interval: “unobserved” here means missing returned SAM object observations, not missing video frames. Gripper occlusion is visually plausible, not a verified sole cause for every absent detection.

The original paid Muse response has one hypothesis and three visual interpretations, matching historical-analysis exactly. Original E0–E3 remain bound to the original package. The later two-claim reconstruction was not sent back into Muse. Its current empty hypothesis list must stay empty; grafting historical hypotheses onto current E0–E5 would corrupt provenance. Historical raw links are explicit and working. Inline historical-context rendering could be a later usability improvement with separate citation handlers, not a reason to merge contexts now.

## Scientific coverage by mechanism

| Coverage dimension | EP010 | EP005 | EP003 | EP013 | EP006 | PILOT |
|---|---|---|---|---|---|---|
| Outside-target location | Supported window rest, not full final catalog | Unknown end geometry | Inside 2D | Outside plate supports final failure | Partial unknown geometry | Unsupported containment: destination mask absent |
| Physical orientation | Unassessed | Hypothesis only | Visually plausible; unverified by pipeline | Unassessed | Reference disputed; unassessed | Unassessed |
| Grasp/release | Opening measured; release inferred | Opening measured; release not reconstructed | Opening measured; release hypothesis | Opening measured; no plate release event | Opening measured; release hypothesis | No measured joint/gripper signal |
| Complete required-object inventory | Not established | Not established | Not independently established by plate-only task | One required plate outside suffices for narrower failure | Not established | Expected count/final inside unknown |
| Full temporal/causal reconstruction | 121/2090 sampled frames | 240/2090 + end image | 240/2090 + end image | 120/2090 + end image | 240/2090 + end image | 632/737 detections, 105-frame gap |
| Incorrect VLM statements | Intent/mid-air remain unverified | Muse-only upright-success false relative to reference | Model visual pose is not independently checked | Drop causality not resolved | Competing reference interpretations | Historical visual placement is not verified containment |

## Confirmed presentation defects and repairs

| ID / severity | Exact cause and reproduction | Applied correction | Regression evidence |
|---|---|---|---|
| DC-01 / P2, fixed | `findingGroups` sent every non-observed/non-inferred status to Uncertain. Open EP003/EP013 Findings: saved supported_by_end_state item appeared under Uncertain while header said Success/Failure | Separate End-state supported group and explicit 2D-only qualification in group/header; no verdict/record mutation | Helper test plus both real-App source/seek tests; original EP003 reproduction replayed after fix |
| DC-02 / P2, fixed | EP010 export's frame_catalog is empty although `pilot_report.json#package.frame_refs` retains F0–F3. Saved visual F0/F1 showed unavailable references | Read-only, narrowly bound presentation catalog copied exactly from that saved package, with original provenance displayed and wrapping; no timestamp guessed from prose | Original fixture equality, wrong-episode/video/dry-run guard tests, App F1=44.5s test, real-browser F0/F1 seeks |
| DC-03 / P2, fixed | Unknowns combines curator-inserted reference context with uncertainty notes, without identifying the source distinction. EP005's orientation-reference line could look like a pipeline finding | General saved-note/reference-context disclosure; retained exact source text and Uncertain verdict; reference text stays out of Findings | App regression on reference context and unchanged verdict; Unknowns checked in all six episodes |

Files: [presentation groups](web/src/lib/evidencePresentation.ts), [recorded frame provenance](web/src/lib/diagnosticFrameCatalog.ts), [diagnostic renderer](web/src/components/DiagnosticDetails.tsx), [workstation](web/src/components/InvestigationDesk.tsx), [CSS](web/src/workstation.css). These helpers read no ground-truth outcome files and add no event or claim to a scientific record.

## Remaining confirmed issues and non-defect limitations

| Item | Classification | Evidence / impact / recommendation |
|---|---|---|
| EP010 timeline marker overlap | Existing confirmed **P2 UI defect**, left unchanged | Actual hit testing at 1280x720 targets Rest outside target at the center of Measured gripper open. Keyboard activation and E2 both seek correctly. Original public snapshot already documented this. Give clustered markers separate hit targets in a separately scoped repair; retain source/keyboard workaround |
| Held-out numeric SAM source availability in inspector | Confirmed **P2 presentation/data-availability gap**, not invented data | EP003/005/006/013 do not load tracks.json for the inspector. Source details explicitly say matching frozen SAM observations were not loaded; catalog text and recorded SAM overlays remain available. Original mask caches were separately inspected here. A future reviewed, sanitized read-only source export can expose detailed calculations; this audit does not change data or backend serving |
| Historical DROID missing optional tracks artifact | Confirmed **P3 legacy-job issue**, left unchanged | Loading the old job requests `/api/jobs/.../tracks`, returns404, and produces one resource console error. App remains usable and correctly provider-skipped. New dry runs write empty track metadata; do not mutate this historical job to hide the limitation |
| PILOT historical H/V only via explicit JSON links | **P2 discoverability limitation**, package separation intentional | All links work; no silent rebinding. Potential future inline historical view needs its own source/citation context, not reuse of current IDs |
| EP006 reference conflict | **Evaluation limitation**, not a confirmed wrong prediction | Obtain independently adjudicated task/slot criteria and final-state annotation. Do not use the band or local success flag as unquestioned gold |
| Orientation, grasp/contact, drawer closure, complete inventory | **Scientifically unverified capabilities** | No independent predicates/sensors for these. Display gaps and abstain; a new detector requires a separate reviewed study |
| Development dependency advisories | Previously confirmed **publication concern**, not re-scanned here | The separate public update report records unchanged Vitest/tinypool critical package advisories. This audit does not repair dependencies or clear that publication decision |

No new P0/P1 evidence-promotion defect was reproduced in the exercised current views. This is a bounded audit, not proof that no unknown bug exists. Unsupported Muse interpretations remain prominently unverified, rather than promoted to observations or final verdicts.

## New-video and DROID support — separate from replay

The existing DROID job `data/live_jobs/20261031T233708Z_5816831d` records task “Pick up the blue block, place it in the open drawer, and close the drawer.” Both uploaded/prepared composite files hash to `eaec1033f19cf7fce385b0a120fa80edda4d78a9a171cb9462a0af5351961f53`: 3872x736, 158 frames, 15 FPS, last timestamp10.466667s. Request has dry_run=true, run_muse=false, complete_demonstration=false; selected window0,60), first four seconds. Status explicitly records SAM-video and destination dry-run skips. No Muse, evidence-package or real SAM-track artifact is present. Analysis has zero observed/inferred/physical events and Uncertain outcome. Its `verification.ok=true,dry_run=true` is not two/three verified physical claims. The actual UI displays **Dry run · SAM/Muse not executed**, not successful inference.

The existing derivative crop is x=2584,y=8,w=1280,h=720 (rightmost stationary view), hash `78bce58e59109b85bfebc5e72db04092aa9182cf6327968bd097a7db91c28f22`. All 158 frames and i/15 timing are retained with zero time offset; lossy H.264 re-encoding and burned-in axes are disclosed. Redistribution rights for this user-supplied DROID input remain unestablished; media stays private/ignored. A collection success label is not an independently established task reference.

**Self-service Real Analysis is implemented**, not unavailable or dry-run-only. Existing Import Footage can prepare a video/estimate, obtain a file-bound single-use expiring approval, run the existing SAM object-video + destination-image + reconstruction + verification + Muse path, show progress/errors, then open/recover the actual job workstation. Backend-only provider configuration, loopback/origin/path guards, ledger checks and zero automatic paid retries remain. Relevant Python/React tests ran with synthetic providers; they test real workflow state transitions, failures and no mock substitution after failure, not model accuracy.

Ordinary DemoDoctor intentionally starts offline. One-time explicit `-RealAnalysis` startup, valid Meta/Fireworks configuration and an adequate ledger cap are prerequisites; each subsequent video is operated in UI. Configuration presence does not prove account authentication or credit. Current default $1 cap is below the $1.32 Muse reservation before SAM; the existing owner-reviewed first-four-second crop plan estimates $1.3345 using configured admission rates, not a provider-enforced billing guarantee. No opt-in or paid/provider request was executed here.

The pipeline's task outcome is still bounded by all_objects_in_target with an uncalibrated raw destination footprint and stationary-camera/target assumptions for new video-only inputs. It cannot certify drawer closure, arbitrary language goals, orientation or physical release. Therefore a completed DROID job would not by itself establish this full task succeeded. The remaining missing capability is **validated scientific coverage/generalization**, not the self-service UI connection. Release wording must distinguish replay, dry run, mocked real-workflow tests, and an actually approved fresh real-provider experiment.

## Browser/test results and screenshot evidence

- Complete Python suite: **284 passed**, 189.55s. No frozen result changed.
- Frontend: **74 passed**, 13 files; production TypeScript/Vite build passed after final presentation changes.
- Native gstack checks: Findings, Evidence and Unknowns in all six; **42 source entries** (21 untimed), 8 hypothesis source-control activations, 15 explicit visual-frame controls; all valid original references retained. PILOT's untimed E2–E4 preserved a nonzero frame after seeking F736.
- All cached model explanation/factual-claim sections expanded and checked against saved text. All Unknowns/limitations checked. Criterion coverage opened in all six, keeping unassessed orientation and missing evidence explicit.
- Right-panel keyboard resizing + width persistence on refresh, left-panel keyboard resizing, independent collapse/reopen/source preservation, actual playback advancement/pause, one-frame button activation and keyboard timeline seeking checked for every episode. Mouse-marker overlap is separately reported above, not passed.
- Route/source binding was validated at each navigation with its own fetched episode catalog. Refresh restores correct episode and saved width; it need not retain the previous active evidence/time (the existing initial-selection policy remains).
- Geometry checks at 1366x768, 1440x900, 1920x1080: video, timeline and selected evidence inside viewport, no vertical page overflow. Six-tab audit screenshots initially use the isolated browser's1280x720 desktop size; later source/viewport screenshots use their recorded sizes.
- Six-recorded-episode flow had no console errors. Loading the historical DROID job later produced the one expected missing-tracks404, explicitly retained above. No global “zero errors” claim is made for that combined flow.
- Early harness failures (missing EP010 expected frame catalog, ambiguous selectors, stream metadata after container close, wrong npm cwd) were corrected or used to identify the real omission; no failed attempt is counted as a pass. Native action receipts remain preserved.

| Episode | Findings | Evidence | Unknowns |
|---|---|---|---|
| EP010 | [Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep010-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep010-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep010-unknowns-final.png`) |
| EP005 | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep005-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep005-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep005-unknowns-final.png`) |
| EP003 | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-unknowns-final.png`) |
| EP013 | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep013-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep013-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep013-unknowns-final.png`) |
| EP006 | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep006-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep006-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep006-unknowns-final.png`) |
| PILOT | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-findings-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-evidence-final.png`) | Open (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-unknowns-final.png`) |

Focused evidence: EP005 orientation hypothesis (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep005-orientation-current.png`), EP003 incorrect label before (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-before-end-state-label.png`), EP003 corrected label (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-after-end-state-label.png`), EP010 restored F1 and original source (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep010-original-source-wrapped-seek.png`), DROID provider-skipped UI (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/droid-existing-dry-run.png`), PILOT historical source links (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-historical-source-links.png`), 1366 viewport (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-scope-1366x768.png`), 1920 viewport (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/ep003-scope-1920x1080.png`).

Durable detailed results: native browser command log (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/browser-evidence.jsonl`), six-episode result matrix (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/six-browser-results.json`), panel preservation (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/extra-panel-results.json`), DROID provenance audit (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/droid-audit.json`), original PILOT Muse comparison (original local receipt/input not distributed: `qa-browser-artifacts/diagnostic-coverage-20261101/pilot-original-muse-check.json`). Local QA artifacts and private media are ignored, not publication contents.

## Recommended regressions and next decisions

Added: explicit end-state-support grouping without record mutation; actual EP003/EP013 source inspection and end-frame seeking; reference-note disclosure without promoting EP005 reference text; EP010 frame metadata equality to original package; package/episode/video/dry-run isolation; actual App F1 seeking while retaining Unverified status. Existing diagnostics tests continue to cover all saved H/V, absent/orphan references, missing citations and cross-episode navigation.

Before publication: review this audit and its frontend diff, decide separately whether to repair the known marker overlap and dependency advisories, adjudicate EP006 before making accuracy claims, and reconcile the **separate** public candidate with any subsequently approved integration fixes. No update to that public candidate was authorized or performed in this audit. Do not rerun paid providers to fill display gaps. A genuinely unseen, rights-cleared video experiment needs exact input/request/budget approval and separate tracking/claims/citation/abstention/outcome evaluation.

## Exact saved hypothesis and visual-interpretation appendix

The following is original grounded model text, not new detector output. Every entry is displayed as **Unverified**. Identical labels/text across episodes do not confer common object identity.

### EP010 saved diagnostic text

- H1: The opening at 44.5s may correspond to an intentional release or an unintended drop, but the pipeline does not establish intent; release is inferred from opening together with coming to rest outside target. Sources: E0, E1, E2.
- V1 (F0): F0 shows the red arm with gripper apparently over a green plate on the table near the dish rack. F1 shows a green plate in motion/blur near the rack edge while the gripper appears open. F2-F3 show a green plate at rest on the table outside the rack.
- V2 (F1): F1 appears to capture the plate mid-air during the transport, consistent with the inferred movement interval, but depth and contact are not verified by the pipeline.

### EP005 saved diagnostic text

- H1: The arm may have attempted to place a plate in the rack between 53.5-57.5s, but without a reconstructed release event this remains speculative Sources: E7, E5.
- H2: Final plates appearing in/near rack could be inside but geometry was insufficient to confirm, or could be incorrectly oriented flat Sources: E4, E3, E1.
- V1 (F0): F0 appears to show red gripper holding a green plate above the dish rack
- V2 (F1): F1 appears to show gripper positioned over rack with a green plate partially in rack
- V3 (F2): F2 appears to show gripper contacting a green plate on the table outside the rack
- V4 (F3): F3 appears to show three green plates in/around rack at end of episode

### EP003 saved diagnostic text

- H1: The measured opening at 62.5s may correspond to a release of a plate into the rack, consistent with plates being inside at end-state, but this is not verified as a physical release event by the pipeline. Sources: E5, E7, E4.
- H2: Plates appearing inside in 2D could still be incorrectly oriented (e.g., lying flat) which the pipeline explicitly does not verify. Sources: E3, E4.
- V1 (F0): F0 (61.5s) appears to show the red gripper holding a green plate above the rack; F1 (62.5s) shows the gripper near the rack with plates visible inside; F2-F3 show the gripper retracted with three green plates standing in the rack. These are visual impressions only, not verified physical events by the pipeline.
- V2 (F1): F1 corresponds to the measured gripper opening window, visually consistent with a placement action, but the pipeline states opening alone is not a drop and holding is not detectable.
- V3 (F3): F3 end-state view shows three green plates inside the rack footprint, matching the SAM inside regions, but 2D containment does not confirm upright orientation.

### EP013 saved diagnostic text

- H1: The plate observed outside at end-of-episode may have never been placed in the rack, or may have been placed and then displaced; pipeline provides no verified physical event to distinguish. Sources: E4, E6.
- H2: The unknown-region plate may be partially occluded or at rack edge causing insufficient geometry for inside/outside determination. Sources: E4.
- V1 (F0): F0 (49.933s) appears to show robot arm over dish rack with two green plates already in rack and one green plate on table; no gripper object clearly visible.
- V2 (F1): F1 (50.933s) corresponds to measured gripper opening; visually gripper appears open/empty above rack.
- V3 (F2): F2 (53.9s) appears to show robot holding green whisk over table, not a plate.
- V4 (F3): F3 (69.167s) end-state appears to show two plates in rack, whisk in rack, and one green plate on table outside rack, consistent with outside detection.

### EP006 saved diagnostic text

- H1: Apparent placement of a plate into the rack between 50-54s may have occurred but was not verified as a physical release event by the pipeline Sources: E5, E7, E4.
- V1 (F0): In F0-F2 the red arm appears to move from above the rack toward a green plate on the table, and in F3 multiple green plates appear in/near the rack; this visual impression is not verified as a successful placement by the pipeline
- V2 (F1): F1 corresponds to the measured gripper opening at 51s, but the image alone does not confirm grasp or release
