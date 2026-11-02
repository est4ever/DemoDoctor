import { useEffect, useState } from "react";
import { Button, Panel } from "./ui";
import { isSavedJobId, savedJobHref } from "../lib/savedInvestigations";

type SavedJob = {
  job_id: string; task_description?: string; video_filename?: string; created_at?: string | null; date_basis?: string;
  camera_count?: number; analysis_type?: string; status: string; outcome?: string | null;
  outcome_note?: string; can_open?: boolean; availability_error?: string | null;
};
const modes: Record<string,string> = {real: "Real analysis · saved outputs", dry_run: "Dry Run · providers skipped", recorded_replay: "Recorded replay", unknown: "Analysis type not recorded"};

export function RecentInvestigations() {
  const [jobs,setJobs] = useState<SavedJob[]>([]), [error,setError] = useState<string|null>(null);
  const [loading,setLoading] = useState(true), [epoch,setEpoch] = useState(0), [all,setAll] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);setError(null);
    fetch('/api/jobs',{method:'GET',signal:controller.signal}).then(async r => {
      if (!r.ok) throw new Error('Local investigation history is unavailable. Check the backend connection.');
      const body = await r.json();if (!Array.isArray(body.jobs)) throw new Error('Local investigation history is unreadable.');
      if (!controller.signal.aborted) setJobs(body.jobs.filter((j:SavedJob) => typeof j?.job_id==='string' && isSavedJobId(j.job_id)));
    }).catch(e => {if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Local history unavailable.');})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  },[epoch]);
  return <section aria-label="Recent Investigations" className="mt-5">
    <Panel title="Recent Investigations" action={<Button disabled={loading} onClick={() => setEpoch(n=>n+1)}>Refresh investigations</Button>} bodyClassName="space-y-3">
      <p>Saved locally by this backend, separate from the six bundled demonstrations. Opening a completed investigation uses saved results: no upload, inference or payment. No credentials are needed for offline replay.</p>
      {loading && <p role="status">Loading saved investigations…</p>}
      {error && <p role="alert">{error} No analysis was started.</p>}
      {!loading && !error && !jobs.length && <p>No saved investigations found in this backend. New analyses will appear here; the bundled demonstration library remains separate.</p>}
      <ul className="grid gap-3 md:grid-cols-2">{(all?jobs:jobs.slice(0,6)).map(job => {
        const date=job.created_at ? new Date(job.created_at) : null;
        return <li key={job.job_id} className="rounded-xl border border-[var(--border)] p-4 space-y-2" data-saved-job={job.job_id}>
          <h3 className="font-semibold">{job.task_description ?? 'Task not recorded'}</h3>
          <p>{job.video_filename ?? 'Original filename not recorded'} · {job.camera_count ? `${job.camera_count} camera view${job.camera_count===1?'':'s'}` : 'Camera count not recorded'}</p>
          <p><time dateTime={job.created_at ?? undefined} title={job.date_basis}>{date && Number.isFinite(date.getTime()) ? date.toLocaleString(undefined,{timeZoneName:'short'}) : 'Analysis date not recorded'}</time></p>
          <p>{modes[job.analysis_type ?? 'unknown'] ?? modes.unknown} · Status: {job.status}</p>
          <p>{job.analysis_type==='dry_run' ? 'No physical conclusions · Dry Run' : job.outcome ? `${job.outcome[0].toUpperCase()+job.outcome.slice(1)} · saved verdict` : 'Outcome unavailable'}</p>
          {job.outcome_note && <p className="text-sm text-[var(--muted)]">{job.outcome_note}</p>}
          <p className="text-xs break-all">Job {job.job_id}</p>
          {job.can_open ? <a href={savedJobHref(job.job_id)} className="inline-flex rounded-xl border border-[var(--border)] px-4 py-2.5 focus-visible:outline-2 focus-visible:outline-offset-2" aria-label={`Open Investigation ${job.job_id}`}>Open Investigation ↗</a>
            : <><Button disabled>Open Investigation</Button><p>{job.availability_error ?? 'Results unavailable. Restart the local backend if its history metadata is outdated. No analysis was started.'}</p></>}
        </li>;
      })}</ul>
      {jobs.length>6 && <Button onClick={() => setAll(v=>!v)}>{all?'Show fewer investigations':`Show all ${jobs.length} recent investigations`}</Button>}
      {jobs.length===50 && <small>Showing the most recent 50 local records. Older saved investigations remain accessible through their bookmarked job URLs.</small>}
    </Panel>
  </section>;
}
