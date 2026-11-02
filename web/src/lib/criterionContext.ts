import type { CriterionContextFrame, MultiCameraManifest } from "./types";

/** A context link cannot seek outside its own camera, source or approved window. */
export function criterionContextTime(frame: CriterionContextFrame, manifest?: MultiCameraManifest, requireBinding=false): number | null {
  if (!frame || typeof frame.frame_ref!=='string' || !Array.isArray(manifest?.cameras)) return null;
  const camera = manifest?.cameras.find(c => c && c.camera_id === frame.camera_id && c.source_video_id === frame.source_video_id);
  if (!camera || !Number.isInteger(frame.original_frame) || frame.original_frame < camera.frame_start || frame.original_frame >= camera.frame_end) return null;
  // New T references require the entire binding. Legacy unhashed C/F references
  // retain their explicit timestamp/ID path; they are never treated as T records.
  if (requireBinding || frame.frame_ref.startsWith('T_') || frame.camera_sha256!==undefined || frame.source_sha256!==undefined) {
    const hash=(v:unknown)=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
    const crop=(v:unknown)=>v===null || Array.isArray(v)&&v.length===4&&v.every(Number.isInteger)&&v[0]>=0&&v[1]>=0&&v[2]>0&&v[3]>0;
    if (!hash(camera.sha256)||!hash(camera.source_sha256)||!hash(frame.camera_sha256)||!hash(frame.source_sha256)||
      frame.camera_sha256!==camera.sha256||frame.source_sha256!==camera.source_sha256||
      !crop(frame.crop)||!crop(camera.crop)||JSON.stringify(frame.crop)!==JSON.stringify(camera.crop)) return null;
  }
  const t = frame.original_timestamp_s - camera.playback_offset_s;
  if (!Number.isFinite(t) || !Number.isFinite(frame.shared_timestamp_s) || t < 0 || t >= manifest!.duration_s ||
      Math.abs(t - frame.shared_timestamp_s) > 1e-6 || Math.abs(frame.original_timestamp_s - frame.original_frame / camera.fps) > 1e-6) return null;
  return t;
}
