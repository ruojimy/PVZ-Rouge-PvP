"""Same-input, fresh-process production targeting A/B; never uses player saves."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def differences(a,b,path=''):
    if type(a)!=type(b):return [(path,a,b)]
    if isinstance(a,dict):
        out=[]
        for k in sorted(set(a)|set(b)):
            out.extend(differences(a.get(k),b.get(k),path+'/'+str(k)))
            if len(out)>=12:break
        return out[:12]
    if isinstance(a,list):
        if len(a)!=len(b):return [(path+'/length',len(a),len(b))]
        out=[]
        for i,(x,y) in enumerate(zip(a,b)):
            out.extend(differences(x,y,path+'/'+str(i)))
            if len(out)>=12:break
        return out[:12]
    return [] if a==b else [(path,a,b)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--quick',action='store_true');p.add_argument('--ticks',type=int,default=60)
    args=p.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    exe=ROOT/'build/app-typed72-v2/Release/pvp742_targeting_bench.exe'
    jobs=[('idle',100),('idle',1000),('asparagus',200),('grabber',120),('grabber',500),('mixed',100),('mixed',1000),('dense',500),('sizes',500),('moving',200),('churn',200),('turnip',100),('reed',200)]
    if args.quick:jobs=[('idle',100),('mixed',100),('grabber',120),('moving',100)]
    results=[];passed=True
    for scene,n in jobs:
        pair=[]
        for enabled in (False,True):
            name='%s-%s-%s'%(scene,n,'current' if enabled else 'reference');d=out/name;d.mkdir()
            env=dict(os.environ,PVP742_TARGETING='1' if enabled else '0',PVP741_PROFILE='1',SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(d/'userdata'))
            start=time.time()
            with (d/'stdout.log').open('wb') as stdout,(d/'stderr.log').open('wb') as stderr:
                r=subprocess.run([str(exe),scene,str(n),str(args.ticks),str(d/'report.json')],cwd=str(ROOT),env=env,stdout=stdout,stderr=stderr,timeout=900,creationflags=0x08000000)
            if r.returncode:
                raise RuntimeError(name+' failed: '+(d/'stderr.log').read_text('utf8',errors='replace')[-2500:])
            j=json.loads((d/'report.json').read_text('utf8'));assert j['passed'],name
            pair.append(j)
            print(name,round(time.time()-start,2),'seconds',j['step_ms'],flush=True)
        diff={k:differences(pair[0][k],pair[1][k]) for k in ('final_state','final_rng','final_native')}
        equal=not any(diff.values());passed=passed and equal
        row={'scene':scene,'units':n,'equal_state_rng_native':equal,'differences':diff,'reference':{},'current':{}}
        for key,j in zip(('reference','current'),pair):
            row[key]={k:j[k] for k in ('live_units_final','peak_entities','memory_before','memory_after','step_ms','counter_deltas')}
            row[key]['functions']=j['counters']['function_profile']
        results.append(row)
        (out/'summary.json').write_text(json.dumps({'passed':passed,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'room_steps':args.ticks,'runs':results},ensure_ascii=False,indent=2),encoding='utf8')
        if not equal:raise AssertionError(scene+' deterministic mismatch: '+json.dumps(diff,ensure_ascii=False)[:2500])
    return 0

if __name__=='__main__':raise SystemExit(main())
