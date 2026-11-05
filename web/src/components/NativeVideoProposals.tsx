import {useState} from 'react';

export type NativeResult={mode:string;model:string;explanation:string;explanation_status:string;physical_cause:string;proposal_only_frames?:number[];
  accounting:{rate_derived_usd:number;provider_confirmed_charge_usd:number|null};
  proposals:Array<{proposal_id:string;event_type:string;description:string;uncertainty:string;status:string;
    proposed_start_time:number;proposed_end_time:number;frame_start:number;frame_end_exclusive:number;
    visible_evidence:string[];alternative_interpretations:string[];missing_evidence:string[];verified_statement:string|null;
    supported_interval:{start_frame:number;end_frame_exclusive:number;start_s:number;last_s:number}|null;
    scope:string;source_citations:Array<{frame:number;timestamp_s:number}>}>};
type Plan={plan_id:string;plan_sha256:string;model:string;reservation_usd:number;frame_count:number;last_source_timestamp:number;source_sha256:string;upload_sha256:string};
export function NativeVideoProposals({jobId,result,seek,showFrame,allowPrepare=true}:{jobId:string;result?:NativeResult;seek:(t:number,opts?:{pause?:boolean})=>void;showFrame:(f:number)=>void;allowPrepare?:boolean}){
  const [task,setTask]=useState('Place all dishes in the rack'),[desired,setDesired]=useState('All required dishes are in the rack');
  const [plan,setPlan]=useState<Plan|null>(null),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function post(url:string,body:unknown){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.detail??'Stopped');return data;}
  async function prepare(){setBusy(true);setError('');setPlan(null);setApproved(false);try{setPlan(await post(`/api/placement/jobs/${jobId}/native-video/plan`,{task_description:task,desired_end_state:desired}));}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function execute(){if(!plan||!approved||busy)return;setBusy(true);setError('');try{const r=await post(`/api/native-video/${plan.plan_id}/execute`,{plan_sha256:plan.plan_sha256,approve_reservation_usd:plan.reservation_usd});window.location.hash=`job/${r.job_id}`;}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section aria-label="Native video event proposals"><h3>Video event proposals · Experimental</h3>
    <p>Meta-hosted Muse Spark 1.3 examines the complete video. Its event descriptions are proposals, not verified findings. This is separate from Fireworks Muse Spark Open.</p>
    {result&&<>
      <p><strong>{result.mode==='offline_mock'?'OFFLINE MOCK MODEL RESPONSE — source footage is real; model responses are test fixtures, not genuine inference':result.mode==='genuine_native_video'?'GENUINE NATIVE-VIDEO MODEL RESPONSE':'MODEL EXECUTION UNCONFIRMED'}</strong></p>
      <p>{result.explanation}</p><p>{result.explanation_status}</p>
      <p>Original failure onset: Unknown. Physical cause: {result.physical_cause}. No physical grasp, release or task-success confirmation.</p>
      {result.proposals.map(e=><article key={e.proposal_id} aria-label={`Proposal ${e.proposal_id}`}>
        <h4>{e.proposal_id}: {e.event_type} — checked relation {e.status}</h4>
        <button onClick={()=>seek(e.proposed_start_time,{pause:true})}>Model-proposed interval {e.proposed_start_time.toFixed(3)}–{e.proposed_end_time.toFixed(3)} s · frames {e.frame_start}–{e.frame_end_exclusive-1}</button>
        <p>Unverified model description: {e.description}</p><p>Model uncertainty: {e.uncertainty}</p>
        {e.verified_statement&&<p>Independent checked statement: {e.verified_statement}</p>}
        {e.supported_interval&&<button onClick={()=>seek(e.supported_interval!.start_s,{pause:true})}>Verified relation only: {e.supported_interval.start_s.toFixed(6)}–{e.supported_interval.last_s.toFixed(6)} s</button>}
        <p>{e.scope}</p>
        <p>Alternatives proposed by model (unverified): {e.alternative_interpretations.join('; ')||'None supplied; this does not exclude alternatives.'}</p>
        {e.missing_evidence.map((v,i)=><p key={i}>{v}</p>)}
        {e.source_citations.map(r=><button key={r.frame} onClick={()=>{showFrame(r.frame);seek(r.timestamp_s,{pause:true});}}>Inspect original frame {r.frame} · {r.timestamp_s.toFixed(6)} s</button>)}
      </article>)}
      {!result.proposals.length&&<p>No model event proposal. This does not establish success.</p>}
      <p>{result.mode==='offline_mock'?'Simulated usage only':'Provider token-rate calculation'}: ${result.accounting.rate_derived_usd.toFixed(6)}. Provider-confirmed dollar charge: {result.accounting.provider_confirmed_charge_usd===null?'unavailable':result.accounting.provider_confirmed_charge_usd}.</p>
    </>}
    {allowPrepare&&<details><summary>Prepare a separate native-video analysis plan</summary>
      <label>Task description<input value={task} disabled={busy||!!plan} onChange={e=>setTask(e.target.value)}/></label>
      <label>Desired end state (instruction, never actual outcome)<input value={desired} disabled={busy||!!plan} onChange={e=>setDesired(e.target.value)}/></label>
      <p>This pilot is limited to the displayed dish-to-rack task and registered recordings; arbitrary upload criteria are not yet verified. Do not enter reference outcomes, failure times or historical diagnoses. One full-video upload and one bounded native-video request. No SAM, retries, or paid refinement. Existing assisted geometry is supplied only to the independent verifier after the response.</p>
      <button disabled={busy||!!plan||task.length<3||desired.length<3} onClick={prepare}>{busy?'Working…':'Prepare source bindings — no inference charge'}</button>
      {plan&&<><p>{plan.model}; {plan.frame_count} frames, 0–{plan.last_source_timestamp.toFixed(6)} s; reservation ${plan.reservation_usd.toFixed(2)}. Expected charge unknown; reservation is not a provider hard cap.</p>
        <small style={{overflowWrap:'anywhere'}}>Original SHA-256 {plan.source_sha256}<br/>H.264 upload SHA-256 {plan.upload_sha256}<br/>Plan SHA-256 {plan.plan_sha256}</small>
        <p>Execution requires separate, current operator authorization for this exact plan, provider funding, exclusive account usage and reconciled accounting. A checkbox alone cannot authorize provider access.</p>
        <label><input type="checkbox" checked={approved} disabled={busy} onChange={e=>setApproved(e.target.checked)}/>I approve this exact plan and ${plan.reservation_usd.toFixed(2)} reservation, subject to the operator gate.</label>
        <button disabled={busy||!approved} onClick={execute}>Run authorized native-video analysis</button></>}
      {error&&<p role="alert">{error}</p>}
    </details>}
  </section>;
}
