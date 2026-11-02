"""Standalone diagnostic evaluation over saved investigations (evaluation only; no inference, no API calls).

Predictions come from saved_investigations + task_criteria (and saved Muse outputs). References come from
data/evaluation/reference_mechanisms.json, read only here and only after predictions are computed.

Measures, per investigation and in aggregate:
- failure mechanisms identified (pipeline criteria layer, grounded Muse hypotheses, Muse-only)
- unsupported claims (uncited / invalid-cited facts, unhedged unmeasurable physical assertions)
- abstention, and whether each abstention names the unresolved criteria and resolving evidence
- citation validity (model citations vs the package they could cite; criterion citations vs the catalog)
- missing-evidence reporting
- reference outcome vs each prediction

    python diagnostic_eval.py            # writes data/evaluation/diagnostic_eval_v2/
    python diagnostic_eval.py --check    # exits 1 if the committed report differs from a fresh run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import saved_investigations as S
import task_criteria as TC

ROOT = Path(__file__).parent
REFERENCES_PATH = ROOT / "data" / "evaluation" / "reference_mechanisms.json"
OUT_DIR = ROOT / "data" / "evaluation" / "diagnostic_eval_v2"

CATEGORY_CRITERION = {"placement_outside_target": "containment", "incorrect_orientation": "orientation"}
CATEGORY_TERMS = {
    "incorrect_orientation": r"orient|\bflat\b|upright|wrong[- ]way|lying|lean",
    "placement_outside_target": r"outside|\bdrop|never (been )?placed|displaced|on (the )?table|misplac|not (stored|placed) in",
}
# Physical states this pipeline cannot measure; asserting them as fact is unsupported unless hedged.
PHYSICAL_TERMS = re.compile(r"\b(upright|flat|lying|oriented|holds?|holding|grasps?|grasped|gripped|drops?|dropped|"
                            r"releases?|released|intentional|successfully|mid-air|falling|inserts?|seated|stored)\b", re.I)
HEDGE_TERMS = re.compile(r"\b(not|cannot|can't|no|may|might|could|unverified|insufficient|unknown|does not|"
                         r"doesn't|appears?|possibl[ey]|whether)\b", re.I)
OUTCOME_OF_STATE = {"supported": "success", "contradicted": "failure", "unverified": "uncertain",
                    "not_assessed": "uncertain"}


def load_references(path: Path = REFERENCES_PATH) -> dict[str, dict[str, Any]]:
    return {e["investigation_id"]: e for e in json.loads(path.read_text(encoding="utf-8"))["episodes"]}


# --- prediction-side summaries (no reference access) ----------------------------------------

def _model(inv: S.SavedInvestigation, kind: str) -> S.ModelOutput | None:
    return next((m for m in inv.models if m.kind == kind), None)


def _categories(text: str) -> list[str]:
    return [c for c, rx in CATEGORY_TERMS.items() if re.search(rx, text, re.I)]


def unhedged_physical(text: str) -> bool:
    return bool(PHYSICAL_TERMS.search(text)) and not HEDGE_TERMS.search(text)


def citation_check(m: S.ModelOutput) -> dict[str, Any]:
    raw = m.raw
    cited: list[str] = []
    for c in raw.get("factual_claims") or []:
        cited += [str(x) for x in c.get("evidence_ids") or []]
    for h in raw.get("hypotheses") or []:
        cited += [str(x) for x in h.get("related_evidence_ids") or []]
    cited += [str(x) for x in raw.get("outcome_evidence_ids") or []]
    cited += [str(x) for x in (raw.get("earliest_failure_interval") or {}).get("evidence_ids") or []]
    frames = [str(v["frame_ref"]) for v in raw.get("visual_interpretations") or [] if v.get("frame_ref") is not None]
    bad_e = sorted({e for e in cited if e not in m.package_evidence_ids})
    bad_f = sorted({f for f in frames if f not in m.package_frame_refs})
    return {"evidence_citations": len(cited), "frame_citations": len(frames),
            "invalid": len([e for e in cited if e in bad_e]) + len([f for f in frames if f in bad_f]),
            "invalid_ids": bad_e + bad_f, "historical_package": m.historical}


def claim_audit(m: S.ModelOutput) -> dict[str, Any]:
    """Classify each model statement as cited fact / labeled-unverified / unsupported."""
    raw, unsupported, labeled, entailment_unverified = m.raw, [], 0, []
    if m.kind == "evidence_grounded":
        facts = raw.get("factual_claims") or []
        for c in facts:
            ids = [str(x) for x in c.get("evidence_ids") or []]
            text = str(c.get("text") or "")
            if not ids:
                unsupported.append({"text": text, "reason": "factual claim without citation"})
            elif any(i not in m.package_evidence_ids for i in ids):
                unsupported.append({"text": text, "reason": "cites unknown evidence"})
            else:
                entailment_unverified.append({"text": text,
                    "reason": "Citation IDs exist; this evaluator does not independently establish semantic entailment. Use original strict verifier records; lexical matches cannot certify a fact."})
        for v in raw.get("visual_interpretations") or []:
            if v.get("not_verified_by_pipeline", True):
                labeled += 1
            else:
                unsupported.append({"text": v.get("text"), "reason": "visual interpretation not labeled unverified"})
        labeled += len(raw.get("hypotheses") or [])
        n = len(facts) + len(raw.get("visual_interpretations") or []) + len(raw.get("hypotheses") or [])
    else:  # muse_only: no citation mechanism exists, so every physical assertion is unsupported
        statements = [str(s) for s in raw.get("observed_actions") or []]
        statements += [str(e.get("description") or "") for e in raw.get("evidence") or []]
        for text in statements:
            if unhedged_physical(text) or _categories(text):
                unsupported.append({"text": text, "reason": "uncited physical assertion (no evidence package)"})
        n = len(statements)
    return {"statements": n, "labeled_unverified": labeled, "unsupported": unsupported,
            "entailment_unverified": entailment_unverified,
            "scope": "Citation/label audit only. No natural-language fact is certified by keywords or citation existence."}


def predicted_mechanisms(inv: S.SavedInvestigation, report: TC.CriteriaReport) -> dict[str, Any]:
    grounded, only = _model(inv, "evidence_grounded"), _model(inv, "muse_only")
    hyps = {}
    if grounded is not None:
        for h in grounded.raw.get("hypotheses") or []:
            for c in _categories(str(h.get("text") or "")):
                hyps.setdefault(c, []).append(h.get("text"))
    muse_only = []
    if only is not None and only.outcome == "failure":
        muse_only = _categories(f"{only.raw.get('failure_mode') or ''} {only.raw.get('summary') or ''}")
    return {"pipeline": [{"mechanism": m.mechanism, "category": m.category, "status": m.status,
                          "verifier": m.verifier, "objects": m.objects, "evidence_ids": m.evidence_ids}
                         for m in report.mechanisms],
            "grounded_hypothesis_categories": hyps, "muse_only_categories": muse_only}


def missing_evidence(report: TC.CriteriaReport) -> dict[str, Any]:
    unverified = [a for a in report.assessments if a.state == "unverified" and a.kind != "completion"]
    return {"unverified_criteria": len(unverified),
            "with_requirement": sum(1 for a in unverified if a.requirements),
            "requirement_kinds": dict(sorted(Counter(r.kind for a in unverified for r in a.requirements).items())),
            "abstention_explained": (report.completion != "unverified") or bool(
                report.abstention_explanation and report.evidence_requirements)}


def criteria_citations(inv: S.SavedInvestigation, report: TC.CriteriaReport) -> dict[str, Any]:
    ids = [e for a in report.assessments for e in a.evidence_ids] + [e for m in report.mechanisms for e in m.evidence_ids]
    bad = [e for e in ids if e not in inv.evidence.evidence_ids]
    decisive_uncited = [a.criterion_id for a in report.assessments
                        if a.state in ("supported", "contradicted") and not a.evidence_ids]
    return {"citations": len(ids), "invalid": len(bad), "decisive_without_citation": decisive_uncited}


def predict(inv: S.SavedInvestigation) -> dict[str, Any]:
    report = TC.assess(inv.task, inv.evidence)
    grounded, only = _model(inv, "evidence_grounded"), _model(inv, "muse_only")
    return {
        "investigation_id": inv.investigation_id, "example_id": inv.example_id, "split": inv.split,
        "sources": inv.sources,
        "criteria": report.to_dict(),
        "outcomes": {"pipeline": inv.pipeline_verdict,
                     "criteria_completion": OUTCOME_OF_STATE[report.completion],
                     "evidence_grounded_muse": grounded.outcome if grounded else None,
                     "muse_only": only.outcome if only else None},
        "grounded_historical": bool(grounded and grounded.historical),
        "mechanisms": predicted_mechanisms(inv, report),
        "missing_evidence": missing_evidence(report),
        "criteria_citations": criteria_citations(inv, report),
        "model_citations": {m.kind: citation_check(m) for m in inv.models if m.kind == "evidence_grounded"},
        "claims": {m.kind: claim_audit(m) for m in inv.models},
    }


# --- scoring against references (evaluation only) ---------------------------------------------

def _outcome_class(pred: str | None, ref: dict[str, Any]) -> str:
    if ref.get("status") == "no_reference" or ref.get("reference_outcome") is None:
        return "no_reference"
    if ref.get("status") == "disputed":
        return "disputed"
    if pred is None:
        return "not_run"
    if pred == "uncertain":
        return "abstain"
    return "correct" if pred == ref["reference_outcome"] else "wrong"


def _mechanism_level(category: str, pred: dict[str, Any]) -> dict[str, str]:
    crit = pred["criteria"]
    pipeline = [m for m in pred["mechanisms"]["pipeline"] if m["category"] == category]
    criterion = next((a for a in crit["assessments"] if a["criterion_id"] == CATEGORY_CRITERION.get(category)), None)
    if pipeline:
        best = pipeline[0]
        level = f"candidate only ({best['status']}, verifier {best['verifier']}); physical mechanism unverified"
    elif criterion and criterion["state"] == "contradicted":
        level = "2D criterion contradicted; physical mechanism unverified"
    elif criterion and criterion["state"] == "unverified" and criterion["requirements"]:
        level = "missed (criterion unverified; abstention is not identification)"
    else:
        level = "missed"
    grounded = "hypothesis only (unverified)" if category in pred["mechanisms"]["grounded_hypothesis_categories"] else (
        "not run" if pred["outcomes"]["evidence_grounded_muse"] is None else "not mentioned")
    if pred["outcomes"]["muse_only"] is None:
        only = "not run"
    elif category in pred["mechanisms"]["muse_only_categories"]:
        only = "asserted without citations"
    else:
        only = f"missed (verdict {pred['outcomes']['muse_only']})"
    return {"demodoctor_criteria": level, "evidence_grounded_muse": grounded, "muse_only": only}


def score(preds: list[dict[str, Any]], refs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    systems = ("pipeline", "criteria_completion", "evidence_grounded_muse", "muse_only")
    rows, outcome_counts = [], {s: Counter() for s in systems}
    mech_rows, false_mechs = [], []
    for p in preds:
        ref = refs.get(p["investigation_id"], {"status": "no_reference", "reference_outcome": None})
        classes = {s: _outcome_class(p["outcomes"][s], ref) for s in systems}
        for s in systems:
            outcome_counts[s][classes[s]] += 1
        rows.append({"investigation_id": p["investigation_id"], "split": p["split"],
                     "reference_outcome": ref.get("reference_outcome"), "reference_status": ref.get("status"),
                     **{f"{s}": p["outcomes"][s] for s in systems}, "classes": classes})
        if ref.get("status") == "reference":
            for cat in ref.get("mechanisms") or []:
                mech_rows.append({"investigation_id": p["investigation_id"], "category": cat, **_mechanism_level(cat, p)})
            if ref.get("reference_outcome") == "success":
                for m in p["mechanisms"]["pipeline"]:
                    false_mechs.append({"investigation_id": p["investigation_id"], "system": "demodoctor_criteria", **m})
                for c in p["mechanisms"]["muse_only_categories"]:
                    false_mechs.append({"investigation_id": p["investigation_id"], "system": "muse_only", "category": c})
    def _pct(n: int, d: int) -> float | None:
        return round(n / d, 3) if d else None
    summary: dict[str, Any] = {}
    for s in systems:
        c = outcome_counts[s]
        scorable = c["correct"] + c["wrong"] + c["abstain"]
        summary[s] = {**dict(sorted(c.items())), "scorable": scorable,
                      "abstention_rate": _pct(c["abstain"], scorable),
                      "definitive_accuracy": _pct(c["correct"], c["correct"] + c["wrong"])}
    identified = sum(1 for r in mech_rows if r["demodoctor_criteria"].startswith("identified"))
    localized = sum(1 for r in mech_rows if r["demodoctor_criteria"].startswith("localized"))
    claims = Counter()
    for p in preds:
        for kind, a in p["claims"].items():
            claims[f"{kind}_statements"] += a["statements"]
            claims[f"{kind}_unsupported"] += len(a["unsupported"])
            claims[f"{kind}_labeled_unverified"] += a["labeled_unverified"]
            claims[f"{kind}_entailment_unverified"] += len(a["entailment_unverified"])
    cit = Counter()
    for p in preds:
        for c in p["model_citations"].values():
            cit["model_citations"] += c["evidence_citations"] + c["frame_citations"]
            cit["model_invalid"] += c["invalid"]
        cit["criteria_citations"] += p["criteria_citations"]["citations"]
        cit["criteria_invalid"] += p["criteria_citations"]["invalid"]
        cit["criteria_decisive_without_citation"] += len(p["criteria_citations"]["decisive_without_citation"])
    me = Counter()
    kinds: Counter = Counter()
    for p in preds:
        m = p["missing_evidence"]
        me["unverified_criteria"] += m["unverified_criteria"]
        me["with_requirement"] += m["with_requirement"]
        me["abstentions"] += p["outcomes"]["criteria_completion"] == "uncertain"
        me["abstentions_explained"] += p["outcomes"]["criteria_completion"] == "uncertain" and m["abstention_explained"]
        kinds.update(m["requirement_kinds"])
    return {
        "outcome_rows": rows, "outcome_summary": summary,
        "mechanism_rows": mech_rows,
        "mechanism_summary": {"reference_mechanisms": len(mech_rows), "identified": identified,
                              "localized_unverified": localized,
                              "missed": len(mech_rows) - identified - localized,
                              "false_mechanisms_on_reference_success": false_mechs},
        "claims_summary": dict(sorted(claims.items())),
        "citation_summary": dict(sorted(cit.items())),
        "missing_evidence_summary": {**dict(sorted(me.items())), "requirement_kinds": dict(sorted(kinds.items()))},
    }


def run() -> dict[str, Any]:
    preds = [predict(inv) for inv in S.load_all()]  # predictions first; references are not yet loaded
    refs = load_references()
    return {"evaluation": "diagnostic_eval_v2",
            "scope": "Six saved investigations from DIAGNOSTIC_COVERAGE_AUDIT.md; no inference re-run.",
            "references": REFERENCES_PATH.relative_to(ROOT).as_posix(),
            "predictions": preds, "scores": score(preds, refs)}


# --- report rendering --------------------------------------------------------------------------

def _md_report(result: dict[str, Any]) -> str:
    sc, preds = result["scores"], {p["investigation_id"]: p for p in result["predictions"]}
    L = ["# Diagnostic evaluation v2 — task criteria, mechanisms and missing evidence", "",
         "Generated by `python diagnostic_eval.py` from saved investigations only (no provider calls, no inference "
         "re-run). Predictions are computed before references are loaded; references are "
         f"`{result['references']}`. Six investigations is far too few for accuracy claims; read counts, not rates.", "",
         "## Reference outcome vs predictions", "",
         "| Investigation | Split | Reference | Pipeline | Criteria completion | Grounded Muse | Muse-only |",
         "|---|---|---|---|---|---|---|"]
    for r in sc["outcome_rows"]:
        ref = r["reference_outcome"] or "none"
        if r["reference_status"] == "disputed":
            ref += " (disputed)"
        cells = [f"{r[s] or '—'} · {r['classes'][s]}" for s in ("pipeline", "criteria_completion",
                                                                   "evidence_grounded_muse", "muse_only")]
        L.append(f"| {r['investigation_id']} | {r['split']} | {ref} | " + " | ".join(cells) + " |")
    L += ["", "| System | Correct | Wrong | Abstain | Scorable | Abstention rate | Definitive accuracy |",
          "|---|---|---|---|---|---|---|"]
    for s, v in sc["outcome_summary"].items():
        L.append(f"| {s} | {v.get('correct', 0)} | {v.get('wrong', 0)} | {v.get('abstain', 0)} | {v['scorable']} | "
                 f"{v['abstention_rate']} | {v['definitive_accuracy']} |")
    ms = sc["mechanism_summary"]
    L += ["", "## Failure mechanisms", "",
          f"Reference failure mechanisms: {ms['reference_mechanisms']}. DemoDoctor criteria layer: "
          f"{ms['identified']} independently identified, {ms['localized_unverified']} localized, "
          f"{ms['missed']} not independently identified. Inferred candidates and missing criteria do not count as identified mechanisms. Candidate mechanisms on reference-success episodes: "
          f"{len([m for m in ms['false_mechanisms_on_reference_success'] if m['system'] == 'demodoctor_criteria'])}.", "",
          "| Investigation | Reference mechanism | DemoDoctor criteria | Grounded Muse | Muse-only |", "|---|---|---|---|---|"]
    for r in sc["mechanism_rows"]:
        L.append(f"| {r['investigation_id']} | {r['category']} | {r['demodoctor_criteria']} | "
                 f"{r['evidence_grounded_muse']} | {r['muse_only']} |")
    cs, cit, me = sc["claims_summary"], sc["citation_summary"], sc["missing_evidence_summary"]
    L += ["", "## Claims, citations and missing evidence", "",
          f"- Grounded Muse: {cs.get('evidence_grounded_statements', 0)} statements, "
          f"{cs.get('evidence_grounded_labeled_unverified', 0)} labeled unverified (hypotheses/visual), "
          f"{cs.get('evidence_grounded_unsupported', 0)} confirmed citation/label defects; "
          f"{cs.get('evidence_grounded_entailment_unverified', 0)} cited factual statements have semantic entailment unverified by this evaluator. Zero citation defects is not proof of claim accuracy.",
          f"- Muse-only: {cs.get('muse_only_statements', 0)} statements, {cs.get('muse_only_unsupported', 0)} "
          "uncited physical assertions (it has no evidence package to cite).",
          f"- Model citations: {cit.get('model_invalid', 0)} invalid of {cit.get('model_citations', 0)} "
          "(existence against the package the model was given; existence is not entailment).",
          f"- Criteria citations: {cit.get('criteria_invalid', 0)} invalid of {cit.get('criteria_citations', 0)}; "
          f"decisive states without citation: {cit.get('criteria_decisive_without_citation', 0)}.",
          f"- Unverified criteria with at least one evidence requirement: {me.get('with_requirement', 0)}/"
          f"{me.get('unverified_criteria', 0)}. Criteria-level abstentions explained: "
          f"{me.get('abstentions_explained', 0)}/{me.get('abstentions', 0)}.",
          "- Requirement kinds: " + ", ".join(f"{k} ×{v}" for k, v in me["requirement_kinds"].items()) + ".", ""]
    unsup = [(i, k, u) for i, p in preds.items() for k, a in p["claims"].items() for u in a["unsupported"]]
    if unsup:
        L += ["### Unsupported statements", "", "| Investigation | Source | Statement | Reason |", "|---|---|---|---|"]
        L += [f"| {i} | {k} | {u['text']} | {u['reason']} |" for i, k, u in unsup]
        L.append("")
    L += ["## Per-investigation criterion reports", ""]
    for i, p in preds.items():
        c = p["criteria"]
        L += [f"### {i} ({p['split']})", "", "| Criterion | Required | State | Evidence | Basis | Would resolve |",
              "|---|---|---|---|---|---|"]
        for a in c["assessments"]:
            reqs = "; ".join(sorted({r["kind"] for r in a["requirements"]})) or "—"
            L.append(f"| {a['criterion_id']} | {'yes' if a['required'] else 'no'} | **{a['state']}** | "
                     f"{', '.join(a['evidence_ids']) or '—'} | {a['basis']} | {reqs} |")
        for m in c["mechanisms"]:
            alts = "; ".join(m["alternatives"]) or "—"
            res = "; ".join(sorted({r["kind"] for r in m["resolving_evidence"]})) or "—"
            L.append(f"\nMechanism candidate: `{m['mechanism']}` on {', '.join(m['objects'])} — status {m['status']}, "
                     f"verifier {m['verifier']}, evidence {', '.join(m['evidence_ids'])}. Alternatives: {alts}. "
                     f"Resolving evidence: {res}.")
        if c["abstention_explanation"]:
            L.append(f"\n{c['abstention_explanation']}")
        if p["grounded_historical"]:
            L.append("\nGrounded Muse output is historical and bound to the earlier package; its citations are "
                     "checked against that package only.")
        L.append("")
    L += ["## Method boundaries", "",
          "- Criteria states use only saved pipeline artifacts. Decisive predicates require typed source support matching object, frame, camera and package, not merely existing citation IDs. Missing evidence is never scored as failure.",
          "- `criteria_completion` is a new, stricter view, not a replacement of the frozen pipeline verdict. It "
          "preserves EP003's supported 2D sample while abstaining on full physical completion.",
          "- Required physical pose and expected object counts remain unspecified. Anomaly vocabulary does not define success criteria.",
          "- Keyword categories are lexical evaluation annotations only. Citation checking does not establish semantic entailment; valid-cited model prose remains separately listed as entailment_unverified in evaluation.json. No runtime prediction imports this evaluator.",
          "- EP010 is a development episode; EP003/005/006/013 are held-out; PILOT has no outcome reference. "
          "EP006 is excluded from scoring because its references conflict.", ""]
    return "\n".join(L)


def write(result: dict[str, Any], out_dir: Path = OUT_DIR) -> dict[str, str]:
    files = {"evaluation.json": json.dumps(result, indent=1, ensure_ascii=False) + "\n",
             "REPORT.md": _md_report(result)}
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare a fresh run to the committed outputs")
    args = ap.parse_args(argv)
    result = run()
    if args.check:
        fresh = {"evaluation.json": json.dumps(result, indent=1, ensure_ascii=False) + "\n",
                 "REPORT.md": _md_report(result)}
        stale = [n for n, t in fresh.items()
                 if not (OUT_DIR / n).is_file() or (OUT_DIR / n).read_text(encoding="utf-8") != t]
        print("stale: " + ", ".join(stale) if stale else "up to date")
        return 1 if stale else 0
    write(result)
    print(f"wrote {OUT_DIR.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
