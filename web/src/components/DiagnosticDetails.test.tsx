// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { DiagnosticDetails } from "./DiagnosticDetails";
import { findingGroups } from "../lib/evidencePresentation";
import type { AnalysisBundle } from "../lib/types";

const saved = (ep: string): AnalysisBundle => JSON.parse(readFileSync(resolve("public/data", ep, "analysis.json"), "utf8"));
let root: Root;
let host: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function render(a: AnalysisBundle) {
  const inspect = vi.fn(), seek = vi.fn();
  await act(async () => root.render(<DiagnosticDetails analysis={a} inspectEvidence={inspect} seek={seek} />));
  return { inspect, seek };
}
describe("Saved diagnostics preserve epistemic status and provenance", () => {
  it('selects the original camera for a camera-labelled Muse visual interpretation',async()=>{
    const a=saved('ep005'),inspect=vi.fn(),seek=vi.fn();
    a.multicamera={duration_s:2,cameras:[{camera_id:'cam2',source_video_id:'source2',fps:10,frame_start:0,frame_end:20,playback_offset_s:.1}]} as AnalysisBundle['multicamera'];
    a.frame_catalog=[{frame_ref:'F1',frame_index:19,timestamp_s:1.8,camera_id:'cam2',source_video_id:'source2',original_frame:19,original_timestamp_s:1.9}] as AnalysisBundle['frame_catalog'];
    a.visual_interpretations=[{text:'Original view-specific suggestion',frame_ref:'F1',not_verified_by_pipeline:true}];
    await act(async()=>root.render(<DiagnosticDetails analysis={a} inspectEvidence={vi.fn()} seek={seek} inspectFrame={inspect}/>));
    await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="View diagnostic frame F1"]')!.click());
    expect(inspect).toHaveBeenCalledWith(expect.objectContaining({camera_id:'cam2',original_frame:19,shared_timestamp_s:1.8}));expect(seek).not.toHaveBeenCalled();
  });
  it.each(["ep005", "ep003", "ep010", "ep006", "ep013"])("restores %s verbatim, without changing recorded facts or outcome", async ep => {
    const a = saved(ep), before = JSON.stringify(a);
    await render(a);
    const articles = [...host.querySelectorAll(".diagnostic-hypotheses article")];
    expect(articles).toHaveLength(a.hypotheses.length + a.visual_interpretations.length);
    for (const article of articles) expect(article.querySelector(".provenance")?.textContent).toContain("Unverified");
    for (const h of a.hypotheses) {
      expect(host.textContent).toContain(h.text);
      expect(findingGroups(a).flatMap(g => g.items).some(item => item.text === h.text)).toBe(false);
      for (const id of h.related_evidence_ids ?? []) expect(a.evidence_catalog.some(e => e.evidence_id === id)).toBe(true);
    }
    expect(JSON.stringify(a)).toBe(before);
  });
  it("keeps missing orientation evidence separate from EP005 uncertainty and EP003 2D success", async () => {
    for (const [ep, verdict] of [["ep005", "uncertain"], ["ep003", "success"]]) {
      const a = saved(ep); await render(a);
      expect(a.task_outcome).toBe(verdict);
      const coverage = host.querySelector(".criterion-coverage")!.textContent!;
      expect(coverage).toContain("Unassessed"); expect(coverage).toContain("no verified 3D placement");
      expect(coverage).toContain("not that a criterion was met");
      expect(host.textContent).toContain(ep === "ep005" ? "incorrectly oriented flat" : "lying flat");
    }
  });
  it("retains original citation IDs and exact saved frame references", async () => {
    const a = saved("ep005"), { inspect, seek } = await render(a);
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Inspect diagnostic citation E3"]')!.click());
    expect(inspect).toHaveBeenCalledWith("E3"); expect(seek).not.toHaveBeenCalled();
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="View diagnostic frame F3"]')!.click());
    expect(seek).toHaveBeenCalledWith(a.frame_catalog.find(f => f.frame_ref === "F3")!.timestamp_s, { pause: true });
  });
  it("reports absent data and orphan references without inventing citations or zero-frame seeks", async () => {
    const a = { ...saved("ep005"), hypotheses: [{ text: "Candidate", label: "verified" }], visual_interpretations: [{ text: "Untimed" }, { text: "Orphan", frame_ref: "F999" }] };
    const { seek } = await render(a);
    expect(host.textContent).toContain("No source citation supplied"); expect(host.textContent).toContain("Frame reference unavailable: F999");
    expect(host.querySelectorAll(".diagnostic-hypotheses button")).toHaveLength(0);
    expect(host.querySelector(".diagnostic-hypotheses .provenance")!.textContent).toContain("Unverified"); expect(seek).not.toHaveBeenCalled();
    await render({ ...a, hypotheses: [{ text: "Candidate", related_evidence_ids: ["E999"] }], visual_interpretations: [] });
    expect(host.textContent).toContain("Source reference unavailable: E999");
    await render({ ...a, hypotheses: undefined, visual_interpretations: undefined } as unknown as AnalysisBundle);
    expect(host.textContent).toContain("No diagnostic hypotheses or visual interpretations saved");
  });
  it("does not derive criteria from ground-truth wording or a model label", async () => {
    const a = saved("ep005"); await render({ ...a, title: "success", task: "orientation failure", task_outcome: "success", unknowns: ["orientation failure ground truth"] });
    expect(host.querySelector(".criterion-coverage")!.textContent).not.toContain("orientation failure");
    expect(host.querySelector(".criterion-coverage")!.textContent).toContain("Unassessed");
  });
  it("keeps video-only PILOT measurement gaps and its empty current hypothesis package", async () => {
    const a: AnalysisBundle = JSON.parse(readFileSync(resolve("../data/submission_demo/pilot/audit/after/analysis.json"), "utf8"));
    const before = JSON.stringify(a); await render({ ...a, recorded_evidence: { verification: { claims_checked: 2, claims_failed: 0, ok: true }, provenance: { target_segmentation: { status: "empty_result" } } } });
    expect(host.textContent).toContain("No diagnostic hypotheses or visual interpretations saved");
    expect(host.textContent).toContain("Unsupported · joint measurement unavailable");
    expect(host.textContent).toContain("609.01px"); expect(host.textContent).toContain("105 frames unobserved");
    expect(host.textContent).toContain("Containment unsupported"); expect(host.textContent).toContain("does not mean the tray was physically absent");
    expect(a.task_outcome).toBe("uncertain"); expect(JSON.stringify(a)).toBe(before);
  });
});
