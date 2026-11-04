"""Read-only local investigation history. No inference clients or credentials."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re


def file(directory: Path, name: str) -> Path:
    root=directory.resolve();path=(root/name).resolve()
    if not path.is_relative_to(root):raise ValueError('Saved artifact path escapes its investigation')
    return path


def read(directory: Path, name: str):
    try:
        value=json.loads(file(directory,name).read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else None
    except (OSError, ValueError):return None


def required_artifacts(directory: Path, analysis: dict) -> list[str]:
    required=['status.json','analysis.json']
    # Older provider-skipped jobs intentionally contain no SAM tracks.
    if analysis.get('dry_run') is not True or file(directory,'tracks.json').exists():
        required.append('tracks.json')
    manifest=analysis.get('multicamera')
    if manifest:
        manifest=read(directory,'multicamera.json') or manifest
        cameras=manifest.get('cameras',[]);sources=manifest.get('sources',[])
        if not 1<=len(cameras)<=3:raise ValueError('Invalid saved camera manifest')
        required.append('multicamera.json')
        for c in cameras:
            cid=c.get('camera_id')
            if cid not in {'cam1','cam2','cam3'}:raise ValueError('Invalid saved camera identifier')
            required.extend([f'{cid}/video.mp4',f'{cid}/tracks.json'])
            if analysis.get('dry_run') is False:
                required.extend(f'{cid}/{n}.json' for n in ('provider_observations','provenance','evidence_package','verification','failure_report'))
        for s in sources:
            sid=s.get('source_video_id')
            if sid not in {'source1','source2','source3'}:raise ValueError('Invalid saved source identifier')
            required.append(sid+'.mp4')
        if analysis.get('dry_run') is False:required.extend(['muse_result.json','evidence_package.json'])
    else:
        required.append('video.mp4')
        request=read(directory,'request.json') or {}
        if request.get('run_muse') and analysis.get('dry_run') is False:required.append('muse_result.json')
    return list(dict.fromkeys(required))


def availability_error(directory: Path) -> str | None:
    status=read(directory,'status.json')
    if not status:return 'Saved job status is missing or unreadable. No analysis was started.'
    if status.get('status')!='completed':
        return f"Saved job is {status.get('status','unknown')}; completed results are unavailable. No analysis was started."
    analysis=read(directory,'analysis.json')
    if not analysis:return 'Saved analysis.json is missing or unreadable. No analysis was started.'
    if (not isinstance(analysis.get('video'),dict) or
        any(not isinstance(analysis.get(k),list) for k in ('evidence_catalog','observed','inferred','unknowns','physical_events','timeline_markers'))):
        return 'Saved analysis schema is incomplete or unsupported. Original files are preserved; no analysis was started.'
    try:
        required=required_artifacts(directory,analysis)
        missing=[name for name in required if not file(directory,name).is_file() or file(directory,name).stat().st_size==0]
    except (ValueError, TypeError, KeyError, AttributeError):return 'Saved camera/source provenance is invalid. No analysis was started.'
    if missing:return 'Missing or empty saved artifacts: '+', '.join(missing)+'. No analysis was started.'
    for name in required:
        if name.endswith('.json') and read(directory,name) is None:return f'Saved {name} is unreadable. No analysis was started.'
    tracks=read(directory,'tracks.json')
    if tracks is not None and (not isinstance(tracks.get('frames'),dict) or not isinstance(tracks.get('tracks'),dict)):return 'Saved tracks.json has an unsupported schema. No analysis was started.'
    for c in (analysis.get('multicamera') or {}).get('cameras',[]):
        if read(directory,c['camera_id']+'/tracks.json') is None:return 'Saved camera tracks are unreadable. No analysis was started.'
    if analysis.get('multicamera'):
        try:
            from saved_provenance import validate, CitationBindingError
            validate(directory,analysis)
        except CitationBindingError:return 'Saved citation-to-evidence binding is invalid. Original artifacts are unchanged; no analysis was started.'
        except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError):return 'Saved source/camera/crop/frame provenance is invalid or unavailable. No analysis was started.'
    return None


def _basename(name):
    return str(name).replace('\\','/').rsplit('/',1)[-1] if name else None


def execution_summary(directory: Path) -> dict:
    """Read local execution records, never infer provider use from a verdict.

    This is a local-record description, not remote provider authentication.
    Missing legacy metadata remains unconfirmed; saved files are never rewritten.
    """
    analysis=read(directory,'analysis.json') or {}
    status=read(directory,'status.json') or {}
    request=read(directory,'request.json') or {}
    if analysis.get('dry_run') is True or status.get('dry_run') is True:
        return {'mode':'dry_run','note':'SAM and Muse were skipped. No physical findings were generated.'}
    if request.get('cache_only') is True:
        return {'mode':'recorded_replay','note':'Saved analysis replay. No new provider calls are made when opening it.'}
    muse=read(directory,'muse_result.json') or {}
    if muse.get('paid_call') is False:
        return {'mode':'experimental','note':'The saved Muse record reports no paid call. Treat this as experimental or provider-skipped, not confirmed real inference.'}
    cameras=(analysis.get('multicamera') or {}).get('cameras')
    folders=[file(directory,c['camera_id']) for c in cameras] if cameras and all(isinstance(c,dict) and c.get('camera_id') in {'cam1','cam2','cam3'} for c in cameras) else [directory]
    sam_records=[]
    for folder in folders:
        observations=read(folder,'provider_observations.json') or {}
        calls=observations.get('provider_calls') or []
        usage=observations.get('usage_events') or []
        sam_records.append(isinstance(calls,list) and bool(calls) and
            all(isinstance(c,dict) and c.get('status')=='completed' and c.get('from_cache') is False for c in calls) and
            isinstance(usage,list) and any(isinstance(u,dict) and u.get('provider')=='meta_sam' and u.get('kind')=='video_window' and u.get('status')=='completed' for u in usage))
    if (analysis.get('dry_run') is False and status.get('status')=='completed' and
        muse.get('paid_call') is True and muse.get('dry_run') is False and
        muse.get('model')=='accounts/fireworks/models/muse-spark-open' and all(sam_records)):
        return {'mode':'real','note':'Local records report completed SAM and Muse provider execution. You are replaying saved outputs; reopening makes no provider calls. Physical actions are not thereby verified.'}
    return {'mode':'unconfirmed','note':'Saved analysis replay; provider execution metadata is incomplete or unconfirmed. Do not treat it as confirmed real inference.'}


def describe(directory: Path) -> dict:
    if directory.name.startswith('placement-'):
        from placement_assessment.service import verify
        verify(directory)  # Do not expose forged outcomes even in the history list.
    status=read(directory,'status.json') or {}
    analysis=read(directory,'analysis.json') or {}
    manifest=read(directory,'multicamera.json') or analysis.get('multicamera') or {}
    request=read(directory,'request.json') or {}
    dry=analysis.get('dry_run',status.get('dry_run',request.get('dry_run')))
    kind='recorded_replay' if request.get('cache_only') else 'dry_run' if dry is True else 'real' if dry is False else 'unknown'
    names=[_basename(s.get('filename')) for s in manifest.get('sources',[]) if isinstance(s,dict)]
    name=', '.join(dict.fromkeys(n for n in names if n)) or _basename(request.get('filename'))
    if not name:
        prepared=read(directory,'prepared.json') or {}
        name=_basename((prepared.get('quote') or {}).get('filename'))
    created=None;date_basis=None
    stamp=status.get('created_at')
    try:
        if isinstance(stamp,(int,float)) and not isinstance(stamp,bool) and math.isfinite(stamp):
            created=datetime.fromtimestamp(stamp,timezone.utc).isoformat();date_basis='Saved creation time'
        elif re.match(r'^\d{8}T\d{6}Z_',directory.name):
            created=datetime.strptime(directory.name[:16],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat();date_basis='Job identifier (UTC)'
    except (ValueError,OverflowError,OSError):pass
    outcome=analysis.get('task_outcome') if status.get('status')=='completed' and kind!='dry_run' else None
    if outcome not in {'success','failure','uncertain'}:outcome=None
    problem=availability_error(directory)
    return {'job_id':directory.name,'task_description':manifest.get('task_description') or request.get('task_description') or analysis.get('task') or 'Task not recorded',
        'video_filename':name or 'Original filename not recorded','created_at':created,'date_basis':date_basis,
        'camera_count':len(manifest['cameras']) if isinstance(manifest.get('cameras'),list) else 1,
        'analysis_type':kind,'execution':execution_summary(directory),'status':status.get('status','unknown'),'outcome':outcome,
        'outcome_note':'Provider-skipped preparation; no physical conclusions' if kind=='dry_run' else 'Saved verdict; inspect its evidence scope and limitations',
        'can_open':problem is None,'availability_error':problem}
