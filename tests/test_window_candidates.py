"""Deterministic tests for window_candidates (no network, no paid APIs)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import failures as F
import proprio
import window_candidates as W

ROOT = Path(__file__).resolve().parents[1]
BOTFAILS = ROOT / "data/lerobot/kantine__BotFails/test/domotic_dishTidyUp_anomaly"
CAL_PATH = ROOT / "data/calibration/so100_botfails_gripper.json"
FPS = 30.0

CAL = F.GripperCalibration(
    "test",
    "unit-test",
    holding_detectable=False,
    persist_s=0.15,
    detector="relative_rise",
    open_rise_frac=0.15,
    noise_mult=5.0,
    baseline_s=0.5,
    settle_frac=0.02,
    settle_noise_mult=2.0,
    close_settle_frac=0.05,
    close_band_frac=0.25,
)


def _square_open(n, opens, closed=1.0, opened=40.0):
    g = np.full(n, closed, dtype=float)
    for a, b in opens:
        g[a:b] = opened
    return g


def test_propose_windows_includes_pre_post_context():
    g = _square_open(400, [(120, 160)])
    cands = W.propose_windows(
        g, fps=FPS, n_frames=400, calibration=CAL,
        params=W.WindowCandidateParams(pre_s=1.0, post_s=3.0),
    )
    assert len(cands) == 1
    c = cands[0]
    assert c.kind == "open_centered"
    assert c.anchor_frame == 120
    assert c.frame_start == 120 - 30  # 1.0 s * 30
    assert c.frame_end == 120 + 90  # 3.0 s * 30
    assert c.t_start == pytest.approx(c.frame_start / FPS)
    assert c.t_end == pytest.approx(c.frame_end / FPS)


def test_arm_activity_boosts_score_and_flag():
    # Separate opens far enough that windows do not merge (merge_gap=1.5s)
    g = _square_open(500, [(120, 160), (350, 390)])
    speed = np.zeros(500)
    speed[110:130] = 5.0  # activity near first open only
    speed[200] = 0.5  # ensure a positive distribution for percentile
    cands = W.propose_windows(
        g, fps=FPS, n_frames=500, calibration=CAL, arm_speed=speed,
        params=W.WindowCandidateParams(
            pre_s=1.0, post_s=3.0, arm_speed_percentile=50, merge_gap_s=0.5
        ),
    )
    assert len(cands) >= 2
    by_anchor = {c.anchor_frame: c for c in cands}
    assert 120 in by_anchor and 350 in by_anchor
    assert by_anchor[120].near_arm_activity is True
    assert by_anchor[350].near_arm_activity is False
    assert by_anchor[120].score > by_anchor[350].score


def test_nearby_opens_merge():
    # Close, then reopen — leave enough closed frames for a second open detection
    g = _square_open(400, [(100, 130), (160, 200)])
    cands = W.propose_windows(
        g, fps=FPS, n_frames=400, calibration=CAL,
        params=W.WindowCandidateParams(pre_s=1.0, post_s=3.0, merge_gap_s=2.0),
    )
    assert len(cands) == 1
    assert cands[0].frame_start <= 70
    assert cands[0].frame_end >= 160 + 90
    merged = cands[0].features.get("merged_opens") or []
    assert len(merged) >= 2


def test_max_duration_blocks_chain_merge():
    """Configurable max duration keeps consecutive opens as separate candidates."""
    g = _square_open(500, [(100, 130), (160, 190), (220, 250)])
    # Without cap, merge_gap=2s would chain these into one long window
    uncapped = W.propose_windows(
        g, fps=FPS, n_frames=500, calibration=CAL,
        params=W.WindowCandidateParams(pre_s=1.0, post_s=3.0, merge_gap_s=2.0),
    )
    assert len(uncapped) == 1
    assert uncapped[0].n_frames > 120

    capped = W.propose_windows(
        g, fps=FPS, n_frames=500, calibration=CAL,
        params=W.WindowCandidateParams(
            pre_s=1.0, post_s=3.0, merge_gap_s=2.0, max_duration_s=4.0, max_merged_opens=2
        ),
    )
    assert len(capped) >= 2
    assert all(c.n_frames <= 120 for c in capped)


def test_efficient_profile_preserves_pre_post_and_limits_length():
    g = _square_open(600, [(120, 150), (200, 230), (280, 310), (400, 430)])
    frozen = W.propose_windows(
        g, fps=FPS, n_frames=600, calibration=CAL, params=W.WindowCandidateParams.frozen(),
    )
    efficient = W.propose_windows(
        g, fps=FPS, n_frames=600, calibration=CAL, params=W.WindowCandidateParams.efficient(),
    )
    assert efficient
    assert all(c.n_frames <= int(round(W.EFFICIENT_MAX_DURATION_S * FPS)) for c in efficient)
    # Efficient should not collapse everything into one mega-window when opens are spaced
    assert len(efficient) >= len(frozen) or all(c.n_frames <= 120 for c in efficient)
    # Context around each efficient anchor still present when in-bounds
    for c in efficient:
        assert c.frame_start <= c.anchor_frame < c.frame_end
        if c.anchor_frame >= 30:
            assert c.anchor_frame - c.frame_start >= 25  # ~pre_s


def test_frozen_defaults_unchanged():
    p = W.WindowCandidateParams.frozen()
    assert p.merge_gap_s == W.DEFAULT_MERGE_GAP_S == 1.5
    assert p.max_duration_s is None
    assert p.max_merged_opens is None
    assert p.rank_prefer_compact is False
    assert p.pre_s == 1.0 and p.post_s == 3.0


def test_no_opens_yields_empty():
    g = np.full(200, 1.0)
    assert W.propose_windows(g, fps=FPS, n_frames=200, calibration=CAL) == []


def test_clips_to_episode_bounds():
    # Open after baseline_s so relative-rise can fire; pre-context clips to 0
    g = _square_open(150, [(40, 90)])
    cands = W.propose_windows(
        g, fps=FPS, n_frames=150, calibration=CAL,
        params=W.WindowCandidateParams(pre_s=2.0, post_s=3.0),
    )
    assert cands
    assert cands[0].frame_start == 0
    assert cands[0].frame_end <= 150


def test_arm_joint_speed_excludes_gripper():
    state = np.zeros((10, 3))
    state[:, 0] = np.arange(10)  # moving
    state[:, 2] = np.arange(10) * 10  # gripper moving a lot
    speed = W.arm_joint_speed(state, ["a", "b", "main_gripper"], exclude=("main_gripper",))
    assert speed[0] == 0
    assert speed[1] == pytest.approx(1.0)


@pytest.mark.skipif(not (BOTFAILS / "data/chunk-000/episode_000000.parquet").is_file(),
                    reason="BotFails ep000 joints not present")
def test_dev_ep000_proposes_open_centered_windows():
    """Development episode only — smoke that real joints produce candidates."""
    import json

    cal_raw = json.loads(CAL_PATH.read_text(encoding="utf-8"))
    cal = F.GripperCalibration(
        cal_raw["source"], cal_raw["basis"], bool(cal_raw["holding_detectable"]),
        persist_s=float(cal_raw.get("persist_s", 0.15)),
        detector=str(cal_raw.get("detector", "relative_rise")),
        open_sign=int(cal_raw.get("open_sign", 1)),
        open_rise_frac=float(cal_raw.get("open_rise_frac", 0.15)),
        noise_mult=float(cal_raw.get("noise_mult", 5.0)),
        baseline_s=float(cal_raw.get("baseline_s", 0.5)),
        settle_frac=float(cal_raw.get("settle_frac", 0.02)),
        settle_noise_mult=float(cal_raw.get("settle_noise_mult", 2.0)),
        close_settle_frac=float(cal_raw.get("close_settle_frac", 0.05)),
        close_band_frac=float(cal_raw.get("close_band_frac", 0.25)),
    )
    ep = proprio.load_episode(BOTFAILS, episode_index=0)
    cands = W.propose_windows_from_proprio(ep, cal)
    assert cands, "ep000 (dev success) should yield at least one open-centered window"
    for c in cands:
        assert c.frame_end > c.frame_start
        assert 0 <= c.frame_start < c.frame_end <= len(ep.frame_index)
        # Context present when room allows
        assert c.frame_end - c.anchor_frame >= 1


@pytest.mark.skipif(not (BOTFAILS / "data/chunk-000/episode_000010.parquet").is_file(),
                    reason="BotFails ep010 joints not present")
def test_dev_ep010_includes_window_covering_manual_open_1335():
    """Dev episode: a candidate should cover the known measured open near frame 1335."""
    import json

    cal_raw = json.loads(CAL_PATH.read_text(encoding="utf-8"))
    cal = F.GripperCalibration(
        cal_raw["source"], cal_raw["basis"], bool(cal_raw["holding_detectable"]),
        persist_s=float(cal_raw.get("persist_s", 0.15)),
        detector=str(cal_raw.get("detector", "relative_rise")),
        open_sign=int(cal_raw.get("open_sign", 1)),
        open_rise_frac=float(cal_raw.get("open_rise_frac", 0.15)),
        noise_mult=float(cal_raw.get("noise_mult", 5.0)),
        baseline_s=float(cal_raw.get("baseline_s", 0.5)),
        settle_frac=float(cal_raw.get("settle_frac", 0.02)),
        settle_noise_mult=float(cal_raw.get("settle_noise_mult", 2.0)),
        close_settle_frac=float(cal_raw.get("close_settle_frac", 0.05)),
        close_band_frac=float(cal_raw.get("close_band_frac", 0.25)),
    )
    ep = proprio.load_episode(BOTFAILS, episode_index=10)
    cands = W.propose_windows_from_proprio(ep, cal)
    assert cands
    # Manual analysis window was 1260–1381 with open @1335
    hit = [c for c in cands if c.frame_start <= 1335 < c.frame_end]
    assert hit, f"no candidate covers frame 1335; got {[(c.frame_start, c.frame_end, c.anchor_frame) for c in cands]}"


def _fake_cand(anchor: int, score: float, *, start: int | None = None, end: int | None = None):
    fs = start if start is not None else max(0, anchor - 30)
    fe = end if end is not None else anchor + 90
    return W.WindowCandidate(
        frame_start=fs,
        frame_end=fe,
        t_start=fs / FPS,
        t_end=fe / FPS,
        anchor_frame=anchor,
        anchor_t=anchor / FPS,
        kind="open_centered",
        near_arm_activity=True,
        score=score,
        features={"measured_gripper": True},
    )


def test_rank0_plus_latest_among_top3_picks_two():
    """Policy: rank-0 plus latest anchor among ranks 1..2; max two windows."""
    ranked = [
        _fake_cand(100, 3.2),
        _fake_cand(500, 3.1),
        _fake_cand(800, 3.0),  # latest among top3
        _fake_cand(900, 2.9),  # outside top3 — ignored
    ]
    picked = W.select_rank0_plus_latest_among_top3(ranked)
    assert len(picked) == 2
    assert picked[0].anchor_frame == 100
    assert picked[1].anchor_frame == 800
    assert all(c.n_frames <= 120 for c in picked)
    assert picked[0].features["selection_policy"] == "rank0_plus_latest_among_top3"
    assert picked[1].features["selection_role"] == "latest_among_top3"


def test_rank0_plus_latest_dedups_overlapping():
    ranked = [
        _fake_cand(100, 3.2, start=70, end=190),
        _fake_cand(110, 3.1, start=80, end=200),  # heavy overlap with rank0
        _fake_cand(400, 3.0, start=370, end=490),
    ]
    # Among ranks 1..2, latest is 400 — no overlap with rank0 → two windows
    picked = W.select_rank0_plus_latest_among_top3(ranked)
    assert len(picked) == 2
    assert picked[1].anchor_frame == 400

    # When latest among top3 overlaps rank0 heavily, keep only rank0
    overlapping = [
        _fake_cand(100, 3.2, start=70, end=190),
        _fake_cand(105, 3.1, start=75, end=195),
        _fake_cand(108, 3.0, start=78, end=198),
    ]
    picked2 = W.select_rank0_plus_latest_among_top3(overlapping)
    assert len(picked2) == 1
    assert picked2[0].anchor_frame == 100
    assert "selection_dedup" in picked2[0].features
    assert picked2[0].features["selection_dedup"]["reason"] == "overlap_iou"


def test_rank0_plus_latest_drops_earlier_overlapping_secondary():
    """Secondary among ranks 1..2 that is not later than rank-0 is dropped.

    Label-independent late-coverage rule (motivated by ep013-style plans).
    """
    ranked = [
        _fake_cand(1528, 3.17, start=1498, end=1618),
        _fake_cand(1249, 3.16, start=1219, end=1339),
        _fake_cand(1481, 3.15, start=1451, end=1571),  # latest in pool, still earlier
        _fake_cand(1671, 3.14, start=1641, end=1761),  # later but outside top-3
    ]
    picked = W.select_rank0_plus_latest_among_top3(ranked)
    assert len(picked) == 1
    assert picked[0].anchor_frame == 1528
    assert picked[0].features["selection_dedup"]["reason"] == "not_later_than_rank0"
    assert picked[0].features["selection_dedup"]["skipped_latest"] == 1481


def test_rank0_plus_latest_empty_and_single():
    assert W.select_rank0_plus_latest_among_top3([]) == []
    one = [_fake_cand(50, 1.0)]
    assert len(W.select_rank0_plus_latest_among_top3(one)) == 1


def test_efficient_windows_respect_max_four_seconds():
    g = _square_open(800, [(100, 130), (200, 230), (400, 430), (600, 630)])
    cands = W.propose_windows(
        g, fps=FPS, n_frames=800, calibration=CAL, params=W.WindowCandidateParams.efficient()
    )
    picked = W.select_rank0_plus_latest_among_top3(cands)
    assert len(picked) <= 2
    assert all(c.n_frames <= int(round(W.EFFICIENT_MAX_DURATION_S * FPS)) for c in picked)
    assert all((c.t_end - c.t_start) <= W.EFFICIENT_MAX_DURATION_S + 1e-6 for c in picked)


def test_select_windows_policy_names():
    with pytest.raises(ValueError):
        W.select_windows_for_episode(object(), CAL, policy="not_a_policy")
