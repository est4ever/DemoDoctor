"""Download a small curated BotFails subset for DemoDoctor evaluation.

Does NOT download the full ~9 GB dataset.
Does NOT treat anomaly CSV flags as automatic task-failure labels.
Does NOT run Fireworks / Muse inference.

Usage (PowerShell):
  .\\venv\\Scripts\\python.exe import_botfails.py --list
  .\\venv\\Scripts\\python.exe import_botfails.py --download
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

from evaluation import LABELS_PATH, ensure_data_files, upsert_label_record

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "data" / "botfails_selection.json"
EVAL_DIR = ROOT / "eval_videos" / "botfails"
REPO_ID = "kantine/BotFails"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def remote_video_path(ep: dict) -> str:
    idx = int(ep["episode_index"])
    return (
        f"BotFails/{ep['split']}/{ep['task_dir']}/videos/chunk-000/"
        f"{ep['camera']}/episode_{idx:06d}.mp4"
    )


def remote_label_csv_path(ep: dict) -> str | None:
    if not ep.get("label_dir"):
        return None
    idx = int(ep["episode_index"])
    return f"BotFails/labels/{ep['label_dir']}/episode_{idx:06d}_labels.csv"


def local_video_name(ep: dict) -> str:
    return f"{ep['example_id']}.mp4"


def read_anomaly_presence(csv_path: Path) -> tuple[bool | None, int, int]:
    """Return (any_anomaly_frame, n_frames, n_anomaly_frames).

    BotFails CSVs are a single column of 0/1 per frame. Presence of anomaly
    frames does NOT mean the task failed.
    """
    text = csv_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None, 0, 0
    values: list[str] = []
    # Files are often headerless single-column; DictReader would mis-handle them.
    for line in text.splitlines():
        cell = line.strip().split(",")[0].strip()
        if cell == "":
            continue
        values.append(cell)
    # If the only distinct values are 0/1, treat all rows as frame labels.
    numeric = [v for v in values if v in {"0", "1"}]
    if not numeric:
        return None, len(values), 0
    n_anom = sum(1 for v in numeric if v == "1")
    return n_anom > 0, len(numeric), n_anom


def list_selection() -> None:
    manifest = load_manifest()
    print(f"Dataset: {manifest['dataset']}")
    print(f"Episodes selected: {len(manifest['episodes'])} (not the full dataset)")
    print()
    for note in manifest.get("notes", []):
        print(f"- {note}")
    print()
    for ep in manifest["episodes"]:
        print(
            f"{ep['example_id']:32} suggested={ep['suggested_label']:8} "
            f"task={ep['task_description'][:60]!r}"
        )
        print(f"  remote: {remote_video_path(ep)}")
        print(f"  basis:  {ep['annotation_basis']}")
        print()


def download_selection(*, skip_existing: bool = True) -> list[dict]:
    ensure_data_files()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    imported: list[dict] = []

    for ep in manifest["episodes"]:
        example_id = ep["example_id"]
        out_video = EVAL_DIR / local_video_name(ep)
        rel_video = f"eval_videos/botfails/{local_video_name(ep)}"

        if out_video.is_file() and skip_existing:
            print(f"[skip video] {example_id} already at {out_video}")
        else:
            remote = remote_video_path(ep)
            print(f"[download] {remote}")
            cached = hf_hub_download(repo_id=REPO_ID, filename=remote, repo_type="dataset")
            shutil.copyfile(cached, out_video)
            print(f"  -> {out_video} ({out_video.stat().st_size / 1e6:.1f} MB)")

        anomaly_present = None
        n_frames = None
        n_anom = None
        label_remote = remote_label_csv_path(ep)
        if label_remote:
            cached_csv = hf_hub_download(repo_id=REPO_ID, filename=label_remote, repo_type="dataset")
            anomaly_present, n_frames, n_anom = read_anomaly_presence(Path(cached_csv))

        # Suggested label from dataset documentation — NOT verified ground truth.
        suggested = ep["suggested_label"]
        notes = (
            f"SOURCE: {REPO_ID}. "
            f"suggested_label={suggested} from: {ep['annotation_basis']}. "
            f"anomaly_csv_any_positive={anomaly_present} "
            f"(frames={n_frames}, anomaly_frames={n_anom}). "
            "Anomaly ≠ task failure. verified=false until you watch the video."
        )

        record = {
            "example_id": example_id,
            "video_path": rel_video,
            "task_description": ep["task_description"],
            # Keep label aligned with suggestion only as an unverified draft.
            "label": suggested,
            "verified": False,
            "needs_manual_review": True,
            "suggested_label": suggested,
            "anomaly_present": anomaly_present,
            "source_dataset": REPO_ID,
            "source_ref": remote_video_path(ep),
            "camera": ep["camera"],
            "episode_group_id": example_id,
            "notes": notes,
        }
        upsert_label_record(record, preserve_verified=True)
        imported.append(record)
        print(f"[label] {example_id}: suggested={suggested}, verified=false, anomaly_present={anomaly_present}")

    # Keep SO-101 sample as a separate independent example if present.
    sample = ROOT / "sample_videos" / "sample.mp4"
    if sample.is_file():
        upsert_label_record(
            {
                "example_id": "sample_hf_episode_000000",
                "video_path": "sample_videos/sample.mp4",
                "task_description": "Pick up the screwdriver and place it inside the box",
                "label": "uncertain",
                "verified": False,
                "needs_manual_review": True,
                "suggested_label": None,
                "anomaly_present": None,
                "source_dataset": "ankithreddy/so101_pickplace_uno",
                "source_ref": "videos/.../episode_000000.mp4",
                "camera": "observation.images.images.top",
                "episode_group_id": "sample_hf_episode_000000",
                "notes": "SO-101 sample. Watch and set verified label before counting in accuracy.",
            },
            preserve_verified=True,
        )

    print()
    print(f"Imported {len(imported)} BotFails episodes into {EVAL_DIR}")
    print(f"Labels updated at {LABELS_PATH} (all verified=false until you confirm).")
    print("No Fireworks API calls were made.")
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a small BotFails evaluation subset.")
    parser.add_argument("--list", action="store_true", help="Show curated selection without downloading.")
    parser.add_argument("--download", action="store_true", help="Download selected videos + merge draft labels.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download videos even if they already exist locally.",
    )
    args = parser.parse_args()
    if not args.list and not args.download:
        parser.print_help()
        print("\nTip: start with --list, then --download")
        return
    if args.list:
        list_selection()
    if args.download:
        download_selection(skip_existing=not args.force)


if __name__ == "__main__":
    main()
