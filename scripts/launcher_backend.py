"""Offline launcher entrypoint; the application and scientific pipeline stay unchanged."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

# Explicit process-only configuration. Never send credentials to the UI or log them.
if os.environ.get("DEMODOCTOR_REAL_ANALYSIS") == "1" and os.environ.get("DEMODOCTOR_CREDENTIALS_FILE"):
    load_dotenv(os.environ["DEMODOCTOR_CREDENTIALS_FILE"], override=False)
# Always replay the distributable package, regardless of personal shell settings.
os.environ["DEMODOCTOR_PILOT_AUDIT"] = str(ROOT / "data/submission_demo/pilot/audit")
os.environ["DEMODOCTOR_PILOT_JOB"] = str(ROOT / "data/submission_demo/pilot/job")
import live_api as api
real_analysis = os.environ.get("DEMODOCTOR_REAL_ANALYSIS") == "1"
api.OFFLINE_ONLY = not real_analysis
api.REAL_ANALYSIS_ENABLED = real_analysis
if real_analysis and os.environ.get("DEMODOCTOR_PER_RUN_BUDGET"):
    import math
    import live_budget as budget
    limit = float(os.environ["DEMODOCTOR_PER_RUN_BUDGET"])
    ledger = budget.load_ledger()
    if not math.isfinite(limit) or not 0 < limit <= min(10, ledger["total_budget_usd"]):
        raise ValueError("Explicit per-run budget must be positive and within the total ledger limit")
    ledger["per_run_budget_usd"] = limit
    budget.save_ledger(ledger)
from fastapi import HTTPException
import uvicorn

spawn = api._spawn_analyze


def offline_analyze(req):
    if not real_analysis and not (req.dry_run or req.cache_only):
        raise HTTPException(403, "DemoDoctor launcher is offline: use dry_run or cache_only.")
    return spawn(req)


api._spawn_analyze = offline_analyze


@api.app.get("/api/launcher", include_in_schema=False)
def identity():
    return {"protocol": 1, "kind": "backend", "root": str(ROOT),
            "pid": os.getpid(), "instance": os.environ["DEMODOCTOR_LAUNCH_INSTANCE"],
            "offline": not real_analysis, "real_analysis": real_analysis}


if __name__ == "__main__":
    uvicorn.run(api.app, host="127.0.0.1", port=8765, log_level="info")
