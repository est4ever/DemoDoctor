// @vitest-environment jsdom
import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LiveAnalyzePanel } from './LiveAnalyzePanel';
import { useUploadDraftStore, type UploadDraft, type UploadDraftStore } from '../lib/uploadDraft';

let root:Root,host:HTMLDivElement,posts:Array<{url:string;body:FormData|unknown}>,store:UploadDraftStore;
const result=vi.fn();
function Harness(){
  store=useUploadDraftStore();const [open,setOpen]=useState(true);
  return <><button onClick={()=>setOpen(v=>!v)}>Toggle import</button>{open&&<LiveAnalyzePanel draftStore={store} onLiveResult={result}/>}</>;
}
const input=(label:string)=>host.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)!;
const button=(text:string)=>[...host.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent?.includes(text))!;
async function edit(label:string,value:string){
  const e=input(label);const proto=e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto,'value')!.set!.call(e,value);
  await act(async()=>e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true})));
}
async function click(text:string){await act(async()=>button(text).click());}
function seed(count=2,composite=false):UploadDraft{
  const video=new File(['MOCK validation bytes; not genuine footage'],'unseen.mp4',{type:'video/mp4'});
  return {file:video,task:'Pick up the block and put it in the drawer',questions:'What is occluded?',objectConcept:'blue block',destination:'drawer',windowStart:'0',windowEnd:'4',useWindow:false,completeDemo:false,mode:'dry',dirty:true,
    cameras:{count,sourceMode:composite?'composite':'separate',files:composite?[video]:Array(count).fill(video),cameras:Array.from({length:3},(_,i)=>({name:`View ${i+1}`,motion:'unknown',offset_s:i*.25,object_concept:'blue block',destination_concept:'drawer',crop:[i*400,0,400,480]})),size:[1280,480],cropsConfirmed:composite,aligned:!composite,basis:'Matched visible light cue',proposal:null}};
}
async function mount(draft?:UploadDraft){
  if(draft){store={current:draft};await act(async()=>root.render(<LiveAnalyzePanel draftStore={store} onLiveResult={result}/>));}
  else await act(async()=>root.render(<Harness/>));
  for(const v of host.querySelectorAll('video'))await act(async()=>v.dispatchEvent(new Event('loadeddata')));
}
beforeEach(()=>{
  sessionStorage.clear();localStorage.clear();posts=[];result.mockClear();vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
  URL.createObjectURL=vi.fn(()=> 'blob:mock-preview');URL.revokeObjectURL=vi.fn();
  vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
    if(options?.method==='POST'){posts.push({url,body:options.body});return Response.json({job_id:'draft-mock',quote:{job_id:'draft-mock',approval_id:'private-approval-must-not-persist',filename:'unseen.mp4',sha256:'mock',start_s:0,end_s:4,frame_start:0,frame_end:40,fps:10,source_frames:40,estimated_max_usd:.5,sam_estimate_usd:.1,muse_reservation_usd:.4,operations:[],complete_task_scope:false,budget:{per_run_budget_usd:1,remaining_usd:10},note:'mock estimate'}});}
    return Response.json({ok:true,sam_key:true,muse_key:true,real_analysis_enabled:true,budget:{total_budget_usd:10,per_run_budget_usd:1,spent_usd:0,remaining_usd:10}});
  }));
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});

it.each([1,2,3])('retains %i-view files, task, prompts, raw edits and settings across route-style remounts without POSTs',async count=>{
  await mount();await edit('Task description','An unsaved explicit instruction');await edit('Camera count',String(count));
  if(count>1){await edit('Camera 1 object prompt','red cup');await edit('Camera 1 offset','');}
  else await edit('Object concept','red cup');
  const file=new File(['mock'],'pending.mp4',{type:'video/mp4'}),f=host.querySelector<HTMLInputElement>('input[type=file]')!;
  Object.defineProperty(f,'files',{value:[file],configurable:true});await act(async()=>f.dispatchEvent(new Event('change',{bubbles:true})));
  await click('Toggle import');await click('Toggle import');
  expect(input('Task description').value).toBe('An unsaved explicit instruction');expect(input('Camera count').value).toBe(String(count));
  expect(count>1?input('Camera 1 object prompt').value:input('Object concept').value).toBe('red cup');
  if(count>1){expect(input('Camera 1 offset').value).toBe('');expect(store.current?.cameras.files[0]).toBe(file);}
  else{expect(host.textContent).toContain('pending.mp4');expect(store.current?.file).toBe(file);}
  expect(posts).toEqual([]);expect(sessionStorage.length).toBe(0);expect(localStorage.length).toBe(0);
});

it('protects refresh/close even away from Import; cancelling preserves draft, confirmed reload starts clean',async()=>{
  await mount();let event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(false);
  await edit('Task description','Work that must not vanish');await click('Toggle import');
  event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(true);
  await click('Toggle import');expect(input('Task description').value).toBe('Work that must not vanish');expect(posts).toEqual([]);
  await act(async()=>root.unmount());root=createRoot(host);await mount();
  expect(input('Task description').value).toBe('Store green plates in the dish rack');expect(posts).toEqual([]);
});

it('cancels reset without changes; intentional reset clears draft and unload warning without touching saved jobs',async()=>{
  await mount();await edit('Task description','Do not discard without consent');
  const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);await click('Reset draft');expect(input('Task description').value).toBe('Do not discard without consent');
  confirm.mockReturnValue(true);await click('Reset draft');expect(input('Task description').value).toBe('Store green plates in the dish rack');
  const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);expect(event.defaultPrevented).toBe(false);expect(posts).toEqual([]);
});

it('does not restore an approval token, submit, or retain a quote across a remount; cancellation retains draft',async()=>{
  await mount();const f=input('Robot demonstration video');Object.defineProperty(f,'files',{value:[seed(1).file],configurable:true});
  await act(async()=>f.dispatchEvent(new Event('change',{bubbles:true})));await act(async()=>host.querySelector('video')!.dispatchEvent(new Event('loadeddata')));
  await act(async()=>host.querySelectorAll<HTMLInputElement>('input[name=analysis-mode]')[1].click());await click('Review real analysis estimate');
  expect(host.querySelector('[aria-label="Confirm real analysis"]')).not.toBeNull();await click('Cancel');expect(host.textContent).toContain('unseen.mp4');
  await click('Review real analysis estimate');await click('Toggle import');await click('Toggle import');
  expect(host.querySelector('[aria-label="Confirm real analysis"]')).toBeNull();expect(posts).toHaveLength(2);
  expect(JSON.stringify(store.current)).not.toContain('approval');expect(sessionStorage.length).toBe(0);expect(localStorage.length).toBe(0);
});

it.each([
  ['Camera 1 offset','','analysis-camera-0-offset'],['Camera 2 offset','61','analysis-camera-1-offset'],
  ['Camera 1 name','','analysis-camera-0-name'],['Camera 2 name','View 1','analysis-camera-1-name'],
  ['Camera 1 object prompt','','analysis-camera-0-object_concept'],['Camera 2 destination prompt','','analysis-camera-1-destination_concept'],
])('focuses and announces %s validation without dropping other fields or preparing',async(label,value,id)=>{
  await mount(seed());await edit(label,value);await click('Prepare dry run');
  expect(document.activeElement?.id).toBe(id);expect(document.activeElement?.getAttribute('aria-invalid')).toBe('true');expect(host.querySelector('#analysis-input-error[role=alert]')).not.toBeNull();
  expect(input('Task description').value).toBe(seed().task);expect(input('Camera 2 object prompt').value).toBe('blue block');expect(posts).toEqual([]);
  button('Prepare dry run').focus();await click('Prepare dry run');expect(document.activeElement?.id).toBe(id);
});
it.each([
  ['Camera 1 crop x','-2','analysis-camera-0-crop-0'],['Camera 1 crop y','3','analysis-camera-0-crop-1'],
  ['Camera 1 crop width','','analysis-camera-0-crop-2'],['Camera 1 crop width','1300','analysis-camera-0-crop-2'],
  ['Camera 2 crop x','0','analysis-camera-1-crop-0'],
])('keeps raw %s edits and focuses invalid crops before any request',async(label,value,id)=>{
  await mount(seed(2,true));await edit(label,value);await click('Prepare dry run');expect(document.activeElement?.id).toBe(id);expect(input(label).value).toBe(value);expect(posts).toEqual([]);
});
it('focuses missing source, crop confirmation, alignment approval and its basis, each in the visible configuration',async()=>{
  const d=seed();d.cameras.files[1]=undefined;await mount(d);await click('Prepare dry run');expect(document.activeElement?.id).toBe('analysis-camera-1-file');
  await act(async()=>root.unmount());root=createRoot(host);const d2=seed();d2.cameras.aligned=false;await mount(d2);await click('Prepare dry run');expect(document.activeElement?.id).toBe('analysis-camera-aligned');
  await act(async()=>input('Approve camera alignment').click());await edit('Alignment basis','');await click('Prepare dry run');expect(document.activeElement?.id).toBe('analysis-camera-basis');
  await act(async()=>root.unmount());root=createRoot(host);const d3=seed(2,true);d3.cameras.cropsConfirmed=false;await mount(d3);await click('Prepare dry run');expect(document.activeElement?.id).toBe('analysis-camera-crops');expect(posts).toEqual([]);
});
it.each([['Window start seconds','', 'analysis-window'],['Window start seconds','-1','analysis-window'],['Window end seconds','0','analysis-window-end'],['Window end seconds','bad','analysis-window-end']])('focuses invalid %s timestamps',async(label,value,id)=>{
  const d=seed();d.useWindow=true;await mount(d);await edit(label,value);await click('Prepare dry run');expect(document.activeElement?.id).toBe(id);expect(posts).toEqual([]);
});
it('requires explicit zero after an empty edit and invalidates earlier synchronization approval',async()=>{
  await mount(seed());await edit('Camera 1 offset','');expect(input('Approve camera alignment').checked).toBe(false);await click('Prepare dry run');expect(posts).toEqual([]);
  await edit('Camera 1 offset','0');await click('Prepare dry run');expect(document.activeElement).toBe(input('Approve camera alignment'));expect(posts).toEqual([]);
  await act(async()=>input('Approve camera alignment').click());await click('Prepare dry run');expect(posts).toHaveLength(1);
  const manifest=JSON.parse((posts[0].body as FormData).get('manifest') as string);expect(manifest.cameras.map((c:any)=>c.offset_s)).toEqual([0,.25]);
});
it('focuses an invalid source layout instead of looking for a hidden camera input',async()=>{
  const d=seed();d.cameras.sourceMode='invalid';await mount(d);await click('Prepare dry run');expect(document.activeElement).toBe(input('Source layout'));expect(posts).toEqual([]);
});
it('focuses a window outside the decoded source overlap while keeping valid offsets',async()=>{
  const d=seed();d.useWindow=true;d.windowEnd='12';await mount(d);
  for(const v of host.querySelectorAll('video')){Object.defineProperty(v,'duration',{value:10});await act(async()=>v.dispatchEvent(new Event('loadedmetadata')));}
  await click('Prepare dry run');expect(document.activeElement).toBe(input('Window end seconds'));expect(input('Camera 2 offset').value).toBe('0.25');expect(posts).toEqual([]);
});
it('rechecks decoding on restoration without auto-replacing retained manual crops',async()=>{
  const d=seed(2,true);d.cameras.cameras[0].crop=[8,0,384,480];await mount(d);
  expect(input('Camera 1 crop x').value).toBe('8');expect(store.current?.cameras.cropsConfirmed).toBe(true);
  expect(host.textContent).toContain('Selected: unseen.mp4');expect(posts).toEqual([]);
});
it.each([2,3])('prepares %i separate views using explicit numeric offsets, and no inference start',async count=>{
  await mount(seed(count));await edit('Camera 1 offset','-0.25');await act(async()=>input('Approve camera alignment').click());await click('Prepare dry run');
  expect(posts).toHaveLength(1);expect(posts[0].url).toBe('/api/multicamera/prepare');const body=posts[0].body as FormData,manifest=JSON.parse(body.get('manifest') as string);
  expect(manifest.cameras).toHaveLength(count);expect(manifest.cameras[0].offset_s).toBe(-.25);expect(manifest.alignment_confirmed).toBe(true);expect(body.get('dry_run')).toBe('true');
});
it.each([1,2,3])('prepares %i confirmed composite view(s) preserving crops and zero inherited offsets',async count=>{
  await mount(seed(count,true));await click('Prepare dry run');expect(posts).toHaveLength(1);const manifest=JSON.parse((posts[0].body as FormData).get('manifest') as string);
  expect(manifest.cameras).toHaveLength(count);expect(manifest.cameras.every((c:any)=>c.offset_s===0)).toBe(true);expect(manifest.cameras.map((c:any)=>c.crop)).toEqual(seed(count,true).cameras.cameras.slice(0,count).map(c=>c.crop));
});
