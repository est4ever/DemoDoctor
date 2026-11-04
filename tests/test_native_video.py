"""Bounded adapter/provenance contracts. These are not recognition accuracy."""
import asyncio
import json
from pathlib import Path
import time
import av
import numpy as np
import pytest
from placement_assessment import service,meta_video as M,video_events as V,video_integration as I
from placement_assessment.support import write,read,index,sha
from scripts.native_video_offline import mock_client,mock_owner,mock_response


@pytest.fixture
def prepared(tmp_path):
    parent=tmp_path/'store'/'placement-0123456789abcdef';parent.mkdir(parents=True)
    with av.open(str(parent/'video.mp4'),'w') as c:
        stream=c.add_stream('libx264',rate=30);stream.width=64;stream.height=48;stream.pix_fmt='yuv420p'
        for n in range(20):
            frame=av.VideoFrame.from_ndarray(np.zeros((48,64,3),dtype=np.uint8),'rgb24')
            for p in stream.encode(frame):c.mux(p)
        for p in stream.encode():c.mux(p)
    source=index(parent/'video.mp4',sha(parent/'video.mp4'));write(parent/'source_index.json',source)
    interval=dict(start_frame=4,end_frame_exclusive=20,start_seconds=4/30,last_frame_seconds=19/30)
    write(parent/'placement-result.json',dict(source_sha256=source['source_sha256'],source_citations=[],failure_detected=True,
        failure_type='fixture_final_condition',time_interval=interval,observed_evidence=[dict(evidence_id='E0')]))
    write(parent/'placement-measurements.json',dict(decisions=[dict(qualifies=True,measurements=[dict(frame=n) for n in range(4,20)])]))
    write(parent/'analysis.json',dict(timeline_markers=[]));(parent/'placement-frames').mkdir()
    for f in ('status.json','request.json','tracks.json'):write(parent/f,{})
    service.seal(parent)
    directory,plan=M.prepare(parent,M.PILOT_TASK,M.PILOT_GOAL,tmp_path/'plans')
    ledger=tmp_path/'ledger.json';write(ledger,dict(total_budget_usd=10,per_run_budget_usd=1.5,spent_usd=0,reserved_usd=0,events=[],reservations={}))
    return directory,plan,ledger,source


def execute(fixture,mode='success'):
    directory,plan,ledger,source=fixture;calls=[]
    async def run():
        client=mock_client(plan,source,mode,calls)
        try:return await M.execute(directory,mock_owner(directory,ledger),ledger,client,offline=True)
        finally:await client.close()
    return asyncio.run(run()),calls


@pytest.mark.parametrize('upload_mode',['success','no_expiry','future_expiry'])
def test_full_sdk_wire_and_saved_reopening(prepared,upload_mode):
    directory,p,ledger,source=prepared
    result,calls=execute(prepared,upload_mode)
    upload=json.loads((directory/'upload.body').read_bytes())
    assert ('expires_at' in upload)==(upload_mode!='no_expiry')
    assert len(calls)==2 and [x['status'] for x in result['proposals']]==['UNVERIFIED','SUPPORTED','CONTRADICTED']
    assert result['original_failure_onset'] is None and result['physical_task_outcome']=='Uncertain'
    assert read(ledger)['reserved_usd']==0
    request=read(directory/'actual-request.json')
    text=request['input'][0]['content'][0]['text']
    assert 'fixture_final_condition' not in text and 'E0' not in text and 'publisher' not in text
    assert set(json.loads(text))=={'task_description','desired_end_state','source_time_range_seconds','sampling_plan'}
    published=I.publish(directory,ledger.parent/'new-store')
    job=ledger.parent/'new-store'/published['job_id']
    assert service.verify(job)['native_video']['mode']=='offline_mock'
    assert service.verify(job)==published
    assert read(directory/'accounting.json')['provider_confirmed_charge_usd'] is None
    with pytest.raises(ValueError,match='already accounted'):execute(prepared)
    (job/'forged.json').write_text('{}')
    with pytest.raises(ValueError,match='Unregistered'):service.verify(job)


@pytest.mark.parametrize('mode',['expired_upload','malformed_expiry'])
def test_invalid_upload_expiry_blocks_model_request(prepared,mode):
    directory,p,ledger,source=prepared
    with pytest.raises(ValueError,match='Invalid/expired'):execute(prepared,mode)
    assert read(directory/'STOP.json')['sent_operations']==1
    assert not (directory/'actual-request.json').exists()
    assert not (directory/'response.body').exists()
    assert read(ledger)['events'][-1]['actual_usd']==0
    assert (ledger.parent/'.native-video-active.lock').exists()


@pytest.mark.parametrize('expiry',[True,False,'9999999999','',[],{},float('nan'),float('inf'),9999999999.0,0,-1,1000])
def test_present_expiry_must_be_future_integer_timestamp(expiry):
    metadata=dict(id='file-12345',object='file',bytes=1,filename='video.mp4',purpose='user_data',
                  status='uploaded',created_at=int(time.time()),expires_at=expiry)
    with pytest.raises(ValueError,match='Invalid/expired'):M.file_identity(metadata,dict(upload_bytes=1))


@pytest.mark.parametrize('mode',['interrupted','incomplete','upload_error','wrong_model'])
def test_stop_and_preserve_uncertain_or_failed_operation(prepared,mode):
    directory,p,ledger,source=prepared
    with pytest.raises(Exception):execute(prepared,mode)
    stopped=read(directory/'STOP.json');assert stopped['retry_permitted'] is False
    assert stopped['sent_operations']==(1 if mode=='upload_error' else 2)
    assert (ledger.parent/'.native-video-active.lock').exists()
    event=read(ledger)['events'][-1]
    assert event['actual_usd']==(0.0 if mode=='upload_error' else None)
    if mode=='upload_error':assert (directory/'error-response.body').is_file()


@pytest.mark.parametrize('problem',['source','budget','funding','approval','old_execution'])
def test_pretransmission_rejection(prepared,problem):
    directory,p,ledger,source=prepared;owner=mock_owner(directory,ledger)
    if problem=='source':(directory/'video.mp4').write_bytes(b'wrong video')
    if problem=='budget':d=read(ledger);d['per_run_budget_usd']=1;write(ledger,d)
    if problem=='funding':owner['eligible_meta_muse_credits']=False
    if problem=='approval':owner['plan_sha256s']=['wrong']
    if problem=='old_execution':d=read(ledger);d['events']=[dict(actual_usd=None,from_cache=False)];write(ledger,d)
    with pytest.raises(ValueError):M.admission(directory,owner,ledger)
    assert not (directory/'attempt.json').exists()


def test_modified_completed_execution_is_rejected(prepared):
    directory,p,ledger,source=prepared;execute(prepared)
    (directory/'response.body').write_text('{}')
    with pytest.raises(ValueError,match='altered'):I.publish(directory,ledger.parent/'new-store')


@pytest.mark.parametrize('value',[-1,9999,float('nan')])
def test_invalid_model_times_rejected(prepared,value):
    raw=mock_response(prepared[3]);payload=json.loads(raw['output'][0]['content'][0]['text'])
    payload['events'][0]['proposed_start_time']=value;raw['output'][0]['content'][0]['text']=json.dumps(payload)
    with pytest.raises(ValueError):V.parse_response(raw,prepared[3])


def test_control_never_promoted_to_success(prepared):
    d,p,l,s=prepared;parsed=V.parse_response(mock_response(s),s)
    final=dict(source_sha256=s['source_sha256'],failure_detected=False,failure_type=None,time_interval=None)
    result=V.verify(parsed,s,final,dict(decisions=[]))
    assert all(e['status']=='UNVERIFIED' for e in result['proposals'])
    assert result['physical_task_outcome']=='Uncertain' and not result['failure_detected']


def test_different_task_cannot_inherit_rack_failure(prepared,tmp_path):
    d,p,l,s=prepared
    with pytest.raises(ValueError,match='only the approved'):
        M.prepare(Path(p['parent_job']),'Move a cup to the table','Cup is on table',tmp_path/'other-plans')


def test_api_paid_gate_without_operator_authorization(prepared,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    d,p,l,s=prepared;monkeypatch.setattr(M,'PLANS',d.parent);monkeypatch.delenv('DEMODOCTOR_NATIVE_VIDEO_APPROVAL',raising=False)
    app=FastAPI();I.register(app,l.parent/'store')
    r=TestClient(app).post(f'/api/native-video/{d.name}/execute',json=dict(plan_sha256=sha(d/'plan.json'),approve_reservation_usd=1.33))
    assert r.status_code==409 and 'disabled' in r.text and not (d/'attempt.json').exists()
