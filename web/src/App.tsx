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
import { useUploadDraftStore } from "./lib/uploadDraft";
import { MultiCameraWorkspace } from "./components/MultiCameraWorkspace";
import { loadOptionalJson } from "./lib/loadOptionalJson";
import { bindCriteria } from "./lib/criteria";
import { criterionContextTime } from "./lib/criterionContext";
import { loadSavedInvestigation } from "./lib/savedInvestigations";
import { citationTime, validateCitations } from './lib/citationIntegrity';
import {markerTarget} from './lib/timelineNavigation';
import {initialPlayback,routeIntent,savePlayback} from './lib/playbackIntent';
import type { CriteriaBundle, CriterionContextFrame } from "./lib/types";
import { VideoPane, type VideoViewMode } from "./components/VideoPane";
import { Button,NavigationLink } from "./components/ui";
import { InvestigationDesk } from "./components/InvestigationDesk";
import { useSharedPlayback } from "./lib/playback";
import { RERUN_EP010_HASH, isRerunEp010Route } from "./lib/rerunEvidence";

/** Rerun Wasm + viewer — loaded only when Advanced Robotics Viewer opens. */
const AdvancedRoboticsViewer = lazy(
  () => import("./components/AdvancedRoboticsViewer"),
);
import {
  type AnalysisBundle,
  type JointsBundle,
  type TimelineMarker,
  type TracksBundle,
} from "./lib/types";

const DEFAULT_EPISODE = "ep010";
const EPISODE_OPTIONS = [
  { key: "pilot", label: "pilot — recorded video-only pilot" },
  { key: "ep010", label: "ep010 — recorded investigation" },
  {
    key: "ep005",
    label: "ep005 — recorded investigation",
  },
  { key: "ep003", label: "ep003 — recorded investigation" },
  { key: "ep013", label: "ep013 — recorded investigation" },
  { key: "ep006", label: "ep006 — recorded investigation" },
] as const;
const EPISODE_KEYS = EPISODE_OPTIONS.map((e) => e.key);

function isEpisodeKey(value: string): boolean {
  return (EPISODE_KEYS as readonly string[]).includes(value);
}

const jobFromHash = () => /^job\/([A-Za-z0-9_-]{1,128})$/.exec(routeIntent().route)?.[1] ?? null;

class ViewerErrorBoundary extends Component<{children: ReactNode; onError: (message: string) => void}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch(error: Error) { this.props.onError(error.message); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function App() {
  const uploadDraft = useUploadDraftStore();
  const [requestedJobId, setRequestedJobId] = useState(jobFromHash);
  const [rerunEp010, setRerunEp010] = useState(() =>
    isRerunEp010Route(window.location.hash),
  );
  const [episodeKey, setEpisodeKey] = useState<string>(() => {
    const hash = routeIntent().route;
    if (isRerunEp010Route(hash)) return DEFAULT_EPISODE;
    return isEpisodeKey(hash) ? hash : DEFAULT_EPISODE;
  });
  const [joints, setJoints] = useState<JointsBundle | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisBundle | null>(null);
  const [tracks, setTracks] = useState<TracksBundle | null>(null);
  const [duration, setDuration] = useState(0);
  const [routeToken,setRouteToken]=useState(window.location.hash);
  const [navigationMessage,setNavigationMessage]=useState('');
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
  const fps = joints?.fps ?? tracks?.fps ?? analysis?.multicamera?.cameras[0]?.fps ?? 30;
  const playback = useSharedPlayback(duration, fps);
  /** True once the lazy Rerun viewer reports recording ready. */
  const [advancedViewerReady, setAdvancedViewerReady] = useState(false);
  const [advancedViewerError, setAdvancedViewerError] = useState<string | null>(null);
  const advancedOverlay=useRef<HTMLDivElement>(null);
  const advancedReturnFocus=useRef<HTMLElement|null>(null);
  const advancedWasOpen=useRef(false);
  useEffect(()=>{
    if(error)document.title='Investigation unavailable · DemoDoctor';
    else if(loading)document.title='Loading investigation · DemoDoctor';
  },[error,loading]);
  useEffect(()=>{
    if(advancedViewerReady || rerunEp010&&advancedViewerError) {
      (advancedOverlay.current?.querySelector<HTMLElement>('button,a[href]')??advancedOverlay.current)?.focus({preventScroll:true});
    }
  },[advancedViewerReady,advancedViewerError,rerunEp010]);
  useEffect(()=>{
    if(rerunEp010){advancedWasOpen.current=true;return;}
    if(advancedWasOpen.current){
      (advancedReturnFocus.current??document.querySelector<HTMLElement>('[data-testid="open-advanced-robotics-viewer"]')??document.getElementById('workspace-main'))?.focus({preventScroll:true});
      advancedReturnFocus.current=null;advancedWasOpen.current=false;
    }
  },[rerunEp010]);
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
    // Route intent and React state change in the same interaction. Waiting only
    // for hashchange leaves the previous episode's sources visible for a task.
    setEpisodeKey(next);
    setRouteToken(`#${next}`);
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
      const hash = routeIntent().route;
      setRouteToken(window.location.hash);
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
    playback.setPlaying(false);
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
        validateCitations(a, !!requestedJobId);
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

  const onLiveResult = useCallback(
    (args: {
      jobId: string;
      analysis: AnalysisBundle;
      tracks: TracksBundle | null;
    }) => {
      validateCitations(args.analysis, true);
      liveModeRef.current = true;
      setLiveMode(true);
      setLiveJobId(args.jobId);
      setAnalysis(args.analysis);
      setTracks(args.tracks);
      setJoints(null);
      setVideoMode(args.tracks ? "annotated" : "original");
      setDuration(args.analysis.video.duration_s ?? args.tracks?.t_end ?? 0);
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

  const initialized=useRef<{analysis:AnalysisBundle;route:string;key:string;binding:string;target:number;settled:boolean}|null>(null);
  const latestPlayback=useRef<{analysis:AnalysisBundle;key:string;binding:string;time:number;evidence:string|null}|null>(null);
  // Exported initial_seek_s is an editorial highlight, not an explicit user seek.
  useEffect(() => {
    if (!analysis || duration<=0 || liveMode && !requestedJobId || initialized.current?.analysis===analysis && initialized.current.route===routeToken) return;
    const key=requestedJobId?`job/${requestedJobId}`:episodeKey;
    const ownRoute=routeIntent().route;
    if (ownRoute && ownRoute!==key && ownRoute!=='home' && ownRoute!=='upload') return;
    const next=initialPlayback(analysis,key,duration,!!requestedJobId,fps);
    const intent=routeIntent(),linked=analysis.evidence_catalog.find(e=>e.evidence_id===intent.evidence);
    if(initialized.current?.analysis===analysis && intent.time==null && (!linked || citationTime(analysis,linked,!!requestedJobId)==null)) next.time=playback.t;
    if(initialized.current?.analysis===analysis && !linked) next.evidenceId=activeEvidenceId??next.evidenceId;
    initialized.current={analysis,route:routeToken,key,binding:next.binding,target:next.time,settled:false};
    playback.setT(next.time,{pause:true});setActiveEvidenceId(next.evidenceId);setNavigationMessage('');
  }, [analysis,duration,routeToken,episodeKey,requestedJobId,liveMode,fps,joints,playback.setT]);
  useEffect(()=>{
    const init=initialized.current;if(!analysis || init?.analysis!==analysis)return;
    if(!init.settled && Math.abs(playback.t-init.target)>1e-6)return;init.settled=true;
    const value={analysis,key:init.key,binding:init.binding,time:playback.t,evidence:activeEvidenceId};latestPlayback.current=value;
    const timer=setTimeout(()=>savePlayback(value.key,value.binding,value.time,value.evidence),200);
    return()=>clearTimeout(timer);
  },[analysis,playback.t,activeEvidenceId]);
  useEffect(()=>()=>{const v=latestPlayback.current;if(v?.analysis===analysis)savePlayback(v.key,v.binding,v.time,v.evidence);},[analysis]);
  useEffect(()=>{const flush=()=>{const v=latestPlayback.current;if(v)savePlayback(v.key,v.binding,v.time,v.evidence);};window.addEventListener('pagehide',flush);return()=>{flush();window.removeEventListener('pagehide',flush);};},[]);

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
      const seekT = analysis && item ? citationTime(analysis,item,liveMode) : null;
      if (seekT != null) {
        playback.setT(seekT, { pause: true });
      }
      setNavigationMessage(seekT==null?'This source has no validated seek time; the video position is unchanged.':'');
    },
    [analysis, liveMode, playback],
  );

  const selectMarker = useCallback(
    (marker: TimelineMarker) => {
      if(!analysis)return;
      const target=markerTarget(analysis,marker,liveMode,duration);
      if(target.evidenceId)setActiveEvidenceId(target.evidenceId);
      if(target.time!=null)playback.setT(target.time,{pause:true});
      setNavigationMessage(target.reason);
    },
    [analysis, liveMode, playback,duration],
  );

  if (error) {
    return (
      <div className="app-shell">
        <h1 className="brand text-3xl">DemoDoctor</h1>
        <p role="alert" className="mt-3 text-[var(--warn)]">{error}</p>
        <NavigationLink className="recovery-link" href="#upload" onNavigate={() => {window.location.hash='upload';}}>Recent investigations / Import footage</NavigationLink>{" "}
        <NavigationLink className="recovery-link" href="#ep010" onNavigate={() => switchEpisode(DEFAULT_EPISODE)}>Open cached EP010 demonstration</NavigationLink>
      </div>
    );
  }

  if (loading || !analysis) {
    return (
      <div role="status" aria-live="polite" className="flex min-h-screen items-center justify-center text-[1rem] text-[var(--muted)]">
        Loading {episodeKey} demonstration…
      </div>
    );
  }

  // All hooks run above. Rerun is an overlay (not an early return) so the
  // primary investigation stays mounted while Wasm loads, and hash switches
  // never skip hooks (#rerun-ep010 ↔ #ep010 previously blanked the app).
  const openAdvancedRoboticsViewer = () => {
    advancedReturnFocus.current=document.activeElement as HTMLElement;
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
          navigationMessage={navigationMessage}
          interactionSuspended={advancedViewerReady}
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
          upload={<ImportFootage onLiveResult={onLiveResult} draftStore={uploadDraft} />}
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
          ref={advancedOverlay}
          tabIndex={-1}
          onKeyDown={event=>{
            if(!advancedViewerReady)return;
            if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeAdvancedRoboticsViewer();}
            if(event.key==='Tab'){
              const items=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter(e=>e.getClientRects().length&&!e.closest('[aria-hidden="true"]'));
              if(!items.length){event.preventDefault();event.currentTarget.focus();return;}
              const i=items.indexOf(document.activeElement as HTMLElement);
              if(event.shiftKey&&i<=0){event.preventDefault();items.at(-1)!.focus();}
              else if(!event.shiftKey&&(i===items.length-1||i<0)){event.preventDefault();items[0].focus();}
            }
          }}
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
