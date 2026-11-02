import {
  Component,
  type ReactNode,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ImportFootage } from "./components/ImportFootage";
import { MultiCameraWorkspace } from "./components/MultiCameraWorkspace";
import { loadOptionalJson } from "./lib/loadOptionalJson";
import { bindCriteria } from "./lib/criteria";
import { criterionContextTime } from "./lib/criterionContext";
import { loadSavedInvestigation } from "./lib/savedInvestigations";
import type { CriteriaBundle, CriterionContextFrame } from "./lib/types";
import { VideoPane, type VideoViewMode } from "./components/VideoPane";
import { Button } from "./components/ui";
import { InvestigationDesk } from "./components/InvestigationDesk";
import { useSharedPlayback } from "./lib/playback";
import { RERUN_EP010_HASH, isRerunEp010Route } from "./lib/rerunEvidence";

/** Rerun Wasm + viewer — loaded only when Advanced Robotics Viewer opens. */
const AdvancedRoboticsViewer = lazy(
  () => import("./components/AdvancedRoboticsViewer"),
);
import {
  getHighlight,
  type AnalysisBundle,
  type JointsBundle,
  type TimelineMarker,
  type TracksBundle,
} from "./lib/types";

const DEFAULT_EPISODE = "ep010";
const EPISODE_OPTIONS = [
  { key: "pilot", label: "pilot — recorded SO-101 endpoint evidence" },
  { key: "ep010", label: "ep010 — suspected release (dev)" },
  {
    key: "ep005",
    label: "ep005 — Muse-only false success vs evidence uncertainty",
  },
  { key: "ep003", label: "ep003 — evidence-supported success" },
  { key: "ep013", label: "ep013 — evidence-supported failure" },
  { key: "ep006", label: "ep006 — optional abstention example" },
] as const;
const EPISODE_KEYS = EPISODE_OPTIONS.map((e) => e.key);

function isEpisodeKey(value: string): boolean {
  return (EPISODE_KEYS as readonly string[]).includes(value);
}

const jobFromHash = () => /^#job\/([A-Za-z0-9_-]{1,128})$/.exec(window.location.hash)?.[1] ?? null;

class ViewerErrorBoundary extends Component<{children: ReactNode; onError: (message: string) => void}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch(error: Error) { this.props.onError(error.message); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function App() {
  const [requestedJobId, setRequestedJobId] = useState(jobFromHash);
  const [rerunEp010, setRerunEp010] = useState(() =>
    isRerunEp010Route(window.location.hash),
  );
  const [episodeKey, setEpisodeKey] = useState<string>(() => {
    const hash = window.location.hash.replace(/^#/, "");
    if (isRerunEp010Route(hash)) return DEFAULT_EPISODE;
    return isEpisodeKey(hash) ? hash : DEFAULT_EPISODE;
  });
  const [joints, setJoints] = useState<JointsBundle | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisBundle | null>(null);
  const [tracks, setTracks] = useState<TracksBundle | null>(null);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [criterionCamera, setCriterionCamera] = useState<string>();
  const [criterionFocus, setCriterionFocus] = useState(0);
  useEffect(() => {setCriterionCamera(undefined);setCriterionFocus(0);}, [analysis]);
  const [videoMode, setVideoMode] = useState<VideoViewMode>("original");
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState(false);
  const liveModeRef = useRef(false);
  const [dataEpoch, setDataEpoch] = useState(0);
  /** True once the lazy Rerun viewer reports recording ready. */
  const [advancedViewerReady, setAdvancedViewerReady] = useState(false);
  const [advancedViewerError, setAdvancedViewerError] = useState<string | null>(null);
  const handleAdvancedViewerError = useCallback((message: string) => {
    setAdvancedViewerReady(false);
    setAdvancedViewerError(message);
  }, []);

  const switchEpisode = useCallback((next: string) => {
    if (!isEpisodeKey(next)) return;
    setRequestedJobId(null);
    const returningFromUpload = liveModeRef.current;
    if (returningFromUpload) setDataEpoch((epoch) => epoch + 1);
    liveModeRef.current = false;
    setLiveMode(false);
    setLiveJobId(null);
    const desired = `#${next}`;
    if (window.location.hash !== desired) {
      // Prefer hash assignment so hashchange keeps URL and React state aligned.
      window.location.hash = next;
      return;
    }
    setEpisodeKey((prev) => (prev === next ? prev : next));
    // Same-episode return from an upload must restore its cached analysis too.
    if (!returningFromUpload) setDataEpoch((epoch) => epoch + 1);
  }, []);

  useEffect(() => {
    const syncFromHash = () => {
      const hash = window.location.hash.replace(/^#/, "");
      if (isRerunEp010Route(hash)) {
        setRerunEp010(true);
        return;
      }
      setRerunEp010(false);
      const job = jobFromHash();
      if (job) { setRequestedJobId(job); return; }
      if (!hash || hash === 'home' || hash === 'upload') {
        setRequestedJobId(null);
        if (liveModeRef.current) setDataEpoch(epoch => epoch+1);
        liveModeRef.current=false;setLiveMode(false);setLiveJobId(null);
        return;
      }
      if (!isEpisodeKey(hash)) {
        return;
      }
      setRequestedJobId(null);
      if (liveModeRef.current) setDataEpoch((epoch) => epoch + 1);
      liveModeRef.current = false;
      setLiveMode(false);
      setLiveJobId(null);
      setEpisodeKey((prev) => (prev === hash ? prev : hash));
    };
    window.addEventListener("hashchange", syncFromHash);
    syncFromHash();
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  useEffect(() => {
    if (!rerunEp010) { setAdvancedViewerReady(false); setAdvancedViewerError(null); }
  }, [rerunEp010]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setJoints(null);
    setAnalysis(null);
    setTracks(null);
    setVideoMode("original");
    setDuration(0);

    const base = requestedJobId ? `/api/jobs/${requestedJobId}`
      : episodeKey === "pilot" ? "/api/recorded-pilot" : `/data/${episodeKey}`;
    const suffix = requestedJobId ? "" : ".json";
    const source = requestedJobId ? loadSavedInvestigation(requestedJobId).then(result =>
      [null,result.analysis,result.tracks,null] as const) : Promise.all([
      requestedJobId || episodeKey === "pilot" ? Promise.resolve(null) : loadOptionalJson<JointsBundle>(`${base}/joints.json`),
      fetch(`${base}/analysis${suffix}`).then((r) => {
        if (!r.ok)
          throw new Error(
            requestedJobId ? `Uploaded investigation unavailable (${r.status}). Return to Import to recover a pending job, or open cached EP010.`
            : episodeKey === "pilot"
              ? "Recorded pilot unavailable. Start the local backend with python live_api.py, then reopen PILOT. Cached EP010 remains available without the backend."
              : `${episodeKey}/analysis.json missing — restore the tracked demonstration files.`,
          );
        return r.json() as Promise<AnalysisBundle>;
      }),
      loadOptionalJson<TracksBundle>(`${base}/tracks${suffix}`),
      requestedJobId ? Promise.resolve(null) : loadOptionalJson<CriteriaBundle>(`/criteria/${episodeKey}.json`).catch(() => null),
    ]);
    source
      .then(([j, a, tr, criteria]) => {
        if (cancelled) return;
        setJoints(j);
        setAnalysis(requestedJobId ? a : bindCriteria(a, criteria));
        if (requestedJobId) {
          liveModeRef.current = true;
          setLiveMode(true);
          setLiveJobId(requestedJobId);
        }
        if (a.video.duration_s) setDuration(a.video.duration_s);
        setTracks(tr);
        // ep010 prototype: annotated camera is the reliable primary view when tracks exist
        if (tr?.tracks && Object.keys(tr.tracks).length > 0) {
          setVideoMode("annotated");
        }
        if (j?.timestamps_s?.length) {
          setDuration(j.timestamps_s[j.timestamps_s.length - 1] ?? 0);
        }
        setLoading(false);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [episodeKey, dataEpoch, requestedJobId]);

  const fps = joints?.fps ?? tracks?.fps ?? analysis?.multicamera?.cameras[0]?.fps ?? 30;
  const playback = useSharedPlayback(duration, fps);
  const onLiveResult = useCallback(
    (args: {
      jobId: string;
      analysis: AnalysisBundle;
      tracks: TracksBundle | null;
    }) => {
      liveModeRef.current = true;
      setLiveMode(true);
      setLiveJobId(args.jobId);
      setAnalysis(args.analysis);
      setTracks(args.tracks);
      setJoints(null);
      setVideoMode(args.tracks ? "annotated" : "original");
      setDuration(args.analysis.video.duration_s ?? args.tracks?.t_end ?? 0);
      setActiveEvidenceId(
        args.analysis.initial_evidence_id ??
          args.analysis.timeline_markers[0]?.evidence_ids?.[0] ??
          args.analysis.evidence_catalog[0]?.evidence_id ??
          null,
      );
      const seek =
        args.analysis.initial_seek_s ??
        getHighlight(args.analysis)?.t_start ??
        args.analysis.timeline_markers[0]?.t ??
        0;
      playback.setT(seek, { pause: true });
      window.location.hash = `job/${args.jobId}`;
    },
    [playback.setT],
  );

  const videoSrc =
    liveMode && liveJobId
      ? `/live-data/${liveJobId}/video.mp4`
      : episodeKey === "pilot" ? "/api/recorded-pilot/video.mp4" : `/replays/${episodeKey}/video.mp4`;
  const overlaySrc =
    liveMode && liveJobId && analysis?.sam_overlay?.available
      ? `/live-data/${liveJobId}/overlay.mp4`
      : analysis?.sam_overlay?.available
        ? `/replays/${episodeKey}/overlay.mp4`
        : null;

  // Initial seek / selection when episode analysis loads
  useEffect(() => {
    if (!analysis) return;
    const seek =
      analysis.initial_seek_s ??
      getHighlight(analysis)?.t_start ??
      analysis.timeline_markers[0]?.t ??
      0;
    playback.setT(seek, { pause: true });
    setActiveEvidenceId(
      analysis.initial_evidence_id ??
        analysis.timeline_markers[0]?.evidence_ids?.[0] ??
        analysis.evidence_catalog[0]?.evidence_id ??
        null,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per episode load
  }, [analysis]);

  const activeEvidence = useMemo(() => {
    if (!analysis || !activeEvidenceId) return null;
    return (
      analysis.evidence_catalog.find(
        (e) => e.evidence_id === activeEvidenceId,
      ) ?? null
    );
  }, [analysis, activeEvidenceId]);

  /** Highlight plate track when evidence names it; never invent ids. */
  const highlightObjectId = useMemo(() => {
    if (!activeEvidence) return null;
    const claims = activeEvidence.claims ?? [];
    for (const c of claims) {
      if (
        c &&
        typeof c === "object" &&
        "track_id" in c &&
        typeof (c as { track_id?: unknown }).track_id === "string"
      ) {
        return (c as { track_id: string }).track_id;
      }
    }
    const m = activeEvidence.summary?.match(/green plate:\d+/);
    return m ? m[0] : null;
  }, [activeEvidence]);

  const selectEvidence = useCallback(
    (id: string) => {
      setCriterionCamera(undefined);
      setActiveEvidenceId(id);
      const item = analysis?.evidence_catalog.find((e) => e.evidence_id === id);
      let seekT: number | null = null;
      if (item?.t_start != null) {
        seekT = item.t_start;
      } else if (item?.frame_start != null && fps > 0) {
        seekT = item.frame_start / fps;
      }
      if (seekT != null) {
        playback.setT(seekT, { pause: true });
      }
    },
    [analysis, fps, playback],
  );

  const selectMarker = useCallback(
    (marker: TimelineMarker) => {
      playback.setT(marker.t, { pause: true });
      // Prefer evidence whose timestamp is closest to the marker (not always ids[0]).
      let best: string | null = marker.evidence_ids[0] ?? null;
      let bestDist = Number.POSITIVE_INFINITY;
      for (const eid of marker.evidence_ids) {
        const item = analysis?.evidence_catalog.find(
          (e) => e.evidence_id === eid,
        );
        if (!item) continue;
        const et =
          item.t_start ??
          (item.frame_start != null ? item.frame_start / fps : null);
        if (et == null) continue;
        const dist = Math.abs(et - marker.t);
        if (dist < bestDist) {
          bestDist = dist;
          best = eid;
        }
      }
      if (best) setActiveEvidenceId(best);
    },
    [analysis, fps, playback],
  );

  if (error) {
    return (
      <div className="app-shell">
        <h1 className="brand text-3xl">DemoDoctor</h1>
        <p role="alert" className="mt-3 text-[var(--warn)]">{error}</p>
        <Button onClick={() => {window.location.hash='upload';}}>Recent investigations / Import footage</Button>{" "}
        <Button onClick={() => switchEpisode(DEFAULT_EPISODE)}>Open cached EP010 demonstration</Button>
      </div>
    );
  }

  if (loading || !analysis) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[1rem] text-[var(--muted)]">
        Loading {episodeKey} demonstration…
      </div>
    );
  }

  // All hooks run above. Rerun is an overlay (not an early return) so the
  // primary investigation stays mounted while Wasm loads, and hash switches
  // never skip hooks (#rerun-ep010 ↔ #ep010 previously blanked the app).
  const openAdvancedRoboticsViewer = () => {
    playback.setPlaying(false);
    window.location.hash = RERUN_EP010_HASH;
  };
  const closeAdvancedRoboticsViewer = () => {
    setAdvancedViewerReady(false);
    window.location.hash = episodeKey || DEFAULT_EPISODE;
  };

  return (
    <div className="app-shell">
      <div inert={advancedViewerReady}>
        <InvestigationDesk
          analysis={analysis}
          episodeKey={episodeKey}
          episodes={EPISODE_OPTIONS}
          switchEpisode={switchEpisode}
          t={playback.t}
          duration={duration}
          fps={fps}
          playing={playback.playing}
          seek={playback.setT}
          toggle={() => playback.setPlaying((v) => !v)}
          tracks={tracks}
          joints={joints}
          activeEvidence={activeEvidence}
          selectEvidence={selectEvidence}
          selectMarker={selectMarker}
          liveMode={liveMode}
          liveJobId={liveJobId}
          originalVideoSrc={videoSrc}
          inspectCriterionFrame={(frame: CriterionContextFrame) => {
            const time = criterionContextTime(frame, analysis.multicamera);
            if (time == null) return;
            setCriterionCamera(frame.camera_id);
            setCriterionFocus(n => n+1);
            playback.setT(time, { pause: true });
          }}
          video={
            analysis.multicamera && liveJobId ? <MultiCameraWorkspace manifest={analysis.multicamera} jobId={liveJobId} t={playback.t} playing={playback.playing} activeCamera={criterionCamera ?? activeEvidence?.camera_id} cameraFocus={criterionFocus}/> : <VideoPane
              key={liveMode ? "live-" + liveJobId : episodeKey}
              src={videoSrc}
              overlaySrc={overlaySrc}
              overlay={analysis.sam_overlay}
              tracks={tracks}
              mode={videoMode}
              onModeChange={setVideoMode}
              t={playback.t}
              playing={playback.playing}
              markers={analysis.timeline_markers}
              highlightObjectId={highlightObjectId}
              fps={fps}
              onDuration={(d) => {
                if (d > 0) setDuration(d);
              }}
            />
          }
          upload={<ImportFootage onLiveResult={onLiveResult} />}
          advanced={
            episodeKey === "ep010" && !liveMode ? (
              <Button
                variant="ghost"
                onClick={openAdvancedRoboticsViewer}
                data-testid="open-advanced-robotics-viewer"
              >
                Advanced Robotics Viewer ↗
              </Button>
            ) : null
          }
        />
      </div>

      {/*
        Advanced Robotics Viewer overlay: primary investigation stays mounted
        (and visible) until Wasm reports ready, then the viewer fills the viewport.
        Closing clears the hash and unmounts the lazy chunk.
      */}
      {rerunEp010 ? (
        <div
          className={
            advancedViewerReady
              ? "fixed inset-0 z-[80] flex flex-col bg-[var(--bg)]"
              : "pointer-events-none fixed inset-0 z-[80]"
          }
          data-testid="advanced-robotics-overlay"
          role={advancedViewerReady ? "dialog" : undefined}
          aria-modal={advancedViewerReady || undefined}
          aria-label="Advanced Robotics Viewer"
        >
          {!advancedViewerReady ? (
            <div className="pointer-events-auto absolute inset-x-0 bottom-0 z-[81] border-t border-[var(--border)] bg-[var(--panel)] px-4 py-4 shadow-[0_-8px_30px_rgba(0,0,0,0.12)] md:px-6">
              <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div
                    className={`${advancedViewerError ? "hidden" : ""} mt-1 h-8 w-8 shrink-0 animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--accent)]`}
                    aria-hidden
                  />
                  <div>
                    <div
                      className="font-semibold"
                      role={advancedViewerError ? "alert" : "status"}
                      aria-live="polite"
                    >
                      {advancedViewerError ? `Advanced Robotics Viewer unavailable: ${advancedViewerError}` : "Loading Advanced Robotics Viewer…"}
                    </div>
                    <p className="mt-1 max-w-2xl text-[0.9rem] text-[var(--muted)]">
                      {advancedViewerError ? "The primary investigation remains available. Return to continue inspecting recorded evidence."
                        : "Downloading Rerun Wasm only now (not on initial page load). Camera and evidence above stay usable — return anytime."}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" onClick={closeAdvancedRoboticsViewer}>
                  Return to investigation
                </Button>
              </div>
            </div>
          ) : null}
          <div
            className={
              advancedViewerReady
                ? "min-h-0 flex-1"
                : "pointer-events-none invisible absolute h-[100dvh] w-full overflow-hidden"
            }
            aria-hidden={!advancedViewerReady}
          >
            <ViewerErrorBoundary onError={handleAdvancedViewerError}>
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center text-[var(--muted)]">
                  Preparing viewer module…
                </div>
              }
            >
              <AdvancedRoboticsViewer
                onViewerReady={() => setAdvancedViewerReady(true)}
                onViewerError={handleAdvancedViewerError}
                onClose={closeAdvancedRoboticsViewer}
              />
            </Suspense>
            </ViewerErrorBoundary>
          </div>
        </div>
      ) : null}
    </div>
  );
}
