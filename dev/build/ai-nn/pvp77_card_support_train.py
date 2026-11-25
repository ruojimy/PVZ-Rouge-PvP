"""Continue PvP77 r4 ranked-seven research from the archived battle and draft heads."""
import argparse
from collections import Counter
from copy import deepcopy
import functools
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import time

from league_data import ROOT, read, sha
import pvp77_deploy_train as battle
import pvp76_ranked_draft_train as native
from pvp77_ranked_draft_night import VariedFastOpponent


PREVIOUS = battle.RUN
RUN = ROOT / 'card-support-pvp77-r4-20261124'
VERSION = battle.VERSION
PLANT, ZOMBIE = native.SIDES
LASER, CROTON, SHIELD, SERVANT = 'plant:激光豆', 'plant:巴豆', 'zombie:盾卫僵尸', 'zombie:克苏鲁之仆'
FOCUS, GUARD = 'secret:聚能', 'zsecret:守卫'
CARDS = (LASER, CROTON, SHIELD, SERVANT, FOCUS, GUARD)
DEPENDENCIES = {FOCUS: LASER, GUARD: SHIELD}
DRAFTS = dict(zip(native.SIDES, (battle.PLANT_DRAFT, battle.ZOMBIE_DRAFT)))
DATA_SEED, HOLDOUT_SEED = 77820000, 77900000
WAVE_SIZE, WAVES, HOLDOUT_CASES = 144, 8, 36
SOURCES = {
    'plant': ROOT / 'ranked-v2-20261120/battle/models/0012-plant-2.json',
    'zombie': ROOT / 'ranked-v2-20261120/battle/models/0000-zombie-r22anchor.json',
    'zombie-evolved': ROOT / 'ranked-day-league-20261120/battle/models/0016-zombie-3.json',
    'position': ROOT / 'ranked-seven-20261120/battle/weights/position.json',
}


def verify_frozen_release(build):
    assert build['version'] == VERSION
    release = read(native.R / 'dist/latest-native-release.json')
    if release['version'] == VERSION:
        path = Path(release['target'])
        assert release['exe_sha256'] == build['release']
    else:
        # Preserve same-version experiment comparisons when the installed release advances.
        path = native.R / 'dist/PvZ-PvP-Native-20261124-pvp77-r4/PvZPvPNative.exe'
        assert (RUN / 'profile.json').exists()
    assert sha(path) == build['release']


def setup():
    profile, build = (read(p / 'native-build.json') for p in (PREVIOUS, RUN))
    verify_frozen_release(build)
    assert build['release'] == profile['release']
    for key in ('fingerprint', 'libraries', 'draft_probe', 'shipped_catalog'):
        assert profile[key] == build[key], key
    for name, digest in build['binaries'].items():
        assert sha(RUN / 'native' / f'{name}.exe') == digest, name
    profile = read(PREVIOUS / 'profile.json')
    assert profile['native_build'] == build['fingerprint']
    assert sha(Path(profile['simulation_atlas'])) == profile['simulation_atlas_sha256']
    assert sha(Path(profile['data_root']) / 'extract/data/_resolved_cards.json') == build['shipped_catalog']
    native.RUN = battle.RUN = RUN
    native.PROFILE_PATH, native.STOP = RUN / 'profile.json', RUN / 'STOP'
    native.EXPECTED_VERSION = VERSION
    profile.update(output=str(RUN), native_dir=str(RUN / 'native'))
    if native.PROFILE_PATH.exists():
        assert read(native.PROFILE_PATH) == profile
    else:
        native.write_atomic(native.PROFILE_PATH, profile)
    native.configure()
    native.check_deadline()
    if not (RUN / 'catalog.json').exists():
        shutil.copyfile(PREVIOUS / 'catalog.json', RUN / 'catalog.json')
    assert sha(PREVIOUS / 'catalog.json') == sha(RUN / 'catalog.json')
    contract = json.loads(subprocess.check_output(
        [exe(), '--model-contract'], timeout=20))
    assert contract['sim_fingerprint'] == build['fingerprint']
    receipt = RUN / 'transfer.json'
    if receipt.exists():
        saved = read(receipt)
        assert saved['contract'] == contract and set(saved['battle']) == set(SOURCES)
        for name, record in saved['battle'].items():
            assert sha(model_path(name)) == record['sha256'] and sha(SOURCES[name]) == record['source_sha256']
        for side, (path, prior) in DRAFTS.items():
            assert saved['draft'][side]['weights_sha256'] == sha(path)
            assert saved['draft'][side]['prior_sha256'] == sha(prior)
    else:
        transfer(contract)


def exe():
    return str(RUN / 'native/position_match.exe')


def model_path(name):
    return RUN / 'models' / f'{name}-inherited.json'


def deploy_candidate(side):
    candidate = read(PREVIOUS / 'candidate.json')['frozen_candidates'][side]
    path = Path(candidate['path'])
    assert sha(path) == candidate['sha256']
    return path, candidate['sha256']


def transfer(contract):
    model_path('plant').parent.mkdir(exist_ok=True)
    manifest = {}
    original_position = sha(SOURCES['position'])
    for name in ('position', 'plant', 'zombie', 'zombie-evolved'):
        source = SOURCES[name]
        body = read(source)
        source_digest = sha(source)
        assert body['sim_fingerprint'] == read(SOURCES['position'])['sim_fingerprint']
        additional = []
        if name == PLANT:
            assert body['format'] == 'pvz-deepset-hybrid-1'
            assert body['feature_version'] == body['policy_version'] == 2
            assert all(body[key] == contract[key] for key in ('rules_hash', 'catalog_hash'))
            old = body['behaviors']
            current = contract['behaviors']
            assert set(old).issubset(current)
            additional = sorted(set(current) - set(old))
            for row in body['unit']['weight']:
                assert len(row) == 16 + len(old)
            body['unit']['weight'] = [
                row[:16] + [row[16 + old.index(key)] if key in old else 0. for key in current]
                for row in body['unit']['weight']
            ]
            body['behaviors'] = current
        if name in (ZOMBIE, 'zombie-evolved'):
            assert body['format'] == 'pvz-event-actions-1'
            for node in (body, body['legacy']):
                assert node['position_parent'] == original_position
                node['position_parent'] = sha(model_path('position'))
                node['sim_fingerprint'] = contract['sim_fingerprint']
        body['sim_fingerprint'] = contract['sim_fingerprint']
        target = model_path(name)
        native.write_atomic(target, body)
        manifest[name] = {'source': str(source), 'source_sha256': source_digest, 'path': str(target),
                          'sha256': sha(target), 'format': body['format'], 'zero_input_columns': additional}
    native.write_atomic(RUN / 'transfer.json', {'battle': manifest, 'contract': contract,
                        'draft': {side: {'weights': str(path), 'weights_sha256': sha(path),
                                         'prior_sha256': sha(prior)}
                                  for side, (path, prior) in DRAFTS.items()}})


def play(folder, name, opening, *, plant=True, zombie=ZOMBIE, laser=True, deploy=None, events=False,
         deploy_model=None, deploy_trace=None, measure=False, retry_slow=False):
    native.check_deadline()
    path = folder / f'{name}.jsonl'
    args = [exe(), '--corpus', str(folder), '--id', '000', '--out', str(path),
            '--limit-seconds', '600', '--control-hz', '15', '--no-records', '--telemetry']
    plant_model = (model_path(PLANT) if plant is True else Path(plant)) if plant else None
    zombie_model = (model_path(zombie) if isinstance(zombie, str) else Path(zombie)) if zombie else None
    if plant:
        args += ['--planner', 'nn', '--nn-seat', PLANT, '--model', str(plant_model)]
    if zombie:
        args += ['--position-model', str(model_path('position')), '--option-model', str(zombie_model)]
    active_deploy = None
    if deploy:
        active_deploy = deploy_model or deploy_candidate(deploy)[0]
        args += ['--deploy-model', str(active_deploy), '--deploy-side', deploy]
    if deploy_trace:
        args += ['--deploy-trace', str(deploy_trace)]
    if laser:
        args += ['--laser-basics']
    log_path = folder / f'{name}-events.jsonl'
    if events:
        args += ['--log', str(log_path)]
    def run_game(wall_seconds):
        return subprocess.run(args, capture_output=True, timeout=max(.1, min(wall_seconds, native.seconds_left())))

    try:
        p = run_game(180.)
    except subprocess.TimeoutExpired:
        native.check_deadline()
        if not retry_slow:
            raise
        print(f'Retrying slow native game seed={opening["seed"]} arm={name}', flush=True)
        p = run_game(420.)
    if p.returncode:
        raise RuntimeError(f'{name}, seed {opening["seed"]}: {p.stderr.decode("utf-8", errors="replace")[-2000:]}')
    head, foot = (json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
    assert head['source_fingerprint'] == native.PROFILE['native_build']
    assert head['ranked_rules']['build'] == VERSION
    assert all(head['ranked_rules'][k] == v for k, v in native.PROFILE['rules'].items())
    assert head['seed'] == opening['seed'] and head['decks'] == opening['decks']
    if plant:
        assert head['model_sha256'] == sha(plant_model)
    if zombie:
        assert head['option_sha256'] == sha(zombie_model)
        assert head['zombie_position_sha256'] == sha(model_path('position'))
    if active_deploy:
        assert head['deploy_controller']['sha256'] == sha(active_deploy)
    assert not foot['ai_error'] and (foot['finished'] or foot['timeout']), foot['ai_error']
    deployments = [e for e in foot['activity'] if e['kind'] == 'deploy']
    summary = {'winner': (foot['result'] or {}).get('winner'), 'timeout': foot['timeout'],
               'seconds': foot['time'], 'log_sha256': foot['log_sha256'], 'planners': head['planners'],
               'hybrid_heads': head.get('hybrid_heads', []), 'laser': foot['laser_basics'],
               'option_switches': len(foot['switches']), 'option_events': len(foot['options']),
               'deploy_policy': foot['deploy_policy'],
               'models': {k: v for k, v in head.items() if k in
                          ('model_sha256', 'zombie_position_sha256', 'option_sha256')},
               'deploys': dict(Counter(e['side'] for e in deployments)),
               'new_card_deploys': dict(Counter(e['card'] for e in deployments if e['card'] in CARDS))}
    if measure:
        activity = {'plant': [], 'troops': [], 'graves': []}
        for e in deployments:
            group = 'plant' if e['side'] == PLANT else 'graves' if e['card'] in zombie_graves() else 'troops'
            activity[group].append(round(30 * e['time']))
        summary['activity_ticks'] = activity
    if events:
        strikes, commands = [], []
        with log_path.open(encoding='utf-8') as log:
            for line in log:
                event = json.loads(line)
                if event.get('event') == 'input' and event.get('kind') in ('laser', 'laser_cancel'):
                    commands.append(event)
                if event.get('event') == 'damage' and event.get('kind') == 'environment':
                    strikes.append(event)
        summary.update(laser_commands=commands, environmental_damage=strikes)
    return summary


@functools.cache
def zombie_graves():
    return frozenset(k for k, card in read(RUN / 'catalog.json')['cards'].items()
                     if card['side'] == ZOMBIE and card['behavior'] == 'grave')


def draft_heads(coverage=True, trained=None):
    from deckvalue_distill import FastDrafter

    return {side: FastDrafter((trained or {}).get(side, path), read(prior), coverage=CARDS if coverage else ())
            for side, (path, prior) in DRAFTS.items()}


class PreferLegal:
    def __init__(self, policy, cards):
        self.policy = policy
        self.cards = cards

    def choose(self, side, action, state, offers):
        if action['kind'] == 'pick':
            for card in self.cards:
                if card in offers:
                    return card
        return self.policy.choose(side, action, state, offers)


def smoke(heads, lanes=4):
    folder = RUN / 'laser-smoke'
    folder.mkdir(exist_ok=True)

    def case(i):
        seed = 77811000 + i
        plant_cards = (LASER, FOCUS, CROTON) if i < 8 else (native.SUNFLOWER, LASER, FOCUS, CROTON)
        policies = {
            PLANT: PreferLegal(VariedFastOpponent(heads[PLANT], seed), plant_cards),
            ZOMBIE: PreferLegal(VariedFastOpponent(heads[ZOMBIE], seed), (SHIELD, GUARD, SERVANT)),
        }
        opening, _, _, _ = native.draft(seed, policies)
        with battle.cold_opening(opening) as cold:
            base = play(cold, 'inherited', opening, laser=False, events=True)
            candidate = play(cold, 'laser', opening, events=True)
        return i, {'opening': opening, 'base': base, 'laser': candidate}

    def save(item):
        i, result = item
        native.write_atomic(folder / f'{i:02}.json', result)
        print('smoke', i, result['laser']['laser'], result['laser']['winner'], flush=True)

    indices = (5, 8, 9, 10, 0, 1, 2, 3)
    native.work((i for i in indices if not (folder / f'{i:02}.json').exists()), case, save,
                lanes, time.time() + 360)
    rows = [read(path) for path in sorted(folder.glob('[0-9]*.json'))]
    assert rows and any(r['laser']['laser']['beam_pulses'] > 0 for r in rows), 'laser never fired'
    return rows


class RecordAlternative:
    def __init__(self, policy, card):
        self.policy = PreferLegal(policy, (DEPENDENCIES[card],)) if card in DEPENDENCIES else policy
        self.card = card
        self.decisions = []

    def choose(self, side, action, state, offers):
        default = self.policy.choose(side, action, state, offers)
        if action['kind'] == 'pick' and self.card in offers and default != self.card:
            self.decisions.append({'step': state['step'], 'action': action, 'offers': list(offers),
                                   'state': {k: deepcopy(state[k]) for k in ('decks', 'bans')},
                                   'default': default, 'alternate': self.card})
        return default


def branches(index, heads):
    seed = DATA_SEED + index
    card = CARDS[index % len(CARDS)]
    side = PLANT if card.startswith(('plant:', 'secret:')) else ZOMBIE
    foe = ZOMBIE if side == PLANT else PLANT
    pressure = (None, 'economy', 'late', 'support')[index // len(CARDS) % 4]
    policies = {s: VariedFastOpponent(heads[s], seed) for s in native.SIDES}
    if index // len(CARDS) % 3 == 1:
        policies[foe] = 'builtin'
    selector = RecordAlternative(policies[side], card)
    policies[side] = selector
    base, _, _, _ = native.draft(seed, policies, pressure=pressure)
    note = {'index': index, 'seed': seed, 'side': side, 'card': card, 'pressure': pressure}
    if not selector.decisions:
        return note
    pick = random.Random(seed).choice(selector.decisions)
    step = pick['step']
    prefix = [action['card'] for action in base['draft_history'][:step]]
    forced = {**dict(enumerate(prefix)), step: card}
    policies[side] = selector.policy
    changed, _, _, _ = native.draft(seed, policies, pressure=pressure, force=forced)
    assert [a['card'] for a in changed['draft_history'][:step]] == prefix
    assert base['draft_history'][step]['card'] == pick['default']
    assert changed['draft_history'][step]['card'] == card and card in changed['decks'][side]
    assert changed['terrain_hash'] == base['terrain_hash']
    note['decision'] = pick
    for tag, opening in (('base', base), ('alternate', changed)):
        try:
            with battle.cold_opening(opening) as path:
                note[tag] = {'opening': opening, 'game': play(path, tag, opening, retry_slow=True)}
        except subprocess.TimeoutExpired as exc:
            native.check_deadline()
            note['unresolved_decision'] = note.pop('decision')
            note['wall_timeout'] = {'arm': tag, 'seconds': exc.timeout, 'opening': opening}
            break
    return note


def draft_fit(rows, heads, wave):
    """Fit just the six card embeddings against actual paired outcomes."""
    import torch
    import torch.nn.functional as functional

    results = {}
    for side in native.SIDES:
        reference = heads[side]
        examples = []
        for row in rows:
            if row['side'] != side or 'decision' not in row:
                continue
            old, alt = (native.battle_outcome(row[tag]['game']) for tag in ('base', 'alternate'))
            utility = {side: 1., 'timeout': -.15}
            difference = utility.get(alt, 0.) - utility.get(old, 0.)
            if not difference:
                continue
            decision = row['decision']
            state = decision['state']
            feature = reference.enc.encode(side, decision['action']['stage'], 'pick', state['decks'], state['bans'],
                                           [decision['default'], decision['alternate']])
            examples.append((feature, float(difference > 0.), abs(difference), row['index']))
        if not examples:
            continue
        train = [r for r in examples if r[3] % 11 != 0]
        val = [r for r in examples if r[3] % 11 == 0]
        if not train:
            continue
        net = deepcopy(reference.net)
        for parameter in net.parameters():
            parameter.requires_grad_(False)
        net.embed.requires_grad_(True)
        initial = net.embed.detach().clone()
        editable = {reference.vocab.index[row['card']] for row in rows if row['side'] == side}
        frozen = [i for i in range(len(initial)) if i not in editable]
        optimizer = torch.optim.Adam([net.embed], lr=.004)

        def pair_loss(batch):
            features, target, weights, _ = zip(*batch)
            pred = torch.stack([x[1] - x[0] for x in net(features)])
            return functional.binary_cross_entropy_with_logits(pred, pred.new_tensor(target),
                                                                weight=pred.new_tensor(weights))

        with torch.no_grad():
            before = float(pair_loss(val or train))
        for epoch in range(15):
            batch = train.copy()
            random.Random(epoch + 77).shuffle(batch)
            for offset in range(0, len(batch), 32):
                optimizer.zero_grad()
                loss = pair_loss(batch[offset:offset+32]) + .3 * (net.embed - initial).square().sum()
                loss.backward()
                net.embed.grad[frozen] = 0.
                optimizer.step()
        with torch.no_grad():
            after = float(pair_loss(val or train))
        assert torch.equal(net.embed[frozen], initial[frozen])
        path = RUN / 'models' / f'{side}-draft-wave{wave:02}.pt'
        tmp = path.with_suffix('.partial')
        torch.save({'keys': reference.vocab.keys, 'state': net.state_dict()}, tmp)
        os.replace(tmp, path)
        native.write_atomic(path.with_suffix('.json'), {
            'match_pairs': len(examples), 'train': len(train), 'validation': len(val),
            'loss_before': before, 'loss_after': after, 'sha256': sha(path), 'parent': sha(DRAFTS[side][0]),
            'trainable_embeddings': [reference.vocab.keys[i] for i in sorted(editable)],
        })
        results[side] = path
    return results


def collect(heads, lanes):
    folder = RUN / 'native-pairs'
    folder.mkdir(exist_ok=True)
    rows = {int(path.stem): read(path) for path in folder.glob('*.json')}

    def save(row):
        index = row['index']
        native.write_atomic(folder / f'{index:05}.json', row)
        rows[index] = row
        if len(rows) % 8 == 0:
            native.status('paired-draft', receipts=len(rows), tested=dict(Counter(
                r['card'] for r in rows.values() if 'decision' in r)))
        if not len(rows) % 16 and sum(p.stat().st_size for p in folder.glob('*.json')) > 256 * 1024**2:
            raise RuntimeError('paired draft evidence exceeded 256 MiB')

    latest = {}
    cutoff = native.DEADLINE - 2700
    for wave in range(1, WAVES + 1):
        limit = wave * WAVE_SIZE
        native.work((i for i in range(limit - WAVE_SIZE, limit) if i not in rows),
                    lambda i: branches(i, heads), save, lanes, cutoff)
        latest.update(draft_fit([v for i, v in sorted(rows.items()) if i < limit], heads, wave))
        native.status('draft-fit', wave=wave, receipts=len(rows),
                      models={seat: str(path) for seat, path in latest.items()})
        if time.time() >= cutoff or native.STOP.exists():
            break
    return latest


def evaluate(heads, learned, lanes):
    folder = RUN / 'holdout'
    folder.mkdir(exist_ok=True)
    trained = draft_heads(trained=learned)
    original = draft_heads(coverage=False)
    holdout_play = functools.partial(play, retry_slow=True)
    plan = {
        'seed_base': HOLDOUT_SEED, 'openings_per_seat': HOLDOUT_CASES, 'mode': native.PROFILE['rules'],
        'checkpoints': {side: sha(path) for side, path in learned.items()},
        'conditions': ['normal', 'economy', 'late'], 'architecture_cases_per_seat': 12,
        'deploy_input_sha256': {side: deploy_candidate(side)[1] for side in native.SIDES},
    }
    if (folder / 'plan.json').exists():
        assert read(folder / 'plan.json') == plan, 'holdout already bound to different checkpoints'
    else:
        native.write_atomic(folder / 'plan.json', plan)

    def draft_case(job):
        side, j = job
        seed = HOLDOUT_SEED + j
        foe = ZOMBIE if side == PLANT else PLANT
        opponent = 'builtin' if j % 4 == 1 else VariedFastOpponent(heads[foe], seed)
        pressure = (None, 'economy', 'late')[j % 3]
        results = {}
        for name, head in (('archived', original[side]), ('inherited-expanded', heads[side]), ('warm', trained[side])):
            opening, _, _, _ = native.draft(seed, {side: head, foe: opponent}, pressure=pressure)
            if results:
                assert opening['terrain_hash'] == results['archived']['opening']['terrain_hash']
            same = next((arm['game'] for arm in results.values()
                         if all(arm['opening'][key] == opening[key] for key in ('decks', 'bans'))), None)
            if same is None:
                with battle.cold_opening(opening) as cold:
                    same = holdout_play(cold, name, opening)
            results[name] = {'opening': opening, 'game': same}
        return folder / f'draft-{side}-{j:02}.json', {'side': side, 'seed': seed, 'pressure': pressure, 'arms': results}

    def architecture_case(j):
        seed = HOLDOUT_SEED + 1000 + j
        opening, _, _, _ = native.draft(seed, {s: VariedFastOpponent(heads[s], seed) for s in native.SIDES})
        with battle.cold_opening(opening) as cold:
            base = holdout_play(cold, 'r22', opening, plant=False, zombie=None, laser=False)
            current = holdout_play(cold, 'both-inherited', opening, laser=False)
            old_plant = holdout_play(cold, 'inherited-plant', opening, zombie=None, laser=False)
            old_zombie = holdout_play(cold, 'inherited-zombie', opening, plant=False, laser=False)
            evolved_zombie = holdout_play(cold, 'evolved-zombie', opening, plant=False, zombie='zombie-evolved', laser=False)
            new = {side: holdout_play(cold, f'deploy-{side}', opening, plant=False, zombie=None, laser=False, deploy=side)
                   for side in native.SIDES}
        return folder / f'architecture-{j:02}.json', {
            'opening': opening, 'games': {'r22': base, 'both-inherited': current,
                                         'plant': old_plant, 'zombie': old_zombie,
                                         'zombie-evolved': evolved_zombie, 'deploy': new},
        }

    def save(item):
        path, row = item
        native.write_atomic(path, row)

    def attempt(run, job):
        try:
            return run(job)
        except subprocess.TimeoutExpired as exc:
            native.check_deadline()
            return (folder / 'wall-timeouts' / f'{run.__name__}-{job}.json',
                    {'job': job, 'wall_limit_seconds': exc.timeout})

    native.status('architecture-holdout')
    native.work((j for j in range(12) if not (folder / f'architecture-{j:02}.json').exists()),
                lambda j: attempt(architecture_case, j), save, lanes, native.DEADLINE - 60)
    native.status('draft-holdout')
    native.work(((side, j) for j in range(HOLDOUT_CASES) for side in learned
                 if not (folder / f'draft-{side}-{j:02}.json').exists()),
                lambda job: attempt(draft_case, job), save, lanes, native.DEADLINE - 60)
    report = {}
    for side in native.SIDES:
        rows = [read(p) for p in sorted(folder.glob(f'draft-{side}-*.json'))]
        report[side] = {
            name: {**summary_games(side, [r['arms'][name]['game'] for r in rows]),
                   'distinct_decks': len({tuple(sorted(r['arms'][name]['opening']['decks'][side])) for r in rows}),
                   'new_card_picks': dict(Counter(card for r in rows for card in r['arms'][name]['opening']['decks'][side]
                                                  if card in CARDS))}
            for name in ('archived', 'inherited-expanded', 'warm')
        }
    arch = [read(p)['games'] for p in sorted(folder.glob('architecture-*.json'))]
    report['architecture'] = {
        side: {'r22': summary_games(side, [a['r22'] for a in arch]),
               'inherited': summary_games(side, [a[side] for a in arch]),
               'deploy_only': summary_games(side, [a['deploy'][side] for a in arch])}
        for side in native.SIDES
    }
    report['architecture'][ZOMBIE]['inherited_evolved'] = summary_games(ZOMBIE, [a['zombie-evolved'] for a in arch])
    native.write_atomic(folder / 'summary.json', report)
    return report


def summary_games(side, results):
    return {'games': len(results), 'wins': sum(native.battle_outcome(g) == side for g in results),
            'timeouts': sum(g['timeout'] for g in results),
            'mean_seconds': sum(g['seconds'] for g in results) / len(results) if results else None,
            'deployments': sum(g['deploys'].get(side, 0) for g in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['smoke', 'train'])
    parser.add_argument('--lanes', type=int, default=4)
    args = parser.parse_args()
    setup()
    import torch

    torch.set_num_threads(1)
    heads = draft_heads()
    preflight = smoke(heads, args.lanes)
    if args.mode == 'train':
        outcomes = {arm: summary_games(PLANT, [row[arm] for row in preflight]) for arm in ('base', 'laser')}
        native.write_atomic(RUN / 'plan.json', {
            'version': VERSION, 'rules': native.PROFILE['rules'], 'deadline': native.PROFILE['deadline'],
            'controller': 'inherited battle heads plus tutorial-based laser operations',
            'preflight': outcomes, 'cards': list(CARDS), 'seed_base': DATA_SEED,
            'planned_pairs': WAVES * WAVE_SIZE, 'draft_head_changes': 'target card embeddings only',
            'opening_source': native.PROFILE['opening_source'],
        })
        native.status('paired-draft', receipts=0, lanes=args.lanes)
        try:
            candidates = collect(heads, args.lanes)
            if not native.STOP.exists():
                evaluate(heads, candidates, args.lanes)
            native.status('stopped' if native.STOP.exists() else 'finished',
                          candidate_sides=list(candidates), holdout=(RUN / 'holdout/summary.json').exists())
        except Exception as exc:
            native.status('failed', error=repr(exc))
            raise


if __name__ == '__main__':
    main()
