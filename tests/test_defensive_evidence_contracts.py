"""Defensive evidence contracts only; no experimental detector dependency."""
from dataclasses import replace
from urllib.parse import quote
import pytest
import task_criteria as T
from test_task_criteria import TASK, _ev
from test_task_actions import closure_evidence


@pytest.mark.parametrize('start,end',[(-1,10),(101,110),(10,101),(20,10),(10,10),(True,20),(10.5,20)])
def test_unobserved_or_invalid_release_spans_never_establish_failure(start,end):
    event=T.EventRecord('dropped_in_transport','released_outside_target','observed','plate:0',start,end,('E2',),'supported')
    ev=_ev(gripper='measured',holding_detectable=True,gripper_evidence_ids=('E2',),events=[event])
    report=T.assess(TASK,ev)
    assert report.by_id('grasp_release').state=='unverified' and report.completion!='contradicted'
    assert all(m.status=='unverified' for m in report.mechanisms)



def test_release_must_be_in_the_declared_view_scope_and_relevant_object():
    event=T.EventRecord('dropped_in_transport','released_outside_target','observed','plate:0',10,20,('E2',),'supported')
    ev=_ev(gripper='measured',holding_detectable=True,gripper_evidence_ids=('E2',),events=[event],analyzed_ranges=(('primary',50,100),))
    assert T.assess(TASK,ev).by_id('grasp_release').state=='unverified'
    other=replace(event,track_id='other:0')
    ev=_ev(gripper='measured',holding_detectable=True,gripper_evidence_ids=('E2',),events=[other])
    assert T.assess(TASK,ev).by_id('grasp_release').state=='unverified'



def test_holding_flag_without_measurement_is_not_an_observed_release():
    event=T.EventRecord('dropped_in_transport','released_outside_target','observed','plate:0',10,20,('E2',),'supported')
    ev=_ev(holding_detectable=True,gripper='unavailable',events=[event])
    assert T.assess(TASK,ev).by_id('grasp_release').state=='unverified'



def test_legacy_single_view_scope_cannot_authorize_an_undeclared_multi_view_camera():
    event=T.EventRecord('dropped_in_transport','released_outside_target','observed','plate:0',10,20,('E2',),'supported')
    ev=_ev(gripper='measured',holding_detectable=True,gripper_evidence_ids=('E2',),events=[event],viewpoints=('left','right'))
    assert T.assess(TASK,ev).by_id('grasp_release').state=='unverified'



def test_orientation_of_an_unrelated_object_cannot_become_a_task_mechanism():
    pose=T.OrientationObservation('unrelated:0',False,99,('E2',))
    task=replace(TASK,criteria=TASK.criteria+(T.CriterionSpec('pose','orientation',True,'Upright',params={'required_pose':'upright'}),))
    report=T.assess(task,_ev(orientation_observations=[pose]))
    assert report.by_id('pose').state=='unverified'
    assert not any(m.category=='incorrect_orientation' for m in report.mechanisms)



@pytest.mark.parametrize('reference',['end','start','encoded-end'])
def test_reference_artifact_cannot_be_the_assessed_observation(reference):
    import task_actions
    ev=closure_evidence();first,last=ev.predicates
    ref=first.source_ref if reference=='start' else last.source_ref
    if reference=='encoded-end':ref=quote(ref,safe='')
    ev.predicates=tuple(replace(p,measurement={**p.measurement,'reference_geometry_source':ref}) for p in ev.predicates)
    assert T.assess(task_actions.parse_task('Close the drawer','block','drawer'),ev).by_id('step_1').state=='unverified'
