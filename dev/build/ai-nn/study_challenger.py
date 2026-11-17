"""Predeclared trained-network holdout, including when validation prefers r22.

Freeze protocol before main selection. Select each seat's trained challenger using
validation wins only, never test outcomes. This supplements, not replaces, the
main deployment-oriented comparison which may correctly choose r22.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from compare import compare

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text('utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument('--study', type=Path, required=True)
ap.add_argument('--freeze', action='store_true')
args = ap.parse_args()
base = args.study.resolve()
protocol = base / 'challenger-protocol.json'
if args.freeze:
    assert not protocol.exists() and not (base / 'selection.json').exists()
    protocol.write_text(json.dumps(dict(
        script_sha256=sha(Path(__file__)), frozen_before_validation_games_and_test=True,
        rule='For each seat choose compact or wide by validation wins, then fewer lost baseline wins, then compact. '
             'Run that trained challenger on the sealed test even if r22/original/residual wins overall selection. '
             'Reuse an exactly matching main test arm. Score both architectures on held-out teacher states afterwards. '
             'No test-driven model change or production promotion.',
        note='Additional research comparison. All four trained-challenger vs r22/original seat comparisons '
             'join the four selected-policy comparisons in an eight-test Holm family.'), indent=2), 'utf-8')
    print('Challenger rule frozen before model selection.')
    raise SystemExit(0)
assert read(protocol)['script_sha256'] == sha(Path(__file__))
selection = read(base / 'selection.json')
chosen = {}
for seat in ('plant', 'zombie'):
    scores = selection['validation']
    name = max(('compact', 'wide'), key=lambda n: (scores[n][seat]['candidate_wins'],
               -scores[n][seat]['losses'], n=='compact'))
    chosen[seat] = dict(name=name, model=selection['models'][name])
target = base / 'challenger-selection.json'
if target.exists():
    assert read(target)['chosen'] == chosen
else:
    target.write_text(json.dumps(dict(chosen=chosen, protocol_sha256=sha(protocol),
        selection_sha256=sha(base / 'selection.json'), rule_uses_test=False), indent=2), 'utf-8')
assert read(base / 'run.json')['completed']
baseline = read(base / 'test-r22/summary.json')
results = {}
for seat, spec in chosen.items():
    name = spec['name']
    if selection['selected'][seat]['name'] == name:
        folder = base / ('test-selected-' + seat)
    else:
        folder = base / ('test-challenger-' + seat)
        assert not folder.exists(), 'No implicit cache reuse'
        model = Path(spec['model']['path'])
        assert sha(model) == spec['model']['sha256']
        cmd = [sys.executable, '-X', 'utf8', str(HERE/'eval.py'), '--bin', str(HERE/'windows-20261116/Release/headless_match.exe'),
            '--corpus', str(base/'corpus-plain'), '--out-dir', str(folder), '--ids', ','.join(baseline['ids']),
            '--jobs', '4', '--limit-seconds', '600', '--planner', 'nn', '--', '--model', str(model),
            '--nn-seat', seat, '--no-records']
        with (base / ('challenger-' + seat + '.log')).open('wb') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
    candidate = read(folder / 'summary.json')
    original = read(base / ('test-original-' + seat) / 'summary.json')
    results[seat] = dict(name=name, summary_path=str(folder/'summary.json'),
                        vs_r22=compare(baseline, candidate, seat), vs_original=compare(original, candidate, seat))
(base/'challenger-strength.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps({s:dict(model=r['name'],wins=r['vs_r22']['candidate_wins'],base=r['vs_r22']['baseline_wins'],
                        paired_p=r['vs_r22']['paired_exact_p']) for s,r in results.items()}))
