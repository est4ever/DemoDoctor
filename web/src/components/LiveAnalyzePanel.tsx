import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalysisBundle, TracksBundle } from "../lib/types";
import { Badge, Button, Panel } from "./ui";
import { CameraInputs, useCameraInputs } from "./CameraInputs";

type Budget = { total_budget_usd: number; per_run_budget_usd: number; spent_usd: number; remaining_usd: number };
type Health = { ok?: boolean; sam_key?: boolean; muse_key?: boolean; real_analysis_enabled?: boolean; offline_only?: boolean };
type JobStatus = { job_id: string; status: string; dry_run?: boolean; stages?: Array<{name: string}>; errors?: string[]; joint_limitations?: string[]; has_analysis?: boolean };
type Quote = { job_id: string; approval_id: string; filename: string; sha256: string; start_s: number; end_s: number; frame_start: number; frame_end: number; fps: number; source_frames: number; estimated_max_usd: number; sam_estimate_usd: number; muse_reservation_usd: number; operations: string[]; complete_task_scope: boolean; budget: Budget; note: string;
  task_description?: string; task_subgoals?: Array<{description:string;action:string}>;
  camera_set?: boolean; cameras?: Array<{camera_id:string;name:string;sha256:string;source_sha256?:string;crop?:number[]|null;width?:number;height?:number;frame_start:number;frame_end:number;fps:number;operations:string[];sam_estimate_usd:number}> };
type Props = { onLiveResult: (args: { jobId: string; analysis: AnalysisBundle; tracks: TracksBundle | null }) => void };
async function responseBody(r: Response) {
  const body = await r.json();
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? r.statusText));
  return body;
}

export function LiveAnalyzePanel({ onLiveResult }: Props) {
  const cameras = useCameraInputs();
  const [file, setFile] = useState<File | null>(null);
  const [task, setTask] = useState("Store green plates in the dish rack");
  const [questions,setQuestions]=useState("");
  const [objectConcept, setObjectConcept] = useState("green plate");
  const [destination, setDestination] = useState("dish rack");
  const [windowStart, setWindowStart] = useState("0"), [windowEnd, setWindowEnd] = useState("4");
  const [useWindow, setUseWindow] = useState(false), [completeDemo, setCompleteDemo] = useState(false);
  const [mode, setMode] = useState<"dry" | "real">("dry");
  const [preview, setPreview] = useState<string | null>(null), [previewReady, setPreviewReady] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null), [health, setHealth] = useState<Health | null>(null);
  const [budget, setBudget] = useState<Budget | null>(null), [pollEpoch, setPollEpoch] = useState(0);
  const [pollPaused, setPollPaused] = useState(false);
  const submitting = useRef(false);
  const [job, setJob] = useState<JobStatus | null>(() => {
    try { const id = sessionStorage.getItem("demodoctor.uploadJob"); return id && /^[A-Za-z0-9_-]{1,128}$/.test(id) ? {job_id: id, status: "queued"} : null; }
    catch { return null; }
  });
  const jobId = job?.job_id;
  const refreshBudget = useCallback(async () => {
    try { const h = await responseBody(await fetch("/api/health")); setHealth(h); if (h.budget) setBudget(h.budget); }
    catch { setHealth({ok: false}); }
  }, []);
  useEffect(() => { void refreshBudget(); }, [refreshBudget]);
  useEffect(() => {
    setPreviewReady(false);
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  // A prepared quote is immutable. Any input edit cancels the visible approval.
  useEffect(() => { setQuote(null); }, [file, task, questions, objectConcept, destination, windowStart, windowEnd, useWindow, completeDemo, mode]);
  useEffect(() => { setQuote(null); }, [cameras.count,cameras.sourceMode,cameras.cameras,cameras.files,cameras.cropsConfirmed,cameras.aligned,cameras.basis]);
  const chooseFile = (next: File | null) => {
    if (busy) return;
    try { sessionStorage.removeItem("demodoctor.uploadJob"); } catch { /* browser storage optional */ }
    setJob(null); setQuote(null); setError(null);
    if (next && (!next.type.startsWith("video/") || !next.size)) { setFile(null); setError("Choose a non-empty video file, such as MP4 or WebM."); return; }
    setFile(next);
  };
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false, timer: number | undefined;
    setBusy(true); setPollPaused(false);
    const poll = async () => {
      try {
        const st = await responseBody(await fetch(`/api/jobs/${jobId}`)) as JobStatus;
        if (cancelled) return;
        setJob(st);
        if (st.status === "completed") {
          if (!st.has_analysis) throw new Error("Job completed without an analysis artifact");
          const [analysis, tracks] = await Promise.all([
            fetch(`/api/jobs/${jobId}/analysis`).then(responseBody),
            fetch(`/api/jobs/${jobId}/tracks`).then(r => r.ok ? r.json() : null),
          ]);
          if (cancelled) return;
          try { if (sessionStorage.getItem("demodoctor.uploadJob") === jobId) sessionStorage.removeItem("demodoctor.uploadJob"); } catch { /* URL preserves completed results */ }
          setBusy(false); onLiveResult({jobId, analysis, tracks}); void refreshBudget(); return;
        }
        if (["failed", "interrupted"].includes(st.status)) {
          setError((st.errors || []).join("; ") || "Analysis stopped. No automatic retry was made.");
          setBusy(false); void refreshBudget(); return;
        }
        if (st.status === "awaiting_approval") { setBusy(false); setError(previous => previous ? `${previous} No inference was started.` : "This upload was not started. Prepare it again to obtain a new confirmation."); return; }
        timer = window.setTimeout(poll, 1500);
      } catch (e) {
        if (cancelled) return;
        setError(`${String(e)}. Status unknown; recover this job before starting another. No paid retry was made.`);
        setPollPaused(true); // Preserve the job ID and prevent accidental paid resubmission.
      }
    };
    timer = window.setTimeout(poll, 100);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [jobId, pollEpoch, onLiveResult, refreshBudget]);

  const submit = async () => {
    if (submitting.current) return;
    setError(null);
    if (!task.trim() || (!cameras.cameraSet && (!file || !objectConcept.trim() || !destination.trim()))) { setError("Choose footage and fill in the task, object concept and destination."); return; }
    if (cameras.cameraSet) { const invalid=cameras.validate();if(invalid){setError(invalid);return;} }
    if (useWindow && (!windowStart.trim() || !windowEnd.trim() || !Number.isFinite(Number(windowStart)) || !Number.isFinite(Number(windowEnd)) || Number(windowStart) < 0 || Number(windowEnd) <= Number(windowStart) || Number(windowEnd) - Number(windowStart) > 30)) {
      setError("Choose a valid time window: start at zero or later, end after start, at most 30 seconds."); return;
    }
    if (!health?.ok) { setError("The local analysis service is unavailable. You can still preview footage here."); return; }
    submitting.current = true; setBusy(true); setQuote(null);
    const fd = cameras.cameraSet ? cameras.form(task, useWindow?Number(windowStart):0, useWindow?Number(windowEnd):4, mode==="dry", questions) : new FormData();
    if (!cameras.cameraSet) {
    fd.append("video", file!); fd.append("task_description", task);
    fd.append("investigation_questions",questions);
    fd.append("object_concept", objectConcept); fd.append("destination_concept", destination);
    fd.append("run_muse", String(mode === "real")); fd.append("dry_run", String(mode === "dry"));
    fd.append("prepare_only", String(mode === "real")); fd.append("force_sam_refresh", "false"); fd.append("complete_demonstration", String(completeDemo));
    if (useWindow) { fd.append("window_start_s", windowStart); fd.append("window_end_s", windowEnd); }
    else fd.append("max_window_s", completeDemo ? "30" : "4");
    }
    try {
      const body = await responseBody(await fetch(cameras.cameraSet?"/api/multicamera/prepare":"/api/analyze", {method: "POST", body: fd}));
      if (body.quote) { setQuote({...body.quote,camera_set:cameras.cameraSet}); setBusy(false); }
      else { try { sessionStorage.setItem("demodoctor.uploadJob", body.job_id); } catch { /* optional */ } setJob({job_id: body.job_id, status: "queued"}); }
    } catch (e) { setError(String(e)); setBusy(false); }
    finally { submitting.current = false; }
  };
  const approve = async () => {
    if (!quote || submitting.current) return;
    const id = quote.job_id;
    submitting.current = true; setBusy(true); setError(null);
    // Save the identity before the POST: a dropped response must recover, never retry.
    try { sessionStorage.setItem("demodoctor.uploadJob", id); } catch { /* current panel still recovers */ }
    try {
      await responseBody(await fetch(quote.camera_set?`/api/multicamera/${id}/start`:`/api/jobs/${id}/start`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({approval_id: quote.approval_id})}));
      setQuote(null); setJob({job_id: id, status: "queued"});
    } catch (e) { setError(`${String(e)}. Checking this job; no automatic paid retry.`); setQuote(null); setJob({job_id: id, status: "queued"}); }
    finally { submitting.current = false; }
  };
  const realReady = health?.real_analysis_enabled && health.sam_key && health.muse_key;
  const budgetFits = quote && quote.estimated_max_usd <= Math.min(quote.budget.per_run_budget_usd, quote.budget.remaining_usd);
  return <Panel title="Import & prepare" className="mt-5" bodyClassName="space-y-4">
    <p className="text-[0.9rem] text-[var(--muted)]">Preview footage locally. Dry Run prepares a video without provider calls. Real Analysis uses Meta SAM 3.1 and Muse Spark Open only after you confirm its estimate.</p>
    <div className="flex flex-wrap gap-2">
      <Badge tone={health?.ok ? "ok" : "muted"}>Local service {health?.ok ? "online" : "unavailable"}</Badge>
      <Badge tone="muted">Meta {health?.sam_key ? "configured" : "not configured"}</Badge>
      <Badge tone="muted">Fireworks {health?.muse_key ? "configured" : "not configured"}</Badge>
      <Badge tone="muted">{health?.real_analysis_enabled ? "Real-analysis session enabled" : "Offline session"}</Badge>
      {budget && <Badge tone="muted">budget ${budget.spent_usd.toFixed(3)} / ${budget.total_budget_usd} · rem ${budget.remaining_usd.toFixed(3)} · run limit ${budget.per_run_budget_usd.toFixed(2)}</Badge>}
    </div>
    <CameraInputs setup={cameras} disabled={busy}/>
    <fieldset disabled={busy} className="flex flex-wrap gap-4"><legend className="text-sm font-medium">Analysis mode</legend>
      <label><input type="radio" name="analysis-mode" checked={mode === "dry"} onChange={() => setMode("dry")} /> Dry Run · no provider calls</label>
      <label><input type="radio" name="analysis-mode" checked={mode === "real"} onChange={() => setMode("real")} /> Real Analysis · paid SAM + Muse</label>
    </fieldset>
    {mode === "real" && <div className="rounded-xl border border-[var(--border)] p-3 text-sm" role="note">
      {!health?.real_analysis_enabled && <p>Offline protection is active. Start an explicitly enabled local session with <code>DemoDoctor -RealAnalysis</code>. Stop the managed offline session first. Ordinary DemoDoctor stays offline.</p>}
      {(!health?.sam_key || !health?.muse_key) && <p>Configure MODEL_API_KEY and FIREWORKS_API_KEY in the backend environment or a private .env file, then restart the enabled session. Never enter API keys in this page. See <a href="/real-analysis-setup.html" target="_blank" rel="noreferrer">local setup instructions</a>.</p>}
      <p>Configuration presence does not verify credentials, credit or provider availability. Video-only analysis cannot measure gripper opening or prove release. Raw destination masks cannot certify calibrated interior placement; the outcome may remain uncertain.</p>
      <p>{cameras.cameraSet?"Camera sets and cropped views publish independent image-space observations only. Physical-event reconstruction is disabled, including for wrist cameras; the combined outcome stays uncertain.":"The outcome rule is all objects in the target, with a stationary camera and target footprint. Articulated goals such as closing a drawer are not verified by this rule."}</p>
    </div>}
    {!cameras.cameraSet&&<><label className="upload-drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); chooseFile(e.dataTransfer.files[0] ?? null); }}>
      <strong>{file?.name ?? "Drop robot footage here"}</strong><small>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · Local preview` : "Or browse files · MP4, WebM and other browser-supported video"}</small>
      <input type="file" accept="video/mp4,video/*" aria-label="Robot demonstration video" disabled={busy} onChange={e => chooseFile(e.target.files?.[0] ?? null)} />
    </label>
    {preview && <video className="upload-preview" src={preview} controls muted playsInline onLoadedData={() => setPreviewReady(true)} onError={() => { setPreviewReady(false); setError("This video cannot be decoded by the browser. Try an H.264 MP4 or WebM file."); }} />}</>}
    <ol className="progress-stages" aria-label="Import progress" aria-live="polite">
      <li>01 · Footage selected <span>{cameras.cameraSet?cameras.files.filter(Boolean).length+" source(s)":file ? "Ready" : "Waiting"}</span></li>
      <li>02 · Local preview <span>{(cameras.cameraSet?cameras.previewReady:previewReady) ? "Ready" : "Waiting"}</span></li>
      <li>03 · {job ? job.dry_run === false ? "Real analysis job" : job.dry_run === true ? "Dry-run preparation" : "Recovered job" : mode === "dry" ? "Dry-run preparation" : "Real analysis"} <span>{job?.status ?? (busy ? "Uploading footage" : quote ? "Awaiting confirmation" : "Not started")}</span></li>
      <li>04 · Evidence results <span>{job?.status === "completed" ? "Available in investigation" : "Awaiting service"}</span></li>
    </ol>
    <fieldset disabled={busy} className="grid gap-3 md:grid-cols-2">
      <label className="block text-sm">Task<input aria-label="Task description" className="mt-1 w-full rounded-xl border border-[var(--border)] px-3 py-2" value={task} onChange={e => setTask(e.target.value)} /></label>
      <label className="block text-sm">Questions to investigate (optional)<input aria-label="Questions to investigate" maxLength={2000} className="mt-1 w-full rounded-xl border border-[var(--border)] px-3 py-2" value={questions} onChange={e=>setQuestions(e.target.value)} placeholder="Placement, orientation, incomplete manipulation, occlusion…"/><small>Questions do not establish task criteria or physical facts. Unsupported explanations remain Unverified.</small></label>
      {!cameras.cameraSet&&<><label className="block text-sm">Object concept<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-3 py-2" value={objectConcept} onChange={e => setObjectConcept(e.target.value)} /></label>
      <label className="block text-sm">Destination<input className="mt-1 w-full rounded-xl border border-[var(--border)] px-3 py-2" value={destination} onChange={e => setDestination(e.target.value)} /></label></>}
    </fieldset>
    <fieldset disabled={busy} className="flex flex-wrap items-end gap-3 text-sm">
      <label><input type="checkbox" checked={useWindow} onChange={e => setUseWindow(e.target.checked)} /> Custom time window (s)</label>
      {useWindow ? <><input aria-label="Window start seconds" className="w-20 rounded-lg border px-2 py-1.5" value={windowStart} onChange={e => setWindowStart(e.target.value)} /><span>→</span><input aria-label="Window end seconds" className="w-20 rounded-lg border px-2 py-1.5" value={windowEnd} onChange={e => setWindowEnd(e.target.value)} /></> : <span>{completeDemo&&!cameras.cameraSet ? "Complete video, up to 30 seconds" : "Default: first 4 seconds (partial task)"}</span>}
      {!cameras.cameraSet&&<label><input type="checkbox" checked={completeDemo} onChange={e => setCompleteDemo(e.target.checked)} /> Video contains the complete task</label>}
      {cameras.cameraSet&&<span>Shared time window; completeness and physical outcome remain unverified.</span>}
    </fieldset>
    <div className="flex flex-wrap gap-2">
      <Button variant="primary" disabled={busy || !(cameras.cameraSet?cameras.previewReady:previewReady) || !health?.ok || (mode === "real" && !realReady)} onClick={() => void submit()}>{busy ? "Working…" : mode === "real" ? "Review real analysis estimate" : "Prepare dry run"}</Button>
      <Button variant="ghost" disabled={busy} onClick={() => void refreshBudget()}>Check local service</Button>
      {pollPaused && <Button onClick={() => setPollEpoch(n => n + 1)}>Recover job status</Button>}
    </div>
    {quote && <section aria-label="Confirm real analysis" className="rounded-xl border border-[var(--border)] p-4 space-y-2" tabIndex={-1} ref={el => el?.focus()}>
      <h3 className="font-semibold">Confirm Real Analysis</h3>
      {quote.cameras?<><p>{quote.cameras.length} camera view(s) · shared window {quote.start_s.toFixed(3)}–{quote.end_s.toFixed(3)}s</p>{quote.cameras.map(c=><div key={c.camera_id}><strong>{c.camera_id} · {c.name}</strong><p>Native frames [{c.frame_start}, {c.frame_end}) at {c.fps} FPS · ${c.sam_estimate_usd.toFixed(4)}</p><p>Crop (x, y, width, height): {c.crop?.join(", ") ?? "original source"} · {c.width} × {c.height} px</p><p className="break-all text-xs">Camera SHA256 {c.sha256}<br/>Source SHA256 {c.source_sha256 ?? "unavailable"}</p><p>{c.operations.join("; ")}</p></div>)}</>:<><p>{quote.filename} · {quote.start_s.toFixed(3)}–{quote.end_s.toFixed(3)}s · frames {quote.frame_start}–{quote.frame_end - 1} at {quote.fps} FPS</p><p className="break-all text-xs">SHA256 {quote.sha256}</p></>}
      <p>Task: {quote.task_description ?? task}{!quote.cameras&&` · Object: ${objectConcept} · Destination: ${destination}`}</p>
      {!!quote.task_subgoals?.length && <><p>Explicit subgoals to assess; these are requirements, not findings:</p><ol>{quote.task_subgoals.map((s,i)=><li key={i}>{s.description}{s.action === "unparsed" ? " · Not assessed: clarify unsupported instruction" : " · requires independent evidence"}</li>)}</ol></>}
      {questions&&<p>Investigation questions: {questions} · hypotheses remain unverified unless independently supported.</p>}
      <p>{quote.complete_task_scope ? "Declared complete task" : "Whole-task completeness not established: the task outcome remains uncertain"}</p>
      <ul className="list-disc pl-5">{quote.operations.map(op => <li key={op}>{op}</li>)}</ul>
      <p>SAM estimate ${quote.sam_estimate_usd.toFixed(4)} + Muse reservation ${quote.muse_reservation_usd.toFixed(2)} = ${quote.estimated_max_usd.toFixed(4)}. Zero automatic paid retries.</p>
      <p className="text-sm">{quote.note}</p>
      {!budgetFits && <p role="alert">Estimate exceeds the remaining or per-run budget. No provider calls have been made. An owner must explicitly configure an adequate run limit; this page will not raise it.</p>}
      <Button variant="primary" disabled={busy || !budgetFits} onClick={() => void approve()}>Analyze — approve estimated cost</Button>{" "}
      <Button disabled={busy} onClick={() => setQuote(null)}>Cancel</Button>
    </section>}
    {error && <p role="alert" className="text-sm text-[var(--danger)]">{error}</p>}
    {job && <div className="rounded-xl border border-[var(--border)] p-3 text-sm" aria-live="polite"><strong>Job {job.job_id} · {job.status}{job.dry_run === false ? " · Real Analysis" : job.dry_run === true ? " · Dry Run" : ""}</strong><p>{job.stages?.slice(-6).map(s => s.name).join(" → ") || "waiting…"}</p>{job.joint_limitations?.map(u => <p key={u}>{u}</p>)}</div>}
  </Panel>;
}
