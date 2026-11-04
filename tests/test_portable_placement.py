"""Portable admission rejects substitutes; no providers or synthetic detections."""
import json
from pathlib import Path
import shutil
import pytest
from placement_assessment import portable as p
from placement_assessment import service


def test_missing_assets_produce_setup_requirement(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'STORE',tmp_path/'assets')
    monkeypatch.delenv('DEMODOCTOR_PLACEMENT_REGISTRY',raising=False)
    result=service.options()
    assert not result['available'] and '--download' in result['reason'] and '--bf010' in result['reason']


def test_public_manifest_has_no_private_dependency_or_labels():
    data=p.manifest();text=json.dumps(data)
    assert all(s['url'].startswith('https://huggingface.co/datasets/kantine/BotFails/resolve/'+data['revision']) for s in data['sources'].values())
    assert sum(s['bytes'] for s in data['sources'].values())==63245876
    assert not any(x in text for x in ['C:\\Users','C:/Users','outcome_label','failure_timestamp','2074','69.133'])
    raw=p.read(p.ASSETS/data['template']['destination_cache'])
    assert 'cache_dir' not in raw and 'overlay_paths' not in raw
    assert raw['diagnostics']['usage']['dish rack']['terminal_event']=='response.completed'


@pytest.mark.parametrize('target',['manifest','template'])
def test_altered_public_authority_is_rejected(tmp_path,monkeypatch,target):
    shutil.copytree(p.ASSETS,tmp_path/'assets');monkeypatch.setattr(p,'ASSETS',tmp_path/'assets')
    file=p.ASSETS/('manifest.json' if target=='manifest' else 'rack/27ae50fe53698423265d1ac9/summary.json')
    file.write_bytes(file.read_bytes()+b' ')
    with pytest.raises(ValueError):p.manifest()


def test_unknown_source_rejected_before_decode(tmp_path):
    file=tmp_path/'renamed-original.mp4';file.write_bytes(b'not the approved original')
    with pytest.raises(ValueError,match='size/hash mismatch'):
        p.checked_index(file,p.manifest()['sources']['ep010'])


def test_explicit_bad_replacement_is_not_hidden_by_existing_install(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'STORE',tmp_path)
    data=p.manifest();(tmp_path/data['sources']['bf000']['filename']).write_bytes(b'existing')
    bad=tmp_path/'bad.mp4';bad.write_bytes(b'derivative')
    checked=[]
    original=p.checked_index
    def record(path,spec):
        checked.append(path)
        return original(path,spec)
    monkeypatch.setattr(p,'checked_index',record)
    with pytest.raises(ValueError,match='size/hash mismatch'):p.provision(supplied={'bf000':bad})
    assert checked==[bad.resolve()]  # Must validate the explicit input, not hide it behind the existing file.


def test_interrupted_download_is_not_automatically_retried(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'STORE',tmp_path)
    spec=p.manifest()['sources']['bf000']
    (tmp_path/(spec['filename']+'.part')).write_bytes(b'interrupted')
    def forbidden(*args,**kwargs):raise AssertionError('No network retry permitted')
    monkeypatch.setattr(p.urllib.request,'urlopen',forbidden)
    with pytest.raises(ValueError,match='Incomplete prior acquisition'):p.provision(download=True)


def test_stale_registration_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'STORE',tmp_path)
    p.write(tmp_path/'registration.json',{'manifest_sha256':'0'*64})
    with pytest.raises(ValueError,match='Stale portable'):p.load_registry()


def test_decoder_identity_mismatch_cannot_register(tmp_path,monkeypatch):
    file=tmp_path/'source.mp4';file.write_bytes(b'fixture')
    spec={'bytes':7,'sha256':p.sha(file),'n_frames':2,'width':4,'height':4,'fps':30,'decoded_index_sha256':'0'*64}
    monkeypatch.setattr(p,'index',lambda *a:{'n_frames':2,'width':4,'height':4,'fps':30,'frames':[]})
    with pytest.raises(ValueError,match='Decoded frame identities'):p.checked_index(file,spec)
