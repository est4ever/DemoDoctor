import type { CriterionContextFrame, MultiCameraManifest } from "./types";

/** A context link cannot seek outside its own camera, source or approved window. */
export function criterionContextTime(frame: CriterionContextFrame, manifest?: MultiCameraManifest): number | null {
  const camera = manifest?.cameras.find(c => c.camera_id === frame.camera_id && c.source_video_id === frame.source_video_id);
  if (!camera || !Number.isInteger(frame.original_frame) || frame.original_frame < camera.frame_start || frame.original_frame >= camera.frame_end) return null;
  const t = frame.original_timestamp_s - camera.playback_offset_s;
  if (!Number.isFinite(t) || !Number.isFinite(frame.shared_timestamp_s) || t < 0 || t >= manifest!.duration_s ||
      Math.abs(t - frame.shared_timestamp_s) > 1e-6 || Math.abs(frame.original_timestamp_s - frame.original_frame / camera.fps) > 1e-6) return null;
  return t;
}
