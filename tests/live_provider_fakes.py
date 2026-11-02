"""Explicit synthetic provider fixtures; never imported by the application."""
from types import SimpleNamespace
import time
import numpy as np
import live_pipeline as lp
import failure_inputs as fi
import failures as f
import evidence_fusion as ef


def install(monkeypatch, *, delay=0):
    state = {"scenario": "complete", "calls": [], "observations": []}
    def forbidden(*a, **kw):
        raise AssertionError("Network providers forbidden in this fixture")
    import sam_api
    monkeypatch.setattr(sam_api, "client", forbidden)
    monkeypatch.setattr(lp.AI, "get_client", forbidden)
    monkeypatch.setattr(lp.T, "model_api_key_available", lambda: True)
    monkeypatch.setattr(lp.AI, "load_fireworks_api_key", lambda: "synthetic-test-only")

    class Tracker:
        def track_window(self, raw, *, start_frame, end_frame, concepts, **kw):
            state["calls"].append("sam-video")
            time.sleep(delay)
            if state["scenario"] == "sam_fail":
                raise RuntimeError("QA synthetic SAM provider failure; no retry")
            fps, _ = lp.T.probe_video(raw)
            obs = []
            for i, frame in enumerate(sorted({start_frame, start_frame+1, end_frame-2, end_frame-1})):
                x = 10 if i < 2 else 40
                obs.append(lp.T.ObjectTrackObservation(frame/fps, f"{concepts[0]}:0", concepts[0], frame,
                    (x, 10, x+4, 14), (x+2, 12), confidence=.9,
                    mask_rle={"size":[4,4], "counts":[0,16]}))
            state["observations"] = obs
            return None, obs, [SimpleNamespace(from_cache=False, status="completed", n_observations=len(obs),
                usage={"usage":{"video_frames_processed":max(50,end_frame-start_frame)}})]
        def segment_image(self, raw, *, concept, **kw):
            state["calls"].append("sam-image")
            return SimpleNamespace(observations=[], from_cache=False,
                diagnostics=SimpleNamespace(usage={concept:{"terminal_event":"response.completed"}}))
    monkeypatch.setattr(lp.T, "Sam31Tracker", Tracker)

    def inputs(path, **kw):
        raw=path.read_bytes(); fps,n=lp.T.probe_video(raw); w,h=lp.T.probe_video_size(raw)
        obs=state["observations"]
        track=f.ObjectTrack(obs[0].object_id, obs[0].concept,
            [f.TrackObs(o.frame_index, o.centroid[0], o.centroid[1], np.hypot(4,4), "unknown") for o in obs])
        return fi.WindowInputs(raw,fps,n,(h,w),None,None,obs,None,
            {"status":"empty_result","concept":kw["container_concept"]},{},[track],None)
    monkeypatch.setattr(lp.FI, "build_window_inputs", inputs)
    def muse(pkg, frames, **kw):
        state["calls"].append("muse")
        if state["scenario"] == "muse_fail":
            raise RuntimeError("QA synthetic Muse provider failure; no retry")
        raw={"task_outcome":"uncertain", "explanation":"Synthetic test: the task outcome remains uncertain.", "factual_claims":[
            {"text":e.summary,"evidence_ids":[e.evidence_id]} for e in pkg.evidence_items
            if e.kind in {"detection","comparison","measurement"}],
            "visual_interpretations":[],"hypotheses":[],"limitations":["QA SYNTHETIC PROVIDERS; not a DROID inference result."]}
        return {"validated":ef.validate_muse_explanation(raw,pkg).to_dict(),"usage":{"prompt_tokens":100,"completion_tokens":100},"paid_call":False}
    monkeypatch.setattr(lp.AI, "analyze_with_evidence", muse)
    return state
