import type { AnalysisBundle, TracksBundle } from "./types";
import { validateCitations } from './citationIntegrity';

export const isSavedJobId = (id: string) => /^[A-Za-z0-9_-]{1,128}$/.test(id);
export function savedJobHref(id: string): string {
  if (!isSavedJobId(id)) throw new Error("Invalid saved investigation identifier");
  return `#job/${id}`;
}

/** This is a GET-only restore. It must never dispatch upload/start/inference. */
export async function loadSavedInvestigation(id: string, signal?: AbortSignal): Promise<{analysis: AnalysisBundle; tracks: TracksBundle | null}> {
  if (!isSavedJobId(id)) throw new Error("Invalid saved investigation identifier");
  const response = await fetch(`/api/jobs/${id}/reopen`, {method: "GET", signal});
  let body;
  try { body = await response.json(); }
  catch { throw new Error("Saved results unavailable. Check that the local backend is running. No analysis was started."); }
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Saved results unavailable (${response.status}). No analysis was started.`);
  if (!body.analysis || (!body.tracks && body.analysis.dry_run !== true)) throw new Error("Saved result artifacts are incomplete. No analysis was started.");
  validateCitations(body.analysis, true);
  return {analysis: body.analysis, tracks: body.tracks ?? null};
}
