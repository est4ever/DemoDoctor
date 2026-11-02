import { beforeEach,vi } from 'vitest';
// JSDOM cannot decode media. Native frame decoding is asserted in Chromium QA.
beforeEach(()=>{
  if(typeof HTMLMediaElement==='undefined')return;
  vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{});
  vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});
});
