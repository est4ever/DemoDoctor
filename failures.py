"""Evidence-grounded failure localization (core rules; no API calls, no I/O).

Separates four things:
1. Physical failure events  - something observed went wrong (object came to rest
   outside the target after being moved, a grasp that left the object in place).
2. Recovery attempts        - a later move of the same object; succeeded / failed.
3. Final task outcome       - each object's final observed state, then the task verdict.
4. Insufficient evidence    - stated explicitly; never converted into a failure.

Inputs are plain data so the rules are testable without datasets:
- ObjectTrack: real detections of one tracked object (missing frames are simply
  absent; they are never interpreted).
- GripperSignal (optional): measured (and commanded) gripper joint plus a per-robot
  GripperCalibration. Without it, only video-only conclusions are drawn.

Thresholds are relative (object size, seconds, the gripper's own measured range);
nothing is tuned to a particular episode, camera, robot or object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

import numpy as np

Region = Literal["inside", "outside", "unknown"]
Status = Literal["observed", "inferred", "uncertain"]
Verdict = Literal["success", "failure", "uncertain"]


# --- specs and inputs --------------------------------------------------------

@dataclass(frozen=True)
class ObjectSpec:
    concept: str
    count: int | None = None  # expected number of instances, if known


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    description: str
    objects: tuple[ObjectSpec, ...]
    target: str  # target container concept
    success: Literal["all_objects_in_target"] = "all_objects_in_target"


@dataclass(frozen=True)
class TrackObs:
    frame: int
    x: float  # image position used for motion (e.g. bbox center)
    y: float
    size: float  # object scale in px (e.g. bbox diagonal) for relative thresholds
    region: Region = "unknown"  # relative to the target; see classify_region()


@dataclass
class ObjectTrack:
    track_id: str
    concept: str
    obs: list[TrackObs]

    def __post_init__(self) -> None:
        self.obs = sorted(self.obs, key=lambda o: o.frame)


@dataclass(frozen=True)
class GripperCalibration:
    """Per-robot (and per-object-type) gripper interpretation.

    holding_detectable: whether a held object measurably changes the closed
    reading for this robot/object (e.g. a stall). Must be justified in `basis`;
    when False, joint data can show opening/closing but never "holding".

    Opening detection (relative_rise, default): a sustained rise above a frozen
    local closed baseline by more than max(open_rise_frac * span, noise_mult *
    closed-plateau noise). Closing requires a settled level in the lower
    close_band_frac of the measured span after falling from the open peak.
    All thresholds are relative (fractions of the signal's own span / noise);
    open_sign flips the series so that larger values mean more open.
    """

    source: str  # e.g. "derived from verified success episode X"
    basis: str
    holding_detectable: bool
    persist_s: float = 0.15  # a crossing counts only if it persists this long
    detector: str = "relative_rise"  # "relative_rise" | "midpoint"
    open_sign: int = 1  # +1 if larger reading = more open; -1 otherwise
    open_rise_frac: float = 0.15  # min rise as a fraction of measured span
    noise_mult: float = 5.0  # rise must also exceed this x closed-plateau noise
    baseline_s: float = 0.5  # lookback used for the closed baseline / settle windows
    settle_frac: float = 0.02  # baseline may track only while this settled
    settle_noise_mult: float = 2.0
    close_settle_frac: float = 0.05  # close requires settle within this x span
    close_band_frac: float = 0.25  # settled close level must lie in lower this frac of span


@dataclass
class GripperSignal:
    measured: np.ndarray
    commanded: np.ndarray | None
    calibration: GripperCalibration


@dataclass(frozen=True)
class FailureParams:
    rest_motion_rel: float = 0.02  # per-frame motion below this x object size = at rest
    rest_min_s: float = 0.3  # a rest phase needs at least this much consecutive observation
    moved_rel: float = 0.5  # displacement >= this x object size counts as moved
    max_gap_s: float = 0.5  # observation gaps longer than this split phases (not interpreted)
    release_window_s: float = 0.7  # opening this close to the end of a move counts as a release
    final_min_span_s: float = 0.5  # final state needs >= 2 observations this far apart


# --- outputs ---------------------------------------------------------------

@dataclass
class Evidence:
    source: str  # sam:<concept> | proprio:<field>[<joint>] | derived
    kind: str  # detection | measurement | comparison
    frame_start: int
    frame_end: int  # exclusive
    summary: str
    claims: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PhysicalEvent:
    kind: Literal["dropped_in_transport", "failed_grasp", "image_position_change"]
    subtype: str
    status: Status
    track_id: str
    frame_start: int
    frame_end: int
    t_start: float
    t_end: float
    evidence: list[Evidence]
    inference: str | None = None
    uncertainties: list[str] = field(default_factory=list)


@dataclass
class RecoveryAttempt:
    after_event: int  # index into FailureReport.physical_events
    track_id: str
    outcome: Literal["succeeded", "failed", "unknown"]
    frame_start: int
    frame_end: int
    status: Status
    evidence: list[Evidence]
    uncertainties: list[str] = field(default_factory=list)


@dataclass
class ObjectOutcome:
    track_id: str
    concept: str
    final_region: Region
    status: Status
    frames: list[int]
    uncertainties: list[str] = field(default_factory=list)


@dataclass
class FailureReport:
    task_id: str
    verdict: Verdict
    failure_type: str | None
    earliest_failure: dict[str, Any] | None
    physical_events: list[PhysicalEvent]
    recoveries: list[RecoveryAttempt]
    object_outcomes: list[ObjectOutcome]
    uncertainties: list[str]
    inputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- helpers -------------------------------------------------------------------

def classify_region(assessment: dict[str, Any] | None, *, inside_frac: float = 0.8,
                    outside_footprint_frac: float = 0.05) -> Region:
    """Map a container.assess_containment() result to inside / outside / unknown.

    inside:  reliable interior estimate and >= inside_frac of the mask inside it.
    outside: essentially none of the mask inside the container's *filled footprint*
             (outside the footprint implies outside the interior, so no interior
             calibration is needed for this direction).
    """
    if not assessment:
        return "unknown"
    if assessment.get("reliable") and (assessment.get("interior_fraction") or 0) >= inside_frac:
        return "inside"
    ff = assessment.get("footprint_fraction")
    if ff is not None and ff <= outside_footprint_frac:
        return "outside"
    return "unknown"


@dataclass
class _Phase:
    kind: Literal["rest", "moving"]
    obs: list[TrackObs]

    @property
    def first(self) -> int:
        return self.obs[0].frame

    @property
    def last(self) -> int:
        return self.obs[-1].frame


def track_phases(track: ObjectTrack, fps: float, p: FailureParams) -> list[list[_Phase]]:
    """Split a track into runs (separated by observation gaps), each a list of rest/moving phases."""
    max_gap = max(1, int(round(p.max_gap_s * fps)))
    runs: list[list[TrackObs]] = []
    for o in track.obs:
        if runs and o.frame - runs[-1][-1].frame <= max_gap:
            runs[-1].append(o)
        else:
            runs.append([o])
    out = []
    rest_min = max(2, int(round(p.rest_min_s * fps)))
    for run in runs:
        still = [False] + [
            np.hypot(b.x - a.x, b.y - a.y) / max(1, b.frame - a.frame) <= p.rest_motion_rel * max(a.size, 1.0)
            for a, b in zip(run, run[1:])
        ]
        phases: list[_Phase] = []
        i = 0
        while i < len(run):
            j = i + 1
            while j < len(run) and still[j]:
                j += 1
            seg = run[i:j]
            kind = "rest" if len(seg) >= rest_min else "moving"
            if phases and phases[-1].kind == kind:
                phases[-1].obs.extend(seg)
            else:
                phases.append(_Phase(kind, list(seg)))
            i = j
        out.append(phases)
    return out


def _oriented(g: np.ndarray, cal: GripperCalibration) -> np.ndarray:
    """Return a view where larger values mean more open."""
    sign = 1 if int(cal.open_sign) >= 0 else -1
    arr = np.asarray(g, dtype=float)
    return arr if sign > 0 else -arr


def _closed_noise(g: np.ndarray, span: float) -> float:
    """P95 of |frame-to-frame diff| on the lower 20% of the measured span (closed plateaus)."""
    if span <= 0 or len(g) < 3:
        return 0.0
    lo = float(np.min(g))
    closed = g <= lo + 0.2 * span
    diffs = np.abs(np.diff(g))
    mask = closed[:-1] & closed[1:]
    if int(mask.sum()) < 5:
        return max(1e-9, 0.01 * span)
    return max(1e-9, float(np.percentile(diffs[mask], 95)))


def _transitions_midpoint(g: np.ndarray, fps: float, cal: GripperCalibration) -> list[tuple[str, int]]:
    """(kind, frame) of measured open/close crossings at the midpoint of the measured range.

    Kept for comparison / regression; the default detector is relative_rise.
    """
    g = _oriented(g, cal)
    lo, hi = float(np.min(g)), float(np.max(g))
    if hi - lo <= 0:
        return []
    mid = lo + 0.5 * (hi - lo)
    persist = max(1, int(round(cal.persist_s * fps)))
    side = g > mid
    out, cur, f = [], bool(side[0]), 1
    while f < len(g):
        if bool(side[f]) != cur and all(bool(side[k]) != cur for k in range(f, min(len(g), f + persist))):
            cur = bool(side[f])
            out.append(("open" if cur else "close", f))
            f += persist
            continue
        f += 1
    return out


def _transitions_relative_rise(g: np.ndarray, fps: float, cal: GripperCalibration) -> list[tuple[str, int]]:
    """(kind, frame) openings/closings from a rise relative to a frozen closed baseline.

    An opening starts when the measured value stays above the local closed baseline
    by more than max(open_rise_frac * span, noise_mult * closed-plateau noise) for
    persist_s. The baseline is only updated while the signal is settled near it, so
    gradual openings are not chased away. A closing requires a settled level in the
    lower close_band_frac of the span after a fall of at least the open threshold
    from the open peak (covers stalled-closed holds that never return to empty-closed).
    """
    g = _oriented(g, cal)
    lo, hi = float(np.min(g)), float(np.max(g))
    span = hi - lo
    if span <= 0 or len(g) < 3:
        return []
    noise = _closed_noise(g, span)
    open_thr = max(cal.open_rise_frac * span, cal.noise_mult * noise)
    track_thr = max(cal.settle_frac * span, cal.settle_noise_mult * noise)
    close_settle_thr = max(cal.close_settle_frac * span, cal.noise_mult * noise)
    close_band = lo + cal.close_band_frac * span
    baseline_n = max(1, int(round(cal.baseline_s * fps)))
    persist = max(1, int(round(cal.persist_s * fps)))
    if baseline_n >= len(g) or persist >= len(g):
        return []
    # Offline init: closed level from the episode's lower band (handles series that
    # begin already open). The scan itself only updates the baseline causally.
    lower = g[g <= lo + 0.2 * span]
    closed_baseline = float(np.median(lower)) if len(lower) else float(np.median(g[:baseline_n]))
    early = float(np.median(g[:baseline_n]))
    state = "open" if early - closed_baseline > open_thr else "closed"
    peak = float(np.max(g[: baseline_n + 1]))
    out: list[tuple[str, int]] = []
    f = baseline_n
    while f + max(persist, baseline_n) <= len(g):
        if state == "closed":
            window = g[f - baseline_n : f]
            w_med = float(np.median(window))
            w_std = float(np.std(window))
            if w_std <= track_thr and abs(w_med - closed_baseline) <= track_thr:
                closed_baseline = 0.8 * closed_baseline + 0.2 * w_med
            if all(float(g[k]) - closed_baseline > open_thr for k in range(f, f + persist)):
                out.append(("open", f))
                state = "open"
                peak = float(np.max(g[f : f + persist]))
                f += persist
                continue
        else:
            peak = max(peak, float(g[f]))
            window = g[f - baseline_n : f]
            w_med = float(np.median(window))
            w_std = float(np.std(window))
            if (
                w_std <= close_settle_thr
                and w_med <= close_band
                and (peak - w_med) > open_thr
                and all(peak - float(g[k]) > open_thr for k in range(f, f + persist))
            ):
                out.append(("close", f))
                state = "closed"
                closed_baseline = w_med
                f += persist
                continue
        f += 1
    return out


def _transitions(g: np.ndarray, fps: float, cal: GripperCalibration) -> list[tuple[str, int]]:
    """Dispatch to the calibrated opening detector (default: relative_rise)."""
    if cal.detector == "midpoint":
        return _transitions_midpoint(g, fps, cal)
    return _transitions_relative_rise(g, fps, cal)


def _region_at_rest(phase: _Phase) -> tuple[Region, list[int]]:
    regions = [o.region for o in phase.obs]
    for r in ("inside", "outside"):
        frames = [o.frame for o in phase.obs if o.region == r]
        if len(frames) >= max(2, len(regions) // 2 + 1):
            return r, frames
    return "unknown", []


# --- engine ----------------------------------------------------------------------

def localize_failures(
    task: TaskSpec,
    tracks: Sequence[ObjectTrack],
    *,
    fps: float,
    n_frames: int,
    gripper: GripperSignal | None = None,
    proximity: dict[str, set[int]] | None = None,
    params: FailureParams = FailureParams(),
) -> FailureReport:
    """proximity: per track id, frames with spatial evidence that the manipulator was at
    the object (e.g. object partly covered while at rest). Needed for failed-grasp claims."""
    p = params
    t = lambda f: round(f / fps, 3)  # noqa: E731
    events: list[PhysicalEvent] = []
    recoveries: list[RecoveryAttempt] = []
    outcomes: list[ObjectOutcome] = []
    notes: list[str] = []
    transitions = _transitions(gripper.measured, fps, gripper.calibration) if gripper is not None else []
    opens = [f for k, f in transitions if k == "open"]
    win = int(round(p.release_window_s * fps))
    if gripper is None:
        notes.append("No joint data: releases and grasps cannot be measured; conclusions are video-only.")
    elif not gripper.calibration.holding_detectable:
        notes.append(f"Gripper reading cannot show whether an object is held ({gripper.calibration.basis}); "
                     "joint data is used only for measured opening/closing.")

    for track in tracks:
        events_for_track: list[int] = []
        all_phases = track_phases(track, fps, p)
        # Failed grasp: measured close->open cycle at the object, object observed at rest
        # throughout and not moved by it. Requires joint data AND spatial proximity evidence.
        if gripper is not None and proximity and proximity.get(track.track_id):
            near = proximity[track.track_id]
            for k, (kind, cf) in enumerate(transitions):
                if kind != "close":
                    continue
                of = next((f for kk, f in transitions[k + 1:] if kk == "open"), None)
                if of is None or not any(cf - win <= f <= cf + win for f in near):
                    continue
                rest_phase = next((ph for run in all_phases for ph in run if ph.kind == "rest"
                                   and ph.first <= cf - win and ph.last >= of + win), None)
                if rest_phase is None:
                    continue
                ev = [
                    Evidence("proprio:observation.state[gripper]", "measurement", cf, of + 1,
                             f"measured gripper closed at frame {cf} and reopened at frame {of}",
                             [{"type": "gripper_close", "frame": cf}, {"type": "gripper_open", "frame": of}]),
                    Evidence(f"sam:{track.concept}", "detection", rest_phase.first, rest_phase.last + 1,
                             f"track {track.track_id} observed at rest from frame {rest_phase.first} to "
                             f"{rest_phase.last}, spanning the whole close/open cycle",
                             [{"type": "rest_span", "track_id": track.track_id, "frame_start": rest_phase.first,
                               "frame_end": rest_phase.last + 1}]),
                    Evidence("derived", "comparison", cf - win, cf + win + 1,
                             "spatial evidence that the manipulator was at the object near the closure",
                             [{"type": "proximity", "track_id": track.track_id,
                               "frames": sorted(f for f in near if cf - win <= f <= cf + win)}]),
                ]
                events.append(PhysicalEvent(
                    "failed_grasp", "closed_and_reopened_without_moving_object", "inferred", track.track_id,
                    cf, of + 1, t(cf), t(of + 1), ev,
                    "The gripper closed and reopened at the object while it stayed in place: consistent with a "
                    "failed grasp attempt.",
                    ["Whether the fingers touched the object is not measured.",
                     "A deliberate non-grasp (e.g. a nudge or a probe) would look similar."]))
                events_for_track.append(len(events) - 1)

        for run in all_phases:
            for a, m, b in zip(run, run[1:], run[2:]):
                if not (a.kind == "rest" and m.kind == "moving" and b.kind == "rest"):
                    continue
                start, end = a.obs[-1], b.obs[0]
                disp = float(np.hypot(end.x - start.x, end.y - start.y))
                if disp < p.moved_rel * max(start.size, 1.0):
                    continue
                end_region, end_frames = _region_at_rest(b)
                ev = [
                    Evidence(f"sam:{track.concept}", "detection", start.frame, end.frame + 1,
                             f"track {track.track_id} moved {disp:.0f}px ({disp / max(start.size, 1):.1f}x its size) "
                             f"from rest at frame {start.frame} to rest at frame {end.frame}",
                             [{"type": "displacement", "track_id": track.track_id, "from_frame": start.frame,
                               "to_frame": end.frame, "value_px": round(disp, 2)}]),
                    Evidence(f"sam:{track.concept}+target", "comparison", b.first, b.last + 1,
                             f"came to rest {end_region} the target ({len(end_frames)} of {len(b.obs)} rest observations)",
                             [{"type": "rest_region", "track_id": track.track_id, "region": end_region,
                               "frames": end_frames}]),
                ]
                # Recovery bookkeeping: a move after an earlier failure event of this track.
                prior = [i for i in events_for_track if events[i].frame_end <= start.frame + win]
                if prior:
                    outcome = {"inside": "succeeded", "outside": "failed"}.get(end_region, "unknown")
                    recoveries.append(RecoveryAttempt(prior[-1], track.track_id, outcome, start.frame,
                                                      end.frame + 1, "inferred" if outcome != "unknown" else "uncertain",
                                                      ev, [] if outcome != "unknown" else
                                                      ["End position relative to the target could not be determined."]))
                if end_region != "outside":
                    continue
                # Physical failure candidate: object moved, then came to rest outside the target.
                # Only openings after the move began can be a release (an opening before it is the approach).
                release = [f for f in opens if start.frame <= f <= end.frame + win]
                unc = ["Only 2D image positions are used; no depth."]
                if gripper is not None and release:
                    ev.append(Evidence("proprio:observation.state[gripper]", "measurement", release[0], release[0] + 1,
                                       f"measured gripper opened at frame {release[0]} ({t(release[0])}s), during or "
                                       f"just after the move", [{"type": "gripper_open", "frame": release[0]}]))
                    subtype, status = "released_outside_target", "inferred"
                    inference = ("The object was moved and came to rest outside the target, with a measured gripper "
                                 "opening during that move: consistent with it being dropped/released before reaching "
                                 "the target.")
                    unc.append("A measured gripper opening is not by itself proof of a drop; release is inferred "
                               "from the opening together with the object coming to rest outside the target, "
                               "and does not establish whether the opening was intended.")
                elif gripper is not None:
                    subtype, status = "no_measured_release", "inferred" if gripper.calibration.holding_detectable else "uncertain"
                    inference = ("The object came to rest outside the target without a measured gripper opening: "
                                 "consistent with slipping out of the grasp.") if status == "inferred" else None
                    if status == "uncertain":
                        unc.append("No measured opening, and this gripper cannot show holding: cause undetermined.")
                else:
                    subtype, status, inference = "cause_undetermined", "uncertain", None
                    unc.append("Video-only: a deliberate placement outside the target and a drop look the same.")
                events.append(PhysicalEvent("dropped_in_transport", subtype, status, track.track_id, start.frame,
                                            end.frame + 1, t(start.frame), t(end.frame + 1), ev, inference, unc))
                events_for_track.append(len(events) - 1)

        # Final outcome: the track's *last* phase must be a rest with >= 2 separated observations.
        # If the object was last seen moving, its final position is unobserved (not a failure).
        last_phase = all_phases[-1][-1] if all_phases and all_phases[-1] else None
        if last_phase is None or last_phase.kind != "rest":
            outcomes.append(ObjectOutcome(
                track.track_id, track.concept, "unknown", "uncertain",
                [], ["Object was last observed moving (or never at rest); its final position is not observed."]))
            continue
        region, frames = _region_at_rest(last_phase)
        span_ok = bool(frames) and (frames[-1] - frames[0]) >= p.final_min_span_s * fps
        tail_unobserved = n_frames - 1 - last_phase.last
        unc = []
        if tail_unobserved > p.max_gap_s * fps:
            # The object may still be moved later; a mid-episode state is not a final outcome.
            outcomes.append(ObjectOutcome(
                track.track_id, track.concept, "unknown", "uncertain", frames,
                [f"Last observation at frame {last_phase.last} (state there: {region}); frames "
                 f"{last_phase.last + 1}-{n_frames - 1} unobserved, so the final position is not established."]))
            continue
        if region == "unknown" or not span_ok:
            outcomes.append(ObjectOutcome(track.track_id, track.concept, "unknown", "uncertain", frames,
                                          unc + ["Final position relative to the target not established by >= 2 "
                                                 "separated observations."]))
        else:
            outcomes.append(ObjectOutcome(track.track_id, track.concept, region, "inferred", frames,
                                          unc + ["Based on discrete observations; later motion is not ruled out."]))

    # Task verdict.
    verdict: Verdict = "uncertain"
    failure_type = None
    by_concept: dict[str, list[ObjectOutcome]] = {}
    for o in outcomes:
        by_concept.setdefault(o.concept, []).append(o)
    failed_objs = [o for o in outcomes if o.final_region == "outside"]
    if failed_objs:
        verdict = "failure"
        dropped = {events[i].track_id for i in range(len(events)) if events[i].status == "inferred"
                   and not any(r.after_event == i and r.outcome == "succeeded" for r in recoveries)}
        failure_type = ("dropped_in_transport" if any(o.track_id in dropped for o in failed_objs)
                        else "incorrect_final_placement")
    else:
        complete = all(
            spec.count is None or sum(1 for o in by_concept.get(spec.concept, []) if o.final_region == "inside") >= spec.count
            for spec in task.objects)
        if outcomes and complete and all(o.final_region == "inside" for o in outcomes):
            verdict = "success"
        else:
            missing = [f"{spec.concept}: {sum(1 for o in by_concept.get(spec.concept, []) if o.final_region == 'inside')}"
                       f"/{spec.count if spec.count is not None else '?'} established inside"
                       for spec in task.objects]
            notes.append("Not every expected object has an established final position: " + "; ".join(missing) + ".")

    supported = [(i, e) for i, e in enumerate(events) if e.status == "inferred"]
    earliest = None
    if supported:
        i, e = min(supported, key=lambda x: x[1].frame_start)
        earliest = {"event_index": i, "kind": e.kind, "track_id": e.track_id, "frame_start": e.frame_start,
                    "frame_end": e.frame_end, "t_start": e.t_start, "t_end": e.t_end}
    return FailureReport(
        task_id=task.task_id, verdict=verdict, failure_type=failure_type, earliest_failure=earliest,
        physical_events=events, recoveries=recoveries, object_outcomes=outcomes, uncertainties=notes,
        inputs={"fps": fps, "n_frames": n_frames, "tracks": [tr.track_id for tr in tracks],
                "joint_data": gripper is not None,
                "gripper_calibration": asdict(gripper.calibration) if gripper is not None else None,
                "params": asdict(p)},
    )
