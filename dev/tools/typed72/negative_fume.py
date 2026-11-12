"""Compile wrong fumeshroom timing/damage/visual policies; require actual differences."""
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
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);original=ROOT/'src/sim/typed/fume_effects.cpp'
    source=original.read_text(encoding='utf8');digest=sha(original)
    faults=[('omit_fallback', 'const double hp=body(t).hp-amount;', 'return false;const double hp=body(t).hp-amount;', 1, 'fume-index-fallback-'), ('no_player_fallback', 'g.hp.set(before.get()-1.);', 'g.hp.set(before.get());', 1, 'fume-player-fallback-'), ('skip_dead', 'body(t).ash.present()||body(t).hp<=0.', 'body(t).dead.present()||body(t).ash.present()||body(t).hp<=0.', 2, 'fume-line-'), ('bypass_protection', 'world_.protection.amount({hp,no_hand,p->source,p->protection},amount)', 'amount', 1, 'fume-plant-protection-'), ('single_pulse', 'while(done<pulses&&shoot>=damage_tick+vt*done)', 'if(done<pulses&&shoot>=damage_tick+vt*done)', 1, 'fume-pulse-'), ('late_pulse', 'shoot>=damage_tick+vt*done', 'shoot>damage_tick+vt*done', 1, 'fume-pulse-'), ('no_stun', 'if(friendly&&electric)stun(t,point);', '', 1, 'fume-line-'), ('new_bubbles_culled', 'list.erase(list.begin(),list.end()-600)', 'list.resize(600)', 1, 'fume-bubbles-'), ('bubble_250hz', 'py::round0(dt*60.)', 'py::round0(dt*250.)', 1, 'fume-bubbles-'), ('unsourced_line', 'SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);const auto hits=raw_line(u,p,angle,c);scope.finish();return hits;', 'return raw_line(u,p,angle,c);', 1, 'fume-line-'), ('unsourced_update', 'SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_update(u,c);scope.finish();', 'raw_update(u,c);', 1, 'fume-update-context-'), ('null_angle_uses_previous', 'p.fume_attack_angle.present()?p.fume_attack_angle:p.aim_angle', 'p.fume_attack_angle.present()&&!p.fume_attack_angle.is_null()?p.fume_attack_angle:p.aim_angle', 1, 'fume-angle-presence-'), ('retarget_legacy_view', 'const auto targets=*(legacy_view?view_targets:world_.targets);', 'const auto targets=*world_.targets;', 1, 'fume-legacy-view-chain-')]
    changes=[];results=[];build=out/'build';env=dict(os.environ);env['_CL_']='/MP1 /FS'
    for label,old,new,count,prefix in faults:
        if source.count(old)!=count:raise ValueError('mutation anchor '+label)
        mutant=out/(label+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        changes.append(dict(original=str(original),original_sha256=digest,mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        commands=[[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64','-DPVZ_TYPED_FUME_SOURCE='+str(mutant)],
            [a.cmake,'--build',str(build),'--config','Release','--target','fume72_probe','--parallel','1']]
        with (out/(label+'-build.log')).open('wb') as log:
            for cmd in commands:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        folder=out/label
        with (out/(label+'.log')).open('wb') as log:
            run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_fume.py'),'--exe',str(build/'Release/fume72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));targeted=[r for r in raw['results'] if r['label'].startswith(prefix)]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and any(not r['passed'] and r.get('first_difference') for r in targeted)
        result=dict(name=label,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=[r for r in targeted if not r['passed']],evidence=str(folder/'summary.json'))
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(original)] if sha(original)!=digest else []
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=changes,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
