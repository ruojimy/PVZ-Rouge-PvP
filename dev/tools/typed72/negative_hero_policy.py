"""Deliberately wrong isolated sources must be caught by independent oracles."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True)
    args=ap.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    mutations=[('hero.cpp','if(w.active)copy_combat(w.globals,w.hero(w.active->target).frame);',
                '/* Fault injection: restore the obsolete enclosing hero state. */'),
               ('protection.cpp','amount*=damage_factor(target);',
                'target.state.hurt_tick.set(double(heroes_.tick)); amount*=damage_factor(target);')]
    changes=[]
    for name,old,new in mutations:
        original=ROOT/'src/sim/typed'/name;text=original.read_text(encoding='utf8')
        if text.count(old)!=1:raise ValueError('unexpected mutation site count: '+name)
        path=out/name;path.write_text(text.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(original),original_sha256=sha(original),mutant=str(path),mutant_sha256=sha(path),removed=old,inserted=new))
    build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    commands=[[args.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64',
               '-DPVZ_TYPED_HERO_SOURCE='+str(out/'hero.cpp'),'-DPVZ_TYPED_PROTECTION_SOURCE='+str(out/'protection.cpp')],
              [args.cmake,'--build',str(build),'--config','Release','--target','hero72_probe','protection72_probe','--parallel','1']]
    with (out/'build.log').open('wb') as log:
        for command in commands:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    results=[]
    for name,script,exe,extra in [('hero','verify_heroes.py','hero72_probe.exe',['--filter','nested']),
                                  ('protection','verify_protection.py','protection72_probe.exe',[])]:
        folder=out/name
        with (out/(name+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72'/script),'--exe',str(build/'Release'/exe),'--out',str(folder)]+extra,
                               stdout=log,stderr=subprocess.STDOUT,timeout=240)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'))
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and raw['passed_cases']<raw['cases'] and not raw['changed_inputs']
        results.append(dict(name=name,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],evidence=str(folder/'summary.json')))
    drift=[r['original'] for r in changes if sha(Path(r['original']))!=r['original_sha256']]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],results=results),ensure_ascii=False));return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
