import type {AnalysisBundle,TimelineMarker} from './types';
import originals from './recordedNavigation.json';
import {citationBinding,citationTime} from './citationIntegrity';
import {criterionContextTime} from './criterionContext';

/** A marker's source frame is distinct from the beginning of its cited span. */
export function markerTarget(a:AnalysisBundle,m:TimelineMarker,savedJob=false,duration=Infinity) {
  const unavailable={time:null as number|null,evidenceId:m.evidence_ids.find(id=>a.evidence_catalog.some(e=>e.evidence_id===id))??null,
    reason:'This marker has no validated source timestamp. Its source can be inspected without moving the video.'};
  const items=m.evidence_ids.map(id=>a.evidence_catalog.find(e=>e.evidence_id===id));
  if (items.some(e=>!e || citationBinding(a,e,savedJob).status!=='record_match')) return unavailable;
  let time:number|null=null;
  if (!savedJob) {
    const original=(originals as unknown as Record<string,{video_rel:string;markers:TimelineMarker[];frames:AnalysisBundle['frame_catalog']}>)[a.episode_key];
    const expected=original?.markers.find(x=>x.id===m.id);
    if (original?.video_rel!==a.video.rel || !expected || expected.t!==m.t || expected.kind!==m.kind ||
        expected.label!==m.label || JSON.stringify(expected.evidence_ids)!==JSON.stringify(m.evidence_ids)) return unavailable;
    const frame=original.frames.find(f=>f.frame_ref===m.id);
    if (frame) {
      const supplied=a.frame_catalog.find(f=>f.frame_ref===m.id);
      if (!supplied || supplied.frame_index!==frame.frame_index || supplied.timestamp_s!==frame.timestamp_s ||
          JSON.stringify(supplied.tied_evidence_ids)!==JSON.stringify(frame.tied_evidence_ids) ||
          supplied.camera_id!==frame.camera_id || supplied.source_video_id!==frame.source_video_id ||
          supplied.original_frame!==frame.original_frame || supplied.original_timestamp_s!==frame.original_timestamp_s) return unavailable;
    }
    time=expected.t; // Original marker/frame time, not a substituted evidence-start time.
  } else {
    const frame=a.frame_catalog.find(f=>f.frame_ref===m.id);
    if (frame && a.multicamera && frame.camera_id && frame.source_video_id && frame.original_frame!=null && frame.original_timestamp_s!=null) {
      const camera=a.multicamera.cameras.find(c=>c.camera_id===frame.camera_id && c.source_video_id===frame.source_video_id);
      if (camera && Math.abs(frame.timestamp_s-m.t)<=.000500001) {
        const t=frame.original_timestamp_s-camera.playback_offset_s;
        time=criterionContextTime({...frame,original_frame:frame.original_frame,original_timestamp_s:frame.original_timestamp_s,
          camera_id:frame.camera_id,source_video_id:frame.source_video_id,shared_timestamp_s:t,scope:'Original saved marker frame'},a.multicamera);
      }
    } else {
      const cited=items.find(e=>e?.evidence_id===m.id)??items[0];
      const t=cited ? citationTime(a,cited,true) : null;
      if (t!=null && Number.isFinite(m.t) && Math.abs(t-m.t)<=1e-6) time=t;
    }
  }
  if (time==null || !Number.isFinite(time) || time<0 || time>duration) return unavailable;
  // A frame can be at the end of a span. Prefer the nearest relevant source, but
  // never replace the frame's timestamp with that source's beginning.
  const ordered=items.filter(e=>e!=null).sort((x,y)=>Math.abs((citationTime(a,x,savedJob)??Infinity)-time!)-Math.abs((citationTime(a,y,savedJob)??Infinity)-time!));
  return {time,evidenceId:ordered[0]?.evidence_id??null,reason:''};
}
