import {it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {endpointMeasurement,observationSummary,readableEvidence} from './readableEvidence';
import type {AnalysisBundle,TracksBundle} from './types';
const json=(p:string)=>JSON.parse(readFileSync(resolve(p),'utf8'));
const pilot=()=>json('../data/submission_demo/pilot/audit/after/analysis.json') as AnalysisBundle;
const tracks=()=>json('../data/submission_demo/pilot/job/tracks.json') as TracksBundle;
it('keeps model displacement proposals unverified rather than observed, even with numeric claims',()=>{
  const a=pilot();a.evidence_catalog=[{evidence_id:'H0',source:'muse:hypothesis',kind:'inferred',status_context:'unverified',claims:[{type:'displacement',value_px:987654}]}];
  expect(observationSummary(a).join(' ')).not.toContain('987654');
  expect(readableEvidence(a.evidence_catalog[0])).toContain('Unverified');
});
it('independently recomputes the narrow genuine endpoint measurement and preserves original data',()=>{
  const a=pilot(),t=tracks(),before=JSON.stringify([a,t]);
  expect(endpointMeasurement(a,a.evidence_catalog[0],t)?.value).toBeCloseTo(609.01,2);
  expect(observationSummary(a,{tracks:t}).join(' ')).toContain('609.01');
  expect(JSON.stringify([a,t])).toBe(before);
});
it('withholds a number when an endpoint is missing, mismatched, or belongs to another source',()=>{
  const a=pilot();
  expect(endpointMeasurement(a,a.evidence_catalog[0])).toBeNull();
  for(const corruption of ['missing','box','time','episode','provenance','malformed-box']){
    const t=tracks(),p=t.tracks['screwdriver:0'].points;
    if(corruption==='missing')p.shift();
    if(corruption==='box')p[0].bbox=[0,0,10,10];
    if(corruption==='time')p[0].t=5;
    if(corruption==='episode')t.episode_key='another';
    if(corruption==='provenance')(t as {provenance:string}).provenance='inferred';
    if(corruption==='malformed-box')(p[0] as unknown as {bbox:null}).bbox=null;
    expect(endpointMeasurement(a,a.evidence_catalog[0],t),corruption).toBeNull();
  }
});
it('does not bypass citation quarantine or treat a copied claim as a new independent measurement',()=>{
  const a=pilot();(a.evidence_catalog[0].claims![0] as {value_px:number}).value_px=42;
  expect(()=>endpointMeasurement(a,a.evidence_catalog[0],tracks())).toThrow(/quarantined/);
});
it('does not describe a gripper reading as measured without its original sensor samples',()=>{
  const a=json('public/data/ep010/analysis.json');
  expect(observationSummary(a).join(' ')).not.toContain('Gripper opening was measured');
  expect(observationSummary(a,{joints:json('public/data/ep010/joints.json')}).join(' ')).toContain('Gripper opening was measured');
});
