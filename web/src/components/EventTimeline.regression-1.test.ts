import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { EventTimeline } from "./EventTimeline";

// Regression: ISSUE-001 - timeline evidence buttons were nested inside marker buttons.
// Found by gstack QA on 2026-10-31.
// Report: qa-browser-artifacts/qa-report.md
describe("timeline control semantics", () => {
  it("labels uncertain events without presenting them as measurements", () => {
    const html = renderToStaticMarkup(createElement(EventTimeline, {
      t: 0, duration: 4, playing: false, fps: 30, frameIndex: 0,
      onSeek: vi.fn(), onToggle: vi.fn(), onSelectMarker: vi.fn(),
      onSelectEvidence: vi.fn(), selectedMarkerId: null, activeEvidenceId: null,
      highlight: null, markers: [{ id: "candidate", label: "Candidate", t: 0,
        kind: "uncertain_event", evidence_ids: [] }],
    }));
    expect(html).toContain(">uncertain<");
    expect(html).not.toContain(">observed<");
  });
  it("keeps the marker and evidence independently operable without nested buttons", () => {
    const html = renderToStaticMarkup(
      createElement(EventTimeline, {
        t: 44.5, duration: 70, playing: false, fps: 30, frameIndex: 1335,
        onSeek: vi.fn(), onToggle: vi.fn(), onSelectMarker: vi.fn(),
        onSelectEvidence: vi.fn(), selectedMarkerId: "release", activeEvidenceId: "E2",
        highlight: null, markers: [{ id: "release", label: "Measured opening", t: 44.5,
          kind: "observed_measurement", evidence_ids: ["E2"] }],
      }),
    );
    expect(html).toContain("Measured opening");
    expect(html).toContain("E2");
    expect(html).not.toMatch(/<button\b[^>]*>(?:(?!<\/button>)[\s\S])*<button\b/);
  });
});
