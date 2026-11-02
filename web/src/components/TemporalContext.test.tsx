// @vitest-environment jsdom
import { beforeEach,afterEach,it,expect,vi } from 'vitest';
import { act } from 'react';import { createRoot,type Root } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { TemporalContext } from './TemporalContext';
import type { AnalysisBundle } from '../lib/types';
let root:Root,host:HTMLDivElement;
beforeEach(()=>{vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{});vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
const a=()=>JSON.parse(readFileSync('public/data/ep005/analysis.json','utf8')) as AnalysisBundle;
it('shows saved native frames, seeks original time and keeps original analysis unchanged',async()=>{
 const analysis=a(),before=JSON.stringify(analysis),seek=vi.fn();
 await act(async()=>root.render(<TemporalContext analysis={analysis} videoSrc="/replays/ep005/video.mp4" fps={30} duration={100} seek={seek}/>));
 expect(host.textContent).toContain('not verified action support');expect(host.textContent).toContain('Saved Muse catalog: F0');
 const frame=host.querySelector<HTMLButtonElement>('[aria-label="Inspect original primary frame 1607"]')!;
 await act(async()=>frame.click());expect(seek).toHaveBeenCalledWith(1607/30,{pause:true});expect(JSON.stringify(analysis)).toBe(before);
});
it('reports unavailable optional review provenance and never applies it to another investigation',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({schema:'wrong',job_id:'job'})));
 await act(async()=>root.render(<TemporalContext analysis={a()} videoSrc="/video" fps={30} duration={100} jobId="job" seek={vi.fn()}/>));
 expect(host.querySelector('[role=alert]')?.textContent).toContain('provenance does not match');
 await act(async()=>root.render(<TemporalContext analysis={a()} videoSrc="/video" fps={30} duration={100} seek={vi.fn()}/>));
 expect(host.querySelector('[role=alert]')).toBeNull();expect(host.querySelector('[aria-label="Local analyst visual review"]')).toBeNull();
});
it('treats a missing optional review or SPA fallback as absent, without inventing a review',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('<html>app</html>',{headers:{'content-type':'text/html'}})));
 await act(async()=>root.render(<TemporalContext analysis={a()} videoSrc="/video" fps={30} duration={100} jobId="job" seek={vi.fn()}/>));
 expect(host.querySelector('[role=alert]')).toBeNull();expect(host.querySelector('[aria-label="Local analyst visual review"]')).toBeNull();
});
it('keeps a matching analyst interpretation Unverified and seeks only its bound camera frame',async()=>{
 const analysis=a(),before=JSON.stringify(analysis),inspect=vi.fn(),seek=vi.fn();
 analysis.multicamera={duration_s:2,cameras:[{camera_id:'cam1',source_video_id:'source1',fps:10,frame_start:0,frame_end:20,playback_offset_s:0}]} as AnalysisBundle['multicamera'];
 analysis.criteria={...JSON.parse(readFileSync('public/criteria/ep005.json','utf8')),context_frames:[{frame_ref:'C1',camera_id:'cam1',source_video_id:'source1',original_frame:19,original_timestamp_s:1.9,shared_timestamp_s:1.9,scope:'Local context'}],coverage:[{camera_id:'cam1',source_video_id:'source1',sha256:'camera',source_sha256:'source',fps:10,frame_start:0,frame_end:20,observed_ranges:[]}]};
 const snapshot=JSON.stringify(analysis);
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({schema:'demodoctor.local-visual-review/v1',job_id:'job',reviewer:'Analyst',method:'Manual review',observations:[{text:'Visually consistent with closed',limitation:'Not independently verified mechanical closure',camera_id:'cam1',source_video_id:'source1',camera_sha256:'camera',source_sha256:'source',frame:19,original_timestamp_s:1.9,state:'supported'}]})));
 await act(async()=>root.render(<TemporalContext analysis={analysis} videoSrc="/video" fps={10} duration={2} jobId="job" inspectFrame={inspect} seek={seek}/>));
 const note=host.querySelector('[aria-label="Local analyst visual review"]')!;
 expect(note.textContent).toContain('Unverified · analyst interpretation');expect(note.textContent).toContain('Not independently verified mechanical closure');
 await act(async()=>note.querySelector<HTMLButtonElement>('button')!.click());
 expect(inspect).toHaveBeenCalledWith(expect.objectContaining(analysis.criteria!.context_frames![0]));expect(seek).not.toHaveBeenCalled();expect(JSON.stringify(analysis)).toBe(snapshot);expect(before).not.toBe(snapshot);
});
