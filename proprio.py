"""LeRobot proprioception for DemoDoctor episodes (read-only, local files).

Joint names come from the dataset's own meta/info.json; nothing is hardcoded.
`observation.state` is the measured joint position; `action` is the command the
policy/teleoperator sent. A command is not evidence that the motion happened.
Units are not declared by the dataset and are left as-is.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

LEROBOT_ROOT = Path(__file__).parent / "data" / "lerobot"
SO101_SAMPLE_DIR = LEROBOT_ROOT / "ankithreddy__so101_pickplace_uno"


@dataclass
class EpisodeProprio:
    episode_index: int
    fps: float
    frame_index: np.ndarray
    timestamp_s: np.ndarray
    state: np.ndarray  # (n, joints) measured
    action: np.ndarray  # (n, joints) commanded
    joint_names: list[str]
    source: dict[str, Any] = field(default_factory=dict)

    def joint(self, name: str, *, kind: str = "state") -> np.ndarray:
        """One joint's series by its dataset name, e.g. 'gripper.pos'."""
        if name not in self.joint_names:
            raise KeyError(f"{name!r} not in dataset joint names {self.joint_names}")
        arr = self.state if kind == "state" else self.action
        return arr[:, self.joint_names.index(name)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_episode(dataset_dir: Path = SO101_SAMPLE_DIR, episode_index: int = 0) -> EpisodeProprio:
    import pandas as pd

    info = json.loads((dataset_dir / "meta" / "info.json").read_text(encoding="utf-8"))
    rel = info["data_path"].format(episode_chunk=episode_index // info["chunks_size"], episode_index=episode_index)
    path = dataset_dir / rel
    source = {}
    source_file = dataset_dir / "SOURCE.json"
    if source_file.is_file():
        source = json.loads(source_file.read_text(encoding="utf-8"))
        expected = source.get("files", {}).get(rel, {}).get("sha256")
        if expected and expected != _sha256(path):
            raise ValueError(f"{path} does not match the sha256 recorded in SOURCE.json")

    state_names = info["features"]["observation.state"]["names"]
    if info["features"]["action"]["names"] != state_names:
        raise ValueError("state and action joint names differ; refusing to pair them")

    df = pd.read_parquet(path)
    return EpisodeProprio(
        episode_index=episode_index,
        fps=float(info["fps"]),
        frame_index=df["frame_index"].to_numpy(),
        timestamp_s=df["timestamp"].to_numpy(dtype=float),
        state=np.stack(df["observation.state"].to_numpy()).astype(float),
        action=np.stack(df["action"].to_numpy()).astype(float),
        joint_names=list(state_names),
        source=source,
    )


def download_episode(
    repo_id: str,
    *,
    dataset_subdir: str,
    episode_index: int,
    out_dir: Path,
    paired_video_local: Path | None = None,
    camera: str | None = None,
    extra_files: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Copy one LeRobot episode's joint data + metadata from the Hugging Face Hub (free).

    Writes unmodified copies under out_dir (mirroring dataset_subdir) and records
    provenance in out_dir/SOURCE.json: revision, license, sha256 of every file and,
    if given, the sha256 of the local video plus whether it matches the dataset's
    video for `camera`. No local cache paths are recorded.
    """
    import shutil

    from huggingface_hub import HfApi, hf_hub_download

    info = HfApi().dataset_info(repo_id)
    revision = info.sha
    license_ = (info.card_data.to_dict() if info.card_data else {}).get("license")
    prefix = f"{dataset_subdir.strip('/')}/" if dataset_subdir else ""
    meta_rel = "meta/info.json"
    meta_path = Path(hf_hub_download(repo_id, prefix + meta_rel, repo_type="dataset", revision=revision))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    chunk = episode_index // meta["chunks_size"]
    rels = [meta_rel, "meta/episodes.jsonl", "meta/tasks.jsonl",
            meta["data_path"].format(episode_chunk=chunk, episode_index=episode_index), *extra_files]

    source_file = out_dir / "SOURCE.json"
    source = json.loads(source_file.read_text(encoding="utf-8")) if source_file.is_file() else {
        "repo_id": repo_id, "repo_type": "dataset", "dataset_subdir": dataset_subdir,
        "license": license_, "revision": revision, "files": {}, "paired_videos": {},
        "attribution": f"Unmodified copies of files from the Hugging Face dataset {repo_id} ({license_}).",
    }
    if source.get("revision") != revision:
        raise ValueError(f"{out_dir} holds revision {source.get('revision')}, hub is at {revision}; refusing to mix")
    for rel in rels:
        cached = Path(hf_hub_download(repo_id, prefix + rel, repo_type="dataset", revision=revision))
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copyfile(cached, dst)
        source["files"][rel] = {"sha256": _sha256(dst), "bytes": dst.stat().st_size}

    if paired_video_local is not None and camera:
        video_rel = meta["video_path"].format(episode_chunk=chunk, video_key=camera, episode_index=episode_index)
        remote_video = Path(hf_hub_download(repo_id, prefix + video_rel, repo_type="dataset", revision=revision))
        local_sha = _sha256(paired_video_local)
        source["paired_videos"][str(episode_index)] = {
            "filename": video_rel, "camera": camera, "local": paired_video_local.as_posix(),
            "sha256": local_sha, "matches_dataset_file": local_sha == _sha256(remote_video),
        }
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(json.dumps(source, indent=2), encoding="utf-8")
    return source


def check_video_alignment(ep: EpisodeProprio, *, video_frames: int, video_fps: float) -> list[str]:
    """Problems preventing a 1:1 row-to-video-frame mapping (empty list = aligned)."""
    problems = []
    if len(ep.frame_index) != video_frames:
        problems.append(f"{len(ep.frame_index)} rows vs {video_frames} video frames")
    if not np.array_equal(ep.frame_index, np.arange(len(ep.frame_index))):
        problems.append("frame_index is not contiguous from 0")
    if abs(ep.fps - video_fps) > 1e-6:
        problems.append(f"dataset fps {ep.fps} vs video fps {video_fps}")
    drift = float(np.max(np.abs(ep.timestamp_s - ep.frame_index / ep.fps))) if len(ep.frame_index) else 0.0
    if drift > 0.5 / ep.fps:
        problems.append(f"timestamps drift up to {drift:.4f}s from frame_index/fps")
    return problems
