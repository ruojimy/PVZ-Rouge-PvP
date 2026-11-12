"""Four independently built projectile faults; preserve raw failing evidence."""
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
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    original=ROOT/'src/sim/typed/projectile_rules.cpp';source=original.read_text(encoding='utf8');digest=sha(original)
    faults=[('range_boundary','return distance>world_.runtime.tile','return distance>=world_.runtime.tile',('flight-range-',)),
        ('append_iteration','for(size_t i=0;i<incoming->size();++i)','for(size_t i=0,end=incoming->size();i<end&&i<incoming->size();++i)',('cull-live-list-',)),
        ('splash_cleanup','~SplashGuard(){source.melon_splash.erase();}','~SplashGuard(){}',('splash-source-34',)),
        ('event_order','events.push_back(BasketballHitEvent{','events.insert(events.begin(),BasketballHitEvent{',('cross-system-event-order-',))]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,old,new,prefixes in faults:
        if source.count(old)!=1:raise ValueError('mutation anchor count '+label)
        mutant=out/(label+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(original),original_sha256=digest,mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64','-DPVZ_TYPED_PROJECTILE_RULES_SOURCE='+str(mutant)],
            [a.cmake,'--build',str(build),'--config','Release','--target','projectiles72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for command in commands:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_projectiles.py'),'--exe',str(build/'Release/projectiles72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=240)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'))
        targeted=[r for r in raw['results'] if any(r['label'].startswith(p) for p in prefixes)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[] if sha(original)==digest else [str(original)]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
