"""Freeze verified native actor phases before extending the world scheduler."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))

def main():
    regression=RUN/'hero-and-mobile-combined';r=read(regression/'summary.json')
    negative=RUN/'native-phase-negative/summary.json';n=read(negative)
    supplement=RUN/'bite-boundaries-negative/summary.json';extra=read(supplement)
    audit=RUN/'native-phases-audit/audit.json';a=read(audit)
    assert r['passed'] and len(r['results'])==56
    assert len(n['results'])==12 and a['passed'] and not n['source_drift']
    assert extra['passed'] and len(extra['results'])==2
    faults={v['name']:v for v in n['results']}
    original_misses={name for name,v in faults.items() if not v['caught']}
    assert original_misses=={v['name'] for v in extra['results']}
    faults.update({v['name']:v for v in extra['results']})
    supplemental={}
    for config in ('release','asan'):
        path=RUN/('bite-boundaries-'+config)/'summary.json';raw=read(path)
        assert raw['passed'] and raw['cases']==192
        for file,digest in read(path.parent/'pinned.json').items():assert sha(Path(file))==digest,file
        supplemental[config]=dict(passed=True,cases=raw['cases'],steps=raw['compared_steps'],evidence=str(path),sha256=sha(path))
    for file,digest in read(regression/'pinned.json').items():assert sha(Path(file))==digest,file
    for v in r['results'].values():
        evidence=Path(v['evidence']);assert v['passed'] and sha(evidence)==v['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for file,digest in a['local_dependencies'].items():assert sha(Path(file))==digest,file
    for v in faults.values():
        raw=read(Path(v['evidence']));assert v['caught'] and not raw['changed_inputs'] and raw['process_exit_code']==0
    groups=[
        ('installed_plant_zombie_shooting',['plant_zombie_shooting.cpp'],'shooting',
         ['PlantZombieShooting.step','PlantZombieShooting.live'],['complete NativeBattle caller']),
        ('native_entity_region_and_owner_passes',['entity_region.cpp','entity_contacts.cpp','entity_phase.cpp','native_tracking.cpp','torch_rules.cpp','plant_lookup.cpp'],'entity_phase',
         ['NativeBattle._step_original entity owner passes','NativeBattle._tracking_index','NativeTargets.target_index','entities.marshal'],
         ['later custom content projectile scheduler','production renderer integration']),
        ('mobile_zombie_motion',['zombie_motion.cpp'],'zombie_motion',
         ['zombies.marshal body after gate through displacement','NativeContent.plant_bite','native_bites.install','NativeContent.bite_damage'],
         ['per-zombie upstream gate installation']),
        ('mobile_zombie_region',['zombie_actions.cpp'],'zombie_actions',
         ['zombies.marshal complete reverse mobile pass','NativeContent.plant_art','NativeContent cart ammunition hooks','pvp56_zombies miner goals'],
         ['per-body gate is observed in this oracle','full grave/barrel suspension phase']),
        ('native_hero_physics',['hero_physics.cpp'],'hero_physics',
         ['NativePhysics.make_state','NativePhysics.step','NativePhysics.advance_hero_effects'],
         ['draw_dave presentation and hurt clock']),
        ('native_hero_seat_loops',['hero_phase.cpp'],'hero_phase',
         ['NativeBattle._step_original physics and ability loops','NativeBattle._float_body','NativeBattle._rally_rise','NativeBattle._jump_cap','balance.hero_hp','balance.balloon_hp'],
         ['room-frame recovery/economy','network input admission','whole match scheduling'])
    ]
    entries=[]
    for name,files,suite,sources,pending in groups:
        entries.append(dict(id=name,implementation=[str(ROOT/'src/sim/typed'/f) for f in files],
            source_regions=sources,verification={k:r['results'][k+'-'+suite] for k in ('release','asan')},
            status='verified_in_stated_phase_scope',pending=pending,full_product_acceptance=False))
    implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')}
    implementation[str(ROOT/'src/core/number_text.h')]=sha(ROOT/'src/core/number_text.h')
    entries.append(dict(id='bite_reentrancy_and_half_health',implementation=[str(ROOT/'src/sim/typed/zombie_motion.cpp')],
        source_regions=['native_bites.install reciprocal context','NativeContent.plant_bite'],verification=supplemental,
        status='verified_in_stated_phase_scope',full_product_acceptance=False))
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),entries=entries,implementation=implementation,
        component_runs=58,cases_per_build=192+sum(v['cases'] for k,v in r['results'].items() if k.startswith('release-')),
        checkpoints_per_build=supplemental['release']['steps']+sum(v['steps'] for k,v in r['results'].items() if k.startswith('release-')),
        source_drift=r['input_drift'],negative_controls=dict(initial_report=str(negative),initial_sha256=sha(negative),
            supplemental_report=str(supplement),supplemental_sha256=sha(supplement),original_coverage_gaps=sorted(original_misses),faults=list(faults.values())),
        dependency_audit=dict(path=str(audit),sha256=sha(audit)),full_product_acceptance=False,old_full_suite_executed=False,
        pending=['whole typed battle driver and all content gates','plant region and maintenance','resources/world scheduler',
                 'AI commands and strategy adapter','network spectator and replay adapters','same-rules complete backend comparison',
                 'full 2366-execution suite without new unexplained failures','new Android execution','formal battle performance','PC and APK products'],
        preserved_failures=[str(RUN/p/'summary.json') for p in ('motion-raw-prefix-admitted','zombie-full-region')])
    out=RUN/'checkpoint-native-phases';out.mkdir(exist_ok=False)
    target=ROOT/'docs/coverage/typed72-native-phases.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(target,out/target.name)
    status=dict(report=report,previous_checkpoint=str(RUN/'checkpoint-pea-chain/status.json'),verification=r['results'],supplemental_verification=supplemental)
    (out/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(runs=58,cases_per_build=report['cases_per_build'],checkpoints_per_build=report['checkpoints_per_build'],negative_faults=12,full_product=False)))
if __name__=='__main__':main()
