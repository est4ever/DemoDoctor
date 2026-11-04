"""Multi-camera API + real orchestration with synthetic providers only."""
import copy
import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient

import live_api as api
import live_pipeline as lp
import live_budget as budget
import multicamera as mc
from live_provider_fakes import install


def video(path, *, width=96, height=64, count=20, fps=10):
    with av.open(str(path), 'w') as output:
        stream=output.add_stream('libx264', rate=fps)
        stream.width=width;stream.height=height;stream.pix_fmt='yuv420p'
        for i in range(count):
            pixels=np.zeros((height,width,3),np.uint8);pixels[:, :width//2, 1]=100+i
            for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):output.mux(packet)
        for packet in stream.encode():output.mux(packet)


@pytest.fixture
def setup(tmp_path,monkeypatch):
    jobs=tmp_path/'jobs';jobs.mkdir()
    monkeypatch.setattr(api,'JOBS_ROOT',jobs);monkeypatch.setattr(lp,'JOBS_ROOT',jobs)
    monkeypatch.setattr(budget,'ROOT',tmp_path);monkeypatch.setattr(budget,'LEDGER_PATH',jobs/'ledger.json')
    ledger=budget.load_ledger();ledger['per_run_budget_usd']=2.10;budget.save_ledger(ledger)
    monkeypatch.setattr(api,'REAL_ANALYSIS_ENABLED',True);monkeypatch.setattr(api,'OFFLINE_ONLY',False)
    state=install(monkeypatch)
    def forbidden(*a,**kw):raise AssertionError('Static physical-event reconstruction forbidden for multi-camera')
    monkeypatch.setattr(lp.FI,'localize_window',forbidden)
    p=tmp_path/'new.mp4';video(p)
    with TestClient(api.app) as client:
        yield client,p,state,jobs,monkeypatch
        for thread in tuple(api._running.values()):thread.join(timeout=10);assert not thread.is_alive()


def plan(mode='separate',count=2):
    return {'source_mode':mode,'task_description':'Put the object in the destination',
        'alignment_confirmed':True,'alignment_basis':'User approved matching visible flash at time zero',
        'crops_confirmed':True,'window_start_s':0,'window_end_s':1,
        'cameras':[{'name':f'View {i+1}','motion':'moving' if i==1 else 'static','offset_s':0,
            'object_concept':'item','destination_concept':'box',
            'crop':[i*32,0,32,64] if mode=='composite' else None} for i in range(count)]}


def prepare(setup,manifest=None,*,dry=False):
    c,p,_,_,_=setup;manifest=manifest or plan()
    n=1 if manifest['source_mode']=='composite' else len(manifest['cameras'])
    return c.post('/api/multicamera/prepare',files=[('videos',(f'cam{i}.mp4',p.read_bytes(),'video/mp4')) for i in range(n)],data={'manifest':json.dumps(manifest),'dry_run':str(dry).lower()})


def start(client,q):
    return client.post(f'/api/multicamera/{q["job_id"]}/start',json={'approval_id':q['approval_id']})


def wait(client,job):
    for _ in range(500):
        result=client.get(f'/api/jobs/{job}').json()
        if result['status'] in {'completed','failed'}:return result
        time.sleep(.01)
    pytest.fail('job did not finish')


def test_independent_views_one_muse_original_citations_and_parent_budget(setup):
    c,p,s,jobs,_=setup
    r=prepare(setup);assert r.status_code==200,r.text
    q=r.json()['quote'];assert s['calls']==[] and q['estimated_max_usd']==1.345
    assert len(q['cameras'])==2 and start(c,q).status_code==200
    assert start(c,q).status_code==409
    status=wait(c,q['job_id']);assert status['status']=='completed',status
    assert s['calls']==['sam-video','sam-image','sam-video','sam-image','muse']
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert a['task_outcome']=='uncertain' and a['physical_events']==[] and not a['inferred']
    assert a['criteria']['completion']=='unverified' and not a['criteria']['mechanisms']
    assert all(part['state'] not in {'supported','contradicted'} for part in a['criteria']['assessments'])
    cat=a['evidence_catalog'];assert {e['camera_id'] for e in cat}=={'cam1','cam2'}
    assert len({e['evidence_id'] for e in cat})==len(cat)
    for e in cat:
        original=c.get(f'/api/jobs/{q["job_id"]}/cameras/{e["camera_id"]}/evidence_package.json').json()
        assert e['original_evidence_id'] in {x['evidence_id'] for x in original['evidence_catalog']}
        assert e['summary'].startswith('['+e['camera_id'])
    raw=c.get(f'/api/jobs/{q["job_id"]}/cameras/cam2/provider_observations.json').json()
    assert raw['observations'][0]['camera_id']=='cam2'
    assert raw['observations'][0]['native_image_dimensions']==[96,64]
    assert raw['observations'][0]['source_frame']==raw['observations'][0]['frame_index']
    assert all(e['job_id']==q['job_id'] for e in budget.load_ledger()['events'])
    assert c.get(f'/api/jobs/{q["job_id"]}/sources/source1').content==p.read_bytes()
    assert c.get(f'/api/jobs/{q["job_id"]}/sources/source1.mp4',headers={'Range':'bytes=0-31'}).status_code==206
    assert c.get(f'/api/jobs/{q["job_id"]}/cameras/cam1/prepared.json').status_code==400
    assert c.get(f'/api/jobs/{q["job_id"]}/cameras/C:secret/video.mp4').status_code==400
    assert 'approval_id' not in c.get('/api/jobs').text
    with TestClient(api.app) as reloaded:
        assert reloaded.get(f'/api/jobs/{q["job_id"]}/analysis').json()==a


@pytest.mark.parametrize('count', [1,2,3])
def test_explicit_task_context_and_quote_remain_camera_bound(setup,count):
    c,_,state,jobs,mp=setup
    manifest=plan('composite',count)
    manifest['task_description']='Pick up the blue block, put it in the drawer, then close the drawer.'
    original=lp.AI.analyze_with_evidence
    def inspect(pkg,frames,**kw):
        assert [s['params']['action'] for s in pkg.provenance['task_subgoals']]==['pick_up','place','close']
        assert len(frames)==len(pkg.frame_refs)<=6
        for f in pkg.frame_refs:
            source=pkg.provenance['frame_sources'][f.frame_ref]
            assert 0<=source['original_frame']<10
            assert source['camera_id'] in {f'cam{i+1}' for i in range(count)}
        return original(pkg,frames,**kw)
    mp.setattr(lp.AI,'analyze_with_evidence',inspect)
    response=prepare(setup,manifest);assert response.status_code==200,response.text
    q=response.json()['quote'];assert state['calls']==[]
    assert [s['action'] for s in q['task_subgoals']]==['pick_up','place','close']
    for approved,config in zip(q['cameras'],manifest['cameras']):
        assert approved['crop']==config['crop'] and approved['source_sha256']
        assert [approved['width'],approved['height']]==config['crop'][2:]
    assert start(c,q).status_code==200
    assert wait(c,q['job_id'])['status']=='completed'
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert [s['state'] for s in a['criteria']['assessments'] if s['kind']=='action']==['unverified']*3
    assert len(a['criteria']['context_frames'])==6
    for f in a['criteria']['context_frames']:
        camera=next(v for v in a['multicamera']['cameras'] if v['camera_id']==f['camera_id'])
        assert f['source_video_id']==camera['source_video_id']
        assert camera['frame_start']<=f['original_frame']<camera['frame_end']
        assert f['shared_timestamp_s']==f['original_timestamp_s']-camera['playback_offset_s']
    assert c.get(f'/api/jobs/{q["job_id"]}/analysis').json()==a  # reload does not rerun
    assert state['calls']==['sam-video','sam-image']*count+['muse']


def test_dry_run_offline_has_no_physical_conclusions(setup):
    c,_,s,_,mp=setup;mp.setattr(api,'OFFLINE_ONLY',True);mp.setattr(api,'REAL_ANALYSIS_ENABLED',False)
    r=prepare(setup,dry=True);assert r.status_code==200,r.text
    status=wait(c,r.json()['job_id']);assert status['status']=='completed',status
    a=c.get(f'/api/jobs/{r.json()["job_id"]}/analysis').json()
    assert a['dry_run'] and not a['evidence_catalog'] and not a['observed'] and not a['hypotheses']
    assert a['criteria']['completion']=='not_assessed'
    assert a['task_outcome']=='uncertain' and s['calls']==[]


def test_ffmpeg_crops_keep_every_timestamp_and_original_source(setup):
    if not shutil.which('ffmpeg'):pytest.skip('Installed FFmpeg required')
    c,p,s,jobs,_=setup
    r=prepare(setup,plan('composite',3),dry=True);assert r.status_code==200,r.text
    j=r.json()['job_id'];status=wait(c,j);assert status['status']=='completed',status
    manifest=mc.read(jobs/j/'multicamera.json');source=mc.probe(p)
    for cam in manifest['cameras']:
        crop=mc.probe(jobs/j/cam['camera_id']/'video.mp4')
        assert crop['n_frames']==source['n_frames'] and crop['timestamps_s']==source['timestamps_s']
        assert [crop['width'],crop['height']]==[32,64]
        assert cam['frame_mapping'][-1]['source_frame']==19
        assert cam['frame_mapping'][-1]['source_timestamp_s']==source['timestamps_s'][-1]
    assert mc.digest(jobs/j/'source1.mp4')==mc.digest(p) and s['calls']==[]


@pytest.mark.parametrize('case',['alignment','nan','crop','overlap','window','name'])
def test_invalid_plan_is_rejected_before_calls(setup,case):
    m=plan()
    if case=='alignment':m['alignment_confirmed']=False
    if case=='nan':m['cameras'][1]['offset_s']=float('nan')
    if case=='crop':m=plan('composite');m['cameras'][0]['crop']=[-2,0,32,64]
    if case=='overlap':m=plan('composite');m['cameras'][1]['crop']=m['cameras'][0]['crop']
    if case=='window':m['window_end_s']=3
    if case=='name':m['cameras'][1]['name']=m['cameras'][0]['name']
    r=prepare(setup,m);assert r.status_code==422,r.text
    assert setup[2]['calls']==[]


@pytest.mark.parametrize('case',['budget','origin','disabled','offline','token','source_changed','plan_changed','expired'])
def test_approval_rechecks_security_and_all_source_bytes(setup,case):
    c,_,s,jobs,mp=setup;q=prepare(setup).json()['quote'];directory=jobs/q['job_id']
    if case=='budget':d=budget.load_ledger();d['per_run_budget_usd']=1;budget.save_ledger(d)
    if case=='disabled':mp.setattr(api,'REAL_ANALYSIS_ENABLED',False)
    if case=='offline':mp.setattr(api,'OFFLINE_ONLY',True)
    if case=='token':q['approval_id']='wrong'
    if case=='source_changed':(directory/'source2.mp4').write_bytes(b'changed')
    if case=='plan_changed':(directory/'multicamera.json').write_text('{}')
    if case=='expired':d=mc.read(directory/'prepared-multicamera.json');d['quote']['expires_at']=0;lp._write_job(directory,'prepared-multicamera.json',d)
    r=c.post(f'/api/multicamera/{q["job_id"]}/start',json={'approval_id':q['approval_id']},headers={'Origin':'https://untrusted.invalid'} if case=='origin' else {})
    assert r.status_code in {402,403,409} and s['calls']==[]


@pytest.mark.parametrize('scenario,expected',[('sam_fail',['sam-video']),('muse_fail',['sam-video','sam-image','sam-video','sam-image','muse'])])
def test_stop_on_first_provider_failure_without_paid_retries(setup,scenario,expected):
    c,_,s,_,_=setup;s['scenario']=scenario;q=prepare(setup).json()['quote'];assert start(c,q).status_code==200
    result=wait(c,q['job_id']);assert result['status']=='failed' and s['calls']==expected,result
    assert c.get(f'/api/jobs/{q["job_id"]}/analysis').status_code==404


def test_offsets_use_native_frames_without_temporal_resampling(setup):
    c,_,s,jobs,_=setup;m=plan();m['cameras'][1]['offset_s']=.2
    r=prepare(setup,m);assert r.status_code==200,r.text
    manifest=r.json()['manifest'];assert manifest['cameras'][1]['frame_start']==2
    assert manifest['cameras'][1]['frame_mapping'][2]['shared_timestamp_s']==pytest.approx(0)


def test_wrong_camera_citation_rejected_and_disagreement_stays_hypothesis(setup):
    c,_,s,jobs,mp=setup
    original=lp.AI.analyze_with_evidence
    def disagreement(pkg,frames,**kw):
        result=original(pkg,frames,**kw)
        raw=result['validated']['raw']
        raw['hypotheses']=[{'text':'Views may disagree about object location; association unverified',
                            'related_evidence_ids':[pkg.evidence_items[0].evidence_id,pkg.evidence_items[-1].evidence_id]}]
        result['validated']=mc.ef.validate_muse_explanation(raw,pkg).to_dict()
        wrong=copy.deepcopy(raw);wrong['factual_claims']=[{'text':pkg.evidence_items[0].summary,'evidence_ids':[pkg.evidence_items[-1].evidence_id]}]
        assert not mc.ef.validate_muse_explanation(wrong,pkg).ok
        return result
    mp.setattr(lp.AI,'analyze_with_evidence',disagreement)
    q=prepare(setup).json()['quote'];start(c,q);status=wait(c,q['job_id']);assert status['status']=='completed',status
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert a['hypotheses'][0]['label']=='hypothesis' and a['task_outcome']=='uncertain'


def test_missing_detections_do_not_become_object_absence(setup):
    c,_,s,jobs,mp=setup;original_tracker=lp.T.Sam31Tracker;original_inputs=lp.FI.build_window_inputs
    class Missing(original_tracker):
        def track_window(self,*a,**kw):
            chunk,obs,calls=super().track_window(*a,**kw)
            if s['calls'].count('sam-video')==2:
                s['observations']=[];return chunk,[],calls
            return chunk,obs,calls
    def inputs(path,**kw):
        if s['observations']:return original_inputs(path,**kw)
        return lp.FI.WindowInputs(path.read_bytes(),10,20,(64,96),None,None,[],None,{'status':'empty_result'}, {}, [], None)
    mp.setattr(lp.T,'Sam31Tracker',Missing);mp.setattr(lp.FI,'build_window_inputs',inputs)
    q=prepare(setup).json()['quote'];start(c,q);status=wait(c,q['job_id']);assert status['status']=='completed',status
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert a['task_outcome']=='uncertain'
    assert any('cam2' in u and 'No object detections' in u for u in a['unknowns'])
    assert not [e for e in a['evidence_catalog'] if e['camera_id']=='cam2' and e['kind']=='detection']


def test_updated_cost_above_approved_plan_stops_later_camera_requests(setup):
    c,_,s,_,mp=setup;original=lp.T.Sam31Tracker
    class ExtraUsage(original):
        def track_window(self,*a,**kw):
            chunk,obs,calls=super().track_window(*a,**kw)
            calls[0].usage={'usage':{'video_frames_processed':1000}}
            return chunk,obs,calls
    mp.setattr(lp.T,'Sam31Tracker',ExtraUsage)
    q=prepare(setup).json()['quote'];start(c,q);status=wait(c,q['job_id'])
    assert status['status']=='failed' and 'exceeds the approved plan' in status['errors'][0]
    assert s['calls']==['sam-video']


@pytest.mark.parametrize('count',[1,2,3])
@pytest.mark.parametrize('mode',['separate','composite'])
def test_variable_camera_set_uses_same_pipeline_budget_and_citation_contract(setup,count,mode):
    c,p,s,jobs,_=setup;m=plan(mode,count)
    if mode=='composite':
        video(p,width=192)
        for i,cam in enumerate(m['cameras']):cam['crop']=[i*64,0,64,64]
    if count==1:
        m['alignment_confirmed']=False;m['alignment_basis']=''
    response=prepare(setup,m);assert response.status_code==200,response.text
    q=response.json()['quote'];assert len(q['cameras'])==count and s['calls']==[]
    assert q['estimated_max_usd']==pytest.approx(1.32+count*.0125)
    assert start(c,q).status_code==200
    result=wait(c,q['job_id']);assert result['status']=='completed',result
    assert s['calls']==['sam-video','sam-image']*count+['muse']
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert len(a['multicamera']['cameras'])==count and a['task_outcome']=='uncertain'
    assert a['physical_events']==[]
    assert {e['camera_id'] for e in a['evidence_catalog']}=={f'cam{i+1}' for i in range(count)}
    for camera in a['multicamera']['cameras']:
        raw=c.get(f'/api/jobs/{q["job_id"]}/cameras/{camera["camera_id"]}/provider_observations.json').json()
        assert all(o['camera_id']==camera['camera_id'] for o in raw['observations'])
        assert camera['frame_mapping'][0]['source_timestamp_s']==0
        assert camera['frame_mapping'][-1]['source_frame']==19
    assert len(a['frame_catalog'])<=6
    assert c.get(f'/api/jobs/{q["job_id"]}/files/muse_result.json').json()['validated']['ok']


@pytest.mark.parametrize('count',[0,4])
def test_camera_count_outside_one_to_three_is_rejected(setup,count):
    m=plan(count=count)
    with pytest.raises(ValueError):mc.Manifest.model_validate(m)
    response=prepare(setup,m)
    assert response.status_code==422 and setup[2]['calls']==[]


def test_questions_and_unverified_layout_proposal_preserve_verifier_rules(setup):
    c,_,s,jobs,mp=setup;m=plan();m['investigation_questions']='Was placement incomplete or orientation incorrect? Which view is occluded?'
    m['layout_proposal']={'method':'equal-panels','axis':'horizontal','rectangles':[[0,0,48,64],[48,0,48,64]],'preview_time_s':0,'note':'Unverified proposal; operator selected separate sources'}
    original=lp.AI.analyze_with_evidence
    def inspect(pkg,frames,**kw):
        assert pkg.provenance['investigation_questions']==m['investigation_questions']
        assert any('question is not a success criterion' in n for n in pkg.tracking_notes)
        result=original(pkg,frames,**kw)
        wrong={'task_outcome':'uncertain','explanation':'orientation is verified','factual_claims':[{'text':'The object has verified correct orientation','evidence_ids':[pkg.evidence_items[0].evidence_id]}]}
        assert not mc.ef.validate_muse_explanation(wrong,pkg).ok
        return result
    mp.setattr(lp.AI,'analyze_with_evidence',inspect)
    q=prepare(setup,m).json()['quote'];assert s['calls']==[];start(c,q);status=wait(c,q['job_id']);assert status['status']=='completed',status
    a=c.get(f'/api/jobs/{q["job_id"]}/analysis').json()
    assert a['task_outcome']=='uncertain' and not a['physical_events']
    assert a['multicamera']['layout_proposal']['method']=='equal-panels'
    assert a['multicamera']['investigation_questions']==m['investigation_questions']
@pytest.mark.parametrize('field',['offset_s','crop','window_start_s','window_end_s','preview_time_s'])
@pytest.mark.parametrize('bad',[False,True,None,''])
def test_manifest_numeric_types_are_not_coerced_from_boolean_or_empty(field,bad):
    from pydantic import ValidationError
    from multicamera import Manifest
    plan={'source_mode':'composite','task_description':'Synthetic numeric contract','crops_confirmed':True,
          'cameras':[{'name':'one','object_concept':'block','destination_concept':'drawer','offset_s':0,'crop':[0,0,64,64]}],
          'window_start_s':0,'window_end_s':1}
    if field in ('offset_s','crop'):
        if field=='crop':plan['cameras'][0]['crop'][0]=bad
        else:plan['cameras'][0][field]=bad
    elif field=='preview_time_s':
        plan['layout_proposal']={'method':'equal-panels','axis':'horizontal','rectangles':[[0,0,64,64]],'preview_time_s':bad,'note':'Synthetic suggested layout'}
    else:plan[field]=bad
    with pytest.raises(ValidationError):Manifest.model_validate(plan)
