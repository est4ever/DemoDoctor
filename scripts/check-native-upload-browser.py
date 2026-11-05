"""Focused local Chromium check of sealed mock proposals in the existing app."""
import argparse
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import urllib.request
import websockets


async def run(a):
    a.output=a.output.resolve()
    a.output.mkdir(parents=True,exist_ok=False)
    proc=subprocess.Popen([a.chrome,'--headless','--disable-gpu','--disable-background-networking','--disable-component-update',
        '--no-first-run','--disable-extensions','--remote-debugging-port='+str(a.debug_port),
        '--user-data-dir='+str(a.output/'profile'),'--window-size=1600,1100','about:blank'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    checks=[];requests=[];errors=[];counter=0
    try:
        for _ in range(100):
            try:
                targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{a.debug_port}/json',timeout=1))
                target=next(t for t in targets if t['type']=='page');break
            except Exception:await asyncio.sleep(.1)
        async with websockets.connect(target['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
            async def call(method,params=None):
                nonlocal counter
                counter+=1;ident=counter;await ws.send(json.dumps(dict(id=ident,method=method,params=params or {})))
                while True:
                    v=json.loads(await ws.recv())
                    if v.get('method')=='Network.requestWillBeSent':requests.append(v['params']['request'])
                    if v.get('method')=='Runtime.exceptionThrown':errors.append(v['params'])
                    if v.get('id')==ident:
                        assert 'error' not in v,v
                        return v.get('result',{})
            async def js(code):
                r=await call('Runtime.evaluate',dict(expression=code,returnByValue=True,awaitPromise=True))
                assert 'exceptionDetails' not in r,r
                return r.get('result',{}).get('value')
            async def wait(code):
                for _ in range(400):
                    if await js('!!document.body && Boolean('+code+')'):return
                    await asyncio.sleep(.1)
                raise AssertionError(code)
            async def check(name,code):
                if not await js(code):
                    (a.output/'failed-page.txt').write_text(str(await js("location.href+'\\n'+document.body.innerText")),encoding='utf-8')
                    png=await call('Page.captureScreenshot',dict(format='png'));(a.output/'failed-page.png').write_bytes(base64.b64decode(png['data']))
                    raise AssertionError(name)
                checks.append(name)

            async def shot(name):
                png=await call('Page.captureScreenshot',dict(format='png'));(a.output/(name+'.png')).write_bytes(base64.b64decode(png['data']))
            await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('DOM.enable')
            await call('Page.navigate',dict(url=a.url+'/#job/'+a.saved_job))
            await wait("document.body.innerText.includes('GENUINE NATIVE-VIDEO MODEL RESPONSE')")
            await check('saved genuine BF010 available in actual findings',"document.body.innerText.includes('Visible final-placement failure') && document.body.innerText.includes('39.500')")
            await check('verified placement summary replaces generic missing measurement fallback',"!document.querySelector('[aria-label=\"Investigation findings summary\"]').innerText.includes('No source-bound image-space measurement') && document.querySelector('[aria-label=\"Investigation findings summary\"]').innerText.includes('outside')")
            await js("document.querySelector('[aria-label=\"Proposal P6\"] button').click()")
            await wait("document.querySelector('video')?.readyState>=2 && Math.abs(document.querySelector('video').currentTime-39.5)<.05")
            checks.append('saved genuine BF010 video decodes and seeks its original drop proposal')
            await js("document.querySelector('[aria-label=\"Native video event proposals\"]').scrollIntoView({block:'start'})")
            await shot('saved-genuine')
            await js("document.querySelector('[aria-label=\"Import footage\"]').click()")
            await wait("document.querySelector('[aria-label=\"Experimental Native Video Analysis\"]') && document.body.innerText.includes('OFFLINE MOCK')")
            await wait("!document.querySelector('[aria-label=\"Recent Investigations\"]').innerText.includes('Loading saved investigations')")
            await js("[...document.querySelectorAll('[aria-label=\"Recent Investigations\"] button')].find(b=>b.textContent.startsWith('Show all'))?.click()")
            await wait("document.querySelector('[data-saved-job=\"'+"+json.dumps(a.saved_job)+"+'\"]')")
            await check('visible saved genuine replay entry on Import Footage',"document.querySelector('[data-saved-job=\"'+"+json.dumps(a.saved_job)+"+'\"]').innerText.includes('Saved genuine Meta Muse video analysis')")
            doc=await call('DOM.getDocument');node=await call('DOM.querySelector',dict(nodeId=doc['root']['nodeId'],selector='input[aria-label="Native video MP4"]'))
            await call('DOM.setFileInputFiles',dict(nodeId=node['nodeId'],files=[str(a.video.resolve())]))
            await js("(()=>{for(const [name,text] of [['Native robot task','Place the dishes in the rack'],['Native intended end state','All required dishes are in the rack']]){const e=document.querySelector('textarea[aria-label=\"'+name+'\"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,text);e.dispatchEvent(new Event('input',{bubbles:true}));}})()")
            await shot('import-new-video')
            await js("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Prepare native video plan')).click()")
            await wait("document.querySelector('[aria-label=\"Native analysis approval\"]')")
            await check('full video and original/upload hashes displayed',"document.querySelector('[aria-label=\"Native analysis approval\"]').innerText.includes('2090 original frames') && document.body.innerText.includes('H.264 upload SHA-256') && document.body.innerText.includes('$1.33')")
            await check('execution disabled before consent',"[...document.querySelectorAll('button')].find(b=>b.textContent==='Run offline mock native analysis').disabled")
            assert not any('/execute' in r['url'] for r in requests)
            checks.append('no execution request during upload/preparation')
            await js("document.querySelector('[aria-label=\"Native analysis approval\"]').scrollIntoView({block:'start'})")
            await shot('plan-approval')
            await js("document.querySelectorAll('[aria-label=\"Native analysis approval\"] input[type=checkbox]').forEach(e=>e.click())")
            await wait("![...document.querySelectorAll('button')].find(b=>b.textContent==='Run offline mock native analysis').disabled")
            await js("[...document.querySelectorAll('button')].find(b=>b.textContent==='Run offline mock native analysis').click()")
            await wait("document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE') && document.body.innerText.includes('Experimental native-video investigation')")
            new_job=await js("location.hash.slice(5)")
            await check('new upload has mock proposals, not assisted or genuine claims',"document.body.innerText.includes('Task outcome Uncertain') && !document.body.innerText.includes('Visible final-placement failure') && !document.body.innerText.includes('GENUINE NATIVE-VIDEO MODEL RESPONSE')")
            await check('all three mock proposals remain Unverified',"document.querySelectorAll('[aria-label^=\"Proposal P\"]').length===3 && [...document.querySelectorAll('[aria-label^=\"Proposal P\"]')].every(e=>e.innerText.includes('checked relation UNVERIFIED'))")
            await js("document.querySelector('[aria-label=\"Proposal P0\"] button').click()")
            await wait("document.querySelector('video')?.readyState>=2 && Math.abs(document.querySelector('video').currentTime-23.211111111)<.05")
            checks.append('proposal seeks original source time')
            await js("document.querySelector('[aria-label=\"Native video event proposals\"]').scrollIntoView({block:'start'})")
            await shot('new-upload-mock-findings')
            await js("[...document.querySelectorAll('summary')].find(s=>s.textContent==='Source frames, masks and measurement limitations').click()")
            await js("[...document.querySelectorAll('[aria-label=\"Proposal P0\"] button')].find(b=>b.textContent.startsWith('Inspect original frame')).click()")
            await wait("document.querySelector('img[alt^=\"Original source frame\"]')?.naturalWidth===640")
            await check('source frame citation and missing geometry explicit',"document.querySelector('img[alt^=\"Original source frame\"]').alt==='Original source frame 696' && document.body.innerText.includes('No segmentation or event measurement is registered')")
            await js("document.querySelector('img[alt^=\"Original source frame\"]').scrollIntoView({block:'center'})")
            await shot('new-source-evidence')
            before_posts=len([r for r in requests if r['method']=='POST'])
            await js('window.__nativeReloadMarker=true');await call('Page.reload')
            await wait("!window.__nativeReloadMarker && document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE')")
            checks.append('refresh restores saved mock investigation')
            await js("document.querySelector('[aria-label=\"Import footage\"]').click()")
            await wait("document.querySelector('[data-saved-job=\"'+"+json.dumps(new_job)+"+'\"] a')")
            await check('newly saved investigation is first in recent history',"document.querySelector('[data-saved-job]').getAttribute('data-saved-job')==="+json.dumps(new_job))
            await js("document.querySelector('[data-saved-job=\"'+"+json.dumps(new_job)+"+'\"] a').click()")
            await wait("document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE')")
            assert len([r for r in requests if r['method']=='POST'])==before_posts
            checks.append('history reopening and refresh issue no further POST/inference')
            assert len([r for r in requests if '/execute' in r['url']])==1
            assert all(r['url'].startswith(a.url) for r in requests),requests
            assert not errors,errors
            checks.append('exactly one user execution POST; no browser provider/external requests or runtime errors')
            (a.output/'results.json').write_text(json.dumps(dict(passed=True,new_job=new_job,saved_genuine_job=a.saved_job,checks=checks,requests=[dict(method=r['method'],url=r['url']) for r in requests],errors=errors),indent=2))
            print(json.dumps(dict(passed=True,new_job=new_job,checks=checks)))
    finally:proc.terminate();proc.wait(timeout=15)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:18902');p.add_argument('--debug-port',type=int,default=9242)
    p.add_argument('--chrome',default='C:/Program Files/Google/Chrome/Application/chrome.exe')
    p.add_argument('--saved-job',default='placement-464e793f360e4e3f');p.add_argument('--video',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    asyncio.run(run(p.parse_args()))
