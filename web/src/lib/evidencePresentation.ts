import type { AnalysisBundle, EvidenceItem, TimelineMarker } from "./types";

/** Display-only excerpt. The full, unmodified record remains in the inspector. */
export function evidenceHeadline(item: EvidenceItem): string {
  const summary = item.summary?.trim();
  if (!summary) return "No summary provided";
  const withoutFrameAside = summary.replace(/ at frame \d+ \([\d.]+s\),/g, "");
  // Only omit recognized supporting calibration/count details. Unknown
  // parentheticals or later sentences may contain essential uncertainty.
  const firstClause = withoutFrameAside.split(
    /\s+\((?=(?:In ep\d+|[\d.]+x its size\b|\d+ of \d+ rest observations\b))/,
  )[0];
  const readable = firstClause
    .replace(/^track /, "")
    .replace(/green plate:(\d+)/g, "green plate $1");
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

/** Provenance comes from the frozen context, never from the wording of a claim. */
export function evidenceStatus(item: EvidenceItem): string {
  return item.status_context || item.kind || "Unclassified";
}

/** Exact matching is essential: unobserved must never match observed. */
export function evidenceTone(
  item: EvidenceItem,
): "observed" | "inferred" | "uncertain" {
  const status = evidenceStatus(item).toLowerCase();
  return status === "observed"
    ? "observed"
    : status === "inferred"
      ? "inferred"
      : "uncertain";
}

export function markerPresentation(marker: TimelineMarker): {
  label: string;
  tone: "observed" | "inferred" | "uncertain";
} {
  switch (marker.kind) {
    case "observed_measurement":
      return { label: "Observed", tone: "observed" };
    case "inferred_event":
      return { label: "Inferred", tone: "inferred" };
    case "analysis_frame":
      return { label: "Frame", tone: "uncertain" };
    default:
      return { label: "Uncertain", tone: "uncertain" };
  }
}

export function findingGroups(
  analysis: Pick<AnalysisBundle, "observed" | "inferred">,
) {
  const observed = [...analysis.observed];
  const inferred: typeof analysis.inferred = [];
  const endState: typeof analysis.inferred = [];
  const uncertain: typeof analysis.inferred = [];
  for (const item of analysis.inferred) {
    // An explicit record status wins over the historical array name.
    if (item.status === "observed") observed.push(item);
    else if (item.status === "supported_by_end_state") endState.push(item);
    else if (item.status == null || item.status === "inferred")
      inferred.push(item);
    else uncertain.push(item);
  }
  return [
    { label: "Observed", tone: "observed", items: observed },
    { label: "Inferred", tone: "inferred", items: inferred },
    { label: "End-state supported", tone: "inferred", items: endState },
    { label: "Uncertain", tone: "uncertain", items: uncertain },
  ].filter((group) => group.items.length > 0);
}
