"""Build failures.py inputs from cached SAM results and LeRobot joint data.

Reads only: the video, SAM caches (window chunk entry + container image result),
joint data, a gripper calibration file and a task spec. It deliberately does not
read manual annotations (data/event_labels.json) or dataset anomaly flags.
No API calls.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

import container as C
import failures as F
import proprio
import tracking as T

ROOT = Path(__file__).parent


def load_task(path: Path) -> F.TaskSpec:
    d = json.loads(path.read_text(encoding="utf-8"))
    return F.TaskSpec(d["task_id"], d["description"],
                      tuple(F.ObjectSpec(o["concept"], o.get("count")) for o in d["objects"]), d["target"])


def load_gripper_calibration(path: Path) -> tuple[F.GripperCalibration, str]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return F.GripperCalibration(
        d["source"],
        d["basis"],
        bool(d["holding_detectable"]),
        float(d.get("persist_s", 0.15)),
        detector=str(d.get("detector", "relative_rise")),
        open_sign=int(d.get("open_sign", 1)),
        open_rise_frac=float(d.get("open_rise_frac", 0.15)),
        noise_mult=float(d.get("noise_mult", 5.0)),
        baseline_s=float(d.get("baseline_s", 0.5)),
        settle_frac=float(d.get("settle_frac", 0.02)),
        settle_noise_mult=float(d.get("settle_noise_mult", 2.0)),
        close_settle_frac=float(d.get("close_settle_frac", 0.05)),
        close_band_frac=float(d.get("close_band_frac", 0.25)),
    ), d["joint"]


@dataclass
class WindowInputs:
    video_bytes: bytes
    fps: float
    n_frames: int
    frame_shape: tuple[int, int]
    chunk: Any
    call: dict[str, Any] | None
    observations: list[Any]  # SAM observations in the window (object concept)
    container_mask: np.ndarray | None  # full-frame mask of the container (raw SAM)
    container_source: dict[str, Any]
    assessments: dict[tuple[str, int], dict[str, Any]]  # (object_id, frame) -> assess_containment
    tracks: list[F.ObjectTrack]
    gripper: F.GripperSignal | None
    sources: dict[str, Any] = field(default_factory=dict)


def _container_mask(video_bytes: bytes, frame: int, concept: str, fps: float, shape: tuple[int, int]) -> tuple[np.ndarray | None, dict]:
    jpeg = T.extract_frame_jpeg(video_bytes, timestamp_s=frame / fps, quality=95)
    cached = T.load_cached_tracking(jpeg, [concept], media_kind="image")
    info = {"concept": concept, "frame": frame, "cached": cached is not None,
            "n_observations": len(cached.observations) if cached else 0,
            "status": "cache_missing" if cached is None else "empty_result"}
    if cached is None or not cached.observations:
        return None, info
    mask = np.zeros(shape, bool)
    for o in cached.observations:
        if o.mask_rle and o.bbox:
            try:
                m = T.mask_in_frame(o.mask_rle, o.bbox, shape)
            except (KeyError, ValueError, TypeError, IndexError):
                m = None
            if m is not None and o.observation_returned:
                mask |= m
    info["confidences"] = [getattr(o, "confidence", None) for o in cached.observations]
    info["status"] = "available" if mask.any() else "unusable_masks"
    info["mask_pixels"] = int(mask.sum())
    usage = getattr(getattr(cached, "diagnostics", None), "usage", None) or {}
    terminal = (usage.get(concept) or {}).get("terminal_event")
    info["terminal_event"] = terminal
    if mask.any() and terminal != "response.completed":
        info["status"] = "completion_unverified"
        return None, info
    return (mask if mask.any() else None), info


def observation_coverage(observations: list[Any], start_frame: int, end_frame: int) -> dict[str, Any]:
    """Count actual returned box frames, never interpolate or infer physical absence."""
    frames = {o.frame_index for o in observations if o.observation_returned
              and o.bbox is not None and o.frame_index is not None
              and start_frame <= o.frame_index < end_frame}
    ranges: list[dict[str, int]] = []
    for frame in range(start_frame, end_frame):
        if frame in frames:
            continue
        if ranges and ranges[-1]["frame_end"] == frame:
            ranges[-1]["frame_end"] = frame + 1
        else:
            ranges.append({"frame_start": frame, "frame_end": frame + 1})
    expected = max(0, end_frame - start_frame)
    return {"frame_start": start_frame, "frame_end": end_frame,
            "frames_with_detections": len(frames), "missing_frames": expected - len(frames),
            "expected_frames": expected, "missing_ranges": ranges,
            "note": "Missing detections are unobserved, not proof of physical absence. No interpolation."}


def build_window_inputs(
    video_path: Path,
    *,
    start_frame: int,
    end_frame: int,
    object_concept: str,
    container_concept: str,
    container_frame: int,
    joint_dir: Path | None = None,
    episode_index: int | None = None,
    gripper_calibration: Path | None = None,
) -> WindowInputs:
    video = video_path.read_bytes()
    fps, n_frames = T.probe_video(video)
    w, h = T.probe_video_size(video)
    shape = (h, w)
    chunk = T.window_chunk(start_frame, end_frame)
    entry = T.read_chunk_entry(T.chunk_cache_path(T._video_digest(video), chunk, object_concept))
    if not T.chunk_entry_matches(entry, object_concept, chunk):
        entry = None
    call = (entry or {}).get("call")
    obs = [T._observation_from_row(r) for r in (entry or {}).get("observations") or []] \
        if entry and T.chunk_entry_reusable(entry) else []
    cmask, csrc = _container_mask(video, container_frame, container_concept, fps, shape)

    # Region per observation: outside only if (essentially) none of the object mask
    # lies in the container's hole-filled footprint (see failures.classify_region).
    assessments: dict[tuple[str, int], dict[str, Any]] = {}
    by_track: dict[str, list[F.TrackObs]] = {}
    for o in obs:
        if (not o.observation_returned or o.bbox is None or o.frame_index is None
                or not start_frame <= o.frame_index < end_frame):
            continue
        om = T.mask_in_frame(o.mask_rle, o.bbox, shape) if o.mask_rle else None
        a = C.assess_containment(om, cmask, None, None) if om is not None else None
        assessments[(o.object_id, o.frame_index)] = a
        x1, y1, x2, y2 = o.bbox
        by_track.setdefault(o.object_id, []).append(F.TrackObs(
            o.frame_index, (x1 + x2) / 2, (y1 + y2) / 2, float(np.hypot(x2 - x1, y2 - y1)), F.classify_region(a)))
    tracks = [F.ObjectTrack(tid, object_concept, ob) for tid, ob in sorted(by_track.items())]

    gripper = None
    sources: dict[str, Any] = {"video": video_path.as_posix(), "video_sha256": hashlib.sha256(video).hexdigest(),
                               "window": [start_frame, end_frame], "sam_call": call, "container": csrc,
                               "observation_coverage": observation_coverage(obs, start_frame, end_frame)}
    if joint_dir is not None and episode_index is not None and gripper_calibration is not None:
        cal, joint = load_gripper_calibration(gripper_calibration)
        ep = proprio.load_episode(joint_dir, episode_index)
        problems = proprio.check_video_alignment(ep, video_frames=n_frames, video_fps=fps)
        if problems:
            raise ValueError(f"joint data not aligned with video: {problems}")
        gripper = F.GripperSignal(ep.joint(joint), ep.joint(joint, kind="action"), cal)
        sources["joint_data"] = {"dir": joint_dir.as_posix(), "episode": episode_index, "joint": joint,
                                 "calibration": gripper_calibration.as_posix()}
    return WindowInputs(video, fps, n_frames, shape, chunk, call, obs, cmask, csrc, assessments, tracks, gripper, sources)


def localize_window(inputs: WindowInputs, task: F.TaskSpec, params: F.FailureParams = F.FailureParams(),
                    *, include_observation_events: bool = False) -> F.FailureReport:
    report = F.localize_failures(task, inputs.tracks, fps=inputs.fps, n_frames=inputs.n_frames,
                                 gripper=inputs.gripper, params=params)
    report.inputs["sources"] = inputs.sources
    if inputs.container_mask is None:
        report.uncertainties.append(
            f"Target {task.target!r} segmentation unavailable ({inputs.container_source.get('status', 'unknown')}); "
            "containment, placement and target-relative failure cannot be established.")
    if include_observation_events:
        _append_observation_events(report, inputs, params)
    return report


def _append_observation_events(report: F.FailureReport, inputs: WindowInputs, params: F.FailureParams) -> None:
    """Observed endpoint change is not a reconstructed trajectory or manipulation event.

    Opted into by live analysis only; existing frozen failure-rule semantics stay intact.
    """
    for track in inputs.tracks:
        samples = sorted([o for o in inputs.observations if o.object_id == track.track_id
                          and o.observation_returned and o.frame_index is not None
                          and o.bbox is not None], key=lambda o: o.frame_index)
        if len(samples) < 2:
            continue
        first, last = samples[0], samples[-1]
        a, b = np.asarray(first.bbox, dtype=float), np.asarray(last.bbox, dtype=float)
        displacement = float(np.hypot(*((b[:2] + b[2:] - a[:2] - a[2:]) / 2)))
        size = float(np.hypot(*(a[2:] - a[:2])))
        if last.frame_index <= first.frame_index or displacement < params.moved_rel * max(size, 1):
            continue
        coverage = observation_coverage(samples, first.frame_index, last.frame_index + 1)
        report.physical_events.append(F.PhysicalEvent(
            "image_position_change", "endpoint_displacement", "observed", track.track_id,
            first.frame_index, last.frame_index + 1, round(first.frame_index / inputs.fps, 3),
            round((last.frame_index + 1) / inputs.fps, 3), [
                F.Evidence(f"sam:{track.concept}", "detection", first.frame_index, last.frame_index + 1,
                    f"The box center for SAM track {track.track_id} differs by {displacement:.2f}px "
                    f"between observed frames {first.frame_index} and {last.frame_index}; endpoint comparison only.",
                    [{"type": "displacement", "track_id": track.track_id,
                      "from_frame": first.frame_index, "to_frame": last.frame_index,
                      "value_px": round(displacement, 2)}]),
                F.Evidence(f"sam:{track.concept}", "comparison", first.frame_index, last.frame_index + 1,
                    f"{coverage['frames_with_detections']} of {coverage['expected_frames']} frames have returned "
                    f"detections; {coverage['missing_frames']} frames unobserved. No interpolation.",
                    [{"type": "observation_coverage", "track_id": track.track_id,
                      **{k: coverage[k] for k in ('frame_start', 'frame_end', 'frames_with_detections',
                                                 'missing_frames', 'missing_ranges')}}])],
            uncertainties=["Only 2D box-center positions of one SAM track ID are compared; no depth or physical identity guarantee.",
                           "No continuous trajectory is established across missing detections.",
                           "This does not establish grasp, holding, release, placement, or task success/failure."]))
