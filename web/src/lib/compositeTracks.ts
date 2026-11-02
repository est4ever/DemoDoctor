import type { MultiCameraManifest, TracksBundle } from "./types";

/** Display-only pixel translation. Stored camera observations and IDs are untouched. */
export function compositeDisplayTracks(manifest:MultiCameraManifest,cameraTracks:Record<string,TracksBundle>):TracksBundle|null {
  const source=manifest.sources?.[0];
  if(manifest.source_mode!=="composite"||!source||manifest.cameras.some(c=>!c.crop||c.playback_offset_s!==0))return null;
  const result:TracksBundle={episode_key:"composite-display",source:`original composite ${source.source_video_id} ${source.sha256}`,provenance:"observed",
    note:"Display translation only: original composite pixels = camera-local pixels + confirmed crop origin. Namespaced labels are not cross-camera object identity or 3D fusion.",
    image_size:[source.width,source.height],fps:source.fps,t_start:null,t_end:null,frame_start:null,frame_end:null,legend:[],tracks:{},frames:{}};
  for(const c of manifest.cameras){
    const tr=cameraTracks[c.camera_id];if(!tr)continue;
    const [x,y]=c.crop!;const oid=(id:string)=>`${c.camera_id}/${id}`;
    const box=(b:number[]):[number,number,number,number]=>[b[0]+x,b[1]+y,b[2]+x,b[3]+y];
    const center=(p:number[]):[number,number]=>[p[0]+x,p[1]+y];
    for(const l of tr.legend??[])result.legend.push({...l,object_id:oid(l.object_id),label:`${c.name}: ${l.label}`});
    for(const [id,track]of Object.entries(tr.tracks??{}))result.tracks[oid(id)]={...track,object_id:oid(id),points:track.points.map(p=>({...p,bbox:box(p.bbox),centroid:center(p.centroid)}))};
    for(const [f,detections]of Object.entries(tr.frames??{})){
      result.frames[f]??=[];
      // SAM box-local mask dimensions/counts stay unchanged; only the box origin moves.
      result.frames[f].push(...detections.map(d=>({...d,object_id:oid(d.object_id),bbox:box(d.bbox),centroid:center(d.centroid)})));
    }
    if(tr.t_start!=null)result.t_start=result.t_start==null?tr.t_start:Math.min(result.t_start,tr.t_start);
    if(tr.t_end!=null)result.t_end=result.t_end==null?tr.t_end:Math.max(result.t_end,tr.t_end);
    if(tr.frame_start!=null)result.frame_start=result.frame_start==null?tr.frame_start:Math.min(result.frame_start,tr.frame_start);
    if(tr.frame_end!=null)result.frame_end=result.frame_end==null?tr.frame_end:Math.max(result.frame_end,tr.frame_end);
  }
  return result;
}
