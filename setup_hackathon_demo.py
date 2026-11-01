"""Prepare a reproducible DemoDoctor Analysis demo (no paid API calls).

1. Downloads BotFails primary demo videos (Apache-2.0 via Hugging Face).
2. Ensures joint parquet files listed in SOURCE.json are present (download if missing).
3. Installs compact SAM window caches from data/demo_cache/ into data/tracking/chunks/.
4. Verifies video digests match the frozen experiment provenance.

Usage (PowerShell):
  .\\venv\\Scripts\\python.exe setup_hackathon_demo.py
  .\\venv\\Scripts\\python.exe setup_hackathon_demo.py --skip-download
  .\\venv\\Scripts\\python.exe -m streamlit run app.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).parent
DEMO_CACHE = ROOT / "data" / "demo_cache"
EVAL_DIR = ROOT / "eval_videos" / "botfails"
SOURCE = ROOT / "data" / "lerobot" / "kantine__BotFails" / "test" / "domotic_dishTidyUp_anomaly" / "SOURCE.json"
JOINT_DIR = SOURCE.parent
REPO_ID = "kantine/BotFails"

# Primary judge path + archive episodes for DemoDoctor Analysis.
DEMO_VIDEOS = [
    {
        "example_id": "botfails_dish_test_ep010",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000010.mp4",
        "local": "botfails_dish_test_ep010.mp4",
    },
    {
        "example_id": "botfails_dish_test_ep003",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000003.mp4",
        "local": "botfails_dish_test_ep003.mp4",
    },
    {
        "example_id": "botfails_dish_test_ep013",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000013.mp4",
        "local": "botfails_dish_test_ep013.mp4",
    },
    {
        "example_id": "botfails_dish_test_ep005",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000005.mp4",
        "local": "botfails_dish_test_ep005.mp4",
    },
    {
        "example_id": "botfails_dish_test_ep006",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000006.mp4",
        "local": "botfails_dish_test_ep006.mp4",
    },
    # Archive continuity
    {
        "example_id": "botfails_dish_test_ep001",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000001.mp4",
        "local": "botfails_dish_test_ep001.mp4",
    },
    {
        "example_id": "botfails_dish_test_ep011",
        "remote": "BotFails/test/domotic_dishTidyUp_anomaly/videos/chunk-000/observation.images.logitech_1/episode_000011.mp4",
        "local": "botfails_dish_test_ep011.mp4",
    },
]

PRIMARY_REPLAY_KEYS = ("ep010", "ep003", "ep013", "ep005", "ep006")
ARCHIVE_REPLAY_KEYS = ("ep001", "ep011")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_demo_videos(*, skip_existing: bool = True) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    revision = None
    if SOURCE.is_file():
        revision = json.loads(SOURCE.read_text(encoding="utf-8")).get("revision")
    for item in DEMO_VIDEOS:
        dest = EVAL_DIR / item["local"]
        if dest.is_file() and skip_existing:
            print(f"[skip video] {item['example_id']} ({dest.stat().st_size / 1e6:.1f} MB)")
            continue
        print(f"[download] {item['remote']}")
        cached = hf_hub_download(
            repo_id=REPO_ID,
            filename=item["remote"],
            repo_type="dataset",
            revision=revision,
        )
        shutil.copyfile(cached, dest)
        print(f"  -> {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def ensure_joints() -> None:
    if not SOURCE.is_file():
        print("SOURCE.json missing — skip joint download")
        return
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    repo_id = src["repo_id"]
    revision = src.get("revision")
    subdir = src["dataset_subdir"]
    for rel, meta in (src.get("files") or {}).items():
        dest = JOINT_DIR / rel
        if dest.is_file():
            expect = meta.get("sha256")
            if expect and _sha256(dest) == expect:
                print("joint ok", dest.name)
                continue
            if expect is None:
                print("joint present", dest.name)
                continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        filename = f"{subdir}/{rel}"
        print("Downloading", filename, "...")
        path = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            filename=filename,
        )
        shutil.copy2(path, dest)
        got = _sha256(dest)
        expect = meta.get("sha256")
        if expect and got != expect:
            print(f"WARNING: sha256 mismatch for {dest.name}")
        else:
            print("joint saved", dest.name)


def install_demo_caches() -> list[str]:
    index_path = DEMO_CACHE / "INDEX.json"
    if not index_path.is_file():
        raise SystemExit(
            "Missing data/demo_cache/INDEX.json. Maintainer: run "
            "`python scripts/export_demo_cache.py` after SAM windows exist."
        )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for ep in index["episodes"]:
        src = ROOT / ep["sam_window_rel"]
        dest = ROOT / ep["install_chunk_rel"]
        if not src.is_file():
            problems.append(f"missing cache file {src}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        video = ROOT / ep["video_rel"]
        if video.is_file():
            digest = _sha256(video)
            if digest != ep["video_sha256"]:
                problems.append(
                    f"{ep['episode_key']}: video sha256 mismatch "
                    f"(got {digest[:16]}… expected {ep['video_sha256'][:16]}…)"
                )
            else:
                print(f"installed {ep['episode_key']} → {dest.relative_to(ROOT)} (video digest ok)")
        else:
            print(f"installed {ep['episode_key']} → {dest.relative_to(ROOT)} (video not present yet)")
            problems.append(f"{ep['episode_key']}: video missing at {ep['video_rel']}")
    return problems


def verify_replay_loads() -> None:
    from demo_replay import load_replay_bundle

    for key in (*PRIMARY_REPLAY_KEYS, *ARCHIVE_REPLAY_KEYS):
        b = load_replay_bundle(key)
        if not b.ok:
            raise SystemExit(f"Replay bundle failed for {key}: {b.missing}")
        print(
            f"replay ok {key}: verdict={b.failure_report.get('verdict')} "
            f"muse={(b.evidence_muse or {}).get('task_outcome')} "
            f"muse_only={(b.muse_only or {}).get('verdict')} "
            f"video={'yes' if b.video_path else 'no'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true", help="Only install demo_cache into tracking/")
    parser.add_argument("--skip-joints", action="store_true", help="Do not download joint parquets")
    parser.add_argument("--force-videos", action="store_true", help="Re-download videos even if present")
    args = parser.parse_args()

    if not args.skip_download:
        download_demo_videos(skip_existing=not args.force_videos)
        if not args.skip_joints:
            ensure_joints()
    problems = install_demo_caches()
    verify_replay_loads()
    # Video missing is fatal for full demo; digest mismatch is fatal
    fatal = [p for p in problems if "missing cache" in p or "sha256 mismatch" in p or "video missing" in p]
    if fatal and not args.skip_download:
        print("Problems:", file=sys.stderr)
        for p in fatal:
            print(" -", p, file=sys.stderr)
        raise SystemExit(1)
    if problems and args.skip_download:
        print("Notes:", *problems, sep="\n - ")
    print("\nDemo setup complete. Run:  python -m streamlit run app.py")
    print("Open the 'DemoDoctor Analysis' tab. Primary path: ep010 → ep003 → ep013 → ep005 → ep006.")
    print("No API keys required for cached replay.")
    print(
        "React 3D/web replay (optional): after videos+joints are present, regenerate "
        "mapping/joints overlays with:  python scripts/export_web_demo_bundles.py"
    )
    print("Then:  cd web && npm install && npm run build && npm run preview")


if __name__ == "__main__":
    main()
