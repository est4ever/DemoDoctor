"""Bounded native Meta Muse adapter using the existing SDK factory and ledger.

One upload + one native-video Responses request per approved plan. No retries,
SAM calls, model fallback, paid refinement or automatic explanation requests.
"""
import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
import av
import numpy as np
import httpx
import sam_api
import tracking
import live_budget
from . import service,video_events as V
from .support import need,read,write,sha,index

ROOT=Path(__file__).resolve().parents[1]
PLANS=ROOT/'data/native_video_plans'
PILOT_TASK='Place all dishes in the rack'
PILOT_GOAL='All required dishes are in the rack'


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def implementation():
    paths=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.json'),
           *(ROOT/f for f in ('sam_api.py','tracking.py','live_budget.py','requirements-lock.txt'))]
    return hashlib.sha256(canonical({str(p.relative_to(ROOT)):sha(p) for p in paths})).hexdigest()


def execution_seal(directory,create=False):
    files={p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.name!='execution-seal.json'}
    key=service.secret(directory.parent,create)
    signature=hmac.new(key,canonical(files),hashlib.sha256).hexdigest()
    if create:write(directory/'execution-seal.json',dict(files=files,signature=signature))
    else:
        sealed=read(directory/'execution-seal.json')
        need(files==sealed['files'] and hmac.compare_digest(signature,sealed['signature']),'Unregistered or altered native execution artifact')


def prepare(parent,task,desired,root=PLANS):
    parent=Path(parent).resolve();verified=service.verify(parent)
    need(3<=len(task)<=2000 and 3<=len(desired)<=2000,'Task and desired condition required')
    if verified.get('native_upload'):
        original=read(parent/'request.json')
        need(task==original['task_description'] and desired==original['desired_end_state'],'Task changed after source preparation')
        need(not verified['failure_detected'] and not verified['observed_evidence'] and verified['time_interval'] is None,'New upload cannot inherit assisted evidence')
    else:
        need(task==PILOT_TASK and desired==PILOT_GOAL,'This pilot verifies only the approved dish-to-rack task. Other task criteria remain unsupported.')
    root.mkdir(parents=True,exist_ok=True);directory=root/('native-'+uuid.uuid4().hex[:16]);directory.mkdir()
    shutil.copyfile(parent/'video.mp4',directory/'source.mp4')
    source=index(directory/'source.mp4',verified['source_sha256'])
    need(source==read(parent/'source_index.json') and source['frames'][0]['timestamp_s']==0,'Original camera/frame origin binding mismatch')
    with av.open(str(directory/'source.mp4')) as container:
        need(len(container.streams.video)==1 and not container.streams.audio,'Pilot accepts one silent video stream only')
    converted=tracking.ensure_h264_mp4((directory/'source.mp4').read_bytes())
    shutil.copyfile(converted,directory/'video.mp4')
    with av.open(str(directory/'video.mp4')) as container:
        need(container.streams.video[0].codec_context.name=='h264' and (directory/'video.mp4').stat().st_size<=1024**3,'Unsupported upload codec/size')
    upload=index(directory/'video.mp4',sha(directory/'video.mp4'))
    need(all(source[k]==upload[k] for k in ('n_frames','width','height','fps')),'Upload changed video scope')
    mapping=[]
    with av.open(str(directory/'source.mp4')) as a,av.open(str(directory/'video.mp4')) as b:
        for f,(x,y) in enumerate(zip(a.decode(video=0),b.decode(video=0))):
            xr=x.to_ndarray(format='rgb24');yr=y.to_ndarray(format='rgb24')
            error=float(np.abs(xr.astype(float)-yr.astype(float)).mean())
            need(source['frames'][f]['timestamp_s']==upload['frames'][f]['timestamp_s'] and error<=20,'Unverified derivative mapping')
            mapping.append(dict(source=source['frames'][f],upload=upload['frames'][f],mean_abs_rgb_difference=error))
    need(len(mapping)==source['n_frames'],'Incomplete derivative')
    write(directory/'source_index.json',source);write(directory/'upload_index.json',upload);write(directory/'frame_mapping.json',mapping)
    plan=dict(schema='demodoctor.native-video-plan/v1',plan_id=directory.name,provider='Meta Model API',model=V.MODEL,
        source_sha256=source['source_sha256'],upload_sha256=upload['source_sha256'],upload_bytes=(directory/'video.mp4').stat().st_size,
        upload_filename='video.mp4',frame_count=source['n_frames'],last_source_timestamp=source['frames'][-1]['timestamp_s'],
        task_description=task,desired_end_state=desired,operations=['upload','video_proposals'],max_output_tokens=V.MAX_OUTPUT,
        reservation_usd=V.RESERVATION,source_index_sha256=sha(directory/'source_index.json'),
        upload_index_sha256=sha(directory/'upload_index.json'),frame_mapping_sha256=sha(directory/'frame_mapping.json'),
        parent_job=str(parent),parent_seal_sha256=sha(parent/'placement-seal.json'),implementation_sha256=implementation(),
        provider_sampling='Full-duration H.264 derivative supplied with original-frame mapping; provider-defined native sampling, no silent truncation.',
        refinement='Offline candidate-only original-frame verification. No additional paid refinement request.',
        pricing={'input_per_million':1.25,'output_per_million':4.25,'context_upper_bound':1048576,
                 'conservative_request_bound':(1048576*1.25+V.MAX_OUTPUT*4.25)/1e6,
                 'expected_cost':'Unknown before native video token usage; this is a conservative reservation, not expected charge.'})
    write(directory/'plan.json',plan)
    write(directory/'request-preview.json',V.request(task,desired,source,'FILE_ID_FROM_THIS_UPLOAD_ONLY'))
    return directory,plan


def check_plan(directory):
    p=read(directory/'plan.json')
    need(p['implementation_sha256']==implementation(),'Frozen implementation changed')
    need(p['operations']==['upload','video_proposals'] and p['model']==V.MODEL and p['reservation_usd']==V.RESERVATION,'Plan scope changed')
    for file,key in [('source.mp4','source_sha256'),('video.mp4','upload_sha256'),('source_index.json','source_index_sha256'),
                     ('upload_index.json','upload_index_sha256'),('frame_mapping.json','frame_mapping_sha256')]:
        need(sha(directory/file)==p[key],'Frozen input changed: '+file)
    parent=Path(p['parent_job']);need(sha(parent/'placement-seal.json')==p['parent_seal_sha256'],'Verification source changed')
    need(service.verify(parent)['source_sha256']==p['source_sha256'],'Verification source mismatch')
    return p,read(directory/'source_index.json')


def admission(directory,owner,ledger):
    p,s=check_plan(directory)
    for flag in ('paid_authorized','agent1_accepted','eligible_meta_muse_credits','exclusive_account_usage',
                 'prior_requests_reconciled','dataset_processing_permitted','estimate_not_provider_hard_cap_accepted'):
        need(owner.get(flag) is True,'Authorization/readiness gate missing: '+flag)
    need(owner.get('implementation_sha256')==implementation() and sha(directory/'plan.json') in owner.get('plan_sha256s',[]),'Approval not bound to this plan/code')
    need(1<=len(owner['plan_sha256s'])<=2 and len(set(owner['plan_sha256s']))==len(owner['plan_sha256s']) and owner.get('max_total_usd',0)<=2.66,'Pilot limited to two distinct plans and $2.66')
    need(owner.get('max_per_plan_usd')==V.RESERVATION and len(owner['plan_sha256s'])*V.RESERVATION<=owner.get('max_total_usd',0)+1e-9,'Approval reservation mismatch')
    need(time.time()<owner.get('expires_at',0)<=time.time()+86400,'Approval expired or unbounded')
    need(ledger.is_file() and str(ledger.resolve())==owner.get('ledger_path'),'Existing accounting ledger required')
    d=read(ledger)
    need(not d['reservations'] and d['reserved_usd']==0 and not any(e.get('actual_usd') is None and not e.get('from_cache') for e in d['events']),'Unresolved spending blocks execution')
    need(V.RESERVATION<=d['per_run_budget_usd'] and d['spent_usd']+V.RESERVATION<=min(d['total_budget_usd'],4.5),'Existing per-run/project/experiment budget admission failed')
    need(not any(e.get('job_id')==p['plan_id'] for e in d['events']),'Plan already accounted; no repeat')
    return p,s


def file_identity(d,p):
    need(isinstance(d.get('id'),str) and re.fullmatch(r'file-[0-9]+',d['id']),'Invalid file ID')
    need(d.get('object')=='file' and d.get('bytes')==p['upload_bytes'] and d.get('filename')=='video.mp4' and d.get('purpose')=='user_data','Mismatched upload metadata')
    need(d.get('status') in ('uploaded','processed') and not d.get('status_details') and not d.get('error') and not d.get('deleted'),'Uncertain/error upload status')
    expires=d.get('expires_at')  # Absent/null means non-expiring in the Files API.
    need(type(d.get('created_at')) is int and 0<d['created_at']<=time.time()+60 and
         (expires is None or (type(expires) is int and expires>time.time())),'Invalid/expired upload metadata')
    return d['id']


async def execute(directory,owner,ledger,client,*,offline=False):
    """Offline mode requires real SDK MockTransport, never a cached model answer."""
    directory=Path(directory);ledger=Path(ledger);p,source=admission(directory,owner,ledger)
    need(str(client.base_url).rstrip('/')=='https://api.meta.ai/v1' and client.max_retries==0,'Wrong provider/retries')
    need(isinstance(client._client._transport,httpx.MockTransport)==offline,'Live/mock transport mismatch')
    claim=directory/'attempt.json'
    with claim.open('x',encoding='utf-8') as f:json.dump({'started':time.time(),'mode':'offline_mock' if offline else 'genuine_native_video','plan_sha256':sha(directory/'plan.json')},f)
    active=ledger.parent/'.native-video-active.lock'
    with active.open('x',encoding='utf-8') as f:json.dump({'plan_id':p['plan_id']},f)
    live_budget.LEDGER_PATH=ledger;rid=None;committed=False;sent=[];expected=None
    async def wire(request):
        nonlocal expected
        need(time.time()<owner['expires_at'] and implementation()==p['implementation_sha256'],'Approval/code changed before transmission')
        pending=read(ledger)['reservations'].get(rid,{})
        need(pending.get('job_id')==p['plan_id'] and pending.get('estimated_usd')==V.RESERVATION,'Reservation missing or changed before transmission')
        need(request.method=='POST' and str(request.url)==('https://api.meta.ai/v1/files' if len(sent)==0 else 'https://api.meta.ai/v1/responses') and len(sent)<2,'Unauthorized endpoint/duplicate operation')
        body=await request.aread()
        if len(sent)==0:
            from email.parser import BytesParser
            message=BytesParser().parsebytes(b'Content-Type: '+request.headers['content-type'].encode()+b'\r\nMIME-Version: 1.0\r\n\r\n'+body)
            fields={part.get_param('name',header='content-disposition'):part for part in message.get_payload()}
            need(set(fields)=={'file','purpose'} and fields['purpose'].get_payload(decode=True)==b'user_data','Wrong upload parts')
            need(fields['file'].get_filename()=='video.mp4' and hashlib.sha256(fields['file'].get_payload(decode=True)).hexdigest()==p['upload_sha256'],'Transmitted upload bytes changed')
        else:need(json.loads(body)==expected,'Unapproved response request')
        sent.append({'method':request.method,'url':str(request.url),'body_sha256':hashlib.sha256(body).hexdigest(),'started':time.time()})
        write(directory/'operations.json',{'sent':sent,'state':'execution_pending'})
    client._client.event_hooks['request']=[wire]
    async def saved(raw,name):
        response=raw.http_response;body=response.content
        (directory/(name+'.body')).write_bytes(body)
        write(directory/(name+'-receipt.json'),dict(http_status=response.status_code,request_id=response.headers.get('x-request-id'),body_sha256=hashlib.sha256(body).hexdigest(),received=time.time()))
        need(response.status_code==200,'Non-success provider HTTP response')
        return json.loads(body)
    try:
        rid=live_budget.reserve(p['plan_id'],V.RESERVATION,note='One native Meta Muse video request; upload included, no retry. Reservation is not provider-confirmed charge.')
        upload=(directory/'video.mp4').read_bytes()
        u=await saved(await client.files.with_raw_response.create(file=('video.mp4',upload,'video/mp4'),purpose='user_data'),'upload')
        fid=file_identity(u,p);check_plan(directory)
        expected=V.request(p['task_description'],p['desired_end_state'],source,fid)
        write(directory/'actual-request.json',expected)
        raw=await saved(await client.responses.with_raw_response.create(**expected),'response')
        usage=raw.get('usage',{})
        need(raw.get('status')=='completed' and raw.get('error') is None and raw.get('model')==V.MODEL and
             isinstance(raw.get('id'),str) and raw['id'],'Uncertain model completion/identity; charge cannot be priced as the approved model')
        need(all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens','total_tokens')) and
             usage['total_tokens']==usage['input_tokens']+usage['output_tokens'] and usage['input_tokens']<=1048576 and usage['output_tokens']<=V.MAX_OUTPUT,'Unknown or over-bound usage')
        cost=(usage['input_tokens']*1.25+usage['output_tokens']*4.25)/1e6
        need(cost<=V.RESERVATION,'Provider-reported usage exceeds reserved cost')
        live_budget.commit(rid,provider='meta_muse_spark',kind='native_video',actual_usd=cost,
            usage=dict(provider_usage=usage,charge_basis='Uncached published-rate calculation; invoice NOT verified',response_id=raw.get('id')),
            note='Rate-derived accounting value, not provider-confirmed dollar charge. Raw usage retained.')
        committed=True
        parsed=V.parse_response(raw,source)
        parent=Path(p['parent_job']);final=service.verify(parent)
        assessed=V.verify(parsed,source,final,read(parent/'placement-measurements.json'))
        write(directory/'assessment.json',assessed)
        write(directory/'accounting.json',dict(provider_usage=usage,rate_derived_usd=cost,provider_confirmed_charge_usd=None,reservation_usd=V.RESERVATION,
            mode='offline_mock' if offline else 'genuine_native_video'))
        write(directory/'operations.json',{'sent':sent,'state':'completed','file_id':fid,'response_id':raw['id'],'mode':'offline_mock' if offline else 'genuine_native_video'})
        execution_seal(directory,True)
        active.unlink()  # Only a verified completed operation releases this exclusive lock.
        return assessed
    except Exception as error:
        response=getattr(error,'response',None)
        if isinstance(response,httpx.Response):
            (directory/'error-response.body').write_bytes(response.content)
            write(directory/'error-response-receipt.json',dict(http_status=response.status_code,request_id=response.headers.get('x-request-id'),body_sha256=hashlib.sha256(response.content).hexdigest()))
        if rid and not committed:
            if len(sent)<2:
                live_budget.release(rid,note='No model request admitted for transmission. Upload status may require reconciliation; attempt remains blocked, no retry.')
            else:
                live_budget.commit(rid,provider='meta_muse_spark',kind='uncertain_native_video_attempt',actual_usd=None,
                    note='STOP: execution/accounting requires manual reconciliation; no retry.',usage={'error_type':type(error).__name__})
        write(directory/'STOP.json',dict(error_type=type(error).__name__,message=str(error),sent_operations=len(sent),retry_permitted=False))
        raise
