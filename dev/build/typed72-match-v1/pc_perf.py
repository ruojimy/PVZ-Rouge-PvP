"""PC performance with the agreed three-scene scheme (device_bench72.py): 3 rounds, scene order
rotating per round, ordinary=20 / mixed=60 / barrage=120 units, warmup 5 s + 30 s sample, one
fresh process per sample, world_quality native, pixel filter, optimized, detail off.
Real window (default SDL video driver): FPS is rendered FPS, not simulation throughput.
Usage: pc_perf.py <out-dir> <label>=<package-dir> [<label>=<package-dir> ...]"""
import json,os,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
variants=[a.split('=',1) for a in sys.argv[2:]]
orders=[['ordinary','mixed','barrage'],['barrage','mixed','ordinary'],['mixed','ordinary','barrage']]
sizes=dict(ordinary=20,mixed=60,barrage=120)
rows=[]
for label,pkg in variants:
    # Run from a private copy: the game writes reports/ and crash files into its cwd,
    # and a release candidate directory must never be modified by a measurement.
    import shutil
    src=Path(pkg).resolve();pkg=out/('pkg-'+label)
    shutil.copytree(src,pkg)
    for rnd in range(3):
        for scene in orders[rnd%3]:
            run=out/f'{label}-r{rnd+1}-{scene}';run.mkdir()
            cfg=dict(scenario=scene,units=sizes[scene],warmup_seconds=5,seconds=30,world_quality='native',display_filter='pixel',optimized=True,detail=False)
            (run/'config.json').write_text(json.dumps(cfg),encoding='utf-8')
            env=dict(os.environ);env['PVP_USERDATA']=str(run/'userdata')
            for k in ('SDL_VIDEODRIVER','SDL_AUDIODRIVER'):env.pop(k,None)
            t0=time.time()
            with open(run/'stdout.txt','wb') as so,open(run/'stderr.txt','wb') as se:
                rc=subprocess.run([str(pkg/'PvZPvPNative.exe'),'--diagnostic',str(run/'config.json')],cwd=str(pkg),env=env,stdout=so,stderr=se,timeout=300).returncode
            text=(run/'stdout.txt').read_text('utf-8',errors='replace')+(run/'stderr.txt').read_text('utf-8',errors='replace')
            report=None
            for line in text.splitlines():
                if 'PVP72_DIAGNOSTIC_COMPLETE' in line:report=Path(line.split('PVP72_DIAGNOSTIC_COMPLETE',1)[1].strip())
            if report and report.exists():
                import shutil;shutil.copy2(report,run/'report.json')
            typed='[typed72] battle session started' in text
            rows.append(dict(variant=label,round=rnd+1,scene=scene,exit=rc,seconds=round(time.time()-t0,1),report=(run/'report.json').exists(),typed_session=typed))
            print(json.dumps(rows[-1]),flush=True)
(out/'runs.json').write_text(json.dumps(rows,indent=1),encoding='utf-8')
