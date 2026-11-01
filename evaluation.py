"""Labeled evaluation set and prediction comparison for DemoDoctor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from diagnosis import Diagnosis, Verdict, normalize_verdict

DATA_DIR = Path(__file__).parent / "data"
LABELS_PATH = DATA_DIR / "labels.json"
PREDICTIONS_DIR = DATA_DIR / "predictions"
DEMOS_DIR = Path(__file__).parent / "sample_videos"
EVAL_VIDEOS_DIR = Path(__file__).parent / "eval_videos"
VERDICTS: tuple[Verdict, ...] = ("success", "failure", "uncertain")


@dataclass
class LabeledExample:
    """Outcome label for one independent demonstration episode."""

    example_id: str
    video_path: str
    task_description: str
    label: Verdict
    notes: str = ""
    verified: bool = False
    needs_manual_review: bool = False
    suggested_label: str | None = None
    anomaly_present: bool | None = None
    source_dataset: str | None = None
    source_ref: str | None = None
    camera: str | None = None
    episode_group_id: str | None = None


@dataclass
class EvalStats:
    """Accuracy stats; only meaningful with enough verified labels."""

    n_labeled: int
    n_verified: int
    n_compared: int
    n_correct: int
    accuracy: float | None
    abstention_rate: float | None
    confusion: dict[str, dict[str, int]]
    by_frame_count: dict[str, dict[str, Any]]
    by_label: dict[str, dict[str, int]]
    message: str
    show_metrics: bool = False


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    DEMOS_DIR.mkdir(parents=True, exist_ok=True)
    if not LABELS_PATH.is_file():
        seed = {
            "description": (
                "Manually verified demonstration outcomes. "
                "Set verified=true only after you watch the video yourself. "
                "label must be success, failure, or uncertain. "
                "Do not invent labels."
            ),
            "examples": [
                {
                    "example_id": "sample_hf_episode_000000",
                    "video_path": "sample_videos/sample.mp4",
                    "task_description": "Pick up the block and place it inside the box",
                    "label": "uncertain",
                    "verified": False,
                    "notes": (
                        "Placeholder only. Watch sample.mp4, then set label + verified=true "
                        "in the app or by editing this file."
                    ),
                }
            ],
        }
        LABELS_PATH.write_text(json.dumps(seed, indent=2), encoding="utf-8")


def load_labels(path: Path | None = None) -> list[LabeledExample]:
    ensure_data_files()
    target = path or LABELS_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    examples = raw.get("examples", raw if isinstance(raw, list) else [])
    result: list[LabeledExample] = []
    for item in examples:
        if not isinstance(item, dict):
            continue
        notes = str(item.get("notes") or "")
        verified = bool(item.get("verified", False))
        # Legacy seed rows that never set verified stay unverified.
        if "placeholder" in notes.lower() and "verified" not in item:
            verified = False
        anomaly = item.get("anomaly_present", None)
        if anomaly is not None:
            anomaly = bool(anomaly)
        suggested = item.get("suggested_label")
        result.append(
            LabeledExample(
                example_id=str(item["example_id"]),
                video_path=str(item["video_path"]),
                task_description=str(item.get("task_description") or ""),
                label=normalize_verdict(str(item.get("label", "uncertain"))),
                notes=notes,
                verified=verified,
                needs_manual_review=bool(item.get("needs_manual_review", not verified)),
                suggested_label=str(suggested) if suggested is not None else None,
                anomaly_present=anomaly,
                source_dataset=str(item["source_dataset"]) if item.get("source_dataset") else None,
                source_ref=str(item["source_ref"]) if item.get("source_ref") else None,
                camera=str(item["camera"]) if item.get("camera") else None,
                episode_group_id=str(item.get("episode_group_id") or item["example_id"]),
            )
        )
    return result


def upsert_label_record(record: dict[str, Any], *, preserve_verified: bool = False) -> Path:
    """Merge a label record by example_id. Never invents a verified outcome."""
    ensure_data_files()
    raw = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    examples: list[dict[str, Any]] = list(raw.get("examples") or [])
    example_id = str(record["example_id"])
    payload = dict(record)
    payload["example_id"] = example_id
    if "label" in payload:
        payload["label"] = normalize_verdict(str(payload["label"]))
    payload.setdefault("episode_group_id", example_id)

    replaced = False
    for index, item in enumerate(examples):
        if str(item.get("example_id")) != example_id:
            continue
        if preserve_verified and item.get("verified"):
            # Keep human-verified ground truth; refresh metadata / paths only.
            merged = dict(item)
            for key, value in payload.items():
                if key in {"label", "verified", "notes"} and item.get("verified"):
                    continue
                merged[key] = value
            examples[index] = merged
        else:
            examples[index] = payload
        replaced = True
        break
    if not replaced:
        examples.append(payload)
    raw["examples"] = examples
    LABELS_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return LABELS_PATH


def upsert_label(
    *,
    example_id: str,
    video_path: str,
    task_description: str,
    label: Verdict,
    notes: str = "",
    verified: bool = True,
) -> Path:
    """Create or update a manually verified label. Does not invent outcomes."""
    existing = next((ex for ex in load_labels() if ex.example_id == example_id), None)
    record: dict[str, Any] = {
        "example_id": example_id,
        "video_path": video_path,
        "task_description": task_description,
        "label": normalize_verdict(label),
        "verified": bool(verified),
        "needs_manual_review": not bool(verified),
        "notes": notes,
        "episode_group_id": example_id,
    }
    if existing is not None:
        for key in (
            "suggested_label",
            "anomaly_present",
            "source_dataset",
            "source_ref",
            "camera",
            "episode_group_id",
        ):
            value = getattr(existing, key)
            if value is not None:
                record[key] = value
    return upsert_label_record(record, preserve_verified=False)

def save_prediction(
    diagnosis: Diagnosis,
    *,
    example_id: str,
    video_name: str,
    frame_count: int,
    frame_timestamps_s: list[float],
    reasoning_effort: str,
    source: str = "streamlit",
) -> Path:
    """Persist an AI prediction with experiment metadata for evaluation."""
    ensure_data_files()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in example_id)[:80]
    out = PREDICTIONS_DIR / f"{stamp}_{safe_id}_f{frame_count}.json"
    usage = diagnosis.usage or {}
    from ai_analysis import estimate_cost_usd

    cost = estimate_cost_usd(usage)
    payload = {
        "saved_at_utc": stamp,
        "example_id": example_id,
        "video_name": video_name,
        "video_id": example_id,
        "source": source,
        "model": diagnosis.model_name,
        "frame_count": frame_count,
        "frame_timestamps_s": frame_timestamps_s,
        "reasoning_effort": reasoning_effort,
        "verdict": diagnosis.verdict,
        "model_confidence": diagnosis.confidence,
        "evidence": [e.__dict__ for e in diagnosis.evidence],
        "token_usage": usage,
        "cost_estimate_usd": cost,
        "diagnosis": diagnosis.to_dict(),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def load_predictions(directory: Path | None = None) -> list[dict[str, Any]]:
    ensure_data_files()
    root = directory or PREDICTIONS_DIR
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            row["_path"] = str(path)
            rows.append(row)
        except (OSError, json.JSONDecodeError):
            continue
    return rows


def empty_confusion() -> dict[str, dict[str, int]]:
    return {gold: {pred: 0 for pred in VERDICTS} for gold in VERDICTS}


def _prediction_verdict(row: dict[str, Any]) -> Verdict:
    if row.get("verdict"):
        return normalize_verdict(str(row["verdict"]))
    pred_raw = (row.get("diagnosis") or {}).get("verdict")
    return normalize_verdict(str(pred_raw) if pred_raw is not None else "uncertain")


def _prediction_frame_count(row: dict[str, Any]) -> int | None:
    if row.get("frame_count") is not None:
        try:
            return int(row["frame_count"])
        except (TypeError, ValueError):
            return None
    return None


def latest_predictions_by_key(
    predictions: list[dict[str, Any]],
    *,
    key_includes_frame_count: bool = False,
) -> dict[str, dict[str, Any]]:
    """Keep the most recent prediction per example (optionally per frame_count)."""
    latest: dict[str, dict[str, Any]] = {}
    for row in predictions:
        eid = str(row.get("example_id") or row.get("video_id") or "")
        if not eid:
            continue
        if key_includes_frame_count:
            fc = _prediction_frame_count(row)
            key = f"{eid}::f{fc}" if fc is not None else eid
        else:
            key = eid
        latest[key] = row
    return latest


def compute_stats(
    labels: list[LabeledExample] | None = None,
    predictions: list[dict[str, Any]] | None = None,
    *,
    min_examples_for_accuracy: int = 3,
    prefer_frame_count: int | None = None,
) -> EvalStats:
    """Compare predictions against manually verified labels only.

    Model-reported confidence is never used as accuracy.
    Metrics stay hidden until enough verified labels have matching predictions.
    """
    labels = labels if labels is not None else load_labels()
    predictions = predictions if predictions is not None else load_predictions()
    verified = [ex for ex in labels if ex.verified]
    label_map = {ex.example_id: ex for ex in verified}

    # Prefer latest prediction per example; optionally filter to one frame_count.
    filtered = predictions
    if prefer_frame_count is not None:
        filtered = [p for p in predictions if _prediction_frame_count(p) == prefer_frame_count]
    latest = latest_predictions_by_key(filtered, key_includes_frame_count=False)

    confusion = empty_confusion()
    by_label: dict[str, dict[str, int]] = {
        v: {"correct": 0, "total": 0} for v in VERDICTS
    }
    n_compared = 0
    n_correct = 0
    n_abstain = 0

    for eid, row in latest.items():
        if eid not in label_map:
            continue
        gold = label_map[eid].label
        pred = _prediction_verdict(row)
        confusion[gold][pred] += 1
        by_label[gold]["total"] += 1
        n_compared += 1
        if pred == "uncertain":
            n_abstain += 1
        if pred == gold:
            by_label[gold]["correct"] += 1
            n_correct += 1

    by_frame_count = compare_frame_counts(verified_labels=verified, predictions=predictions)

    n_verified = len(verified)
    show = n_compared >= min_examples_for_accuracy and n_verified >= min_examples_for_accuracy

    if not show:
        return EvalStats(
            n_labeled=len(labels),
            n_verified=n_verified,
            n_compared=n_compared,
            n_correct=n_correct,
            accuracy=None,
            abstention_rate=None,
            confusion=confusion,
            by_frame_count=by_frame_count,
            by_label=by_label,
            show_metrics=False,
            message=(
                f"Empirical metrics hidden until at least {min_examples_for_accuracy} "
                "manually verified labels have matching predictions. "
                f"Currently: {n_verified} verified labels, {n_compared} compared. "
                "Model-reported confidence is not accuracy."
            ),
        )

    accuracy = n_correct / n_compared if n_compared else None
    abstention_rate = n_abstain / n_compared if n_compared else None
    return EvalStats(
        n_labeled=len(labels),
        n_verified=n_verified,
        n_compared=n_compared,
        n_correct=n_correct,
        accuracy=accuracy,
        abstention_rate=abstention_rate,
        confusion=confusion,
        by_frame_count=by_frame_count,
        by_label=by_label,
        show_metrics=True,
        message=(
            f"Empirical accuracy on {n_compared} verified comparisons: "
            f"{n_correct}/{n_compared} correct. "
            "This is measured against your labels — not the model's self-reported confidence."
        ),
    )


def compare_frame_counts(
    *,
    verified_labels: list[LabeledExample],
    predictions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Accuracy broken down by frame_count for verified examples only."""
    label_map = {ex.example_id: ex for ex in verified_labels}
    # latest per (example_id, frame_count)
    latest = latest_predictions_by_key(predictions, key_includes_frame_count=True)
    buckets: dict[int, dict[str, int]] = {}
    for key, row in latest.items():
        eid = str(row.get("example_id") or "")
        if eid not in label_map:
            continue
        fc = _prediction_frame_count(row)
        if fc is None:
            continue
        gold = label_map[eid].label
        pred = _prediction_verdict(row)
        bucket = buckets.setdefault(fc, {"n": 0, "correct": 0, "abstain": 0})
        bucket["n"] += 1
        if pred == gold:
            bucket["correct"] += 1
        if pred == "uncertain":
            bucket["abstain"] += 1

    result: dict[str, dict[str, Any]] = {}
    for fc, counts in sorted(buckets.items()):
        n = counts["n"]
        result[str(fc)] = {
            "n": n,
            "correct": counts["correct"],
            "abstain": counts["abstain"],
            "accuracy": (counts["correct"] / n) if n else None,
            "abstention_rate": (counts["abstain"] / n) if n else None,
        }
    return result


def list_demo_videos(directory: Path | None = None) -> list[Path]:
    """Prerecorded demos available for batch evaluation (local files only)."""
    if directory is not None:
        roots = [directory]
    else:
        roots = [DEMOS_DIR, EVAL_VIDEOS_DIR]
    videos: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in ("*.mp4", "*.mov", "*.mkv"):
            videos.extend(sorted(root.rglob(pattern)))
    # De-duplicate by resolved path while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in videos:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def example_id_for_video(video_name: str, source: Literal["sample", "upload", "batch"]) -> str:
    stem = Path(video_name).stem
    if source == "sample" or stem == "sample":
        return "sample_hf_episode_000000"
    # Imported BotFails files are named after their stable example_id.
    if stem.startswith("botfails_"):
        return stem
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:60]
    if source == "batch":
        return f"batch_{safe}"
    return f"upload_{safe}"


def relative_video_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).parent.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def build_comparison_rows(
    *,
    frame_count: int | None = None,
) -> list[dict[str, Any]]:
    """One row per independent example_id (not per frame-count run).

    Frame-count variants of the same episode share example_id; only the latest
    prediction (optionally filtered to one frame_count) is shown for correctness.
    """
    labels = load_labels()
    predictions = load_predictions()
    if frame_count is not None:
        predictions = [p for p in predictions if _prediction_frame_count(p) == frame_count]
    latest = latest_predictions_by_key(predictions, key_includes_frame_count=False)

    rows: list[dict[str, Any]] = []
    for ex in labels:
        pred = latest.get(ex.example_id)
        pred_verdict = _prediction_verdict(pred) if pred else None
        pred_frames = _prediction_frame_count(pred) if pred else None
        correct: bool | None
        if not ex.verified or pred_verdict is None:
            correct = None
        else:
            correct = pred_verdict == ex.label
        rows.append(
            {
                "example_id": ex.example_id,
                "verified": ex.verified,
                "needs_manual_review": ex.needs_manual_review,
                "suggested_label": ex.suggested_label,
                "verified_label": ex.label if ex.verified else None,
                "draft_label": None if ex.verified else ex.label,
                "anomaly_present": ex.anomaly_present,
                "muse_verdict": pred_verdict,
                "frame_count": pred_frames,
                "model_confidence": (pred or {}).get("model_confidence"),
                "correct": correct,
                "task_description": ex.task_description,
                "video_path": ex.video_path,
                "source_dataset": ex.source_dataset,
            }
        )
    return rows
