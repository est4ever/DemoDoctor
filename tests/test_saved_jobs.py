"""History/reopen are read-only and require neither providers nor credentials."""
from pathlib import Path
import hashlib,json
import pytest
from fastapi.testclient import TestClient
import live_api as api
import live_pipeline as lp
import saved_jobs as H

@pytest.fixture
def setup(tmp_path,monkeypatch):
    root=tmp_path/'jobs';root.mkdir()
    monkeypatch.setattr(api,'JOBS_ROOT',root);monkeypatch.setattr(lp,'JOBS_ROOT',root)
    monkeypatch.setattr(api,'OFFLINE_ONLY',True);monkeypatch.setattr(api,'REAL_ANALYSIS_ENABLED',False)
    def forbidden(*a,**kw):raise AssertionError('History/reopen must never dispatch inference')
    monkeypatch.setattr(api,'_spawn_analyze',forbidden)
    monkeypatch.setattr(lp,'run_analyze',forbidden)
    monkeypatch.setattr(lp.T,'Sam31Tracker',forbidden)
    monkeypatch.setattr(lp.AI,'get_client',forbidden)
    monkeypatch.delenv('MODEL_API_KEY',raising=False);monkeypatch.delenv('FIREWORKS_API_KEY',raising=False)
    with TestClient(api.app) as client:yield client,root

def write(job,name,value):
    p=job/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),encoding='utf-8')

def make(root,job_id='20261101T160738Z_test',*,dry=False,multi=False):
    d=root/job_id;d.mkdir()
    a=json.loads((Path(__file__).resolve().parents[1]/'web/public/data/ep010/analysis.json').read_text())
    a.update(task='Pick up the block, put it in the drawer, then close the drawer.',dry_run=dry,task_outcome='uncertain',criteria={'task_text':'Current explicit task presentation'})
    tracks={'fps':15,'frames':{},'tracks':{},'image_size':[1280,720],'legend':[]}
    write(d,'analysis.json',a);write(d,'tracks.json',tracks);write(d,'status.json',{'job_id':job_id,'status':'completed','dry_run':dry})
    write(d,'request.json',{'filename':r'C:\private\robot.mp4','dry_run':dry,'run_muse':not dry,'task_description':a['task']})
    if multi:
        (d/'source1.mp4').write_bytes(b'synthetic media')
        write(d,'cam1/tracks.json',tracks);(d/'cam1/video.mp4').write_bytes(b'synthetic cropped media')
        camera={'camera_id':'cam1','source_video_id':'source1','crop':[0,0,1280,720],
            'sha256':hashlib.sha256((d/'cam1/video.mp4').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256((d/'source1.mp4').read_bytes()).hexdigest(),
            'fps':15,'n_frames':2,'frame_start':0,'frame_end':2,'timestamps_s':[0,1/15],'playback_offset_s':0,'object_concept':'block','destination_concept':'drawer'}
        m={'sources':[{'source_video_id':'source1','filename':'droid.mp4','sha256':camera['source_sha256']}],'cameras':[camera]}
        a['multicamera']=m;a['frame_catalog']=[];write(d,'analysis.json',a);write(d,'multicamera.json',m)
        write(d,'prepared-multicamera.json',{'manifest_sha256':hashlib.sha256((d/'multicamera.json').read_bytes()).hexdigest()})
        write(d,'cam1/provenance.json',camera)
        if not dry:
            for name in ('provider_observations','evidence_package','verification','failure_report'):write(d,f'cam1/{name}.json',{'synthetic':True})
            write(d,'evidence_package.json',{'synthetic':True})
    else:(d/'video.mp4').write_bytes(b'synthetic media')
    if not dry:write(d,'muse_result.json',{'synthetic':True})
    return d

def hashes(d):return {str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()}

@pytest.mark.parametrize('multi',[False,True])
@pytest.mark.parametrize('dry',[False,True])
def test_reopen_survives_new_sessions_and_never_changes_artifacts(setup,multi,dry):
    client,root=setup;job=make(root,multi=multi,dry=dry);before=hashes(job)
    listing=client.get('/api/jobs').json()['jobs'];assert len(listing)==1
    row=listing[0];assert row['can_open'] and row['camera_count']==1
    assert row['analysis_type']==('dry_run' if dry else 'real')
    assert row['created_at']=='2026-11-01T16:07:38+00:00'
    assert row['video_filename']==('droid.mp4' if multi else 'robot.mp4')
    assert 'private' not in json.dumps(row)
    for _ in range(2):
        response=client.get(f'/api/jobs/{job.name}/reopen');assert response.status_code==200,response.text
        assert response.json()['analysis']['task_outcome']=='uncertain'
    with TestClient(api.app) as restarted:
        assert restarted.get(f'/api/jobs/{job.name}/reopen').json()==response.json()
    assert hashes(job)==before

@pytest.mark.parametrize('missing',['analysis.json','tracks.json','source1.mp4','cam1/video.mp4','cam1/tracks.json','cam1/provider_observations.json','muse_result.json'])
def test_missing_artifact_never_reruns_or_overwrites_results(setup,missing):
    client,root=setup;job=make(root,multi=True);(job/missing).unlink();before=hashes(job)
    row=client.get('/api/jobs').json()['jobs'][0];assert not row['can_open'] and row['availability_error']
    response=client.get(f'/api/jobs/{job.name}/reopen');assert response.status_code==409
    assert missing in response.json()['detail'] and 'No analysis was started' in response.text
    assert hashes(job)==before

@pytest.mark.parametrize('status',['running','queued','failed','interrupted','awaiting_approval'])
def test_incomplete_job_is_reported_not_restarted(setup,status):
    client,root=setup;job=make(root);write(job,'status.json',{'status':status});before=hashes(job)
    response=client.get(f'/api/jobs/{job.name}/reopen')
    assert response.status_code==409 and status in response.text
    assert not client.get('/api/jobs').json()['jobs'][0]['can_open']
    assert hashes(job)==before

def test_metadata_whitelist_excludes_secrets_approvals_and_absolute_paths(setup):
    client,root=setup;job=make(root)
    write(job,'status.json',{'status':'completed','dry_run':False,'approval_id':'private-approval-sentinel','credentials':'private-key-sentinel'})
    write(job,'prepared.json',{'quote':{'approval_id':'private-approval-sentinel','filename':'robot.mp4'}})
    text=client.get('/api/jobs').text
    assert 'private-key-sentinel' not in text and 'private-approval-sentinel' not in text and 'C:' not in text

def test_recorded_replay_type_and_bad_json_are_explicit(setup):
    client,root=setup;job=make(root);request=H.read(job,'request.json');request['cache_only']=True;write(job,'request.json',request)
    assert client.get('/api/jobs').json()['jobs'][0]['analysis_type']=='recorded_replay'
    (job/'tracks.json').write_text('invalid json')
    assert client.get(f'/api/jobs/{job.name}/reopen').status_code==409
    assert 'unreadable' in client.get('/api/jobs').text

def test_missing_status_and_nonexistent_jobs(setup):
    client,root=setup;job=make(root);(job/'status.json').unlink()
    assert client.get('/api/jobs').json()['jobs'][0]['status']=='unknown'
    assert client.get(f'/api/jobs/{job.name}/reopen').status_code==409
    assert client.get('/api/jobs/nonexistent/reopen').status_code==404
    assert client.get('/api/jobs/..%5Cneighbor/reopen').status_code==400

def test_invalid_camera_paths_cannot_be_read(setup):
    client,root=setup;job=make(root,multi=True);m=H.read(job,'multicamera.json');m['cameras'][0]['camera_id']='..\\neighbor';write(job,'multicamera.json',m)
    response=client.get(f'/api/jobs/{job.name}/reopen')
    assert response.status_code==409 and 'invalid' in response.text

def test_legacy_dry_run_without_sam_tracks_is_replayable(setup):
    client,root=setup;job=make(root,dry=True);(job/'tracks.json').unlink();before=hashes(job)
    row=client.get('/api/jobs').json()['jobs'][0]
    assert row['can_open'] and row['analysis_type']=='dry_run' and row['outcome'] is None
    result=client.get(f'/api/jobs/{job.name}/reopen')
    assert result.status_code==200 and result.json()['tracks'] is None
    assert result.json()['analysis']['dry_run'] is True
    assert hashes(job)==before
