"""Proprio loader tests on the downloaded SO-101 episode (local files only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import proprio

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_videos" / "sample.mp4"
pytestmark = pytest.mark.skipif(
    not (proprio.SO101_SAMPLE_DIR / "SOURCE.json").is_file(), reason="LeRobot episode not downloaded"
)


@pytest.fixture(scope="module")
def ep():
    return proprio.load_episode()


def test_joint_names_come_from_dataset_metadata(ep):
    assert ep.joint_names[-1] == "gripper.pos" and len(ep.joint_names) == 6
    with pytest.raises(KeyError):
        ep.joint("gripper")  # no guessed aliases


def test_rows_align_one_to_one_with_video_frames(ep):
    assert proprio.check_video_alignment(ep, video_frames=737, video_fps=30.0) == []
    assert proprio.check_video_alignment(ep, video_frames=736, video_fps=30.0)


@pytest.mark.skipif(not SAMPLE.is_file(), reason="sample video not downloaded")
def test_local_video_is_the_paired_dataset_video(ep):
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == ep.source["paired_video"]["sha256"]


def test_tampered_file_is_rejected(tmp_path):
    src = proprio.SO101_SAMPLE_DIR
    for rel in ("meta/info.json", "data/chunk-000/episode_000000.parquet"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes((src / rel).read_bytes())
    meta = json.loads((src / "SOURCE.json").read_text())
    meta["files"]["data/chunk-000/episode_000000.parquet"]["sha256"] = "0" * 64
    (tmp_path / "SOURCE.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        proprio.load_episode(tmp_path)


def test_measured_gripper_plateaus_match_inspection(ep):
    # Values observed during manual inspection (2026-10-26); guards against
    # silently loading the wrong column or episode.
    g = ep.joint("gripper.pos")
    cmd = ep.joint("gripper.pos", kind="action")
    assert np.allclose(g[[0, 680]], 0.78, atol=0.01)
    assert np.allclose(g[340:490], 6.44, atol=0.01)
    # Commanded nearly closed while measured stays at 6.44. (The opening command
    # starts a few frames before the measured state moves at ~frame 490.)
    assert cmd[340:470].max() < 1.0
