"""DemoDoctor SAM 3.1 tracking: structured observations, cache, overlays, diagnostics.

Uses Meta Model API via sam_api.py + official meta_sam_parser.
Does NOT fabricate masks. Does NOT auto-call the API on import.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import io
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Protocol

import cv2
import numpy as np
from dotenv import load_dotenv
import os

from track_stitch import (
    ChunkCall,
    ChunkSpec,
    FrameState,
    assign_legacy_chunks,
    concept_frame_states,
    legacy_chunk_log,
    plan_chunks,
    state_runs,
    stitch_tracks,
)

TrackStatus = Literal["visible", "occluded", "lost", "unknown", "missing"]

META_BASE_URL = "https://api.meta.ai/v1"
SAM_MODEL = "sam-3.1"
TRACKING_ROOT = Path(__file__).parent / "data" / "tracking"
# Keep old cache path as alias for prior runs.
LEGACY_CACHE_ROOT = Path(__file__).parent / "data" / "tracking_cache"
CACHE_ROOT = TRACKING_ROOT
# Per-chunk, per-concept results so adding a concept never re-bills the others.
CHUNK_CACHE_ROOT = TRACKING_ROOT / "chunks"
MASK_OVERLAY_DIR = "overlays_masks"
DEFAULT_CHUNK_S = 4.0
DEFAULT_OVERLAP_FRAMES = 1
DEFAULT_SO101_CONCEPTS = ("screwdriver", "white box", "robot gripper")
CONCEPT_COLORS = {
    "screwdriver": (0, 200, 255),
    "white box": (80, 220, 80),
    "robot gripper": (255, 120, 80),
    "gripper": (255, 120, 80),
}


@dataclass(frozen=True)
class ObjectTrackObservation:
    timestamp_s: float
    object_id: str
    concept: str
    frame_index: int | None
    bbox: tuple[float, float, float, float] | None
    centroid: tuple[float, float] | None
    track_status: TrackStatus = "unknown"
    confidence: float | None = None
    mask_rle: dict[str, Any] | None = None
    observation_returned: bool = True
    # Provenance for chunked runs: which request produced this record and the
    # SAM-local object id it had there (object_id holds the stitched global id).
    chunk_index: int | None = None
    local_object_id: str | None = None
    prompt_mode: str | None = None


@dataclass
class TrackingDiagnostics:
    frames_in_source: int | None = None
    frames_with_any_detection: int = 0
    observations_total: int = 0
    per_concept: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_concepts: list[str] = field(default_factory=list)
    api_notes: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrackingResult:
    available: bool
    provider: str
    observations: list[ObjectTrackObservation] = field(default_factory=list)
    notes: str = ""
    concepts: list[str] = field(default_factory=list)
    cache_dir: str | None = None
    overlay_paths: list[str] = field(default_factory=list)
    fps: float | None = None
    from_cache: bool = False
    diagnostics: TrackingDiagnostics | None = None
    media_kind: str = "video"  # image | clip | video
    # {"source", "chunks": [ChunkSpec dicts], "calls": [ChunkCall dicts], "links": [...]}
    chunk_log: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_log": self.chunk_log,
            "available": self.available,
            "provider": self.provider,
            "notes": self.notes,
            "concepts": self.concepts,
            "cache_dir": self.cache_dir,
            "overlay_paths": self.overlay_paths,
            "fps": self.fps,
            "from_cache": self.from_cache,
            "media_kind": self.media_kind,
            "diagnostics": self.diagnostics.to_dict() if self.diagnostics else None,
            "observations": [asdict(obs) for obs in self.observations],
        }


class SegmentationTracker(Protocol):
    def track_video(
        self,
        video_bytes: bytes,
        *,
        object_prompts: list[str] | None = None,
        force_refresh: bool = False,
    ) -> TrackingResult:
        ...


class ModelApiConfigError(RuntimeError):
    pass


def load_model_api_key() -> str:
    load_dotenv()
    key = (os.getenv("MODEL_API_KEY") or "").strip()
    if not key:
        raise ModelApiConfigError(
            "MODEL_API_KEY is not set. Add it to .env (separate from FIREWORKS_API_KEY)."
        )
    return key


def model_api_key_available() -> bool:
    load_dotenv()
    return bool((os.getenv("MODEL_API_KEY") or "").strip())


class UnavailableTracker:
    def track_video(
        self,
        video_bytes: bytes,
        *,
        object_prompts: list[str] | None = None,
        force_refresh: bool = False,
    ) -> TrackingResult:
        del video_bytes, force_refresh
        concepts = list(object_prompts or DEFAULT_SO101_CONCEPTS)
        return TrackingResult(
            available=False,
            provider="none",
            concepts=concepts,
            notes=(
                "SAM 3.1 tracking is not configured (MODEL_API_KEY missing). "
                "No masks were invented."
            ),
        )


def get_default_tracker() -> SegmentationTracker:
    if model_api_key_available():
        return Sam31Tracker()
    return UnavailableTracker()


def cache_key(payload: bytes, concepts: list[str], *, media_kind: str) -> str:
    digest = hashlib.sha256()
    digest.update(payload)
    digest.update(SAM_MODEL.encode())
    digest.update(media_kind.encode())
    digest.update("|".join(concepts).encode())
    return digest.hexdigest()[:24]


def ensure_h264_mp4(video_bytes: bytes) -> Path:
    """Write H.264 MP4 for Meta SAM upload (AV1 samples are transcoded via PyAV)."""
    import av

    TRACKING_ROOT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(video_bytes).hexdigest()[:16]
    out_path = TRACKING_ROOT / f"_upload_h264_{digest}.mp4"
    if out_path.is_file() and out_path.stat().st_size > 0:
        return out_path

    raw_path = TRACKING_ROOT / f"_upload_src_{digest}.mp4"
    raw_path.write_bytes(video_bytes)

    with av.open(str(raw_path)) as src:
        stream = src.streams.video[0]
        codec_name = (stream.codec_context.name or "").lower()
        if codec_name in {"h264", "hevc", "mpeg4"} and raw_path.suffix.lower() == ".mp4":
            out_path.write_bytes(video_bytes)
            return out_path

        with av.open(str(out_path), mode="w") as dst:
            out_stream = dst.add_stream("libx264", rate=stream.average_rate or 30)
            out_stream.width = stream.codec_context.width
            out_stream.height = stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"
            out_stream.options = {"preset": "veryfast", "crf": "23"}
            for frame in src.decode(video=0):
                frame = frame.reformat(format="yuv420p")
                for packet in out_stream.encode(frame):
                    dst.mux(packet)
            for packet in out_stream.encode(None):
                dst.mux(packet)
    return out_path


def probe_video(video_bytes: bytes) -> tuple[float, int]:
    import av

    fps = 30.0
    n = 0
    with av.open(io.BytesIO(video_bytes)) as container:
        stream = container.streams.video[0]
        if stream.average_rate:
            fps = float(stream.average_rate)
        for _ in container.decode(video=0):
            n += 1
    return fps, n


def probe_fps(video_bytes: bytes) -> float:
    return probe_video(video_bytes)[0]


def extract_frame_jpeg(video_bytes: bytes, *, timestamp_s: float = 0.0, quality: int = 90) -> bytes:
    """Extract one RGB frame near timestamp_s as JPEG bytes."""
    import av

    target = max(0.0, timestamp_s)
    best = None
    best_dt = 1e9
    with av.open(io.BytesIO(video_bytes)) as container:
        for frame in container.decode(video=0):
            t = float(frame.time) if frame.time is not None else 0.0
            dt = abs(t - target)
            if dt < best_dt:
                best_dt = dt
                best = frame
            if t >= target and best is not None and dt <= 1.0 / 30.0:
                break
    if best is None:
        raise ValueError("No frame could be decoded from the video.")
    rgb = best.to_ndarray(format="rgb24")
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("Failed to encode JPEG frame.")
    return buf.tobytes()


def extract_clip_mp4(
    video_bytes: bytes,
    *,
    start_s: float = 0.0,
    duration_s: float = 4.0,
) -> bytes:
    """Cut a short H.264 clip [start_s, start_s+duration_s] for cheaper SAM tests."""
    import av

    end_s = start_s + duration_s
    out = io.BytesIO()
    with av.open(io.BytesIO(video_bytes)) as src:
        stream = src.streams.video[0]
        with av.open(out, mode="w", format="mp4") as dst:
            out_stream = dst.add_stream("libx264", rate=stream.average_rate or 30)
            out_stream.width = stream.codec_context.width
            out_stream.height = stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"
            out_stream.options = {"preset": "veryfast", "crf": "23"}
            for frame in src.decode(video=0):
                t = float(frame.time) if frame.time is not None else 0.0
                if t < start_s:
                    continue
                if t > end_s:
                    break
                frame = frame.reformat(format="yuv420p")
                for packet in out_stream.encode(frame):
                    dst.mux(packet)
            for packet in out_stream.encode(None):
                dst.mux(packet)
    data = out.getvalue()
    if not data:
        raise ValueError("Clip extraction produced an empty file.")
    return data


def extract_frame_range_mp4(video_bytes: bytes, *, start_frame: int, end_frame: int) -> bytes:
    """Cut decoded frames [start_frame, end_frame) into an H.264 clip.

    Indexing by decoded frame (not timestamp) keeps clip frame 0 == global
    start_frame exactly, so chunk-local SAM frame indices map back without drift.
    """
    import av

    out = io.BytesIO()
    written = 0
    with av.open(io.BytesIO(video_bytes)) as src:
        stream = src.streams.video[0]
        with av.open(out, mode="w", format="mp4") as dst:
            out_stream = dst.add_stream("libx264", rate=stream.average_rate or 30)
            out_stream.width = stream.codec_context.width
            out_stream.height = stream.codec_context.height
            out_stream.pix_fmt = "yuv420p"
            out_stream.options = {"preset": "veryfast", "crf": "23"}
            for i, frame in enumerate(src.decode(video=0)):
                if i < start_frame:
                    continue
                if i >= end_frame:
                    break
                frame = frame.reformat(format="yuv420p")
                for packet in out_stream.encode(frame):
                    dst.mux(packet)
                written += 1
            for packet in out_stream.encode(None):
                dst.mux(packet)
    if written != end_frame - start_frame:
        raise ValueError(
            f"Requested frames [{start_frame}, {end_frame}) but decoded {written}."
        )
    return out.getvalue()


def probe_video_size(video_bytes: bytes) -> tuple[int, int]:
    import av

    with av.open(io.BytesIO(video_bytes)) as container:
        ctx = container.streams.video[0].codec_context
        return int(ctx.width), int(ctx.height)


def _run_coro(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _frame_index(record: Any) -> int | None:
    frame = getattr(record, "frame", None)
    if frame is None:
        return None
    return int(getattr(frame, "frame_index", frame))


def _rle_from_mask(mask_rec: Any) -> dict[str, Any] | None:
    try:
        from meta_sam_parser import decode_mask_to_rle

        rle = decode_mask_to_rle(mask_rec.mask)
        return {"size": list(rle.size), "counts": rle.counts}
    except Exception:  # noqa: BLE001
        return None


def observations_from_result(
    result: Any,
    *,
    concept: str,
    fps: float,
    media_kind: str,
) -> list[ObjectTrackObservation]:
    boxes_by_key: dict[tuple[int | None, str], Any] = {}
    masks_by_key: dict[tuple[int | None, str], Any] = {}
    for record in result.records:
        kind = getattr(record, "kind", None)
        key = (_frame_index(record), str(record.object_id))
        if kind == "box":
            boxes_by_key[key] = record
        elif kind == "mask":
            masks_by_key[key] = record

    keys = sorted(
        set(boxes_by_key) | set(masks_by_key),
        key=lambda k: (k[0] is None, k[0] or 0, k[1]),
    )
    observations: list[ObjectTrackObservation] = []
    for frame_idx, object_id in keys:
        box = boxes_by_key.get((frame_idx, object_id))
        mask_rec = masks_by_key.get((frame_idx, object_id))
        bbox = None
        centroid = None
        confidence = None
        if box is not None:
            bbox = (float(box.left), float(box.top), float(box.right), float(box.bottom))
            centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
            confidence = getattr(box, "confidence", None)
        elif mask_rec is not None and getattr(mask_rec, "bounds", None) is not None:
            b = mask_rec.bounds
            bbox = (float(b.left), float(b.top), float(b.right), float(b.bottom))
            centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
            confidence = getattr(mask_rec, "confidence", None)

        if media_kind == "image":
            timestamp_s = 0.0
        elif frame_idx is not None:
            timestamp_s = round(frame_idx / max(fps, 1e-6), 3)
        else:
            timestamp_s = 0.0

        observations.append(
            ObjectTrackObservation(
                timestamp_s=timestamp_s,
                object_id=f"{concept}:{object_id}",
                concept=concept,
                frame_index=0 if media_kind == "image" else frame_idx,
                bbox=bbox,
                centroid=centroid,
                track_status="visible" if bbox is not None else "unknown",
                confidence=float(confidence) if confidence is not None else None,
                mask_rle=_rle_from_mask(mask_rec) if mask_rec is not None else None,
                observation_returned=True,
            )
        )
    return observations


def build_diagnostics(
    *,
    concepts: list[str],
    observations: list[ObjectTrackObservation],
    frames_in_source: int | None,
    api_notes: list[str],
    chunks: list[ChunkSpec] | None = None,
    calls: list[ChunkCall] | None = None,
) -> TrackingDiagnostics:
    per_concept: dict[str, dict[str, Any]] = {}
    frames_by_concept: dict[str, set[int]] = defaultdict(set)
    for obs in observations:
        if obs.frame_index is not None:
            frames_by_concept[obs.concept].add(obs.frame_index)

    for concept in concepts:
        frames = frames_by_concept.get(concept, set())
        coverage = None
        if frames_in_source and frames_in_source > 0:
            coverage = len(frames) / frames_in_source
        info: dict[str, Any] = {
            "frames_with_detection": len(frames),
            "observations": sum(1 for o in observations if o.concept == concept),
            "coverage": coverage,
            "missing_entirely": len(frames) == 0,
            "global_tracks": sorted({o.object_id for o in observations if o.concept == concept}),
        }
        if chunks is not None and calls is not None and frames_in_source:
            states = concept_frame_states(observations, chunks, calls, concept, frames_in_source)
            info["frames_detected"] = states.count("detected")
            info["frames_not_detected"] = states.count("not_detected")
            info["frames_unknown"] = states.count("unknown")
            info["state_runs"] = state_runs(states)
            info["calls"] = [
                {"chunk": c.chunk_index, "status": c.status, "n_observations": c.n_observations}
                for c in calls
                if c.concept == concept
            ]
        per_concept[concept] = info

    any_frames = {o.frame_index for o in observations if o.frame_index is not None}
    missing = [c for c, info in per_concept.items() if info["missing_entirely"]]
    return TrackingDiagnostics(
        frames_in_source=frames_in_source,
        frames_with_any_detection=len(any_frames),
        observations_total=len(observations),
        per_concept=per_concept,
        missing_concepts=missing,
        api_notes=api_notes,
    )


def chunk_log_parts(result: TrackingResult) -> tuple[list[ChunkSpec], list[ChunkCall]]:
    log = result.chunk_log or {}
    chunks = [ChunkSpec(**c) for c in log.get("chunks") or []]
    calls = [ChunkCall(**c) for c in log.get("calls") or []]
    return chunks, calls


def frame_states_for(result: TrackingResult, concept: str) -> list[FrameState]:
    """Per-frame detected / not_detected / unknown for one concept."""
    chunks, calls = chunk_log_parts(result)
    n = result.diagnostics.frames_in_source if result.diagnostics else None
    return concept_frame_states(result.observations, chunks, calls, concept, n or 0)


def _observation_from_row(row: dict[str, Any]) -> ObjectTrackObservation:
    return ObjectTrackObservation(
        timestamp_s=float(row["timestamp_s"]),
        object_id=str(row["object_id"]),
        concept=str(row.get("concept") or ""),
        frame_index=row.get("frame_index"),
        bbox=tuple(row["bbox"]) if row.get("bbox") else None,  # type: ignore[arg-type]
        centroid=tuple(row["centroid"]) if row.get("centroid") else None,  # type: ignore[arg-type]
        track_status=row.get("track_status") or "unknown",  # type: ignore[arg-type]
        confidence=row.get("confidence"),
        mask_rle=row.get("mask_rle"),
        observation_returned=bool(row.get("observation_returned", True)),
        chunk_index=row.get("chunk_index"),
        local_object_id=row.get("local_object_id"),
        prompt_mode=row.get("prompt_mode"),
    )


def _legacy_parts(
    observations: list[ObjectTrackObservation],
    diagnostics: TrackingDiagnostics | None,
    *,
    fps: float,
    concepts: list[str],
) -> tuple[list[ObjectTrackObservation], list[ChunkSpec], list[ChunkCall]]:
    """Attach chunk provenance to a pre-chunk-log cache (no stitching yet)."""
    n_frames = (diagnostics.frames_in_source if diagnostics else None) or 0
    notes = diagnostics.api_notes if diagnostics else []
    chunks, calls = legacy_chunk_log(notes, fps=fps, n_frames=n_frames, concepts=concepts)
    return assign_legacy_chunks(observations, chunks), chunks, calls


def normalize_legacy_result(result: TrackingResult) -> TrackingResult:
    """Upgrade a cache written before chunk logs: stitch ids, drop overlap
    duplicates, mark unrecorded outcomes as unverified. Disk is not modified."""
    if result.chunk_log is not None or result.media_kind == "image":
        return result
    concepts = list(result.concepts)
    obs, chunks, calls = _legacy_parts(
        result.observations, result.diagnostics, fps=result.fps or 30.0, concepts=concepts
    )
    stitched, links = stitch_tracks(obs, chunks)
    result.observations = stitched
    result.chunk_log = {
        "source": "legacy_notes",
        "chunks": [c.to_dict() for c in chunks],
        "calls": [c.to_dict() for c in calls],
        "links": links,
    }
    old = result.diagnostics
    result.diagnostics = build_diagnostics(
        concepts=concepts,
        observations=stitched,
        frames_in_source=old.frames_in_source if old else None,
        api_notes=(old.api_notes if old else [])
        + ["Normalized legacy cache: overlap duplicates removed, ids stitched, outcomes unverified."],
        chunks=chunks,
        calls=calls,
    )
    return result


def _video_digest(video_bytes: bytes) -> str:
    return hashlib.sha256(video_bytes).hexdigest()[:16]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "concept"


def chunk_cache_path(
    video_digest: str, chunk: ChunkSpec, concept: str, *, prompt_mode: str = "concept", tag: str = ""
) -> Path:
    prefix = f"{_slug(concept)}__k{hashlib.sha256(concept.encode()).hexdigest()[:16]}"
    name = prefix if prompt_mode == "concept" else f"{prefix}__{prompt_mode}_{tag}"
    folder = CHUNK_CACHE_ROOT / video_digest / f"f{chunk.start_frame:06d}-{chunk.end_frame:06d}"
    return folder / f"{name}.json"


def read_chunk_entry(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        # Read existing caches without renaming or overwriting historical files.
        # Every request-facing caller also validates the exact recorded identity.
        legacy = path.with_name(re.sub(r"__k[a-f0-9]{16}(?=__|\.json$)", "", path.name))
        if legacy == path or not legacy.is_file():
            return None
        path = legacy
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _chunk_paths(digest: str, chunk: ChunkSpec, concept: str) -> list[Path]:
    primary = chunk_cache_path(digest, chunk, concept)
    folder, slug = primary.parent, _slug(concept)
    paths = [folder / f"{slug}.json"] + sorted(folder.glob(f"{slug}__*.json"))
    # A newer keyed version supersedes its same-request legacy entry; do not
    # double-count observations after an explicit refresh.
    return [p for p in paths if p.name.startswith(primary.stem) or not
            p.with_name(primary.stem + p.name[len(slug):]).is_file()]


def cached_chunk_entries(digest: str, chunk: ChunkSpec, concept: str) -> list[dict[str, Any]]:
    """All reusable cached entries for one chunk x concept (concept and seeded prompts)."""
    entries = [read_chunk_entry(p) for p in _chunk_paths(digest, chunk, concept)]
    return [e for e in entries if chunk_entry_matches(e, concept, chunk) and chunk_entry_reusable(e)]


def seed_plan(
    video_bytes: bytes,
    *,
    chunk_index: int,
    concept: str,
    chunk_s: float = DEFAULT_CHUNK_S,
    overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
    max_seeds: int | None = 1,
) -> tuple[ChunkSpec, list[tuple[str, tuple[int, int, int, int], float | None]]]:
    """Dry run: seed boxes chunk_index would get from the previous chunk's cache.

    Returns (chunk, [(source local id, box, confidence)]), highest confidence first.
    """
    fps, n_frames = probe_video(video_bytes)
    chunks = plan_chunks(n_frames, max(1, int(round(chunk_s * fps))), overlap_frames=overlap_frames)
    chunk = chunks[chunk_index]
    if chunk_index == 0:
        return chunk, []
    digest = _video_digest(video_bytes)
    prev = [
        _observation_from_row(r)
        for e in cached_chunk_entries(digest, chunks[chunk_index - 1], concept)
        for r in e.get("observations") or []
    ]
    conf = {
        (o.local_object_id or o.object_id): o.confidence
        for o in prev
        if o.frame_index == chunk.start_frame
    }
    seeds = [(lid, box, conf.get(lid)) for lid, box in _seed_boxes(prev, [], chunk)]
    seeds.sort(key=lambda s: -(s[2] or 0.0))
    return chunk, seeds[:max_seeds] if max_seeds is not None else seeds


def assemble_from_chunk_cache(
    video_bytes: bytes,
    concepts: list[str],
    *,
    chunk_s: float = DEFAULT_CHUNK_S,
    overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
) -> TrackingResult:
    """Stitch every cached chunk entry (concept and box-seeded) into one result.

    No API calls. Each cached request keeps its recorded status, so frames covered
    only by legacy/unverified or missing requests stay "unknown".
    """
    fps, n_frames = probe_video(video_bytes)
    backfill_chunk_cache(video_bytes)
    digest = _video_digest(video_bytes)
    chunks = plan_chunks(n_frames, max(1, int(round(chunk_s * fps))), overlap_frames=overlap_frames)
    observations: list[ObjectTrackObservation] = []
    calls: list[ChunkCall] = []
    for chunk in chunks:
        for concept in concepts:
            for path in _chunk_paths(digest, chunk, concept):
                entry = read_chunk_entry(path)
                if not chunk_entry_matches(entry, concept, chunk):
                    continue
                calls.append(ChunkCall(**{**entry["call"], "from_cache": True}))
                observations += [_observation_from_row(r) for r in entry.get("observations") or []]
    stitched, links = stitch_tracks(observations, chunks)
    diagnostics = build_diagnostics(
        concepts=concepts,
        observations=stitched,
        frames_in_source=n_frames,
        api_notes=["Assembled from per-chunk cache (no API calls)."],
        chunks=chunks,
        calls=calls,
    )
    return TrackingResult(
        available=bool(stitched),
        provider="meta-sam-3.1",
        observations=stitched,
        concepts=concepts,
        notes="Assembled from per-chunk cache (no API calls).",
        fps=fps,
        from_cache=True,
        diagnostics=diagnostics,
        media_kind="video",
        chunk_log={
            "source": "chunk_cache",
            "overlap_frames": overlap_frames,
            "chunks": [c.to_dict() for c in chunks],
            "calls": [c.to_dict() for c in calls],
            "links": links,
        },
    )


def window_chunk(start_frame: int, end_frame: int) -> ChunkSpec:
    """A free-standing window (not on the 4 s grid); cached like any chunk by its frame range."""
    return ChunkSpec(index=-1, start_frame=start_frame, end_frame=end_frame, owned_end_frame=end_frame)


def plan_window_calls(video_bytes: bytes, *, start_frame: int, end_frame: int, concepts: list[str]) -> list[dict[str, Any]]:
    """Dry run for one window: cached vs paid video requests (no API key needed)."""
    chunk = window_chunk(start_frame, end_frame)
    digest = _video_digest(video_bytes)
    rows = []
    for concept in concepts:
        entry = read_chunk_entry(chunk_cache_path(digest, chunk, concept))
        if not chunk_entry_matches(entry, concept, chunk):
            entry = None
        rows.append({"frames": f"{start_frame}-{end_frame - 1}", "n_frames": end_frame - start_frame,
                     "concept": concept, "cached_status": (entry or {}).get("call", {}).get("status"),
                     "action": "cached" if chunk_entry_reusable(entry) else "PAID CALL"})
    return rows


def _chunk_entry_files(video_bytes: bytes, concepts: list[str]) -> list[Path]:
    folder = CHUNK_CACHE_ROOT / _video_digest(video_bytes)
    return sorted(p for c in concepts for p in folder.glob(f"f*/{_slug(c)}*.json")
                  if chunk_entry_matches(read_chunk_entry(p), c))


def load_assembled_tracking(video_bytes: bytes, concepts: list[str]) -> TrackingResult | None:
    """Latest stitched result from the chunk cache, with mask overlays (no API).

    Returns None unless every concept has at least one cached chunk entry, so
    callers can fall back to the full-video summary cache. Overlays are rendered
    once per distinct set of cached entries.
    """
    backfill_chunk_cache(video_bytes)
    files = _chunk_entry_files(video_bytes, concepts)
    if not all(any(chunk_entry_matches(read_chunk_entry(p), c) for p in files) for c in concepts):
        return None
    sig = hashlib.sha256(
        "|".join(concepts).encode() + b"".join(f"{p.parent.name}/{p.name}:{p.stat().st_size}".encode() for p in files)
    ).hexdigest()[:12]
    result = assemble_from_chunk_cache(video_bytes, concepts)
    folder = TRACKING_ROOT / "assembled" / f"{_video_digest(video_bytes)}_{sig}"
    result.cache_dir = str(folder)
    overlays = sorted(folder.glob(f"{MASK_OVERLAY_DIR}/*.png"))
    if not overlays and result.observations:
        overlays = render_and_save_overlays(video_bytes, result, folder / MASK_OVERLAY_DIR)
    result.overlay_paths = [str(p) for p in overlays]
    return result


# --- Keyframe probes -------------------------------------------------------
# One SAM image request on one frame with a manually selected box. Stored apart
# from the chunk cache under their own track id, so they are never stitched to
# a continuous track.

PROBE_ROOT = TRACKING_ROOT / "probes"


@dataclass
class ProbeRequest:
    frame_index: int
    timestamp_s: float
    concept: str
    box: tuple[int, int, int, int]  # half-open, full-frame pixels
    selected_by: str
    prompt_text: str
    image_png: bytes
    path: Path

    @property
    def cached(self) -> bool:
        return self.path.is_file()


def extract_frame_rgb(video_bytes: bytes, frame_index: int) -> np.ndarray:
    import av

    with av.open(io.BytesIO(video_bytes)) as container:
        for i, frame in enumerate(container.decode(video=0)):
            if i == frame_index:
                return frame.to_ndarray(format="rgb24")
    raise ValueError(f"Frame {frame_index} not in video.")


def prepare_box_probe(
    video_bytes: bytes,
    *,
    frame_index: int,
    box: tuple[int, int, int, int],
    concept: str = "screwdriver",
    selected_by: str = "manual",
) -> ProbeRequest:
    """Build (but do not send) the image request for a manual box on one frame."""
    rgb = extract_frame_rgb(video_bytes, frame_index)
    h, w = rgb.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        raise ValueError(f"Box {box} is outside the {w}x{h} frame or empty.")
    ok, png = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        raise ValueError("PNG encoding failed.")
    fps, _ = probe_video(video_bytes)
    path = (PROBE_ROOT / _video_digest(video_bytes)
            / f"f{frame_index:06d}_{_slug(concept)}_box_{x1}_{y1}_{x2}_{y2}.json")
    return ProbeRequest(frame_index, round(frame_index / fps, 3), concept, (x1, y1, x2, y2), selected_by,
                        build_seed_prompt((w, h), 0, (x1, y1, x2, y2)), png.tobytes(), path)


def probe_preview(video_bytes: bytes, request: ProbeRequest) -> np.ndarray:
    """RGB frame with the selected box drawn (what will be sent, plus the box)."""
    rgb = extract_frame_rgb(video_bytes, request.frame_index).copy()
    x1, y1, x2, y2 = request.box
    cv2.rectangle(rgb, (x1, y1), (x2 - 1, y2 - 1), (255, 140, 0), 2)
    return rgb


def run_box_probe(request: ProbeRequest) -> dict[str, Any]:
    """PAID: one SAM image request. Returns the stored probe record (cached afterwards)."""
    if request.cached:
        return json.loads(request.path.read_text(encoding="utf-8"))
    load_model_api_key()

    async def _go() -> dict[str, Any]:
        from sam_api import segment_image_bytes

        usage: dict[str, Any] = {}
        try:
            result = await segment_image_bytes(request.image_png, request.prompt_text, mime="image/png", usage_out=usage)
        except Exception as err:  # noqa: BLE001
            return {"status": "failed", "reason": f"{type(err).__name__}: {err}", "usage": usage or None, "observations": []}
        status = "completed" if getattr(result.outcome, "status", None) == "completed" else "incomplete"
        obs = [
            replace(o, frame_index=request.frame_index, timestamp_s=request.timestamp_s,
                    object_id=f"{request.concept}:probe-f{request.frame_index}", chunk_index=None,
                    local_object_id=o.object_id.split(":")[-1], prompt_mode="image_box")
            for o in observations_from_result(result, concept=request.concept, fps=1.0, media_kind="image")
        ]
        return {"status": status, "reason": getattr(result.outcome, "reason", None), "usage": usage or None,
                "n_records": len(result.records), "observations": [asdict(o) for o in obs]}

    outcome = _run_coro(_go())
    record = {
        "model": SAM_MODEL,
        "frame_index": request.frame_index,
        "timestamp_s": request.timestamp_s,
        "concept": request.concept,
        "box": list(request.box),
        "selected_by": request.selected_by,
        "prompt_text": request.prompt_text,
        "linking": "not stitched: separate track id, observation after an occlusion/tracking gap",
        **outcome,
    }
    if outcome["status"] != "failed":
        request.path.parent.mkdir(parents=True, exist_ok=True)
        request.path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def load_probe_observations(video_bytes: bytes, concept: str) -> list[ObjectTrackObservation]:
    """Detections from completed keyframe probes (each keeps its own probe track id)."""
    out: list[ObjectTrackObservation] = []
    for path in sorted((PROBE_ROOT / _video_digest(video_bytes)).glob(f"f*_{_slug(concept)}_box_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("status") == "completed":
            out += [_observation_from_row(r) for r in record.get("observations") or []]
    return out


def chunk_entry_matches(entry: dict[str, Any] | None, concept: str,
                        chunk: ChunkSpec | None = None, prompt_text: str | None = None) -> bool:
    """A filename/slug is not request identity; validate recorded provenance."""
    if not entry or entry.get("model") != SAM_MODEL or (entry.get("call") or {}).get("concept") != concept:
        return False
    if chunk is not None and any((entry.get("chunk") or {}).get(k) != getattr(chunk, k)
                                 for k in ("start_frame", "end_frame", "owned_end_frame")):
        return False
    if prompt_text is not None and entry.get("prompt_text") != prompt_text:
        return False
    return all(row.get("concept") == concept for row in entry.get("observations") or [])


def chunk_entry_reusable(entry: dict[str, Any] | None) -> bool:
    """Completed calls are reusable. Legacy calls with unrecorded outcomes are
    reused only if they returned detections (frames they did not cover still
    read as unknown); empty unverified results are worth re-running."""
    if not entry:
        return False
    call = entry.get("call") or {}
    status = call.get("status")
    if status == "completed":
        return True
    return status == "unverified" and int(call.get("n_observations") or 0) > 0


def write_chunk_entry(
    path: Path,
    *,
    chunk: ChunkSpec,
    call: ChunkCall,
    observations: list[ObjectTrackObservation],
    prompt_text: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": SAM_MODEL,
        "chunk": chunk.to_dict(),
        "call": call.to_dict(),
        "prompt_text": prompt_text,
        "observations": [asdict(o) for o in observations],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def backfill_chunk_cache(video_bytes: bytes) -> int:
    """Split legacy full-video summaries for this video into per-chunk entries.

    Re-indexes real cached detections only; never overwrites an existing entry.
    Returns the number of entries written.
    """
    digest = _video_digest(video_bytes)
    written = 0
    for summary in sorted(TRACKING_ROOT.glob("*/summary.json")):
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("media_kind") != "video" or data.get("chunk_log") is not None:
            continue
        concepts = list(data.get("concepts") or [])
        if cache_key(video_bytes, concepts, media_kind="video") != summary.parent.name:
            continue
        diag_raw = data.get("diagnostics")
        diagnostics = TrackingDiagnostics(**diag_raw) if isinstance(diag_raw, dict) else None
        observations = [_observation_from_row(r) for r in data.get("observations") or []]
        obs, chunks, calls = _legacy_parts(
            observations, diagnostics, fps=float(data.get("fps") or 30.0), concepts=concepts
        )
        by_chunk = {c.index: c for c in chunks}
        for call in calls:
            chunk = by_chunk.get(call.chunk_index)
            if chunk is None or call.status == "failed":
                continue
            path = chunk_cache_path(digest, chunk, call.concept)
            if path.exists():
                continue
            mine = [o for o in obs if o.concept == call.concept and o.chunk_index == chunk.index]
            write_chunk_entry(path, chunk=chunk, call=call, observations=mine)
            written += 1
    return written


def plan_tracking_calls(
    video_bytes: bytes,
    concepts: list[str],
    *,
    chunk_s: float = DEFAULT_CHUNK_S,
    overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
) -> list[dict[str, Any]]:
    """Dry run: which chunk x concept requests are cached vs would be paid calls."""
    fps, n_frames = probe_video(video_bytes)
    backfill_chunk_cache(video_bytes)
    digest = _video_digest(video_bytes)
    rows = []
    for chunk in plan_chunks(n_frames, max(1, int(round(chunk_s * fps))), overlap_frames=overlap_frames):
        for concept in concepts:
            entry = read_chunk_entry(chunk_cache_path(digest, chunk, concept))
            if not chunk_entry_matches(entry, concept, chunk):
                entry = None
            rows.append(
                {
                    "chunk": chunk.index,
                    "frames": f"{chunk.start_frame}-{chunk.end_frame - 1}",
                    "concept": concept,
                    "cached_status": (entry or {}).get("call", {}).get("status"),
                    "action": "cached" if chunk_entry_reusable(entry) else "PAID CALL",
                }
            )
    return rows


def load_cached_tracking(
    video_bytes: bytes,
    concepts: list[str],
    *,
    media_kind: str = "video",
) -> TrackingResult | None:
    key = cache_key(video_bytes, concepts, media_kind=media_kind)
    for root in (TRACKING_ROOT, LEGACY_CACHE_ROOT):
        folder = root / key
        summary = folder / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        observations = [_observation_from_row(row) for row in data.get("observations") or []]
        # Prefer mask-rendered overlays; overlays/ from older runs drew boxes only.
        overlays = sorted(str(p) for p in folder.glob(f"{MASK_OVERLAY_DIR}/*.png")) or sorted(
            str(p) for p in folder.glob("overlays/*.png")
        )
        diag_raw = data.get("diagnostics")
        diagnostics = TrackingDiagnostics(**diag_raw) if isinstance(diag_raw, dict) else None
        result = TrackingResult(
            available=True,
            provider=str(data.get("provider") or "meta-sam-3.1"),
            observations=observations,
            notes=str(data.get("notes") or "Loaded from local cache (no new API call)."),
            concepts=list(data.get("concepts") or concepts),
            cache_dir=str(folder),
            overlay_paths=overlays,
            fps=data.get("fps"),
            from_cache=True,
            diagnostics=diagnostics,
            media_kind=str(data.get("media_kind") or media_kind),
            chunk_log=data.get("chunk_log"),
        )
        return normalize_legacy_result(result)
    return None


def save_tracking_cache(
    result: TrackingResult,
    payload: bytes,
    concepts: list[str],
    *,
    media_kind: str,
) -> Path:
    key = cache_key(payload, concepts, media_kind=media_kind)
    folder = TRACKING_ROOT / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "overlays").mkdir(exist_ok=True)
    payload_dict = result.to_dict()
    payload_dict["cache_key"] = key
    payload_dict["model"] = SAM_MODEL
    (folder / "summary.json").write_text(json.dumps(payload_dict, indent=2), encoding="utf-8")
    result.cache_dir = str(folder)
    return folder


def _call_note(call: ChunkCall) -> str:
    text = (
        f"chunk{call.chunk_index}/{call.concept}[{call.prompt_mode}]: status={call.status} "
        f"records={call.n_records} observations={call.n_observations}"
    )
    if call.from_cache:
        text += " (cached)"
    if call.reason:
        text += f" reason={call.reason}"
    return text


def build_seed_prompt(
    size: tuple[int, int], object_id: int, box: tuple[int, int, int, int], *, frame: int = 0
) -> str:
    """SAM object-prompt text: one box on one clip frame (official builder)."""
    from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt

    width, height = size
    x1, y1, x2, y2 = box
    x1, y1 = max(0, min(x1, width - 1)), max(0, min(y1, height - 1))
    x2, y2 = max(x1 + 1, min(x2, width)), max(y1 + 1, min(y2, height))
    return build_object_prompt(
        size=(width, height),
        objects=[
            PromptObject(
                id=object_id,
                prompts=[FramePrompt(frame=frame, box=PromptBox(x1, y1, x2, y2))],
            )
        ],
    )


def _seed_boxes(
    previous: list[ObjectTrackObservation],
    current: list[ObjectTrackObservation],
    chunk: ChunkSpec,
    *,
    iou_threshold: float = 0.5,
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Boxes the previous chunk observed on this chunk's first (overlap) frame
    that the current concept request did not re-find there."""
    from track_stitch import bbox_iou

    here = [o.bbox for o in current if o.frame_index == chunk.start_frame and o.bbox]
    seeds = []
    for o in previous:
        if o.frame_index != chunk.start_frame or not o.bbox:
            continue
        if any(bbox_iou(o.bbox, b) >= iou_threshold for b in here):
            continue
        box = tuple(int(round(v)) for v in o.bbox)
        seeds.append((o.local_object_id or o.object_id, box))  # type: ignore[arg-type]
    return seeds


class Sam31Tracker:
    """Hosted Meta SAM 3.1 tracker (one request per concept)."""

    def track_video(
        self,
        video_bytes: bytes,
        *,
        object_prompts: list[str] | None = None,
        force_refresh: bool = False,
        media_kind: str = "video",
        chunk_s: float = DEFAULT_CHUNK_S,
        overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
        seed_from_previous: bool = False,
    ) -> TrackingResult:
        concepts = [c.strip() for c in (object_prompts or list(DEFAULT_SO101_CONCEPTS)) if c.strip()]
        if not concepts:
            concepts = list(DEFAULT_SO101_CONCEPTS[:2])

        if not force_refresh:
            cached = load_cached_tracking(video_bytes, concepts, media_kind=media_kind)
            if cached is not None:
                return cached

        try:
            load_model_api_key()
        except ModelApiConfigError as err:
            return TrackingResult(
                available=False,
                provider="none",
                concepts=concepts,
                notes=str(err),
                media_kind=media_kind,
            )

        try:
            return _run_coro(
                self._track_async(
                    video_bytes,
                    concepts=concepts,
                    media_kind=media_kind,
                    chunk_s=chunk_s,
                    overlap_frames=overlap_frames,
                    seed_from_previous=seed_from_previous,
                    force_refresh=force_refresh,
                )
            )
        except Exception as error:  # noqa: BLE001
            return TrackingResult(
                available=False,
                provider="meta-sam-3.1",
                concepts=concepts,
                notes=f"SAM 3.1 tracking failed: {type(error).__name__}: {error}",
                media_kind=media_kind,
            )

    def segment_image(
        self,
        image_bytes: bytes,
        *,
        concept: str = "screwdriver",
        force_refresh: bool = False,
    ) -> TrackingResult:
        return self.track_video(
            image_bytes,
            object_prompts=[concept],
            force_refresh=force_refresh,
            media_kind="image",
        )

    async def _track_chunked(
        self,
        video_bytes: bytes,
        *,
        concepts: list[str],
        fps: float,
        n_frames: int,
        chunk_s: float = DEFAULT_CHUNK_S,
        overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
        seed_from_previous: bool = False,
        force_refresh: bool = False,
    ) -> tuple[list[ObjectTrackObservation], list[ChunkSpec], list[ChunkCall], list[str]]:
        """Run one SAM request per chunk x concept, cached per chunk and concept.

        SAM object ids stay chunk-local (local_object_id); global identity is
        assigned afterwards by stitch_tracks. Upload happens lazily, only for
        chunks that still need a request.
        """
        from sam_api import upload_video

        digest = _video_digest(video_bytes)
        backfilled = backfill_chunk_cache(video_bytes)
        chunks = plan_chunks(
            n_frames, max(1, int(round(chunk_s * fps))), overlap_frames=overlap_frames
        )
        notes = [
            f"chunk plan: {len(chunks)} chunks x {chunk_s:.1f}s, overlap={overlap_frames} frame(s), "
            f"legacy entries backfilled={backfilled}"
        ]
        merged: list[ObjectTrackObservation] = []
        calls: list[ChunkCall] = []
        size = probe_video_size(video_bytes) if seed_from_previous else None
        prev_chunk_obs: dict[str, list[ObjectTrackObservation]] = {}

        for chunk in chunks:
            file_id: str | None = None

            async def ensure_uploaded() -> str:
                nonlocal file_id
                if file_id is None:
                    clip = extract_frame_range_mp4(
                        video_bytes, start_frame=chunk.start_frame, end_frame=chunk.end_frame
                    )
                    file_id = await upload_video(ensure_h264_mp4(clip))
                    notes.append(
                        f"chunk{chunk.index}: frames {chunk.start_frame}-{chunk.end_frame - 1} "
                        f"file_id={file_id}"
                    )
                return file_id

            for concept in concepts:
                obs, call = await self._run_chunk_call(
                    chunk=chunk,
                    concept=concept,
                    prompt_text=concept,
                    prompt_mode="concept",
                    tag="",
                    digest=digest,
                    fps=fps,
                    ensure_uploaded=ensure_uploaded,
                    force_refresh=force_refresh,
                )
                calls.append(call)
                notes.append(_call_note(call))
                chunk_obs = list(obs)
                if size is not None:
                    for local_id, box in _seed_boxes(prev_chunk_obs.get(concept, []), obs, chunk):
                        seed_obs, seed_call = await self._run_chunk_call(
                            chunk=chunk,
                            concept=concept,
                            prompt_text=build_seed_prompt(size, 0, box),
                            prompt_mode="box_seed",
                            tag="_".join(str(v) for v in box),
                            digest=digest,
                            fps=fps,
                            ensure_uploaded=ensure_uploaded,
                            force_refresh=force_refresh,
                        )
                        calls.append(seed_call)
                        notes.append(_call_note(seed_call) + f" seed_from={local_id} box={box}")
                        chunk_obs.extend(seed_obs)
                merged.extend(chunk_obs)
                prev_chunk_obs[concept] = chunk_obs
        return merged, chunks, calls, notes

    def track_window(
        self, video_bytes: bytes, *, start_frame: int, end_frame: int, concepts: list[str], force_refresh: bool = False,
    ) -> tuple[ChunkSpec, list[ObjectTrackObservation], list[ChunkCall]]:
        """PAID (unless cached): one concept request per concept on frames [start_frame, end_frame)."""
        async def _go() -> tuple[ChunkSpec, list[ObjectTrackObservation], list[ChunkCall]]:
            from sam_api import upload_video

            fps, _ = probe_video(video_bytes)
            chunk = window_chunk(start_frame, end_frame)
            digest = _video_digest(video_bytes)
            file_id: str | None = None

            async def ensure_uploaded() -> str:
                nonlocal file_id
                if file_id is None:
                    clip = extract_frame_range_mp4(video_bytes, start_frame=start_frame, end_frame=end_frame)
                    file_id = await upload_video(ensure_h264_mp4(clip))
                return file_id

            obs: list[ObjectTrackObservation] = []
            calls: list[ChunkCall] = []
            for concept in concepts:
                o, c = await self._run_chunk_call(
                    chunk=chunk, concept=concept, prompt_text=concept, prompt_mode="concept", tag="",
                    digest=digest, fps=fps, ensure_uploaded=ensure_uploaded, force_refresh=force_refresh)
                obs += o
                calls.append(c)
            return chunk, obs, calls

        return _run_coro(_go())

    def track_single_chunk(
        self,
        video_bytes: bytes,
        *,
        chunk_index: int,
        concepts: list[str],
        chunk_s: float = DEFAULT_CHUNK_S,
        overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
        seed_from_previous: bool = False,
        force_refresh: bool = False,
        seed_only: bool = False,
        max_seeds: int | None = None,
    ) -> tuple[ChunkSpec, list[ObjectTrackObservation], list[ChunkCall]]:
        """Diagnostic probe: run (or load) one chunk of the full-video plan.

        Seeds come from the previous chunk's cached entries (concept and seeded),
        so probing chunk k never re-runs chunk k-1. seed_only skips the concept
        request; max_seeds caps seeded requests (highest-confidence first).
        Results land in the shared chunk cache.
        """
        return _run_coro(
            self._single_chunk_async(
                video_bytes,
                chunk_index=chunk_index,
                concepts=concepts,
                chunk_s=chunk_s,
                overlap_frames=overlap_frames,
                seed_from_previous=seed_from_previous or seed_only,
                force_refresh=force_refresh,
                seed_only=seed_only,
                max_seeds=max_seeds,
            )
        )

    async def _single_chunk_async(
        self,
        video_bytes: bytes,
        *,
        chunk_index: int,
        concepts: list[str],
        chunk_s: float,
        overlap_frames: int,
        seed_from_previous: bool,
        force_refresh: bool,
        seed_only: bool = False,
        max_seeds: int | None = None,
    ) -> tuple[ChunkSpec, list[ObjectTrackObservation], list[ChunkCall]]:
        from sam_api import upload_video

        fps, n_frames = probe_video(video_bytes)
        backfill_chunk_cache(video_bytes)
        chunks = plan_chunks(n_frames, max(1, int(round(chunk_s * fps))), overlap_frames=overlap_frames)
        chunk = chunks[chunk_index]
        digest = _video_digest(video_bytes)
        file_id: str | None = None

        async def ensure_uploaded() -> str:
            nonlocal file_id
            if file_id is None:
                clip = extract_frame_range_mp4(
                    video_bytes, start_frame=chunk.start_frame, end_frame=chunk.end_frame
                )
                file_id = await upload_video(ensure_h264_mp4(clip))
            return file_id

        all_obs: list[ObjectTrackObservation] = []
        calls: list[ChunkCall] = []
        size = probe_video_size(video_bytes) if seed_from_previous else None
        for concept in concepts:
            obs: list[ObjectTrackObservation] = []
            if not seed_only:
                obs, call = await self._run_chunk_call(
                    chunk=chunk, concept=concept, prompt_text=concept, prompt_mode="concept", tag="",
                    digest=digest, fps=fps, ensure_uploaded=ensure_uploaded, force_refresh=force_refresh,
                )
                all_obs.extend(obs)
                calls.append(call)
            if size is not None and chunk_index > 0:
                prev = [
                    _observation_from_row(r)
                    for e in cached_chunk_entries(digest, chunks[chunk_index - 1], concept)
                    for r in e.get("observations") or []
                ]
                conf = {(o.local_object_id or o.object_id): o.confidence or 0.0
                        for o in prev if o.frame_index == chunk.start_frame}
                seeds = sorted(_seed_boxes(prev, obs, chunk), key=lambda s: -conf.get(s[0], 0.0))
                if max_seeds is not None:
                    seeds = seeds[:max_seeds]
                for _, box in seeds:
                    seed_obs, seed_call = await self._run_chunk_call(
                        chunk=chunk, concept=concept, prompt_text=build_seed_prompt(size, 0, box),
                        prompt_mode="box_seed", tag="_".join(str(v) for v in box), digest=digest,
                        fps=fps, ensure_uploaded=ensure_uploaded, force_refresh=force_refresh,
                    )
                    all_obs.extend(seed_obs)
                    calls.append(seed_call)
        return chunk, all_obs, calls

    async def _run_chunk_call(
        self,
        *,
        chunk: ChunkSpec,
        concept: str,
        prompt_text: str,
        prompt_mode: str,
        tag: str,
        digest: str,
        fps: float,
        ensure_uploaded: Any,
        force_refresh: bool,
    ) -> tuple[list[ObjectTrackObservation], ChunkCall]:
        from sam_api import segment_video

        path = chunk_cache_path(digest, chunk, concept, prompt_mode=prompt_mode, tag=tag)
        entry = None if force_refresh else read_chunk_entry(path)
        if chunk_entry_matches(entry, concept, chunk, prompt_text) and chunk_entry_reusable(entry):
            obs = [_observation_from_row(r) for r in entry.get("observations") or []]
            return obs, ChunkCall(**{**entry["call"], "from_cache": True})

        file_id: str | None = None
        usage_out: dict[str, Any] = {}
        try:
            file_id = await ensure_uploaded()
            result = await segment_video(file_id, prompt_text, usage_out=usage_out)
        except Exception as err:  # noqa: BLE001
            return [], ChunkCall(
                chunk.index,
                concept,
                "failed",
                reason=f"{type(err).__name__}: {err}",
                file_id=file_id,
                prompt_mode=prompt_mode,
                usage=usage_out or None,
            )

        outcome = result.outcome
        status = "completed" if getattr(outcome, "status", None) == "completed" else "incomplete"
        reasons = []
        if status == "incomplete":
            reasons += [str(x) for x in (getattr(outcome, "reason", None), getattr(outcome, "detail", None)) if x]
        obs: list[ObjectTrackObservation] = []
        out_of_range = 0
        for item in observations_from_result(result, concept=concept, fps=fps, media_kind="clip"):
            global_fi = (item.frame_index if item.frame_index is not None else 0) + chunk.start_frame
            if not chunk.contains(global_fi):
                out_of_range += 1
                continue
            local = item.object_id.split(":")[-1]
            obs.append(
                replace(
                    item,
                    frame_index=global_fi,
                    timestamp_s=round(global_fi / max(fps, 1e-6), 3),
                    chunk_index=chunk.index,
                    local_object_id=local if prompt_mode == "concept" else f"{prompt_mode}-{local}",
                    prompt_mode=prompt_mode,
                )
            )
        if out_of_range:
            reasons.append(f"dropped {out_of_range} records outside chunk frame range")
        if result.diagnostics:
            reasons.append(f"parser diagnostics={len(result.diagnostics)}")
        call = ChunkCall(
            chunk.index,
            concept,
            status,  # type: ignore[arg-type]
            reason="; ".join(reasons) or None,
            n_records=len(result.records),
            n_observations=len(obs),
            file_id=file_id,
            prompt_mode=prompt_mode,
            usage=usage_out or None,
        )
        write_chunk_entry(path, chunk=chunk, call=call, observations=obs, prompt_text=prompt_text)
        return obs, call

    async def _track_async(
        self,
        payload: bytes,
        *,
        concepts: list[str],
        media_kind: str,
        chunk_s: float = DEFAULT_CHUNK_S,
        overlap_frames: int = DEFAULT_OVERLAP_FRAMES,
        seed_from_previous: bool = False,
        force_refresh: bool = False,
    ) -> TrackingResult:
        from sam_api import segment_image_bytes, segment_video, upload_video

        api_notes: list[str] = []
        all_observations: list[ObjectTrackObservation] = []
        fps = 30.0
        frames_in_source: int | None = None
        chunks: list[ChunkSpec] | None = None
        calls: list[ChunkCall] | None = None
        links: list[dict[str, Any]] = []
        image_usage: dict[str, Any] = {}

        if media_kind == "image":
            fps = 0.0
            frames_in_source = 1
            for concept in concepts:
                api_notes.append(f"image concept={concept!r}")
                usage_out: dict[str, Any] = {}
                result = await segment_image_bytes(payload, concept, usage_out=usage_out)
                outcome = getattr(result.outcome, "status", None)
                api_notes.append(f"{concept}: outcome={outcome}")
                image_usage[concept] = {
                    **usage_out,
                    "segmentation_outcome": outcome,
                    "parser_record_count": len(result.records),
                    "parser_diagnostics": [str(d) for d in getattr(result, "diagnostics", ())],
                    "raw_output": getattr(result, "raw_output", None),
                }
                obs = observations_from_result(
                    result, concept=concept, fps=1.0, media_kind="image"
                )
                if not obs:
                    api_notes.append(
                        f"{concept}: zero matches (valid empty)."
                        if outcome == "completed"
                        else f"{concept}: zero matches but response incomplete (not a confirmed empty)."
                    )
                all_observations.extend(obs)
        else:
            fps, frames_in_source = probe_video(payload)
            duration_s = (frames_in_source / fps) if frames_in_source and fps else 0.0
            # Long streams have been observed to fail near completion on Meta's
            # Responses stream. Chunk into short real SAM calls and stitch by
            # global frame index — still real detections, never fabricated.
            use_chunks = media_kind == "video" and duration_s > 5.5
            if use_chunks:
                api_notes.append(
                    f"Chunked full-video tracking ({duration_s:.1f}s @ {fps:.1f}fps)."
                )
                chunk_obs, chunks, calls, chunk_notes = await self._track_chunked(
                    payload,
                    concepts=concepts,
                    fps=fps,
                    n_frames=frames_in_source,
                    chunk_s=chunk_s,
                    overlap_frames=overlap_frames,
                    seed_from_previous=seed_from_previous,
                    force_refresh=force_refresh,
                )
                api_notes.extend(chunk_notes)
                all_observations, links = stitch_tracks(chunk_obs, chunks)
            else:
                upload_path = ensure_h264_mp4(payload)
                file_id = await upload_video(upload_path)
                api_notes.append(f"Uploaded {upload_path.name} as {file_id}")
                chunks = [ChunkSpec(0, 0, frames_in_source, frames_in_source)]
                calls = []
                for concept in concepts:
                    api_notes.append(f"video concept={concept!r}")
                    try:
                        result = await segment_video(file_id, concept)
                    except Exception as concept_error:  # noqa: BLE001
                        api_notes.append(
                            f"{concept}: FAILED {type(concept_error).__name__}: {concept_error}"
                        )
                        calls.append(
                            ChunkCall(0, concept, "failed", reason=str(concept_error), file_id=file_id)
                        )
                        continue
                    outcome = getattr(result.outcome, "status", None)
                    api_notes.append(
                        f"{concept}: outcome={outcome} records={len(result.records)}"
                    )
                    obs = observations_from_result(
                        result, concept=concept, fps=fps, media_kind=media_kind
                    )
                    obs = [
                        replace(o, chunk_index=0, local_object_id=o.object_id.split(":")[-1])
                        for o in obs
                    ]
                    calls.append(
                        ChunkCall(
                            0,
                            concept,
                            "completed" if outcome == "completed" else "incomplete",
                            reason=getattr(result.outcome, "reason", None),
                            n_records=len(result.records),
                            n_observations=len(obs),
                            file_id=file_id,
                        )
                    )
                    if not obs:
                        api_notes.append(
                            f"{concept}: zero matches (valid empty)."
                            if outcome == "completed"
                            else f"{concept}: zero matches but response incomplete (not a confirmed empty)."
                        )
                    all_observations.extend(obs)

        all_observations.sort(key=lambda o: (o.timestamp_s, o.concept, o.object_id))
        diagnostics = build_diagnostics(
            concepts=concepts,
            observations=all_observations,
            frames_in_source=frames_in_source,
            api_notes=api_notes,
            chunks=chunks,
            calls=calls,
        )
        if image_usage:
            diagnostics.usage = image_usage
        tracking = TrackingResult(
            available=bool(all_observations),
            provider="meta-sam-3.1",
            observations=all_observations,
            concepts=concepts,
            notes=" | ".join(api_notes),
            fps=fps if media_kind != "image" else None,
            from_cache=False,
            diagnostics=diagnostics,
            media_kind=media_kind,
            chunk_log=None
            if chunks is None
            else {
                "source": "recorded",
                "overlap_frames": overlap_frames,
                "chunks": [c.to_dict() for c in chunks],
                "calls": [c.to_dict() for c in (calls or [])],
                "links": links,
            },
        )
        if not all_observations:
            tracking.notes += " | No objects tracked; refusing to invent masks."
            folder = save_tracking_cache(tracking, payload, concepts, media_kind=media_kind)
            tracking.cache_dir = str(folder)
            return tracking

        folder = save_tracking_cache(tracking, payload, concepts, media_kind=media_kind)
        if media_kind == "image":
            overlays = render_image_overlay(payload, tracking, folder / "overlays")
        else:
            overlays = render_and_save_overlays(payload, tracking, folder / "overlays")
        tracking.overlay_paths = [str(p) for p in overlays]
        save_tracking_cache(tracking, payload, concepts, media_kind=media_kind)
        return tracking


def render_image_overlay(
    image_bytes: bytes,
    result: TrackingResult,
    overlay_dir: Path,
) -> list[Path]:
    overlay_dir.mkdir(parents=True, exist_ok=True)
    for old in overlay_dir.glob("*.png"):
        old.unlink()
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return []
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    canvas = rgb.copy()
    for obs in result.observations:
        color = CONCEPT_COLORS.get(obs.concept, (255, 160, 0))
        if obs.mask_rle:
            _paint_rle(canvas, obs.mask_rle, color, obs.bbox)
        if obs.bbox:
            x1, y1, x2, y2 = [int(v) for v in obs.bbox]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                canvas,
                f"{obs.concept}:{obs.object_id.split(':')[-1]}",
                (x1, max(16, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )
    out = overlay_dir / "image_overlay.png"
    cv2.imwrite(str(out), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    return [out]


def render_and_save_overlays(
    video_bytes: bytes,
    result: TrackingResult,
    overlay_dir: Path,
    *,
    max_frames: int = 12,
) -> list[Path]:
    import av

    overlay_dir.mkdir(parents=True, exist_ok=True)
    for old in overlay_dir.glob("*.png"):
        old.unlink()

    by_frame: dict[int, list[ObjectTrackObservation]] = {}
    for obs in result.observations:
        if obs.frame_index is None:
            continue
        by_frame.setdefault(obs.frame_index, []).append(obs)
    if not by_frame:
        return []

    frame_indices = sorted(by_frame)
    if len(frame_indices) > max_frames:
        picks = np.linspace(0, len(frame_indices) - 1, max_frames, dtype=int)
        frame_indices = [frame_indices[i] for i in picks]
    wanted = set(frame_indices)
    saved: list[Path] = []

    with av.open(io.BytesIO(video_bytes)) as container:
        decoded = 0
        for frame in container.decode(video=0):
            if decoded in wanted:
                rgb = frame.to_ndarray(format="rgb24")
                canvas = rgb.copy()
                for obs in by_frame.get(decoded, []):
                    color = CONCEPT_COLORS.get(obs.concept, (255, 160, 0))
                    if obs.mask_rle:
                        _paint_rle(canvas, obs.mask_rle, color, obs.bbox)
                    if obs.bbox:
                        x1, y1, x2, y2 = [int(v) for v in obs.bbox]
                        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(
                            canvas,
                            f"{obs.concept}:{obs.object_id.split(':')[-1]}",
                            (x1, max(16, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            1,
                            cv2.LINE_AA,
                        )
                ts = by_frame[decoded][0].timestamp_s
                out = overlay_dir / f"frame_{decoded:06d}_{ts:.2f}s.png"
                cv2.imwrite(str(out), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
                saved.append(out)
            decoded += 1
            if decoded > max(wanted):
                break
    return saved


def render_cached_mask_overlays(payload: bytes, result: TrackingResult) -> list[Path]:
    """Re-render a cached result's overlays with pixel masks (no API call).

    Writes to <cache>/overlays_masks/ so the original overlays/ stay untouched.
    """
    if not result.cache_dir:
        return []
    out_dir = Path(result.cache_dir) / MASK_OVERLAY_DIR
    if result.media_kind == "image":
        paths = render_image_overlay(payload, result, out_dir)
    else:
        paths = render_and_save_overlays(payload, result, out_dir)
    result.overlay_paths = [str(p) for p in paths]
    return paths


def _coco_counts(counts: str | list[int]) -> list[int]:
    """Run lengths from COCO RLE counts (uncompressed list or compressed string)."""
    if not isinstance(counts, str):
        return [int(c) for c in counts]
    out: list[int] = []
    pos = 0
    while pos < len(counts):
        value = 0
        shift = 0
        more = True
        while more:
            c = ord(counts[pos]) - 48
            value |= (c & 0x1F) << (5 * shift)
            more = bool(c & 0x20)
            pos += 1
            shift += 1
            if not more and c & 0x10:
                value |= -1 << (5 * shift)
        if len(out) > 2:
            value += out[-2]
        out.append(value)
    return out


def decode_mask_rle(mask_rle: dict[str, Any]) -> np.ndarray:
    """Decode a stored SAM mask to a bool array of its own raster size (h, w).

    SAM masks are box-local: the raster covers the detection box, not the frame.
    Runs alternate 0/1 starting with 0, in column-major order.
    """
    height, width = int(mask_rle["size"][0]), int(mask_rle["size"][1])
    runs = _coco_counts(mask_rle["counts"])
    if sum(runs) != height * width or any(r < 0 for r in runs):
        raise ValueError(f"RLE runs sum to {sum(runs)}, expected {height * width}.")
    flat = np.repeat(np.arange(len(runs)) % 2, runs).astype(bool)
    return flat.reshape((height, width), order="F")


def mask_in_frame(
    mask_rle: dict[str, Any],
    bbox: tuple[float, float, float, float],
    frame_shape: tuple[int, int],
) -> np.ndarray | None:
    """Place a box-local mask into a full-frame bool array at the bbox origin.

    Returns None when the raster size does not match the bbox (offset unknown),
    rather than guessing a placement.
    """
    local = decode_mask_rle(mask_rle)
    left, top = int(round(bbox[0])), int(round(bbox[1]))
    if local.shape != (int(round(bbox[3])) - top, int(round(bbox[2])) - left):
        return None
    full = np.zeros(frame_shape[:2], dtype=bool)
    fh, fw = full.shape
    y0, x0 = max(0, top), max(0, left)
    y1, x1 = min(fh, top + local.shape[0]), min(fw, left + local.shape[1])
    if y1 > y0 and x1 > x0:
        full[y0:y1, x0:x1] = local[y0 - top : y1 - top, x0 - left : x1 - left]
    return full


def _paint_rle(
    rgb: np.ndarray,
    mask_rle: dict[str, Any],
    color: tuple[int, int, int],
    bbox: tuple[float, float, float, float] | None = None,
) -> bool:
    """Tint mask pixels and outline the mask contour. Returns whether it painted."""
    if not bbox:
        return False
    try:
        mask = mask_in_frame(mask_rle, bbox, rgb.shape[:2])
    except Exception:  # noqa: BLE001
        return False
    if mask is None or not mask.any():
        return False
    alpha = 0.45
    tint = np.array(color, dtype=np.float32)
    rgb[mask] = ((1 - alpha) * rgb[mask] + alpha * tint).astype(np.uint8)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(rgb, contours, -1, color, 1, cv2.LINE_AA)
    return True


def observations_for_display(result: TrackingResult, limit: int = 80) -> list[dict[str, Any]]:
    rows = []
    for obs in result.observations[:limit]:
        rows.append(
            {
                "t_s": obs.timestamp_s,
                "frame": obs.frame_index,
                "concept": obs.concept,
                "object_id": obs.object_id,
                "bbox": obs.bbox,
                "centroid": obs.centroid,
                "status": obs.track_status,
                "confidence": obs.confidence,
                "returned": obs.observation_returned,
            }
        )
    return rows


def timeline_series(result: TrackingResult) -> list[dict[str, Any]]:
    """Per-concept visibility over time for Streamlit charts."""
    rows: list[dict[str, Any]] = []
    for obs in result.observations:
        if obs.centroid is None:
            continue
        rows.append(
            {
                "Time (s)": obs.timestamp_s,
                "concept": obs.concept,
                "centroid_x": obs.centroid[0],
                "centroid_y": obs.centroid[1],
                "visible": 1 if obs.track_status == "visible" else 0,
            }
        )
    return rows
