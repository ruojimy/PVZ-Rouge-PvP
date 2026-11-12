"""Record frozen flying/reed controller evidence before the next implementation changes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'


def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    combined=RUN/'flying-reeds-combined'
    result=read(combined/'summary.json')
    assert result['passed'] and len(result['results'])==90
    assert not result['input_drift'] and not result['errors']
    for file,digest in read(combined/'pinned.json').items():assert sha(Path(file))==digest,file
    for item in result['results'].values():
        evidence=Path(item['evidence'])
        assert item['passed'] and sha(evidence)==item['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    audit_path=RUN/'flying-reeds-audit/audit.json'
    audit=read(audit_path)
    assert audit['passed']
    for file,digest in audit['local_dependencies'].items():assert sha(Path(file))==digest,file
    negatives=[]
    for name,count in [('flying-plants-negative',10),('reed-plants-negative',10)]:
        path=RUN/name/'summary.json';data=read(path)
        assert data['passed'] and not data['source_drift'] and len(data['results'])==count
        for fault in data['results']:
            assert fault['caught'] and sha(Path(fault['original']))==fault['original_sha256']
            raw=read(Path(fault['evidence']))
            assert raw['process_exit_code']==0 and not raw['changed_inputs']
        negatives.append(dict(path=str(path),sha256=sha(path),faults=data['results']))
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),
        component_runs=90,
        cases_per_build=sum(v['cases'] for k,v in result['results'].items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k,v in result['results'].items() if k.startswith('release-')),
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')},
        verified=['turnip periodic ray search and manually tagged piercing projectiles',
                  'asparagus sweep/rest clocks, hidden projectile rosters and current live-roster restoration',
                  'flying wall clipping, extended-head contacts, owner changes and wind wrapper',
                  'lightning-reed target ties, six-target chains and electrotherapy direct stun',
                  'overload-reed direct/contact packet order and callback aliasing',
                  'all prior component groups in Release and ASAN'],
        source_regions=['FlyingPlants configure/plant_tick/fire/before_tick/projectiles and wind wrapper',
                        'PvP61Content reed target/strike/lightning/overload/add_bolt'],
        negative_controls=negatives,
        dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),
        verification=result['results'],
        previous_checkpoint=str(RUN/'checkpoint-content-scheduler/status.json'),
        full_product_acceptance=False,old_full_suite_executed=False,
        pending=['remaining custom plant/zombie gates and custom projectile controllers',
                 'whole typed battle driver, card admission and serialization/render bindings',
                 'AI/network/spectator/replay','same-rule full backend comparison',
                 'full 2366-execution suite','current Android execution',
                 'formal full-battle optimization and PC/APK products'])
    target=RUN/'checkpoint-flying-reeds';target.mkdir(exist_ok=False)
    text=json.dumps(report,ensure_ascii=False,indent=2)
    (target/'status.json').write_text(text,encoding='utf8')
    (ROOT/'docs/coverage/typed72-flying-reeds.json').write_text(text,encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=90,cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'],negative_faults=20,
                         full_product_acceptance=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
