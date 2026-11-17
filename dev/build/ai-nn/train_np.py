"""NumPy reference trainer for the DeepSets planner (no PyTorch needed).

Same loss and pooling as train.py. It exists to compare network sizes, splits, summary inputs and
augmentation on a machine without PyTorch; the numbers in docs/ai-nn were produced with it. With one
unit layer, one body layer and no --aggregates it writes a model.json the C++ planner loads.

  python build/ai-nn/train_np.py --data dataset.jsonl[.gz] --out run1 [--unit 8] [--body 64]
      [--split map|opening] [--extra-test other.jsonl] [--epochs 30] [--lr 0.003] [--cosine] [--aggregates]
"""
import argparse, gzip, hashlib, json, time
from pathlib import Path
import numpy as np

OFFSETS = (0, 11, 13, 24, 27)
HEADS = ("econ_goal", "plant_mode", "grave_goal", "zombie_save")


def open_text(path):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def read_data(paths, use_aggregates=False):
    header, G, Y, meta = None, [], [], dict(id=[], map=[], plant=[], aug=[])
    rows, lens = dict(own=[], enemy=[]), dict(own=[], enemy=[])
    for path in paths:
        with open_text(path) as f:
            h = json.loads(next(f))
            if header is None:
                header = h
            elif any(h[k] != header[k] for k in ("behaviors", "sim_fingerprint", "catalog_hash", "rules_hash")):
                raise SystemExit("datasets were encoded by different builds: " + str(path))
            for line in f:
                r = json.loads(line)
                G.append(r["x"]["global"]); Y.append(r["y"])
                meta["id"].append(r["id"]); meta["map"].append(r["map"]); meta["plant"].append(r["seat"] == "plant"); meta["aug"].append(r.get("aug", 0))
                for k in ("own", "enemy"):
                    a = r["x"][k]; lens[k].append(len(a))
                    if a: rows[k].append(np.asarray(a, np.float32))
    dim = 16 + len(header["behaviors"])
    data = dict(G=np.asarray(G, np.float32), Y=np.asarray(Y, np.int64), plant=np.asarray(meta["plant"]),
                id=np.asarray(meta["id"]), map=np.asarray(meta["map"]), aug=np.asarray(meta["aug"]))
    data["aug"] = np.asarray(meta["aug"], np.int64)
    for k in ("own", "enemy"):
        data[k] = np.concatenate(rows[k]) if rows[k] else np.zeros((0, dim), np.float32)
        data[k + "_ptr"] = np.concatenate(([0], np.cumsum(lens[k]))).astype(np.int64)
    if use_aggregates: data["G"] = np.concatenate([data["G"], aggregates(header, data)], 1)
    return header, data


FIRE = ("shoot", "reed61", "flying56", "mortar")


def aggregates(header, data):
    """Ten summary inputs computed from the unit rows (the C++ forward derives the same ones)."""
    beh = header["behaviors"]; fire = [16 + beh.index(b) for b in FIRE if b in beh]; out = []
    def seg(key, values):
        ptr = data[key + "_ptr"]; c = np.concatenate(([0.], np.cumsum(values, dtype=np.float64)))
        return (c[ptr[1:]] - c[ptr[:-1]]).astype(np.float32)
    for key in ("own", "enemy"):
        r = data[key]
        out += [seg(key, r[:, fire].sum(1)) / 10, seg(key, r[:, 12]) / 10, seg(key, r[:, 9] * (1 - r[:, 12])) / 2,
                seg(key, r[:, 9] * r[:, 6] * r[:, 15]), seg(key, r[:, 8]) / 10]
    return np.stack(out, 1)


def gather(data, key, idx):
    ptr = data[key + "_ptr"]; starts = ptr[idx]; lens = ptr[idx + 1] - starts; total = int(lens.sum())
    first = np.cumsum(lens) - lens
    rowidx = np.repeat(starts - first, lens) + np.arange(total)
    return data[key][rowidx], np.repeat(np.arange(len(idx)), lens), first[lens > 0], lens > 0


def init(spec, unit_dim, rng):
    def dense(i, o):
        bound = 1 / np.sqrt(i)  # torch.nn.Linear default
        return [rng.uniform(-bound, bound, (o, i)).astype(np.float32), rng.uniform(-bound, bound, o).astype(np.float32)]
    sizes = [unit_dim] + list(spec["unit"]); unit = [dense(a, b) for a, b in zip(sizes, sizes[1:])]
    sizes = [spec.get("globals", 20) + 4 * spec["unit"][-1]] + list(spec["body"]); body = [dense(a, b) for a, b in zip(sizes, sizes[1:])]
    return dict(unit=unit, body=body, heads=dense(spec["body"][-1], 27))


def forward(p, data, idx, keep=False):
    cache = dict(groups=[]); x = [data["G"][idx]]
    for key in ("own", "enemy"):
        rows, seg, first, nonempty = gather(data, key, idx)
        acts = [rows]
        for w, b in p["unit"]:
            acts.append(np.maximum(acts[-1] @ w.T + b, 0))
        h = acts[-1]; E = h.shape[1]
        s = np.zeros((len(idx), E), h.dtype); m = np.zeros((len(idx), E), h.dtype)
        if len(h):
            s[nonempty] = np.add.reduceat(h, first, axis=0) / 10; m[nonempty] = np.maximum.reduceat(h, first, axis=0)
        x += [s, m]
        if keep: cache["groups"].append((acts, seg, m))
    acts = [np.concatenate(x, 1)]
    for w, b in p["body"]:
        acts.append(np.maximum(acts[-1] @ w.T + b, 0))
    logits = acts[-1] @ p["heads"][0].T + p["heads"][1]
    cache["body"] = acts
    return logits, cache


def loss_grad(logits, plant, y):
    grad = np.zeros_like(logits); terms = []
    for h in range(4):
        mask = plant if h < 2 else ~plant
        if not mask.any(): continue
        z = logits[mask, OFFSETS[h]:OFFSETS[h + 1]].astype(np.float64)
        z -= z.max(1, keepdims=True); logp = z - np.log(np.exp(z).sum(1, keepdims=True))
        t = y[mask, h]; terms.append(-logp[np.arange(len(t)), t].mean())
        g = np.exp(logp); g[np.arange(len(t)), t] -= 1
        grad[np.flatnonzero(mask)[:, None], np.arange(OFFSETS[h], OFFSETS[h + 1])[None]] = g / len(t)
    return float(np.mean(terms)), grad / len(terms)


def backward(p, cache, dlogits):
    grads = dict(unit=[[np.zeros_like(w), np.zeros_like(b)] for w, b in p["unit"]], body=[None] * len(p["body"]))
    acts = cache["body"]
    grads["heads"] = [dlogits.T @ acts[-1], dlogits.sum(0)]
    d = dlogits @ p["heads"][0]
    for i in range(len(p["body"]) - 1, -1, -1):
        d = d * (acts[i + 1] > 0); grads["body"][i] = [d.T @ acts[i], d.sum(0)]; d = d @ p["body"][i][0]
    E = p["unit"][-1][0].shape[0]; G0 = d.shape[1] - 4 * E
    for g, (uacts, seg, m) in enumerate(cache["groups"]):
        if not len(seg): continue
        ds = d[:, G0 + 2 * g * E:G0 + (2 * g + 1) * E]; dm = d[:, G0 + (2 * g + 1) * E:G0 + (2 * g + 2) * E]
        h = uacts[-1]; dh = ds[seg] / 10 + dm[seg] * (h == m[seg])
        for i in range(len(p["unit"]) - 1, -1, -1):
            dh = dh * (uacts[i + 1] > 0); grads["unit"][i][0] += dh.T @ uacts[i]; grads["unit"][i][1] += dh.sum(0)
            if i: dh = dh @ p["unit"][i][0]
    return grads


def flat(p):
    return [a for w, b in p["unit"] for a in (w, b)] + [a for w, b in p["body"] for a in (w, b)] + list(p["heads"])


def measure(p, data, idx, batch=1024):
    correct, count, loss, exact = np.zeros(4, int), np.zeros(4, int), 0., 0
    confusion = [np.zeros((OFFSETS[h + 1] - OFFSETS[h],) * 2, int) for h in range(4)]
    for i in range(0, len(idx), batch):
        b = idx[i:i + batch]; logits, _ = forward(p, data, b); plant, y = data["plant"][b], data["Y"][b]
        loss += loss_grad(logits, plant, y)[0] * len(b); ok = np.ones(len(b), bool)
        for h in range(4):
            mask = plant if h < 2 else ~plant
            pred = logits[:, OFFSETS[h]:OFFSETS[h + 1]].argmax(1); same = pred == y[:, h]
            np.add.at(confusion[h], (y[mask, h], pred[mask]), 1)
            correct[h] += int((same & mask).sum()); count[h] += int(mask.sum()); ok &= same | ~mask
        exact += int(ok.sum())
    return dict(samples=len(idx), loss=loss / max(1, len(idx)), exact_plan_heads_rate=exact / max(1, len(idx)),
                heads={k: dict(correct=int(c), samples=int(n), accuracy=int(c) / max(1, int(n)),
                               within_one=float((np.abs(np.subtract.outer(np.arange(len(m)), np.arange(len(m)))) <= 1)[m > 0].dot(m[m > 0]) / max(1, m.sum())),
                               confusion=m.tolist()) for k, c, n, m in zip(HEADS, correct, count, confusion)})


def train(spec, data, split, epochs, batch, lr, seed, log=print, weight_decay=0.):
    rng = np.random.default_rng(seed); p = init(spec, data["own"].shape[1], rng)
    params = flat(p); m1 = [np.zeros_like(a) for a in params]; m2 = [np.zeros_like(a) for a in params]
    step, best, best_p, history = 0, float("inf"), None, []
    for epoch in range(epochs):
        order = rng.permutation(split["train"])
        for i in range(0, len(order), batch):
            b = order[i:i + batch]; logits, cache = forward(p, data, b, True)
            _, dlogits = loss_grad(logits, data["plant"][b], data["Y"][b])
            g = backward(p, cache, dlogits.astype(np.float32)); gs = flat(g)
            norm = np.sqrt(sum(float((a.astype(np.float64) ** 2).sum()) for a in gs)); scale = min(1., 5. / (norm + 1e-6))
            step += 1; cur = lr * (.5 * (1 + np.cos(np.pi * epoch / epochs)) if spec.get("cosine") else 1.)
            for a, ga, a1, a2 in zip(params, gs, m1, m2):
                ga = ga * scale; a1 *= .9; a1 += .1 * ga; a2 *= .999; a2 += .001 * ga * ga
                a -= cur * ((a1 / (1 - .9 ** step)) / (np.sqrt(a2 / (1 - .999 ** step)) + 1e-8) + (weight_decay * a if a.ndim == 2 else 0.))
        v = measure(p, data, split["validation"]); history.append(dict(epoch=epoch + 1, validation_loss=v["loss"]))
        if v["loss"] < best:
            best = v["loss"]; best_p = [a.copy() for a in params]
        log(json.dumps(dict(spec=spec, lr=lr, epoch=epoch + 1, validation_loss=round(v["loss"], 5),
                            validation_econ=round(v["heads"]["econ_goal"]["accuracy"], 4))), flush=True)
    for a, c in zip(params, best_p): a[...] = c
    return p, best, history


def make_split(data, mode, test_maps=None, validation_maps=None, only_maps=None, exclude_maps=()):
    """mode 'map': whole maps held out (train.py behaviour). mode 'opening': within every map,
    game ids are held out (every 6th game validation, every 6th+1 test)."""
    idx = np.arange(len(data["Y"])); keep = ~np.isin(data["map"], list(exclude_maps))
    if only_maps: keep &= np.isin(data["map"], list(only_maps))
    part = np.full(len(idx), "train", dtype=object)
    if mode == "map":
        maps = sorted(set(data["map"][keep]))
        test_maps = set(test_maps or maps[-3:]); validation_maps = set(validation_maps or [m for m in maps if m not in test_maps][-2:])
        part[np.isin(data["map"], list(test_maps))] = "test"; part[np.isin(data["map"], list(validation_maps))] = "validation"
    else:
        for mp in sorted(set(data["map"][keep])):
            ids = sorted(set(data["id"][keep & (data["map"] == mp)]))
            for k, i in enumerate(ids):
                if k % 6 == 4: part[data["id"] == i] = "validation"
                if k % 6 == 5: part[data["id"] == i] = "test"
    # identical feature/label records must not cross a split
    seen, out = set(), {}
    for name in ("test", "validation", "train"):
        chosen, hashes = [], set()
        for i in idx[keep & (part == name) & ((name == "train") | (data["aug"] == 0))]:
            d = hashlib.sha256(data["G"][i].tobytes() + b"|" + b"|".join(
                data[k][data[k + "_ptr"][i]:data[k + "_ptr"][i + 1]].tobytes() for k in ("own", "enemy")) + data["Y"][i].tobytes()).digest()
            if d not in seen: chosen.append(i); hashes.add(d)
        out[name] = np.asarray(chosen, np.int64); seen |= hashes
    return out


def export(p, spec, header, enabled, data_sha):
    """Same layout as train.py writes; loaded by neural_planner.h."""
    doc = {k: header[k] for k in ("catalog_hash", "rules_hash", "behaviors", "sim_fingerprint")}
    doc.update(format="pvz-deepset-hybrid-1", embedding=spec["unit"][0], hidden=spec["body"][0], hybrid=True,
               data_sha256=data_sha, enabled_heads=enabled, trainer="train_np.py",
               unit=dict(weight=p["unit"][0][0].tolist(), bias=p["unit"][0][1].tolist()),
               body=dict(weight=p["body"][0][0].tolist(), bias=p["body"][0][1].tolist()),
               heads=dict(weight=p["heads"][0].tolist(), bias=p["heads"][1].tolist()))
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--unit", default="32,32", help="unit-network layer widths")
    ap.add_argument("--body", default="128,64", help="body layer widths")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, nargs="+", default=[.003, .001])
    ap.add_argument("--split", choices=("map", "opening"), default="map")
    ap.add_argument("--only-maps", default="")
    ap.add_argument("--exclude-maps", default="")
    ap.add_argument("--train-games", type=int, default=0, help="learning curve: keep only the first N training games")
    ap.add_argument("--seed", type=int, default=743)
    ap.add_argument("--extra-test", type=Path, nargs="*", default=[], help="datasets evaluated after selection only (e.g. other maps)")
    ap.add_argument("--aggregates", action="store_true", help="append ten per-side summary inputs (format 2 only)")
    ap.add_argument("--cosine", action="store_true", help="cosine learning-rate decay")
    args = ap.parse_args()
    if args.out.exists(): raise SystemExit("Use a new output directory to preserve checkpoints")
    args.out.mkdir(parents=True); started = time.perf_counter()
    header, data = read_data(args.data, args.aggregates)
    split = make_split(data, args.split, only_maps=[m for m in args.only_maps.split(",") if m], exclude_maps=[m for m in args.exclude_maps.split(",") if m])
    if args.train_games:
        games = sorted(set(data["id"][split["train"]])); rng = np.random.default_rng(args.seed); rng.shuffle(games)
        split["train"] = split["train"][np.isin(data["id"][split["train"]], games[:args.train_games])]
    spec = dict(unit=[int(x) for x in args.unit.split(",")], body=[int(x) for x in args.body.split(",")], globals=data["G"].shape[1], cosine=args.cosine)
    sha = hashlib.sha256(b"".join(Path(q).read_bytes() for q in args.data)).hexdigest()
    report = dict(format="pvz-neural-training-2", trainer="numpy " + np.__version__, seed=args.seed, data_sha256=sha, spec=spec,
                  split={k: dict(samples=len(v), maps=sorted(set(data["map"][v])), games=len(set(data["id"][v]))) for k, v in split.items()}, candidates=[])
    best, best_p = float("inf"), None
    for lr in args.lr:
        p, loss, history = train(spec, data, split, args.epochs, args.batch_size, lr, args.seed)
        report["candidates"].append(dict(lr=lr, best_validation_loss=loss, history=history))
        if loss < best: best, best_p, report["selected"] = loss, p, dict(lr=lr, **spec)
    report["metrics"] = {k: measure(best_p, data, v) for k, v in split.items()}
    for q in args.extra_test:
        h2, d2 = read_data([q], args.aggregates)
        if h2["behaviors"] != header["behaviors"]: raise SystemExit("extra test set was encoded differently")
        report["metrics"]["extra:" + q.name] = measure(best_p, d2, np.flatnonzero(d2["aug"] == 0))
    tr = report["metrics"]["train"]["heads"]
    enabled = [sum(sum(row) > 0 for row in tr[k]["confusion"]) >= 2 for k in HEADS]
    report["enabled_heads"] = dict(zip(HEADS, enabled)); report["wall_seconds"] = time.perf_counter() - started
    if len(spec["unit"]) == 1 and len(spec["body"]) == 1 and not args.aggregates:
        (args.out / "model.json").write_text(json.dumps(export(best_p, spec, header, enabled, sha), ensure_ascii=False, separators=(",", ":")), "utf-8")
    else:
        report["model_json"] = "not written: the C++ planner loads one unit layer, one body layer and no summary inputs"
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({k: {h: round(v["heads"][h]["accuracy"], 4) for h in HEADS[:3]} for k, v in report["metrics"].items()}), flush=True)


if __name__ == "__main__":
    main()
