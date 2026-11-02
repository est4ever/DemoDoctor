"""Approved binding contracts; synthetic bytes, no paid provider or frozen edits."""
from copy import deepcopy
import hashlib,json,os
import pytest
from fastapi.testclient import TestClient
import live_api as api
from test_task_coverage_report import job
from task_coverage import build_assessment,hashes


def read(job,name):return json.loads((job/name).read_text())
def write(job,name,value):(job/name).write_text(json.dumps(value),encoding='utf-8')
def approve(job,manifest):
    write(job,'multicamera.json',manifest)
    write(job,'prepared-multicamera.json',{'manifest_sha256':hashlib.sha256((job/'multicamera.json').read_bytes()).hexdigest()})


@pytest.fixture
def ready(job,monkeypatch):
    a=read(job,'analysis.json');a['dry_run']=False
    write(job,'analysis.json',a);c=build_assessment(job)[0]
    a['criteria']=c;write(job,'analysis.json',a);write(job,'tracks.json',{'frames':{},'tracks':{}})
    monkeypatch.setattr(api,'JOBS_ROOT',job.parent)
    monkeypatch.setattr(api,'_spawn_analyze',lambda *_:pytest.fail('No inference on saved reads'))
    return job


@pytest.mark.parametrize('field,bad',[('source_sha256','c'*64),('camera_sha256','d'*64),('crop',[8,8,32,32]),
    ('camera_id','cam2'),('source_video_id','source2'),('original_frame',999),('original_timestamp_s',77),('camera_sha256','not-a-hash')])
def test_cached_temporal_metadata_is_rebuilt_not_trusted_or_written(ready,field,bad):
    a=read(ready,'analysis.json');a['criteria']['temporal_evidence'][0]['frames'][0][field]=bad
    a['criteria']['coverage'][0]['sha256']='stale';write(ready,'analysis.json',a);before=hashes(ready)
    expected=build_assessment(ready)[0]
    with TestClient(api.app) as client:
        for path in ('analysis','files/analysis.json'):
            response=client.get(f'/api/jobs/{ready.name}/{path}');assert response.status_code==200,response.text
            result=response.json();assert result['criteria']['temporal_evidence']==expected['temporal_evidence']
            assert result['criteria']['coverage']==expected['coverage'] and result['task_outcome']=='uncertain'
    assert hashes(ready)==before


@pytest.mark.parametrize('which',['source1.mp4','cam1/video.mp4'])
def test_modified_bytes_with_same_size_and_mtime_are_rejected_without_a_cache_bypass(ready,which):
    # Prime all relevant read paths before an equal-length media mutation.
    with TestClient(api.app) as client:
        assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==200
        path=ready/which;st=path.stat();raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:]);os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
        for suffix in ('analysis','files/analysis.json','tracks','sources/source1','cameras/cam1/video.mp4','cameras/cam1/provenance.json'):
            r=client.get(f'/api/jobs/{ready.name}/{suffix}');assert r.status_code==409,(suffix,r.text)


@pytest.mark.parametrize('field,bad',[('source_sha256','f'*64),('sha256','not-a-hash'),('crop',[-2,0,64,64]),
    ('frame_start',-1),('frame_mapping',[{'camera_frame':0,'source_frame':7}]),('source_video_id','source2')])
def test_content_hashes_do_not_replace_source_crop_frame_consistency(ready,field,bad):
    m=read(ready,'multicamera.json');m['cameras'][0][field]=bad
    write(ready,'cam1/provenance.json',m['cameras'][0]);approve(ready,m)
    a=read(ready,'analysis.json');a['multicamera']=m;write(ready,'analysis.json',a)
    with TestClient(api.app) as client:assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==409


def test_swapped_camera_record_and_analysis_frame_source_are_quarantined(ready):
    p=read(ready,'cam1/provenance.json');p['camera_id']='cam2';write(ready,'cam1/provenance.json',p)
    with TestClient(api.app) as client:
        assert client.get(f'/api/jobs/{ready.name}/cameras/cam1/video.mp4').status_code==409
        p['camera_id']='cam1';write(ready,'cam1/provenance.json',p)
        a=read(ready,'analysis.json');a['frame_catalog']=[{'frame_ref':'F0','camera_id':'cam1','source_video_id':'source2','original_frame':0,'original_timestamp_s':0,'timestamp_s':0}];write(ready,'analysis.json',a)
        assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==409


@pytest.mark.parametrize('field,bad',[('camera_id','cam2'),('source_video_id','source2'),('source_frame',3),('original_timestamp_s',.6)])
def test_wrong_observation_binding_is_withheld_and_never_served_as_current_camera(ready,field,bad):
    obs={'frame_index':0,'camera_id':'cam1','source_video_id':'source1','source_frame':0,'original_timestamp_s':0,'bbox':[1,1,8,8],'object_id':'block:0'}
    obs[field]=bad;write(ready,'cam1/provider_observations.json',{'observations':[obs]})
    before=hashes(ready)
    with TestClient(api.app) as client:
        r=client.get(f'/api/jobs/{ready.name}/analysis');assert r.status_code==409
        assert 'quarantined' in r.json()['detail']
        assert client.get(f'/api/jobs/{ready.name}/cameras/cam1/provider_observations.json').status_code==409
    assert hashes(ready)==before


def test_valid_approved_legacy_camera_without_redundant_mapping_stays_read_only(ready):
    before=hashes(ready)
    with TestClient(api.app) as client:
        assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==200
        assert client.get(f'/api/jobs/{ready.name}/sources/source1').status_code==200
        assert client.get(f'/api/jobs/{ready.name}/cameras/cam1/video.mp4').status_code==200
    assert hashes(ready)==before


def test_missing_approval_is_not_recreated_on_read(ready):
    (ready/'prepared-multicamera.json').unlink();before=hashes(ready)
    with TestClient(api.app) as client:assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==409
    assert hashes(ready)==before


def test_deleted_manifest_cannot_downgrade_a_camera_job_to_unchecked_legacy_routes(ready):
    (ready/'multicamera.json').unlink();before=hashes(ready)
    with TestClient(api.app) as client:
        for suffix in ('analysis','files/analysis.json','tracks','files/tracks.json','sources/source1','cameras/cam1/video.mp4'):
            assert client.get(f'/api/jobs/{ready.name}/{suffix}').status_code==409
    assert hashes(ready)==before


def test_valid_dynamic_evidence_is_not_http_cached(ready):
    with TestClient(api.app) as client:
        for suffix in ('analysis','files/analysis.json','sources/source1','cameras/cam1/video.mp4'):
            r=client.get(f'/api/jobs/{ready.name}/{suffix}')
            assert r.status_code==200 and r.headers['cache-control']=='no-store'


def test_stale_observation_hash_and_fabricated_cached_steps_are_recomputed(ready):
    a=read(ready,'analysis.json');t=a['criteria']['temporal_evidence'][0]
    t['provider_observations_sha256']='f'*64;t['adjacent_box_steps']=[{'frames':[0,999],'distance_px':999999}]
    write(ready,'analysis.json',a);before=hashes(ready)
    with TestClient(api.app) as client:
        r=client.get(f'/api/jobs/{ready.name}/analysis');assert r.status_code==200
        result=r.json()['criteria']['temporal_evidence'][0]
        assert result['adjacent_box_steps']==[]
        assert result['provider_observations_sha256']==hashlib.sha256((ready/'cam1/provider_observations.json').read_bytes()).hexdigest()
    assert hashes(ready)==before


@pytest.mark.parametrize('corruption',['unknown_muse_frame','wrong_package_camera','missing_original_id'])
def test_historical_citation_locator_must_match_its_original_package(ready,corruption):
    a=read(ready,'analysis.json')
    source={'camera_id':'cam1','source_video_id':'source1','original_frame':0,'original_timestamp_s':0}
    binding={'camera_id':'cam1','source_video_id':'source1','original_evidence_id':'E0','package':'cam1/evidence_package.json'}
    write(ready,'cam1/evidence_package.json',{'evidence_catalog':[{'evidence_id':'E0'}]})
    if corruption=='wrong_package_camera':binding['package']='cam2/evidence_package.json'
    if corruption=='missing_original_id':binding['original_evidence_id']='E9'
    write(ready,'evidence_package.json',{'provenance':{'frame_sources':{'F0':source},'camera_citations':{'E0':binding}}})
    a['frame_catalog']=[{'frame_ref':'F9' if corruption=='unknown_muse_frame' else 'F0',**source,'timestamp_s':0}]
    a['evidence_catalog']=[{'evidence_id':'E0',**{k:binding[k] for k in ('camera_id','source_video_id','original_evidence_id')}}]
    write(ready,'analysis.json',a)
    with TestClient(api.app) as client:assert client.get(f'/api/jobs/{ready.name}/analysis').status_code==409


@pytest.mark.parametrize('legacy',[False,True])
def test_unbound_or_dry_run_temporal_cache_is_not_served_through_analysis_aliases(ready,legacy):
    if legacy:
        from test_saved_jobs import make
        job=make(ready.parent,job_id='legacy-unbound',dry=True)
    else:job=ready
    a=read(job,'analysis.json');a['dry_run']=True
    a.setdefault('criteria',{})['temporal_evidence']=[{'frames':[{'frame_ref':'T_bad','source_sha256':'wrong'}]}]
    write(job,'analysis.json',a)
    with TestClient(api.app) as client:
        for suffix in ('analysis','files/analysis.json'):
            r=client.get(f'/api/jobs/{job.name}/{suffix}');assert r.status_code==200
            assert not r.json()['criteria'].get('temporal_evidence')


def test_reopen_cannot_bypass_root_track_camera_binding(ready):
    from test_saved_jobs import make
    job=make(ready.parent,job_id='reopen-track-binding',multi=True)
    tracks=read(job,'tracks.json');tracks.update(camera_id='cam2',source_video_id='source1');write(job,'tracks.json',tracks)
    with TestClient(api.app) as client:assert client.get(f'/api/jobs/{job.name}/reopen').status_code==409


def test_child_analysis_alias_cannot_expose_an_unbound_temporal_cache(ready):
    write(ready,'cam1/analysis.json',{'criteria':{'temporal_evidence':[{'frames':[{'source_sha256':'wrong'}]}]}})
    with TestClient(api.app) as client:assert client.get(f'/api/jobs/{ready.name}/cameras/cam1/analysis.json').status_code==409
