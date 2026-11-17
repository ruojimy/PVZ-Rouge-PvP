"""Reproducible capacity comparison on a predeclared, seed-disjoint study split.

Test labels are not scored here. All old/observed data are explicitly training data.
Every architecture has the same seeds, optimizer grid, data and early-stop budget.
The C++ runtime already accepts these widths, so no production change is needed.
"""
import argparse
import copy
import hashlib
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from train import DeepSet, HEADS, OFFSETS, batches, collate, measure, read_data


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_model(model, header, spec, folder, data_sha, enabled):
    folder.mkdir(parents=True)
    doc = {k: header[k] for k in ('catalog_hash', 'rules_hash', 'behaviors', 'sim_fingerprint')}
    doc.update(format='pvz-deepset-hybrid-1', embedding=spec['embedding'], hidden=spec['hidden'],
               hybrid=True, enabled_heads=enabled, data_sha256=data_sha,
               head_names=list(HEADS), study_spec=spec)
    for key in ('unit', 'body', 'heads'):
        layer = getattr(model, key)
        doc[key] = dict(weight=layer.weight.detach().tolist(), bias=layer.bias.detach().tolist())
    (folder / 'model.json').write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), 'utf-8')
    torch.save(dict(state_dict=model.state_dict(), spec=spec, feature_header=header), folder / 'selected.pt')


def from_export(path):
    doc = json.loads(path.read_text('utf-8'))
    model = DeepSet(16 + len(doc['behaviors']), doc['embedding'], doc['hidden'])
    with torch.no_grad():
        for key in ('unit', 'body', 'heads'):
            layer = getattr(model, key)
            layer.weight.copy_(torch.tensor(doc[key]['weight']))
            layer.bias.copy_(torch.tensor(doc[key]['bias']))
    return doc, model


def split_rows(rows, plan):
    assignment = {r['id']: r['part'] for r in plan['entries']}
    split = {k: [] for k in ('train', 'validation', 'test')}
    for row in rows:
        part = 'train' if row['id'].startswith('old-') else assignment[row['id']]
        if part == 'train' or not row.get('aug'):
            split[part].append(row)
    # Keep evaluation denominators fixed; remove cross-partition duplicates from training.
    # This is a fixed preprocessing rule, independent of model predictions or performance.
    digest = lambda r: hashlib.sha256(r['g'].numpy().tobytes() + r['own'].numpy().tobytes() +
                                     r['enemy'].numpy().tobytes() + r['y'].numpy().tobytes()).digest()
    held = {digest(r) for part in ('validation', 'test') for r in split[part]}
    before = len(split['train'])
    split['train'] = [r for r in split['train'] if digest(r) not in held]
    return split, before - len(split['train'])


def weighted_batches(rows, size):
    ids = list(range(len(rows)))
    random.shuffle(ids)
    for start in range(0, len(ids), size):
        selected = [rows[i] for i in ids[start:start + size]]
        x, side, y = collate(selected)
        weights = torch.tensor([0.25 if r.get('aug') else 1.0 for r in selected])
        yield x, side, y, weights


def loss(logits, side, y, weight):
    terms = []
    for h in range(3):  # save is deliberately left under r22; no one-class objective dilutes validation.
        mask = side if h < 2 else ~side
        if mask.any():
            v = torch.nn.functional.cross_entropy(logits[mask, OFFSETS[h]:OFFSETS[h+1]], y[mask, h], reduction='none')
            terms.append((v * weight[mask]).sum() / weight[mask].sum())
    return torch.stack(terms).mean()


@torch.no_grad()
def score(model, rows):
    result = measure(model, rows, 256)
    weighted = count = 0
    for x, side, y in batches(rows, 256):
        weighted += float(loss(model(*x), side, y, torch.ones(len(y)))) * len(y)
        count += len(y)
    result['active_heads_loss'] = weighted / count
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--study', type=Path, required=True)
    ap.add_argument('--threads', type=int, default=2)
    args = ap.parse_args()
    base = args.study.resolve()
    out = base / 'training'
    if out.exists():
        raise SystemExit('Use a fresh study output; checkpoints are immutable')
    out.mkdir()
    plan = json.loads((base / 'plan.json').read_text('utf-8'))
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    header, rows = read_data(base / 'dataset.jsonl')
    split, removed = split_rows(rows, plan)
    split_doc = {part: dict(ids=sorted({r['id'] for r in rr}), samples=len(rr),
                          original_samples=sum(not r.get('aug') for r in rr)) for part, rr in split.items()}
    (out / 'split.json').write_text(json.dumps(dict(parts=split_doc, duplicate_train_rows_removed=removed), indent=2), 'utf-8')
    old_header, old_model = from_export(Path(plan['original_model']))
    for key in ('sim_fingerprint', 'behaviors', 'catalog_hash', 'rules_hash'):
        assert header[key] == old_header[key], key
    report = dict(format='pvz-ai-capacity-study-1', torch=str(torch.__version__), device='cpu',
        plan_sha256=sha(base / 'plan.json'), data_sha256=sha(base / 'dataset.jsonl'), split=split_doc,
        augmentation_weight=0.25, active_heads=[0, 1, 2], save_head_enabled=False,
        original_validation=score(old_model, split['validation']), candidates=[], selected={})
    started = time.perf_counter()
    for arch in plan['architectures']:
        best_score, best_state, best_spec = float('inf'), None, None
        for seed in plan['training_seeds']:
            rates = [(lr, False) for lr in plan['learning_rates']]
            if arch['name'] == 'compact':
                rates.append((0.0003, True))
            for lr, warm in rates:
                random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
                model = DeepSet(16 + len(header['behaviors']), arch['embedding'], arch['hidden'])
                if warm:
                    model.load_state_dict(old_model.state_dict())
                optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0001)
                local_best, state, stale, history = float('inf'), None, 0, []
                for epoch in range(plan['epochs']):
                    model.train()
                    for x, side, y, weights in weighted_batches(split['train'], 256):
                        optimizer.zero_grad(set_to_none=True)
                        value = loss(model(*x), side, y, weights)
                        value.backward()
                        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                        optimizer.step()
                    model.eval()
                    metrics = score(model, split['validation'])
                    value = metrics['active_heads_loss']
                    history.append(dict(epoch=epoch+1, loss=value,
                        heads={h: metrics['heads'][h]['accuracy'] for h in HEADS[:3]}))
                    if value < local_best:
                        local_best, state, stale = value, copy.deepcopy(model.state_dict()), 0
                    else:
                        stale += 1
                    if epoch % 5 == 0:
                        print(json.dumps(dict(architecture=arch['name'], seed=seed, lr=lr, warm=warm, epoch=epoch+1,
                                              validation_loss=value, best=local_best)), flush=True)
                    if stale >= plan['patience']:
                        break
                spec = dict(**arch, lr=lr, seed=seed, warm_start=warm,
                            original_sha256=plan['original_model_sha256'] if warm else None)
                candidate = dict(spec=spec, best_validation_loss=local_best, history=history,
                                 parameters=sum(p.numel() for p in model.parameters()))
                report['candidates'].append(candidate)
                model.load_state_dict(state)
                save_model(model, header, spec, out / f"{arch['name']}-s{seed}-lr{lr}", report['data_sha256'], [True, True, True, False])
                if local_best < best_score:
                    best_score, best_state, best_spec = local_best, state, spec
                (out / 'progress.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        model.load_state_dict(best_state)
        folder = out / arch['name']
        save_model(model, header, best_spec, folder, report['data_sha256'], [True, True, True, False])
        report['selected'][arch['name']] = dict(spec=best_spec, validation=score(model, split['validation']),
            train=score(model, split['train']), model_sha256=sha(folder / 'model.json'),
            parameters=sum(p.numel() for p in model.parameters()))
    report['wall_seconds'] = time.perf_counter() - started
    report['test_scored'] = False
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(dict(completed=True, selected={k: v['spec'] for k, v in report['selected'].items()},
                         wall_seconds=report['wall_seconds'])), flush=True)


if __name__ == '__main__':
    main()
