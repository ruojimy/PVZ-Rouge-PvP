"""Freeze the current component union and retained negative-control attempts."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'
def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    combined=RUN/'zombies64-combined';result=read(combined/'summary.json')
    assert result['passed'] and len(result['results'])==102 and not result['input_drift'] and not result['errors']
    for manifest in (combined/'pinned.json',RUN/'zombies64-combined-build-inputs.json'):
        for name,digest in read(manifest).items():assert sha(Path(name))==digest,name
    for item in result['results'].values():
        path=Path(item['evidence']);assert item['passed'] and sha(path)==item['sha256']
        for name,digest in read(path.parent/'pinned.json').items():assert sha(Path(name))==digest,name
    audit_path=RUN/'zombies64-audit/audit.json';audit=read(audit_path);assert audit['passed']
    for name,digest in audit['local_dependencies'].items():assert sha(Path(name))==digest,name
    attempts=[];faults={}
    for name,count in [('grenadiers-negative',12),('content-zombies64-negative',13),('native-summons-negative',9),('scripted-spawn-fractional-negative',15)]:
        path=RUN/name/'summary.json';report=read(path)
        assert report['passed'] and not report['source_drift'] and len(report['results'])==count
        attempts.append(dict(path=str(path),sha256=sha(path),passed=report['passed']))
        for fault in report['results']:
            assert sha(Path(fault['original']))==fault['original_sha256']
            raw=read(Path(fault['evidence']))
            assert raw['process_exit_code']==0 and not raw['changed_inputs']
            faults[fault['name']]=fault
    assert len(faults)==49 and all(fault['caught'] for fault in faults.values())
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),component_runs=102,
        cases_per_build=sum(v['cases'] for k,v in result['results'].items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k,v in result['results'].items() if k.startswith('release-')),
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')},
        verified=['grenadier damage windup, target priority, thrown secret/seat capture, reflection and explosions',
                  'PvP64 conveyor control, red-eye grab/throw and slime split callback ordering',
                  'native content summons with live producer timing and frozen deferred provenance',
                  'fractional summon slot identity, finite admission and exception-safe source scopes',
                  'all 51 component groups in optimized and sanitized builds'],
        negative_attempts=attempts,negative_controls=list(faults.values()),
        dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),verification=result['results'],
        previous_checkpoint=str(RUN/'checkpoint-mortar-spawns/status.json'),
        full_product_acceptance=False,old_full_suite_executed=False,
        pending=['remaining custom plant/zombie controllers and complete sourced/content damage wrappers',
                 'custom art and projectile drawing bindings',
                 'whole typed battle driver, public card admission and cold codecs',
                 'AI/network/spectator/replay and versioned state serialization',
                 'same-rule complete backend comparison and 2366-execution suite',
                 'current Android execution, formal full-battle optimization and PC/APK products'])
    target=RUN/'checkpoint-zombies64-summons';target.mkdir(exist_ok=False)
    text=json.dumps(report,ensure_ascii=False,indent=2);(target/'status.json').write_text(text,encoding='utf8')
    (ROOT/'docs/coverage/typed72-zombies64-summons.json').write_text(text,encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=102,cases_per_build=report['cases_per_build'],
        checkpoints_per_build=report['checkpoints_per_build'],negative_faults=49,full_product_acceptance=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
