"""PvP78 r3 ranked Home games with the live r22 controller and selected draft heads."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from league_data import ROOT, read, sha
import pvp77_card_support_train as prior


native, battle = prior.native, prior.battle
RUN = ROOT / 'r22-cards-pvp78-r3-20261125'
NATIVE_DRAFT_RUN = ROOT / 'r22-cards-native-draft-pvp78-r3-20261125'
SELECTION = ROOT / 'model-selection-pvp77-r4-20261125/selected-models.json'
VERSION = '1.6.0.78-typed.20261125-r3'
PLANT, ZOMBIE = native.SIDES
MECHANICS = ('laser_beam_pulses', 'laser_focus_hits', 'croton_triggers', 'croton_gas_hits')
SEED = 78830000


class NativeHead:
    def __init__(self, head):
        self.head = head

    def choose_native(self, room, side, action, state, offers):
        actual = room.request(op='selected')['card']
        expected = self.head.choose(side, action, state, offers)
        if actual != expected:
            raise AssertionError(f'native fast draft disagrees with the selected checkpoint at step {state["step"]}: '
                                 f'{actual} != {expected}')
        return actual


def export_native_bundle(heads):
    import torch

    def layer(linear):
        return {'weights': linear.weight.tolist(), 'bias': linear.bias.tolist()}

    vocab = heads[PLANT].vocab
    bundle = {'format': 'pvz-ranked-fast-draft-1', 'build': VERSION,
              'keys': vocab.keys, 'sides': [vocab.side[k] for k in vocab.keys]}
    with torch.no_grad():
        for side, head in heads.items():
            bundle[side] = {'cards': head.net.cards().tolist(),
                            'prior': [head.prior.get(k, 0.) for k in vocab.keys],
                            'coverage': [k in head.coverage for k in vocab.keys],
                            'context': layer(head.net.ctx[0]), 'score': layer(head.net.score[0]),
                            'output': layer(head.net.score[2])}
    file = RUN / 'fast-ranked-heads.json'
    native.write_atomic(file, bundle)
    os.environ['PVZ_RANKED_FAST_HEADS'] = str(file)
    return sha(file)


def setup():
    release = read(native.R / 'dist/latest-native-release.json')
    build = read(RUN / 'native-build.json')
    assert release['version'] == build['version'] == VERSION
    assert sha(Path(release['target'])) == release['exe_sha256'] == build['release']
    assert sha(Path(release['developer_package'])) == build['developer_package']
    assert all(sha(native.R / source) == digests['candidate'] for source, digests in build['candidate_sources'].items())
    assert all(sha(RUN / 'native' / f'{name}.exe') == digest for name, digest in build['binaries'].items())
    data = Path(release['release'])
    assert sha(data / 'extract/data/_resolved_cards.json') == build['shipped_catalog']
    source = read(SELECTION)
    assert source['map'] == '家院' and not source['night']
    profile = dict(output=str(RUN), native_dir=str(RUN / 'native'), data_root=str(data),
                   version=VERSION, native_build=build['fingerprint'], rules=source['rules'],
                   home='家院', night=False, weather='clear', day_league=True, draft_v2=True,
                   reference='r22', deadline=(datetime.now(timezone(timedelta(hours=8)))+timedelta(hours=2)).isoformat(),
                   opening_source='PvP78 r3 Room native pick/ban -> cold export -> production typed Session')
    profile_path = RUN / 'profile.json'
    if profile_path.exists():
        frozen = read(profile_path)
        profile.update({k: frozen[k] for k in ('simulation_atlas', 'simulation_atlas_sha256') if k in frozen})
        assert all(profile[k] == frozen[k] for k in profile if k != 'deadline')
    native.write_atomic(profile_path, profile)
    native.RUN = battle.RUN = RUN
    native.PROFILE_PATH, native.STOP, native.ATLAS = profile_path, RUN / 'STOP', RUN / 'simulation-atlas.bin'
    native.EXPECTED_VERSION = VERSION
    native.configure()

    from ranked_draft import Room
    room = Room()
    try:
        native.write_atomic(RUN / 'catalog.json', room.catalog)
    finally:
        room.close()

    import torch
    from deckvalue_distill import FastDrafter
    from deckvalue_model import Vocab
    torch.set_num_threads(1)
    vocab = Vocab()
    heads = {}
    for side in native.SIDES:
        bundle = source['selected'][side]['draft']
        weights, card_prior = (Path(bundle[k]) for k in ('weights', 'prior'))
        assert sha(weights) == bundle['weight_sha256'] and sha(card_prior) == bundle['prior_sha256']
        checkpoint = torch.load(weights, map_location='cpu', weights_only=False)
        assert checkpoint['keys'] == vocab.keys and torch.equal(checkpoint['state']['fixed'][:-1], vocab.fixed)
        heads[side] = FastDrafter(weights, read(card_prior), coverage=bundle['coverage'])
    bundle_sha = export_native_bundle(heads) if RUN == NATIVE_DRAFT_RUN else None
    native.write_atomic(RUN / 'plan.json', {'version': VERSION, 'selection_sha256': sha(SELECTION),
                        'heads': source['selected'], 'battle_ai': 'native r22 Plant19 and Zombie19',
                        'native_draft_bundle_sha256': bundle_sha,
                        'rules': profile['rules'], 'map': profile['home'], 'opening_source': profile['opening_source']})
    if 'simulation_atlas' not in profile:
        opening, _, _, _ = native.draft(SEED - 1, heads)
        native.bridge_atlas(opening)
    return heads


def play(opening):
    native.check_deadline()
    with battle.cold_opening(opening) as work:
        path, events = work / 'match.jsonl', work / 'events.jsonl'
        process = subprocess.run([str(RUN / 'native/position_match.exe'), '--corpus', str(work), '--id', '000',
                                  '--out', str(path), '--log', str(events), '--no-records', '--telemetry',
                                  '--limit-seconds', '600', '--control-hz', '15'],
                                 capture_output=True, timeout=420)
        if process.returncode:
            raise RuntimeError(process.stderr.decode('utf-8', errors='replace'))
        header, footer = map(json.loads, path.read_text(encoding='utf-8').splitlines())
        assert header['source_fingerprint'] == native.PROFILE['native_build']
        assert header['ranked_rules']['build'] == VERSION and all(
            header['ranked_rules'][key] == value for key, value in native.PROFILE['rules'].items())
        assert header['decks'] == opening['decks'] and header['seed'] == opening['seed']
        assert header['planners'] == {'plant': 'r22', 'zombie': 'r22'}
        assert not footer['ai_error'] and (footer['finished'] or footer['timeout'])
        # Keep accepted commands and the actual pulse/poison counters from the native kernel.
        with events.open(encoding='utf-8') as stream:
            card_commands = [event for line in stream if (event := json.loads(line)).get('event') == 'input'
                             and event.get('kind') in ('laser', 'laser_cancel')]
        deploys = Counter(x['card'] for x in footer['activity'] if x.get('kind') == 'deploy')
        return {'winner': (footer['result'] or {}).get('winner'), 'timeout': footer['timeout'],
                'seconds': footer['time'], 'deployment': dict(deploys), 'mechanics': footer['card_mechanics'],
                'laser_inputs': card_commands, 'log_sha256': footer['log_sha256'],
                'native_build': header['source_fingerprint']}


def case(heads, arm, i):
    seed = SEED + i + (1000 if arm == 'directed' else 0)
    pressure = (None, 'economy', 'late')[i % 3] if arm != 'directed' else None
    policies = {s: heads[s] for s in native.SIDES}
    if arm == 'builtin':
        policies = dict.fromkeys(native.SIDES, 'builtin')
    elif arm == 'plant-head':
        policies[ZOMBIE] = 'builtin'
    elif arm == 'zombie-head':
        policies[PLANT] = 'builtin'
    elif arm == 'directed':
        main = (prior.LASER, prior.FOCUS, prior.CROTON) if i % 2 == 0 else (prior.CROTON, prior.LASER, prior.FOCUS)
        policies[PLANT] = prior.PreferLegal(prior.VariedFastOpponent(heads[PLANT], seed),
                                           (native.SUNFLOWER, *main))
        policies[ZOMBIE] = prior.PreferLegal(prior.VariedFastOpponent(heads[ZOMBIE], seed),
                                            ('zombie:脑光墓碑','zombie:普通僵尸'))
    if RUN == NATIVE_DRAFT_RUN and arm != 'directed':
        policies = {s: NativeHead(head) if head != 'builtin' else head for s, head in policies.items()}
    opening, _, targeted, fallbacks = native.draft(seed, policies, pressure=pressure)
    assert opening['map'] == '家院' and not opening['night'] and opening['weather'] == 'clear'
    assert len(opening['draft_history']) == 30 and all(len(v) == 7 for v in opening['decks'].values())
    return {'arm': arm, 'index': i, 'pressure': pressure, 'opening': opening, 'targeted': targeted,
            'fallbacks': fallbacks, 'game': play(opening)}


def report(rows, arms):
    results = {}
    for arm in arms:
        subset = [r for r in rows.values() if r['arm'] == arm]
        results[arm] = {'games': len(subset), 'outcomes': dict(Counter(native.battle_outcome(r['game']) for r in subset)),
                        'new_card_picks': dict(Counter(k for r in subset for deck in r['opening']['decks'].values()
                                                      for k in deck if k in prior.CARDS)),
                        'laser_deployed_games': sum(r['game']['deployment'].get(prior.LASER, 0)>0 for r in subset),
                        'croton_deployed_games': sum(r['game']['deployment'].get(prior.CROTON, 0)>0 for r in subset),
                        'mechanics_games': {k: sum(r['game']['mechanics'][k]>0 for r in subset) for k in MECHANICS},
                        'mechanics_total': {k: sum(r['game']['mechanics'][k] for r in subset) for k in MECHANICS}}
    native.write_atomic(RUN / 'summary.json', results)
    return results


def main():
    global RUN
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lanes', type=int, default=8)
    parser.add_argument('--cases', type=int, default=12)
    parser.add_argument('--native-draft', action='store_true')
    args = parser.parse_args()
    if args.native_draft:
        RUN = NATIVE_DRAFT_RUN
    heads = setup()
    out = RUN / 'cases'
    out.mkdir(exist_ok=True)
    rows = {p.stem: read(p) for p in out.glob('*.json')}
    arms = ('directed', 'builtin', 'plant-head', 'zombie-head', 'both-heads')
    jobs = [((arm, i), f'{arm}-{i:02}') for arm in arms for i in range(args.cases)]

    def save(result):
        label, row = result
        native.write_atomic(out / f'{label}.json', row)
        rows[label] = row
        report(rows, arms)
        native.status('matches', complete=len(rows), expected=len(jobs))
        print(label, row['game']['winner'], row['game']['mechanics'], flush=True)

    native.status('matches', complete=len(rows), expected=len(jobs))
    native.work((j for j in jobs if j[1] not in rows), lambda j: (j[1], case(heads, *j[0])), save,
                args.lanes, native.DEADLINE-30)
    assert len(rows) == len(jobs)
    final = report(rows, arms)
    directed = final['directed']
    assert directed['mechanics_total']['laser_beam_pulses'] > 0
    assert directed['mechanics_total']['laser_focus_hits'] > 0
    assert directed['mechanics_total']['croton_triggers'] > 0
    assert directed['mechanics_total']['croton_gas_hits'] > 0
    fired = [row['game'] for row in rows.values() if row['game']['mechanics']['laser_beam_pulses'] > 0]
    assert any(any(x['kind'] == 'laser' and x['accepted'] and x.get('target') for x in g['laser_inputs'])
               and any(x['kind'] == 'laser' and x['accepted'] and not x.get('target') for x in g['laser_inputs'])
               for g in fired)
    native.status('finished', complete=len(rows), expected=len(jobs))


if __name__ == '__main__':
    main()
