"""Resume the ranked draft study on the released PvP77 r2 rules for one night."""
import argparse
from collections import Counter
import ctypes
from datetime import datetime, timedelta
import msvcrt
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

import pvp76_ranked_draft_train as native
from league_data import ROOT, read, sha


RUN = ROOT / 'deck-value-pvp77-r2-20261123'
OLD = ROOT / 'deck-value-pvp76-r3-20261123'
TRANSFER = (RUN / 'models/transferred.pt', RUN / 'models/transferred-prior.json')
REFERENCE = (RUN / 'models/wave-06.pt', RUN / 'models/wave-06-prior.json')
CANDIDATE = (RUN / 'models/wave-07.pt', RUN / 'models/wave-07-prior.json')
START = '2026-11-23T23:30:00+08:00'
END = '2026-11-24T09:30:00+08:00'
INITIAL_SEED = 76200000
FINAL_SEED = 76400000
ACTION_SEED = 76500000
PRESSURES = ('economy', 'double', 'late')
PLANT, ZOMBIE = native.SIDES


def configure_paths():
    native.RUN = RUN
    native.PROFILE_PATH = RUN / 'profile.json'
    native.ATLAS = RUN / 'simulation-atlas.bin'
    native.STOP = RUN / 'STOP'
    native.EXPECTED_VERSION = '1.6.0.77-typed.20261123-r2'
    native.SMOKE_SEED = 76199000
    native.CORPUS_SEED = 76250000
    native.TEACHER_SEED = 76300000
    native.PRESSURE['double'] = {'opening_ban': (native.SUNFLOWER, native.CABBAGE)}


def migrate():
    source = read(OLD / 'candidate.json')
    assert source['wave'] == 'wave-06'
    assert sha(Path(source['path'])) == source['sha256']
    assert sha(Path(source['prior'])) == source['prior_sha256']
    native.transfer_checkpoint(
        OLD / 'models/fast-transferred.pt', OLD / 'models/prior-transferred.json',
        *TRANSFER, RUN / 'transfer-baseline.json')
    native.transfer_checkpoint(
        Path(source['path']), Path(source['prior']), *REFERENCE, RUN / 'transfer-wave-06.json')


class VariedFastOpponent:
    """Draw a fixed per-turn perturbation from the top legal choices of a frozen head."""
    def __init__(self, head, seed):
        self.head = head
        self.seed = seed

    def choose(self, side, action, state, offers):
        rng = random.Random(self.seed * 1009 + state['step'] * 7)
        if rng.random() >= 0.25:
            return self.head.choose(side, action, state, offers)
        choices = self.head.rank_choices(side, action, state, offers, 3)
        return rng.choice(choices)


def bundle_receipt(paths):
    return {'weights': str(paths[0]), 'weight_sha256': sha(paths[0]),
            'prior': str(paths[1]), 'prior_sha256': sha(paths[1])}


def matrix(name, seed_base, cases, old, new, frozen, lanes, cutoff, *,
           stages=None, opponent_bundle=TRANSFER, load_new=None, variant=None):
    """Vary one draft seat at a time; use common opening and opponent seeds."""
    folder = RUN / name
    if stages is None:
        stages = [(PLANT, condition) for condition in (None, *PRESSURES)] + [(ZOMBIE, None)]
    specs = [(seat, pressure, foe) for seat, pressure in stages for foe in ('builtin', 'fast')]
    total = cases * len(specs) * 2
    receipt = {'seed_base': seed_base, 'seeds': cases, 'cases': total,
               'old': bundle_receipt(old), 'new': bundle_receipt(new), 'opponent': bundle_receipt(opponent_bundle),
               'opponent_rng': 'seed * 1009 + turn * 7; 25% chance of drawing from top three',
               'rules': native.PROFILE['rules'], 'native_build': native.PROFILE['native_build'],
               'opening_source': native.PROFILE['opening_source'], 'controllers': dict.fromkeys(native.SIDES, 'r22')}
    if variant:
        receipt['variant'] = variant
    plan_path = folder / 'plan.json'
    if plan_path.exists():
        assert read(plan_path) == receipt
    else:
        native.write_atomic(plan_path, receipt)
    models = {'old': native.fast_head(*old), 'new': (load_new or native.fast_head)(*new)}
    rows, jobs = {}, []
    for seed in range(seed_base, seed_base + cases):
        for seat, pressure, foe in specs:
            key = f'{seed}-{seat}-{pressure or "normal"}-{foe}'
            for arm in models:
                path = folder / f'{key}-{arm}.json'
                if path.exists():
                    rows[key, arm] = read(path)
                else:
                    jobs.append((seed, seat, pressure, foe, key, arm, path))

    def play(item):
        seed, seat, pressure, foe, key, arm, path = item
        opponent = 'builtin' if foe == 'builtin' else VariedFastOpponent(frozen, seed)
        policies = dict.fromkeys(native.SIDES, opponent)
        policies[seat] = models[arm]
        sc, _, targeted, fallbacks = native.draft(seed, policies, pressure=pressure)
        result = native.fight(sc)
        return key, arm, path, {'seat': seat, 'pressure': pressure, 'opponent': foe, 'arm': arm,
                                'opening': sc, 'targeted': targeted, 'builtin_fallbacks': fallbacks,
                                'result': result}

    def consume(item):
        key, arm, path, row = item
        native.write_atomic(path, row)
        rows[key, arm] = row
        if len(rows) % 24 == 0:
            native.status(name, games=len(rows), target=total)
            native.write_atomic(folder / 'summary.json', matrix_summary(rows, total))

    native.status(name, games=len(rows), target=total)
    native.work(jobs, play, consume, lanes, cutoff)
    summary = matrix_summary(rows, total)
    native.write_atomic(folder / 'summary.json', summary)
    native.status(name + '-done', games=len(rows), target=total, paired=summary['paired'])
    return summary


def matrix_summary(rows, total):
    groups = {}
    for (key, arm), old in sorted(rows.items()):
        if arm != 'old' or (key, 'new') not in rows:
            continue
        new = rows[key, 'new']
        seat, foe, pressure = old['seat'], old['opponent'], old['pressure'] or 'normal'
        tag = f'{seat}/{foe}/{pressure}'
        g = groups.setdefault(tag, {'transitions': Counter(), 'applied': Counter(),
                                    'applied_cards': {'old': Counter(), 'new': Counter()},
                                    'wins_when_applied': Counter(), 'decks': {'old': set(), 'new': set()}})
        before, after = (native.battle_outcome(row['result']) for row in (old, new))
        g['transitions'][f'{before}->{after}'] += 1
        for row, result in ((old, before), (new, after)):
            which = row['arm']
            cards = {x['applied'] for x in row['targeted'] if x['applied']}
            g['applied'][which] += bool(cards)
            g['applied_cards'][which].update(cards)
            g['wins_when_applied'][which] += bool(cards) and result == seat
            opponent = ZOMBIE if seat == PLANT else PLANT
            g['decks'][which].add(tuple(sorted(row['opening']['decks'][opponent])))
        g['applied']['both'] += all(any(x['applied'] for x in row['targeted']) for row in (old, new))
    for name, g in groups.items():
        seat = name.split('/')[0]
        transitions = g['transitions']
        g['old_wins'] = sum(n for k, n in transitions.items() if k.split('->')[0] == seat)
        g['new_wins'] = sum(n for k, n in transitions.items() if k.split('->')[1] == seat)
        g['old_wins_lost'] = sum(n for k, n in transitions.items()
                                if k.split('->')[0] == seat and k.split('->')[1] != seat)
        g['old_timeouts'] = sum(n for k, n in transitions.items() if k.startswith('timeout->'))
        g['new_timeouts'] = sum(n for k, n in transitions.items() if k.endswith('->timeout'))
        g['distinct_opponent_decks'] = {k: len(v) for k, v in g.pop('decks').items()}
    return {'games': len(rows), 'target': total, 'paired': sum(sum(g['transitions'].values())
                                                              for g in groups.values()),
            'groups': groups}


def training_weights(summary):
    weights = dict.fromkeys((*PRESSURES, 'secret', 'support'), 1.0)
    for tag, g in summary['groups'].items():
        seat, _, pressure = tag.split('/')
        if seat == PLANT and pressure in weights:
            for arm in ('old', 'new'):
                losses = g['applied'][arm] - g['wins_when_applied'][arm]
                weights[pressure] += 2.0 * losses / max(1, g['applied'][arm])
    return weights


def run_fit(phase, log_name, until):
    if until <= time.time() or native.STOP.exists():
        return False
    with (RUN / 'models' / (log_name + '.log')).open('w', encoding='utf-8') as log:
        try:
            subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', phase],
                           env={**os.environ, 'DV_THREADS': '4'}, stdout=log, stderr=subprocess.STDOUT,
                           timeout=until - time.time(), check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            native.status('fit-fallback', stage=phase, log=log_name, error=repr(error))
            return False
    return True


def fitted_value(label, until):
    from deckvalue_search import Value, corpus_prior

    native.status('fit-value', checkpoint=label)
    if not run_fit('value', label, until):
        return None
    value = Value()
    prior = corpus_prior(value)
    native.write_atomic(RUN / 'prior.json', {'prior': prior, 'value_sha256': sha(RUN / 'models/value-latest.pt')})
    return value, prior


def collect_actions(frozen, latest, lanes, cutoff, count):
    folder = RUN / 'action-traces'
    seeds = [seed for seed in range(ACTION_SEED, ACTION_SEED + count)
             if not (folder / str(seed) / 'receipt.json').exists()]
    made = count - len(seeds)

    def one(seed):
        selected = dict(zip(native.SIDES, (VariedFastOpponent(latest, seed), VariedFastOpponent(frozen, seed))))
        sc, _, _, _ = native.draft(seed, selected, pressure=PRESSURES[seed % 3] if seed % 2 else None)
        path = folder / str(seed)
        result = native.fight(sc, recording=path)
        return path, {'opening': sc, 'controllers': dict.fromkeys(native.SIDES, 'r22'), 'result': result,
                      'native_build': native.PROFILE['native_build'],
                      'files': {p.name: sha(p) for p in path.glob('*.gz')}}

    def consume(item):
        nonlocal made
        path, receipt = item
        native.write_atomic(path / 'receipt.json', receipt)
        made += 1
        if made % 12 == 0:
            native.status('action-traces', games=made, target=count)

    if seeds and time.time() < cutoff:
        native.status('action-traces', games=made, target=count)
        native.work(seeds, one, consume, lanes, cutoff)
    return made


def run(start, end, cases, lanes, action_count):
    at = lambda h, m: min(end.timestamp(), (start + timedelta(hours=h, minutes=m)).timestamp())
    frozen = native.fast_head(*TRANSFER)
    wave06 = native.fast_head(*REFERENCE)
    if not (RUN / 'preflight.json').exists():
        native.status('preflight')
        native.preflight(frozen)
        sc, _, _, _ = native.draft(native.SMOKE_SEED + 2, {
            PLANT: wave06, ZOMBIE: VariedFastOpponent(frozen, native.SMOKE_SEED + 2)}, pressure='double')
        result = native.fight(sc, recording=RUN / 'preflight-actions')
        native.write_atomic(RUN / 'preflight-night.json', {'opening': sc, 'result': result})
    native.status('armed', starts=start.isoformat())
    while time.time() < start.timestamp():
        native.check_deadline()
        time.sleep(min(20, max(0, start.timestamp() - time.time())))

    first = matrix('wave-06-blind', INITIAL_SEED, cases, TRANSFER, REFERENCE, frozen, lanes, at(1, 26))
    weights = training_weights(first)
    native.write_atomic(RUN / 'sampling-plan.json', {
        'weights': weights, 'source': 'wave-06-blind paired outcomes', 'old_labels_imported': 0,
        'seeds': {'corpus': native.CORPUS_SEED, 'teacher': native.TEACHER_SEED, 'final': FINAL_SEED},
        'controllers': dict.fromkeys(native.SIDES, 'r22')})

    promoted, drafts = REFERENCE, 0
    try:
        corpus = native.sample_corpus(wave06, weights, 420, lanes, at(2, 40))
        value = fitted_value('value-initial', at(3, 0)) if corpus >= 120 else None
        if value:
            model, prior = value
            drafts = native.sample_teacher(0, 750, model, prior, wave06, weights, lanes, at(5, 24),
                                           fast_opponent=lambda seed: VariedFastOpponent(wave06, seed))
            del model, value
        if drafts >= 48 and fitted_value('value-final', at(6, 0)):
            native.status('fit-draft', drafts=drafts, checkpoint='wave-07')
            if run_fit('draft', 'draft-wave-07', at(6, 15)):
                shutil.copy2(RUN / 'models/distill-latest.pt', CANDIDATE[0])
                native.write_atomic(CANDIDATE[1], read(RUN / 'prior.json')['prior'])
                native.fast_head(*CANDIDATE)
                promoted = CANDIDATE
                native.write_atomic(RUN / 'candidate.json', {**bundle_receipt(promoted), 'r2_teacher_drafts': drafts,
                                                              'holdout': 'pending'})
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as error:
        native.status('training-fallback', error=repr(error), drafts=drafts, checkpoint='wave-06')

    control = REFERENCE if promoted == CANDIDATE else TRANSFER
    final = matrix('final-blind', FINAL_SEED, cases, control, promoted, frozen, lanes, at(8, 40))
    if promoted == CANDIDATE:
        receipt = read(RUN / 'candidate.json')
        native.write_atomic(RUN / 'candidate.json', {**receipt, 'holdout': 'complete' if
                            final['games'] == final['target'] else 'partial', 'holdout_pairs': final['paired']})
    action_games = 0
    if final['games'] == final['target']:
        action_games = collect_actions(frozen, native.fast_head(*promoted), lanes, end.timestamp() - 240, action_count)
    native.status('finished', checkpoint=promoted[0].name, r2_teacher_drafts=drafts,
                  initial_pairs=first['paired'], final_pairs=final['paired'], action_games=action_games,
                  final_complete=final['games'] == final['target'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default=START)
    parser.add_argument('--until', default=END)
    parser.add_argument('--cases', type=int, default=24)
    parser.add_argument('--lanes', type=int, default=6)
    parser.add_argument('--action-count', type=int, default=120)
    parser.add_argument('--worker', choices=('value', 'draft'))
    args = parser.parse_args()
    configure_paths()
    if args.worker:
        native.configure()
        native.check_deadline()
        if args.worker == 'value':
            from deckvalue_model import fit
            fit(ensemble=3, epochs=40)
        else:
            from deckvalue_distill import fit
            fit(epochs=26, initial=REFERENCE[0])
        return
    start, end = (datetime.fromisoformat(value) for value in (args.start, args.until))
    if end <= start or args.cases < 1 or args.lanes < 1:
        parser.error('Require an increasing time window and positive cases/lanes')
    with (RUN / 'training.lock').open('a+b') as lock:
        if not lock.tell():
            lock.write(b'x')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            native.setup(end.isoformat())
            native.configure()
            native.check_deadline()
            migrate()
            run(start, end, args.cases, args.lanes, args.action_count)
        except Exception as error:
            native.status('failed', error=repr(error))
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
