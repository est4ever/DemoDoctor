import type {AnalysisBundle} from './types';

/** Provider execution is distinct from both playback and scientific verification. */
export function investigationMode(a:AnalysisBundle,savedJob:boolean) {
  if(a.placement_assessment&&a.native_video){
    if(!savedJob||a.dry_run)return {label:'Native video · execution unconfirmed',note:'Contradictory or unregistered execution metadata. No genuine model execution is established.'};
    if(a.native_video.mode==='offline_mock')return {label:'Mock proposals · real footage',note:'No native-video inference occurred. Mock proposals exercise verification against genuine saved source evidence.'};
    if(a.native_video.mode==='genuine_native_video')return {label:'Native video · saved genuine proposals',note:'Meta Muse produced these proposals. Geometric verification remains Assisted. Model descriptions are not verified facts. Reopening makes no inference request.'};
    return {label:'Native video · execution unconfirmed',note:'Unknown execution mode; do not treat this as genuine model output.'};
  }
  if(a.placement_assessment)return {label:'Assisted offline assessment',note:'New source-pixel computation with a saved genuine SAM rack template. No fresh SAM or Muse call. Reopening validates saved evidence without inference.'};
  if(a.dry_run===true || a.execution?.mode==='dry_run')return {label:'Dry Run · no inference',note:'SAM and Muse were skipped. No physical findings were generated.'};
  if(!savedJob)return {label:'Saved analysis replay',note:'Recorded demonstration. Opening it makes no new provider calls. Supported claims retain their original measurement scope.'};
  if(a.execution?.mode==='real')return {label:'Real Analysis · saved outputs',note:a.execution.note};
  if(a.execution?.mode==='experimental')return {label:'Experimental · execution unconfirmed',note:a.execution.note};
  if(a.execution?.mode==='recorded_replay')return {label:'Saved analysis replay',note:a.execution.note};
  return {label:'Saved analysis · mode unconfirmed',note:'Provider execution is not confirmed by the available local records. Reopening never starts inference.'};
}
