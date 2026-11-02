import { useEffect, useMemo, useRef } from "react";
import type { TimelineMarker, TracksBundle } from "../lib/types";
import { markerPresentation } from "../lib/evidencePresentation";

function rgbCss(rgb: number[] | undefined, a = 1) {
  if (!rgb || rgb.length < 3) return `rgba(0,220,255,${a})`;
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${a})`;
}

/** Map native image coords → canvas pixels under object-contain letterboxing. */
function containMapping(
  canvasW: number,
  canvasH: number,
  imgW: number,
  imgH: number,
) {
  const scale = Math.min(canvasW / imgW, canvasH / imgH);
  const drawW = imgW * scale;
  const drawH = imgH * scale;
  const ox = (canvasW - drawW) / 2;
  const oy = (canvasH - drawH) / 2;
  return {
    scale,
    ox,
    oy,
    map(x: number, y: number) {
      return { x: ox + x * scale, y: oy + y * scale };
    },
  };
}

type Props = {
  tracks: TracksBundle;
  t: number;
  fps: number;
  markers: TimelineMarker[];
  highlightObjectId: string | null;
  showTrails: boolean;
  showLabels: boolean;
  videoMode: "original" | "sam" | "annotated";
};

/**
 * Canvas overlay of observed SAM centroids/bboxes/trails.
 * Never interpolates missing frames — gaps break the trail stroke.
 */
export function AnnotatedVideoOverlay({
  tracks,
  t,
  fps,
  markers,
  highlightObjectId,
  showTrails,
  showLabels,
  videoMode,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const frameIndex = useMemo(() => Math.round(t * fps), [t, fps]);
  const inWindow =
    tracks.t_start != null &&
    tracks.t_end != null &&
    t >= tracks.t_start &&
    t <= tracks.t_end;

  const activeMarkers = useMemo(
    () => markers.filter((m) => Math.abs(m.t - t) <= 0.55),
    [markers, t],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const paint = () => {
      const rect = wrap.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width));
      const h = Math.max(1, Math.floor(rect.height));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);

      if (videoMode === "original") return;

      const [imgW, imgH] = tracks.image_size;
      const m = containMapping(w, h, imgW, imgH);

      if (!inWindow) {
        // VideoPane owns the accessible DOM notice. Do not paint a second,
        // unwrappable warning over the footage, especially in narrow views.
        return;
      }

      // Trails: stroke only consecutive observed points (frame gap === 1)
      if (showTrails) {
        for (const track of Object.values(tracks.tracks)) {
          const pts = track.points;
          if (pts.length < 2) continue;
          const hi =
            highlightObjectId == null || highlightObjectId === track.object_id;
          ctx.strokeStyle = rgbCss(track.color_rgb, hi ? 0.9 : 0.25);
          ctx.lineWidth = hi ? 2.5 : 1.25;
          ctx.lineJoin = "round";
          ctx.beginPath();
          let drawing = false;
          for (let i = 0; i < pts.length; i++) {
            const p = pts[i];
            if (p.t > t + 1e-6) break;
            const { x, y } = m.map(p.centroid[0], p.centroid[1]);
            if (i === 0) {
              ctx.moveTo(x, y);
              drawing = true;
              continue;
            }
            const prev = pts[i - 1];
            if (p.frame_index - prev.frame_index !== 1) {
              // Gap: break stroke — do not interpolate
              ctx.stroke();
              ctx.beginPath();
              ctx.moveTo(x, y);
              drawing = true;
              continue;
            }
            ctx.lineTo(x, y);
            drawing = true;
          }
          if (drawing) ctx.stroke();
        }
      }

      // Current-frame detections only (exact frame key; no neighbor fill)
      const dets = tracks.frames[String(frameIndex)] ?? [];
      for (const d of dets) {
        const color = tracks.legend.find((l) => l.object_id === d.object_id)
          ?.color_rgb ?? [0, 220, 255];
        const hi =
          highlightObjectId == null || highlightObjectId === d.object_id;
        const [x1, y1, x2, y2] = d.bbox;
        const a = m.map(x1, y1);
        const b = m.map(x2, y2);
        // Original SAM box-local RLE only. Never infer a mask from its bounding box.
        if (d.mask) {
          const [mh, mw] = d.mask.size;
          const counts = d.mask.counts;
          if (mh === Math.round(y2) - Math.round(y1) && mw === Math.round(x2) - Math.round(x1)
              && counts.every(n => Number.isInteger(n) && n >= 0) && counts.reduce((a, n) => a + n, 0) === mh * mw) {
            ctx.fillStyle = rgbCss(color, hi ? 0.3 : 0.1);
            let position = 0;
            for (let i = 0; i < counts.length; i++) {
              const end = position + counts[i];
              if (i % 2) {
                while (position < end) {
                  const row = position % mh, column = Math.floor(position / mh);
                  const length = Math.min(end - position, mh - row);
                  const p = m.map(Math.round(x1) + column, Math.round(y1) + row);
                  ctx.fillRect(p.x, p.y, m.scale, length * m.scale);
                  position += length;
                }
              }
              position = end;
            }
          }
        }
        ctx.strokeStyle = rgbCss(color, hi ? 1 : 0.35);
        ctx.lineWidth = hi ? 2.5 : 1.25;
        ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);

        const c = m.map(d.centroid[0], d.centroid[1]);
        ctx.fillStyle = rgbCss(color, hi ? 1 : 0.4);
        ctx.beginPath();
        ctx.arc(c.x, c.y, hi ? 4.5 : 3, 0, Math.PI * 2);
        ctx.fill();

        if (showLabels) {
          const label = d.object_id.replace("green plate:", "plate:");
          ctx.font = "600 12px IBM Plex Sans, sans-serif";
          const tw = ctx.measureText(label).width;
          const lx = a.x;
          const ly = Math.max(14, a.y - 6);
          ctx.fillStyle = "rgba(0,0,0,0.65)";
          ctx.fillRect(lx, ly - 13, tw + 8, 16);
          ctx.fillStyle = "#fff";
          ctx.textAlign = "left";
          ctx.fillText(label, lx + 4, ly);
        }
      }

      // Event annotation chips (observed vs inferred from marker.kind)
      let chipY = 12;
      for (const mk of activeMarkers) {
        const provenance = markerPresentation(mk);
        const label = `${provenance.label} · ${mk.label}`;
        ctx.font = "600 12px IBM Plex Sans, sans-serif";
        const tw = ctx.measureText(label).width;
        ctx.fillStyle =
          provenance.tone === "observed"
            ? "rgba(31,122,76,0.88)"
            : provenance.tone === "inferred"
              ? "rgba(184,106,28,0.9)"
              : "rgba(76,86,102,0.9)";
        ctx.fillRect(12, chipY, tw + 16, 22);
        ctx.fillStyle = "#fff";
        ctx.textAlign = "left";
        ctx.fillText(label, 20, chipY + 15);
        chipY += 28;
      }
    };

    paint();
    const ro = new ResizeObserver(paint);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [
    tracks,
    t,
    fps,
    frameIndex,
    inWindow,
    activeMarkers,
    highlightObjectId,
    showTrails,
    showLabels,
    videoMode,
  ]);

  return (
    <div ref={wrapRef} className="pointer-events-none absolute inset-0">
      <canvas ref={canvasRef} className="h-full w-full" />
    </div>
  );
}
