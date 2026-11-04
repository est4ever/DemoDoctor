// @vitest-environment jsdom
// Product-state tests; real browser source/seek/reopen checks live in scripts/check-placement-browser.py.
import {afterEach,expect,it,vi} from 'vitest';
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {PlacementAssessment} from './PlacementAssessment';
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>|undefined;
afterEach(async()=>{if(root)await act(async()=>root!.unmount());document.body.innerHTML='';vi.restoreAllMocks();});
it('shows unavailable assistance without inventing findings',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({available:false,sources:[],reason:'No approved template.'})})));
  const el=document.createElement('div');document.body.append(el);root=createRoot(el);
  await act(async()=>root!.render(<PlacementAssessment episodeKey="new-video" seek={()=>{}}/>));
  expect(el.textContent).toContain('Unverified — No approved template.');
  expect(el.textContent).not.toContain('Visible final-placement failure');
});
it('quarantine errors cannot display a result or source image',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({detail:'Placement evidence quarantined'})})));
  const el=document.createElement('div');document.body.append(el);root=createRoot(el);
  await act(async()=>root!.render(<PlacementAssessment jobId="placement-123" episodeKey="ep010" seek={()=>{}}/>));
  expect(el.textContent).toContain('Placement evidence quarantined');
  expect(el.querySelector('img')).toBeNull();
  expect(el.textContent).not.toContain('Visible final-placement failure');
});

it('does not show the previous job finding while the next job is loading',async()=>{
  const first={job_id:'placement-first',failure_detected:true,time_interval:null,source_citations:[],observed_evidence:[],rejected_frames:[],muse_status:'provider_skipped'};
  let finish:(value:unknown)=>void=()=>{};
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.includes('placement-first')?{ok:true,json:async()=>first}:await new Promise(resolve=>{finish=resolve;})));
  const el=document.createElement('div');document.body.append(el);root=createRoot(el);
  await act(async()=>root!.render(<PlacementAssessment jobId="placement-first" episodeKey="ep010" seek={()=>{}}/>));
  expect(el.textContent).toContain('Visible final-placement failure');
  await act(async()=>root!.render(<PlacementAssessment jobId="placement-next" episodeKey="bf000" seek={()=>{}}/>));
  expect(el.textContent).not.toContain('Visible final-placement failure');
  await act(async()=>finish({ok:true,json:async()=>({...first,job_id:'placement-next',failure_detected:false})}));
  expect(el.textContent).toContain('No supported outside-rack finding');
});
