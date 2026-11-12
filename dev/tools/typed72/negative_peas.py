"""Compile independent pea-chain faults and require targeted divergences."""
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
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True);ap.add_argument('--only');a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    sources={'pea':ROOT/'src/sim/typed/zombie_pea.cpp','patch':ROOT/'src/sim/typed/damage_patch.cpp'}
    text={n:p.read_text(encoding='utf8') for n,p in sources.items()};pinned={str(p):sha(p) for p in sources.values()}
    faults=[
        ('endpoint_only','pea','return segment_hits_ellipse(a,b,{c,radii.x,radii.y});','return segment_hits_ellipse(b,b,{c,radii.x,radii.y});',1,'pea-segment-'),
        ('no_blue_multiplier','pea','fire=="blue"?3.','fire=="blue"?2.',1,'pea-torch-'),
        ('no_torch','pea','void ZombiePeas::torch_check(const EntityRef& e) {','void ZombiePeas::torch_check(const EntityRef& e) {return;',1,'pea-torch-'),
        ('torch_takes_splash','pea','||p->kind=="火炬树桩"||!in_range','||!in_range',1,'pea-splash-'),
        ('spike_damage','pea','if(p->kind=="地刺"||p->kind=="地刺王")','if(false)',1,'pea-plant-hit-'),
        ('no_protection','pea','world_.protection.amount({hp,no_hand,p->source,p->protection},amount)','amount',1,'pea-plant-hit-'),
        ('surface_exception_fallback','pea','std::optional<bool> result=false;','std::optional<bool> result;',1,'pea-charmed-damage-'),
        ('ignore_tracking','pea','amount>5.&&!e->tracking.present()','amount>5.',1,'pea-charmed-damage-'),
        ('missing_nested_entry','patch','if(result==SurfaceDamageResult::armorless)nested_ordinary(unit,facing,amount);','if(result==SurfaceDamageResult::armorless)dispatch().ordinary(CombatTarget::zombie(unit),facing,amount);',1,'pea-nested-index-'),
        ('no_player_fallback','pea','g.hp.set(before.get()-1.);','g.hp.set(before.get());',1,'pea-player-'),
        ('source_self_hit','pea','e->native_source_zombie.get()==identity(t)','false',1,'pea-charmed-hit-'),
        ('splash_direct_repeat','pea','p==direct_plant||!live(p)','!live(p)',1,'pea-splash-'),
        ('inclusive_vertical_splash','pea','top<p.y&&p.y<bottom','top<=p.y&&p.y<=bottom',1,'pea-splash-boundary-'),
        ('double_native_move','pea','if(!truth(pea.native_move)){','if(true){',1,'pea-movement-age-'),
        ('early_expiration','pea','pea.age.get()>4000.','pea.age.get()>=4000.',1,'pea-movement-age-'),
        ('replace_wrong_entity_list','pea','if(changed){*entities=std::move(kept);','if(changed){*world_.runtime.entities.list()=std::move(kept);',1,'pea-list-identity-'),
        ('omit_legacy_list','pea','if(world_.zombie_peas.legacy->empty())return;','return;if(world_.zombie_peas.legacy->empty())return;',1,'pea-list-identity-'),
        ('single_shot_fan','pea','{-30.,-18.,-6.,6.,18.,30.}','{0.}',1,'pea-shotgun-'),
        ('short_volley','pea','world_.heroes.tick-last.get()<200.','world_.heroes.tick-last.get()<100.',1,'pea-shotgun-'),
        ('unsourced_spawn','pea','SourcedContext scope(world_,source?source_ref_for(*source):nullptr,CombatPhase::zombies,SourcedCall::spawn);const bool result=raw_spawn(p,a,friendly,source);scope.finish();return result;','return raw_spawn(p,a,friendly,source);',1,'pea-spawn-'),
        ('unsourced_hit','pea','SourcedContext scope(world_,source_ref(e),CombatPhase::entities);const auto result=raw_hit(e);scope.finish();return result;','return raw_hit(e);',1,'pea-source-context-'),
        ('unsourced_tick','pea','SourcedContext scope(world_,source_ref(e),CombatPhase::entities);const auto result=raw_update_one(e,scale,width,height);scope.finish();return result;','return raw_update_one(e,scale,width,height);',1,'pea-source-context-'),
        ('hero_wrong_seat','pea','e->source.seat=seat;','e->source.seat=Seat::zombie;',1,'pea-hero-'),
        ('unwrapped_hero','pea','wrap_delta(x,p.x,width)','p.x-x',1,'pea-hero-'),
    ]
    if a.only:
        faults=[f for f in faults if f[0]==a.only]
        if not faults:raise ValueError('unknown fault '+a.only)
    env=dict(os.environ);env['_CL_']='/MP1 /FS';build=out/'build';results=[];mutations=[]
    for name,kind,old,new,count,prefix in faults:
        source=text[kind];assert source.count(old)==count,('mutation anchor',name)
        mutant=out/(name+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        mutations.append(dict(name=name,original=str(sources[kind]),original_sha256=pinned[str(sources[kind])],mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        configure=[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64']
        for k in sources:configure.append('-DPVZ_TYPED_'+k.upper()+'_SOURCE='+str(mutant if k==kind else sources[k]))
        with (out/(name+'-build.log')).open('wb') as log:
            for command in (configure,[a.cmake,'--build',str(build),'--config','Release','--target','pea72_probe','--parallel','1']):subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=300)
        folder=out/name
        with (out/(name+'.log')).open('wb') as log:run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_peas.py'),'--exe',str(build/'Release/pea72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));failures=[r for r in raw['results'] if r['label'].startswith(prefix) and not r['passed'] and r.get('first_difference')]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and bool(failures)
        result=dict(name=name,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=failures,evidence=str(folder/'summary.json'));results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(p) for p in sources.values() if sha(p)!=pinned[str(p)]]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=mutations,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())
