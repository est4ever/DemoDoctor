"""Read-only citation metadata from original frozen artifacts; never outcomes/media.

Does not regenerate demonstrations or inference. Existing legacy export's EP010
frame/fps conversion is explicit. Only already-distributed catalog fields enter
the tiny frontend registry; private live-job directories are never read.
"""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from saved_provenance import single_authority


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def build():
    registry={}
    for ep in ('ep010','ep003','ep005','ep006','ep013','pilot'):
        if ep=='pilot':
            path=ROOT/'data/submission_demo/pilot/audit/after/evidence_package.json';a=read(path.parent/'analysis.json');package=read(path)
        else:
            a=read(ROOT/f'web/public/data/{ep}/analysis.json')
            if ep=='ep010':
                path=ROOT/'data/experiments/botfails_ep010_w1260_v2/failure_report.json';fr=read(path);items=[];fps=fr['inputs']['fps']
                for ev in fr.get('physical_events',[]):
                    for raw in ev.get('evidence',[]):
                        row={**raw,'evidence_id':f'E{len(items)}','status_context':ev.get('status')}
                        row['t_start']=row['frame_start']/fps if row.get('frame_start') is not None else None
                        row['t_end']=row['frame_end']/fps if row.get('frame_end') is not None else None
                        items.append(row)
                for note in fr.get('uncertainties',[])[:2]:
                    items.append({'evidence_id':f'E{len(items)}','source':'pipeline:report','kind':'derived','status_context':'uncertain','frame_start':None,'frame_end':None,'t_start':None,'t_end':None,'summary':str(note)[:400],'claims':[]})
                package={'evidence_catalog':items}
            else:
                path=ROOT/f'data/experiments/heldout_four_muse_comparison/{ep}/evidence_grounded/package_snapshot.json';package=read(path)
                # Match the documented legacy 30-fps export, deriving absent
                # times from original frames, never from displayed citations.
                for row in package.get('evidence_catalog',[]):
                    for key,frame_key in (('t_start','frame_start'),('t_end','frame_end')):
                        if row.get(key) is None and type(row.get(frame_key)) is int:row[key]=row[frame_key]/30.0
        authority=single_authority(a,package,path.relative_to(ROOT).as_posix(),hashlib.sha256(path.read_bytes()).hexdigest())
        assert all(r['status']=='record_match' for r in authority['records'].values()),(ep,authority)
        registry[a['episode_key']]=authority
    return registry


if __name__=='__main__':
    target=ROOT/'web/src/lib/recordedCitationBindings.json';raw=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    if '--check' in sys.argv:
        assert json.loads(target.read_text(encoding='utf-8'))==json.loads(raw),'Recorded citation registry differs from original source artifacts'
        print('Six source-derived citation registries match original artifacts')
    else:
        target.write_text(raw,encoding='utf-8');print('Wrote metadata only:',target.relative_to(ROOT),len(raw.encode('utf-8')),'bytes')
