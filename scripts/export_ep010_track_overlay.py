"""Export lean ep010 track overlay JSON from frozen SAM demo cache (no re-inference).

Writes web/public/data/ep010/tracks.json for client-side labels/trails.
Does not modify SAM/Muse pipelines or evaluation reports.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/demo_cache/ep010/sam_window/green_plate.json"
OUT = ROOT / "web/public/data/ep010/tracks.json"

# Match painted overlay legend colors (cyan/magenta/gold — not object color)
LEGEND_RGB = {
    "green plate:0": [255, 0, 200],
    "green plate:1": [255, 210, 0],
    "green plate:2": [80, 120, 255],
}


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    obs = raw["observations"]
    by_frame: dict[int, list[dict]] = defaultdict(list)
    by_track: dict[str, list[dict]] = defaultdict(list)

    for o in obs:
        if not o.get("observation_returned", True):
            continue
        cent = o.get("centroid")
        bbox = o.get("bbox")
        if not cent or not bbox or len(cent) < 2 or len(bbox) < 4:
            continue
        oid = str(o["object_id"])
        frame = int(o["frame_index"])
        t = float(o["timestamp_s"])
        rec = {
            "object_id": oid,
            "frame_index": frame,
            "t": round(t, 4),
            "centroid": [round(float(cent[0]), 1), round(float(cent[1]), 1)],
            "bbox": [round(float(v), 1) for v in bbox[:4]],
            "confidence": round(float(o.get("confidence") or 0.0), 4),
            "track_status": o.get("track_status") or "visible",
        }
        by_frame[frame].append(
            {k: rec[k] for k in ("object_id", "centroid", "bbox", "confidence", "track_status")}
        )
        by_track[oid].append(
            {
                "frame_index": frame,
                "t": rec["t"],
                "centroid": rec["centroid"],
                "bbox": rec["bbox"],
            }
        )

    for oid in by_track:
        by_track[oid].sort(key=lambda r: r["frame_index"])

    frames_sorted = sorted(by_frame.keys())
    payload = {
        "episode_key": "ep010",
        "source": str(SRC.relative_to(ROOT)).replace("\\", "/"),
        "provenance": "observed",
        "note": (
            "Centroids/bboxes from frozen SAM demo-cache observations only. "
            "No interpolation across missing frames. Outside the window there are "
            "no track points — do not invent detections."
        ),
        "image_size": [640, 480],
        "fps": 30.0,
        "t_start": float(obs[0]["timestamp_s"]) if obs else None,
        "t_end": float(obs[-1]["timestamp_s"]) if obs else None,
        "frame_start": frames_sorted[0] if frames_sorted else None,
        "frame_end": frames_sorted[-1] if frames_sorted else None,
        "legend": [
            {"object_id": oid, "color_rgb": LEGEND_RGB.get(oid, [0, 220, 255]), "label": oid}
            for oid in sorted(by_track.keys())
        ],
        "tracks": {
            oid: {
                "object_id": oid,
                "color_rgb": LEGEND_RGB.get(oid, [0, 220, 255]),
                "n_observations": len(pts),
                "points": pts,
            }
            for oid, pts in sorted(by_track.items())
        },
        "frames": {str(f): by_frame[f] for f in frames_sorted},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} "
        f"tracks={len(by_track)} frames={len(frames_sorted)} obs={sum(len(v) for v in by_track.values())}"
    )


if __name__ == "__main__":
    main()
