"""Local FastAPI service: upload video → analyze (SAM + events + Muse).

Keys stay in .env. Paid calls only on explicit POST /analyze.
Does not mutate frozen experiment evaluation trees.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import secrets
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field

import live_budget as budget
from live_pipeline import AnalyzeRequest, JOBS_ROOT, JOB_IO_LOCK, new_job_id, run_analyze
import live_pipeline as pipeline

load_dotenv(Path(__file__).resolve().parent / ".env")

@asynccontextmanager
async def lifespan(app):
    # Background jobs cannot survive a process restart. Never restart paid work.
    for path in JOBS_ROOT.glob("*/status.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("status") in {"queued", "running"}:
                data.update(status="interrupted", errors=["Backend restarted during analysis. No automatic retry was made; inspect the ledger for unresolved charges before a new job."])
                pipeline._write_job(path.parent, "status.json", data)
        except (OSError, ValueError):
            continue
    yield


app = FastAPI(title="DemoDoctor Live API", version="0.1.0", lifespan=lifespan)
TRUSTED_BROWSER_ORIGINS = {
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
    for port in (5173, 4173, 3000, 8765)
}
OFFLINE_ONLY = False  # The Windows launcher enables this before serving requests.
REAL_ANALYSIS_ENABLED = False  # Explicit local startup opt-in; never changed by a browser request.
_approval_lock = threading.Lock()
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
    response=await call_next(request)
    if request.url.path.startswith(('/api/jobs','/live-data/','/api/placement/','/api/native-video/')):
        response.headers['Cache-Control']='no-store'
    return response


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


def _validated_camera_manifest(job_id: str, analysis=None):
    directory=_job_directory(job_id)
    if job_id.startswith('placement-'):
        from placement_assessment.service import verify
        try: verify(directory)
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(409, 'Placement evidence quarantined: missing, altered or unauthorized artifacts. No inference was started.')
    from saved_provenance import validate, CitationBindingError
    try:
        analysis_path=_job_file(job_id,'analysis.json')
        if analysis is None and analysis_path.is_file():
            analysis=json.loads(analysis_path.read_text(encoding='utf-8'))
        if not (directory/'multicamera.json').is_file() and not (analysis or {}).get('multicamera'):
            if analysis is not None:
                from saved_provenance import citation_authority
                citation_authority(directory,analysis)
            return None  # Original single-camera jobs have no composite/camera binding.
        return validate(directory,analysis)
    except CitationBindingError:
        raise HTTPException(409,'Saved citation-to-evidence binding is invalid. The original package and saved results were not changed. No analysis was started.')
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError):
        raise HTTPException(409,'Saved source/camera/crop/frame provenance could not be validated. Media and context are quarantined; original results are unchanged. No inference was started.')


def _require_run_allowed(dry_run: bool, cache_only: bool = False) -> None:
    if OFFLINE_ONLY and not (dry_run or cache_only):
        raise HTTPException(403, "DemoDoctor launcher is offline: use dry_run or cache_only.")

JOBS_ROOT.mkdir(parents=True, exist_ok=True)
from placement_assessment.service import register as register_placement
register_placement(app, JOBS_ROOT)
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
        from saved_provenance import single_authority, digest
        analysis['citation_bindings']=single_authority(analysis,package,'recorded-pilot/after/evidence_package.json',digest(audit/'after/evidence_package.json'))
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
        "offline_only": OFFLINE_ONLY,
        "real_analysis_enabled": REAL_ANALYSIS_ENABLED and not OFFLINE_ONLY,
        "providers": {"meta": {"configured": T.model_api_key_available(), "model": "sam-3.1"},
                      "fireworks": {"configured": muse_ready, "model": "accounts/fireworks/models/muse-spark-open"}},
        "configuration_note": "Configuration detected locally; credentials, credit and provider acceptance are not authenticated by this check.",
    }


@app.get("/api/budget")
def get_budget() -> dict[str, Any]:
    return budget.status()


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    import saved_jobs
    jobs = []
    if JOBS_ROOT.is_dir():
        # Native/placement IDs are random, not sortable creation timestamps.
        # Show recently saved investigations before applying the history limit.
        for p in sorted(JOBS_ROOT.iterdir(), key=lambda p:p.stat().st_mtime, reverse=True):
            if not p.is_dir() or p.name.startswith("_"):
                continue
            try:
                directory = _job_directory(p.name)
            except HTTPException:
                continue
            if not any((directory/name).is_file() for name in ('status.json','analysis.json','request.json','multicamera.json')):
                continue
            try:
                with JOB_IO_LOCK:
                    jobs.append(saved_jobs.describe(directory))
            except Exception:
                jobs.append({"job_id": p.name, "status": "unknown", "can_open": False,
                             "availability_error": "Saved metadata is unreadable. No analysis was started."})
            if len(jobs)==50:break
    return {"jobs": jobs[:50]}


@app.get('/api/jobs/{job_id}/reopen')
def reopen_job(job_id: str) -> dict[str, Any]:
    """Restore saved artifacts only. Never starts, resumes or retries inference."""
    import saved_jobs
    directory=_job_directory(job_id)
    if not directory.is_dir():raise HTTPException(404,'Saved investigation not found. No analysis was started.')
    problem=saved_jobs.availability_error(directory)
    if problem:raise HTTPException(409,problem)
    analysis=get_analysis(job_id)
    if analysis.get('task_coverage_error'):
        raise HTTPException(409,analysis['task_coverage_error'])
    tracks=get_tracks(job_id) if (directory/'tracks.json').is_file() else None
    return {'job_id':job_id,'analysis':analysis,'tracks':tracks}


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
    analysis = json.loads(path.read_text(encoding="utf-8"))
    if analysis.get('placement_assessment') and not job_id.startswith('placement-'):
        raise HTTPException(409, 'Unregistered placement assessment')
    manifest = _validated_camera_manifest(job_id,analysis)
    if manifest is not None:
        analysis={**analysis,'multicamera':manifest}
    from saved_provenance import citation_authority, CitationBindingError
    try:analysis={**analysis,'citation_bindings':citation_authority(path.parent,analysis,manifest)}
    except CitationBindingError:
        raise HTTPException(409,'Saved citation-to-evidence binding is invalid. Original artifacts are unchanged. No analysis was started.')
    if (analysis.get('criteria') or {}).get('temporal_evidence') and not (manifest is not None and analysis.get('dry_run') is False):
        analysis={**analysis,'criteria':{k:v for k,v in analysis['criteria'].items() if k!='temporal_evidence'},
            'temporal_evidence_error':'Cached temporal evidence withheld: no validated real camera-analysis binding is available. Original results are unchanged.'}
    # Older camera jobs gain explicit task coverage on read, not by mutating
    # their recorded analysis, provider output, verdict or citation package.
    if analysis.get('multicamera') and analysis.get('dry_run') is False and not (analysis.get('criteria') or {}).get('task_text'):
        try:
            from task_coverage import build_assessment
            criteria, _ = build_assessment(path.parent)
            analysis = {**analysis, 'criteria': criteria}
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            analysis.pop('criteria', None)
            analysis['task_coverage_error'] = 'Task reassessment unavailable: approved camera/source provenance could not be verified. Original results remain available; no new inference was run.'
    # New local temporal selections are separate from original Muse inputs and
    # saved criteria. Existing results survive an unavailable context artifact.
    if manifest is not None and analysis.get('dry_run') is False and analysis.get('criteria'):
        try:
            from task_coverage import build_assessment
            updated, _ = build_assessment(path.parent)
            analysis = {**analysis, 'criteria': {**analysis['criteria'], **{k:updated[k] for k in ('temporal_evidence','coverage','context_frames')}}}
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            criteria={k:v for k,v in analysis['criteria'].items() if k not in ('temporal_evidence','context_frames','coverage')}
            analysis = {**analysis, 'criteria':criteria,'temporal_evidence_error': 'Local temporal evidence unavailable: original camera/observation provenance could not be validated. Cached context was withheld; saved results remain unchanged.'}
    import saved_jobs
    return {**analysis, 'execution':saved_jobs.execution_summary(path.parent)}


@app.get("/api/jobs/{job_id}/tracks")
def get_tracks(job_id: str) -> dict[str, Any]:
    path = _job_file(job_id, "tracks.json")
    if not path.is_file():
        raise HTTPException(404, "tracks not ready")
    manifest=_validated_camera_manifest(job_id)
    tracks=json.loads(path.read_text(encoding="utf-8"))
    if manifest is not None:
        from saved_provenance import validate_artifact, numeric_metadata
        try:
            numeric_metadata(tracks)
            if 'camera_id' in tracks or 'camera_provenance' in tracks:
                provenance=tracks.get('camera_provenance')
                cid=tracks.get('camera_id') or (provenance.get('camera_id') if isinstance(provenance,dict) else None)
                validate_artifact(path.parent,manifest,cid,'tracks.json',tracks)
        except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'Saved track camera/source binding is invalid')
    return tracks


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
    manifest=_validated_camera_manifest(job_id)
    if name=='analysis.json':
        return get_analysis(job_id)  # Never expose an unchecked cached T report through the raw-file alias.
    if manifest is not None and name=='tracks.json':
        return get_tracks(job_id)
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
    prepare_only: bool = Form(False),
    investigation_questions: str = Form("", max_length=2000),
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
    if not dry_run:
        if not REAL_ANALYSIS_ENABLED:
            raise HTTPException(403, "Real Analysis requires explicit local startup: DemoDoctor -RealAnalysis. Offline mode is unchanged.")
        if not prepare_only:
            raise HTTPException(409, "Prepare the video and confirm its estimate before starting Real Analysis.")
        ready = health()
        if not ready["sam_key"] or not ready["muse_key"]:
            raise HTTPException(503, "Configure MODEL_API_KEY and FIREWORKS_API_KEY in the backend environment; restart the local real-analysis service.")
        if not run_muse or force_sam_refresh:
            raise HTTPException(422, "UI Real Analysis requires Muse and uses the existing cache without forced paid refresh.")

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
        "investigation_questions": investigation_questions,
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
        investigation_questions=investigation_questions,
    )
    if not dry_run:
        # Probe the actual bytes before a cost confirmation. No provider calls here.
        try:
            raw = video_path.read_bytes()
            fps, frames = pipeline.T.probe_video(raw)
            start, end = pipeline._choose_window(fps, frames, window_start_s, window_end_s, max_window_s)
            width, height = pipeline.T.probe_video_size(raw)
        except Exception as exc:
            pipeline._write_job(job_dir, "status.json", {"job_id": job_id, "status": "failed", "stages": [],
                                "errors": ["Video could not be decoded; no providers were called."]})
            raise HTTPException(422, "Video could not be decoded or its selected window is empty.") from exc
        sam = budget.estimate_sam_window_usd(end - start, fps) + budget.estimate_sam_image_usd()
        quote = {"job_id": job_id, "approval_id": secrets.token_urlsafe(32), "expires_at": time.time() + 900,
                 "filename": video.filename, "sha256": hashlib.sha256(raw).hexdigest(),
                 "frame_start": start, "frame_end": end, "fps": fps, "source_frames": frames,
                 "width": width, "height": height, "start_s": start / fps, "end_s": end / fps,
                 "complete_task_scope": complete_demonstration and start == 0 and end == frames,
                 "sam_estimate_usd": sam, "muse_reservation_usd": pipeline.MUSE_RESERVATION_USD,
                 "estimated_max_usd": round(sam + pipeline.MUSE_RESERVATION_USD, 6),
                 "operations": ["At most 1 Meta file upload", "1 SAM object-video request", "1 SAM destination-image request", "1 Muse evidence explanation"],
                 "automatic_retries": 0, "budget": b,
                 "note": "Conservative reservation at published standard rates, not a provider-enforced billing guarantee. Cache hits can reduce calls. No joint data or calibrated destination interior is supplied."}
        pipeline._write_job(job_dir, "prepared.json", {"quote": quote, "request": meta})
        pipeline._write_job(job_dir, "status.json", {"job_id": job_id, "status": "awaiting_approval", "stages": [], "errors": []})
        return {"job_id": job_id, "status": "awaiting_approval", "quote": quote}
    _spawn_analyze(req)
    return {
        "job_id": job_id,
        "status": "queued",
        "budget": budget.status(),
        "message": "Analysis started. Poll GET /api/jobs/{job_id}.",
    }


class AnalysisApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


@app.post("/api/jobs/{job_id}/start")
def start_prepared(job_id: str, approval: AnalysisApproval) -> dict[str, Any]:
    """Consume a file-bound, expiring approval once; never retry a lost POST."""
    _require_run_allowed(False)
    if not REAL_ANALYSIS_ENABLED:
        raise HTTPException(403, "Real Analysis is not enabled for this local session")
    with _approval_lock:
        directory = _job_directory(job_id)
        path = _job_file(job_id, "prepared.json")
        if not path.is_file():
            raise HTTPException(404, "Prepared analysis not found; prepare the video again")
        saved = json.loads(path.read_text(encoding="utf-8"))
        quote = saved["quote"]
        if saved.get("consumed"):
            raise HTTPException(409, "This approval was already used; recover its job status instead of resubmitting")
        if not secrets.compare_digest(quote["approval_id"], approval.approval_id) or time.time() > quote["expires_at"]:
            raise HTTPException(409, "Invalid or expired approval; prepare again")
        if hashlib.sha256((directory / "video.mp4").read_bytes()).hexdigest() != quote["sha256"]:
            raise HTTPException(409, "Prepared video changed; analysis was not started")
        ready = health()
        if not ready["sam_key"] or not ready["muse_key"]:
            raise HTTPException(503, "Provider configuration is missing; no inference was started")
        headroom = ready["budget"]
        if quote["estimated_max_usd"] > min(headroom["remaining_usd"], headroom["per_run_budget_usd"]):
            raise HTTPException(402, "Full estimate exceeds the remaining or per-run budget; no provider was called")
        if _running:
            raise HTTPException(409, "Another analysis is running; wait for completion before approving this one")
        ledger = budget.load_ledger()
        if ledger.get("reservations") or any(e.get("actual_usd") is None and not e.get("from_cache") for e in ledger.get("events", [])):
            raise HTTPException(409, "Unresolved provider charge or reservation: reconcile the local ledger before starting another real analysis")
        fields = {k: v for k, v in saved["request"].items() if k not in {"filename", "job_id"}}
        req = AnalyzeRequest(job_id=job_id, video_path=directory / "video.mp4", **fields)
        saved["consumed"] = True
        pipeline._write_job(directory, "prepared.json", saved)
        _spawn_analyze(req)
        return {"job_id": job_id, "status": "queued", "budget": budget.status()}


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


import multicamera_api
import sys as _sys
multicamera_api.register(app, _sys.modules[__name__])


def main() -> None:
    import uvicorn

    uvicorn.run("live_api:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
