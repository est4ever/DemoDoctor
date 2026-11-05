import type {AnalysisBundle,EvidenceItem,CriteriaBundle,TracksBundle,JointsBundle} from './types';
import {citationBinding} from './citationIntegrity';

type SourceContext={tracks?:TracksBundle|null;joints?:JointsBundle|null;savedJob?:boolean};
function observedSource(a:AnalysisBundle,e:EvidenceItem,savedJob=false) {
  return e.status_context==='observed' && citationBinding(a,e,savedJob).status==='record_match';
}
/** Check the narrow arithmetic against the two actual source observations.
 * Matching a saved citation alone does not verify a numerical measurement. */
export function endpointMeasurement(a:AnalysisBundle,e:EvidenceItem,tracks?:TracksBundle|null,savedJob=false) {
  if(!e.source?.startsWith('sam:') || !['detection','comparison','measurement'].includes(e.kind??'') ||
    !observedSource(a,e,savedJob) || !tracks || ![a.episode_key,'live'].includes(tracks.episode_key) || tracks.provenance!=='observed' || a.multicamera) return null;
  // Older single-camera exports use the generic bundle label "live". The
  // citation, exact endpoint frames and arithmetic must still match; that label
  // never establishes a camera association, and multi-camera bundles abstain.
  for(const raw of e.claims??[]) {
    if(!raw || typeof raw!=='object' || Array.isArray(raw))continue;
    const c=raw as {type?:string;value_px?:number;track_id?:string;from_frame?:number;to_frame?:number};
    if(c.type!=='displacement' || !Number.isFinite(c.value_px) || c.value_px!<0 || !Number.isInteger(c.from_frame) || !Number.isInteger(c.to_frame) ||
      c.from_frame!>=c.to_frame! || !c.track_id || e.track_id!==c.track_id || e.frame_start==null || e.frame_end==null ||
      c.from_frame!<e.frame_start || c.to_frame!>=e.frame_end || !(tracks.fps>0)) continue;
    const track=tracks.tracks[c.track_id];
    if(track?.object_id!==c.track_id || !Array.isArray(track.points))continue;
    const points=[c.from_frame,c.to_frame].map(frame=>track.points.find(p=>p.frame_index===frame));
    if(points.some(p=>!p || !Number.isFinite(p.t) || Math.abs(p.t-p.frame_index/tracks.fps)>.000500001 ||
      !Array.isArray(p.bbox) || p.bbox.length!==4 || !p.bbox.every(Number.isFinite) || p.bbox[2]<p.bbox[0] || p.bbox[3]<p.bbox[1]))continue;
    const center=(p:NonNullable<typeof points[number]>)=>[(p.bbox[0]+p.bbox[2])/2,(p.bbox[1]+p.bbox[3])/2];
    const [x,y]=points.map(p=>center(p!)),value=Math.hypot(y[0]-x[0],y[1]-x[1]);
    if(Math.abs(value-c.value_px!)>.005000001)continue; // Saved claims round to 2 decimal places.
    return {value,from_frame:c.from_frame!,to_frame:c.to_frame!,evidence_id:e.evidence_id};
  }
  return null;
}

/** Presentation only. Full provider wording/numbers stay in the source record. */
export function readableEvidence(e:EvidenceItem) {
  if(e.kind==='measurement' && e.source?.startsWith('proprio:') && /gripper/i.test(e.source))return 'Measured gripper opening';
  if(e.claims?.some(c=>(c as {type?:string})?.type==='displacement'))return e.status_context==='observed' && e.source?.startsWith('sam:')?'Recorded endpoint claim':'Unverified displacement proposal';
  if(e.source?.includes('end keyframe'))return 'Object positions in the sampled image';
  if(e.source?.startsWith('sam:') && /window|coverage/i.test(e.summary??''))return 'Observed tracking window';
  if(e.source?.startsWith('sam:'))return 'Recorded image-space observations';
  if(/empty_result/i.test(e.summary??''))return 'Destination mask unavailable';
  if(/No joint|gripper reading cannot/i.test(e.summary??''))return 'Grasp and release measurement is limited';
  if(/orientation/i.test(e.summary??''))return 'Physical orientation remains unresolved';
  if(/final position|expected object/i.test(e.summary??''))return 'Final object positions are incomplete';
  return 'Saved evidence and uncertainty note';
}
export function resolvingObservation(r:{kind:string;reason:string},criterionKind:string) {
  const labels:Record<string,string>={additional_viewpoint:'A clearer view of the target interior, ideally from another camera.',
    final_state_observation:'A clear observation of the required final state.',continuous_tracking:'Continuous, identity-consistent object observations through the missing interval.',
    orientation_measurement:'An independently validated measurement of the required object orientation.',destination_mask:'A usable destination mask or calibrated interior geometry.',
    gripper_measurement:'A synchronized gripper signal that can distinguish holding from an empty gripper.'};
  if(r.kind==='task_specification')return criterionKind==='inventory'?'An explicit count of the objects required by the task.':criterionKind==='orientation'?'An approved definition of the required pose.':'An explicit, operator-approved task requirement.';
  return labels[r.kind]??r.reason;
}
export function observationSummary(a:AnalysisBundle,context:SourceContext={}):string[] {
  const result:string[]=[];
  if(a.placement_assessment && context.savedJob){
    const measured=a.evidence_catalog.filter(e=>e.source==='offline:assisted_final_placement' && e.kind==='measurement' && citationBinding(a,e,true).status==='record_match');
    if(measured.length)result.push(...measured.map(e=>`${e.summary} Assisted image-space measurement; physical cause and earlier onset remain Unverified.`));
    else if(a.native_video)result.push('Source-linked native-video event proposals are available below. They are not independently verified measurements or physical failure conclusions.');
  }
  const containment=a.criteria?.assessments.find(c=>c.kind==='containment');
  // A criterion's independently checked 2D geometry can be decisive even when
  // its historical catalog entry labels full physical completion uncertain.
  const supportedSources=containment && ['supported','contradicted'].includes(containment.state) && containment.sources.length>0 && containment.evidence_ids.length && containment.evidence_ids.every(id=>{
    const e=a.evidence_catalog.find(e=>e.evidence_id===id);return e && citationBinding(a,e,context.savedJob).status==='record_match';
  });
  const objects=supportedSources?containment?.objects:undefined;
  const values=Object.values(objects??{});
  const objectName=Object.keys(objects??{}).every(id=>/plate/i.test(id))?'plate':'object';
  if(values.some(v=>v==='outside'))result.push(`The sampled image-space assessment places at least one ${objectName} region outside the target. This does not establish the physical cause or a later final position.`);
  else if(values.length && values.every(v=>v==='inside'))result.push('The assessed object regions are inside the target in the sampled 2D image. This does not verify physical orientation or full task completion.');
  else if(values.length)result.push('The sampled object regions do not establish that all required objects are inside the target. Some positions remain unknown.');
  const joints=context.joints,gripper=joints?.dataset_joint_names.findIndex(n=>/gripper/i.test(n))??-1;
  if(joints?.episode_key===a.episode_key && gripper>=0 && a.evidence_catalog.some(e=>e.kind==='measurement' && e.source?.startsWith('proprio:') && /gripper/i.test(e.source) &&
    citationBinding(a,e,context.savedJob).status==='record_match' && e.frame_start!=null && Number.isFinite(joints.motor_deg[e.frame_start]?.[gripper])))result.push('Gripper opening was measured. Opening alone does not establish holding, release or a drop.');
  const displacement=a.evidence_catalog.map(e=>endpointMeasurement(a,e,context.tracks,context.savedJob)).find(Boolean);
  if(displacement)result.push(`The recorded box centers are approximately ${displacement.value.toFixed(2)} pixels apart at the observed endpoints. Missing observations do not establish continuous physical travel.`);
  if(!result.length)result.push(a.dry_run?'Providers were skipped. This dry run contains no physical findings.':
    a.evidence_catalog.some(e=>e.source?.startsWith('sam:') && ['detection','comparison'].includes(e.kind??'') && observedSource(a,e,context.savedJob))?
      'SAM returned image-space observations. They do not independently establish pickup, release, placement or mechanical closure.':
      'No source-bound image-space measurement is available in this saved analysis. This does not establish a physical action or task outcome.');
  return result;
}
export function criterionExplanation(c:CriteriaBundle['assessments'][number]) {
  if(c.state==='not_assessed')return 'This criterion was not assessed by the saved analysis.';
  if(c.kind==='containment' && c.state==='supported')return 'The stated 2D location criterion is supported at the sampled frame; full physical completion is a separate question.';
  if(c.kind==='containment' && c.state==='contradicted')return 'A sampled object region is outside the specified image-space target. The physical cause remains unresolved.';
  if(c.state==='unverified')return c.kind==='action'?'The available evidence does not independently verify this action.':'The saved evidence is insufficient to verify this criterion.';
  return c.state==='supported'?'Supported within the stated measurement scope. See the original assessment for its limits.':'Contradicted within the stated measurement scope. See the original assessment for its limits.';
}
