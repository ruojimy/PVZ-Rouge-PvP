"""Infer the value type of every unit-record member from the Python oracle recordings.

Scans extract/oracle/*.jsonl (all scenarios, every native tick) for the records in g["僵尸"], g["植物"],
g["实体"] and the hero avatars, and classifies each key:
  int      always an integral number            float   any non-integral number seen
  bool     True/False only                      str     text (symbol) only
  vecN     list of N numbers (fixed length)      list    other lists
  dict     dict                                 mixed   more than one of the above (None counts separately)
Output: extract/schema/unit_types.json  {collection: {key: {"type", "nullable", "seen", "examples"}}}
        and a summary on stdout (also written to docs/单位成员类型.md).
"""
import json, sys, math
from collections import defaultdict, Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
COLLS = {"僵尸": "zombie", "植物": "plant", "实体": "entity"}


def kind(v):
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "int" if v.is_integer() and abs(v) < 2 ** 53 else "float"
    if isinstance(v, str):
        return "float" if v in ("inf", "-inf", "nan") else "str"
    if isinstance(v, list):
        if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            return "vec%d" % len(v)
        return "list"
    if isinstance(v, dict):
        return "dict"
    return "other"


def merge(kinds):
    k = set(kinds) - {"none"}
    if not k:
        return "none"
    if k <= {"int", "float"}:
        return "float" if "float" in k else "int"
    if len(k) == 1:
        return k.pop()
    vecs = {x for x in k if x.startswith("vec")}
    if vecs and k == vecs:
        return "vec*"   # numeric list, varying length
    if k <= {"int", "float", "bool"}:
        return "num|bool"
    return "mixed:" + "/".join(sorted(k))


def main():
    stats = defaultdict(lambda: defaultdict(Counter))      # coll -> key -> kind -> count
    examples = defaultdict(dict)
    present = defaultdict(Counter)                          # coll -> key -> records containing it
    records = Counter()
    files = sorted((ROOT / "extract/oracle").glob("*.jsonl"))
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i % 5:      # every 5th tick is plenty for type evidence
                    continue
                r = json.loads(line)
                g = r.get("g", {})
                for coll in COLLS:
                    for unit in g.get(coll) or []:
                        if not isinstance(unit, dict):
                            continue
                        records[coll] += 1
                        for key, val in unit.items():
                            k = kind(val)
                            stats[coll][key][k] += 1
                            present[coll][key] += 1
                            examples[coll].setdefault((key, k), val)
                for side, av in (r.get("avatars") or {}).items():
                    records["avatar"] += 1
                    for key, val in av.items():
                        k = kind(val)
                        stats["avatar"][key][k] += 1
                        present["avatar"][key] += 1
                        examples["avatar"].setdefault((key, k), val)
    out = {}
    lines = ["# 单位成员类型（由 tools/infer_unit_types.py 从 %d 个对拍记录推断）" % len(files), ""]
    for coll in list(COLLS) + ["avatar"]:
        out[coll] = {}
        tcount = Counter()
        for key, ks in sorted(stats[coll].items(), key=lambda kv: -present[coll][kv[0]]):
            t = merge(ks)
            tcount[t.split(":")[0]] += 1
            ex = examples[coll].get((key, t)) if (key, t) in examples[coll] else next(iter(
                examples[coll][(key, k)] for k in ks if (key, k) in examples[coll]))
            out[coll][key] = dict(type=t, nullable="none" in ks, seen=present[coll][key],
                                  share=round(present[coll][key] / max(1, records[coll]), 4),
                                  kinds=dict(ks), example=ex if len(json.dumps(ex, ensure_ascii=False)) < 120 else "<large>")
        lines.append("## %s（%d 条记录，%d 个键）" % (coll, records[coll], len(out[coll])))
        lines.append("类型分布：" + "，".join("%s %d" % kv for kv in tcount.most_common()))
        lines.append("")
        lines.append("| 键 | 类型 | 可为 None | 出现率 |")
        lines.append("| --- | --- | --- | --- |")
        for key, d in out[coll].items():
            lines.append("| %s | %s | %s | %.0f%% |" % (key, d["type"], "是" if d["nullable"] else "", d["share"] * 100))
        lines.append("")
    (ROOT / "extract/schema/unit_types.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "docs/单位成员类型.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for coll in out:
        tc = Counter(d["type"].split(":")[0] for d in out[coll].values())
        print("%-7s records=%-7d keys=%-4d %s" % (coll, records[coll], len(out[coll]), dict(tc.most_common())))


if __name__ == "__main__":
    main()
