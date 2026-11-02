# Architecture

```text
Robot video ── SAM 3.1 ── observed masks/boxes/track IDs ─┐
Optional paired LeRobot joints ── measured gripper ────┤
                                                     ▼
                 failure_inputs → deterministic event/outcome rules
                                                     ▼
                      verification → evidence package and E IDs
                                                     ▼
                       Muse Spark Open via Fireworks
                         constrained, cited explanation
                                                     ▼
             recorded JSON/video → React investigation desk
                camera ↔ timeline ↔ evidence inspector
```

New inference and recorded replay are distinct execution paths:

The diagram is the general evidence-grounded analysis path. It does not describe
the provenance of the later SO-101 reconstruction: that offline endpoint/coverage
package was never fed into the original Muse response. Original pilot citations
remain bound only to the original package.

- **Submission replay:** tracked compact videos, recorded analysis/catalogs,
  and numerical tracks. Loading or seeking a replay initiates no provider calls.
- **PILOT read-only API:** FastAPI serves the sanitized packaged `before` and
  `after` contexts. Environment path overrides are optional maintainer tools.
- **Upload UI:** Dry Run is the default (`dry_run=true`, `run_muse=false`).
  Explicit local Real Analysis opt-in enables prepare/quote, followed by an expiring,
  file-bound, single-use approval. That executes the existing SAM tracking, destination
  segmentation, reconstruction, verification and Muse path. Browser readiness exposes
  configuration booleans only. Ledger admission, origin/host/path guards, zero paid
  retries and stop-on-provider-failure remain enforced. Reload recovers the same job.
- **Diagnostic presentation:** current-package saved hypotheses/visual interpretations
  remain Unverified and separate from observed/inferred findings and outcomes. Coverage
  shows available assessments and gaps, without adding unstated task criteria.
- **Optional Rerun:** lazy loads its viewer only when requested, using the
  separate recorded ep010 event window. It is never reused for the SO-101 pilot.

Main modules: `live_api.py`, `live_pipeline.py`, `failure_inputs.py`, `failures.py`,
`verification.py`, `evidence_fusion.py`, and `web/src/App.tsx`.
The legacy Streamlit interface remains available; it has a separate larger-data
setup and is not required for the judge's primary React path.

No model weights or robotics simulator are needed for replay. PyAV wheels provide
media codecs; an external FFmpeg executable is not required by the primary path.

## Incremental local analysis and task coverage

One import controller supports 1/2/3 views. Camera sets reuse independent existing
SAM calls, retain source/crop/frame provenance and make one combined camera-labelled
Muse request. Explicit quote approval, origin/Host restrictions, budget reservations,
zero paid retries and offline defaults remain. There is no cross-camera identity
or geometry fusion. The established ordinary single-camera path is preserved.

`task_actions.py` parses a limited set of explicit instructions. `task_criteria.py`
assesses only bound source predicates; `criteria_presentation.py` adds four-state
assessments without overwriting outcomes. `saved_investigations.py` reads frozen
inference outputs, never evaluation references. `task_coverage.py` exposes original
context and analyzed intervals without creating measured action events.

`saved_jobs.py` validates local saved results and provides whitelisted history
metadata. GET reopening dispatches no providers. New and historical camera jobs
can display a read-only assessment; original provider outputs/verdicts/citations
remain unchanged. Completed criteria open first in Findings, while detailed
records and citations remain expandable. Evaluation tools are outside runtime.
