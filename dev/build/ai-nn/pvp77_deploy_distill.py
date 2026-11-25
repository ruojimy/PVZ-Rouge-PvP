"""Qualify a deployment teacher on inherited controller states before distilling it."""
import argparse
import gzip
import json
from pathlib import Path
import time

from league_data import read, sha
from league_matches import summarize
import pvp77_inherited_league as league


card, native = league.card, league.native
RUN = league.RUN.with_name('inherited-deploy-distill-pvp77-r4-20261124')
CONDITIONS = ('normal', 'economy', 'late')
SCREEN, DATA, TEST = 78300000, 78400000, 78500000


def play_pair(heads, case, model=None, trace=None):
    side, seed, condition = case
    sc, targeted = league.opening(seed, heads, condition if condition != 'normal' else None)
    other = league.evolution.other(side)
    opponent = league.HISTORIC[other] if seed % 2 else league.R22
    with card.battle.cold_opening(sc) as cold:
        if trace is not None:
            raw = cold / 'choices.jsonl'
            game = league.played(cold, 'capture', sc, side, league.PARENT[side], opponent, deploy_trace=raw)
            data = []
            with raw.open(encoding='utf-8') as source:
                for line in source:
                    row = json.loads(line)
                    if row['side'] == side:
                        data.append(row['features'])
            with gzip.open(trace.with_suffix('.partial'), 'wt', compresslevel=4, encoding='utf-8') as file:
                json.dump({'opening': sc, 'game': game, 'choices': data}, file, ensure_ascii=False)
            trace.with_suffix('.partial').replace(trace)
            return
        old = league.played(cold, 'old', sc, side, league.PARENT[side], opponent)
        new = league.played(cold, 'local', sc, side, league.PARENT[side], opponent, deploy=side, deploy_model=model)
    return {'side': side, 'condition': condition, 'targeted': targeted, 'opening': sc, 'opponent': str(opponent),
            'old': old, 'new': new}


def stats(side, rows):
    metric = summarize([league.comparison(side, row['opponent'], row['opening']['seed'], row['old'], row['new'])
                        for row in rows], side)
    counts = [row['new']['deploy_policy'] for row in rows]
    metric['swaps'] = sum(v['swaps'] for v in counts)
    metric['fallbacks'] = sum(v['fallbacks'] for v in counts)
    metric['qualified'] = bool(len(rows) >= 6 and metric['swaps'] and not metric['fallbacks']
                               and league.qualifies(metric, 2))
    return metric


def subgroup(rows, side, condition):
    return [r for r in rows if r['side'] == side and r['condition'] == condition
            and (condition == 'normal' or any(v['applied'] for v in r['targeted']))]


def fit(side, teacher, files, output):
    import torch
    from torch import nn
    from torch.nn import functional as F

    rows = {'train': [], 'validation': []}
    for i, file in enumerate(sorted(files)):
        with gzip.open(file, 'rt', encoding='utf-8') as src:
            rows['validation' if i % 4 == 0 else 'train'].extend(json.load(src)['choices'])
    if len(rows['train']) < 64 or len(rows['validation']) < 8:
        return None
    src = read(teacher)['sides'][side]
    hidden, bias, head = (torch.tensor(src[key]) for key in ('hidden', 'bias', 'output'))
    chosen = torch.argsort(head.abs(), descending=True)[:16]
    model = nn.Sequential(nn.Linear(24, len(chosen)), nn.ReLU(), nn.Linear(len(chosen), 1))
    with torch.no_grad():
        model[0].weight.copy_(hidden[chosen])
        model[0].bias.copy_(bias[chosen])
        model[2].weight.copy_(head[chosen].unsqueeze(0))
        model[2].bias.zero_()

    def batch(values):
        inputs = torch.zeros(len(values), 10, 24)
        valid = torch.zeros(len(values), 10, dtype=torch.bool)
        for i, v in enumerate(values):
            inputs[i, :len(v)] = torch.tensor(v)
            valid[i, 1:len(v)] = True
        with torch.no_grad():
            raw = (inputs @ hidden.T + bias).relu() @ head
        return inputs, valid, raw - raw[:, :1]

    x, mask, target = batch(rows['train'])
    dev, dmask, dtarget = batch(rows['validation'])
    torch.manual_seed(77)
    opt = torch.optim.AdamW(model.parameters(), lr=.002)

    def value(x):
        scores = model(x).squeeze(-1)
        return scores - scores[:, :1]

    for _ in range(20):
        for ids in torch.randperm(len(x)).split(128):
            opt.zero_grad()
            loss = F.smooth_l1_loss(value(x[ids])[mask[ids]], target[ids][mask[ids]])
            loss.backward()
            opt.step()
    with torch.no_grad():
        v = value(dev)
        gap = float((v[dmask] - dtarget[dmask]).abs().mean())
        dmask[:, 0] = True
        v[:, 0] = dtarget[:, 0] = .35
        match = float((v.masked_fill(~dmask, -torch.inf).argmax(1)
                       == dtarget.masked_fill(~dmask, -torch.inf).argmax(1)).float().mean())
    params = model.state_dict()
    native.write_atomic(output, {'format': 'pvz77-deploy-rank-1', 'features': 24, 'sides': {side: {
        'hidden': params['0.weight'].tolist(), 'bias': params['0.bias'].tolist(),
        'output': params['2.weight'][0].tolist(), 'intercept': 0.,
    }}})
    return {'teacher_sha256': sha(teacher), 'sha256': sha(output), 'train': len(x), 'validation': len(dev),
            'mean_pair_score_error': gap, 'relative_action_match': match}


def run(heads, lanes):
    teachers = {s: card.deploy_candidate(s)[0] for s in native.SIDES}
    native.write_atomic(RUN / 'teacher-plan.json', {
        'teacher_sha256': {s: sha(p) for s, p in teachers.items()},
        'conditions': CONDITIONS, 'screen_seed': SCREEN, 'data_seed': DATA, 'test_seed': TEST,
        'min_pairs': 6, 'min_additional_true_wins': 2, 'r22_and_historical_opponents': True,
        'distill_target': 'relative scores for identical native legal deploy candidates',
    })
    jobs = {f'{s}-{condition}-{i}': (s, SCREEN + 100 * j + i, condition)
            for s in native.SIDES for j, condition in enumerate(CONDITIONS) for i in range(8)}
    scanned = league.stage(RUN / 'comparison', 'teacher-screen', jobs, lambda c: play_pair(heads, c),
                           lanes, native.DEADLINE - 3600)
    report = {}
    for side in native.SIDES:
        report[side] = {}
        for j, condition in enumerate(CONDITIONS):
            rows = subgroup(scanned.values(), side, condition)
            if not rows:
                continue
            summary = stats(side, rows)
            report[side][condition] = {'teacher': summary}
            if len(scanned) != len(jobs) or not summary['qualified'] or native.STOP.exists() or native.seconds_left() < 900:
                continue
            data = RUN / 'data' / f'{side}-{condition}'
            data.mkdir(parents=True, exist_ok=True)

            def capture(i):
                target = data / f'{i}.json.gz'
                if not target.exists():
                    play_pair(heads, (side, DATA + 100*j + i, condition), trace=target)

            native.status('teacher-distill', side=side, condition=condition)
            native.work(range(8), capture, lambda _: None, lanes, native.DEADLINE - 900)
            model = data / 'distilled.json'
            check = fit(side, teachers[side], data.glob('*.json.gz'), model)
            if check is None:
                continue
            report[side][condition]['fit'] = check
            extra = {f'{i:02}': (side, TEST + 100*j + i, condition) for i in range(12)}
            tested = league.stage(data / 'holdout', 'teacher-distill-test', extra, lambda c: play_pair(heads, c, model=model),
                                 lanes, native.DEADLINE - 60)
            valid = subgroup(tested.values(), side, condition)
            if valid:
                report[side][condition]['distilled'] = stats(side, valid)
                report[side][condition]['admitted'] = len(tested) == len(extra) and stats(side, valid)['qualified']
    native.write_atomic(RUN / 'summary.json', report)
    native.status('stopped' if native.STOP.exists() else 'finished', teacher_receipts=len(scanned), summary=str(RUN / 'summary.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lanes', type=int, default=3)
    args = parser.parse_args()
    league.RUN = RUN
    with league.exclusive():
        league.setup()
        import torch
        torch.set_num_threads(1)
        try:
            run(card.draft_heads(), args.lanes)
        except Exception as exc:
            native.status('failed', error=repr(exc))
            raise


if __name__ == '__main__':
    main()
