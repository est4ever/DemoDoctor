// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LiveAnalyzePanel } from "./LiveAnalyzePanel";
import { EvidenceSource } from "./EvidenceSource";
import { readFileSync } from "node:fs";
let host: HTMLDivElement, root: Root;
let realEnabled: boolean, providerReady: boolean, loseStart: boolean, statusFailure: boolean, resultStatus: string;
let posts: string[], confirmed: boolean;
const onResult = vi.fn();
const budget = {total_budget_usd:10, per_run_budget_usd:2.10, spent_usd:0, remaining_usd:10};
const quote = {job_id:"new-job", approval_id:"opaque-single-use", filename:"new.mp4", sha256:"abc", start_s:0, end_s:2, frame_start:0, frame_end:20, fps:10, source_frames:20, estimated_max_usd:1.3325, sam_estimate_usd:.0125, muse_reservation_usd:1.32, operations:["1 SAM object-video request","1 Muse evidence explanation"], complete_task_scope:true,budget,note:"Not a provider-enforced billing guarantee"};
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);
  vi.useFakeTimers();sessionStorage.clear();onResult.mockClear();posts=[];confirmed=false;
  realEnabled=true;providerReady=true;loseStart=false;statusFailure=false;resultStatus="completed";
  URL.createObjectURL=vi.fn(()=>"blob:preview");URL.revokeObjectURL=vi.fn();
  host=document.createElement("div");document.body.append(host);root=createRoot(host);
  vi.stubGlobal("fetch",vi.fn(async (url:string, options?:RequestInit) => {
    if (options?.method === "POST") posts.push(url);
    if (url === "/api/health") return Response.json({ok:true,sam_key:providerReady,muse_key:providerReady,real_analysis_enabled:realEnabled,budget});
    if (url === "/api/analyze") {
      const dry=(options!.body as FormData).get("dry_run") === "true";
      return Response.json(dry ? {job_id:"new-job",status:"queued"} : {job_id:"new-job",quote});
    }
    if (url.endsWith("/start")) { confirmed=true;if (loseStart) throw new Error("connection lost");return Response.json({job_id:"new-job"}); }
    if (url.endsWith("/analysis")) return Response.json({title:"New verified investigation",task_outcome:"uncertain"});
    if (url.endsWith("/tracks")) return Response.json({fps:10});
    if (statusFailure) throw new Error("status connection lost");
    return Response.json({job_id:"new-job",status:resultStatus,has_analysis:true,errors:resultStatus === "failed" ? ["SAM provider failed; no retry"] : [],stages:[{name:"sam_window_done"}]});
  }));
  await act(async()=>root.render(<LiveAnalyzePanel onLiveResult={onResult}/>));
});
afterEach(async()=>{ await act(async()=>root.unmount());host.remove();vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals(); });
const button=(text:string)=>[...host.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent?.includes(text))!;
async function click(text:string){ await act(async()=>button(text).click()); }
async function upload(){
  const input=host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input,"files",{value:[new File(["video"],"new.mp4",{type:"video/mp4"})],configurable:true});
  await act(async()=>input.dispatchEvent(new Event("change",{bubbles:true})));
  await act(async()=>host.querySelector("video")!.dispatchEvent(new Event("loadeddata")));
}
async function real(){await act(async()=>host.querySelectorAll<HTMLInputElement>('input[type="radio"]')[1].click());}
async function poll(){await act(async()=>{await vi.advanceTimersByTimeAsync(200);});}
it("defaults to dry run and never starts a real job on upload or mount",async()=>{
  expect(posts).toEqual([]);await upload();expect(posts).toEqual([]);
  expect(host.querySelector<HTMLInputElement>('input[type="radio"]')!.checked).toBe(true);
  await click("Prepare dry run");await poll();expect(posts).toEqual(["/api/analyze"]);expect(confirmed).toBe(false);
  const req=vi.mocked(fetch).mock.calls.find(c=>c[0]==="/api/analyze")![1]!.body as FormData;
  expect(req.get("dry_run")).toBe("true");expect(req.get("run_muse")).toBe("false");
});
it("requires a file-bound estimate confirmation and hands actual results to the workstation",async()=>{
  await upload();await real();await click("Review real analysis estimate");
  expect(host.textContent).toContain("new.mp4 · 0.000–2.000s");expect(host.textContent).toContain("$1.3325");
  expect(posts).toEqual(["/api/analyze"]);expect(onResult).not.toHaveBeenCalled();
  await click("Analyze — approve");await poll();
  expect(posts).toEqual(["/api/analyze","/api/jobs/new-job/start"]);
  expect(onResult).toHaveBeenCalledWith(expect.objectContaining({jobId:"new-job",analysis:expect.objectContaining({task_outcome:"uncertain"})}));
  expect(sessionStorage.getItem("demodoctor.uploadJob")).toBeNull();
});
it("recovers a dropped approval response without sending a second paid POST",async()=>{
  loseStart=true;await upload();await real();await click("Review real analysis estimate");await click("Analyze — approve");await poll();
  expect(confirmed).toBe(true);expect(onResult).toHaveBeenCalledOnce();expect(posts.filter(p=>p.endsWith("/start"))).toHaveLength(1);
});
it("preserves an unknown job on polling failure and permits read-only recovery",async()=>{
  sessionStorage.setItem("demodoctor.uploadJob","new-job");
  await act(async()=>root.unmount());root=createRoot(host);statusFailure=true;
  await act(async()=>root.render(<LiveAnalyzePanel onLiveResult={onResult}/>));await poll();
  expect(host.textContent).toContain("Status unknown");expect(sessionStorage.getItem("demodoctor.uploadJob")).toBe("new-job");
  statusFailure=false;await click("Recover job status");await poll();expect(onResult).toHaveBeenCalledOnce();expect(posts).toEqual([]);
});
it("shows provider failures without substituting results",async()=>{
  resultStatus="failed";await upload();await real();await click("Review real analysis estimate");await click("Analyze — approve");await poll();
  expect(host.textContent).toContain("SAM provider failed");expect(onResult).not.toHaveBeenCalled();
});
it("keeps real execution unavailable in an offline or missing-credential session",async()=>{
  realEnabled=false;providerReady=false;await click("Check local service");await upload();await real();
  expect(host.textContent).toContain("Offline protection is active");expect(host.textContent).toContain("Never enter API keys");
  expect(button("Review real analysis estimate").disabled).toBe(true);expect(posts).toEqual([]);
});
it("invalidates approval when the user changes analysis mode",async()=>{
  await upload();await real();await click("Review real analysis estimate");expect(host.querySelector('[aria-label="Confirm real analysis"]')).not.toBeNull();
  await act(async()=>host.querySelectorAll<HTMLInputElement>('input[type="radio"]')[0].click());
  expect(host.querySelector('[aria-label="Confirm real analysis"]')).toBeNull();expect(posts).toEqual(["/api/analyze"]);
});
it("exposes original live-job source artifacts without rebinding an untimed source",async()=>{
  const fixturePath="../../public/data/ep010/analysis.json";
  const analysis=JSON.parse(readFileSync(new URL(fixturePath,import.meta.url),"utf8"));
  const seek=vi.fn();
  await act(async()=>root.render(<EvidenceSource item={{evidence_id:"E2",source:"pipeline:report",kind:"derived",status_context:"uncertain",t_start:null,t_end:null,frame_start:null,frame_end:null,summary:"No joint data: releases cannot be measured"}} analysis={analysis} fps={30} seek={seek} jobId="new-job"/>));
  expect(host.textContent).toContain("The original job report and verification are available below");
  expect([...host.querySelectorAll("a")].map(a=>a.getAttribute("href"))).toEqual([
    "/api/jobs/new-job/files/failure_report.json","/api/jobs/new-job/files/verification.json",
    "/api/jobs/new-job/files/evidence_package.json","/api/jobs/new-job/files/muse_result.json"]);
  expect(host.textContent).toContain("Untimed · no camera seek");expect(seek).not.toHaveBeenCalled();
});
