import type {
  EvidenceItem,
  ReconstructionStatus,
  TimelineMarker,
} from "../lib/types";
import { Badge } from "./ui";

type Props = {
  marker: TimelineMarker | null;
  evidence: EvidenceItem | null;
  reconstruction: ReconstructionStatus | null;
  highlightObjectId: string | null;
  t: number;
  hasJointPose: boolean;
};

function markerProvenance(kind: string): "observed" | "inferred" {
  return kind === "observed_measurement" ? "observed" : "inferred";
}

/**
 * Phase 5 lite: show what each visual element is (observed / inferred / illustrative)
 * when an event is selected.
 */
export function EvidenceSyncPanel({
  marker,
  evidence,
  reconstruction,
  highlightObjectId,
  t,
  hasJointPose,
}: Props) {
  if (!marker && !evidence) {
    return (
      <p className="text-[0.85rem] text-[var(--muted)]">
        Select a timeline event to seek video, update the optional 3D pose, and
        inspect evidence provenance.
      </p>
    );
  }

  const mkProv = marker ? markerProvenance(marker.kind) : null;

  return (
    <div className="space-y-3 text-[0.9rem]">
      <div>
        <div className="text-[0.75rem] font-semibold uppercase tracking-wide text-[var(--muted)]">
          Synced at {t.toFixed(2)}s
        </div>
        {marker ? (
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="font-medium">{marker.label}</span>
            <Badge tone={mkProv === "observed" ? "observed" : "inferred"}>
              {mkProv}
            </Badge>
          </div>
        ) : null}
      </div>

      <ul className="space-y-1.5 text-[0.85rem] leading-relaxed text-[var(--muted)]">
        <li>
          <Badge tone="observed">camera</Badge> seek to event time — primary
          evidence
        </li>
        <li>
          <Badge tone={hasJointPose ? "warn" : "muted"}>
            3D robot · {hasJointPose ? "approximate" : "unavailable"}
          </Badge>{" "}
          joint-driven URDF; kinematics not physically validated
        </li>
        <li>
          <Badge tone="muted">scene props · illustrative</Badge> plates/rack/table
          are placeholders — not measured 3D poses
          {highlightObjectId ? (
            <span className="text-[var(--text)]">
              {" "}
              · highlighting {highlightObjectId.replace("green plate:", "plate:")}
            </span>
          ) : null}
        </li>
        {evidence ? (
          <li>
            <Badge
              tone={
                evidence.status_context === "inferred" ? "inferred" : "observed"
              }
            >
              {evidence.evidence_id} · {evidence.status_context ?? "evidence"}
            </Badge>{" "}
            {evidence.summary}
          </li>
        ) : null}
      </ul>

      {reconstruction ? (
        <p className="rounded-lg border border-[var(--border)] bg-[var(--panel-soft)] px-3 py-2 text-[0.8rem] leading-relaxed text-[var(--muted)]">
          {reconstruction.phase3_pose_reconstruction.decision}
        </p>
      ) : null}
    </div>
  );
}
