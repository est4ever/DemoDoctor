"""Local source utilities; importing this module never invokes a provider."""
import hashlib
import json
from pathlib import Path
import numpy as np
import tracking


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def rle(mask, bbox):
    x,y,right,bottom=bbox
    a=mask[y:bottom,x:right].flatten(order='F').astype(np.uint8)
    boundaries=np.flatnonzero(np.diff(a))+1
    counts=np.diff(np.concatenate(([0],boundaries,[len(a)]))).tolist()
    if a[0]:counts.insert(0,0)
    return dict(size=[bottom-y,right-x],counts=counts)


def index(video, expected_hash, camera_id='cam1'):
    """Decode original bytes; no supplied timestamps, labels or event windows."""
    import av
    need(sha(video)==expected_hash, 'Registered video bytes changed')
    rows=[]
    with av.open(str(video)) as container:
        stream=container.streams.video[0]
        fps=float(stream.average_rate)
        for i,frame in enumerate(container.decode(video=0)):
            need(frame.pts is not None, 'Native timestamp missing')
            rgb=frame.to_ndarray(format='rgb24');t=float(frame.pts*frame.time_base)
            need(t>=0 and (not rows or t>rows[-1]['timestamp_s']), 'Nonmonotonic native timestamps')
            rows.append(dict(frame=i,timestamp_s=t,native_pts=frame.pts,time_base=str(frame.time_base),
                             frame_sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
        need(len(rows)>=2, 'Insufficient video frames')
    need(sha(video)==expected_hash, 'Source changed during indexing')
    return dict(source_sha256=expected_hash,source_video_id='source1',camera_id=camera_id,crop=None,
                width=rgb.shape[1],height=rgb.shape[0],fps=fps,n_frames=len(rows),frames=rows)
