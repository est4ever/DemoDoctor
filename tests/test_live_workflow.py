"""Live HTTP regression: real upload and pipeline, no provider calls."""
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import live_api as api
import live_pipeline as pipeline
import live_budget as budget


@pytest.fixture
def client(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(api, "JOBS_ROOT", jobs)
    monkeypatch.setattr(pipeline, "JOBS_ROOT", jobs)
    monkeypatch.setattr(budget, "ROOT", tmp_path)
    monkeypatch.setattr(budget, "LEDGER_PATH", jobs / "ledger.json")
    def forbidden(*args, **kwargs):
        pytest.fail("Paid inference must never run")
    monkeypatch.setattr(pipeline.T, "Sam31Tracker", forbidden)
    monkeypatch.setattr(pipeline.AI, "analyze_with_evidence", forbidden)
    with TestClient(api.app) as c:
        yield c


def test_upload_dry_run_returns_complete_results(client, tmp_path):
    video = tmp_path / "test.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    response = client.post("/api/analyze", files={"video": ("test.mp4", video.read_bytes(), "video/mp4")},
                           data={"task_description": "Move the object", "dry_run": "true"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.02)
    assert status["status"] == "completed", status
    result = client.get(f"/api/jobs/{job_id}/analysis").json()
    for key in ("title", "task_outcome", "outcome_label", "frame_catalog", "observed", "inferred",
                "hypotheses", "factual_claims", "visual_interpretations", "limitations", "disclaimer"):
        assert key in result
    assert result["dry_run"] is True
    assert result["task_outcome"] == "uncertain"
    assert result["evidence_catalog"] == []
    assert client.get(f"/api/jobs/{job_id}/tracks").json()["frames"] == {}
    assert client.get("/api/budget").json()["spent_usd"] == 0
    assert client.get(f"/api/jobs/{job_id}/files/video.mp4").content == video.read_bytes()


@pytest.mark.parametrize("fields", [
    {"window_start_s": "3"},
    {"window_start_s": "4", "window_end_s": "2"},
    {"max_window_s": "nan"}, {"task_description": " "},
])
def test_invalid_request_rejected_before_job(client, fields):
    response = client.post("/api/analyze", files={"video": ("test.mp4", b"unused")},
                           data={"task_description": "Move object", **fields})
    assert response.status_code == 422
    assert client.get("/api/jobs").json()["jobs"] == []


def test_exhausted_budget_refuses_paid_upload(client):
    ledger = budget.load_ledger()
    ledger["spent_usd"] = ledger["total_budget_usd"]
    budget.save_ledger(ledger)
    response = client.post("/api/analyze", files={"video": ("test.mp4", b"unused")},
                           data={"task_description": "Move object", "dry_run": "false"})
    assert response.status_code == 402
    assert client.get("/api/jobs").json()["jobs"] == []


def test_budget_reservations_enforce_caps(client):
    reservation = budget.reserve("job", 0.8)
    with pytest.raises(RuntimeError, match="Per-run"):
        budget.reserve("job", 0.3)
    budget.release(reservation)
    assert budget.status()["reserved_usd"] == 0


def test_health_handles_missing_muse_configuration(client, monkeypatch):
    import ai_analysis as AI
    def missing():
        raise AI.FireworksConfigError("missing test key")
    monkeypatch.setattr(AI, "load_fireworks_api_key", missing)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["muse_key"] is False


def test_complete_task_declaration_reaches_upload_request(client, monkeypatch):
    captured = []
    monkeypatch.setattr(api, "_spawn_analyze", captured.append)
    response = client.post("/api/analyze", files={"video": ("complete.mp4", b"test fixture")},
                           data={"task_description": "Move object", "dry_run": "true",
                                 "complete_demonstration": "true", "max_window_s": "30"})
    assert response.status_code == 200
    assert captured[0].complete_demonstration is True
    assert captured[0].max_window_s == 30


def test_rejected_muse_cannot_override_pipeline_or_publish_claims():
    from types import SimpleNamespace
    report = SimpleNamespace(to_dict=lambda: {"verdict": "uncertain", "physical_events": []})
    result = pipeline._analysis_bundle_from_pipeline(
        job_id="test", task_description="Move object", report=report,
        verification={}, muse={"validated": {"ok": False, "task_outcome": "success",
        "explanation": "Invented success", "factual_claims": [{"text": "invented"}],
        "validation_errors": ["unsupported"]}}, tracks_meta={}, overlay_meta={},
        joint_limitations=[], window=(0, 20), fps=10)
    assert result["task_outcome"] == "uncertain"
    assert result["factual_claims"] == []
    assert result["muse_explanation"] is None
    assert result["live_job"]["muse_validation_errors"] == ["unsupported"]


def test_fused_event_evidence_ids_reach_timeline():
    from types import SimpleNamespace
    report = SimpleNamespace(to_dict=lambda: {"verdict": "uncertain", "physical_events": [{"kind": "release"}]})
    result = pipeline._analysis_bundle_from_pipeline(
        job_id="test", task_description="Move object", report=report,
        verification={}, muse=None, tracks_meta={}, overlay_meta={},
        joint_limitations=[], window=(0, 20), fps=10,
        package={"physical_events": [{"kind": "release", "status": "inferred",
                 "t_start": 1, "inference": "Candidate release", "evidence_ids": ["E0", "E1"]}]})
    assert result["timeline_markers"][0]["evidence_ids"] == ["E0", "E1"]
    assert result["inferred"][0]["evidence_ids"] == ["E0", "E1"]
