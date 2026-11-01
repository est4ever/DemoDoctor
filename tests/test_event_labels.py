"""Annotation schema tests (no datasets needed)."""

from __future__ import annotations

import json

import pytest

import event_labels as L


def record(**kw):
    base = {"example_id": "ep", "video_path": "v.mp4", "first_mishandling": None, "recovered": None,
            "final_outcome": None, "notes": "", "verified": False}
    base.update(kw)
    return base


def test_unset_fields_are_valid_and_nothing_is_filled_in(tmp_path):
    path = tmp_path / "event_labels.json"
    L.upsert_event_label(record(), path)
    saved = json.loads(path.read_text())["episodes"][0]
    assert saved["first_mishandling"] is None and saved["recovered"] is None and saved["final_outcome"] is None


def test_upsert_replaces_same_episode(tmp_path):
    path = tmp_path / "event_labels.json"
    L.upsert_event_label(record(final_outcome="failure"), path)
    L.upsert_event_label(record(final_outcome="success"), path)
    eps = json.loads(path.read_text())["episodes"]
    assert len(eps) == 1 and eps[0]["final_outcome"] == "success"


@pytest.mark.parametrize("bad,msg", [
    (record(example_id=""), "example_id"),
    (record(first_mishandling={"frame": 50, "t_s": 1.667, "object": ""}), "object is required"),
    (record(first_mishandling={"frame": 5000, "t_s": 166.667, "object": "plate"}), "valid frame"),
    (record(first_mishandling={"frame": 30, "t_s": 9.0, "object": "plate"}), "t_s does not match"),
    (record(recovered="maybe"), "recovered"),
    (record(final_outcome="ok"), "final_outcome"),
    (record(verified=True), "verified record needs a final_outcome"),
])
def test_invalid_records_are_rejected(tmp_path, bad, msg):
    with pytest.raises(ValueError, match=msg):
        L.upsert_event_label(bad, tmp_path / "x.json", n_frames=2090, fps=30.0)


def test_dataset_anomaly_onset_reads_headerless_csv(tmp_path):
    csv = tmp_path / "labels.csv"
    csv.write_text("\n".join(["0"] * 10 + ["1"] * 5 + ["0"] * 3) + "\n")
    onset = L.dataset_anomaly_onset(csv)
    assert onset["n_frames"] == 18 and onset["first_flagged_frame"] == 10 and onset["flagged_frames"] == 5
    assert "not a verified failure time" in onset["kind"]
    assert L.dataset_anomaly_onset(tmp_path / "missing.csv") is None
