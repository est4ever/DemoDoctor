"""Container interior estimation for 2D containment (fixed-camera demonstrations).

Why not the raw SAM container mask: it covers the *visible* container surface,
so anything resting inside (screwdriver, pad) is cut out as a hole, and it also
includes the walls/rim. "Fraction of object inside the raw mask" is therefore
~0 for an object lying in the container.

Approach:
1. Calibrate once, on a frame where the container is empty: measure the inner
   wall edges (brightness changes inside the SAM footprint), fit straight lines,
   and intersect them into an interior polygon. Stored with its measurements.
2. Per frame, check the container is where the calibration says: the SAM mask
   with enclosed holes filled (the footprint) must match the calibration-frame
   footprint (IoU) and contain the polygon. Otherwise the interior is
   "unreliable" for that frame and callers must return uncertain.
3. Containment = fraction of the object's own SAM mask inside the polygon.

All measurements are 2D image-plane; they say nothing about depth.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

CALIBRATION_DIR = Path(__file__).parent / "data" / "calibration"
SAMPLE_CALIBRATION = CALIBRATION_DIR / "so101_sample_white_box_interior.json"
MIN_FOOTPRINT_IOU = 0.95
MIN_POLYGON_IN_FOOTPRINT = 0.99


@dataclass
class InteriorCalibration:
    concept: str
    calibration_frame: int
    video_sha256: str
    polygon: list[list[float]]  # [[x, y], ...] clockwise from top-left, full-frame pixels
    method: str
    measurements: dict[str, Any] = field(default_factory=dict)
    footprint_area: int = 0
    notes: list[str] = field(default_factory=list)

    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InteriorCalibration":
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Mask plus every background region not connected to the image border."""
    # Seed outside a padded image, so occupied corners cannot hide border-connected
    # background. Only components unreachable from the entire border are holes.
    flood = np.pad((~mask).astype(np.uint8), 1, constant_values=1)
    h, w = flood.shape
    seed_mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, seed_mask, (0, 0), 2)
    return mask | (flood[1:-1, 1:-1] == 1)


def polygon_mask(polygon: Sequence[Sequence[float]], shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(out, [np.round(np.asarray(polygon)).astype(np.int32)], 1)
    return out.astype(bool)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = (a | b).sum()
    return float((a & b).sum() / union) if union else 0.0


# --- calibration -----------------------------------------------------------

def _fit_x_of_y(points: list[tuple[int, int]], *, max_residual: float = 3.0) -> tuple[float, float, list]:
    """Least-squares x = a*y + b, refit after dropping points > max_residual px off.

    Returns (a, b, rejected points)."""
    pts = list(points)
    rejected: list = []
    for _ in range(3):
        ys = np.array([p[1] for p in pts], float)
        xs = np.array([p[0] for p in pts], float)
        a, b = np.polyfit(ys, xs, 1)
        res = np.abs(xs - (a * ys + b))
        if res.max() <= max_residual or len(pts) <= 4:
            break
        worst = int(np.argmax(res))
        rejected.append(pts.pop(worst))
    return float(a), float(b), rejected


def _robust_median(values: list[int], *, max_dev: float = 3.0) -> tuple[float, list]:
    med = float(np.median(values))
    kept = [v for v in values if abs(v - med) <= max_dev]
    return float(np.median(kept)), [v for v in values if abs(v - med) > max_dev]


def calibrate_interior(
    rgb_empty: np.ndarray,
    container_footprint: np.ndarray,
    *,
    concept: str,
    calibration_frame: int,
    video_sha256: str,
    rows: Sequence[int] = tuple(range(300, 571, 30)),
    columns: Sequence[int] = (240, 280, 320, 360),
    floor_drop: float = 10.0,
) -> InteriorCalibration:
    """Measure inner wall edges on an empty-container frame and build the interior polygon.

    Left wall:   strongest brightness gradient between the footprint's left edge (+6px)
                 and the footprint's middle (the wall/floor boundary).
    Right wall:  scanning outward from the middle, the first pixel more than `floor_drop`
                 gray levels darker than the floor median (the inner crease).
    Top/bottom:  strongest gradient within 6-40px inside the footprint's top/bottom edge.
    Rows/columns default to the tray's unobstructed middle band (the pad near the bottom
    edge interferes with the left-wall measurement there).
    """
    gray = cv2.GaussianBlur(rgb_empty.astype(np.float32).mean(axis=2), (5, 5), 0)
    left_pts, right_pts, top_pts, bottom_pts = [], [], [], []
    for y in rows:
        xs = np.nonzero(container_footprint[y])[0]
        if len(xs) < 40:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        mid = (x0 + x1) // 2
        d = np.diff(gray[y, x0:x1 + 1])
        window = np.arange(x0 + 6, mid) - x0
        left_pts.append((int(x0 + window[np.argmax(np.abs(d[window]))]), y))
        floor = float(np.median(gray[y, mid - 20:mid + 20]))
        right = next((x for x in range(mid, x1 - 4) if gray[y, x] < floor - floor_drop), None)
        if right is not None:
            right_pts.append((int(right), y))
    for x in columns:
        ys = np.nonzero(container_footprint[:, x])[0]
        if len(ys) < 80:
            continue
        y0, y1 = int(ys.min()), int(ys.max())
        d = np.diff(gray[y0:y1 + 1, x])
        top_w = np.arange(6, 40)
        bot_w = np.arange((y1 - y0) - 40, (y1 - y0) - 4)
        top_pts.append((x, int(y0 + top_w[np.argmax(np.abs(d[top_w]))])))
        bottom_pts.append((x, int(y0 + bot_w[np.argmax(np.abs(d[bot_w]))])))
    if len(left_pts) < 4 or len(right_pts) < 4 or not top_pts or not bottom_pts:
        raise ValueError("Not enough inner-edge measurements to calibrate the interior.")

    la, lb, left_rej = _fit_x_of_y(left_pts)
    ra, rb, right_rej = _fit_x_of_y(right_pts)
    top_y, top_rej = _robust_median([p[1] for p in top_pts])
    bottom_y, bottom_rej = _robust_median([p[1] for p in bottom_pts])
    left_used = [p for p in left_pts if p not in left_rej]
    right_used = [p for p in right_pts if p not in right_rej]
    if len(left_used) < 4 or len(right_used) < 4:
        raise ValueError("Too few consistent wall measurements after outlier rejection.")
    polygon = [[la * top_y + lb, top_y], [ra * top_y + rb, top_y],
               [ra * bottom_y + rb, bottom_y], [la * bottom_y + lb, bottom_y]]
    residual = lambda pts, a, b: float(np.max([abs(x - (a * y + b)) for x, y in pts]))  # noqa: E731
    return InteriorCalibration(
        concept=concept,
        calibration_frame=calibration_frame,
        video_sha256=video_sha256,
        polygon=[[round(x, 2), round(y, 2)] for x, y in polygon],
        method="inner wall edges measured on an empty-container frame; straight-line fits intersected",
        measurements={
            "left_wall_points": left_pts, "right_wall_points": right_pts,
            "top_points": top_pts, "bottom_points": bottom_pts,
            "left_fit_x_of_y": [la, lb], "right_fit_x_of_y": [ra, rb],
            "max_fit_residual_px": {"left": residual(left_used, la, lb), "right": residual(right_used, ra, rb)},
            "rejected_outliers": {"left": left_rej, "right": right_rej, "top_y": top_rej, "bottom_y": bottom_rej},
            "top_y": top_y, "bottom_y": bottom_y,
        },
        footprint_area=int(container_footprint.sum()),
        notes=["Fixed camera and container position assumed; validated per frame against the SAM footprint."],
    )


# --- per-frame assessment ------------------------------------------------------

def assess_containment(
    object_mask: np.ndarray,
    container_mask: np.ndarray | None,
    calibration: InteriorCalibration | None,
    calibration_footprint: np.ndarray | None,
) -> dict[str, Any]:
    """Interior containment of one object mask on one frame, with reliability checks."""
    out: dict[str, Any] = {"reliable": False, "interior_fraction": None, "footprint_fraction": None,
                           "raw_mask_fraction": None, "footprint_iou": None, "polygon_in_footprint": None,
                           "reason": None}
    area = int(object_mask.sum())
    if area == 0:
        out["reason"] = "empty object mask"
        return out
    if container_mask is None:
        out["reason"] = "container not detected on this frame"
        return out
    footprint = fill_holes(container_mask)
    out["raw_mask_fraction"] = round(float((object_mask & container_mask).sum() / area), 4)
    out["footprint_fraction"] = round(float((object_mask & footprint).sum() / area), 4)
    if calibration is None or calibration_footprint is None:
        out["reason"] = "no interior calibration"
        return out
    interior = polygon_mask(calibration.polygon, object_mask.shape)
    # Pixels hidden by the measured object itself say nothing about whether the
    # container moved, so both reliability checks ignore them. Occlusion by
    # anything else (e.g. the arm) still counts against reliability.
    visible = ~object_mask
    out["footprint_iou"] = round(iou(footprint & visible, calibration_footprint & visible), 4)
    out["polygon_in_footprint"] = round(
        float((interior & footprint & visible).sum() / max(1, (interior & visible).sum())), 4)
    out["interior_fraction"] = round(float((object_mask & interior).sum() / area), 4)
    if out["footprint_iou"] < MIN_FOOTPRINT_IOU:
        out["reason"] = (f"container footprint differs from calibration (IoU {out['footprint_iou']:.3f} < "
                         f"{MIN_FOOTPRINT_IOU}): moved, or its boundary is obscured")
    elif out["polygon_in_footprint"] < MIN_POLYGON_IN_FOOTPRINT:
        out["reason"] = f"interior polygon extends outside the container footprint ({out['polygon_in_footprint']:.3f})"
    else:
        out["reliable"] = True
    return out


def calibrate_sample(save: bool = True) -> InteriorCalibration:
    """Calibrate the SO-101 sample's white box on frame 0 (container empty)."""
    import tracking as T

    video = (Path(__file__).parent / "sample_videos" / "sample.mp4").read_bytes()
    result = T.assemble_from_chunk_cache(video, ["white box"])
    box0 = next(o for o in result.observations if o.concept == "white box" and o.frame_index == 0)
    rgb = T.extract_frame_rgb(video, 0)
    footprint = fill_holes(T.mask_in_frame(box0.mask_rle, box0.bbox, rgb.shape[:2]))
    cal = calibrate_interior(rgb, footprint, concept="white box", calibration_frame=0,
                             video_sha256=hashlib.sha256(video).hexdigest())
    cal.notes.append("Frame 0 chosen because the container is empty (screwdriver still on the mat).")
    if save:
        cal.save(SAMPLE_CALIBRATION)
    return cal


if __name__ == "__main__":
    c = calibrate_sample(save=True)
    print(json.dumps(asdict(c), indent=2))
