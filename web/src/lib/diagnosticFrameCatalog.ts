import type { AnalysisBundle } from "./types";

// Exact saved frame references, not reconstructed from the prose or event times.
// The classic EP010 web export omitted these; the frozen package retains them.
const original = {
  source: "data/experiments/botfails_ep010_w1260_v2_muse_pilot/pilot_report.json#package.frame_refs",
  frames: [
    { frame_ref: "F0", frame_index: 1293, timestamp_s: 43.1, tied_evidence_ids: ["E0"], role: "event_start+earliest_failure_start" },
    { frame_ref: "F1", frame_index: 1335, timestamp_s: 44.5, tied_evidence_ids: ["E2"], role: "gripper_open" },
    { frame_ref: "F2", frame_index: 1350, timestamp_s: 45, tied_evidence_ids: ["E0", "E1"], role: "event_end+event_start" },
    { frame_ref: "F3", frame_index: 1380, timestamp_s: 46, tied_evidence_ids: ["E1"], role: "event_end" },
  ],
};

export function diagnosticFrameCatalog(a: AnalysisBundle): {
  source: string; frames: AnalysisBundle["frame_catalog"];
} {
  if (a.frame_catalog.length) return { source: "frame_catalog in this saved analysis", frames: a.frame_catalog };
  // Bind only to this recorded video/package. Never borrow references for uploads,
  // PILOT or an unrelated episode with coincidentally equal F/E IDs.
  if (a.episode_key === "ep010" && a.split === "development" && !a.dry_run &&
      a.video.rel === "eval_videos/botfails/botfails_dish_test_ep010.mp4" &&
      a.evidence_catalog.find(e => e.evidence_id === "E2")?.source === "proprio:observation.state[gripper]") return original;
  return { source: "No usable frame catalog supplied", frames: [] };
}
