"""Zero-network SDK replay. Responses below are MOCKS, never real predictions."""
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import time
import httpx
from openai import AsyncOpenAI
from placement_assessment import meta_video as M,video_integration as I
from placement_assessment.support import read,write,sha


def mock_response(source):
    end=source['frames'][-1]['timestamp_s']
    def event(kind,start,stop,relation):
        return dict(event_type=kind,proposed_start_time=start,proposed_end_time=stop,
            description='MOCK contract fixture: this is not a video-model prediction.',visible_evidence=['MOCK assertion only'],
            relevant_objects=['plate','rack'],uncertainty='Mock answer; no actual visual reasoning was performed.',
            alternative_interpretations=['Visibility may be insufficient'],relation=relation)
    data=dict(events=[event('drop',end/3,end/3+.1,'unknown'),
        event('final_position',max(0,end-.5),end,'some_task_object_outside_destination'),
        event('visible_task_criterion_violation',max(0,end-.5),end,'all_task_objects_inside_destination')],
        coverage_limitations=['OFFLINE MOCK: no provider processed this video.'])
    return dict(id='resp_mock_only',object='response',status='completed',error=None,model=M.V.MODEL,
        output=[dict(type='message',role='assistant',status='completed',content=[dict(type='output_text',text=json.dumps(data),annotations=[])])],
        usage=dict(input_tokens=1000,output_tokens=500,total_tokens=1500))


def mock_client(plan,source,mode='success',calls=None):
    calls=[] if calls is None else calls
    async def handler(request):
        calls.append(str(request.url))
        if request.url.path.endswith('/files'):
            if mode=='upload_error':return httpx.Response(400,json={'error':{'message':'mock rejected upload','type':'invalid_request_error'}})
            metadata=dict(id='file-12345',object='file',bytes=plan['upload_bytes'],filename='video.mp4',
                purpose='user_data',status='uploaded',created_at=int(time.time()),expires_at=None)
            if mode=='no_expiry':metadata.pop('expires_at')
            if mode=='future_expiry':metadata['expires_at']=int(time.time())+3600
            if mode=='expired_upload':metadata['expires_at']=int(time.time())-60
            if mode=='malformed_expiry':metadata['expires_at']='tomorrow'
            return httpx.Response(200,json=metadata)
        if mode=='interrupted':raise httpx.ReadError('Mock interrupted response',request=request)
        raw=mock_response(source)
        if mode=='incomplete':raw['status']='incomplete'
        if mode=='wrong_model':raw['model']='unapproved-model'
        return httpx.Response(200,json=raw,headers={'x-request-id':'mock-only'})
    return AsyncOpenAI(api_key='OFFLINE_NOT_A_KEY',base_url='https://api.meta.ai/v1',max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def mock_owner(directory,ledger):
    return dict(paid_authorized=True,agent1_accepted=True,eligible_meta_muse_credits=True,exclusive_account_usage=True,
        prior_requests_reconciled=True,dataset_processing_permitted=True,estimate_not_provider_hard_cap_accepted=True,
        implementation_sha256=M.implementation(),plan_sha256s=[sha(directory/'plan.json')],max_per_plan_usd=1.33,max_total_usd=1.33,
        expires_at=time.time()+3600,ledger_path=str(ledger.resolve()),purpose='OFFLINE MOCK ONLY; never use as live approval')


async def run(plan_path,output,store,upload_mode='success'):
    output.mkdir(parents=True,exist_ok=False)
    target=output/plan_path.name;shutil.copytree(plan_path,target)
    ledger=output/'mock-ledger.json';write(ledger,dict(total_budget_usd=10,per_run_budget_usd=1.5,spent_usd=0,reserved_usd=0,events=[],reservations={}))
    p,s=M.check_plan(target);client=mock_client(p,s,upload_mode)
    try:await M.execute(target,mock_owner(target,ledger),ledger,client,offline=True)
    finally:await client.close()
    result=I.publish(target,store)
    write(output/'result-summary.json',dict(job_id=result['job_id'],mode='offline_mock',real_model_requests=0,
        checked_relation_statuses=[e['status'] for e in result['native_video']['proposals']],
        source_sha256=result['source_sha256']))
    print(json.dumps(read(output/'result-summary.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--store',type=Path,default=M.ROOT/'data/live_jobs')
    p.add_argument('--upload-mode',choices=['success','no_expiry','future_expiry','expired_upload','malformed_expiry'],default='success');a=p.parse_args()
    asyncio.run(run(a.plan,a.output,a.store,a.upload_mode))
