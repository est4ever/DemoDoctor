"""The launcher must reject paid requests before reaching any pipeline/provider."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
import pytest


def test_launcher_rejects_paid_requests_and_preserves_dry_cache_paths(monkeypatch):
    spawned = []
    fake_api = SimpleNamespace(app=FastAPI(), _spawn_analyze=spawned.append)
    monkeypatch.setitem(sys.modules, "live_api", fake_api)
    monkeypatch.setenv("DEMODOCTOR_PILOT_AUDIT", "unused-test-override")
    monkeypatch.setenv("DEMODOCTOR_PILOT_JOB", "unused-test-override")
    # run_path loads only the launcher; the real pipeline is never imported/called.
    before_path = sys.path[:]
    try:
        runpy.run_path(str(Path(__file__).parents[1] / "scripts/launcher_backend.py"))
        with pytest.raises(HTTPException) as error:
            fake_api._spawn_analyze(SimpleNamespace(dry_run=False, cache_only=False))
        assert error.value.status_code == 403
        assert spawned == []
        for dry_run, cache_only in [(True, False), (False, True)]:
            request = SimpleNamespace(dry_run=dry_run, cache_only=cache_only)
            fake_api._spawn_analyze(request)
            assert spawned[-1] is request
    finally:
        sys.path[:] = before_path
