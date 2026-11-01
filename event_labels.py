"""Manually verified failure-event annotations (separate from task labels).

data/event_labels.json holds what a person recorded after watching a video:
the first visible mishandling (frame + object), whether the robot recovered,
and the final task outcome. Nothing here is generated. Dataset-provided
annotations (e.g. BotFails per-frame anomaly flags) are read by a separate
function and never written into this file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENT_LABELS = Path(__file__).parent / "data" / "event_labels.json"
RECOVERED = ("yes", "no", "partial", "uncertain")
OUTCOMES = ("success", "failure", "uncertain")
_HEADER = {
    "description": (
        "Manually verified failure-event annotations. Fill in only after watching the video. "
        "first_mishandling.frame is the first frame where mishandling or a drop is visible. "
        "Dataset anomaly flags are NOT stored here."
    ),
    "episodes": [],
}


def load_event_labels(path: Path = EVENT_LABELS) -> dict[str, Any]:
    if not path.is_file():
        return json.loads(json.dumps(_HEADER))
    return json.loads(path.read_text(encoding="utf-8"))


def validate_event_label(record: dict[str, Any], *, n_frames: int | None = None, fps: float | None = None) -> list[str]:
    """Problems with a record (empty list = valid). Unset fields are allowed; wrong ones are not."""
    problems = []
    if not record.get("example_id"):
        problems.append("example_id is required")
    fm = record.get("first_mishandling")
    if fm is not None:
        frame = fm.get("frame")
        if not isinstance(frame, int) or frame < 0 or (n_frames is not None and frame >= n_frames):
            problems.append(f"first_mishandling.frame {frame!r} is not a valid frame index")
        if fps and isinstance(frame, int) and abs(fm.get("t_s", -1) - round(frame / fps, 3)) > 1e-6:
            problems.append("first_mishandling.t_s does not match frame / fps")
        if not (fm.get("object") or "").strip():
            problems.append("first_mishandling.object is required when a frame is given")
    if record.get("recovered") not in (None, *RECOVERED):
        problems.append(f"recovered must be one of {RECOVERED} or unset")
    if record.get("final_outcome") not in (None, *OUTCOMES):
        problems.append(f"final_outcome must be one of {OUTCOMES} or unset")
    if record.get("verified") and record.get("final_outcome") is None:
        problems.append("a verified record needs a final_outcome")
    return problems


def upsert_event_label(record: dict[str, Any], path: Path = EVENT_LABELS, **validate_kw: Any) -> Path:
    problems = validate_event_label(record, **validate_kw)
    if problems:
        raise ValueError("; ".join(problems))
    data = load_event_labels(path)
    record = dict(record, updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    episodes = [e for e in data["episodes"] if e.get("example_id") != record["example_id"]]
    episodes.append(record)
    data["episodes"] = sorted(episodes, key=lambda e: e["example_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def get_event_label(example_id: str, path: Path = EVENT_LABELS) -> dict[str, Any] | None:
    return next((e for e in load_event_labels(path)["episodes"] if e.get("example_id") == example_id), None)


def dataset_anomaly_onset(csv_path: Path) -> dict[str, Any] | None:
    """First flagged frame in a BotFails-style per-frame anomaly CSV (header-less 0/1 values).

    This is the dataset's annotation of an anomaly, not a verified failure time.
    """
    if not csv_path.is_file():
        return None
    values = [line.strip() for line in csv_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    flags = [v == "1" for v in values]
    first = next((i for i, v in enumerate(flags) if v), None)
    return {"source": csv_path.as_posix(), "n_frames": len(flags), "first_flagged_frame": first,
            "flagged_frames": sum(flags), "kind": "dataset anomaly flag (not a verified failure time)"}
