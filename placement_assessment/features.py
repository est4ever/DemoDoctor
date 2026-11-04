"""Small source-pixel adapter using existing LK and temporal policy settings.

No ROI/time/answer inputs; no dark-region or rejected occlusion correction.
Mask centroids never drive motion. Same feature identities must survive every
frame in a fixed interval. Residuals are screens, not localization-error bounds.
"""
from collections import Counter,deque
import hashlib,json,math
from pathlib import Path
import av,cv2,numpy as np

TEMPORAL=json.loads(Path(__file__).with_name('temporal_policy.json').read_text())

POLICY=json.loads(Path(__file__).with_name('motion_policy.json').read_text())

def correspondence(previous,current,points,mask,policy=POLICY):
    opts=dict(winSize=(policy['window_px'],)*2,maxLevel=policy['levels'],
        criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
    q,s1,_=cv2.calcOpticalFlowPyrLK(previous,current,points.reshape(-1,1,2),None,**opts)
    if q is None:return None,None,None
    b,s2,_=cv2.calcOpticalFlowPyrLK(current,previous,q,None,**opts)
    if b is None:return None,None,None
    q=q.reshape(-1,2);b=b.reshape(-1,2);fb=np.linalg.norm(b-points,axis=1)
    h,w=current.shape;finite=np.isfinite(q).all(axis=1)&np.isfinite(fb)
    keep=s1.ravel().astype(bool)&s2.ravel().astype(bool)&finite&(fb<=policy['fb_limit_px'])
    for k,(a,z) in enumerate(zip(points,q)):
        if not keep[k]:continue
        x,y=np.rint(z).astype(int)
        if not(0<=x<w and 0<=y<h and mask[y,x]):keep[k]=False;continue
        side=policy['patch_size'];patch_a=cv2.getRectSubPix(previous,(side,side),tuple(map(float,a))).astype(float)
        patch_b=cv2.getRectSubPix(current,(side,side),tuple(map(float,z))).astype(float)
        corr=float(np.corrcoef(patch_a.ravel(),patch_b.ravel())[0,1]) if patch_a.std()>1e-6 and patch_b.std()>1e-6 else -1
        if not math.isfinite(corr) or corr<policy['minimum_patch_correlation']:keep[k]=False
    return q,keep,fb

def window_candidate(part,policy=POLICY):
    """No source-specific category or event interval; part is a fixed clock bin."""
    if any(r['mask'] is None for r in part):return None,'missing_or_unreliable_mask'
    if len({r['identity'] for r in part})!=1:return None,'model_identity_changed'
    if part[-1]['time_s']-part[0]['time_s']<TEMPORAL['minimum_interval_s']:return None,'interval_too_short'
    first=part[0];p=cv2.goodFeaturesToTrack(first['gray'],mask=first['mask'].astype(np.uint8)*255,
        **{k:policy[k] for k in ('maxCorners','qualityLevel','minDistance','blockSize')})
    if p is None or len(p)<policy['minimum_features']:return None,'insufficient_source_features'
    p=p.reshape(-1,2);seed_count=len(p);paths=[p.copy()];residual=[];previous=first['gray']
    for row in part[1:]:
        q,keep,fb=correspondence(previous,row['gray'],p,row['mask'],policy)
        if q is None:return None,'correspondence_unavailable'
        paths=[x[keep] for x in paths];p=q[keep]
        if len(p)<max(policy['minimum_features'],math.ceil(seed_count*policy['minimum_survival'])):return None,'feature_support_lost'
        paths.append(p.copy());residual.extend(fb[keep].tolist());previous=row['gray']
    seed=paths[0]
    support=float(cv2.contourArea(cv2.convexHull(seed)))/max(1,int(first['mask'].sum()))
    if support<policy['minimum_hull_fraction']:return None,'features_too_concentrated'
    positions=np.asarray(paths);deltas=positions-positions[0]
    translation=np.median(deltas,axis=1)
    # Rigid image rotation/scale must not be confused with inconsistent tracks.
    # Fit only to the same surviving feature identities, never to mask centers.
    # No polygon/hidden boundary is extrapolated from the fit.
    fit_residual=[]
    for current_points in positions:
        cv2.setRNGSeed(0)
        transform,inliers=cv2.estimateAffinePartial2D(seed,current_points,method=cv2.RANSAC,
            ransacReprojThreshold=policy['coherence_residual_px'])
        if transform is None:return None,'incoherent_feature_motion'
        predicted=np.column_stack((seed,np.ones(len(seed))))@transform.T
        fit_residual.append(float(np.linalg.norm(predicted-current_points,axis=1).max()))
    if max(fit_residual)>policy['coherence_residual_px']:return None,'incoherent_feature_motion'
    diameter=np.linalg.norm(translation[:,None,:]-translation[None,:,:],axis=2)
    i,j=np.unravel_index(np.argmax(diameter),diameter.shape)
    if i>j:i,j=j,i
    maximum=float(diameter[i,j]);threshold=TEMPORAL['resolved_motion_margin_px']
    kind='image_feature_motion' if maximum>threshold else 'image_feature_stability'
    return dict(kind=kind,state='Inferred',measurement_basis='Persistent source features within each returned mask; not mask-centroid displacement.',
        median_feature_displacement_px=maximum,threshold_px=threshold,witnessing_frames=[part[i]['frame'],part[j]['frame']],
        surviving_features=len(seed),initial_features=seed_count,support_hull_fraction=support,
        maximum_fb_residual_px=max(residual,default=0),maximum_coherence_residual_px=max(fit_residual),
        feature_paths=[dict(frame=r['frame'],points_xy=positions[k].tolist()) for k,r in enumerate(part)],
        trajectory=[dict(frame=r['frame'],time_s=r['time_s'],xy=np.median(positions[k],axis=0).tolist()) for k,r in enumerate(part)],
        absolute_error_bound_px=None,identity='SAM query/model ID only, not independently confirmed',
        camera_motion='unknown; common camera motion may explain image displacement',
        physical_confirmation=False),None
