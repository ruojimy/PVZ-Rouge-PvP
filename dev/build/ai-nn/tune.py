#!/usr/bin/env python3
"""Outcome-driven first step: does a constant correction to one r22 goal win more games?

Starts from the identity residual model (identity_model.py), which plays exactly like r22, and
tries candidates that add a fixed offset to one goal: the plant economy goal or the zombie grave
goal. Every candidate plays the same openings as the r22 baseline on one seat; the comparison is
paired (compare.py) and timeouts count as not won.

  python build/ai-nn/tune.py --bin <headless_match> --corpus build/ai-nn/corpus-pvp743-r2 \
      --identity identity.json --seat plant --deltas=-2,-1,1,2 --ids 家院 --out-dir tune-plant \
      [--jobs N] [--limit-seconds 1800] [--holdout-ids @file]

A candidate chosen here was selected on these openings, so its win rate on them is biased upward.
Give --holdout-ids to replay only the best candidate on openings that were not used for selection;
only that second comparison is evidence of strength. Standard library only.
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare
from eval import select

OFFSETS = (0, 11, 13, 24, 27)
HEAD = dict(plant=0, zombie=2)


def run_eval(args, ids, out_dir, extra):
    if not (out_dir / "summary.json").exists():
        subprocess.run([sys.executable, str(Path(__file__).with_name("eval.py")), "--bin", args.bin, "--corpus", args.corpus,
                        "--out-dir", str(out_dir), "--ids", ids, "--jobs", str(args.jobs), "--limit-seconds", str(args.limit_seconds),
                        "--resume", *extra], check=True, stdout=subprocess.DEVNULL)
    return json.loads((out_dir / "summary.json").read_text("utf-8"))


def candidate_model(identity, seat, delta, path):
    doc = json.loads(json.dumps(identity)); bias = doc["heads"]["bias"]; h = HEAD[seat]
    for i in range(OFFSETS[h], OFFSETS[h + 1]):
        bias[i] = 0.0
    bias[OFFSETS[h] + 5 + delta] = 1.0
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), "utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True); ap.add_argument("--corpus", required=True)
    ap.add_argument("--identity", type=Path, required=True)
    ap.add_argument("--seat", choices=("plant", "zombie"), required=True)
    ap.add_argument("--deltas", default="-2,-1,1,2")
    ap.add_argument("--ids", default="家院"); ap.add_argument("--holdout-ids", default="")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=2); ap.add_argument("--limit-seconds", type=float, default=1800.)
    args = ap.parse_args()
    identity = json.loads(args.identity.read_text("utf-8"))
    if not identity.get("residual"):
        raise SystemExit("--identity must be a residual model written by identity_model.py")
    deltas = [int(x) for x in args.deltas.split(",") if x]
    if not deltas or len(deltas)!=len(set(deltas)) or any(d == 0 or abs(d) > 5 for d in deltas):
        raise SystemExit("deltas must be non-zero and within -5..5")
    index=json.loads((Path(args.corpus)/"index.json").read_text("utf-8"))
    selection=set(select(index,args.ids))
    if args.holdout_ids and selection.intersection(select(index,args.holdout_ids)):
        raise SystemExit("selection and holdout openings must be disjoint")
    if args.out_dir.exists():
        raise SystemExit("Use a new output directory; cached games may use a different model or build")
    args.out_dir.mkdir(parents=True)
    baseline = run_eval(args, args.ids, args.out_dir / "baseline", [])
    rows = []
    for d in deltas:
        name = f"{args.seat}{d:+d}"; model = args.out_dir / (name + ".json"); candidate_model(identity, args.seat, d, model)
        got = run_eval(args, args.ids, args.out_dir / name, ["--planner", "nn", "--", "--model", str(model), "--nn-seat", args.seat])
        row = compare(baseline, got, args.seat); row.update(delta=d, model=str(model)); row.pop("ids"); rows.append(row)
        print(json.dumps({k: row[k] for k in ("delta", "matches", "baseline_wins", "candidate_wins", "gains", "losses", "paired_exact_p", "timeouts", "ai_errors")}), flush=True)
    best = max(rows, key=lambda r: (r["gains"] - r["losses"], r["candidate_wins"]))
    report = dict(format="pvz-ai-nn-tune-1", seat=args.seat, selection_ids=args.ids, limit_seconds=args.limit_seconds, candidates=rows,
                  selected=dict(delta=best["delta"], model=best["model"]),
                  note="Selection results are biased upward; only the holdout comparison is evidence of strength.")
    if args.holdout_ids:
        base2 = run_eval(args, args.holdout_ids, args.out_dir / "holdout-baseline", [])
        got2 = run_eval(args, args.holdout_ids, args.out_dir / "holdout-selected", ["--planner", "nn", "--", "--model", best["model"], "--nn-seat", args.seat])
        report["holdout"] = compare(base2, got2, args.seat); report["holdout"].pop("ids")
    (args.out_dir / "tune.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(dict(selected=report["selected"], holdout=report.get("holdout", {}).get("paired_exact_p"))), flush=True)


if __name__ == "__main__":
    main()
