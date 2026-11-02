import type { AnalysisBundle, CriterionContextFrame } from "../lib/types";
import { diagnosticFrameCatalog } from "../lib/diagnosticFrameCatalog";
import { CriterionCoverage } from "./CriterionCoverage";
import { TemporalContext } from "./TemporalContext";
import { criterionContextTime } from "../lib/criterionContext";

type Props = {
  analysis: AnalysisBundle;
  inspectEvidence: (id: string) => void;
  seek: (t: number, options?: { pause?: boolean }) => void;
  inspectFrame?: (frame: CriterionContextFrame) => void;
  videoSrc?: string;
  fps?: number;
  duration?: number;
  jobId?: string | null;
  showCriteria?: boolean;
};

/** Presentation only: saved model suggestions never enter the verified finding groups. */
export function DiagnosticDetails({ analysis: a, inspectEvidence, seek, inspectFrame, videoSrc, fps=30, duration=0, jobId,showCriteria=true }: Props) {
  const catalog = a.evidence_catalog;
  const citations = (ids: string[] = []) => ids.length ? (
    <div className="claim-links diagnostic-links">
      {ids.map((id, i) => catalog.some(e => e.evidence_id === id) ? (
        <button key={`${id}-${i}`} onClick={() => inspectEvidence(id)} aria-label={`Inspect diagnostic citation ${id}`}>
          {id} ↗
        </button>
      ) : <span key={`${id}-${i}`}>Source reference unavailable: {id}</span>)}
    </div>
  ) : <p className="model-context">No source citation supplied in this saved record.</p>;
  // Use source metadata and the original observed statements, never outcome labels,
  // dataset ground truth, model prose, or episode-specific failure labels.
  const location = a.observed.filter(item => item.evidence_ids.some(id => catalog.some(e =>
    e.evidence_id === id && e.source?.startsWith("sam:") && ["detection", "comparison"].includes(e.kind ?? ""),
  )));
  const gripper = catalog.filter(e => e.kind === "measurement" && e.source?.startsWith("proprio:"));
  const hypotheses = a.hypotheses ?? [];
  const interpretations = a.visual_interpretations ?? [];
  const frameCatalog = diagnosticFrameCatalog(a);

  return <>
    {a.task_coverage_error && <p role="alert">{a.task_coverage_error}</p>}
    {a.temporal_evidence_error && <p role="alert">{a.temporal_evidence_error}</p>}
    {showCriteria && a.criteria && <CriterionCoverage criteria={a.criteria} citations={citations} inspectFrame={inspectFrame} manifest={a.multicamera} />}
    {videoSrc && <TemporalContext analysis={a} videoSrc={videoSrc} fps={fps} duration={duration} jobId={jobId} inspectFrame={inspectFrame} seek={seek}/>}
    <section className="diagnostic-hypotheses" aria-label="Diagnostic hypotheses">
      <h3>Diagnostic hypotheses</h3>
      <p>Saved Muse suggestions and visual interpretations. <strong>Unverified</strong>: citations provide context, not independent confirmation. These do not change the recorded outcome.</p>
      {!hypotheses.length && !interpretations.length && <p>No diagnostic hypotheses or visual interpretations saved in this analysis.</p>}
      {hypotheses.map((h, i) => <article key={`h-${i}`}>
        <span className="provenance uncertain">Unverified · saved hypothesis</span>
        <p>{h.text}</p>
        {citations(h.related_evidence_ids)}
        <small>No direct frame reference supplied for this hypothesis. Cited evidence may be timed or untimed.</small>
      </article>)}
      {interpretations.map((v, i) => {
        const frame = frameCatalog.frames.find(f => f.frame_ref === v.frame_ref);
        const context:CriterionContextFrame|null = a.multicamera && frame?.camera_id && frame.source_video_id && frame.original_frame!=null && frame.original_timestamp_s!=null ? {
          frame_ref:frame.frame_ref,camera_id:frame.camera_id,source_video_id:frame.source_video_id,original_frame:frame.original_frame,
          original_timestamp_s:frame.original_timestamp_s,shared_timestamp_s:frame.timestamp_s,scope:'Original saved Muse visual interpretation, Unverified',
        } : null;
        const timed = frame && Number.isFinite(frame.timestamp_s) && frame.timestamp_s >= 0 &&
          (!a.multicamera || context && inspectFrame && criterionContextTime(context,a.multicamera)!=null);
        return <article key={`v-${i}`}>
          <span className="provenance uncertain">Unverified · saved visual interpretation</span>
          <p>{v.text}</p>
          {timed ? <div className="claim-links">
            <button onClick={() => context ? inspectFrame?.(context) : seek(frame.timestamp_s, { pause: true })} aria-label={`View diagnostic frame ${frame.frame_ref}`}>
              {frame.frame_ref} · frame {frame.frame_index} · {frame.timestamp_s.toFixed(3)}s ↗
            </button>
            {context && <small>{context.camera_id}/{context.source_video_id} · native frame {context.original_frame} · source {context.original_timestamp_s.toFixed(3)}s</small>}
          </div> : <p>Frame reference unavailable{v.frame_ref ? `: ${v.frame_ref}` : " (none supplied)"}. No camera seek.</p>}
          {timed && <small>Frame source: {frameCatalog.source}</small>}
          <small>Provenance: visual_interpretations in this saved analysis; a frame reference is not verification.</small>
        </article>;
      })}
    </section>
    {!a.criteria && !a.task_coverage_error && <details open className="model-explanation criterion-coverage">
      <summary>Task-criterion coverage</summary>
      <p>Coverage of the saved assessment, not additional success requirements. Supported means an assessment source is present, not that a criterion was met. Missing evidence never implies success or failure.</p>
      <article>
        <h3>Object location / containment</h3>
        <span className={`provenance ${location.length ? "observed" : "uncertain"}`}>{location.length ? "Supported · assessment source" : "Unknown"}</span>
        <p>Image-space evidence only; no verified 3D placement or physical orientation. Individual regions may remain unknown.</p>
        {a.recorded_evidence?.provenance.target_segmentation?.status === "empty_result" && <p>Containment unsupported: destination segmentation returned no usable tray mask (empty_result). This does not mean the tray was physically absent.</p>}
        {location.length ? location.map((item, i) => <div key={i}><p>{item.text}</p>{citations(item.evidence_ids)}</div>) : <p>No observed location assessment with a SAM detection/comparison source in this catalog. Inspect missing-data diagnostics in Evidence.</p>}
      </article>
      <article><h3>Object orientation</h3><span className="provenance uncertain">Unassessed</span>
        <p>No independently verified physical-orientation assessment is supplied by this analysis format. 2D containment and Muse interpretations cannot establish upright orientation. An orientation requirement is not inferred from the video or dataset label.</p>
      </article>
      <article><h3>Required objects accounted for</h3><span className="provenance uncertain">Unknown</span>
        <p>No complete expected-object inventory is supplied in this saved analysis. Detected tracks do not establish that all required objects were accounted for.</p>
      </article>
      <article><h3>Task-completion conditions</h3><span className="provenance uncertain">Unknown</span>
        <p>The task description is not a complete machine-readable checklist here. The recorded outcome is preserved; it does not verify unstated completion conditions or physical orientation.</p>
      </article>
      <article><h3>Grasp or release</h3><span className="provenance uncertain">{gripper.length ? "Unknown · physical event" : "Unsupported · joint measurement unavailable"}</span>
        <p>{gripper.length ? "A recorded gripper measurement is available below. Opening does not establish holding, release, intent or placement; inferred events keep their original status." : "No measured gripper source is supplied in this catalog. Video-only observations do not invent joint measurements or verify physical release."}</p>
        {gripper.length > 0 && citations(gripper.map(e => e.evidence_id))}
      </article>
    </details>}
  </>;
}
