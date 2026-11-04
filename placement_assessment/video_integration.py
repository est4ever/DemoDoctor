"""Native-video proposals in the existing sealed investigation store and UI."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
import cv2
from . import service,meta_video as M
from .support import need,read,write,sha
from .detector import native_images


def publish(directory,root):
    directory=Path(directory);plan,source=M.check_plan(directory)
    M.execution_seal(directory)
    journal=read(directory/'operations.json');attempt=read(directory/'attempt.json')
    need(journal['state']=='completed' and journal['mode']==attempt['mode'] and
         attempt['plan_sha256']==sha(directory/'plan.json'),'No completed source-bound execution')
    raw=json.loads((directory/'response.body').read_bytes())
    need(sha(directory/'response.body')==read(directory/'response-receipt.json')['body_sha256'],'Altered model response')
    need(raw['id']==journal['response_id'] and journal['file_id']==json.loads((directory/'upload.body').read_bytes())['id'],'Operation identity mismatch')
    parent=Path(plan['parent_job']);final=service.verify(parent)
    # Recompute the verification from raw proposals and sealed source evidence.
    assessment=M.V.verify(M.V.parse_response(raw,source),source,final,read(parent/'placement-measurements.json'))
    need(assessment==read(directory/'assessment.json'),'Altered assessment')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    job=root/('placement-'+uuid.uuid4().hex[:16]);shutil.copytree(parent,job)
    (job/'placement-seal.json').unlink()  # New child only; original never modified.
    proof=job/'native-video';proof.mkdir()
    for name in ('plan.json','attempt.json','operations.json','response.body','response-receipt.json',
                 'upload.body','upload-receipt.json','actual-request.json','accounting.json','assessment.json'):
        shutil.copyfile(directory/name,proof/name)
    result=read(job/'placement-result.json');analysis=read(job/'analysis.json')
    mode=journal['mode']
    native=dict(assessment,mode=mode,model=M.V.MODEL,source_sha256=source['source_sha256'],
        upload_sha256=plan['upload_sha256'],file_id=journal['file_id'],response_id=raw['id'],
        accounting=read(directory/'accounting.json'),
        explanation_status='No post-verification Muse explanation request. Model descriptions are proposals; verified summary is deterministic.')
    result.update(job_id=job.name,native_video=native,
        muse_status='offline_mock' if mode=='offline_mock' else 'genuine_native_video_proposals_only',
        muse_note='Native-video proposals are separate from historical Muse explanations. No historical provider response was changed or rerun.')
    refs={r['frame']:r for r in result['source_citations']}
    added={}
    for e in native['proposals']:
        for r in e['source_citations']:
            if r['frame'] not in refs:added[r['frame']]=r
            refs[r['frame']]=r
    native['proposal_only_frames']=sorted(added)
    images=native_images(job/'video.mp4',source,sorted(added)) if added else {}
    for frame,rgb in images.items():
        # A proposal frame is a citation, not a mask or measured observation.
        for kind in ('source','overlay'):
            need(cv2.imwrite(str(job/'placement-frames'/f'{frame}-{kind}.png'),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)),'Frame export failed')
    result['source_citations']=[refs[f] for f in sorted(refs)]
    analysis.update(episode_key=job.name,native_video=native,
        muse_explanation=None,muse_only=None,evidence_muse_outcome=None)
    for e in native['proposals']:
        analysis['timeline_markers'].append(dict(id='native-'+e['proposal_id'],label='MODEL PROPOSAL: '+e['event_type'],
            t=e['proposed_start_time'],kind='unverified',evidence_ids=[]))
    write(job/'placement-result.json',result);write(job/'analysis.json',analysis)
    for filename,key in [('status.json','job_id'),('request.json','job_id'),('tracks.json','episode_key')]:
        value=read(job/filename);value[key]=job.name;write(job/filename,value)
    service.seal(job);service.verify(job)
    return result


def register(app,root):
    from fastapi import HTTPException
    from pydantic import BaseModel,Field
    class PlanInput(BaseModel):
        task_description:str=Field(min_length=3,max_length=2000)
        desired_end_state:str=Field(min_length=3,max_length=2000)
    class ExecuteInput(BaseModel):
        plan_sha256:str
        approve_reservation_usd:float
    def path(plan_id):
        need(re.fullmatch(r'native-[a-f0-9]{16}',plan_id),'Invalid plan ID')
        return M.PLANS/plan_id
    @app.post('/api/placement/jobs/{job_id}/native-video/plan')
    def prepare(job_id:str,body:PlanInput):
        try:
            need(re.fullmatch(r'placement-[a-f0-9]{16}',job_id),'Invalid job ID')
            with service.LOCK:
                directory,plan=M.prepare(root/job_id,body.task_description,body.desired_end_state)
            return dict(plan,plan_sha256=sha(directory/'plan.json'),execution_enabled=False,
                note='No provider request. Operator approval bound to this exact plan plus explicit browser approval required.')
        except (ValueError,OSError,KeyError) as e:raise HTTPException(409,str(e))
    @app.post('/api/native-video/{plan_id}/execute')
    def execute(plan_id:str,body:ExecuteInput):
        try:
            directory=path(plan_id)
            need(body.plan_sha256==sha(directory/'plan.json') and body.approve_reservation_usd==M.V.RESERVATION,'Explicit exact-plan cost approval required')
            approval=os.environ.get('DEMODOCTOR_NATIVE_VIDEO_APPROVAL')
            need(approval and Path(approval).is_file(),'Paid execution disabled: operator authorization unavailable')
            owner=read(approval);ledger=Path(owner['ledger_path'])
            async def run():
                client=M.sam_api.client()
                try:return await M.execute(directory,owner,ledger,client)
                finally:await client.close()
            with service.LOCK:
                asyncio.run(run());result=publish(directory,root)
            return result
        except Exception as e:raise HTTPException(409,'Native-video analysis stopped; no automatic retry: '+str(e))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--parent',required=True);p.add_argument('--task',required=True);p.add_argument('--desired-end-state',required=True)
    p=sub.add_parser('execute');p.add_argument('--plan',required=True);p.add_argument('--approval',required=True);p.add_argument('--ledger',required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        directory,plan=M.prepare(Path(args.parent),args.task,args.desired_end_state);print(json.dumps(dict(path=str(directory),plan_sha256=sha(directory/'plan.json'),reservation_usd=plan['reservation_usd'])))
    else:
        async def run():
            client=M.sam_api.client()
            try:return await M.execute(Path(args.plan),read(args.approval),Path(args.ledger),client)
            finally:await client.close()
        asyncio.run(run());print(json.dumps(publish(Path(args.plan),M.ROOT/'data/live_jobs')))

if __name__=='__main__':main()
