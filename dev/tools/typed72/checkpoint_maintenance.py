"""Record verified plant-death and grave-clock phases with current integration limits."""
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
    combined=RUN/'maintenance-combined'
    regression=read(combined/'summary.json')
    negative_path=RUN/'maintenance-negative/summary.json'
    negative=read(negative_path)
    audit_path=RUN/'maintenance-audit/audit.json'
    audit=read(audit_path)
    assert regression['passed'] and len(regression['results'])==72
    assert negative['passed'] and len(negative['results'])==9 and not negative['source_drift']
    assert audit['passed']
    for file,digest in read(combined/'pinned.json').items():assert sha(Path(file))==digest,file
    for result in regression['results'].values():
        evidence=Path(result['evidence'])
        assert result['passed'] and sha(evidence)==result['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    for file,digest in audit['local_dependencies'].items():assert sha(Path(file))==digest,file
    for result in negative['results']:
        raw=read(Path(result['evidence']))
        assert result['caught'] and raw['process_exit_code']==0 and not raw['changed_inputs']
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')},
        component_runs=72,
        cases_per_build=sum(value['cases'] for key,value in regression['results'].items() if key.startswith('release-')),
        checkpoints_per_build=sum(value['steps'] for key,value in regression['results'].items() if key.startswith('release-')),
        source_regions=['NativeBattle._step_original grave production loop','GraveIdle.advance/wake/wake_input',
                        'installed PvP plant_maintenance region under the actual plants HeroContext',
                        'SeptemberContent.supplement_death','PlantSecrets66.doom/note_death_sun',
                        'ZombieSecrets.on_plant_killed/pay/_queue_conversion','PvP64Content._mine_x/_mine_y'],
        verified=['native status decrement and production factor order','non-producing graves have no production clock',
                  'deathmatch and last-stand multipliers','scarecrow allegiance and periodic radius',
                  'physical hero contact and open vertical bounds','wake-input validation and event deduplication',
                  'reverse plant-death order and retained aliases','raw doom/cherry/chili/kelp/mine effects and RNG',
                  'primal-mine body circle and nuclear hero cap dispatch','terrain cleanup and supplement emission',
                  'one-time brain payments and conversion queue admission','numeric and boolean monochrome markers',
                  'lifecycle callback replacement and exception unwinding'],
        full_product_acceptance=False,old_full_suite_executed=False,
        negative_controls=dict(path=str(negative_path),sha256=sha(negative_path),faults=negative['results']),
        dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),
        previous_checkpoint=str(RUN/'checkpoint-seat-paths/status.json'),
        pending=['complete native plant action region and source gates','complete zombie/taunt/custom-content gate chains',
                 'whole typed battle driver and card admission','queued plant-zombie conversion spawning',
                 'AI/network/spectator/replay','same-rules complete backend comparison','full 2366-execution suite',
                 'current Android execution','formal full-battle performance and PC/APK products'],
        preserved_attempts=[str(RUN/name) for name in ('maintenance-build.log','maintenance-build-include.log',
            'grave_clock-release.log','plant_maintenance-release.log','plant_maintenance-source-loop/summary.json')])
    output=RUN/'checkpoint-maintenance'
    output.mkdir(exist_ok=False)
    target=ROOT/'docs/coverage/typed72-maintenance.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(target,output/target.name)
    (output/'status.json').write_text(json.dumps(dict(report=report,verification=regression['results']),ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=72,cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'],negative_faults=9,full_product_acceptance=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
