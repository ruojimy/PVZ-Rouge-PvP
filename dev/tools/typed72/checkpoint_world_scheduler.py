"""Record the exact verified world/resource/recovery implementation and remaining integration."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'

def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    regression=RUN/'world-scheduler-combined';r=read(regression/'summary.json')
    negative=RUN/'world-scheduler-negative/summary.json';n=read(negative)
    audit=RUN/'world-scheduler-audit/audit.json';a=read(audit)
    core=RUN/'native-number-core/summary.json';c=read(core)
    assert r['passed'] and len(r['results'])==66
    assert n['passed'] and len(n['results'])==25 and not n['source_drift']
    assert a['passed']
    assert c['passed'] and not c['source_drift'] and c['checks_actual_py_str']==8
    for file,digest in c['pinned'].items():assert sha(Path(file))==digest,file
    for file,digest in read(regression/'pinned.json').items():assert sha(Path(file))==digest,file
    for v in r['results'].values():
        evidence=Path(v['evidence']);assert v['passed'] and sha(evidence)==v['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for file,digest in a['local_dependencies'].items():assert sha(Path(file))==digest,file
    for v in n['results']:
        raw=read(Path(v['evidence']))
        assert v['caught'] and not raw['changed_inputs'] and raw['process_exit_code']==0
    groups=[
        ('native_world_resources',['world_regions.cpp','resources.cpp'],'resources',
         ['water_animation','important_blocks','water_ice_clock','sun_motion','NativeBattle resource/merge/collect'],
         ['full battle phase ordering','resource admission from network/save']),
        ('native_path_tracking',['path_tracking.cpp'],'path_tracking',
         ['NativePhysics.initialize_tracking','NativePhysics.update_tracking','native_flood.advance'],
         ['per-seat field banks','rally field selection','full zombie gate chain']),
        ('native_room_hero_recovery',['hero_recovery.cpp'],'hero_recovery',
         ['NativeBattle._deathmatch_water','NativeBattle._masochist','NativeBattle._sturdy','NativeBattle._recover_heroes'],
         ['room-step integration','team revival']),
        ('native_room_economy',['economy.cpp'],'economy',
         ['NativeBattle._economy','NativeBattle._sun_owner','ZombieSecrets.day_income_count','PlantSecrets66.death_sun_amount',
          'NativeBattle native producer clock','balance.rest_factor'],
         ['resolved catalog admission','full native plant burst and supplement emission','grave tick production progress']),
        ('independent_public_and_observed_hp',['zombie_motion.cpp','targets.h'],'bite_boundaries',
         ['NativeContent.plant_bite','_pvp_max_hp distinct from __pvz_sb_zombie_observed_max_hp'],
         ['complete unit registration'])]
    entries=[]
    for name,files,suite,sources,pending in groups:
        entries.append(dict(id=name,implementation=[str(ROOT/'src/sim/typed'/f) for f in files],source_regions=sources,
            verification={k:r['results'][k+'-'+suite] for k in ('release','asan')},
            status='verified_in_stated_phase_scope',pending=pending,full_product_acceptance=False))
    implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')}
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),entries=entries,implementation=implementation,
        component_runs=len(r['results']),cases_per_build=sum(v['cases'] for k,v in r['results'].items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k,v in r['results'].items() if k.startswith('release-')),
        source_drift=r['input_drift'],negative_controls=dict(path=str(negative),sha256=sha(negative),faults=n['results']),
        dependency_audit=dict(path=str(audit),sha256=sha(audit)),
        legacy_number_format_regression=dict(path=str(core),sha256=sha(core)),
        full_product_acceptance=False,old_full_suite_executed=False,
        pending=['complete typed battle driver and all content gates','native plant region/maintenance','per-seat and rally path ownership',
                 'card admission and command validation','AI/network/spectator/replay','same-rules complete backend comparison',
                 'full 2366-execution suite','current Android execution','formal battle performance','PC/APK products'],
        preserved_attempts=[str(RUN/p) for p in ('world-resources-release/summary.json','world-resources-bound-reference/summary.json',
            'path-tracking-release.log','path-tracking-pinned-reference/summary.json','economy-release/interrupted.json','economy-bounded-clocks/summary.json')])
    out=RUN/'checkpoint-world-scheduler';out.mkdir(exist_ok=False)
    target=ROOT/'docs/coverage/typed72-world-scheduler.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(target,out/target.name)
    status=dict(report=report,previous_checkpoint=str(RUN/'checkpoint-native-phases/status.json'),verification=r['results'])
    (out/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=report['component_runs'],cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'],negative_faults=len(n['results']),full_product_acceptance=False)))
    return 0

if __name__=='__main__':raise SystemExit(main())
