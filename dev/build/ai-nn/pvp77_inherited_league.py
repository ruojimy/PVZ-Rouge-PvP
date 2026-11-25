"""Continue the inherited combat weights on native PvP77 r4 ranked sevens."""
import argparse
from bisect import bisect_right
from contextlib import contextmanager
import msvcrt
from pathlib import Path
import shutil
import time

import league_evolve as evolution
from league_data import ROOT, read, sha
from league_matches import summarize
import pvp77_card_support_train as card


native = card.native
PLANT, ZOMBIE = native.SIDES
RUN = ROOT / 'inherited-combat-pvp77-r4-20261124'
PRESSURES = (None, 'economy', 'late')
TRAIN_SEED, CONFIRM_SEED, BLIND_SEED = 78000000, 78100000, 78200000
PARENT = {side: card.model_path(side) for side in native.SIDES}
HISTORIC = {PLANT: PARENT[PLANT], ZOMBIE: card.model_path('zombie-evolved')}
R22 = 'r22'
DISK_LIMIT = 512 * 1024**2


@contextmanager
def exclusive():
    RUN.mkdir(exist_ok=True)
    with (RUN / 'training.lock').open('a+b') as handle:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        yield


def setup():
    build = read(card.RUN / 'native-build.json')
    profile = read(card.RUN / 'profile.json')
    card.verify_frozen_release(build)
    assert profile['version'] == build['version'] == card.VERSION
    assert build['fingerprint'] == profile['native_build']
    for name, digest in build['binaries'].items():
        assert sha(card.RUN / 'native' / f'{name}.exe') == digest
    assert sha(Path(profile['simulation_atlas'])) == profile['simulation_atlas_sha256']
    for name, receipt in read(card.RUN / 'transfer.json')['battle'].items():
        assert sha(card.model_path(name)) == receipt['sha256']
    assert profile['home'] == '家院' and not profile['night'] and profile['weather'] == 'clear'
    assert profile['rules'] == {'ranked': True, 'plant_slots': 7, 'zombie_slots': 7, 'extra_slot': False}
    native.RUN = card.battle.RUN = evolution.RUN = RUN
    native.PROFILE_PATH, native.STOP = RUN / 'profile.json', RUN / 'STOP'
    native.EXPECTED_VERSION = card.VERSION
    shutil.copyfile(card.RUN / 'catalog.json', RUN / 'catalog.json')
    profile['output'] = str(RUN)
    native.write_atomic(native.PROFILE_PATH, profile)
    native.configure()
    native.check_deadline()
    (RUN / 'models').mkdir(exist_ok=True)
    plan = {'version': card.VERSION, 'rules': profile['rules'], 'opening_source': profile['opening_source'],
            'map': profile['home'], 'deadline': profile['deadline'], 'pressure': PRESSURES,
            'model_parents': {s: {'path': str(p), 'sha256': sha(p)} for s, p in PARENT.items()},
            'old_zombie_comparator': sha(HISTORIC[ZOMBIE]),
            'seeds': {'screen': TRAIN_SEED, 'confirmation': CONFIRM_SEED, 'blind': BLIND_SEED},
            'method': 'paired mutation of inherited models with independent confirmation',
            'promotion': 'net true wins with no lost old wins, higher timeouts, or meaningful tempo loss'}
    native.write_atomic(RUN / 'plan.json', plan)


def opening(seed, heads, pressure):
    policies = {s: card.VariedFastOpponent(heads[s], seed) for s in native.SIDES}
    if seed % 5 in (1, 3):
        policies[native.SIDES[seed % 5 == 3]] = 'builtin'
    battle, _, targeted, _ = native.draft(seed, policies, pressure=pressure)
    assert battle['map'] == '家院' and not battle['night'] and battle['weather'] == 'clear'
    assert len(battle['draft_history']) == 30 and all(len(battle['decks'][s]) == 7 for s in native.SIDES)
    return battle, targeted


def played(cold, name, sc, side, model, foe, **kwargs):
    seats = {side: model, evolution.other(side): foe}
    args = {k: None if v == R22 else Path(v) for k, v in seats.items()}
    return card.play(cold, name, sc, measure=True, **args, **kwargs)


def comparison(side, opponent, case, old, new):
    ends = [round(30 * game['seconds']) for game in (old, new)]
    common = min(ends)
    outcomes = [native.battle_outcome(game) for game in (old, new)]
    values = [0 if result == 'timeout' else 1 if result == side else -1 for result in outcomes]
    return {'opp': opponent, 'case': case, 'old': values[0], 'new': values[1], 'ends': ends, 'window': common,
            'different': old['log_sha256'] != new['log_sha256'],
            'deploy': {kind: [bisect_right(game['activity_ticks'][kind], common) for game in (old, new)]
                       for kind in ('plant', 'troops', 'graves')}}


def qualifies(stats, minimum_gains):
    old, new = stats['old'], stats['new']
    return (new[0] - old[0] >= minimum_gains and not stats['lost'] and new[1] <= old[1]
            and all(new[0] >= old[0] and new[1] <= old[1] for old, new in stats['by'].values())
            and stats['seconds'][1] <= 1.05 * stats['seconds'][0]
            and all(after >= .95 * before for before, after in
                    (stats['rates']['plant'], stats['rates']['troops'])))


def stage(folder, label, jobs, run, lanes, cutoff):
    folder.mkdir(parents=True, exist_ok=True)
    stored = {path.stem: read(path) for path in folder.glob('*.json')}

    def save(item):
        key, result = item
        native.write_atomic(folder / f'{key}.json', result)
        stored[key] = result
        if len(stored) % 4 == 0:
            native.status(label, completed=len(stored), target=len(jobs))

    native.status(label, completed=len(stored), target=len(jobs))
    native.work(((key, job) for key, job in jobs.items() if key not in stored),
                lambda item: (item[0], run(item[1])), save, lanes, cutoff)
    return stored


def run_games(heads, folder, label, seed_base, count, baseline, candidates, opponents, lanes, cutoff):
    jobs = {f'{side}-{i:03}': (side, i) for i in range(count) for side in candidates}

    def run(job):
        side, i = job
        seed = seed_base + i
        pressure = PRESSURES[i % len(PRESSURES)]
        sc, targeted = opening(seed, heads, pressure)
        results = []
        with card.battle.cold_opening(sc) as cold:
            for j, foe in enumerate(opponents[side]):
                games = {'parent': played(cold, f'{j}-ref', sc, side, baseline[side], foe)}
                games.update({name: played(cold, f'{j}-{name}', sc, side, model, foe)
                              for name, model in candidates[side].items()})
                results.append({'opponent': str(foe), 'games': games})
        return {'opening': sc, 'pressure': pressure, 'targeted': targeted, 'side': side, 'results': results}

    receipts = stage(folder, label, jobs, run, lanes, cutoff)
    if len(receipts) != len(jobs):
        return None
    return stats(receipts, candidates)


def stats(receipts, candidates):
    matrix = {}
    for side, names in candidates.items():
        matrix[side] = {}
        for name in names:
            rows = [comparison(side, r['opponent'], sc['opening']['seed'], r['games']['parent'], r['games'][name])
                    for sc in receipts.values() if sc['side'] == side for r in sc['results']]
            matrix[side][name] = summarize(rows, side)
    return matrix


def zombie_gate_candidates(turn, folder, parent, progress):
    """Find a usable activation threshold before perturbing a dormant action policy."""
    receipt = folder / 'zombie-gate-plan.json'
    if receipt.exists():
        probes = read(receipt)['probes']
    else:
        if progress['promotions'] or any((RUN / 'models').glob(f'{turn:04}-zombie-*.json')):
            return None
        history = sorted((RUN / 'rounds').glob('*/screen-summary.json'))[-8:]
        inherited = any((RUN / 'rounds').glob('*/zombie-gate-plan.json'))
        dormant = len(history) == 8 and not any(
            result['changed'] for path in history for result in read(path)[ZOMBIE].values())
        if not inherited and not dormant:
            return None
        probes = (.25, .50) if turn % 2 else (.75, 1.)
        native.write_atomic(receipt, {
            'probes': probes, 'reference_sha256': sha(parent),
            'evolved_sha256': sha(HISTORIC[ZOMBIE]), 'reason': 'native gate remained inactive in paired screens',
        })
    old, evolved = (read(path)['switch']['native_gate']['bias'] for path in (parent, HISTORIC[ZOMBIE]))
    models = {}
    for slot, strength in enumerate(probes):
        target = RUN / 'models' / f'{turn:04}-zombie-gate-{slot}.json'
        model = read(parent)
        model['switch']['native_gate']['bias'] = [a + strength * (b - a) for a, b in zip(old, evolved)]
        model['gate_continuation'] = {'parent': sha(parent), 'evolved': sha(HISTORIC[ZOMBIE]), 'strength': strength}
        if target.exists():
            assert read(target) == model
        else:
            native.write_atomic(target, model)
        models[f'gate-{slot}'] = target
    return models


def train(heads, lanes):
    state_path = RUN / 'state.json'
    state = read(state_path) if state_path.exists() else {
        'round': 0, 'sides': {s: {'champ': str(PARENT[s]), 'temp': .24, 'promotions': 0, 'defenses': 0}
                              for s in native.SIDES}}
    native.write_atomic(state_path, state)
    cutoff = native.DEADLINE - 2700
    while time.time() < cutoff and not native.STOP.exists():
        turn = state['round'] + 1
        folder = RUN / 'rounds' / f'{turn:03}'
        base = {s: Path(state['sides'][s]['champ']) for s in native.SIDES}
        candidates = {}
        for side, parent in base.items():
            progress = state['sides'][side]
            gate = zombie_gate_candidates(turn, folder, parent, progress) if side == ZOMBIE else None
            candidates[side] = gate or {f'mutation-{slot}': Path(evolution.mutate(
                side, parent, turn, slot, progress['temp'])[0]) for slot in (0, 1)}
        opponents = {s: [R22, base[evolution.other(s)]] for s in native.SIDES}
        offset = turn * 100
        screen = run_games(heads, folder / 'screen', f'round-{turn}-screen', TRAIN_SEED + offset,
                           3, base, candidates, opponents, lanes, cutoff)
        if screen is None:
            break
        native.write_atomic(folder / 'screen-summary.json', screen)
        selected = {}
        for side, scores in screen.items():
            name = max(scores, key=lambda option: (scores[option]['score'], scores[option]['new'][0],
                                                    scores[option]['changed']))
            if scores[name]['changed'] and scores[name]['new'][0] >= scores[name]['old'][0]:
                selected[side] = {name: candidates[side][name]}
        if selected:
            confirm = run_games(heads, folder / 'confirm', f'round-{turn}-confirm', CONFIRM_SEED + offset,
                                6, base, selected, opponents, lanes, cutoff)
            if confirm is None:
                break
        else:
            confirm = {}
        for side, progress in state['sides'].items():
            validations = confirm.get(side, {})
            if validations and qualifies(next(iter(validations.values())), 2):
                progress.update(champ=str(next(iter(selected[side].values()))),
                                promotions=progress['promotions'] + 1, defenses=0)
            elif validations:
                progress['defenses'] += 1
                if progress['defenses'] % 3 == 0:
                    progress['temp'] = max(.10, round(progress['temp'] * .72, 5))
        native.write_atomic(folder / 'confirmation-summary.json', confirm)
        state['round'] = turn
        native.write_atomic(state_path, state)
        native.status('confirmed-round', round=turn, sides=state['sides'])
        if turn % 4 == 0 and sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file()) > DISK_LIMIT:
            break

    champs = {s: {'champion': Path(progress['champ'])} for s, progress in state['sides'].items()
              if Path(progress['champ']) != PARENT[s]}
    if champs and not native.STOP.exists():
        final = run_games(heads, RUN / 'blind', 'blind', BLIND_SEED, 12, PARENT, champs,
                          {s: [R22, HISTORIC[evolution.other(s)]] for s in native.SIDES}, lanes, native.DEADLINE - 40)
        if final is not None:
            native.write_atomic(RUN / 'blind-summary.json', final)
    native.status('stopped' if native.STOP.exists() else 'finished',
                  round=state['round'], sides=state['sides'], blind=(RUN / 'blind-summary.json').exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lanes', type=int, default=6)
    args = parser.parse_args()
    with exclusive():
        setup()
        import torch
        torch.set_num_threads(1)
        try:
            train(card.draft_heads(), args.lanes)
        except Exception as exc:
            native.status('failed', error=repr(exc))
            raise


if __name__ == '__main__':
    main()
