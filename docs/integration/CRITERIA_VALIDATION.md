# Criterion integration validation

November 1, 2026. Local `feat/integrated-demo`; no public repository update.

Integration sequence: stable multi-camera checkpoint `bd148db`; independent
review of Claude `3d09778`; additive cherry-pick `43190d2`; local scientific
hardening and product integration. See [review](CRITERIA_REVIEW.md) and
[implemented interface](CRITERIA_INTEGRATED.md).

## Six-recording result matrix

These are separate assessments, not replacements for saved verdicts. Counts
and physical pose are unspecified, so inventory and orientation remain open.

| Investigation | Unchanged saved outcome | Computed location criterion | Physical completion | Important qualification |
|---|---|---|---|---|
| EP003 | Success (recorded 2D criterion) | Supported at sampled frame 2075 | Unverified | Three observed plates inside in 2D; 14 later frames and physical pose unverified |
| EP005 | Uncertain | Unverified | Unverified | Saved flat-orientation suggestion remains Unverified, not a measurement |
| EP010 | Uncertain | Unverified final state | Unverified | Measured gripper source E2 at 44.5 s still inspectable; release remains inferred |
| EP013 | Failure (recorded criterion) | Contradicted at sampled frame 2075 | Unverified | Outside object at that 2D sample; causal mechanism and later recovery unverified |
| EP006 | Uncertain | Unverified | Unverified | Disputed reference remains evaluation-only; no invented final placement |
| PILOT | Uncertain | Unverified | Unverified | No usable tray mask, no joint measurements, 105-frame gap; original historical Muse package stays separate |

No independently measured orientation predicate was added. The evaluation
explicitly counts zero independently identified physical failure mechanisms;
an inferred candidate or abstention is not successful mechanism identification.
See the corrected [evaluation v2](../../data/evaluation/diagnostic_eval_v2/REPORT.md).
Original v1 is retained as an archived, superseded evaluation.

## Executed verification

- Complete project Python suite: **383 passed** in 201.80 s,
  `python -m pytest tests -q` against the final source.
- React suite: **98 passed**, 18 files, `npm test -- --run`.
- TypeScript check and Vite production build: **passed**, `npm run build`.
- `scripts/export-criteria.py --check` and `diagnostic_eval.py --check`: passed.
- Scientific regressions: arbitrary existing citations; stale/negative/future
  frames; frame/camera/object/package/value mismatches; failed verifier;
  unassociated cameras; conflicting views; unspecified count/pose; 2D versus
  physical completion; source-pointer resolution; reference changes leaving
  predictions identical. Original unsafe positive fixtures were corrected to
  supply structured source predicates.
- Final scientific rules, source presentation and mocked workflow subset:
  **105 passed**, including unassessed containment versus missing segmentation.

An unrestricted repository-root pytest invocation initially collected ignored
historical QA checkouts and video tooling, causing duplicate-module collection
errors. `tests/` is the complete project suite; those unrelated artifacts are
not application tests. No frozen files or video tooling were changed to hide
that collection issue.

## Actual gstack browser checks

Used gstack's own Chromium against an isolated QA backend (8797) and production
frontend (4173), with synthetic providers and backend external networking
blocked. The user's normal launcher services were preserved.

- All six recordings: decoded video, computed criteria, Findings/Evidence/
  Unknowns, original source controls, episode navigation and refresh.
- PILOT E0–E5: source details and timed seeking. E2–E4 were also selected and
  inspected at nonzero video times; timestamps stayed unchanged. E5 is timed.
- EP010 E2: actual `motor_deg` source table and 44.5 s seeking, not fabricated
  grasp or release measurements.
- Ordinary one-camera upload: default provider-skipped Dry Run, explicit
  quote/approval with mock providers, computed result, reload without rerun.
- One-, two- and three-panel composite uploads through the same controls:
  confirmed native crop regions, one parent investigation, independent SAM
  operations and one combined Muse call, camera citation identity, reload.
- Three-camera disagreement remained an Unverified hypothesis. No physical
  completion or cross-camera object association was created.
- Camera-specific source inspection showed the original camera/evidence ID
  and matching observation table. Panel collapse/reopen retained assessment
  expansion. Video, timeline and inspector fit at 1920×1080, 1440×900 and
  1366×768; playback/frame stepping continued to work.
- Synthetic SAM failure was visibly reported after exactly one SAM attempt;
  no retry, fallback physical result or follow-on Muse request occurred.
  Its unresolved mock reservation then correctly blocked a new start before
  any provider request. Final successful runs used a fresh **QA-only** ledger;
  the failed-test ledger and user's real ledger were preserved. Real failed
  charges require manual reconciliation, not an automatic paid retry.
- Separate camera files, validated offsets, missing detections, strict
  citation rejection and provider failures are additionally covered by the
  full API/orchestration regressions; no paid calls were used.

Local screenshots and machine-readable receipts are intentionally ignored:
`qa-browser-artifacts/criteria-review/`.

| Screenshot | Shows |
|---|---|
| `ep005-hypothesis.png` | Saved possible flat orientation, prominently Unverified; unchanged uncertain outcome |
| `ep003-criteria.png` | Supported sampled 2D containment with video and timeline |
| `ep003-measurement.png` | Original numerical geometry and resolvable source record |
| `ep010-measured-gripper.png` | Original measured joint source with synchronized footage |
| `pilot-E2-source.png`, `pilot-E4-source.png` | Untimed missing-measurement provenance, no video seek |
| `mock3-camera-source.png` | Three simultaneous views and camera-specific source inspection |
| `provider-error.png` | Visible synthetic provider failure; no automatic retry |

## Preservation and remaining limits

Credential-pattern scan of tracked/intended text files found no candidates or
private environment paths. Frozen experiments, replay outputs, reference
outcomes, original evaluation v1, launcher files and video-production files
match the cherry-picked checkpoint. The user's real budget ledger and original
DROID source hashes match their pre-work baselines. No paid provider request
was made.

Real multi-camera inference remains experimental and has only been exercised
with mocked providers here. Independent SAM outputs and camera-labeled Muse
reasoning are implemented, but no validated physical cross-view associations,
3D reconstruction or physical orientation detector exists. No generalization
or outcome-accuracy claim follows from these tests. The separately documented
[first real experiment](MULTICAMERA_REAL_EXPERIMENT.md) still requires explicit
approval of the video, request plan and budget.

Durable implementation notes: late keyframes are not final frames; same-named
camera tracks are not associated identities; arbitrary citation IDs are not
entailment; optional presentation assets must not prevent replay if unavailable.
