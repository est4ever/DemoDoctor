"""Deterministic tests for gripper opening detectors (no datasets, no network)."""

from __future__ import annotations

import numpy as np
import pytest

import failures as F

FPS = 30.0
CAL = F.GripperCalibration(
    "test",
    "unit-test calibration",
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


def opens(g, cal=CAL, fps=FPS):
    return [f for k, f in F._transitions(np.asarray(g, dtype=float), fps, cal) if k == "open"]


def closes(g, cal=CAL, fps=FPS):
    return [f for k, f in F._transitions(np.asarray(g, dtype=float), fps, cal) if k == "close"]


def square_open(n, ranges, closed=1.0, opened=30.0):
    g = np.full(n, closed, dtype=float)
    for a, b in ranges:
        g[a:b] = opened
    return g


# --- relative-rise behavior ----------------------------------------------------

def test_full_opening_detected():
    g = square_open(300, [(60, 120)])
    assert opens(g) == [60]
    assert closes(g)  # returns to closed after the pulse


def test_partial_opening_25_to_60_percent_of_range_detected():
    """Partial opens of 25–60% of the measured span must fire; sub-threshold must not."""
    for frac in (0.25, 0.40, 0.60):
        # Brief full excursion establishes span=100; the partial pulse is the event under test.
        g = np.full(400, 0.0)
        g[20:40] = 100.0
        g[40:60] = 0.0
        g[120:180] = frac * 100.0
        got = [f for f in opens(g) if f >= 100]
        assert got and 115 <= got[0] <= 130, f"frac={frac} opens={got}"

    # 10% of an established span is below open_rise_frac=0.15 → not an opening
    g = np.full(400, 0.0)
    g[20:40] = 100.0
    g[40:60] = 0.0
    g[120:180] = 10.0
    assert [f for f in opens(g) if f >= 100] == []


def test_gradual_opening_detected():
    """A multi-second ramp still opens once it clears the relative threshold."""
    g = np.full(300, 1.0)
    # Ramp 1 → 40 over 60 frames (~2 s); span ≈ 39 → thr ≈ 5.85
    g[60:120] = np.linspace(1.0, 40.0, 60)
    g[120:180] = 40.0
    g[180:] = 1.0
    got = opens(g)
    assert len(got) == 1
    # First frame where value exceeds baseline(~1) + 0.15*span
    assert 60 <= got[0] <= 100


def test_sub_noise_jitter_and_slow_drift_not_detected():
    rng = np.random.default_rng(0)
    g = 5.0 + 0.05 * rng.normal(size=400)  # tiny jitter; span small but rise never sustained above frac*span meaningfully
    # Force a known small span with slow drift of 5% over the episode
    g = np.linspace(0.0, 5.0, 400) + 0.1 * rng.normal(size=400)
    assert opens(g) == []


def test_command_only_changes_ignored():
    """Detector reads measured only; commanded motion without measured rise is ignored."""
    measured = np.full(300, 1.0)
    # No opens on measured
    assert opens(measured) == []
    # localize_failures also must not treat command as a release
    track = F.ObjectTrack("item:0", "item", [
        F.TrackObs(f, 100, 100, 100, "outside") for f in range(0, 61)
    ] + [
        F.TrackObs(f, x, 100, 100, "unknown") for f, x in zip(range(61, 101), np.linspace(110, 500, 40))
    ] + [
        F.TrackObs(f, 500, 100, 100, "outside") for f in range(101, 300)
    ])
    cmd = np.full(300, 1.0)
    cmd[90:140] = 30.0  # command opens during the move; measured stays closed
    cal = CAL
    r = F.localize_failures(
        F.TaskSpec("t", "t", (F.ObjectSpec("item", 1),), "box"),
        [track], fps=FPS, n_frames=300,
        gripper=F.GripperSignal(measured, cmd, cal),
    )
    e = r.physical_events[0]
    assert e.subtype == "no_measured_release"
    assert not any(c.get("type") == "gripper_open" for ev in e.evidence for c in ev.claims)


def test_unit_scale_and_offset_invariance():
    base = square_open(300, [(70, 130)], closed=2.0, opened=40.0)
    a = opens(base)
    b = opens(base * 3.0 + 10.0)
    c = opens(-base, cal=F.GripperCalibration(
        "test", "inverted joint", False, open_sign=-1,
        open_rise_frac=0.15, noise_mult=5.0, close_band_frac=0.25))
    assert a and a == b == c


def test_so101_like_and_so100_like_ranges():
    """Same relative motion on 0–27 and 0–90 spans yields openings at the same frames."""
    def pulse(hi):
        g = np.full(300, 0.05 * hi)
        g[90:150] = 0.55 * hi  # 50% partial open
        return g

    assert opens(pulse(27.0)) == opens(pulse(90.0))


def test_opening_without_object_motion_is_measurement_only():
    """Gripper opens while the object stays put: no drop event; opens are still detectable."""
    g = square_open(300, [(50, 100)])
    assert opens(g)
    still = F.ObjectTrack("item:0", "item",
                          [F.TrackObs(f, 100, 100, 100, "outside") for f in range(300)])
    r = F.localize_failures(
        F.TaskSpec("t", "t", (F.ObjectSpec("item", 1),), "box"),
        [still], fps=FPS, n_frames=300,
        gripper=F.GripperSignal(g, g.copy(), CAL),
    )
    assert r.physical_events == []


def test_measured_opening_does_not_alone_prove_drop():
    """Drop inference requires rest-outside + opening; wording must not claim proof."""
    track = F.ObjectTrack("item:0", "item", [
        F.TrackObs(f, 100, 100, 100, "outside") for f in range(0, 61)
    ] + [
        F.TrackObs(f, x, 100, 100, "unknown") for f, x in zip(range(61, 101), np.linspace(110, 500, 40))
    ] + [
        F.TrackObs(f, 500, 100, 100, "outside") for f in range(101, 300)
    ])
    g = square_open(300, [(40, 60), (95, 140)])
    r = F.localize_failures(
        F.TaskSpec("t", "t", (F.ObjectSpec("item", 1),), "box"),
        [track], fps=FPS, n_frames=300,
        gripper=F.GripperSignal(g, g.copy(), CAL),
    )
    e = r.physical_events[0]
    assert e.kind == "dropped_in_transport" and e.status == "inferred"
    assert e.subtype == "released_outside_target"
    assert any("not by itself proof" in u.lower() for u in e.uncertainties)


# --- midpoint regression -------------------------------------------------------

def test_midpoint_detector_still_available_for_comparison():
    g = square_open(300, [(60, 120)], closed=1.0, opened=30.0)
    mid_cal = F.GripperCalibration("test", "midpoint", False, detector="midpoint", persist_s=0.15)
    assert F._transitions_midpoint(g, FPS, mid_cal) == F._transitions(g, FPS, mid_cal)
    # Midpoint misses a partial open that stays below mid (same failure mode as ep010)
    partial = np.full(300, 0.5)
    partial[100:160] = 19.0  # peak below mid once a later high establishes the range
    partial[200:220] = 50.0  # establishes max → mid ≈ 25.25; 19 never crosses mid
    mid_opens = opens(partial, mid_cal)
    assert not any(95 <= f <= 110 for f in mid_opens)
    assert any(f >= 195 for f in mid_opens)  # the full excursion still crosses mid
    rel = [f for f in opens(partial, CAL) if f < 180]
    assert rel and 95 <= rel[0] <= 110
