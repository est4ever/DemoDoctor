"""Export compact SAM window caches for offline DemoDoctor Analysis replay.

Copies BotFails window track JSON for primary demo episodes (~200KB each).
Does not copy videos, full tracking trees, or API keys.
Writes relative-path manifests only (no machine-local absolute paths).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Analysis windows used for SAM overlays in demo_replay (matched Muse window).
EPISODES = {
    "ep010": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep010.mp4",
        "window": [1260, 1381],
        "example_id": "botfails_dish_test_ep010",
        "episode_index": 10,
    },
    "ep003": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep003.mp4",
        "window": [1845, 1965],
        "example_id": "botfails_dish_test_ep003",
        "episode_index": 3,
    },
    "ep013": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep013.mp4",
        "window": [1498, 1618],
        "example_id": "botfails_dish_test_ep013",
        "episode_index": 13,
    },
    "ep005": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep005.mp4",
        "window": [1607, 1727],
        "example_id": "botfails_dish_test_ep005",
        "episode_index": 5,
    },
    "ep006": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep006.mp4",
        "window": [1500, 1620],
        "example_id": "botfails_dish_test_ep006",
        "episode_index": 6,
    },
    # Archive episodes still installable for continuity
    "ep001": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep001.mp4",
        "window": [1203, 1324],
        "example_id": "botfails_dish_test_ep001",
        "episode_index": 1,
    },
    "ep011": {
        "video_rel": "eval_videos/botfails/botfails_dish_test_ep011.mp4",
        "window": [1518, 1639],
        "example_id": "botfails_dish_test_ep011",
        "episode_index": 11,
    },
}


def main() -> None:
    out = ROOT / "data" / "demo_cache"
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for key, meta in EPISODES.items():
        video = ROOT / meta["video_rel"]
        if not video.is_file():
            raise SystemExit(f"Missing video for export: {video}")
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        digest16 = digest[:16]
        start, end = meta["window"]
        src = (
            ROOT / "data" / "tracking" / "chunks" / digest16
            / f"f{start:06d}-{end:06d}" / "green_plate.json"
        )
        if not src.is_file():
            raise SystemExit(f"Missing SAM chunk cache: {src}")
        dest_dir = out / key / "sam_window"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "green_plate.json"
        shutil.copy2(src, dest)
        entry = {
            "episode_key": key,
            "example_id": meta["example_id"],
            "episode_index": meta["episode_index"],
            "video_rel": meta["video_rel"].replace("\\", "/"),
            "video_sha256": digest,
            "tracking_digest16": digest16,
            "window_frames": meta["window"],
            "sam_window_rel": str(dest.relative_to(ROOT)).replace("\\", "/"),
            "install_chunk_rel": (
                f"data/tracking/chunks/{digest16}/"
                f"f{start:06d}-{end:06d}/green_plate.json"
            ),
            "bytes": dest.stat().st_size,
            "dataset": {
                "repo_id": "kantine/BotFails",
                "license": "apache-2.0",
                "revision": "3478e49d91e1737eb76dfee2d81bb22617039c13",
                "camera": "observation.images.logitech_1",
                "attribution": (
                    "SAM window tracks were computed locally with Meta SAM 3.1 for DemoDoctor. "
                    "Source videos/joints: Hugging Face kantine/BotFails (Apache-2.0). "
                    "Redistribute dataset media via Hugging Face download, not this repo."
                ),
            },
        }
        (out / key / "MANIFEST.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        entries.append(entry)
        print("exported", key, dest.stat().st_size, "bytes")

    index = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Offline SAM overlays/trajectories for DemoDoctor Analysis tab",
        "paid_api_artifacts": False,
        "contains_videos": False,
        "contains_api_keys": False,
        "primary_episodes": ["ep010", "ep003", "ep013", "ep005", "ep006"],
        "episodes": entries,
        "setup": "python setup_hackathon_demo.py",
    }
    (out / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        """# DemoDoctor offline SAM window cache

Compact green-plate SAM tracks for DemoDoctor Analysis windows (~200KB each).

Primary judge path: **ep010**, **ep003**, **ep013**, **ep005**, **ep006**
(plus archive ep001/ep011).

- **Not** full videos (download via `setup_hackathon_demo.py` / `import_botfails.py`).
- **Not** Muse paid responses (those live under `data/experiments/`).
- Apache-2.0 BotFails media must be obtained from Hugging Face; this folder only stores
  derived local SAM window JSON needed for mask overlays in the Streamlit replay.

Install into the expected `data/tracking/chunks/<digest>/...` paths with:

```powershell
python setup_hackathon_demo.py
```
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
