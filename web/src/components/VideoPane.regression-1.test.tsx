// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { VideoPane } from "./VideoPane";

afterEach(() => vi.restoreAllMocks());
it("seeks each paused frame, nearby evidence, and the final paused playback time", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const render = async (t: number, playing = false) => {
    await act(async () => root.render(<VideoPane src="/test.mp4" mode="original"
      t={t} playing={playing} onModeChange={() => {}} onDuration={() => {}} />));
  };
  try {
    await render(1);
    const video = host.querySelector("video")!;
    expect(video.currentTime).toBe(1);
    await render(1 + 1 / 30);
    expect(video.currentTime).toBeCloseTo(1 + 1 / 30, 8);
    await render(1);
    expect(video.currentTime).toBe(1);
    await render(1.01);
    expect(video.currentTime).toBe(1.01);
    await render(1.03, true);
    expect(video.currentTime).toBe(1.01);
    await render(1.03, false);
    expect(video.currentTime).toBe(1.03);
    video.currentTime = 0;
    await act(async () => { video.dispatchEvent(new Event("loadeddata")); });
    expect(video.currentTime).toBe(1.03);
  } finally {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  }
});
