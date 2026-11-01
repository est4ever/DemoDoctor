// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import App from "./App";

vi.mock("./components/VideoPane", () => ({ VideoPane: ({src}: {src: string}) => <output data-testid="video-src">{src}</output> }));
const viewerState = vi.hoisted(() => ({fail: false}));
vi.mock("./components/AdvancedRoboticsViewer", () => ({ default: ({onViewerError, onViewerReady}: {onViewerError?: (s: string) => void; onViewerReady?: () => void}) =>
  { if (viewerState.fail) throw new Error("Viewer module failed"); return <><button onClick={() => onViewerReady?.()}>Simulate ready</button><button data-testid="viewer-failure" onClick={() => onViewerError?.("Recording unavailable (404)")}>Simulate recording failure</button></>; } }));
const json = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const data = (name: string) => json(`../public/data/ep010/${name}.json`);
const replay = data("analysis");
const jobAnalysis = {...replay, episode_key: "audit-job", title: "Uploaded dry run", dry_run: true,
  evidence_catalog: [], initial_evidence_id: null, timeline_markers: [], task_outcome: "uncertain"};
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  sessionStorage.clear();
  viewerState.fail = false;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const body = url === "/api/budget" ? {spent_usd: 0, total_budget_usd: 10, remaining_usd: 10, per_run_budget_usd: 1}
      : url === "/api/jobs/audit-job" ? {job_id: "audit-job", status: "completed", has_analysis: true}
      : url === "/api/jobs/audit-job/analysis" ? jobAnalysis
      : url === "/api/jobs/audit-job/tracks" ? null
      : url.endsWith("analysis.json") ? replay
      : url.endsWith("joints.json") ? data("joints")
      : url.endsWith("tracks.json") ? data("tracks") : {ok: true};
    return new Response(JSON.stringify(body), {status: 200, headers: {"content-type": "application/json"}});
  }));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function load(hash: string) { history.replaceState({}, "", "/" + hash); await act(async () => root.render(<App />)); }
async function click(text: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.includes(text));
  expect(button).toBeDefined(); await act(async () => button!.click());
}

it("writes visible page routes and restores Overview and Import on a fresh mount", async () => {
  await load("#ep010"); await click("Overview"); expect(location.hash).toBe("#home");
  await act(async () => root.unmount()); root = createRoot(host); await load("#home");
  expect(host.textContent).toContain("Demonstration library");
  await click("Import footage"); expect(location.hash).toBe("#upload");
  await act(async () => root.unmount()); root = createRoot(host); await load("#upload");
  expect(host.textContent).toContain("Import & prepare");
});

it("restores a completed uploaded investigation from its URL", async () => {
  await load("#job/audit-job");
  expect(host.textContent).toContain("Uploaded dry run");
  expect(host.textContent).toContain("Dry run · SAM/Muse not executed");
  expect(host.querySelector('[data-testid="video-src"]')?.textContent).toBe("/live-data/audit-job/video.mp4");
});

it("resumes a saved upload job after the panel remounts", async () => {
  sessionStorage.setItem("demodoctor.uploadJob", "audit-job");
  vi.useFakeTimers();
  await load("#upload");
  await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
  expect(fetch).toHaveBeenCalledWith("/api/jobs/audit-job");
  expect(location.hash).toBe("#job/audit-job");
  expect(host.textContent).toContain("Uploaded dry run");
  expect(host.querySelector('[data-testid="video-src"]')?.textContent).toBe("/live-data/audit-job/video.mp4");
});

it("shows recording failures in the visible viewer shell and permits return", async () => {
  await load("#rerun-ep010");
  const fail = host.querySelector<HTMLButtonElement>('[data-testid="viewer-failure"]');
  expect(fail).not.toBeNull(); await act(async () => fail!.click());
  const alert = host.querySelector('[role="alert"]');
  expect(alert?.textContent).toContain("Recording unavailable (404)");
  expect(alert?.closest('[aria-hidden="true"]')).toBeNull();
  await click("Return to investigation");
  expect(location.hash).toBe("#ep010");
});

it("keeps post-ready viewer failures visible instead of a blank overlay", async () => {
  await load("#rerun-ep010"); await click("Simulate ready"); await click("Simulate recording failure");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Recording unavailable");
});

it("contains optional viewer module/render failures and preserves the primary investigation", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  viewerState.fail = true;
  await load("#rerun-ep010");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Viewer module failed");
  await click("Return to investigation");
  expect(host.querySelector('[data-testid="video-src"]')).not.toBeNull();
});
