import { useEffect, useMemo, useState } from "react";
import type { MultiCameraManifest, TracksBundle } from "../lib/types";
import { VideoPane, type VideoViewMode } from "./VideoPane";
import { Button } from "./ui";
import { compositeDisplayTracks } from "../lib/compositeTracks";

const ignoreDuration = () => {};
export function MultiCameraWorkspace({manifest,jobId,t,playing,activeCamera,cameraFocus=0}:{manifest:MultiCameraManifest;jobId:string;t:number;playing:boolean;activeCamera?:string;cameraFocus?:number}) {
  const [primary,setPrimary]=useState(manifest.cameras[0].camera_id),[expanded,setExpanded]=useState(false);
  const [modes,setModes]=useState<Record<string,VideoViewMode>>({}),[tracks,setTracks]=useState<Record<string,TracksBundle>>({}),[error,setError]=useState("");
  const [display,setDisplay]=useState("all");
  useEffect(()=>{setPrimary(manifest.cameras[0].camera_id);setExpanded(false);setTracks({});setError("");setDisplay("all");setModes({});let cancelled=false;
    Promise.all(manifest.cameras.map(async c=>{const r=await fetch(`/api/jobs/${jobId}/cameras/${c.camera_id}/tracks.json`);if(!r.ok)throw Error(`${c.name}: tracks unavailable`);return[c.camera_id,await r.json()] as const;}))
      .then(entries=>{if(!cancelled)setTracks(Object.fromEntries(entries));}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};
  },[jobId,manifest]);
  useEffect(()=>{if(activeCamera&&manifest.cameras.some(c=>c.camera_id===activeCamera)){setPrimary(activeCamera);setDisplay(v=>cameraFocus>0||v!=="all"&&v!=="composite"?activeCamera:v);}},[activeCamera,manifest,cameraFocus]);
  const composite=useMemo(()=>compositeDisplayTracks(manifest,tracks),[manifest,tracks]);
  return <div className={`multicamera-workspace ${expanded&&display==="all"?"camera-expanded":""} ${manifest.cameras.length===1||display!=="all"?"camera-single":""}`}>
    <div className="multicamera-toolbar"><span>Camera-local evidence · shared clock {t.toFixed(3)}s</span>
      <label>Display <select aria-label="Camera display" value={display} onChange={e=>{setDisplay(e.target.value);if(manifest.cameras.some(c=>c.camera_id===e.target.value))setPrimary(e.target.value);}}><option value="all">All views</option>{manifest.cameras.map(c=><option key={c.camera_id} value={c.camera_id}>Only {c.name}</option>)}{manifest.source_mode==="composite"&&<option value="composite">Original composite</option>}</select></label>
      {manifest.cameras.length>1&&display==="all"&&<Button onClick={()=>setExpanded(v=>!v)}>{expanded?"Show equal views":"Expand primary view"}</Button>}</div>
    {error&&<p role="alert">{error}. Original videos remain available; no overlays synthesized.</p>}
    <div className="multicamera-views">{display==="composite"?<section aria-label="Original composite camera view"><p>Original source · display-only crop translation; no cross-camera identity or geometry fusion.</p><VideoPane src={`/api/jobs/${jobId}/sources/${manifest.sources?.[0]?.source_video_id??"source1"}.mp4`} tracks={composite} mode={modes.composite??"original"} onModeChange={mode=>setModes(v=>({...v,composite:mode}))} t={t} playing={playing} onDuration={ignoreDuration} fps={manifest.sources?.[0]?.fps??manifest.cameras[0].fps}/></section>:manifest.cameras.filter(c=>display==="all"||display===c.camera_id).map(c=><section key={c.camera_id} data-camera-id={c.camera_id} className={primary===c.camera_id?"camera-primary":""} aria-label={`${c.name} camera view`}>
      <div><Button aria-pressed={primary===c.camera_id} onClick={()=>setPrimary(c.camera_id)}>{c.name} · {c.camera_id}</Button><span> {c.motion} · source t={(t+c.playback_offset_s).toFixed(3)}s</span></div>
      <VideoPane src={`/api/jobs/${jobId}/cameras/${c.camera_id}/video.mp4`} tracks={tracks[c.camera_id]} mode={modes[c.camera_id]??"original"} onModeChange={mode=>setModes(v=>({...v,[c.camera_id]:mode}))} t={t+c.playback_offset_s} playing={playing} onDuration={ignoreDuration} fps={c.fps}/>
    </section>)}</div>
  </div>;
}
