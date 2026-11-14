"""Compare paired baseline / one-seat neural matches, with timeouts in denominator."""
import argparse
import json
import math
from pathlib import Path
from eval import wilson


def compare(baseline, candidate, side):
    ids = sorted(candidate['ids'])
    changed = []
    gains = losses = wins = old_wins = timeouts = errors = 0
    for key in ids:
        a = baseline['matches'][key]
        b = candidate['matches'].get(key)
        aw = a['winner'] == side and not a['timeout'] and not a['ai_error']
        if b is None:
            old_wins += aw
            losses += aw
            continue
        if any(a[k] != b[k] for k in ('map', 'night', 'seed')):
            raise ValueError('unpaired scenario ' + key)
        bw = b['winner'] == side and not b['timeout'] and not b['ai_error']
        wins += bw
        old_wins += aw
        gains += bw and not aw
        losses += aw and not bw
        timeouts += b['timeout']
        errors += bool(b['ai_error'])
        if (a['winner'], a['timeout'], a['log_sha256']) != (b['winner'], b['timeout'], b['log_sha256']):
            changed.append(key)
    n = len(ids)
    discordant = gains + losses
    p = min(1., 2 * sum(math.comb(discordant, k) for k in range(min(gains, losses) + 1)) / 2**discordant) if discordant else 1.
    return dict(seat=side, matches=n, ids=ids, baseline_wins=old_wins, candidate_wins=wins,
                baseline_rate=old_wins / max(1, n), candidate_rate=wins / max(1, n), candidate_ci95=wilson(wins, n),
                gains=gains, losses=losses, paired_exact_p=p, timeouts=timeouts, ai_errors=errors,
                crashed=candidate['crashed'], changed_games=changed,
                stronger_supported=not errors and not candidate['crashed'] and gains > losses and p < .05)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--plant', type=Path, required=True)
    ap.add_argument('--zombie', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    read = lambda p: json.loads(p.read_text('utf-8'))
    baseline = read(args.baseline)
    result = {s: compare(baseline, read(p), s) for s, p in (('plant', args.plant), ('zombie', args.zombie))}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(result, ensure_ascii=False))
