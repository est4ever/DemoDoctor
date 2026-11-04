"""Provision two pinned publisher originals and the approved public rack template.

No provider, label, ROI, outcome or failure-time inputs. Downloads are explicit,
bounded, single-attempt and optional; exact original-video import is supported.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
from .support import index, need, read, sha, write

ROOT=Path(__file__).resolve().parents[1]
ASSETS=Path(__file__).resolve().parent/'assets'
STORE=ROOT/'data/placement_assets'
MANIFEST_SHA256='57bd664ad24112c9f89edeb4ec3e710c33617a731eb4705b4979c407903e200a'
SETUP='Run python -m placement_assessment.portable --download (63.25 MB from the official publisher), or --bf010 PATH --bf000 PATH to import exact originals. See docs/integration/PORTABLE_PLACEMENT_SETUP.md. No inference or API key is needed.'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def manifest():
    need(sha(ASSETS/'manifest.json')==MANIFEST_SHA256,'Unapproved placement asset manifest')
    data=read(ASSETS/'manifest.json')
    template=(ASSETS/data['template']['destination_cache']).resolve()
    need(template.is_relative_to(ASSETS.resolve()) and sha(template)==data['template']['destination_cache_sha256'],
         'Approved rack template is missing or altered')
    return data


def checked_index(path, spec):
    need(path.stat().st_size==spec['bytes'] and sha(path)==spec['sha256'],'Original video size/hash mismatch; a re-encode is not an approved substitute')
    native=index(path,spec['sha256'])
    need(all(native[k]==spec[k] for k in ('n_frames','width','height','fps')),'Original video geometry/frame count mismatch')
    need(hashlib.sha256(canonical(native)).hexdigest()==spec['decoded_index_sha256'],
         'Decoded frame identities or native timestamps differ; use the pinned dependencies, not a derivative')
    return native


def load_registry():
    """Default portable admission; does not download or provision at startup."""
    data=manifest()
    if not (STORE/'registration.json').is_file():return None
    receipt=read(STORE/'registration.json')
    need(receipt.get('manifest_sha256')==MANIFEST_SHA256,'Stale portable asset registration')
    sources={}
    for key,spec in data['sources'].items():
        video=STORE/spec['filename'];native_path=STORE/(key+'-source-index.json')
        need(video.is_file() and video.stat().st_size==spec['bytes'] and sha(video)==spec['sha256'],'Registered original video unavailable or altered. '+SETUP)
        native=read(native_path)
        need(hashlib.sha256(canonical(native)).hexdigest()==spec['decoded_index_sha256'],'Registered native frame mapping is missing or altered')
        sources[key]={k:spec[k] for k in ('sha256','label','task_description','task_criterion','camera')}
        sources[key]['video']=str(video.resolve())
    template=dict(data['template'])
    template['destination_cache']=str((ASSETS/template['destination_cache']).resolve())
    template['reference_video']=sources['ep010']['video']
    return dict(schema='demodoctor.assisted-placement-inputs/v1',task_criterion='all_required_green_plates_in_rack',
                template=template,sources=sources,portable_manifest_sha256=MANIFEST_SHA256)


def provision(download=False, supplied=None):
    data=manifest();supplied=supplied or {}
    need(not download or not supplied,'Choose publisher download OR original-file import')
    STORE.mkdir(parents=True,exist_ok=True)
    for key,spec in data['sources'].items():
        target=STORE/spec['filename']
        if key in supplied:
            # An existing correct installation must not hide a bad explicitly
            # supplied replacement. Reject it instead of silently ignoring it.
            checked_index(Path(supplied[key]).resolve(),spec)
        if target.exists():
            native=checked_index(target,spec)  # Never overwrite a mismatched existing source.
        else:
            temp=target.with_suffix('.mp4.part')
            need(not temp.exists(),'Incomplete prior acquisition found: inspect/remove only '+str(temp)+' before explicit retry')
            if download:
                # Publisher URL is pinned in the code-authorized manifest. The
                # CDN may redirect; accepted bytes still require the exact hash.
                request=urllib.request.Request(spec['url'],headers={'User-Agent':'DemoDoctor-public-asset-setup/1'})
                with urllib.request.urlopen(request,timeout=60) as response,temp.open('xb') as output:
                    declared=response.headers.get('Content-Length')
                    need(declared is None or int(declared)==spec['bytes'],'Unexpected publisher response size')
                    total=0
                    while True:
                        block=response.read(min(1024*1024,spec['bytes']-total+1))
                        if not block:break
                        total+=len(block);need(total<=spec['bytes'],'Publisher download exceeds approved size')
                        output.write(block)
            else:
                need(key in supplied,SETUP)
                source=Path(supplied[key]).resolve()
                # Reject the lossy bundle before copying or registering anything.
                checked_index(source,spec)
                with source.open('rb') as src,temp.open('xb') as dst:shutil.copyfileobj(src,dst)
            native=checked_index(temp,spec)
            temp.rename(target)
        write(STORE/(key+'-source-index.json'),native)
        print(key+': verified original bytes, '+str(native['n_frames'])+' native frame timestamps and RGB identities',flush=True)
    # Exercise the unchanged original-frame/JPEG/request-key/mask validation.
    from .detector import DestinationTemplate
    t=dict(data['template']);t['destination_cache']=str(ASSETS/t['destination_cache'])
    receipt=DestinationTemplate(t,read(STORE/'ep010-source-index.json'),STORE/data['sources']['ep010']['filename']).receipt
    registration=dict(manifest_sha256=MANIFEST_SHA256,template_receipt=receipt,
                      scope='Approved source assets only. No failure labels or inference results registered; findings must be computed.')
    temporary=STORE/'registration.pending.json';write(temporary,registration)
    os.replace(temporary,STORE/'registration.json')
    need(load_registry() is not None,'Portable registration unavailable')
    print('Ready. Start DemoDoctor normally; the assisted assessment discovers this verified local registration. No provider calls.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true',help='Download ONLY the two pinned original MP4 files (63,245,876 bytes total)')
    parser.add_argument('--bf010',type=Path);parser.add_argument('--bf000',type=Path)
    args=parser.parse_args()
    supplied={k:v for k,v in [('ep010',args.bf010),('bf000',args.bf000)] if v}
    try:provision(args.download,supplied)
    except (OSError,ValueError,KeyError) as error:
        parser.exit(1,'Setup incomplete: '+str(error)+'\nNo detector success or provider execution is claimed.\n')
