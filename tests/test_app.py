"""Headless Streamlit tests (AppTest). No paid buttons are clicked."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not ((ROOT / "sample_videos" / "sample.mp4").is_file()
         and (ROOT / "data" / "lerobot" / "ankithreddy__so101_pickplace_uno" / "SOURCE.json").is_file()),
    reason="needs sample video and joint data",
)


@pytest.fixture()
def app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    radio = [r for r in at.radio if r.label == "Video source"][0]
    radio.set_value("Hugging Face SO-101 sample")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _sam_mode(at, mode):
    [r for r in at.radio if r.key == "sam_mode"][0].set_value(mode)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at.session_state["last_tracking"] if "last_tracking" in at.session_state else None


def test_muse_baseline_controls_are_still_present(app):
    labels = [b.label for b in app.button]
    assert any(label.startswith("Analyze with AI") for label in labels)
    assert "last_diagnosis" not in app.session_state  # nothing was sent


def test_single_frame_mode_loads_its_cache(app):
    tr = _sam_mode(app, "Single frame (cheap)")
    assert tr is not None and tr.media_kind == "image" and len(tr.observations) == 1


def test_full_video_mode_shows_recovered_track_with_masks(app):
    tr = _sam_mode(app, "Full video")
    sd = tr.diagnostics.per_concept["screwdriver"]
    assert sd["frames_detected"] == 433 and sd["global_tracks"] == ["screwdriver:0"]
    assert tr.diagnostics.per_concept["white box"]["frames_detected"] == 737
    assert tr.overlay_paths and all("overlays_masks" in p for p in tr.overlay_paths)


def test_event_timeline_renders_and_every_event_is_inspectable(app):
    box = [s for s in app.selectbox if s.key == "event_inspect"][0]
    assert len(box.options) == 9
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Claims contradicted"] == "0"
    for i in range(len(box.options)):
        [s for s in app.selectbox if s.key == "event_inspect"][0].set_value(i)
        app.run()
        assert not app.exception, (i, [e.value for e in app.exception])
        assert [s for s in app.selectbox if s.key == "event_inspect"][0].value == i
    # Last event is the closure at ~20.8 s that reaches the command.
    assert any("does not prove the gripper is empty" in w.value for w in app.warning)


def test_annotation_section_shows_reference_without_prefilling(app):
    import event_labels as L

    box = [s for s in app.selectbox if s.key == "ann_episode"]
    if not box or "botfails_dish_test_ep010" not in box[0].options:
        pytest.skip("BotFails ep010 video not present")
    box[0].set_value("botfails_dish_test_ep010")
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    captions = " ".join(c.value for c in app.caption)
    assert "first flagged frame 1341" in captions and "not a verified failure time" in captions
    if L.get_event_label("botfails_dish_test_ep010") is None:
        assert any("not set" in m.value for m in app.markdown)  # nothing pre-filled


def test_probe_preview_without_sending(app):
    [t for t in app.toggle if t.key == "probe_toggle"][0].set_value(True)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("box;x1=245;y1=302;x2=315;y2=613" in c.value for c in app.code)
    send = [b for b in app.button if b.key == "probe_send"]
    if send:
        assert send[0].disabled  # approval checkbox not ticked
    else:  # already run: the cached result is shown and nothing can be re-sent
        assert any("Cached probe result" in s.value for s in app.success)
