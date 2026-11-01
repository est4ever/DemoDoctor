import type { AnalysisBundle } from "../lib/types";
import { Badge } from "./ui";

type Props = {
  analysis: AnalysisBundle;
};

function toneFor(verdict: string | null | undefined) {
  if (verdict === "success") return "ok" as const;
  if (verdict === "failure") return "danger" as const;
  return "warn" as const;
}

function plainVerdict(verdict: string | null | undefined) {
  if (verdict === "success") return "Success — the task looks finished";
  if (verdict === "failure") return "Failure — the task did not finish correctly";
  return "Uncertain — not enough proof to decide";
}

/** Side-by-side Muse-only vs evidence-grounded — prominent on false-success demos. */
export function MuseComparison({ analysis }: Props) {
  const eg = analysis.evidence_muse_outcome ?? analysis.task_outcome;
  const mo = analysis.muse_only;
  if (!mo) return null;

  const conf =
    typeof mo.confidence === "number"
      ? ` @ ${(mo.confidence * 100).toFixed(0)}%`
      : "";

  return (
    <section className="mb-5 rounded-2xl border border-[var(--accent)]/25 bg-white px-5 py-4 shadow-[var(--shadow)] md:px-6 md:py-5">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-[0.8rem] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
          Why DemoDoctor’s evidence check matters
        </div>
        <Badge tone="accent">side-by-side comparison</Badge>
      </div>
      <p className="mt-2 max-w-5xl text-[1.05rem] leading-relaxed text-[var(--text)]/90">
        Two AI reads of the <strong>same demonstration</strong>. One watches the
        video and guesses. The other must stick to measured evidence — and may
        refuse to guess.
      </p>
      <p className="mt-2 max-w-5xl text-[0.95rem] leading-relaxed text-[var(--muted)]">
        {analysis.comparison_note ||
          "A confident wrong answer is worse than saying “we’re not sure.”"}
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[#fdf4f4] px-4 py-4">
          <div className="text-[0.75rem] font-semibold uppercase tracking-wide text-[var(--danger)]">
            Video-only AI (Muse-only)
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone="danger">Muse-only</Badge>
            <Badge tone={toneFor(mo.verdict)}>
              {mo.verdict || "—"}
              {conf}
            </Badge>
          </div>
          <p className="mt-3 text-[1.05rem] font-semibold leading-snug">
            {plainVerdict(mo.verdict)}
          </p>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-[var(--text)]/90">
            {mo.summary || "No Muse-only summary in frozen artifacts."}
          </p>
          <p className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-[0.85rem] leading-relaxed text-[var(--muted)]">
            In plain terms: it looked at a few frames and declared the plates
            stored correctly — without proving orientation from measurements.
            Model-reported confidence is <em>not</em> accuracy.
          </p>
        </div>

        <div className="rounded-xl border border-[var(--ok)]/30 bg-[var(--ok-soft)]/50 px-4 py-4">
          <div className="text-[0.75rem] font-semibold uppercase tracking-wide text-[var(--ok)]">
            Evidence-grounded DemoDoctor
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone="ok">Evidence-grounded</Badge>
            <Badge tone={toneFor(eg)}>{eg || "—"}</Badge>
            <Badge>pipeline: {analysis.pipeline_verdict}</Badge>
          </div>
          <p className="mt-3 text-[1.05rem] font-semibold leading-snug">
            {plainVerdict(eg)}
          </p>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-[var(--text)]/90">
            {analysis.muse_explanation ||
              "Evidence-grounded explanation unavailable."}
          </p>
          <p className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-[0.85rem] leading-relaxed text-[var(--muted)]">
            In plain terms: 2D “inside the rack” geometry cannot prove a plate is
            upright. With no verified timed failure event either, DemoDoctor{" "}
            <strong>abstains</strong> instead of inventing a success.
          </p>
        </div>
      </div>
    </section>
  );
}
