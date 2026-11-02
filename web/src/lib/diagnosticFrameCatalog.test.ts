import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { diagnosticFrameCatalog } from "./diagnosticFrameCatalog";
import type { AnalysisBundle } from "./types";
const read = (name: string) => JSON.parse(readFileSync(name, "utf8"));
describe("Original recorded frame provenance", () => {
  it("restores only the exact original EP010 package frame references", () => {
    const a: AnalysisBundle = read("public/data/ep010/analysis.json");
    const original = read("../data/experiments/botfails_ep010_w1260_v2_muse_pilot/pilot_report.json");
    expect(a.frame_catalog).toEqual([]);
    const result = diagnosticFrameCatalog(a);
    expect(result.frames).toEqual(original.package.frame_refs);
    expect(result.source).toContain("pilot_report.json#package.frame_refs");
    expect(a.frame_catalog).toEqual([]);
  });
  it("does not invent frames or borrow another package's IDs", () => {
    const a: AnalysisBundle = read("public/data/ep010/analysis.json");
    for (const patch of [{ episode_key: "pilot" }, { video: { rel: "upload.mp4", primary_evidence: true } }, { dry_run: true }, { evidence_catalog: [] }]) {
      expect(diagnosticFrameCatalog({ ...a, ...patch }).frames).toEqual([]);
    }
    const frame = { frame_ref: "F0", frame_index: 900, timestamp_s: 30 };
    expect(diagnosticFrameCatalog({ ...a, frame_catalog: [frame] }).frames).toEqual([frame]);
  });
});
