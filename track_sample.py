"""CLI: track screwdriver + white box on sample.mp4 via Meta SAM 3.1.

Does not invent masks. Uses cache under data/tracking_cache/.
Requires MODEL_API_KEY in .env (separate from FIREWORKS_API_KEY).

PowerShell:
  .\\venv\\Scripts\\python.exe track_sample.py
  .\\venv\\Scripts\\python.exe track_sample.py --force
  .\\venv\\Scripts\\python.exe track_sample.py --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tracking import (
    DEFAULT_SO101_CONCEPTS,
    Sam31Tracker,
    ensure_h264_mp4,
    get_default_tracker,
    load_cached_tracking,
    model_api_key_available,
    observations_for_display,
)

SAMPLE = Path(__file__).parent / "sample_videos" / "sample.mp4"


def main() -> None:
    parser = argparse.ArgumentParser(description="SAM 3.1 track SO-101 sample.mp4")
    parser.add_argument("--force", action="store_true", help="Ignore cache; call Meta API again.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate local video remux + cache paths without calling Meta API.",
    )
    parser.add_argument(
        "--concepts",
        nargs="+",
        default=list(DEFAULT_SO101_CONCEPTS),
        help="Noun phrases (one SAM request each). Default: screwdriver 'white box'",
    )
    args = parser.parse_args()

    if not SAMPLE.is_file():
        raise SystemExit(f"Missing {SAMPLE}. Run: python download_sample.py")

    video_bytes = SAMPLE.read_bytes()
    print(f"Video: {SAMPLE} ({len(video_bytes) / 1e6:.1f} MB)")
    print(f"Concepts: {args.concepts}")
    print(f"MODEL_API_KEY present: {model_api_key_available()}")

    h264 = ensure_h264_mp4(video_bytes)
    print(f"Uploadable H.264 path: {h264} ({h264.stat().st_size / 1e6:.1f} MB)")

    if args.dry_run:
        cached = load_cached_tracking(video_bytes, list(args.concepts))
        print("Cache hit:" if cached else "No cache yet.", getattr(cached, "cache_dir", None))
        print("Dry-run complete (no Meta API call).")
        return

    tracker = get_default_tracker()
    if isinstance(tracker, Sam31Tracker) is False and not model_api_key_available():
        print("No MODEL_API_KEY — structures are ready, but tracking cannot run yet.")
        print("Add MODEL_API_KEY to .env, then re-run without --dry-run.")
        return

    result = tracker.track_video(
        video_bytes,
        object_prompts=list(args.concepts),
        force_refresh=args.force,
    )
    print(f"available={result.available} provider={result.provider} from_cache={result.from_cache}")
    print(f"notes: {result.notes}")
    print(f"observations: {len(result.observations)}")
    print(f"cache_dir: {result.cache_dir}")
    print(f"overlays: {len(result.overlay_paths)}")
    for row in observations_for_display(result, limit=12):
        print(row)
    if result.overlay_paths:
        print("First overlay:", result.overlay_paths[0])


if __name__ == "__main__":
    main()
