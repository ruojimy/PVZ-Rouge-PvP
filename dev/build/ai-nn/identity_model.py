#!/usr/bin/env python3
"""Write a residual model that reproduces r22 exactly (the starting point for outcome-driven tuning).

  python build/ai-nn/identity_model.py --like <dataset.jsonl[.gz] or model.json> --out identity.json

--like supplies the build identity (simulation fingerprint, catalog and rules hashes, behavior list);
the C++ loader refuses a model whose identity differs from the running build. All weights are zero.
The output biases prefer the neutral class of each head (goal +0, mode keep), so every plan equals
r22's until a tuner changes the parameters. Standard library only.
"""
import argparse, gzip, json
from pathlib import Path

OFFSETS = (0, 11, 13, 24, 27)
NEUTRAL = (5, 0, 5)   # econ_goal +0, plant_mode keep, grave_goal +0

ap = argparse.ArgumentParser()
ap.add_argument("--like", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--embedding", type=int, default=8)
ap.add_argument("--hidden", type=int, default=64)
args = ap.parse_args()
if args.out.exists():
    raise SystemExit("Output exists; use a new path")
opener = gzip.open if args.like.suffix == ".gz" else open
with opener(args.like, "rt", encoding="utf-8") as f:
    head = json.loads(f.readline() if args.like.name.endswith((".jsonl", ".jsonl.gz")) else f.read())
unit_dim = 16 + len(head["behaviors"])
zeros = lambda rows, cols: [[0.0] * cols for _ in range(rows)]
bias = [0.0] * 27
for h, c in enumerate(NEUTRAL):
    bias[OFFSETS[h] + c] = 1.0
doc = {k: head[k] for k in ("catalog_hash", "rules_hash", "behaviors", "sim_fingerprint")}
doc.update(format="pvz-deepset-hybrid-1", residual=True, hybrid=True, embedding=args.embedding, hidden=args.hidden,
           heads=["econ_goal", "plant_mode", "grave_goal", "zombie_save"], enabled_heads=[True, True, True, False],
           unit=dict(weight=zeros(args.embedding, unit_dim), bias=[0.0] * args.embedding),
           body=dict(weight=zeros(args.hidden, 20 + 4 * args.embedding), bias=[0.0] * args.hidden),
           heads_note="identity: zero weights, neutral classes biased")
doc["heads"] = dict(weight=zeros(27, args.hidden), bias=bias)
doc["head_names"] = ["econ_goal", "plant_mode", "grave_goal", "zombie_save"]
args.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), "utf-8")
print(json.dumps(dict(out=str(args.out), parameters=sum(len(r) for k in ("unit", "body", "heads") for r in doc[k]["weight"]) + args.embedding + args.hidden + 27)))
