"""Recompute additive offline assessment files without editing recorded results."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import saved_investigations as S
from criteria_presentation import bundle


def exports() -> dict[str, str]:
    out = {}
    for inv in S.load_all():
        result = bundle(inv.task, inv.evidence)
        # Bind this presentation to the actual UI catalog, including original package scopes.
        source = ROOT / ("data/submission_demo/pilot/audit/after/analysis.json" if inv.investigation_id == "pilot"
                         else f"web/public/data/{inv.investigation_id}/analysis.json")
        catalog = json.loads(source.read_text(encoding="utf-8"))["evidence_catalog"]
        ids = {e for a in result["assessments"] for e in a["evidence_ids"]}
        ids |= {e for m in result["mechanisms"] for e in m["evidence_ids"]}
        result["catalog_binding"] = [{k: e.get(k) for k in ("evidence_id", "source", "frame_start", "frame_end", "summary")}
                                     for e in catalog if e["evidence_id"] in ids]
        if ids - {e["evidence_id"] for e in result["catalog_binding"]}:
            raise ValueError(f"{inv.investigation_id}: criterion citation absent from displayed package")
        result["source_artifacts"] = inv.sources
        out[inv.investigation_id] = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    return out


if __name__ == "__main__":
    check = "--check" in sys.argv
    directory = ROOT / "web/public/criteria"
    if not check:
        directory.mkdir(exist_ok=True)
    for key, text in exports().items():
        path = directory / f"{key}.json"
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"stale: {path.name}")
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
    print("Six criterion presentations verified" if check else "Wrote six additive criterion presentations")
