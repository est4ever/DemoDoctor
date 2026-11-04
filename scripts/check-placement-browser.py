"""Exercise the actual built React application in local Chromium; no inference.

Requires the existing local server and websockets (QA only, no app dependency).
"""
import argparse
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import websockets


async def run(args, out):
    profile=out/'chrome-profile'
    browser=subprocess.Popen([args.chrome,'--headless','--disable-gpu','--disable-background-networking','--disable-component-update',
        '--disable-extensions','--no-first-run','--no-default-browser-check','--disable-sync','--remote-debugging-port='+str(args.debug_port),
        '--user-data-dir='+str(profile),'--window-size=1600,1100','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    checks=[];requests=[];errors=[];counter=0
    try:
        for _ in range(100):
            try:
                targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{args.debug_port}/json'))
                target=next(t for t in targets if t['type']=='page');break
            except Exception:await asyncio.sleep(.1)
        async with websockets.connect(target['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
            async def call(method,params=None):
                nonlocal counter
                counter+=1;ident=counter
                await ws.send(json.dumps(dict(id=ident,method=method,params=params or {})))
                while True:
                    reply=json.loads(await ws.recv())
                    if reply.get('method')=='Network.requestWillBeSent':requests.append(reply['params']['request'])
                    if reply.get('method')=='Runtime.exceptionThrown':errors.append(reply['params'])
                    if reply.get('id')==ident:
                        if 'error' in reply:raise AssertionError(reply['error'])
                        return reply.get('result',{})
            async def js(code):
                r=await call('Runtime.evaluate',dict(expression=code,returnByValue=True,awaitPromise=True))
                if 'exceptionDetails' in r:raise AssertionError(r['exceptionDetails'])
                return r.get('result',{}).get('value')
            async def until(code):
                for _ in range(200):
                    if await js(code):return
                    await asyncio.sleep(.1)
                raise AssertionError('Timed out: '+code)
            async def check(label,code):
                assert await js(code),label
                checks.append(label)
            await call('Page.enable');await call('Runtime.enable');await call('Network.enable')
            await call('Page.navigate',dict(url=args.url+'/#ep010'))
            await until("!!document.querySelector('[aria-label=\"Placement source recording\"]')")
            if args.portable:
                await check('portable registration offers exactly the two provisioned originals',"fetch('/api/placement/options').then(r=>r.json()).then(o=>o.available && o.sources.map(s=>s.key).sort().join(',')==='bf000,ep010')")
            await check('existing investigation has assisted assessment control',"document.body.innerText.includes('Final-placement assessment')")
            await js("[...document.querySelectorAll('button')].find(b=>b.textContent==='Assess final placement offline').click()")
            await until("location.hash.startsWith('#job/placement-') && document.body.innerText.includes('Visible final-placement failure')")
            job=await js("location.hash.slice(5)")
            await check('new saved investigation contains final finding',"document.body.innerText.includes('minimum plate/rack separation 93 pixels')")
            await check('onset and cause are explicitly unavailable',"document.body.innerText.includes('Earlier failure onset: Unknown. Physical cause: Unverified.')")
            await check('Muse remains provider skipped',"document.body.innerText.includes('Muse: provider_skipped')")
            await js("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Seek failure evidence')).click()")
            await until("Math.abs(document.querySelector('video').currentTime-69.1333333333)<.04")
            await until("(()=>{const v=document.querySelector('video');return v.readyState>=2 && !v.seeking && v.videoWidth===640;})()")
            await check('original video decodes visible source pixels',"(()=>{const v=document.querySelector('video'),c=document.createElement('canvas');c.width=64;c.height=48;const x=c.getContext('2d');x.drawImage(v,0,0,64,48);const a=x.getImageData(0,0,64,48).data;return a.some((n,i)=>i%4!==3&&n>80);})()")
            checks.append('finding seeks original frame 2074 / 69.133333 seconds')
            await js("document.querySelector('.timeline-marker').click()")
            await until("document.querySelector('#inspector-tab-Evidence')?.getAttribute('aria-selected')==='true'")
            await check('existing timeline marker uses validated source citation',"Math.abs(document.querySelector('video').currentTime-69.1333333333)<.04")
            await js("document.querySelector('#inspector-tab-Findings').click()")
            await until("document.body.innerText.includes('Visible final-placement failure')")
            await js("[...document.querySelectorAll('summary')].find(s=>s.textContent==='Source frames, masks and measurement limitations').click()")
            await until("document.querySelector('img[alt^=\"Assisted plate candidates\"]')?.naturalWidth===640")
            await check('source and overlay images both load',"document.querySelector('img[alt=\"Original source frame 2074\"]').naturalWidth===640")
            await js("document.querySelector('[aria-label=\"Assisted final-placement assessment\"]').scrollIntoView({block:'start'})")
            await asyncio.sleep(.5)
            screenshot=await call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
            (out/'ep010.png').write_bytes(base64.b64decode(screenshot['data']))
            await js("document.querySelector('img[alt^=\"Assisted plate candidates\"]').scrollIntoView({block:'end'})")
            await asyncio.sleep(.2)
            screenshot=await call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
            (out/'ep010-masks.png').write_bytes(base64.b64decode(screenshot['data']))
            before=len([r for r in requests if r['method']=='POST'])
            await call('Page.reload')
            await until("document.body.innerText.includes('Visible final-placement failure')")
            await check('refresh restores saved assessment',"location.hash==='#job/'+"+json.dumps(job))
            assert len([r for r in requests if r['method']=='POST'])==before
            checks.append('refresh makes no POST or inference request')
            result=await js(f"fetch('/api/placement/jobs/{job}').then(r=>r.json())")
            (out/'ep010-result.json').write_text(json.dumps(result,indent=2))
            for key,expected in ([('bf000',False)] if args.portable else [('bf000',False),('so101',False)]):
                await call('Page.navigate',dict(url=args.url+'/#ep010'))
                await until("!!document.querySelector('[aria-label=\"Placement source recording\"]')")
                await js("(()=>{const s=document.querySelector('[aria-label=\"Placement source recording\"]');Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,"+json.dumps(key)+");s.dispatchEvent(new Event('change',{bubbles:true}));})()")
                await js("[...document.querySelectorAll('button')].find(b=>b.textContent==='Assess final placement offline').click()")
                await until("location.hash.startsWith('#job/placement-') && document.body.innerText.includes('No supported outside-rack finding.')")
                jid=await js('location.hash.slice(5)')
                r=await js(f"fetch('/api/placement/jobs/{jid}').then(r=>r.json())")
                assert r['failure_detected']==expected and r['time_interval'] is None
                (out/(key+'-result.json')).write_text(json.dumps(r,indent=2))
                checks.append(key+' computed through UI, no false failure claim')
            for key in ['ep003','ep005','ep006','ep010','ep013','pilot']:
                await call('Page.navigate',dict(url=args.url+'/#'+key))
                await until("!!document.querySelector('[aria-label=\"Placement source recording\"]')")
                await check(key+' original investigation still opens',"!document.body.innerText.includes('Investigation quarantined')")
            await call('Page.navigate',dict(url=args.url+'/#job/'+job))
            await until("document.body.innerText.includes('Visible final-placement failure')")
            assert not errors,errors
            assert all(r['url'].startswith(args.url) or r['url'].startswith('data:') for r in requests)
            assert all('/api/placement/assess/' in r['url'] for r in requests if r['method']=='POST')
            count=2 if args.portable else 3
            checks.append(f'only {count} explicit offline assessment POSTs; no provider operations')
            assert len([r for r in requests if r['method']=='POST'])==count
            receipt=dict(passed=True,checks=checks,job_id=job,requests=[dict(method=r['method'],url=r['url']) for r in requests],browser_errors=errors)
            (out/'browser-results.json').write_text(json.dumps(receipt,indent=2))
            print(json.dumps(dict(passed=True,checks=checks,job_id=job),indent=2))
    finally:
        browser.terminate();browser.wait(timeout=15)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:18890')
    p.add_argument('--chrome',default='C:/Program Files/Google/Chrome/Application/chrome.exe')
    p.add_argument('--debug-port',type=int,default=9228);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--portable',action='store_true',help='Check only the two publicly provisioned original recordings')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);asyncio.run(run(a,a.output.resolve()))
