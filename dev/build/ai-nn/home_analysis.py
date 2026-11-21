"""Summarize matched home outcomes and uncertainty across independent openings."""
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import gzip
import json
import shutil
import subprocess

import numpy as np

from home_pool import BIN, CURRENT, OUT, POOL, SIDES, footer, jointly_idle, measure, read, score, sha, write


POLICIES = {
    'r': '原生 r22',
    'o': '较早的神经快照',
    'n': '更新前的神经头',
    'a': '固定 r22',
    'b': '固定上一版神经对手',
    'h': '混合对手池',
}


def arm_for(side, policy, opponent):
    return policy + opponent if side == 'plant' else opponent + policy


def policy_scores(side, policy, ids):
    values = np.zeros((len(ids), len(POOL)), dtype=int)
    by_opponent = []
    outcome_changes = Counter()
    flagged = []
    timeouts = 0
    labels = {-1: 'L', 0: 'T', 1: 'W'}

    for col, opponent in enumerate(POOL):
        arm = arm_for(side, policy, opponent)
        parent_arm = arm_for(side, 'n', opponent)
        rows = read(OUT / 'test' / arm / 'ready.json')['rows']
        parent_rows = read(OUT / 'test' / parent_arm / 'ready.json')['rows']
        for i, uid in enumerate(ids):
            before, after = parent_rows[uid], rows[uid]
            old = score(before['match'], side)
            new = score(after['match'], side)
            values[i, col] = new
            change = labels[old] + labels[new]
            outcome_changes[change] += 1
            if after['match']['timeout']:
                timeouts += 1
                if jointly_idle(after, before):
                    flagged.append({'opponent': opponent, 'opening': uid, 'change': change})
        column = values[:, col]
        by_opponent.append([int((column == value).sum()) for value in (1, 0, -1)])

    opponent_totals = values.sum(axis=0)
    summary = dict(side=side, policy=policy, name=POLICIES[policy], WTL=by_opponent,
                   pooled_total=int(opponent_totals.sum()), worst_opponent_total=int(opponent_totals.min()),
                   timeouts=timeouts, changes_vs_parent=dict(outcome_changes), joint_idle_flags=flagged)
    return values, summary


def deployment_rates(arm):
    rows = read(OUT / 'test' / arm / 'ready.json')['rows']
    count = Counter()
    seconds = 0.0
    for row in rows.values():
        trace = footer(Path(row['trace']))
        seconds += trace['time']
        for side in SIDES:
            count[side] += measure(trace['activity'], side, trace['time'])['deploys']
    return {side: count[side] * 60 / seconds for side in SIDES}


def mixed_vs_r22():
    """Replay the mixed head on all the exact parent inputs used for the r22 comparison."""
    model = OUT / 'home-model' / 'model.json'
    updated, parent = read(model), read(CURRENT)
    for key in set(updated) | set(parent):
        if key not in {'heads', 'training_source'}:
            assert updated[key] == parent[key]
    assert updated['enabled_heads'] == [True, True, True, False]
    assert not updated.get('residual') and updated['heads']['bias'] == parent['heads']['bias']
    for i in (12, 13, 25, 26, 27):
        assert updated['heads']['weight'][i] == parent['heads']['weight'][i]

    counts = {side: Counter() for side in SIDES}
    root = OUT / 'train' / 'nn'
    with TemporaryDirectory(dir=OUT / 'temp') as directory:
        raw = Path(directory) / 'parent.jsonl'
        relabelled = Path(directory) / 'teacher.jsonl'
        for uid in read(OUT / 'plan.json')['train']:
            with gzip.open(root / 'archives' / (uid + '.jsonl.gz'), 'rb') as src, raw.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            assert sha(raw) == read(root / 'receipts' / (uid + '.json'))['raw_sha256']
            subprocess.run([BIN / 'teacher_trace.exe', raw, relabelled], check=True, stdout=subprocess.DEVNULL)
            with relabelled.open(encoding='utf8') as records, subprocess.Popen(
                    [BIN / 'neural_dataset.exe', '-', model, raw], stdout=subprocess.PIPE,
                    encoding='utf8') as encoder:
                states = (r for r in map(json.loads, records) if r['type'] == 'plan')
                encoded = (r for r in map(json.loads, encoder.stdout) if r['type'] == 'sample')
                for state, features in zip(states, encoded, strict=True):
                    side = state['seat']
                    assert (features['tick'], features['seat']) == (state['tick'], side)
                    executed, teacher = state['executed_plan'], state['plan']
                    candidate = executed.copy()
                    # Only the economy and grave output weights changed in this update.
                    if side == 'plant':
                        candidate['econ_goal'] = max(2, min(11, features['classes'][0]))
                    else:
                        goal = max(2, min(10, features['classes'][2]))
                        candidate['grave_start'] = candidate['grave_max'] = goal
                    counts[side]['replans'] += 1
                    counts[side]['parent_vs_r22'] += executed != teacher
                    counts[side]['mixed_vs_r22'] += candidate != teacher
                    counts[side]['mixed_vs_parent'] += candidate != executed
                assert encoder.wait() == 0
    original = read(OUT / 'current-vs-r22.json')
    for side in SIDES:
        assert counts[side]['replans'] == original[side]['replans']
        assert counts[side]['parent_vs_r22'] == original[side]['any_plan_difference']
    return counts


def details():
    completion = read(OUT / 'completion.json')
    ids = read(OUT / 'plan.json')['test']
    assert completion['heldout_openings'] == len(ids)
    table = []
    intervals = {}
    # Each bootstrap sample retains all three opponents from a given opening.
    rng = np.random.default_rng(812312)
    samples = rng.integers(0, len(ids), size=(20000, len(ids)))
    for side in SIDES:
        scores = {}
        for policy in POLICIES:
            scores[policy], summary = policy_scores(side, policy, ids)
            table.append(summary)
        for left, right in [('h', 'n'), ('h', 'a'), ('h', 'b'), ('a', 'n'), ('b', 'n'), ('h', 'o'), ('o', 'n')]:
            delta = (scores[left] - scores[right]).mean(axis=1)
            lo, hi = np.quantile(delta[samples].mean(axis=1), [.025, .975])
            intervals[f'{side}/{left}/{right}'] = [delta.mean(), lo, hi]

    rates = {arm: deployment_rates(arm) for arm in ('rr', 'nn', 'hh')}
    write(OUT / 'analysis.json', dict(scores=table, paired_bootstrap_mean_and_interval=intervals,
          same_state_plan_differences=mixed_vs_r22(),
          deploys_per_game_minute=rates, methods='WTL is per-seat W/T/L vs r22,old,parent. '
          'Pooled totals sum 36 games per seat. Worst opponent sums one group of 12. '
          '95% bootstrap intervals resample 12 opening indices, keeping opponents together.'))


if __name__ == '__main__':
    details()
