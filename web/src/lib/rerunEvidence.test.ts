import { describe, expect, it } from "vitest";
import {
  evidenceIdAtTime,
  isRerunEp010Route,
  markerAtTime,
  nanosToSeconds,
  seekSecondsForEvidence,
  secondsToDurationNanos,
} from "./rerunEvidence";
import type { AnalysisBundle, EvidenceItem, TimelineMarker } from "./types";

const catalog: EvidenceItem[] = [
  {
    evidence_id: "E0",
    summary: "move",
    t_start: 43.1,
    t_end: 45.0,
  },
  {
    evidence_id: "E2",
    summary: "gripper",
    t_start: 44.5,
    t_end: 44.5,
  },
  {
    evidence_id: "E1",
    summary: "rest",
    t_start: 45.0,
    t_end: 46.0,
  },
];

const markers: TimelineMarker[] = [
  { id: "m0", t: 43.1, label: "E0", kind: "evidence", evidence_ids: ["E0"] },
  { id: "m2", t: 44.5, label: "E2", kind: "evidence", evidence_ids: ["E2"] },
  { id: "m1", t: 45.0, label: "E1", kind: "evidence", evidence_ids: ["E1"] },
];

const analysis = {
  evidence_catalog: catalog,
  timeline_markers: markers,
} as AnalysisBundle;

describe("rerunEvidence sync helpers", () => {
  it("recognizes the advanced viewer hash", () => {
    expect(isRerunEp010Route("rerun-ep010")).toBe(true);
    expect(isRerunEp010Route("#rerun-ep010")).toBe(true);
    expect(isRerunEp010Route("ep010")).toBe(false);
  });

  it("maps E0/E1/E2 to their frozen timestamps", () => {
    expect(seekSecondsForEvidence(analysis, "E0")).toBe(43.1);
    expect(seekSecondsForEvidence(analysis, "E2")).toBe(44.5);
    expect(seekSecondsForEvidence(analysis, "E1")).toBe(45.0);
  });

  it("picks the narrowest evidence window at a playhead time", () => {
    expect(evidenceIdAtTime(catalog, 43.1)).toBe("E0");
    expect(evidenceIdAtTime(catalog, 44.5)).toBe("E2");
    expect(evidenceIdAtTime(catalog, 45.0)).toBe("E1");
  });

  it("finds timeline markers near evidence times", () => {
    expect(markerAtTime(markers, 44.5)?.id).toBe("m2");
    expect(markerAtTime(markers, 43.100)?.id).toBe("m0");
  });

  it("round-trips duration nanos used by Rerun set_time", () => {
    const ns = secondsToDurationNanos(44.5);
    expect(nanosToSeconds(ns)).toBeCloseTo(44.5, 6);
  });
});
