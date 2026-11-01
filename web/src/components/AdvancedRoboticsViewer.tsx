import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DiagnosisPanel } from "./DiagnosisPanel";
import {
  RerunViewerEmbed,
  type RerunLoadMetrics,
  type RerunSeekRequest,
} from "./RerunViewerEmbed";
import { Badge, Button } from "./ui";
import {
  RERUN_EP010_RRD_URL,
  RERUN_EVIDENCE_IDS,
  evidenceIdAtTime,
  markerAtTime,
  seekSecondsForEvidence,
} from "../lib/rerunEvidence";
import type { AnalysisBundle, EvidenceItem } from "../lib/types";

type Props = {
  /** Fired once the Wasm viewer has loaded a recording (not merely the JS chunk). */
  onViewerReady?: (metrics: RerunLoadMetrics) => void;
  onViewerError?: (message: string) => void;
  onClose?: () => void;
};

/**
 * Optional Advanced Robotics Viewer (Rerun) for ep010.
 * Lazy-imported from App so the main investigation never downloads Wasm up front.
 */
export function AdvancedRoboticsViewer({ onViewerReady, onViewerError, onClose }: Props) {
  const [analysis, setAnalysis] = useState<AnalysisBundle | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [viewerError, setViewerError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [t, setT] = useState(43.1);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>("E0");
  const [seekRequest, setSeekRequest] = useState<RerunSeekRequest | null>(null);
  const [syncLog, setSyncLog] = useState<string[]>([]);
  const pendingSeekMeta = useRef<{
    token: number;
    id: string;
    targetS: number;
    startedAt: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/data/ep010/analysis.json")
      .then((r) => {
        if (!r.ok) throw new Error("ep010/analysis.json missing");
        return r.json() as Promise<AnalysisBundle>;
      })
      .then((bundle) => {
        if (cancelled) return;
        setAnalysis(bundle);
        setActiveEvidenceId(bundle.initial_evidence_id ?? "E0");
        const seek =
          seekSecondsForEvidence(bundle, bundle.initial_evidence_id ?? "E0") ??
          43.1;
        setT(seek);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
          onViewerError?.(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeEvidence = useMemo(() => {
    if (!analysis || !activeEvidenceId) return null;
    return (
      analysis.evidence_catalog.find((e) => e.evidence_id === activeEvidenceId) ??
      null
    );
  }, [analysis, activeEvidenceId]);

  const pushLog = useCallback((line: string) => {
    setSyncLog((prev) => [line, ...prev].slice(0, 8));
  }, []);

  const close = useCallback(() => {
    if (onClose) onClose();
    else window.location.hash = "ep010";
  }, [onClose]);

  const seekToEvidence = useCallback(
    (id: string, source: "react" | "init") => {
      if (!analysis) return;
      const seconds = seekSecondsForEvidence(analysis, id);
      if (seconds == null) {
        pushLog(`seek blocked: ${id} has no timestamp`);
        return;
      }
      setActiveEvidenceId(id);
      setT(seconds);
      const token = performance.now();
      pendingSeekMeta.current = {
        token,
        id,
        targetS: seconds,
        startedAt: token,
      };
      setSeekRequest({ seconds, token, fromReact: true });
      pushLog(`${source}: seek ${id} @ ${seconds.toFixed(3)}s`);
    },
    [analysis, pushLog],
  );

  const handleReady = useCallback(
    (metrics: RerunLoadMetrics) => {
      setViewerReady(true);
      onViewerReady?.(metrics);
      pushLog(
        `viewer usable ${metrics.coldStartMs.toFixed(0)}ms · ${(metrics.rrdBytes / (1024 * 1024)).toFixed(2)} MiB`,
      );
      if (analysis) {
        seekToEvidence(analysis.initial_evidence_id ?? "E0", "init");
      }
    },
    [analysis, onViewerReady, pushLog, seekToEvidence],
  );

  const onTimeSeconds = useCallback(
    (nextT: number, meta: { source: "viewer" | "seek_ack" }) => {
      setT(nextT);
      if (!analysis || meta.source === "seek_ack") return;
      const eid = evidenceIdAtTime(analysis.evidence_catalog, nextT);
      const marker = markerAtTime(analysis.timeline_markers, nextT);
      if (eid && eid !== activeEvidenceId) {
        setActiveEvidenceId(eid);
        pushLog(
          `playhead ${nextT.toFixed(3)}s → ${eid}` +
            (marker ? ` (${marker.id})` : ""),
        );
      }
    },
    [analysis, activeEvidenceId, pushLog],
  );

  const onSeekSettled = useCallback(
    (token: number, actualSeconds: number, errorMs: number) => {
      const meta = pendingSeekMeta.current;
      if (!meta || meta.token !== token) return;
      const latencyMs = performance.now() - meta.startedAt;
      pushLog(
        `settled ${meta.id}: ${actualSeconds.toFixed(3)}s · err ${errorMs.toFixed(1)}ms · ${latencyMs.toFixed(0)}ms`,
      );
      pendingSeekMeta.current = null;
    },
    [pushLog],
  );

  const evidenceSubset: EvidenceItem[] = useMemo(() => {
    if (!analysis) return [];
    return analysis.evidence_catalog.filter((e) =>
      (RERUN_EVIDENCE_IDS as readonly string[]).includes(e.evidence_id),
    );
  }, [analysis]);

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)] text-[var(--text)]"
      data-testid="advanced-robotics-viewer"
    >
      <header className="shrink-0 border-b border-[var(--border)] bg-[var(--panel)] px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[0.7rem] font-semibold uppercase tracking-wide text-[var(--muted)]">
              DemoDoctor · optional
            </div>
            <h1 className="text-base font-semibold leading-tight">
              Advanced Robotics Viewer
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={viewerReady ? "observed" : "muted"}>
              {viewerReady ? "viewer ready" : "loading viewer…"}
            </Badge>
            <Badge tone="accent">t = {t.toFixed(3)}s</Badge>
            <div className="flex flex-wrap gap-1">
              {evidenceSubset.map((e) => (
                <Button
                  key={e.evidence_id}
                  variant={
                    activeEvidenceId === e.evidence_id ? "primary" : "ghost"
                  }
                  onClick={() => seekToEvidence(e.evidence_id, "react")}
                >
                  {e.evidence_id}
                  {e.t_start != null ? ` @ ${e.t_start.toFixed(2)}s` : ""}
                </Button>
              ))}
            </div>
            <Button variant="ghost" onClick={close}>
              Return to investigation
            </Button>
          </div>
        </div>
      </header>

      {!viewerReady ? (
        <div
          className="shrink-0 border-b border-[var(--border)] bg-[var(--panel-soft)] px-4 py-3"
          role="status"
          aria-live="polite"
          data-testid="rerun-loading-indicator"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div
                className="mt-0.5 h-7 w-7 shrink-0 animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--accent)]"
                aria-hidden
              />
              <div>
                <div className="font-semibold">
                  Loading Advanced Robotics Viewer…
                </div>
                <p className="mt-0.5 text-[0.85rem] text-[var(--muted)]">
                  Wasm loads only on open. Primary investigation stays available
                  until you return.
                </p>
              </div>
            </div>
            <Button variant="ghost" onClick={close}>
              Cancel · return to investigation
            </Button>
          </div>
        </div>
      ) : null}

      <main className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.85fr)]">
        <div className="relative min-h-0 bg-black">
          {!viewerReady ? (
            <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-black/75 px-6 text-center text-white">
              <div
                className="h-10 w-10 animate-spin rounded-full border-2 border-white/30 border-t-white"
                aria-hidden
              />
              <div className="text-[1rem] font-medium">Starting Rerun viewer…</div>
            </div>
          ) : null}
          <RerunViewerEmbed
            className="h-full w-full"
            rrdUrl={RERUN_EP010_RRD_URL}
            seekRequest={seekRequest}
            onReady={handleReady}
            onTimeSeconds={onTimeSeconds}
            onSeekSettled={onSeekSettled}
            onError={(message) => {
              setViewerError(message);
              onViewerError?.(message);
              pushLog(`viewer error: ${message}`);
            }}
          />
          {(loadError || viewerError) && (
            <div className="absolute bottom-0 inset-x-0 z-20 bg-red-50/95 px-4 py-2 text-[0.9rem] text-red-700">
              {loadError ?? viewerError}
            </div>
          )}
        </div>

        <aside className="flex min-h-0 flex-col border-l border-[var(--border)] bg-[var(--panel)]">
          <div className="shrink-0 border-b border-[var(--border)] px-3 py-2 text-[0.8rem] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Evidence (React)
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto scroll-thin px-3 py-3">
            {analysis ? (
              <DiagnosisPanel
                analysis={analysis}
                activeEvidenceId={activeEvidenceId}
                onSelectEvidence={(id) => seekToEvidence(id, "react")}
                activeEvidence={activeEvidence}
              />
            ) : (
              <p className="text-[var(--muted)]">Loading frozen ep010 analysis…</p>
            )}
            {syncLog.length > 0 ? (
              <ul className="mt-4 space-y-1 border-t border-[var(--border)] pt-3 font-mono text-[0.7rem] text-[var(--muted)]">
                {syncLog.map((line, i) => (
                  <li key={`${i}-${line}`}>{line}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </aside>
      </main>
    </div>
  );
}

export default AdvancedRoboticsViewer;
