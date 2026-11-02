import type { CriteriaBundle, CriterionContextFrame } from "../lib/types";

const stateLabel = { supported: "Supported", contradicted: "Contradicted", unverified: "Unverified", not_assessed: "Not assessed" };
export function CriterionCoverage({ criteria: c, citations, inspectFrame }: {
  criteria: CriteriaBundle; citations: (ids: string[]) => React.ReactNode;
  inspectFrame?: (frame: CriterionContextFrame) => void;
}) {
  return <details open className="model-explanation criterion-coverage">
    <summary>Task-criterion coverage</summary>
    <p>Scoped assessments; recorded verdicts unchanged.</p>
    {c.assessments.map(a => <article key={a.criterion_id} data-criterion={a.kind}>
      <h3>{a.name}</h3>
      <span className={`provenance ${a.state === "supported" ? "observed" : "uncertain"}`}>{stateLabel[a.state]}</span>
      <p>{a.basis}</p>
      {a.requirements.length > 0 && <><h4>What would resolve this</h4><ul>
        {a.requirements.map((r, i) => <li key={i}>{r.reason}</li>)}
      </ul></>}
      {(a.evidence_ids.length > 0 || a.sources.length > 0) && <details><summary>Supporting evidence and source records</summary>
        {a.evidence_ids.length > 0 && citations(a.evidence_ids)}
        {a.sources.map((s, i) => <div key={i}><p>{s.evidence_id} · {s.kind} · {s.value} · {s.object_id} · frame {s.frame} · {s.view}<br />
          <small>{s.source_ref} · package {s.package_id}</small></p>
          {Object.entries(s.measurement ?? {}).map(([key, value]) => <p key={key}><small>{key}: {value}</small></p>)}
        </div>)}
      </details>}
    </article>)}
    <details className="criterion-scope"><summary>Assessment scope and task definition</summary>
      <p>{c.scope} Supported or contradicted applies only to the stated measurement scope; 2D containment does not verify full physical completion.</p>
      {c.task_text && <p>Explicit instruction: {c.task_text}. No extra object counts, orientation or success requirements are inferred.</p>}
      {c.notes.map((note, i) => <p key={i}>{note}</p>)}
    </details>
    {!!c.coverage?.length && <details><summary>Processing coverage and crop provenance</summary>
      {c.coverage.map(v => <article key={v.camera_id}><h3>{v.camera_id} · {v.source_video_id}</h3>
        <p>Processed native frames [{v.frame_start}, {v.frame_end}) · {(v.frame_start/v.fps).toFixed(3)}–{(v.frame_end/v.fps).toFixed(3)}s. Source: {v.n_frames} frames. Returned observations: {v.returned_observations}.</p>
        <p>Detection spans: {v.observed_ranges.map(([a,b]) => `${a}–${b-1}`).join(", ") || "none"}.</p>
        <p>Missing observations: {v.missing_ranges.map(([a,b]) => `${a}–${b-1}`).join(", ") || "none"}. No trajectory is invented.</p>
        <p>Outside analysis: {v.outside_analysis.map(([a,b]) => `${a}–${b-1}`).join(", ") || "none"}. These frames are not analyzed evidence.</p>
        <p>Crop (x, y, width, height): {v.crop?.join(", ") ?? "original source"}.</p>
        <p className="break-all"><small>Source SHA256: {v.source_sha256}<br/>Camera SHA256: {v.sha256}</small></p>
      </article>)}
    </details>}
    {!!c.context_frames?.length && <details aria-label="Task context frames"><summary>Original frame context</summary>
      <p>Candidate visual context for the explicit subgoals, not independently verified support. Missing action measurements keep criteria Unverified. These references do not replace historical Muse citations.</p>
      <div className="claim-links">{c.context_frames.map(f => <button key={`${f.camera_id}-${f.frame_ref}`} disabled={!inspectFrame} onClick={() => inspectFrame?.(f)}
        aria-label={`View task context ${f.frame_ref} ${f.camera_id} frame ${f.original_frame}`}>
        {f.frame_ref} · {f.camera_id} · frame {f.original_frame} · {f.original_timestamp_s.toFixed(3)}s ↗
      </button>)}</div>
    </details>}
    {c.mechanisms.length > 0 && <section aria-label="Criterion diagnostic candidates">
      <h3>Possible failure mechanisms</h3>
      <p>Candidate explanations are not additional observed physical events.</p>
      {c.mechanisms.map((m, i) => <article key={i}>
        <span className="provenance uncertain">{m.status === "inferred" || m.status === "end_state" ? "Inferred" : "Unverified"} · diagnostic candidate</span>
        <p>{m.mechanism.replaceAll("_", " ")}</p>
        <small>Original verifier: {m.verifier}. A verifier-supported inference is not a directly observed physical event.</small>
        {citations(m.evidence_ids)}
        {m.alternatives.length > 0 && <p>Alternatives: {m.alternatives.join("; ")}</p>}
        {m.resolving_evidence.map((r, j) => <p key={j}>Needed: {r.reason}</p>)}
      </article>)}
    </section>}
    {c.abstention_explanation && <p>{c.abstention_explanation}</p>}
  </details>;
}
