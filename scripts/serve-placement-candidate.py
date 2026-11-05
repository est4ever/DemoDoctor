"""Serve the existing built React app and API, offline, on one isolated port."""
import argparse
from pathlib import Path
import sys
import os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import live_api
from fastapi.staticfiles import StaticFiles
import uvicorn

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=18890)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--mock-native',action='store_true',help='SDK MockTransport only; no provider requests')
    mode.add_argument('--native-live',action='store_true',help='Enable reviewed native worker; browser authorization still required')
    parser.add_argument('--reviewed-implementation',help='Independently accepted implementation SHA-256, not a Git hash')
    parser.add_argument('--ledger',type=Path,help='Existing ledger; never created or increased for live execution')
    args=parser.parse_args()
    live_api.OFFLINE_ONLY=True
    live_api.REAL_ANALYSIS_ENABLED=False
    if args.mock_native:
        from scripts.native_video_offline import mock_client
        from placement_assessment.support import write
        folder=ROOT/'qa-browser-artifacts/native-product-mock';folder.mkdir(parents=True,exist_ok=True)
        ledger=folder/'mock-ledger.json'
        if not ledger.exists():write(ledger,dict(total_budget_usd=10,per_run_budget_usd=1.5,spent_usd=0,reserved_usd=0,events=[],reservations={}))
        live_api.app.state.native_mock=dict(client=mock_client,ledger=ledger)
    if args.native_live:
        from placement_assessment import meta_video as M
        if not args.reviewed_implementation or args.reviewed_implementation!=M.implementation():parser.error('Exact independently reviewed implementation hash required')
        if not args.ledger or not args.ledger.is_file():parser.error('An existing ledger is required; no budget limits are changed')
        M.live_budget.LEDGER_PATH=args.ledger.resolve()
        os.environ['DEMODOCTOR_NATIVE_VIDEO_ENABLED']='1'
        os.environ['DEMODOCTOR_NATIVE_VIDEO_REVIEWED_SHA256']=args.reviewed_implementation
        live_api.OFFLINE_ONLY=False
    live_api.TRUSTED_BROWSER_ORIGINS.update({f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'})
    live_api.app.mount('/',StaticFiles(directory=ROOT/'web/dist',html=True),name='application')
    uvicorn.run(live_api.app,host='127.0.0.1',port=args.port)
