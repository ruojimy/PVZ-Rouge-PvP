"""Require squash differential fixtures to reject separately compiled faults."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
from verify_stages import sha
ROOT=Path(__file__).resolve().parents[3 if Path(__file__).parent.name=='drafts' else 2]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--cmake',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);sources={n:ROOT/'src/sim/typed'/f for n,f in [('squash','squash_effects.cpp'),('ballistics','ballistics.cpp')]}
    text={n:p.read_text(encoding='utf8') for n,p in sources.items()};pinned={str(p):sha(p) for p in sources.values()}
    faults=[
        ('wide_candidate','squash','ahead>scale*2.35','ahead>scale*3.35',1,'squash-candidate-'),
        ('skip_dead_target','squash','if(charmed==friendly||ballistics.body(t).ash.present()','if(ballistics.body(t).dead.present()||charmed==friendly||ballistics.body(t).ash.present()',1,'squash-dead-positive-target-'),
        ('no_fallback','ballistics','if(!solution&&(std::abs(velocity.x)>.001||std::abs(velocity.y)>.001))','if(false)',1,'squash-ballistic-fallback-'),
        ('ignore_lock_identity','ballistics','if(lock.target_id.present()&&!lock.target_id.is_null()&&identity(t)!=lock.target_id.get())return {};','',1,'squash-ballistic-fallback-'),
        ('wrong_lead','ballistics','p.vx*.35,p.vy*.35','p.vx,p.vy',1,'squash-velocity-'),
        ('no_secondary_damage','squash','try{callbacks_.damage_zombie(index,direction,99999.);return;}catch(const std::exception&){}','',1,'squash-hit-callback-'),
        ('no_player_fallback','squash','g.hp.set(before.get()-10.);','g.hp.set(before.get());',1,'squash-player-fallback-'),
        ('overwrite_knockback','squash','p.vx+=knock*500.*world_.runtime.plk;','p.vx=knock*500.*world_.runtime.plk;',1,'squash-hit-once-'),
        ('no_clear_fallback','squash','p->dead.set(DeathMarker(true));','',1,'squash-hit-callback-'),
        ('unsourced_update','squash','SourcedContext scope(world_,source_ref(u),CombatPhase::zombies);raw_update(u,c);scope.finish();','raw_update(u,c);',1,'squash-update-context-'),
        ('unsourced_spawn','squash','SourcedContext scope(world_,source_ref(u),CombatPhase::zombies,SourcedCall::spawn);const bool result=raw_spawn(u,t,o,c);scope.finish();return result;','return raw_spawn(u,t,o,c);',1,'squash-spawn-callback-'),
        ('unsourced_hit','squash','SourcedContext scope(world_,source_ref(e),CombatPhase::entities);raw_hit(e,r,x);scope.finish();','raw_hit(e,r,x);',1,'squash-player-fallback-'),
        ('early_timeout','squash','age>=hit_time+3.','age>=hit_time',1,'squash-entity-hit-timing-'),
        ('repeat_hit','squash','if(!enemy(e)||truth(q.hit))continue;','if(!enemy(e))continue;',1,'squash-hit-once-'),
        ('unwrapped_splash','squash','py::mod(p.x-cx+width/2.,width)-width/2.','p.x-cx',1,'squash-pvp66-splash-'),
        ('reduced_splash','squash','reach=2.4*world_.runtime.tile','reach=2.0*world_.runtime.tile',1,'squash-pvp66-splash-'),
    ]
    env=dict(os.environ);env['_CL_']='/MP1 /FS';build=out/'build';results=[];mutations=[]
    for name,kind,old,new,count,prefix in faults:
        source=text[kind];assert source.count(old)==count,('mutation anchor',name)
        mutant=out/(name+'.cpp');mutant.write_text(source.replace(old,new),encoding='utf8')
        mutations.append(dict(name=name,original=str(sources[kind]),original_sha256=pinned[str(sources[kind])],mutant=str(mutant),mutant_sha256=sha(mutant),removed=old,inserted=new))
        configure=[a.cmake,'-S',str(ROOT/'src/sim/typed'),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64']
        for k in sources:configure.append('-DPVZ_TYPED_'+k.upper()+'_SOURCE='+str(mutant if k==kind else sources[k]))
        with (out/(name+'-build.log')).open('wb') as log:
            for command in (configure,[a.cmake,'--build',str(build),'--config','Release','--target','squash72_probe','--parallel','1']):subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=300)
        folder=out/name
        with (out/(name+'.log')).open('wb') as log:run=subprocess.run([sys.executable,str(ROOT/'tools/typed72/verify_squash.py'),'--exe',str(build/'Release/squash72_probe.exe'),'--out',str(folder)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
        raw=json.loads((folder/'summary.json').read_text(encoding='utf8'));failures=[r for r in raw['results'] if r['label'].startswith(prefix) and not r['passed'] and r.get('first_difference')]
        caught=run.returncode==1 and raw['process_exit_code']==0 and not raw['passed'] and not raw['changed_inputs'] and bool(failures)
        result=dict(name=name,caught=caught,cases=raw['cases'],failed_cases=raw['cases']-raw['passed_cases'],targeted_failures=failures,evidence=str(folder/'summary.json'));results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='targeted_failures'}),flush=True)
    drift=[str(p) for p in sources.values() if sha(p)!=pinned[str(p)]]
    report=dict(passed=all(r['caught'] for r in results) and not drift,mutations=mutations,results=results,original_source_drift=drift,full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');return 0 if report['passed'] else 1
if __name__=='__main__':sys.exit(main())
