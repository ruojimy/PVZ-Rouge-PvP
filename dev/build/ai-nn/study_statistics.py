"""Post-selection statistics. Does not pick or modify a checkpoint."""
import argparse
import json
from pathlib import Path
import numpy as np


def read(p):
    return json.loads(p.read_text('utf-8'))


def paired(a, b, seat):
    ids = list(a['ids'])
    assert set(ids) == set(b['ids'])
    blocks = {}
    for key in ids:
        ra, rb = a['matches'][key], b['matches'].get(key)
        win = lambda r: bool(r and r['winner']==seat and not r['timeout'] and not r['ai_error'])
        blocks.setdefault(ra['map'], []).append(int(win(rb))-int(win(ra)))
    rng = np.random.default_rng(161116)
    sums = np.array([sum(v) for v in blocks.values()])
    sizes = np.array([len(v) for v in blocks.values()])
    picked = rng.integers(0, len(blocks), (20000, len(blocks)))
    values = sums[picked].sum(1) / sizes[picked].sum(1)
    return dict(paired_win_rate_difference=float(sums.sum()/sizes.sum()),
                map_block_bootstrap_ci95=np.quantile(values, [.025, .975]).tolist(),
                map_blocks=len(blocks), resamples=20000,
                note='Exploratory map-cluster interval; shared seeds across maps remain correlated.')


ap = argparse.ArgumentParser()
ap.add_argument('--study', type=Path, required=True)
args = ap.parse_args()
base = args.study
assert read(base / 'run.json')['completed']
strength = read(base / 'strength.json')
selection = read(base / 'selection.json')['selected']
baseline = read(base / 'test-r22/summary.json')
result = {}
for seat in ('plant', 'zombie'):
    old = read(base / f'test-original-{seat}/summary.json')
    name = selection[seat]['name']
    selected = baseline if name=='r22' else old if name=='original' else read(base / f'test-selected-{seat}/summary.json')
    result['selected-'+seat] = paired(baseline, selected, seat)
    result['selected-vs-original-'+seat] = paired(old, selected, seat)
pvalues = sorted((strength['comparisons'][key]['paired_exact_p'], key) for key in result)
running = 0.0
for rank, (p, key) in enumerate(pvalues):
    running = max(running, min(1.0, p*(len(pvalues)-rank)))
    result[key]['paired_exact_p_holm_four_comparisons'] = running
    result[key]['improvement_supported_after_multiplicity'] = bool(running < .05 and
        result[key]['paired_win_rate_difference'] > 0 and not strength['comparisons'][key]['crashed'] and
        not strength['comparisons'][key]['ai_errors'])
(base / 'statistics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(result, ensure_ascii=False))
