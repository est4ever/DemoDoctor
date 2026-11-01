"""Inference boundary regressions. No external requests or credentials needed."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

import ai_analysis as AI
import evidence_fusion as EF
import failures as F
import live_pipeline as LP
import sam_api


def package(**kwargs):
    report = {"verdict": "uncertain", "inputs": {"fps": 30}, "physical_events": [],
              "uncertainties": []}
    return EF.build_evidence_package(task_description="Place object in box", failure_report=report,
        experiment_id="test", strict_grounding=True, context_frames=[0, 60, 119], **kwargs)


def reply(**kwargs):
    return {"explanation": "The gripper opened and the task succeeded.",
            "task_outcome": "uncertain", "factual_claims": [], **kwargs}


def test_sdk_retry_policy_sends_one_attempt(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "dummy-test-key")
    calls = []
    def reject(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "test rate limit"}})
    client = AI.get_client("dummy-test-key")
    assert client.max_retries == 0 and client.timeout == 120
    client._client = httpx.Client(transport=httpx.MockTransport(reject))
    with client, pytest.raises(RateLimitError):
        client.chat.completions.create(model="test", messages=[])
    assert len(calls) == 1
    async def check():
        client = sam_api.client()
        assert client.max_retries == 0 and client.timeout == 120
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(reject))
        async with client:
            with pytest.raises(RateLimitError):
                await client.responses.create(model="test", input="test")
    asyncio.run(check())
    assert len(calls) == 2


def test_existing_id_does_not_verify_fabricated_gripper_or_success():
    obs = SimpleNamespace(observation_returned=True, frame_index=0, bbox=[0, 0, 10, 10],
                          object_id="object:0", timestamp_s=0)
    pkg = package(observations=[obs])
    assert pkg.evidence_items
    for raw in (reply(task_outcome="success"), reply(factual_claims=[{
            "text": "Measured gripper opening proved successful placement", "evidence_ids": ["E0"]}])):
        assert not EF.validate_muse_explanation(raw, pkg).ok
    safe = reply(factual_claims=[{"text": pkg.evidence_items[0].summary, "evidence_ids": ["E0"]}])
    validated = EF.validate_muse_explanation(safe, pkg)
    assert validated.ok
    assert "The gripper opened and the task succeeded" not in validated.explanation
    assert "(observed)" in validated.explanation


def test_empty_event_package_retains_context_not_fake_evidence():
    pkg = package()
    assert pkg.physical_events == [] and pkg.evidence_items == []
    assert [r.frame_index for r in pkg.frame_refs] == [0, 60, 119]
    assert all(r.role == "context" and not r.tied_evidence_ids for r in pkg.frame_refs)
    validated = EF.validate_muse_explanation(reply(), pkg)
    assert validated.ok and validated.task_outcome == "uncertain"
    assert "Insufficient verified evidence" in validated.explanation


@pytest.mark.parametrize("declared,start,end,expected", [(False, 0, 120, False),
    (True, 0, 60, False), (True, 10, 120, False), (True, 0, 120, True)])
def test_clip_final_frame_is_not_task_final_state(declared, start, end, expected):
    report = F.FailureReport("task", "success", None, None, [SimpleNamespace()], [], [], [], {})
    scope = LP._apply_analysis_scope(report, complete=declared, start=start, end=end, n_frames=120)
    assert scope["complete_demonstration"] is expected
    assert report.verdict == ("success" if expected else "uncertain")


@pytest.mark.parametrize("result", [{"claims_failed": 1}, {"claims_unverifiable": 1},
    {"findings": [{"severity": "error"}]}, {"event_verdicts": {0: "unsupported"}}])
def test_verifier_failure_is_a_hard_gate(result):
    assert not LP._verification_accepted(result)


def test_unknown_charge_is_not_recorded_as_actual(tmp_path, monkeypatch):
    import live_budget as budget
    monkeypatch.setattr(budget, "LEDGER_PATH", tmp_path / "ledger.json")
    rid = budget.reserve("job", 0.05)
    event = budget.commit(rid, provider="test", kind="test", actual_usd=None)
    assert event["actual_usd"] is None
    assert budget.load_ledger()["spent_usd"] == 0.05
    with pytest.raises(RuntimeError, match="reconciliation"):
        budget.reserve("next-job", 0.01)


def test_job_diagnostics_redact_credentials_in_provider_errors(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("MODEL_API_KEY", "dummy-meta-credential")
    monkeypatch.setenv("FIREWORKS_API_KEY", 'dummy-fireworks-"credential')
    path = LP._write_job(tmp_path, "status.json", {
        "errors": ["Authorization: Bearer dummy-meta-credential"],
        "traceback": 'provider echoed dummy-fireworks-"credential',
        "raw_response": {"message": "dummy-meta-credential"}})
    result = json.loads(path.read_text())
    assert result["errors"] == ["Authorization: Bearer [REDACTED]"]
    assert result["traceback"] == "provider echoed [REDACTED]"
    assert result["raw_response"]["message"] == "[REDACTED]"


@pytest.mark.parametrize("sam_status", ["completed", "incomplete", "failed"])
def test_live_empty_events_calls_muse_once_but_failed_sam_stops(tmp_path, monkeypatch, sam_status):
    import cv2
    import numpy as np
    import live_budget as budget
    video = tmp_path / "input.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    monkeypatch.setattr(LP, "JOBS_ROOT", tmp_path / "jobs")
    monkeypatch.setattr(budget, "ROOT", tmp_path)
    monkeypatch.setattr(budget, "LEDGER_PATH", tmp_path / "ledger.json")
    ledger = budget.load_ledger()
    ledger["per_run_budget_usd"] = 2
    budget.save_ledger(ledger)
    monkeypatch.setattr(LP.T, "model_api_key_available", lambda: True)
    monkeypatch.setattr(AI, "load_fireworks_api_key", lambda: "dummy-test-key")
    sequence = []
    class MockTracker:
        def track_window(self, *args, **kwargs):
            sequence.append("sam-video")
            return None, [], [SimpleNamespace(from_cache=False, status=sam_status,
                n_observations=0, usage={"usage": {"video_frames_processed": 50}})]
        def segment_image(self, *args, **kwargs):
            sequence.append("sam-image")
            return SimpleNamespace(observations=[], from_cache=False, diagnostics=SimpleNamespace(
                usage={"box": {"terminal_event": "response.completed"}}))
    monkeypatch.setattr(LP.T, "Sam31Tracker", MockTracker)
    inputs = LP.FI.WindowInputs(video.read_bytes(), 10, 20, (48, 64), None,
        None, [], None, {}, {}, [], None)
    monkeypatch.setattr(LP.FI, "build_window_inputs", lambda *a, **kw: inputs)
    def muse(pkg, frames, **kwargs):
        sequence.append("muse")
        assert frames and pkg.frame_refs
        assert not pkg.physical_events
        assert all(e.kind == "derived" and e.status_context == "uncertain" for e in pkg.evidence_items)
        assert pkg.deterministic_verdict == "uncertain"
        return {"validated": EF.validate_muse_explanation(reply(), pkg).to_dict(),
                "usage": {"prompt_tokens": 100, "completion_tokens": 100}, "paid_call": True}
    monkeypatch.setattr(AI, "analyze_with_evidence", muse)
    result = LP.run_analyze(LP.AnalyzeRequest("test", video, "Put item in box", "item", "box", dry_run=False))
    if sam_status == "completed":
        assert result["status"] == "completed", result
        assert sequence == ["sam-video", "sam-image", "muse"]
    else:
        assert result["status"] == "failed"
        assert sequence == ["sam-video"]
