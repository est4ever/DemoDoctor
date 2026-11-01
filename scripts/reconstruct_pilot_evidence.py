"""Reconstruct one recorded pilot offline; never calls SAM or Muse.

Writes a new before/after directory, preserving the original job and provider caches.
Usage: venv/Scripts/python.exe scripts/reconstruct_pilot_evidence.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, default=ROOT / "data/live_jobs/20261030T222607Z_7325777c")
    parser.add_argument("--out", type=Path, default=ROOT / "data/live_jobs/_reconstruction_audit/20261030T222607Z_7325777c")
    args = parser.parse_args()
    job, output = args.job.resolve(), args.out.resolve()
    if output.is_relative_to(job) or output.is_relative_to(ROOT / "data/experiments"):
        raise ValueError("Output must not be inside the original job or frozen experiments")
    output.mkdir(parents=True, exist_ok=False)

    def forbidden(*a, **kw):
        raise RuntimeError("Offline reconstruction forbids network and inference")

    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    import httpx
    import httpx2
    for module in (httpx, httpx2):
        module.Client.send = forbidden
        module.AsyncClient.send = forbidden
    import ai_analysis as AI
    import sam_api
    import failure_inputs as FI
    import failures as F
    import evidence_fusion as EF
    import live_pipeline as LP
    import verification as V

    AI.get_client = forbidden
    sam_api.client = forbidden
    FI.T.Sam31Tracker = forbidden

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.write("\n")

    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in job.iterdir() if p.is_file()}
    ledger_path = ROOT / "data/live_jobs/budget_ledger.json"
    ledger_digest = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    request = read(job / "request.json")
    old_report, old_verifier = read(job / "failure_report.json"), read(job / "verification.json")
    old_muse = read(job / "muse_result.json")
    for name in ("failure_report.json", "verification.json", "evidence_package.json", "analysis.json", "muse_result.json"):
        target = output / "before" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(job / name, target)

    n = old_report["inputs"]["n_frames"]
    fps = old_report["inputs"]["fps"]
    start, end = read(job / "status.json")["window_frames"]
    inputs = FI.build_window_inputs(job / "video.mp4", start_frame=start, end_frame=end,
        object_concept=request["object_concept"], container_concept=request["destination_concept"],
        container_frame=start)
    assert inputs.gripper is None
    task = F.TaskSpec("live_custom", request["task_description"],
                      (F.ObjectSpec(request["object_concept"], None),), request["destination_concept"])
    report = FI.localize_window(inputs, task, include_observation_events=True)
    scope = LP._apply_analysis_scope(report, complete=request["complete_demonstration"],
                                     start=start, end=end, n_frames=n)
    verifier = V.verify_failure_report(report.to_dict(), observations=inputs.observations,
        container_mask=inputs.container_mask, gripper_measured=None, fps=fps,
        n_frames=n, frame_shape=inputs.frame_shape).to_dict()
    verifier["ok"] = LP._verification_accepted(verifier)
    if not verifier["ok"]:
        raise RuntimeError(f"Offline verification failed: {verifier}")
    package = EF.build_evidence_package(task_description=task.description,
        failure_report=report.to_dict(), experiment_id=job.name + "_offline_reconstruction",
        verification=verifier, strict_grounding=True, observations=inputs.observations,
        analysis_scope=scope, context_frames=[start, (start + end - 1) // 2, end - 1])
    text_package = package.to_muse_text_dict()
    tracks = read(job / "tracks.json")
    analysis = LP._analysis_bundle_from_pipeline(job_id=job.name, task_description=task.description,
        report=report, verification=verifier, muse=None, tracks_meta=tracks,
        overlay_meta={"available": False}, joint_limitations=[], window=(start, end),
        fps=fps, package=text_package, video_duration_s=n / fps)
    analysis["evidence_catalog"] = text_package["evidence_catalog"]
    analysis["frame_catalog"] = text_package["frame_catalog"]
    analysis["observed"] = [{"text": item["summary"], "evidence_ids": [item["evidence_id"]],
                             "t": item["t_start"]} for item in analysis["evidence_catalog"]
                            if item["status_context"] == "observed"]
    analysis["limitations"].append("Offline reconstruction only. Muse was not rerun; the original response belongs to the before catalog.")
    for name, data in (("failure_report.json", report.to_dict()), ("verification.json", verifier),
                       ("evidence_package.json", text_package), ("analysis.json", analysis)):
        write(output / "after" / name, data)
    revalidation = EF.validate_muse_explanation(old_muse["validated"]["raw"], package)
    write(output / "historical_muse_revalidation.json", {
        "paid_call": False, "note": "Historical citations must not be rebound to regenerated IDs. This is not a new Muse response.",
        "validation": revalidation.to_dict()})
    summary = {
        "source_job": job.name, "network_allowed": False, "paid_calls": 0,
        "before": {"verdict": old_report["verdict"], "events": len(old_report["physical_events"]),
                   "claims_checked": old_verifier["claims_checked"]},
        "after": {"verdict": report.verdict, "events": len(report.physical_events),
                  "event_kinds": [e.kind for e in report.physical_events],
                  "claims_checked": verifier["claims_checked"], "verification_ok": verifier["ok"]},
        "target_segmentation": inputs.container_source,
        "observation_coverage": inputs.sources["observation_coverage"],
        "historical_muse_rebound_valid": revalidation.ok,
        "original_job_hashes": originals, "budget_ledger_sha256": ledger_digest,
    }
    assert originals == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in job.iterdir() if p.is_file()}, "Original job changed"
    assert hashlib.sha256(ledger_path.read_bytes()).hexdigest() == ledger_digest, "Budget changed"
    write(output / "comparison.json", summary)
    print(json.dumps({"output": str(output), **{k: v for k, v in summary.items()
                                              if k not in ("original_job_hashes", "budget_ledger_sha256")}}, indent=2))


if __name__ == "__main__":
    main()
