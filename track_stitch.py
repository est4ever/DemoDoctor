"""Chunk planning, cross-chunk identity stitching, and per-frame detection states.

Pure functions over tracking observations: no API calls, no video decoding, no file I/O.

Terminology (kept deliberately literal):
- "detected":     SAM returned a box/mask for this concept on this frame.
- "not_detected": a SAM request covering this frame *completed* and returned nothing
                  for it. This says nothing certain about physical visibility.
- "unknown":      no completed request covers this frame (failed, incomplete,
                  outcome never recorded, or never queried).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Literal, Protocol, Sequence

CallStatus = Literal["completed", "incomplete", "failed", "unverified", "not_run"]
FrameState = Literal["detected", "not_detected", "unknown"]


class _Obs(Protocol):
    concept: str
    object_id: str
    frame_index: int | None
    bbox: tuple[float, float, float, float] | None
    chunk_index: int | None
    local_object_id: str | None


@dataclass(frozen=True)
class ChunkSpec:
    """Global frame window sent to SAM as one request.

    [start_frame, end_frame) is what SAM sees; [start_frame, owned_end_frame) is the
    part this chunk is authoritative for. Frames past owned_end_frame overlap the
    next chunk and exist only to link identities.
    """

    index: int
    start_frame: int
    end_frame: int
    owned_end_frame: int

    def contains(self, frame: int) -> bool:
        return self.start_frame <= frame < self.end_frame

    def owns(self, frame: int) -> bool:
        return self.start_frame <= frame < self.owned_end_frame

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class ChunkCall:
    """Outcome of one SAM request for one concept on one chunk."""

    chunk_index: int
    concept: str
    status: CallStatus
    reason: str | None = None
    n_records: int | None = None
    n_observations: int = 0
    file_id: str | None = None
    prompt_mode: str = "concept"
    from_cache: bool = False
    usage: dict[str, Any] | None = None  # as reported by the API, never estimated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_chunks(
    n_frames: int,
    chunk_frames: int,
    *,
    overlap_frames: int = 1,
    min_last_chunk_frames: int = 15,
) -> list[ChunkSpec]:
    """Split [0, n_frames) into chunks of chunk_frames owned frames plus overlap.

    overlap_frames=1 reproduces the historical inclusive-end clips (121 frames per
    4 s chunk at 30 fps), so legacy cached chunks line up with new plans.
    """
    if n_frames <= 0:
        return []
    if chunk_frames <= 0:
        raise ValueError("chunk_frames must be positive")
    overlap_frames = max(0, overlap_frames)
    starts = list(range(0, n_frames, chunk_frames))
    if len(starts) > 1 and n_frames - starts[-1] < min_last_chunk_frames:
        starts.pop()  # fold a tiny tail into the previous chunk
    specs: list[ChunkSpec] = []
    for i, start in enumerate(starts):
        owned_end = starts[i + 1] if i + 1 < len(starts) else n_frames
        end = min(owned_end + overlap_frames, n_frames)
        specs.append(ChunkSpec(i, start, end, owned_end))
    return specs


def bbox_iou(
    a: Sequence[float] | None, b: Sequence[float] | None
) -> float:
    if a is None or b is None:
        return 0.0
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def stitch_tracks(
    observations: Iterable[_Obs],
    chunks: Sequence[ChunkSpec],
    *,
    iou_threshold: float = 0.5,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Assign global track ids across chunks and drop duplicate overlap frames.

    SAM object ids are local to one request. A local track in chunk k inherits a
    global id only if its boxes overlap (mean IoU >= iou_threshold) with that
    global track on frames shared with earlier chunks. Otherwise it gets a new
    global id. Tracks separated by a gap are never merged here: whether they are
    the same physical object is an inference for later layers.

    Returns (observations with object_id = "<concept>:<global id>", link log).
    """
    chunk_by_index = {c.index: c for c in chunks}
    by_track: dict[tuple[str, int, str], list[_Obs]] = defaultdict(list)
    passthrough: list[_Obs] = []
    for obs in observations:
        if obs.chunk_index is None or obs.frame_index is None:
            passthrough.append(obs)
            continue
        local = obs.local_object_id or obs.object_id.split(":")[-1]
        by_track[(obs.concept, obs.chunk_index, local)].append(obs)

    links: list[dict[str, Any]] = []
    gid_of: dict[tuple[str, int, str], int] = {}
    # concept -> gid -> {frame: bbox}
    global_boxes: dict[str, dict[int, dict[int, Any]]] = defaultdict(lambda: defaultdict(dict))
    next_gid: dict[str, int] = defaultdict(int)

    concepts = sorted({k[0] for k in by_track})
    for concept in concepts:
        for chunk in sorted(chunks, key=lambda c: c.index):
            locals_here = sorted(
                (k for k in by_track if k[0] == concept and k[1] == chunk.index),
                key=lambda k: k[2],
            )
            candidates: list[tuple[float, str, int, list[int]]] = []
            for key in locals_here:
                boxes = {o.frame_index: o.bbox for o in by_track[key]}
                for gid, gboxes in global_boxes[concept].items():
                    shared = sorted(f for f in boxes if f in gboxes)
                    if not shared:
                        continue
                    ious = [bbox_iou(boxes[f], gboxes[f]) for f in shared]
                    candidates.append((sum(ious) / len(ious), key[2], gid, shared))
            candidates.sort(key=lambda c: -c[0])
            used_local: set[str] = set()
            used_gid: set[int] = set()
            for iou, local, gid, shared in candidates:
                if local in used_local or gid in used_gid or iou < iou_threshold:
                    continue
                used_local.add(local)
                used_gid.add(gid)
                gid_of[(concept, chunk.index, local)] = gid
                links.append(
                    {
                        "concept": concept,
                        "chunk_index": chunk.index,
                        "local_object_id": local,
                        "global_id": gid,
                        "decision": "linked",
                        "mean_iou": round(iou, 4),
                        "shared_frames": shared,
                    }
                )
            for key in locals_here:
                if key in gid_of:
                    continue
                gid = next_gid[concept]
                next_gid[concept] += 1
                gid_of[key] = gid
                best = max(
                    (c for c in candidates if c[1] == key[2]),
                    key=lambda c: c[0],
                    default=None,
                )
                links.append(
                    {
                        "concept": concept,
                        "chunk_index": chunk.index,
                        "local_object_id": key[2],
                        "global_id": gid,
                        "decision": "new_track",
                        "mean_iou": round(best[0], 4) if best else None,
                        "shared_frames": best[3] if best else [],
                    }
                )
            for key in locals_here:
                gid = gid_of[key]
                for o in by_track[key]:
                    global_boxes[concept][gid].setdefault(o.frame_index, o.bbox)

    # One observation per (concept, global id, frame): prefer the owning chunk,
    # else the earliest chunk that saw it (a real detection is never discarded
    # just because it came from an overlap frame).
    chosen: dict[tuple[str, int, int], Any] = {}
    for key, items in by_track.items():
        concept, chunk_index, _ = key
        gid = gid_of[key]
        chunk = chunk_by_index.get(chunk_index)
        for o in items:
            slot = (concept, gid, o.frame_index)
            new = replace(o, object_id=f"{concept}:{gid}")
            prev = chosen.get(slot)
            if prev is None:
                chosen[slot] = new
                continue
            prev_chunk = chunk_by_index.get(prev.chunk_index)
            prev_owns = bool(prev_chunk and prev_chunk.owns(o.frame_index))
            new_owns = bool(chunk and chunk.owns(o.frame_index))
            if new_owns and not prev_owns:
                chosen[slot] = new
            elif new_owns == prev_owns and chunk_index < (prev.chunk_index or 0):
                chosen[slot] = new

    out = list(chosen.values()) + passthrough
    out.sort(key=lambda o: (o.frame_index if o.frame_index is not None else -1, o.concept, o.object_id))
    return out, links


def concept_frame_states(
    observations: Iterable[_Obs],
    chunks: Sequence[ChunkSpec],
    calls: Sequence[ChunkCall],
    concept: str,
    n_frames: int,
) -> list[FrameState]:
    """Per-frame state for one concept (see module docstring for meanings)."""
    states: list[FrameState] = ["unknown"] * max(0, n_frames)
    completed = {
        c.chunk_index for c in calls if c.concept == concept and c.status == "completed"
    }
    for chunk in chunks:
        if chunk.index in completed:
            for f in range(chunk.start_frame, min(chunk.end_frame, n_frames)):
                states[f] = "not_detected"
    for obs in observations:
        if obs.concept == concept and obs.frame_index is not None and 0 <= obs.frame_index < n_frames:
            states[obs.frame_index] = "detected"
    return states


def state_runs(states: Sequence[str]) -> list[dict[str, Any]]:
    """Collapse per-frame states into [start, end) runs."""
    runs: list[dict[str, Any]] = []
    for f, s in enumerate(states):
        if runs and runs[-1]["state"] == s:
            runs[-1]["end_frame"] = f + 1
        else:
            runs.append({"state": s, "start_frame": f, "end_frame": f + 1})
    return runs


# --- Legacy cache support -------------------------------------------------
# Caches written before chunk logs existed only kept free-text api_notes, so the
# request outcome was never recorded. Those calls are reported as "unverified".

_CHUNK_RE = re.compile(r"^chunk(\d+): t=([\d.]+)-([\d.]+)s file_id=(\S+)$")
_CHUNK_OK_RE = re.compile(r"^chunk(\d+)/(.+): ok observations=(\d+)$")
_CHUNK_FAIL_RE = re.compile(r"^chunk(\d+)/(.+): FAILED (.*)$")
_SINGLE_OUTCOME_RE = re.compile(r"^(.+): outcome=(\w+) records=(\d+)$")
_SINGLE_FAIL_RE = re.compile(r"^(.+): FAILED (.*)$")


def legacy_chunk_log(
    api_notes: Sequence[str],
    *,
    fps: float,
    n_frames: int,
    concepts: Sequence[str],
) -> tuple[list[ChunkSpec], list[ChunkCall]]:
    """Reconstruct chunk windows and call outcomes from legacy api_notes."""
    raw_chunks: list[tuple[int, int, int, str]] = []
    calls: list[ChunkCall] = []
    file_ids: dict[int, str] = {}
    for note in api_notes:
        note = note.strip()
        if m := _CHUNK_RE.match(note):
            idx = int(m.group(1))
            start = int(round(float(m.group(2)) * fps))
            last = min(int(round(float(m.group(3)) * fps)), n_frames - 1)
            raw_chunks.append((idx, start, last + 1, m.group(4)))
            file_ids[idx] = m.group(4)
        elif m := _CHUNK_OK_RE.match(note):
            idx = int(m.group(1))
            calls.append(
                ChunkCall(
                    chunk_index=idx,
                    concept=m.group(2),
                    status="unverified",
                    reason="legacy cache: request outcome was not recorded",
                    n_observations=int(m.group(3)),
                    file_id=file_ids.get(idx),
                )
            )
        elif m := _CHUNK_FAIL_RE.match(note):
            idx = int(m.group(1))
            calls.append(
                ChunkCall(idx, m.group(2), "failed", reason=m.group(3), file_id=file_ids.get(idx))
            )

    if raw_chunks:
        raw_chunks.sort()
        chunks = []
        for i, (idx, start, end, _) in enumerate(raw_chunks):
            owned_end = raw_chunks[i + 1][1] if i + 1 < len(raw_chunks) else end
            chunks.append(ChunkSpec(idx, start, end, min(owned_end, end)))
        return chunks, calls

    # Single-request (non-chunked) result.
    chunk = ChunkSpec(0, 0, n_frames, n_frames)
    seen: set[str] = set()
    for note in api_notes:
        note = note.strip()
        if m := _SINGLE_OUTCOME_RE.match(note):
            status: CallStatus = "completed" if m.group(2) == "completed" else "incomplete"
            calls.append(ChunkCall(0, m.group(1), status, n_records=int(m.group(3))))
            seen.add(m.group(1))
        elif (m := _SINGLE_FAIL_RE.match(note)) and m.group(1) in concepts:
            calls.append(ChunkCall(0, m.group(1), "failed", reason=m.group(2)))
            seen.add(m.group(1))
    for concept in concepts:
        if concept not in seen:
            calls.append(ChunkCall(0, concept, "unverified", reason="no outcome note"))
    return [chunk], calls


def assign_legacy_chunks(observations: Sequence[Any], chunks: Sequence[ChunkSpec]) -> list[Any]:
    """Recover which chunk produced each legacy observation.

    Legacy stitching appended chunk results in order and then did a stable sort,
    so for a frame covered by two chunks the first stored copy came from the
    earlier chunk.
    """
    ordered = sorted(chunks, key=lambda c: c.index)
    seen: dict[tuple[str, str, int], int] = defaultdict(int)
    out = []
    for obs in observations:
        if obs.frame_index is None:
            out.append(obs)
            continue
        local = obs.object_id.split(":")[-1]
        key = (obs.concept, local, obs.frame_index)
        covering = [c for c in ordered if c.contains(obs.frame_index)]
        k = seen[key]
        seen[key] += 1
        chunk_index = covering[min(k, len(covering) - 1)].index if covering else None
        out.append(replace(obs, chunk_index=chunk_index, local_object_id=local))
    return out
