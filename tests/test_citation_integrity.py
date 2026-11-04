"""Citation locators are compared to original records, never cached authority."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import live_api as api
from saved_provenance import CITATION_FIELDS, CitationBindingError, citation_authority, single_authority
from test_task_coverage_report import job


def read(d,n):return json.loads((d/n).read_text(encoding='utf-8'))
def write(d,n,v):(d/n).write_text(json.dumps(v),encoding='utf-8')
def inventory(d):return {str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*') if p.is_file()}


@pytest.fixture
def bound(job,monkeypatch):
    original={'evidence_id':'E0','source':'sam:video','kind':'detection','status_context':'observed',
        'frame_start':0,'frame_end':8,'t_start':0,'t_end':.7,'summary':'Original observation',
        'claims':[{'type':'displacement','from_frame':0,'to_frame':7,'value_px':4}]}
    binding={'camera_id':'cam1','source_video_id':'source1','original_evidence_id':'E0','package':'cam1/evidence_package.json'}
    merged={**original,**binding,'evidence_id':'E4'}
    write(job,'cam1/evidence_package.json',{'evidence_catalog':[original]})
    write(job,'evidence_package.json',{'evidence_catalog':[merged],'provenance':{'camera_citations':{'E4':binding}}})
    a=read(job,'analysis.json');a.update(evidence_catalog=[merged],dry_run=False);write(job,'analysis.json',a)
    write(job,'tracks.json',{'frames':{},'tracks':{}})
    monkeypatch.setattr(api,'JOBS_ROOT',job.parent)
    monkeypatch.setattr(api,'_spawn_analyze',lambda *_:pytest.fail('No inference on citation inspection'))
    return job


@pytest.mark.parametrize('field,bad',[('frame_start',3),('frame_end',7),('t_start',.3),('t_end',.6),
    ('package','cam2/evidence_package.json'),('evidence_id','E999'),('camera_id','cam2'),
    ('source_video_id','source2'),('original_evidence_id','E7'),('source','proprio:gripper'),
    ('claims',[]),('status_context','verified'),('summary','Changed meaning')])
def test_changed_locator_claim_or_classification_is_quarantined_on_all_aliases(bound,field,bad):
    a=read(bound,'analysis.json');a['evidence_catalog'][0][field]=bad
    # A self-issued cache must not certify its own changed record.
    a['citation_bindings']={'schema':'demodoctor.citation-bindings/v1','records':{'E4':{'status':'record_match','expected':a['evidence_catalog'][0]}}}
    write(bound,'analysis.json',a);before=inventory(bound)
    with TestClient(api.app) as c:
        for path in ('analysis','files/analysis.json','tracks','files/evidence_package.json','cameras/cam1/video.mp4','sources/source1'):
            r=c.get(f'/api/jobs/{bound.name}/{path}')
            assert r.status_code==409,(path,r.text)
    assert inventory(bound)==before


def test_current_original_record_wins_over_stale_response_cache(bound):
    a=read(bound,'analysis.json');a['citation_bindings']={'untrusted':'stale'};write(bound,'analysis.json',a)
    before=inventory(bound)
    with TestClient(api.app) as c:
        r=c.get(f'/api/jobs/{bound.name}/analysis');assert r.status_code==200,r.text
        b=r.json()['citation_bindings']['records']['E4']
        assert b['status']=='record_match' and b['expected']['t_start']==0
        pkg=read(bound,'evidence_package.json');pkg['evidence_catalog'][0]['frame_start']=3;write(bound,'evidence_package.json',pkg)
        assert c.get(f'/api/jobs/{bound.name}/analysis').status_code==409
    # Only this test's explicit mutation changed bytes.
    before['evidence_package.json']=(bound/'evidence_package.json').read_bytes();assert inventory(bound)==before


@pytest.mark.parametrize('field,bad',[('t_start',.5),('t_end',.75)])
def test_child_record_frame_clock_must_match_even_when_all_merged_copies_agree(bound,field,bad):
    for name in ('analysis.json','evidence_package.json','cam1/evidence_package.json'):
        x=read(bound,name);x['evidence_catalog'][0][field]=bad;write(bound,name,x)
    with TestClient(api.app) as c:assert c.get(f'/api/jobs/{bound.name}/analysis').status_code==409


def test_claim_frame_boolean_cannot_alias_numeric_original_frame(bound):
    a=read(bound,'analysis.json');a['evidence_catalog'][0]['claims'][0]['from_frame']=False;write(bound,'analysis.json',a)
    with TestClient(api.app) as c:assert c.get(f'/api/jobs/{bound.name}/analysis').status_code==409


@pytest.mark.parametrize('field,bad',[('package','cam2/evidence_package.json'),('camera_id','cam2'),('source_video_id','source2')])
def test_merged_original_package_metadata_cannot_disagree_with_its_own_map(bound,field,bad):
    x=read(bound,'evidence_package.json');x['evidence_catalog'][0][field]=bad;write(bound,'evidence_package.json',x)
    with TestClient(api.app) as c:assert c.get(f'/api/jobs/{bound.name}/analysis').status_code==409


def test_camera_analysis_artifact_alias_cannot_bypass_original_binding(bound):
    original=read(bound,'cam1/evidence_package.json')['evidence_catalog'][0]
    write(bound,'cam1/analysis.json',{'evidence_catalog':[original]})
    with TestClient(api.app) as c:
        url=f'/api/jobs/{bound.name}/cameras/cam1/analysis.json'
        assert c.get(url).status_code==200
        altered=deepcopy(original);altered['t_start']=.4
        write(bound,'cam1/analysis.json',{'evidence_catalog':[altered]})
        assert c.get(url).status_code==409


def test_missing_camera_map_is_unverifiable_not_silently_single_camera_authority(bound):
    pkg=read(bound,'evidence_package.json');pkg.pop('provenance');write(bound,'evidence_package.json',pkg)
    with TestClient(api.app) as c:
        r=c.get(f'/api/jobs/{bound.name}/analysis');assert r.status_code==200,r.text
        record=r.json()['citation_bindings']['records']['E4']
        assert record['status']=='unverifiable' and 'map unavailable' in record['reason']
        a=read(bound,'analysis.json');a['evidence_catalog'][0]['t_start']=.4;write(bound,'analysis.json',a)
        assert c.get(f'/api/jobs/{bound.name}/analysis').status_code==409


def test_missing_legacy_metadata_is_not_a_proven_mismatch():
    partial={'evidence_id':'E0','source':'sam:video','summary':'Original saved text'}
    a={'evidence_catalog':[{**partial,'t_start':3}]}
    b=single_authority(a,{'evidence_catalog':[partial]},'original.json',None)['records']['E0']
    assert b['status']=='unverifiable' and 't_start' not in b['expected']
    assert b['expected']['source']=='sam:video'
    with pytest.raises(CitationBindingError):single_authority({'evidence_catalog':[{**partial,'source':'other'}]}, {'evidence_catalog':[partial]},'original.json',None)


def test_unknown_id_in_known_empty_package_is_not_missing_metadata():
    with pytest.raises(CitationBindingError):single_authority({'evidence_catalog':[{'evidence_id':'E1'}]}, {'evidence_catalog':[]},'original.json',None)
    assert single_authority({'evidence_catalog':[{'evidence_id':'E1'}]}, {},'original.json',None)['records']['E1']['status']=='unverifiable'


def test_valid_offset_uses_original_native_clock_not_merged_timestamp(bound):
    m=read(bound,'multicamera.json');m['cameras'][0]['playback_offset_s']=.2
    # Direct authority test: camera preparation validation is covered separately.
    for name in ('analysis.json','evidence_package.json'):
        x=read(bound,name);x['evidence_catalog'][0].update(t_start=-.2,t_end=.5);write(bound,name,x)
    result=citation_authority(bound,read(bound,'analysis.json'),m)['records']['E4']
    assert result['status']=='record_match' and result['expected']['t_start']==-.2
    assert result['playback_offset_s']==.2 # Client must not clamp this to frame zero.


def test_recorded_registry_is_derived_from_six_unchanged_original_sources():
    import importlib.util
    root=Path(__file__).resolve().parents[1];path=root/'scripts/export_citation_bindings.py'
    spec=importlib.util.spec_from_file_location('citation_registry_export',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    expected=module.build();actual=read(root,'web/src/lib/recordedCitationBindings.json')
    assert actual==expected and len(actual)==6
    assert all(b['status']=='record_match' for a in actual.values() for b in a['records'].values())
