"""Train and check a native deployment-position policy on PvP77 r4 ranked sevens."""
import argparse
from collections import Counter
from contextlib import contextmanager
import ctypes
from datetime import datetime
import gzip
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import pvp76_ranked_draft_train as native
import pvp77_ranked_draft_night as draft_study
from league_data import ROOT, read, sha


RUN = ROOT / 'battle-control-pvp77-r4-20261124'
PROFILE = RUN / 'profile.json'
ARCHIVE = draft_study.RUN
PLANT_DRAFT = (RUN / 'models/plant-draft-wave06.pt', RUN / 'models/plant-draft-prior.json')
ZOMBIE_DRAFT = (RUN / 'models/zombie-draft-wave07.pt', RUN / 'models/zombie-draft-prior.json')
END = '2026-11-25T09:00:00+08:00'
VERSION = '1.6.0.77-typed.20261124-r4'
FORMAT = 'pvz77-deploy-rank-1'
FEATURES = 24
CHOICES = 10
TRAIN_SEED, DEV_SEED, BLIND_SEED = 77000000, 77500000, 77600000
SIDES = native.SIDES
FIRST_BATCH, NEXT_BATCH = 180, 240
DEV_CASES, BLIND_CASES = 32, 96
MARGIN = 0.35


def setup(until):
    draft_study.configure_paths()
    native.RUN, native.PROFILE_PATH, native.ATLAS, native.STOP = RUN, PROFILE, RUN / 'simulation-atlas.bin', RUN / 'STOP'
    native.EXPECTED_VERSION = VERSION
    # After the first setup, reuse the same source/data even if a release is published overnight.
    if not PROFILE.exists():
        native.setup(until)
    assert read(PROFILE)['deadline'] == until
    native.configure()
    native.check_deadline()
    build = read(RUN / 'native-build.json')
    assert build['version'] == VERSION and build['fingerprint'] == native.PROFILE['native_build']
    assert all(sha(Path(native.PROFILE['native_dir']) / (name + '.exe')) == digest
               for name, digest in build['binaries'].items())
    frozen = read(ARCHIVE / 'final-blind/plan.json')
    for name, path, bundle in (('old', draft_study.REFERENCE, PLANT_DRAFT), ('new', draft_study.CANDIDATE, ZOMBIE_DRAFT)):
        assert frozen[name] == draft_study.bundle_receipt(path)
        native.transfer_checkpoint(*path, *bundle, RUN / ('transfer-' + name + '.json'))
    plan = {'version': VERSION, 'rules': native.PROFILE['rules'], 'build': build['fingerprint'],
            'opening_source': native.PROFILE['opening_source'],
            'drafts': {'plant': draft_study.bundle_receipt(PLANT_DRAFT),
                       'zombie': draft_study.bundle_receipt(ZOMBIE_DRAFT)},
            'action_scope': 'deployment position and origin grave; same card, with r22 timing and other controls',
            'model_margin': MARGIN, 'deadline': until, 'historical_r2_labels_imported': 0,
            'seeds': {'train': TRAIN_SEED, 'development': DEV_SEED, 'blind': BLIND_SEED}}
    native.write_atomic(RUN / 'plan.json', plan)


def opening(seed, plants, zombies):
    # Mostly varied drafts from the frozen heads; some seats use the shipped selector.
    # Native masks and the full 30-step ban/pick sequence own all legality.
    variant = seed % 12
    plant = 'builtin' if variant == 2 else draft_study.VariedFastOpponent(plants, seed)
    zombie = 'builtin' if variant == 5 else draft_study.VariedFastOpponent(zombies, seed)
    stress = {1: 'economy', 4: 'late', 7: 'double', 10: 'economy'}.get(variant)
    sc, _, _, _ = native.draft(seed, dict(zip(SIDES, (plant, zombie))), pressure=stress)
    return sc


@contextmanager
def cold_opening(sc):
    from ranked_corpus import atlas, native as export

    native.check_deadline()
    scratch = RUN / 'scratch'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='battle-') as tmp:
        folder = Path(tmp)
        cold, draw = export(sc, folder, '000', timeout=max(0.1, min(90, native.seconds_left())))
        atlas_ref = Path(os.path.relpath(atlas(), folder)).as_posix()
        native.write_atomic(folder / 'index.json', {
            'atlas': atlas_ref,
            'entries': [{**sc, 'id': '000', 'cold': cold.name, 'draw': draw.name,
                         'cold_sha256': sha(cold), 'draw_sha256': sha(draw)}],
        })
        yield folder


def play(folder, name, sc, model=None, seat=None, trace=None):
    native.check_deadline()
    exe = Path(native.PROFILE['native_dir']) / 'position_match.exe'
    path = folder / (name + '.jsonl')
    args = [str(exe), '--corpus', str(folder), '--id', '000', '--out', str(path),
            '--limit-seconds', '600', '--control-hz', '15', '--no-records', '--telemetry']
    if trace is not None:
        args += ['--deploy-trace', str(trace)]
    if model is not None:
        args += ['--deploy-model', str(model), '--deploy-side', seat, '--deploy-margin', str(MARGIN)]
    result = subprocess.run(args, capture_output=True, timeout=max(0.1, min(180, native.seconds_left())))
    if result.returncode:
        detail = result.stderr.decode('utf-8', errors='replace')[-1800:]
        raise RuntimeError(f'Action simulator exited {result.returncode} on {sc["seed"]}: {detail}')
    head, foot = (json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
    assert head['planners'] == dict.fromkeys(SIDES, 'r22')
    assert head['source_fingerprint'] == native.PROFILE['native_build']
    assert head['ranked_rules']['build'] == VERSION and all(
        head['ranked_rules'][key] == value for key, value in native.PROFILE['rules'].items())
    assert head['seed'] == sc['seed'] and head['decks'] == sc['decks']
    if model is None:
        assert head['deploy_controller'] is None
    else:
        assert head['deploy_controller'] == {'seat': seat, 'margin': MARGIN, 'sha256': sha(model)}
    assert not foot['ai_error'] and (foot['finished'] or foot['timeout']), foot['ai_error']
    deployments = Counter(e['side'] for e in foot['activity'] if e['kind'] == 'deploy')
    return {'winner': (foot['result'] or {}).get('winner'), 'timeout': foot['timeout'],
            'seconds': foot['time'], 'deploys': dict(deployments), 'log_sha256': foot['log_sha256'],
            'controller': head['deploy_controller'], 'policy': foot['deploy_policy'],
            'send_errors': {s: foot['ai'][s]['send_errors'] for s in SIDES}}


def deck_bucket(sc):
    decks = [sorted(sc['decks'][s]) for s in SIDES]
    digest = hashlib.sha256(json.dumps(decks, ensure_ascii=False).encode()).hexdigest()
    return int(digest[:8], 16) % 10


def collection_case(index, plants, zombies, model):
    seed = TRAIN_SEED + index
    sc = opening(seed, plants, zombies)
    # Some student rollouts use legal r22 suggestions as labels on states visited by the student.
    seat = SIDES[(index // 5) % 2] if model and index % 5 in (2, 4) else None
    path = RUN / 'training-games' / f'{index:05}.json.gz'
    with cold_opening(sc) as folder:
        trace = folder / 'deploy.ndjson'
        result = play(folder, 'train', sc, model if seat else None, seat, trace)
        data = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        assert all(row['label'] == 0 and 2 <= len(row['features']) <= CHOICES for row in data)
    receipt = {'i': index, 'opening': sc, 'result': result, 'fold': deck_bucket(sc),
               'counts': dict(Counter(row['side'] for row in data)), 'native_build': native.PROFILE['native_build']}
    path.parent.mkdir(exist_ok=True)
    temp = path.with_suffix('.partial')
    with gzip.open(temp, 'wt', compresslevel=4, encoding='utf-8') as file:
        file.write(json.dumps(receipt, ensure_ascii=False) + '\n')
        for row in data:
            file.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    os.replace(temp, path)
    return receipt


def collect(start, stop, plants, zombies, model, lanes, cutoff):
    seen = {int(p.name.split('.')[0]) for p in (RUN / 'training-games').glob('*.json.gz')}
    made = len(seen)

    def consume(_):
        nonlocal made
        made += 1
        if made % 20 == 0:
            native.status('collect-actions', games=made, target=stop)

    native.status('collect-actions', games=made, target=stop)
    native.work((i for i in range(start, stop) if i not in seen),
                lambda i: collection_case(i, plants, zombies, model), consume, lanes, cutoff)
    native.status('collect-actions-done', games=made, target=stop)
    return made


def dataset():
    import numpy as np

    # Bound memory and keep all rows from one deck pair in the same fold.
    bins = {(side, fold): [] for side in SIDES for fold in ('train', 'validation')}
    files = list((RUN / 'training-games').glob('*.json.gz'))
    files.sort(key=lambda p: hashlib.sha256(p.name.encode()).hexdigest())
    for path in files:
        with gzip.open(path, 'rt', encoding='utf-8') as file:
            info = json.loads(file.readline())
            fold = 'validation' if info['fold'] < 2 else 'train'
            for line in file:
                row = json.loads(line)
                target = bins[row['side'], fold]
                if len(target) < (85000 if fold == 'train' else 14000):
                    target.append(np.asarray(row['features'], dtype=np.float32))
        if all(len(rows) >= (85000 if key[1] == 'train' else 14000) for key, rows in bins.items()):
            break
    return bins


def fit(checkpoint, cutoff):
    import torch
    import torch.nn.functional as F
    from torch import nn

    bins = dataset()

    def tensors(rows):
        x = torch.zeros(len(rows), CHOICES, FEATURES)
        mask = torch.zeros(len(rows), CHOICES, dtype=torch.bool)
        for i, row in enumerate(rows):
            x[i, :len(row)] = torch.from_numpy(row)
            mask[i, :len(row)] = True
        assert torch.isfinite(x).all()
        return x, mask

    weights, report = {}, {}
    for side in SIDES:
        torch.manual_seed(7704)
        train_x, train_mask = tensors(bins.pop((side, 'train')))
        val_x, val_mask = tensors(bins.pop((side, 'validation')))
        if len(train_x) < 64 or len(val_x) < 8:
            raise RuntimeError(f'Insufficient native choice groups in {side} or its held-out deck fold')
        net = nn.Sequential(nn.Linear(FEATURES, 48), nn.ReLU(), nn.Linear(48, 1))
        opt = torch.optim.AdamW(net.parameters(), lr=0.0015, weight_decay=0.001)
        target = torch.zeros(len(train_x), dtype=torch.long)
        best = None
        for epoch in range(18):
            if time.time() >= cutoff:
                raise TimeoutError('deployment fitting budget expired')
            net.train()
            for idx in torch.randperm(len(train_x)).split(256):
                scores = net(train_x[idx]).squeeze(-1).masked_fill(~train_mask[idx], float('-inf'))
                loss = F.cross_entropy(scores, target[idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
            net.eval()
            with torch.no_grad():
                scores = net(val_x).squeeze(-1).masked_fill(~val_mask, float('-inf'))
                loss = float(F.cross_entropy(scores, torch.zeros(len(val_x), dtype=torch.long)))
                top1 = float((scores.argmax(1) == 0).float().mean())
            if best is None or loss < best[0]:
                best = (loss, top1, epoch + 1, {k: v.clone() for k, v in net.state_dict().items()})
        loss, top1, epoch, state = best
        weights[side] = {'hidden': state['0.weight'].tolist(), 'bias': state['0.bias'].tolist(),
                         'output': state['2.weight'][0].tolist(), 'intercept': float(state['2.bias'][0])}
        report[side] = {'train': len(train_x), 'validation': len(val_x), 'epoch': epoch,
                        'held_out_action_match': top1, 'loss': loss, 'random_match': float(
                            (1. / val_mask.sum(dim=1).float()).mean())}
    native.write_atomic(checkpoint, {'format': FORMAT, 'features': FEATURES, 'sides': weights})
    native.write_atomic(checkpoint.with_suffix('.fit.json'), report)
    return report


def compare_case(seed, plants, zombies, models, kind):
    fixed = RUN / 'openings' / kind / f'{seed}.json'
    saved = read(fixed) if fixed.exists() else None
    sc = saved['opening'] if saved else opening(seed, plants, zombies)
    with cold_opening(sc) as folder:
        base = saved['r22'] if saved else play(folder, 'r22', sc)
        if not saved:
            native.write_atomic(fixed, {'opening': sc, 'r22': base})
        candidates = {seat: play(folder, seat, sc, path, seat) for seat, path in models.items()}
    return {'opening': sc, 'r22': base, 'candidates': candidates}


def summarize(rows, target):
    arms = {}
    for side in SIDES:
        paired = [(r['r22'], r['candidates'][side]) for r in rows if side in r['candidates']]
        if not paired:
            continue
        outcome = native.battle_outcome
        changes = Counter((outcome(old), outcome(new)) for old, new in paired)
        def count(which, result):
            return sum(v for k, v in changes.items() if k[which] == result)
        deploy_rate = []
        for which in (0, 1):
            total = sum(r[which]['deploys'].get(side, 0) for r in paired)
            time_sum = sum(r[which]['seconds'] for r in paired)
            deploy_rate.append(round(60 * total / max(1, time_sum), 3))
        lost = sum(v for (old, new), v in changes.items() if old == side and new != side)
        swaps = sum(new['policy']['swaps'] for _, new in paired)
        fallbacks = sum(new['policy']['fallbacks'] for _, new in paired)
        arms[side] = {'pairs': len(paired), 'r22_wins': count(0, side), 'candidate_wins': count(1, side),
                      'r22_timeouts': count(0, 'timeout'), 'candidate_timeouts': count(1, 'timeout'),
                      'wins_lost': lost, 'actions_changed': swaps, 'native_fallbacks': fallbacks,
                      'r22_deploys_per_minute': deploy_rate[0], 'candidate_deploys_per_minute': deploy_rate[1],
                      'transitions': {f'{a}->{b}': v for (a, b), v in changes.items()},
                      'admitted': len(paired) == target and swaps > 0 and fallbacks == 0 and lost == 0
                          and count(1, 'timeout') <= count(0, 'timeout') and deploy_rate[1] >= .9 * deploy_rate[0]}
    return {'finished_openings': len(rows), 'target_openings': target, 'sides': arms}


def compare(name, kind, seed_base, count, plants, zombies, models, lanes, cutoff):
    folder = RUN / name
    metadata = {'kind': kind, 'seed_base': seed_base, 'openings': count,
                'models': {seat: {'path': str(path), 'sha256': sha(path)} for seat, path in models.items()},
                'build': native.PROFILE['native_build'], 'rules': native.PROFILE['rules']}
    if (folder / 'plan.json').exists():
        assert read(folder / 'plan.json') == metadata
    else:
        native.write_atomic(folder / 'plan.json', metadata)
    rows = {int(path.stem): read(path) for path in folder.glob('77*.json')}

    def consume(row):
        seed = row['opening']['seed']
        native.write_atomic(folder / f'{seed}.json', row)
        rows[seed] = row
        if len(rows) % 8 == 0:
            native.status(name, openings=len(rows), target=count)
            native.write_atomic(folder / 'summary.json', summarize(rows.values(), count))

    native.status(name, openings=len(rows), target=count)
    native.work((s for s in range(seed_base, seed_base + count) if s not in rows),
                lambda seed: compare_case(seed, plants, zombies, models, kind), consume, lanes, cutoff)
    result = summarize(rows.values(), count)
    native.write_atomic(folder / 'summary.json', result)
    native.status(name + '-done', openings=len(rows), target=count)
    return result


def preflight(plants, zombies):
    sc = opening(76990000, plants, zombies)
    if not native.PROFILE.get('simulation_atlas'):
        native.bridge_atlas(sc)
    with cold_opening(sc) as folder:
        base = play(folder, 'base', sc)
        trace = folder / 'deploy.ndjson'
        teacher = play(folder, 'teacher', sc, trace=trace)
        if base['log_sha256'] != teacher['log_sha256']:
            native.write_atomic(RUN / 'preflight-difference.json', {'opening': sc, 'untraced': base, 'traced': teacher})
            raise AssertionError('Recording changed the r22 battle')
        rows = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        assert rows and all(row['executed'] == row['label'] == 0 for row in rows)
        assert all(2 <= len(row['features']) <= CHOICES and all(len(x) == FEATURES for x in row['features'])
                   for row in rows)
        counts = dict(Counter(row['side'] for row in rows))
    evidence = {'opening': sc, 'same_r22_battle': True, 'choice_groups': counts,
                'baseline': base, 'native_build': native.PROFILE['native_build']}
    native.write_atomic(RUN / 'preflight.json', evidence)
    native.status('preflight-passed', choice_groups=counts, win=native.battle_outcome(base))


def rank(metrics):
    return (int(metrics['admitted']), metrics['candidate_wins'] - metrics['r22_wins'],
            -metrics['wins_lost'], metrics['r22_timeouts'] - metrics['candidate_timeouts'],
            -metrics['native_fallbacks'], metrics['candidate_deploys_per_minute'])


def run(lanes):
    plants, zombies = native.fast_head(*PLANT_DRAFT), native.fast_head(*ZOMBIE_DRAFT)
    if not (RUN / 'preflight.json').exists():
        native.status('preflight')
        preflight(plants, zombies)
    final_at = native.DEADLINE - 60 * 60
    progress = RUN / 'training-checkpoint.json'
    state = read(progress) if progress.exists() else {'games': 0, 'wave': 0, 'best': {}}
    best = state['best']
    while not native.STOP.exists() and time.time() < final_at - 25 * 60:
        before = state['games']
        wave = state['wave'] + 1
        label = f'wave-{wave:02d}'
        checkpoint = RUN / 'models' / (label + '.json')
        current = RUN / 'models' / f'wave-{wave - 1:02d}.json' if wave > 1 else None
        target = before + (FIRST_BATCH if wave == 1 else NEXT_BATCH)
        count = collect(before, target, plants, zombies, current, lanes, final_at - 25 * 60)
        if count <= before:
            break
        native.status('fit-actions', wave=wave, r4_games=count)
        try:
            metrics = fit(checkpoint, final_at - 17 * 60)
        except TimeoutError:
            native.status('fit-timeout', wave=wave, r4_games=count)
            break
        result = compare('dev-' + label, 'dev', DEV_SEED, DEV_CASES, plants, zombies,
                         dict.fromkeys(SIDES, checkpoint), lanes, final_at - 180)
        for side, score in result['sides'].items():
            if score['pairs'] != DEV_CASES:
                continue
            if side not in best or rank(score) > rank(best[side]['development']):
                best[side] = {'path': str(checkpoint), 'sha256': sha(checkpoint),
                              'fit': metrics[side], 'development': score}
        state.update(games=count, wave=wave)
        native.write_atomic(progress, state)
    if not best:
        native.status('finished-without-validated-candidate', r4_games=state['games'], waves=state['wave'])
        return
    candidates = {side: Path(row['path']) for side, row in best.items()}
    assert all(sha(candidates[side]) == row['sha256'] for side, row in best.items())
    holdout = compare('final-blind', 'blind', BLIND_SEED, BLIND_CASES, plants, zombies,
                      candidates, lanes, native.DEADLINE - 240)
    native.write_atomic(RUN / 'candidate.json', {
        'action_scope': read(RUN / 'plan.json')['action_scope'],
        'r4_games': state['games'], 'waves': state['wave'], 'frozen_candidates': best,
        'holdout': holdout,
    })
    native.status('finished', r4_games=state['games'], waves=state['wave'],
                  blind_openings=holdout['finished_openings'], blind_target=BLIND_CASES,
                  admitted={seat: row['admitted'] for seat, row in holdout['sides'].items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lanes', type=int, default=6)
    parser.add_argument('--until', default=END)
    args = parser.parse_args()
    if args.lanes < 1 or datetime.fromisoformat(args.until).timestamp() <= time.time():
        parser.error('Require positive lanes and a future deadline')
    RUN.mkdir(exist_ok=True)
    with (RUN / 'training.lock').open('a+b') as lock:
        if not lock.tell():
            lock.write(b'x')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            setup(args.until)
            run(args.lanes)
        except Exception as error:
            native.status('failed', error=repr(error))
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
