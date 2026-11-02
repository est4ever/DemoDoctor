import type { AnalysisBundle, EvidenceItem } from './types';
import recorded from './recordedCitationBindings.json';

export type CitationBindings = {schema: 'demodoctor.citation-bindings/v1'; records: Record<string, {
  status: 'record_match' | 'unverifiable'; reason: string; package?: string; package_sha256?: string | null;
  camera_id?: string; source_video_id?: string; original_evidence_id?: string; playback_offset_s?: number;
  expected?: Record<string, unknown>;
}>};
const fields = ['source','kind','status_context','frame_start','frame_end','t_start','t_end','summary','claims','track_id','event_index'];
const equal = (a: unknown,b: unknown): boolean => {
  if (a == null || b == null) return a == null && b == null;
  if (typeof a === 'number' && typeof b === 'number') return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a-b)<=1e-9;
  if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length===b.length && a.every((v,i)=>equal(v,b[i]));
  if (typeof a==='object' && typeof b==='object') {
    const x=a as Record<string,unknown>, y=b as Record<string,unknown>;
    return Object.keys(x).length===Object.keys(y).length && Object.keys(x).every(k=>k in y && equal(x[k],y[k]));
  }
  return a===b;
};
function authority(a: AnalysisBundle, savedJob: boolean): CitationBindings | undefined {
  // Uploaded jobs can reuse an episode_key. They must never inherit the replay's authority.
  return a.citation_bindings ?? (!savedJob ? (recorded as unknown as Record<string,CitationBindings>)[a.episode_key] : undefined);
}
export function citationBinding(a: AnalysisBundle, item: EvidenceItem, savedJob=false) {
  const source=authority(a,savedJob);
  if (!source) return {status:'unverifiable' as const,reason:'Original citation binding metadata unavailable; source record remains inspectable. No validated camera seek.'};
  const fail=()=>{throw Error(`Citation ${item.evidence_id} does not match its original evidence package. Investigation quarantined; no analysis was started.`);};
  if (source.schema!=='demodoctor.citation-bindings/v1' || !source.records) return fail();
  const binding=source.records[item.evidence_id];
  if (!binding) return fail();
  if (binding.expected) {
    const row=item as unknown as Record<string,unknown>;
    let missing=false;
    for (const key of fields) if (key in binding.expected) {
      if (!(key in row) && binding.expected[key]!=null) missing=true;
      else if (!equal(row[key],binding.expected[key])) return fail();
    }
    for (const key of ['camera_id','source_video_id','original_evidence_id','package'] as const)
      if (row[key] != null && row[key]!==binding[key]) return fail();
    if (binding.camera_id) for (const key of ['camera_id','source_video_id','original_evidence_id'])
      if (!(key in row)) missing=true;
    if (missing) return {...binding,status:'unverifiable' as const,reason:'Citation lacks fields needed to match the original record. No validated camera seek.'};
  } else if (binding.status==='record_match') return fail();
  return binding;
}
export function validateCitations(a: AnalysisBundle, savedJob=false): void {
  // JSON is untrusted at runtime: TypeScript's number annotations do not prevent
  // false/null/empty metadata from being coerced by video arithmetic later.
  const metadata=(raw:unknown):void=>{
    if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('Camera metadata is malformed. Investigation quarantined.');
    const r=raw as Record<string,unknown>;
    const fail=()=>{throw Error('Camera metadata has invalid numeric types. Investigation quarantined; no analysis was started.');};
    for(const key of ['fps','duration_s','offset_s','playback_offset_s','source_timestamp_s','original_timestamp_s','shared_timestamp_s','timestamp_s','window_start_s','window_end_s','shared_start_s','shared_end_s'])
      if(key in r&&(typeof r[key]!=='number'||!Number.isFinite(r[key])))fail();
    for(const key of ['frame_start','frame_end','n_frames','camera_frame','source_frame','original_frame','frame_index','width','height'])if(key in r&&!Number.isInteger(r[key]))fail();
    if('timestamps_s' in r&&(!Array.isArray(r.timestamps_s)||r.timestamps_s.some(t=>typeof t!=='number'||!Number.isFinite(t))))fail();
    for(const key of ['crop','native_image_dimensions'])if(key in r&&!(key==='crop'&&r[key]===null)){
      const v=r[key];if(!Array.isArray(v)||v.length!==(key==='crop'?4:2)||v.some(n=>!Number.isInteger(n)))fail();
    }
    if(r.frame_mapping!=null){if(!Array.isArray(r.frame_mapping))fail();else r.frame_mapping.forEach(metadata);}
  };
  if(a.multicamera){
    metadata(a.multicamera);
    for(const rows of [a.multicamera.cameras,a.multicamera.sources])if(rows!==undefined){
      if(!Array.isArray(rows))throw Error('Camera metadata is malformed. Investigation quarantined.');
      rows.forEach(metadata);
    }
  }
  const seen=new Set<string>();
  for (const item of a.evidence_catalog ?? []) {
    if (seen.has(item.evidence_id)) throw Error('Duplicate evidence ID; investigation quarantined.');
    seen.add(item.evidence_id);citationBinding(a,item,savedJob);
  }
}
export function citationTime(a: AnalysisBundle, item: EvidenceItem, savedJob=false): number | null {
  const binding=citationBinding(a,item,savedJob);
  if (binding.status!=='record_match') return null;
  const t=binding.expected?.t_start;
  // No raw citation-time fallback and no clamping an out-of-overlap source to frame zero.
  return typeof t==='number' && Number.isFinite(t) && t>=0 && (!a.video.duration_s || t<=a.video.duration_s) ? t : null;
}
