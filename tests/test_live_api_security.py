"""Security boundaries use temporary sentinels and captured workers, never providers."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import live_api as api


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    neighbor = tmp_path / "neighbor"
    neighbor.mkdir()
    for name in ("status.json", "analysis.json", "tracks.json"):
        (neighbor / name).write_text('{"sentinel":true}')
    monkeypatch.setattr(api, "JOBS_ROOT", jobs)
    monkeypatch.setattr(api.budget, "status", lambda: {"remaining_usd": 10})
    dispatched = []
    monkeypatch.setattr(api, "_spawn_analyze", dispatched.append)
    monkeypatch.delenv("DEMODOCTOR_LOCAL_INPUT_ROOT", raising=False)
    return TestClient(api.app), jobs, dispatched, neighbor


@pytest.mark.parametrize("suffix", ["", "/analysis", "/tracks", "/files/analysis.json"])
def test_windows_traversal(isolated, suffix):
    client, _, _, _ = isolated
    response = client.get("/api/jobs/..%5Cneighbor" + suffix)
    assert response.status_code == 400
    assert "sentinel" not in response.text


@pytest.mark.parametrize("origin", ["https://attacker.invalid", "null", "http://localhost:5173.attacker.invalid"])
@pytest.mark.parametrize("endpoint", ["/api/analyze", "/api/analyze_local"])
def test_untrusted_origin_before_side_effects(isolated, origin, endpoint):
    client, jobs, dispatched, _ = isolated
    response = client.post(endpoint, headers={"Origin": origin},
        files={"video": ("test.mp4", b"synthetic")},
        data={"task_description": "test", "dry_run": "false"})
    assert response.status_code == 403
    assert not list(jobs.iterdir()) and not dispatched


def test_dns_rebinding_host(isolated):
    client, _, _, _ = isolated
    assert client.get("/api/jobs", headers={"Host": "attacker.invalid:8765"}).status_code == 400


def test_cross_site_browser_without_origin(isolated):
    client, jobs, dispatched, _ = isolated
    response = client.post("/api/analyze", headers={"Sec-Fetch-Site": "cross-site"},
        files={"video": ("test.mp4", b"synthetic")}, data={"task_description": "test"})
    assert response.status_code == 403 and not dispatched and not list(jobs.iterdir())


def test_local_file_endpoint_disabled_by_default(isolated):
    client, jobs, dispatched, neighbor = isolated
    response = client.post("/api/analyze_local", json={"video_path": str(neighbor / "analysis.json")})
    assert response.status_code == 403 and not dispatched and not list(jobs.iterdir())


def test_local_file_opt_in_cannot_escape_root(isolated, monkeypatch):
    client, jobs, dispatched, neighbor = isolated
    monkeypatch.setenv("DEMODOCTOR_LOCAL_INPUT_ROOT", str(jobs))
    response = client.post("/api/analyze_local", json={"video_path": str(neighbor / "analysis.json")})
    assert response.status_code == 403 and not dispatched and not list(jobs.iterdir())


@pytest.mark.parametrize("origin", [None, "http://localhost:5173", "http://127.0.0.1:4173"])
def test_cli_and_allowed_browser_still_work(isolated, origin):
    client, _, dispatched, _ = isolated
    response = client.post("/api/analyze", headers={"Origin": origin} if origin else {},
        files={"video": ("test.mp4", b"synthetic")}, data={"task_description": "test", "dry_run": "true"})
    assert response.status_code == 200 and dispatched[0].dry_run


def test_junction_or_symlink_job_cannot_escape(isolated):
    client, jobs, _, neighbor = isolated
    try:
        (jobs / "linked").symlink_to(neighbor, target_is_directory=True)
    except OSError:
        # Windows directory junctions need no administrator privilege.
        import subprocess
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(jobs / "linked"), str(neighbor)], capture_output=True)
        assert result.returncode == 0, result.stderr
    assert client.get("/api/jobs/linked/analysis").status_code == 400


def test_direct_media_route_has_same_boundary(isolated):
    client, jobs, _, _ = isolated
    job = jobs / "safe-job"
    job.mkdir()
    (job / "video.mp4").write_bytes(b"synthetic media")
    (job / "request.json").write_text('{"private":"sentinel"}')
    assert client.get("/live-data/..%5Cneighbor/analysis.json").status_code in (400, 404)
    assert client.get("/live-data/safe-job/request.json").status_code in (400, 404)
    assert client.get("/live-data/safe-job/video.mp4").content == b"synthetic media"
    assert client.get("/live-data/safe-job/video.mp4", headers={"Range": "bytes=0-3"}).content == b"synt"


def test_offline_rejection_precedes_job_creation(isolated, monkeypatch):
    client, jobs, dispatched, _ = isolated
    monkeypatch.setattr(api, "OFFLINE_ONLY", True)
    response = client.post("/api/analyze", files={"video": ("test.mp4", b"synthetic")},
        data={"task_description": "test", "dry_run": "false"})
    assert response.status_code == 403 and not list(jobs.iterdir()) and not dispatched


def test_explicit_local_cli_root_is_usable_but_browser_cannot_use_it(isolated, monkeypatch):
    client, jobs, dispatched, _ = isolated
    media = jobs / "synthetic.mp4"; media.write_bytes(b"synthetic media")
    monkeypatch.setenv("DEMODOCTOR_LOCAL_INPUT_ROOT", str(jobs))
    response = client.post("/api/analyze_local", json={"video_path": str(media), "dry_run": True})
    assert response.status_code == 200 and dispatched[0].dry_run
    dispatched.clear()
    response = client.post("/api/analyze_local", headers={"Origin": "http://localhost:5173"},
        json={"video_path": str(media), "dry_run": True})
    assert response.status_code == 403 and not dispatched


def test_artifact_symlink_cannot_expose_a_neighbor_file(isolated, monkeypatch):
    client, jobs, _, neighbor = isolated
    job = jobs / "safe-job"; job.mkdir()
    # Resolve-path substitution also covers Windows hosts without file-symlink privilege.
    original = Path.resolve
    def resolve(path, *args, **kwargs):
        if path == job / "analysis.json":
            return neighbor / "analysis.json"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    assert client.get("/api/jobs/safe-job/analysis").status_code == 400
