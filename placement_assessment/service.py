"""Opt-in, offline adapter to the existing investigation store.

Only a startup-pinned local registry authorizes assisted source/template inputs.
Browser requests cannot supply paths, masks, timestamps, labels or observations.
Derived jobs use the existing APIs, citation authority and React investigation.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
import uuid
import cv2
import numpy as np
from .support import read, write, sha, need, index
from .detector import DestinationTemplate, native_images, assess

LOCK=threading.Lock()
SCOPE='Assisted green-plate/rack final-state assessment; not autonomous arbitrary-object discovery.'
LIMIT='Earlier failure onset: Unknown. Physical cause, grasp, release and 3D containment: Unverified. No failure finding does not establish success.'


def registry():
    path=os.environ.get('DEMODOCTOR_PLACEMENT_REGISTRY')
    digest=os.environ.get('DEMODOCTOR_PLACEMENT_REGISTRY_SHA256')
    if not path:
        from .portable import load_registry
        return load_registry()
    need(digest and sha(path)==digest, 'Assisted registry changed or lacks startup authorization')
    value=read(path)
    need(value.get('schema')=='demodoctor.assisted-placement-inputs/v1', 'Unsupported registry')
    need(value.get('task_criterion')=='all_required_green_plates_in_rack', 'Unsupported task criterion')
    return value


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def secret(root, create=False):
    p=root/'.placement-key'
    if create and not p.exists():
        with p.open('xb') as stream:stream.write(secrets.token_bytes(32))
    value=p.read_bytes();need(len(value)==32,'Invalid local assessment key')
    return value


def seal(job):
    files={p.relative_to(job).as_posix():sha(p) for p in job.rglob('*') if p.is_file()}
    payload=dict(job_id=job.name,files=files)
    write(job/'placement-seal.json',dict(payload=payload,signature=hmac.new(secret(job.parent,True),canonical(payload),hashlib.sha256).hexdigest()))


def verify(job):
    need(job.name.startswith('placement-'),'Not a placement investigation')
    envelope=read(job/'placement-seal.json');p=envelope['payload']
    need(p['job_id']==job.name and hmac.compare_digest(envelope['signature'],hmac.new(secret(job.parent),canonical(p),hashlib.sha256).hexdigest()),'Unauthorized assessment seal')
    actual={p.relative_to(job).as_posix() for p in job.rglob('*') if p.is_file() and p.name!='placement-seal.json'}
    need(actual==set(p['files']), 'Unregistered or missing assessment artifact')
    for name,digest in p['files'].items():
        path=(job/name).resolve();need(path.is_relative_to(job.resolve()) and sha(path)==digest,'Altered assessment artifact')
    result=read(job/'placement-result.json');source=read(job/'source_index.json')
    need(sha(job/'video.mp4')==source['source_sha256']==result['source_sha256'],'Assessment source mismatch')
    for ref in result['source_citations']:
        native=source['frames'][ref['frame']]
        need(all(ref[k]==native[k] for k in native) and ref['source_sha256']==source['source_sha256'] and
             ref['camera_id']==source['camera_id'] and ref['crop']==source['crop'],'Assessment citation mismatch')
    return result


def options():
    r=registry()
    if r is None:
        from .portable import SETUP
        return dict(available=False,sources=[],reason='Original sources and approved rack template are not registered. '+SETUP+' New footage remains Unverified.')
    return dict(available=True,scope=SCOPE,sources=[dict(key=k,label=v['label']) for k,v in r['sources'].items()])


def create(root, key):
    with LOCK:
        r=registry();need(r is not None and key in r['sources'],'No approved assisted inputs for this recording')
        spec=r['sources'][key];video=Path(spec['video'])
        source=index(video,spec['sha256'])
        t=r['template'];ref=index(Path(t['reference_video']),t['reference_source_sha256'])
        template=DestinationTemplate(t,ref,Path(t['reference_video']))
        end=source['frames'][-1]['timestamp_s']
        selected=[f['frame'] for f in source['frames'] if f['timestamp_s']>=end-.5-1e-9]
        images=native_images(video,source,selected)
        events,decisions,registrations,tracks,rejected=assess(source,images,template)
        if spec.get('task_criterion')!='all_required_green_plates_in_rack':
            events=[]
            rejected.append(dict(frame=selected[0],reason='unsupported_task_criterion'))
        # Recheck the startup authorization and input bytes before publishing.
        need(registry()==r and sha(video)==spec['sha256'],'Inputs changed during assessment')
        root.mkdir(parents=True,exist_ok=True)
        job=root/('placement-'+uuid.uuid4().hex[:16]);job.mkdir()
        try:
            shutil.copyfile(video,job/'video.mp4')
            write(job/'source_index.json',source)
            write(job/'template_receipt.json',template.receipt)
            citations=[dict(source['frames'][f],source_sha256=source['source_sha256'],source_video_id=source['source_video_id'],camera_id=source['camera_id'],crop=None) for f in selected]
            interval=dict(start_frame=selected[0],end_frame_exclusive=selected[-1]+1,start_seconds=source['frames'][selected[0]]['timestamp_s'],last_frame_seconds=end,role='final_state_evidence_NOT_original_failure_onset')
            result=dict(schema='demodoctor.placement-result/v1',job_id=job.name,source_key=key,source_sha256=source['source_sha256'],
                source_label=spec['label'],scope=SCOPE,failure_detected=bool(events),failure_type='required_plate_visibly_outside_target_at_recording_end' if events else None,
                onset_frame=None,onset_time_seconds=None,time_interval=interval if events else None,assessed_interval=interval,
                observed_evidence=[dict(evidence_id=e['event_id'],minimum_lateral_separation_px=e['minimum_target_gap_px'],stable_features=e['surviving_features'],
                    median_translation_diameter_px=e['median_feature_displacement_px'],text='Persistent plate-like green region remains wholly beside the registered rack enclosure.') for e in events],
                possible_causes=[],uncertainty=LIMIT,source_citations=citations,absolute_error_bound_px=None,
                physical_events=[],muse_status='provider_skipped',muse_note='No Muse request. These newly computed observations were not supplied to historical Muse responses.',
                paid_calls=0,ground_truth_consumed=False,rejected_frames=rejected,
                verification_status='Supported visual criterion / inferred plate class' if events else 'Unverified')
            write(job/'placement-result.json',result)
            write(job/'placement-measurements.json',dict(events=events,decisions=decisions,rejected_frames=rejected,
                registrations={str(f):{k:v for k,v in a.items() if k!='mask'} if a else None for f,a in registrations.items()},masks=tracks))
            implementation={p.name:sha(p) for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.json')}
            write(job/'placement-implementation.json',dict(files=implementation,registry_sha256=r.get('portable_manifest_sha256') or os.environ['DEMODOCTOR_PLACEMENT_REGISTRY_SHA256']))
            (job/'placement-frames').mkdir()
            for f,rgb in images.items():
                overlay=rgb.copy()
                # Source-pixel candidates are yellow; registered rack is cyan.
                for a in tracks[str(f)]:
                    import tracking
                    mask=tracking.mask_in_frame(a['mask'],tuple(a['bbox']),rgb.shape[:2])
                    color=np.array([0,220,255] if a['object_id']=='target' else [255,210,0])
                    overlay[mask]=(overlay[mask]*.55+color*.45).astype(np.uint8)
                for suffix,img in [('source',rgb),('overlay',overlay)]:
                    need(cv2.imwrite(str(job/'placement-frames'/f'{f}-{suffix}.png'),cv2.cvtColor(img,cv2.COLOR_RGB2BGR)),'Frame export failed')
            catalog=[]
            for e in events:
                catalog.append(dict(evidence_id=e['event_id'],source='offline:assisted_final_placement',kind='measurement',status_context='inferred',
                    frame_start=selected[0],frame_end=selected[-1]+1,t_start=interval['start_seconds'],t_end=end,
                    summary=f"Plate-like green region remains outside the registered rack by at least {e['minimum_target_gap_px']} pixels at the recording end. Earlier onset unknown.",
                    claims=[],track_id=e['segment_id'],event_index=None))
            write(job/'evidence_package.json',dict(evidence_catalog=catalog,provenance=dict(source_sha256=source['source_sha256'],camera_id=source['camera_id'],crop=None)))
            title='Final placement condition contradicted' if events else 'Final placement Unverified'
            analysis=dict(episode_key=job.name,title=title,task=spec['task_description'],split='development',available_episodes=[],has_joint_animation=False,
                pipeline_verdict='failure' if events else 'uncertain',task_outcome='uncertain',outcome_label='Visible placement failure; physical mechanism Unverified' if events else 'Unverified',
                diagnosis_headline=title,diagnosis_summary=(catalog[0]['summary'] if catalog else 'No supported outside-rack finding. This does not establish successful placement.'),
                earliest_failure=None,physical_events=[],highlight_interval=None,timeline_markers=[dict(id=e['evidence_id'],label='Final placement evidence (not onset)',t=e['t_start'],kind='observed_measurement',evidence_ids=[e['evidence_id']]) for e in catalog],
                evidence_catalog=catalog,frame_catalog=[],observed=[],inferred=[dict(text=e['summary'],evidence_ids=[e['evidence_id']],status='inferred',t=e['t_start']) for e in catalog],
                hypotheses=[],unknowns=[SCOPE,LIMIT],muse_explanation=None,factual_claims=[],visual_interpretations=[],limitations=[LIMIT],muse_only=None,evidence_muse_outcome=None,
                comparison_note=None,highlight_muse_comparison=False,sam_overlay=dict(available=False),video=dict(rel='video.mp4',primary_evidence=True,duration_s=end+1/source['fps']),
                disclaimer=SCOPE,placement_assessment=True)
            write(job/'analysis.json',analysis)
            write(job/'tracks.json',dict(episode_key=job.name,source='offline_assisted',provenance='observed',note='No SAM object tracking; source-frame candidate overlays in Findings.',image_size=[source['width'],source['height']],fps=source['fps'],t_start=None,t_end=None,frame_start=None,frame_end=None,legend=[],tracks={},frames={}))
            write(job/'request.json',dict(job_id=job.name,filename=video.name,task_description=analysis['task'],run_muse=False,cache_only=True,placement_assessment=True))
            write(job/'status.json',dict(job_id=job.name,status='completed',stage='completed',created_at=time.time(),updated_at=time.time(),errors=[]))
            seal(job);verify(job)
            return result
        except Exception:
            # Preserve an incomplete attempt, but never expose it as completed.
            write(job/'status.json',dict(job_id=job.name,status='error',stage='placement',errors=['Offline assessment failed; no inference was started.']))
            raise


def register(app, root):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    def checked(job_id):
        if not re.fullmatch(r'placement-[0-9a-f]{16}',job_id):raise HTTPException(400,'Invalid placement ID')
        job=root/job_id
        try:return job,verify(job)
        except (OSError,ValueError,KeyError,TypeError):raise HTTPException(409,'Placement evidence quarantined: missing, altered or unauthorized artifacts. No inference was started.')

    @app.get('/api/placement/options')
    def get_options():
        try:return options()
        except (OSError,ValueError,KeyError):
            from .portable import SETUP
            raise HTTPException(409,'Assisted assets unavailable or integrity invalid. Restore the approved packaged template and originals. '+SETUP)

    @app.post('/api/placement/assess/{key}')
    def start(key: str):
        try:return create(root,key)
        except (OSError,ValueError,KeyError,TypeError) as e:raise HTTPException(409,'Placement assessment blocked: '+str(e))

    @app.get('/api/placement/jobs/{job_id}')
    def get_result(job_id: str):return checked(job_id)[1]

    @app.get('/api/placement/jobs/{job_id}/frames/{frame}/{kind}')
    def get_frame(job_id: str,frame:int,kind:str):
        job,result=checked(job_id)
        if kind not in ('source','overlay') or frame not in [r['frame'] for r in result['source_citations']]:raise HTTPException(404,'No registered source frame')
        return FileResponse(job/'placement-frames'/f'{frame}-{kind}.png',media_type='image/png',headers={'Cache-Control':'no-store'})
