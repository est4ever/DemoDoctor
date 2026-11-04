import type {AnalysisBundle,TracksBundle,JointsBundle} from '../lib/types';
import {observationSummary,readableEvidence} from '../lib/readableEvidence';
import {useMemo,type ReactNode} from 'react';

export function InvestigationOverview({analysis:a,inspectEvidence,children,tracks,joints,savedJob=false}:{analysis:AnalysisBundle;inspectEvidence:(id:string)=>void;children?:ReactNode;tracks?:TracksBundle|null;joints?:JointsBundle|null;savedJob?:boolean}) {
  const hypotheses=[...(a.hypotheses??[])].sort((x,y)=>Number(/orient|flat|outside|drop|occlu|incomplete/i.test(y.text))-Number(/orient|flat|outside|drop|occlu|incomplete/i.test(x.text)));
  const evidence=a.evidence_catalog.filter(e=>e.source?.startsWith('sam:')||e.kind==='measurement').slice(0,3);
  const actions=a.criteria?.assessments.some(c=>c.kind==='action');
  const observations=useMemo(()=>observationSummary(a,{tracks,joints,savedJob}),[a,tracks,joints,savedJob]);
  const hypothesis=(h:NonNullable<AnalysisBundle['hypotheses']>[number],i:number)=><article key={i} className="possible-mechanism"><span className="provenance uncertain">Unverified · saved hypothesis</span><p>{h.text}</p>
    <details className="hypothesis-sources"><summary>Supporting evidence{h.related_evidence_ids?.length?` · ${h.related_evidence_ids.length} source records`:''}</summary>
    <div className="claim-links">{h.related_evidence_ids?.length?h.related_evidence_ids.map((id,j)=>{
      const e=a.evidence_catalog.find(e=>e.evidence_id===id);
      return e?<button key={`${id}-${j}`} title={id} aria-label={`Inspect hypothesis source ${id}`} onClick={()=>inspectEvidence(id)}>{readableEvidence(e)} ↗</button>:<small key={`${id}-${j}`}>Source reference unavailable: {id}</small>;
    }):<small>No source citation supplied in this saved hypothesis.</small>}</div>
    <small>No direct frame reference supplied. Cited sources may be timed or untimed; they do not verify this hypothesis.</small>
    </details>
  </article>;
  return <section className="investigation-overview" aria-label="Investigation findings summary">
    {a.task_coverage_error && <p role="alert">{a.task_coverage_error}</p>}
    {a.temporal_evidence_error && <p role="alert">{a.temporal_evidence_error}</p>}
    <h2>What was observed</h2>
    <p>{observations[0]}</p>
    {observations.length>1 && <details><summary>More recorded observations</summary>{observations.slice(1).map((text,i)=><p key={i}>{text}</p>)}</details>}
    {actions && children}
    <h3>Possible failure mechanism</h3>
    {hypotheses.length?hypothesis(hypotheses[0],0):
      <p>No specific failure mechanism is established by the saved evidence. Missing observations are not proof of a failure.</p>}
    {hypotheses.length>1 && <details><summary>More saved hypotheses ({hypotheses.length-1}) · Unverified</summary>{hypotheses.slice(1).map(hypothesis)}</details>}
    {!actions && children}
    <h3>{a.task_outcome==='uncertain'?'Why the outcome is uncertain':'What remains unverified'}</h3>
    <p>{a.criteria?.assessments.some(c=>c.kind==='action')?'The task steps still need independent action evidence. Their individual assessments and missing observations are shown separately.':
      'Narrow image-space findings do not establish the physical cause, grasp or release, orientation, or every task-completion condition. The saved outcome is unchanged.'}</p>
    {!hypotheses.length && !!evidence.length && <div className="supporting-observations"><h3>Supporting evidence</h3><div className="claim-links">{evidence.map(e=><button key={e.evidence_id} aria-label={`Inspect supporting evidence ${e.evidence_id}`} title={e.evidence_id} onClick={()=>inspectEvidence(e.evidence_id)}>{readableEvidence(e)} ↗</button>)}</div></div>}
  </section>;
}
