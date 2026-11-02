// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import App from "../App";

// Test the real App selection/clock handlers; media decoding is checked in Chromium.
vi.mock("./VideoPane", () => ({
  VideoPane: ({ t }: { t: number }) => <output data-testid="camera-time">{t}</output>,
}));
const json = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const pilot = json("../../../data/submission_demo/pilot/audit/after/analysis.json");
const pilotTracks = json("../../../data/submission_demo/pilot/job/tracks.json");
let root: Root;
let host: HTMLDivElement;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function load(episode = "pilot", missingTracks = false, computedCriteria = false) {
  window.history.replaceState({}, "", `/#${episode}`);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const requestedEpisode = /\/data\/(ep\d+)\//.exec(url)?.[1] ?? (url.includes("recorded-pilot") ? "pilot" : episode);
    const suffix = url.split("/").pop();
    let data;
    if (computedCriteria && url === `/criteria/${episode}.json`) {
      data = JSON.parse(readFileSync(resolve('public/criteria', `${episode}.json`), 'utf8'));
    } else if (requestedEpisode === "pilot") {
      if (suffix === "analysis.json") data = pilot;
      if (suffix === "tracks.json" && !missingTracks) data = pilotTracks;
    } else if (["analysis.json", "tracks.json", "joints.json"].includes(suffix!)) {
      const path = resolve("public/data", requestedEpisode, suffix!);
      if (existsSync(path)) data = JSON.parse(readFileSync(path, "utf8"));
    }
    // A nonzero initial UI clock catches accidental seeking of untimed evidence to zero.
    if (suffix === "analysis.json") data = { ...data, initial_seek_s: 12 };
    return new Response(JSON.stringify(data ?? {}), {
      status: data ? 200 : 404, headers: { "content-type": "application/json" },
    });
  }));
  await act(async () => { root.render(<App />); });
  if (!computedCriteria) expect(host.querySelector(".evidence-list"), host.textContent ?? "").not.toBeNull();
}
it('opens completed criterion assessments by default and retains expandable sources and Evidence navigation', async()=>{
  await load('ep003', false, true);
  expect(host.querySelector('#inspector-tab-Findings')?.getAttribute('aria-selected')).toBe('true');
  expect(host.querySelector<HTMLDetailsElement>('.criterion-coverage')!.open).toBe(true);
  const row=host.querySelector('[data-criterion=containment]')!;
  expect(row.textContent).toContain('Supported');
  expect(row.querySelector<HTMLDetailsElement>('details')!.open).toBe(false);
  await act(async()=>host.querySelector<HTMLButtonElement>('#inspector-tab-Evidence')!.click());
  expect(host.querySelector('.evidence-list')).not.toBeNull();
});
async function inspect(id: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>(".evidence-list button")]
    .find(b => b.querySelector(".evidence-id")?.textContent === id)!;
  await act(async () => button.click());
}
const source = () => host.querySelector<HTMLDetailsElement>(".technical-evidence details")!;
const time = () => Number(host.querySelector('[data-testid="camera-time"]')!.textContent);

describe("Inspect source interaction", () => {
  it("seeks EP010 visual references using the original package, retaining unverified interpretation status", async () => {
    await load("ep010");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect(host.querySelector(".diagnostic-hypotheses")!.textContent).toContain("pilot_report.json#package.frame_refs");
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="View diagnostic frame F1"]')!.click());
    expect(time()).toBe(44.5);
    expect(host.querySelector(".diagnostic-hypotheses article .provenance")!.textContent).toContain("Unverified");
  });
  it.each(["ep003", "ep013"])("keeps %s end-state support distinct from uncertain physical orientation", async ep => {
    await load(ep);
    expect(host.querySelector(".outcome-scope")!.textContent).toContain("physical orientation remains unverified");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect([...host.querySelectorAll(".inspector-content h3")].some(h => h.textContent === "End-state supported")).toBe(true);
    const link = [...host.querySelectorAll<HTMLButtonElement>(".claim-links button")].filter(b => b.textContent?.startsWith("E4")).at(-1)!;
    await act(async () => link.click());
    expect(source().open).toBe(true); expect(time()).toBeCloseTo(2075 / 30, 2);
    expect(source().textContent).toContain("End-of-episode plate observations");
  });
  it("identifies saved reference context without turning EP005's reference into a finding", async () => {
    await load("ep005");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Unknowns")!.click());
    expect(host.querySelector(".saved-note-context")!.textContent).toContain("curator/reference context");
    expect(host.querySelector('[data-testid="task-outcome"]')!.textContent?.toLowerCase()).toContain("uncertain");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect(host.querySelector(".inspector-content")!.textContent).not.toContain("Orientation failure is the visual ground truth");
  });
  it.each(["E0", "E1", "E2", "E3", "E4", "E5"])("opens the real PILOT %s source and preserves untimed playback", async id => {
    await load();
    expect(time()).toBe(12);
    await inspect(id);
    expect(source().open).toBe(true);
    expect(source().textContent).toContain(pilot.evidence_catalog.find((e: { evidence_id: string }) => e.evidence_id === id).summary);
    expect(time()).toBe(["E2", "E3", "E4"].includes(id) ? 12 : 0);
    if (id === "E0") expect(source().textContent).toContain("891");
    if (id === "E2") expect(source().textContent).toContain("Joint/gripper measurements unavailable");
    if (id === "E4") expect(source().textContent).toContain("empty_result");
  });
  it("reopens and focuses a selected untimed source, including after inspector scrolling", async () => {
    await load();
    await inspect("E2");
    await act(async () => { source().open = false; source().dispatchEvent(new Event("toggle")); });
    host.querySelector(".inspector-scroll")!.scrollTop = 300;
    const button = host.querySelector<HTMLButtonElement>('[aria-label="Inspect source for E2"]')!;
    await act(async () => button.click());
    expect(source().open).toBe(true);
    expect(host.querySelector(".inspector-scroll")!.scrollTop).toBe(0);
    expect(document.activeElement).toBe(source().querySelector("summary"));
    expect(time()).toBe(12);
  });
  it("shows EP010's recorded joint sample and seeks to measured gripper evidence", async () => {
    await load("ep010");
    await inspect("E2");
    expect(source().open).toBe(true);
    expect(time()).toBe(44.5);
    expect(source().textContent).toContain("10.6586");
    expect(source().textContent).toContain("main_gripper");
    expect(host.querySelector(".source-detail .provenance")!.textContent).toBe("inferred");
  });
  it("reports unavailable source artifacts instead of emitting a dead link", async () => {
    await load("pilot", true);
    await inspect("E0");
    expect(source().textContent).toContain("Source artifact unavailable");
    expect(source().querySelector("a")).toBeNull();
    expect(time()).toBe(0);
  });
  it("opens the current catalog source from a finding citation without rebinding its ID", async () => {
    await load("ep010");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    const citation = [...host.querySelectorAll<HTMLButtonElement>(".claim-links button")]
      .find(b => b.textContent?.startsWith("E2"))!;
    expect(citation).toBeDefined();
    await act(async () => citation.click());
    expect(source().open).toBe(true);
    expect(source().textContent).toContain("proprio:observation.state[gripper]");
    expect(time()).toBe(44.5);
    expect(host.querySelector("#inspector-tab-Evidence")!.getAttribute("aria-selected")).toBe("true");
  });
  it("restores EP005 hypotheses and opens untimed context without moving the video", async () => {
    await load("ep005");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect(host.querySelector(".diagnostic-hypotheses")!.textContent).toContain("incorrectly oriented flat");
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Inspect diagnostic citation E3"]')!.click());
    expect(source().open).toBe(true); expect(time()).toBe(12);
    expect(source().textContent).toContain("2D containment");
    expect(host.querySelector("#inspector-tab-Evidence")!.getAttribute("aria-selected")).toBe("true");
  });
  it("replaces hypotheses and source bindings when navigating to another investigation", async () => {
    await load("ep005");
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect(host.textContent).toContain("incorrectly oriented flat");
    await act(async () => host.querySelector<HTMLButtonElement>('.session-list [aria-label^="Open EP010 "]')!.click());
    await act(async () => host.querySelector<HTMLButtonElement>("#inspector-tab-Findings")!.click());
    expect(host.querySelector(".diagnostic-hypotheses")!.textContent).not.toContain("incorrectly oriented flat");
    expect(host.querySelector(".diagnostic-hypotheses")!.textContent).toContain("intentional release or an unintended drop");
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Inspect diagnostic citation E2"]')!.click());
    expect(source().textContent).toContain("proprio:observation.state[gripper]");
    expect(time()).toBe(44.5);
  });
});
