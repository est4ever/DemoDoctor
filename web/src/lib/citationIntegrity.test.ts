import {it,expect,vi,afterEach} from 'vitest';
import {citationBinding,citationTime,validateCitations} from './citationIntegrity';
import {loadSavedInvestigation} from './savedInvestigations';
import registry from './recordedCitationBindings.json';
import type {AnalysisBundle,EvidenceItem} from './types';

const original:EvidenceItem={evidence_id:'E4',camera_id:'cam1',source_video_id:'source1',package:'cam1/evidence_package.json',original_evidence_id:'E0',source:'sam:video',kind:'detection',frame_start:0,frame_end:128,t_start:0,t_end:8.467,summary:'Original',claims:[]};
const bundle=():AnalysisBundle=>({episode_key:'ep010',video:{rel:'uploaded.mp4',duration_s:10.53},evidence_catalog:[structuredClone(original)],citation_bindings:{schema:'demodoctor.citation-bindings/v1',records:{E4:{status:'record_match',reason:'Original camera record',package:original.package,camera_id:'cam1',source_video_id:'source1',original_evidence_id:'E0',expected:{source:'sam:video',kind:'detection',frame_start:0,frame_end:128,t_start:0,t_end:8.467,summary:'Original',claims:[]}}}}} as AnalysisBundle);
afterEach(()=>vi.unstubAllGlobals());
it.each([false,true,null,''])('quarantines malformed camera numeric metadata before the workstation can consume it: %j',bad=>{
  for(const field of ['playback_offset_s','offset_s','frame_start']){
    const a=bundle();a.multicamera={duration_s:10,cameras:[{camera_id:'cam1',source_video_id:'source1',playback_offset_s:0,offset_s:0,frame_start:0,[field]:bad}]} as unknown as NonNullable<AnalysisBundle['multicamera']>;
    expect(()=>validateCitations(a,true)).toThrow(/quarantined/);
  }
});
it.each(['source_time','crop','mapping_frame','mapping_time'])('rejects nested boolean metadata at the saved-result parsing boundary: %s',mutation=>{
  const a=bundle();const c={camera_id:'cam1',source_video_id:'source1',playback_offset_s:0,crop:[0,0,64,64],frame_mapping:[{source_frame:0,source_timestamp_s:0}]} as any;
  const sources=[{source_video_id:'source1',timestamps_s:[0,.1]}] as any;
  if(mutation==='crop')c.crop[0]=false;
  if(mutation==='source_time')sources[0].timestamps_s[0]=false;
  if(mutation==='mapping_frame')c.frame_mapping[0].source_frame=false;
  if(mutation==='mapping_time')c.frame_mapping[0].source_timestamp_s=false;
  a.multicamera={duration_s:10,cameras:[c],sources} as AnalysisBundle['multicamera'];
  expect(()=>validateCitations(a,true)).toThrow(/quarantined/);
});
it('keeps explicit numeric zero valid at saved-result loading before any source seeking',async()=>{
  const a=bundle();a.multicamera={duration_s:10,cameras:[{camera_id:'cam1',source_video_id:'source1',playback_offset_s:0,offset_s:0,frame_start:0,crop:null}]} as unknown as AnalysisBundle['multicamera'];
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({analysis:a,tracks:{frames:{},tracks:{}}})));
  await expect(loadSavedInvestigation('valid-zero')).resolves.toMatchObject({analysis:a});
});
it.each([['t_start',80/15],['frame_start',80],['frame_end',90],['package','cam2/evidence_package.json'],['evidence_id','E999'],['camera_id','cam2'],['source_video_id','source2'],['original_evidence_id','E9'],['claims',[{type:'physical_release'}]],['summary','Changed claim']])('quarantines changed %s before reopening or seeking',async(field,bad)=>{
  const a=bundle();(a.evidence_catalog[0] as unknown as Record<string,unknown>)[field as string]=bad;
  expect(()=>validateCitations(a,true)).toThrow(/original evidence package/);
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({analysis:a,tracks:{frames:{},tracks:{}}})));
  await expect(loadSavedInvestigation('saved')).rejects.toThrow(/quarantined/);
});
it('uses validated zero time, not a truthy fallback',()=>{const a=bundle();expect(citationTime(a,a.evidence_catalog[0],true)).toBe(0);});
it('does not borrow a bundled replay authority for an uploaded episode_key',()=>{
  const a=bundle();delete a.citation_bindings;
  expect(citationBinding(a,a.evidence_catalog[0],true).status).toBe('unverifiable');
  expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it('preserves missing historical metadata as unverified, without trusting its supplied timestamp',()=>{
  const a=bundle();const b=a.citation_bindings!.records.E4;b.status='unverifiable';delete b.expected!.t_start;
  a.evidence_catalog[0].t_start=5;
  expect(()=>validateCitations(a,true)).not.toThrow();expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it('does not treat an omitted required citation field as a proven mismatch or a valid seek',()=>{
  const a=bundle();delete a.evidence_catalog[0].t_start;
  expect(citationBinding(a,a.evidence_catalog[0],true).status).toBe('unverifiable');expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it.each(['camera_id','source_video_id','original_evidence_id'] as const)('withholds seek when a camera citation omits %s',key=>{
  const a=bundle();delete a.evidence_catalog[0][key];
  expect(citationBinding(a,a.evidence_catalog[0],true).status).toBe('unverifiable');expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it('does not clamp an authoritative native record outside shared overlap to zero',()=>{
  const a=bundle();a.evidence_catalog[0].t_start=-.2;a.citation_bindings!.records.E4.expected!.t_start=-.2;
  expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it('keeps valid untimed citations inspectable without frame-zero seeking',()=>{
  const a=bundle();for(const key of ['frame_start','frame_end','t_start','t_end']) {
    (a.evidence_catalog[0] as unknown as Record<string,unknown>)[key]=null;a.citation_bindings!.records.E4.expected![key]=null;
  }
  expect(citationBinding(a,a.evidence_catalog[0],true).status).toBe('record_match');expect(citationTime(a,a.evidence_catalog[0],true)).toBeNull();
});
it('keeps all six recorded original locator registries inspectable',()=>{
  expect(Object.keys(registry)).toHaveLength(6);
  for(const [episode_key,r] of Object.entries(registry)) {
    const a={episode_key,video:{},evidence_catalog:Object.entries(r.records).map(([evidence_id,b])=>({evidence_id,...b.expected}))} as AnalysisBundle;
    expect(()=>validateCitations(a)).not.toThrow();
  }
});
