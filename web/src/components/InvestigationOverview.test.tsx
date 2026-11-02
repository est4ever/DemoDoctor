// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {it,expect,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {InvestigationOverview} from './InvestigationOverview';
import type {AnalysisBundle} from '../lib/types';

it('preserves original hypothesis citations behind readable source controls without claiming verification',async()=>{
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
  const a:AnalysisBundle=JSON.parse(readFileSync(resolve('public/data/ep005/analysis.json'),'utf8'));
  const before=JSON.stringify(a),inspect=vi.fn(),host=document.createElement('div'),root=createRoot(host);
  try{
    await act(async()=>root.render(<InvestigationOverview analysis={a} inspectEvidence={inspect}/>));
    const first=host.querySelector('.possible-mechanism')!;
    expect(first.textContent).toContain('incorrectly oriented flat');
    expect(first.querySelector('.provenance')!.textContent).toContain('Unverified');
    expect(first.querySelector<HTMLDetailsElement>('.hypothesis-sources')!.open).toBe(false);
    const h=a.hypotheses.find(h=>h.text.includes('incorrectly oriented flat'))!;
    expect(first.querySelectorAll('button')).toHaveLength(h.related_evidence_ids!.length);
    await act(async()=>first.querySelector<HTMLButtonElement>('button')!.click());
    expect(inspect).toHaveBeenCalledWith(h.related_evidence_ids![0]);
    expect(JSON.stringify(a)).toBe(before);
  }finally{await act(async()=>root.unmount());vi.unstubAllGlobals();}
});

it('makes missing hypotheses and unavailable citations explicit and keeps provenance errors visible',async()=>{
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
  const a:AnalysisBundle=JSON.parse(readFileSync(resolve('public/data/ep005/analysis.json'),'utf8'));
  const host=document.createElement('div'),root=createRoot(host);
  try{
    a.hypotheses=[];
    await act(async()=>root.render(<InvestigationOverview analysis={a} inspectEvidence={()=>{}}/>));
    expect(host.textContent).toContain('No specific failure mechanism is established');
    a.hypotheses=[{text:'Candidate only'},{text:'Missing citation',related_evidence_ids:['unknown']}];
    a.temporal_evidence_error='Temporal provenance mismatch; context withheld.';
    await act(async()=>root.render(<InvestigationOverview analysis={a} inspectEvidence={()=>{}}/>));
    expect(host.textContent).toContain('No source citation supplied');
    expect(host.textContent).toContain('Source reference unavailable: unknown');
    expect(host.querySelector('[role=alert]')!.textContent).toContain('context withheld');
    expect(host.querySelectorAll('.possible-mechanism .provenance')).toHaveLength(2);
  }finally{await act(async()=>root.unmount());vi.unstubAllGlobals();}
});
