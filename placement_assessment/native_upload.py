"""Upload adapter for the existing native worker and sealed investigation store.

No object templates, old predictions or reference outcomes enter a new plan.
New task proposals have no geometric verifier and remain UNVERIFIED.
"""
import os
import time
import uuid
from pathlib import Path
import av
from . import service,meta_video as M
from .support import need,read,write,sha,index

MAX_BYTES=100*1024*1024
MAX_SECONDS=90


def create_parent(root,stream,filename,task,desired):
    need(filename and filename.lower().endswith('.mp4'),'Single-camera MP4 required')
    need(3<=len(task.strip())<=2000 and 3<=len(desired.strip())<=2000,'Task and intended end state required')
    root.mkdir(parents=True,exist_ok=True)
    job=root/('placement-'+uuid.uuid4().hex[:16]);job.mkdir()
    try:
        total=0
        with (job/'video.mp4').open('xb') as target:
            while chunk:=stream.read(1024*1024):
                total+=len(chunk);need(total<=MAX_BYTES,'Maximum upload size is 100 MiB');target.write(chunk)
        with av.open(str(job/'video.mp4')) as c:
            need(len(c.streams.video)==1 and not c.streams.audio,'One silent video stream required; audio is not silently removed')
            s=c.streams.video[0]
            need(s.duration is not None and 0<float(s.duration*s.time_base)<=MAX_SECONDS,'Maximum full-video duration is 90 seconds; no truncation')
            need(s.codec_context.width*s.codec_context.height<=1920*1080,'Maximum source size is 1920x1080 pixels')
        source=index(job/'video.mp4',sha(job/'video.mp4'))
        need(source['frames'][0]['timestamp_s']==0 and source['frames'][-1]['timestamp_s']<=MAX_SECONDS,'Video must start at native timestamp zero and fit the full window')
        write(job/'source_index.json',source)
        result=dict(schema='demodoctor.placement-result/v1',job_id=job.name,native_upload=True,
            source_key='user_upload',source_label='New user upload',source_sha256=source['source_sha256'],
            scope='Experimental native-video proposals for this upload. No assisted object prior or geometry is supplied.',
            failure_detected=False,failure_type=None,onset_frame=None,onset_time_seconds=None,time_interval=None,
            observed_evidence=[],possible_causes=[],source_citations=[],physical_events=[],rejected_frames=[],
            uncertainty='Task outcome Uncertain. Model proposals do not confirm grasp, release, physical cause or completion.',
            muse_status='provider_skipped',muse_note='Prepared only; no provider request.',verification_status='Unverified')
        write(job/'placement-result.json',result)
        write(job/'placement-measurements.json',dict(events=[],decisions=[],registrations={},masks={},rejected_frames=[]))
        (job/'placement-frames').mkdir()
        write(job/'evidence_package.json',dict(evidence_catalog=[],provenance=dict(source_sha256=source['source_sha256'],camera_id='cam1',crop=None)))
        analysis=dict(episode_key=job.name,title='Native video prepared — providers skipped',task=task,split='user_upload',
            available_episodes=[],has_joint_animation=False,pipeline_verdict='uncertain',task_outcome='uncertain',outcome_label='Unverified',
            diagnosis_headline='Prepared only',diagnosis_summary='No model execution or measured task finding yet.',earliest_failure=None,
            physical_events=[],highlight_interval=None,timeline_markers=[],evidence_catalog=[],frame_catalog=[],observed=[],inferred=[],
            hypotheses=[],unknowns=[result['uncertainty']],muse_explanation=None,factual_claims=[],visual_interpretations=[],
            limitations=[result['scope']],muse_only=None,evidence_muse_outcome=None,comparison_note=None,highlight_muse_comparison=False,
            sam_overlay=dict(available=False),video=dict(rel='video.mp4',primary_evidence=True,duration_s=source['frames'][-1]['timestamp_s']+1/source['fps']),
            disclaimer=result['scope'],placement_assessment=True,native_upload=True)
        write(job/'analysis.json',analysis)
        write(job/'tracks.json',dict(episode_key=job.name,source='no_segmentation',provenance='unverified',note='No SAM request in native-video analysis.',
            image_size=[source['width'],source['height']],fps=source['fps'],t_start=None,t_end=None,frame_start=None,frame_end=None,legend=[],tracks={},frames={}))
        write(job/'request.json',dict(job_id=job.name,filename=Path(filename).name,task_description=task,desired_end_state=desired,
            run_muse=False,cache_only=True,native_upload=True))
        write(job/'status.json',dict(job_id=job.name,status='completed',stage='prepared_provider_skipped',created_at=time.time(),updated_at=time.time(),errors=[]))
        service.seal(job);service.verify(job)
        return job
    except Exception:
        write(job/'status.json',dict(job_id=job.name,status='error',stage='source_preparation',errors=['Input preparation failed; no provider call.']))
        raise


def configuration(app):
    mock=getattr(app.state,'native_mock',None)
    enabled=os.environ.get('DEMODOCTOR_NATIVE_VIDEO_ENABLED')=='1'
    reviewed=os.environ.get('DEMODOCTOR_NATIVE_VIDEO_REVIEWED_SHA256')==M.implementation()
    ledger=Path(mock['ledger']) if mock else M.live_budget.LEDGER_PATH
    problems=[];balance=None
    if not mock:
        import live_api
        if live_api.OFFLINE_ONLY:problems.append('Offline launcher forbids provider execution.')
        if not enabled:problems.append('Native paid execution is disabled at server startup.')
        if not reviewed:problems.append('Operator must pin the independently reviewed implementation hash at startup.')
        if not os.environ.get('MODEL_API_KEY','').strip():problems.append('Backend MODEL_API_KEY is missing.')
    if ledger.is_file():
        d=read(ledger);balance=dict(spent_usd=d['spent_usd'],reserved_usd=d['reserved_usd'],per_run_budget_usd=d['per_run_budget_usd'],total_budget_usd=d['total_budget_usd'])
        if d['reservations'] or d['reserved_usd'] or any(e.get('actual_usd') is None and not e.get('from_cache') for e in d['events']):problems.append('Outstanding or uncertain ledger operations require reconciliation.')
        if M.V.RESERVATION>d['per_run_budget_usd'] or d['spent_usd']+M.V.RESERVATION>min(d['total_budget_usd'],4.5):problems.append('Existing budget limits cannot admit $1.33. No limits were changed.')
        if (ledger.parent/'.native-video-active.lock').exists():problems.append('Native execution lock exists; inspect prior request before continuing.')
    else:problems.append('An existing spending ledger is required; no ledger or limits are created automatically.')
    return dict(mode='offline_mock' if mock else 'fresh_genuine',execution_enabled=not problems,blockers=problems,
        model=M.V.MODEL,reservation_usd=M.V.RESERVATION,ledger=balance,max_bytes=MAX_BYTES,max_seconds=MAX_SECONDS,
        implementation_sha256=M.implementation())


def browser_owner(app,directory,body):
    config=configuration(app);need(config['execution_enabled'],' '.join(config['blockers']))
    for flag in ('eligible_meta_muse_credits','exclusive_account_usage','prior_requests_reconciled','dataset_processing_permitted','estimate_not_provider_hard_cap_accepted'):
        need(body.attestations.get(flag) is True,'Confirm current condition: '+flag)
    mock=getattr(app.state,'native_mock',None)
    ledger=Path(mock['ledger']) if mock else M.live_budget.LEDGER_PATH
    owner=dict(body.attestations,paid_authorized=True,agent1_accepted=True,
        implementation_sha256=M.implementation(),plan_sha256s=[sha(directory/'plan.json')],max_per_plan_usd=M.V.RESERVATION,
        max_total_usd=M.V.RESERVATION,expires_at=time.time()+900,ledger_path=str(ledger.resolve()))
    need(not (directory/'attempt.json').exists(),'This plan already has an attempt; no retry')
    return owner,ledger,mock


def register(app,root):
    from fastapi import File,Form,UploadFile,HTTPException
    @app.get('/api/native-video/config')
    def config():return configuration(app)
    @app.post('/api/native-video/prepare')
    def prepare(video:UploadFile=File(...),task_description:str=Form(...),desired_end_state:str=Form(...)):
        try:
            with service.LOCK:
                parent=create_parent(root,video.file,video.filename,task_description,desired_end_state)
                directory,plan=M.prepare(parent,task_description,desired_end_state,root=M.PLANS)
            return dict(plan,plan_sha256=sha(directory/'plan.json'),configuration=configuration(app),prepared_job_id=parent.name)
        except Exception as e:raise HTTPException(409,'Preparation blocked; no inference: '+str(e))
