"""Regression: BotFails → stock SO-100 URDF joint conversion for web 3D replay.

Guards the wrist_flex sign fix (must match elbow_flex negation) and checks that
the recorded ep010 trajectory does not require inappropriate URDF clamping after
conversion. Uses frozen local web/public/data when present; otherwise computes
from the BotFails parquet via the export helper.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "scripts" / "export_web_demo_bundles.py"
EP010_JOINTS = ROOT / "web" / "public" / "data" / "ep010" / "joints.json"
EP010_MAPPING = ROOT / "web" / "public" / "data" / "ep010" / "mapping.json"
BOTFAILS = (
    ROOT
    / "data"
    / "lerobot"
    / "kantine__BotFails"
    / "test"
    / "domotic_dishTidyUp_anomaly"
)

LIMITS = {
    "shoulder_pan": (-2.0, 2.0),
    "shoulder_lift": (0.0, 3.5),
    "elbow_flex": (-3.14158, 0.0),
    "wrist_flex": (-2.5, 1.2),
    "wrist_roll": (-3.14158, 3.14158),
    "gripper": (-0.2, 2.0),
}
URDF_JOINTS = list(LIMITS.keys())


def _load_export_module():
    spec = importlib.util.spec_from_file_location("export_web_demo_bundles", EXPORT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def export_mod():
    return _load_export_module()


def test_wrist_flex_sign_matches_elbow_negation(export_mod):
    """wrist_flex must use -deg2rad like elbow_flex (BotFails flex convention)."""
    # Synthetic motors in the observed BotFails wrist range that formerly OOB'd.
    motor = np.array(
        [
            [0.0, 90.0, 90.0, 85.43, 0.0, 10.0],
            [0.0, 60.0, 80.0, 105.0, 0.0, 20.0],
        ],
        dtype=float,
    )
    clamped, raw = export_mod.motor_to_urdf_rad(motor)
    wrist_i = URDF_JOINTS.index("wrist_flex")
    elbow_i = URDF_JOINTS.index("elbow_flex")
    assert np.allclose(raw[:, wrist_i], -np.deg2rad(motor[:, 3]))
    assert np.allclose(raw[:, elbow_i], -np.deg2rad(motor[:, 2]))
    # Former bug: +deg2rad(85.43) ≈ 1.491 > URDF upper 1.2 → clamp.
    assert raw[0, wrist_i] < -1.4
    assert not np.any(
        (raw[:, wrist_i] < LIMITS["wrist_flex"][0])
        | (raw[:, wrist_i] > LIMITS["wrist_flex"][1])
    )
    assert np.allclose(clamped[:, wrist_i], raw[:, wrist_i])


def test_mapping_json_documents_wrist_negation():
    if not EP010_MAPPING.is_file():
        pytest.skip("web ep010 mapping not exported")
    mapping = json.loads(EP010_MAPPING.read_text(encoding="utf-8"))
    by_urdf = {t["urdf"]: t["formula"] for t in mapping["transform"]}
    assert "-deg2rad" in by_urdf["wrist_flex"]
    assert "-deg2rad" in by_urdf["elbow_flex"]
    assert by_urdf["wrist_flex"] == "urdf = -deg2rad(motor)"
    assert mapping["out_of_limit_frames"]["wrist_flex"] == 0


@pytest.mark.skipif(not EP010_JOINTS.is_file(), reason="web ep010 joints not exported")
def test_ep010_exported_trajectory_has_no_wrist_clamping():
    joints = json.loads(EP010_JOINTS.read_text(encoding="utf-8"))
    mapping = json.loads(EP010_MAPPING.read_text(encoding="utf-8"))
    motor = np.array(joints["motor_deg"], dtype=float)
    urdf = np.array(joints["urdf_rad"], dtype=float)
    assert motor.shape == urdf.shape == (2090, 6)

    expect_wrist = -np.deg2rad(motor[:, 3])
    expect_elbow = -np.deg2rad(motor[:, 2])
    expect_pan = -np.deg2rad(motor[:, 0])
    expect_lift = np.deg2rad(motor[:, 1])
    expect_roll = np.deg2rad(motor[:, 4])
    expect_grip = (motor[:, 5] / 100.0) * math.pi

    assert np.allclose(urdf[:, 0], expect_pan, atol=1e-4)
    assert np.allclose(urdf[:, 1], expect_lift, atol=1e-4)
    assert np.allclose(urdf[:, 2], expect_elbow, atol=1e-4)
    assert np.allclose(urdf[:, 3], expect_wrist, atol=1e-4)
    assert np.allclose(urdf[:, 4], expect_roll, atol=1e-4)
    assert np.allclose(urdf[:, 5], expect_grip, atol=1e-4)

    # No inappropriate clamping on wrist for this recorded trajectory.
    assert mapping["out_of_limit_frames"]["wrist_flex"] == 0
    lo, hi = LIMITS["wrist_flex"]
    assert int(np.sum((expect_wrist < lo) | (expect_wrist > hi))) == 0


@pytest.mark.skipif(
    not (BOTFAILS / "meta" / "info.json").is_file(),
    reason="BotFails dataset not available locally",
)
def test_motor_to_urdf_matches_live_ep010_export(export_mod):
    """Fresh conversion from parquet must match committed web joints for wrist."""
    sys.path.insert(0, str(ROOT))
    from proprio import load_episode

    ep = load_episode(BOTFAILS, 10)
    clamped, raw = export_mod.motor_to_urdf_rad(ep.state)
    wrist_i = URDF_JOINTS.index("wrist_flex")
    assert export_mod.LIMITS["wrist_flex"] == LIMITS["wrist_flex"]
    assert int(
        np.sum(
            (raw[:, wrist_i] < LIMITS["wrist_flex"][0])
            | (raw[:, wrist_i] > LIMITS["wrist_flex"][1])
        )
    ) == 0
    assert np.allclose(clamped[:, wrist_i], raw[:, wrist_i])

    if EP010_JOINTS.is_file():
        exported = np.array(
            json.loads(EP010_JOINTS.read_text(encoding="utf-8"))["urdf_rad"],
            dtype=float,
        )
        assert np.allclose(exported[:, wrist_i], clamped[:, wrist_i], atol=1e-4)
