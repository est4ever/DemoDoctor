// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { DiagnosticDetails } from "./DiagnosticDetails";
import { bindCriteria } from "../lib/criteria";
import type { AnalysisBundle, CriteriaBundle } from "../lib/types";

const saved = (ep: string): AnalysisBundle => JSON.parse(readFileSync(`public/data/${ep}/analysis.json`, "utf8"));
const criteria = (ep: string): CriteriaBundle => JSON.parse(readFileSync(`public/criteria/${ep}.json`, "utf8"));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function render(ep: string) {
  const inspect = vi.fn(), seek = vi.fn(), a = bindCriteria(saved(ep), criteria(ep));
  await act(async () => root.render(<DiagnosticDetails analysis={a} inspectEvidence={inspect} seek={seek} />));
  return { a, inspect, seek };
}
it.each(["ep003", "ep005", "ep006", "ep010", "ep013"])("shows computed %s criteria with original scoped sources", async ep => {
  const { a } = await render(ep);
  expect(a.criteria).toBeDefined();
  const coverage = host.querySelector(".criterion-coverage")!;
  expect((coverage as HTMLDetailsElement).open).toBe(true);
  expect(host.querySelector(".diagnostic-hypotheses")!.compareDocumentPosition(coverage) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  expect([...coverage.querySelectorAll('details')].every(d=>!d.open)).toBe(true);
  expect(coverage.querySelector('.criterion-scope')!.compareDocumentPosition(coverage.querySelector('[data-criterion]')!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  expect(coverage.textContent).not.toContain("Supported · assessment source");
  for (const c of a.criteria!.assessments) {
    expect(coverage.querySelector(`[data-criterion=${c.kind}]`)?.textContent).toContain(c.basis);
  }
  expect(a.criteria!.completion).toBe("unverified");
  const completion = coverage.querySelector('[data-criterion=completion]')!;
  expect(completion.textContent).toContain("What would resolve this");
  expect(completion.textContent).toContain("operator-approved complete task checklist");
  if (ep === "ep005") {
    expect(a.task_outcome).toBe("uncertain");
    expect(host.querySelector(".diagnostic-hypotheses")!.textContent).toContain("incorrectly oriented flat");
    expect(host.querySelector(".diagnostic-hypotheses .provenance")!.textContent).toContain("Unverified");
  }
});
it("inspects computed EP003 E4 without inventing orientation evidence and navigates without stale criteria", async () => {
  const { inspect, seek } = await render("ep003");
  const c = host.querySelector('[data-criterion=containment]')!;
  expect(c.textContent).toContain("Supported"); expect(c.textContent).toContain("2075");
  await act(async () => c.querySelector<HTMLElement>('summary')!.click());
  await act(async () => c.querySelector<HTMLButtonElement>('button')!.click());
  expect(inspect).toHaveBeenCalledWith("E4"); expect(seek).not.toHaveBeenCalled();
  expect(host.querySelector('[data-criterion=orientation]')!.textContent).toContain("Unverified");
  await render("ep010");
  expect(host.querySelector(".criterion-coverage")!.textContent).not.toContain("sampled keyframe 2075");
  expect(host.querySelector('[data-criterion=grasp_release]')!.textContent).toContain("Gripper openings measured");
});
it("rejects foreign episodes, stale packages, ID-only matches and absent optional assessments", () => {
  const a = saved("ep003"), c = criteria("ep003");
  expect(bindCriteria(a, criteria("ep005"))).toBe(a);
  expect(bindCriteria(a, null)).toBe(a);
  expect(bindCriteria({ ...a, evidence_catalog: a.evidence_catalog.map(e => ({ ...e, source: "other-camera" })) }, c).criteria).toBeUndefined();
  expect(bindCriteria(a, { ...c, catalog_binding: [] }).criteria).toBeUndefined();
});
it("preserves PILOT original package and historical Muse citation binding", async () => {
  const a: AnalysisBundle = JSON.parse(readFileSync("../data/submission_demo/pilot/audit/after/analysis.json", "utf8"));
  const bound = bindCriteria(a, criteria("pilot"));
  await act(async () => root.render(<DiagnosticDetails analysis={bound} inspectEvidence={vi.fn()} seek={vi.fn()} />));
  expect(bound.task_outcome).toBe("uncertain"); expect(bound.criteria).toBeDefined();
  expect(host.querySelector('[data-criterion=containment]')!.textContent).toContain("does not mean the destination was absent");
  expect(host.querySelector('[data-criterion=orientation]')!.textContent).toContain("Not assessed");
  expect(JSON.stringify(a)).toBe(JSON.stringify({ ...bound, criteria: undefined }));
});
