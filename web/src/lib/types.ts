export type JointsBundle = {
  episode_key: string;
  robot_type: string;
  fps: number;
  n_frames: number;
  dataset_joint_names: string[];
  urdf_joint_names: string[];
  timestamps_s: number[];
  motor_deg: number[][];
  urdf_rad: number[][];
  urdf_rad_unclamped_stats: Record<
    string,
    { min: number; max: number; out_of_limit_frames: number; limits: number[] }
  >;
};

export type EvidenceItem = {
  package?: string;
  event_index?: number | null;
  camera_id?: string;
  camera_name?: string;
  original_evidence_id?: string;
  source_video_id?: string;
  evidence_id: string;
  source?: string;
  kind?: string;
  status_context?: string;
  frame_start?: number | null;
  frame_end?: number | null;
  t_start?: number | null;
  t_end?: number | null;
  summary?: string;
  claims?: unknown[];
  track_id?: string | null;
  note?: string | null;
};

export type TimelineMarker = {
  id: string;
  label: string;
  t: number;
  kind: string;
  evidence_ids: string[];
};

export type HighlightInterval = {
  t_start: number;
  t_end: number;
  label: string;
  status: string;
  note: string;
};

export type CriterionContextFrame = {
  frame_ref: string; camera_id: string; source_video_id: string; original_frame: number;
  original_timestamp_s: number; shared_timestamp_s: number; scope: string;
  selection_reasons?: string[];
  sam_observation_available?: boolean;
  camera_sha256?: string;
  source_sha256?: string;
  crop?: number[] | null;
};

export type CriteriaBundle = {
  schema: "demodoctor.criteria/v2";
  investigation_id: string;
  completion: "supported" | "contradicted" | "unverified" | "not_assessed";
  scope: string;
  notes: string[];
  abstention_explanation: string | null;
  task_text?: string;
  context_frames?: CriterionContextFrame[];
  temporal_evidence?: Array<{camera_id:string; source_video_id:string; frames:CriterionContextFrame[];
    adjacent_box_steps:Array<{object_id:string;frames:number[];delta_xy_px:number[];distance_px:number;scope:string}>;
    camera_motion:string;full_source_final_frame_assessed:boolean;limitations:string[]}>;
  coverage?: Array<{camera_id: string; source_video_id: string; crop: number[] | null; sha256: string; source_sha256: string; fps: number; n_frames: number;
    frame_start: number; frame_end: number; returned_observations: number; observed_ranges: number[][]; missing_ranges: number[][]; outside_analysis: number[][]}>;
  catalog_binding?: Array<Pick<EvidenceItem, "evidence_id" | "source" | "frame_start" | "frame_end" | "summary">>;
  assessments: Array<{
    criterion_id: string; kind: string; name: string; state: CriteriaBundle["completion"];
    required: boolean; basis: string; evidence_ids: string[];
    objects?: Record<string,string>;
    sources: Array<{ evidence_id: string; kind: string; object_id: string; frame: number; view: string; source_ref: string; package_id: string; value: string; measurement?: Record<string, string | number> }>;
    requirements: Array<{ kind: string; reason: string }>;
  }>;
  mechanisms: Array<{
    mechanism: string; status: string; verifier: string; evidence_ids: string[];
    alternatives: string[]; resolving_evidence: Array<{ kind: string; reason: string }>;
  }>;
};

export type AnalysisBundle = {
  citation_bindings?: import('./citationIntegrity').CitationBindings;
  temporal_evidence_error?: string;
  task_coverage_error?: string;
  criteria?: CriteriaBundle;
  multicamera?: MultiCameraManifest;
  recorded_evidence?: {
    verification: { claims_checked: number; claims_failed: number; ok: boolean };
    provenance: {
      target_segmentation?: { status?: string };
      observation_coverage?: { missing_frames: number; expected_frames: number; missing_ranges: Array<{ frame_start: number; frame_end: number }> };
    };
  };
  dry_run?: boolean;
  episode_key: string;
  title: string;
  task: string;
  split: string;
  available_episodes: Array<{
    key: string;
    label: string;
    enabled: boolean;
    note?: string;
  }>;
  has_joint_animation?: boolean;
  pipeline_verdict: string;
  task_outcome: string;
  outcome_label: string;
  diagnosis_headline: string;
  diagnosis_summary: string;
  earliest_failure: {
    t_start: number;
    t_end: number;
    kind?: string;
    frame_start?: number;
    frame_end?: number;
  } | null;
  physical_events: Array<{
    id?: string;
    kind?: string;
    subtype?: string;
    status?: string;
    t_start?: number;
    t_end?: number;
    frame_start?: number;
    frame_end?: number;
    inference?: string;
    uncertainties?: string[];
    evidence_ids?: string[];
  }>;
  /** Preferred highlight band; may be null when no timed interval exists. */
  highlight_interval?: HighlightInterval | null;
  /** Alias kept for ep010 compatibility. */
  release_interval?: HighlightInterval | null;
  timeline_markers: TimelineMarker[];
  evidence_catalog: EvidenceItem[];
  frame_catalog: Array<{
    camera_id?: string;
    source_video_id?: string;
    original_frame?: number;
    original_timestamp_s?: number;
    frame_ref: string;
    frame_index: number;
    timestamp_s: number;
    tied_evidence_ids?: string[];
    role?: string;
  }>;
  observed: Array<{ text: string; evidence_ids: string[]; t?: number }>;
  inferred: Array<{
    text: string;
    evidence_ids: string[];
    t?: number;
    status?: string;
  }>;
  hypotheses: Array<{
    text: string;
    related_evidence_ids?: string[];
    label?: string;
  }>;
  unknowns: string[];
  muse_explanation?: string;
  factual_claims: Array<{ text: string; evidence_ids: string[] }>;
  visual_interpretations: Array<{
    text: string;
    frame_ref?: string;
    not_verified_by_pipeline?: boolean;
  }>;
  limitations: string[];
  muse_only?: {
    verdict?: string;
    confidence?: number;
    summary?: string;
    failure_mode?: string;
  } | null;
  evidence_muse_outcome?: string | null;
  comparison_note?: string | null;
  /** When true, render a prominent Muse-only vs evidence-grounded panel. */
  highlight_muse_comparison?: boolean;
  sam_overlay?: {
    available: boolean;
    source?: string;
    concept?: string;
    frame_start?: number;
    frame_end?: number;
    t_start?: number;
    t_end?: number;
    n_observations?: number;
    video?: string;
    note?: string;
    reason?: string;
    style_version?: number;
    legend?: Array<{ object_id: string; color_rgb: number[] }>;
  } | null;
  video: { rel: string; primary_evidence: boolean; dev_url?: string; duration_s?: number };
  disclaimer: string;
  initial_seek_s?: number;
  initial_marker_id?: string | null;
  initial_evidence_id?: string | null;
};

export type MultiCameraManifest = {
  source_mode?: "composite"|"separate";
  sources?: Array<{source_video_id:string;width:number;height:number;fps:number;sha256:string}>;
  investigation_questions?: string;
  duration_s: number;
  alignment: {kind: string; basis: string; convention: string};
  limitations: string[];
  cameras: Array<{camera_id: string; name: string; motion: string; source_video_id: string;
    playback_offset_s: number; offset_s: number; fps: number; width: number; height: number;
    frame_start: number; frame_end: number; sha256: string; source_sha256?: string; crop: number[] | null}>;
};

export type MappingBundle = {
  available?: boolean;
  known_limitations: string[];
  out_of_limit_frames: Record<string, number>;
  transform: Array<{ dataset: string; urdf: string; formula: string }>;
  urdf_source: { repo: string; path: string; license: string };
};

/** Frozen SAM track centroids/bboxes for annotated camera (observed only). */
export type TracksBundle = {
  episode_key: string;
  source: string;
  provenance: "observed";
  note: string;
  image_size: [number, number];
  fps: number;
  t_start: number | null;
  t_end: number | null;
  frame_start: number | null;
  frame_end: number | null;
  legend: Array<{ object_id: string; color_rgb: number[]; label: string }>;
  tracks: Record<
    string,
    {
      object_id: string;
      color_rgb: number[];
      n_observations: number;
      points: Array<{
        frame_index: number;
        t: number;
        centroid: [number, number];
        bbox: [number, number, number, number];
      }>;
    }
  >;
  frames: Record<
    string,
    Array<{
      object_id: string;
      centroid: [number, number];
      bbox: [number, number, number, number];
      confidence: number;
      track_status: string;
      mask?: { size: [number, number]; counts: number[] } | null;
    }>
  >;
};

export type ReconstructionStatus = {
  episode_key: string;
  status: string;
  primary_evidence: string;
  phase3_pose_reconstruction: Record<string, string>;
  object_motion_3d_policy: string;
  provenance_legend: Record<string, string>;
};

export type ProvenanceKind = "observed" | "inferred" | "estimated" | "illustrative";

/** Resolve the amber timeline band, if any. */
export function getHighlight(
  analysis: AnalysisBundle,
): HighlightInterval | null {
  return analysis.highlight_interval ?? analysis.release_interval ?? null;
}
