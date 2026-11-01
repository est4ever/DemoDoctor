"""Meta SAM 3.1 API helpers adapted from the official Model API cookbook.

Source pattern: meta-models/meta-model-cookbook 07_sam/01_api_basics/python/sam_api.py
Uses AsyncOpenAI + meta_sam_parser. Does not invent masks.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import aclosing
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from meta_sam_parser import (
    ImageSegmentationResult,
    ResponsesEventLike,
    VideoSegmentationResult,
    VideoSegmentationSnapshot,
    image_segmentation_format,
    parse_responses_stream,
    video_segmentation_format,
)
from openai import AsyncOpenAI

BASE_URL = "https://api.meta.ai/v1"
MODEL = "sam-3.1"


def client() -> AsyncOpenAI:
    load_dotenv()
    key = (os.environ.get("MODEL_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "Set MODEL_API_KEY before calling the Segment Anything Model API."
        )
    return AsyncOpenAI(base_url=BASE_URL, api_key=key, max_retries=0, timeout=120.0)


def media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed is None:
        raise ValueError(f"Could not infer a media type for {path}.")
    return guessed


def image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type(path)};base64,{encoded}"


def image_bytes_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def response_input(prompt: str, media: dict[str, str]) -> list[dict[str, Any]]:
    phrase = prompt.strip()
    if not phrase:
        raise ValueError("The concept must be a short noun phrase.")
    return [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": phrase}, media],
        }
    ]


async def stream_events(
    stream: AsyncIterable[Any], usage_out: dict[str, Any] | None = None
) -> AsyncIterator[ResponsesEventLike]:
    """Convert SDK events for meta_sam_parser; synthesize output_text.done when needed.

    If usage_out is given, it receives the final response's usage block and
    terminal event type when the API reports them (nothing is estimated).
    """
    completed_lanes: set[tuple[object, object, object]] = set()
    async for event in stream:
        data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        if usage_out is not None and isinstance(data.get("response"), dict):
            usage = data["response"].get("usage")
            if usage:
                usage_out["usage"] = usage
            if data.get("type") in ("response.completed", "response.incomplete", "response.failed"):
                usage_out["terminal_event"] = data.get("type")
        lane = (
            data.get("item_id"),
            data.get("output_index"),
            data.get("content_index"),
        )
        if data.get("type") == "response.output_text.done":
            if lane not in completed_lanes:
                completed_lanes.add(lane)
                yield data
            continue
        yield data
        part = data.get("part")
        if (
            data.get("type") == "response.content_part.done"
            and lane not in completed_lanes
            and isinstance(part, dict)
            and part.get("type") == "output_text"
            and isinstance(part.get("text"), str)
        ):
            completed_lanes.add(lane)
            yield {
                "type": "response.output_text.done",
                "item_id": data.get("item_id"),
                "output_index": data.get("output_index"),
                "content_index": data.get("content_index"),
                "text": part["text"],
            }


async def segment_image_path(path: Path, concept: str) -> ImageSegmentationResult:
    async with client() as api:
        stream = await api.responses.create(
            model=MODEL,
            stream=True,
            input=response_input(
                concept, {"type": "input_image", "image_url": image_data_url(path)}
            ),
            metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
        )
        async with stream, aclosing(stream_events(stream)) as events:
            return await parse_responses_stream(
                events, image_segmentation_format()
            ).final_result()


async def segment_image_bytes(
    image_bytes: bytes,
    concept: str,
    *,
    mime: str = "image/jpeg",
    usage_out: dict[str, Any] | None = None,
) -> ImageSegmentationResult:
    async with client() as api:
        stream = await api.responses.create(
            model=MODEL,
            stream=True,
            input=response_input(
                concept,
                {
                    "type": "input_image",
                    "image_url": image_bytes_data_url(image_bytes, mime=mime),
                },
            ),
            metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
        )
        async with stream, aclosing(stream_events(stream, usage_out)) as events:
            return await parse_responses_stream(
                events, image_segmentation_format()
            ).final_result()


async def upload_video(path: Path) -> str:
    async with client() as api:
        uploaded = await api.files.create(
            file=(path.name, path.read_bytes(), media_type(path)),
            purpose="user_data",
        )
        file_id = uploaded.id
        if not isinstance(file_id, str) or not file_id.startswith("file-"):
            raise ValueError("The Files API returned an invalid file ID.")
        return file_id


async def segment_video(
    file_id: str,
    concept: str,
    *,
    on_snapshot: Any | None = None,
    usage_out: dict[str, Any] | None = None,
) -> VideoSegmentationResult:
    if not file_id.startswith("file-"):
        raise ValueError("Expected a Files API ID beginning with 'file-'.")
    async with client() as api:
        stream = await api.responses.create(
            model=MODEL,
            stream=True,
            input=response_input(concept, {"type": "input_video", "file_id": file_id}),
            metadata={"mask_encoding": "one_bit", "include_confidence": "true"},
        )
        async with stream, aclosing(stream_events(stream, usage_out)) as events:
            parsed = parse_responses_stream(events, video_segmentation_format())
            async with parsed:
                async for snapshot in parsed:
                    if on_snapshot is not None:
                        on_snapshot(snapshot)
                    elif isinstance(snapshot, VideoSegmentationSnapshot) and (
                        snapshot.revision == 1 or snapshot.revision % 30 == 0
                    ):
                        print(
                            f"  revision={snapshot.revision} records={len(snapshot.records)}",
                            flush=True,
                        )
                return await parsed.final_result()
