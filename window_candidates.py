"""Propose manipulation analysis windows from joints only (no labels, no APIs).

Candidates are centered on measured gripper openings (failures._transitions),
optionally boosted when nearby arm joints show elevated motion. Context before
and after each anchor is included so rest→move→rest patterns can be observed.

Forbidden inputs: anomaly CSVs, event_labels, suggested outcomes, Muse verdicts.

Frozen defaults (DEFAULT_*) preserve the original open-centered + merge behavior.
Use ``WindowCandidateParams.efficient()`` for budget-aware selection (max duration,
stricter merge) without changing frozen call sites.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

import failures as F

# Frozen before held-out use. Derived from open-centered windows used in
# development prep (~1 s pre + ~3 s post around a measured open ≈ 121 frames @ 30 fps).
# Not tuned on ep001/ep011 outcomes. Unlimited merge/duration = original behavior.
DEFAULT_PRE_S = 1.0
DEFAULT_POST_S = 3.0
DEFAULT_ARM_RADIUS_S = 1.0
DEFAULT_ARM_SPEED_PERCENTILE = 70.0
DEFAULT_MERGE_GAP_S = 1.5
DEFAULT_MAX_DURATION_S: float | None = None
DEFAULT_MAX_MERGED_OPENS: int | None = None

# Budget-aware profile for new experiments. Caps one candidate at ~pre+post so
# consecutive manipulation opens stay separate. Not fitted to ep010's manual window
# or any held-out failure timestamp.
EFFICIENT_MAX_DURATION_S = 4.0
EFFICIENT_MERGE_GAP_S = 0.5
EFFICIENT_MAX_MERGED_OPENS = 2


@dataclass(frozen=True)
class WindowCandidateParams:
    pre_s: float = DEFAULT_PRE_S
    post_s: float = DEFAULT_POST_S
    arm_radius_s: float = DEFAULT_ARM_RADIUS_S
    arm_speed_percentile: float = DEFAULT_ARM_SPEED_PERCENTILE
    merge_gap_s: float = DEFAULT_MERGE_GAP_S
    max_duration_s: float | None = DEFAULT_MAX_DURATION_S
    max_merged_opens: int | None = DEFAULT_MAX_MERGED_OPENS
    rank_prefer_compact: bool = False
    gripper_joint: str = "main_gripper"

    @classmethod
    def frozen(cls) -> "WindowCandidateParams":
        """Original selector configuration (unlimited merge/duration)."""
        return cls()

    @classmethod
    def efficient(cls) -> "WindowCandidateParams":
        """Conservative SAM-budget profile: keep pre/post context, limit merge chains."""
        return cls(
            pre_s=DEFAULT_PRE_S,
            post_s=DEFAULT_POST_S,
            arm_radius_s=DEFAULT_ARM_RADIUS_S,
            arm_speed_percentile=DEFAULT_ARM_SPEED_PERCENTILE,
            merge_gap_s=EFFICIENT_MERGE_GAP_S,
            max_duration_s=EFFICIENT_MAX_DURATION_S,
            max_merged_opens=EFFICIENT_MAX_MERGED_OPENS,
            rank_prefer_compact=True,
        )


@dataclass
class WindowCandidate:
    """One proposed SAM/analysis window."""

    frame_start: int
    frame_end: int  # exclusive
    t_start: float
    t_end: float
    anchor_frame: int
    anchor_t: float
    kind: str  # "open_centered"
    near_arm_activity: bool
    score: float
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def n_frames(self) -> int:
        return max(0, self.frame_end - self.frame_start)


def arm_joint_speed(
    state: np.ndarray,
    joint_names: Sequence[str],
    *,
    exclude: Sequence[str] = ("main_gripper",),
) -> np.ndarray:
    """Per-frame L2 speed of non-gripper joints (length n_frames; index 0 = 0)."""
    state = np.asarray(state, dtype=float)
    if state.ndim != 2:
        raise ValueError("state must be (n_frames, n_joints)")
    keep = [i for i, n in enumerate(joint_names) if n not in exclude]
    if not keep:
        return np.zeros(state.shape[0], dtype=float)
    arm = state[:, keep]
    speed = np.zeros(state.shape[0], dtype=float)
    if len(arm) > 1:
        speed[1:] = np.linalg.norm(np.diff(arm, axis=0), axis=1)
    return speed


def _clip_window(start: int, end: int, n_frames: int) -> tuple[int, int]:
    start = max(0, int(start))
    end = min(int(n_frames), int(end))
    if end <= start:
        end = min(n_frames, start + 1)
    return start, end


def _activity_score(
    *,
    near: bool,
    peak_speed: float,
    speed_thr: float | None,
    measured_gripper: float,
    gripper_span_hint: float,
) -> float:
    """Rank by gripper openness + nearby arm motion (no labels)."""
    arm_term = 0.0
    if speed_thr is not None and speed_thr > 0:
        arm_term = (1.0 if near else 0.0) + min(1.0, peak_speed / (speed_thr + 1e-9))
    grip_term = 0.0
    if gripper_span_hint > 1e-6 and np.isfinite(measured_gripper):
        grip_term = min(1.0, max(0.0, float(measured_gripper)) / gripper_span_hint)
    return 1.0 + arm_term + 0.5 * grip_term


def _can_merge(
    prev: dict[str, Any],
    item: dict[str, Any],
    *,
    merge_gap: int,
    max_duration_frames: int | None,
    max_merged_opens: int | None,
) -> bool:
    if item["frame_start"] > prev["frame_end"] + merge_gap:
        return False
    merged_opens = (prev.get("merged_opens") or [prev["anchor_frame"]]) + [item["anchor_frame"]]
    if max_merged_opens is not None and len(merged_opens) > max_merged_opens:
        return False
    new_start = min(prev["frame_start"], item["frame_start"])
    new_end = max(prev["frame_end"], item["frame_end"])
    if max_duration_frames is not None and (new_end - new_start) > max_duration_frames:
        return False
    return True


def propose_windows(
    gripper_measured: np.ndarray,
    *,
    fps: float,
    n_frames: int,
    calibration: F.GripperCalibration,
    arm_speed: np.ndarray | None = None,
    params: WindowCandidateParams = WindowCandidateParams(),
) -> list[WindowCandidate]:
    """Return ranked open-centered windows with pre/post context.

    `frame_end` is exclusive. Overlapping / nearby opens may be merged when
    ``merge_gap_s`` allows and ``max_duration_s`` / ``max_merged_opens`` are not
    exceeded (both unlimited under frozen defaults).
    """
    g = np.asarray(gripper_measured, dtype=float).reshape(-1)
    if n_frames <= 0:
        return []
    if len(g) != n_frames:
        n = min(len(g), n_frames)
        g = g[:n]
        n_frames = n
    if arm_speed is not None:
        arm_speed = np.asarray(arm_speed, dtype=float).reshape(-1)
        if len(arm_speed) != n_frames:
            arm_speed = arm_speed[:n_frames]

    opens = [f for kind, f in F._transitions(g, fps, calibration) if kind == "open"]
    if not opens:
        return []

    pre = max(0, int(round(params.pre_s * fps)))
    post = max(1, int(round(params.post_s * fps)))
    arm_r = max(0, int(round(params.arm_radius_s * fps)))
    merge_gap = max(0, int(round(params.merge_gap_s * fps)))
    max_duration_frames = (
        max(1, int(round(params.max_duration_s * fps)))
        if params.max_duration_s is not None
        else None
    )

    speed_thr = None
    if arm_speed is not None and len(arm_speed):
        positive = arm_speed[arm_speed > 0]
        if len(positive):
            speed_thr = float(np.percentile(positive, params.arm_speed_percentile))

    # Span of measured gripper over the episode (for relative openness in score)
    finite = g[np.isfinite(g)]
    grip_span = float(np.nanmax(finite) - np.nanmin(finite)) if len(finite) else 1.0
    if grip_span <= 1e-6:
        grip_span = 1.0

    raw: list[dict[str, Any]] = []
    for f_open in opens:
        start, end = _clip_window(f_open - pre, f_open + post, n_frames)
        if max_duration_frames is not None and (end - start) > max_duration_frames:
            # Keep anchor-centered context but enforce max duration
            half = max_duration_frames // 2
            start, end = _clip_window(f_open - half, f_open + (max_duration_frames - half), n_frames)
        near = False
        peak_speed = 0.0
        mean_speed = 0.0
        if arm_speed is not None and speed_thr is not None:
            a0, a1 = _clip_window(f_open - arm_r, f_open + arm_r + 1, n_frames)
            if a1 > a0:
                peak_speed = float(np.max(arm_speed[a0:a1]))
                mean_speed = float(np.mean(arm_speed[a0:a1]))
            near = peak_speed >= speed_thr
        measured = float(g[f_open]) if 0 <= f_open < len(g) else float("nan")
        if params.rank_prefer_compact:
            score = _activity_score(
                near=near,
                peak_speed=peak_speed,
                speed_thr=speed_thr,
                measured_gripper=measured,
                gripper_span_hint=grip_span,
            )
        else:
            # Frozen score: arm activity only (unchanged from original selector)
            score = (
                1.0
                + (1.0 if near else 0.0)
                + (min(1.0, peak_speed / (speed_thr + 1e-9)) if speed_thr else 0.0)
            )
        raw.append({
            "frame_start": start,
            "frame_end": end,
            "anchor_frame": int(f_open),
            "near_arm_activity": near,
            "score": score,
            "peak_arm_speed": peak_speed,
            "mean_arm_speed": mean_speed,
            "speed_threshold": speed_thr,
            "measured_gripper": measured,
        })

    raw.sort(key=lambda r: r["anchor_frame"])
    merged: list[dict[str, Any]] = []
    for item in raw:
        if not merged:
            item = {**item, "merged_opens": [item["anchor_frame"]]}
            merged.append(item)
            continue
        prev = merged[-1]
        if _can_merge(
            prev,
            item,
            merge_gap=merge_gap,
            max_duration_frames=max_duration_frames,
            max_merged_opens=params.max_merged_opens,
        ):
            if params.rank_prefer_compact and (
                item["score"] > prev["score"]
                or (
                    item["score"] == prev["score"]
                    and item["peak_arm_speed"] > prev["peak_arm_speed"]
                )
            ):
                prev["anchor_frame"] = item["anchor_frame"]
                prev["measured_gripper"] = item["measured_gripper"]
            # Frozen path keeps earliest open as primary anchor
            prev["frame_end"] = max(prev["frame_end"], item["frame_end"])
            prev["frame_start"] = min(prev["frame_start"], item["frame_start"])
            prev["near_arm_activity"] = prev["near_arm_activity"] or item["near_arm_activity"]
            prev["score"] = max(prev["score"], item["score"])
            prev["peak_arm_speed"] = max(prev["peak_arm_speed"], item["peak_arm_speed"])
            prev["mean_arm_speed"] = max(prev["mean_arm_speed"], item["mean_arm_speed"])
            prev.setdefault("merged_opens", [prev["anchor_frame"]]).append(item["anchor_frame"])
        else:
            item = {**item, "merged_opens": [item["anchor_frame"]]}
            merged.append(item)

    out: list[WindowCandidate] = []
    for item in merged:
        fs, fe = int(item["frame_start"]), int(item["frame_end"])
        af = int(item["anchor_frame"])
        out.append(
            WindowCandidate(
                frame_start=fs,
                frame_end=fe,
                t_start=round(fs / fps, 3),
                t_end=round(fe / fps, 3),
                anchor_frame=af,
                anchor_t=round(af / fps, 3),
                kind="open_centered",
                near_arm_activity=bool(item["near_arm_activity"]),
                score=float(item["score"]),
                features={
                    "measured_gripper": item["measured_gripper"],
                    "peak_arm_speed": item["peak_arm_speed"],
                    "mean_arm_speed": item["mean_arm_speed"],
                    "speed_threshold": item["speed_threshold"],
                    "merged_opens": item.get("merged_opens") or [af],
                    "n_frames": fe - fs,
                    "params": asdict(params),
                },
            )
        )

    if params.rank_prefer_compact:
        out.sort(
            key=lambda c: (
                -c.score,
                -float(c.features.get("peak_arm_speed") or 0.0),
                c.n_frames,
                c.anchor_frame,
            )
        )
    else:
        # Frozen sort: activity score, then earliest anchor
        out.sort(key=lambda c: (-c.score, c.anchor_frame))
    return out


def propose_windows_from_proprio(
    episode: Any,
    calibration: F.GripperCalibration,
    *,
    gripper_joint: str = "main_gripper",
    params: WindowCandidateParams = WindowCandidateParams(),
) -> list[WindowCandidate]:
    """Convenience wrapper around EpisodeProprio (proprio.load_episode)."""
    g = episode.joint(gripper_joint, kind="state")
    speed = arm_joint_speed(episode.state, episode.joint_names, exclude=(gripper_joint,))
    return propose_windows(
        g,
        fps=float(episode.fps),
        n_frames=len(g),
        calibration=calibration,
        arm_speed=speed,
        params=params,
    )


# Overlap IoU threshold for deduplicating the second (latest) pick vs rank-0.
DEFAULT_TOPK_DEDUP_IOU = 0.5


def _interval_iou(a: WindowCandidate, b: WindowCandidate) -> float:
    inter = max(0, min(a.frame_end, b.frame_end) - max(a.frame_start, b.frame_start))
    union = max(a.frame_end, b.frame_end) - min(a.frame_start, b.frame_start)
    return float(inter / union) if union > 0 else 0.0


def select_rank0_plus_latest_among_top3(
    candidates: Sequence[WindowCandidate],
    *,
    dedup_iou: float = DEFAULT_TOPK_DEDUP_IOU,
    max_windows: int = 2,
) -> list[WindowCandidate]:
    """Budget-aware pick: rank-0 plus the latest anchor among ranks 1..2.

    Developed after examining ep012 (early rank-0 missed late task activity).
    Uses only the already-ranked joint-based candidates — no labels or anomaly
    timestamps. At most ``max_windows`` (default 2). The second window is kept
    only when it is strictly later than rank-0 and does not heavily overlap
    (IoU >= dedup_iou); otherwise only rank-0 is returned.

    Does not modify ``propose_windows`` / frozen / efficient ranking.
    """
    if not candidates:
        return []
    ranked = list(candidates)
    primary = ranked[0]
    primary_out = WindowCandidate(
        frame_start=primary.frame_start,
        frame_end=primary.frame_end,
        t_start=primary.t_start,
        t_end=primary.t_end,
        anchor_frame=primary.anchor_frame,
        anchor_t=primary.anchor_t,
        kind=primary.kind,
        near_arm_activity=primary.near_arm_activity,
        score=primary.score,
        features={
            **primary.features,
            "selection_policy": "rank0_plus_latest_among_top3",
            "selection_role": "rank0",
        },
    )
    if max_windows < 2 or len(ranked) < 2:
        return [primary_out]

    pool = ranked[1: min(3, len(ranked))]
    latest = max(pool, key=lambda c: (c.anchor_frame, c.score))
    iou = _interval_iou(primary, latest)
    # Late-coverage intent: the second window must be strictly later than rank-0.
    # Otherwise it cannot extend temporal coverage (ep013-style earlier overlap).
    if latest.anchor_frame <= primary.anchor_frame:
        primary_out.features["selection_dedup"] = {
            "skipped_latest": latest.anchor_frame,
            "iou": round(iou, 3),
            "dedup_iou": dedup_iou,
            "reason": "not_later_than_rank0",
        }
        return [primary_out]
    if iou >= dedup_iou:
        primary_out.features["selection_dedup"] = {
            "skipped_latest": latest.anchor_frame,
            "iou": round(iou, 3),
            "dedup_iou": dedup_iou,
            "reason": "overlap_iou",
        }
        return [primary_out]

    secondary = WindowCandidate(
        frame_start=latest.frame_start,
        frame_end=latest.frame_end,
        t_start=latest.t_start,
        t_end=latest.t_end,
        anchor_frame=latest.anchor_frame,
        anchor_t=latest.anchor_t,
        kind=latest.kind,
        near_arm_activity=latest.near_arm_activity,
        score=latest.score,
        features={
            **latest.features,
            "selection_policy": "rank0_plus_latest_among_top3",
            "selection_role": "latest_among_top3",
            "pool_anchors": [c.anchor_frame for c in pool],
        },
    )
    return [primary_out, secondary]


def select_windows_for_episode(
    episode: Any,
    calibration: F.GripperCalibration,
    *,
    policy: str = "efficient_rank0",
    gripper_joint: str = "main_gripper",
) -> list[WindowCandidate]:
    """High-level window selection for experiments.

    Policies:
      - ``frozen_rank0``: original unlimited-merge params, take rank-0 only
      - ``efficient_rank0``: efficient params, rank-0 only
      - ``rank0_plus_latest_among_top3``: efficient params + budget top-K pick
    """
    if policy == "frozen_rank0":
        cands = propose_windows_from_proprio(
            episode, calibration, gripper_joint=gripper_joint, params=WindowCandidateParams.frozen()
        )
        return cands[:1]
    if policy == "efficient_rank0":
        cands = propose_windows_from_proprio(
            episode, calibration, gripper_joint=gripper_joint, params=WindowCandidateParams.efficient()
        )
        return cands[:1]
    if policy == "rank0_plus_latest_among_top3":
        cands = propose_windows_from_proprio(
            episode, calibration, gripper_joint=gripper_joint, params=WindowCandidateParams.efficient()
        )
        return select_rank0_plus_latest_among_top3(cands)
    raise ValueError(f"unknown window policy: {policy!r}")
