import { useEffect, useState } from "react";
import type { AnalysisBundle, EvidenceItem, JointsBundle, TracksBundle } from "../lib/types";
import { citationBinding } from '../lib/citationIntegrity';

type Props = {
  item: EvidenceItem;
  analysis: AnalysisBundle;
  tracks?: TracksBundle | null;
  joints?: JointsBundle | null;
  fps: number;
  jobId?: string | null;
  seek: (t: number, options?: { pause?: boolean }) => void;
};

/** Read-only presentation of the current catalog and its loaded source artifacts. */
export function EvidenceSource(props: Props) {
  const {item,jobId,analysis}=props;
  const [cameraTracks,setCameraTracks]=useState<{cameraId:string;jobId:string;tracks:TracksBundle}|null>(null);
  const [cameraError,setCameraError]=useState("");
  useEffect(()=>{setCameraTracks(null);setCameraError("");if(!item.camera_id||!jobId)return;let cancelled=false;
    fetch(`/api/jobs/${jobId}/cameras/${item.camera_id}/tracks.json`).then(r=>{if(!r.ok)throw Error("Camera-specific source observations unavailable");return r.json();})
      .then(tracks=>{if(!cancelled)setCameraTracks({cameraId:item.camera_id!,jobId,tracks});}).catch(e=>{if(!cancelled)setCameraError(String(e));});return()=>{cancelled=true;};
  },[item.camera_id,jobId]);
  const c=analysis.multicamera?.cameras.find(c=>c.camera_id===item.camera_id);
  const guardedSeek=(native:number,options?:{pause?:boolean})=>{
    const t=native-(c?.playback_offset_s??0),duration=analysis.video?.duration_s;
    if (Number.isFinite(t) && t>=0 && (duration==null || t<duration)) props.seek(t,options);
  };
  const bound=item.camera_id&&jobId&&cameraTracks?.cameraId===item.camera_id&&cameraTracks.jobId===jobId?cameraTracks.tracks:null;
  return <>{item.camera_id&&<div className="source-limitation"><strong>{item.camera_name} · {item.camera_id}</strong><p>Original {item.original_evidence_id} · {item.source_video_id} · camera-local pixels. Cross-view identity is unverified.</p>{cameraError&&<p role="alert">{cameraError}</p>}</div>}
    <EvidenceSourceDetails {...props} tracks={item.camera_id?bound:props.tracks} fps={c?.fps??props.fps}
      seek={guardedSeek}/>
  </>;
}

function EvidenceSourceDetails({ item, analysis, tracks, joints, fps, seek, jobId }: Props) {
  const binding=citationBinding(analysis,item,!!jobId);
  const matched=binding.status==='record_match';
  // A missing original locator permits inspection, never synthesized measurements/seek.
  const claims = (item.claims ?? []).filter((c): c is Record<string, unknown> => !!c && typeof c === "object");
  const displacement = claims.find(c => c.type === "displacement");
  const trackId = item.track_id ?? claims.find(c => typeof c.track_id === "string")?.track_id;
  const track = typeof trackId === "string" ? tracks?.tracks[trackId] : undefined;
  const from = displacement?.from_frame ?? item.frame_start;
  const to = displacement?.to_frame;
  const rawPoints = track ? (displacement
    ? [track.points.find(p => p.frame_index === from), track.points.find(p => p.frame_index === to)].filter(p => p != null)
    : [track.points[0], track.points[track.points.length - 1]].filter(p => p != null)) : [];
  const inSpan=(f:number)=>item.frame_start!=null && item.frame_end!=null && f>=item.frame_start && f<item.frame_end;
  const scopedPoints=displacement ? rawPoints : track?.points.filter(p=>inSpan(p.frame_index)) ?? [];
  const endpoints=displacement ? scopedPoints : [scopedPoints[0],scopedPoints[scopedPoints.length-1]].filter(p=>p!=null);
  const points = endpoints.filter((p,i,all)=>inSpan(p.frame_index) && all.findIndex(other=>other.frame_index===p.frame_index)===i);
  const center = (box: number[]) => [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
  const gripperClaim = claims.find(c => c.type === "gripper_open");
  const frame = typeof gripperClaim?.frame === "number" ? gripperClaim.frame : item.frame_start;
  const gripperIndex = joints?.dataset_joint_names.findIndex(n => /gripper/i.test(n)) ?? -1;
  const jointAvailable = frame != null && gripperIndex >= 0 && joints?.motor_deg[frame]?.[gripperIndex] != null;
  const sam = item.source?.startsWith("sam:");
  const proprio = item.source?.startsWith("proprio:");
  const report = item.source === "pipeline:report";
  const camera=analysis.multicamera?.cameras.find(c=>c.camera_id===item.camera_id);
  const inSharedWindow=(f:number)=>{const t=f/fps-(camera?.playback_offset_s??0);return t>=0 && (analysis.video?.duration_s==null || t<analysis.video.duration_s);};
  return <>
    <p className="source-limitation"><strong>{matched ? 'Original citation record matched.' : 'Citation binding unverified.'}</strong> {binding.reason} This does not verify physical actions.</p>
    <p className="technical-summary">{item.summary || "No summary provided"}</p>
    {report && <>

      {/No joint data/i.test(item.summary ?? "") && <p className="source-limitation"><strong>Joint/gripper measurements unavailable.</strong> No joint dataset is attached to this video-only investigation. Gripper opening, grasp and release cannot be measured from this entry.</p>}
      {/Not every expected object/i.test(item.summary ?? "") && <p className="source-limitation">An established final object position is missing; this record cannot verify placement in the destination.</p>}
      {/empty_result/i.test(item.summary ?? "") && <>
        <p className="source-limitation"><strong>Destination measurement unavailable.</strong> Segmentation returned no usable {jobId ? "destination" : "tray"} mask (empty_result). No destination-mask artifact is available; this does not mean the {jobId ? "destination" : "tray"} was physically absent.</p>
        {analysis.recorded_evidence?.provenance.target_segmentation && <pre aria-label="Destination segmentation diagnostic">{JSON.stringify(analysis.recorded_evidence.provenance.target_segmentation, null, 2)}</pre>}
      </>}
      <p>Provenance: saved analysis catalog · report-level uncertainty, not a timed physical event. {jobId ? "The original job report and verification are available below." : "Separate raw report artifact unavailable in this replay."}</p>
    </>}
    {sam && <>
      <h4>Recorded image-space source</h4>
      {matched && tracks && points.length ? <>
        <p>{trackId as string} · {track?.n_observations} returned observations · image {tracks.image_size.join(" × ")} px</p>
        <table className="source-measurements"><thead><tr><th>Frame</th><th>Box center (px)</th><th>Returned box</th></tr></thead>
          <tbody>{points.map(p => <tr key={p.frame_index}><td><button disabled={!inSharedWindow(p.frame_index)} title={!inSharedWindow(p.frame_index)?'Original source frame is outside the shared playback window':undefined} onClick={() => seek(p.frame_index / fps, { pause: true })}>F{p.frame_index} ↗</button></td><td>{center(p.bbox).join(", ")}</td><td>{p.bbox.join(", ")}</td></tr>)}</tbody>
        </table>
        {displacement && points.length === 2 && <p>Box-center calculation: √(({center(points[1].bbox)[0]} − {center(points[0].bbox)[0]})² + ({center(points[1].bbox)[1]} − {center(points[0].bbox)[1]})²). Saved endpoint difference: {String(displacement.value_px)} px.</p>}
        {displacement && points.length !== 2 && <p className="source-limitation">Source artifact unavailable for one or more endpoints; the saved endpoint calculation cannot be fully inspected from the loaded observations.</p>}
        <p className="source-limitation">Image-space observations only. No continuous tracking or physical identity across unobserved frames, release, placement or task completion is established.</p>
        <p>Artifact provenance: {tracks.source}</p>
      </> : <p className="source-limitation">Source artifact unavailable: the matching frozen SAM observations were not loaded. Only the saved catalog record is available; no measurements are synthesized.</p>}
    </>}
    {proprio && <>
      <h4>Recorded joint source</h4>
      {matched && jointAvailable && joints && frame != null ? <>
        <p>joints.json · {joints.dataset_joint_names[gripperIndex]} · recorded motor_deg export</p>
        <table className="source-measurements"><thead><tr><th>Frame</th><th>Recorded time (s)</th><th>motor_deg</th></tr></thead>
          <tbody>{[frame - 1, frame, frame + 1].filter(f => joints.motor_deg[f]?.[gripperIndex] != null).map(f => <tr key={f}><td>{f}</td><td>{joints.timestamps_s[f]?.toFixed(6) ?? "Unavailable"}</td><td>{joints.motor_deg[f][gripperIndex]}</td></tr>)}</tbody>
        </table>
        <p className="source-limitation">Measured gripper signal; the catalog event status is unchanged. Holding, object contact and placement are not measured by this signal.</p>
      </> : <p className="source-limitation">Source artifact unavailable: the matching recorded gripper sample is not available. No joint measurement is invented.</p>}
    </>}
    <dl>
      <dt>Source ID</dt><dd>{item.source || "Not provided"}</dd>
      <dt>Time</dt><dd>{item.t_start != null ? `${item.t_start.toFixed(3)}s – ${(item.t_end ?? item.t_start).toFixed(3)}s` : "Untimed · no camera seek"}</dd>
      <dt>Frames</dt><dd>{item.frame_start != null ? `${item.frame_start} – ${item.frame_end ?? item.frame_start} (catalog bounds)` : "No frame assigned"}</dd>
    </dl>
    {item.note && <p>{item.note}</p>}
    {jobId && <div className="claim-links" aria-label="Original job source artifacts">
      {[['failure_report.json','Failure report'],['verification.json','Independent verification'],['evidence_package.json','Original evidence package'],['muse_result.json','Original Muse response']].map(([file,label]) =>
        file === 'muse_result.json' && item.camera_id ? <a key={file} href={`/api/jobs/${encodeURIComponent(jobId)}/files/${file}`} target="_blank" rel="noreferrer">Combined Muse response ↗</a> :
        <a key={file} href={item.camera_id?`/api/jobs/${encodeURIComponent(jobId)}/cameras/${item.camera_id}/${file}`:`/api/jobs/${encodeURIComponent(jobId)}/files/${file}`} target="_blank" rel="noreferrer">{label} ↗</a>)}
      {item.camera_id&&<a href={`/api/jobs/${encodeURIComponent(jobId)}/cameras/${item.camera_id}/provenance.json`} target="_blank" rel="noreferrer">Crop, original timestamps & frame mapping ↗</a>}
      {item.camera_id&&<a href={`/api/jobs/${encodeURIComponent(jobId)}/cameras/${item.camera_id}/provider_observations.json`} target="_blank" rel="noreferrer">Original camera/provider observations ↗</a>}
    </div>}
    <details><summary>Raw evidence record · {item.evidence_id}</summary><pre aria-label="Raw evidence record">{JSON.stringify(item, null, 2)}</pre></details>
  </>;
}
