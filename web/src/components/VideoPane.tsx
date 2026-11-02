import { useEffect, useRef, useState } from "react";
import type {
  AnalysisBundle,
  TimelineMarker,
  TracksBundle,
} from "../lib/types";
import { AnnotatedVideoOverlay } from "./AnnotatedVideoOverlay";
import { Badge, Button } from "./ui";

export type SamOverlayInfo = NonNullable<AnalysisBundle["sam_overlay"]>;
export type VideoViewMode = "original" | "sam" | "annotated";

type Props = {
  src: string;
  /** Painted SAM overlay video; same timeline as original when available. */
  overlaySrc?: string | null;
  overlay?: SamOverlayInfo | null;
  tracks?: TracksBundle | null;
  mode: VideoViewMode;
  onModeChange: (mode: VideoViewMode) => void;
  t: number;
  playing: boolean;
  onDuration: (s: number) => void;
  markers?: TimelineMarker[];
  highlightObjectId?: string | null;
  fps?: number;
};

function rgbCss(rgb: number[] | undefined) {
  if (!rgb || rgb.length < 3) return "#00dcff";
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

/** Camera footage is primary evidence; SAM overlay uses frozen cache only. */
export function VideoPane({
  src,
  overlaySrc,
  overlay,
  tracks,
  mode,
  onModeChange,
  t,
  playing,
  onDuration,
  markers = [],
  highlightObjectId = null,
  fps = 30,
}: Props) {
  const ref = useRef<HTMLVideoElement>(null);
  const [videoError, setVideoError] = useState(false);
  const [aspectRatio, setAspectRatio] = useState("4 / 3");
  const hasOverlay = Boolean(overlay?.available && overlaySrc);
  const hasSamMasks = Boolean(tracks && Object.values(tracks.frames).some(ds => ds.some(d => d.mask)));
  const hasTracks = Boolean(
    tracks?.tracks && Object.keys(tracks.tracks).length,
  );
  const useSamVideo = mode === "sam" && hasOverlay;
  const activeSrc = useSamVideo ? (overlaySrc as string) : String(src);
  useEffect(() => setVideoError(false), [activeSrc]);

  const windowMeta = tracks ?? overlay;
  const inSamWindow =
    windowMeta?.t_start != null &&
    windowMeta?.t_end != null &&
    t >= windowMeta.t_start &&
    t <= windowMeta.t_end;

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const onMeta = () => {
      onDuration(v.duration || 0);
      if (v.videoWidth && v.videoHeight)
        setAspectRatio(`${v.videoWidth} / ${v.videoHeight}`);
    };
    const onReady = () => {
      if (Number.isFinite(t) && Math.abs(v.currentTime - t) > (playing ? 0.05 : 0.000001)) {
        try {
          v.currentTime = t;
        } catch {
          /* ignore */
        }
      }
    };
    v.addEventListener("loadedmetadata", onMeta);
    v.addEventListener("loadeddata", onReady);
    if (v.readyState >= 1) onMeta();
    return () => {
      v.removeEventListener("loadedmetadata", onMeta);
      v.removeEventListener("loadeddata", onReady);
    };
  }, [onDuration, activeSrc, t, playing]);

  useEffect(() => {
    const v = ref.current;
    if (!v || !Number.isFinite(t)) return;
    // Paused evidence and frame-step seeks must resolve sub-50ms differences.
    // Keep the playback deadband to avoid continually seeking a playing video.
    if (Math.abs(v.currentTime - t) > (playing ? 0.05 : 0.000001)) {
      try {
        v.currentTime = t;
      } catch {
        /* seek before ready */
      }
    }
  }, [t, activeSrc, playing]);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    if (playing) {
      void v.play().catch(() => undefined);
    } else {
      v.pause();
    }
  }, [playing, activeSrc]);

  const badgeLabel =
    mode === "annotated"
      ? inSamWindow
        ? "Annotated · observed tracks"
        : "Annotated · outside SAM window"
      : mode === "sam" && (hasOverlay || hasSamMasks)
        ? inSamWindow
          ? hasOverlay ? "Cached SAM overlay · frozen" : "SAM masks · returned observations"
          : "No SAM masks at this time"
        : "Primary evidence · camera";

  return (
    <div className="video-pane space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[0.8rem] font-medium uppercase tracking-wide text-[var(--muted)]">
          Video view
        </span>
        <Button
          variant={mode === "original" ? "primary" : "default"}
          onClick={() => onModeChange("original")}
        >
          Original
        </Button>
        {hasOverlay || hasSamMasks ? (
          <Button
            variant={mode === "sam" ? "primary" : "default"}
            onClick={() => onModeChange("sam")}
          >
            SAM Overlay
          </Button>
        ) : null}
        {hasTracks ? (
          <Button
            variant={mode === "annotated" ? "primary" : "default"}
            onClick={() => onModeChange("annotated")}
          >
            Annotated
          </Button>
        ) : null}
        {mode !== "original" ? (
          inSamWindow ? (
            <Badge tone="observed">
              SAM window · {windowMeta?.t_start?.toFixed(1)}–
              {windowMeta?.t_end?.toFixed(1)}s
            </Badge>
          ) : (
            <Badge tone="warn">
              Outside SAM window — no cached segmentation
              {windowMeta?.t_start != null && windowMeta?.t_end != null
                ? ` (${windowMeta.t_start.toFixed(1)}–${windowMeta.t_end.toFixed(1)}s)`
                : ""}
            </Badge>
          )
        ) : null}
      </div>

      <div
        className="video-frame relative aspect-video w-full overflow-hidden rounded-xl bg-[#0d1218]"
        style={{ aspectRatio }}
      >
        <video
          aria-label={mode==='sam'?'Recorded robot footage with SAM overlay':'Recorded robot footage'}
          ref={ref}
          key={activeSrc}
          src={activeSrc}
          className="absolute inset-0 h-full w-full object-contain"
          playsInline
          preload="auto"
          muted
          controls={false}
          onError={() => setVideoError(true)}
        />
        {videoError && (
          <div
            role="alert"
            className="absolute inset-0 flex items-center justify-center bg-black/80 p-8 text-center text-sm text-white"
          >
            Footage unavailable. Restore the local video assets to inspect this
            recording.
          </div>
        )}
        {(mode === "annotated" || (mode === "sam" && hasSamMasks && !hasOverlay)) && tracks ? (
          <AnnotatedVideoOverlay
            tracks={tracks}
            t={t}
            fps={fps}
            markers={markers}
            highlightObjectId={highlightObjectId}
            showTrails={mode === "annotated"}
            showLabels={mode === "annotated"}
            videoMode={mode}
          />
        ) : null}
        <div className="pointer-events-none absolute bottom-3 right-3 rounded bg-black/65 px-3 py-1.5 text-[0.65rem] font-medium uppercase tracking-wide text-white/95">
          {badgeLabel}
        </div>
        {(mode === "sam" || mode === "annotated") && !inSamWindow ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-black/70 px-4 py-3 text-center text-[0.9rem] text-white">
            Outside the frozen SAM analysis window
            {windowMeta?.t_start != null && windowMeta?.t_end != null
              ? ` (${windowMeta.t_start.toFixed(1)}–${windowMeta.t_end.toFixed(1)}s)`
              : ""}
            . Showing original camera — no detections invented.
          </div>
        ) : null}
      </div>

      {mode === "annotated" && tracks ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3 text-[0.8rem] text-[var(--muted)]">
            <span className="font-medium uppercase tracking-wide">
              Observed tracks
            </span>
            {tracks.legend.map((item) => (
              <span
                key={item.object_id}
                className="inline-flex items-center gap-1.5"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: rgbCss(item.color_rgb) }}
                />
                {item.object_id.replace("green plate:", "plate:")}
              </span>
            ))}
          </div>
          <details className="video-provenance">
            <summary>Track provenance & limitations</summary>
            <p>{tracks.note}</p>
            <Badge tone="observed">centroids · no interpolation</Badge>{" "}
            <Badge tone="inferred">event chips · inferred when marked</Badge>
          </details>
        </div>
      ) : null}

      {mode === "sam" && hasOverlay && overlay?.legend?.length ? (
        <div className="flex flex-wrap items-center gap-3 text-[0.8rem] text-[var(--muted)]">
          <span className="font-medium uppercase tracking-wide">
            Track legend
          </span>
          {overlay.legend.map((item) => (
            <span
              key={item.object_id}
              className="inline-flex items-center gap-1.5"
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: rgbCss(item.color_rgb) }}
              />
              {item.object_id.replace("green plate:", "plate:")}
            </span>
          ))}
        </div>
      ) : null}

      {mode === "sam" && hasOverlay && overlay?.note ? (
        <details className="video-provenance">
          <summary>Overlay provenance & limitations</summary>
          <p>{overlay.note}</p>
        </details>
      ) : null}
    </div>
  );
}
