"""Train a plant-only override from paired native r2 draft continuations."""
import argparse
from collections import Counter
import ctypes
from datetime import datetime, timedelta, timezone
import msvcrt
import os
from pathlib import Path
import random
import shutil
import time

import pvp76_ranked_draft_train as native
import pvp77_ranked_draft_night as night
from league_data import read, sha


SOURCE = night.RUN
RUN = SOURCE / 'plant-refine-20261124'
REFERENCE, OPPONENT = night.REFERENCE, night.CANDIDATE
MODEL = RUN / 'models/plant-picks.pt'
CATALOG = SOURCE / 'catalog.json'
DATA_SEED, HOLDOUT_SEED = 76600000, 76700000
PLANT, ZOMBIE = native.SIDES
PROTECTED = (native.CABBAGE, native.CABBAGE_SECRET)
THRESHOLD = 0.24
TRAIN_CASES = 180
BLIND_CASES = 24
HZ_OFFSET = timezone(timedelta(hours=8))


def configure():
    night.configure_paths()
    native.RUN, night.RUN = RUN, RUN
    native.PROFILE_PATH = RUN / 'profile.json'
    native.STOP = RUN / 'STOP'
    source = read(SOURCE / 'profile.json')
    release = read(native.R / 'dist/latest-native-release.json')
    build = read(SOURCE / 'native-build.json')
    assert source['version'] == release['version'] == native.EXPECTED_VERSION
    assert build['release'] == release['exe_sha256'] == sha(Path(release['target']))
    assert source['native_build'] == build['fingerprint']
    assert all(sha(Path(source['native_dir']) / (name + '.exe')) == digest
               for name, digest in build['binaries'].items())
    assert sha(Path(source['simulation_atlas'])) == source['simulation_atlas_sha256']
    plan = read(SOURCE / 'final-blind/plan.json')
    assert plan['old'] == night.bundle_receipt(REFERENCE) and plan['new'] == night.bundle_receipt(OPPONENT)
    if not native.PROFILE_PATH.exists():
        now = datetime.now(HZ_OFFSET)
        source.update(output=str(RUN), deadline=(now + timedelta(hours=4)).isoformat(timespec='seconds'),
                      sample_until=(now + timedelta(hours=2, minutes=15)).isoformat(timespec='seconds'))
        native.write_atomic(native.PROFILE_PATH, source)
    profile = read(native.PROFILE_PATH)
    assert profile['native_build'] == source['native_build']
    if not (RUN / 'catalog.json').exists():
        shutil.copy2(CATALOG, RUN / 'catalog.json')
    assert sha(RUN / 'catalog.json') == sha(CATALOG)
    native.configure()
    native.check_deadline()
    native.write_atomic(RUN / 'plan.json', {
        'study': 'plant pick override only', 'reference': plan['old'], 'opponent': plan['new'],
        'candidate_threshold': THRESHOLD, 'data_seed_base': DATA_SEED, 'holdout_seed_base': HOLDOUT_SEED,
        'conditions': ['economy', 'late', 'normal'], 'collection_cases': TRAIN_CASES,
        'blind_cases_per_group': BLIND_CASES, 'controllers': dict.fromkeys(native.SIDES, 'r22'),
        'opening_source': profile['opening_source'],
    })


class PlantDecisions:
    """Select public-state opportunities for an alternate pick."""
    def __init__(self, reference, cards):
        self.reference = reference
        self.producers = {card for card, c in cards.items() if c['side'] == PLANT and c.get('producer')}

    def alternatives(self, action, state, offers, default):
        if action['side'] != PLANT or action['kind'] != 'pick':
            return None, []
        deck = state['decks'][PLANT]
        if native.SUNFLOWER in state['bans'] and self.producers.isdisjoint(deck):
            return 'economy', [card for card in offers if card in self.producers and card != default]
        if action['stage'] != 'opening_pick' or any(card in deck for card in PROTECTED):
            return None, []
        legal_protection = [card for card in PROTECTED if card in offers]
        if default in legal_protection:
            other = [card for card in offers if card not in PROTECTED]
            return 'protection', self.reference.rank_choices(PLANT, action, state, other, 3) if other else []
        return 'protection', legal_protection


class RecordPicks:
    def __init__(self, rules):
        self.rules = rules
        self.decisions = []

    def choose(self, side, action, state, offers):
        default = self.rules.reference.choose(side, action, state, offers)
        reason, alternatives = self.rules.alternatives(action, state, offers, default)
        if alternatives:
            self.decisions.append({'step': state['step'], 'reason': reason, 'action': action,
                                   'state': {'decks': state['decks'], 'bans': state['bans']},
                                   'default': default, 'alternatives': alternatives})
        return default


def collect_case(index, rules, fast_opponent):
    seed = DATA_SEED + index
    pressure = ('economy', 'late', 'economy', None, 'late', 'economy')[index % 6]
    foe = 'builtin' if (index // 6 + index) % 2 else 'fast'
    opponent = foe if foe == 'builtin' else night.VariedFastOpponent(fast_opponent, seed)
    recorder = RecordPicks(rules)
    opening, _, targeted, _ = native.draft(seed, {PLANT: recorder, ZOMBIE: opponent}, pressure=pressure)
    reason = 'economy' if pressure == 'economy' else 'protection'
    options = [pick for pick in recorder.decisions if pick['reason'] == reason]
    if not options:
        return {'seed': seed, 'pressure': pressure, 'opponent': foe, 'eligible': False}
    rng = random.Random(seed)
    decision = rng.choice(options[:3])
    alternate = rng.choice(decision['alternatives'])
    step = decision['step']
    prefix = [r['card'] for r in opening['draft_history'][:step]]
    forced = {**dict(enumerate(prefix)), step: alternate}
    changed, _, changed_bans, _ = native.draft(seed, {PLANT: rules.reference, ZOMBIE: opponent},
                                               pressure=pressure, force=forced)
    assert [r['card'] for r in changed['draft_history'][:step]] == prefix
    assert opening['draft_history'][step]['card'] == decision['default']
    assert changed['draft_history'][step]['card'] == alternate
    assert opening['terrain_hash'] == changed['terrain_hash']
    return {'seed': seed, 'pressure': pressure, 'opponent': foe, 'eligible': True,
            **decision, 'alternate': alternate, 'prefix': prefix,
            'base': {'opening': opening, 'targeted': targeted, 'result': native.fight(opening)},
            'alternate_game': {'opening': changed, 'targeted': changed_bans, 'result': native.fight(changed)}}


def collect(rules, opponent, lanes, cutoff):
    folder = RUN / 'training-pairs'
    folder.mkdir(exist_ok=True)
    rows = {int(path.stem): read(path) for path in folder.glob('*.json')}

    def consume(item):
        index, row = item
        native.write_atomic(folder / f'{index:04}.json', row)
        rows[index] = row
        if len(rows) % 12 == 0:
            native.status('plant-pairs', collected=len(rows), target=TRAIN_CASES,
                          eligible=sum(r['eligible'] for r in rows.values()))

    native.status('plant-pairs', collected=len(rows), target=TRAIN_CASES)
    native.work((i for i in range(TRAIN_CASES) if i not in rows),
                lambda i: (i, collect_case(i, rules, opponent)), consume, lanes, cutoff)
    return [row for _, row in sorted(rows.items()) if row['eligible']]


def fit(rows, reference):
    import torch
    import torch.nn.functional as F
    from deckvalue_distill import Fast

    torch.manual_seed(77)
    utility = {PLANT: 1.0, ZOMBIE: 0.0, 'timeout': -0.15}
    partitions = {'train': [], 'validation': []}
    for row in rows:
        before, after = (native.battle_outcome(row[key]['result']) for key in ('base', 'alternate_game'))
        state = row['state']
        encoded = reference.enc.encode(PLANT, row['action']['stage'], 'pick', state['decks'], state['bans'],
                                       [row['default'], row['alternate']])
        bucket = 'validation' if (row['seed'] - DATA_SEED) % 5 == 0 else 'train'
        partitions[bucket].append((encoded, utility[after] - utility[before]))
    train, validation = partitions['train'], partitions['validation']
    if sum(y != 0 for _, y in train) < 8 or not validation:
        raise RuntimeError('Too few informative native pairs to fit a plant draft override')
    net = Fast(reference.vocab)
    net.load_state_dict(reference.net.state_dict())
    net.embed.requires_grad_(False)
    net.card.requires_grad_(False)
    optim = torch.optim.AdamW([*net.ctx.parameters(), *net.score.parameters()], lr=0.0004)

    def predictions(items):
        outputs = net([encoded for encoded, _ in items])
        return torch.stack([v[1] - v[0] for v in outputs])

    def labels(items):
        return torch.tensor([y for _, y in items], dtype=torch.float32)

    best = None
    expected = labels(validation)
    for epoch in range(24):
        shuffled = train.copy()
        random.Random(epoch).shuffle(shuffled)
        for start in range(0, len(shuffled), 32):
            batch = shuffled[start:start + 32]
            targets = labels(batch)
            loss = F.smooth_l1_loss(predictions(batch), targets, beta=0.25, reduction='none')
            loss = (loss * torch.where(targets == 0, 0.4, 1.0)).mean()
            optim.zero_grad()
            loss.backward()
            optim.step()
        with torch.no_grad():
            estimate = predictions(validation)
            switches = estimate > THRESHOLD
            gain = float(expected[switches].sum())
            error = float(F.smooth_l1_loss(estimate, expected, beta=0.25))
        score = (gain, -error)
        if best is None or score > best[0]:
            best = (score, {k: v.clone() for k, v in net.state_dict().items()}, epoch, int(switches.sum()))
    score, state, epoch, switches = best
    MODEL.parent.mkdir(exist_ok=True)
    temp = MODEL.with_suffix('.partial')
    torch.save({'state': state, 'keys': reference.vocab.keys}, temp)
    os.replace(temp, MODEL)
    audit = {'paired': len(rows), 'conditions': dict(Counter(r['pressure'] or 'normal' for r in rows)),
             'train': len(train), 'validation': len(validation),
             'nonzero_train': sum(y != 0 for _, y in train), 'best_epoch': epoch + 1,
             'validation_switches': switches, 'validation_utility_gain': score[0]}
    native.write_atomic(RUN / 'fit.json', audit)
    return audit


class PlantOverride:
    def __init__(self, path, prior, reference, rules):
        self.model = native.fast_head(path, prior)
        self.reference = reference
        self.rules = rules

    def choose(self, side, action, state, offers):
        import torch

        default = self.reference.choose(side, action, state, offers)
        _, alternatives = self.rules.alternatives(action, state, offers, default)
        if not alternatives:
            return default
        enc = self.model.enc.encode(side, action['stage'], 'pick', state['decks'], state['bans'],
                                    [default, *alternatives])
        with torch.no_grad():
            scores = self.model.net([enc])[0]
            index = int(scores[1:].argmax()) + 1
            return alternatives[index - 1] if float(scores[index] - scores[0]) > THRESHOLD else default


def run(lanes):
    from deckvalue_model import catalog

    reference = native.fast_head(*REFERENCE)
    opponent = native.fast_head(*OPPONENT)
    rules = PlantDecisions(reference, catalog()['cards'])
    cutoff = datetime.fromisoformat(native.PROFILE['sample_until']).timestamp()
    rows = collect(rules, opponent, lanes, cutoff)
    native.status('plant-fit', paired=len(rows), target=TRAIN_CASES)
    trained = fit(rows, reference)
    variant = {'scope': 'plant-only override of first economy pick or opening precursor protection',
               'threshold': THRESHOLD, 'baseline_prior_for_both_arms': True}
    summary = night.matrix('plant-blind', HOLDOUT_SEED, BLIND_CASES, REFERENCE, (MODEL, REFERENCE[1]),
                           opponent, lanes, native.DEADLINE - 240, opponent_bundle=OPPONENT,
                           stages=[(PLANT, condition) for condition in (None, *night.PRESSURES)],
                           load_new=lambda path, prior: PlantOverride(path, prior, reference, rules),
                           variant=variant)
    groups = summary['groups']
    complete = summary['games'] == summary['target']
    gain = lambda g: g['new_wins'] - g['old_wins']
    economy_gain = sum(gain(g) for name, g in groups.items() if name.endswith('/economy'))
    normal_holds = all(gain(g) >= 0 for name, g in groups.items() if name.endswith('/normal'))
    double_holds = all(gain(g) >= 0 for name, g in groups.items() if name.endswith('/double'))
    late_holds = all(g['applied']['new'] <= g['applied']['old'] and gain(g) >= 0
                     for name, g in groups.items() if name.endswith('/late'))
    admitted = complete and economy_gain > 0 and normal_holds and double_holds and late_holds
    native.write_atomic(RUN / 'candidate.json', {
        **night.bundle_receipt((MODEL, REFERENCE[1])), 'reference': night.bundle_receipt(REFERENCE),
        'variant': variant, 'fit': trained, 'holdout_complete': complete, 'holdout_pairs': summary['paired'],
        'economy_gain': economy_gain, 'normal_holds': normal_holds, 'double_holds': double_holds,
        'late_holds': late_holds, 'admitted': admitted,
    })
    native.status('finished', holdout_complete=complete, holdout_pairs=summary['paired'],
                  admitted=admitted, economy_gain=economy_gain)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lanes', type=int, default=6)
    args = parser.parse_args()
    if args.lanes < 1:
        parser.error('--lanes must be positive')
    RUN.mkdir(exist_ok=True)
    with (RUN / 'training.lock').open('a+b') as lock:
        if not lock.tell():
            lock.write(b'x')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            configure()
            run(args.lanes)
        except Exception as error:
            native.status('failed', error=repr(error))
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
