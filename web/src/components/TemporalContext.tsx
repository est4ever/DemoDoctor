import { useEffect, useMemo, useState } from 'react';
import type { AnalysisBundle, CriterionContextFrame } from '../lib/types';
import { temporalContext, validateVisualReview, type TemporalFrame, type VisualReview } from '../lib/temporalContext';

function Preview({frame}:{frame:TemporalFrame}) {
  const [image,setImage]=useState<string>(),[unavailable,setUnavailable]=useState(false);
  useEffect(()=>{
    let cancelled=false;const v=document.createElement('video');v.muted=true;v.preload='auto';v.src=frame.videoSrc;
    setImage(undefined);setUnavailable(false);
    const timeout=window.setTimeout(()=>{if(!cancelled)setUnavailable(true);},12000);
    const capture=()=>{
      if(cancelled||v.readyState<2||v.seeking)return;
      try {const canvas=document.createElement('canvas');canvas.width=160;canvas.height=Math.max(1,Math.round(160*v.videoHeight/v.videoWidth));canvas.getContext('2d')!.drawImage(v,0,0,canvas.width,canvas.height);setImage(canvas.toDataURL('image/jpeg',.75));window.clearTimeout(timeout);}
      catch {setUnavailable(true);}
    };
    const seek=()=>{if(Math.abs(v.currentTime-frame.original_timestamp_s)>1e-6)v.currentTime=frame.original_timestamp_s;else capture();};
    v.addEventListener('loadeddata',seek);v.addEventListener('seeked',capture);v.addEventListener('error',()=>{if(!cancelled)setUnavailable(true);});v.load();
    return()=>{cancelled=true;window.clearTimeout(timeout);v.pause();v.removeAttribute('src');v.load();};
  },[frame.videoSrc,frame.original_timestamp_s]);
  return image?<img src={image} alt={`Original ${frame.camera_id} frame ${frame.original_frame}`} style={{width:'100%',height:80,objectFit:'contain'}}/>:<span>{unavailable?'Frame preview unavailable; seek original footage':'Loading original frame…'}</span>;
}

export function TemporalContext({analysis:a,videoSrc,fps,duration,jobId,inspectFrame,seek,previewsEnabled=true}:{analysis:AnalysisBundle;videoSrc:string;fps:number;duration:number;jobId?:string|null;inspectFrame?:(f:CriterionContextFrame)=>void;seek:(t:number,o?:{pause?:boolean})=>void;previewsEnabled?:boolean}) {
  const frames=useMemo(()=>temporalContext(a,videoSrc,fps,duration,jobId),[a,videoSrc,fps,duration,jobId]);
  const [review,setReview]=useState<VisualReview|null>(null),[invalid,setInvalid]=useState(false);
  useEffect(()=>{
    setReview(null);setInvalid(false);if(!jobId||!/^[A-Za-z0-9_-]{1,128}$/.test(jobId))return;
    const controller=new AbortController();
    fetch(`/local-reviews/${jobId}.json`,{signal:controller.signal}).then(async r=>{
      if(r.status===404)return;if(!r.ok)throw Error('Local visual review unavailable');
      if(!r.headers.get('content-type')?.includes('application/json'))return; // SPA fallback means no optional note.
      const raw=await r.json(),valid=validateVisualReview(raw,a,jobId);if(!controller.signal.aborted){setReview(valid);setInvalid(!valid);}
    }).catch(()=>{if(!controller.signal.aborted)setInvalid(true);});
    return()=>controller.abort();
  },[a,jobId]);
  if(!frames.length&&!review&&!invalid)return null;
  const open=(f:TemporalFrame)=>a.multicamera?inspectFrame?.(f):seek(f.shared_timestamp_s,{pause:true});
  return <section aria-label="Original temporal context" className="model-explanation">
    <h3>Original temporal context</h3>
    <p>Original footage for inspection, not verified action support. Saved Muse catalog references identify recorded inputs, not correct interpretation. Other frames are local context; no claim Muse received them.</p>
    <div style={{display:'grid',gridTemplateColumns:'repeat(2,minmax(0,1fr))',gap:8}}>{frames.map(f=><button key={`${f.camera_id}-${f.original_frame}`} onClick={()=>open(f)} aria-label={`Inspect original ${f.camera_id} frame ${f.original_frame}`} style={{textAlign:'left'}}>
      {previewsEnabled?<Preview frame={f}/>:<span>Open technical details to load the original frame preview.</span>}<span>{f.camera_id} · frame {f.original_frame} · {f.original_timestamp_s.toFixed(3)}s ↗</span><br/>
      <small>{f.museReferences.length?`Saved Muse catalog: ${f.museReferences.join(', ')}`:'Local context; not a saved Muse reference'}</small><br/>
      {f.selection_reasons?.length ? <small>{f.selection_reasons.join('; ')}<br/></small> : null}
      {f.observedBySam!==null&&<small>{f.observedBySam?'SAM observation returned at this frame; identity unverified':'No returned SAM observation at this frame'}</small>}
    </button>)}</div>
    {invalid&&<p role="alert">Local analyst review unavailable or its camera/hash/frame provenance does not match. No interpretation was applied.</p>}
    {review&&<section aria-label="Local analyst visual review"><h3>Local analyst visual review</h3><p>Separate from the original SAM/Muse outputs. <strong>Unverified visual interpretation</strong>; never a verified criterion or mechanical measurement.</p>
      {review.observations.map((o,i)=><article key={i}><span className="provenance uncertain">Unverified · analyst interpretation</span><p>{o.text}</p><p>{o.limitation}</p>
        <button onClick={()=>{const frame=frames.find(f=>f.camera_id===o.camera_id&&f.original_frame===o.frame);if(frame)open(frame);}} disabled={!frames.some(f=>f.camera_id===o.camera_id&&f.original_frame===o.frame)}>Inspect {o.camera_id} frame {o.frame} · {o.original_timestamp_s.toFixed(3)}s ↗</button>
        <details><summary>Analyst review provenance</summary><p>{review.reviewer} · {review.method}</p><p>{o.camera_id}/{o.source_video_id}; native frame {o.frame}. Camera SHA256: {o.camera_sha256}. Source SHA256: {o.source_sha256}.</p><p>No independent closure validation method or measurement is supplied.</p></details>
      </article>)}</section>}
  </section>;
}
