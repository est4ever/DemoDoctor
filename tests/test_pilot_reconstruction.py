"""Video-only evidence regressions. Synthetic inputs; no provider requests."""
from types import SimpleNamespace

import numpy as np
import pytest

import failure_inputs as FI
import failures as F
import verification as V


def obs(frame, x):
    return SimpleNamespace(object_id="item:0", concept="item", frame_index=frame,
                           bbox=(x, 10, x + 10, 20), observation_returned=True,
                           timestamp_s=frame / 30, mask_rle=None)


def inputs(observations):
    track = F.ObjectTrack("item:0", "item", [F.TrackObs(o.frame_index,
        (o.bbox[0] + o.bbox[2]) / 2, 15, np.hypot(10, 10), "unknown") for o in observations])
    return FI.WindowInputs(b"", 30, 60, (100, 100), None, None, observations, None,
        {"status": "empty_result", "concept": "tray"}, {}, [track], None)


TASK = F.TaskSpec("test", "Place item in tray", (F.ObjectSpec("item", 1),), "tray")


def test_missing_target_explained_instead_of_just_unknown_final_state():
    report = FI.localize_window(inputs([obs(0, 10), obs(59, 50)]), TASK)
    assert any("empty_result" in u and "tray" in u for u in report.uncertainties)
    assert report.verdict == "uncertain"


def test_endpoint_change_is_verified_without_bridging_a_detection_gap():
    observations = [obs(0, 10), obs(1, 10), obs(58, 50), obs(59, 50)]
    report = FI.localize_window(inputs(observations), TASK, include_observation_events=True)
    assert report.verdict == "uncertain" and report.earliest_failure is None
    assert len(report.physical_events) == 1
    event = report.physical_events[0]
    assert event.kind == "image_position_change" and event.status == "observed"
    assert "continuous" in " ".join(event.uncertainties)
    verified = V.verify_failure_report(report.to_dict(), observations=observations,
        container_mask=None, gripper_measured=None, fps=30, n_frames=60, frame_shape=(100, 100))
    assert verified.claims_checked == 2 and not verified.errors and not verified.claims_unverifiable
    assert verified.event_verdicts == {0: "supported"}
    # Legacy failure localization still abstains and does not acquire new failure events.
    assert not FI.localize_window(inputs(observations), TASK).physical_events


def test_coverage_does_not_count_unreturned_or_out_of_window_rows():
    returned = [obs(0, 0), obs(0, 0), obs(9, 10), obs(10, 10)]
    missing = obs(1, 1); missing.observation_returned = False
    summary = FI.observation_coverage(returned + [missing], 0, 10)
    assert summary["frames_with_detections"] == 2
    assert summary["missing_frames"] == 8
    assert summary["missing_ranges"] == [{"frame_start": 1, "frame_end": 9}]


def test_no_motion_event_from_jitter_or_a_single_detection():
    for observations in ([obs(0, 10)], [obs(0, 10), obs(59, 11)]):
        report = FI.localize_window(inputs(observations), TASK, include_observation_events=True)
        assert not report.physical_events


@pytest.mark.parametrize("tamper", ["value", "coverage", "status", "time"])
def test_independent_verifier_rejects_tampered_observation_event(tamper):
    observations = [obs(0, 10), obs(59, 50)]
    report = FI.localize_window(inputs(observations), TASK, include_observation_events=True).to_dict()
    event = report["physical_events"][0]
    if tamper == "value": event["evidence"][0]["claims"][0]["value_px"] = 4000
    if tamper == "coverage": event["evidence"][1]["claims"][0]["missing_frames"] = 0
    if tamper == "status": event["status"] = "inferred"
    if tamper == "time": event["t_end"] = 99
    verified = V.verify_failure_report(report, observations=observations,
        container_mask=None, gripper_measured=None, fps=30, n_frames=60, frame_shape=(100, 100))
    assert verified.errors


def test_empty_and_undecodable_target_masks_are_not_target_geometry(monkeypatch):
    monkeypatch.setattr(FI.T, "extract_frame_jpeg", lambda *a, **k: b"test")
    monkeypatch.setattr(FI.T, "load_cached_tracking", lambda *a, **k:
        SimpleNamespace(observations=[], diagnostics=None))
    mask, source = FI._container_mask(b"test", 0, "tray", 30, (100, 100))
    assert mask is None and source["status"] == "empty_result"
    invalid = obs(0, 10); invalid.mask_rle = {"invalid": True}
    monkeypatch.setattr(FI.T, "load_cached_tracking", lambda *a, **k:
        SimpleNamespace(observations=[invalid], diagnostics=None))
    mask, source = FI._container_mask(b"test", 0, "tray", 30, (100, 100))
    assert mask is None and source["status"] == "unusable_masks"


def test_strict_package_exposes_missing_target_and_gaps_without_upgrading_outcome():
    import evidence_fusion as EF
    observations = [obs(0, 10), obs(59, 50)]
    report = FI.localize_window(inputs(observations), TASK, include_observation_events=True)
    report.inputs["sources"]["container"] = inputs(observations).container_source
    package = EF.build_evidence_package(task_description=TASK.description,
        failure_report=report.to_dict(), experiment_id="offline-test", strict_grounding=True,
        observations=observations, analysis_scope={"complete_demonstration": True,
                                                  "frame_start": 0, "frame_end": 60})
    assert package.provenance["observation_coverage"]["missing_frames"] == 58
    assert package.provenance["target_segmentation"]["status"] == "empty_result"
    fabricated = {"explanation": "Gripper opened and task succeeded.", "task_outcome": "success",
                  "factual_claims": [{"text": "Measured gripper opening", "evidence_ids": ["E0"]}]}
    assert not EF.validate_muse_explanation(fabricated, package).ok
    assert package.deterministic_verdict == "uncertain"


def test_image_segmentation_retains_parser_evidence_for_empty_matches(monkeypatch, tmp_path):
    import asyncio
    import tracking as T
    import sam_api
    async def image(*args, usage_out, **kwargs):
        usage_out["terminal_event"] = "response.completed"
        return SimpleNamespace(outcome=SimpleNamespace(status="completed"), records=[],
                               diagnostics=["empty diagnostic"], raw_output="recorded empty output")
    monkeypatch.setattr(sam_api, "segment_image_bytes", image)
    monkeypatch.setattr(T, "save_tracking_cache", lambda *a, **kw: tmp_path)
    result = asyncio.run(T.Sam31Tracker()._track_async(b"synthetic", concepts=["tray"], media_kind="image",
        chunk_s=4, overlap_frames=0, seed_from_previous=False))
    saved = result.diagnostics.usage["tray"]
    assert saved["parser_record_count"] == 0
    assert saved["raw_output"] == "recorded empty output"
    assert saved["parser_diagnostics"] == ["empty diagnostic"]
    assert not result.observations


def test_pilot_shaped_gap_is_not_filled_by_record_conversion():
    import tracking as T
    records = [SimpleNamespace(kind="box", frame=frame, object_id="0", left=0,
                               top=0, right=10, bottom=10)
               for frame in list(range(433)) + list(range(538, 737))]
    decoded = T.observations_from_result(SimpleNamespace(records=records), concept="item",
                                         fps=30, media_kind="clip")
    summary = FI.observation_coverage(decoded, 0, 737)
    assert len(decoded) == 632 and summary["missing_frames"] == 105
    assert summary["missing_ranges"] == [{"frame_start": 433, "frame_end": 538}]
