"""Conservative final-object placement checks (2D image plane only).

Dish-rack path: when empty-container wall calibration is unavailable (cups already
in the rack), approximate an interior by eroding the SAM rack footprint. Inside
requires a reliable containment assessment; otherwise return unknown. Outside can
still be declared from footprint overlap alone (same rule as failures.classify_region).

No labels, anomaly flags, or episode-specific threshold tuning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

import cv2
import numpy as np

import container as C
import failures as F

Region = Literal["inside", "outside", "unknown"]

# Frozen defaults for dish-rack approximate interior (not tuned on held-out outcomes).
DEFAULT_ERODE_PX = 12
DEFAULT_INSIDE_FRAC = 0.85  # stricter than failures default 0.8
DEFAULT_OUTSIDE_FOOTPRINT_FRAC = 0.05
# Near-rack ambiguity: upright plates in wire slots often have tiny footprint overlap
# while sitting next to / in the rack. Do not call outside in that band — prefer unknown.
# Not tuned to force ep002 (or any episode) to "inside".
DEFAULT_NEAR_RACK_DILATE_PX = 20
DEFAULT_NEAR_RACK_FRAC = 0.5


@dataclass
class PlacementResult:
    region: Region
    method: str
    assessment: dict[str, Any]
    reliable: bool
    reason: str | None = None
    notes: list[str] = field(default_factory=list)
    # Which decision rule produced `region` (for audits; proximity never yields inside).
    geometry_rule: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def approximate_interior_from_footprint(
    footprint: np.ndarray,
    *,
    concept: str,
    calibration_frame: int,
    video_sha256: str,
    erode_px: int = DEFAULT_ERODE_PX,
) -> C.InteriorCalibration:
    """Build an InteriorCalibration by eroding the filled container footprint.

    Label-free fallback when an empty-container wall fit is impossible (e.g. dish
    rack already holding cups). Shrinks the footprint so rim/wall pixels are less
    likely to count as "inside".
    """
    fp = np.asarray(footprint, dtype=bool)
    if fp.ndim != 2 or not fp.any():
        raise ValueError("footprint must be a non-empty 2D boolean mask")
    erode_px = max(1, int(erode_px))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * erode_px + 1, 2 * erode_px + 1))
    eroded = cv2.erode(fp.astype(np.uint8), kernel, iterations=1).astype(bool)
    if not eroded.any():
        raise ValueError(f"erosion by {erode_px}px removed the entire footprint; reduce erode_px")

    contours, _ = cv2.findContours(
        eroded.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        raise ValueError("no contour on eroded footprint")
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 50:
        raise ValueError("eroded interior contour too small")
    # Polygon: simplify slightly for stable IoU checks
    eps = 0.01 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, eps, True)
    polygon = [[float(p[0][0]), float(p[0][1])] for p in approx]
    if len(polygon) < 3:
        polygon = [[float(p[0][0]), float(p[0][1])] for p in contour]

    return C.InteriorCalibration(
        concept=concept,
        calibration_frame=calibration_frame,
        video_sha256=video_sha256,
        polygon=[[round(x, 2), round(y, 2)] for x, y in polygon],
        method=(
            f"approximate interior = morphological erosion of SAM footprint "
            f"by {erode_px}px (no empty-container wall fit)"
        ),
        measurements={
            "erode_px": erode_px,
            "footprint_area": int(fp.sum()),
            "eroded_area": int(eroded.sum()),
            "contour_area": float(cv2.contourArea(contour)),
        },
        footprint_area=int(fp.sum()),
        notes=[
            "Conservative fallback for occupied dish racks; prefer empty-frame wall calibration when available.",
            "Fixed camera and container position assumed; validated per frame against the SAM footprint.",
        ],
    )


def near_container_fraction(
    object_mask: np.ndarray,
    container_mask: np.ndarray,
    *,
    dilate_px: int = DEFAULT_NEAR_RACK_DILATE_PX,
) -> float:
    """Fraction of object mask within a dilated filled container footprint."""
    obj = np.asarray(object_mask, dtype=bool)
    area = int(obj.sum())
    if area == 0:
        return 0.0
    fp = C.fill_holes(np.asarray(container_mask, dtype=bool))
    dilate_px = max(0, int(dilate_px))
    if dilate_px > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
        region = cv2.dilate(fp.astype(np.uint8), kernel, iterations=1).astype(bool)
    else:
        region = fp
    return float((obj & region).sum() / area)


def assess_object_placement(
    object_mask: np.ndarray,
    container_mask: np.ndarray | None,
    *,
    calibration: C.InteriorCalibration | None = None,
    calibration_footprint: np.ndarray | None = None,
    inside_frac: float = DEFAULT_INSIDE_FRAC,
    outside_footprint_frac: float = DEFAULT_OUTSIDE_FOOTPRINT_FRAC,
    near_rack_dilate_px: int = DEFAULT_NEAR_RACK_DILATE_PX,
    near_rack_frac: float = DEFAULT_NEAR_RACK_FRAC,
) -> PlacementResult:
    """Classify one object mask as inside / outside / unknown relative to the container.

    Development-set proximity params (20px / 50%) were motivated by the ep002
    upright-slot investigation; they are not independently validated on held-out data.
    Proximity alone never yields ``inside``.
    """
    assessment = C.assess_containment(
        object_mask, container_mask, calibration, calibration_footprint
    )
    region = F.classify_region(
        assessment,
        inside_frac=inside_frac,
        outside_footprint_frac=outside_footprint_frac,
    )
    geometry_rule = "footprint_outside" if region == "outside" else (
        "reliable_interior_inside" if region == "inside" else "insufficient_geometry_unknown"
    )

    # Extra conservatism: never call inside unless assessment is reliable
    if region == "inside" and not assessment.get("reliable"):
        region = "unknown"
        geometry_rule = "inside_blocked_unreliable"
        assessment = {**assessment, "reason": assessment.get("reason") or "inside blocked: unreliable"}

    # Ambiguous near-rack: low footprint overlap can mean "on the table far away"
    # OR "upright in a wire slot whose silhouette barely intersects the filled
    # footprint / eroded interior". Prefer unknown over a false outside.
    # Params: development-set (ep002 investigation); not held-out validated.
    near_frac = None
    if region == "outside" and container_mask is not None:
        near_frac = near_container_fraction(
            object_mask, container_mask, dilate_px=near_rack_dilate_px
        )
        assessment = {
            **assessment,
            "near_container_fraction": round(near_frac, 4),
            "near_rack_dilate_px": near_rack_dilate_px,
            "near_rack_frac_threshold": near_rack_frac,
        }
        if near_frac >= near_rack_frac:
            region = "unknown"
            geometry_rule = "near_rack_proximity_unknown"
            assessment = {
                **assessment,
                "reason": (
                    f"near container (dilated-footprint fraction {near_frac:.3f} >= {near_rack_frac}) "
                    f"but footprint overlap too low for outside and interior not established; "
                    f"upright-in-slot vs misplacement ambiguous"
                ),
            }
        else:
            geometry_rule = "footprint_outside_clearly_separated"

    method = "none"
    if calibration is not None:
        method = calibration.method
    elif container_mask is not None:
        method = "footprint_only (outside/unknown; no interior calibration)"

    reason = assessment.get("reason")
    if region == "unknown" and reason is None:
        reason = "insufficient support for inside or outside"
    notes = []
    if region == "unknown":
        notes.append("Retaining unknown — containment not sufficiently supported.")
    if region == "outside":
        notes.append("Outside uses footprint overlap only (no interior required).")
    if region == "inside":
        notes.append("Inside requires reliable interior assessment and high interior_fraction.")
    if geometry_rule == "near_rack_proximity_unknown":
        notes.append(
            "Outside suppressed: object is near the container footprint "
            "(cannot distinguish valid upright slot storage from a near-miss). "
            "Proximity alone never yields inside."
        )
    assessment = {**assessment, "geometry_rule": geometry_rule}

    return PlacementResult(
        region=region,  # type: ignore[arg-type]
        method=method,
        assessment=assessment,
        reliable=bool(assessment.get("reliable")),
        reason=reason,
        notes=notes,
        geometry_rule=geometry_rule,
    )


def assess_many(
    object_masks: Sequence[np.ndarray],
    container_mask: np.ndarray | None,
    *,
    calibration: C.InteriorCalibration | None = None,
    calibration_footprint: np.ndarray | None = None,
    inside_frac: float = DEFAULT_INSIDE_FRAC,
    outside_footprint_frac: float = DEFAULT_OUTSIDE_FOOTPRINT_FRAC,
    near_rack_dilate_px: int = DEFAULT_NEAR_RACK_DILATE_PX,
    near_rack_frac: float = DEFAULT_NEAR_RACK_FRAC,
) -> list[PlacementResult]:
    return [
        assess_object_placement(
            m,
            container_mask,
            calibration=calibration,
            calibration_footprint=calibration_footprint,
            inside_frac=inside_frac,
            outside_footprint_frac=outside_footprint_frac,
            near_rack_dilate_px=near_rack_dilate_px,
            near_rack_frac=near_rack_frac,
        )
        for m in object_masks
    ]
