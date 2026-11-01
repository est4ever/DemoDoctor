"""Progressive SAM 3.1 milestone tests for sample.mp4.

Explicit paid-call stages (nothing runs unless you choose a stage):

  python run_sam_milestone.py --stage frame
  python run_sam_milestone.py --stage clip
  python run_sam_milestone.py --stage video
  python run_sam_milestone.py --stage video --concepts screwdriver "white box" "robot gripper"
  python run_sam_milestone.py --stage chunk --chunk-index 2 --concepts screwdriver [--seed]

Use --force to bypass cache. Use --dry-run with video/chunk to list which
chunk x concept requests are cached vs would be paid calls (no API key needed).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import cv2

from tracking import (
    Sam31Tracker,
    extract_clip_mp4,
    extract_frame_jpeg,
    extract_frame_rgb,
    load_cached_tracking,
    plan_window_calls,
    probe_video,
    model_api_key_available,
    observations_for_display,
    plan_tracking_calls,
    prepare_box_probe,
    probe_preview,
    render_cached_mask_overlays,
    run_box_probe,
    seed_plan,
)

SAMPLE = Path(__file__).parent / "sample_videos" / "sample.mp4"
OUT = Path(__file__).parent / "data" / "tracking" / "milestone_runs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=("frame", "clip", "video", "chunk", "probe", "window"),
        required=True,
        help="frame=single JPEG; clip=~4s H.264; video=full sample; chunk=one chunk of the full-video plan",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List cached vs paid requests; call nothing.")
    parser.add_argument("--seed", action="store_true", help="Box-seed chunks from the previous chunk's overlap frame.")
    parser.add_argument("--chunk-index", type=int, default=None)
    parser.add_argument("--video", type=Path, default=SAMPLE, help="video file (default: SO-101 sample)")
    parser.add_argument("--start-frame", type=int, default=None, help="window stage: first frame")
    parser.add_argument("--end-frame", type=int, default=None, help="window stage: end frame (exclusive)")
    parser.add_argument("--container", default=None, help="window stage: container concept for one image request")
    parser.add_argument("--container-frame", type=int, default=None, help="window stage: frame for the container image")
    parser.add_argument("--frame-index", type=int, default=None, help="probe stage: global frame index")
    parser.add_argument("--box", type=int, nargs=4, metavar=("X1", "Y1", "X2", "Y2"), default=None,
                        help="probe stage: manually selected half-open box in full-frame pixels")
    parser.add_argument("--selected-by", default="manual", help="probe stage: who chose the box (provenance)")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="chunk stage: skip the concept request; one box-seeded request from the previous chunk.",
    )
    parser.add_argument(
        "--render-overlays",
        action="store_true",
        help="Re-render cached results with pixel masks into overlays_masks/ (no API call).",
    )
    parser.add_argument(
        "--concepts",
        nargs="+",
        default=None,
        help="Defaults: frame→screwdriver; clip/video→screwdriver white box",
    )
    parser.add_argument("--frame-time", type=float, default=0.5, help="Seconds for clear screwdriver view")
    parser.add_argument("--clip-start", type=float, default=0.0)
    parser.add_argument("--clip-duration", type=float, default=4.0)
    args = parser.parse_args()

    if not args.video.is_file():
        raise SystemExit(f"Missing {args.video}. Run download_sample.py / import_botfails.py first.")
    if args.video != SAMPLE and args.stage not in ("window",):
        raise SystemExit("--video other than the SO-101 sample is supported by the window stage only.")
    video_bytes = args.video.read_bytes()

    if args.stage == "window":
        if args.start_frame is None or args.end_frame is None or not args.concepts:
            raise SystemExit("--stage window requires --start-frame, --end-frame and --concepts")
        fps, n_frames = probe_video(video_bytes)
        if not (0 <= args.start_frame < args.end_frame <= n_frames):
            raise SystemExit(f"window must lie within 0..{n_frames}")
        rows = plan_window_calls(video_bytes, start_frame=args.start_frame, end_frame=args.end_frame,
                                 concepts=list(args.concepts))
        print(f"video {args.video.name}: {n_frames} frames @ {fps:.0f}fps; window frames "
              f"{args.start_frame}-{args.end_frame - 1} ({args.start_frame / fps:.2f}-{args.end_frame / fps:.2f}s)")
        for r in rows:
            print(f"  video request  {r['concept']:<14} {r['n_frames']} frames  cached={r['cached_status']} -> {r['action']}")
        container_req = None
        if args.container:
            cf = args.container_frame if args.container_frame is not None else args.start_frame
            jpeg = extract_frame_jpeg(video_bytes, timestamp_s=cf / fps, quality=95)
            cached = load_cached_tracking(jpeg, [args.container], media_kind="image")
            container_req = (cf, jpeg)
            print(f"  image request  {args.container:<14} frame {cf} ({cf / fps:.2f}s)  -> "
                  f"{'cached' if cached is not None else 'PAID CALL'}")
        paid_video = sum(r["action"] == "PAID CALL" for r in rows)
        paid_img = int(bool(container_req) and load_cached_tracking(container_req[1], [args.container], media_kind="image") is None)
        print(f"--- total paid SAM requests: {paid_video + paid_img} "
              f"({paid_video} video x {args.end_frame - args.start_frame} frames, {paid_img} image)"
              f"{', +1 upload' if paid_video else ''}")
        if args.dry_run:
            OUT.mkdir(parents=True, exist_ok=True)
            picks = [args.start_frame, (args.start_frame + args.end_frame - 1) // 2, args.end_frame - 1]
            tiles = [cv2.cvtColor(extract_frame_rgb(video_bytes, f), cv2.COLOR_RGB2BGR) for f in picks]
            for img, f in zip(tiles, picks):
                cv2.putText(img, f"f{f} {f / fps:.2f}s", (8, 28), 0, 0.8, (0, 0, 255), 2)
            stem = f"window_{args.video.stem}_f{args.start_frame}-{args.end_frame - 1}"
            cv2.imwrite(str(OUT / f"{stem}.jpg"), cv2.hconcat(tiles))
            print(f"--- DRY RUN: nothing sent. Preview: {OUT / (stem + '.jpg')}")
            return
        if not model_api_key_available():
            raise SystemExit("MODEL_API_KEY is not set in .env")
        tracker = Sam31Tracker()
        chunk, obs, calls = tracker.track_window(video_bytes, start_frame=args.start_frame, end_frame=args.end_frame,
                                                 concepts=list(args.concepts), force_refresh=args.force)
        for c in calls:
            print(f"  {c.concept}: status={c.status} records={c.n_records} observations={c.n_observations} "
                  f"cached={c.from_cache} usage={c.usage}")
        ids = sorted({o.local_object_id for o in obs})
        print(f"  local object ids: {ids}")
        if container_req:
            res = tracker.segment_image(container_req[1], concept=args.container, force_refresh=args.force)
            print(f"  {args.container} image: available={res.available} observations={len(res.observations)} "
                  f"usage={res.diagnostics.usage if res.diagnostics else None}")
        return

    if args.stage == "probe":
        if args.frame_index is None or args.box is None:
            raise SystemExit("--stage probe requires --frame-index and --box X1 Y1 X2 Y2")
        concept = (args.concepts or ["screwdriver"])[0]
        req = prepare_box_probe(video_bytes, frame_index=args.frame_index, box=tuple(args.box),
                                concept=concept, selected_by=args.selected_by)
        print(f"frame {req.frame_index} (t={req.timestamp_s}s) concept={concept} box={req.box} selected_by={req.selected_by}")
        print(f"prompt text: {req.prompt_text}")
        print(f"image: {len(req.image_png)} bytes PNG; result path: {req.path}")
        if args.dry_run:
            OUT.mkdir(parents=True, exist_ok=True)
            stem = f"probe_preview_f{req.frame_index}_{'_'.join(map(str, req.box))}"
            (OUT / f"{stem}_request.png").write_bytes(req.image_png)
            cv2.imwrite(str(OUT / f"{stem}.png"), cv2.cvtColor(probe_preview(video_bytes, req), cv2.COLOR_RGB2BGR))
            print(f"--- DRY RUN: no request sent. Preview: {OUT / (stem + '.png')}")
            print("--- " + ("cached result exists; running would not call the API." if req.cached
                         else "running without --dry-run makes 1 PAID SAM image request."))
            return
        if not model_api_key_available():
            raise SystemExit("MODEL_API_KEY is not set in .env")
        record = run_box_probe(req)
        print(json.dumps({k: v for k, v in record.items() if k != "observations"}, indent=2))
        for o in record.get("observations", []):
            print(f"  observation {o['object_id']} bbox={[round(v) for v in o['bbox']]} conf={o['confidence']}")
        return

    if args.dry_run and args.seed_only:
        if args.stage != "chunk" or args.chunk_index is None:
            raise SystemExit("--seed-only applies to --stage chunk --chunk-index K")
        for concept in args.concepts or ["screwdriver"]:
            chunk, seeds = seed_plan(video_bytes, chunk_index=args.chunk_index, concept=concept)
            print(f"chunk{chunk.index} frames {chunk.start_frame}-{chunk.end_frame - 1} {concept}: "
                  + (f"1 PAID seeded request, seed from {seeds[0][0]} box={seeds[0][1]} conf={seeds[0][2]}"
                     if seeds else "no seed available on overlap frame -> no request"))
        return

    if args.dry_run:
        if args.stage not in ("video", "chunk"):
            raise SystemExit("--dry-run applies to the video and chunk stages.")
        concepts = args.concepts or ["screwdriver", "white box"]
        rows = plan_tracking_calls(video_bytes, concepts)
        if args.stage == "chunk" and args.chunk_index is not None:
            rows = [r for r in rows if r["chunk"] == args.chunk_index]
        for r in rows:
            print(f"chunk{r['chunk']} frames {r['frames']:>9}  {r['concept']:<15} "
                  f"cached={str(r['cached_status']):<11} -> {r['action']}")
        paid = sum(r["action"] == "PAID CALL" for r in rows)
        print(f"--- {paid} paid SAM request(s) (+1 upload per affected chunk)", end="")
        print("; --seed may add up to one seeded request per chunk that loses the object." if args.seed else ".")
        return

    if args.render_overlays:
        if args.stage == "frame":
            payload, kind = extract_frame_jpeg(video_bytes, timestamp_s=args.frame_time), "image"
            concepts = args.concepts or ["screwdriver"]
        elif args.stage == "clip":
            payload = extract_clip_mp4(video_bytes, start_s=args.clip_start, duration_s=args.clip_duration)
            kind, concepts = "clip", args.concepts or ["screwdriver", "white box"]
        elif args.stage == "video":
            payload, kind, concepts = video_bytes, "video", args.concepts or ["screwdriver", "white box"]
        else:
            raise SystemExit("--render-overlays applies to frame, clip and video stages.")
        cached = load_cached_tracking(payload, concepts, media_kind=kind)
        if cached is None or not cached.observations:
            raise SystemExit("No cached observations for that stage/concepts; nothing to render.")
        paths = render_cached_mask_overlays(payload, cached)
        print(f"Rendered {len(paths)} mask overlays into {Path(cached.cache_dir) / 'overlays_masks'}")
        return

    if not model_api_key_available():
        raise SystemExit("MODEL_API_KEY is not set in .env")
    tracker = Sam31Tracker()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.stage == "chunk":
        if args.chunk_index is None:
            raise SystemExit("--stage chunk requires --chunk-index")
        concepts = args.concepts or ["screwdriver"]
        chunk, obs, calls = tracker.track_single_chunk(
            video_bytes, chunk_index=args.chunk_index, concepts=concepts,
            seed_from_previous=args.seed, force_refresh=args.force,
            seed_only=args.seed_only, max_seeds=1 if args.seed_only else None,
        )
        print(f"chunk{chunk.index}: frames {chunk.start_frame}-{chunk.end_frame - 1}")
        for c in calls:
            print(f"  {c.concept}[{c.prompt_mode}] status={c.status} records={c.n_records} "
                  f"observations={c.n_observations} cached={c.from_cache} reason={c.reason}")
        frames = sorted({o.frame_index for o in obs})
        print(f"  frames with detections: {len(frames)}"
              + (f" ({frames[0]}..{frames[-1]})" if frames else ""))
        tag = "_seedonly" if args.seed_only else ("_seed" if args.seed else "")
        report = OUT / f"report_chunk{chunk.index}{tag}.json"
        report.write_text(json.dumps({
            "chunk": chunk.to_dict(),
            "calls": [c.to_dict() for c in calls],
            "observations": [asdict(o) for o in obs],
        }, indent=2), encoding="utf-8")
        print(f"Wrote {report}")
        return

    if args.stage == "frame":
        concepts = args.concepts or ["screwdriver"]
        print(f"Extracting frame near t={args.frame_time}s ...")
        jpeg = extract_frame_jpeg(video_bytes, timestamp_s=args.frame_time)
        frame_path = OUT / f"input_frame_{args.frame_time:.2f}s.jpg"
        frame_path.write_bytes(jpeg)
        print(f"Saved {frame_path} ({len(jpeg)} bytes)")
        print(f"Calling SAM 3.1 image segmentation for {concepts} ...")
        # One concept at a time for image milestone clarity
        result = tracker.segment_image(
            jpeg, concept=concepts[0], force_refresh=args.force
        )
        if len(concepts) > 1:
            print("Note: frame stage uses the first concept only; re-run for others.")
    elif args.stage == "clip":
        concepts = args.concepts or ["screwdriver", "white box"]
        print(f"Extracting clip [{args.clip_start}, {args.clip_start + args.clip_duration}]s ...")
        clip = extract_clip_mp4(
            video_bytes, start_s=args.clip_start, duration_s=args.clip_duration
        )
        clip_path = OUT / f"input_clip_{args.clip_start:.1f}_{args.clip_duration:.1f}s.mp4"
        clip_path.write_bytes(clip)
        print(f"Saved {clip_path} ({len(clip) / 1e6:.2f} MB)")
        print(f"Calling SAM 3.1 video tracking for {concepts} ...")
        result = tracker.track_video(
            clip, object_prompts=concepts, force_refresh=args.force, media_kind="clip"
        )
    else:
        concepts = args.concepts or ["screwdriver", "white box"]
        print(f"Calling SAM 3.1 on full sample.mp4 for {concepts} ...")
        print("This may take several minutes and use more credits.")
        result = tracker.track_video(
            video_bytes,
            object_prompts=concepts,
            force_refresh=args.force,
            media_kind="video",
            seed_from_previous=args.seed,
        )

    print("---")
    print(f"available={result.available} from_cache={result.from_cache} provider={result.provider}")
    print(f"notes: {result.notes}")
    print(f"observations: {len(result.observations)}")
    print(f"cache_dir: {result.cache_dir}")
    print(f"overlays: {len(result.overlay_paths)}")
    if result.diagnostics:
        print("diagnostics:", json.dumps(result.diagnostics.to_dict(), indent=2))
    for row in observations_for_display(result, limit=15):
        print(row)
    if result.overlay_paths:
        print("overlay:", result.overlay_paths[0])
    # Keep the historical names for the default runs; parameterized runs get
    # their own file so earlier reports are never overwritten.
    suffix = ""
    if args.stage == "frame" and abs(args.frame_time - 0.5) > 1e-6:
        suffix = f"_{args.frame_time:.2f}s"
    report = OUT / f"report_{args.stage}{suffix}.json"
    report.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"Wrote {report}")


if __name__ == "__main__":
    main()
