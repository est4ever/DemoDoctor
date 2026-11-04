import { expect,it } from 'vitest';
import { readFileSync } from 'node:fs';
import { temporalContext,validateVisualReview } from './temporalContext';
import type { AnalysisBundle } from './types';
const saved=(ep:string):AnalysisBundle=>JSON.parse(readFileSync(`public/data/${ep}/analysis.json`,'utf8'));
export const cameraAnalysis=()=>({ ...saved('ep005'), episode_key:'multicamera', dry_run:false, frame_catalog:[
  {frame_ref:'F0',frame_index:0,timestamp_s:0,camera_id:'cam1',source_video_id:'source1',original_frame:0},
  {frame_ref:'F1',frame_index:19,timestamp_s:1.9,camera_id:'cam1',source_video_id:'source1',original_frame:19}],
  multicamera:{duration_s:2,cameras:[{camera_id:'cam1',source_video_id:'source1',fps:10,frame_start:0,frame_end:20,playback_offset_s:0,sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null}]},
  criteria:{context_frames:[0,5,19,20].map((n,i)=>({frame_ref:'C'+i,camera_id:'cam1',source_video_id:'source1',original_frame:n,original_timestamp_s:n/10,shared_timestamp_s:n/10,scope:'Local original-frame context'})),
    coverage:[{camera_id:'cam1',source_video_id:'source1',sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null,fps:10,frame_start:0,frame_end:20,observed_ranges:[[0,2],[5,6]]}]}
}) as unknown as AnalysisBundle;

it.each(['ep005','ep003','ep010','ep013','ep006'])('uses %s saved frame provenance without modifying results',ep=>{
 const a=saved(ep),before=JSON.stringify(a),frames=temporalContext(a,`/replays/${ep}/video.mp4`,30,100);
 expect(frames.length).toBeGreaterThan(0);expect(frames.length).toBeLessThanOrEqual(6);
 expect(frames.every(f=>f.original_timestamp_s===f.original_frame/30)).toBe(true);
 expect(frames.every(f=>f.museReferences.length>0)).toBe(true);expect(JSON.stringify(a)).toBe(before);
});
it('separates original context, actual saved Muse references and missing SAM observations',()=>{
 const a=cameraAnalysis(),frames=temporalContext(a,'/unused',10,2,'job');
 expect(frames.map(f=>f.original_frame)).toEqual([0,5,19]);
 expect(frames.map(f=>f.museReferences)).toEqual([['F0'],[],['F1']]);
 expect(frames.map(f=>f.observedBySam)).toEqual([true,true,false]);
 a.frame_catalog[0]={...a.frame_catalog[0],camera_id:'cam2'} as typeof a.frame_catalog[0];
 expect(temporalContext(a,'/unused',10,2,'job')[0].museReferences).toEqual([]);
 expect(temporalContext(a,'/unused',10,2,'../private')).toEqual([]);
});
it('does not borrow historical PILOT Muse references or show dry-run inference context',()=>{
 const a=JSON.parse(readFileSync('../data/submission_demo/pilot/audit/after/analysis.json','utf8'));
 const frames=temporalContext(a,'/api/recorded-pilot/video.mp4',30,737/30);
 expect(frames.length).toBeGreaterThan(0);expect(frames.every(f=>!f.museReferences.length)).toBe(true);
 expect(temporalContext({...a,dry_run:true},'/video',30,100)).toEqual([]);
});
it('rejects camera/hash/time/job mismatches in optional local visual reviews',()=>{
 const a=cameraAnalysis();const raw={schema:'demodoctor.local-visual-review/v1',job_id:'job',reviewer:'Analyst',method:'Manual original-frame review',observations:[{text:'Visually consistent with closed',limitation:'Not independently verified mechanical closure',camera_id:'cam1',source_video_id:'source1',camera_sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),frame:19,original_timestamp_s:1.9}]};
 expect(validateVisualReview(raw,a,'job')).toEqual(raw);
 for(const patch of [{camera_id:'cam2'},{camera_sha256:'other'},{source_sha256:'other'},{frame:20},{original_timestamp_s:0},{limitation:''}])expect(validateVisualReview({...raw,observations:[{...raw.observations[0],...patch}]},a,'job')).toBeNull();
 expect(validateVisualReview(raw,a,'other')).toBeNull();expect(validateVisualReview({...raw,observations:[null]},a,'job')).toBeNull();
});

it('uses new native temporal selections without borrowing Muse references or filling missing SAM frames',()=>{
 const a=cameraAnalysis(),before=JSON.stringify(a);
 Object.assign(a.multicamera!.cameras[0],{sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null});
 Object.assign(a.criteria!.coverage![0],{sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null});
 a.criteria!.temporal_evidence=[{camera_id:'cam1',source_video_id:'source1',camera_motion:'static',adjacent_box_steps:[],full_source_final_frame_assessed:false,limitations:[],frames:[3,7,19].map(n=>({frame_ref:'T_cam1_'+n,camera_id:'cam1',source_video_id:'source1',original_frame:n,original_timestamp_s:n/10,shared_timestamp_s:n/10,scope:'New local temporal selection',sam_observation_available:n===3,selection_reasons:['Gap boundary; not verified pickup'],camera_sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null}))}];
 const snapshot=JSON.stringify(a),frames=temporalContext(a,'/unused',10,2,'job');
 expect(frames.map(f=>f.original_frame)).toEqual([3,7,19]);
 expect(frames.map(f=>f.observedBySam)).toEqual([true,false,false]);
 expect(frames.map(f=>f.museReferences)).toEqual([[],[],['F1']]);
 expect(JSON.stringify(a)).toBe(snapshot);expect(before).not.toBe(snapshot);
});

it.each(['hash','crop','parent-camera','coverage','renamed-legacy','missing-hash','null-frame'])('quarantines invalid cached temporal %s without a legacy fallback',kind=>{
 const a=cameraAnalysis();Object.assign(a.multicamera!.cameras[0],{sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null});
 Object.assign(a.criteria!.coverage![0],{sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null});
 const f={...a.criteria!.context_frames![1],frame_ref:'T_cam1_5',camera_sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),crop:null} as import('./types').CriterionContextFrame;
 const r={camera_id:'cam1',source_video_id:'source1',camera_motion:'static',frames:[f],adjacent_box_steps:[],full_source_final_frame_assessed:false,limitations:[]};
 if(kind==='hash')f.camera_sha256='c'.repeat(64);
 if(kind==='crop')f.crop=[8,8,16,16];
 if(kind==='parent-camera')r.camera_id='cam2';
 if(kind==='coverage')a.criteria!.coverage![0].source_sha256='c'.repeat(64);
 if(kind==='renamed-legacy'){f.frame_ref='C5';delete f.camera_sha256;}
 if(kind==='missing-hash')delete f.source_sha256;
 if(kind==='null-frame')r.frames=[null as unknown as typeof f];
 a.criteria!.temporal_evidence=[r];
 expect(temporalContext(a,'/unused',10,2,'job')).toEqual([]);
});
