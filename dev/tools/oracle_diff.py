"""Compare a C++ run (extract/oracle_cpp/<name>.jsonl) with the Python oracle (extract/oracle/<name>.jsonl).

    python tools/oracle_diff.py <name> [--tol 1e-9] [--max 20]

Numbers compare with a relative/absolute tolerance; python-only placeholders ("<Type>") are
skipped; dict key order is ignored; keys absent on one side are reported.
"""
import json, sys, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


IGNORE_KEYS = {"三向目标", "智能星命中", "target_id"}   # python id() values (memory addresses)


def walk(a, b, path, out, tol, limit):
    if len(out) >= limit:
        return
    if isinstance(a, str) and a.startswith("<") and a.endswith(">"):
        return
    if isinstance(b, str) and b.startswith("<") and b.endswith(">"):
        return
    if isinstance(a, bool) or isinstance(b, bool):
        if bool(a) != bool(b) or type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            out.append((path, a, b))
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            return
        if abs(a - b) <= tol * max(1.0, abs(a), abs(b)):
            return
        out.append((path, a, b))
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k in IGNORE_KEYS:
                continue
            if k not in b:
                out.append((path + "." + k, a[k], "<missing in C++>"))
                if len(out) >= limit:
                    return
            else:
                walk(a[k], b[k], path + "." + k, out, tol, limit)
        for k in b:
            if k not in a:
                out.append((path + "." + k, "<missing in Python>", b[k]))
                if len(out) >= limit:
                    return
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path + ".len", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, "%s[%d]" % (path, i), out, tol, limit)
        return
    if a != b:
        out.append((path, a, b))


def main():
    name = sys.argv[1]
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 1e-9
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 20
    py = (ROOT / "extract/oracle" / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()
    cc = (ROOT / "extract/oracle_cpp" / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()
    sys.stdout.reconfigure(encoding="utf-8")
    print("lines: python %d, c++ %d" % (len(py), len(cc)))
    if not py or len(py) != len(cc):
        print("FAILED: empty or unequal output lengths")
        return 1
    for i, (a, b) in enumerate(zip(py, cc)):
        ja, jb = json.loads(a), json.loads(b)
        ja.pop("rng", None); jb.pop("rng", None)
        out = []
        walk(ja, jb, "", out, tol, limit)
        if out:
            print("first divergence at line %d (native tick %s):" % (i, ja.get("t")))
            for p, x, y in out:
                print("  %-60s python=%s  c++=%s" % (p, json.dumps(x, ensure_ascii=False)[:80], json.dumps(y, ensure_ascii=False)[:80]))
            return 1
    print("IDENTICAL over %d lines (tol %g)" % (min(len(py), len(cc)), tol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
