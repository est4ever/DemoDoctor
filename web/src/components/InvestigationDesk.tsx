import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { EvidenceSource } from "./EvidenceSource";
import { RecordedEvidence } from "./RecordedEvidence";
import { DiagnosticDetails } from "./DiagnosticDetails";
import type { CSSProperties, ReactNode } from "react";
import { DEFAULT_PANELS, usePanelLayout } from "../lib/usePanelLayout";
import { PanelDivider } from "./PanelDivider";
import type {
  AnalysisBundle,
  EvidenceItem,
  TimelineMarker,
  TracksBundle,
  JointsBundle,
} from "../lib/types";
import { formatTime } from "../lib/playback";
import { getHighlight } from "../lib/types";
import {
  evidenceHeadline,
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
  liveMode: boolean;
  liveJobId?: string | null;
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
        const items = [...root.querySelectorAll<HTMLElement>('button:not(:disabled),input,summary,[tabindex="0"]')]
          .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== "hidden");
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
  const [tab, setTab] = useState("Evidence");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const a = p.analysis;
  const displayKey = p.liveMode ? a.episode_key : p.episodeKey;
  const highlight = getHighlight(a);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        page !== "desk" ||
        /INPUT|TEXTAREA|SELECT|BUTTON/.test(target.tagName) ||
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
    setTab("Evidence");
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
  const [sourceOpen, setSourceOpen] = useState(false);
  const [inspection, setInspection] = useState(0);
  const sourceSummary = useRef<HTMLElement>(null);
  const inspectorScroll = useRef<HTMLDivElement>(null);
  const inspectEvidence = (id: string) => {
    p.selectEvidence(id); // Existing App handler seeks only when a time/frame exists.
    setSourceOpen(true);
    setInspection(n => n + 1); // Re-open/reveal even when selecting the same ID again.
  };
  useLayoutEffect(() => {
    if (!inspection) return;
    sourceSummary.current?.focus({ preventScroll: true });
    if (inspectorScroll.current) inspectorScroll.current.scrollTop = 0;
  }, [inspection]);
  return (
    <div className={`workstation adjustable-panels ${panels.desktop ? "panels-desktop" : "panels-narrow"} ${panels.navCollapsed ? "nav-collapsed" : ""}`}
      style={{"--nav-width": `${panels.navCollapsed ? panels.leftOffset : panels.leftWidth}px`, "--nav-offset": `${panels.leftOffset}px`,
        "--inspector-width": `${panels.rightWidth}px`, "--inspector-column": `${panels.inspectorCollapsed ? 44 : panels.rightWidth}px`} as CSSProperties}>
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
        <button
          className="wordmark"
          onClick={() => navigate("home")}
          aria-label="DemoDoctor home"
        >
          <span className="logo-mark">
            d<span>°</span>
          </span>
          <span className="nav-copy">
            DemoDoctor<small>ROBOTICS INVESTIGATION</small>
          </span>
        </button>
        <div className="rail-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button
            aria-label="Overview" title="Overview"
            className={page === "home" ? "nav-active" : ""}
            onClick={() => navigate("home")}
          >
            <span aria-hidden="true">⌂</span><span className="nav-copy">Overview</span> <kbd>01</kbd>
          </button>
          <button
            aria-label="Investigation" title="Investigation"
            className={page === "desk" ? "nav-active" : ""}
            onClick={() => navigate("desk")}
          >
            <span aria-hidden="true">⌖</span><span className="nav-copy">Investigation</span> <kbd>02</kbd>
          </button>
          <button
            aria-label="Import footage" title="Import footage"
            className={page === "upload" ? "nav-active" : ""}
            onClick={() => navigate("upload")}
          >
            <span aria-hidden="true">↥</span><span className="nav-copy">Import footage</span> <kbd>03</kbd>
          </button>
        </nav>
        <div className="rail-label session-heading">
          DEMONSTRATIONS <span>{p.episodes.length}</span>
        </div>
        <div className="session-list">
          {p.episodes.map((ep) => (
            <button
              key={ep.key}
              aria-label={`Open ${ep.key.toUpperCase()} ${ep.label}`} title={ep.label}
              aria-current={page === "desk" && !p.liveMode && ep.key === p.episodeKey ? "page" : undefined}
              className={
                page === "desk" && !p.liveMode && ep.key === p.episodeKey
                  ? "session-active"
                  : ""
              }
              onClick={() => open(ep.key)}
            >
              <span className="session-dot" />
              <span className="episode-glyph" aria-hidden="true">{ep.key === "pilot" ? "P" : ep.key.slice(-2)}</span>
              <span className="nav-copy">
                {ep.key.toUpperCase()}
                <small>
                  {ep.key === "ep010"
                    ? "Dish tidy-up · development"
                    : ep.label.split("—")[1]?.trim()}
                </small>
              </span>
              <span className="session-arrow">↗</span>
            </button>
          ))}
        </div>
        <div className="rail-bottom">
          <span className="status-dot" /> Local workspace
          <small>Cached demos replay offline · Uploads require confirmation</small>
          <div className="rail-version">
            UI EXPERIMENT <span>v0.1</span>
          </div>
        </div>
      </aside>
      {panels.desktop && !panels.navCollapsed && <PanelDivider side="left" width={panels.leftWidth} min={180} max={panels.leftMax}
        onResize={width => panels.setPreferences(v => ({...v, leftWidth: width}))}
        onReset={() => panels.setPreferences(v => ({...v, leftWidth: DEFAULT_PANELS.leftWidth}))}
        style={{left: `calc(${panels.leftWidth}px - 5px)`}} />}
      <main className="desk-main" inert={!panels.desktop && panels.navDrawer}>
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
            {page === "upload" ? "Import · explicit approval" : a.dry_run ? "Dry run · SAM/Muse not executed" : p.liveMode ? "Uploaded footage" : "Offline replay"}
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
                <button className="lime-button" onClick={() => open("ep010")}>
                  Open investigation <span>↗</span>
                </button>
                <small>Development episode · Frozen analysis</small>
              </div>
            </div>
            <div className="section-line">
              <h2>Demonstration library</h2>
              <span>{p.episodes.length} RECORDED DEMONSTRATIONS</span>
            </div>
            <div className="episode-grid">
              {p.episodes.map((ep, i) => (
                <button
                  className="episode-card"
                  key={ep.key}
                  onClick={() => open(ep.key)}
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
                </button>
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
              <button onClick={() => navigate("upload")}>
                Import footage ↗
              </button>
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
                <h1>{a.title}</h1>
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
              </div>
            </div>
            <div className="investigation-grid">
              <div className="camera-column" inert={!panels.desktop && panels.inspectorDrawer}>
                <section className="camera-stage">
                  <div className="stage-heading">
                    <span>
                      <span className="status-dot" /> CAMERA 01{" "}
                      <span className="muted">/ PRIMARY EVIDENCE</span>
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
                    {a.timeline_markers.map((m, index) => (
                      <button
                        key={m.id}
                        title={`${m.label} · ${m.t}s · ${m.kind}`}
                        aria-label={`Seek to ${m.label}`}
                        style={{
                          left: `${p.duration ? (m.t / p.duration) * 100 : 0}%`,
                          top: `${(index % 3) * 25}px`,
                        }}
                        onClick={() => p.selectMarker(m)}
                        className={`timeline-marker ${markerPresentation(m).tone}`}
                        aria-pressed={m.evidence_ids.includes(
                          active?.evidence_id ?? "",
                        )}
                      >
                        {index + 1}
                      </button>
                    ))}
                    <span
                      className="playhead"
                      style={{
                        left: `${p.duration ? (p.t / p.duration) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <input
                    aria-label="Timeline position"
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
                {active && (
                  <section
                    className="source-detail"
                    aria-label="Selected evidence"
                  >
                    <div className="selected-evidence-heading">
                      <span className="eyebrow">
                        SELECTED EVIDENCE {active.evidence_id}
                      </span>
                      <span className={`provenance ${evidenceTone(active)}`}>
                        {status(active)}
                      </span>
                    </div>
                    <h3>{evidenceHeadline(active)}</h3>
                    <button className="inspect-source-button" aria-label={`Inspect source for ${active.evidence_id}`} aria-controls="evidence-source-details" aria-expanded={sourceOpen} onClick={() => inspectEvidence(active.evidence_id)}>Inspect source ↗</button>
                    {active.t_start != null ? (
                      <button
                        className="evidence-seek"
                        onClick={() => p.selectEvidence(active.evidence_id)}
                        aria-label={`Seek to selected evidence at ${active.t_start.toFixed(2)} seconds`}
                      >
                        {formatTime(active.t_start)} <span>Seek camera ↗</span>
                      </button>
                    ) : (
                      <p className="untimed-evidence">
                        Untimed evidence · no camera seek
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
                  {active && (
                    <div className="technical-evidence">
                      <details id="evidence-source-details" open={sourceOpen} onToggle={e => setSourceOpen(e.currentTarget.open)}>
                        <summary ref={sourceSummary}>Source & technical evidence · {active.evidence_id}</summary>
                        <EvidenceSource item={active} analysis={a} tracks={p.tracks} joints={p.joints} fps={p.fps} seek={p.seek} jobId={p.liveMode ? p.liveJobId : null} />
                      </details>
                    </div>
                  )}
                  <details className="investigation-summary">
                    <summary>Investigation summary</summary>
                    <h3>{a.diagnosis_headline}</h3>
                    <p>{a.diagnosis_summary}</p>
                    <RecordedEvidence analysis={a} fps={p.fps} seek={p.seek} />
                    <p className="summary-disclaimer">{a.disclaimer}</p>
                  </details>
                  {tab === "Evidence" ? (
                    <>
                      <details className="timeline-index">
                        <summary>Timeline event index</summary>
                        <div className="timeline-events" aria-label="Timeline events">
                          {a.timeline_markers.map((m, index) => (
                            <button
                              key={m.id}
                              onClick={() => p.selectMarker(m)}
                              aria-pressed={m.evidence_ids.includes(
                                active?.evidence_id ?? "",
                              )}
                            >
                              <span className="mono">
                                <b>{index + 1}</b> {m.t.toFixed(2)}s
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
                            <p>{evidenceHeadline(e)}</p>
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
                          <p className="empty-state">
                            No evidence matches. Try another search or filter.
                          </p>
                        )}
                      </div>
                    </>
                  ) : tab === "Findings" ? (
                    <div className="inspector-content">
                      <DiagnosticDetails analysis={a} inspectEvidence={(id) => { inspectEvidence(id); setTab("Evidence"); }} seek={p.seek} />
                      {findingGroups(a).map((group) => (
                        <div key={group.label}>
                          <h3
                            className={`provenance ${group.label.toLowerCase()}`}
                          >
                            {group.label}
                          </h3>
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
                          <h3>Muse-only comparison</h3>
                          <p>{a.comparison_note}</p>
                          <p>Baseline verdict: {a.muse_only?.verdict}</p>
                          <p>{a.muse_only?.summary}</p>
                        </article>
                      )}
                    </div>
                  ) : (
                    <div className="inspector-content">
                      <span className="provenance uncertain">
                        Uncertain / not established
                      </span>
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
