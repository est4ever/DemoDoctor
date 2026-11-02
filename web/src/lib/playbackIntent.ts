import type {AnalysisBundle} from './types';
import {citationBinding,citationTime} from './citationIntegrity';

export const PLAYBACK_KEY='demodoctor.playback.v1:';
export function routeIntent(hash=window.location.hash) {
  const [route,query='']=hash.replace(/^#/,'').split('?');const q=new URLSearchParams(query);
  const t=q.get('t');
  return {route,evidence:q.get('evidence'),time:t!==null && t.trim()!=='' && Number.isFinite(Number(t)) && Number(t)>=0?Number(t):null};
}
export function playbackBinding(a:AnalysisBundle,savedJob=false) {
  return JSON.stringify([a.video.rel,a.multicamera?.cameras.map(c=>[c.camera_id,c.source_video_id,c.sha256,c.source_sha256,c.crop]),
    a.evidence_catalog.map(e=>{const b=citationBinding(a,e,savedJob);return [e.evidence_id,b.status,'package_sha256' in b?b.package_sha256:null];})]);
}
export function initialPlayback(a:AnalysisBundle,key:string,duration:number,savedJob=false,fps=30) {
  const bound=playbackBinding(a,savedJob),intent=routeIntent();let stored:{time:number;evidence?:string;binding:string}|null=null;
  try {const raw=JSON.parse(sessionStorage.getItem(PLAYBACK_KEY+key)||'null');if(raw?.binding===bound && typeof raw.time==='number' && Number.isFinite(raw.time) && raw.time>=0 && raw.time<=duration)stored=raw;} catch {/* storage is optional */}
  const rate=Number.isFinite(fps)&&fps>0?fps:30;
  const shortEnd=Math.max(0,(Math.ceil(duration*rate)-1)/rate);
  let time=stored?.time??(duration<1?Math.min(duration,shortEnd):1);
  let evidenceId=stored?.evidence??a.initial_evidence_id??a.evidence_catalog[0]?.evidence_id??null;
  const ownRoute=savedJob?intent.route===key:intent.route===a.episode_key;
  if (ownRoute && intent.evidence) {
    const e=a.evidence_catalog.find(e=>e.evidence_id===intent.evidence);
    if(e) {evidenceId=e.evidence_id;const t=citationTime(a,e,savedJob);if(t!=null && t<=duration)time=t;}
  } else if (ownRoute && intent.time!=null && intent.time<=duration) time=intent.time;
  return {time,evidenceId,binding:bound};
}
export function savePlayback(key:string,binding:string,time:number,evidence:string|null) {
  if(!Number.isFinite(time)||time<0)return;
  try {sessionStorage.setItem(PLAYBACK_KEY+key,JSON.stringify({binding,time,evidence}));}catch {/* private browsing/quota must not break playback */}
}
