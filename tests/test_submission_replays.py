"""Regression: judge replay must use distributable recorded media, never local jobs.

Found during submission QA: a tracked-only checkout rendered broken videos.
"""
import hashlib
import json
from pathlib import Path

import av
from fastapi.testclient import TestClient

import live_api

ROOT = Path(__file__).resolve().parents[1]


def test_distributed_replays_match_manifest_and_keep_native_frame_timing():
    manifest = json.loads((ROOT / "data/submission_demo/MANIFEST.json").read_text())
    assert manifest["recorded_not_mock"] is True
    assert manifest["new_inference_calls"] == 0
    assert sum(row["bytes"] for row in manifest["entries"]) < 40_000_000
    for row in manifest["entries"]:
        path = ROOT / row["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        if path.suffix == ".mp4":
            with av.open(str(path)) as source:
                stream = source.streams.video[0]
                assert stream.frames == row["frames"]
                assert float(stream.average_rate) == row["fps"]
                assert (stream.width, stream.height) == (row["width"], row["height"])


def test_packaged_pilot_needs_no_private_paths_and_keeps_evidence_limits(monkeypatch):
    monkeypatch.delenv("DEMODOCTOR_PILOT_AUDIT", raising=False)
    monkeypatch.delenv("DEMODOCTOR_PILOT_JOB", raising=False)
    with TestClient(live_api.app) as client:
        response = client.get("/api/recorded-pilot/analysis.json")
        assert response.status_code == 200
        analysis = response.json()
        assert analysis["task_outcome"] == "uncertain"
        assert analysis["earliest_failure"] is None
        assert analysis["factual_claims"] == []
        assert analysis["recorded_evidence"]["verification"]["claims_checked"] == 2
        claims = [c for e in analysis["evidence_catalog"] for c in e["claims"]]
        assert next(c for c in claims if c["type"] == "displacement")["value_px"] == 609.01
        coverage = next(c for c in claims if c["type"] == "observation_coverage")
        assert coverage["missing_ranges"] == [{"frame_start": 433, "frame_end": 538}]
        assert analysis["recorded_evidence"]["provenance"]["target_segmentation"]["status"] == "empty_result"
        original = client.get("/api/recorded-pilot/historical-analysis.json").json()
        package = client.get("/api/recorded-pilot/historical-package.json").json()
        assert all(eid in {e["evidence_id"] for e in package["evidence_catalog"]}
                   for c in original["factual_claims"] for eid in c["evidence_ids"])
