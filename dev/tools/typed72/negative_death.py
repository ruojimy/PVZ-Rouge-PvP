"""Independent compiled faults in the concrete sourced death chain."""
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
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    paths={k:ROOT/'src/sim/typed'/n for k,n in dict(DEATH='death_chain.cpp',PATCH='damage_patch.cpp',SOURCED='sourced_context.cpp').items()}
    sources={k:p.read_text(encoding='utf8') for k,p in paths.items()};digests={k:sha(p) for k,p in paths.items()}
    faults=[('doom_age_frequency','DEATH',[('age+=elapsed*60.','age+=elapsed*250.')],('death-auto-timer-',)),
        ('owner_launch','DEATH',[('chili.enemy_scan(e,box,scale);player_hit(e,box,scale);','chili.enemy_scan(e,box,scale);')],('death-owner-launch-',)),
        ('numeric_selector_capture','DEATH',[('bool triggered=false;','const auto captured=resolve(target);bool triggered=false;'),
            ('patch.trigger_doom(resolve(target))','patch.trigger_doom(captured)'),('patch.trigger_grave(resolve(target))','patch.trigger_grave(captured)')],('death-live-selector-',)),
        ('raw_ash_target_argument','PATCH',[('effects_.plant_zombie_deaths(index);','effects_.plant_zombie_deaths(unit);')],('death-raw-ash-current-index-',)),
        ('eager_launch_identity','SOURCED',[('auto fallback=AttackIdentity::native(heroes.source_id(source_),heroes.tick);',
            'auto fallback=AttackIdentity::native(source_->instant_attack?std::string("unused"):heroes.source_id(source_),heroes.tick);')],('death-owner-launch-',)),
        ('fast_hint_sync_order','DEATH',[('if(sourced_fastpath){context_effects(source);return chili.row_hint(t,force);}',
            'if(sourced_fastpath){auto result=chili.row_hint(t,force);context_effects(source);return result;}')],('death-fast-context-',))]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,key,edits,prefixes in faults:
        source=sources[key]
        for old,new in edits:
            if source.count(old)!=1:raise ValueError('mutation anchor count '+label)
            source=source.replace(old,new)
        mutant=out/(label+'.cpp');mutant.write_text(source,encoding='utf8')
        changes.append(dict(original=str(paths[key]),original_sha256=digests[key],mutant=str(mutant),mutant_sha256=sha(mutant),edits=[dict(removed=o,inserted=n) for o,n in edits]))
        options=['-DPVZ_TYPED_'+k+'_SOURCE='+str(mutant if k==key else p) for k,p in paths.items()]
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64']+options,
            [a.cmake,'--build',str(build),'--config','Release','--target','death72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for cmd in commands:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_death.py'),'--exe',str(build/'Release/death72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));targeted=[r for r in raw['results'] if any(r['label'].startswith(p) for p in prefixes)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(p) for k,p in paths.items() if sha(p)!=digests[k]];report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
