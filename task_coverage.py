"""Read-only presentation adapter for previously completed camera jobs. No providers."""
from pathlib import Path
import hashlib
import json

import task_actions as A
import criteria_presentation as P


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(job):
    return {str(p.relative_to(job)): digest(p) for p in job.rglob('*') if p.is_file()}


def build_assessment(job):
    job=Path(job).resolve()
    def file(name):
        p=(job/name).resolve()
        if not p.is_relative_to(job):raise ValueError('Artifact outside original job')
        return p
    from saved_provenance import validate, validate_artifact
    analysis=read(file('analysis.json'));manifest=validate(job,analysis);coverage=[];context=[];temporal=[]
    for c in manifest['cameras']:
        validate_artifact(job,manifest,c['camera_id'],'provider_observations.json')
        obs=read(file(c['camera_id']+'/provider_observations.json'))['observations']
        coverage.append(A.camera_coverage(c,obs))
        from temporal_evidence import select
        selected=select(c,obs,max(4,12//len(manifest['cameras'])))
        selected['provider_observations_sha256']=digest(file(c['camera_id']+'/provider_observations.json'))
        temporal.append(selected)
        for frame in A.select_context_frames(c,obs,6//len(manifest['cameras'])):
            source_time=c['timestamps_s'][frame]
            context.append({'frame_ref':f'C{len(context)}','camera_id':c['camera_id'],'source_video_id':c['source_video_id'],
                'original_frame':frame,'original_timestamp_s':source_time,'shared_timestamp_s':source_time-c['playback_offset_s'],
                'scope':'Locally selected original-frame context, not a historical Muse citation or verified action measurement'})
    a={**analysis,'analysis_coverage':coverage,'criterion_frame_context':context}
    c=manifest['cameras'][0]
    criteria=P.for_analysis(a,n_frames=c['n_frames'],fps=c['fps'],object_concept=c['object_concept'],
        destination=c['destination_concept'],dry_run=a.get('dry_run',False))
    criteria['reassessment']={'original_job':job.name,'original_outcome':analysis['task_outcome'],
        'original_muse_sha256':digest(file('muse_result.json')),'original_package_sha256':digest(file('evidence_package.json')),
        'method':'Read-only task presentation from original structured evidence; no new inference or image-derived predicates',
        'approved_provenance_verified':True}
    criteria['temporal_evidence']=temporal
    return criteria,a
