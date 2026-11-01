"""Synthetic scientific boundary regressions; never modify recorded evidence."""
from types import SimpleNamespace
import numpy as np
import pytest
import container as C
import failure_inputs as FI
import tracking as T
import verification as V


@pytest.mark.parametrize("terminal", ["response.incomplete", "response.failed", None])
def test_uncompleted_destination_not_admitted(monkeypatch, terminal):
    cache = SimpleNamespace(observations=[SimpleNamespace(mask_rle={"test": True}, bbox=[0, 0, 2, 2],
        observation_returned=True, confidence=.9)], diagnostics=SimpleNamespace(usage={"tray": {"terminal_event": terminal}}))
    monkeypatch.setattr(T, "extract_frame_jpeg", lambda *a, **k: b"synthetic")
    monkeypatch.setattr(T, "load_cached_tracking", lambda *a, **k: cache)
    monkeypatch.setattr(T, "mask_in_frame", lambda *a: np.ones((2, 2), bool))
    mask, info = FI._container_mask(b"test", 0, "tray", 30, (2, 2))
    assert mask is None and info["status"] == "completion_unverified"
    cache.diagnostics.usage["tray"]["terminal_event"] = "response.completed"
    mask, info = FI._container_mask(b"test", 0, "tray", 30, (2, 2))
    assert mask.all() and info["status"] == "available"


def test_border_background_is_never_a_hole():
    mask = np.zeros((5, 5), bool)
    mask[0, 0] = mask[-1, 0] = mask[0, -1] = mask[-1, -1] = True
    assert np.array_equal(C.fill_holes(mask), mask)
    # A real enclosed hole still fills.
    ring = np.ones((5, 5), bool); ring[2, 2] = False
    assert C.fill_holes(ring).all()


def test_success_cannot_be_verified_without_any_evidence():
    result = V.verify_failure_report({"verdict": "success", "physical_events": [], "object_outcomes": []},
        observations=[], container_mask=None, gripper_measured=None, fps=30, n_frames=120, frame_shape=(10, 10))
    assert result.errors


def test_final_region_is_recomputed_from_raw_observations():
    # Claim "outside" for a stationary mask entirely in the destination footprint.
    observations = [T.ObjectTrackObservation(f/30, "plate:0", "plate", f, (2, 2, 4, 4), None,
        mask_rle={"size": [2, 2], "counts": [0, 4]}) for f in range(30)]
    report = {"verdict": "failure", "physical_events": [], "object_outcomes": [
        {"track_id": "plate:0", "concept": "plate", "final_region": "outside", "frames": list(range(30)), "status": "inferred"}]}
    mask = np.ones((10, 10), bool)
    args = dict(observations=observations, gripper_measured=None, fps=30, n_frames=30, frame_shape=(10, 10))
    assert V.verify_failure_report(report, container_mask=mask, **args).errors
    # Actually outside a distant footprint remains independently verifiable.
    mask[:] = False; mask[7:9, 7:9] = True
    assert not V.verify_failure_report(report, container_mask=mask, **args).errors


def test_cached_concept_identity_is_not_a_lossy_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "CHUNK_CACHE_ROOT", tmp_path)
    chunk = T.window_chunk(0, 30)
    # Old colliding slug file contains another concept, despite completed status.
    path = T.chunk_cache_path("synthetic", chunk, "red cup")
    call = SimpleNamespace(to_dict=lambda: {"concept": "red-cup", "status": "completed", "n_observations": 0})
    T.write_chunk_entry(path, chunk=chunk, call=call, observations=[], prompt_text="red-cup")
    assert T.cached_chunk_entries("synthetic", chunk, "red cup") == []


def test_legacy_muse_cannot_contradict_deterministic_outcome():
    from pathlib import Path
    import evidence_fusion as EF
    package = EF.load_experiment_package(Path(__file__).resolve().parents[1] /
        "data/experiments/botfails_ep010_w1260_v2", task_description="test")
    assert package.physical_events
    package.deterministic_verdict = "failure"
    result = EF.validate_muse_explanation({"explanation": "unsupported success", "task_outcome": "success",
        "earliest_failure_interval": None, "outcome_evidence_ids": [], "factual_claims": [],
        "hypotheses": [], "visual_interpretations": [], "limitations": []}, package)
    assert not result.ok


def test_final_outcome_requires_rest_not_just_fresh_outside_detections():
    observations = [T.ObjectTrackObservation(f/30, "plate:0", "plate", f, (f, 2, f+2, 4), None,
        mask_rle={"size": [2, 2], "counts": [0, 4]}) for f in range(30)]
    report = {"verdict": "failure", "physical_events": [], "object_outcomes": [
        {"track_id": "plate:0", "concept": "plate", "final_region": "outside", "frames": list(range(30)), "status": "inferred"}]}
    mask = np.zeros((50, 50), bool); mask[40:45, 40:45] = True
    assert V.verify_failure_report(report, observations=observations, container_mask=mask,
        gripper_measured=None, fps=30, n_frames=30, frame_shape=(50, 50)).errors


def test_existing_citation_does_not_validate_invented_legacy_measurement():
    from pathlib import Path
    import evidence_fusion as EF
    package = EF.load_experiment_package(Path(__file__).resolve().parents[1] /
        "data/experiments/botfails_ep010_w1260_v2", task_description="test")
    result = EF.validate_muse_explanation({"explanation": "Invented measurement", "task_outcome": "uncertain",
        "earliest_failure_interval": None, "outcome_evidence_ids": [],
        "factual_claims": [{"text": "The gripper measured 900 degrees.", "evidence_ids": [package.evidence_items[0].evidence_id]}],
        "hypotheses": [], "visual_interpretations": [], "limitations": []}, package)
    assert not result.ok


def test_cache_filenames_preserve_exact_concept_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "CHUNK_CACHE_ROOT", tmp_path)
    chunk = T.window_chunk(0, 30)
    assert T.chunk_cache_path("video", chunk, "red cup") != T.chunk_cache_path("video", chunk, "red-cup")


def test_legacy_cache_is_read_without_mutation_and_not_double_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "CHUNK_CACHE_ROOT", tmp_path)
    chunk = T.window_chunk(0, 30)
    primary = T.chunk_cache_path("video", chunk, "red cup")
    legacy = primary.parent / "red_cup.json"
    call = SimpleNamespace(to_dict=lambda: {"concept": "red cup", "status": "completed", "n_observations": 0})
    T.write_chunk_entry(legacy, chunk=chunk, call=call, observations=[], prompt_text="red cup")
    original = legacy.read_bytes()
    assert T.read_chunk_entry(primary)["call"]["concept"] == "red cup"
    assert not primary.exists() and legacy.read_bytes() == original
    T.write_chunk_entry(primary, chunk=chunk, call=call, observations=[], prompt_text="red cup")
    assert len(T.cached_chunk_entries("video", chunk, "red cup")) == 1
    assert legacy.read_bytes() == original
