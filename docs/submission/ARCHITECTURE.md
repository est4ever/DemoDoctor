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
- **Upload UI:** sends `dry_run=true`, `run_muse=false`. It probes and replays the
  upload but skips SAM/Muse; it creates no physical findings. This is not a live
  inference demonstration. The backend's paid path exists but is not used here.
- **Optional Rerun:** lazy loads its viewer only when requested, using the
  separate recorded ep010 event window. It is never reused for the SO-101 pilot.

Main modules: `live_api.py`, `live_pipeline.py`, `failure_inputs.py`, `failures.py`,
`verification.py`, `evidence_fusion.py`, and `web/src/App.tsx`.
The legacy Streamlit interface remains available; it has a separate larger-data
setup and is not required for the judge's primary React path.

No model weights or robotics simulator are needed for replay. PyAV wheels provide
media codecs; an external FFmpeg executable is not required by the primary path.
