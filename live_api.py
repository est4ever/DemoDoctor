"""Local FastAPI service: upload video → analyze (SAM + events + Muse).

Keys stay in .env. Paid calls only on explicit POST /analyze.
Does not mutate frozen experiment evaluation trees.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict

import live_budget as budget
from live_pipeline import AnalyzeRequest, JOBS_ROOT, JOB_IO_LOCK, new_job_id, run_analyze

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="DemoDoctor Live API", version="0.1.0")
TRUSTED_BROWSER_ORIGINS = {
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
    for port in (5173, 4173, 3000, 8765)
}
OFFLINE_ONLY = False  # The Windows launcher enables this before serving requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(TRUSTED_BROWSER_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Reject DNS-rebinding hostnames. testserver is the in-process TestClient host.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])


@app.middleware("http")
async def trusted_browser_request(request: Request, call_next):
    origin = request.headers.get("origin")
    if ((origin is not None and origin not in TRUSTED_BROWSER_ORIGINS)
            or (origin is None and request.headers.get("sec-fetch-site") == "cross-site")):
        return JSONResponse({"detail": "Untrusted browser origin"}, status_code=403)
    return await call_next(request)


def _job_directory(job_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
        raise HTTPException(400, "Invalid job ID")
    root = JOBS_ROOT.resolve()
    directory = (root / job_id).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(400, "Invalid job directory")
    return directory


def _job_file(job_id: str, name: str) -> Path:
    directory = _job_directory(job_id)
    path = (directory / name).resolve()
    if not path.is_relative_to(directory):
        raise HTTPException(400, "Invalid artifact path")
    return path


def _require_run_allowed(dry_run: bool, cache_only: bool = False) -> None:
    if OFFLINE_ONLY and not (dry_run or cache_only):
        raise HTTPException(403, "DemoDoctor launcher is offline: use dry_run or cache_only.")

JOBS_ROOT.mkdir(parents=True, exist_ok=True)
_jobs_lock = threading.Lock()
_running: dict[str, threading.Thread] = {}


def _recorded_root(variable: str) -> Path:
    value = os.environ.get(variable)
    packaged = Path(__file__).resolve().parent / "data/submission_demo/pilot"
    path = Path(value) if value else packaged / ("audit" if variable.endswith("AUDIT") else "job")
    if not path.is_dir():
        raise HTTPException(404, f"Recorded replay unavailable: configure {variable}")
    return path.resolve()


@app.get("/api/recorded-pilot/{name}")
def recorded_pilot(name: str):
    """Read-only replay. No job creation, inference, or historical citation rebinding."""
    audit = _recorded_root("DEMODOCTOR_PILOT_AUDIT")
    job = _recorded_root("DEMODOCTOR_PILOT_JOB")
    if name == "analysis.json":
        analysis = json.loads((audit / "after/analysis.json").read_text(encoding="utf-8"))
        package = json.loads((audit / "after/evidence_package.json").read_text(encoding="utf-8"))
        analysis["recorded_evidence"] = {
            "verification": json.loads((audit / "after/verification.json").read_text(encoding="utf-8")),
            "provenance": package["provenance"],
        }
        # This span compares observations; it is not a suspected manipulation interval.
        analysis["highlight_interval"] = None
        return analysis
    paths = {"tracks.json": job / "tracks.json", "video.mp4": job / "video.mp4",
             "historical-analysis.json": audit / "before/analysis.json",
             "historical-package.json": audit / "before/evidence_package.json",
             "historical-muse.json": audit / "before/muse_result.json"}
    path = paths.get(name)
    if path is None or not path.is_file():
        raise HTTPException(404, "Recorded artifact unavailable")
    return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/json")


@app.get("/api/health")
def health() -> dict[str, Any]:
    import tracking as T
    import ai_analysis as AI
    try:
        muse_ready = bool(AI.load_fireworks_api_key())
    except AI.FireworksConfigError:
        muse_ready = False

    return {
        "ok": True,
        "sam_key": T.model_api_key_available(),
        "muse_key": muse_ready,
        "budget": budget.status(),
    }


@app.get("/api/budget")
def get_budget() -> dict[str, Any]:
    return budget.status()


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    jobs = []
    if JOBS_ROOT.is_dir():
        for p in sorted(JOBS_ROOT.iterdir(), reverse=True):
            if not p.is_dir() or p.name.startswith("_"):
                continue
            try:
                st = _job_file(p.name, "status.json")
            except HTTPException:
                continue
            if not st.is_file():
                continue
            try:
                with JOB_IO_LOCK:
                    jobs.append(json.loads(st.read_text(encoding="utf-8")))
            except Exception:
                jobs.append({"job_id": p.name, "status": "unknown"})
    return {"jobs": jobs[:50]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job_dir = _job_directory(job_id)
    if not job_dir.is_dir():
        raise HTTPException(404, "job not found")
    st = _job_file(job_id, "status.json")
    if not st.is_file():
        raise HTTPException(404, "status missing")
    with JOB_IO_LOCK:
        data = json.loads(st.read_text(encoding="utf-8"))
    # Attach lightweight result pointers
    data["has_analysis"] = (job_dir / "analysis.json").is_file()
    data["has_tracks"] = (job_dir / "tracks.json").is_file()
    data["has_overlay"] = (job_dir / "overlay.mp4").is_file()
    return data


@app.get("/api/jobs/{job_id}/analysis")
def get_analysis(job_id: str) -> dict[str, Any]:
    path = _job_file(job_id, "analysis.json")
    if not path.is_file():
        raise HTTPException(404, "analysis not ready")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/jobs/{job_id}/tracks")
def get_tracks(job_id: str) -> dict[str, Any]:
    path = _job_file(job_id, "tracks.json")
    if not path.is_file():
        raise HTTPException(404, "tracks not ready")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/jobs/{job_id}/files/{name}")
def get_file(job_id: str, name: str) -> FileResponse:
    allowed = {"video.mp4", "overlay.mp4", "analysis.json", "tracks.json",
               "status.json", "failure_report.json", "muse_result.json",
               "sam_overlay.json", "evidence_package.json", "verification.json"}
    if name not in allowed:
        raise HTTPException(400, "file not allowed")
    path = _job_file(job_id, name)
    if not path.is_file():
        raise HTTPException(404, "missing")
    media = "video/mp4" if name.endswith(".mp4") else "application/json"
    return FileResponse(path, media_type=media)


@app.get("/live-data/{job_id}/{name}", include_in_schema=False)
def job_media(job_id: str, name: str) -> FileResponse:
    # Same allowlist/containment as the API; never serve request.json or ledgers.
    return get_file(job_id, name)


def _spawn_analyze(req: AnalyzeRequest) -> None:
    def _run() -> None:
        try:
            run_analyze(req)
        finally:
            with _jobs_lock:
                _running.pop(req.job_id, None)

    (JOBS_ROOT / req.job_id / "status.json").write_text(
        json.dumps({"job_id": req.job_id, "status": "queued", "stages": [], "errors": []}),
        encoding="utf-8",
    )
    t = threading.Thread(target=_run, name=f"analyze-{req.job_id}", daemon=True)
    with _jobs_lock:
        _running[req.job_id] = t
    t.start()


@app.post("/api/analyze")
async def analyze(
    video: UploadFile = File(...),
    task_description: str = Form(...),
    object_concept: str = Form("green plate"),
    destination_concept: str = Form("dish rack"),
    window_start_s: float | None = Form(None),
    window_end_s: float | None = Form(None),
    max_window_s: float = Form(4.0),
    run_muse: bool = Form(True),
    dry_run: bool = Form(True),
    force_sam_refresh: bool = Form(False),
    complete_demonstration: bool = Form(False),
) -> dict[str, Any]:
    """Explicit analyze request. Does not run on GET/page load."""
    _require_run_allowed(dry_run)
    if not video.filename:
        raise HTTPException(400, "video required")
    try:
        AnalyzeRequest(job_id="validation", video_path=Path("unused"),
            task_description=task_description, object_concept=object_concept,
            destination_concept=destination_concept, window_start_s=window_start_s,
            window_end_s=window_end_s, max_window_s=max_window_s)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Pre-check budget headroom for a typical short run (~$0.30 est)
    b = budget.status()
    if not dry_run and b["remaining_usd"] < 0.05:
        raise HTTPException(402, f"Budget nearly exhausted: {b}")

    job_id = new_job_id()
    job_dir = JOBS_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "upload.mp4"
    with video_path.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    # Also copy to video.mp4 for stable naming
    shutil.copy2(video_path, job_dir / "video.mp4")

    meta = {
        "job_id": job_id,
        "filename": video.filename,
        "task_description": task_description,
        "object_concept": object_concept,
        "destination_concept": destination_concept,
        "window_start_s": window_start_s,
        "window_end_s": window_end_s,
        "max_window_s": max_window_s,
        "run_muse": run_muse,
        "dry_run": dry_run,
        "force_sam_refresh": force_sam_refresh,
        "complete_demonstration": complete_demonstration,
    }
    (job_dir / "request.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    req = AnalyzeRequest(
        job_id=job_id,
        video_path=job_dir / "video.mp4",
        task_description=task_description,
        object_concept=object_concept.strip(),
        destination_concept=destination_concept.strip(),
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        max_window_s=max_window_s,
        run_muse=run_muse,
        force_sam_refresh=force_sam_refresh,
        dry_run=dry_run,
        complete_demonstration=complete_demonstration,
    )
    _spawn_analyze(req)
    return {
        "job_id": job_id,
        "status": "queued",
        "budget": budget.status(),
        "message": "Analysis started. Poll GET /api/jobs/{job_id}.",
    }


class LocalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_path: Path
    task_description: str = "analyze demonstration"
    object_concept: str = "green plate"
    destination_concept: str = "dish rack"
    window_start_s: float | None = None
    window_end_s: float | None = None
    max_window_s: float = 4.0
    joint_dir: Path | None = None
    episode_index: int | None = None
    gripper_calibration: Path | None = None
    run_muse: bool = True
    force_sam_refresh: bool = False
    dry_run: bool = True
    cache_only: bool = False
    complete_demonstration: bool = False


@app.post("/api/analyze_local")
def analyze_local(payload: LocalRequest, request: Request) -> dict[str, Any]:
    """Local regression. cache_only never calls either provider, even with keys."""
    _require_run_allowed(payload.dry_run, payload.cache_only)
    local_root = os.environ.get("DEMODOCTOR_LOCAL_INPUT_ROOT")
    if not local_root or request.headers.get("origin") is not None or request.headers.get("sec-fetch-site"):
        raise HTTPException(403, "Local-path analysis is disabled; use video upload or explicitly configure a CLI input root.")
    root = Path(local_root).resolve()
    for value in (payload.video_path, payload.joint_dir, payload.gripper_calibration):
        if value is not None and not value.resolve().is_relative_to(root):
            raise HTTPException(403, "Local input is outside the configured input root")
    if payload.video_path.suffix.lower() not in {".mp4", ".webm", ".mov", ".avi", ".mkv"}:
        raise HTTPException(400, "A video file is required")
    if not payload.video_path.is_file():
        raise HTTPException(400, "video not found")
    job_id = new_job_id()
    job_dir = JOBS_ROOT / job_id
    try:
        req = AnalyzeRequest(job_id=job_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    b = budget.status()
    if not (req.dry_run or req.cache_only) and b["remaining_usd"] < 0.05:
        raise HTTPException(402, f"Budget nearly exhausted: {b}")
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(req.video_path, job_dir / "video.mp4")
    req.video_path = job_dir / "video.mp4"
    (job_dir / "request.json").write_text(
        json.dumps({**payload.model_dump(mode="json"), "job_id": job_id}, indent=2),
        encoding="utf-8",
    )
    _spawn_analyze(req)
    return {"job_id": job_id, "status": "queued", "budget": budget.status()}


def main() -> None:
    import uvicorn

    uvicorn.run("live_api:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
