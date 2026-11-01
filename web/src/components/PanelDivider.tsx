import { useRef } from "react";
import type { CSSProperties } from "react";

type Props = { side: "left" | "right"; width: number; min: number; max: number;
  onResize: (width: number) => void; onReset: () => void; style?: CSSProperties };

export function PanelDivider({ side, width, min, max, onResize, onReset, style }: Props) {
  const drag = useRef<{x: number; width: number} | null>(null);
  const sign = side === "left" ? 1 : -1;
  const resize = (next: number) => onResize(Math.max(min, Math.min(max, next)));
  return <div className={`panel-divider ${side}-divider`} style={style}
    role="separator" tabIndex={0} aria-orientation="vertical"
    aria-label={`Resize ${side === "left" ? "navigation" : "evidence inspector"}`}
    aria-valuemin={min} aria-valuemax={max} aria-valuenow={width} aria-valuetext={`${Math.round(width)} pixels`}
    aria-describedby="panel-resize-help" title="Drag or use Left/Right arrows; Home/End; Enter or double-click to reset"
    onDoubleClick={onReset}
    onPointerDown={e => {
      if (e.button !== 0) return;
      e.preventDefault(); e.currentTarget.focus({preventScroll: true});
      drag.current = { x: e.clientX, width }; e.currentTarget.setPointerCapture(e.pointerId);
    }}
    onPointerMove={e => { if (drag.current) resize(drag.current.width + sign * (e.clientX - drag.current.x)); }}
    onPointerUp={e => { drag.current = null; if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); }}
    onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}
    onKeyDown={e => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End", "Enter"].includes(e.key)) return;
      e.preventDefault(); e.stopPropagation(); // Resizing must never frame-step the camera.
      if (e.key === "Enter") onReset();
      else if (e.key === "Home") resize(min);
      else if (e.key === "End") resize(max);
      else resize(width + (e.key === "ArrowRight" ? 1 : -1) * sign * (e.shiftKey ? 32 : 16));
    }} />;
}
