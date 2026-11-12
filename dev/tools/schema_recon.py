"""Run reference scenarios in the Python PvP71 battle and record every key and
value type seen in the authoritative unit dictionaries and match globals.

Output: extract/schema/schema.json
"""
import sys, json, collections
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = Path(__file__).resolve().parents[1] / "extract" / "schema"


def tname(v):
    t = type(v).__name__
    if t == "list" and v:
        inner = sorted({type(x).__name__ for x in v[:8]})
        return "list[%s]" % "|".join(inner)
    return t


def main():
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit"), str(REF / "cpp_port" / "tools")]
    import os
    os.chdir(str(REF))
    import multiworker_fixtures as F
    keys = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    gl = collections.defaultdict(collections.Counter)
    names = collections.defaultdict(collections.Counter)

    def scan(b):
        g = b.g
        for coll in ("植物", "僵尸", "实体", "粒子", "阳光球"):
            for obj in g.get(coll, []):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        keys[coll][str(k)][tname(v)] += 1
                    nm = obj.get("植物") or obj.get("僵尸") or obj.get("名")
                    if nm is not None:
                        names[coll][str(nm)] += 1
                elif isinstance(obj, list):
                    keys[coll]["<list len %d>" % len(obj)][tname(obj)] += 1
        for side, av in b.avatars.items():
            for k, v in av.items():
                keys["avatar"][str(k)][tname(v)] += 1
        for k, v in g.items():
            if not callable(v) and type(v).__name__ not in ("module", "Surface", "type"):
                gl[str(k)][tname(v)] += 1

    scenarios = []
    for name, fn in F.SCENARIOS.items():
        scenarios.append((name, fn))
    import pvp70_workload, pvp64_workload
    scenarios.append(("pvp70", None))
    for sname, fn in scenarios:
        try:
            if fn is None:
                b = pvp70_workload.battle()
            else:
                b = F.new_battle(seed=7)
                F.durable_heroes(b)
                fn(b)
            for i in range(120):
                b.step()
                if i % 3 == 0:
                    scan(b)
            b.close()
            print("ok", sname, flush=True)
        except Exception as ex:
            import traceback; traceback.print_exc()
            print("FAIL", sname, ex, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    data = {c: {k: dict(v) for k, v in sorted(d.items())} for c, d in keys.items()}
    data["_globals"] = {k: dict(v) for k, v in sorted(gl.items())}
    data["_names"] = {c: dict(v) for c, v in names.items()}
    (OUT / "schema.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
