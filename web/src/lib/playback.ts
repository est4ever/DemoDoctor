import { useCallback, useEffect, useRef, useState } from "react";

/** Shared timestamp clock for video + 3D + timeline (seconds). */
export function useSharedPlayback(durationS: number, fps: number) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  const last = useRef<number | null>(null);

  const clamp = useCallback(
    (x: number) => Math.min(Math.max(0, x), Math.max(0, durationS || 0)),
    [durationS],
  );

  const seek = useCallback(
    (next: number, opts?: { pause?: boolean }) => {
      setT(clamp(next));
      if (opts?.pause) setPlaying(false);
    },
    [clamp],
  );

  useEffect(() => {
    if (!playing) {
      last.current = null;
      if (raf.current != null) cancelAnimationFrame(raf.current);
      return;
    }
    const tick = (now: number) => {
      if (last.current == null) last.current = now;
      const dt = (now - last.current) / 1000;
      last.current = now;
      setT((prev) => {
        const n = prev + dt;
        if (durationS > 0 && n >= durationS) {
          setPlaying(false);
          return durationS;
        }
        return n;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current != null) cancelAnimationFrame(raf.current);
    };
  }, [playing, durationS]);

  const frameIndex = Math.min(
    Math.max(0, Math.round(t * fps)),
    Math.max(0, Math.floor((durationS || 0) * fps)),
  );

  return { t, setT: seek, playing, setPlaying, frameIndex, fps };
}

export function formatTime(s: number) {
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${m}:${r.toFixed(2).padStart(5, "0")}`;
}
