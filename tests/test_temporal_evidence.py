from copy import deepcopy
import pytest
from temporal_evidence import select


def camera(**kw):
    return dict(camera_id='cam1',source_video_id='source1',frame_start=0,frame_end=12,n_frames=15,
        width=320,height=240,fps=10,timestamps_s=[i/10 for i in range(15)],playback_offset_s=0,
        sha256='a'*64,source_sha256='b'*64,crop=[0,0,320,240],motion='static')|kw


def observations():
    return [dict(object_id='block:0',frame_index=i,bbox=[10+i,20,20+i,30],camera_id='cam1',source_video_id='source1') for i in range(12)]


def test_peak_changes_and_gaps_use_original_frames_without_inventing_actions():
    obs=observations();obs=[o for o in obs if o['frame_index'] not in (5,6,7)]
    for o in obs:
        if o['frame_index']==4:o['bbox']=[40,20,50,30]
    r=select(camera(),obs);frames={f['original_frame']:f for f in r['frames']}
    assert {0,3,4,6,8,11}<=frames.keys()
    assert frames[6]['sam_observation_available'] is False and frames[8]['sam_observation_available']
    assert r['missing_ranges']==[[5,8]] and not r['full_source_final_frame_assessed']
    assert all(b==a+1 and not(a<5 and b>=8) for a,b in [s['frames'] for s in r['adjacent_box_steps']])
    assert max(r['adjacent_box_steps'],key=lambda s:s['distance_px'])['delta_xy_px']==[27,0]
    assert all('not verified physical-action' in f['scope'] for f in frames.values())
    assert not any('state' in f for f in frames.values())


@pytest.mark.parametrize('mutation',[{'bbox':[0,0,0,0]},{'bbox':[float('nan'),0,20,20]},{'source_frame':99},
    {'original_timestamp_s':None},{'native_image_dimensions':[240,320]},{'observation_returned':False},{'track_status':'occluded'}])
def test_invalid_observation_is_missing_not_interpolated(mutation):
    obs=observations();obs[5].update(mutation);r=select(camera(),obs)
    assert r['rejected_observation_records']==1 and [5,6] in r['missing_ranges']
    assert not any(5 in s['frames'] for s in r['adjacent_box_steps'])


def test_duplicate_and_identity_switch_are_not_continuous_motion():
    obs=observations();obs.append(deepcopy(obs[5]))
    for o in obs:
        if o['frame_index']>=8:o['object_id']='other:0'
    r=select(camera(),obs)
    assert r['duplicate_frames']==[5]
    assert not any(s['frames']==[7,8] for s in r['adjacent_box_steps'])


@pytest.mark.parametrize('field',['camera_id','source_video_id'])
def test_foreign_camera_is_rejected(field):
    obs=observations();obs[0][field]='other'
    with pytest.raises(ValueError):select(camera(),obs)


def test_moving_camera_only_has_image_coordinate_measurements_and_original_offsets():
    r=select(camera(motion='moving',playback_offset_s=.2,frame_start=2),observations())
    assert r['camera_motion']=='moving'
    assert r['frames'][0]['shared_timestamp_s']==0
    assert all('physical identity' in s['scope'] for s in r['adjacent_box_steps'])
    assert all('state' not in s for s in r['adjacent_box_steps'])


@pytest.mark.parametrize('times',[[0]*15,[float('nan')]*15])
def test_bad_timestamps_rejected(times):
    with pytest.raises(ValueError):select(camera(timestamps_s=times),observations())


def test_no_detections_still_provides_original_context_without_measurements():
    r=select(camera(),[])
    assert not r['adjacent_box_steps'] and all(not f['sam_observation_available'] for f in r['frames'])
    assert r['missing_ranges']==[[0,12]]


def test_existing_millisecond_provider_times_map_to_exact_native_pts_not_new_frames():
    c=camera(fps=15,timestamps_s=[i/15 for i in range(15)])
    obs=observations()
    for o in obs:o['original_timestamp_s']=round(c['timestamps_s'][o['frame_index']],3)
    r=select(c,obs)
    assert r['observed_ranges']==[[0,12]]
    assert all(f['original_timestamp_s']==c['timestamps_s'][f['original_frame']] for f in r['frames'])
    obs[4]['original_timestamp_s']+=1/15
    assert select(c,obs)['rejected_observation_records']==1
