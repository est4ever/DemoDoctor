"""Bounded upload/product tests; real SDK mock transport, no paid calls."""
import io,json
import av,numpy as np,pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from placement_assessment import service,meta_video as M,native_upload as U
from placement_assessment.support import read,write,sha
from scripts.native_video_offline import mock_client

@pytest.fixture
def product(tmp_path,monkeypatch):
    video=tmp_path/'input.mp4'
    with av.open(str(video),'w') as c:
        s=c.add_stream('libx264',rate=30);s.width=64;s.height=48;s.pix_fmt='yuv420p'
        for n in range(20):
            for packet in s.encode(av.VideoFrame.from_ndarray(np.full((48,64,3),n*8,dtype=np.uint8),format='rgb24')):c.mux(packet)
        for packet in s.encode():c.mux(packet)
    ledger=tmp_path/'mock-ledger.json';write(ledger,dict(total_budget_usd=10,per_run_budget_usd=1.5,spent_usd=0,reserved_usd=0,events=[],reservations={}))
    monkeypatch.setattr(M,'PLANS',tmp_path/'plans')
    app=FastAPI();root=tmp_path/'jobs';service.register(app,root)
    calls=[]
    app.state.native_mock=dict(ledger=ledger,client=lambda p,s:mock_client(p,s,calls=calls))
    return TestClient(app),video,ledger,root,calls,app

def prepare(p):
    c,video,*_=p
    r=c.post('/api/native-video/prepare',files={'video':('new.mp4',video.read_bytes(),'video/mp4')},data={'task_description':'Move the cube into the box','desired_end_state':'Cube is inside box'})
    assert r.status_code==200,r.text
    return r.json()

def approval(plan):return dict(plan_sha256=plan['plan_sha256'],approve_reservation_usd=1.33,attestations={k:True for k in ('eligible_meta_muse_credits','exclusive_account_usage','prior_requests_reconciled','dataset_processing_permitted','estimate_not_provider_hard_cap_accepted')})

def test_actual_upload_sdk_mock_results_and_sealed_reopen(product):
    c,v,ledger,root,calls,_=product;p=prepare(product)
    assert not calls and p['source_sha256']==sha(v) and p['frame_count']==20
    r=c.post(f"/api/native-video/{p['plan_id']}/execute",json=approval(p));assert r.status_code==200,r.text
    result=r.json();assert len(calls)==2 and result['native_upload'] and not result['failure_detected']
    assert {e['status'] for e in result['native_video']['proposals']}=={'UNVERIFIED'}
    job=root/result['job_id'];assert service.verify(job)==result
    assert c.get('/api/placement/jobs/'+job.name).status_code==200 and len(calls)==2
    assert c.post(f"/api/native-video/{p['plan_id']}/execute",json=approval(p)).status_code==409 and len(calls)==2
    request=read(M.PLANS/p['plan_id']/'actual-request.json')
    assert 'Move the cube into the box' in json.dumps(request) and 'fixture_final_condition' not in json.dumps(request)
    (job/'forged.json').write_text('{}');assert c.get('/api/placement/jobs/'+job.name).status_code==409

@pytest.mark.parametrize('bad',['approval','budget','source','review'])
def test_product_gates_send_nothing(product,bad,monkeypatch):
    c,v,ledger,root,calls,app=product;p=prepare(product);body=approval(p)
    if bad=='approval':body['attestations']={}
    if bad=='budget':d=read(ledger);d['per_run_budget_usd']=1;write(ledger,d)
    if bad=='source':(M.PLANS/p['plan_id']/'source.mp4').write_bytes(b'altered')
    if bad=='review':del app.state.native_mock
    r=c.post(f"/api/native-video/{p['plan_id']}/execute",json=body)
    assert r.status_code==409 and calls==[]

def test_incomplete_provider_stops_without_retry(product):
    c,v,ledger,root,calls,app=product;p=prepare(product)
    app.state.native_mock['client']=lambda p,s:mock_client(p,s,'incomplete',calls)
    r=c.post(f"/api/native-video/{p['plan_id']}/execute",json=approval(p))
    assert r.status_code==409 and len(calls)==2
    assert read(ledger)['events'][-1]['actual_usd'] is None
    assert c.post(f"/api/native-video/{p['plan_id']}/execute",json=approval(p)).status_code==409 and len(calls)==2
