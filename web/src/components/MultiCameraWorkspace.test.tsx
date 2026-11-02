// @vitest-environment jsdom
import {act} from "react";
import {createRoot,type Root} from "react-dom/client";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import type {MultiCameraManifest} from "../lib/types";
import {MultiCameraWorkspace} from "./MultiCameraWorkspace";
vi.mock('./VideoPane',()=>({VideoPane:(p:{src:string;mode:string;onModeChange:(m:string)=>void;t:number;tracks?:{frames:unknown}})=><div data-mode={p.mode} data-src={p.src} data-time={p.t}><button onClick={()=>p.onModeChange('sam')}>SAM Overlay</button><pre>{JSON.stringify(p.tracks?.frames)}</pre></div>}));
let host:HTMLDivElement,root:Root;
const manifest={source_mode:'composite',sources:[{source_video_id:'source1',width:300,height:100,fps:10,sha256:'hash'}],cameras:[1,2,3].map(n=>({camera_id:`cam${n}`,name:`View ${n}`,motion:'unknown',crop:[100*(n-1),0,100,100],playback_offset_s:0,fps:10})),duration_s:2} as MultiCameraManifest;
beforeEach(()=>{vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);host=document.createElement('div');document.body.append(host);root=createRoot(host);
vi.stubGlobal('fetch',vi.fn(async()=>Response.json({source:'original',image_size:[100,100],fps:10,tracks:{},legend:[],t_start:0,t_end:2,frames:{'0':[{object_id:'same:0',bbox:[10,10,14,14],centroid:[12,12],mask:{size:[4,4],counts:[0,16]}}]}})));});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
async function display(value:string){const s=host.querySelector<HTMLSelectElement>('[aria-label="Camera display"]')!;await act(async()=>{Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value')!.set!.call(s,value);s.dispatchEvent(new Event('change',{bubbles:true}));});}
it('switches all/individual/composite views and keeps overlay modes camera-specific',async()=>{
 await act(async()=>root.render(<MultiCameraWorkspace manifest={manifest} jobId="job" t={.4} playing={false}/>));
 await act(async()=>host.querySelector<HTMLButtonElement>('[data-camera-id="cam1"] [data-mode] button')!.click());
 expect(host.querySelector('[data-camera-id="cam1"] [data-mode]')!.getAttribute('data-mode')).toBe('sam');
 expect(host.querySelector('[data-camera-id="cam2"] [data-mode]')!.getAttribute('data-mode')).toBe('original');
 await display('cam2');expect(host.querySelectorAll('[data-camera-id]')).toHaveLength(1);expect(host.querySelector('[data-camera-id]')!.getAttribute('data-camera-id')).toBe('cam2');
 await display('composite');expect(host.querySelector('[data-src]')!.getAttribute('data-src')).toBe('/api/jobs/job/sources/source1.mp4');
 expect(host.textContent).toContain('cam2/same:0');expect(host.textContent).toContain('110');
 await display('all');expect(host.querySelectorAll('[data-camera-id]')).toHaveLength(3);
 expect(host.querySelector('[data-camera-id="cam1"] [data-mode]')!.getAttribute('data-mode')).toBe('sam');
 expect(host.querySelector('[data-time]')!.getAttribute('data-time')).toBe('0.4');
});
it('shows the supporting camera when evidence changes while one camera is isolated',async()=>{
 await act(async()=>root.render(<MultiCameraWorkspace manifest={manifest} jobId="job" t={.8} playing={false} activeCamera="cam1"/>));await display('cam1');
 await act(async()=>root.render(<MultiCameraWorkspace manifest={manifest} jobId="job" t={.8} playing={false} activeCamera="cam3"/>));
 expect(host.querySelector('[data-camera-id]')!.getAttribute('data-camera-id')).toBe('cam3');expect(host.querySelector('[data-time]')!.getAttribute('data-time')).toBe('0.8');
});
it('repeated context requests restore their camera after manual view switching',async()=>{
 await act(async()=>root.render(<MultiCameraWorkspace manifest={manifest} jobId="job" t={.8} playing={false} activeCamera="cam1" cameraFocus={1}/>));
 await display('cam2');
 await act(async()=>root.render(<MultiCameraWorkspace manifest={manifest} jobId="job" t={1} playing={false} activeCamera="cam1" cameraFocus={2}/>));
 expect(host.querySelector('[data-camera-id]')!.getAttribute('data-camera-id')).toBe('cam1');
 expect(host.querySelector('[data-time]')!.getAttribute('data-time')).toBe('1');
});
