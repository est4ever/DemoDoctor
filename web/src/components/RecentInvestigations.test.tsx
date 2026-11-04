// @vitest-environment jsdom
import { act } from "react";
import { createRoot,type Root } from "react-dom/client";
import { beforeEach,afterEach,expect,it,vi } from "vitest";
import { RecentInvestigations } from "./RecentInvestigations";
let host:HTMLDivElement,root:Root;
const job={job_id:'20261101T160738Z_saved',task_description:'Pick up the block, place it, then close the drawer',video_filename:'droid.mp4',created_at:'2026-11-01T16:07:38Z',camera_count:1,analysis_type:'real',status:'completed',outcome:'uncertain',can_open:true,outcome_note:'Saved verdict; inspect evidence'};
beforeEach(()=>{vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();});
it('loads persisted backend history in new mounts with a GET-only open link',async()=>{
  const fetcher=vi.fn(async(_url:string)=>Response.json({jobs:[job]}));vi.stubGlobal('fetch',fetcher);
  await act(async()=>root.render(<RecentInvestigations/>));
  expect(host.textContent).toContain('droid.mp4 · 1 camera view');expect(host.textContent).toContain('Uncertain · saved verdict');
  expect(host.textContent).toContain('Saved analysis · execution unconfirmed');expect(host.querySelector('time')?.dateTime).toBe(job.created_at);
  expect(host.querySelector('a')?.getAttribute('href')).toBe('#job/'+job.job_id);
  expect(fetcher.mock.calls.every(c=>c[0]==='/api/jobs')).toBe(true);
  await act(async()=>root.unmount());root=createRoot(host);await act(async()=>root.render(<RecentInvestigations/>));
  expect(host.querySelector('a')).not.toBeNull();expect(fetcher).toHaveBeenCalledTimes(2);
});
it('distinguishes locally recorded real execution from explicit provider-skipped experimental jobs',async()=>{
  vi.stubGlobal('fetch',async()=>Response.json({jobs:[
    {...job,execution:{mode:'real',note:'Local provider records'}},
    {...job,job_id:'mock',execution:{mode:'experimental',note:'No paid call'}}]}));
  await act(async()=>root.render(<RecentInvestigations/>));
  expect(host.textContent).toContain('Real Analysis · saved outputs');
  expect(host.textContent).toContain('Experimental · execution unconfirmed');
});
it('shows accurate missing and dry-run states without a restart button',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({jobs:[{...job,can_open:false,availability_error:'Missing saved camera video. No analysis was started.'},
    {...job,job_id:'dry',analysis_type:'dry_run',outcome:'success'}]})));
  await act(async()=>root.render(<RecentInvestigations/>));
  expect(host.textContent).toContain('Missing saved camera video');expect(host.querySelector('button[disabled]')).not.toBeNull();
  expect(host.textContent).toContain('No physical conclusions · Dry Run');expect(host.textContent).not.toContain('Success · saved verdict');
});
it('handles empty history and an unavailable backend',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({jobs:[]})));await act(async()=>root.render(<RecentInvestigations/>));
  expect(host.textContent).toContain('No saved investigations found');
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('',{status:503})));
  await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='Refresh investigations')!.click());
  expect(host.querySelector('[role=alert]')?.textContent).toContain('backend connection');
});
