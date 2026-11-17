"""Serial, two-core Application A/B runs. Every case owns isolated userdata."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime
import psutil

ROOT = Path(__file__).resolve().parents[1]
SCENES = {'ordinary': 20, 'mixed': 120, 'barrage': 240, 'grabber': 120}
ARMS = {
    'legacy': {},
    'sliced': {'PVP744_STEP_BUDGET_MS': '8'},
    'adaptive': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1'},
    'guard035': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1', 'PVP744_FIXED_GUARD': '.35'},
    'single': {'PVP744_STEP_LIMIT': '1', 'PVP744_PACING': '1'},
    'view': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1', 'PVP744_VIEW_REUSE': '1'},
    'localframe': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1', 'PVP744_VIEW_REUSE': '1', 'PVP744_LOCAL_FRAME': '1'},
    'stateview': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1', 'PVP744_VIEW_REUSE': '1', 'PVP744_LOCAL_FRAME': '1', 'PVP744_STATE_VIEW': '1'},
    'metadata': {'PVP744_STEP_BUDGET_MS': '8', 'PVP744_PACING': '1', 'PVP744_VIEW_REUSE': '1', 'PVP744_LOCAL_FRAME': '1', 'PVP744_STATE_VIEW': '1', 'PVP744_METADATA_VIEW': '1'},
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True)
    p.add_argument('--exe', default=str(ROOT/'build/app-typed72-v2/Release/pvp743_pacing_lab.exe'))
    p.add_argument('--scenes', nargs='+', choices=SCENES, default=['ordinary', 'barrage', 'grabber'])
    p.add_argument('--arms', nargs='+', choices=ARMS, default=['legacy', 'sliced', 'adaptive'])
    p.add_argument('--scale', default='auto')
    p.add_argument('--wall', action='store_true', help='fixed wall time, not equal logical work')
    p.add_argument('--seconds', type=float, default=40.)
    p.add_argument('--ticks', type=int, default=150)
    p.add_argument('--warm-ticks', type=int, default=150)
    p.add_argument('--interactive', action='store_true')
    p.add_argument('--profile', action='store_true')
    a = p.parse_args()
    if a.interactive and (len(a.scenes)!=1 or len(a.arms)!=1): p.error('one interactive case at a time')
    if not 1 <= a.seconds <= 600 or not 1 <= a.ticks <= 1800: p.error('duration out of range')
    if a.scale != 'auto' and not .1 <= float(a.scale) <= 1.: p.error('scale must be auto or .10-1')
    out = (ROOT/'test_results/pvp744'/('manual-'+datetime.now().strftime('%Y%m%d-%H%M%S'))) if a.out=='auto' else Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    exe = Path(a.exe).resolve(); sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    rows = []
    for scene in a.scenes:
        for arm in a.arms:
            folder = out/(scene+'-'+arm); folder.mkdir()
            cfg = dict(scenario=scene, units=SCENES[scene], prime_tentacles=scene=='grabber',
                       seconds=a.seconds, warmup_seconds=5, interactive_input=a.interactive,
                       label='PvP performance '+arm+' / '+scene+' / '+a.scale)
            if not a.wall and not a.interactive:
                cfg.update(warmup_room_ticks=a.warm_ticks, measure_room_ticks=a.ticks)
            if a.scale != 'auto': cfg['fixed_scale'] = float(a.scale)
            (folder/'config.json').write_text(json.dumps(cfg, indent=2), 'utf8')
            env = {k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')
                   and not k.startswith('PVP744_')}
            env.update(NO_PROXY='*', no_proxy='*', PVP_USERDATA=str(folder/'userdata'),
                       PVP741_PROFILE='1' if a.profile else '0')
            env.update(ARMS[arm])
            if a.interactive: env['PVP744_INPUT_TRACE'] = '1'
            if not a.interactive: env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
            with (folder/'process.log').open('wb') as log:
                proc = subprocess.Popen([str(exe),str(folder/'config.json'),str(folder/'report.json')],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
                ps = psutil.Process(proc.pid); ps.cpu_affinity(ps.cpu_affinity()[-2:]); ps.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                (folder/'process.json').write_text(json.dumps(dict(pid=proc.pid, affinity=ps.cpu_affinity(),
                    exe=str(exe), exe_sha256=sha, arm=arm, switches=ARMS[arm], profile=a.profile),indent=2),'utf8')
                try: code = proc.wait(timeout=max(600,a.seconds*3))
                finally:
                    if proc.poll() is None: proc.terminate();proc.wait(timeout=10)
            if code: raise RuntimeError((folder/'process.log').read_text('utf8',errors='replace'))
            d = json.loads((folder/'report.json').read_text('utf8'))
            trace = d['pacing_lab']['applied']
            row = dict(scene=scene, arm=arm, fixed_scale=a.scale, wall=d['wall_seconds'],
                fps=d['presentation']['frames_per_second'], ratio=d['simulation_wall_ratio'],
                native_ticks=d['native_ticks'], tick=d['final_state']['tick'],
                state=d['final_state_sha256'], rng=d['final_rng_sha256'],
                min_scale=min((x['scale'] for x in trace),default=None),
                last_scale=trace[-1]['scale'] if trace else None,
                max_debt=max((x['accumulator'] for x in trace),default=None),
                phases=d['frame_phases_ms'], long_frames=d['over_budget_pct'])
            rows.append(row)
            comparisons = {}
            if not a.wall and not a.interactive:
                for name in a.scenes:
                    rr=[r for r in rows if r['scene']==name]
                    comparisons[name]=dict(cases=len(rr),equal_state_rng=len({(r['state'],r['rng'],r['tick'],r['native_ticks']) for r in rr})<=1)
            (out/'summary.json').write_text(json.dumps(dict(completed=len(rows)==len(a.scenes)*len(a.arms),
                denominator='wall' if a.wall or a.interactive else 'logical ticks',
                comparisons=comparisons,results=rows),indent=2),'utf8')
            print(json.dumps({k:v for k,v in row.items() if k not in ('phases','long_frames')}) ,flush=True)
    if any(not v['equal_state_rng'] for v in comparisons.values()): raise SystemExit('state/RNG mismatch')


if __name__=='__main__': main()
