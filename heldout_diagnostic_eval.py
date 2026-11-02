"""Retrospective saved-artifact evaluation; never imported by inference.

No provider calls. References are loaded only after predictions and coverage.
Outcome, physical diagnosis, lexical hypotheses, claims, citations and coverage
are separate measures. An abstention is not correct failure identification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import diagnostic_eval as D
import saved_investigations as S

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data/evaluation/heldout_diagnostic_v1"


def missing_coverage_inputs() -> list[str]:
    """Optional raw caches are not required for public offline replay."""
    return [f"data/demo_cache/{key}/{name}" for key in (*S.HELDOUT, 'ep010')
            for name in ('sam_window/green_plate.json', 'MANIFEST.json')
            if not (ROOT / f"data/demo_cache/{key}/{name}").is_file()]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def coverage(inv: S.SavedInvestigation) -> dict[str, Any]:
    """Count actual unique returned frames, never infer them from record counts.

    Demo cache contains only one of some investigations' two sampled windows.
    Provider-processed frames, actual returned observations, entire video and
    end-keyframe geometry are not interchangeable denominators.
    """
    ev = inv.evidence
    requested = {f for start, end in ev.tracking_windows for f in range(max(0, start), min(ev.n_frames, end))}
    if inv.investigation_id == "pilot":
        path = ROOT / "data/submission_demo/pilot/job/tracks.json"
        raw = _read(path)
        frames = {int(f) for f, observations in raw.get("frames", {}).items() if observations}
        records = sum(len(items) for items in raw.get("frames", {}).values())
        masks = sum(bool(o.get("mask") or o.get("mask_rle")) for items in raw.get("frames", {}).values() for o in items)
        chunk_bounds = None
    else:
        path = ROOT / f"data/demo_cache/{inv.investigation_id}/sam_window/green_plate.json"
        raw = _read(path)
        observations = [o for o in raw.get("observations", []) if o.get("observation_returned", True)]
        frames = {int(o["frame_index"]) for o in observations}
        records = len(observations)
        masks = sum(bool(o.get("mask_rle")) for o in observations)
        chunk = raw.get("chunk") or {}
        chunk_bounds = [chunk.get("start_frame"), chunk.get("end_frame")]
        manifest = _read(path.parent.parent / "MANIFEST.json")
        if inv.investigation_id in S.HELDOUT:
            saved = _read(ROOT / f"data/experiments/heldout_four_v2/{inv.example_id}/sam_partial.json")
            if manifest.get("video_sha256") != saved.get("video_sha256"):
                raise ValueError("Coverage cache belongs to a different source video")
        if len(chunk_bounds) != 2 or tuple(chunk_bounds) != tuple(manifest["window_frames"]):
            raise ValueError("Coverage cache and manifest window disagree")
    invalid = sorted(f for f in frames if not 0 <= f < ev.n_frames)
    valid = frames - set(invalid)
    within_requested = valid & requested
    # Disclose any source-bound discrepancy rather than silently clipping it.
    outside_chunk = sorted(f for f in valid if chunk_bounds and not chunk_bounds[0] <= f < chunk_bounds[1])
    return {"native_video_frames": ev.n_frames, "requested_window_frames": len(requested),
        "inspectable_returned_frames": len(valid), "inspectable_frames_in_requested_windows": len(within_requested),
        "requested_frames_without_inspectable_returned_observations": len(requested - valid),
        "inspectable_video_fraction": round(len(valid) / ev.n_frames, 6),
        "returned_record_count": records, "records_with_masks": masks,
        "first_returned_frame": min(valid) if valid else None, "last_returned_frame": max(valid) if valid else None,
        "invalid_source_frames": invalid, "frames_outside_cache_chunk_bounds": outside_chunk,
        "cache_chunk_bounds": chunk_bounds, "source": path.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scope": "Inspectable saved observations only. Unavailable earlier window artifacts are not counted as missing provider detections. This is not identity continuity, complete-object recall or segmentation accuracy."}


def run() -> dict:
    investigations = S.load_all()
    predictions = [D.predict(inv) for inv in investigations]
    coverages = {inv.investigation_id: coverage(inv) for inv in investigations}
    refs = D.load_references()  # evaluation only, after prediction/measurement
    rows = []
    for p in predictions:
        key = p["investigation_id"]
        ref = refs[key]
        heldout = p["split"] == "held-out"
        eligible = heldout and ref["status"] == "reference"
        grounded = next((m for m in next(i for i in investigations if i.investigation_id == key).models
                         if m.kind == "evidence_grounded"), None)
        rows.append({"investigation_id": key, "heldout": heldout, "eligible": eligible,
            "exclusion": None if eligible else ("disputed reference" if heldout else "development or no independent reference"),
            "reference": ref, "outcomes": p["outcomes"],
            "outcome_scores": {s: D._outcome_class(v, ref) for s, v in p["outcomes"].items()},
            "physical_mechanisms_independently_identified": [],
            "diagnostic_candidates": p["mechanisms"]["pipeline"],
            "saved_hypotheses": [] if grounded is None else grounded.raw.get("hypotheses", []),
            "mechanism_comparison": [{"reference_category": cat, **D._mechanism_level(cat, p)} for cat in ref["mechanisms"]],
            "criteria": p["criteria"], "citations": p["model_citations"], "claim_audit": p["claims"],
            "tracking": coverages[key]})
    scored = [row for row in rows if row["eligible"]]
    def counts(system: str) -> dict:
        labels = [r["outcome_scores"][system] for r in scored]
        return {"correct_definitive": labels.count("correct"), "wrong_definitive": labels.count("wrong"),
                "abstentions": labels.count("abstain"), "denominator": len(labels)}
    return {"evaluation": "heldout_diagnostic_v1", "new_inference_calls": 0,
        "design": "Retrospective frozen held-out split, already inspected during development; not a prospective unseen-video or generalization study.",
        "semantic_false_claims": {"confirmed_count": None,
            "reason": "No independent per-statement semantic adjudication. Citation existence, lexical matching and abstention cannot establish absence of false physical claims."},
        "summary": {"heldout_total": sum(r["heldout"] for r in rows), "scorable": len(scored),
            "outcomes": {s: counts(s) for s in predictions[0]["outcomes"]},
            "independently_verified_physical_failure_mechanisms": 0,
            "reference_failure_mechanisms": sum(len(r["reference"]["mechanisms"]) for r in scored),
            "recorded_2d_outside_contradictions": [r["investigation_id"] for r in scored if any(
                a["kind"] == "containment" and a["state"] == "contradicted" for a in r["criteria"]["assessments"])]},
        "episodes": rows}


def render(data: dict) -> str:
    lines = ["# Retrospective held-out diagnostic evaluation", "", data["design"], "",
        "Predictions and source-frame counts are computed before reference outcomes are loaded. "
        "Frozen outputs are unchanged; no new inference. EP010 development and PILOT are context only; "
        "EP006's disputed reference is excluded. Three scorable episodes are too few for accuracy claims.", "",
        "## Outcomes and diagnosis", "",
        "| Episode | Evaluation role | Reference | Pipeline | Criteria completion | Grounded Muse | Muse-only | Mechanism evidence |",
        "|---|---|---|---|---|---|---|---|"]
    for r in data["episodes"]:
        o = r["outcomes"]
        role = "scored retrospective held-out" if r["eligible"] else r["exclusion"]
        mechanism = "; ".join(m["mechanism"] + " (" + m["status"] + ")" for m in r["diagnostic_candidates"]) or "No reconstructed physical mechanism"
        lines.append(f"| {r['investigation_id']} | {role} | {r['reference']['reference_outcome'] or 'unknown'} | {o['pipeline']} | {o['criteria_completion']} | {o['evidence_grounded_muse']} | {o['muse_only'] or 'not run'} | {mechanism} |")
    lines += ["", "| System | Correct definitive | Wrong definitive | Abstain | Scorable |", "|---|---|---|---|---|"]
    for name, counts in data["summary"]["outcomes"].items():
        lines.append(f"| {name} | {counts['correct_definitive']} | {counts['wrong_definitive']} | {counts['abstentions']} | {counts['denominator']} |")
    lines += ["", "EP013 reconstructs an outside-target **2D sample**, not the cause or unobserved later recovery. "
        "EP005's saved flat-orientation suggestion is a plausible **Unverified hypothesis**, not measured orientation. "
        "Zero independently verified physical mechanisms; abstention is not failure identification.", "",
        "## Actual inspectable tracking coverage", "",
        "| Episode | Video frames | Requested frames | Inspectable unique frames | Observation records | Mask records | Video fraction | Cache-bound discrepancies |",
        "|---|---|---|---|---|---|---|---|"]
    for r in data["episodes"]:
        t = r["tracking"]
        lines.append(f"| {r['investigation_id']} | {t['native_video_frames']} | {t['requested_window_frames']} | {t['inspectable_returned_frames']} | {t['returned_record_count']} | {t['records_with_masks']} | {100*t['inspectable_video_fraction']:.2f}% | {t['frames_outside_cache_chunk_bounds']} |")
    lines += ["", "Some frozen runs requested two 120-frame windows but distribute only the later observation artifact. "
        "The report counts actual unique frame indices, not observations divided by three or provider-processed frames. "
        "A final segmentation image is not continuous tracking. Missing inspectable artifacts are not proof the provider missed a detection. "
        "EP010's actual raw-cache window is [1260,1381), including its recorded frame 1380. "
        "PILOT has 632/737 observed frames, with frames 433–537 unobserved. Coverage is not mask quality, object recall or identity continuity.", "",
        "## False claims and citation reliability", "",
        "- Mask counts refer only to retained artifacts. PILOT's packaged track export has boxes/centers and no mask payloads; zero retained masks does not mean the provider returned zero masks.",
        "- Muse-only EP005 success disagrees with the documented failure reference. This is an outcome error, not a per-statement semantic audit.",
        "- Semantic false-claim count: **not established**. Existing cited prose remains entailment-unverified by this retrospective evaluator; zero citation errors must not be called zero false claims."]
    for r in data["episodes"]:
        c = r["citations"].get("evidence_grounded")
        if c:
            lines.append(f"- {r['investigation_id']}: {c['evidence_citations']} evidence + {c['frame_citations']} frame references; {c['invalid']} invalid IDs; historical package={c['historical_package']}.")
    lines += ["", "All criteria and hypotheses keep their original evidence package. Predictions do not read references. "
        "No new measurements, failure labels, 3D estimates or cross-camera physical associations were created.", "",
        "## Resolving observations and reproducibility", "",
        "Each episode's JSON includes verbatim saved hypotheses, scoped criteria, per-criterion resolving observations, "
        "source paths/hashes and citation diagnostics. Orientation needs an approved pose definition plus an independent measurement; "
        "inventory needs an explicit expected count; final placement needs final-frame geometry; release needs holding-sensitive data "
        "and continuous object association. Additional views can reduce occlusion, but do not automatically establish 3D or identity.", "",
        "Run `python heldout_diagnostic_eval.py --check` to reproduce. This report is never imported by runtime prediction. "
        "A prospective newly uploaded robot-video run still requires separate explicit paid-inference approval.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__);ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    missing = missing_coverage_inputs()
    if missing:
        ap.error('Retrospective coverage reproduction requires optional original SAM caches, intentionally not bundled with public offline replay. No inference was started. Missing: ' + ', '.join(missing))
    data = run()
    files = {"evaluation.json": json.dumps(data, indent=2, ensure_ascii=False) + "\n", "REPORT.md": render(data)}
    if args.check:
        stale = [name for name, text in files.items() if not (OUT/name).is_file() or (OUT/name).read_text(encoding="utf-8") != text]
        print("stale: " + ", ".join(stale) if stale else "up to date")
        return int(bool(stale))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():(OUT/name).write_text(text, encoding="utf-8", newline="\n")
    print("Wrote retrospective held-out report; zero inference calls")
    return 0


if __name__ == "__main__":raise SystemExit(main())
