"""Task coverage and conservative, source-backed action contracts. All fixtures synthetic."""
from dataclasses import replace
import copy
import json

import pytest

import task_actions as A
import task_criteria as T
import criteria_presentation as P

TEXT = 'Pick up the blue block, put the blue block inside the drawer, then close the drawer.'


def test_explicit_clauses_without_extra_requirements():
    task = A.parse_task(TEXT, 'blue block', 'open drawer')
    assert [s.params.get('action') for s in task.criteria[:-1]] == ['pick_up', 'place', 'close']
    assert [s.kind for s in task.criteria] == ['action']*3+['completion']
    assert task.objects[0].count is None
    # An adjective naming the destination never creates an additional opening requirement.
    assert not any(s.params.get('action') == 'open' for s in task.criteria)
    assert A.parse_task('Store green plates in the dish rack','green plate','dish rack').criteria[0].params['action']=='place'


@pytest.mark.parametrize('text', ['Do not close the drawer', 'Close the drawer if empty', 'Wave to the camera', 'Pick up the block or close the drawer'])
def test_unknown_and_conditional_clauses_remain_visible_and_block_completion(text):
    task = A.parse_task(text, 'block', 'drawer')
    ev = T.InvestigationEvidence('test', task.task_id, 100, 15, frozenset())
    report = T.assess(task, ev)
    assert report.by_id('step_1').state == 'not_assessed'
    assert report.completion == 'unverified'
    assert 'step_1' in report.by_id('completion').blocking


def closure_evidence(end=.02, view='cam1'):
    measurement = {'start_frame': 0, 'closed_threshold': .1, 'open_threshold': .5,
        'start_open_fraction': .9, 'end_open_fraction': end,
        'target_id': 'drawer', 'view': view, 'reference_geometry_source': 'synthetic-geometry#/reference',
        'start_source_ref': f'synthetic-geometry#/{view}/0'}
    start = T.SourcePredicate(f'{view}-E0', 'articulation_2d', 'drawer', 0, 'open', view,
        measurement['start_source_ref'], 'pkg', {'open_fraction': .9, 'reference_geometry_source': measurement['reference_geometry_source']})
    value = 'closed' if end <= .1 else 'open' if end >= .5 else 'ambiguous'
    finish = T.SourcePredicate(f'{view}-E1', 'articulation_2d', 'drawer', 99, value, view,
        f'synthetic-geometry#/{view}/99', 'pkg', measurement)
    return T.InvestigationEvidence('test', 'uploaded_task', 100, 15, frozenset([start.evidence_id, finish.evidence_id]),
        predicates=(start, finish), package_id='pkg', analyzed_ranges=((view,0,100),), camera_motion={view:'static'})


@pytest.mark.parametrize('end,state', [(.02,'supported'),(.9,'contradicted'),(.3,'unverified')])
def test_closure_requires_numeric_comparison_and_scoped_sources(end, state):
    task = A.parse_task('Close the drawer', 'block', 'drawer')
    report = T.assess(task, closure_evidence(end))
    action = report.by_id('step_1')
    assert action.state == state and action.evidence_ids == ['cam1-E0','cam1-E1']
    assert report.completion == 'unverified'  # image-space articulation != full physical completion


@pytest.mark.parametrize('corruption', ['citation','package','target','frame','interval','moving','unknown','initial','metrics','value'])
def test_plausible_ids_and_prose_do_not_establish_closure(corruption):
    ev=closure_evidence(); first,last=ev.predicates
    if corruption=='citation': ev.evidence_ids=frozenset({'unrelated-E0'})
    if corruption=='package': ev.package_id='another-job'
    if corruption=='target': last=replace(last,object_id='another drawer')
    if corruption=='frame': last=replace(last,frame=98)
    if corruption=='interval': ev.analyzed_ranges=(('cam1',0,99),)
    if corruption in {'moving','unknown'}: ev.camera_motion={'cam1':corruption}
    if corruption=='initial': first=replace(first,source_ref='unrelated-record')
    if corruption=='metrics': last=replace(last,measurement={**last.measurement,'end_open_fraction':float('nan')})
    if corruption=='value': last=replace(last,value='open')
    ev.predicates=(first,last)
    assert T.assess(A.parse_task('Close the drawer','block','drawer'),ev).by_id('step_1').state=='unverified'


def test_views_require_association_and_disagreement_never_votes_to_success():
    ev=closure_evidence(); other=closure_evidence(.9,'cam2')
    ev.predicates+=other.predicates;ev.evidence_ids|=other.evidence_ids
    ev.analyzed_ranges+=other.analyzed_ranges;ev.camera_motion.update(other.camera_motion)
    ev.time_alignment_validated=True;ev.object_associations=frozenset({'drawer'})
    task=A.parse_task('Close the drawer','block','drawer')
    assert T.assess(task,ev).by_id('step_1').state=='unverified'
    # Matching strings and agreeing views alone also cannot establish association.
    ev.predicates=closure_evidence().predicates+closure_evidence(.02,'cam2').predicates
    ev.object_associations=frozenset()
    assert T.assess(task,ev).by_id('step_1').state=='unverified'


def test_incomplete_three_step_task_never_inherits_closure_as_success():
    report=T.assess(A.parse_task(TEXT.replace(', put',' and put'),'blue block','drawer'),closure_evidence())
    assert [report.by_id(f'step_{i}').state for i in (1,2,3)]==['unverified','unverified','supported']
    assert report.completion=='unverified'


def test_missing_intermediates_and_model_hypotheses_are_not_decisive():
    a={'episode_key':'new','task':TEXT.replace(', put',' and put'),'hypotheses':[{'text':'The drawer is closed','label':'verified'}],
       'task_outcome':'success','reference_outcome':'success','evidence_catalog':[]}
    result=P.for_analysis(a,n_frames=158,fps=15,object_concept='blue block',destination='open drawer')
    assert len([s for s in result['assessments'] if s['kind']=='action'])==3
    assert all(s['state']=='unverified' for s in result['assessments'] if s['kind']=='action')
    a.update(reference_outcome='failure',task_outcome='failure',hypotheses=[])
    assert P.for_analysis(a,n_frames=158,fps=15,object_concept='blue block',destination='open drawer')==result


def camera():
    return dict(camera_id='cam1',source_video_id='source1',crop=[0,0,1280,720],sha256='derived',source_sha256='source',fps=15,
                n_frames=158,frame_start=0,frame_end=155)


def test_window_gaps_and_context_never_extend_into_unprocessed_tail():
    c=camera();obs=[{'frame_index':f} for f in list(range(93))+list(range(124,128))]
    before=copy.deepcopy(c); coverage=A.camera_coverage(c,obs)
    assert coverage['missing_ranges']==[[93,124],[128,155]]
    assert coverage['outside_analysis']==[[155,158]] and coverage['returned_observations']==97
    chosen=A.select_context_frames(c,obs,6)
    assert chosen[:2]==[0,154] and 92 in chosen and 124 in chosen
    assert all(0<=f<155 for f in chosen) and len(chosen)==6 and c==before


def test_dry_run_explicit_actions_are_not_assessed():
    a={'episode_key':'dry','task':'Close the drawer','evidence_catalog':[]}
    result=P.for_analysis(a,n_frames=100,fps=15,object_concept='block',destination='drawer',dry_run=True)
    assert result['completion']=='not_assessed' and all(s['state']=='not_assessed' for s in result['assessments'])


@pytest.mark.parametrize('tag',[{'camera_id':'cam2'},{'source_video_id':'source2'}])
def test_another_camera_observation_cannot_enter_coverage(tag):
    with pytest.raises(ValueError,match='provenance mismatch'):
        A.camera_coverage(camera(),[{'frame_index':5,**tag}])
