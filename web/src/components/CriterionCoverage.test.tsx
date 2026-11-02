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
it('keeps new visual box context separate from physical action states and seeks the bound camera',async()=>{
 const a=bindCriteria(saved('ep005'),criteria('ep005')),inspectFrame=vi.fn();
 a.criteria!.assessments=[{...a.criteria!.assessments[0],kind:'action',name:'Pick up block',state:'unverified'}];
 const frame={frame_ref:'T_cam1_3',camera_id:'cam1',source_video_id:'source1',original_frame:3,original_timestamp_s:.3,shared_timestamp_s:.3,scope:'Local context',sam_observation_available:false,camera_sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null};
 a.multicamera={duration_s:2,cameras:[{camera_id:'cam1',source_video_id:'source1',fps:10,frame_start:0,frame_end:20,playback_offset_s:0,sha256:frame.camera_sha256,source_sha256:frame.source_sha256,crop:null}]} as AnalysisBundle['multicamera'];
 a.criteria!.coverage=[{camera_id:'cam1',source_video_id:'source1',sha256:frame.camera_sha256,source_sha256:frame.source_sha256,crop:null,fps:10,n_frames:20,frame_start:0,frame_end:20,returned_observations:0,observed_ranges:[],missing_ranges:[[0,20]],outside_analysis:[]}];
 a.criteria!.temporal_evidence=[{camera_id:'cam1',source_video_id:'source1',camera_motion:'static',full_source_final_frame_assessed:false,limitations:[],frames:[frame],adjacent_box_steps:[{object_id:'block:0',frames:[1,2],delta_xy_px:[3,4],distance_px:5,scope:'Image coordinates only'}]}];
 await act(async()=>root.render(<DiagnosticDetails analysis={a} inspectEvidence={vi.fn()} seek={vi.fn()} inspectFrame={inspectFrame}/>));
 expect(host.querySelector('[data-criterion=action] .provenance')?.textContent).toBe('Unverified');
 expect(host.textContent).toContain('5.00 px');expect(host.textContent).toContain('full source final frame is outside analysis');
 await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="Inspect temporal cam1 frame 3"]')!.click());
 expect(inspectFrame).toHaveBeenCalledWith(frame);
});
it('withholds mismatched temporal measurements and source buttons with a visible provenance error',async()=>{
 const a=bindCriteria(saved('ep005'),criteria('ep005'));
 a.criteria!.assessments=[{...a.criteria!.assessments[0],kind:'action',name:'Pick up block',state:'unverified'}];
 a.multicamera={duration_s:2,cameras:[{camera_id:'cam1',source_video_id:'source1',fps:10,frame_start:0,frame_end:20,playback_offset_s:0,sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null}]} as AnalysisBundle['multicamera'];
 a.criteria!.temporal_evidence=[{camera_id:'cam1',source_video_id:'source1',camera_motion:'static',frames:[{frame_ref:'T_cam1_3',camera_id:'cam1',source_video_id:'source1',original_frame:3,original_timestamp_s:.3,shared_timestamp_s:.3,scope:'Local',camera_sha256:'f'.repeat(64),source_sha256:'b'.repeat(64),crop:null}],adjacent_box_steps:[{object_id:'block:0',frames:[1,2],delta_xy_px:[3,4],distance_px:5,scope:'Image coordinates only'}],full_source_final_frame_assessed:false,limitations:[]}];
 await act(async()=>root.render(<DiagnosticDetails analysis={a} inspectEvidence={vi.fn()} seek={vi.fn()} inspectFrame={vi.fn()}/>));
 expect(host.querySelector('[role=alert]')?.textContent).toContain('context withheld');
 expect(host.querySelector('[aria-label^="Inspect temporal"]')).toBeNull();
 expect(host.textContent).not.toContain('5.00 px');
 expect(host.querySelector('[data-criterion=action] .provenance')?.textContent).toBe('Unverified');
});
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
