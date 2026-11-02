"""Explicit task-criterion assessment over saved evidence (pure rules; no I/O, no API calls).

Each declared task criterion receives one of four states:

- supported     - cited evidence satisfies the criterion (within the stated basis, e.g. 2D only).
- contradicted  - cited evidence shows the criterion is violated.
- unverified    - the criterion applies, but available evidence cannot settle it. Each unverified
                  criterion lists EvidenceRequirements: observations that could resolve it. These are
                  requirements, never fabricated measurements.
- not_assessed  - the task specification does not declare the criterion (or it is out of scope).

Missing evidence is never converted into failure. Reference / ground-truth outcomes are never an input:
this module only sees InvestigationEvidence built from saved inference artifacts.

Multi-view inputs: an ObjectObservation carries a `view`; observations of one object from several views
are combined conservatively (any inside-vs-outside disagreement -> unknown). With one view, regions that
remain unknown request an additional viewpoint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from dataclasses import replace
import math
from typing import Any, Iterable, Literal

CriterionState = Literal["supported", "contradicted", "unverified", "not_assessed"]
CriterionKind = Literal["containment", "orientation", "inventory", "grasp_release", "completion", "action"]
RequirementKind = Literal[
    "additional_viewpoint",
    "final_state_observation",
    "gripper_measurement",
    "destination_mask",
    "continuous_tracking",
    "orientation_measurement",
    "task_specification",
]
Region = Literal["inside", "outside", "unknown"]
STATES: tuple[CriterionState, ...] = ("supported", "contradicted", "unverified", "not_assessed")


# --- task criteria specification ----------------------------------------------

@dataclass(frozen=True)
class CriterionSpec:
    criterion_id: str
    kind: CriterionKind
    required: bool
    description: str
    basis: str = ""  # where the requirement comes from (task text, dataset task definition, ...)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectRequirement:
    concept: str
    count: int | None = None  # None = expected count not declared


@dataclass(frozen=True)
class TaskCriteria:
    task_id: str
    description: str
    target: str
    objects: tuple[ObjectRequirement, ...]
    criteria: tuple[CriterionSpec, ...]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TaskCriteria":
        return TaskCriteria(
            task_id=str(d["task_id"]),
            description=str(d.get("description") or ""),
            target=str(d["target"]),
            objects=tuple(ObjectRequirement(str(o["concept"]), o.get("count")) for o in d.get("objects") or []),
            criteria=tuple(CriterionSpec(str(c["criterion_id"]), c["kind"], bool(c.get("required", True)),
                                         str(c.get("description") or ""), str(c.get("basis") or ""),
                                         dict(c.get("params") or {})) for c in d.get("criteria") or []),
        )


# --- normalized evidence (built by adapters from saved artifacts) ------------------------------

@dataclass(frozen=True)
class ObjectObservation:
    object_id: str
    concept: str
    region: Region
    frame: int
    evidence_ids: tuple[str, ...]
    view: str = "primary"
    note: str = ""


@dataclass(frozen=True)
class OrientationObservation:
    """Placeholder interface: no saved investigation measures orientation today."""
    object_id: str
    satisfies: bool | None  # None = measured but inconclusive
    frame: int
    evidence_ids: tuple[str, ...]
    view: str = "primary"


@dataclass(frozen=True)
class EventRecord:
    kind: str  # failures.PhysicalEvent.kind
    subtype: str
    status: str  # observed | inferred | uncertain
    track_id: str
    frame_start: int
    frame_end: int
    evidence_ids: tuple[str, ...]
    verifier_verdict: str | None = None  # verification.event_verdicts value, if checked
    uncertainties: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourcePredicate:
    """Adapter-validated structured source predicate, never extracted from model prose.

    source_ref identifies the original artifact/record; package_id scopes its citation.
    The adapter must check source geometry/measurement and catalog scope before creating it.
    """
    evidence_id: str
    kind: str  # containment_2d | detection | orientation | physical_release | event_inference
    object_id: str
    frame: int
    value: str
    view: str = "primary"
    source_ref: str = ""
    package_id: str = ""
    measurement: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvestigationEvidence:
    investigation_id: str
    task_id: str
    n_frames: int
    fps: float
    evidence_ids: frozenset[str]  # the investigation's citable catalog
    final_observations: list[ObjectObservation] = field(default_factory=list)
    destination: Literal["available", "unavailable", "not_requested", "unassessed"] = "not_requested"
    destination_evidence_ids: tuple[str, ...] = ()
    tracking_windows: list[tuple[int, int]] = field(default_factory=list)  # [start, end) with returned detections
    tracking_missing_ranges: list[tuple[int, int]] = field(default_factory=list)
    tracking_evidence_ids: tuple[str, ...] = ()
    gripper: Literal["measured", "unavailable"] = "unavailable"
    gripper_open_frames: tuple[int, ...] = ()
    holding_detectable: bool | None = None
    gripper_evidence_ids: tuple[str, ...] = ()
    events: list[EventRecord] = field(default_factory=list)
    orientation_observations: list[OrientationObservation] = field(default_factory=list)
    viewpoints: tuple[str, ...] = ("primary",)
    notes: tuple[str, ...] = ()
    predicates: tuple[SourcePredicate, ...] = ()
    package_id: str = ""
    time_alignment_validated: bool = False
    # Explicit physical association identifiers, not matching camera-local track strings.
    object_associations: frozenset[str] = frozenset()
    analyzed_ranges: tuple[tuple[str, int, int], ...] = ()
    camera_motion: dict[str, str] = field(default_factory=dict)

    def tracked_frames(self) -> int:
        return sum(max(0, b - a) for a, b in self.tracking_windows) - sum(
            max(0, b - a) for a, b in self.tracking_missing_ranges)


# --- outputs -----------------------------------------------------------------------

@dataclass
class EvidenceRequirement:
    kind: RequirementKind
    criterion_id: str
    reason: str
    objects: tuple[str, ...] = ()
    frames: tuple[int, int] | None = None  # [start, end) that the observation should cover


@dataclass
class CriterionAssessment:
    criterion_id: str
    kind: CriterionKind
    required: bool
    state: CriterionState
    basis: str
    evidence_ids: list[str] = field(default_factory=list)
    objects: dict[str, str] = field(default_factory=dict)  # object_id -> per-object state/region
    requirements: list[EvidenceRequirement] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)  # completion only: unresolved criteria


@dataclass
class MechanismCandidate:
    """A failure mechanism the saved pipeline evidence points to (never from model text or references)."""
    mechanism: str
    category: str  # coarse class used by evaluation, e.g. placement_outside_target
    status: str  # observed | inferred | end_state
    verifier: str  # supported | failed | not_checked
    objects: list[str]
    frames: tuple[int, int] | None
    evidence_ids: list[str]
    alternatives: list[str] = field(default_factory=list)
    criterion_id: str | None = None
    resolving_evidence: list[EvidenceRequirement] = field(default_factory=list)  # separates the alternatives


@dataclass
class CriteriaReport:
    investigation_id: str
    task_id: str
    assessments: list[CriterionAssessment]
    mechanisms: list[MechanismCandidate]
    completion: CriterionState
    abstention_explanation: str | None
    evidence_requirements: list[EvidenceRequirement]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def by_id(self, criterion_id: str) -> CriterionAssessment | None:
        return next((a for a in self.assessments if a.criterion_id == criterion_id), None)


# --- helpers ----------------------------------------------------------------------------

def combine_views(observations: Iterable[ObjectObservation], *, aligned: bool = False,
                  associated: frozenset[str] = frozenset()) -> dict[str, tuple[Region, list[str], list[str]]]:
    """object_id -> (region, evidence_ids, views). Any inside/outside disagreement -> unknown."""
    grouped: dict[str, list[ObjectObservation]] = {}
    for o in observations:
        grouped.setdefault(o.object_id, []).append(o)
    out: dict[str, tuple[Region, list[str], list[str]]] = {}
    for oid, obs in grouped.items():
        regions = {o.region for o in obs} - {"unknown"}
        views = {o.view for o in obs}
        can_combine = len(views) == 1 or (aligned and oid in associated)
        region: Region = regions.pop() if len(regions) == 1 and can_combine else "unknown"
        out[oid] = (region, _uniq(e for o in obs for e in o.evidence_ids), _uniq(o.view for o in obs))
    return out


def _uniq(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _final_frame_ok(ev: InvestigationEvidence, tail_s: float, *, sampled_2d: bool = False) -> tuple[bool, int | None]:
    if not ev.final_observations:
        return False, None
    frame = max(o.frame for o in ev.final_observations)
    # No late/intermediate frame may stand in for an unobserved final state.
    return (ev.n_frames > 0 and math.isfinite(ev.fps) and ev.fps > 0
            and all(0 <= o.frame < ev.n_frames and
                    (o.frame == ev.n_frames - 1 or (sampled_2d and
                     ev.n_frames - 1 - o.frame <= tail_s * ev.fps)) for o in ev.final_observations)
            and len({o.frame for o in ev.final_observations}) == 1), frame


def _supports(ev: InvestigationEvidence, ids: Iterable[str], kind: str, oid: str,
              frame: int, value: str, view: str = "primary") -> bool:
    return any(p.evidence_id in ids and p.evidence_id in ev.evidence_ids
               and p.kind == kind and p.object_id == oid and p.frame == frame
               and p.value == value and p.view == view and bool(p.source_ref)
               and bool(ev.package_id) and p.package_id == ev.package_id
               for p in ev.predicates)


def _bound_evidence(ev: InvestigationEvidence) -> InvestigationEvidence:
    """Reject normalized assertions unless the cited structured source entails them."""
    observations = [replace(o, region=o.region if _supports(
        ev, o.evidence_ids, "containment_2d", o.object_id, o.frame, o.region, o.view) else "unknown")
        for o in ev.final_observations]
    orientations = [o for o in ev.orientation_observations if
        o.frame == ev.n_frames - 1 and _supports(ev, o.evidence_ids, "orientation", o.object_id,
                                               o.frame, str(o.satisfies), o.view)]
    return replace(ev, final_observations=observations, orientation_observations=orientations)


def _concepts(task: TaskCriteria) -> set[str]:
    return {o.concept for o in task.objects}


# --- assessors ------------------------------------------------------------------------

def assess_containment(spec: CriterionSpec, task: TaskCriteria, ev: InvestigationEvidence) -> CriterionAssessment:
    a = CriterionAssessment(spec.criterion_id, "containment", spec.required, "unverified", "")
    tail_s = float(spec.params.get("final_tail_s", 1.0))
    if ev.destination != "available":
        a.basis = ("No validated final-state destination interior / containment measurement was supplied. "
                   "A returned raw SAM footprint may be available, but does not establish calibrated containment; "
                   "this assessment does not classify segmentation as missing."
                   if ev.destination == "unassessed" else
                   f"Destination '{task.target}' segmentation is {ev.destination}; containment cannot be "
                   "measured. This does not mean the destination was absent.")
        a.evidence_ids = list(ev.destination_evidence_ids)
        a.requirements.append(EvidenceRequirement("destination_mask", a.criterion_id,
            f"A usable '{task.target}' mask (or calibrated interior) at the final-state frame."))
        if not ev.final_observations:
            a.requirements.append(_final_req(a.criterion_id, ev, task))
        return a
    sampled = spec.params.get("observation_scope") == "sampled_keyframe_2d"
    final_ok, frame = _final_frame_ok(ev, tail_s, sampled_2d=sampled)
    relevant = [o for o in ev.final_observations if o.concept in _concepts(task)]
    if not relevant or not final_ok:
        last = frame if frame is not None else None
        a.basis = ("No object observation near the end of the episode" if last is None else
                   f"Latest object-region observation is frame {last} of {ev.n_frames}; the final position "
                   "after that is unobserved, so intermediate regions are not treated as the final state.")
        outside = [o.object_id for o in relevant if o.region == "outside"]
        if outside:
            a.basis += f" Intermediate outside observations: {', '.join(outside)} (recovery remains possible)."
        a.evidence_ids = _uniq(e for o in relevant for e in o.evidence_ids)
        a.requirements.append(_final_req(a.criterion_id, ev, task))
        if last is not None:
            a.requirements.append(EvidenceRequirement("continuous_tracking", a.criterion_id,
                "Track each object from its last observation to the end to establish where it ends up.",
                frames=(last + 1, ev.n_frames)))
        return a
    regions = combine_views(relevant, aligned=ev.time_alignment_validated, associated=ev.object_associations)
    scope = f"sampled keyframe {frame} (2D only; later frames unobserved)" if sampled else f"final frame {frame}"
    a.objects = {oid: r for oid, (r, _, _) in regions.items()}
    outside = [oid for oid, (r, _, _) in regions.items() if r == "outside"]
    unknown = [oid for oid, (r, _, _) in regions.items() if r == "unknown"]
    if outside:
        a.state = "contradicted"
        a.evidence_ids = _uniq(e for oid in outside for e in regions[oid][1])
        a.basis = (f"At {scope}, {len(outside)} observed object(s) lie outside the '{task.target}' "
                   f"footprint in 2D ({', '.join(outside)}).")
        if unknown:
            a.basis += f" {len(unknown)} other region(s) remain unknown."
        return a
    a.evidence_ids = _uniq(e for _, (_, eids, _) in regions.items() for e in eids)
    if not unknown:
        a.state = "supported"
        a.basis = (f"At {scope}, all {len(regions)} observed object(s) are inside the "
                   f"'{task.target}' in 2D image space (not 3D placement or orientation).")
        return a
    n_views = len(set(ev.viewpoints))
    a.basis = (f"At {scope}, {len(unknown)} of {len(regions)} region(s) are unknown "
               f"(insufficient single-view geometry or view disagreement); none are outside.")
    a.requirements.append(EvidenceRequirement("additional_viewpoint", a.criterion_id,
        ("A second camera viewpoint of the destination at the final frame to separate inside from "
         "overlap/occlusion." if n_views < 2 else
         "Views disagree or are inconclusive; a further viewpoint or calibrated interior is needed."),
        objects=tuple(unknown), frames=(frame, frame + 1)))
    return a


def _final_req(cid: str, ev: InvestigationEvidence, task: TaskCriteria) -> EvidenceRequirement:
    return EvidenceRequirement("final_state_observation", cid,
        f"Object detections and destination geometry at the last frame {ev.n_frames - 1}; earlier observations do not establish the final state.",
        objects=tuple(sorted(_concepts(task))), frames=(max(0, ev.n_frames - 1), ev.n_frames))


def assess_orientation(spec: CriterionSpec, task: TaskCriteria, ev: InvestigationEvidence) -> CriterionAssessment:
    a = CriterionAssessment(spec.criterion_id, "orientation", spec.required, "unverified", "")
    pose = spec.params.get("required_pose", "declared pose")
    if not spec.params.get("required_pose"):
        a.basis = "No approved orientation success predicate is specified. Model suggestions and dataset anomaly wording do not define it."
        a.requirements.append(EvidenceRequirement("task_specification", a.criterion_id,
            "Specify the required physical pose independently of episode outcomes."))
        a.requirements.append(EvidenceRequirement("orientation_measurement", a.criterion_id,
            "An independently validated final-frame orientation measurement is also needed."))
        return a
    obs = [o for o in ev.orientation_observations if _supports(ev, o.evidence_ids,
        "orientation_pose", o.object_id, o.frame, str(pose), o.view)]
    views = {o.view for o in obs}
    if len(views) > 1 and (not ev.time_alignment_validated or
                           not {o.object_id for o in obs} <= ev.object_associations):
        obs = []
    if any(len({o.satisfies for o in obs if o.object_id == oid}) > 1
           for oid in {o.object_id for o in obs}):
        obs = []  # Conflicting views cannot establish either physical pose claim.
    if obs:
        a.evidence_ids = _uniq(e for o in obs for e in o.evidence_ids)
        a.objects = {o.object_id: {True: "satisfies", False: "violates", None: "inconclusive"}[o.satisfies] for o in obs}
        bad = [o.object_id for o in obs if o.satisfies is False]
        if bad:
            a.state = "contradicted"
            a.evidence_ids = _uniq(e for o in obs if o.satisfies is False for e in o.evidence_ids)
            a.basis = f"Measured orientation violates '{pose}' for {', '.join(bad)}."
            return a
        expected = {o.object_id for o in ev.final_observations if o.concept in _concepts(task)}
        if expected and all(o.satisfies for o in obs) and {o.object_id for o in obs} == expected:
            a.state = "supported"
            a.basis = f"Measured orientation satisfies '{pose}' for every observed object."
            return a
    a.basis = (f"Required pose '{pose}' is not measured by this investigation. 2D containment and model "
               "visual impressions do not establish physical orientation.")
    a.requirements += [
        EvidenceRequirement("orientation_measurement", a.criterion_id,
            f"An independent orientation predicate for '{pose}' (e.g. slot-aligned mask axis calibrated on the "
            "destination, or object pose estimation) at the final frame."),
        EvidenceRequirement("additional_viewpoint", a.criterion_id,
            "A side or top view of the destination in which slot engagement / upright pose is visible."),
    ]
    return a


def assess_inventory(spec: CriterionSpec, task: TaskCriteria, ev: InvestigationEvidence) -> CriterionAssessment:
    a = CriterionAssessment(spec.criterion_id, "inventory", spec.required, "unverified", "")
    final_ok, frame = _final_frame_ok(ev, float(spec.params.get("final_tail_s", 1.0)))
    parts, supported = [], True
    for req in task.objects:
        seen = sorted({o.object_id for o in ev.final_observations if o.concept == req.concept
                       and _supports(ev, o.evidence_ids, "detection", o.object_id, o.frame, req.concept, o.view)})
        views = {o.view for o in ev.final_observations}
        identities_ok = len(views) <= 1 or (ev.time_alignment_validated and set(seen) <= ev.object_associations)
        a.evidence_ids += [e for o in ev.final_observations if o.concept == req.concept for e in o.evidence_ids]
        where = f"final frame {frame}" if final_ok else f"latest observation (frame {frame}, not final)"
        if req.count is None:
            supported = False
            parts.append(f"{len(seen)} '{req.concept}' detected at the {where}, but the expected count "
                         "is not declared")
            a.requirements.append(EvidenceRequirement("task_specification", a.criterion_id,
                f"Declare the expected number of '{req.concept}' so detections can be checked for completeness.",
                objects=(req.concept,)))
        elif not final_ok:
            supported = False
            parts.append(f"no final-state observation for '{req.concept}'")
        elif len(seen) == req.count and identities_ok:
            parts.append(f"{len(seen)}/{req.count} '{req.concept}' located at final frame {frame}")
        else:
            supported = False
            parts.append(f"{len(seen)}/{req.count} '{req.concept}' located (missing or duplicate identities)")
            a.requirements.append(EvidenceRequirement("additional_viewpoint", a.criterion_id,
                f"A second view to find occluded or merged '{req.concept}' instances.", objects=(req.concept,)))
            a.requirements.append(EvidenceRequirement("continuous_tracking", a.criterion_id,
                f"Continuous tracking of every '{req.concept}' to preserve identity through occlusion.",
                objects=(req.concept,)))
    if not final_ok:
        a.requirements.append(_final_req(a.criterion_id, ev, task))
    a.evidence_ids = _uniq(a.evidence_ids)
    a.state = "supported" if supported and final_ok and task.objects else "unverified"
    a.basis = "; ".join(parts) + "." if parts else "No required objects declared."
    return a


def assess_grasp_release(spec: CriterionSpec, task: TaskCriteria, ev: InvestigationEvidence) -> CriterionAssessment:
    a = CriterionAssessment(spec.criterion_id, "grasp_release", spec.required, "unverified", "")
    outside_releases = [e for e in ev.events if e.subtype == "released_outside_target"]
    observed_bad = [e for e in outside_releases if e.status == "observed" and e.verifier_verdict == "supported"
                    and _supports(ev, e.evidence_ids, "physical_release", e.track_id, e.frame_start, e.subtype)]
    if observed_bad and ev.holding_detectable:
        a.state = "contradicted"
        a.evidence_ids = _uniq(x for e in observed_bad for x in e.evidence_ids)
        a.basis = "Observed, verifier-supported release outside the target with a holding-sensitive gripper signal."
        return a
    if ev.gripper == "unavailable":
        a.basis = "No gripper measurement: grasp and release cannot be measured; video-only position changes do not establish them."
        a.requirements.append(EvidenceRequirement("gripper_measurement", a.criterion_id,
            "Recorded gripper joint (and ideally width/current) synchronized with the video."))
    else:
        a.evidence_ids = list(ev.gripper_evidence_ids)
        opens = ", ".join(str(f) for f in ev.gripper_open_frames) or "none listed"
        a.basis = f"Gripper openings measured (frames {opens})"
        if not ev.holding_detectable:
            a.basis += ", but this gripper signal cannot show whether an object is held, so release is not established."
            a.requirements.append(EvidenceRequirement("gripper_measurement", a.criterion_id,
                "A holding-sensitive signal (motor current, force, or jaw width with object) around each opening.",
                frames=_span(ev.gripper_open_frames)))
        else:
            a.basis += "."
    if outside_releases:
        a.evidence_ids = _uniq(a.evidence_ids + [x for e in outside_releases for x in e.evidence_ids])
        a.basis += (f" {len(outside_releases)} release(s) outside the target are inferred (status "
                    f"{'/'.join(sorted({e.status for e in outside_releases}))}), not observed.")
    if ev.tracking_missing_ranges:
        for start, end in ev.tracking_missing_ranges:
            a.requirements.append(EvidenceRequirement("continuous_tracking", a.criterion_id,
                f"Object observations are missing for frames {start}-{end - 1}; recover tracking there "
                "(e.g. another viewpoint around the occluder) to see where the object is put down.",
                frames=(start, end)))
    else:
        a.requirements.append(EvidenceRequirement("continuous_tracking", a.criterion_id,
            "Continuous object tracking through each gripper opening to associate the object with the release.",
            frames=_span(ev.gripper_open_frames)))
    return a


def _span(frames: Iterable[int]) -> tuple[int, int] | None:
    f = list(frames)
    return (min(f), max(f) + 1) if f else None


def assess_action(spec, task, ev):
    from task_actions import assess_action as assessor
    return assessor(spec, task, ev)


ASSESSORS = {"containment": assess_containment, "orientation": assess_orientation,
             "inventory": assess_inventory, "grasp_release": assess_grasp_release, "action": assess_action}


def assess_completion(spec: CriterionSpec, parts: list[CriterionAssessment]) -> CriterionAssessment:
    required = [p for p in parts if p.required]
    a = CriterionAssessment(spec.criterion_id, "completion", spec.required, "unverified", "")
    if not required:
        a.state, a.basis = "not_assessed", "No required criteria were assessable."
        return a
    bad = [p for p in required if p.state == "contradicted"]
    physical_bad = [p for p in bad if p.kind not in {"containment", "action"}]
    if physical_bad and spec.params.get("complete_scope") == "physical":
        a.state = "contradicted"
        a.evidence_ids = _uniq(e for p in physical_bad for e in p.evidence_ids)
        a.basis = "Contradicted by independently measured physical criteria: " + ", ".join(p.criterion_id for p in physical_bad) + "."
        return a
    open_ = [p for p in required if p.state != "supported"]
    if not open_:
        if spec.params.get("complete_scope") != "physical" or any(p.kind in {"containment", "action"} for p in required):
            a.basis = "The assessed predicates do not constitute a complete physical task specification. Supported 2D containment does not establish orientation, inventory, release or full completion."
            a.blocking = ["complete_task_specification"]
            a.requirements.append(EvidenceRequirement("task_specification", a.criterion_id,
                "An approved complete physical-task checklist and independent evidence for every required condition."))
            return a
        a.state = "supported"
        a.evidence_ids = _uniq(e for p in required for e in p.evidence_ids)
        a.basis = "Every required criterion is supported (within each criterion's stated basis)."
        return a
    a.blocking = [p.criterion_id for p in open_]
    a.basis = ("Physical completion remains unverified: " + ", ".join(a.blocking) +
               ". Any contradicted 2D sample is scoped to that frame; missing or later evidence is not treated as a final task outcome.")
    # Resolve completion through the actual open predicates, not a new invented
    # success condition or a generic second-view request.
    a.requirements = _dedupe(replace(r, criterion_id=a.criterion_id)
                             for p in open_ for r in p.requirements)
    if spec.params.get("complete_scope") != "physical":
        a.requirements.append(EvidenceRequirement("task_specification", a.criterion_id,
            "An operator-approved complete task checklist, followed by independent evidence for its stated conditions; unstated conditions are not assumed."))
    return a


# --- mechanisms ---------------------------------------------------------------------------

def mechanism_candidates(ev: InvestigationEvidence, assessments: list[CriterionAssessment]) -> list[MechanismCandidate]:
    out: list[MechanismCandidate] = []
    for e in ev.events:
        bound = (e.verifier_verdict == "supported" and e.status in ("inferred", "observed")
                 and 0 <= e.frame_start < e.frame_end <= ev.n_frames
                 and bool(e.evidence_ids) and all(x in ev.evidence_ids for x in e.evidence_ids)
                 and _supports(ev, e.evidence_ids, "event_inference", e.track_id, e.frame_start, e.subtype or e.kind))
        status = "inferred" if bound else "unverified"
        verifier = e.verifier_verdict or "not_checked"
        if e.subtype == "released_outside_target" or e.kind == "dropped_in_transport":
            out.append(MechanismCandidate(
                e.subtype or e.kind, "placement_outside_target", status, verifier,
                [e.track_id], (e.frame_start, e.frame_end), list(e.evidence_ids),
                ["intended placement that missed the target", "unintended drop during transport"],
                "grasp_release",
                [EvidenceRequirement("gripper_measurement", "grasp_release",
                    "A holding-sensitive gripper signal to show whether the object was held until the opening.",
                    (e.track_id,), (e.frame_start, e.frame_end)),
                 EvidenceRequirement("final_state_observation", "containment",
                    "The object's region at the episode end, to show whether the misplacement was recovered.",
                    (e.track_id,), (max(0, ev.n_frames - 1), ev.n_frames))]))
        elif e.kind == "failed_grasp":
            out.append(MechanismCandidate("failed_grasp", "failed_grasp", status, verifier,
                                          [e.track_id], (e.frame_start, e.frame_end), list(e.evidence_ids), [],
                                          "grasp_release"))
    for a in assessments:
        if a.kind == "containment" and a.state == "contradicted":
            objs = [o for o, r in a.objects.items() if r == "outside"]
            already = {t for m in out if m.category == "placement_outside_target" for t in m.objects}
            if set(objs) - already:
                last = max((b for _, b in ev.tracking_windows), default=0)
                sampled = any(o.object_id in objs and o.frame != ev.n_frames - 1 for o in ev.final_observations)
                out.append(MechanismCandidate("object_outside_target_at_sample" if sampled else "object_left_outside_target",
                    "placement_outside_target", "unverified" if sampled else "end_state",
                    "not_checked", objs, None, list(a.evidence_ids),
                    ["a later recovery remains unobserved", "never placed", "placed then displaced", "dropped in transport"], a.criterion_id,
                    [EvidenceRequirement("continuous_tracking", a.criterion_id,
                        "Track the outside object(s) from the last tracked window to the end to tell never-placed "
                        "from placed-then-displaced or dropped.", tuple(objs), (last, ev.n_frames))]))
        if a.kind == "orientation" and a.state == "contradicted":
            out.append(MechanismCandidate("incorrect_orientation", "incorrect_orientation", "observed", "not_checked",
                                          [o for o, s in a.objects.items() if s == "violates"], None,
                                          list(a.evidence_ids), [], a.criterion_id))
    return out


# --- entry point ------------------------------------------------------------------------------

def assess(task: TaskCriteria, ev: InvestigationEvidence) -> CriteriaReport:
    ev = _bound_evidence(ev)
    declared = {c.kind for c in task.criteria}
    parts: list[CriterionAssessment] = []
    for spec in task.criteria:
        if spec.kind in ASSESSORS:
            parts.append(ASSESSORS[spec.kind](spec, task, ev))
    for kind in ("containment", "orientation", "inventory", "grasp_release"):
        if kind not in declared:
            parts.append(CriterionAssessment(kind, kind, False, "not_assessed",  # type: ignore[arg-type]
                                             "The task specification does not declare this criterion."))
    completion_spec = next((c for c in task.criteria if c.kind == "completion"),
                           CriterionSpec("completion", "completion", True, "All required criteria hold."))
    _check_citations(parts, ev)
    completion = assess_completion(completion_spec, parts)
    _check_citations([completion], ev)
    assessments = parts + [completion]
    requirements = _dedupe(r for p in assessments if p.state == "unverified" for r in p.requirements)
    explanation = None
    if completion.state == "unverified":
        kinds = ", ".join(sorted({r.kind for r in requirements})) or "none identified"
        explanation = (f"Abstains on physical completion: unresolved criteria {', '.join(completion.blocking)}. "
                       f"Evidence that could resolve them: {kinds}. Scoped 2D findings are preserved separately.")
    return CriteriaReport(ev.investigation_id, task.task_id, assessments,
                          mechanism_candidates(ev, assessments), completion.state, explanation, requirements)


def _dedupe(reqs: Iterable[EvidenceRequirement]) -> list[EvidenceRequirement]:
    seen: dict[tuple, EvidenceRequirement] = {}
    for r in reqs:
        seen.setdefault((r.kind, r.criterion_id, r.objects, r.frames), r)
    return list(seen.values())


def _check_citations(assessments: list[CriterionAssessment], ev: InvestigationEvidence) -> None:
    """Supported/contradicted must cite existing evidence; otherwise demote to unverified."""
    for a in assessments:
        if a.state in ("supported", "contradicted"):
            if not a.evidence_ids or any(e not in ev.evidence_ids for e in a.evidence_ids):
                a.basis = f"[demoted from {a.state}: missing or unknown citation] " + a.basis
                a.state = "unverified"
