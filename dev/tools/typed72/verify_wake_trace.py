"""Assert that the supplementary permanent-wake scenario actually exercised its branch.

Run AFTER regression_gate with --keep-pass-artifacts, passing the sim case attempt
folder. This is additional behavior coverage, not a replacement for V comparison.
"""
import argparse
import json
from pathlib import Path


def verify(trace, final, width, tile):
    awake_tick = None
    awake_records = remote_records = remote_after_idle_limit = 0
    idle_max = 0.0
    last_tick = -1
    grave_id = None
    for line in trace.open(encoding='utf-8'):
        row = json.loads(line)
        tick = row['t']
        if tick <= last_tick:
            raise ValueError('Trace ticks are not strictly increasing')
        last_tick = tick
        graves = [z for z in row['g']['僵尸'] if z.get('_pvp_grave') and z['血量'] > 0]
        if not graves:
            if awake_tick is not None:
                raise ValueError('Awakened grave disappeared; persistence branch is not covered')
            continue
        if len(graves) != 1:
            raise ValueError('Persistence fixture must contain exactly one living grave')
        grave = graves[0]
        if grave.get('_pvp_zs_awake') is not True:
            if awake_tick is not None:
                raise ValueError('Permanent-wake marker was lost')
            continue
        grave_id = grave['_pvp_id']
        if awake_tick is None:
            awake_tick = tick
        awake_records += 1
        idle = grave['_pvp_idle']
        idle_max = max(idle_max, idle)
        if idle != 0.0:
            raise ValueError('Awakened grave idle advanced at native tick %d: %r' % (tick, idle))
        gx, gy = grave['位置'][:2]
        hx, hy = row['avatars']['zombie']['玩家位置'][:2]
        dx = (hx - gx + width / 2.0) % width - width / 2.0
        if dx * dx + (hy - gy) * (hy - gy) > (tile * 2.4) ** 2:
            remote_records += 1
            if tick - awake_tick > 20 * 250:
                remote_after_idle_limit += 1
    events = json.loads(final.read_text(encoding='utf-8'))['log']
    wakes = [e['graves'] for e in events if e['event'] == 'zsecret_wake']
    heals = [e for e in events if e['event'] == 'heal' and e.get('kind') == 'zsecret_wake']
    teleports = [e for e in events if e['event'] == 'teleport' and e.get('side') == 'zombie']
    if wakes != [1, 0] or len(heals) != 2 or any(e['amount'] != 4 for e in heals):
        raise ValueError('Expected two successful wake teleports, fresh grave counts [1,0], and two +4 heals')
    if len(teleports) != 2 or any(e['target'] != grave_id for e in teleports):
        raise ValueError('Both teleports must reach the same persistent grave')
    if awake_tick is None or last_tick - awake_tick < 60 * 250:
        raise ValueError('Trace does not observe permanent wake for at least sixty seconds')
    if remote_after_idle_limit < 20 * 250:
        raise ValueError('Hero was not away long enough beyond the twenty-second idle threshold')
    return dict(passed=True, first_awake_tick=awake_tick, last_tick=last_tick,
                awake_records=awake_records, remote_records=remote_records,
                remote_after_idle_threshold=remote_after_idle_limit,
                maximum_idle_after_wake=idle_max, new_graves_per_teleport=wakes,
                successful_teleports=len(teleports), heal_events=len(heals))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Refusing to overwrite existing evidence')
    cold = json.loads((args.attempt / 'cold.json').read_text(encoding='utf-8'))['battle']
    results = {}
    for backend, trace, final in [('typed', 'typed.jsonl', 'typed.final.json'),
                                  ('reference', 'reference.jsonl', 'reference.jsonl.final.json')]:
        results[backend] = verify(args.attempt / trace, args.attempt / final, cold['width'], cold['tile'])
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
