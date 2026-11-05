import {useEffect,useState} from 'react';
import {NativeVideoProposals,type NativeResult} from './NativeVideoProposals';

type Reference={frame:number;timestamp_s:number;frame_sha256:string;source_sha256:string;camera_id:string;native_pts:number;time_base:string};
type Result={job_id:string;native_upload?:boolean;failure_detected:boolean;failure_type:string|null;scope:string;uncertainty:string;source_label:string;source_sha256:string;
  time_interval:{start_frame:number;end_frame_exclusive:number;start_seconds:number;last_frame_seconds:number}|null;
  source_citations:Reference[];observed_evidence:Array<{evidence_id:string;minimum_lateral_separation_px:number;stable_features:number;median_translation_diameter_px:number}>;
  muse_status:string;muse_note:string;native_video?:NativeResult;rejected_frames:Array<{frame:number;reason:string}>};
type Options={available:boolean;reason?:string;sources:Array<{key:string;label:string}>};
async function response<T>(url:string,options?:RequestInit):Promise<T>{const r=await fetch(url,options);const value=await r.json();if(!r.ok)throw Error(value.detail??'Assessment unavailable');return value;}

export function PlacementAssessment({jobId,episodeKey,seek}:{jobId?:string|null;episodeKey:string;seek:(t:number,opts?:{pause?:boolean})=>void}){
  const [options,setOptions]=useState<Options|null>(null),[selected,setSelected]=useState(episodeKey),[storedResult,setResult]=useState<Result|null>(null);
  const result=storedResult?.job_id===jobId?storedResult:null;
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[frame,setFrame]=useState<number|null>(null);
  useEffect(()=>{let active=true;
    setError('');setFrame(null);
    if(jobId)response<Result>(`/api/placement/jobs/${jobId}`).then(r=>{if(active){setResult(r);setFrame(r.source_citations[0]?.frame??null);}}).catch(e=>{if(active)setError(e.message);});
    else response<Options>('/api/placement/options').then(o=>{if(active){
      if(typeof o.available!=='boolean'||!Array.isArray(o.sources)){setOptions({available:false,sources:[],reason:'Approved assisted inputs unavailable.'});return;}
      setOptions(o);setSelected(o.sources.some(s=>s.key===episodeKey)?episodeKey:'');
    }}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;};
  },[jobId,episodeKey]);
  const run=async()=>{if(busy)return;setBusy(true);setError('');try{const r=await response<Result>(`/api/placement/assess/${encodeURIComponent(selected)}`,{method:'POST'});window.location.hash=`job/${r.job_id}`;}catch(e){setError(e instanceof Error?e.message:'Assessment failed');}finally{setBusy(false);}};
  const ref=result?.source_citations.find(r=>r.frame===frame);
  return <section className="placement-assessment" aria-label="Assisted final-placement assessment">
    <h2>{result?.native_upload?'Experimental native-video investigation':'Final-placement assessment · Assisted'}</h2>
    <p>{result?.native_upload?'Original uploaded footage and source-linked model proposals. No assisted rack template, old masks or independently verified physical measurements were supplied.':'Checks the final half-second for a stable green plate-like region outside a registered rack. Requires an approved SAM rack template and green-plate task prior. Does not discover arbitrary failures.'}</p>
    {error&&<p role={jobId?'alert':'status'}>{error}</p>}
    {!jobId&&options?.available&&<><label>Approved source recording<select aria-label="Placement source recording" disabled={busy} value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Select an approved recording</option>{options.sources.map(s=><option key={s.key} value={s.key}>{s.label}</option>)}</select></label>
      <p>The selected source opens as a separate saved investigation. Historical findings remain unchanged. No provider charge.</p>
      <button disabled={busy||!selected} onClick={run}>{busy?'Computing source evidence…':'Assess final placement offline'}</button></>}
    {!jobId&&options&&!options.available&&<p>Unverified — {options.reason}</p>}
    {!jobId&&options?.available&&<p>New uploads without registered source/task/template evidence remain Unverified. This button assesses only the explicitly selected approved source.</p>}
    {result&&<>
      <h3>{result.native_upload?'Task outcome Uncertain':result.failure_detected?'Visible final-placement failure':'Final placement Unverified'}</h3>
      <p>{result.native_upload?'Model-proposed events are displayed below with original source frames. Event timing is a proposal, not independently verified failure onset.':result.failure_detected?'A plate-like green region remains visibly outside the rack at the recording end.':'No supported outside-rack finding. This does not establish task success.'}</p>
      {result.time_interval&&<button onClick={()=>seek(result.time_interval!.start_seconds,{pause:true})}>Seek failure evidence · {result.time_interval.start_seconds.toFixed(6)}–{result.time_interval.last_frame_seconds.toFixed(6)} s · frames {result.time_interval.start_frame}–{result.time_interval.end_frame_exclusive-1}</button>}
      <p><strong>Earlier failure onset: Unknown. Physical cause: Unverified.</strong></p>
      {result.observed_evidence.map(e=><p key={e.evidence_id}>{e.evidence_id}: minimum plate/rack separation {e.minimum_lateral_separation_px} pixels; {e.stable_features} persistent features; median translation diameter {e.median_translation_diameter_px.toFixed(4)} pixels. This is not the maximum displacement of every feature or a calibrated physical measurement.</p>)}
      <p>{result.uncertainty}</p>
      <p>Muse: {result.muse_status}. {result.muse_note}</p>
      {jobId&&<NativeVideoProposals key={jobId} jobId={jobId} result={result.native_video} seek={seek} showFrame={setFrame} allowPrepare={!result.native_upload&&!result.native_video}/>}
      <details><summary>Source frames, masks and measurement limitations</summary>
        <p>{result.native_upload?'Original proposal-citation frames only. No SAM masks, object trajectories or calibrated geometry are available in this mode.':'Yellow: offline green-plate candidate pixels. Cyan: registered genuine SAM rack template. Neither is a new SAM video result. Semantic plate identity is inferred; absolute error bounds and calibrated depth are unavailable.'}</p>
        <label>Evidence frame<select aria-label="Placement evidence frame" value={frame??''} onChange={e=>setFrame(Number(e.target.value))}>{result.source_citations.map(r=><option key={r.frame} value={r.frame}>{r.frame} · {r.timestamp_s.toFixed(6)} s</option>)}</select></label>
        {ref&&<><button onClick={()=>seek(ref.timestamp_s,{pause:true})}>Seek original frame {ref.frame}</button><img style={{width:'100%'}} src={`/api/placement/jobs/${jobId}/frames/${ref.frame}/source`} alt={`Original source frame ${ref.frame}`}/>{result.native_video?.proposal_only_frames?.includes(ref.frame)?<p>This is a model-proposal citation only. No segmentation or event measurement is registered for this frame.</p>:<img style={{width:'100%'}} src={`/api/placement/jobs/${jobId}/frames/${ref.frame}/overlay`} alt={`Assisted plate candidates and registered rack overlay at frame ${ref.frame}`}/>}<p>Camera {ref.camera_id}; native PTS {ref.native_pts}, time base {ref.time_base}.</p><small style={{overflowWrap:'anywhere'}}>Source SHA-256: {ref.source_sha256}<br/>RGB frame SHA-256: {ref.frame_sha256}</small></>}
        {result.rejected_frames.length>0&&<p>Missing target geometry: {result.rejected_frames.length} assessed frames. No gap interpolation or forced failure.</p>}
      </details>
      <p>Saved automatically. Refresh or reopen this investigation without inference.</p>
      <a href={`/api/placement/jobs/${jobId}`} target="_blank" rel="noreferrer">Open result JSON</a>
    </>}
  </section>;
}
