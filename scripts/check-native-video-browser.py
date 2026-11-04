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
                    if await js('!!document.body && ('+code+')'):return
                    await asyncio.sleep(.1)
                raise AssertionError(code)
            async def check(name,code):
                if not await js(code):
                    (a.output/'failed-page.txt').write_text(str(await js("location.href+'\\n'+document.body.innerText")),encoding='utf-8')
                    png=await call('Page.captureScreenshot',dict(format='png'));(a.output/'failed-page.png').write_bytes(base64.b64decode(png['data']))
                    raise AssertionError(name)
                checks.append(name)
            await call('Page.enable');await call('Runtime.enable');await call('Network.enable')
            await call('Page.navigate',dict(url=a.url+'/#job/'+a.failure_job))
            await wait("document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE')")
            await check('mock remains explicitly labeled, original final finding preserved',"document.body.innerText.includes('Visible final-placement failure') && document.body.innerText.includes('Unverified model description: MOCK') && document.body.innerText.includes('Mock proposals · real footage')")
            await check('three proposal statuses remain separate from descriptions',"document.querySelector('[aria-label=\"Proposal P0\"]').innerText.includes('UNVERIFIED') && document.querySelector('[aria-label=\"Proposal P1\"]').innerText.includes('SUPPORTED') && document.querySelector('[aria-label=\"Proposal P2\"]').innerText.includes('CONTRADICTED')")
            await check('no post-verification Muse execution is claimed',"document.body.innerText.includes('No post-verification Muse explanation request')")
            await check('onset and physical cause remain unknown',"document.body.innerText.includes('Original failure onset: Unknown. Physical cause: UNVERIFIED')")
            await js("document.querySelector('[aria-label=\"Proposal P0\"] button').click()")
            await wait("Math.abs(document.querySelector('video').currentTime-23.211111111)<.04 && document.querySelector('video').readyState>=2")
            checks.append('model proposal seeks original native time, not final failure time')
            await js("[...document.querySelectorAll('[aria-label=\"Proposal P1\"] button')].find(b=>b.textContent.startsWith('Verified relation only')).click()")
            await wait("Math.abs(document.querySelector('video').currentTime-69.133333333)<.04")
            checks.append('independent relation seeks verified final interval')
            await js("document.querySelector('[aria-label=\"Native video event proposals\"]').scrollIntoView({block:'start'})")
            png=await call('Page.captureScreenshot',dict(format='png'));(a.output/'proposals.png').write_bytes(base64.b64decode(png['data']))
            await js("[...document.querySelectorAll('summary')].find(s=>s.textContent==='Source frames, masks and measurement limitations').click()")
            await js("[...document.querySelectorAll('[aria-label=\"Proposal P0\"] button')].find(b=>b.textContent.startsWith('Inspect original frame')).click()")
            await wait("document.querySelector('img[alt^=\"Original source frame\"]')?.complete && document.querySelector('img[alt^=\"Original source frame\"]')?.naturalWidth===640")
            await check('proposal endpoints have original source image citations',"document.querySelector('img[alt^=\"Original source frame\"]').alt==='Original source frame 696'")
            await js("document.querySelector('img[alt^=\"Original source frame\"]').scrollIntoView({block:'center'})")
            png=await call('Page.captureScreenshot',dict(format='png'));(a.output/'source-frame.png').write_bytes(base64.b64decode(png['data']))
            await js('window.__nativeReloadMarker=true')
            await call('Page.reload');await wait("!window.__nativeReloadMarker && document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE') && document.body.innerText.includes('checked relation SUPPORTED')")
            await check('saved native investigation reopens after refresh',"document.body.innerText.includes('checked relation SUPPORTED')")
            await call('Page.navigate',dict(url=a.url+'/#job/'+a.control_job));await wait("document.body.innerText.includes('OFFLINE MOCK MODEL RESPONSE') && document.body.innerText.includes('No supported outside-rack finding')")
            await check('control abstains and never claims success',"document.body.innerText.includes('No supported outside-rack finding') && !document.body.innerText.includes('checked relation SUPPORTED') && !document.body.innerText.includes('checked relation CONTRADICTED')")
            await wait("document.querySelector('video')?.readyState>=2 && !document.querySelector('video').seeking")
            await check('control original video decodes visible pixels',"(()=>{const v=document.querySelector('video'),c=document.createElement('canvas');c.width=64;c.height=48;const x=c.getContext('2d');x.drawImage(v,0,0,64,48);return x.getImageData(0,0,64,48).data.some((n,i)=>i%4!==3&&n>80);})()")
            await js("document.querySelector('[aria-label=\"Native video event proposals\"]').scrollIntoView({block:'start'})")
            png=await call('Page.captureScreenshot',dict(format='png'));(a.output/'control.png').write_bytes(base64.b64decode(png['data']))
            assert not errors,errors
            assert all(r['method']=='GET' and r['url'].startswith(a.url) for r in requests),requests
            checks.append('no POST, provider request, or external network access on view/refresh')
            (a.output/'results.json').write_text(json.dumps(dict(passed=True,checks=checks,requests=[dict(method=r['method'],url=r['url']) for r in requests],errors=errors),indent=2))
            print(json.dumps(dict(passed=True,checks=checks)))
    finally:proc.terminate();proc.wait(timeout=15)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:18896');p.add_argument('--debug-port',type=int,default=9236)
    p.add_argument('--chrome',default='C:/Program Files/Google/Chrome/Application/chrome.exe');p.add_argument('--failure-job',required=True)
    p.add_argument('--control-job',required=True);p.add_argument('--output',type=Path,required=True)
    asyncio.run(run(p.parse_args()))
