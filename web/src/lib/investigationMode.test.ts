import {it,expect} from 'vitest';
import type {AnalysisBundle} from './types';
import {investigationMode} from './investigationMode';
const a=(extra:Partial<AnalysisBundle>={})=>({...extra} as AnalysisBundle);
it('distinguishes recorded replay from currently running inference',()=>{
  expect(investigationMode(a(),false).label).toBe('Saved analysis replay');
  expect(investigationMode(a(),false).note).toContain('no new provider calls');
});
it('never promotes dry or unconfirmed jobs to genuine real inference',()=>{
  expect(investigationMode(a({dry_run:true,execution:{mode:'real',note:'bad'}}),true).label).toBe('Dry Run · no inference');
  expect(investigationMode(a({dry_run:false}),true).label).toContain('unconfirmed');
  expect(investigationMode(a({execution:{mode:'experimental',note:'Provider-skipped'}}),true).label).toContain('Experimental');
});
it('labels saved real outputs only with explicit execution metadata',()=>{
  const mode=investigationMode(a({execution:{mode:'real',note:'Local execution records; not physical verification'}}),true);
  expect(mode.label).toBe('Real Analysis · saved outputs');expect(mode.note).toContain('not physical verification');
});
