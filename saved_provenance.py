"""Validate saved camera evidence against its approved extraction record.

Content hashes identify bytes. IDs, crop geometry and native frame mappings bind
those bytes to a camera. Neither is physical identity, calibrated 3D evidence,
nor tamper-proof authentication against an owner replacing all local records.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re


class ProvenanceError(ValueError):
    pass


class CitationBindingError(ProvenanceError):
    pass


CITATION_FIELDS=('source','kind','status_context','frame_start','frame_end','t_start','t_end','summary','claims','track_id','event_index')


def catalog(records):
    if not isinstance(records,list):raise CitationBindingError('Original evidence catalog is malformed')
    result={}
    for r in records:
        if not isinstance(r,dict):raise CitationBindingError('Original evidence record is malformed')
        eid=r.get('evidence_id')
        if not isinstance(eid,str) or not eid or eid in result:raise CitationBindingError('Missing or duplicate evidence ID')
        result[eid]=r
    return result


def same_value(a,b):
    if number(a) and number(b):return abs(a-b)<=1e-9
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(same_value(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(same_value(x,y) for x,y in zip(a,b))
    return a==b


def check_record(actual,expected,known_fields=None):
    """Missing historical fields are unverified; supplied conflicting fields fail."""
    missing=[]
    for key in CITATION_FIELDS:
        if key not in (known_fields if known_fields is not None else expected):
            if key not in ('track_id','event_index') or actual.get(key) is not None:missing.append('original '+key)
            continue
        if key not in actual and expected.get(key) is not None:
            missing.append(key);continue
        if not same_value(actual.get(key),expected.get(key)):
            raise CitationBindingError('Evidence record disagrees with its original '+key)
    return missing


def single_authority(analysis,package,package_name,package_sha):
    records=catalog(package.get('evidence_catalog',[]));result={}
    for eid,item in catalog(analysis.get('evidence_catalog',[])).items():
        original=records.get(eid)
        if original is None:
            # No original catalog is missing information; an unknown ID in an
            # available catalog is a proven mismatch, never a substitute match.
            if 'evidence_catalog' in package:raise CitationBindingError('Evidence ID is absent from the original package')
            result[eid]={'status':'unverifiable','reason':'Original evidence catalog unavailable; no validated seek metadata.'};continue
        missing=check_record(item,original)
        if 'package' in item and item['package']!=package_name:raise CitationBindingError('Saved citation points to another original package')
        for key in ('camera_id','source_video_id','original_evidence_id'):
            if key in item and item[key]!=original.get(key,eid if key=='original_evidence_id' else None):raise CitationBindingError('Single-source citation binding mismatch')
        result[eid]={'status':'unverifiable' if missing else 'record_match','reason':'Missing historical fields: '+', '.join(missing) if missing else 'Original record locator matched; source-video identity is a separate check.',
            'package':package_name,'package_sha256':package_sha,'original_evidence_id':eid,'expected':{k:original[k] for k in CITATION_FIELDS if k in original}}
    return {'schema':'demodoctor.citation-bindings/v1','records':result,'scope':'Locator integrity only; not independent verification of physical claims.'}


def citation_authority(job,analysis,manifest=None):
    """Fresh original records, never a cached analysis-side authority document."""
    path=file(job,'evidence_package.json')
    package=read(job,'evidence_package.json') if path.is_file() else {}
    bindings=package.get('provenance',{}).get('camera_citations',{})
    if not bindings:
        if manifest is None:return single_authority(analysis,package,'evidence_package.json',digest(path) if path.is_file() else None)
        # A merged camera catalog alone cannot certify its child-package binding.
        # Preserve legacy inspection, but never downgrade this to single-camera authority.
        originals=catalog(package.get('evidence_catalog',[]));result={}
        for eid,item in catalog(analysis.get('evidence_catalog',[])).items():
            original=originals.get(eid)
            if original is None and 'evidence_catalog' in package:raise CitationBindingError('Evidence ID absent from saved package')
            if original is not None:
                check_record(item,original)
                for key in ('camera_id','source_video_id','original_evidence_id','package'):
                    if key in original and key in item and item[key]!=original[key]:raise CitationBindingError('Saved camera citation differs from original record')
            result[eid]={'status':'unverifiable','reason':'Original camera citation map unavailable; source-to-child-package binding and camera seek are unverified.',
                **{k:original[k] for k in ('camera_id','source_video_id','original_evidence_id','package') if original is not None and k in original},
                'expected':{k:original[k] for k in CITATION_FIELDS if original is not None and k in original}}
        return {'schema':'demodoctor.citation-bindings/v1','records':result,'scope':'Missing camera citation map; no verified source-to-package binding or seek.'}
    cameras={c['camera_id']:c for c in (manifest or {}).get('cameras',[])}
    merged=catalog(package.get('evidence_catalog',[]));items=catalog(analysis.get('evidence_catalog',[]));result={}
    if 'evidence_catalog' in package and set(merged)!=set(bindings):raise CitationBindingError('Merged package IDs disagree with the original citation map')
    if set(items)!=set(bindings):raise CitationBindingError('Saved evidence IDs disagree with the original citation map')
    for eid,item in items.items():
        b=bindings[eid];cid=b['camera_id'];camera=cameras[cid];original_path=cid+'/evidence_package.json'
        if b.get('package')!=original_path:raise CitationBindingError('Original evidence package camera mismatch')
        original=catalog(read(job,original_path).get('evidence_catalog',[])).get(b['original_evidence_id'])
        if original is None:raise CitationBindingError('Original evidence ID unavailable')
        fs,fe=original.get('frame_start'),original.get('frame_end')
        if fs is not None or fe is not None:
            if type(fs) is not int or type(fe) is not int or not camera['frame_start']<=fs<fe<=camera['frame_end']:raise CitationBindingError('Original evidence has an invalid native frame span')
            for key,lo,hi in (('t_start',fs/camera['fps'],fs/camera['fps']),('t_end',(fe-1)/camera['fps'],fe/camera['fps'])):
                t=original.get(key)
                if t is not None and (not number(t) or min(abs(t-lo),abs(t-hi))>.000500001):raise CitationBindingError('Original evidence timestamp does not bind its native frames')
        expected={k:original.get(k) for k in CITATION_FIELDS};offset=camera['playback_offset_s']
        for key in ('t_start','t_end'):
            if expected[key] is not None:
                if not number(expected[key]):raise CitationBindingError('Original timestamp is malformed')
                expected[key]-=offset
        if original.get('summary') is not None and camera.get('name') is not None:
            expected['summary']=f"[{cid} — {camera['name']}] {original['summary']}"
        for row in (item,merged.get(eid,{})):
            for key in ('camera_id','source_video_id','original_evidence_id','package'):
                if key in row and row[key]!=b[key]:raise CitationBindingError('Saved citation '+key+' differs from original binding')
        for key in ('camera_id','source_video_id'):
            if key in original and original[key]!=b[key]:raise CitationBindingError('Original record camera/source differs from citation map')
        # Validate the merged package itself against the original child record.
        # IDs merely existing cannot certify a changed span/claim/classification.
        if eid in merged:check_record(merged[eid],expected,set(original))
        missing=check_record(item,expected,set(original))
        result[eid]={'status':'unverifiable' if missing else 'record_match','reason':'Missing historical fields: '+', '.join(missing) if missing else 'Original camera record and shared-time locator matched.',
            **b,'package_sha256':digest(file(job,original_path)),'playback_offset_s':offset,'expected':{k:v for k,v in expected.items() if k in original}}
    return {'schema':'demodoctor.citation-bindings/v1','records':result,'scope':'Original camera-package binding and locator equality; physical claims keep their existing verification status.'}


def file(job, name):
    root=Path(job).resolve();p=(root/name).resolve()
    if not p.is_relative_to(root):raise ProvenanceError('Saved provenance path escapes the investigation')
    return p


def read(job,name):
    try:
        value=json.loads(file(job,name).read_text(encoding='utf-8'))
        if not isinstance(value,dict):raise ValueError('Object required')
        return value
    except (OSError,ValueError,TypeError) as exc:raise ProvenanceError('Saved provenance artifact missing or malformed: '+name) from exc


def digest(path):
    h=hashlib.sha256()
    try:
        with path.open('rb') as f:
            while chunk:=f.read(1024*1024):h.update(chunk)
    except OSError as exc:raise ProvenanceError('Saved provenance media unavailable') from exc
    return h.hexdigest()


def hash_value(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def frame(camera,record):
    """Validate an explicitly camera-tagged frame, never substitute another view."""
    f=record.get('original_frame',record.get('source_frame',record.get('frame_index')))
    if type(f) is not int or not camera['frame_start']<=f<camera['frame_end']:raise ProvenanceError('Frame outside approved camera interval')
    for key in ('camera_id','source_video_id'):
        if key in record and record[key]!=camera[key]:raise ProvenanceError('Frame camera/source mismatch')
    if 'source_frame' in record and record['source_frame']!=f:raise ProvenanceError('Frame-to-source mismatch')
    if 'frame_index' in record and record['frame_index']!=f:raise ProvenanceError('Native frame index mismatch')
    t=camera['timestamps_s'][f]
    for key in ('source_timestamp_s','original_timestamp_s'):
        if key in record and (not number(record[key]) or abs(record[key]-t)>.000500001):raise ProvenanceError('Native frame timestamp mismatch')
    for key in ('shared_timestamp_s','timestamp_s'):
        # Provider timestamp_s is native; frame catalog timestamp_s is shared.
        if key=='timestamp_s' and 'frame_ref' not in record:continue
        if key in record and (not number(record[key]) or abs(record[key]-(t-camera['playback_offset_s']))>1e-6):raise ProvenanceError('Shared frame timestamp mismatch')
    if 'native_image_dimensions' in record and 'width' in camera and record['native_image_dimensions']!=[camera['width'],camera['height']]:raise ProvenanceError('Camera-local dimensions mismatch')


def validate(job, analysis=None):
    """No persistent validation cache: current approved metadata and bytes checked.

    Legacy single-camera (non-manifest) jobs use their original path. Camera jobs
    need the preparation receipt; missing bindings are not invented on reopen.
    Older approved records may omit redundant frame_mapping/source probe fields.
    Their explicit native timestamps and extraction record remain authoritative.
    """
    try:
        raw=file(job,'multicamera.json').read_bytes();m=json.loads(raw)
    except (OSError,ValueError) as exc:raise ProvenanceError('Camera manifest unavailable or malformed') from exc
    approval=read(job,'prepared-multicamera.json')
    if not hash_value(approval.get('manifest_sha256')) or hashlib.sha256(raw).hexdigest()!=approval['manifest_sha256']:raise ProvenanceError('Camera manifest differs from approved preparation')
    sources=m.get('sources');cameras=m.get('cameras')
    if not isinstance(sources,list) or not 1<=len(sources)<=3 or not isinstance(cameras,list) or not 1<=len(cameras)<=3:raise ProvenanceError('Invalid source/camera collection')
    sm={};cm={}
    for s in sources:
        sid=s.get('source_video_id')
        if sid not in {'source1','source2','source3'} or sid in sm or not hash_value(s.get('sha256')):raise ProvenanceError('Invalid/duplicate source identity or hash')
        if digest(file(job,sid+'.mp4'))!=s['sha256']:raise ProvenanceError('Original source content hash mismatch')
        sm[sid]=s
    for c in cameras:
        cid=c.get('camera_id');sid=c.get('source_video_id')
        if cid not in {'cam1','cam2','cam3'} or cid in cm or sid not in sm:raise ProvenanceError('Invalid/duplicate camera-to-source binding')
        if not hash_value(c.get('sha256')) or not hash_value(c.get('source_sha256')) or c['source_sha256']!=sm[sid]['sha256']:raise ProvenanceError('Camera-to-original-source hash mismatch')
        if digest(file(job,cid+'/video.mp4'))!=c['sha256']:raise ProvenanceError('Derived camera content hash mismatch')
        p=read(job,cid+'/provenance.json')
        # Compare the entire approved camera record, not just five convenient fields.
        if p!=c:raise ProvenanceError('Camera provenance differs from approved extraction record')
        start,end,n=c.get('frame_start'),c.get('frame_end'),c.get('n_frames');ts=c.get('timestamps_s');fps=c.get('fps');offset=c.get('playback_offset_s')
        if not all(type(v) is int for v in (start,end,n)) or not 0<=start<end<=n or not number(fps) or fps<=0 or not number(offset):raise ProvenanceError('Invalid approved native interval')
        if not isinstance(ts,list) or len(ts)!=n or any(not number(t) or abs(t-i/fps)>1e-6 for i,t in enumerate(ts)):raise ProvenanceError('Invalid native camera timestamps')
        rect=c.get('crop');s=sm[sid]
        if rect is not None:
            if not isinstance(rect,list) or len(rect)!=4 or any(type(v) is not int for v in rect) or min(rect[:2])<0 or min(rect[2:])<=0:raise ProvenanceError('Malformed camera crop')
            x,y,w,h=rect
            if ('width' in c and (c['width'],c['height'])!=(w,h)) or ('width' in s and (x+w>s['width'] or y+h>s['height'])):raise ProvenanceError('Crop dimensions/bounds mismatch')
        elif 'width' in s and ((c.get('width'),c.get('height'))!=(s['width'],s['height']) or c['sha256']!=s['sha256']):raise ProvenanceError('Uncropped camera is not the original source')
        for key in ('n_frames','timestamps_s','fps'):
            if key in s and s[key]!=c[key]:raise ProvenanceError('Camera/source native mapping mismatch')
        mapping=c.get('frame_mapping')
        if mapping is not None:
            expected=[{'camera_frame':i,'source_frame':i,'source_timestamp_s':t,'shared_timestamp_s':t-offset} for i,t in enumerate(ts)]
            if mapping!=expected:raise ProvenanceError('Source-to-camera frame mapping mismatch')
        if file(job,cid+'/provider_observations.json').is_file():
            observations=read(job,cid+'/provider_observations.json').get('observations',[])
            if not isinstance(observations,list):raise ProvenanceError('Malformed observation collection')
            for r in observations:frame(c,r)
        cm[cid]=c
    if analysis is not None:
        saved=analysis.get('multicamera') or {};saved_cameras=saved.get('cameras',[])
        if len(saved_cameras)!=len(cameras) or {c.get('camera_id') for c in saved_cameras}!=set(cm):raise ProvenanceError('Saved analysis camera set mismatch')
        for c in saved_cameras:
            authoritative=cm[c['camera_id']]
            if any(k in c and c[k]!=authoritative.get(k) for k in authoritative):raise ProvenanceError('Saved analysis camera binding mismatch')
        for s in saved.get('sources',[]):
            if s.get('source_video_id') not in sm or s!=sm[s['source_video_id']]:raise ProvenanceError('Saved analysis source binding mismatch')
        for r in analysis.get('frame_catalog',[]):
            if 'camera_id' in r:
                if r['camera_id'] not in cm:raise ProvenanceError('Unknown frame camera')
                frame(cm[r['camera_id']],r)
        for r in analysis.get('evidence_catalog',[]):
            if 'camera_id' in r and (r['camera_id'] not in cm or r.get('source_video_id')!=cm[r['camera_id']]['source_video_id']):raise ProvenanceError('Evidence camera/source mismatch')
    if file(job,'evidence_package.json').is_file():
        provenance=read(job,'evidence_package.json').get('provenance',{})
        bindings=provenance.get('camera_citations',{});frames=provenance.get('frame_sources',{})
        for r in list(bindings.values())+list(frames.values()):
            if r.get('camera_id') not in cm or r.get('source_video_id')!=cm[r['camera_id']]['source_video_id']:raise ProvenanceError('Original citation package camera/source mismatch')
        for b in bindings.values():
            package=b['camera_id']+'/evidence_package.json'
            if b.get('package')!=package:raise ProvenanceError('Original citation points to another camera package')
            original=read(job,package).get('evidence_catalog',[])
            if b.get('original_evidence_id') not in {e.get('evidence_id') for e in original}:raise ProvenanceError('Original cited evidence is unavailable')
        for r in frames.values():frame(cm[r['camera_id']],r)
        if analysis is not None:
            for r in analysis.get('evidence_catalog',[]):
                b=bindings.get(r.get('evidence_id'))
                if b and any(r.get(k)!=b[k] for k in ('camera_id','source_video_id','original_evidence_id')):raise ProvenanceError('Original evidence citation binding mismatch')
            for r in analysis.get('frame_catalog',[]):
                b=frames.get(r.get('frame_ref'))
                if frames and b is None:raise ProvenanceError('Frame is not in the original Muse input package')
                if b and any(r.get(k)!=b[k] for k in ('camera_id','source_video_id','original_frame','original_timestamp_s')):raise ProvenanceError('Original Muse frame binding mismatch')
        if analysis is not None:citation_authority(job,analysis,m)
    return m


def validate_artifact(job,manifest,camera_id,name,record=None):
    cameras={c['camera_id']:c for c in manifest['cameras']}
    if camera_id not in cameras:raise ProvenanceError('Camera is not in approved investigation')
    c=cameras[camera_id]
    if name.endswith('.json'):
        r=record if record is not None else read(job,camera_id+'/'+name)
        for k in ('camera_id','source_video_id'):
            if k in r and r[k]!=c[k]:raise ProvenanceError('Artifact camera/source mismatch')
        if name=='analysis.json' and (r.get('criteria') or {}).get('temporal_evidence'):
            raise ProvenanceError('Unbound camera-local temporal cache; use the validated parent investigation')
        if name=='analysis.json':
            package=camera_id+'/evidence_package.json'
            single_authority(r,read(job,package),package,digest(file(job,package)))
    if name=='provider_observations.json':
        for r in read(job,camera_id+'/'+name).get('observations',[]):frame(c,r)
    elif name=='tracks.json':
        r=record if record is not None else read(job,camera_id+'/'+name)
        for k in ('camera_id','source_video_id'):
            if k in r and r[k]!=c[k]:raise ProvenanceError('Track camera/source mismatch')
        if 'camera_provenance' in r and r['camera_provenance']!=c:raise ProvenanceError('Track extraction record mismatch')
