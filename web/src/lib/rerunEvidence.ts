import type { AnalysisBundle, EvidenceItem, TimelineMarker } from "./types";

export const RERUN_EP010_HASH = "rerun-ep010";
// NOTE: do not put the asset under `/rerun/...` — the web viewer URL parser
// treats that path as host `rerun` (becomes `http://rerun/...`).
export const RERUN_EP010_RRD_URL = "/recordings/ep010_event_window.rrd";
export const RERUN_TIMELINE = "timestamp";

/** Evidence ids exercised by the Rerun embed experiment. */
export const RERUN_EVIDENCE_IDS = ["E0", "E1", "E2"] as const;
export type RerunEvidenceId = (typeof RERUN_EVIDENCE_IDS)[number];

export function isRerunEp010Route(hash: string): boolean {
  return hash.replace(/^#/, "") === RERUN_EP010_HASH;
}

/** Prefer t_start; fall back to marker time tied to the evidence id. */
export function seekSecondsForEvidence(
  analysis: AnalysisBundle,
  evidenceId: string,
): number | null {
  const item = analysis.evidence_catalog.find((e) => e.evidence_id === evidenceId);
  if (item?.t_start != null && Number.isFinite(item.t_start)) {
    return item.t_start;
  }
  const marker = analysis.timeline_markers.find((m) =>
    (m.evidence_ids ?? []).includes(evidenceId),
  );
  if (marker && Number.isFinite(marker.t)) return marker.t;
  return null;
}

/**
 * Map a Rerun playhead (seconds on the shared `timestamp` timeline) to the
 * narrowest evidence window that contains it among E0/E1/E2.
 */
export function evidenceIdAtTime(
  catalog: EvidenceItem[],
  tSeconds: number,
): string | null {
  const hits = catalog.filter((e) => {
    if (!RERUN_EVIDENCE_IDS.includes(e.evidence_id as RerunEvidenceId)) {
      return false;
    }
    if (e.t_start == null || e.t_end == null) return false;
    return tSeconds >= e.t_start && tSeconds <= e.t_end;
  });
  if (!hits.length) return null;
  hits.sort(
    (a, b) =>
      (a.t_end! - a.t_start!) - (b.t_end! - b.t_start!),
  );
  return hits[0]?.evidence_id ?? null;
}

export function markerAtTime(
  markers: TimelineMarker[],
  tSeconds: number,
  toleranceS = 0.05,
): TimelineMarker | null {
  let best: TimelineMarker | null = null;
  let bestDist = Infinity;
  for (const m of markers) {
    const d = Math.abs(m.t - tSeconds);
    if (d <= toleranceS && d < bestDist) {
      best = m;
      bestDist = d;
    }
  }
  return best;
}

export function nanosToSeconds(timeNanos: number | bigint): number {
  const n = typeof timeNanos === "bigint" ? Number(timeNanos) : timeNanos;
  return n / 1e9;
}

export function secondsToDurationNanos(seconds: number): bigint {
  return BigInt(Math.round(seconds * 1e9));
}
