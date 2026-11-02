// @vitest-environment jsdom
import {act} from 'react';
import {createRoot,type Root} from 'react-dom/client';
import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import App from '../App';
import {VideoPane} from './VideoPane';
vi.mock('./AnnotatedVideoOverlay',()=>({AnnotatedVideoOverlay:()=> <canvas/>}));
let host:HTMLDivElement,root:Root;
beforeEach(()=>{
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);sessionStorage.clear();localStorage.clear();
  Object.defineProperty(window,'innerWidth',{value:390,configurable:true});
  vi.spyOn(HTMLElement.prototype,'getClientRects').mockReturnValue([{}] as unknown as DOMRectList);
  vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});
  vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue();
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
  history.replaceState({},'','/#ep005');
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    const p=resolve('public'+url);return new Response(existsSync(p)?readFileSync(p,'utf8'):'{}',{status:existsSync(p)?200:404});
  }));
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
it('keeps normal link Tab order in a narrow modal navigation drawer, wrapping only its actual end',async()=>{
  await act(async()=>root.render(<App/>));
  await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="Expand navigation"]')!.click());
  const home=host.querySelector<HTMLAnchorElement>('a[aria-label="DemoDoctor home"]')!;home.focus();
  const tab=new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true});
  await act(async()=>home.dispatchEvent(tab));
  expect(tab.defaultPrevented).toBe(false);
  const last=host.querySelector<HTMLAnchorElement>('.session-list a:last-child')!;last.focus();
  const wrap=new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true});
  await act(async()=>last.dispatchEvent(wrap));
  expect(wrap.defaultPrevented).toBe(true);
  expect(document.activeElement?.getAttribute('aria-label')).toBe('Reset navigation width');
});
it('shows the replay mode and preserves an Unverified mechanism instead of implying validated failure detection',async()=>{
  await act(async()=>root.render(<App/>));
  expect(host.querySelector('.local-tag')!.textContent).toContain('Saved analysis replay');
  expect(host.querySelector('.possible-mechanism .provenance')!.textContent).toContain('Unverified');
  expect(host.querySelector('[data-testid=task-outcome]')!.textContent?.toLowerCase()).toContain('uncertain');
});
it('shows one wrapping out-of-window notice outside the footage rather than duplicated overlays',async()=>{
  const tracks=JSON.parse(readFileSync(resolve('public/data/ep010/tracks.json'),'utf8'));
  await act(async()=>root.render(<VideoPane src="/test.mp4" tracks={tracks} mode="sam" onModeChange={()=>{}} t={0} playing={false} onDuration={()=>{}}/>));
  const notice=host.querySelector('.sam-window-notice')!;
  expect(notice.textContent).toContain('no detections invented');
  expect(host.querySelector('.video-frame')!.contains(notice)).toBe(false);
  expect(host.querySelector('.video-frame')!.textContent).not.toContain('Outside');
  expect(host.querySelectorAll('.sam-window-notice')).toHaveLength(1);
});
