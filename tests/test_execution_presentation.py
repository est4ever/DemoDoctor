"""Execution labels describe local records, never a scientific verdict or billing attestation."""
import hashlib
import json
from pathlib import Path
import pytest
from saved_jobs import execution_summary


def write(root, name, value):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))


def records(root, cameras=1):
    write(root,'analysis.json',{'dry_run':False,'task_outcome':'uncertain',
        'multicamera':{'cameras':[{'camera_id':f'cam{i+1}'} for i in range(cameras)]}})
    write(root,'status.json',{'status':'completed','dry_run':False})
    write(root,'muse_result.json',{'paid_call':True,'dry_run':False,'model':'accounts/fireworks/models/muse-spark-open'})
    for i in range(cameras):
        write(root,f'cam{i+1}/provider_observations.json',{
            'provider_calls':[{'status':'completed','from_cache':False}],
            'usage_events':[{'provider':'meta_sam','kind':'video_window','status':'completed'}]})


@pytest.mark.parametrize('cameras',[1,2,3])
def test_real_label_requires_complete_provider_records_and_never_changes_them(tmp_path,cameras):
    records(tmp_path,cameras)
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*.json')}
    assert execution_summary(tmp_path)['mode']=='real'
    assert 'Physical actions are not thereby verified' in execution_summary(tmp_path)['note']
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    (tmp_path/f'cam{cameras}/provider_observations.json').unlink()
    assert execution_summary(tmp_path)['mode']=='unconfirmed'


@pytest.mark.parametrize('record,value',[
    ('analysis.json',{'dry_run':True}),('status.json',{'status':'completed','dry_run':True}),
    ('request.json',{'cache_only':True}),('muse_result.json',{'paid_call':False}),
    ('muse_result.json',{'paid_call':True,'dry_run':False,'model':'another-model'}),
    ('cam1/provider_observations.json',{'provider_calls':[{'status':'completed','from_cache':True}]}),
])
def test_dry_cache_mock_and_unconfirmed_are_not_reported_as_real(tmp_path,record,value):
    records(tmp_path);write(tmp_path,record,value)
    assert execution_summary(tmp_path)['mode']!='real'


def test_legacy_missing_records_remain_accessible_without_claiming_real(tmp_path):
    write(tmp_path,'analysis.json',{'dry_run':False,'task_outcome':'uncertain'})
    assert execution_summary(tmp_path)['mode']=='unconfirmed'
    write(tmp_path,'muse_result.json',{'paid_call':False})
    assert execution_summary(tmp_path)['mode']=='experimental'
