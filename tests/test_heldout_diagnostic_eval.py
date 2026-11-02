"""Evaluation measures source coverage without turning abstention/citations into accuracy."""
import ast
import json
from pathlib import Path
import pytest
import heldout_diagnostic_eval as H


@pytest.fixture(scope="module")
def report():
    if H.missing_coverage_inputs():
        pytest.skip('retrospective coverage reproduction needs optional original SAM caches; not bundled for public replay')
    return H.run()


def test_missing_raw_inputs_have_an_explicit_no_inference_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(H, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['heldout_diagnostic_eval.py', '--check'])
    with pytest.raises(SystemExit) as error:H.main()
    assert error.value.code == 2
    assert 'optional original SAM caches' in capsys.readouterr().err


def test_unique_coverage_counts_with_portable_synthetic_observations(tmp_path, monkeypatch):
    from dataclasses import replace
    inv = H.S.load('ep010')
    inv.evidence = replace(inv.evidence, n_frames=5, tracking_windows=((0, 4),))
    path = tmp_path/'data/demo_cache/ep010/sam_window/green_plate.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'chunk':{'start_frame':0,'end_frame':4},'observations':[
        {'frame_index':0,'mask_rle':{'counts':[0,1]}}, {'frame_index':0}, {'frame_index':2}]}))
    (path.parent.parent/'MANIFEST.json').write_text(json.dumps({'window_frames':[0,4]}))
    monkeypatch.setattr(H, 'ROOT', tmp_path)
    row=H.coverage(inv)
    assert row['returned_record_count']==3 and row['inspectable_returned_frames']==2
    assert row['requested_frames_without_inspectable_returned_observations']==2
    assert row['records_with_masks']==1 and not row['invalid_source_frames']


def test_only_undisputed_retrospective_heldouts_are_scored(report):
    assert report["summary"]["heldout_total"] == 4
    assert {r["investigation_id"] for r in report["episodes"] if r["eligible"]} == {"ep003", "ep005", "ep013"}
    assert report["summary"]["outcomes"]["pipeline"] == {"correct_definitive": 2, "wrong_definitive": 0, "abstentions": 1, "denominator": 3}
    assert report["summary"]["outcomes"]["muse_only"]["wrong_definitive"] == 1
    assert report["summary"]["outcomes"]["criteria_completion"]["abstentions"] == 3
    assert report["summary"]["independently_verified_physical_failure_mechanisms"] == 0
    assert report["semantic_false_claims"]["confirmed_count"] is None


def test_unique_frame_counts_are_not_record_counts_or_assumed_full_windows(report):
    rows = {r["investigation_id"]: r["tracking"] for r in report["episodes"]}
    assert rows["ep005"]["requested_window_frames"] == 240
    assert rows["ep005"]["inspectable_returned_frames"] == 120
    assert rows["ep005"]["returned_record_count"] == 360
    assert rows["ep005"]["requested_frames_without_inspectable_returned_observations"] == 120
    assert rows["ep010"]["inspectable_returned_frames"] == 121
    assert rows["ep010"]["cache_chunk_bounds"] == [1260, 1381]
    assert rows["ep010"]["frames_outside_cache_chunk_bounds"] == []
    assert rows["pilot"]["inspectable_returned_frames"] == 632
    assert rows["pilot"]["requested_frames_without_inspectable_returned_observations"] == 105
    assert all(not row["invalid_source_frames"] for row in rows.values())


def test_references_do_not_affect_coverage_or_predictions(monkeypatch, report):
    refs = H.D.load_references()
    for r in refs.values():r["reference_outcome"] = "opposite";r["mechanisms"] = []
    monkeypatch.setattr(H.D, "load_references", lambda: refs)
    changed = H.run()
    for before, after in zip(report["episodes"], changed["episodes"]):
        for field in ("tracking", "outcomes", "diagnostic_candidates", "criteria", "saved_hypotheses"):
            assert before[field] == after[field]


def test_reproduction_files_match_current_sources(report):
    assert (H.OUT/"evaluation.json").read_text(encoding="utf-8") == json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    assert (H.OUT/"REPORT.md").read_text(encoding="utf-8") == H.render(report)


def test_evaluation_is_never_imported_by_runtime():
    root = Path(__file__).resolve().parents[1]
    for name in ("task_criteria.py", "criteria_presentation.py", "saved_investigations.py", "live_pipeline.py", "live_api.py", "multicamera.py"):
        tree = ast.parse((root/name).read_text(encoding="utf-8"))
        modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        modules += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert "heldout_diagnostic_eval" not in modules and "diagnostic_eval" not in modules
