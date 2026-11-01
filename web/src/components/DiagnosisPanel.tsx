import type { AnalysisBundle, EvidenceItem } from "../lib/types";
import { Badge, EvidenceChip } from "./ui";

type Props = {
  analysis: AnalysisBundle;
  activeEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  activeEvidence: EvidenceItem | null;
};

function ClaimList({
  title,
  tone,
  borderClass,
  bgClass,
  items,
  activeEvidenceId,
  onSelectEvidence,
}: {
  title: string;
  tone: "observed" | "inferred" | "muted";
  borderClass: string;
  bgClass: string;
  items: Array<{ text: string; evidence_ids?: string[]; t?: number }>;
  activeEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <Badge tone={tone}>{title}</Badge>
      </div>
      <ul className="space-y-2.5">
        {items.map((item, i) => (
          <li
            key={`${title}-${i}`}
            className={`rounded-xl border px-3.5 py-3 text-[0.95rem] leading-relaxed ${borderClass} ${bgClass}`}
          >
            <p>{item.text}</p>
            {item.evidence_ids?.length ? (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {item.evidence_ids.map((id) => (
                  <EvidenceChip
                    key={id}
                    id={id}
                    active={activeEvidenceId === id}
                    onClick={() => onSelectEvidence(id)}
                  />
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DiagnosisPanel({
  analysis,
  activeEvidenceId,
  onSelectEvidence,
  activeEvidence,
}: Props) {
  const outcomeTone =
    analysis.task_outcome === "success"
      ? "ok"
      : analysis.task_outcome === "failure"
        ? "danger"
        : "warn";

  return (
    <div className="flex h-full flex-col gap-5">
      {/* Headline/summary live in the orange banner — avoid duplicating them here. */}
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone={outcomeTone}>Outcome: {analysis.task_outcome}</Badge>
          <Badge>pipeline: {analysis.pipeline_verdict}</Badge>
          {analysis.evidence_muse_outcome ? (
            <Badge tone="muted">Muse EG: {analysis.evidence_muse_outcome}</Badge>
          ) : null}
        </div>
        <p className="text-[0.9rem] leading-relaxed text-[var(--muted)]">
          {analysis.outcome_label}
        </p>
        {analysis.comparison_note ? (
          <p className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--panel-soft)] px-3 py-2 text-[0.88rem] leading-relaxed text-[var(--text)]/85">
            {analysis.comparison_note}
          </p>
        ) : null}
        {analysis.physical_events.length === 0 ? (
          <p className="mt-2 text-[0.85rem] text-[var(--muted)]">
            Physical-event catalog is empty — no timed release was reconstructed
            for this episode.
          </p>
        ) : null}
      </div>

      <ClaimList
        title="Observed measurements"
        tone="observed"
        borderClass="border-[var(--ok)]/30"
        bgClass="bg-[var(--ok-soft)]/45"
        items={analysis.observed}
        activeEvidenceId={activeEvidenceId}
        onSelectEvidence={onSelectEvidence}
      />
      <ClaimList
        title="Inferred / supported findings"
        tone="inferred"
        borderClass="border-[var(--warn)]/35"
        bgClass="bg-[var(--warn-soft)]/55"
        items={analysis.inferred}
        activeEvidenceId={activeEvidenceId}
        onSelectEvidence={onSelectEvidence}
      />

      {analysis.unknowns.length ? (
        <div>
          <Badge tone="muted">Unknown / not established</Badge>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[0.95rem] text-[var(--muted)]">
            {analysis.unknowns.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {activeEvidence ? (
        <div className="rounded-xl border border-[var(--accent)]/35 bg-[var(--accent-soft)] p-3.5">
          <div className="flex items-center gap-2">
            <EvidenceChip id={activeEvidence.evidence_id} active />
            <span className="text-[0.85rem] text-[var(--muted)]">
              {activeEvidence.kind} · {activeEvidence.source}
            </span>
          </div>
          <p className="mt-2 text-[0.95rem] leading-relaxed">
            {activeEvidence.summary}
          </p>
          {activeEvidence.t_start != null ? (
            <p className="mt-1 font-mono text-[0.85rem] text-[var(--accent)]">
              t≈{activeEvidence.t_start.toFixed(2)}s
              {activeEvidence.frame_start != null
                ? ` · frame ${activeEvidence.frame_start}`
                : ""}
            </p>
          ) : activeEvidence.frame_start != null ? (
            <p className="mt-1 font-mono text-[0.85rem] text-[var(--accent)]">
              frame {activeEvidence.frame_start}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-[0.85rem] text-[var(--muted)]">
          Click an evidence ID (E0, E1, …) or a timeline card to inspect
          supporting measurements.
        </p>
      )}

      {(analysis.hypotheses.length > 0 ||
        analysis.factual_claims.length > 0) && (
        <details className="rounded-xl border border-[var(--border)] bg-[var(--panel-soft)]">
          <summary className="cursor-pointer px-3.5 py-3 text-[0.95rem] font-medium text-[var(--muted)]">
            More detail — hypotheses & Muse claims
          </summary>
          <div className="space-y-3 border-t border-[var(--border)] px-3.5 py-3">
            {analysis.hypotheses.map((h, i) => (
              <div key={i} className="text-[0.95rem] leading-relaxed">
                <Badge tone="warn">hypothesis</Badge>
                <p className="mt-1.5">{h.text}</p>
                {h.related_evidence_ids?.length ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {h.related_evidence_ids.map((id) => (
                      <EvidenceChip
                        key={id}
                        id={id}
                        active={activeEvidenceId === id}
                        onClick={() => onSelectEvidence(id)}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
