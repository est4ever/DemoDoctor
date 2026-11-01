import { useEffect, useRef } from "react";
import { WebViewer } from "@rerun-io/web-viewer";
import {
  RERUN_TIMELINE,
  nanosToSeconds,
  secondsToDurationNanos,
} from "../lib/rerunEvidence";

export type RerunSeekRequest = {
  seconds: number;
  token: number;
  /** When true, parent already updated inspector; ignore time_update until settled. */
  fromReact?: boolean;
};

export type RerunLoadMetrics = {
  coldStartMs: number;
  recordingReadyMs: number;
  rrdBytes: number;
  rrdTransferMs: number;
};

type Props = {
  rrdUrl: string;
  seekRequest: RerunSeekRequest | null;
  onReady?: (metrics: RerunLoadMetrics) => void;
  onTimeSeconds?: (t: number, meta: { source: "viewer" | "seek_ack" }) => void;
  onError?: (message: string) => void;
  onSeekSettled?: (token: number, actualSeconds: number, errorMs: number) => void;
  className?: string;
};

async function waitForRecording(viewer: WebViewer, timeoutMs = 120_000) {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    const state = await viewer.get_state();
    if (state.recordings.length > 0 && state.loading.length === 0) {
      return state;
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error("Timed out waiting for Rerun recording to load");
}

async function readTimelineSeconds(viewer: WebViewer): Promise<number | null> {
  const state = await viewer.get_state();
  const rec =
    state.recordings.find((r) => r.store_id === state.active_store_id) ??
    state.recordings[0];
  if (!rec) return null;
  const cursor = rec.current_time;
  if (cursor?.time != null && cursor.timeline === RERUN_TIMELINE) {
    return nanosToSeconds(cursor.time);
  }
  const named = rec.timelines.find((t) => t.name === RERUN_TIMELINE);
  if (named?.current_time != null) {
    return nanosToSeconds(named.current_time);
  }
  if (cursor?.time != null) {
    return nanosToSeconds(cursor.time);
  }
  return null;
}

/**
 * Isolated Rerun web-viewer host. Rerun owns the only playback timeline;
 * React drives seeks via set_time and mirrors playhead via time_update.
 */
export function RerunViewerEmbed({
  rrdUrl,
  seekRequest,
  onReady,
  onTimeSeconds,
  onError,
  onSeekSettled,
  className,
}: Props) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<WebViewer | null>(null);
  const readyRef = useRef(false);
  const pendingSeekRef = useRef<{
    token: number;
    targetSeconds: number;
    fromReact: boolean;
  } | null>(null);
  const onReadyRef = useRef(onReady);
  const onTimeRef = useRef(onTimeSeconds);
  const onErrorRef = useRef(onError);
  const onSeekSettledRef = useRef(onSeekSettled);
  onReadyRef.current = onReady;
  onTimeRef.current = onTimeSeconds;
  onErrorRef.current = onError;
  onSeekSettledRef.current = onSeekSettled;

  useEffect(() => {
    const parent = parentRef.current;
    if (!parent) return;

    let cancelled = false;
    const viewer = new WebViewer();
    viewerRef.current = viewer;
    readyRef.current = false;
    const t0 = performance.now();

    const offTime = viewer.on("time_update", (event) => {
      const seconds = nanosToSeconds(event.time);
      const pending = pendingSeekRef.current;
      if (pending?.fromReact) {
        const errMs = Math.abs(seconds - pending.targetSeconds) * 1000;
        // Settle when we are within 1 frame (~33ms) of the requested time.
        if (errMs <= 40) {
          pendingSeekRef.current = null;
          onSeekSettledRef.current?.(pending.token, seconds, errMs);
          onTimeRef.current?.(seconds, { source: "seek_ack" });
        }
        // Drop intermediate echoes while a React seek is in flight.
        return;
      }
      onTimeRef.current?.(seconds, { source: "viewer" });
    });

    (async () => {
      try {
        const absoluteUrl = new URL(rrdUrl, window.location.origin).href;

        // Measure transfer with a dedicated GET (viewer uses the HTTP URL —
        // blob: URLs timed out in @rerun-io/web-viewer 0.41).
        const transferStart = performance.now();
        const resp = await fetch(absoluteUrl);
        if (!resp.ok) {
          throw new Error(`Failed to fetch ${rrdUrl}: HTTP ${resp.status}`);
        }
        const buf = await resp.arrayBuffer();
        const rrdTransferMs = performance.now() - transferStart;
        const rrdBytes = buf.byteLength;
        if (cancelled) return;

        await viewer.start(absoluteUrl, parent, {
          hide_welcome_screen: true,
          check_for_updates_on_startup: false,
          width: "100%",
          height: "100%",
          video_decoder: "prefer_software",
          theme: "light",
          memory_limit: "1GB",
        });
        if (cancelled) return;

        await waitForRecording(viewer);
        if (cancelled) return;

        try {
          await viewer.set_time({
            timeline: RERUN_TIMELINE,
            duration_nanos: secondsToDurationNanos(43.1),
            play_state: "paused",
          });
        } catch {
          // Timeline may appear one frame later.
        }

        // Usable = recording loaded AND playhead can settle on the event window.
        let usableAt = performance.now();
        for (let i = 0; i < 40; i++) {
          const actual = await readTimelineSeconds(viewer);
          if (actual != null && Math.abs(actual - 43.1) <= 0.05) {
            usableAt = performance.now();
            break;
          }
          await new Promise((r) => setTimeout(r, 50));
        }

        readyRef.current = true;
        onReadyRef.current?.({
          coldStartMs: usableAt - t0,
          recordingReadyMs: usableAt - t0,
          rrdBytes,
          rrdTransferMs,
        });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to start Rerun web viewer";
        onErrorRef.current?.(message);
      }
    })();

    return () => {
      cancelled = true;
      offTime();
      readyRef.current = false;
      viewerRef.current = null;
      pendingSeekRef.current = null;
      try {
        viewer.stop();
      } catch {
        // ignore shutdown races
      }
    };
  }, [rrdUrl]);

  useEffect(() => {
    if (!seekRequest) return;
    const viewer = viewerRef.current;
    if (!viewer || !readyRef.current) return;

    const token = seekRequest.token;
    pendingSeekRef.current = {
      token,
      targetSeconds: seekRequest.seconds,
      fromReact: Boolean(seekRequest.fromReact),
    };

    (async () => {
      try {
        await viewer.set_time({
          timeline: RERUN_TIMELINE,
          duration_nanos: secondsToDurationNanos(seekRequest.seconds),
          play_state: "paused",
        });

        // Poll get_state until cursor matches (no fixed echo-suppression sleep).
        const deadline = performance.now() + 1500;
        let actual: number | null = null;
        while (performance.now() < deadline) {
          // A newer seek superseded this one — drop without reporting.
          if (pendingSeekRef.current?.token !== token) return;
          actual = await readTimelineSeconds(viewer);
          if (
            actual != null &&
            Math.abs(actual - seekRequest.seconds) * 1000 <= 40
          ) {
            break;
          }
          await new Promise((r) => setTimeout(r, 20));
        }
        if (pendingSeekRef.current?.token !== token) return;
        const settled = actual ?? seekRequest.seconds;
        const errMs = Math.abs(settled - seekRequest.seconds) * 1000;
        pendingSeekRef.current = null;
        onSeekSettledRef.current?.(token, settled, errMs);
        onTimeRef.current?.(settled, { source: "seek_ack" });
      } catch (err) {
        if (pendingSeekRef.current?.token === token) {
          pendingSeekRef.current = null;
        }
        const message =
          err instanceof Error ? err.message : "Rerun set_time failed";
        onErrorRef.current?.(message);
      }
    })();
  }, [seekRequest]);

  return (
    <div
      ref={parentRef}
      className={className}
      style={{ position: "relative", width: "100%", height: "100%" }}
    />
  );
}
