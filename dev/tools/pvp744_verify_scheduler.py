"""Run the native scheduler and existing input/mechanism gates serially."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import psutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    candidate={'PVP744_PACING':'1','PVP744_STEP_LIMIT':'1','PVP744_STEP_BUDGET_MS':'8',
               'PVP744_VIEW_REUSE':'1','PVP744_INPUT_TRACE':'1'}
    jobs=[('scheduler-legacy','pvp744_scheduler_audit',{'PVP744_INPUT_TRACE':'1'}),
          ('scheduler-candidate','pvp744_scheduler_audit',candidate),
          ('performance','pvp742_performance_audit',{}),('combat','pvp741_combat_audit',{}),
          ('network-legacy','pvp742_network_refresh_audit',{'PVP741_PROFILE':'1'}),
          ('network-candidate','pvp742_network_refresh_audit',{**candidate,'PVP741_PROFILE':'1'}),
          ('presentation','pvp744_presentation_audit',{}),
          ('local-frame','pvp744_local_frame_audit',{'PVP744_LOCAL_FRAME':'1','PVP742_VERIFY_FRAME':'1'}),
          ('network-local-frame','pvp742_network_refresh_audit',{**candidate,'PVP744_LOCAL_FRAME':'1','PVP741_PROFILE':'1'}),
          ('state-view','pvp744_state_view_audit',{'PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1'}),
          ('pixels-state-view','pvp744_local_frame_audit',{'PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1','PVP742_VERIFY_FRAME':'1'}),
          ('scheduler-state-view','pvp744_scheduler_audit',{**candidate,'PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1'}),
          ('network-state-view','pvp742_network_refresh_audit',{**candidate,'PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP741_PROFILE':'1'}),
          ('metadata','pvp744_state_view_audit',{'PVP744_METADATA_VIEW':'1','PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1'}),
          ('pixels-metadata','pvp744_local_frame_audit',{'PVP744_METADATA_VIEW':'1','PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1','PVP742_VERIFY_FRAME':'1'}),
          ('scheduler-metadata','pvp744_scheduler_audit',{**candidate,'PVP744_METADATA_VIEW':'1','PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP744_VERIFY_STATE':'1'}),
          ('network-metadata','pvp742_network_refresh_audit',{**candidate,'PVP744_METADATA_VIEW':'1','PVP744_STATE_VIEW':'1','PVP744_LOCAL_FRAME':'1','PVP741_PROFILE':'1'})]
    rows=[]
    for name,target,settings in jobs:
        env={k:v for k,v in os.environ.items() if not k.startswith('PVP744_')}
        env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',
                   PVP_USERDATA=str(out/(name+'-userdata')),PVP741_PROFILE='0');env.update(settings)
        exe=ROOT/'build/app-typed72-v2/Release'/(target+'.exe')
        with (out/(name+'.log')).open('wb') as log:
            proc=subprocess.Popen([str(exe),str(out/(name+'.json'))],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
            ps=psutil.Process(proc.pid);ps.cpu_affinity(ps.cpu_affinity()[-2:]);ps.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            try:code=proc.wait(timeout=600)
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
        result=json.loads((out/(name+'.json')).read_text('utf8')) if (out/(name+'.json')).exists() else {}
        checks=result.get('checks',[])
        rows.append(dict(name=name,exit_code=code,checks=len(checks),passed=sum(bool(c.get('passed')) for c in checks),
            exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),settings=settings))
        (out/'summary.json').write_text(json.dumps(dict(completed=len(rows)==len(jobs),results=rows),indent=2),'utf8')
        print(json.dumps(rows[-1]),flush=True)
    if any(r['exit_code'] or r['checks']!=r['passed'] for r in rows):raise SystemExit('native gate failure')


if __name__=='__main__':main()
