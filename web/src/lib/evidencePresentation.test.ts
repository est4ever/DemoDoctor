import { describe, expect, it } from "vitest";
import {
  evidenceHeadline,
  evidenceStatus,
  evidenceTone,
  markerPresentation,
  findingGroups,
} from "./evidencePresentation";
import type { EvidenceItem } from "./types";

describe("Evidence presentation preserves verification context", () => {
  it("keeps the uncertainty in a long gripper limitation", () => {
    const item: EvidenceItem = Object.freeze({
      evidence_id: "E3",
      status_context: "uncertain",
      summary:
        "Gripper reading cannot show whether an object is held (In ep000 calibration details follow).",
    });
    expect(evidenceHeadline(item)).toBe(
      "Gripper reading cannot show whether an object is held",
    );
    expect(evidenceStatus(item)).toBe("uncertain");
    expect(item.summary).toContain("calibration details follow");
  });
  it("does not upgrade an inferred catalog item because its text says measured", () => {
    const item: EvidenceItem = {
      evidence_id: "E2",
      status_context: "inferred",
      summary:
        "measured gripper opened at frame 1335 (44.5s), during or just after the move",
    };
    expect(evidenceHeadline(item)).toBe(
      "Measured gripper opened during or just after the move",
    );
    expect(evidenceStatus(item)).toBe("inferred");
    expect(item.summary).toContain("1335 (44.5s)");
  });
  it("preserves uncertain qualifiers in unfamiliar evidence", () => {
    const item: EvidenceItem = {
      evidence_id: "X",
      status_context: "uncertain",
      summary: "Object may have moved; contact is not established.",
    };
    expect(evidenceHeadline(item)).toBe(item.summary);
    expect(evidenceStatus({ evidence_id: "Y" })).toBe("Unclassified");
  });
  it("does not discard a parenthetical or later sentence that limits verification", () => {
    const summary =
      "Object moved (possibly; not verified). Contact has not been established.";
    expect(evidenceHeadline({ evidence_id: "X", summary })).toBe(summary);
  });
  it("does not classify unobserved frames as observed evidence", () => {
    expect(
      evidenceTone({ evidence_id: "gap", status_context: "unobserved" }),
    ).toBe("uncertain");
    expect(
      evidenceStatus({ evidence_id: "gap", status_context: "unobserved" }),
    ).toBe("unobserved");
  });
  it("keeps uncertain events and reference frames out of inferred action labels", () => {
    const marker = {
      id: "gap",
      t: 14.4,
      label: "No observation",
      evidence_ids: [],
    };
    expect(
      markerPresentation({ ...marker, kind: "uncertain_event" }).label,
    ).toBe("Uncertain");
    expect(
      markerPresentation({ ...marker, kind: "analysis_frame" }).label,
    ).toBe("Frame");
    expect(markerPresentation({ ...marker, kind: "unrecognized" }).tone).toBe(
      "uncertain",
    );
  });
  it("respects explicit finding status without mutating records or citation IDs", () => {
    const item = Object.freeze({
      text: "Endpoint displacement only; task remains uncertain.",
      status: "observed",
      evidence_ids: ["original:Q1"],
    });
    const groups = findingGroups({ observed: [], inferred: [item] });
    expect(groups.map((g) => g.label)).toEqual(["Observed"]);
    expect(groups[0].items[0]).toBe(item);
    expect(groups[0].items[0].evidence_ids).toEqual(["original:Q1"]);
    expect(
      findingGroups({
        observed: [],
        inferred: [{ ...item, status: "uncertain" }],
      })[0].label,
    ).toBe("Uncertain");
  });
  it("preserves end-state support without relabeling it as observation or uncertainty", () => {
    const supported = Object.freeze({ text: "End-state assessment", evidence_ids: ["E4"], status: "supported_by_end_state" });
    const groups = findingGroups({ observed: [], inferred: [supported, { ...supported, status: "uncertain" }] });
    expect(groups.map(g => g.label)).toEqual(["End-state supported", "Uncertain"]);
    expect(groups[0].items[0]).toBe(supported);
    expect(groups[0].tone).toBe("inferred");
    expect(supported.status).toBe("supported_by_end_state");
  });
});
