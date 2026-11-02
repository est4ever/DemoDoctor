import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { EvidenceSource } from "./EvidenceSource";
import { citationTime } from '../lib/citationIntegrity';
import {markerTarget} from '../lib/timelineNavigation';
import {routeIntent} from '../lib/playbackIntent';
import {readableEvidence} from '../lib/readableEvidence';
import {investigationMode} from '../lib/investigationMode';
import {InvestigationOverview} from './InvestigationOverview';
import {CriterionCoverage} from './CriterionCoverage';
import { RecordedEvidence } from "./RecordedEvidence";
import { DiagnosticDetails } from "./DiagnosticDetails";
import type { CSSProperties, ReactNode } from "react";
import {NavigationLink} from './ui';
import { DEFAULT_PANELS, usePanelLayout } from "../lib/usePanelLayout";
import { PanelDivider } from "./PanelDivider";
import type {
  AnalysisBundle,
  EvidenceItem,
  TimelineMarker,
  TracksBundle,
  JointsBundle,
  CriterionContextFrame,
} from "../lib/types";
import { formatTime } from "../lib/playback";
import { getHighlight } from "../lib/types";
import {
  evidenceStatus,
  evidenceTone,
  markerPresentation,
  findingGroups,
} from "../lib/evidencePresentation";

type Props = {
  analysis: AnalysisBundle;
  episodeKey: string;
  episodes: readonly { key: string; label: string }[];
  switchEpisode: (key: string) => void;
  video: ReactNode;
  upload: ReactNode;
  advanced: ReactNode;
  t: number;
  duration: number;
  fps: number;
  playing: boolean;
  seek: (t: number, options?: { pause?: boolean }) => void;
  toggle: () => void;
  activeEvidence: EvidenceItem | null;
  selectEvidence: (id: string) => void;
  selectMarker: (marker: TimelineMarker) => void;
  navigationMessage?: string;
  interactionSuspended?: boolean;
  liveMode: boolean;
  liveJobId?: string | null;
  inspectCriterionFrame?: (frame: CriterionContextFrame) => void;
  originalVideoSrc?: string;
  tracks?: TracksBundle | null;
  joints?: JointsBundle | null;
};

export function InvestigationDesk(p: Props) {
  const panels = usePanelLayout();
  const navPanel = useRef<HTMLElement>(null);
  const evidencePanel = useRef<HTMLElement>(null);
  const navToggle = useRef<HTMLButtonElement>(null);
  const inspectorToggle = useRef<HTMLButtonElement>(null);
  const inspectorReopen = useRef<HTMLButtonElement>(null);
  const panelFocus = useRef<"left" | "right" | null>(null);
  const toggleNav = () => {
    panelFocus.current = "left";
    if (panels.desktop) panels.setPreferences(v => ({...v, leftCollapsed: !v.leftCollapsed}));
    else { panels.setNavDrawer(!panels.navDrawer); panels.setInspectorDrawer(false); }
  };
  const toggleInspector = () => {
    panelFocus.current = "right";
    if (panels.desktop) panels.setPreferences(v => ({...v, rightCollapsed: !v.rightCollapsed}));
    else { panels.setInspectorDrawer(!panels.inspectorDrawer); panels.setNavDrawer(false); }
  };
  useLayoutEffect(() => {
    if (panelFocus.current === "left") navToggle.current?.focus({preventScroll: true});
    if (panelFocus.current === "right") (panels.inspectorCollapsed ? inspectorReopen : inspectorToggle).current?.focus({preventScroll: true});
    if (panels.inspectorCollapsed && evidencePanel.current?.contains(document.activeElement)) inspectorReopen.current?.focus({preventScroll: true});
    panelFocus.current = null;
  }, [panels.navCollapsed, panels.inspectorCollapsed]);
  useEffect(() => {
    if (panels.desktop || (!panels.navDrawer && !panels.inspectorDrawer)) return;
    const key = (e: KeyboardEvent) => {
      const root = panels.navDrawer ? navPanel.current : evidencePanel.current;
      if (e.key === "Escape") {
        e.preventDefault(); panelFocus.current = panels.navDrawer ? "left" : "right";
        panels.setNavDrawer(false); panels.setInspectorDrawer(false);
      }
      if (e.key === "Tab" && root) {
        const items = [...root.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex="0"]')]
          .filter(el => el.tabIndex>=0 && !el.closest('[inert]') && el.getClientRects().length && getComputedStyle(el).visibility !== "hidden");
        const index = items.indexOf(document.activeElement as HTMLElement);
        if (items.length && ((e.shiftKey && index <= 0) || (!e.shiftKey && (index < 0 || index === items.length - 1)))) {
          e.preventDefault(); items[e.shiftKey ? items.length - 1 : 0].focus({preventScroll: true});
        }
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [panels.desktop, panels.navDrawer, panels.inspectorDrawer]);
  const pageFromHash = () => !window.location.hash || window.location.hash === "#home" ? "home"
    : window.location.hash === "#upload" ? "upload" : "desk";
  const [page, setPage] = useState<"home" | "desk" | "upload">(pageFromHash);
  useEffect(() => {
    const sync = () => setPage(pageFromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const [tab, setTab] = useState("Findings");
  const [technicalOpen,setTechnicalOpen]=useState(false);
  useEffect(() => {
    setTab("Findings");
    setTechnicalOpen(false);
  }, [p.analysis]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const a = p.analysis;
  const mode=investigationMode(a,p.liveMode);
  const originalRecord=useMemo(()=>JSON.stringify(a,null,2),[a]);
  const displayKey = p.liveMode ? a.episode_key : p.episodeKey;
  useEffect(()=>{document.title=`${page==='home'?'Overview':page==='upload'?'Import footage':p.liveMode?'Saved investigation':displayKey.toUpperCase()+' investigation'} · DemoDoctor`;},[page,displayKey,p.liveMode]);
  const highlight = getHighlight(a);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        page !== "desk" || p.interactionSuspended ||
        target.closest('input,textarea,select,button,a,summary,[role="separator"],[role="tab"]') ||
        target.isContentEditable
      )
        return;
      if (e.code === "Space") {
        e.preventDefault();
        p.toggle();
      }
      if (e.code === "ArrowRight" || e.code === "ArrowLeft") {
        e.preventDefault();
        p.seek(p.t + (e.code === "ArrowRight" ? 1 : -1) / p.fps, {
          pause: true,
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [page, p]);
  const navigate = (next: "home" | "desk" | "upload") => {
    panels.setNavDrawer(false); panels.setInspectorDrawer(false);
    p.seek(p.t, { pause: true });
    setPage(next);
    window.location.hash = next === "home" ? "home" : next === "upload" ? "upload"
      : p.liveMode && p.liveJobId ? `job/${p.liveJobId}` : p.episodeKey;
  };
  const open = (key: string) => {
    panels.setNavDrawer(false); panels.setInspectorDrawer(false);
    p.seek(p.t, { pause: true });
    p.switchEpisode(key);
    setPage("desk");
    setTab("Findings");
    setQuery("");
    setFilter("All");
  };
  const status = evidenceStatus;
  const evidence = a.evidence_catalog.filter(
    (e) =>
      `${e.evidence_id} ${e.summary} ${e.source}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()) &&
      (filter === "All" || status(e).toLowerCase() === filter.toLowerCase()),
  );
  const active = p.activeEvidence;
  const activeTime = active ? citationTime(a,active,p.liveMode) : null;
  const [sourceOpen, setSourceOpen] = useState(false);
  const [inspection, setInspection] = useState(0);
  const linkedEvidence=routeIntent().evidence;
  useEffect(()=>{
    if(linkedEvidence && active?.evidence_id===linkedEvidence){setTab('Evidence');setSourceOpen(true);}
  },[a,linkedEvidence,active?.evidence_id]);
  const sourceSummary = useRef<HTMLElement>(null);
  const inspectorScroll = useRef<HTMLDivElement>(null);
  const inspectEvidence = (id: string) => {
    p.selectEvidence(id); // Existing App handler seeks only when a time/frame exists.
    setSourceOpen(true);
    setInspection(n => n + 1); // Re-open/reveal even when selecting the same ID again.
  };
  const openMarker=(m:TimelineMarker)=>{p.selectMarker(m);setTab('Evidence');};
  useLayoutEffect(() => {
    if (!inspection) return;
    sourceSummary.current?.focus({ preventScroll: true });
    if (inspectorScroll.current) inspectorScroll.current.scrollTop = 0;
  }, [inspection]);
  return (
    <div className={`workstation adjustable-panels ${panels.desktop ? "panels-desktop" : "panels-narrow"} ${panels.navCollapsed ? "nav-collapsed" : ""}`}
      style={{"--nav-width": `${panels.navCollapsed ? panels.leftOffset : panels.leftWidth}px`, "--nav-offset": `${panels.leftOffset}px`,
        "--inspector-width": `${panels.rightWidth}px`, "--inspector-column": `${panels.inspectorCollapsed ? 44 : panels.rightWidth}px`} as CSSProperties}>
      <a className="skip-link" href="#workspace-main" onClick={event=>{event.preventDefault();document.getElementById('workspace-main')?.focus();}}>Skip to main content</a>
      <span id="panel-resize-help" className="sr-only">Use Left and Right arrows to resize, Home or End for limits, Enter or double-click to reset.</span>
      {!panels.desktop && (panels.navDrawer || panels.inspectorDrawer) && <button className="panel-backdrop" tabIndex={-1} aria-label="Close side panel" onClick={() => {
        panelFocus.current = panels.navDrawer ? "left" : "right"; panels.setNavDrawer(false); panels.setInspectorDrawer(false);
      }} />}
      <aside id="workspace-navigation" ref={navPanel} className="rail" inert={!panels.desktop && panels.inspectorDrawer} aria-hidden={!panels.desktop && panels.inspectorDrawer || undefined} role={!panels.desktop && panels.navDrawer ? "dialog" : undefined}
        aria-modal={!panels.desktop && panels.navDrawer || undefined} aria-label="Workspace navigation">
        <div className="panel-actions nav-panel-actions">
          {!panels.navCollapsed && <button className="panel-button" aria-label="Reset navigation width" title="Reset navigation width" onClick={() => panels.setPreferences(v => ({...v, leftWidth: DEFAULT_PANELS.leftWidth}))}>↺</button>}
          <button ref={navToggle} className="panel-button" aria-controls="workspace-navigation" aria-expanded={!panels.navCollapsed}
            aria-label={panels.navCollapsed ? "Expand navigation" : "Collapse navigation"} title={panels.navCollapsed ? "Expand navigation" : "Collapse navigation"} onClick={toggleNav}>{panels.navCollapsed ? "›" : "‹"}</button>
        </div>
        <NavigationLink href="#home"
          className="wordmark"
          onNavigate={() => navigate("home")}
          aria-label="DemoDoctor home"
        >
          <span className="logo-mark">
            d<span>°</span>
          </span>
          <span className="nav-copy">
            DemoDoctor<small>ROBOTICS INVESTIGATION</small>
          </span>
        </NavigationLink>
        <div className="rail-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavigationLink href="#home" aria-current={page==='home'?'page':undefined}
            aria-label="Overview" title="Overview"
            className={page === "home" ? "nav-active" : ""}
            onNavigate={() => navigate("home")}
          >
            <span aria-hidden="true">⌂</span><span className="nav-copy">Overview</span> <kbd>01</kbd>
          </NavigationLink>
          <NavigationLink href={p.liveMode&&p.liveJobId?`#job/${p.liveJobId}`:`#${p.episodeKey}`} aria-current={page==='desk'?'page':undefined}
            aria-label="Investigation" title="Investigation"
            className={page === "desk" ? "nav-active" : ""}
            onNavigate={() => navigate("desk")}
          >
            <span aria-hidden="true">⌖</span><span className="nav-copy">Investigation</span> <kbd>02</kbd>
          </NavigationLink>
          <NavigationLink href="#upload" aria-current={page==='upload'?'page':undefined}
            aria-label="Import footage" title="Import footage"
            className={page === "upload" ? "nav-active" : ""}
            onNavigate={() => navigate("upload")}
          >
            <span aria-hidden="true">↥</span><span className="nav-copy">Import footage</span> <kbd>03</kbd>
          </NavigationLink>
        </nav>
        <div className="rail-label session-heading">
          DEMONSTRATIONS <span>{p.episodes.length}</span>
        </div>
        <div className="session-list">
          {p.episodes.map((ep) => (
            <NavigationLink href={`#${ep.key}`}
              key={ep.key}
              aria-label={`Open ${ep.key.toUpperCase()} ${ep.label}`} title={ep.label}
              aria-current={page === "desk" && !p.liveMode && ep.key === p.episodeKey ? "page" : undefined}
              className={
                page === "desk" && !p.liveMode && ep.key === p.episodeKey
                  ? "session-active"
                  : ""
              }
              onNavigate={() => open(ep.key)}
            >
              <span className="session-dot" />
              <span className="episode-glyph" aria-hidden="true">{ep.key === "pilot" ? "P" : ep.key.slice(-2)}</span>
              <span className="nav-copy">
                {ep.key.toUpperCase()}
                <small>
                  {ep.key==='pilot'?'Recorded video-only pilot':'Recorded investigation'}
                </small>
              </span>
              <span className="session-arrow">↗</span>
            </NavigationLink>
          ))}
        </div>
        <div className="rail-bottom">
          <span className="status-dot" /> Local workspace
          <small>Cached demos replay offline · Uploads require confirmation</small>
          <div className="rail-version">
            LOCAL PROTOTYPE <span>v0.1</span>
          </div>
        </div>
      </aside>
      {panels.desktop && !panels.navCollapsed && <PanelDivider side="left" width={panels.leftWidth} min={180} max={panels.leftMax}
        onResize={width => panels.setPreferences(v => ({...v, leftWidth: width}))}
        onReset={() => panels.setPreferences(v => ({...v, leftWidth: DEFAULT_PANELS.leftWidth}))}
        style={{left: `calc(${panels.leftWidth}px - 12px)`}} />}
      <main id="workspace-main" tabIndex={-1} className="desk-main" inert={!panels.desktop && panels.navDrawer}>
        <header className="topbar" inert={!panels.desktop && panels.inspectorDrawer}>
          <div>
            <span className="breadcrumb">Workspace</span>
            <span className="slash">/</span>
            {page === "home"
              ? "Overview"
              : page === "upload"
                ? "Import footage"
                : "Investigation"}
            {page === "desk" && (
              <>
                <span className="slash">/</span>
                <span className="mono">{displayKey.toUpperCase()}</span>
              </>
            )}
          </div>
          <div className="topbar-panel-actions"><button className="panel-button" onClick={panels.reset} aria-label="Reset panel layout" title="Restore default widths and expanded desktop panels">Reset layout</button><span className="local-tag">
            <span className="status-dot" />{" "}
            {page === "upload" ? "Import · explicit approval" : mode.label}
          </span>
          </div>
        </header>
        {page === "home" ? (
          <div className="overview">
            <div className="eyebrow">
              <span className="lime-line" /> FROM MOTION TO UNDERSTANDING
            </div>
            <div className="home-heading">
              <h1>
                Every motion.
                <br />
                <span>A closer look.</span>
              </h1>
              <p>
                Diagnose robot manipulation failures from video and SAM evidence.
                <br />
                Muse explains what verified observations support.
                <br />
                Know what remains uncertain.
              </p>
            </div>
            <div className="hero-case">
              <div className="hero-image">
                <video
                  src="/replays/ep010/video.mp4#t=43.1"
                  muted
                  playsInline
                  preload="metadata"
                  onLoadedMetadata={(e) => {
                    e.currentTarget.currentTime = 43.1;
                  }}
                />
                <div className="image-grid" />
                <span className="camera-label">
                  CAM 01 / REAL ROBOT FOOTAGE
                </span>
                <span className="image-caption">
                  SO-100 <span>43.10s</span>
                </span>
              </div>
              <div className="hero-copy">
                <div className="eyebrow">
                  FEATURED INVESTIGATION <span className="mono">EP010</span>
                </div>
                <span className="provenance uncertain">Uncertain outcome</span>
                <h2>
                  What happened <br />
                  to the green plate?
                </h2>
                <p>
                  Inspect the suspected release, compare SAM tracks with the
                  original footage, and trace each claim to its source.
                </p>
                <NavigationLink href="#ep010" className="lime-button" onNavigate={() => open("ep010")}>
                  Open investigation <span>↗</span>
                </NavigationLink>
                <small>Development episode · Frozen analysis</small>
              </div>
            </div>
            <div className="section-line">
              <h2>Demonstration library</h2>
              <span>{p.episodes.length} RECORDED DEMONSTRATIONS</span>
            </div>
            <div className="episode-grid">
              {p.episodes.map((ep, i) => (
                <NavigationLink href={`#${ep.key}`}
                  className="episode-card"
                  key={ep.key}
                  onNavigate={() => open(ep.key)}
                >
                  <div className="episode-thumbnail">
                    <video
                      src={ep.key === "pilot" ? "/api/recorded-pilot/video.mp4#t=1" : `/replays/${ep.key}/video.mp4#t=1`}
                      muted
                      playsInline
                      preload="metadata"
                      onLoadedMetadata={(e) => {
                        e.currentTarget.currentTime = 1;
                      }}
                    />
                    <span>{String(i + 1).padStart(2, "0")}</span>
                  </div>
                  <div className="episode-card-title">
                    {ep.key.toUpperCase()} <span>↗</span>
                  </div>
                  <p>{ep.label.split("—")[1]?.trim()}</p>
                  <small>OPEN CACHED REPLAY</small>
                </NavigationLink>
              ))}
            </div>
            <div className="home-note">
              <span>↥</span>
              <div>
                <strong>Bring your own demonstration</strong>
                <p>
                  Preview a local video and prepare an analysis with a clear
                  view of each processing stage.
                </p>
              </div>
              <NavigationLink href="#upload" onNavigate={() => navigate("upload")}>
                Import footage ↗
              </NavigationLink>
            </div>
          </div>
        ) : page === "upload" ? (
          <div className="upload-page">
            <div className="eyebrow">NEW INVESTIGATION</div>
            <h1>Start with the footage.</h1>
            <p className="page-subtitle">
              Import a robot demonstration. Keep the original video at the
              center of the investigation.
            </p>
            {p.upload}
          </div>
        ) : (
          <div className="investigation-page">
            <div className="investigation-heading" inert={!panels.desktop && panels.inspectorDrawer}>
              <div>
                <div className="eyebrow">
                  {displayKey.toUpperCase()} <span>/</span>{" "}
                  {a.split.toUpperCase()}
                </div>
                <h1>{p.liveMode ? 'Uploaded task investigation' : `${p.episodeKey.toUpperCase()} investigation`}</h1>
                <p>{a.task}</p>
              </div>
              <div className="heading-actions">
                {p.advanced}
                <span
                  className={`provenance outcome-badge ${a.task_outcome === "success" ? "outcome-success" : a.task_outcome === "failure" ? "outcome-failure" : "uncertain"}`}
                  data-testid="task-outcome"
                >
                  Outcome: {a.task_outcome}
                </span>
                {a.inferred.some(item => item.status === "supported_by_end_state") && <p className="outcome-scope">Recorded 2D end-state criterion; physical orientation remains unverified.</p>}
              </div>
            </div>
            <div className="investigation-grid">
              <div className="camera-column" inert={!panels.desktop && panels.inspectorDrawer}>
                <section className="camera-stage">
                  <div className="stage-heading">
                    <span>
                      <span className="status-dot" /> {a.multicamera ? `${a.multicamera.cameras.length} CAMERA VIEW${a.multicamera.cameras.length===1?"":"S"}` : "CAMERA 01"}{" "}
                      <span className="muted">/ {a.multicamera?"CAMERA-LOCAL EVIDENCE":"PRIMARY EVIDENCE"}</span>
                    </span>
                    <span className="mono">{p.fps} FPS</span>
                  </div>
                  {p.video}
                </section>
                <section
                  className="unified-timeline"
                  aria-label="Synchronized timeline"
                >
                  <div className="timeline-toolbar">
                    <div>
                      <button
                        className="play-button"
                        onClick={p.toggle}
                        aria-label={p.playing ? "Pause" : "Play"}
                      >
                        {p.playing ? "Ⅱ" : "▶"}
                      </button>
                      <button
                        onClick={() => p.seek(p.t - 1 / p.fps, { pause: true })}
                        aria-label="Previous frame"
                      >
                        ‹
                      </button>
                      <button
                        onClick={() => p.seek(p.t + 1 / p.fps, { pause: true })}
                        aria-label="Next frame"
                      >
                        ›
                      </button>
                      <span className="time-readout">
                        {formatTime(p.t)}{" "}
                        <span>/ {formatTime(p.duration)}</span>
                      </span>
                    </div>
                    <span className="mono muted">
                      F{" "}
                      {Math.round(p.t * p.fps)
                        .toString()
                        .padStart(4, "0")}
                    </span>
                  </div>
                  <div className="timeline-ruler">
                    {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                      <span key={v}>{formatTime(p.duration * v)}</span>
                    ))}
                  </div>
                  <div className="timeline-track">
                    {a.recorded_evidence?.provenance.observation_coverage?.missing_ranges.map(gap => (
                      <span key={gap.frame_start} aria-label={`Unobserved frames ${gap.frame_start}–${gap.frame_end - 1}`} style={{ position: "absolute", height: "100%", background: "repeating-linear-gradient(135deg, #969ba444 0 4px, transparent 4px 8px)", left: `${gap.frame_start / p.fps / p.duration * 100}%`, width: `${(gap.frame_end - gap.frame_start) / p.fps / p.duration * 100}%` }} />
                    ))}
                    {highlight && p.duration > 0 && (
                      <span
                        className="highlight-band"
                        style={{
                          left: `${(highlight.t_start / p.duration) * 100}%`,
                          width: `${Math.max(0.5, ((highlight.t_end - highlight.t_start) / p.duration) * 100)}%`,
                        }}
                        title={highlight.label}
                      />
                    )}
                    {a.timeline_markers.map((m, index) => {
                      const target=markerTarget(a,m,p.liveMode,p.duration);
                      return (
                      <button
                        key={m.id}
                        title={target.time==null?`${m.label} · no validated seek timestamp`:`${m.label} · ${target.time}s · ${m.kind}`}
                        aria-label={`${target.time==null?'Inspect':'Seek to'} ${m.label}${target.time==null?' · no camera seek':''}`}
                        style={{
                          left: `${Math.min(98,Math.max(2,p.duration && Number.isFinite(m.t)?(m.t/p.duration)*100:0))}%`,
                          '--marker-lane': index % 3,
                        } as CSSProperties}
                        onClick={() => openMarker(m)}
                        className={`timeline-marker ${markerPresentation(m).tone}`}
                        aria-pressed={target.time!=null && Math.abs(p.t-target.time)<.5/p.fps}
                      >
                        {index + 1}
                      </button>
                    );})}
                    <span
                      className="playhead"
                      style={{
                        left: `${p.duration ? (p.t / p.duration) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <input
                    aria-label="Timeline position"
                    aria-valuetext={`${formatTime(p.t)} of ${formatTime(p.duration)}`}
                    type="range"
                    min="0"
                    max={p.duration || 1}
                    step={1 / p.fps}
                    value={Math.min(p.t, p.duration)}
                    onChange={(e) =>
                      p.seek(Number(e.target.value), { pause: true })
                    }
                  />
                  <div className="timeline-footer">
                    <span>ONE CLOCK · CAMERA + OVERLAYS + EVIDENCE</span>
                    <span>Space to play · ← → frame</span>
                  </div>
                  {p.navigationMessage && <p className="navigation-message" role="status">{p.navigationMessage}</p>}
                </section>
              </div>
              <div className={`inspector-shell ${panels.inspectorCollapsed ? "is-collapsed" : ""}`}>
              {panels.inspectorCollapsed && <button ref={inspectorReopen} className="inspector-reopen panel-button" aria-label="Expand evidence inspector" title="Expand evidence inspector"
                aria-controls="evidence-inspector" aria-expanded={false} onClick={toggleInspector}>‹ <span>Evidence</span></button>}
              {panels.desktop && !panels.inspectorCollapsed && <PanelDivider side="right" width={panels.rightWidth} min={320} max={panels.rightMax}
                onResize={width => panels.setPreferences(v => ({...v, rightWidth: width}))}
                onReset={() => panels.setPreferences(v => ({...v, rightWidth: DEFAULT_PANELS.rightWidth}))} />}
              <aside id="evidence-inspector" ref={evidencePanel} className="inspector" inert={panels.inspectorCollapsed} aria-hidden={panels.inspectorCollapsed || undefined}
                role={!panels.desktop && !panels.inspectorCollapsed ? "dialog" : undefined} aria-modal={!panels.desktop && !panels.inspectorCollapsed || undefined} aria-label="Evidence inspector">
                <div className="inspector-heading">
                  <h2>Evidence inspector</h2>
                  <span className="mono">
                    {a.evidence_catalog.length.toString().padStart(2, "0")}
                  </span>
                  <div className="panel-actions">
                    <button className="panel-button" aria-label="Reset evidence inspector width" title="Reset inspector width" onClick={() => panels.setPreferences(v => ({...v, rightWidth: DEFAULT_PANELS.rightWidth}))}>↺</button>
                    <button ref={inspectorToggle} className="panel-button" aria-label="Collapse evidence inspector" title="Collapse evidence inspector" aria-controls="evidence-inspector" aria-expanded={true} onClick={toggleInspector}>›</button>
                  </div>
                </div>
                <div
                  className="inspector-tabs"
                  role="tablist"
                  aria-label="Inspector"
                >
                  {["Evidence", "Findings", "Unknowns"].map((t) => (
                    <button
                      key={t}
                      role="tab"
                      id={`inspector-tab-${t}`}
                      aria-controls="inspector-panel"
                      tabIndex={tab === t ? 0 : -1}
                      onKeyDown={(e) => {
                        const tabs = ["Evidence", "Findings", "Unknowns"];
                        const next = e.key === "Home" ? 0 : e.key === "End" ? 2
                          : e.key === "ArrowRight" ? (tabs.indexOf(t) + 1) % 3
                          : e.key === "ArrowLeft" ? (tabs.indexOf(t) + 2) % 3 : -1;
                        if (next < 0) return;
                        e.preventDefault();
                        setTab(tabs[next]);
                        document.getElementById(`inspector-tab-${tabs[next]}`)?.focus({ preventScroll: true });
                      }}
                      aria-selected={tab === t}
                      className={tab === t ? "tab-active" : ""}
                      onClick={() => setTab(t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                {active && tab==='Evidence' && (
                  <section
                    className="source-detail"
                    aria-label="Selected evidence"
                  >
                    <div className="selected-evidence-heading">
                      <span className="eyebrow">
                        SELECTED EVIDENCE <span className="evidence-id">{active.evidence_id}</span>
                      </span>
                      <span className={`provenance ${evidenceTone(active)}`}>
                        {status(active)}
                      </span>
                    </div>
                    <h3>{readableEvidence(active)}</h3>
                    <button className="inspect-source-button" aria-label={`Inspect source for ${active.evidence_id}`} aria-controls="evidence-source-details" aria-expanded={sourceOpen} onClick={() => inspectEvidence(active.evidence_id)}>Inspect source ↗</button>
                    {activeTime != null ? (
                      <button
                        className="evidence-seek"
                        onClick={() => p.selectEvidence(active.evidence_id)}
                        aria-label={`Seek to selected evidence at ${activeTime.toFixed(2)} seconds`}
                      >
                        {formatTime(activeTime)} <span>Seek camera ↗</span>
                      </button>
                    ) : (
                      <p className="untimed-evidence">
                        {active.t_start!=null || active.frame_start!=null ? 'No validated seek within the shared video window' : 'Untimed evidence · no camera seek'}
                      </p>
                    )}
                  </section>
                )}
                <div
                  ref={inspectorScroll}
                  className="inspector-scroll"
                  role="tabpanel"
                  id="inspector-panel"
                  aria-labelledby={`inspector-tab-${tab}`}
                  tabIndex={0}
                >
                  <section className="execution-context" aria-label="Analysis mode">
                    <strong>{mode.label}</strong><p>{mode.note}</p>
                    {(a.multicamera?.cameras.length??0)>1 && <p>Multi-camera workflow · Experimental. Software integration is mock-tested; genuine multi-camera action verification is not established.</p>}
                  </section>
                  {active && tab==='Evidence' && (
                    <div className="technical-evidence">
                      <details id="evidence-source-details" open={sourceOpen} onToggle={e => setSourceOpen(e.currentTarget.open)}>
                        <summary ref={sourceSummary}>Source & technical evidence · {active.evidence_id}</summary>
                        <EvidenceSource item={active} analysis={a} tracks={p.tracks} joints={p.joints} fps={p.fps} seek={p.seek} jobId={p.liveMode ? p.liveJobId : null} />
                      </details>
                    </div>
                  )}
                  {tab==='Evidence' && <details className="investigation-summary">
                    <summary>Investigation summary</summary>
                    <h3>{a.diagnosis_headline}</h3>
                    <p>{a.diagnosis_summary}</p>
                    <RecordedEvidence analysis={a} tracks={p.tracks} fps={p.fps} seek={p.seek} />
                    <p className="summary-disclaimer">{a.disclaimer}</p>
                  </details>}
                  {tab === "Evidence" ? (
                    <>
                      <details className="timeline-index">
                        <summary>Timeline event index</summary>
                        <div className="timeline-events" aria-label="Timeline events">
                          {a.timeline_markers.map((m, index) => (
                            <button
                              key={m.id}
                              onClick={() => openMarker(m)}
                              aria-pressed={markerTarget(a,m,p.liveMode,p.duration).time!=null && Math.abs(p.t-m.t)<.5/p.fps}
                            >
                              <span className="mono">
                                <b>{index + 1}</b> {markerTarget(a,m,p.liveMode,p.duration).time!=null?`${m.t.toFixed(2)}s`:'No seek time'}
                              </span>
                              <span className="event-label">{m.label}</span>
                              <span
                                className={`provenance ${markerPresentation(m).tone}`}
                              >
                                {markerPresentation(m).label}
                              </span>
                            </button>
                          ))}
                        </div>
                      </details>
                      <label className="evidence-search">
                        <span>⌕</span>
                        <input
                          aria-label="Search evidence"
                          placeholder="Find evidence or source…"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </label>
                      <div className="filter-row">
                        {["All", "Observed", "Inferred", "Uncertain"].map((f) => (
                          <button
                            key={f}
                            aria-pressed={filter === f}
                            className={filter === f ? "filter-active" : ""}
                            onClick={() => setFilter(f)}
                          >
                            {f}
                          </button>
                        ))}
                      </div>
                      <div className="evidence-list">
                        {evidence.map((e) => (
                          <button
                            key={e.evidence_id}
                            className={
                              active?.evidence_id === e.evidence_id
                                ? "evidence-selected"
                                : ""
                            }
                            onClick={() => inspectEvidence(e.evidence_id)}
                            aria-pressed={active?.evidence_id === e.evidence_id}
                          >
                            <div>
                              <span className="evidence-id">{e.evidence_id}</span>
                              <span className={`provenance ${evidenceTone(e)}`}>
                                {status(e)}
                              </span>
                            </div>
                            <p>{readableEvidence(e)}</p>
                            <small>
                              {e.t_start != null
                                ? `${e.t_start.toFixed(2)}s`
                                : "Untimed evidence"}{" "}
                              <span className="inspect-hint">
                                Inspect source ↗
                              </span>
                            </small>
                          </button>
                        ))}
                        {!evidence.length && (
                          <p className="empty-state" role="status">
                            {!a.evidence_catalog.length
                              ? a.dry_run ? 'Dry Run skipped SAM and Muse. No physical evidence was generated. Open Findings for preparation status, or return to Import footage to review a new analysis.'
                                : 'No evidence records were saved for this investigation. Inspect Findings and Unknowns for missing-data explanations; reopening does not run inference.'
                              : 'No evidence matches. Try another search or filter.'}
                          </p>
                        )}
                      </div>
                    </>
                  ) : tab === "Findings" ? (
                    <div className="inspector-content">
                      <InvestigationOverview analysis={a} tracks={p.tracks} joints={p.joints} savedJob={p.liveMode} inspectEvidence={id=>{inspectEvidence(id);setTab('Evidence');}}>
                      {a.criteria && <CriterionCoverage criteria={a.criteria} citations={ids=><div className="claim-links">{ids.map(id=><button key={id} aria-label={`Inspect diagnostic citation ${id}`} onClick={()=>{inspectEvidence(id);setTab('Evidence');}}>{readableEvidence(a.evidence_catalog.find(e=>e.evidence_id===id)??{evidence_id:id})} ↗</button>)}</div>} inspectFrame={p.inspectCriterionFrame} manifest={a.multicamera}/>}
                      </InvestigationOverview>
                      <details className="findings-technical" open={technicalOpen} onToggle={event=>setTechnicalOpen(event.currentTarget.open)}><summary>Technical Details · original statements, frames and provenance</summary>
                      <DiagnosticDetails analysis={a} showCriteria={false} previewsEnabled={technicalOpen} inspectEvidence={(id) => { inspectEvidence(id); setTab("Evidence"); }} seek={p.seek} inspectFrame={p.inspectCriterionFrame} videoSrc={p.originalVideoSrc} fps={p.fps} duration={p.duration} jobId={p.liveMode?p.liveJobId:null}/>
                      {findingGroups(a).map((group) => (
                        <div key={group.label}>
                          <h3
                            className={`provenance ${group.tone}`}
                          >
                            {group.label}
                          </h3>
                          {group.label === "End-state supported" && <p>Recorded 2D geometry supports this assessment. Physical orientation, release and unstated task conditions are not independently verified.</p>}
                          {group.items.map((item, i) => (
                            <article key={i}>
                              <p>{item.text}</p>
                              <div className="claim-links">
                                {item.evidence_ids.map((id) => (
                                  <button
                                    key={id}
                                    onClick={() => {
                                      inspectEvidence(id);
                                      setTab("Evidence");
                                    }}
                                  >
                                    {id} ↗
                                  </button>
                                ))}
                              </div>
                            </article>
                          ))}
                        </div>
                      ))}
                      {(a.muse_explanation || a.factual_claims.length > 0) && (
                        <details className="model-explanation">
                          <summary>
                            {p.liveMode
                              ? "Muse explanation & citations"
                              : "Historical Muse explanation & citations"}
                          </summary>
                          <p className="model-context">
                            Model interpretation from this saved analysis.
                            Citations refer to this analysis catalog; they do not
                            establish task success or independent verification.
                          </p>
                          {a.muse_explanation && <p>{a.muse_explanation}</p>}
                          {a.factual_claims.map((claim, index) => (
                            <article key={index}>
                              <p>{claim.text}</p>
                              <div className="claim-links">
                                {claim.evidence_ids.map((id) => (
                                  <button
                                    key={id}
                                    onClick={() => {
                                      inspectEvidence(id);
                                      setTab("Evidence");
                                    }}
                                    aria-label={`Inspect model citation ${id}`}
                                  >
                                    {id} ↗
                                  </button>
                                ))}
                              </div>
                            </article>
                          ))}
                        </details>
                      )}
                      {a.highlight_muse_comparison && (
                        <article>
                          <h3>Historical comparison / reference context</h3>
                          <p>This saved comparison includes curator/reference commentary. It is not an independently detected failure mechanism.</p>
                          <p>{a.comparison_note}</p>
                          <p>Baseline verdict: {a.muse_only?.verdict}</p>
                          <p>{a.muse_only?.summary}</p>
                        </article>
                      )}
                      <details><summary>Full unchanged analysis record</summary><pre>{originalRecord}</pre></details>
                      </details>
                    </div>
                  ) : (
                    <div className="inspector-content">
                      <span className="provenance uncertain">
                        Uncertain / not established
                      </span>
                      <p className="saved-note-context">Saved analysis notes may include curator/reference context. They are not independently verified physical findings or additional pipeline predictions.</p>
                      {a.unknowns.map((u, i) => (
                        <article key={i}>
                          <p>{u}</p>
                        </article>
                      ))}
                      <h3>Limitations</h3>
                      {a.limitations.map((u, i) => (
                        <article key={i}>
                          <p>{u}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </aside>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
