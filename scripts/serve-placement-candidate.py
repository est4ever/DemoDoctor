"""Serve the existing built React app and API, offline, on one isolated port."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import live_api
from fastapi.staticfiles import StaticFiles
import uvicorn

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=18890)
    args=parser.parse_args()
    live_api.OFFLINE_ONLY=True
    live_api.REAL_ANALYSIS_ENABLED=False
    live_api.TRUSTED_BROWSER_ORIGINS.update({f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'})
    live_api.app.mount('/',StaticFiles(directory=ROOT/'web/dist',html=True),name='application')
    uvicorn.run(live_api.app,host='127.0.0.1',port=args.port)
