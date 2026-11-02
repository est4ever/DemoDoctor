// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LiveAnalyzePanel } from "./LiveAnalyzePanel";
import { ImportFootage } from "./ImportFootage";
import { EvidenceSource } from "./EvidenceSource";
import type { AnalysisBundle, EvidenceItem } from "../lib/types";

let host:HTMLDivElement, root:Root;
const onResult=vi.fn();
let requests:Array<{url:string;options?:RequestInit}>;
beforeEach(()=>{
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);sessionStorage.clear();onResult.mockClear();requests=[];
  vi.stubGlobal("URL",class extends URL {static createObjectURL(){return "blob:synthetic-preview";}static revokeObjectURL(){}});
  host=document.createElement("div");document.body.append(host);root=createRoot(host);
  vi.stubGlobal("fetch",vi.fn(async(url:string,options?:RequestInit)=>{requests.push({url,options});
    if(url==="/api/health")return Response.json({ok:true,sam_key:true,muse_key:true,real_analysis_enabled:true});
    if(url==="/api/multicamera/prepare"){
      const m=JSON.parse((options!.body as FormData).get("manifest") as string);
      return Response.json({job_id:"multi-job",quote:{job_id:"multi-job",approval_id:"opaque",estimated_max_usd:1.32+m.cameras.length*.0125,sam_estimate_usd:m.cameras.length*.0125,muse_reservation_usd:1.32,budget:{per_run_budget_usd:2.1,remaining_usd:10},start_s:m.window_start_s,end_s:m.window_end_s,operations:["1 combined Muse request"],note:"Not a provider-enforced billing guarantee",cameras:m.cameras.map((c:{name:string},i:number)=>({camera_id:`cam${i+1}`,name:c.name,sha256:"hash",frame_start:0,frame_end:40,fps:10,operations:["1 SAM object-video request","1 destination-image request"],sam_estimate_usd:.0125}))}});
    }
    if(url.endsWith("/start"))return Response.json({status:"queued"});
    if(url.endsWith("/analysis"))return Response.json({title:"Multi-camera image-space investigation",task_outcome:"uncertain"});
    return Response.json({status:"completed",has_analysis:true,stages:[]});
  }));
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
const button=(text:string)=>[...host.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent?.includes(text))!;
async function click(text:string){await act(async()=>button(text).click());}
async function change(label:string,value:string){const el=host.querySelector<HTMLInputElement|HTMLSelectElement>(`[aria-label="${label}"]`)!;const proto=el instanceof HTMLSelectElement?HTMLSelectElement.prototype:HTMLInputElement.prototype;await act(async()=>{Object.getOwnPropertyDescriptor(proto,"value")!.set!.call(el,value);el.dispatchEvent(new Event(el instanceof HTMLSelectElement?"change":"input",{bubbles:true}));});}
async function upload(label:string){const el=host.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!;Object.defineProperty(el,"files",{value:[new File(["video"],"new.mp4",{type:"video/mp4"})],configurable:true});await act(async()=>el.dispatchEvent(new Event("change",{bubbles:true})));await act(async()=>host.querySelectorAll('video').forEach(v=>v.dispatchEvent(new Event('loadeddata'))));}

it("keeps the established single-camera workflow as the default",async()=>{
  await act(async()=>root.render(<ImportFootage onLiveResult={onResult}/>));
  expect(host.textContent).toContain("Import & prepare");expect(host.querySelector<HTMLSelectElement>('[aria-label="Camera count"]')!.value).toBe("1");
  expect(host.querySelector<HTMLInputElement>('input[name="analysis-mode"]')!.checked).toBe(true);
  await change("Camera count","3");expect(host.textContent).toContain("cam3");
  expect(host.querySelectorAll('input[name="analysis-mode"]')).toHaveLength(2);
  expect(host.querySelector<HTMLInputElement>('input[name="analysis-mode"]')!.checked).toBe(true);
  expect(host.querySelectorAll('ol[aria-label="Import progress"]')).toHaveLength(1);
  expect(requests.filter(r=>r.options?.method==="POST")).toEqual([]);
});

it("requires native crop preview/confirmation before even a dry preparation",async()=>{
  await act(async()=>root.render(<LiveAnalyzePanel onLiveResult={onResult}/>));await change("Camera count","3");await change("Source layout","composite");await upload("Composite MP4");
  await click("Prepare dry run");expect(host.textContent).toContain("confirm every crop boundary");
  expect(requests.filter(r=>r.options?.method==="POST")).toEqual([]);
  const v=host.querySelector("video")!;Object.defineProperty(v,"videoWidth",{value:3872});Object.defineProperty(v,"videoHeight",{value:736});
  await act(async()=>v.dispatchEvent(new Event("loadedmetadata")));
  await click("Preview DROID panel boundaries");
  expect(host.querySelector<HTMLInputElement>('[aria-label="Camera 3 crop x"]')!.value).toBe("2584");
  const check=host.querySelector<HTMLInputElement>('[aria-label="Confirm crop boundaries"]')!;await act(async()=>check.click());
  await change("Camera 1 crop x","10");expect(check.checked).toBe(false);
});

it("prepares separate views with approved offsets and starts only after combined cost approval",async()=>{
  await act(async()=>root.render(<LiveAnalyzePanel onLiveResult={onResult}/>));
  await change("Camera count","2");
  await upload("Camera 1 MP4");await upload("Camera 2 MP4");
  await change("Alignment basis","Manually aligned shared flash");await change("Camera 2 offset","0.2");
  const check=host.querySelector<HTMLInputElement>('[aria-label="Approve camera alignment"]')!;await act(async()=>check.click());
  await change("Task description","Put item in box");
  await act(async()=>host.querySelectorAll<HTMLInputElement>('input[name="analysis-mode"]')[1].click());
  await click("Review real analysis estimate");
  expect(requests.filter(r=>r.url.endsWith("/start"))).toHaveLength(0);
  const form=requests.find(r=>r.url==="/api/multicamera/prepare")!.options!.body as FormData;
  const manifest=JSON.parse(form.get("manifest") as string);
  expect(manifest.cameras[1].offset_s).toBe(.2);expect(manifest.alignment_confirmed).toBe(true);
  expect(form.getAll("videos")).toHaveLength(2);expect(form.get("dry_run")).toBe("false");
  expect(host.textContent).toContain("$1.3450");expect(host.textContent).toContain("Zero automatic paid retries");
  await click("Analyze — approve");
  await act(async()=>{await new Promise(r=>setTimeout(r,130));});
  expect(requests.filter(r=>r.url.endsWith("/start"))).toHaveLength(1);
  expect(onResult).toHaveBeenCalledWith(expect.objectContaining({jobId:"multi-job",analysis:expect.objectContaining({task_outcome:"uncertain"})}));
});

it("never inspects another camera's observations or fabricates an untimed seek",async()=>{
  const seek=vi.fn();
  const a={multicamera:{cameras:[{camera_id:"cam2",fps:10,playback_offset_s:.2}]}} as AnalysisBundle;
  const item:EvidenceItem={evidence_id:"E9",original_evidence_id:"E0",camera_id:"cam2",camera_name:"Wrist",source_video_id:"source2",source:"pipeline:report",summary:"No object detections returned"};
  await act(async()=>root.render(<EvidenceSource item={item} analysis={a} seek={seek} fps={30} jobId="multi-job"/>));
  expect(requests.some(r=>r.url.includes("/cameras/cam2/tracks.json"))).toBe(true);
  expect(requests.some(r=>r.url.includes("/cameras/cam1/"))).toBe(false);
  expect(host.textContent).toContain("Untimed");expect(host.textContent).toContain("Original E0");expect(seek).not.toHaveBeenCalled();
  expect(host.querySelector('a[href$="/cameras/cam2/evidence_package.json"]')).not.toBeNull();
});

it("uses camera-local frame measurements and offsets, ignoring late responses from another camera",async()=>{
  const seek=vi.fn();let finishFirst:(r:Response)=>void=()=>{};
  const track=(x:number)=>({image_size:[96,64],source:`camera-${x}`,frames:{},tracks:{item:{n_observations:1,points:[{frame_index:8,bbox:[x,0,x+4,4]}]}}});
  vi.stubGlobal("fetch",vi.fn((url:string)=>url.includes('/cam1/')?new Promise<Response>(r=>{finishFirst=r;}):Promise.resolve(Response.json(track(40)))));
  const a={multicamera:{cameras:[{camera_id:"cam1",fps:10,playback_offset_s:0},{camera_id:"cam2",fps:10,playback_offset_s:.2}]}} as AnalysisBundle;
  const item:EvidenceItem={evidence_id:"E1",original_evidence_id:"E0",camera_id:"cam1",camera_name:"First",source_video_id:"source1",source:"sam:video",kind:"detection",track_id:"item",frame_start:8,frame_end:9,summary:"Original observation"};
  // Mirror the backend's original-record binding; raw catalog data alone is not authority.
  const bound=(row:EvidenceItem):AnalysisBundle=>({...a,citation_bindings:{schema:'demodoctor.citation-bindings/v1',records:{E1:{status:'record_match',reason:'Synthetic original record',camera_id:row.camera_id,source_video_id:row.source_video_id,original_evidence_id:'E0',expected:{source:row.source,kind:row.kind,track_id:row.track_id,frame_start:8,frame_end:9,summary:row.summary}}}}});
  const second={...item,camera_id:"cam2",camera_name:"Second"};
  await act(async()=>root.render(<EvidenceSource item={item} analysis={bound(item)} seek={seek} fps={30} jobId="multi-job"/>));
  await act(async()=>root.render(<EvidenceSource item={second} analysis={bound(second)} seek={seek} fps={30} jobId="multi-job"/>));
  await act(async()=>finishFirst(Response.json(track(10))));
  expect(host.textContent).toContain("Second");expect(host.textContent).toContain("camera-40");expect(host.textContent).not.toContain("camera-10");
  expect(host.querySelectorAll('.source-measurements tbody tr')).toHaveLength(1);
  await click("F8");expect(seek).toHaveBeenCalledWith(.8-.2,{pause:true});
});

it.each([1,2,3])("uses one approval/progress controller for %i selected composite views",async count=>{
  await act(async()=>root.render(<ImportFootage onLiveResult={onResult}/>));
  await change("Camera count",String(count));await change("Source layout","composite");await upload("Composite MP4");
  const v=host.querySelector('video')!;Object.defineProperty(v,'videoWidth',{value:192});Object.defineProperty(v,'videoHeight',{value:64});
  await act(async()=>v.dispatchEvent(new Event('loadedmetadata')));await click("Set equal horizontal panels");
  await act(async()=>host.querySelector<HTMLInputElement>('[aria-label="Confirm crop boundaries"]')!.click());
  await act(async()=>host.querySelectorAll<HTMLInputElement>('input[name="analysis-mode"]')[1].click());
  await click("Review real analysis estimate");
  expect(requests.filter(r=>r.url.endsWith('/start'))).toHaveLength(0);
  const post=requests.find(r=>r.url==='/api/multicamera/prepare')!;
  expect(JSON.parse((post.options!.body as FormData).get('manifest') as string).cameras).toHaveLength(count);
  expect(host.querySelectorAll('section[aria-label="Confirm real analysis"]')).toHaveLength(1);
  expect(host.textContent).toContain(`${count} camera view(s)`);
  // Editing camera count invalidates the same approval, rather than retaining another controller's quote.
  await change('Camera count',String(count===3?1:count+1));
  expect(host.querySelector('section[aria-label="Confirm real analysis"]')).toBeNull();
});

it("preserves single-camera inputs when changing the camera count and back",async()=>{
  await act(async()=>root.render(<ImportFootage onLiveResult={onResult}/>));
  await upload('Robot demonstration video');await change('Task description','Keep my single-camera task');
  await change('Camera count','3');await change('Camera count','1');
  expect(host.querySelector<HTMLInputElement>('[aria-label="Task description"]')!.value).toBe('Keep my single-camera task');
  expect(host.textContent).toContain('new.mp4');
  expect(host.querySelector<HTMLInputElement>('input[name="analysis-mode"]')!.checked).toBe(true);
  expect(requests.filter(r=>r.options?.method==='POST')).toHaveLength(0);
});
