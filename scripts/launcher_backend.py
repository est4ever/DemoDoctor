"""Offline launcher entrypoint; the application and scientific pipeline stay unchanged."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Always replay the distributable package, regardless of personal shell settings.
os.environ["DEMODOCTOR_PILOT_AUDIT"] = str(ROOT / "data/submission_demo/pilot/audit")
os.environ["DEMODOCTOR_PILOT_JOB"] = str(ROOT / "data/submission_demo/pilot/job")
import live_api as api
api.OFFLINE_ONLY = True
from fastapi import HTTPException
import uvicorn

spawn = api._spawn_analyze


def offline_analyze(req):
    if not (req.dry_run or req.cache_only):
        raise HTTPException(403, "DemoDoctor launcher is offline: use dry_run or cache_only.")
    return spawn(req)


api._spawn_analyze = offline_analyze


@api.app.get("/api/launcher", include_in_schema=False)
def identity():
    return {"protocol": 1, "kind": "backend", "root": str(ROOT),
            "pid": os.getpid(), "instance": os.environ["DEMODOCTOR_LAUNCH_INSTANCE"],
            "offline": True}


if __name__ == "__main__":
    uvicorn.run(api.app, host="127.0.0.1", port=8765, log_level="info")
