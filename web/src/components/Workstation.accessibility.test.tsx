// @vitest-environment jsdom
import {act} from 'react';
import {createRoot,type Root} from 'react-dom/client';
import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import App from '../App';
import {NavigationLink} from './ui';
vi.mock('./VideoPane',()=>({VideoPane:({t}:{t:number})=><output data-time={t}/> }));
let host:HTMLDivElement,root:Root;
beforeEach(()=>{
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);sessionStorage.clear();localStorage.clear();
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
  history.replaceState({},'','/#ep005?t=12');
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    const relative=url.startsWith('/criteria/')?'public'+url:'public'+url;
    const file=resolve(relative);return new Response(existsSync(file)?readFileSync(file,'utf8'):'{}',{status:existsSync(file)?200:404,headers:{'content-type':'application/json'}});
  }));
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
it('lets summary and link keys keep their native behavior instead of starting playback',async()=>{
  await act(async()=>root.render(<App/>));
  const summary=host.querySelector<HTMLElement>('.hypothesis-sources > summary')!;
  const space=new KeyboardEvent('keydown',{key:' ',code:'Space',bubbles:true,cancelable:true});
  await act(async()=>summary.dispatchEvent(space));
  expect(space.defaultPrevented).toBe(false);
  expect(host.querySelector('[aria-label=Play]')).not.toBeNull();
  expect(host.querySelector('[data-time]')!.getAttribute('data-time')).toBe('12');
});
it('provides real navigation links, a working skip link and context-specific titles',async()=>{
  await act(async()=>root.render(<App/>));
  expect(host.querySelector('.session-list [aria-label^="Open EP010"]')?.getAttribute('href')).toBe('#ep010');
  expect(document.title).toBe('EP005 investigation · DemoDoctor');
  await act(async()=>host.querySelector<HTMLAnchorElement>('.skip-link')!.click());
  expect(document.activeElement).toBe(host.querySelector('main'));
  expect(location.hash).toBe('#ep005?t=12');
});
it('does not depend on a later hashchange event to replace the current episode and sources',async()=>{
  const add=window.addEventListener.bind(window);
  vi.spyOn(window,'addEventListener').mockImplementation((type,listener,options)=>{if(type!=='hashchange')add(type,listener,options);});
  await act(async()=>root.render(<App/>));
  expect(host.textContent).toContain('incorrectly oriented flat');
  await act(async()=>host.querySelector<HTMLAnchorElement>('.session-list [aria-label^="Open EP010"]')!.click());
  expect(host.querySelector('h1')!.textContent).toBe('EP010 investigation');
  expect(host.querySelector('.diagnostic-hypotheses')!.textContent).not.toContain('incorrectly oriented flat');
  expect(host.querySelector('.diagnostic-hypotheses')!.textContent).toContain('intentional release');
});
it('preserves modified-click browser navigation instead of intercepting it as an action',async()=>{
  const navigate=vi.fn();await act(async()=>root.render(<NavigationLink href="#ep010" onNavigate={navigate}>Open investigation</NavigationLink>));
  const modified=new MouseEvent('click',{button:0,ctrlKey:true,bubbles:true,cancelable:true});
  await act(async()=>host.querySelector('a')!.dispatchEvent(modified));
  expect(modified.defaultPrevented).toBe(false);expect(navigate).not.toHaveBeenCalled();
  await act(async()=>host.querySelector('a')!.click());expect(navigate).toHaveBeenCalledOnce();
});
it('explains a genuinely empty dry-run catalog instead of blaming search filters',async()=>{
  const transport=fetch;
  vi.stubGlobal('fetch',async(url:string)=>{
    const r=await transport(url);if(!url.endsWith('analysis.json'))return r;
    const a=await r.json();return Response.json({...a,dry_run:true,evidence_catalog:[],hypotheses:[]});
  });
  await act(async()=>root.render(<App/>));
  await act(async()=>host.querySelector<HTMLButtonElement>('#inspector-tab-Evidence')!.click());
  expect(host.querySelector('.empty-state')!.textContent).toContain('Dry Run skipped SAM and Muse');
  expect(host.querySelector('.empty-state')!.textContent).not.toContain('Try another search');
});
