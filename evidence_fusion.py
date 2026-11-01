"""Build evidence packages for Muse Spark from verified failure / event reports.

The Muse-only baseline (ai_analysis.analyze_demonstration) is unchanged.
This module only prepares structured inputs and validates model replies against
evidence IDs — it never invents SAM tracks or upgrades uncertain statuses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

import tracking as T
from vision import SampledFrame

ROOT = Path(__file__).parent

Outcome = Literal["success", "failure", "uncertain"]
ClaimKind = Literal["verified_pipeline", "hypothesis", "visual_interpretation"]


@dataclass
class EvidenceItem:
    """One citable unit of pipeline evidence (measurements / detections / comparisons)."""

    evidence_id: str  # e.g. E1
    source: str
    kind: str  # detection | measurement | comparison | derived
    status_context: str  # observed | inferred | uncertain | report_level
    frame_start: int | None
    frame_end: int | None
    t_start: float | None
    t_end: float | None
    summary: str
    claims: list[dict[str, Any]] = field(default_factory=list)
    track_id: str | None = None
    event_index: int | None = None
    note: str | None = None


@dataclass
class FrameRef:
    """A video frame tied to evidence (identity across SAM requests is NOT assumed)."""

    frame_ref: str  # F0, F1, ...
    frame_index: int
    timestamp_s: float
    tied_evidence_ids: list[str]
    role: str  # event_start | event_end | gripper_open | end_state | context


@dataclass
class EvidencePackage:
    """Structured package sent to Muse (no ground-truth labels / anomaly flags)."""

    task_id: str
    task_description: str
    experiment_id: str
    provenance: dict[str, Any]
    deterministic_verdict: Outcome
    failure_type: str | None
    earliest_failure: dict[str, Any] | None
    physical_events: list[dict[str, Any]]
    evidence_items: list[EvidenceItem]
    uncertainties: list[str]
    tracking_notes: list[str]
    final_state: dict[str, Any] | None
    frame_refs: list[FrameRef]
    identity_caveat: str = (
        "Object ids from separate SAM requests (window video vs end-of-episode image) "
        "are not assumed to be the same physical instance across gaps."
    )

    def evidence_id_set(self) -> set[str]:
        return {e.evidence_id for e in self.evidence_items}

    def frame_ref_set(self) -> set[str]:
        return {f.frame_ref for f in self.frame_refs}

    def to_muse_text_dict(self) -> dict[str, Any]:
        """JSON-serializable payload for the text portion of the Muse request."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "experiment_id": self.experiment_id,
            "provenance": self.provenance,
            "identity_caveat": self.identity_caveat,
            "deterministic_pipeline": {
                "verdict": self.deterministic_verdict,
                "failure_type": self.failure_type,
                "earliest_failure": self.earliest_failure,
                "n_physical_events": len(self.physical_events),
            },
            "physical_events": self.physical_events,
            "evidence_catalog": [asdict(e) for e in self.evidence_items],
            "uncertainties": self.uncertainties,
            "tracking_notes": self.tracking_notes,
            "final_state": self.final_state,
            "frame_catalog": [asdict(f) for f in self.frame_refs],
            "instructions_for_model": {
                "cite_only": "Use evidence_id values from evidence_catalog (E…) and frame_ref (F…) only.",
                "do_not_invent": "Do not invent gripper openings, drops, or placements absent from the catalog.",
                "status_rules": (
                    "Statuses observed/inferred/uncertain come from the pipeline. "
                    "You may explain them; you must not upgrade uncertain→inferred or inferred→observed."
                ),
                "hypotheses": "Label speculative causes under hypotheses[], never as factual_claims[].",
                "empty_events": (
                    "If physical_events is empty, say so; do not fabricate events from the images alone "
                    "as verified pipeline findings."
                ),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_muse_text_dict(),
            "frame_refs": [asdict(f) for f in self.frame_refs],
        }


@dataclass
class ValidatedMuseExplanation:
    """Parsed Muse reply after evidence-reference validation."""

    ok: bool
    explanation: str
    task_outcome: Outcome
    earliest_failure_interval: dict[str, Any] | None
    factual_claims: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    visual_interpretations: list[dict[str, Any]]
    limitations: list[str]
    outcome_evidence_ids: list[str]
    validation_errors: list[str]
    validation_warnings: list[str]
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MUSE_EVIDENCE_SYSTEM_PROMPT = """You are DemoDoctor's evidence-grounded explainer for robot demonstrations.
You receive a STRUCTURED EVIDENCE PACKAGE from a deterministic vision+joint pipeline, plus a few frames
that are tied to that evidence. Your job is to explain what the package supports — not to re-judge the video from scratch.

Hard rules:
1. Cite only evidence_id values listed in evidence_catalog (E0, E1, …) and frame_ref values (F0, F1, …).
2. Do NOT invent physical events, gripper openings, drops, or placements that are absent from the package.
3. Do NOT upgrade statuses: uncertain must stay uncertain; inferred is not observed.
4. Separate factual_claims (must cite evidence_ids) from hypotheses (speculative causes) and visual_interpretations
   (what you think you see in a frame that the pipeline did not verify).
5. If physical_events is empty, say the pipeline found no supported physical failure events; do not fabricate them.
6. If deterministic_pipeline.verdict is uncertain, your task_outcome should usually be uncertain unless the package
   explicitly supports success or failure via catalog evidence — and you must cite those evidence_ids.
7. Respond with a single JSON object only (no markdown fences):
{
  "explanation": "concise paragraph of what physically happened per the package",
  "earliest_failure_interval": null | {"t_start": 0.0, "t_end": 0.0, "evidence_ids": ["E0"], "note": "..."},
  "task_outcome": "success" | "failure" | "uncertain",
  "outcome_evidence_ids": ["E..."],
  "factual_claims": [{"text": "...", "evidence_ids": ["E0"]}],
  "hypotheses": [{"text": "...", "related_evidence_ids": ["E0"]}],
  "visual_interpretations": [{"text": "...", "frame_ref": "F0", "not_verified_by_pipeline": true}],
  "limitations": ["..."]
}
"""


def _fps_from_report(report: dict[str, Any]) -> float:
    return float((report.get("inputs") or {}).get("fps") or 30.0)


def _collect_evidence_from_report(report: dict[str, Any]) -> tuple[list[EvidenceItem], list[dict[str, Any]]]:
    """Assign stable evidence IDs to each Evidence blob under physical_events."""
    items: list[EvidenceItem] = []
    events_out: list[dict[str, Any]] = []
    eid = 0
    for ei, event in enumerate(report.get("physical_events") or []):
        ev_ids: list[str] = []
        for block in event.get("evidence") or []:
            evidence_id = f"E{eid}"
            eid += 1
            fs = block.get("frame_start")
            fe = block.get("frame_end")
            fps = _fps_from_report(report)
            items.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    source=str(block.get("source") or ""),
                    kind=str(block.get("kind") or ""),
                    status_context=str(event.get("status") or "uncertain"),
                    frame_start=fs if isinstance(fs, int) else None,
                    frame_end=fe if isinstance(fe, int) else None,
                    t_start=round(fs / fps, 3) if isinstance(fs, int) else None,
                    t_end=round(fe / fps, 3) if isinstance(fe, int) else event.get("t_end"),
                    summary=str(block.get("summary") or ""),
                    claims=list(block.get("claims") or []),
                    track_id=event.get("track_id"),
                    event_index=ei,
                )
            )
            ev_ids.append(evidence_id)
        events_out.append({
            "event_index": ei,
            "kind": event.get("kind"),
            "subtype": event.get("subtype"),
            "status": event.get("status"),
            "track_id": event.get("track_id"),
            "frame_start": event.get("frame_start"),
            "frame_end": event.get("frame_end"),
            "t_start": event.get("t_start"),
            "t_end": event.get("t_end"),
            "inference": event.get("inference"),
            "uncertainties": event.get("uncertainties") or [],
            "evidence_ids": ev_ids,
        })
    # Report-level uncertainty notes as catalog entries (citable limitations, not measurements)
    for note in report.get("uncertainties") or []:
        evidence_id = f"E{eid}"
        eid += 1
        items.append(
            EvidenceItem(
                evidence_id=evidence_id,
                source="pipeline:report",
                kind="derived",
                status_context="uncertain",
                frame_start=None,
                frame_end=None,
                t_start=None,
                t_end=None,
                summary=str(note)[:500],
                claims=[],
                note="report-level uncertainty (not a physical event)",
            )
        )
    return items, events_out


def _pick_frames_for_package(
    report: dict[str, Any],
    evidence_items: list[EvidenceItem],
    *,
    end_frame: int | None,
    max_frames: int = 6,
) -> list[FrameRef]:
    """Select a small set of frames tied to evidence (no dense video dump)."""
    candidates: list[tuple[int, str, list[str]]] = []  # frame, role, evidence_ids
    for e in evidence_items:
        if e.kind == "measurement" and e.frame_start is not None:
            candidates.append((e.frame_start, "gripper_open" if "open" in e.summary.lower() else "measurement", [e.evidence_id]))
        if e.kind in ("detection", "comparison") and e.frame_start is not None:
            role = "observation" if e.source == "sam:video" and e.event_index is None else "event"
            candidates.append((e.frame_start, f"{role}_start", [e.evidence_id]))
            if e.frame_end is not None and e.frame_end - 1 != e.frame_start:
                candidates.append((max(e.frame_start, e.frame_end - 1), f"{role}_end", [e.evidence_id]))
    ef = report.get("earliest_failure") or {}
    if isinstance(ef.get("frame_start"), int):
        candidates.append((ef["frame_start"], "earliest_failure_start", []))
    if end_frame is not None:
        candidates.append((end_frame, "end_state", []))

    # Merge by frame index
    by_frame: dict[int, dict[str, Any]] = {}
    for frame, role, eids in candidates:
        slot = by_frame.setdefault(frame, {"roles": [], "eids": []})
        if role not in slot["roles"]:
            slot["roles"].append(role)
        for eid in eids:
            if eid not in slot["eids"]:
                slot["eids"].append(eid)

    # Prefer event-related frames; cap
    ordered = sorted(by_frame.items(), key=lambda kv: (
        0 if any(r.startswith("event") or r.startswith("gripper") or r.startswith("earliest") for r in kv[1]["roles"]) else 1,
        kv[0],
    ))
    selected = ordered[:max_frames]
    # Always include end_state if provided and not already in
    if end_frame is not None and end_frame not in {f for f, _ in selected}:
        if len(selected) >= max_frames:
            selected = selected[:-1]
        selected.append((end_frame, by_frame.get(end_frame, {"roles": ["end_state"], "eids": []})))
        selected = sorted(selected, key=lambda kv: kv[0])

    fps = _fps_from_report(report)
    refs: list[FrameRef] = []
    for i, (frame, meta) in enumerate(selected):
        if isinstance(meta, dict) and "roles" in meta:
            roles, eids = meta["roles"], meta["eids"]
        else:
            roles, eids = meta["roles"], meta["eids"]
        refs.append(FrameRef(
            frame_ref=f"F{i}",
            frame_index=int(frame),
            timestamp_s=round(int(frame) / fps, 3),
            tied_evidence_ids=list(eids),
            role="+".join(roles),
        ))
    return refs


def build_evidence_package(
    *,
    task_description: str,
    failure_report: dict[str, Any],
    experiment_id: str,
    frozen_config: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    end_state: dict[str, Any] | None = None,
    tracking_notes: list[str] | None = None,
    end_frame: int | None = None,
    max_frames: int = 6,
    analysis_scope: dict[str, Any] | None = None,
    context_frames: list[int] | None = None,
    strict_grounding: bool = False,
    observations: list[Any] | None = None,
) -> EvidencePackage:
    """Assemble a Muse-ready package from a FailureReport dict (+ optional end_state)."""
    evidence_items, events = _collect_evidence_from_report(failure_report)
    by_track: dict[str, list[Any]] = {}
    for obs in observations or []:
        if obs.observation_returned and obs.frame_index is not None and obs.bbox is not None:
            by_track.setdefault(obs.object_id, []).append(obs)
    for track_id, items in sorted(by_track.items()):
        items.sort(key=lambda o: o.frame_index)
        first, last = items[0], items[-1]
        evidence_items.append(EvidenceItem(
            evidence_id=f"E{len(evidence_items)}", source="sam:video", kind="detection",
            status_context="observed", frame_start=first.frame_index, frame_end=last.frame_index + 1,
            t_start=first.timestamp_s, t_end=last.timestamp_s, track_id=track_id,
            summary=f"SAM returned {len(items)} 2D detections for track {track_id} "
                    f"at frames {first.frame_index} through {last.frame_index}; "
                    "this does not establish holding, gripper opening, or task completion."))
    # Attach end-state as citable evidence if present
    if end_state and end_state.get("plate_observations"):
        eid = f"E{len(evidence_items)}"
        summaries = []
        for p in end_state["plate_observations"]:
            summaries.append(
                f"{p.get('object_id')}: region={p.get('region')} conf={p.get('confidence')}"
            )
        evidence_items.append(
            EvidenceItem(
                evidence_id=eid,
                source="sam:green plate (end keyframe)",
                kind="detection",
                status_context="uncertain",
                frame_start=end_state.get("frame"),
                frame_end=(end_state.get("frame") or 0) + 1 if end_state.get("frame") is not None else None,
                t_start=None,
                t_end=None,
                summary="End-of-episode plate observations: " + "; ".join(summaries),
                claims=[],
                note=(
                    "End-image object ids are from a separate SAM request; not matched to window track ids. "
                    + str(end_state.get("note") or "")
                ),
            )
        )
        if end_frame is None:
            end_frame = end_state.get("frame")

    frame_refs = _pick_frames_for_package(
        failure_report, evidence_items, end_frame=end_frame, max_frames=max_frames,
    )
    # Context images are pixels for interpretation, never fabricated event evidence.
    for fi in dict.fromkeys(context_frames or []):
        if len(frame_refs) >= max_frames:
            break
        if fi >= 0 and not any(r.frame_index == fi for r in frame_refs):
            frame_refs.append(FrameRef(f"F{len(frame_refs)}", fi,
                                       fi / _fps_from_report(failure_report), [], "context"))

    provenance = {
        "experiment_id": experiment_id,
        "task_id": failure_report.get("task_id"),
        "inputs": {
            k: failure_report.get("inputs", {}).get(k)
            for k in ("fps", "n_frames", "joint_data", "gripper_calibration")
            if (failure_report.get("inputs") or {}).get(k) is not None
        },
        "verification": {
            "claims_checked": (verification or {}).get("claims_checked"),
            "claims_failed": (verification or {}).get("claims_failed"),
            "event_verdicts": (verification or {}).get("event_verdicts"),
        } if verification else None,
        "frozen_config_experiment": (frozen_config or {}).get("experiment"),
        "frozen_git_head": (frozen_config or {}).get("git_head"),
        "gripper_detector": ((frozen_config or {}).get("gripper_calibration") or {}).get("detector"),
    }

    notes = list(tracking_notes or [])
    if strict_grounding:
        from failure_inputs import observation_coverage

        provenance["strict_grounding"] = True
        provenance["analysis_scope"] = analysis_scope or {"complete_demonstration": False}
        source_info = (failure_report.get("inputs") or {}).get("sources") or {}
        provenance["target_segmentation"] = source_info.get("container")
        scope = analysis_scope or {}
        if observations is not None and scope.get("frame_end") is not None:
            coverage = observation_coverage(observations, scope.get("frame_start", 0), scope["frame_end"])
            provenance["observation_coverage"] = coverage
            notes.append(f"{coverage['missing_frames']} of {coverage['expected_frames']} frames lack returned "
                         "detections. Detection gaps are not continuous tracking or proof of absence.")
        notes.append("For factual_claims, copy a cited evidence summary exactly. "
                     "Free-form explanation is unverified and is not published as verified fact. "
                     "Never upgrade the deterministic verdict; context frames are not event measurements.")
    notes.append(
        "Missing SAM detections are never treated as proof of physical absence."
    )
    if not events:
        notes.append("Pipeline reported zero physical failure events for this window.")

    verdict = failure_report.get("verdict") or "uncertain"
    if verdict not in ("success", "failure", "uncertain"):
        verdict = "uncertain"

    return EvidencePackage(
        task_id=str(failure_report.get("task_id") or "unknown"),
        task_description=task_description,
        experiment_id=experiment_id,
        provenance=provenance,
        deterministic_verdict=verdict,  # type: ignore[arg-type]
        failure_type=failure_report.get("failure_type"),
        earliest_failure=failure_report.get("earliest_failure"),
        physical_events=events,
        evidence_items=evidence_items,
        uncertainties=list(failure_report.get("uncertainties") or []),
        tracking_notes=notes,
        final_state=end_state,
        frame_refs=frame_refs,
    )


def load_experiment_package(
    experiment_dir: Path,
    *,
    task_description: str,
    video_path: Path | None = None,
    max_frames: int = 6,
) -> EvidencePackage:
    """Load failure_report (+ optional run_report end_state / frozen_config) from an experiment folder."""
    experiment_dir = Path(experiment_dir)
    report = json.loads((experiment_dir / "failure_report.json").read_text(encoding="utf-8"))
    frozen = None
    if (experiment_dir / "frozen_config.json").is_file():
        frozen = json.loads((experiment_dir / "frozen_config.json").read_text(encoding="utf-8"))
    verification = None
    if (experiment_dir / "verification.json").is_file():
        verification = json.loads((experiment_dir / "verification.json").read_text(encoding="utf-8"))
    end_state = None
    end_frame = None
    if (experiment_dir / "run_report.json").is_file():
        run = json.loads((experiment_dir / "run_report.json").read_text(encoding="utf-8"))
        end_state = run.get("end_state")
        if end_state:
            end_frame = end_state.get("frame")
    if frozen and frozen.get("sam_plan"):
        end_frame = end_frame or frozen["sam_plan"].get("end_frame_plate")

    return build_evidence_package(
        task_description=task_description,
        failure_report=report,
        experiment_id=experiment_dir.name,
        frozen_config=frozen,
        verification=verification,
        end_state=end_state,
        end_frame=end_frame,
        max_frames=max_frames,
    )


def load_package_frames(package: EvidencePackage, video_path: Path, *, max_width: int = 560) -> list[SampledFrame]:
    """Decode RGB frames listed in the package (for Muse multimodal input / dry-run)."""
    import cv2

    video = Path(video_path).read_bytes()
    out: list[SampledFrame] = []
    for ref in package.frame_refs:
        rgb = T.extract_frame_rgb(video, ref.frame_index)
        h, w = rgb.shape[:2]
        if w > max_width:
            nh = max(1, int(round(h * max_width / w)))
            rgb = cv2.resize(rgb, (max_width, nh), interpolation=cv2.INTER_AREA)
        out.append(SampledFrame(timestamp_s=ref.timestamp_s, rgb=rgb))
    return out


def dry_run_muse_payload(package: EvidencePackage, frames: list[SampledFrame] | None = None) -> dict[str, Any]:
    """Describe exactly what would be sent to Muse (no API call)."""
    text = package.to_muse_text_dict()
    return {
        "system_prompt_chars": len(MUSE_EVIDENCE_SYSTEM_PROMPT),
        "user_text_chars": len(json.dumps(text)),
        "n_evidence_items": len(package.evidence_items),
        "n_physical_events": len(package.physical_events),
        "n_frames": len(frames) if frames is not None else len(package.frame_refs),
        "frame_refs": [asdict(f) for f in package.frame_refs],
        "evidence_ids": sorted(package.evidence_id_set()),
        "deterministic_verdict": package.deterministic_verdict,
        "user_text_preview": text,
        "paid_call": False,
    }


def validate_muse_explanation(raw: dict[str, Any], package: EvidencePackage) -> ValidatedMuseExplanation:
    """Deterministically validate evidence references and outcome consistency."""
    errors: list[str] = []
    warnings: list[str] = []
    allowed_e = package.evidence_id_set()
    allowed_f = package.frame_ref_set()

    def _ids(val: Any) -> list[str]:
        if not isinstance(val, list):
            return []
        return [str(x) for x in val]

    explanation = str(raw.get("explanation") or "").strip()
    if not explanation:
        errors.append("missing explanation")

    outcome = str(raw.get("task_outcome") or "uncertain").strip().lower()
    if outcome not in ("success", "failure", "uncertain"):
        errors.append(f"invalid task_outcome {outcome!r}")
        outcome = "uncertain"

    outcome_ids = _ids(raw.get("outcome_evidence_ids"))
    for eid in outcome_ids:
        if eid not in allowed_e:
            errors.append(f"outcome_evidence_ids references unknown evidence_id {eid}")

    factual = raw.get("factual_claims") or []
    if not isinstance(factual, list):
        errors.append("factual_claims must be a list")
        factual = []
    clean_factual = []
    for i, claim in enumerate(factual):
        if not isinstance(claim, dict):
            errors.append(f"factual_claims[{i}] not an object")
            continue
        eids = _ids(claim.get("evidence_ids"))
        if not eids:
            errors.append(f"factual_claims[{i}] missing evidence_ids")
        for eid in eids:
            if eid not in allowed_e:
                errors.append(f"factual_claims[{i}] unknown evidence_id {eid}")
        clean_factual.append({"text": str(claim.get("text") or ""), "evidence_ids": eids})

    hypotheses = raw.get("hypotheses") or []
    if not isinstance(hypotheses, list):
        errors.append("hypotheses must be a list")
        hypotheses = []
    clean_hyp = []
    for i, h in enumerate(hypotheses):
        if not isinstance(h, dict):
            errors.append(f"hypotheses[{i}] not an object")
            continue
        eids = _ids(h.get("related_evidence_ids"))
        for eid in eids:
            if eid not in allowed_e:
                errors.append(f"hypotheses[{i}] unknown evidence_id {eid}")
        clean_hyp.append({"text": str(h.get("text") or ""), "related_evidence_ids": eids, "label": "hypothesis"})

    visuals = raw.get("visual_interpretations") or []
    if not isinstance(visuals, list):
        errors.append("visual_interpretations must be a list")
        visuals = []
    clean_vis = []
    for i, v in enumerate(visuals):
        if not isinstance(v, dict):
            errors.append(f"visual_interpretations[{i}] not an object")
            continue
        fref = v.get("frame_ref")
        if fref is not None and str(fref) not in allowed_f:
            errors.append(f"visual_interpretations[{i}] unknown frame_ref {fref}")
        if not v.get("not_verified_by_pipeline", True):
            warnings.append(f"visual_interpretations[{i}] should set not_verified_by_pipeline=true")
        clean_vis.append({
            "text": str(v.get("text") or ""),
            "frame_ref": fref,
            "not_verified_by_pipeline": True,
        })

    interval = raw.get("earliest_failure_interval")
    if interval is not None:
        if not isinstance(interval, dict):
            errors.append("earliest_failure_interval must be object or null")
            interval = None
        else:
            eids = _ids(interval.get("evidence_ids"))
            for eid in eids:
                if eid not in allowed_e:
                    errors.append(f"earliest_failure_interval unknown evidence_id {eid}")
            if not package.physical_events and eids:
                errors.append("earliest_failure_interval cites evidence but package has no physical events")
            if package.deterministic_verdict == "uncertain" and not package.earliest_failure:
                # Model may still propose an interval — require it be labeled carefully
                if outcome == "failure" and not package.physical_events:
                    errors.append("task_outcome=failure with empty physical_events is unsupported")
            interval = {
                "t_start": interval.get("t_start"),
                "t_end": interval.get("t_end"),
                "evidence_ids": eids,
                "note": interval.get("note"),
            }

    # Consistency: upgrading empty-event packages to success/failure
    if not package.physical_events:
        end_regions = []
        if package.final_state:
            end_regions = [p.get("region") for p in package.final_state.get("plate_observations") or []]
        if outcome == "failure":
            if "outside" not in end_regions:
                errors.append(
                    "unsupported failure outcome: no physical events and no end-state region=outside"
                )
            elif not outcome_ids:
                warnings.append("failure outcome should cite end-state evidence_ids")
        if outcome == "success":
            if not end_regions or any(r != "inside" for r in end_regions):
                errors.append(
                    "unsupported success outcome: pipeline did not establish inside-rack "
                    "final state for all plates"
                )

    if package.earliest_failure and interval is None and outcome == "failure":
        warnings.append("pipeline has earliest_failure but model returned null earliest_failure_interval")

    limitations = raw.get("limitations") or []
    if isinstance(limitations, str):
        limitations = [limitations]
    if not isinstance(limitations, list):
        limitations = []
        errors.append("limitations must be a list")
    limitations = [str(x) for x in limitations]

    if outcome not in ("uncertain", package.deterministic_verdict):
        errors.append("task_outcome cannot upgrade or contradict the deterministic verdict")
    if package.provenance.get("strict_grounding"):
        if not (package.provenance.get("analysis_scope") or {}).get("complete_demonstration") and outcome != "uncertain":
            errors.append("partial observation window cannot establish whole-task outcome")
    catalog = {e.evidence_id: e for e in package.evidence_items}
    for claim in clean_factual:
        # Citation existence is not entailment, including for older packages.
        if len(claim["evidence_ids"]) != 1 or not any(claim["text"] == catalog[eid].summary
                   for eid in claim["evidence_ids"] if eid in catalog):
            errors.append("factual claim is not a canonical cited evidence summary")
    if interval is not None and (not package.earliest_failure or
            any(interval.get(k) != package.earliest_failure.get(k) for k in ("t_start", "t_end"))):
        errors.append("earliest failure interval is not established by the pipeline")
    explanation = f"Task outcome: {outcome}. " + " ".join(
        f"[{', '.join(c['evidence_ids'])}] "
        f"({catalog[c['evidence_ids'][0]].status_context}) {c['text']}"
        for c in clean_factual
        if c["evidence_ids"] and c["evidence_ids"][0] in catalog
    )
    if not clean_factual:
        explanation += "Insufficient verified evidence for a more specific conclusion."
    limitations.append("Muse free-form narrative is retained only in raw diagnostics; "
                       "published factual text is copied from the pipeline catalog.")

    return ValidatedMuseExplanation(
        ok=not errors,
        explanation=explanation,
        task_outcome=outcome,  # type: ignore[arg-type]
        earliest_failure_interval=interval,
        factual_claims=clean_factual,
        hypotheses=clean_hyp,
        visual_interpretations=clean_vis,
        limitations=limitations,
        outcome_evidence_ids=outcome_ids,
        validation_errors=errors,
        validation_warnings=warnings,
        raw=raw,
    )
