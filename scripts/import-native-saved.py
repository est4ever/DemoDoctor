"""Operator-only local recovery; never downloads, infers, or publishes artifacts."""
import argparse,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from placement_assessment import service
from placement_assessment.support import need,read,write,sha

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True)
    p.add_argument('--permissions-and-privacy-reviewed',action='store_true');a=p.parse_args()
    need(a.permissions_and_privacy_reviewed,'Operator must review media permissions and local-only privacy before recovery')
    result=service.verify(a.source);native=result.get('native_video',{})
    need(result['source_sha256']==a.source_sha256 and native.get('mode')=='genuine_native_video','Wrong source or not a genuine saved native investigation')
    proof=a.source/'native-video';journal=read(proof/'operations.json')
    raw=read(proof/'response.body')
    need(journal['state']=='completed' and journal['mode']=='genuine_native_video' and raw['id']==journal['response_id'] and raw['status']=='completed','Incomplete execution record')
    need(sha(proof/'response.body')==read(proof/'response-receipt.json')['body_sha256'],'Response receipt mismatch')
    for path in a.source.rglob('*'):
        need(not path.is_symlink(),'Symlink cannot be recovered')
        if path.is_file():need(path.suffix in ('.json','.png','.mp4','.body') and not path.name.startswith('.'),'Unexpected private artifact in saved job')
    root=ROOT/'data/live_jobs';root.mkdir(parents=True,exist_ok=True)
    dest=root/a.source.name
    need(not dest.exists(),'Destination exists; never overwrite investigations')
    shutil.copytree(a.source,dest)
    (dest/'placement-seal.json').unlink()
    write(dest/'local-recovery.json',dict(original_seal_sha256=sha(a.source/'placement-seal.json'),source_sha256=a.source_sha256,
        local_only=True,permissions_privacy_reviewed=True,note='Local saved genuine replay; no inference and no media committed. Original remains unchanged.'))
    service.seal(dest);service.verify(dest)
    print(dest.name)
