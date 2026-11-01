import { useCallback, useEffect, useState } from "react";
import type { AnalysisBundle, TracksBundle } from "../lib/types";
import { Badge, Button, Panel } from "./ui";

const API = "";

type Budget = {
  total_budget_usd: number;
  per_run_budget_usd: number;
  spent_usd: number;
  remaining_usd: number;
};

type JobStatus = {
  job_id: string;
  status: string;
  stages?: Array<{ name: string; ts?: number }>;
  errors?: string[];
  cost?: { job_estimated_usd?: number; ledger?: Budget };
  joint_limitations?: string[];
  has_analysis?: boolean;
};

type Props = {
  onLiveResult: (args: {
    jobId: string;
    analysis: AnalysisBundle;
    tracks: TracksBundle | null;
  }) => void;
};

export function LiveAnalyzePanel({ onLiveResult }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [task, setTask] = useState("Store green plates in the dish rack");
  const [objectConcept, setObjectConcept] = useState("green plate");
  const [destination, setDestination] = useState("dish rack");
  const [windowStart, setWindowStart] = useState("0");
  const [windowEnd, setWindowEnd] = useState("4");
  const [useWindow, setUseWindow] = useState(false);
  const dryRun = true;
  const [preview, setPreview] = useState<string | null>(null);
  const [previewReady, setPreviewReady] = useState(false);
  const [completeDemo, setCompleteDemo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(() => {
    try {
      const id = sessionStorage.getItem("demodoctor.uploadJob");
      return id && /^[A-Za-z0-9_-]{1,128}$/.test(id) ? {job_id: id, status: "queued"} : null;
    } catch { return null; }
  });
  const [budget, setBudget] = useState<Budget | null>(null);
  const [health, setHealth] = useState<{
    ok?: boolean;
    sam_key?: boolean;
    muse_key?: boolean;
  } | null>(null);

  const refreshBudget = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/health`);
      setHealth(r.ok ? await r.json() : { ok: false });
    } catch {
      setHealth({ ok: false });
    }
    try {
      const r = await fetch(`${API}/api/budget`);
      if (r.ok) setBudget(await r.json());
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    setPreviewReady(false);
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const chooseFile = (next: File | null) => {
    try { sessionStorage.removeItem("demodoctor.uploadJob"); } catch { /* storage unavailable */ }
    if (next && (!next.type.startsWith("video/") || next.size === 0)) {
      setFile(null);
      setJob(null);
      setError("Choose a non-empty video file, such as MP4 or WebM.");
      return;
    }
    setError(null);
    setFile(next);
    setJob(null);
  };

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    setBusy(true);
    let cancelled = false;
    const id = window.setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/jobs/${job.job_id}`);
        if (!r.ok) throw new Error(`Job status failed (${r.status})`);
        const st = (await r.json()) as JobStatus;
        if (cancelled) return;
        if (st.status !== "completed") setJob(st);
        if (st.status === "completed" && st.has_analysis) {
          const [a, t] = await Promise.all([
            fetch(`${API}/api/jobs/${job.job_id}/analysis`).then((x) =>
              x.ok
                ? x.json()
                : Promise.reject(
                    new Error(`Results unavailable (${x.status})`),
                  ),
            ),
            fetch(`${API}/api/jobs/${job.job_id}/tracks`)
              .then((x) => (x.ok ? x.json() : null))
              .catch(() => null),
          ]);
          if (cancelled) return;
          setJob(st);
          onLiveResult({
            jobId: job.job_id,
            analysis: a as AnalysisBundle,
            tracks: t as TracksBundle | null,
          });
          void refreshBudget();
          setBusy(false);
        } else if (st.status === "completed") {
          throw new Error("Job completed without an analysis artifact");
        } else if (st.status === "failed") {
          setError((st.errors || []).join("; ") || "Analysis failed");
          setBusy(false);
          void refreshBudget();
        }
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
        setJob((previous) =>
          previous ? { ...previous, status: "failed" } : null,
        );
        setBusy(false);
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [job, onLiveResult, refreshBudget]);

  const submit = async () => {
    setError(null);
    if (!file) {
      setError("Choose a video file first.");
      return;
    }
    if (!task.trim()) {
      setError("Describe the task before preparing the demonstration.");
      return;
    }
    if (
      useWindow &&
      (!Number.isFinite(Number(windowStart)) ||
        !Number.isFinite(Number(windowEnd)) ||
        Number(windowStart) < 0 ||
        Number(windowEnd) <= Number(windowStart))
    ) {
      setError(
        "Choose a valid time window: start at zero or later, with the end after the start.",
      );
      return;
    }
    if (!health?.ok) {
      setError(
        "The local analysis service is unavailable. You can still preview footage here.",
      );
      return;
    }
    setBusy(true);
    const fd = new FormData();
    fd.append("video", file);
    fd.append("task_description", task);
    fd.append("object_concept", objectConcept);
    fd.append("destination_concept", destination);
    fd.append("run_muse", "false");
    fd.append("dry_run", dryRun ? "true" : "false");
    fd.append("force_sam_refresh", "false");
    fd.append("complete_demonstration", String(completeDemo));
    if (useWindow) {
      fd.append("window_start_s", windowStart);
      fd.append("window_end_s", windowEnd);
    } else {
      fd.append("max_window_s", completeDemo ? "30" : "4");
    }
    try {
      const r = await fetch(`${API}/api/analyze`, { method: "POST", body: fd });
      const body = await r.json();
      if (!r.ok) {
        setError(body?.detail ? JSON.stringify(body.detail) : r.statusText);
        setBusy(false);
        return;
      }
      try { sessionStorage.setItem("demodoctor.uploadJob", body.job_id); } catch { /* current panel still works */ }
      setJob({ job_id: body.job_id, status: "running", stages: [] });
      if (body.budget) setBudget(body.budget);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  return (
    <Panel title="Import & prepare" className="mt-5" bodyClassName="space-y-4">
      <p className="text-[0.9rem] text-[var(--muted)]">
        Preview footage locally, then prepare a free dry run using the local
        analysis service. SAM and Muse inference are disabled in this UI
        experiment.
      </p>

      <div className="flex flex-wrap gap-2">
        <Badge tone={health == null ? "muted" : health.ok ? "ok" : "danger"}>
          Local service{" "}
          {health == null
            ? "not checked"
            : health.ok
              ? "online"
              : "unavailable"}
        </Badge>
        <Badge tone="muted">Dry run only · No paid inference</Badge>
        {budget ? (
          <Badge tone="muted">
            budget ${budget.spent_usd.toFixed(3)} / ${budget.total_budget_usd} ·
            rem ${budget.remaining_usd.toFixed(3)}
          </Badge>
        ) : null}
      </div>

      <label
        className="upload-drop"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy) chooseFile(e.dataTransfer.files[0] ?? null);
        }}
      >
        <strong>{file ? file.name : "Drop robot footage here"}</strong>
        <small>
          {file
            ? `${(file.size / 1024 / 1024).toFixed(1)} MB · Local preview`
            : "Or browse files · MP4, WebM and other browser-supported video"}
        </small>
        <input
          type="file"
          accept="video/mp4,video/*"
          aria-label="Robot demonstration video"
          disabled={busy}
          className="mt-1 block w-full text-[0.9rem]"
          onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
        />
      </label>
      {preview && (
        <video
          className="upload-preview"
          src={preview}
          controls
          muted
          playsInline
          onLoadedData={() => setPreviewReady(true)}
          onError={() => {
            setPreviewReady(false);
            setError(
              "This video cannot be decoded by the browser. Try an H.264 MP4 or WebM file.",
            );
          }}
        />
      )}
      <ol
        className="progress-stages"
        aria-label="Import progress"
        aria-live="polite"
      >
        <li>
          01 · Footage selected <span>{file ? "Ready" : "Waiting"}</span>
        </li>
        <li>
          02 · Local preview <span>{previewReady ? "Ready" : "Waiting"}</span>
        </li>
        <li>
          03 · Dry-run preparation{" "}
          <span>
            {job?.status ?? (busy ? "Uploading footage" : "Not started")}
          </span>
        </li>
        <li>
          04 · Evidence results{" "}
          <span>
            {job?.status === "completed"
              ? "Available in investigation"
              : "Awaiting service"}
          </span>
        </li>
      </ol>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-[0.85rem]">
          <span className="font-medium text-[var(--muted)]">Task</span>
          <input
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2"
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
        </label>
        <label className="block text-[0.85rem]">
          <span className="font-medium text-[var(--muted)]">
            Object concept
          </span>
          <input
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2"
            value={objectConcept}
            onChange={(e) => setObjectConcept(e.target.value)}
          />
        </label>
        <label className="block text-[0.85rem]">
          <span className="font-medium text-[var(--muted)]">Destination</span>
          <input
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="inline-flex items-center gap-2 text-[0.85rem]">
          <input
            type="checkbox"
            checked={useWindow}
            onChange={(e) => setUseWindow(e.target.checked)}
          />
          Custom time window (s)
        </label>
        {useWindow ? (
          <>
            <input
              className="w-20 rounded-lg border border-[var(--border)] px-2 py-1.5"
              value={windowStart}
              onChange={(e) => setWindowStart(e.target.value)}
            />
            <span className="text-[var(--muted)]">→</span>
            <input
              className="w-20 rounded-lg border border-[var(--border)] px-2 py-1.5"
              value={windowEnd}
              onChange={(e) => setWindowEnd(e.target.value)}
            />
          </>
        ) : (
          <span className="text-[0.85rem] text-[var(--muted)]">
            {completeDemo
              ? "Complete video, up to 30 seconds"
              : "Default: first 4 seconds (partial task)"}
          </span>
        )}
        <label className="inline-flex items-center gap-2 text-[0.85rem]">
          <input
            type="checkbox"
            checked={completeDemo}
            onChange={(e) => setCompleteDemo(e.target.checked)}
          />
          Video contains the complete task
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          disabled={busy || !previewReady || !health?.ok}
          onClick={() => void submit()}
        >
          {busy ? "Preparing dry run…" : "Prepare dry run"}
        </Button>
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => void refreshBudget()}
        >
          Check local service
        </Button>
      </div>

      {error ? (
        <p role="alert" className="text-[0.9rem] text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      {job ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--panel-soft)] px-4 py-3 text-[0.85rem]">
          <div className="font-medium">
            Job {job.job_id} · {job.status}
          </div>
          <div className="mt-1 text-[var(--muted)]">
            {(job.stages || [])
              .slice(-6)
              .map((s) => s.name)
              .join(" → ") || "waiting…"}
          </div>
          {job.joint_limitations?.length ? (
            <ul className="mt-2 list-disc pl-5 text-[var(--warn)]">
              {job.joint_limitations.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          ) : null}
          {job.cost?.job_estimated_usd != null ? (
            <div className="mt-1 text-[var(--muted)]">
              Job spend est. ${job.cost.job_estimated_usd.toFixed(4)}
            </div>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
