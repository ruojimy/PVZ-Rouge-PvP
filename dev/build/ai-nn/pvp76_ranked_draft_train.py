"""PvP76 r3 ranked-seven draft comparisons and training. Battle control is r22 on both seats."""
import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import ctypes
from datetime import datetime
import gzip
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zlib

from league_data import R, ROOT, read, sha

RUN = ROOT / 'deck-value-pvp76-r3-20261123'
PREVIOUS = ROOT / 'deck-value-pvp75-20261121'
PROFILE_PATH = RUN / 'profile.json'
HOME = '家院'
PLANT = 'plant'
ZOMBIE = 'zombie'
SIDES = (PLANT, ZOMBIE)
EXPECTED_VERSION = '1.6.0.76-typed.20261123-r3'
ATLAS = RUN / 'simulation-atlas.bin'
BASELINE_SEED = 76031000
CORPUS_SEED = 76040000
TEACHER_SEED = 76080000
HOLDOUT_SEED = 76130000
SMOKE_SEED = 76030000
DEADLINE = float('inf')
STOP = RUN / 'STOP'
TOP_PLANT = ['plant:花盆', 'plant:向日葵', 'secret:卷心菜', 'plant:卷心菜投手',
             'plant:甜椒投手', 'secret:尖刺', 'plant:仙人掌']
SUNFLOWER, CABBAGE_SECRET, CABBAGE, PEPPER, SPIKE, CACTUS = TOP_PLANT[1:]
PRESSURE = {
    'economy': {'opening_ban': (SUNFLOWER,)},
    'precursor': {'opening_ban': (CABBAGE,)},
    'secret': {'opening_ban': (CABBAGE_SECRET,)},
    'support': {'opening_ban': (PEPPER, SPIKE)},
    'late': {'second_ban': (CABBAGE, CABBAGE_SECRET)},
    'combo': {'opening_ban': (SUNFLOWER, CABBAGE), 'second_ban': (SPIKE, PEPPER, CACTUS)},
}
PROFILE = {}
V0 = RUN / 'models' / 'fast-transferred.pt'
FLASH_PRIOR = RUN / 'models' / 'prior-transferred.json'


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def status(phase, **details):
    stamp = datetime.now().isoformat(timespec='seconds')
    state = {'phase': phase, 'updated': stamp, 'deadline': PROFILE.get('deadline'), **details}
    write_atomic(RUN / 'status.json', state)
    with (RUN / 'events.jsonl').open('a', encoding='utf-8') as file:
        file.write(json.dumps(state, ensure_ascii=False) + '\n')
    print(json.dumps(state, ensure_ascii=False), flush=True)


def setup(until):
    release = read(R / 'dist' / 'latest-native-release.json')
    build = read(RUN / 'native-build.json')
    assert build['version'] == release['version'] == EXPECTED_VERSION
    assert build['release'] == release['exe_sha256'] == sha(Path(release['target']))
    assert build['release'] == sha(Path(release['release']) / 'PvZPvPNative.exe')
    assert all(sha(RUN / 'native' / (name + '.exe')) == digest
               for name, digest in build['binaries'].items())
    data_root = RUN / 'data'
    data_root.mkdir(exist_ok=True)
    for name in ('extract', '图片', 'fonts', '音乐', '音效'):
        if not (data_root / name).is_dir():
            copy = data_root / (name + '.incoming')
            shutil.copytree(Path(release['release']) / name, copy, dirs_exist_ok=True)
            copy.rename(data_root / name)
    assert sha(data_root / 'extract' / 'data' / '_resolved_cards.json') == build['shipped_catalog']
    previous = read(PREVIOUS / 'profile.json')
    profile = {
        'version': EXPECTED_VERSION, 'native_build': build['fingerprint'],
        'output': str(RUN), 'native_dir': str(RUN / 'native'), 'data_root': str(data_root),
        'home': HOME, 'day_league': True, 'weather': 'clear', 'night': False,
        'weights_dir': previous['weights_dir'], 'reference': 'r22', 'draft_v2': True,
        'deadline': until, 'rules': {'ranked': True, 'extra_slot': False, 'plant_slots': 7, 'zombie_slots': 7},
        'opening_source': f'{EXPECTED_VERSION} native Room._start_bans -> pick/ban -> cold73_export -> typed Session',
        'builtin_draft_seeds': {'plant': '2 * opening_seed + 1', 'zombie': '2 * opening_seed + 2'},
    }
    if PROFILE_PATH.exists():
        existing = read(PROFILE_PATH)
        assert existing['native_build'] == profile['native_build']
        if existing.get('simulation_atlas'):
            profile.update({k: existing[k] for k in ('simulation_atlas', 'simulation_atlas_sha256')})
    write_atomic(PROFILE_PATH, profile)


def configure():
    global PROFILE, DEADLINE
    PROFILE = read(PROFILE_PATH)
    DEADLINE = datetime.fromisoformat(PROFILE['deadline']).timestamp()
    os.environ.update(DV_RUN=str(RUN), PVZ_RANKED_PROFILE=str(PROFILE_PATH),
                      DV_THREADS=os.environ.get('DV_THREADS', '1'))


def seconds_left():
    return DEADLINE - time.time()


def check_deadline():
    if seconds_left() <= 0 or STOP.exists():
        raise TimeoutError('training cutoff or STOP')


def transfer_head():
    transfer_checkpoint(PREVIOUS / 'models' / 'distill-latest.pt', PREVIOUS / 'prior.json',
                        V0, FLASH_PRIOR, RUN / 'transfer.json')


def transfer_checkpoint(old_path, old_prior, target, target_prior, receipt):
    """Preserve shared card embeddings and refresh descriptors from the active card catalog."""
    import torch
    from deckvalue_distill import Fast
    from deckvalue_model import Vocab

    if target.exists() and target_prior.exists() and receipt.exists():
        stamp = read(receipt)
        assert stamp['weights_sha256'] == sha(old_path) and stamp['prior_sha256'] == sha(old_prior)
        assert stamp['transferred_sha256'] == sha(target)
        return
    target.parent.mkdir(exist_ok=True)
    source = torch.load(old_path, map_location='cpu', weights_only=False)
    prior = read(old_prior)
    prior = prior.get('prior', prior)
    vocab = Vocab()
    torch.manual_seed(763)
    net = Fast(vocab)
    state = source['state']
    old_index = {key: i for i, key in enumerate(source['keys'])}
    embedding = net.embed.detach().clone()
    for key, i in vocab.index.items():
        if key in old_index:
            embedding[i] = state['embed'][old_index[key]]
    embedding[-1] = state['embed'][-1]
    net.load_state_dict({**state, 'embed': embedding, 'fixed': net.fixed})
    temp = target.with_suffix('.partial')
    torch.save({'keys': vocab.keys, 'state': net.state_dict()}, temp)
    os.replace(temp, target)
    train_prior = {key: prior.get(key, 0.0) for key in vocab.keys}
    write_atomic(target_prior, train_prior)
    write_atomic(receipt, {
        'weights_sha256': sha(old_path), 'prior_sha256': sha(old_prior), 'transferred_sha256': sha(target),
        'shared_cards': len(set(old_index) & set(vocab.keys)),
        'new_cards': sorted(set(vocab.keys) - set(old_index)),
        'retired_cards': sorted(set(old_index) - set(vocab.keys)),
    })


def fast_head(path=V0, prior_path=FLASH_PRIOR):
    from deckvalue_distill import FastDrafter

    return FastDrafter(path=path, prior=read(prior_path))


def desired_bans(pressure, action):
    if pressure and action['side'] == ZOMBIE and action['kind'] == 'ban':
        return [c for c in PRESSURE[pressure].get(action['stage'], ())
                if c.startswith('secret:') == (action['category'] == 'secret')]
    return []


def draft(seed, policies, pressure=None, force=None, noise=0.0):
    """Play only legal native turns and record the public prefix before each decision."""
    from deckvalue_search import keys_for
    from ranked_draft import Room, check_game

    room = Room()
    notes, prefix, targeted, fallbacks = [], [], [], []
    try:
        state = room.request(op='start', seed=seed, map=HOME, night=False, weather='clear')
        terrain = state['terrain']
        while state['action'] is not None:
            check_deadline()
            action = state['action']
            side, kind, stage = (action[k] for k in ('side', 'kind', 'stage'))
            keys = keys_for(room.catalog['cards'], action)
            if kind == 'ban':
                keys.append(None)
            offers = room.request(op='legal', keys=keys, count=len(keys))
            if not offers:
                raise RuntimeError(f'no native legal action on seed {seed}, step {state["step"]}')
            policy = policies[side]
            target = None
            desired = desired_bans(pressure, action)
            if desired:
                protected = set(state['decks'][PLANT])
                protected.update(room.catalog['cards'][c].get('dependency') for c in state['decks'][PLANT])
                target = next((c for c in desired if c in offers), None)
                targeted.append({'step': state['step'], 'stage': stage, 'desired': desired, 'applied': target,
                                 'protected': [c for c in desired if c in protected],
                                 'already_banned': [c for c in desired if c in state['bans']]})
            if force and state['step'] in force:
                if policy == 'builtin' and target is None:
                    room.request(op='builtin')  # Preserve the embedded agent's state across this prefix.
                card = force[state['step']]
            elif target is not None:
                card = target
            elif policy == 'builtin':
                response = room.request(op='builtin')
                card = response['card']
                if response['fallback']:
                    fallbacks.append({'step': state['step'], 'side': side, **response})
            elif hasattr(policy, 'replay'):
                card, scores = policy.choose(seed, prefix, side, offers)
                notes.append({'step': state['step'], 'side': side, 'kind': kind, 'stage': stage,
                              'decks': state['decks'], 'bans': state['bans'], 'offers': offers,
                              'scores': list(scores.items()), 'chosen': card, 'prefix': prefix.copy()})
            else:
                rng = random.Random(seed * 101 + state['step'])
                if policy == 'uniform' or (noise and rng.random() < noise):
                    card = rng.choice(offers)
                else:
                    card = policy.choose(side, action, state, offers)
            if card not in offers:
                raise RuntimeError(f'draft action outside native legal mask: {seed}, {action}, {card}')
            prefix.append(card)
            state = room.request(op='act', key=card)
        sc = check_game({'map': HOME, 'seed': seed, 'night': False, 'weather': 'clear',
                         'rules': state['rules'], 'decks': state['decks'], 'bans': state['bans'],
                         'draft_history': state['history'], 'terrain_hash': terrain['terrain_hash'],
                         'battle_error': state.get('battle_error')})
        if sc['battle_error']:
            raise RuntimeError(f'{EXPECTED_VERSION} native draft cannot start: {seed}: {sc["battle_error"]}')
        return sc, notes, targeted, fallbacks
    finally:
        room.close()


def bridge_atlas(sc):
    from ranked_corpus import PROFILE as corpus_profile, atlas, canonical_draw, native

    with tempfile.TemporaryDirectory(dir=RUN, prefix='atlas-') as temp:
        directory = Path(temp)
        cold1, draw1 = native(sc, directory, 'full', full=True)
        cold2, draw2 = native(sc, directory, 'draw', full=False)
        assert read(cold1) == read(cold2)
        assert canonical_draw(read(draw1)) == canonical_draw(read(draw2))
        generated = directory / 'atlas.bin'
        if ATLAS.exists():
            assert sha(generated) == sha(ATLAS)
        else:
            generated.replace(ATLAS)
    PROFILE.update(simulation_atlas=str(ATLAS), simulation_atlas_sha256=sha(ATLAS))
    corpus_profile.update(PROFILE)
    atlas.cache_clear()
    write_atomic(PROFILE_PATH, PROFILE)


def fight(sc, recording=None):
    from option_games import Game, play, trace
    from ranked_corpus import atlas, native

    check_deadline()
    scratch = RUN / 'scratch'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='battle-') as temp:
        folder = Path(temp)
        corpus = folder / 'cold'
        corpus.mkdir()
        (folder / 'temp').mkdir()
        cold, draw = native(sc, corpus, '000', timeout=max(0.1, min(90, seconds_left())))
        write_atomic(corpus / 'index.json', {
            'entries': [{**sc, 'id': '000', 'cold': cold.name, 'draw': draw.name,
                         'cold_sha256': sha(cold), 'draw_sha256': sha(draw)}],
            'atlas': Path(os.path.relpath(atlas(), corpus)).as_posix(),
        })
        game = Game('000', None, zombie=None, position=None,
                    binary=Path(PROFILE['native_dir']) / 'position_match.exe',
                    corpus=corpus, storage=folder)
        if recording is None:
            play(game, timeout=max(0.1, min(180, seconds_left())))
            with gzip.open(game.path(), 'rt', encoding='utf-8') as file:
                header = json.loads(file.readline())
            report = trace(game)
        else:
            plans, events, inputs = (folder / name for name in ('observations.jsonl', 'events.jsonl', 'inputs.json'))
            subprocess.run([str(game.binary), '--corpus', str(corpus), '--id', '000',
                            '--out', str(plans), '--log', str(events), '--dump-inputs', str(inputs),
                            '--planner', 'r22', '--control-hz', '15', '--limit-seconds', str(game.limit),
                            '--telemetry'], check=True, capture_output=True,
                           timeout=max(0.1, min(180, seconds_left())))
            with plans.open(encoding='utf-8') as file:
                header = json.loads(file.readline())
                for line in file:
                    footer = line
            report = json.loads(footer)
        assert header['planners'] == dict.fromkeys(SIDES, 'r22') and header['controller'] == 'r22'
        assert header['source_fingerprint'] == PROFILE['native_build']
        assert all(header['ranked_rules'][k] == v for k, v in PROFILE['rules'].items())
        assert header['ranked_rules']['build'] == EXPECTED_VERSION
        assert not report['ai_error'] and (report['finished'] or report['timeout'])
        if recording is not None:
            assert report['plan_records'] > 0 and all(path.stat().st_size for path in (plans, events, inputs))
            recording.mkdir(exist_ok=True, parents=True)
            for path in (plans, events, inputs):
                output = recording / (path.name + '.gz')
                temp_output = output.with_suffix('.partial')
                with path.open('rb') as source, gzip.open(temp_output, 'wb', compresslevel=3) as dest:
                    shutil.copyfileobj(source, dest)
                os.replace(temp_output, output)
        return {'winner': (report['result'] or {}).get('winner'), 'timeout': report['timeout'],
                'seconds': report['time'], 'hp': report['hp'], 'log_sha256': report['log_sha256'],
                'deploys': dict(Counter(a['side'] for a in report['activity'] if a['kind'] == 'deploy')),
                'cold_sha256': sha(cold)}


def battle_outcome(result):
    return (result['winner'] if not result['timeout'] and result['winner'] in SIDES else 'timeout')


def evaluate_case(seed, arm, fast, pressure=None):
    plant, zombie = {'builtin': ('builtin', 'builtin'), 'fast-plant': (fast, 'builtin'),
                     'fast-zombie': ('builtin', fast), 'mirror': (fast, fast)}[arm]
    sc, _, targeted, fallbacks = draft(seed, {PLANT: plant, ZOMBIE: zombie}, pressure=pressure)
    return {'arm': arm, 'pressure': pressure, 'opening': sc, 'targeted': targeted,
            'builtin_fallbacks': fallbacks, 'result': fight(sc)}


def eval_summary(rows):
    base = {r['opening']['seed']: battle_outcome(r['result']) for r in rows
            if r['arm'] == 'builtin' and r['pressure'] is None}
    normal = {(r['arm'], r['opening']['seed']): battle_outcome(r['result']) for r in rows if r['pressure'] is None}
    report = {}
    group = lambda row: row['arm'] + (':' + row['pressure'] if row['pressure'] else '')
    for key in sorted(set(map(group, rows))):
        games = [row for row in rows if group(row) == key]
        outcomes = [battle_outcome(row['result']) for row in games]
        decks = {s: Counter(tuple(sorted(r['opening']['decks'][s])) for r in games) for s in SIDES}
        changes = Counter()
        for row, outcome in zip(games, outcomes):
            seed = row['opening']['seed']
            old = normal.get((row['arm'], seed)) if row['pressure'] else base.get(seed)
            if old is not None:
                changes[f'{old}->{outcome}'] += 1
        report[key] = {
            'cases': len(games), 'outcomes': dict(Counter(outcomes)), 'paired_changes': dict(changes),
            'plant_top_template': decks[PLANT][tuple(sorted(TOP_PLANT))],
            'distinct_decks': {s: len(decks[s]) for s in SIDES},
            'top_deck': {s: decks[s].most_common(1)[0] for s in SIDES},
            'applied_by_card': dict(Counter(x['applied'] for r in games for x in r['targeted'] if x['applied'])),
            'protected_by_card': dict(Counter(c for r in games for c in
                                            {c for x in r['targeted'] for c in x['protected']})),
            'affected_outcomes': dict(Counter(outcome for r, outcome in zip(games, outcomes)
                                             if any(x['applied'] for x in r['targeted']))),
            'builtin_fallbacks': sum(len(row['builtin_fallbacks']) for row in games),
        }
    return report


def work(items, function, consume, lanes, until):
    """Bound in-flight work, drain it into the checkpoint, and surface errors."""
    tasks = iter(items)
    active = set()
    with ThreadPoolExecutor(max_workers=lanes) as pool:
        while active or (time.time() < until and not STOP.exists()):
            while len(active) < lanes and time.time() < until and not STOP.exists():
                item = next(tasks, None)
                if item is None:
                    break
                active.add(pool.submit(function, item))
            if not active:
                break
            done, active = wait(active, timeout=5, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    item = future.result()
                except (TimeoutError, subprocess.TimeoutExpired):
                    if seconds_left() > 0 and not STOP.exists():
                        raise
                else:
                    consume(item)


def evaluate(name, seed0, cases, fast, lanes, until, pressures=tuple(PRESSURE), mirror_pressure=True):
    directory = RUN / name
    directory.mkdir(exist_ok=True)
    arms = [('builtin', None), ('fast-plant', None), ('fast-zombie', None), ('mirror', None)]
    for condition in pressures:
        arms.append(('fast-plant', condition))
        if mirror_pressure:
            arms.append(('mirror', condition))
    todo, rows = [], []
    for seed in range(seed0, seed0 + cases):
        for arm, pressure in arms:
            path = directory / f'{seed}-{arm}-{pressure or "normal"}.json'
            if path.exists():
                rows.append(read(path))
            else:
                todo.append((seed, arm, pressure, path))

    def one(job):
        seed, arm, pressure, path = job
        return path, evaluate_case(seed, arm, fast, pressure)

    def consume(item):
        path, row = item
        write_atomic(path, row)
        rows.append(row)
        if len(rows) % 24 == 0:
            status(name, cases=len(rows), total=cases * len(arms))
            write_atomic(directory / 'summary.json', eval_summary(rows))

    work(todo, one, consume, lanes, until)
    summary = eval_summary(rows)
    write_atomic(directory / 'summary.json', summary)
    status(name + '-done', cases=len(rows), total=cases * len(arms))
    return summary, len(rows) == cases * len(arms)


def preflight(fast):
    from deckvalue_model import catalog

    cards = catalog()['cards']
    assert all(card in cards for card in TOP_PLANT)
    baseline = {PLANT: 'builtin', ZOMBIE: 'builtin'}
    sc, _, _, fallbacks = draft(SMOKE_SEED, baseline)
    again, *_ = draft(SMOKE_SEED, baseline)
    assert again == sc, 'r22 built-in draft does not reproduce on an identical opening'
    if 'simulation_atlas' not in PROFILE:
        bridge_atlas(sc)
    result = fight(sc)
    assert result == fight(again), 'same ranked opening produced a different r22 battle'
    stress = evaluate_case(SMOKE_SEED + 1, 'fast-plant', fast, 'combo')
    assert SUNFLOWER in stress['opening']['bans'] and CABBAGE in stress['opening']['bans']
    assert SUNFLOWER not in stress['opening']['decks'][PLANT] and CABBAGE not in stress['opening']['decks'][PLANT]
    write_atomic(RUN / 'preflight.json', {
        'opening': sc, 'builtin_fallbacks': fallbacks, 'result': result, 'stress': stress,
        'atlas_sha256': PROFILE['simulation_atlas_sha256'], 'sim_fingerprint': PROFILE['native_build'],
        'draft_reproduced': True, 'battle_reproduced': True,
    })
    status('preflight-passed', built_in_steps=len(sc['draft_history']),
           builtin_fallbacks=len(fallbacks), results=[battle_outcome(result), battle_outcome(stress['result'])])


def pressure_weights(baseline):
    """Oversample applied counters and the conditions that flipped genuine wins."""
    weights = {}
    for condition in PRESSURE:
        groups = [baseline[arm + ':' + condition] for arm in ('fast-plant', 'mirror')]
        lost = sum(sum(n for change, n in group['paired_changes'].items()
                       if change in ('plant->zombie', 'plant->timeout')) for group in groups)
        affected = sum(sum(group['affected_outcomes'].values()) for group in groups)
        failure = sum(sum(n for outcome, n in group['affected_outcomes'].items()
                          if outcome != PLANT) for group in groups)
        weights[condition] = round(1.0 + 4.0 * lost / max(1, affected) + 2.0 * failure / max(1, affected), 3)
    return weights


def sample_condition(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def completed_ids(path, table):
    with sqlite3.connect(path, timeout=60) as db:
        db.execute(f'create table if not exists {table}(id integer primary key, data blob not null)')
        return {i for (i,) in db.execute(f'select id from {table}')}


def compressed(row):
    return zlib.compress(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode(), 5)


def game_row(i, sc, result, policy, pressure, targeted):
    outcome = battle_outcome(result)
    return {'i': i, 'seed': sc['seed'], 'policy': policy, 'pressure': pressure,
            'decks': sc['decks'], 'bans': sc['bans'], 'result': result, 'outcome': outcome,
            'y': {PLANT: 1, ZOMBIE: 0}.get(outcome, 0.5), 'opening': sc, 'targeted': targeted,
            'native_build': PROFILE['native_build'], 'controllers': dict.fromkeys(SIDES, 'r22')}


def sample_corpus(fast, weights, count, lanes, until):
    db_path = RUN / 'corpus.sqlite'
    done = completed_ids(db_path, 'games')
    todo = [(j, j * 100 + j % 10) for j in range(count) if j * 100 + j % 10 not in done]
    made = len(done)

    def one(item):
        j, i = item
        seed = CORPUS_SEED + j
        rng = random.Random(seed)
        pressure = sample_condition(rng, weights) if j % 5 < 3 else None
        names = rng.choices(('fast', 'builtin', 'uniform'), weights=(65, 24, 11), k=2)
        policy = dict(zip(SIDES, names))
        sc, _, targeted, _ = draft(seed, {s: fast if policy[s] == 'fast' else policy[s] for s in SIDES},
                                   pressure=pressure, noise=0.14 if j % 4 == 0 else 0.035)
        return i, game_row(i, sc, fight(sc), policy, pressure, targeted)

    with sqlite3.connect(db_path, timeout=60) as db:
        db.execute('pragma journal_mode=wal')

        def consume(item):
            nonlocal made
            i, row = item
            with db:
                db.execute('insert into games values(?,?)', (i, compressed(row)))
            made += 1
            if made % 50 == 0:
                status('corpus', games=made, target=count)

        work(todo, one, consume, lanes, until)
    status('corpus-done', games=made, target=count)
    return made


def paired_feedback(seed, policies, pressure, notes):
    """Replay the same public prefix and two legal actions, holding the continuation policy fixed."""
    rng = random.Random(seed + 19271)
    choices = [n for n in notes if n['kind'] == 'pick' and len(n['scores']) >= 2]
    if pressure == 'late':
        protected = [n for n in choices if n['stage'] == 'opening_pick' and CABBAGE in n['offers']]
        choices = protected or choices
    if not choices:
        return None, []
    note = rng.choice(choices)
    preferred = note['chosen']
    alternatives = [c for c, _ in sorted(note['scores'], key=lambda p: -p[1]) if c != preferred]
    if pressure == 'late' and CABBAGE in note['offers'] and preferred != CABBAGE:
        alternative = CABBAGE
    else:
        alternative = rng.choice(alternatives[:4])
    prefix = dict(enumerate(note['prefix']))
    simulations, outcome = [], {}
    for card in (preferred, alternative):
        sc, _, targeted, _ = draft(seed, policies, pressure=pressure, force={**prefix, note['step']: card})
        result = fight(sc)
        simulations.append((sc, result, targeted))
        outcome[card] = {note['side']: 1, 'timeout': 0}.get(battle_outcome(result), -1)
    evidence = {'step': note['step'], 'cards': [preferred, alternative],
                'outcomes': [battle_outcome(s[1]) for s in simulations]}
    if outcome[preferred] != outcome[alternative]:
        # Actual continuation outranks the value teacher for this matched action pair.
        note['scores'] = [[c, v * 0.075] for c, v in outcome.items()]
    return evidence, simulations


def sample_teacher(start, stop, value, prior, fast, weights, lanes, until, fast_opponent=None):
    from deckvalue_search import Searcher

    db_path = RUN / 'distill.sqlite'
    done = completed_ids(db_path, 'drafts')
    todo = [j for j in range(start, stop) if j not in done]
    made = len(done)

    def one(j):
        seed = TEACHER_SEED + j
        rng = random.Random(seed)
        seat = ZOMBIE if j % 4 == 3 else PLANT
        opponent = SIDES[1 - SIDES.index(seat)]
        pressure = sample_condition(rng, weights) if j % 5 != 4 else None
        foe_name = 'builtin' if j % 5 == 0 else 'fast'
        opponent_policy = foe_name if foe_name == 'builtin' else fast_opponent(seed) if fast_opponent else fast
        searcher = Searcher(value, prior, M=16, K=2, explore=4,
                            ban_targets=lambda action: desired_bans(pressure, action))
        try:
            sc, notes, targeted, _ = draft(seed, {seat: searcher, opponent: opponent_policy},
                                           pressure=pressure, noise=0.07 if j % 3 == 0 else 0)
        finally:
            searcher.close()
        first = (sc, fight(sc), targeted)
        evidence, alternatives = paired_feedback(seed, {seat: fast, opponent: opponent_policy},
                                                  pressure, notes) if j % 3 == 0 else (None, [])
        names = {seat: 'value-search', opponent: foe_name}
        i = 10_000_000 + j * 100 + j % 10
        games = [game_row(i + 10 * k, a, r, names if k == 0 else {**names, seat: 'forced-prefix/fast'},
                          pressure, t) for k, (a, r, t) in enumerate([first, *alternatives])]
        return j, {'j': j, 'seed': seed, 'seat': seat, 'opponent': foe_name,
                   'pressure': pressure, 'paired_action_feedback': evidence, 'notes': notes}, games

    with sqlite3.connect(db_path, timeout=60) as db:
        db.execute('pragma journal_mode=wal')
        db.execute('attach database ? as corpus', (str(RUN / 'corpus.sqlite'),))

        def consume(item):
            nonlocal made
            j, row, games = item
            with db:
                db.executemany('insert or replace into corpus.games values(?,?)',
                               [(game['i'], compressed(game)) for game in games])
                db.execute('insert into drafts values(?,?)', (j, compressed(row)))
            made += 1
            if made % 12 == 0:
                status('teacher', drafts=made, target=stop)

        work(todo, one, consume, lanes, until)
    status('teacher-done', drafts=made, target=stop)
    return made


def fit_child(phase, name, until):
    log = RUN / 'models' / f'{name}.log'
    with log.open('w', encoding='utf-8') as file:
        subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__)), phase],
                       env={**os.environ, 'DV_THREADS': '4'}, stdout=file, stderr=subprocess.STDOUT,
                       timeout=max(1, until - time.time()), check=True)


def refresh_value(name, until):
    from deckvalue_search import Value, corpus_prior

    status('fit-value', checkpoint=name)
    fit_child('fit-value', 'value-' + name, until)
    value = Value()
    prior = corpus_prior(value)
    write_atomic(RUN / 'prior.json', {'prior': prior, 'value_sha256': sha(RUN / 'models' / 'value-latest.pt')})
    write_atomic(RUN / 'models' / f'prior-{name}.json', prior)
    return value, prior


def holdout_comparison(old_root, new_root):
    old_cases = {path.name: read(path) for path in old_root.glob('76*.json')}
    groups = {}
    for path in new_root.glob('76*.json'):
        if path.name not in old_cases:
            continue
        old, new = old_cases[path.name], read(path)
        seed = new['opening']['seed']
        assert seed == old['opening']['seed']
        group = new['arm'] + (':' + new['pressure'] if new['pressure'] else '')
        changes = groups.setdefault(group, Counter())
        b, a = battle_outcome(old['result']), battle_outcome(new['result'])
        changes[f'{b}->{a}'] += 1
    return {arm: dict(changes) for arm, changes in groups.items()}


def train(fast, lanes):
    baseline_file = RUN / 'baseline' / 'summary.json'
    baseline = read(baseline_file)
    weights = pressure_weights(baseline)
    critical = sorted(PRESSURE, key=weights.get, reverse=True)[:3]
    write_atomic(RUN / 'sampling-plan.json', {
        'baseline_sha256': sha(baseline_file), 'weights': weights, 'holdout_pressures': critical,
        'sample_seeds': {'corpus': CORPUS_SEED, 'teacher': TEACHER_SEED, 'holdout': HOLDOUT_SEED},
        'battle': dict.fromkeys(SIDES, 'r22'),
    })
    status('corpus', target=1000, pressure_weights=weights)
    holdout_at = DEADLINE - 32 * 60
    corpus = sample_corpus(fast, weights, 1000, lanes, min(holdout_at - 30 * 60, time.time() + 75 * 60))
    if corpus < 120:
        raise RuntimeError(f'Only {corpus} native r3 games collected before fitting')
    name = 'bootstrap'
    value, prior = refresh_value(name, holdout_at - 20 * 60)
    teacher_start, wave = 0, 0
    candidate = None
    while not STOP.exists() and time.time() < holdout_at - 6 * 60:
        name = f'wave-{wave + 1:02}'
        teacher_stop = teacher_start + (72 if wave == 0 else 180)
        status('teacher', wave=name, start=teacher_start, target=teacher_stop)
        made = sample_teacher(teacher_start, teacher_stop, value, prior, fast, weights, lanes,
                              holdout_at - 6 * 60)
        if made < max(16, teacher_start + 8):
            break
        teacher_start, wave = made, wave + 1
        status('fit-draft', wave=name, drafts=made)
        fit_child('fit-draft', 'draft-' + name, holdout_at)
        checkpoint = RUN / 'models' / f'fast-{name}.pt'
        shutil.copy2(RUN / 'models' / 'distill-latest.pt', checkpoint)
        prior_path = RUN / 'models' / f'prior-{name}.json'
        source_prior = RUN / 'prior.json'
        write_atomic(prior_path, read(source_prior)['prior'])
        shutil.copy2(RUN / 'models' / 'distill-report.json', RUN / 'models' / f'distill-{name}.json')
        candidate = (checkpoint, prior_path)
        fast = fast_head(*candidate)
        write_atomic(RUN / 'candidate.json', {
            'wave': name, 'drafts': made, 'path': str(checkpoint), 'sha256': sha(checkpoint),
            'prior': str(prior_path), 'prior_sha256': sha(prior_path), 'holdout': 'pending',
        })
        if time.time() >= holdout_at - 14 * 60:
            break
        # Refit value on the additional r3 real outcomes before collecting the next wave.
        del value
        value, prior = refresh_value(f'after-{name}', holdout_at - 8 * 60)
    if candidate is None or STOP.exists():
        return
    trials = 12
    cutoff = DEADLINE - 40
    old_root, new_root = RUN / 'holdout-transferred', RUN / 'holdout-trained'
    reference = fast_head()
    # Interleave matched seeds so a deadline still leaves paired comparisons.
    for first in range(0, trials, 4):
        if time.time() >= cutoff or STOP.exists():
            break
        # evaluate() loads every existing row from the seed range it is given.
        evaluate(old_root.name, HOLDOUT_SEED, first + 4, reference, lanes, cutoff, critical, False)
        evaluate(new_root.name, HOLDOUT_SEED, first + 4, fast, lanes, cutoff, critical, False)
        write_atomic(RUN / 'holdout-comparison.json', holdout_comparison(old_root, new_root))
    status('finished', last_checkpoint=str(candidate[0]), holdout_matched=sum(
        sum(v.values()) for v in holdout_comparison(old_root, new_root).values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('setup', 'smoke', 'baseline', 'train', 'all', 'fit-value', 'fit-draft'))
    parser.add_argument('--until', default='2026-11-23T21:30:00+08:00')
    parser.add_argument('--cases', type=int, default=24)
    parser.add_argument('--lanes', type=int, default=6)
    args = parser.parse_args()
    if args.phase == 'setup':
        setup(args.until)
        return
    if args.phase == 'all':
        setup(args.until)
    configure()
    check_deadline()
    if args.phase == 'fit-value':
        from deckvalue_model import fit
        fit(ensemble=3, epochs=40)
        return
    if args.phase == 'fit-draft':
        from deckvalue_distill import fit
        fit(epochs=26, initial=V0)
        return
    transfer_head()
    fast = fast_head()
    if args.phase == 'smoke':
        preflight(fast)
    elif args.phase == 'baseline':
        assert (RUN / 'preflight.json').is_file()
        evaluate('baseline', BASELINE_SEED, args.cases, fast, args.lanes, DEADLINE)
    else:
        import msvcrt
        with (RUN / 'training.lock').open('a+b') as lock:
            if not lock.tell():
                lock.write(b'x')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            try:
                if args.phase == 'all':
                    if not (RUN / 'preflight.json').is_file():
                        status('preflight')
                        preflight(fast)
                    status('baseline', cases=0, total=args.cases * (4 + 2 * len(PRESSURE)))
                    _, complete = evaluate('baseline', BASELINE_SEED, args.cases, fast, args.lanes,
                                           DEADLINE - 90 * 60)
                    if not complete:
                        status('baseline-incomplete')
                        return
                assert (RUN / 'preflight.json').is_file()
                train(fast, args.lanes)
            except Exception as error:
                status('failed', error=repr(error))
                raise
            finally:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
