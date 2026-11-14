"""Train/compare small DeepSets behavior-cloning candidates on canonical C++ features.

No game credentials or external service. Whole maps are held out; the test split
is evaluated only after model selection. This is imitation, not a strength claim.
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
from torch import nn
from torch.nn.utils.rnn import pad_sequence

OFFSETS = (0, 11, 13, 24, 27)
HEADS = ("econ_goal", "plant_mode", "grave_goal", "zombie_save")


class DeepSet(nn.Module):
    def __init__(self, unit_dim, embedding=8, hidden=64):
        super().__init__()
        self.unit = nn.Linear(unit_dim, embedding)
        self.body = nn.Linear(20 + 4 * embedding, hidden)
        self.heads = nn.Linear(hidden, 27)

    def forward(self, g, own, enemy, own_mask, enemy_mask):
        groups = [g]
        for rows, mask in ((own, own_mask), (enemy, enemy_mask)):
            h = torch.relu(self.unit(rows)) * mask.unsqueeze(-1)
            groups.extend((h.sum(1) / 10, h.amax(1)))
        return self.heads(torch.relu(self.body(torch.cat(groups, 1))))


def collate(rows):
    g = torch.stack([r["g"] for r in rows])
    sides = torch.tensor([r["plant"] for r in rows], dtype=torch.bool)
    y = torch.stack([r["y"] for r in rows])
    arrays, masks = [], []
    for name in ("own", "enemy"):
        seq = [r[name] for r in rows]
        arrays.append(pad_sequence(seq, batch_first=True))
        masks.append(pad_sequence([torch.ones(len(s)) if r[name + "_count"] else torch.zeros(1)
                                   for s, r in zip(seq, rows)], batch_first=True))
    return (g, *arrays, *masks), sides, y


def read_data(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        header = json.loads(next(f))
        dim = 16 + len(header["behaviors"])
        for line in f:
            r = json.loads(line)
            r["g"] = torch.tensor(r["x"]["global"], dtype=torch.float32)
            r["y"] = torch.tensor(r["y"], dtype=torch.long)
            r["plant"] = r["seat"] == "plant"
            for key in ("own", "enemy"):
                a = r["x"][key]
                r[key + "_count"] = len(a)
                r[key] = torch.tensor(a or [[0.] * dim], dtype=torch.float32)
            del r["x"]
            rows.append(r)
    return header, rows


def batches(rows, batch_size, shuffle=False):
    indices = list(range(len(rows)))
    if shuffle:
        random.shuffle(indices)
    for i in range(0, len(indices), batch_size):
        yield collate([rows[k] for k in indices[i:i + batch_size]])


def loss_for(logits, plant, labels):
    terms = []
    for h in range(4):
        mask = plant if h < 2 else ~plant
        if mask.any():
            terms.append(nn.functional.cross_entropy(logits[mask, OFFSETS[h]:OFFSETS[h+1]], labels[mask, h]))
    return torch.stack(terms).mean()


@torch.no_grad()
def measure(model, rows, batch_size):
    correct, count = np.zeros(4, dtype=int), np.zeros(4, dtype=int)
    exact = total = 0
    confusion = [np.zeros((OFFSETS[h+1]-OFFSETS[h],) * 2, dtype=int) for h in range(4)]
    loss_sum = 0.
    for x, plant, y in batches(rows, batch_size):
        logits = model(*x)
        loss_sum += float(loss_for(logits, plant, y)) * len(y)
        ok = torch.ones(len(y), dtype=torch.bool)
        for h in range(4):
            mask = plant if h < 2 else ~plant
            same = logits[:, OFFSETS[h]:OFFSETS[h+1]].argmax(1) == y[:, h]
            pred = logits[:, OFFSETS[h]:OFFSETS[h+1]].argmax(1)
            np.add.at(confusion[h], (y[mask, h].numpy(), pred[mask].numpy()), 1)
            correct[h] += int((same & mask).sum())
            count[h] += int(mask.sum())
            ok &= same | ~mask
        exact += int(ok.sum())
        total += len(y)
    return dict(samples=total, loss=loss_sum / max(1, total), exact_plan_heads=exact,
                exact_plan_heads_rate=exact / max(1, total),
                heads={k: dict(correct=int(c), samples=int(n), accuracy=int(c)/max(1, int(n)),
                               confusion=matrix.tolist(), class_support=matrix.sum(1).tolist())
                       for k, c, n, matrix in zip(HEADS, correct, count, confusion)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--initial", type=Path, help="Warm-start a previous checkpoint; Adam state starts fresh")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("Use a new output directory to preserve checkpoints")
    args.out.mkdir(parents=True)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    header, rows = read_data(args.data)
    initial = torch.load(args.initial, map_location='cpu', weights_only=True) if args.initial else None
    if initial and any(initial['feature_header'][k] != header[k] for k in ('sim_fingerprint', 'behaviors')):
        raise SystemExit('Warm-start checkpoint uses a different simulation or encoder')
    maps = sorted({r["map"] for r in rows})
    if len(maps) < 6:
        raise SystemExit("Need at least six complete maps for a map-disjoint split")
    # Freeze before fitting: 7 train / 2 validation / 3 test maps for the 12-map corpus.
    test_maps, validation_maps = set(maps[-3:]), set(maps[-5:-3])
    split = {"train": [], "validation": [], "test": []}
    for r in rows:
        part = "test" if r["map"] in test_maps else "validation" if r["map"] in validation_maps else "train"
        split[part].append(r)
    # Prevent identical feature/label records crossing a split (e.g. empty openings).
    seen = set()
    for part in ("test", "validation", "train"):
        keep, hashes = [], set()
        for r in split[part]:
            digest = hashlib.sha256(r["g"].numpy().tobytes() + r["own"].numpy().tobytes() +
                                    r["enemy"].numpy().tobytes() + r["y"].numpy().tobytes()).digest()
            if digest not in seen:
                keep.append(r)
                hashes.add(digest)
        split[part] = keep
        seen |= hashes
    split_doc = {p: dict(maps=sorted({r["map"] for r in rr}), ids=sorted({r["id"] for r in rr}),
                         samples=len(rr)) for p, rr in split.items()}
    (args.out / "split.json").write_text(json.dumps(split_doc, ensure_ascii=False, indent=2), "utf-8")
    report = dict(format="pvz-neural-training-1", torch=torch.__version__, device="cpu", seed=743,
                  data_sha256=hashlib.sha256(args.data.read_bytes()).hexdigest(), split=split_doc, candidates=[])
    best, best_state, best_spec = float("inf"), None, None
    started = time.perf_counter()
    configs = ((32, .003), (64, .003), (64, .001))
    if initial:
        width = initial['spec']['hidden'] if 'spec' in initial else initial['hidden']
        configs = tuple((width, lr) for lr in (.001, .0003, .0001))
        report['warm_start_sha256'] = hashlib.sha256(args.initial.read_bytes()).hexdigest()
    for hidden, lr in configs:
        random.seed(743);np.random.seed(743);torch.manual_seed(743)
        model = DeepSet(16 + len(header["behaviors"]), hidden=hidden)
        if initial:
            model.load_state_dict(initial['state_dict'])
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        history, local_best, state = [], float("inf"), None
        for epoch in range(args.epochs):
            model.train()
            for x, plant, y in batches(split["train"], args.batch_size, True):
                opt.zero_grad(set_to_none=True)
                loss = loss_for(model(*x), plant, y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                opt.step()
            model.eval()
            validation = measure(model, split["validation"], args.batch_size)
            history.append(dict(epoch=epoch + 1, **validation))
            if validation["loss"] < local_best:
                local_best = validation["loss"]
                state = copy.deepcopy(model.state_dict())
            print(json.dumps(dict(hidden=hidden, lr=lr, epoch=epoch + 1, validation_loss=validation["loss"])), flush=True)
        candidate = dict(hidden=hidden, lr=lr, best_validation_loss=local_best, history=history)
        report["candidates"].append(candidate)
        torch.save(dict(state_dict=state, hidden=hidden, embedding=8, feature_header=header), args.out / f"candidate-h{hidden}-lr{lr}.pt")
        if local_best < best:
            best, best_state, best_spec = local_best, state, dict(hidden=hidden, lr=lr)
    model = DeepSet(16 + len(header["behaviors"]), hidden=best_spec["hidden"])
    model.load_state_dict(best_state);model.eval()
    report["selected"] = best_spec
    report["metrics"] = {p: measure(model, rr, args.batch_size) for p, rr in split.items()}
    report["wall_seconds"] = time.perf_counter() - started
    export = {k: header[k] for k in ("catalog_hash", "rules_hash", "behaviors", "sim_fingerprint")}
    export.update(format="pvz-deepset-hybrid-1", embedding=8, hidden=best_spec["hidden"],
                  data_sha256=report["data_sha256"], heads=list(HEADS), hybrid=True)
    export['enabled_heads'] = [sum(n > 0 for n in report['metrics']['train']['heads'][key]['class_support']) >= 2 for key in HEADS]
    report['enabled_heads'] = dict(zip(HEADS, export['enabled_heads']))
    for key, layer in (("unit", model.unit), ("body", model.body), ("heads", model.heads)):
        export[key] = dict(weight=layer.weight.detach().tolist(), bias=layer.bias.detach().tolist())
    (args.out / "model.json").write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":")), "utf-8")
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    torch.save(dict(state_dict=best_state, spec=best_spec, feature_header=header), args.out / "selected.pt")
    print(json.dumps(dict(selected=best_spec, test=report["metrics"]["test"], wall_seconds=report["wall_seconds"])), flush=True)


if __name__ == "__main__":
    main()
