import type { AnalysisBundle } from "../lib/types";

export function RecordedEvidence({ analysis: a, fps, seek }: {
  analysis: AnalysisBundle; fps: number; seek: (t: number, options?: { pause?: boolean }) => void;
}) {
  const record = a.recorded_evidence;
  if (!record) return null;
  const coverage = record.provenance.observation_coverage;
  const displacement = a.evidence_catalog.flatMap(e => e.claims ?? []).find(
    c => (c as { type?: string }).type === "displacement",
  ) as { from_frame: number; to_frame: number; value_px: number } | undefined;
  return <section className="finding" aria-label="Recorded pilot evidence">
    <h2>Observed image-space evidence</h2>
    <p>{record.verification.claims_checked} independently checked claims · {record.verification.claims_failed} failed · {record.verification.ok ? "Checks passed" : "Checks failed"}</p>
    {displacement && <>
      <p>{displacement.value_px.toFixed(2)} px box-center endpoint difference. This does not establish physical identity across the gap, grasp, release, placement, or task completion.</p>
      {[displacement.from_frame, displacement.to_frame].map(frame => <button className="evidence-seek" key={frame} onClick={() => seek(frame / fps, { pause: true })}>Observed endpoint frame {frame} · {(frame / fps).toFixed(3)}s ↗</button>)}
    </>}
    {coverage?.missing_ranges.map(gap => <p key={gap.frame_start}>
      Unobserved frames {gap.frame_start}–{gap.frame_end - 1} inclusive: {gap.frame_end - gap.frame_start} frames · [{gap.frame_start},{gap.frame_end}) · {(gap.frame_start / fps).toFixed(3)}–{(gap.frame_end / fps).toFixed(3)}s. No interpolation or proof of absence.
    </p>)}
    <p>Destination-tray mask: {record.provenance.target_segmentation?.status ?? "unknown"}. Containment and placement remain unknown. No measured gripper or robot joint data.</p>
    <details><summary>Original Muse evidence package (historical only)</summary>
      <p>No Muse response was generated for this reconstruction. Original citations belong only to the original package; they are not rebound to the current E0/E1.</p>
      <a href="/api/recorded-pilot/historical-analysis.json" target="_blank" rel="noreferrer">Original analysis and citations</a>{" · "}
      <a href="/api/recorded-pilot/historical-package.json" target="_blank" rel="noreferrer">Original evidence package</a>{" · "}
      <a href="/api/recorded-pilot/historical-muse.json" target="_blank" rel="noreferrer">Original Muse response</a>
    </details>
  </section>;
}
