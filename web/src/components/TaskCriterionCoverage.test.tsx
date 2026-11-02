// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { CriterionCoverage } from "./CriterionCoverage";
import type { CriteriaBundle } from "../lib/types";
import { DiagnosticDetails } from "./DiagnosticDetails";
import { readFileSync } from "node:fs";

it("keeps explicit actions unverified and context seeking distinct from verified evidence",async()=>{
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);
  const host=document.createElement("div"),root=createRoot(host),seek=vi.fn(),cite=vi.fn(()=>null);
  const c:CriteriaBundle={schema:"demodoctor.criteria/v2",investigation_id:"new",completion:"unverified",scope:"Explicit task",notes:[],abstention_explanation:"Missing measurements",
    task_text:"Pick up the block, place it in the drawer, then close the drawer",mechanisms:[],
    assessments:[{criterion_id:"step_3",kind:"action",name:"Close the drawer",required:true,state:"unverified",basis:"No articulation measurement",evidence_ids:[],sources:[],requirements:[{kind:"final_state_observation",reason:"Independent before/after drawer geometry"}]}],
    context_frames:[{frame_ref:"C5",camera_id:"cam1",source_video_id:"source1",original_frame:154,original_timestamp_s:154/15,shared_timestamp_s:154/15,scope:"context"}],
    coverage:[{camera_id:"cam1",source_video_id:"source1",crop:[0,0,1280,720],sha256:"derived",source_sha256:"source",fps:15,n_frames:158,frame_start:0,frame_end:155,returned_observations:97,observed_ranges:[[0,93],[124,128]],missing_ranges:[[93,124],[128,155]],outside_analysis:[[155,158]]}]};
  try {
    await act(async()=>root.render(<CriterionCoverage criteria={c} citations={cite} inspectFrame={seek}/>));
    expect(host.querySelector<HTMLDetailsElement>('.criterion-coverage')!.open).toBe(true);
    expect(host.querySelector('[data-criterion="action"]')?.textContent).toContain('What would resolve this');
    expect([...host.querySelectorAll('.criterion-coverage details')].every(d=>!d.open)).toBe(true);
    expect(host.querySelector('[data-criterion="action"]')?.textContent).toContain("Unverified");
    expect(host.textContent).toContain("not independently verified support");
    expect(host.textContent).toContain("93–123, 128–154");expect(host.textContent).toContain("155–157");
    expect(host.textContent).toContain("0, 0, 1280, 720");
    await act(async()=>host.querySelector<HTMLElement>('[aria-label="Task context frames"] summary')!.click());
    await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="View task context C5 cam1 frame 154"]')!.click());
    expect(seek).toHaveBeenCalledWith(c.context_frames![0]);expect(cite).not.toHaveBeenCalled();
  } finally { await act(async()=>root.unmount());vi.unstubAllGlobals(); }
});

it("shows a provenance failure instead of stale criterion coverage",async()=>{
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);
  const host=document.createElement("div"),root=createRoot(host);
  const a=JSON.parse(readFileSync('public/data/ep005/analysis.json','utf8'));
  a.task_coverage_error='Approved provenance could not be verified';
  delete a.criteria;
  try {
    await act(async()=>root.render(<DiagnosticDetails analysis={a} inspectEvidence={vi.fn()} seek={vi.fn()}/>));
    expect(host.querySelector('[role=alert]')?.textContent).toBe(a.task_coverage_error);
    expect(host.querySelector('.criterion-coverage')).toBeNull();
  } finally { await act(async()=>root.unmount());vi.unstubAllGlobals(); }
});
