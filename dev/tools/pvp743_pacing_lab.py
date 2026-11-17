"""Sequential low-load pacing exploration or one visible manual-input scene."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import psutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True)
    p.add_argument('--scales',nargs='+',default=['auto','0.65','0.35','0.20'])
    p.add_argument('--interactive',action='store_true',help='visible single case; user judges input responsiveness')
    p.add_argument('--seconds',type=float,default=180)
    a=p.parse_args()
    if a.interactive and len(a.scales)!=1:p.error('interactive mode requires one scale')
    for s in a.scales:
        if s!='auto' and not .10<=float(s)<=1:p.error('scale must be auto or 0.10-1.0')
    if not 1<=a.seconds<=600:p.error('seconds must be 1-600')
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    exe=ROOT/'build/app-typed72-v2/Release/pvp743_pacing_lab.exe'
    rows=[]
    for scale in a.scales:
        folder=out/scale;folder.mkdir()
        cfg=dict(scenario='grabber',units=120,prime_tentacles=True,seconds=a.seconds,
                 warmup_seconds=5,interactive_input=a.interactive)
        if not a.interactive:cfg.update(warmup_room_ticks=150,measure_room_ticks=150)
        if scale!='auto':cfg['fixed_scale']=float(scale)
        (folder/'config.json').write_text(json.dumps(cfg,indent=2),'utf8')
        env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')}
        env.update(NO_PROXY='*',no_proxy='*',PVP_USERDATA=str(folder/'userdata'))
        if not a.interactive:env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
        with (folder/'process.log').open('wb') as log:
            proc=subprocess.Popen([str(exe),str(folder/'config.json'),str(folder/'report.json')],cwd=ROOT,
                env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
            ps=psutil.Process(proc.pid);ps.cpu_affinity(ps.cpu_affinity()[-2:]);ps.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            (folder/'process.json').write_text(json.dumps(dict(pid=proc.pid,affinity=ps.cpu_affinity(),
                exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest()),indent=2),'utf8')
            try:code=proc.wait(timeout=600)
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
        if code:raise RuntimeError((folder/'process.log').read_text('utf8',errors='replace'))
        d=json.loads((folder/'report.json').read_text('utf8'))
        row=dict(scale=scale,wall_seconds=d['wall_seconds'],fps=d['presentation']['frames_per_second'],
            sim_ratio=d['simulation_wall_ratio'],native_ticks=d['native_ticks'],
            final_tick=d['final_state'].get('tick'),state_hash=d['final_state_sha256'],rng_hash=d['final_rng_sha256'],
            phases={k:d['frame_phases_ms'][k] for k in ['frame_interval_actual','room_update','refresh','render']})
        rows.append(row);print(json.dumps(row),flush=True)
        (out/'summary.json').write_text(json.dumps(dict(completed=len(rows)==len(a.scales),results=rows,
            scope='Fixed logical tick denominator for noninteractive cases; fixed scale overrides are exploratory, not an adaptive floor patch or physical input acceptance'),indent=2),'utf8')


if __name__=='__main__':main()
