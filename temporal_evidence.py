"""Local, camera-bound temporal evidence selection. No providers or physical labels.

Ranks actual adjacent returned-box changes and observation-gap boundaries rather
than assuming task phases from time fractions. A returned SAM ID is a proposal,
not independently verified identity. Nothing here settles a physical subgoal.
"""
from __future__ import annotations

import math
from collections import defaultdict


METHOD = 'camera-local-temporal-evidence/v1'
# Existing adapter serializes observation times to milliseconds. Native video
# timestamps remain authoritative; allow only that rounding error, not a frame.
TIMESTAMP_ROUNDING_S = .000500001


def select(camera, observations, limit=12):
    """Return original frame references and reproducible image-space measurements.

    No frame outside the approved analysis interval is called analyzed. Invalid,
    duplicate or conflicting object/frame records are excluded, never averaged.
    Native adjacency is required for every motion sample; gaps are not bridged.
    """
    from task_actions import frame_ranges
    start,end=camera['frame_start'],camera['frame_end'];times=camera['timestamps_s']
    if not (type(start) is int and type(end) is int and 0<=start<end<=camera['n_frames'] and len(times)==camera['n_frames']):
        raise ValueError('Invalid native interval/time mapping')
    if not all(isinstance(t,(int,float)) and not isinstance(t,bool) and math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Invalid native timestamps')
    width,height=camera.get('width'),camera.get('height')
    groups=defaultdict(list);invalid=0
    for index,o in enumerate(observations):
        f=o.get('frame_index');box=o.get('bbox');identity=o.get('object_id')
        if o.get('camera_id',camera['camera_id'])!=camera['camera_id'] or o.get('source_video_id',camera['source_video_id'])!=camera['source_video_id']:
            raise ValueError('Foreign camera/source observation')
        valid=(type(f) is int and start<=f<end and isinstance(identity,str) and bool(identity) and
            isinstance(box,(list,tuple)) and len(box)==4 and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in box) and
            box[0]<box[2] and box[1]<box[3] and o.get('observation_returned',True) is True and o.get('track_status','visible')=='visible')
        if valid and width and height:valid=0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height
        if valid and o.get('source_frame',f)!=f:valid=False
        if valid and 'original_timestamp_s' in o:
            t=o['original_timestamp_s'];valid=isinstance(t,(int,float)) and not isinstance(t,bool) and math.isfinite(t) and abs(t-times[f])<=TIMESTAMP_ROUNDING_S
        if valid and 'native_image_dimensions' in o and width and height:valid=list(o['native_image_dimensions'])==[width,height]
        if not valid:invalid+=1;continue
        groups[(identity,f)].append((index,box))
    tracks=defaultdict(dict);excluded=[]
    for (identity,f),records in groups.items():
        if len(records)!=1:excluded.append(f);invalid+=len(records);continue
        index,box=records[0];tracks[identity][f]={'index':index,'bbox':list(box),'center':[(box[0]+box[2])/2,(box[1]+box[3])/2]}
    observed=sorted({f for track in tracks.values() for f in track})
    spans=frame_ranges(observed);gaps=frame_ranges(set(range(start,end))-set(observed));steps=[]
    for identity,track in sorted(tracks.items()):
        for f,b in sorted(track.items()):
            a=track.get(f-1)
            if a is None:continue
            dx,dy=(b['center'][i]-a['center'][i] for i in range(2));dt=times[f]-times[f-1]
            steps.append({'object_id':identity,'frames':[f-1,f],'delta_xy_px':[dx,dy],
                'distance_px':math.hypot(dx,dy),'dt_s':dt,'speed_px_s':math.hypot(dx,dy)/dt,
                'observation_indices':[a['index'],b['index']],
                'scope':'Difference between adjacent returned SAM box centers; physical identity and motion remain unverified.'})
    # Fixed ranking, not learned from outcome labels: window bounds, largest
    # observed change, observation boundaries, then diverse native time coverage.
    reasons=defaultdict(list);picked=[]
    def add(f,reason):
        if start<=f<end:
            if reason not in reasons[f]:reasons[f].append(reason)
            if f not in picked and len(picked)<limit:picked.append(f)
    add(start,'Analysis start; inspect initial support/approach context')
    add(end-1,'Last analyzed frame; inspect final visible state, not proof of task completion')
    if steps:
        peak=max(steps,key=lambda s:(s['distance_px'],-s['frames'][0]))
        for f in peak['frames']:add(f,'Largest adjacent returned-box change; inspect motion or a possible false match')
    for a,b in sorted(gaps,key=lambda r:(-(r[1]-r[0]),r[0])):
        add(a-1,'Last returned observation before a gap; possible occlusion/placement context')
        add(b,'First returned observation after a gap; identity must be re-established')
        add((a+b-1)//2,'Original gap context; no SAM observation is invented')
    for a,b in spans:
        add(a,'Start of returned-observation span');add(b-1,'End of returned-observation span')
    while len(picked)<min(limit,end-start):
        f=max((i for i in range(start,end) if i not in picked),key=lambda i:(min(abs(times[i]-times[p]) for p in picked),-i))
        add(f,'Additional temporal context for intermediate manipulation/articulation; no action inferred')
    frames=[]
    for f in sorted(picked):
        candidates=[{'object_id':identity,'bbox':track[f]['bbox'],'observation_index':track[f]['index']} for identity,track in sorted(tracks.items()) if f in track]
        frames.append({'frame_ref':f'T_{camera["camera_id"]}_{f}','camera_id':camera['camera_id'],'source_video_id':camera['source_video_id'],
            'original_frame':f,'original_timestamp_s':times[f],'shared_timestamp_s':times[f]-camera['playback_offset_s'],
            'scope':'New local temporal selection; not added to historical Muse inputs and not verified physical-action support',
            'selection_reasons':reasons[f],'sam_observation_available':bool(candidates),'observations':candidates,
            'camera_sha256':camera['sha256'],'source_sha256':camera['source_sha256'],'crop':camera.get('crop')})
    return {'method':METHOD,'camera_id':camera['camera_id'],'source_video_id':camera['source_video_id'],'frames':frames,
        'adjacent_box_steps':steps,'observed_ranges':spans,'missing_ranges':gaps,'rejected_observation_records':invalid,
        'duplicate_frames':sorted(set(excluded)),'camera_motion':camera.get('motion','unknown'),
        'full_source_final_frame_assessed':end==camera['n_frames'],
        'limitations':['Returned track IDs do not establish physical identity. No motion is measured across gaps.',
            'Box differences are camera-local image coordinates, not surface-relative lift or calibrated 3D travel.',
            'Pickup needs associated gripper/support observations; placement needs a validated interior/final state; closure needs disjoint independent reference geometry.']}
