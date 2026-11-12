"""Coverage verdict for supp_ranked_gold_lock2 (Python 3.8+, standard library).

Reads the typed AND V traces of one regression-gate sim attempt plus the snapshot
attempt and checks that every intended ranked branch really ran on both sides:
  far sunflower (rt 400) rejected by the ranked ring, near one (rt 402) accepted,
  a golden bloom accepted (first of rt 600/610/620), mouse collection accepted
  before the lock (540), rejected during it (660, 900) and accepted after (1000),
  and players.plant.collect_locked_until published in the snapshots.
Usage: verify_ranked_gold.py <supp-run-dir> <out.json>
"""
import json
import sys
from pathlib import Path


def results(path):
    """rt -> list of (side, kind, error) from the per-tick 'inp' field."""
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            d = json.loads(line)
            if d.get('inp'):
                out.setdefault(d['rt'], []).extend(tuple(x) for x in d['inp'])
    return out


def deploys(final_path):
    log = json.load(open(final_path, encoding='utf-8'))['log']
    return [(e['tick'], e['card']) for e in log if e.get('event') == 'deploy' and e.get('side') == 'plant']


def verdict(trace, final):
    r = results(trace)
    dep = deploys(final)
    err = lambda rt: [x[2] for x in r.get(rt, []) if x[0] == 'plant']
    gold = [t for t, c in dep if c == 'plant:黄金蓓蕾']
    checks = {
        'far_ring_rejected': any('只能在己方戴夫' in e for e in err(400)),
        'near_accepted': any(t == 402 and c == 'plant:向日葵' for t, c in dep),
        'bloom_accepted': bool(gold) and gold[0] in (600, 610, 620),
        'collect_before_lock_ok': 540 not in r or not any(err(540)),
        'collect_locked_660': any('黄金蓓蕾' in e for e in err(660)),
        'collect_locked_900': any('黄金蓓蕾' in e for e in err(900)),
        'collect_after_lock_ok': 1000 not in r or not any(err(1000)),
    }
    return checks, {'gold_deploy_ticks': gold, 'errors': {str(k): v for k, v in sorted(r.items())}}


def main():
    run, out = Path(sys.argv[1]), Path(sys.argv[2])
    sim = sorted((run / 'cases/sim/supp_ranked_gold_lock2').glob('attempt-*'))[-1]
    report = {}
    for side, trace, final in (('typed', 'typed.jsonl', 'typed.final.json'), ('v', 'reference.jsonl', 'reference.jsonl.final.json')):
        checks, evidence = verdict(sim / trace, sim / final)
        report[side] = {'checks': checks, 'evidence': evidence}
    snap = sorted((run / 'cases/snapshots/supp_ranked_gold_lock2').glob('attempt-*'))[-1]
    published = False
    for path in snap.rglob('*.jsonl'):
        with open(path, encoding='utf-8') as f:
            if any('collect_locked_until' in line for line in f):
                published = True
                break
    report['snapshot_publishes_collect_lock'] = published
    report['passed'] = published and all(all(report[s]['checks'].values()) for s in ('typed', 'v'))
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({s: report[s]['checks'] for s in ('typed', 'v')}, ensure_ascii=False))
    print('snapshot_publishes_collect_lock', published, 'PASSED' if report['passed'] else 'FAILED')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
