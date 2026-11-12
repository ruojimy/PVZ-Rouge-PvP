"""Inject two specific wrong implementations, preserving normal source files."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_stages import sha
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True)
    args=ap.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    mutations=[('targets.cpp','if(has_packet(target))return callback==Callback::ordinary?',
        'if(false&&has_packet(target))return callback==Callback::ordinary?'),
        ('damage_patch.cpp','u.patch.chili_exploded.set(true);effects_.chili_row_hint(unit,true);',
        'effects_.chili_row_hint(unit,true);u.patch.chili_exploded.set(true);')]
    changes=[]
    for name,old,new in mutations:
        original=ROOT/'src/sim/typed'/name;text=original.read_text(encoding='utf8')
        if text.count(old)!=1:raise ValueError('unexpected mutation site count: '+name)
        path=out/name;path.write_text(text.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(original),original_sha256=sha(original),mutant=str(path),mutant_sha256=sha(path),removed=old,inserted=new))
    build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    commands=[[args.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64',
        '-DPVZ_TYPED_TARGETS_SOURCE='+str(out/'targets.cpp'),'-DPVZ_TYPED_PATCH_SOURCE='+str(out/'damage_patch.cpp')],
        [args.cmake,'--build',str(build),'--config','Release','--target','targets72_probe','patch72_probe','--parallel','1']]
    with (out/'build.log').open('wb') as log:
        for command in commands:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    results=[]
    for name,script,exe,labels in [('target_packets','verify_targets.py','targets72_probe.exe',('damage-packets-',)),
        ('death_marker','verify_patch.py','patch72_probe.exe',('death-exception-辣椒僵尸-hint',))]:
        folder=out/name
        with (out/(name+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72'/script),'--exe',str(build/'Release'/exe),'--out',str(folder)],
                stdout=log,stderr=subprocess.STDOUT,timeout=240)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'))
        targeted=[r for r in raw['results'] if any(r['label'].startswith(label) for label in labels)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and any(not r['passed'] and r.get('first_difference') for r in targeted) and not raw['changed_inputs']
        results.append(dict(name=name,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],
            targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json')))
    drift=[r['original'] for r in changes if sha(Path(r['original']))!=r['original_sha256']]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],results=[{k:v for k,v in r.items() if k!='targeted_failures'} for r in results]),ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
