"""Real-analysis HTTP contract using synthetic providers, never paid inference."""
import json
import time
import os
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
import live_api as api
import live_pipeline as lp
import live_budget as budget
from live_provider_fakes import install


@pytest.fixture
def setup(tmp_path, monkeypatch):
    jobs=tmp_path/'jobs'; jobs.mkdir()
    monkeypatch.setattr(api,'JOBS_ROOT',jobs); monkeypatch.setattr(lp,'JOBS_ROOT',jobs)
    monkeypatch.setattr(budget,'ROOT',tmp_path); monkeypatch.setattr(budget,'LEDGER_PATH',jobs/'ledger.json')
    monkeypatch.setattr(api,'REAL_ANALYSIS_ENABLED',True); monkeypatch.setattr(api,'OFFLINE_ONLY',False)
    ledger=budget.load_ledger(); ledger['per_run_budget_usd']=2.10; budget.save_ledger(ledger)
    state=install(monkeypatch)
    video=tmp_path/'new.mp4'; writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,48))
    for _ in range(20): writer.write(np.zeros((48,64,3),np.uint8))
    writer.release()
    with TestClient(api.app) as client:
        yield client,video,state,jobs
        for thread in tuple(api._running.values()):
            thread.join(timeout=5)
            assert not thread.is_alive()


def prepare(client,video,**changes):
    return client.post('/api/analyze',files={'video':('new.mp4',video.read_bytes(),'video/mp4')},data={
        'task_description':'Put item in box','object_concept':'item','destination_concept':'box',
        'dry_run':'false','prepare_only':'true','run_muse':'true','complete_demonstration':'true',**changes})


def start(client,q):
    return client.post(f'/api/jobs/{q["job_id"]}/start',json={'approval_id':q['approval_id']})


def wait(client,id):
    for _ in range(300):
        result=client.get(f'/api/jobs/{id}').json()
        if result['status'] in {'completed','failed'}:return result
        time.sleep(.01)
    pytest.fail('job did not finish')


def test_prepare_confirm_real_pipeline_results_and_duplicate_refusal(setup):
    client,video,state,jobs=setup
    response=prepare(client,video); assert response.status_code==200,response.text
    q=response.json()['quote']; assert state['calls']==[]
    assert q['estimated_max_usd']==1.3325 and q['frame_end']==20
    assert start(client,q).status_code==200
    assert start(client,q).status_code==409
    status=wait(client,q['job_id']); assert status['status']=='completed',status
    assert state['calls']==['sam-video','sam-image','muse']
    a=client.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert not a.get('dry_run') and a['task_outcome']=='uncertain'
    assert a['observed'] and a['evidence_catalog'] and a['timeline_markers']
    muse=json.loads((jobs/q['job_id']/'muse_result.json').read_text())
    assert muse['validated']['ok'],muse
    tracks=client.get(f'/api/jobs/{q["job_id"]}/tracks').json()
    assert tracks['frames']['0'][0]['mask']=={'size':[4,4],'counts':[0,16]}
    assert 'approval_id' not in client.get('/api/jobs').text
    assert client.get(f'/api/jobs/{q["job_id"]}/files/prepared.json').status_code==400


@pytest.mark.parametrize('scenario,expected',[('sam_fail',['sam-video']),('muse_fail',['sam-video','sam-image','muse'])])
def test_provider_failure_stops_without_mock_results_or_retry(setup,scenario,expected):
    c,v,s,_=setup;s['scenario']=scenario;q=prepare(c,v).json()['quote'];assert start(c,q).status_code==200
    result=wait(c,q['job_id']);assert result['status']=='failed' and result['errors']
    assert s['calls']==expected,result
    assert c.get(f'/api/jobs/{q["job_id"]}/analysis').status_code==404


@pytest.mark.parametrize('failure',['expired','token','changed','budget','origin','disabled','offline','missing','unresolved'])
def test_approval_rechecks_every_boundary_without_provider_calls(setup,monkeypatch,failure):
    c,v,s,jobs=setup;q=prepare(c,v).json()['quote']
    if failure=='expired':
        p=jobs/q['job_id']/'prepared.json';d=json.loads(p.read_text());d['quote']['expires_at']=0;p.write_text(json.dumps(d))
    if failure=='token':q['approval_id']='wrong'
    if failure=='changed':(jobs/q['job_id']/'video.mp4').write_bytes(b'changed')
    if failure=='budget':
        d=budget.load_ledger();d['per_run_budget_usd']=1;budget.save_ledger(d)
    if failure=='disabled':monkeypatch.setattr(api,'REAL_ANALYSIS_ENABLED',False)
    if failure=='offline':monkeypatch.setattr(api,'OFFLINE_ONLY',True)
    if failure=='missing':monkeypatch.setattr(lp.T,'model_api_key_available',lambda:False)
    if failure=='unresolved':budget.reserve('interrupted-job',.1,note='unresolved test fixture')
    response=c.post(f'/api/jobs/{q["job_id"]}/start',json={'approval_id':q['approval_id']},
        headers={'Origin':'https://attacker.invalid'} if failure=='origin' else {})
    assert response.status_code in {402,403,409,503};assert s['calls']==[]


def test_corrupt_upload_and_missing_credentials_are_visible_errors(setup,monkeypatch):
    c,v,s,_=setup
    bad=v.parent/'bad.mp4';bad.write_bytes(b'not a video')
    assert prepare(c,bad).status_code==422
    monkeypatch.setattr(lp.AI,'load_fireworks_api_key',lambda:None)
    assert prepare(c,v).status_code==503
    assert s['calls']==[]


def test_readiness_never_returns_credentials_and_malformed_approval_is_rejected(setup):
    c,v,s,_=setup
    ready=c.get('/api/health')
    assert ready.json()['real_analysis_enabled'] and ready.json()['sam_key'] and ready.json()['muse_key']
    assert 'synthetic-test-only' not in ready.text
    q=prepare(c,v).json()['quote']
    assert c.post(f'/api/jobs/{q["job_id"]}/start',json={'approval_id':'invalid\u2603'}).status_code==422
    assert s['calls']==[]


def test_restart_marks_unfinished_job_without_restarting_it(setup):
    c,v,s,jobs=setup
    d=jobs/'unfinished';d.mkdir();(d/'status.json').write_text('{"job_id":"unfinished","status":"running"}')
    with TestClient(api.app) as restarted:
        result=restarted.get('/api/jobs/unfinished').json()
        assert result['status']=='interrupted' and 'No automatic retry' in result['errors'][0]
    assert s['calls']==[]


def test_single_camera_dry_replay_retains_native_fps_without_evidence(setup):
    c,v,s,_=setup
    r=c.post('/api/analyze',files={'video':('new.mp4',v.read_bytes(),'video/mp4')},data={
        'task_description':'Put item in box','object_concept':'item','destination_concept':'box',
        'dry_run':'true','run_muse':'false'})
    assert r.status_code==200
    status=wait(c,r.json()['job_id']);assert status['status']=='completed',status
    tracks=c.get(f'/api/jobs/{r.json()["job_id"]}/tracks').json()
    assert tracks['fps']==10 and tracks['image_size']==[64,48]
    assert tracks['frame_start']==0 and tracks['frame_end']==20 and not tracks['frames']
    analysis=c.get(f'/api/jobs/{r.json()["job_id"]}/analysis').json()
    assert analysis['dry_run'] and not analysis['observed'] and analysis['task_outcome']=='uncertain'
    assert s['calls']==[]


def test_optional_questions_reach_single_camera_muse_without_changing_task_criteria(setup,monkeypatch):
    c,v,s,_=setup;question='Could orientation or occlusion explain incomplete placement?'
    original=lp.AI.analyze_with_evidence
    def inspect(pkg,frames,**kw):
        assert pkg.provenance['investigation_questions']==question
        assert pkg.task_description=='Put item in box'
        return original(pkg,frames,**kw)
    monkeypatch.setattr(lp.AI,'analyze_with_evidence',inspect)
    q=prepare(c,v,investigation_questions=question).json()['quote'];start(c,q)
    status=wait(c,q['job_id']);assert status['status']=='completed',status
    assert c.get(f'/api/jobs/{q["job_id"]}/analysis').json()['task_outcome']=='uncertain'


@pytest.mark.skipif(os.name != 'nt', reason='Windows sharing violations')
def test_temporary_windows_artifact_lock_does_not_repeat_inference(tmp_path,monkeypatch):
    original=Path.replace;attempts=[]
    def locked_once(path,target):
        attempts.append(path)
        if len(attempts)==1:raise PermissionError('synthetic Windows sharing violation')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',locked_once)
    lp._write_job(tmp_path,'status.json',{'status':'running'})
    assert len(attempts)==2 and json.loads((tmp_path/'status.json').read_text())['status']=='running'
