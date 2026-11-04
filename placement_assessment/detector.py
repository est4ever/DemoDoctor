"""Source-bound final visual placement contradiction; no provider calls/labels.

One saved genuine SAM rack image initializes a deterministic appearance template.
The target is independently registered in each evaluated source frame. Objects
are offline task-color/ellipse candidates, NOT recycled SAM object masks. No
same-instance association is asserted between recordings or across gaps.
"""
import argparse
import hashlib
import math
from pathlib import Path
import shutil
import sys
import time
import av,cv2,numpy as np
from . import support as core
from .features import window_candidate
from .regions import regions
from .support import rle

HERE=Path(__file__).resolve().parent
POLICY=core.read(HERE/'policy.json')


def native_images(video, source, selected):
    core.need(core.sha(video)==source['source_sha256'],'Source hash mismatch')
    images={}
    with av.open(str(video)) as container:
        count=0
        for i,frame in enumerate(container.decode(video=0)):
            count+=1
            if i not in selected:continue
            ref=source['frames'][i];rgb=frame.to_ndarray(format='rgb24')
            core.need(frame.pts==ref['native_pts'] and str(frame.time_base)==ref['time_base'] and
                      float(frame.pts*frame.time_base)==ref['timestamp_s'] and
                      hashlib.sha256(rgb.tobytes()).hexdigest()==ref['frame_sha256'],'Native frame binding mismatch')
            images[i]=rgb
    core.need(count==source['n_frames'] and set(images)==set(selected),'Missing source frames')
    return images


class DestinationTemplate:
    def __init__(self, inputs, src, video):
        INPUTS=inputs
        TEMPLATE_CACHE=Path(inputs['destination_cache'])
        TEMPLATE_FRAME=inputs['reference_frame']
        core.need(src['source_sha256']==INPUTS['reference_source_sha256'] and
                  src['frames'][TEMPLATE_FRAME]['frame_sha256']==INPUTS['reference_frame_sha256'] and
                  core.sha(TEMPLATE_CACHE)==INPUTS['destination_cache_sha256'],'Frozen reference or cache changed')
        rgb=native_images(video,src,[TEMPLATE_FRAME])[TEMPLATE_FRAME]
        ok,jpeg=cv2.imencode('.jpg',cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,95]);core.need(ok,'JPEG encoding failed')
        core.need(hashlib.sha256(jpeg.tobytes()).hexdigest()==INPUTS['reference_jpeg95_sha256'],'Original request JPEG changed')
        key=core.tracking.cache_key(jpeg.tobytes(),['dish rack'],media_kind='image')
        data=core.read(TEMPLATE_CACHE)
        core.need(key==TEMPLATE_CACHE.parent.name==data['cache_key'] and data['model']=='sam-3.1' and
                  data['provider']=='meta-sam-3.1' and data['available'] is True and data['concepts']==['dish rack'] and data['media_kind']=='image',
                  'Saved destination image does not match the reconstructed original request')
        core.need(data['diagnostics']['usage']['dish rack']['terminal_event']=='response.completed','Destination request not verified completed')
        core.need(len(data['observations'])==1,'Ambiguous destination instances')
        o=data['observations'][0]
        core.need(o['frame_index']==0 and o['timestamp_s']==0 and o['observation_returned'] is True,'Bad image-local frame binding')
        mask=core.tracking.mask_in_frame(o['mask_rle'],tuple(o['bbox']),rgb.shape[:2]);core.need(mask is not None and mask.any(),'Invalid target mask')
        self.mask=mask;self.gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);self.sift=cv2.SIFT_create()
        self.keys,self.descriptors=self.sift.detectAndCompute(self.gray,mask.astype(np.uint8)*255)
        self.receipt=dict(source_sha256=src['source_sha256'],camera_id=src['camera_id'],frame=TEMPLATE_FRAME,
            frame_sha256=src['frames'][TEMPLATE_FRAME]['frame_sha256'],timestamp_s=src['frames'][TEMPLATE_FRAME]['timestamp_s'],
            request_jpeg_sha256=hashlib.sha256(jpeg.tobytes()).hexdigest(),cache_key=key,cache_sha256=core.sha(TEMPLATE_CACHE),
            method='Exact original-frame JPEG95/request cache-key recomputation; saved completed SAM image. No new request.',
            source_scope='Appearance template. Its original source camera is NOT reassigned to the target video. Every target frame gets its own image registration.',
            absolute_error_bound_px=None)

    def locate(self, rgb):
        gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);keys,desc=self.sift.detectAndCompute(gray,None)
        if desc is None:return None,'no_target_frame_features'
        pairs=cv2.BFMatcher().knnMatch(self.descriptors,desc,k=2)
        matches=[a for pair in pairs if len(pair)==2 for a,b in [pair] if a.distance<POLICY['sift_ratio']*b.distance]
        # Multiple template descriptors cannot inflate support for one image point.
        unique={}
        for m in sorted(matches,key=lambda m:m.distance):unique.setdefault(m.trainIdx,m)
        matches=list(unique.values())
        if len(matches)<POLICY['registration_minimum_inliers']:return None,'insufficient_template_matches'
        p=np.float32([self.keys[m.queryIdx].pt for m in matches]);q=np.float32([keys[m.trainIdx].pt for m in matches])
        cv2.setRNGSeed(0)
        transform,inliers=cv2.estimateAffinePartial2D(p,q,method=cv2.RANSAC,ransacReprojThreshold=POLICY['registration_maximum_inlier_residual_px'],refineIters=10)
        if transform is None:return None,'registration_unavailable'
        keep=inliers.ravel().astype(bool);error=np.linalg.norm(np.column_stack((p,np.ones(len(p))))@transform.T-q,axis=1)
        keep &= error<=POLICY['registration_maximum_inlier_residual_px']
        scale=float(math.hypot(transform[0,0],transform[1,0]));angle=float(math.degrees(math.atan2(transform[1,0],transform[0,0])))
        support=cv2.contourArea(cv2.convexHull(p[keep]))/int(self.mask.sum()) if keep.sum()>=3 else 0
        if (keep.sum()<POLICY['registration_minimum_inliers'] or keep.mean()<POLICY['registration_minimum_inlier_fraction'] or
            support<POLICY['registration_minimum_support_fraction'] or not POLICY['registration_scale_range'][0]<=scale<=POLICY['registration_scale_range'][1] or
            abs(angle)>POLICY['registration_maximum_rotation_degrees']):return None,'registration_quality_rejected'
        warped=cv2.warpAffine(self.mask.astype(np.uint8),transform,(rgb.shape[1],rgb.shape[0]),flags=cv2.INTER_NEAREST).astype(bool)
        y,x=np.where(warped)
        if not len(x):return None,'target_outside_camera'
        return dict(mask=warped,bbox=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)],transform=transform.tolist(),
            inliers=int(keep.sum()),matches=len(matches),maximum_inlier_residual_px=float(error[keep].max()),
            support_fraction=float(support),scale=scale,rotation_degrees=angle,
            source_points_xy=p[keep].tolist(),target_points_xy=q[keep].tolist(),absolute_error_bound_px=None),None


def split_touching(mask):
    """Split a color component by source-derived inscribed-region markers.

    This is a geometric instance proposal, not a fabricated object outline.
    Unknown/occluded boundaries are never filled in the returned observations.
    """
    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    filled=np.zeros(mask.shape,np.uint8);cv2.drawContours(filled,contours,-1,1,-1)
    distance=cv2.distanceTransform(filled,cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
    radius=POLICY['split_peak_local_radius_px']
    maxima=(distance==cv2.dilate(distance,np.ones((2*radius+1,2*radius+1),np.uint8))) & (distance>=distance.max()*POLICY['split_peak_fraction'])
    count,labels,_,_=cv2.connectedComponentsWithStats(maxima.astype(np.uint8),8)
    peaks=[]
    for i in range(1,count):
        y,x=np.where(labels==i);j=int(np.argmax(distance[y,x]));peaks.append((float(distance[y[j],x[j]]),int(x[j]),int(y[j])))
    selected=[]
    for value,x,y in sorted(peaks,reverse=True):
        if all(math.hypot(x-u,y-v)>2*min(value,r) for r,u,v in selected):selected.append((value,x,y))
    if len(selected)<=1:return [mask]
    if len(selected)>POLICY['split_maximum_markers']:return []
    # OpenCV watershed operates on image gradients, not a supplied height field.
    # Use an explicit geometric partition rather than misusing distance as RGB.
    # Each output still contains only pixels actually classified green.
    y,x=np.indices(mask.shape)
    nearest=np.argmin(np.stack([(x-u)**2+(y-v)**2 for _,u,v in selected]),axis=0)
    return [(nearest==i)&mask for i in range(len(selected)) if ((nearest==i)&mask).any()]


def plate_candidates(rgb):
    accepted=[]
    split=[]
    for parent in regions(rgb):
        for mask in split_touching(parent['mask']):
            y,x=np.where(mask)
            split.append(dict(mask=mask,bbox=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)],area=int(mask.sum()),
                              semantic_status='Unverified source-pixel component split'))
    for r in split:
        contours,_=cv2.findContours(r['mask'].astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        contour=max(contours,key=cv2.contourArea)
        if len(contour)<5:continue
        ellipse=cv2.fitEllipse(contour);minor,major=sorted(ellipse[1])
        if major<rgb.shape[1]*POLICY['minimum_major_axis_image_fraction'] or minor/max(major,1)<POLICY['ellipse_minor_major_minimum']:continue
        fit=np.zeros(rgb.shape[:2],np.uint8);cv2.ellipse(fit,ellipse,1,-1);fit=fit.astype(bool)
        filled=np.zeros_like(fit,dtype=np.uint8);cv2.drawContours(filled,[contour],-1,1,-1);filled=filled.astype(bool)
        iou=float((fit&filled).sum()/max(1,(fit|filled).sum()))
        if iou<POLICY['ellipse_iou_minimum']:continue
        accepted.append(dict(r,ellipse_iou=iou,ellipse_axes_px=list(ellipse[1]),semantic_status='Inferred green plate class from task-color and ellipse prior; no cross-video instance identity'))
    return accepted


def assess(source, images, template):
    end=source['frames'][-1]['timestamp_s']
    expected=[r['frame'] for r in source['frames'] if r['timestamp_s']>=end-.5-1e-9]
    core.need(sorted(images)==expected,'Incomplete or substituted final native window; no gap bridging')
    for f,rgb in images.items():
        core.need(hashlib.sha256(rgb.tobytes()).hexdigest()==source['frames'][f]['frame_sha256'],
                  'Image bytes do not match the declared source frame')
    registrations={};candidates={};rejections=[];tracks={}
    for f,rgb in images.items():
        registered,reason=template.locate(rgb);registrations[f]=registered;candidates[f]=plate_candidates(rgb)
        tracks[str(f)]=[dict(bbox=r['bbox'],mask=rle(r['mask'],r['bbox']),concept='offline green plate candidate',object_id=f'frame-{f}-candidate-{i}') for i,r in enumerate(candidates[f])]
        if registered:
            tracks[str(f)].append(dict(bbox=registered['bbox'],mask=rle(registered['mask'],registered['bbox']),concept='registered SAM rack appearance template',object_id='target'))
        else:rejections.append(dict(frame=f,reason=reason))
    ordered=sorted(images);events=[];decisions=[]
    if rejections:return events,decisions,registrations,tracks,rejections
    for index,seed in enumerate(candidates[ordered[0]]):
        part=[];measurements=[];previous=seed;reason=None
        for f in ordered:
            matches=[r for r in candidates[f] if (r['mask']&previous['mask']).sum()/max(1,(r['mask']|previous['mask']).sum())>=POLICY['consecutive_mask_iou_minimum']]
            if len(matches)!=1:reason='missing_or_ambiguous_plate_continuity';break
            r=matches[0];previous=r;ref=source['frames'][f];target=registrations[f]
            gap=max(r['bbox'][0]-target['bbox'][2],target['bbox'][0]-r['bbox'][2])
            record=dict(frame=f,timestamp_s=ref['timestamp_s'],object_bbox=r['bbox'],target_bbox=target['bbox'],
                lateral_gap_px=gap,ellipse_iou=r['ellipse_iou'],target_registration_inliers=target['inliers'],
                target_registration_residual_px=target['maximum_inlier_residual_px'],absolute_error_bound_px=None)
            measurements.append(record)
            evidence=dict(ref,source_sha256=source['source_sha256'],source_video_id=source['source_video_id'],camera_id=source['camera_id'],crop=source['crop'])
            part.append(dict(frame=f,time_s=ref['timestamp_s'],gray=cv2.cvtColor(images[f],cv2.COLOR_RGB2GRAY),mask=r['mask'],identity=f'final-region-{index}',citation=evidence))
        event=None
        if reason is None:event,reason=window_candidate(part)
        if event and event['kind']!='image_feature_stability':reason='final_region_not_image_stable';event=None
        separated=bool(event and all(m['lateral_gap_px']>POLICY['target_padding_px'] for m in measurements))
        decision=dict(candidate=index,qualifies=separated,reason=reason or ('clearly_laterally_outside' if separated else 'not_clearly_laterally_outside'),measurements=measurements)
        decisions.append(decision)
        if separated:
            event.update(event_id=f'FINAL{index}',frame_start=ordered[0],frame_end=ordered[-1]+1,observed_start_s=part[0]['time_s'],observed_end_s=part[-1]['time_s'],
                evidence=[r['citation'] for r in part],segment_id=f'final-region-{index}',source_sha256=source['source_sha256'],camera_id=source['camera_id'],crop=source['crop'],
                identity='Inferred plate class; no physical instance association across gaps',measurement_basis='Persistent original features and same-frame registered destination enclosure; no centroid-motion claim.',
                minimum_target_gap_px=min(m['lateral_gap_px'] for m in measurements),
                limitation='Visible final-state outside criterion only; failure onset, contact, grasp, release and cause Unverified. Registration residuals are not absolute error bounds.')
            events.append(event)
    return events,decisions,registrations,tracks,rejections

