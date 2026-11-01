"""Recorded replay boundary: read-only artifacts and separate citation catalogs."""
import json

from fastapi.testclient import TestClient

import live_api as api


def test_recorded_replay_does_not_rebind_muse_or_write_jobs(tmp_path, monkeypatch):
    audit, job = tmp_path / "audit", tmp_path / "job"
    (audit / "after").mkdir(parents=True)
    (audit / "before").mkdir()
    job.mkdir()
    files = {
        audit / "after/analysis.json": {"task_outcome": "uncertain", "factual_claims": [], "highlight_interval": {"label": "suspected event interval"}},
        audit / "after/evidence_package.json": {"provenance": {"target_segmentation": {"status": "empty_result"}}},
        audit / "after/verification.json": {"claims_checked": 2, "claims_failed": 0, "ok": True},
        audit / "before/analysis.json": {"factual_claims": [{"text": "historical", "evidence_ids": ["E0"]}]},
        audit / "before/evidence_package.json": {"evidence_catalog": [{"evidence_id": "E0", "summary": "original"}]},
        audit / "before/muse_result.json": {"original": True},
        job / "tracks.json": {"frames": {}},
    }
    for path, data in files.items():
        path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("DEMODOCTOR_PILOT_AUDIT", str(audit))
    monkeypatch.setenv("DEMODOCTOR_PILOT_JOB", str(job))
    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not start analysis")
    monkeypatch.setattr(api, "_spawn_analyze", forbidden)
    before = {p: p.read_bytes() for p in files}
    with TestClient(api.app) as client:
        result = client.get("/api/recorded-pilot/analysis.json").json()
        assert result["task_outcome"] == "uncertain"
        assert result["factual_claims"] == []
        assert result["highlight_interval"] is None
        assert result["recorded_evidence"]["verification"]["claims_checked"] == 2
        assert client.get("/api/recorded-pilot/historical-analysis.json").json() == files[audit / "before/analysis.json"]
        assert client.get("/api/recorded-pilot/historical-package.json").json() == files[audit / "before/evidence_package.json"]
        assert client.get("/api/recorded-pilot/request.json").status_code == 404
    assert {p: p.read_bytes() for p in files} == before


def test_unconfigured_recorded_replay_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setenv("DEMODOCTOR_PILOT_AUDIT", "missing-test-pilot-audit")
    with TestClient(api.app) as client:
        response = client.get("/api/recorded-pilot/analysis.json")
        assert response.status_code == 404
        assert "DEMODOCTOR_PILOT_AUDIT" in response.json()["detail"]
