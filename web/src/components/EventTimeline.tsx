import { formatTime } from "../lib/playback";
import type { HighlightInterval, TimelineMarker } from "../lib/types";
import { Badge, Button, EvidenceChip, Slider } from "./ui";

type Props = {
  t: number;
  duration: number;
  playing: boolean;
  onSeek: (t: number, opts?: { pause?: boolean }) => void;
  onToggle: () => void;
  onSelectMarker: (marker: TimelineMarker) => void;
  highlight: HighlightInterval | null;
  markers: TimelineMarker[];
  fps: number;
  frameIndex: number;
  activeEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  selectedMarkerId: string | null;
};

export function EventTimeline({
  t,
  duration,
  playing,
  onSeek,
  onToggle,
  onSelectMarker,
  highlight,
  markers,
  fps,
  frameIndex,
  activeEvidenceId,
  onSelectEvidence,
  selectedMarkerId,
}: Props) {
  const inHighlight =
    highlight != null && t >= highlight.t_start && t <= highlight.t_end;
  const leftPct =
    highlight && duration > 0 ? (highlight.t_start / duration) * 100 : 0;
  const widthPct =
    highlight && duration > 0
      ? ((highlight.t_end - highlight.t_start) / duration) * 100
      : 0;
  const playheadPct = duration > 0 ? (t / duration) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <Button variant="primary" onClick={onToggle}>
          {playing ? "Pause" : "Play"}
        </Button>
        <Button onClick={() => onSeek(Math.max(0, t - 1 / fps), { pause: true })}>
          −1f
        </Button>
        <Button onClick={() => onSeek(t + 1 / fps, { pause: true })}>+1f</Button>
        <span className="ml-1 font-mono text-[0.95rem] tabular-nums">
          {formatTime(t)}
          <span className="text-[var(--muted)]"> / {formatTime(duration || 0)}</span>
        </span>
        <span className="font-mono text-[0.85rem] text-[var(--muted)]">
          frame {frameIndex} · {fps} fps
        </span>
        {highlight ? (
          inHighlight ? (
            <Badge tone="inferred">In highlighted interval</Badge>
          ) : (
            <Badge>Outside highlighted interval</Badge>
          )
        ) : (
          <Badge tone="muted">No timed event interval</Badge>
        )}
      </div>

      <div className="relative pt-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-5 overflow-visible">
          {highlight ? (
            <div
              className="absolute top-0 h-full rounded-full bg-[var(--warn)]/40"
              style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 0.4)}%` }}
              title={highlight.label}
            />
          ) : null}
          {markers.map((m) => {
            const pct = duration > 0 ? (m.t / duration) * 100 : 0;
            const active = selectedMarkerId === m.id;
            return (
              <div
                key={m.id}
                className="absolute top-0 h-full w-1 rounded-full"
                style={{
                  left: `${pct}%`,
                  background: active ? "var(--accent)" : "#8aa0b8",
                }}
              />
            );
          })}
          <div
            className="absolute top-[-3px] h-[26px] w-0.5 bg-[var(--text)]"
            style={{ left: `${playheadPct}%` }}
          />
        </div>
        <Slider
          min={0}
          max={duration || 1}
          step={1 / Math.max(fps, 1)}
          value={Math.min(t, duration || 0)}
          onChange={(e) => onSeek(Number(e.target.value), { pause: true })}
        />
      </div>

      <div
        className={`grid gap-3 ${
          markers.length >= 4
            ? "md:grid-cols-2 xl:grid-cols-4"
            : "md:grid-cols-3"
        }`}
      >
        {markers.map((m) => {
          const active = selectedMarkerId === m.id;
          const observed = m.kind === "observed_measurement";
          return (
            <div
              key={m.id}
              className={`min-h-[7.5rem] rounded-2xl border-2 px-4 py-4 text-left transition ${
                active
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] shadow-[var(--shadow)]"
                  : observed
                    ? "border-[var(--ok)]/25 bg-[var(--ok-soft)]/40 hover:border-[var(--ok)]"
                    : "border-[var(--warn)]/30 bg-[var(--warn-soft)]/50 hover:border-[var(--warn)]"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectMarker(m)}
                className="block w-full text-left"
              >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[0.95rem] font-semibold text-[var(--accent)]">
                  {formatTime(m.t)}
                </span>
                <Badge tone={observed ? "observed" : "inferred"}>
                  {observed ? "observed" : m.kind === "analysis_frame" ? "frame" : m.kind === "uncertain_event" ? "uncertain" : "inferred"}
                </Badge>
              </div>
              <div className="mt-2 text-[1.05rem] font-semibold leading-snug">
                {m.label}
              </div>
              </button>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.evidence_ids.map((id) => (
                  <EvidenceChip
                    key={id}
                    id={id}
                    active={activeEvidenceId === id}
                    onClick={() => {
                      onSelectMarker(m);
                      onSelectEvidence(id);
                    }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[0.85rem] text-[var(--muted)]">
        {highlight
          ? `Amber band = ${highlight.label} (${highlight.t_start.toFixed(1)}s–${highlight.t_end.toFixed(2)}s). `
          : "No reconstructed timed physical-event interval for this episode. "}
        Click a card or evidence ID to seek the video, update the joint pose, and
        select supporting evidence.
      </p>
    </div>
  );
}
