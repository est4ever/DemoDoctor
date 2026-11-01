"""Cached experiment replay loader — no paid APIs, no Streamlit AppTest required."""

from __future__ import annotations

from pathlib import Path

import demo_replay as DR

ROOT = Path(__file__).resolve().parents[1]

PRIMARY = ("ep010", "ep003", "ep013", "ep005", "ep006")
ARCHIVE = ("ep001", "ep011")


def test_primary_and_archive_episodes_load_required_artifacts():
    for key in (*PRIMARY, *ARCHIVE):
        bundle = DR.load_replay_bundle(key, root=ROOT)
        assert bundle.ok, (key, bundle.missing)
        assert bundle.failure_report.get("verdict") in ("success", "failure", "uncertain")
        assert bundle.demo.split in ("development", "held-out")
        assert bundle.muse_only is not None, key
        assert bundle.evidence_muse is not None, key
        assert len(bundle.demo.matched_frames) == 4


def test_primary_demo_keys_order():
    assert DR.PRIMARY_DEMO_KEYS == PRIMARY
    for key in PRIMARY:
        assert key in DR.EPISODES


def test_heldout_v2_episodes_have_empty_physical_events():
    for key in ("ep003", "ep013", "ep005", "ep006"):
        bundle = DR.load_replay_bundle(key, root=ROOT)
        assert bundle.demo.layout == "heldout_v2"
        assert bundle.failure_report.get("physical_events") == []
        assert bundle.run_report is not None


def test_ep003_evidence_success_and_muse_only_success():
    bundle = DR.load_replay_bundle("ep003", root=ROOT)
    assert bundle.failure_report.get("verdict") == "success"
    assert (bundle.evidence_muse or {}).get("task_outcome") == "success"
    assert (bundle.muse_only or {}).get("verdict") == "success"


def test_ep013_evidence_failure_and_muse_only_failure():
    bundle = DR.load_replay_bundle("ep013", root=ROOT)
    assert bundle.failure_report.get("verdict") == "failure"
    assert (bundle.evidence_muse or {}).get("task_outcome") == "failure"
    assert (bundle.muse_only or {}).get("verdict") == "failure"


def test_ep005_muse_only_false_success_evidence_abstains():
    bundle = DR.load_replay_bundle("ep005", root=ROOT)
    assert (bundle.muse_only or {}).get("verdict") == "success"
    assert (bundle.evidence_muse or {}).get("task_outcome") == "uncertain"


def test_ep006_evidence_abstains():
    bundle = DR.load_replay_bundle("ep006", root=ROOT)
    assert (bundle.muse_only or {}).get("verdict") == "success"
    assert (bundle.evidence_muse or {}).get("task_outcome") == "uncertain"


def test_archive_heldout_have_empty_physical_events():
    for key in ARCHIVE:
        bundle = DR.load_replay_bundle(key, root=ROOT)
        assert bundle.failure_report.get("physical_events") == []
        outcome = (bundle.evidence_muse or {}).get("task_outcome")
        assert outcome == "uncertain"


def test_ep010_has_inferred_release_and_interval():
    bundle = DR.load_replay_bundle("ep010", root=ROOT)
    events = bundle.failure_report.get("physical_events") or []
    assert events
    assert any(e.get("subtype") == "released_outside_target" for e in events)
    assert bundle.failure_report.get("earliest_failure") is not None
    assert (bundle.evidence_muse or {}).get("task_outcome") == "uncertain"


def test_evidence_catalog_nonempty_for_primary():
    for key in PRIMARY:
        bundle = DR.load_replay_bundle(key, root=ROOT)
        catalog = DR._evidence_catalog(bundle)
        assert catalog, key
        assert all(e.get("evidence_id", "").startswith("E") for e in catalog)


def test_replay_makes_no_network_imports_of_clients():
    """Sanity: module does not call Muse/SAM paid APIs."""
    import demo_replay as m

    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "analyze_demonstration" not in src
    assert "analyze_with_evidence" not in src
    assert "get_client" not in src
    assert "segment_video" not in src
    assert "MODEL_API_KEY" not in src
