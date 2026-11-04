import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/reassess-task-coverage.py'
spec=importlib.util.spec_from_file_location('coverage_report',SCRIPT)
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)


@pytest.fixture
def job(tmp_path):
    d=tmp_path/'original';(d/'cam1').mkdir(parents=True)
    def write(name,data): (d/name).write_text(json.dumps(data),encoding='utf-8')
    (d/'source1.mp4').write_bytes(b'synthetic source bytes; no provider call')
    (d/'cam1/video.mp4').write_bytes(b'synthetic derived bytes; hash fixture only')
    camera={'camera_id':'cam1','source_video_id':'source1','source_sha256':R.digest(d/'source1.mp4'),
        'sha256':R.digest(d/'cam1/video.mp4'),'crop':[0,0,64,64],'motion':'static','fps':10,'n_frames':10,
        'frame_start':0,'frame_end':8,'timestamps_s':[i/10 for i in range(10)],'playback_offset_s':0,
        'object_concept':'block','destination_concept':'drawer'}
    write('multicamera.json',{'cameras':[camera],'sources':[{'source_video_id':'source1','sha256':camera['source_sha256']}]})
    write('prepared-multicamera.json',{'manifest_sha256':R.digest(d/'multicamera.json')})
    write('analysis.json',{'episode_key':'multicamera','task':'Pick up the block, put it in the drawer, then close the drawer.',
        'task_outcome':'uncertain','evidence_catalog':[],'multicamera':{'cameras':[camera]}})
    write('cam1/provenance.json',camera)
    write('cam1/provider_observations.json',{'observations':[{'frame_index':i} for i in range(4)]})
    write('muse_result.json',{'paid_call':False,'hypotheses':[]});write('evidence_package.json',{'evidence_catalog':[]})
    return d


def test_separate_report_preserves_all_original_bytes_and_context_scope(job,tmp_path):
    before=R.hashes(job);result,text=R.build_report(job)
    assert R.hashes(job)==before and result['completion']=='unverified'
    assert [a['state'] for a in result['assessments'] if a['kind']=='action']==['unverified']*3
    assert all(f['original_frame']<8 for f in result['context_frames'])
    out=tmp_path/'report'
    p=subprocess.run([sys.executable,str(SCRIPT),str(job),'--output',str(out)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    assert (out/'REPORT.md').is_file() and R.hashes(job)==before


@pytest.mark.parametrize('changed',['source1.mp4','cam1/video.mp4','multicamera.json','cam1/provenance.json'])
def test_changed_approved_inputs_are_rejected(job,changed):
    path=job/changed
    if changed.endswith('json'):
        data=R.read(path);data['crop']=[2,2,32,32];path.write_text(json.dumps(data))
    else:path.write_bytes(b'changed source')
    with pytest.raises(ValueError):R.build_report(job)


def test_cannot_write_report_into_original_job(job):
    before=R.hashes(job)
    p=subprocess.run([sys.executable,str(SCRIPT),str(job),'--output',str(job/'report')],capture_output=True,text=True)
    assert p.returncode==2 and R.hashes(job)==before


def test_api_reassesses_on_read_without_mutating_saved_results(job,monkeypatch):
    import live_api as api
    monkeypatch.setattr(api,'JOBS_ROOT',job.parent)
    a=R.read(job/'analysis.json');a['dry_run']=False
    (job/'analysis.json').write_text(json.dumps(a))
    before=R.hashes(job)
    response=api.get_analysis(job.name)
    assert len([s for s in response['criteria']['assessments'] if s['kind']=='action'])==3
    assert response['criteria']['reassessment']['approved_provenance_verified']
    assert response['task_outcome']==a['task_outcome'] and R.hashes(job)==before
    (job/'cam1/video.mp4').write_bytes(b'changed after approval')
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as blocked:api.get_analysis(job.name)
    assert blocked.value.status_code==409


def test_existing_criteria_get_separate_local_temporal_context_without_rewriting_results(job,monkeypatch):
    import live_api as api
    monkeypatch.setattr(api,'JOBS_ROOT',job.parent)
    a=R.read(job/'analysis.json');a.update(dry_run=False,criteria={'task_text':'Preserved explicit task','assessments':[],'completion':'unverified'})
    (job/'analysis.json').write_text(json.dumps(a));before=R.hashes(job)
    response=api.get_analysis(job.name)
    assert {k:v for k,v in response['criteria'].items() if k not in ('temporal_evidence','coverage','context_frames')}==a['criteria']
    assert response['criteria']['temporal_evidence'][0]['adjacent_box_steps']==[]
    assert R.hashes(job)==before and response['task_outcome']=='uncertain'
    (job/'cam1/video.mp4').write_bytes(b'changed after approval')
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as blocked:api.get_analysis(job.name)
    assert blocked.value.status_code==409


@pytest.mark.parametrize('count',[2,3])
def test_temporal_context_keeps_multiple_cameras_and_identical_track_names_separate(job,count):
    import shutil
    from task_coverage import build_assessment
    manifest=R.read(job/'multicamera.json');first=manifest['cameras'][0]
    for i in range(2,count+1):
        cid=f'cam{i}';shutil.copytree(job/'cam1',job/cid)
        c={**first,'camera_id':cid};manifest['cameras'].append(c)
        (job/cid/'provenance.json').write_text(json.dumps(c))
    for c in manifest['cameras']:
        obs=[{'camera_id':c['camera_id'],'source_video_id':'source1','object_id':'same-id','frame_index':i,'bbox':[10+i,10,20+i,20]} for i in range(8)]
        (job/c['camera_id']/'provider_observations.json').write_text(json.dumps({'observations':obs}))
    (job/'multicamera.json').write_text(json.dumps(manifest));(job/'prepared-multicamera.json').write_text(json.dumps({'manifest_sha256':R.digest(job/'multicamera.json')}))
    analysis=R.read(job/'analysis.json');analysis['multicamera']=manifest;(job/'analysis.json').write_text(json.dumps(analysis))
    criteria,_=build_assessment(job)
    assert len(criteria['temporal_evidence'])==count
    for c in criteria['temporal_evidence']:
        assert all(f['camera_id']==c['camera_id'] for f in c['frames'])
        assert len(c['frames'])<=12//count
    assert criteria['completion']=='unverified'
