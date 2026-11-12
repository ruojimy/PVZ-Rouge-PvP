"""Freeze verified seat/rally path ownership with the remaining product work."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'test_results/typed72-20261105'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    combined=RUN/'seat-paths-combined'
    regression=read(combined/'summary.json')
    negative_path=RUN/'seat-paths-negative-retained/summary.json'
    negative=read(negative_path)
    audit_path=RUN/'seat-paths-audit/audit.json'
    audit=read(audit_path)
    equivalence_path=RUN/'seat-path-fixture-equivalence.json'
    equivalence=read(equivalence_path)
    assert regression['passed'] and len(regression['results'])==68
    assert negative['passed'] and len(negative['results'])==7 and not negative['source_drift']
    assert audit['passed'] and equivalence['passed']
    for file,digest in read(combined/'pinned.json').items():
        assert sha(Path(file))==digest,file
    for result in regression['results'].values():
        evidence=Path(result['evidence'])
        assert result['passed'] and sha(evidence)==result['sha256']
        for file,digest in read(evidence.parent/'pinned.json').items():
            assert sha(Path(file))==digest,file
    for file,digest in audit['local_dependencies'].items():
        assert sha(Path(file))==digest,file
    for result in negative['results']:
        evidence=read(Path(result['evidence']))
        assert result['caught'] and evidence['process_exit_code']==0 and not evidence['changed_inputs']
    report=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),
        implementation={str(p):sha(p) for p in (ROOT/'src/sim/typed').glob('*.*')},
        component_runs=68,
        cases_per_build=sum(v['cases'] for k,v in regression['results'].items() if k.startswith('release-')),
        checkpoints_per_build=sum(v['steps'] for k,v in regression['results'].items() if k.startswith('release-')),
        source_regions=['NativePhysics.initialize_tracking','NativePhysics.update_tracking','native_flood.advance',
                        'NativeBattle._team_tracking','NativeBattle._switch_tracking','NativeBattle._update_rally_tracking',
                        'NativeBattle._restore_rally_tracking','NativeBattle.rally_destination','NativeBattle.rally_tracking_for',
                        'NativeBattle._rally_zombie_gate path selection before the required downstream unit gate'],
        verified=['seat order and public-HP selection','persistent player and plant flood fields',
                  'ordinary field aliasing and independent rally construction','scalar commit on seat changes',
                  'original phase-exit restore without an extra final commit','queue replacement and retained aliases',
                  'mixed per-seat commands and charmed-unit exclusion','goal changes and terrain-revision cache invalidation',
                  'periodic seams, out-of-map hero positions, fully solid published terrain and revival'],
        full_product_acceptance=False,old_full_suite_executed=False,
        negative_controls=dict(path=str(negative_path),sha256=sha(negative_path),faults=negative['results']),
        dependency_audit=dict(path=str(audit_path),sha256=sha(audit_path)),
        fixture_equivalence=dict(path=str(equivalence_path),sha256=sha(equivalence_path)),
        previous_checkpoint=str(RUN/'checkpoint-world-scheduler/status.json'),
        pending=['complete zombie gate, taunt and custom-content scheduling','plant maintenance and complete plant region',
                 'complete battle driver and card admission','AI/network/spectator/replay',
                 'same-rules complete backend comparison','full 2366-execution suite','Android execution',
                 'formal complete-battle performance and PC/APK products'],
        preserved_attempts=[str(RUN/p) for p in ('seat-path-build.log','seat-paths-asan/timeout.json',
            'seat-paths-negative/interrupted.json','seat-paths-negative-complete/summary.json',
            'seat-paths-release/summary.json','seat-paths-boundaries/summary.json')])
    out=RUN/'checkpoint-seat-paths'
    out.mkdir(exist_ok=False)
    target=ROOT/'docs/coverage/typed72-seat-paths.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(target,out/target.name)
    status=dict(report=report,verification=regression['results'])
    (out/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,component_runs=68,cases_per_build=report['cases_per_build'],
                         checkpoints_per_build=report['checkpoints_per_build'],negative_faults=7,full_product_acceptance=False)))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
