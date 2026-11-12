"""Which implementation backs each callable the original regions use in a PvP71 match.

Writes extract/schema/override_map.json: name -> {source file, qualname, line}.
Also lists the bytecode gates (regions whose code differs from the original slice).
"""
import sys, os, json, types, dis, marshal, inspect
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = Path(__file__).resolve().parents[1] / "extract" / "schema"


def describe(v):
    f = v
    for attr in ("__wrapped__", "func"):
        if hasattr(f, attr) and callable(getattr(f, attr)):
            pass
    code = getattr(f, "__code__", None)
    if code is None and hasattr(f, "__call__"):
        code = getattr(getattr(f, "__call__"), "__code__", None)
        if code is not None:
            return {"kind": type(f).__name__, "file": Path(code.co_filename).name, "name": code.co_name, "line": code.co_firstlineno}
    if code is None:
        return {"kind": type(f).__name__, "repr": repr(f)[:120]}
    return {"kind": type(f).__name__, "file": Path(code.co_filename).name, "name": code.co_name, "line": code.co_firstlineno}


def main():
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
    os.chdir(str(REF))
    import multiworker_fixtures as F
    b = F.new_battle(seed=3)
    for i in range(5):
        b.step()
    g = b.g
    regions = b.engine.regions
    used = {}
    for rname, code in regions.items():
        names = set(code.co_names)
        for n in names:
            used.setdefault(n, []).append(rname)
    out = {}
    for n, rs in sorted(used.items()):
        if n in g and callable(g[n]) and not isinstance(g[n], type):
            d = describe(g[n])
            d["regions"] = sorted(set(rs))
            out[n] = d
    # gate detection: compare region code with pristine slices
    from pvp.native_runtime import original_regions, REGIONS
    pristine = original_regions(b.engine.root)
    gates = {}
    for rname in regions:
        a, p = regions[rname], pristine.get(rname)
        if p is None:
            gates[rname] = "new region"
        elif a.co_code != p.co_code or a.co_consts != p.co_consts or a.co_names != p.co_names:
            gates[rname] = "modified"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "override_map.json").write_text(json.dumps({"callables": out, "gated_regions": gates},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    by = {}
    for n, d in out.items():
        by.setdefault(d.get("file", d.get("kind")), []).append(n)
    for k, v in sorted(by.items()):
        print("%-40s %d: %s" % (k, len(v), " ".join(v)))
    print("gated:", gates)
    b.close()


if __name__ == "__main__":
    main()
