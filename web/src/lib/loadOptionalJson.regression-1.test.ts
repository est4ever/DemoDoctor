import { afterEach, describe, expect, it, vi } from "vitest";
import { loadOptionalJson } from "./loadOptionalJson";

// Regression: ISSUE-004 - Vite's HTML fallback for optional JSON broke ep005.
// Found by gstack QA on 2026-10-31. Report: qa-browser-artifacts/qa-report.md
afterEach(() => vi.unstubAllGlobals());
describe("optional episode JSON", () => {
  it.each([
    [200, "text/html", "<!doctype html><html></html>", null],
    [404, "text/plain", "Not found", null],
    [200, "application/json", '{"tracks":{}}', { tracks: {} }],
  ])("handles HTTP %s with %s", async (status, type, body, expected) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(String(body), {
      status: Number(status), headers: { "content-type": String(type) },
    })));
    expect(await loadOptionalJson("/data/ep005/tracks.json")).toEqual(expected);
  });
  it("keeps malformed real JSON visible as an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("broken", {
      headers: { "content-type": "application/json" },
    })));
    await expect(loadOptionalJson("/data/ep005/tracks.json")).rejects.toThrow();
  });
});
