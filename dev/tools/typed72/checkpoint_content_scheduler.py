"""Record frozen content scheduler evidence before the next implementation changes."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'


def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    combined=RUN/'content-scheduler-combined'
    result=read(combined/'summary.json')
    assert result['passed'] and len(result['results'])==86
    assert not result['input_drift'] and not result['errors']
    for file,digest in read(combined/'pinned.json').items():assert sha(Path(file))==digest,file
    for item in result['results'].values():
        evidence=Path(item['evidence'])
        assert item['passed'] and sha(evidence)==item['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():assert sha(Path(file))==digest,file
    audit_path=RUN/'content-scheduler-audit/audit.json'
    audit=read(audit_path)
    assert audit['passed']
    for file,digest in audit['local_dependencies'].items():assert sha(Path(file))==digest,file
    negatives=[]
    for name,count in [('content-aim-negative-v2',12),('september-plants-negative',7)]:
        path=RUN/name/'summary.json';data=read(path)
        assert data['passed'] and not data['source_drift'] and len(data['results'])==count
        for fault in data['results']:
            assert fault['caught'] and sha(Path(fault['original']))==fault['original_sha256']
            raw=read(Path(fault['evidence']))
            assert raw['process_exit_code']==0 and not raw['changed_inputs']
        negatives.append(dict(path=str(path),sha256=sha(path),faults=data['results']))
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),
        component_runs=86,
        cases_per_build=sum(v['cases'] for k,v in result['results'].items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k,v in result['results'].items() if k.startswith('release-')),
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')},
        verified=['periodic tripea selection and native pea hybrid constructor/gate',
                  'content enemy ordering, team hero proxies and route interception',
                  'sweet-potato cache, path-bank identity and per-tick chase baseline restoration',
                  'gold bloom native generation, income clock and one-shot settlement',
                  'ghost pepper activation, aura pulses, extended-head contact and final blast',
                  'full previously implemented component regression in Release and ASAN'],
        source_regions=['NativeExpansion._aim_pea/source_gate and constructor wrapper',
                        'NativeContent.enemies/nearest/route_target plus targeting72.cpp',
                        'PvP64Content sweet-potato taunt lifecycle',
                        'NativeSeptember.configure/inside/attack/plant_tick'],
        negative_controls=negatives,
        dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),
        verification=result['results'],
        previous_checkpoint=str(RUN/'checkpoint-plant-actions/status.json'),
        full_product_acceptance=False,old_full_suite_executed=False,
        pending=['remaining custom plant/zombie gates and custom projectile controllers',
                 'whole typed battle driver, card admission and serialization/render bindings',
                 'AI/network/spectator/replay','same-rule full backend comparison',
                 'full 2366-execution suite','current Android execution',
                 'formal full-battle optimization and PC/APK products'])
    target=RUN/'checkpoint-content-scheduler';target.mkdir(exist_ok=False)
    text=json.dumps(report,ensure_ascii=False,indent=2)
    (target/'status.json').write_text(text,encoding='utf8')
    (ROOT/'docs/coverage/typed72-content-scheduler.json').write_text(text,encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=86,cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'],negative_faults=19,
                         full_product_acceptance=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
