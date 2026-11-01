"""Deterministic verification of an event timeline against raw evidence.

The verifier takes a timeline *as data* (Timeline.to_dict(), possibly edited or
written by something else) and independently recomputes every structured claim
from the raw sources: SAM observations (+ keyframe probes), LeRobot joint data,
and, for pixel claims, the video. It does not call events.py's rule code, so it
can disagree with the reconstruction.

Findings are "error" (claim contradicted / unsupported) or "warning" (claim
cannot be checked). An event is "supported" only if every claim it cites checks
out and its status is justified by those claims.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

VALUE_TOL = 1e-3
PX_TOL = 0.5
# Interior geometry is recomputed with a different rasterization (ray casting at pixel
# coordinates vs. cv2.fillPoly), so boundary pixels may differ slightly.
GEOM_TOL = 0.02
# The verifier's own reliability criteria for an interior estimate.
MIN_FOOTPRINT_IOU = 0.95
MIN_POLYGON_IN_FOOTPRINT = 0.99
CONTINUITY_WORDS = re.compile(r"\b(stayed|remained|stable|stably|continuous(ly)?|throughout|the whole time)\b", re.I)
CALIBRATION_DIR = __import__("pathlib").Path(__file__).parent / "data" / "calibration"
KINDS = {"measurement", "detection", "absence", "comparison"}
STATUSES = {"observed", "inferred", "uncertain"}
MEASURED_EVENTS = {"gripper_open", "gripper_close"}  # the only events that may be "observed"
CANDIDATE_EVENTS = {
    "approach_candidate", "grasp_candidate", "coordinated_movement_candidate",
    "release_candidate", "final_placement_candidate",
}


@dataclass
class Finding:
    event_index: int | None
    event_type: str | None
    check: str
    severity: str  # error | warning
    message: str


@dataclass
class VerificationReport:
    findings: list[Finding] = field(default_factory=list)
    event_verdicts: dict[int, str] = field(default_factory=dict)
    claims_checked: int = 0
    claims_failed: int = 0
    claims_unverifiable: int = 0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [asdict(f) for f in self.findings],
            "event_verdicts": self.event_verdicts,
            "claims_checked": self.claims_checked,
            "claims_failed": self.claims_failed,
            "claims_unverifiable": self.claims_unverifiable,
        }


class _Sources:
    """Raw data access, independent of events.py."""

    def __init__(self, tracking: Any, proprio: Any, probes: Sequence[Any], video_bytes: bytes | None):
        self.tracking = tracking
        self.proprio = proprio
        self.video_bytes = video_bytes
        self.n = int(tracking.diagnostics.frames_in_source)
        self.fps = float(proprio.fps)
        self.joints = list(proprio.joint_names)
        self.concepts = set(tracking.concepts)
        self.obs = [o for o in list(tracking.observations) + list(probes)
                    if o.frame_index is not None and o.bbox is not None]
        self.track_ids = {o.object_id for o in self.obs}
        self.by_concept_frame: dict[tuple[str, int], list[Any]] = {}
        for o in self.obs:
            self.by_concept_frame.setdefault((o.concept, o.frame_index), []).append(o)
        self.probe_frames = {(o.concept, o.frame_index) for o in probes}
        self._frames_gray: list[np.ndarray] | None = None

    def joint(self, field_name: str, joint: str) -> np.ndarray | None:
        if joint not in self.joints:
            return None
        arr = {"observation.state": self.proprio.state, "action": self.proprio.action}.get(field_name)
        return None if arr is None else arr[:, self.joints.index(joint)]

    def best(self, concept: str, frame: int) -> Any | None:
        items = self.by_concept_frame.get((concept, frame)) or []
        return max(items, key=lambda o: o.confidence or 0.0) if items else None

    def detected_frames(self, concept: str, a: int, b: int) -> list[int]:
        return [f for f in range(max(0, a), min(self.n, b)) if (concept, f) in self.by_concept_frame]

    def gray(self) -> list[np.ndarray] | None:
        if self.video_bytes is None:
            return None
        if self._frames_gray is None:
            import av

            with av.open(io.BytesIO(self.video_bytes)) as c:
                self._frames_gray = [f.to_ndarray(format="gray").astype(np.int16) for f in c.decode(video=0)]
        return self._frames_gray


def _arm_moving(src: _Sources, params: dict[str, Any]) -> np.ndarray | None:
    if "gripper.pos" not in src.joints:
        return None
    arm = [i for i in range(len(src.joints)) if src.joints[i] != "gripper.pos"]
    x = src.proprio.state[:, arm]
    step = np.concatenate([[0.0], np.abs(x[1:] - x[:-1]).sum(axis=1)])
    w = int(params["arm_speed_window"])
    speed = np.convolve(step, np.full(w, 1.0 / w), mode="same")
    return speed > float(params["arm_moving_speed"])


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def _rest_pose(src: _Sources, concept: str, k: int) -> tuple[float, float, list[float], int] | None:
    frames = [f for f in range(src.n) if (concept, f) in src.by_concept_frame][:k]
    if not frames:
        return None
    boxes = np.array([src.best(concept, f).bbox for f in frames])
    xs = (boxes[:, 0] + boxes[:, 2]) / 2
    return float(np.median(xs)), float(np.median(boxes[:, 3])), list(np.median(boxes, axis=0)), frames[0]


def _holes_filled_cc(mask: np.ndarray) -> np.ndarray:
    """Hole filling via connected components of the background (independent of container.py)."""
    import cv2

    n, labels = cv2.connectedComponents((~mask).astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    holes = np.isin(labels, [k for k in range(1, n) if k not in border])
    return mask | holes


def _inside_polygon(xs: np.ndarray, ys: np.ndarray, polygon: Sequence[Sequence[float]]) -> np.ndarray:
    """Ray-casting point-in-polygon on integer pixel coordinates (vertices rounded)."""
    poly = np.round(np.asarray(polygon, float))
    inside = np.zeros(xs.shape, dtype=bool)
    for (x1, y1), (x2, y2) in zip(poly, np.roll(poly, -1, axis=0)):
        crosses = (y1 > ys) != (y2 > ys)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        inside ^= crosses & (xs < x_at)
    return inside  # boundary pixels may differ from cv2.fillPoly; covered by GEOM_TOL


def _load_calibration(name: str) -> tuple[dict[str, Any], str] | None:
    import hashlib
    import json

    path = CALIBRATION_DIR / name
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _check_interior_claim(claim: dict[str, Any], src: _Sources, calibration_name: str | None) -> tuple[bool | None, str]:
    import hashlib

    from tracking import mask_in_frame

    if not calibration_name:
        return False, "interior containment cited without a calibration source"
    loaded = _load_calibration(calibration_name)
    if loaded is None:
        return False, f"calibration {calibration_name!r} missing"
    cal, sha = loaded
    if claim.get("calibration_sha256") != sha:
        return False, "calibration file changed since the claim was made (sha256 mismatch)"
    if src.video_bytes is not None and cal.get("video_sha256") != hashlib.sha256(src.video_bytes).hexdigest():
        return False, "calibration belongs to a different video"
    concept, target, f = claim.get("concept"), claim.get("target"), claim.get("frame")
    if target != cal.get("concept"):
        return False, f"calibration is for {cal.get('concept')!r}, claim targets {target!r}"
    shape = src.gray()[0].shape if src.gray() else (720, 1280)
    obj = next((o for o in src.by_concept_frame.get((concept, f), []) if o.object_id == claim.get("track_id")), None)
    if obj is None or not obj.mask_rle:
        return False, f"no {concept} mask for track {claim.get('track_id')} at frame {f}"
    om = mask_in_frame(obj.mask_rle, obj.bbox, shape)
    ys, xs = np.nonzero(om)
    poly = cal["polygon"]
    frac = float(_inside_polygon(xs, ys, poly).mean()) if len(xs) else 0.0
    box, box0 = src.best(target, f), src.best(target, int(cal["calibration_frame"]))
    if box is None or box0 is None:
        reliable_now, msg = False, "container not detected"
        if claim.get("reliable"):
            return False, f"claimed reliable but {msg} at frame {f} or calibration frame"
        return True, f"unreliable as claimed ({msg})"
    # Pixels covered by the measured object are excluded from the reliability checks
    # (they cannot show whether the container moved); other occluders still count.
    visible = ~om
    fp = _holes_filled_cc(mask_in_frame(box.mask_rle, box.bbox, shape)) & visible
    fp0 = _holes_filled_cc(mask_in_frame(box0.mask_rle, box0.bbox, shape)) & visible
    union = (fp | fp0).sum()
    fiou = float((fp & fp0).sum() / union) if union else 0.0
    py0, py1 = int(np.floor(min(p[1] for p in poly))), int(np.ceil(max(p[1] for p in poly)))
    px0, px1 = int(np.floor(min(p[0] for p in poly))), int(np.ceil(max(p[0] for p in poly)))
    gy, gx = np.mgrid[py0:py1 + 1, px0:px1 + 1]
    pin = _inside_polygon(gx, gy, poly) & visible[gy, gx]
    pin_fp = float(fp[gy[pin], gx[pin]].mean()) if pin.any() else 0.0
    reliable = fiou >= MIN_FOOTPRINT_IOU and pin_fp >= MIN_POLYGON_IN_FOOTPRINT
    problems = []
    if claim.get("interior_fraction") is None or abs(frac - float(claim["interior_fraction"])) > GEOM_TOL:
        problems.append(f"interior fraction {frac:.3f} vs claimed {claim.get('interior_fraction')}")
    if claim.get("footprint_iou") is not None and abs(fiou - float(claim["footprint_iou"])) > 0.005:
        problems.append(f"footprint IoU {fiou:.4f} vs claimed {claim['footprint_iou']}")
    if claim.get("polygon_in_footprint") is not None and abs(pin_fp - float(claim["polygon_in_footprint"])) > GEOM_TOL:
        problems.append(f"polygon-in-footprint {pin_fp:.3f} vs claimed {claim['polygon_in_footprint']}")
    if bool(claim.get("reliable")) != reliable:
        problems.append(f"reliability {reliable} (IoU {fiou:.3f}, polygon-in-footprint {pin_fp:.3f}) vs claimed {claim.get('reliable')}")
    if problems:
        return False, "; ".join(problems)
    return True, f"interior fraction {frac:.3f}, footprint IoU {fiou:.3f}, polygon-in-footprint {pin_fp:.3f}"


def _check_claim(claim: dict[str, Any], src: _Sources, timeline: dict[str, Any]) -> tuple[bool | None, str]:
    """(True=verified, False=contradicted, None=unverifiable, message)."""
    from tracking import decode_mask_rle, mask_in_frame

    p = timeline.get("params") or {}
    ctype = claim.get("type")
    in_range = lambda f: isinstance(f, int) and 0 <= f < src.n  # noqa: E731

    if ctype in ("joint_value", "closure_gap"):
        frame = claim.get("frame")
        if not in_range(frame):
            return False, f"frame {frame} outside 0..{src.n - 1}"
        if ctype == "joint_value":
            series = src.joint(claim.get("field", ""), claim.get("joint", ""))
            if series is None:
                return False, f"no joint data for {claim.get('field')}[{claim.get('joint')}]"
            actual = float(series[frame])
            ok = _close(actual, claim.get("value"), VALUE_TOL)
            return ok, f"{claim.get('field')}[{claim.get('joint')}] at frame {frame} is {actual:.4f}, claimed {claim.get('value')}"
        state, action = src.joint("observation.state", claim["joint"]), src.joint("action", claim["joint"])
        if state is None or action is None:
            return False, f"no joint data for {claim.get('joint')}"
        gap = float(state[frame] - action[frame])
        threshold = float(p.get("stall_frac", 0.1)) * float(state.max() - state.min())
        if not _close(gap, claim.get("value"), VALUE_TOL):
            return False, f"measured-minus-commanded at {frame} is {gap:.4f}, claimed {claim.get('value')}"
        if bool(claim.get("stalled")) != (gap > threshold):
            return False, f"stalled={claim.get('stalled')} but gap {gap:.2f} vs threshold {threshold:.2f}"
        return True, f"gap {gap:.2f}, stalled={gap > threshold}"

    if ctype == "joint_range":
        a, b = claim.get("frame_start"), claim.get("frame_end")
        series = src.joint(claim.get("field", ""), claim.get("joint", ""))
        if series is None or not (in_range(a) and isinstance(b, int) and a < b <= src.n):
            return False, "bad joint or frame range"
        lo, hi = float(series[a:b].min()), float(series[a:b].max())
        ok = _close(lo, claim.get("min"), VALUE_TOL) and _close(hi, claim.get("max"), VALUE_TOL)
        return ok, f"range {lo:.4f}-{hi:.4f}, claimed {claim.get('min')}-{claim.get('max')}"

    if ctype == "fraction_arm_moving":
        a, b = claim.get("frame_start"), claim.get("frame_end")
        moving = _arm_moving(src, p)
        if moving is None or not (isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= src.n):
            return False, "bad frame range or no arm joints"
        frac = float(moving[a:b].mean())
        return _close(frac, claim.get("value"), VALUE_TOL), f"arm moving fraction {frac:.4f}, claimed {claim.get('value')}"

    if ctype == "detection_count":
        concept, a, b = claim.get("concept"), claim.get("frame_start"), claim.get("frame_end")
        if concept not in src.concepts:
            return False, f"unknown concept {concept!r}"
        frames = src.detected_frames(concept, a, b)
        ids_present = {o.object_id for f in frames for o in src.by_concept_frame[(concept, f)]}
        claimed_ids = set(claim.get("track_ids") or [])
        unknown = claimed_ids - src.track_ids
        if unknown:
            return False, f"track ids {sorted(unknown)} do not exist"
        if not claimed_ids <= ids_present:
            return False, f"track ids {sorted(claimed_ids - ids_present)} have no detections in {a}-{b}"
        ok = len(frames) == claim.get("count")
        return ok, f"{len(frames)} detected frames in {a}-{b}, claimed {claim.get('count')}"

    if ctype == "object_at_rest":
        concept = claim.get("concept")
        pose = _rest_pose(src, concept, int(p.get("rest_frames", 30)))
        if pose is None:
            return False, "no detections to define a rest pose"
        rx, rb, _, _ = pose
        if not (_close(rx, claim.get("rest_x"), PX_TOL) and _close(rb, claim.get("rest_bottom"), PX_TOL)):
            return False, f"rest pose is ({rx:.1f}, {rb:.1f}), claimed ({claim.get('rest_x')}, {claim.get('rest_bottom')})"
        tol = float(claim.get("tolerance_px", p.get("rest_tolerance_px", 5.0)))
        frames = src.detected_frames(concept, claim["frame_start"], claim["frame_end"])
        at_rest = bool(frames) and all(
            abs((src.best(concept, f).bbox[0] + src.best(concept, f).bbox[2]) / 2 - rx) <= tol
            and abs(src.best(concept, f).bbox[3] - rb) <= tol for f in frames)
        return at_rest == bool(claim.get("value")), f"object at rest in all detected frames: {at_rest}"

    if ctype in ("mask_area", "max_displacement_px"):
        concept, tid = claim.get("concept"), claim.get("track_id")
        if tid not in src.track_ids:
            return False, f"track id {tid!r} does not exist"
        if ctype == "mask_area":
            frame = claim.get("frame")
            o = next((o for o in src.by_concept_frame.get((concept, frame), []) if o.object_id == tid), None)
            if o is None or not o.mask_rle:
                return False, f"no mask for {tid} at frame {frame}"
            area = float(decode_mask_rle(o.mask_rle).sum())
            return _close(area, claim.get("value"), PX_TOL), f"mask area {area:.0f}px, claimed {claim.get('value')}"
        frames = [f for f in range(claim["frame_start"], claim["frame_end"])
                  if any(o.object_id == tid for o in src.by_concept_frame.get((concept, f), []))]
        if not frames:
            return False, f"{tid} has no detections in {claim['frame_start']}-{claim['frame_end']}"
        pts = []
        for f in frames:
            o = next(o for o in src.by_concept_frame[(concept, f)] if o.object_id == tid)
            pts.append(((o.bbox[0] + o.bbox[2]) / 2, o.bbox[3]))
        pts_a = np.array(pts)
        disp = float(np.max(np.hypot(*(pts_a - pts_a[0]).T)))
        return _close(disp, claim.get("value"), 0.05), f"max displacement {disp:.2f}px, claimed {claim.get('value')}"

    if ctype == "co_motion_fraction":
        concept, a, b = claim.get("concept"), claim.get("frame_start"), claim.get("frame_end")
        moving = _arm_moving(src, p)
        frames = src.detected_frames(concept, a, b)
        steps = []
        for prev, f in zip(frames, frames[1:]):
            if f != prev + 1:
                continue
            o1, o2 = src.best(concept, prev), src.best(concept, f)
            d = np.hypot((o2.bbox[0] + o2.bbox[2] - o1.bbox[0] - o1.bbox[2]) / 2, o2.bbox[3] - o1.bbox[3])
            if d > float(p.get("object_step_px", 2.0)):
                steps.append(f)
        value = float(np.mean([moving[f] for f in steps])) if steps and moving is not None else None
        return _close(value, claim.get("value"), VALUE_TOL), f"co-motion fraction {value}, claimed {claim.get('value')}"

    if ctype == "ring_change":
        frames = src.gray()
        if frames is None:
            return None, "video not provided; pixel claim not checked"
        pose = _rest_pose(src, claim.get("concept"), int(p.get("rest_frames", 30)))
        frame = claim.get("frame")
        if pose is None or not in_range(frame):
            return False, "no rest pose or bad frame"
        _, _, box, ref = pose
        x1, y1, x2, y2 = (int(round(v)) for v in box)
        m = int(p.get("ring_margin_px", 60))
        h, w = frames[0].shape
        X1, Y1, X2, Y2 = max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)
        ring = np.ones((Y2 - Y1, X2 - X1), dtype=bool)
        ring[y1 - Y1:y2 - Y1, x1 - X1:x2 - X1] = False
        diff = np.abs(frames[frame][Y1:Y2, X1:X2] - frames[ref][Y1:Y2, X1:X2])
        value = float((diff[ring] > int(p.get("ring_pixel_delta", 25))).mean())
        return _close(value, claim.get("value"), VALUE_TOL), f"ring change {value:.4f} at {frame}, claimed {claim.get('value')}"

    if ctype == "containment":
        concept, target, frames = claim.get("concept"), claim.get("target"), claim.get("frames") or []
        if target not in src.concepts or not frames:
            return False, f"unknown target {target!r} or no frames"
        h, w = (src.gray()[0].shape if src.gray() else (720, 1280))
        vals = []
        for f in frames:
            o, t = src.best(concept, f), src.best(target, f)
            if o is None or t is None or not o.mask_rle or not t.mask_rle:
                return False, f"missing {concept} or {target} mask at frame {f}"
            om, tm = mask_in_frame(o.mask_rle, o.bbox, (h, w)), mask_in_frame(t.mask_rle, t.bbox, (h, w))
            vals.append(float((om & tm).sum() / om.sum()))
        med = float(np.median(vals))
        return _close(med, claim.get("value"), VALUE_TOL), f"median containment {med:.4f}, claimed {claim.get('value')}"

    if ctype == "frame_states":
        from tracking import frame_states_for

        concept, a, b = claim.get("concept"), claim.get("frame_start"), claim.get("frame_end")
        states = list(frame_states_for(src.tracking, concept))
        for (c, f) in src.probe_frames:
            if c == concept:
                states[f] = "detected"
        counts = {s: states[a:b].count(s) for s in ("detected", "not_detected", "unknown")}
        return counts == claim.get("counts"), f"states {counts}, claimed {claim.get('counts')}"

    if ctype == "event_ref":
        match = [e for e in timeline.get("events", []) if e.get("event_type") == claim.get("event_type")
                 and e.get("frame_start") == claim.get("frame_start")]
        if not match:
            return False, f"referenced event {claim.get('event_type')}@{claim.get('frame_start')} not in timeline"
        return match[0].get("status") == claim.get("status"), f"referenced event status {match[0].get('status')}"

    return None, f"unknown claim type {ctype!r}"


_SOURCE_PATTERNS = [
    re.compile(r"^proprio:(observation\.state|action|observation\.state\+action)\[(?P<joint>[^\]]+)\]$"),
    re.compile(r"^sam:(?P<concept>[^+]+)$"),
    re.compile(r"^sam:(?P<a>[^+]+)\+sam:(?P<b>[^+]+)$"),
    re.compile(r"^sam:(?P<a>[^+]+)\+sam:(?P<b>[^+]+)\+calibration:(?P<calibration>[\w.\-]+)$"),
    re.compile(r"^sam\+proprio$"),
    re.compile(r"^video:pixels$"),
    re.compile(r"^event:(?P<event>\w+)$"),
]


def _check_source(source: str, src: _Sources) -> str | None:
    for pat in _SOURCE_PATTERNS:
        m = pat.match(source or "")
        if not m:
            continue
        g = m.groupdict()
        if "joint" in g and g["joint"] != "arm joints" and g["joint"] not in src.joints:
            return f"joint {g['joint']!r} is not in the dataset's joint names"
        for key in ("concept", "a", "b"):
            if key in g and g[key] not in src.concepts:
                return f"concept {g[key]!r} is not in the tracking result"
        if "calibration" in g and not (CALIBRATION_DIR / g["calibration"]).is_file():
            return f"calibration file {g['calibration']!r} does not exist"
        return None
    return f"unrecognized evidence source {source!r}"


def verify_timeline(
    timeline: dict[str, Any],
    *,
    tracking: Any,
    proprio: Any,
    probes: Sequence[Any] = (),
    video_bytes: bytes | None = None,
) -> VerificationReport:
    src = _Sources(tracking, proprio, probes, video_bytes)
    report = VerificationReport()
    p = timeline.get("params") or {}

    def add(i, et, check, sev, msg):
        report.findings.append(Finding(i, et, check, sev, msg))

    fps = float(timeline.get("fps", 0))
    if not _close(fps, src.fps, 1e-6):
        add(None, None, "fps", "error", f"timeline fps {fps} != joint data fps {src.fps}")
    if timeline.get("n_frames") != src.n:
        add(None, None, "n_frames", "error", f"timeline n_frames {timeline.get('n_frames')} != video frames {src.n}")

    for i, ev in enumerate(timeline.get("events", [])):
        et = ev.get("event_type")
        before = len([f for f in report.findings if f.event_index == i and f.severity == "error"])
        a, b, status = ev.get("frame_start"), ev.get("frame_end"), ev.get("status")

        # Frames and timestamps.
        if not (isinstance(a, int) and isinstance(b, int) and 0 <= a <= b <= src.n):
            add(i, et, "frames", "error", f"frame range {a}-{b} invalid for {src.n} frames")
        else:
            for key, f in (("t_start", a), ("t_end", b)):
                if not _close(ev.get(key), round(f / src.fps, 3), 1e-6):
                    add(i, et, "timestamp", "error", f"{key}={ev.get(key)} but frame {f} is {round(f / src.fps, 3)}s")

        # Status semantics.
        if status not in STATUSES:
            add(i, et, "status", "error", f"unknown status {status!r}")
        if status == "observed" and et not in MEASURED_EVENTS:
            add(i, et, "status", "error", f"{et} is not a direct measurement and cannot be 'observed'")
        if et not in MEASURED_EVENTS | CANDIDATE_EVENTS:
            add(i, et, "event_type", "error", f"unknown event type {et!r}")
        if status == "inferred" and not ev.get("inference"):
            add(i, et, "inference", "error", "inferred event without a stated inference")
        if status in ("observed", "uncertain") and ev.get("inference"):
            add(i, et, "inference", "error", f"{status} event must not carry an inference")
        if re.search(r"fail|drop|miss", et or "") and all(r.get("kind") == "absence" for r in ev.get("evidence", [])):
            add(i, et, "absence", "error", "failure-like event supported only by missing detections")

        # Evidence provenance and claims.
        verified: list[dict[str, Any]] = []
        evidence = ev.get("evidence") or []
        if not evidence:
            add(i, et, "evidence", "error", "event has no evidence")
        for j, ref in enumerate(evidence):
            if ref.get("kind") not in KINDS:
                add(i, et, "provenance", "error", f"evidence {j}: unknown kind {ref.get('kind')!r}")
            problem = _check_source(ref.get("source", ""), src)
            if problem:
                add(i, et, "provenance", "error", f"evidence {j}: {problem}")
            ra, rb = ref.get("frame_start"), ref.get("frame_end")
            if not (isinstance(ra, int) and isinstance(rb, int) and -1 <= ra <= rb <= src.n + 1):
                add(i, et, "frames", "error", f"evidence {j}: frame range {ra}-{rb} invalid")
            claims = ref.get("claims") or []
            if not claims:
                add(i, et, "claims", "warning", f"evidence {j} ({ref.get('source')}) has no checkable claims")
                report.claims_unverifiable += 1
            cal_match = re.search(r"\+calibration:([\w.\-]+)$", ref.get("source", ""))
            for claim in claims:
                report.claims_checked += 1
                if claim.get("type") == "interior_containment":
                    ok, msg = _check_interior_claim(claim, src, cal_match.group(1) if cal_match else None)
                else:
                    ok, msg = _check_claim(claim, src, timeline)
                if ok is None:
                    report.claims_unverifiable += 1
                    add(i, et, f"claim:{claim.get('type')}", "warning", f"evidence {j}: {msg}")
                elif not ok:
                    report.claims_failed += 1
                    add(i, et, f"claim:{claim.get('type')}", "error", f"evidence {j}: {msg}")
                else:
                    verified.append(claim)
                if claim.get("type") == "detection_count":
                    if ref.get("kind") == "absence" and (claim.get("count") or 0) > 0:
                        add(i, et, "absence", "error", f"evidence {j} is labeled absence but claims detections")
                    if ref.get("kind") == "detection" and not claim.get("count"):
                        add(i, et, "absence", "error", f"evidence {j} is labeled detection but claims none")

        # Status must be justified by *verified* claims.
        def has(ctype: str, pred=lambda c: True) -> bool:
            return any(c.get("type") == ctype and pred(c) for c in verified)

        if status == "inferred":
            needs: list[tuple[str, bool]] = []
            if et == "approach_candidate":
                needs = [("verified ring_change above threshold",
                          has("ring_change", lambda c: (c.get("value") or 0) > float(p.get("ring_change_frac", 0.05)))),
                         ("verified partial-covering mask_area", has("mask_area")),
                         ("verified object_at_rest", has("object_at_rest", lambda c: c.get("value") is True))]
            elif et == "grasp_candidate":
                needs = [("verified stalled closure", any(
                            c.get("type") == "closure_gap" and c.get("stalled") is True for c in verified)
                          or _stall_from_joint_claims(verified, src, p)),
                         ("verified object detection at closure", has("detection_count", lambda c: (c.get("count") or 0) > 0)),
                         ("inferred co-movement event", has("event_ref", lambda c: c.get("status") == "inferred"))]
            elif et == "coordinated_movement_candidate":
                needs = [("verified displacement >= moved_px",
                          has("max_displacement_px", lambda c: (c.get("value") or 0) >= float(p.get("moved_px", 40)))),
                         ("verified co-motion >= threshold",
                          has("co_motion_fraction", lambda c: (c.get("value") or 0) >= float(p.get("co_motion_frac", 0.7))))]
            elif et == "release_candidate":
                needs = [("verified post-opening detections", has("detection_count", lambda c: (c.get("count") or 0) >= 2))]
            elif et == "final_placement_candidate":
                needs = _placement_support(ev, verified, timeline, src, p)
            for label, ok in needs:
                if not ok:
                    add(i, et, "status_support", "error", f"'inferred' lacks {label}")
        if status == "observed" and et in MEASURED_EVENTS and not has("joint_value", lambda c: c.get("field") == "observation.state"):
            add(i, et, "status_support", "error", "'observed' gripper event lacks a verified measured joint value")

        errors_now = len([f for f in report.findings if f.event_index == i and f.severity == "error"])
        warnings_now = [f for f in report.findings if f.event_index == i and f.severity == "warning"]
        report.event_verdicts[i] = ("unsupported" if errors_now > before
                                    else "partially_verifiable" if warnings_now else "supported")
    return report


def _placement_support(ev: dict[str, Any], verified: list[dict[str, Any]], timeline: dict[str, Any],
                       src: _Sources, p: dict[str, Any]) -> list[tuple[str, bool]]:
    """What an 'inferred' placement must have, judged from verified claims and raw data.

    Passing claim checks only shows the numbers are right; these checks ask whether
    they physically support placement: interior (not raw-mask) containment, reliable
    estimates, after release, gripper not holding, separated observations, and no
    claim of continuity from discrete observations.
    """
    contain = float(p.get("contain_frac", 0.8))
    span_min = int(p.get("min_placement_span", 15))
    inside = sorted(c["frame"] for c in verified if c.get("type") == "interior_containment"
                    and c.get("reliable") is True and (c.get("interior_fraction") or 0) >= contain)
    all_interior = [c for r in ev.get("evidence", []) for c in r.get("claims", []) if c.get("type") == "interior_containment"]
    releases = [e for e in timeline.get("events", []) if e.get("event_type") == "release_candidate"]
    release_end = max((e["frame_end"] for e in releases), default=None)
    g, a = src.joint("observation.state", "gripper.pos"), src.joint("action", "gripper.pos")
    holding = []
    if g is not None and a is not None:
        span = float(g.max() - g.min())
        mid = float(g.min()) + float(p.get("gripper_mid_frac", 0.5)) * span
        thr = float(p.get("stall_frac", 0.1)) * span
        holding = [f for f in inside if g[f] < mid and (g[f] - a[f]) > thr]
    return [
        (">= 2 verified, reliable inside-interior observations", len(inside) >= 2),
        (f"observations >= {span_min} frames apart", len(inside) >= 2 and inside[-1] - inside[0] >= span_min),
        ("every cited interior observation verified, reliable and inside",
         bool(all_interior) and len(inside) == len(all_interior)),
        ("observations after the measured release", release_end is not None and all(f >= release_end for f in inside)),
        ("gripper not holding (stalled-closed) at the observation frames", not holding),
        ("inference does not claim continuity from discrete observations",
         not CONTINUITY_WORDS.search(ev.get("inference") or "")),
    ]


def _failure_gripper_opens(g: np.ndarray, fps: float, cal: dict[str, Any]) -> list[int]:
    """Recompute measured gripper openings from raw joints (independent of failures.py).

    Mirrors the relative-rise / midpoint detectors' acceptance criteria using parameters
    recorded on the report; implemented here so a shared bug cannot silently agree.
    """
    sign = 1 if int(cal.get("open_sign", 1)) >= 0 else -1
    g = np.asarray(g, dtype=float) * sign
    lo, hi = float(np.min(g)), float(np.max(g))
    span = hi - lo
    if span <= 0 or len(g) < 3:
        return []
    detector = str(cal.get("detector", "relative_rise"))
    persist = max(1, int(round(float(cal.get("persist_s", 0.15)) * fps)))
    if detector == "midpoint":
        mid = lo + 0.5 * span
        side = g > mid
        out, cur, f = [], bool(side[0]), 1
        while f < len(g):
            if bool(side[f]) != cur and all(bool(side[k]) != cur for k in range(f, min(len(g), f + persist))):
                cur = bool(side[f])
                if cur:
                    out.append(f)
                f += persist
                continue
            f += 1
        return out

    # relative_rise (default)
    closed = g <= lo + 0.2 * span
    diffs = np.abs(np.diff(g))
    mask = closed[:-1] & closed[1:]
    noise = max(1e-9, float(np.percentile(diffs[mask], 95)) if int(mask.sum()) >= 5 else 0.01 * span)
    open_frac = float(cal.get("open_rise_frac", 0.15))
    noise_mult = float(cal.get("noise_mult", 5.0))
    open_thr = max(open_frac * span, noise_mult * noise)
    track_thr = max(float(cal.get("settle_frac", 0.02)) * span,
                    float(cal.get("settle_noise_mult", 2.0)) * noise)
    close_settle_thr = max(float(cal.get("close_settle_frac", 0.05)) * span, noise_mult * noise)
    close_band = lo + float(cal.get("close_band_frac", 0.25)) * span
    baseline_n = max(1, int(round(float(cal.get("baseline_s", 0.5)) * fps)))
    if baseline_n >= len(g) or persist >= len(g):
        return []
    lower = g[g <= lo + 0.2 * span]
    closed_baseline = float(np.median(lower)) if len(lower) else float(np.median(g[:baseline_n]))
    early = float(np.median(g[:baseline_n]))
    state = "open" if early - closed_baseline > open_thr else "closed"
    peak = float(np.max(g[: baseline_n + 1]))
    out: list[int] = []
    f = baseline_n
    while f + max(persist, baseline_n) <= len(g):
        if state == "closed":
            window = g[f - baseline_n : f]
            w_med = float(np.median(window))
            w_std = float(np.std(window))
            if w_std <= track_thr and abs(w_med - closed_baseline) <= track_thr:
                closed_baseline = 0.8 * closed_baseline + 0.2 * w_med
            if all(float(g[k]) - closed_baseline > open_thr for k in range(f, f + persist)):
                out.append(f)
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
                state = "closed"
                closed_baseline = w_med
                f += persist
                continue
        f += 1
    return out


def verify_failure_report(
    report: dict[str, Any],
    *,
    observations: Sequence[Any],
    container_mask: np.ndarray | None,
    gripper_measured: np.ndarray | None,
    fps: float,
    n_frames: int,
    frame_shape: tuple[int, int],
) -> VerificationReport:
    """Independently re-check a failures.FailureReport (as a dict) against raw inputs.

    Recomputes displacement from raw boxes, rest-frame regions from raw masks (own
    hole filling), gripper openings from raw joint values (own crossing search), and
    checks that each status is justified only by claims that verified.
    """
    from tracking import mask_in_frame

    out = VerificationReport()
    p = (report.get("inputs") or {}).get("params") or {}
    win = int(round(float(p.get("release_window_s", 0.7)) * fps))
    moved_rel = float(p.get("moved_rel", 0.5))
    max_gap = float(p.get("max_gap_s", 0.5)) * fps
    obs = {(o.object_id, o.frame_index): o for o in observations
           if o.bbox is not None and o.frame_index is not None and o.observation_returned}
    footprint = _holes_filled_cc(container_mask) if container_mask is not None else None

    def add(i, et, check, sev, msg):
        out.findings.append(Finding(i, et, check, sev, msg))

    def region_of(tid: str, f: int) -> str:
        o = obs.get((tid, f))
        if o is None or not o.mask_rle or footprint is None:
            return "unknown"
        om = mask_in_frame(o.mask_rle, o.bbox, frame_shape)
        if om is None or not om.any():
            return "unknown"
        return "outside" if (om & footprint).sum() / om.sum() <= 0.05 else "unknown"  # no interior calibration here

    def opened_near(f: int) -> bool:
        """Independent recompute of a measured opening near frame f (not failures.py)."""
        if gripper_measured is None:
            return False
        cal = (report.get("inputs") or {}).get("gripper_calibration") or {}
        opens = _failure_gripper_opens(np.asarray(gripper_measured, dtype=float), fps, cal)
        return any(abs(of - f) <= 2 for of in opens)

    events = report.get("physical_events") or []
    for i, e in enumerate(events):
        et = e.get("kind")
        before = len([f for f in out.findings if f.event_index == i and f.severity == "error"])
        a, b = e.get("frame_start"), e.get("frame_end")
        if not (isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= n_frames):
            add(i, et, "frames", "error", f"frame range {a}-{b} invalid")
        else:
            for key, f in (("t_start", a), ("t_end", b)):
                if not _close(e.get(key), round(f / fps, 3), 1e-6):
                    add(i, et, "timestamp", "error", f"{key}={e.get(key)} but frame {f} is {round(f / fps, 3)}s")
        if not any(ev.get("kind") == "detection" for ev in e.get("evidence") or []):
            add(i, et, "absence", "error", "physical event has no positive detection evidence")
        verified: list[dict[str, Any]] = []
        for ev in e.get("evidence") or []:
            for c in ev.get("claims") or []:
                out.claims_checked += 1
                ok, msg = None, f"unknown claim type {c.get('type')!r}"
                if c.get("type") == "displacement":
                    o1, o2 = obs.get((c.get("track_id"), c.get("from_frame"))), obs.get((c.get("track_id"), c.get("to_frame")))
                    if o1 is None or o2 is None:
                        ok, msg = False, f"no observation of {c.get('track_id')} at {c.get('from_frame')} / {c.get('to_frame')}"
                    else:
                        d = float(np.hypot((o2.bbox[0] + o2.bbox[2] - o1.bbox[0] - o1.bbox[2]) / 2,
                                           (o2.bbox[1] + o2.bbox[3] - o1.bbox[1] - o1.bbox[3]) / 2))
                        size = float(np.hypot(o1.bbox[2] - o1.bbox[0], o1.bbox[3] - o1.bbox[1]))
                        ok = abs(d - float(c.get("value_px", -1))) <= PX_TOL
                        msg = f"displacement {d:.2f}px ({d / max(size, 1):.2f}x size), claimed {c.get('value_px')}"
                        c = dict(c, _size=size, _disp=d)
                elif c.get("type") == "observation_coverage":
                    ca, cb = c.get("frame_start"), c.get("frame_end")
                    ok = isinstance(ca, int) and isinstance(cb, int) and 0 <= ca < cb <= n_frames
                    if ok:
                        present = {f for tid, f in obs if tid == c.get("track_id") and ca <= f < cb}
                        missing = [f for f in range(ca, cb) if f not in present]
                        ranges = []
                        for frame in missing:
                            if ranges and ranges[-1]["frame_end"] == frame:
                                ranges[-1]["frame_end"] += 1
                            else:
                                ranges.append({"frame_start": frame, "frame_end": frame + 1})
                        ok = (c.get("frames_with_detections") == len(present)
                              and c.get("missing_frames") == len(missing)
                              and c.get("missing_ranges") == ranges)
                    msg = "Coverage recomputed from returned raw observation frames, including all gaps"
                elif c.get("type") == "rest_region":
                    frames = c.get("frames") or []
                    regions = [region_of(c.get("track_id"), f) for f in frames]
                    claimed = c.get("region")
                    if claimed == "inside":
                        ok, msg = None, "inside requires an interior calibration; not checkable here"
                    elif claimed == "outside":
                        ok = bool(frames) and all(r == "outside" for r in regions)
                        msg = f"recomputed regions {sorted(set(regions))} over {len(frames)} frames"
                    else:
                        ok, msg = True, "region claimed unknown"
                elif c.get("type") == "gripper_open":
                    ok = opened_near(int(c.get("frame", -10)))
                    msg = f"measured gripper opening near frame {c.get('frame')}: {ok}"
                if ok is None:
                    out.claims_unverifiable += 1
                    add(i, et, f"claim:{c.get('type')}", "warning", msg)
                elif not ok:
                    out.claims_failed += 1
                    add(i, et, f"claim:{c.get('type')}", "error", msg)
                else:
                    verified.append(c)
        if et == "image_position_change":
            endpoint = [c for c in verified if c.get("type") == "displacement"
                        and c.get("track_id") == e.get("track_id") and c.get("from_frame") == a
                        and c.get("to_frame") == b - 1 and c["_disp"] >= moved_rel * max(1, c["_size"])]
            coverage = [c for c in verified if c.get("type") == "observation_coverage"
                        and c.get("track_id") == e.get("track_id")
                        and c.get("frame_start") == a and c.get("frame_end") == b]
            if (e.get("status") != "observed" or e.get("subtype") != "endpoint_displacement"
                    or not endpoint or not coverage):
                add(i, et, "status_support", "error", "Observed endpoint change requires matching verified displacement and coverage, not a release inference")
        if e.get("status") == "inferred" and et == "dropped_in_transport":
            disp = [c for c in verified if c.get("type") == "displacement" and c["_disp"] >= moved_rel * c["_size"]]
            outside = [c for c in verified if c.get("type") == "rest_region" and c.get("region") == "outside"]
            if not disp:
                add(i, et, "status_support", "error", f"'inferred' lacks a verified move >= {moved_rel}x object size")
            if not outside:
                add(i, et, "status_support", "error", "'inferred' lacks verified rest outside the target")
            if e.get("subtype") == "released_outside_target":
                frm = disp[0]["from_frame"] if disp else a
                to = disp[0]["to_frame"] if disp else b
                if not any(c.get("type") == "gripper_open" and frm <= c.get("frame", -1) <= to + win for c in verified):
                    add(i, et, "status_support", "error", "'released_outside_target' lacks a verified opening during the move")
            elif not ((report.get("inputs") or {}).get("gripper_calibration") or {}).get("holding_detectable"):
                add(i, et, "status_support", "error", "slip inferred although this gripper cannot show holding")
        errors_now = len([f for f in out.findings if f.event_index == i and f.severity == "error"])
        warns = [f for f in out.findings if f.event_index == i and f.severity == "warning"]
        out.event_verdicts[i] = "unsupported" if errors_now > before else "partially_verifiable" if warns else "supported"

    # Final outcomes and verdict.
    last_obs: dict[str, int] = {}
    for (tid, f) in obs:
        last_obs[tid] = max(last_obs.get(tid, -1), f)
    for o in report.get("object_outcomes") or []:
        if o.get("final_region") in ("inside", "outside"):
            out.claims_checked += 1
            frames = o.get("frames") or []
            valid_frames = (len(frames) >= 2 and all(isinstance(f, int) and 0 <= f < n_frames for f in frames)
                            and frames == sorted(set(frames)))
            enough_span = valid_frames and frames[-1] - frames[0] >= float(p.get("final_min_span_s", .5)) * fps
            matches = valid_frames and all(region_of(o.get("track_id"), f) == o["final_region"] for f in frames)
            identity = valid_frames and all(getattr(obs.get((o.get("track_id"), f)), "concept", None) == o.get("concept") for f in frames)
            rest = bool(valid_frames)
            for fa, fb in zip(frames, frames[1:]) if valid_frames else []:
                oa, ob = obs.get((o.get("track_id"), fa)), obs.get((o.get("track_id"), fb))
                if oa is None or ob is None or fb - fa > max_gap:
                    rest = False
                    break
                a, b = np.asarray(oa.bbox), np.asarray(ob.bbox)
                delta = np.linalg.norm((b[:2] + b[2:] - a[:2] - a[2:]) / 2)
                if delta / (fb - fa) > float(p.get("rest_motion_rel", .02)) * max(1, np.linalg.norm(a[2:] - a[:2])):
                    rest = False
                    break
            # This verifier has raw footprint masks, not an independently supplied
            # calibrated interior. Never certify an "inside" conclusion from them.
            if not enough_span or not matches or not rest or not identity or o.get("status") != "inferred":
                out.claims_failed += 1
                add(None, "object_outcome", "final_outcome", "error",
                    "Final region lacks separated, independently verified raw-mask observations; inside requires calibrated interior support")
            elif n_frames - 1 - frames[-1] > max_gap:
                out.claims_failed += 1
                add(None, "object_outcome", "final_outcome", "error", "Final-region evidence ends before the final observation window")
        if o.get("final_region") in ("inside", "outside") and n_frames - 1 - last_obs.get(o.get("track_id"), -10**9) > max_gap:
            add(None, "object_outcome", "final_outcome", "error",
                f"{o.get('track_id')} given final region {o.get('final_region')} but last observed at frame "
                f"{last_obs.get(o.get('track_id'))} of {n_frames}")
    outs = [o for o in report.get("object_outcomes") or [] if o.get("final_region") == "outside"]
    if report.get("verdict") == "failure" and not outs:
        add(None, "verdict", "verdict", "error", "verdict 'failure' without any object finally outside the target")
    if report.get("verdict") == "success" and (not report.get("object_outcomes") or
            any(o.get("final_region") != "inside" for o in report.get("object_outcomes") or [])):
        add(None, "verdict", "verdict", "error", "verdict 'success' while some object is not finally inside")
    inferred = [(k, e) for k, e in enumerate(events) if e.get("status") == "inferred"]
    ef = report.get("earliest_failure")
    if inferred:
        k, e = min(inferred, key=lambda x: x[1]["frame_start"])
        if not ef or ef.get("event_index") != k or ef.get("frame_start") != e["frame_start"]:
            add(None, "earliest_failure", "earliest_failure", "error", "earliest_failure is not the earliest inferred event")
    elif ef:
        add(None, "earliest_failure", "earliest_failure", "error", "earliest_failure given without an inferred event")
    return out


def _stall_from_joint_claims(verified: list[dict[str, Any]], src: _Sources, p: dict[str, Any]) -> bool:
    """A grasp's stall may also be shown by verified state/action values at the same frame."""
    states = {c["frame"]: c["value"] for c in verified if c.get("type") == "joint_value" and c.get("field") == "observation.state"}
    actions = {c["frame"]: c["value"] for c in verified if c.get("type") == "joint_value" and c.get("field") == "action"}
    g = src.joint("observation.state", "gripper.pos")
    if g is None:
        return False
    threshold = float(p.get("stall_frac", 0.1)) * float(g.max() - g.min())
    return any(f in actions and states[f] - actions[f] > threshold for f in states)
