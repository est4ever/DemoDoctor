import type { AnalysisBundle, CriterionContextFrame } from './types';
import { diagnosticFrameCatalog } from './diagnosticFrameCatalog';
import { criterionContextTime } from './criterionContext';

export type TemporalFrame = CriterionContextFrame & {
  videoSrc: string; provenance: string; museReferences: string[]; observedBySam: boolean | null;
};

/** Original recorded references only. Context never becomes verified task support. */
export function temporalContext(a: AnalysisBundle, videoSrc: string, fps: number, duration: number, jobId?: string | null): TemporalFrame[] {
  if (a.dry_run || !(fps > 0) || !(duration > 0)) return [];
  const saved = diagnosticFrameCatalog(a);
  const input = a.criteria?.context_frames?.length ? a.criteria.context_frames : saved.frames.map(f => ({
    frame_ref: f.frame_ref, camera_id: 'primary', source_video_id: 'recorded', original_frame: f.frame_index,
    original_timestamp_s: f.frame_index/fps, shared_timestamp_s: f.frame_index/fps, scope: saved.source,
  }));
  const refs = input.length ? input : a.evidence_catalog.flatMap(e => [e.frame_start,e.frame_end].filter((f): f is number => Number.isInteger(f)).map(f => ({
    frame_ref: `${e.evidence_id}:frame${f}`, camera_id: 'primary', source_video_id: 'recorded', original_frame:f,
    original_timestamp_s:f/fps, shared_timestamp_s:f/fps, scope:'Original evidence-catalog frame; not a Muse input reference',
  })));
  const result: TemporalFrame[] = [];
  for (const f of refs) {
    const camera = a.multicamera?.cameras.find(c=>c.camera_id===f.camera_id && c.source_video_id===f.source_video_id);
    const time = a.multicamera ? criterionContextTime(f,a.multicamera) : f.original_frame/fps;
    if (time == null || !Number.isInteger(f.original_frame) || f.original_frame<0 || time>=duration ||
        !Number.isFinite(f.original_timestamp_s) || Math.abs(time-f.shared_timestamp_s)>.001) continue;
    if (a.multicamera && (!camera || !/^cam[123]$/.test(camera.camera_id) || !/^source[123]$/.test(camera.source_video_id) || !jobId || !/^[A-Za-z0-9_-]{1,128}$/.test(jobId))) continue;
    const src = camera ? `/api/jobs/${jobId}/cameras/${camera.camera_id}/video.mp4` : videoSrc;
    if (!src.startsWith('/') || src.startsWith('//')) continue;
    if (result.some(x=>x.camera_id===f.camera_id && x.original_frame===f.original_frame)) continue;
    // Same frame in a different camera/package is never treated as the same input.
    const museReferences = (a.muse_explanation ? saved.frames : []).filter(raw=>{
      const r=raw as typeof raw & {camera_id?:string; source_video_id?:string; original_frame?:number};
      return camera ? r.camera_id===f.camera_id && r.source_video_id===f.source_video_id && r.original_frame===f.original_frame
        : r.frame_index===f.original_frame;
    }).map(r=>r.frame_ref);
    const coverage = a.criteria?.coverage?.find(c=>c.camera_id===f.camera_id);
    const observed = coverage ? coverage.observed_ranges.some(([start,end])=>f.original_frame>=start && f.original_frame<end) : null;
    result.push({...f,videoSrc:src,provenance:f.scope,museReferences,observedBySam:observed});
  }
  return result.sort((x,y)=>x.shared_timestamp_s-y.shared_timestamp_s || x.camera_id.localeCompare(y.camera_id)).slice(0,6);
}

export type VisualReview = { schema:'demodoctor.local-visual-review/v1'; job_id:string; reviewer:string; method:string;
  observations:Array<{text:string; camera_id:string; source_video_id:string; camera_sha256:string; source_sha256:string;
    frame:number; original_timestamp_s:number; limitation:string}> };

/** Optional local analyst text is hash-bound and always Unverified; no state field is trusted. */
export function validateVisualReview(raw: unknown, a: AnalysisBundle, jobId: string): VisualReview | null {
  const r=raw as VisualReview;
  if (!r || r.schema!=='demodoctor.local-visual-review/v1' || r.job_id!==jobId || typeof r.reviewer!=='string' || !r.reviewer || typeof r.method!=='string' || !r.method || !Array.isArray(r.observations) || !r.observations.length || r.observations.length>6 || !a.criteria?.coverage?.length) return null;
  for (const o of r.observations) {
    if(!o || typeof o!=='object')return null;
    const c=a.criteria.coverage.find(c=>c.camera_id===o.camera_id && c.source_video_id===o.source_video_id);
    if (!c || typeof o.text!=='string' || !o.text || typeof o.limitation!=='string' || !o.limitation || !Number.isInteger(o.frame) || o.frame<c.frame_start || o.frame>=c.frame_end ||
      o.camera_sha256!==c.sha256 || o.source_sha256!==c.source_sha256 || !Number.isFinite(o.original_timestamp_s) || Math.abs(o.original_timestamp_s-o.frame/c.fps)>1e-6) return null;
    if(!a.criteria?.context_frames?.some(f=>f.camera_id===o.camera_id && f.source_video_id===o.source_video_id && f.original_frame===o.frame && Math.abs(f.original_timestamp_s-o.original_timestamp_s)<1e-6))return null;
  }
  return r;
}
