import type { AnalysisBundle, CriteriaBundle } from "./types";

/** Cached assessments may only attach to their original displayed package. */
export function bindCriteria(a: AnalysisBundle, criteria: CriteriaBundle | null): AnalysisBundle {
  if (!criteria || criteria.schema !== "demodoctor.criteria/v2" || criteria.investigation_id !== a.episode_key) return a;
  const ids = [...criteria.assessments.flatMap(c => c.evidence_ids), ...criteria.mechanisms.flatMap(m => m.evidence_ids)];
  if (!criteria.catalog_binding || !ids.every(id => criteria.catalog_binding!.some(b => b.evidence_id === id))) return a;
  const keys = ["source", "frame_start", "frame_end", "summary"] as const;
  if (!criteria.catalog_binding.every(b => {
    const e = a.evidence_catalog.find(item => item.evidence_id === b.evidence_id);
    return e && keys.every(key => (e[key] ?? null) === (b[key] ?? null));
  })) return a;
  return { ...a, criteria };
}
