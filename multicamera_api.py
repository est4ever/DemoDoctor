"""Register optional multi-camera routes under the existing local security middleware."""
from __future__ import annotations
import hashlib
import json
import secrets
import shutil
import threading
import time
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import multicamera as mc


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


def register(app, api):
    @app.post("/api/multicamera/prepare")
    def prepare(videos: list[UploadFile] = File(...), manifest: str = Form(...), dry_run: bool = Form(True)):
        api._require_run_allowed(dry_run)
        if not dry_run:
            ready = api.health()
            if not ready["real_analysis_enabled"]:
                raise HTTPException(403, "Explicit local Real Analysis launch required")
            if not ready["sam_key"] or not ready["muse_key"]:
                raise HTTPException(503, "Meta and Fireworks configuration required in backend only")
        try:
            plan = mc.Manifest.model_validate_json(manifest)
        except (ValidationError, ValueError):
            raise HTTPException(422, "Invalid camera plan: confirm crops/alignment, unique names, finite offsets and a 0–30s shared window")
        expected = 1 if plan.source_mode == "composite" else len(plan.cameras)
        if len(videos) != expected or any(not f.filename or Path(f.filename).suffix.lower() != ".mp4" for f in videos):
            raise HTTPException(422, f"Upload {expected} MP4 source(s) for this camera plan")
        job_id = api.new_job_id()
        directory = api.JOBS_ROOT/job_id
        directory.mkdir(parents=True)
        try:
            for i, upload in enumerate(videos):
                total = 0
                with (directory/f"source{i+1}.mp4").open("wb") as target:
                    while block := upload.file.read(1024*1024):
                        total += len(block)
                        if total > 200*1024*1024:
                            raise ValueError("Each source must be at most 200 MiB")
                        target.write(block)
            saved = mc.prepare(directory, plan, [Path(v.filename.replace("\\", "/")).name for v in videos])
        except Exception as exc:
            api.pipeline._write_job(directory, "status.json", {"job_id": job_id, "status": "failed", "stages": [], "errors": [str(exc)]})
            raise HTTPException(422, str(exc)) from exc
        sam = sum(c["sam_estimate_usd"] for c in saved["cameras"])
        from task_actions import parse_task
        subgoals = parse_task(plan.task_description, plan.cameras[0].object_concept, plan.cameras[0].destination_concept)
        quote = {"job_id": job_id, "approval_id": secrets.token_urlsafe(32), "expires_at": time.time()+900,
            "task_description": plan.task_description,
            "task_subgoals": [{"description": s.description, "action": s.params['action']} for s in subgoals.criteria if s.kind == 'action'],
            "cameras": [{k: c[k] for k in ("camera_id", "name", "source_video_id", "source_sha256", "crop", "width", "height", "sha256", "frame_start", "frame_end", "fps", "operations", "sam_estimate_usd")} for c in saved["cameras"]],
            "start_s": plan.window_start_s, "end_s": plan.window_end_s,
            "sam_estimate_usd": sam, "muse_reservation_usd": api.pipeline.MUSE_RESERVATION_USD,
            "estimated_max_usd": round(sam+api.pipeline.MUSE_RESERVATION_USD, 6),
            "operations": ["Sequential SAM requests for each listed camera, then 1 combined Muse explanation (<=6 context frames)"],
            "automatic_retries": 0, "budget": api.budget.status(),
            "note": "Not a provider-enforced billing guarantee. No provider calls during preparation; approval covers all listed cameras. No 3D or verified physical outcome."}
        # Bind approval to the exact saved plan, crops, source bytes and derivatives.
        api.pipeline._write_job(directory, "prepared-multicamera.json", {"quote": quote, "dry_run": dry_run,
            "manifest_sha256": mc.digest(directory/"multicamera.json")})
        if dry_run:
            spawn(job_id, saved, True)
            return {"job_id": job_id, "status": "queued", "manifest": saved}
        api.pipeline._write_job(directory, "status.json", {"job_id": job_id, "status": "awaiting_approval", "stages": [], "errors": []})
        return {"job_id": job_id, "status": "awaiting_approval", "quote": quote, "manifest": saved}

    def spawn(job_id, manifest, dry_run):
        def worker():
            try:
                mc.run(api.JOBS_ROOT/job_id, manifest, dry_run)
            finally:
                with api._jobs_lock:
                    api._running.pop(job_id, None)
        api.pipeline._write_job(api.JOBS_ROOT/job_id, "status.json", {"job_id": job_id, "status": "queued", "stages": [], "errors": [], "dry_run": dry_run})
        thread = threading.Thread(target=worker, name=f"multicamera-{job_id}", daemon=True)
        with api._jobs_lock:
            api._running[job_id] = thread
        thread.start()

    @app.post("/api/multicamera/{job_id}/start")
    def start(job_id: str, approval: Approval):
        api._require_run_allowed(False)
        with api._approval_lock:
            ready = api.health()
            if not ready["real_analysis_enabled"] or not ready["sam_key"] or not ready["muse_key"]:
                raise HTTPException(403, "Explicit real-analysis session and both providers required")
            directory = api._job_directory(job_id)
            path = directory/"prepared-multicamera.json"
            if not path.is_file():
                raise HTTPException(404, "Prepared multi-camera analysis not found")
            saved = mc.read(path)
            quote = saved["quote"]
            if saved.get("dry_run") or saved.get("consumed") or time.time()>quote["expires_at"] or not secrets.compare_digest(approval.approval_id, quote["approval_id"]):
                raise HTTPException(409, "Expired, invalid or consumed approval; no automatic retries")
            if mc.digest(directory/"multicamera.json") != saved["manifest_sha256"]:
                raise HTTPException(409, "Camera plan changed; prepare again")
            manifest = mc.read(directory/"multicamera.json")
            for s in manifest["sources"]:
                if mc.digest(directory/(s["source_video_id"]+".mp4")) != s["sha256"]:
                    raise HTTPException(409, "Source bytes changed; prepare again")
            for c in manifest["cameras"]:
                if mc.digest(directory/c["camera_id"]/"video.mp4") != c["sha256"]:
                    raise HTTPException(409, "Camera video changed; prepare again")
            headroom = ready["budget"]
            if quote["estimated_max_usd"] > min(headroom["per_run_budget_usd"], headroom["remaining_usd"]):
                raise HTTPException(402, "Complete camera plan exceeds approved local budget; no providers called")
            ledger = api.budget.load_ledger()
            if api._running or ledger.get("reservations") or any(e.get("actual_usd") is None and not e.get("from_cache") for e in ledger.get("events", [])):
                raise HTTPException(409, "Running job or unresolved charge/reservation; no providers called")
            saved["consumed"] = True
            api.pipeline._write_job(directory, "prepared-multicamera.json", saved)
            spawn(job_id, manifest, False)
            return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}/cameras/{camera_id}/{name}")
    def camera_file(job_id: str, camera_id: str, name: str):
        directory = api._job_directory(job_id)
        if camera_id not in {"cam1", "cam2", "cam3"} or name not in {"video.mp4", "tracks.json", "analysis.json", "provenance.json", "evidence_package.json", "verification.json", "failure_report.json", "provider_observations.json", "status.json"}:
            raise HTTPException(400, "Camera artifact not allowed")
        parent = directory.resolve()
        path = (directory/camera_id/name).resolve()
        if not path.is_relative_to(parent):
            raise HTTPException(400, "Invalid camera artifact path")
        if not path.is_file():
            raise HTTPException(404, "Camera source artifact unavailable")
        manifest=api._validated_camera_manifest(job_id)
        if manifest is None:raise HTTPException(409,'Approved camera provenance unavailable')
        from saved_provenance import validate_artifact
        try:validate_artifact(directory,manifest,camera_id,name)
        except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'Saved camera artifact provenance mismatch')
        return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "application/json")

    @app.get("/api/jobs/{job_id}/sources/{source_id}")
    def source_file(job_id: str, source_id: str):
        if source_id.endswith(".mp4"):
            source_id = source_id[:-4]
        if source_id not in {"source1", "source2", "source3"}:
            raise HTTPException(400, "Source not allowed")
        path = api._job_file(job_id, source_id+".mp4")
        if not path.is_file():
            raise HTTPException(404, "Original source unavailable")
        manifest=api._validated_camera_manifest(job_id)
        if manifest is None or source_id not in {s['source_video_id'] for s in manifest['sources']}:
            raise HTTPException(409,'Source is not bound to the approved investigation')
        return FileResponse(path, media_type="video/mp4")
