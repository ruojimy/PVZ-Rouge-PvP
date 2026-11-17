"""Read-only checks of current source identity and fresh corpus provenance."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument('--study', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
if args.out.exists():
    raise SystemExit('Audit output already exists')
stage = ROOT / 'build/typed72-integrated-v44/source/src/sim/typed'
app = ROOT / 'src/sim/typed72_app'
inputs = set(stage.glob('*.cpp')) | set(stage.glob('*.h'))
for pattern in ('*.cpp', '*.h', '*.inc'):
    inputs.update((app / 'composition').rglob(pattern))
for pattern in ('*.cpp', '*.h'):
    inputs.update((app / 'ai').rglob(pattern))
inputs.update(app / name for name in ('session.cpp', 'session.h', 'ai_planner_r22.cpp', 'ai_planner_r22.h'))
records = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
text = ''.join(f'{key}:{records[key]}\n' for key in sorted(records))
fingerprint = hashlib.sha256(text.encode()).hexdigest()
compiled = re.search(r'"([a-f0-9]{64})"', (ROOT / 'build/ai-nn/windows-20261116/ai_nn_build.h').read_text())[1]
assert fingerprint == compiled, (fingerprint, compiled)
plan = json.loads((args.study / 'plan.json').read_text('utf-8'))
index = json.loads((args.study / 'corpus-plain/index.json').read_text('utf-8'))
old = json.loads((ROOT / 'build/ai-nn/corpus-pvp743-r2-plain/index.json').read_text('utf-8'))
old_keys = {(r['map'], r['night'], r['seed']) for r in old['entries']}
checked = {}
for row, entry in zip(plan['entries'], index['entries']):
    assert all(row[k] == entry[k] for k in ('id', 'map', 'night', 'seed'))
    assert (entry['map'], entry['night'], entry['seed']) not in old_keys
    for key in ('cold', 'draw'):
        path = args.study / 'corpus-plain' / entry[key]
        assert sha(path) == entry[key + '_sha256']
        checked[entry[key]] = entry[key + '_sha256']
    cold = json.loads((args.study / 'corpus-plain' / entry['cold']).read_text('utf-8'))
    assert cold['seed'] == entry['seed']
    assert sorted(cold['battle']['bans']) == sorted(entry['bans'])
for key in ('atlas', 'recipes'):
    assert sha(args.study / 'corpus-plain' / index[key]) == index[key + '_sha256']
parts = {}
for part in ('train', 'validation', 'test'):
    rows = [r for r in plan['entries'] if r['part']==part]
    parts[part] = dict(matches=len(rows), maps=len({r['map'] for r in rows}),
                      night=sum(r['night'] for r in rows), banned=sum(bool(r['ban_variant']) for r in rows))
report = dict(passed=True, sim_fingerprint=fingerprint, source_sha256=records,
              fresh_opening_count=len(index['entries']), overlaps_old_openings=0, partitions=parts,
              corpus_sha256=checked, game_release_sha256=sha(ROOT / 'PVZ_rougePvP_native/PvZPvPNative.exe'),
              documented_teacher_files=90, observed_teacher_files=len(list((ROOT / 'test_results/ai-nn-local-20261114/training-rollouts/matches').glob('*.jsonl'))))
args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256', 'corpus_sha256')}, ensure_ascii=False))
