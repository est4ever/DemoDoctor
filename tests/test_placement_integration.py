"""Bounded real-artifact product regression. No provider requests or new labels.

Set DEMODOCTOR_PLACEMENT_FIXTURE to a generated placement job for artifact tests.
The fixture is copied before every mutation; original outputs never change.
"""
import json
import os
from pathlib import Path
import shutil
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from placement_assessment import service


@pytest.fixture
def saved(tmp_path):
    path=os.environ.get('DEMODOCTOR_PLACEMENT_FIXTURE')
    if not path:pytest.skip('Real local assessment fixture not configured')
    source=Path(path);root=tmp_path/'jobs';root.mkdir()
    job=root/source.name;shutil.copytree(source,job)
    shutil.copyfile(source.parent/'.placement-key',root/'.placement-key')
    service.verify(job)
    return job


def test_valid_reopen_source_and_citations(saved):
    before={p.relative_to(saved).as_posix():service.sha(p) for p in saved.rglob('*') if p.is_file()}
    result=service.verify(saved)
    assert result['failure_detected'] and result['time_interval']['start_frame']==2074
    assert result['time_interval']['start_seconds']==pytest.approx(69.13333333333334)
    assert result['onset_frame'] is None and result['possible_causes']==[]
    assert result['physical_events']==[] and result['muse_status']=='provider_skipped'
    assert len(result['source_citations'])==16
    assert result['observed_evidence'][0]['minimum_lateral_separation_px']==93
    app=FastAPI();service.register(app,saved.parent);client=TestClient(app)
    for _ in range(2):
        assert client.get('/api/placement/jobs/'+saved.name).status_code==200
        assert client.get(f'/api/placement/jobs/{saved.name}/frames/2074/source').status_code==200
    assert client.get(f'/api/placement/jobs/{saved.name}/frames/2073/source').status_code==404
    assert before=={p.relative_to(saved).as_posix():service.sha(p) for p in saved.rglob('*') if p.is_file()}


@pytest.mark.parametrize('change',['added','altered','missing','source','seal','camera','timestamp','muse','stale'])
def test_tampered_evidence_quarantined_on_all_reopen_surfaces(saved,change,monkeypatch):
    if change=='added':service.write(saved/'unsealed-features.json',{'events':[{'kind':'grasp','status':'Supported'}]})
    elif change=='missing':(saved/'template_receipt.json').unlink()
    elif change=='source':
        with (saved/'video.mp4').open('ab') as f:f.write(b'altered')
    elif change=='seal':
        seal=service.read(saved/'placement-seal.json');seal['signature']='0'*64;service.write(saved/'placement-seal.json',seal)
    else:
        p=saved/'placement-result.json';r=service.read(p)
        if change=='camera':r['source_citations'][0]['camera_id']='wrong-camera'
        elif change=='timestamp':r['source_citations'][0]['timestamp_s']=3.89
        elif change=='muse':r['muse_status']='historical_genuine_not_rerun'
        elif change=='stale':r['source_sha256']='0'*64
        else:r['failure_detected']=False
        service.write(p,r)
    with pytest.raises((ValueError,OSError)):service.verify(saved)
    app=FastAPI();service.register(app,saved.parent);client=TestClient(app)
    assert client.get('/api/placement/jobs/'+saved.name).status_code==409
    assert client.get(f'/api/placement/jobs/{saved.name}/frames/2074/overlay').status_code==409
    import live_api
    monkeypatch.setattr(live_api,'JOBS_ROOT',saved.parent)
    client=TestClient(live_api.app)
    for suffix in ['reopen','analysis','tracks','files/video.mp4']:
        assert client.get(f'/api/jobs/{saved.name}/{suffix}').status_code==409
    row=client.get('/api/jobs').json()['jobs'][0]
    assert not row['can_open'] and 'outcome' not in row


def test_registry_requires_startup_hash_and_unknown_sources_fail(monkeypatch,tmp_path):
    from placement_assessment import portable
    monkeypatch.setattr(portable,'STORE',tmp_path/'unregistered-assets')
    monkeypatch.delenv('DEMODOCTOR_PLACEMENT_REGISTRY',raising=False)
    assert service.options()['available'] is False
    with pytest.raises(ValueError):service.create(tmp_path,'unknown')
    p=tmp_path/'registry.json';service.write(p,{'schema':'forged'})
    monkeypatch.setenv('DEMODOCTOR_PLACEMENT_REGISTRY',str(p))
    monkeypatch.setenv('DEMODOCTOR_PLACEMENT_REGISTRY_SHA256','0'*64)
    with pytest.raises(ValueError):service.options()


def test_ported_predicate_has_no_provider_or_label_inputs():
    import inspect
    from placement_assessment.detector import assess
    assert list(inspect.signature(assess).parameters)==['source','images','template']
    code=inspect.getsource(assess)
    assert '2074' not in code and '69.133' not in code
    assert 'window_candidate(part)' in code and "'final_region_not_image_stable'" in code
