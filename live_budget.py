"""Persistent spend ledger for live DemoDoctor API calls.

Caps: total project budget and per-run budget. Refuses reservations that would
exceed either. No automatic retries — callers must not re-bill on failure.
"""
from __future__ import annotations

import json
import math
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LEDGER_PATH = ROOT / "data" / "live_jobs" / "budget_ledger.json"

# Authorized by user (2026-10-29 session)
DEFAULT_TOTAL_BUDGET_USD = 10.0
DEFAULT_PER_RUN_BUDGET_USD = 1.0

# Published Standard SAM rates; unknown usage remains explicitly unknown.

_lock = threading.Lock()


@dataclass
class SpendEvent:
    event_id: str
    ts: float
    job_id: str
    provider: str  # meta_sam | fireworks_muse
    kind: str
    estimated_usd: float
    actual_usd: float | None
    from_cache: bool
    usage: dict[str, Any] = field(default_factory=dict)
    note: str = ""


def _empty_ledger() -> dict[str, Any]:
    return {
        "total_budget_usd": DEFAULT_TOTAL_BUDGET_USD,
        "per_run_budget_usd": DEFAULT_PER_RUN_BUDGET_USD,
        "spent_usd": 0.0,
        "reserved_usd": 0.0,
        "events": [],
        "reservations": {},
    }


def load_ledger() -> dict[str, Any]:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LEDGER_PATH.is_file():
        data = _empty_ledger()
        LEDGER_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def save_ledger(data: dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(LEDGER_PATH)


def status() -> dict[str, Any]:
    with _lock:
        d = load_ledger()
        spent = float(d.get("spent_usd") or 0)
        reserved = float(d.get("reserved_usd") or 0)
        total = float(d.get("total_budget_usd", DEFAULT_TOTAL_BUDGET_USD))
        return {
            "total_budget_usd": total,
            "per_run_budget_usd": float(
                d.get("per_run_budget_usd", DEFAULT_PER_RUN_BUDGET_USD)
            ),
            "spent_usd": round(spent, 6),
            "reserved_usd": round(reserved, 6),
            "remaining_usd": round(total - spent - reserved, 6),
            "n_events": len(d.get("events") or []),
            "ledger_path": str(LEDGER_PATH.relative_to(ROOT)).replace("\\", "/"),
        }


def estimate_sam_window_usd(n_frames: int, fps: float) -> float:
    return round(max(50, n_frames) * 0.20 / 1000, 6)


def estimate_sam_image_usd() -> float:
    return 2.50 / 1000


def reserve(job_id: str, estimated_usd: float, *, note: str = "") -> str:
    """Reserve budget before a paid call. Raises RuntimeError if over cap."""
    if not math.isfinite(estimated_usd) or estimated_usd < 0:
        raise ValueError("estimated_usd must be >= 0")
    with _lock:
        d = load_ledger()
        total = float(d["total_budget_usd"])
        if any(e.get("actual_usd") is None and not e.get("from_cache")
               for e in d.get("events", [])):
            raise RuntimeError("Unknown prior charge requires reconciliation before new inference")
        per_run = float(d["per_run_budget_usd"])
        spent = float(d["spent_usd"])
        reserved = float(d["reserved_usd"])
        # Sum prior spends+reservations for this job
        job_spent = sum(
            float(e.get("actual_usd") or e.get("estimated_usd") or 0)
            for e in d.get("events") or []
            if e.get("job_id") == job_id and not e.get("from_cache")
        )
        job_reserved = sum(
            float(r.get("estimated_usd") or 0)
            for r in (d.get("reservations") or {}).values()
            if r.get("job_id") == job_id
        )
        if job_spent + job_reserved + estimated_usd > per_run + 1e-9:
            raise RuntimeError(
                f"Per-run budget ${per_run:.2f} would be exceeded "
                f"(job so far ${job_spent + job_reserved:.4f} + ${estimated_usd:.4f})"
            )
        if spent + reserved + estimated_usd > total + 1e-9:
            raise RuntimeError(
                f"Total budget ${total:.2f} would be exceeded "
                f"(spent ${spent:.4f} reserved ${reserved:.4f} + ${estimated_usd:.4f})"
            )
        rid = str(uuid.uuid4())
        d.setdefault("reservations", {})[rid] = {
            "job_id": job_id,
            "estimated_usd": estimated_usd,
            "ts": time.time(),
            "note": note,
        }
        d["reserved_usd"] = round(reserved + estimated_usd, 6)
        save_ledger(d)
        return rid


def commit(
    reservation_id: str,
    *,
    provider: str,
    kind: str,
    actual_usd: float | None,
    usage: dict[str, Any] | None = None,
    from_cache: bool = False,
    note: str = "",
) -> dict[str, Any]:
    with _lock:
        d = load_ledger()
        res = (d.get("reservations") or {}).pop(reservation_id, None)
        if res is None:
            raise KeyError(f"unknown reservation {reservation_id}")
        est = float(res["estimated_usd"])
        d["reserved_usd"] = round(max(0.0, float(d["reserved_usd"]) - est), 6)
        charge = 0.0 if from_cache else float(actual_usd if actual_usd is not None else est)
        event = asdict(
            SpendEvent(
                event_id=str(uuid.uuid4()),
                ts=time.time(),
                job_id=res["job_id"],
                provider=provider,
                kind=kind,
                estimated_usd=est,
                actual_usd=0.0 if from_cache else actual_usd,
                from_cache=from_cache,
                usage=usage or {},
                note=note or res.get("note") or "",
            )
        )
        d.setdefault("events", []).append(event)
        if not from_cache:
            d["spent_usd"] = round(float(d["spent_usd"]) + charge, 6)
        save_ledger(d)
        return event


def release(reservation_id: str, *, note: str = "released_unused") -> None:
    """Drop a reservation without charging (e.g. cache hit before call)."""
    with _lock:
        d = load_ledger()
        res = (d.get("reservations") or {}).pop(reservation_id, None)
        if res is None:
            return
        est = float(res["estimated_usd"])
        d["reserved_usd"] = round(max(0.0, float(d["reserved_usd"]) - est), 6)
        d.setdefault("events", []).append(
            {
                "event_id": str(uuid.uuid4()),
                "ts": time.time(),
                "job_id": res["job_id"],
                "provider": "none",
                "kind": "reservation_released",
                "estimated_usd": est,
                "actual_usd": 0.0,
                "from_cache": True,
                "usage": {},
                "note": note,
            }
        )
        save_ledger(d)
