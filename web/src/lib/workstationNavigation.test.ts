// @vitest-environment jsdom
import {beforeEach,describe,it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import type {AnalysisBundle} from './types';
import registry from './recordedNavigation.json';
import {markerTarget} from './timelineNavigation';
import {initialPlayback,playbackBinding,PLAYBACK_KEY,routeIntent,savePlayback} from './playbackIntent';
import {observationSummary} from './readableEvidence';
const load=(key:string):AnalysisBundle=>JSON.parse(readFileSync(new URL('../../../'+(registry as Record<string,{analysis_path:string}>)[key].analysis_path,import.meta.url),'utf8'));
beforeEach(()=>{sessionStorage.clear();window.history.replaceState({},'','/#ep005');});
describe('recorded marker navigation',()=>{
  for(const [key,r] of Object.entries(registry))it(`${key}: all original markers retain their own timestamps and unchanged frame authority`,()=>{
    const a=load(key),bytes=readFileSync(new URL('../../../'+r.analysis_path,import.meta.url));
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(r.analysis_sha256);
    expect(a.timeline_markers).toEqual(r.markers);expect(a.frame_catalog).toEqual(r.frames);
    for(const m of a.timeline_markers)expect(markerTarget(a,m).time).toBe(m.t);
  });
  it('does not redirect EP013 marker 3 to the beginning of its evidence span',()=>{
    const a=load('ep013'),m=a.timeline_markers[2];
    expect(markerTarget(a,m).time).toBe(53.9);expect(markerTarget(a,m).evidenceId).toBe('E6');
  });
  it('withholds altered markers, frames, unknown IDs and out-of-video timestamps',()=>{
    const a=load('ep013'),m=a.timeline_markers[2];
    expect(markerTarget(a,{...m,t:5.333}).time).toBeNull();
    expect(markerTarget(a,{...m,evidence_ids:['missing']}).time).toBeNull();
    expect(markerTarget(a,m,false,1).time).toBeNull();
    a.frame_catalog.find(f=>f.frame_ref===m.id)!.frame_index=0;
    expect(markerTarget(a,m).time).toBeNull();
    const foreign=load('ep013');foreign.frame_catalog.find(f=>f.frame_ref===m.id)!.camera_id='foreign-camera';
    expect(markerTarget(foreign,m).time).toBeNull();
  });
  it('does not let uploaded jobs inherit replay marker authority',()=>{
    const a=load('ep013');expect(markerTarget(a,a.timeline_markers[2],true).time).toBeNull();
  });
  it('preserves the existing quarantine on altered evidence spans and packages',()=>{
    const a=load('ep013');a.evidence_catalog.find(e=>e.evidence_id==='E6')!.t_start=0;
    expect(()=>markerTarget(a,a.timeline_markers[2])).toThrow(/quarantined/);
  });
});
describe('paused initial position and intentional restoration',()=>{
  it('ignores editorial end highlights for a fresh investigation',()=>{
    const a=load('ep005');expect(a.initial_seek_s).toBeGreaterThan(60);
    expect(initialPlayback(a,'ep005',69.67).time).toBe(1);
  });
  it('uses the last available short-video time without inventing frames',()=>{
    expect(initialPlayback(load('ep005'),'ep005',.4,false,10).time).toBeCloseTo(.3);
    expect(initialPlayback(load('ep005'),'ep005',.45,false,10).time).toBe(.4);
  });
  it('preserves explicit zero-time and other user links',()=>{
    window.history.replaceState({},'','/#ep005?t=0');expect(initialPlayback(load('ep005'),'ep005',70).time).toBe(0);
    window.history.replaceState({},'','/#ep005?t=12');expect(initialPlayback(load('ep005'),'ep005',70).time).toBe(12);
    expect(routeIntent('#ep005?t=NaN').time).toBeNull();expect(routeIntent('#ep005?t=-1').time).toBeNull();
  });
  it('explicit evidence uses its canonical source, never the editorial highlight',()=>{
    const a=load('pilot');window.history.replaceState({},'','/#pilot?evidence=E0');
    expect(initialPlayback(a,'pilot',40).time).toBe(0);
    window.history.replaceState({},'','/#pilot?evidence=E2');expect(initialPlayback(a,'pilot',40).time).toBe(1);
  });
  it('restores intentional zero and other positions only for the same bound source',()=>{
    const a=load('ep005'),binding=playbackBinding(a);
    savePlayback('ep005',binding,0,'E1');expect(initialPlayback(a,'ep005',70).time).toBe(0);
    savePlayback('ep005',binding,23,'E1');expect(initialPlayback(a,'ep005',70).time).toBe(23);
    a.video.rel='another-video.mp4';expect(initialPlayback(a,'ep005',70).time).toBe(1);
    expect(JSON.parse(sessionStorage.getItem(PLAYBACK_KEY+'ep005')!).time).toBe(23);
  });
  it('ignores malformed, nonfinite and out-of-range saved positions',()=>{
    const a=load('ep005');for(const time of [-1,90,'5',null]){
      sessionStorage.setItem(PLAYBACK_KEY+'ep005',JSON.stringify({binding:playbackBinding(a),time}));
      expect(initialPlayback(a,'ep005',70).time).toBe(1);
    }
    sessionStorage.setItem(PLAYBACK_KEY+'ep005','{');expect(initialPlayback(a,'ep005',70).time).toBe(1);
  });
});
it('explains narrow observations without deriving outcomes from reference labels',()=>{
  const a=load('ep013');a.criteria=JSON.parse(readFileSync(resolve('public/criteria/ep013.json'),'utf8'));
  expect(observationSummary(a).join(' ')).toContain('outside the target');
  a.title='Success reference';expect(observationSummary(a).join(' ')).not.toContain('Success reference');
  const joints=JSON.parse(readFileSync(resolve('public/data/ep010/joints.json'),'utf8'));
  const tracks=JSON.parse(readFileSync(resolve('../data/submission_demo/pilot/job/tracks.json'),'utf8'));
  expect(observationSummary(load('ep010'),{joints}).join(' ')).toContain('Opening alone does not establish');
  expect(observationSummary(load('pilot'),{tracks}).join(' ')).toContain('609.01');
  const empty=load('ep005');empty.evidence_catalog=[];
  expect(observationSummary(empty).join(' ')).toContain('No source-bound image-space measurement');
  empty.dry_run=true;expect(observationSummary(empty).join(' ')).toContain('Providers were skipped');
});
