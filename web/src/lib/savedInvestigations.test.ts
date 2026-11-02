import { afterEach,expect,it,vi } from "vitest";
import { loadSavedInvestigation, savedJobHref } from "./savedInvestigations";
afterEach(()=>vi.unstubAllGlobals());
it('reopens with one GET and preserves returned evidence and criteria',async()=>{
  const result={analysis:{task_outcome:'uncertain',criteria:{assessments:[{name:'close the drawer',state:'unverified'}]},evidence_catalog:[{evidence_id:'E4'}]},tracks:{frames:{}}};
  const fetcher=vi.fn(async()=>Response.json(result));vi.stubGlobal('fetch',fetcher);
  expect(await loadSavedInvestigation('saved-job')).toEqual(result);
  expect(fetcher).toHaveBeenCalledExactlyOnceWith('/api/jobs/saved-job/reopen',{method:'GET',signal:undefined});
  expect(savedJobHref('saved-job')).toBe('#job/saved-job');
});
it('does not fall back to starting inference on unavailable artifacts',async()=>{
  const fetcher=vi.fn(async()=>Response.json({detail:'Missing saved video.mp4. No analysis was started.'},{status:409}));vi.stubGlobal('fetch',fetcher);
  await expect(loadSavedInvestigation('saved-job')).rejects.toThrow('Missing saved video.mp4');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('rejects invalid identifiers and non-API responses',async()=>{
  const fetcher=vi.fn(async()=>new Response('<html/>'));vi.stubGlobal('fetch',fetcher);
  await expect(loadSavedInvestigation('../private')).rejects.toThrow('Invalid');expect(fetcher).not.toHaveBeenCalled();
  await expect(loadSavedInvestigation('saved-job')).rejects.toThrow('local backend');
});
it('allows original provider-skipped dry runs without fabricated SAM tracks',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({analysis:{dry_run:true},tracks:null})));
  expect((await loadSavedInvestigation('old-dry-run')).tracks).toBeNull();
});
