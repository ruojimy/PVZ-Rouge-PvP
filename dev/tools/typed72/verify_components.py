"""Run current component oracles in both optimized and sanitized binaries.

Two subprocesses at most; compilation is a separate serial prerequisite.
This does not run the old full game suite or claim product acceptance.
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


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--release',required=True);ap.add_argument('--asan',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    modules=[('stages','verify_stages.py','typed72_probe.exe'),('heroes','verify_heroes.py','hero72_probe.exe'),
        ('protection','verify_protection.py','protection72_probe.exe'),('targets','verify_targets.py','targets72_probe.exe'),
        ('patch','verify_patch.py','patch72_probe.exe'),('spawn','verify_spawn.py','spawn72_probe.exe'),
        ('entities','verify_entities.py','entity72_probe.exe'),('projectiles','verify_projectiles.py','projectiles72_probe.exe'),
        ('plants','verify_plants.py','plants72_probe.exe'),('doom','verify_doom.py','doom72_probe.exe'),('chili','verify_chili.py','chili72_probe.exe'),
        ('sourced','verify_sourced.py','sourced72_probe.exe'),('death','verify_death.py','death72_probe.exe'),
        ('registry','verify_registry.py','registry72_probe.exe'),('aim','verify_aim.py','aim72_probe.exe'),
        ('wind','verify_wind.py','wind72_probe.exe'),('lantern','verify_lantern.py','lantern72_probe.exe'),
        ('services','verify_services.py','service72_probe.exe'),('fume','verify_fume.py','fume72_probe.exe'),('squash','verify_squash.py','squash72_probe.exe'),('peas','verify_peas.py','pea72_probe.exe'),('shooting','verify_shooting.py','shooting72_probe.exe')]
    modules.extend([('world_rules','verify_world_rules.py','world_rules72_probe.exe'),
                    ('entity_phase','verify_entity_phase.py','world_rules72_probe.exe'),
                    ('zombie_motion','verify_zombie_motion.py','world_rules72_probe.exe'),
                    ('zombie_actions','verify_zombie_actions.py','world_rules72_probe.exe'),
                    ('hero_physics','verify_hero_physics.py','world_rules72_probe.exe'),
                    ('hero_phase','verify_hero_phase.py','world_rules72_probe.exe'),
                    ('bite_boundaries','verify_zombie_interactions.py','world_rules72_probe.exe'),
                    ('resources','verify_resources.py','resources72_probe.exe'),
                    ('path_tracking','verify_path_tracking.py','resources72_probe.exe'),
                    ('hero_recovery','verify_hero_recovery.py','resources72_probe.exe'),
                    ('economy','verify_economy.py','resources72_probe.exe'),
                    ('seat_paths','verify_seat_paths.py','seat_paths72_probe.exe'),
                    ('grave_clock','verify_grave_clock.py','maintenance72_probe.exe'),
                    ('plant_maintenance','verify_plant_maintenance.py','maintenance72_probe.exe'),
                    ('plant_region','verify_plant_region.py','plant_region72_probe.exe'),
                    ('plant_utilities','verify_plant_utilities.py','plant_utilities72_probe.exe'),
                    ('grave_binding','verify_grave_binding.py','grave_binding72_probe.exe'),
                    ('grave_binding_identity','verify_grave_binding_identity.py','grave_binding72_probe.exe'),
                    ('plant_aim','verify_plant_aim.py','plant_aim72_probe.exe'),
                    ('content_queries','verify_content_queries.py','content_queries72_probe.exe'),
                    ('september_plants','verify_september_plants.py','september_plants72_probe.exe'),
                    ('flying_plants','verify_flying_plants.py','flying_plants72_probe.exe'),
                    ('reed_plants','verify_reed_plants.py','reed_plants72_probe.exe'),
                    ('mortar_plants','verify_mortar_plants.py','mortar_plants72_probe.exe'),
                    ('scarecrow','verify_scarecrow.py','scarecrow72_probe.exe'),
                    ('scripted_spawn','verify_scripted_spawn.py','scripted_spawn72_probe.exe'),
                    ('grenadiers','verify_grenadiers.py','grenadiers72_probe.exe'),
                    ('content_zombies64','verify_content_zombies64.py','content_zombies6472_probe.exe'),
                    ('native_summons','verify_native_summons.py','native_summons72_probe.exe')])
    paths=list((ROOT/'src/sim/typed').glob('*.*'));paths+=[ROOT/'tools/typed72'/m[1] for m in modules]
    pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    def run(config,directory,module):
        name,script,exe=module;key=config+'-'+name;target=out/key
        with (out/(key+'.log')).open('wb') as log:
            process=subprocess.run([sys.executable,str(ROOT/'tools/typed72'/script),'--exe',str(Path(directory).resolve()/exe),'--out',str(target)],
                stdout=log,stderr=subprocess.STDOUT,timeout=600)
        result=json.loads((target/'summary.json').read_text(encoding='utf8'))
        return key,dict(passed=process.returncode==0 and result['passed'] and not result['changed_inputs'],cases=result['cases'],
            passed_cases=result['passed_cases'],steps=result.get('compared_steps',result.get('compared_stage_steps')),
            evidence=str(target/'summary.json'),sha256=sha(target/'summary.json'))
    results={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(run,config,directory,module):(config,module[0]) for config,directory in (('release',a.release),('asan',a.asan)) for module in modules}
        for future in as_completed(pending):
            try:key,result=future.result()
            except Exception as exc:
                config,name=pending[future];key=config+'-'+name;result=dict(passed=False,error=repr(exc))
            results[key]=result;print(key,json.dumps(result),flush=True)
    errors=[]
    for name,unused1,unused2 in modules:
        for k in ('cases','passed_cases','steps'):
            if results['release-'+name].get(k)!=results['asan-'+name].get(k):errors.append(name+' differs between builds: '+k)
    drift=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=all(r['passed'] for r in results.values()) and not drift and not errors,results=results,
        input_drift=drift,errors=errors,full_product_acceptance=False,old_full_suite_executed=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=report['passed'],runs=len(results),full_product_acceptance=False)));return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
