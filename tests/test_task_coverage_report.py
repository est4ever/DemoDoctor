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
    response=api.get_analysis(job.name)
    assert response['task_coverage_error'] and 'criteria' not in response
