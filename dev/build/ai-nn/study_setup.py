"""Freeze fresh, genuinely constructed openings before any learning or match selection."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
plan_path = out / 'plan.json'
if plan_path.exists():
    raise SystemExit('The study is already frozen')
generator = ROOT / 'build/pvp73-tools/ai-20261116/Release/deck73_corpus.exe'
exporter = generator.with_name('cold73_export.exe')
with (out / 'draft.log').open('wb') as log:
    subprocess.run([str(generator), str(out / 'draft-pool.json'), '4', '2', '160000', '161116'],
                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
pool = json.loads((out / 'draft-pool.json').read_text('utf-8'))
assert len(pool) == 192 and all('invalid' not in r and 'error' not in r for r in pool)
maps = list(dict.fromkeys(r['map'] for r in pool))
selected, entries = [], []
for r in pool:
    seed_group = (r['seed'] - 160000) // 1000 - 1
    variant = (r['seed'] % 500) // 17
    if variant != (maps.index(r['map']) + int(r['night']) + seed_group) % 2:
        continue
    key = f'{len(selected):03d}'
    part = 'train' if seed_group < 2 else 'validation' if seed_group == 2 else 'test'
    selected.append(r)
    entries.append(dict(id=key, part=part, map=r['map'], night=r['night'], seed=r['seed'],
                        seed_group=seed_group, ban_variant=variant))
assert len(entries) == 96
for part, count in [('train', 48), ('validation', 24), ('test', 24)]:
    ids = [r['id'] for r in entries if r['part'] == part]
    assert len(ids) == count
    (out / (part + '-ids.txt')).write_text('\n'.join(ids) + '\n', 'utf-8')
(out / 'all-ids.txt').write_text('\n'.join(r['id'] for r in entries) + '\n', 'utf-8')
(out / 'scenarios.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), 'utf-8')
old = ROOT / 'test_results/ai-nn-followup-20261115/training-v1-revalidated/model.json'
aug = ROOT / 'test_results/ai-nn-followup-20261115/training-aug1-current/model.json'
release = ROOT / 'dist/PvZ-PvP-Native-20261116-pvp743-r3/PvZPvPNative.exe'
local = ROOT / 'PVZ_rougePvP_native/PvZPvPNative.exe'
assert sha(release) == sha(local)
plan = dict(format='pvz-ai-study-1', game_revision='pvp743-r3',
    release_exe_sha256=sha(release), simulation_build_header=(ROOT / 'build/ai-nn/windows-20261116/ai_nn_build.h').read_text(),
    original_model=str(old), original_model_sha256=sha(old), previous_augmented_model_sha256=sha(aug),
    generator_sha256=sha(generator), exporter_sha256=sha(exporter), scenarios_sha256=sha(out / 'scenarios.json'),
    entries=entries, split_note='Fresh seed groups, shared known maps; 48 train / 24 validation / 24 sealed test. '
    'All previously observed data may be training; this is NOT unseen-map generalization. '
    'Ban/no-ban is balanced in every partition. Terrain, draft and RNG are constructed by the current Windows game.',
    control_hz=15, limit_seconds=600, jobs=2,
    architectures=[dict(name='compact', embedding=8, hidden=64), dict(name='wide', embedding=16, hidden=128)],
    training_seeds=[743, 1743], epochs=80, patience=15, learning_rates=[0.003, 0.001],
    selection='Best validation imitation loss within architecture; then one-seat paired validation matches. '
    'Include r22 and original network in selection. Select per seat by wins, then fewer losses, then lower complexity. '
    'Freeze selections before opening test outcomes; test results never feed back into this study.',
    denominator='All scheduled games, including timeout/crash/AI error; no timeout counted as victory.',
    scope='Research-only models. No production AI, launcher, user data or deployment changes.')
plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(dict(scenarios=len(entries), plan_sha256=sha(plan_path))))
