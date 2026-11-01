"""Conservative physical-event candidates from SAM tracks + SO-101 joint data.

Each event separates three things:
- evidence:      direct observations only (joint measurements, SAM detections or
                 their absence, local pixel measurements), each with machine-
                 checkable `claims` that verification.py recomputes from raw data.
- inference:     what the observations are taken to suggest (None for events that
                 are themselves measurements).
- uncertainties: what the evidence cannot rule out.

status:
- "observed":  the event is itself a measurement (the measured gripper joint moved).
- "inferred":  independent observations are consistent with the event, which is
               not itself measured (approach, grasp, co-movement, release, placement).
- "uncertain": evidence is missing or insufficient.

Rules this module never breaks:
- A missing detection is never treated as a physical event or failure.
- A commanded gripper position is never treated as a measured one.
- A stalled closure alone never makes a grasp; a full closure never proves "empty".
- Arm-joint motion coinciding with object motion is reported as coincidence, not as
  measured gripper-object co-motion (the gripper is not tracked in the image).
- 2D overlap of object and target is never reported as confirmed placement.
No API calls.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np

Status = Literal["observed", "inferred", "uncertain"]
GRIPPER_JOINT = "gripper.pos"


@dataclass(frozen=True)
class EventParams:
    # Gripper plateaus come from the episode's own measured range.
    gripper_mid_frac: float = 0.5  # open/closed boundary, fraction of measured range
    persist_frames: int = 5  # a crossing counts only if the new side holds this long
    settle_delta: float = 0.05  # |d gripper|/frame below this = settled
    # Measured short of the command by > this fraction of range = stall.
    # (Sample: settles 0.78 vs cmd ~0.5 when nothing is held; 6.44 vs ~0.5 on the tool.)
    stall_frac: float = 0.10
    arm_speed_window: int = 5  # frames; moving mean of sum |d joint| over arm joints
    arm_moving_speed: float = 0.5  # same (undeclared) units as the joint data
    rest_frames: int = 30  # first N detected frames define the object's rest pose
    rest_tolerance_px: float = 5.0
    occlusion_area_frac: float = 0.8  # visible mask area below this x rest = partly covered
    # Pixel change in a ring around the rest box (measured against the first rest frame).
    ring_margin_px: int = 60
    ring_pixel_delta: int = 25  # gray-level change counted as "changed"
    ring_change_frac: float = 0.05  # changed fraction of the ring that counts as intrusion
    moved_px: float = 40.0
    co_motion_frac: float = 0.7
    object_step_px: float = 2.0  # per-frame object motion counted as "moving"
    release_lookahead: int = 60
    final_window: int = 30  # fallback placement window when no release was found
    min_placement_span: int = 15  # placement needs detections at least this many frames apart
    contain_frac: float = 0.8  # 2D mask-in-target fraction for a placement *candidate*


@dataclass
class EvidenceRef:
    source: str  # proprio:<field>[<joint>] | sam:<concept> | video:pixels
    kind: str  # measurement | detection | absence | comparison
    frame_start: int
    frame_end: int  # exclusive
    summary: str
    claims: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Event:
    event_type: str
    status: Status
    frame_start: int
    frame_end: int  # exclusive
    t_start: float
    t_end: float
    evidence: list[EvidenceRef]
    inference: str | None = None
    uncertainties: list[str] = field(default_factory=list)


@dataclass
class ObjectSignal:
    """Per-frame object measurements (NaN / None where not detected)."""

    concept: str
    states: list[str]  # detected | not_detected | unknown
    x_center: np.ndarray
    bottom: np.ndarray
    area: np.ndarray
    track_ids: list[str | None]
    # frame -> container.assess_containment() result (interior fraction, reliability, raw
    # visible-mask fraction, ...); only frames where object and container were both detected.
    containment_detail: dict[int, dict[str, Any]] | None = None
    ring_change: np.ndarray | None = None  # changed fraction of the ring around rest box
    calibration_ref: dict[str, Any] | None = None  # {"file", "sha256", "calibration_frame"}

    def detected(self, f: int) -> bool:
        return self.states[f] == "detected"


@dataclass
class Timeline:
    fps: float
    n_frames: int
    events: list[Event]
    tracking_gaps: list[dict[str, Any]]
    params: EventParams
    sources: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fps": self.fps,
            "n_frames": self.n_frames,
            "events": [asdict(e) for e in self.events],
            "tracking_gaps": self.tracking_gaps,
            "params": asdict(self.params),
            "sources": self.sources,
        }


# --- signal helpers -------------------------------------------------------

def arm_speed(arm_state: np.ndarray, window: int) -> np.ndarray:
    step = np.r_[0.0, np.abs(np.diff(arm_state, axis=0)).sum(axis=1)]
    return np.convolve(step, np.ones(window) / window, mode="same")


def _runs(mask: Sequence[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


@dataclass
class GripperTransition:
    kind: Literal["open", "close"]
    crossing: int
    start: int
    end: int  # settle frame (inclusive)
    settled_value: float
    commanded_at_settle: float
    command_crossing: int | None
    stalled: bool


def gripper_transitions(g: np.ndarray, cmd: np.ndarray, p: EventParams) -> list[GripperTransition]:
    """Open/close transitions of the *measured* gripper; the command is only compared."""
    lo, hi = float(np.min(g)), float(np.max(g))
    span = hi - lo
    if span <= 0:
        return []
    mid = lo + p.gripper_mid_frac * span
    side = g > mid  # True = open side
    out: list[GripperTransition] = []
    current = bool(side[0])
    n = len(g)
    f = 1
    while f < n:
        if bool(side[f]) != current and all(bool(side[k]) != current for k in range(f, min(n, f + p.persist_frames))):
            new = bool(side[f])
            start = f
            while start > 0 and abs(g[start] - g[start - 1]) > p.settle_delta:
                start -= 1
            end = f
            while end + 3 < n and not all(abs(g[k + 1] - g[k]) <= p.settle_delta for k in range(end, end + 3)):
                end += 1
            settled, commanded = float(g[end]), float(cmd[end])
            cmd_side = cmd > mid
            cmd_cross = next(
                (k for k in range(max(1, start - 30), min(n, end + 1))
                 if bool(cmd_side[k]) == new and bool(cmd_side[k - 1]) != new),
                None,
            )
            stalled = (not new) and (settled - commanded) > p.stall_frac * span
            out.append(GripperTransition("open" if new else "close", f, start, end, settled, commanded, cmd_cross, stalled))
            current = new
            f = end + 1
            continue
        f += 1
    return out


# --- claim builders (verification.py recomputes each of these) --------------

def _joint_claim(field_name: str, frame: int, value: float) -> dict[str, Any]:
    return {"type": "joint_value", "field": field_name, "joint": GRIPPER_JOINT, "frame": int(frame), "value": round(float(value), 4)}


def _gripper_ev(g: np.ndarray, cmd: np.ndarray, a: int, b: int, summary: str) -> list[EvidenceRef]:
    return [
        EvidenceRef(f"proprio:observation.state[{GRIPPER_JOINT}]", "measurement", a, b + 1, summary,
                    [_joint_claim("observation.state", a, g[a]), _joint_claim("observation.state", b, g[b])]),
        EvidenceRef(f"proprio:action[{GRIPPER_JOINT}]", "comparison", a, b + 1,
                    f"command {cmd[a]:.2f} -> {cmd[b]:.2f} (a command is not a measurement)",
                    [_joint_claim("action", a, cmd[a]), _joint_claim("action", b, cmd[b])]),
    ]


def _detections_ev(obj: ObjectSignal, a: int, b: int, summary_prefix: str) -> EvidenceRef:
    frames = [f for f in range(max(0, a), min(len(obj.states), b)) if obj.detected(f)]
    ids = sorted({obj.track_ids[f] for f in frames if obj.track_ids[f]})
    return EvidenceRef(
        f"sam:{obj.concept}", "detection" if frames else "absence", a, b,
        f"{summary_prefix}: detected in {len(frames)}/{b - a} frames" + (f" (tracks {', '.join(ids)})" if ids else ""),
        [{"type": "detection_count", "concept": obj.concept, "frame_start": a, "frame_end": b,
          "count": len(frames), "track_ids": ids}],
    )


# --- timeline -------------------------------------------------------------

def build_timeline(
    *,
    gripper: np.ndarray,
    gripper_cmd: np.ndarray,
    arm_state: np.ndarray,
    obj: ObjectSignal,
    fps: float,
    params: EventParams = EventParams(),
    target_concept: str | None = None,
) -> Timeline:
    p = params
    n = len(gripper)
    t = lambda f: round(f / fps, 3)  # noqa: E731
    speed = arm_speed(arm_state, p.arm_speed_window)
    moving = speed > p.arm_moving_speed
    arm_src = "proprio:observation.state[arm joints]"
    sam = f"sam:{obj.concept}"
    events: list[Event] = []

    def arm_ev(a: int, b: int) -> EvidenceRef:
        frac = float(moving[a:b].mean()) if b > a else 0.0
        return EvidenceRef(arm_src, "measurement", a, b,
                           f"arm joints moving in {frac:.0%} of frames (speed > {p.arm_moving_speed})",
                           [{"type": "fraction_arm_moving", "frame_start": a, "frame_end": b, "value": round(frac, 4)}])

    det_frames = [f for f in range(n) if obj.detected(f)]
    rest = det_frames[: p.rest_frames]
    rest_x = float(np.median(obj.x_center[rest])) if rest else None
    rest_bottom = float(np.median(obj.bottom[rest])) if rest else None
    rest_area = float(np.median(obj.area[rest])) if rest else None

    def at_rest(f: int) -> bool:
        return (rest_x is not None and obj.detected(f)
                and abs(obj.x_center[f] - rest_x) <= p.rest_tolerance_px
                and abs(obj.bottom[f] - rest_bottom) <= p.rest_tolerance_px)

    # 1. Gripper open/close: measured joint motion.
    transitions = gripper_transitions(gripper, gripper_cmd, p)
    for tr in transitions:
        ev = _gripper_ev(gripper, gripper_cmd, tr.start, tr.end,
                         f"measured gripper {gripper[tr.start]:.2f} -> {tr.settled_value:.2f}")
        unc: list[str] = []
        if tr.kind == "close":
            gap = tr.settled_value - tr.commanded_at_settle
            ev.append(EvidenceRef(f"proprio:observation.state+action[{GRIPPER_JOINT}]", "comparison", tr.end, tr.end + 1,
                                  f"measured minus commanded at settle = {gap:.2f} (stall threshold "
                                  f"{p.stall_frac * (gripper.max() - gripper.min()):.2f})",
                                  [{"type": "closure_gap", "joint": GRIPPER_JOINT, "frame": tr.end,
                                    "value": round(gap, 4), "stalled": tr.stalled}]))
            if tr.stalled:
                unc.append("The fingers stopped short of the command: something blocked them. "
                           "This does not identify what, or whether it is held securely.")
            else:
                unc.append("Reaching the commanded level is consistent with nothing between the fingers, "
                           "but does not prove the gripper is empty (thin or compliant objects, sensor resolution).")
        events.append(Event(f"gripper_{tr.kind}", "observed", tr.start, tr.end + 1, t(tr.start), t(tr.end + 1), ev, None, unc))

    # 2-5 are anchored on stalled closures.
    for i, tr in enumerate(transitions):
        if tr.kind != "close" or not tr.stalled:
            continue
        prev_open = next((x for x in reversed(transitions[:i]) if x.kind == "open"), None)
        next_open = next((x for x in transitions[i + 1:] if x.kind == "open"), None)

        # 2. Approach: something enters the object's neighborhood and partly covers it while
        #    the object stays at rest and the arm joints move, before the closure.
        a0, a1 = (prev_open.end + 1 if prev_open else 0), tr.start
        if a1 > a0:
            ring_onset = None
            if obj.ring_change is not None:
                ring_onset = next((f for f in range(a0, a1 - p.persist_frames)
                                   if all(obj.ring_change[k] > p.ring_change_frac for k in range(f, f + p.persist_frames))),
                                  None)
            occl = next((f for f in range(a0, a1)
                         if at_rest(f) and rest_area and obj.area[f] < p.occlusion_area_frac * rest_area), None)
            seen = [f for f in range(a0, a1) if obj.detected(f)]
            all_rest = bool(seen) and all(at_rest(f) for f in seen)
            ev = [arm_ev(a0, a1), _detections_ev(obj, a0, a1, "object during approach window")]
            ev[-1].claims.append({"type": "object_at_rest", "concept": obj.concept, "frame_start": a0, "frame_end": a1,
                                  "value": all_rest, "rest_x": rest_x, "rest_bottom": rest_bottom,
                                  "tolerance_px": p.rest_tolerance_px})
            if ring_onset is not None:
                ev.append(EvidenceRef("video:pixels", "measurement", ring_onset, ring_onset + p.persist_frames,
                                      f"{obj.ring_change[ring_onset]:.0%} of the {p.ring_margin_px}px ring around the "
                                      f"object's rest box changed vs the first rest frame",
                                      [{"type": "ring_change", "concept": obj.concept, "frame": ring_onset,
                                        "value": round(float(obj.ring_change[ring_onset]), 4)}]))
            if occl is not None:
                ev.append(EvidenceRef(sam, "detection", occl, occl + 1,
                                      f"visible mask area {obj.area[occl]:.0f}px < {p.occlusion_area_frac:.0%} of rest "
                                      f"{rest_area:.0f}px while the object stayed at rest",
                                      [{"type": "mask_area", "concept": obj.concept, "track_id": obj.track_ids[occl],
                                        "frame": occl, "value": float(obj.area[occl])}]))
            frac_moving = float(moving[a0:a1].mean())
            ok = frac_moving >= 0.3 and ring_onset is not None and occl is not None and all_rest
            start = ring_onset if ring_onset is not None else a0
            events.append(Event(
                "approach_candidate", "inferred" if ok else "uncertain", start, a1, t(start), t(a1), ev,
                "Something entered the object's image neighborhood and then partly covered it while the object "
                "stayed in place and the arm joints were moving, ending in a gripper closure. Consistent with the "
                "gripper approaching the object." if ok else None,
                ["The gripper is not identified in the image; the intruding region is attributed to the robot "
                 "because the arm joints were moving at the same time."]
                + ([] if ok else ["Required spatial evidence (neighborhood change + partial covering at rest) is incomplete."]),
            ))

        # Held interval: from settle of the stalled closure to the next measured opening.
        h0, h1 = tr.end + 1, (next_open.start if next_open else n)
        held = [f for f in range(h0, h1) if obj.detected(f)]
        cm: Event | None = None
        if held:
            tid = obj.track_ids[held[0]]
            x0, b0 = obj.x_center[held[0]], obj.bottom[held[0]]
            disp = float(np.max(np.hypot(obj.x_center[held] - x0, obj.bottom[held] - b0)))
            steps = [f for a, f in zip(held, held[1:]) if f == a + 1
                     and np.hypot(obj.x_center[f] - obj.x_center[a], obj.bottom[f] - obj.bottom[a]) > p.object_step_px]
            co = float(np.mean([moving[f] for f in steps])) if steps else None
            last = held[-1]
            ev = [
                EvidenceRef(sam, "detection", held[0], last + 1,
                            f"object (track {tid}) displaced up to {disp:.0f}px in the image",
                            [{"type": "max_displacement_px", "concept": obj.concept, "track_id": tid,
                              "frame_start": held[0], "frame_end": last + 1, "value": round(disp, 2)}]),
                arm_ev(held[0], last + 1),
                EvidenceRef("sam+proprio", "comparison", held[0], last + 1,
                            (f"arm joints were moving in {co:.0%} of the frames where the object moved"
                             if co is not None else "the object never moved frame-to-frame"),
                            [{"type": "co_motion_fraction", "concept": obj.concept, "frame_start": held[0],
                              "frame_end": last + 1, "value": None if co is None else round(co, 4)}]),
                EvidenceRef(f"proprio:observation.state[{GRIPPER_JOINT}]", "measurement", h0, h1,
                            f"measured gripper stayed between {gripper[h0:h1].min():.2f} and {gripper[h0:h1].max():.2f}",
                            [{"type": "joint_range", "field": "observation.state", "joint": GRIPPER_JOINT,
                              "frame_start": h0, "frame_end": h1,
                              "min": round(float(gripper[h0:h1].min()), 4), "max": round(float(gripper[h0:h1].max()), 4)}]),
            ]
            unc = ["This is temporal coincidence of object image motion and arm joint motion, not measured "
                   "gripper-object co-motion: the gripper is not tracked in the image."]
            if last + 1 < h1:
                unc.append(f"Object detections end at frame {last} while the gripper stays closed until frame {h1}; "
                           f"frames {last + 1}-{h1 - 1} carry no object evidence (not interpreted).")
            ok = disp >= p.moved_px and co is not None and co >= p.co_motion_frac
            cm = Event("coordinated_movement_candidate", "inferred" if ok else "uncertain", held[0], last + 1,
                       t(held[0]), t(last + 1), ev,
                       "The object moved substantially while the arm moved and the gripper stayed stalled-closed; "
                       "consistent with the object moving with the gripper." if ok else None, unc)

        # 3. Grasp: needs the stall AND the object at the closure AND subsequent co-movement.
        near = _detections_ev(obj, max(0, tr.start - 10), min(n, tr.end + 11), "object around the closure")
        ev = _gripper_ev(gripper, gripper_cmd, tr.start, tr.end, f"measured closure stopped at {tr.settled_value:.2f}")
        ev.append(near)
        if cm is not None:
            ev.append(EvidenceRef("event:coordinated_movement_candidate", "comparison", cm.frame_start, cm.frame_end,
                                  f"followed by coordinated_movement_candidate ({cm.status})",
                                  [{"type": "event_ref", "event_type": cm.event_type, "status": cm.status,
                                    "frame_start": cm.frame_start}]))
        ok = near.kind == "detection" and cm is not None and cm.status == "inferred"
        events.append(Event(
            "grasp_candidate", "inferred" if ok else "uncertain", tr.start, tr.end + 1, t(tr.start), t(tr.end + 1), ev,
            "The fingers stopped short of the command with the object present, and the object then moved with the "
            "arm; consistent with the object being held." if ok else None,
            ["A stalled closure only shows something blocked the fingers; grip security and slip are not measured."]
            + ([] if ok else ["Insufficient independent evidence to infer a grasp."]),
        ))
        if cm is not None:
            events.append(cm)

        # 5. Release: measured opening after the stalled hold.
        if next_open is not None:
            r0, r1 = next_open.start, next_open.end + 1
            look = (r1, min(n, r1 + p.release_lookahead))
            after = [f for f in range(*look) if obj.detected(f)]
            ev = _gripper_ev(gripper, gripper_cmd, next_open.start, next_open.end,
                             f"measured gripper opened {gripper[r0]:.2f} -> {next_open.settled_value:.2f}")
            ev.append(_detections_ev(obj, look[0], look[1], "object after opening"))
            ok = False
            if len(after) >= 2:
                still = float(np.ptp(obj.x_center[after])) <= p.rest_tolerance_px
                ok = still and float(moving[look[0]:look[1]].mean()) >= 0.3
                if ok:
                    ev.append(arm_ev(*look))
            events.append(Event(
                "release_candidate", "inferred" if ok else "uncertain", r0, r1, t(r0), t(r1), ev,
                "The object stayed still after the measured opening while the arm moved away." if ok else None,
                ["The gripper opening is measured; the object leaving the gripper is not."]
                + ([] if ok else ["No object observations after the opening to support a release."]),
            ))

    # 6. Final placement: post-release detections inside the *estimated container interior*.
    last_release = next((e for e in reversed(events) if e.event_type == "release_candidate"), None)
    w0 = last_release.frame_end if last_release else max(0, n - p.final_window)
    final = [f for f in range(w0, n) if obj.detected(f)]
    ev = [_detections_ev(obj, w0, n, "object after the last release")]
    counts = {s: obj.states[w0:n].count(s) for s in ("detected", "not_detected", "unknown")}
    ev[0].claims.append({"type": "frame_states", "concept": obj.concept, "frame_start": w0, "frame_end": n, "counts": counts})
    unc = ["Containment is measured in the 2D image plane only (no depth)."]
    held_intervals = [(tr.end + 1, next((x.start for x in transitions[k + 1:] if x.kind == "open"), n))
                      for k, tr in enumerate(transitions) if tr.kind == "close" and tr.stalled]
    ok = False
    inside: list[int] = []
    detail = obj.containment_detail or {}
    if final and target_concept and obj.calibration_ref:
        cal = obj.calibration_ref
        claims = []
        for f in final:
            d = detail.get(f)
            claims.append({"type": "interior_containment", "concept": obj.concept, "target": target_concept,
                           "frame": f, "track_id": obj.track_ids[f], "calibration_sha256": cal["sha256"],
                           **({k: d[k] for k in ("interior_fraction", "reliable", "footprint_iou",
                                                  "polygon_in_footprint", "raw_mask_fraction", "footprint_fraction")}
                              if d else {"interior_fraction": None, "reliable": False}),
                           "reason": (d or {}).get("reason", "container not detected on this frame")})
        summary = "; ".join(
            f"f{c['frame']}: {c['interior_fraction'] if c['interior_fraction'] is not None else 'n/a'} inside interior"
            f"{'' if c['reliable'] else ' (unreliable: ' + str(c['reason']) + ')'}" for c in claims)
        ev.append(EvidenceRef(f"sam:{obj.concept}+sam:{target_concept}+calibration:{cal['file']}", "comparison",
                              final[0], final[-1] + 1,
                              f"fraction of {obj.concept} mask inside the estimated {target_concept} interior: {summary}",
                              claims))
        unreliable = [c["frame"] for c in claims if not c["reliable"]]
        inside = [c["frame"] for c in claims if c["reliable"] and c["interior_fraction"] >= p.contain_frac]
        outside = [c["frame"] for c in claims if c["reliable"] and c["interior_fraction"] < p.contain_frac]
        held = [f for f in final if any(a <= f < b for a, b in held_intervals)]
        span = inside[-1] - inside[0] if inside else 0
        if unreliable:
            unc.append(f"Container interior could not be estimated reliably at frames {unreliable}.")
        if outside:
            unc.append(f"{obj.concept} mostly outside the estimated interior at frames {outside}.")
        if held:
            unc.append(f"Frames {held} fall inside a stalled-closure (holding) interval.")
        if len(inside) < 2 or span < p.min_placement_span:
            unc.append(f"{len(inside)} reliable inside-interior detection(s) spanning {span} frames after release; "
                       f"placement needs >= 2 at least {p.min_placement_span} frames apart.")
        ok = (len(inside) >= 2 and span >= p.min_placement_span and not unreliable and not outside and not held)
        if ok:
            unc.append(f"Only {len(inside)} discrete observations (frames {inside}); whether the object stayed in "
                       "place between or after them is not observed.")
            ids = sorted({obj.track_ids[f] for f in inside if obj.track_ids[f]})
            if len(ids) > 1:
                unc.append(f"The observations are separate tracks {ids}; identity across them is assumed "
                           "from appearance and location, not tracked.")
        unc.append(f"Interior polygon is a calibration from frame {cal['calibration_frame']} (empty container, fixed "
                   "camera); it is only used where the container footprint matches the calibration.")
    elif not final:
        unc.append("No object detections after the last release, so placement cannot be assessed from tracking.")
    else:
        unc.append("No container interior estimate available; placement cannot be assessed.")
    inference = None
    if ok:
        times = ", ".join(f"{f / fps:.2f}s" for f in inside)
        inference = (f"The {obj.concept} was detected inside the estimated {target_concept} interior at {len(inside)} "
                     f"separate post-release frames ({times}); consistent with it having been placed in the container.")
    events.append(Event("final_placement_candidate", "inferred" if ok else "uncertain", w0, n, t(w0), t(n), ev,
                        inference, unc))

    events.sort(key=lambda e: (e.frame_start, e.frame_end))
    gaps = [{"concept": obj.concept, "state": s, "frame_start": a, "frame_end": b, "t_start": t(a), "t_end": t(b)}
            for s in ("not_detected", "unknown") for a, b in _runs([x == s for x in obj.states])]
    gaps.sort(key=lambda g: g["frame_start"])
    return Timeline(fps, n, events, gaps, p)


# --- adapter: real tracking + proprio ---------------------------------------

def ring_change_series(video_bytes: bytes, rest_box: Sequence[float], ref_frame: int, p: EventParams) -> np.ndarray:
    """Changed fraction of a ring around rest_box vs ref_frame, per frame (gray levels)."""
    import av

    x1, y1, x2, y2 = (int(round(v)) for v in rest_box)
    m = p.ring_margin_px
    out: list[float] = []
    frames: list[np.ndarray] = []
    with av.open(io.BytesIO(video_bytes)) as c:
        for f in c.decode(video=0):
            g = f.to_ndarray(format="gray")
            h, w = g.shape
            X1, Y1, X2, Y2 = max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)
            frames.append(g[Y1:Y2, X1:X2].astype(np.int16))
    ring = np.ones_like(frames[0], dtype=bool)
    ix1, iy1 = x1 - max(0, x1 - m), y1 - max(0, y1 - m)
    ring[iy1:iy1 + (y2 - y1), ix1:ix1 + (x2 - x1)] = False
    ref = frames[ref_frame]
    for g in frames:
        out.append(float((np.abs(g - ref)[ring] > p.ring_pixel_delta).mean()))
    return np.array(out)


def object_signal(tracking_result: Any, concept: str, n_frames: int, frame_shape: tuple[int, int],
                  target_concept: str | None = None, extra_observations: Sequence[Any] = (),
                  calibration: Any | None = None, calibration_path: Path | None = None) -> ObjectSignal:
    """Per-frame signals. extra_observations (e.g. keyframe probes) keep their own track ids
    and only mark their own frames detected; they are not stitched to other tracks.
    Containment uses container.py's calibrated interior, never the raw container mask."""
    import container as C
    from tracking import decode_mask_rle, frame_states_for, mask_in_frame

    states = list(frame_states_for(tracking_result, concept))
    x = np.full(n_frames, np.nan)
    bottom = np.full(n_frames, np.nan)
    area = np.full(n_frames, np.nan)
    ids: list[str | None] = [None] * n_frames
    best: dict[int, Any] = {}
    targets: dict[int, Any] = {}
    for o in list(tracking_result.observations) + list(extra_observations):
        if o.frame_index is None or not (0 <= o.frame_index < n_frames) or o.bbox is None:
            continue
        pool = best if o.concept == concept else targets if o.concept == target_concept else None
        if pool is None:
            continue
        cur = pool.get(o.frame_index)
        if cur is None or (o.confidence or 0) > (cur.confidence or 0):
            pool[o.frame_index] = o
    cal_footprint = None
    if calibration is not None and calibration.calibration_frame in targets:
        t0 = targets[calibration.calibration_frame]
        cal_footprint = C.fill_holes(mask_in_frame(t0.mask_rle, t0.bbox, frame_shape))
    detail: dict[int, dict[str, Any]] = {}
    for f, o in best.items():
        states[f] = "detected"
        ids[f] = o.object_id
        x[f] = (o.bbox[0] + o.bbox[2]) / 2
        bottom[f] = o.bbox[3]
        area[f] = float(decode_mask_rle(o.mask_rle).sum()) if o.mask_rle else np.nan
        if target_concept and o.mask_rle:
            om = mask_in_frame(o.mask_rle, o.bbox, frame_shape)
            tm = mask_in_frame(targets[f].mask_rle, targets[f].bbox, frame_shape) if f in targets and targets[f].mask_rle else None
            if om is not None:
                detail[f] = C.assess_containment(om, tm, calibration, cal_footprint)
    cal_ref = None
    if calibration is not None:
        cal_ref = {"file": (calibration_path.name if calibration_path else "calibration"),
                   "sha256": calibration.sha256(), "calibration_frame": calibration.calibration_frame}
    return ObjectSignal(concept, states, x, bottom, area, ids, detail if target_concept else None,
                        calibration_ref=cal_ref)


@dataclass
class SampleInputs:
    """Everything timeline_for_sample used, for display and verification."""

    video_bytes: bytes
    tracking: Any
    proprio: Any
    probes: list[Any]
    calibration: Any | None = None
    calibration_path: Path | None = None


def load_sample_inputs(
    video_path: Path = Path(__file__).parent / "sample_videos" / "sample.mp4",
    *,
    object_concept: str = "screwdriver",
    target_concept: str = "white box",
) -> SampleInputs:
    import hashlib

    import container
    import proprio
    from tracking import assemble_from_chunk_cache, load_probe_observations

    video = video_path.read_bytes()
    tr = assemble_from_chunk_cache(video, [object_concept, target_concept])
    cal, cal_path = None, None
    if container.SAMPLE_CALIBRATION.is_file():
        cal_path = container.SAMPLE_CALIBRATION
        cal = container.InteriorCalibration.load(cal_path)
        if cal.video_sha256 != hashlib.sha256(video).hexdigest() or cal.concept != target_concept:
            cal, cal_path = None, None  # calibration belongs to a different video/container
    return SampleInputs(video, tr, proprio.load_episode(), load_probe_observations(video, object_concept),
                        cal, cal_path)


def timeline_from_inputs(
    inputs: SampleInputs,
    *,
    object_concept: str = "screwdriver",
    target_concept: str = "white box",
    params: EventParams = EventParams(),
) -> Timeline:
    import proprio
    from tracking import probe_video_size

    tr, ep = inputs.tracking, inputs.proprio
    n = tr.diagnostics.frames_in_source
    problems = proprio.check_video_alignment(ep, video_frames=n, video_fps=tr.fps)
    if problems:
        raise ValueError(f"Joint data not aligned with video: {problems}")
    w, h = probe_video_size(inputs.video_bytes)
    obj = object_signal(tr, object_concept, n, (h, w), target_concept, inputs.probes,
                        calibration=inputs.calibration, calibration_path=inputs.calibration_path)
    rest = [f for f in range(n) if obj.detected(f)][: params.rest_frames]
    if rest:
        boxes = np.array([[o.bbox for o in tr.observations if o.concept == object_concept and o.frame_index == f][0]
                          for f in rest])
        obj.ring_change = ring_change_series(inputs.video_bytes, np.median(boxes, axis=0), rest[0], params)
    grip = ep.joint_names.index(GRIPPER_JOINT)
    arm = [i for i in range(len(ep.joint_names)) if i != grip]
    timeline = build_timeline(gripper=ep.state[:, grip], gripper_cmd=ep.action[:, grip], arm_state=ep.state[:, arm],
                              obj=obj, fps=ep.fps, params=params, target_concept=target_concept)
    timeline.sources = {
        "tracking": "per-chunk SAM cache (assemble_from_chunk_cache)",
        "probes": [{"object_id": o.object_id, "frame_index": o.frame_index} for o in inputs.probes],
        "proprio": ep.source,
        "arm_joints": [ep.joint_names[i] for i in arm],
        "tracking_calls": [{k: c[k] for k in ("chunk_index", "concept", "prompt_mode", "status", "n_observations")}
                           for c in tr.chunk_log["calls"]],
    }
    return timeline


def timeline_for_sample(**kwargs: Any) -> Timeline:
    return timeline_from_inputs(load_sample_inputs(), **kwargs)


if __name__ == "__main__":
    tl = timeline_for_sample()
    out = Path(__file__).parent / "data" / "events" / "sample_timeline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tl.to_dict(), indent=2, default=float), encoding="utf-8")
    for e in tl.events:
        print(f"{e.t_start:6.2f}-{e.t_end:6.2f}s  f{e.frame_start}-{e.frame_end}  {e.event_type:<32} {e.status}")
        for r in e.evidence:
            print(f"      [{r.kind}] {r.source} f{r.frame_start}-{r.frame_end}: {r.summary}")
        if e.inference:
            print(f"      inference: {e.inference}")
        for u in e.uncertainties:
            print(f"      uncertainty: {u}")
    print("tracking gaps:", [(g["state"], g["frame_start"], g["frame_end"]) for g in tl.tracking_gaps])
    print(f"wrote {out}")
