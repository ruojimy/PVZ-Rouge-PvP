"""Refresh affected component proofs; reuse only byte-identical pinned inputs.

Every reused executable, oracle, source and raw result is checked again. A
changed shared dependency rejects reuse rather than silently blessing it.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
ROOT=Path(__file__).resolve().parents[2]


def read(p):return json.loads(p.read_text(encoding='utf8'))


def checked(item):
    p=Path(item['evidence']);r=read(p)
    if not item['passed'] or not r['passed'] or r['changed_inputs'] or sha(p)!=item['sha256']:
        raise ValueError('invalid previous proof '+str(p))
    for path,digest in read(p.parent/'pinned.json').items():
        if sha(Path(path))!=digest:raise ValueError('reused proof drift '+path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('previous','release','asan','out'):ap.add_argument('--'+name,required=True)
    ap.add_argument('--component',action='append',required=True)
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    previous=Path(a.previous).resolve()/'summary.json';old=read(previous)
    if not old['passed']:raise ValueError('previous bundle failed')
    fresh=set(a.component);known={k.split('-',1)[1] for k in old['results']}
    if not fresh<=known:raise ValueError('unknown refresh component')
    results={k:v for k,v in old['results'].items() if k.split('-',1)[1] not in fresh}
    for item in results.values():checked(item)
    reused=sorted(results)
    paths=[Path(p) for p in read(previous.parent/'pinned.json')]
    pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    def run(config,directory,name):
        key=config+'-'+name;folder=out/key
        exe='typed72_probe.exe' if name=='stages' else {'heroes':'hero','entities':'entity'}.get(name,name)+'72_probe.exe'
        with (out/(key+'.log')).open('wb') as log:
            process=subprocess.run([sys.executable,str(ROOT/'tools/typed72'/('verify_'+name+'.py')),
                '--exe',str(Path(directory).resolve()/exe),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=600)
        p=folder/'summary.json';r=read(p)
        return key,dict(passed=process.returncode==0 and r['passed'] and not r['changed_inputs'],cases=r['cases'],
            passed_cases=r['passed_cases'],steps=r.get('compared_steps',r.get('compared_stage_steps')),evidence=str(p),sha256=sha(p))
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(run,config,directory,name) for config,directory in (('release',a.release),('asan',a.asan)) for name in sorted(fresh)]
        for f in as_completed(pending):
            key,item=f.result();results[key]=item;print(key,json.dumps(item),flush=True)
    errors=[]
    for item in results.values():
        try:checked(item)
        except Exception as exc:errors.append(str(exc))
    for name in known:
        if any(results['release-'+name][key]!=results['asan-'+name][key] for key in ('cases','passed_cases','steps')):
            errors.append('build difference '+name)
    drift=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=all(r['passed'] for r in results.values()) and not errors and not drift,results=results,input_drift=drift,errors=errors,
        reused_runs=reused,refreshed_components=sorted(fresh),previous=dict(path=str(previous),sha256=sha(previous)),
        full_product_acceptance=False,old_full_suite_executed=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],reused_runs=len(reused),new_runs=len(results)-len(reused),errors=errors)))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
