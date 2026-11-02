"""Read-only task reassessment of a saved camera job. No inference/provider imports.

Writes a separate report, never the original job or saved Muse/SAM outputs.
Usage: python scripts/reassess-task-coverage.py JOB_DIRECTORY --output OUTPUT_DIRECTORY
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from task_coverage import build_assessment, read, digest, hashes


def build_report(job):
    criteria, analysis = build_assessment(job)
    coverage, context = criteria['coverage'], criteria['context_frames']
    lines=['# Saved-job task-coverage reassessment', '', f'Job: `{job.name}`. Original outcome: **{analysis["task_outcome"]}**, unchanged.',
        '', f'Task: {analysis["task"]}', '', 'This is a separate presentation, not a rerun or replacement of the saved scientific result.',
        'Original frame context is not independent verification. No paid inference or new closure measurement was performed.', '',
        '| Explicit subgoal | State | Verified frame support | Original contextual citations |', '|---|---|---|---|']
    for a in criteria['assessments']:
        if a['kind'] != 'action': continue
        lines.append(f'| {a["name"]} | {a["state"]} | None supplied | {", ".join(a["evidence_ids"]) or "None: no action measurement"} |')
    lines += ['', '**Physical completion:** '+criteria['completion']+'.', '', '## Processing and missing observations', '']
    for c in coverage:
        lines += [f'- {c["camera_id"]}: approved native frames [{c["frame_start"]},{c["frame_end"]}), crop {c["crop"]}, {c["returned_observations"]} returned observations.',
            f'  Returned spans (end exclusive): {c["observed_ranges"]}; missing: {c["missing_ranges"]}; outside analysis: {c["outside_analysis"]}.',
            f'  Camera SHA256: `{c["sha256"]}`; original source SHA256: `{c["source_sha256"]}`.']
    lines += ['', '## Original-frame candidates for inspection', '',
        'These are candidate context for unresolved subgoals, not frames that independently prove pickup, placement or closure.',
        'C references are local reassessment references. Original Muse F/E references remain unchanged.', '']
    for f in context:
        lines.append(f'- {f["frame_ref"]}: {f["camera_id"]}/{f["source_video_id"]}, native frame {f["original_frame"]}, source {f["original_timestamp_s"]:.6f}s, shared {f["shared_timestamp_s"]:.6f}s.')
    lines += ['', '## Resolving observations', '']
    for a in criteria['assessments']:
        if a['kind']=='action':
            lines += [f'**{a["name"]}:** {a["basis"]}', *['- '+r['reason'] for r in a['requirements']], '']
    return criteria, '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();job=args.job.resolve();out=args.output.resolve()
    if out==job or job in out.parents:
        parser.error('Output must be separate from the original job directory')
    before=hashes(job);criteria,text=build_report(job)
    if before!=hashes(job):raise RuntimeError('Original job changed during read-only reassessment')
    out.mkdir(parents=True,exist_ok=True)
    (out/'criteria.json').write_text(json.dumps(criteria,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'REPORT.md').write_text(text,encoding='utf-8')
    (out/'original-job-hashes.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    print(json.dumps({'job':job.name,'original_job_unchanged':True,'files_hashed':len(before),'action_states':[
        {'subgoal':a['name'],'state':a['state']} for a in criteria['assessments'] if a['kind']=='action'],'output':str(out)}))


if __name__=='__main__':main()
