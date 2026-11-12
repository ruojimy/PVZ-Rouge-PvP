"""Compile wrong healing/interception/timing policies; require actual differences."""
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
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);original=ROOT/'src/sim/typed/lantern_effects.cpp'
    source=original.read_text(encoding='utf8');digest=sha(original)
    faults=[('heal_hero', 'if(proxy)world_.heroes.write_proxy_hp(target.hero,healed);else body.hp=healed;', 'body.hp=healed;', 1, 'lantern-hero-no-heal-'), ('null_max_fallback', 'specific.present()?specific:observed', 'specific.present()&&!specific.is_null()?specific:observed', 1, 'lantern-health-'), ('skip_dead', 'if(body.ash.present()||body.hp<=0.)', 'if(body.dead.present()||body.ash.present()||body.hp<=0.)', 1, 'lantern-health-'), ('no_visual_rng', 'rt.rng.randint(-18,18)', '0', 1, 'lantern-callback-'), ('repeat_native_pulse', 'if(active<125||yes(p->lantern_charm_healed))continue;', 'if(active<125)continue;', 1, 'lantern-native-pulse-'), ('unsourced', 'SourcedContext scope(world_,source_ref(source),CombatPhase::zombies);raw_update(source,config);scope.finish();', 'raw_update(source,config);', 1, 'lantern-update-')]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,old,new,count,prefix in faults:
        if source.count(old)!=count:raise ValueError('mutation anchor '+label)
        mutant=out/(label+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(original),original_sha256=digest,mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64','-DPVZ_TYPED_LANTERN_SOURCE='+str(mutant)],
            [a.cmake,'--build',str(build),'--config','Release','--target','lantern72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for cmd in commands:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_lantern.py'),'--exe',str(build/'Release/lantern72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));targeted=[r for r in raw['results'] if r['label'].startswith(prefix)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(original)] if sha(original)!=digest else []
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
