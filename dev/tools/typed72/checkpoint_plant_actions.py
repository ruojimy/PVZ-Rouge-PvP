"""Pin verified native plant actions and retain the outstanding product boundary."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'test_results/typed72-20261105'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    combined = RUN / 'plant-actions-combined'
    regression = read(combined / 'summary.json')
    negative_path = RUN / 'plant-actions-negative-v2/summary.json'
    negative = read(negative_path)
    audit_path = RUN / 'plant-actions-audit/audit.json'
    audit = read(audit_path)
    assert regression['passed'] and len(regression['results']) == 78
    results = dict(regression['results'])
    for build in ('release', 'asan'):
        evidence = RUN / ('grave-binding-identity-' + build) / 'summary.json'
        edge = read(evidence)
        assert edge['passed'] and not edge['changed_inputs'] and edge['process_exit_code'] == 0
        results[build + '-grave_binding_identity'] = dict(
            passed=True, cases=edge['cases'], passed_cases=edge['passed_cases'], steps=edge['compared_steps'],
            evidence=str(evidence), sha256=sha(evidence))
    assert negative['passed'] and len(negative['results']) == 10 and not negative['source_drift']
    assert audit['passed']
    for file, digest in read(combined / 'pinned.json').items():
        assert sha(Path(file)) == digest, file
    for result in results.values():
        evidence = Path(result['evidence'])
        assert result['passed'] and sha(evidence) == result['sha256']
        for file, digest in read(evidence.parent / 'pinned.json').items():
            assert sha(Path(file)) == digest, file
    for file, digest in audit['local_dependencies'].items():
        assert sha(Path(file)) == digest, file
    for result in negative['results']:
        raw = read(Path(result['evidence']))
        assert result['caught'] and raw['process_exit_code'] == 0 and not raw['changed_inputs']
    report = dict(
        schema=1, created_utc=datetime.now(timezone.utc).isoformat(),
        implementation={str(p): sha(p) for p in (ROOT / 'src/sim/typed').glob('*.*')},
        component_runs=80,
        cases_per_build=sum(v['cases'] for k, v in results.items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k, v in results.items() if k.startswith('release-')),
        source_regions=['installed raw Plants region with PvP patches',
                        'NativeBattle._own_umbrella_pass/_own_umbrella_effects',
                        'SeaShroom.gate/restore/bubbles',
                        'NativeGravebuster attach/validation/cancellation/completion'],
        verified=['43 native plant families and source query helpers',
                  'captured list length, live list index, callback mutation and exceptions',
                  'producer burst, sleep, cannon, lantern and star constructor ordering',
                  'water-grave targeting, strict sea-bubble contact and outer damage dispatch',
                  'duo/cooperative umbrella ownership and scratch-field null restoration',
                  'grave registry identity, narrow completion bridge and exact reward removal',
                  'nested grave scopes, close and cancellation lifecycle'],
        full_product_acceptance=False, old_full_suite_executed=False,
        negative_controls=dict(path=str(negative_path), sha256=sha(negative_path), faults=negative['results']),
        dependency_audit=dict(path=str(audit_path), sha256=sha(audit_path)),
        previous_checkpoint=str(RUN / 'checkpoint-maintenance/status.json'),
        pending=['remaining custom plant and zombie source gates',
                 'pea hybrid aim, taunts, custom projectiles and content dispatch',
                 'whole typed battle driver and card admission',
                 'grave-buster renderer decoration',
                 'queued plant-zombie conversion spawning',
                 'AI/network/spectator/replay',
                 'same-rules complete backend comparison',
                 'full 2366-execution suite', 'current Android execution',
                 'formal full-battle performance and PC/APK products'],
        preserved_attempts=[str(RUN / name) for name in (
            'plant-utilities-release/summary.json', 'grave-binding-release/summary.json',
            'plant-utilities-release-build2.log', 'plant-actions-negative/summary.json')])
    output = RUN / 'checkpoint-plant-actions'
    output.mkdir(exist_ok=False)
    target = ROOT / 'docs/coverage/typed72-plant-actions.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    shutil.copy2(target, output / target.name)
    (output / 'status.json').write_text(json.dumps(
        dict(report=report, verification=results), ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(passed=True, component_runs=80, cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'], negative_faults=10,
                         full_product_acceptance=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
