"""Video frame extraction and basic visual-change signals."""

from __future__ import annotations

import io
from dataclasses import dataclass

import av
import cv2
import numpy as np


@dataclass(frozen=True)
class SampledFrame:
    """One RGB frame sampled from a demonstration video."""

    timestamp_s: float
    rgb: np.ndarray  # HxWx3 uint8, RGB


@dataclass(frozen=True)
class VisionResult:
    """Frames and optional pixel-change timeline for UI / AI."""

    frames: list[SampledFrame]
    change_chart: list[dict[str, float]]
    fps: float


def inspect_video(
    video_bytes: bytes,
    *,
    sample_interval_s: float = 1.0,
    max_frames: int = 120,
    max_width: int = 560,
) -> VisionResult:
    """Sample approximately one frame per second; compute a basic frame-change signal.

    The change signal is NOT a robot motion metric or an error detector.
    """
    images: list[SampledFrame] = []
    chart: list[dict[str, float]] = []
    previous_gray = None
    next_second = 0.0
    decoded = 0
    fps = 30.0

    with av.open(io.BytesIO(video_bytes)) as container:
        stream = container.streams.video[0]
        if stream.average_rate:
            fps = float(stream.average_rate)
        for frame in container.decode(video=0):
            decoded += 1
            seconds = float(frame.time) if frame.time is not None else (decoded - 1) / fps
            if seconds + 0.0001 < next_second:
                continue

            rgb = frame.to_ndarray(format="rgb24")
            height, width = rgb.shape[:2]
            scaled_width = min(width, max_width)
            scaled_height = max(1, int(round(height * scaled_width / width)))
            rgb = cv2.resize(rgb, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

            if previous_gray is not None:
                difference = cv2.absdiff(gray, previous_gray)
                chart.append(
                    {
                        "Time (s)": round(seconds, 2),
                        "Visual change": round(float(difference.mean()), 2),
                    }
                )

            images.append(SampledFrame(timestamp_s=round(seconds, 2), rgb=rgb))
            previous_gray = gray
            next_second = seconds + sample_interval_s

            if len(images) >= max_frames:
                break

    if not images:
        raise ValueError("This video has no readable frames. Try a different MP4.")

    return VisionResult(frames=images, change_chart=chart, fps=fps)


def select_representative_frames(
    frames: list[SampledFrame],
    count: int,
) -> list[SampledFrame]:
    """Pick evenly spaced frames (early / middle / late) for multimodal analysis."""
    if not frames:
        return []
    count = max(1, min(count, len(frames)))
    if count == 1:
        return [frames[0]]
    indices = np.linspace(0, len(frames) - 1, count, dtype=int)
    # Preserve order and drop duplicate indices from short clips.
    unique: list[int] = []
    for index in indices.tolist():
        if not unique or index != unique[-1]:
            unique.append(index)
    return [frames[i] for i in unique]


def gallery_frames(frames: list[SampledFrame], count: int = 12) -> list[SampledFrame]:
    """Subset of sampled frames for the Streamlit timeline gallery."""
    return select_representative_frames(frames, min(count, len(frames)))


def encode_frame_jpeg_base64(rgb: np.ndarray, quality: int = 80) -> str:
    """Encode an RGB frame as a JPEG data URL for multimodal APIs."""
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buffer = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("Failed to encode frame as JPEG.")
    import base64

    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
