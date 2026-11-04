import type {AnalysisBundle} from './types';

/** Provider execution is distinct from both playback and scientific verification. */
export function investigationMode(a:AnalysisBundle,savedJob:boolean) {
  if(a.dry_run===true || a.execution?.mode==='dry_run')return {label:'Dry Run · no inference',note:'SAM and Muse were skipped. No physical findings were generated.'};
  if(!savedJob)return {label:'Saved analysis replay',note:'Recorded demonstration. Opening it makes no new provider calls. Supported claims retain their original measurement scope.'};
  if(a.execution?.mode==='real')return {label:'Real Analysis · saved outputs',note:a.execution.note};
  if(a.execution?.mode==='experimental')return {label:'Experimental · execution unconfirmed',note:a.execution.note};
  if(a.execution?.mode==='recorded_replay')return {label:'Saved analysis replay',note:a.execution.note};
  return {label:'Saved analysis · mode unconfirmed',note:'Provider execution is not confirmed by the available local records. Reopening never starts inference.'};
}
