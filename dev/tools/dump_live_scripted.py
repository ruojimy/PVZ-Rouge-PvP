"""Dump the region code objects of a co-op (scripted waves) match that differ from the duel ones.

ScriptedSpawnBudget.install_native_guards injects four iteration gates into the zombies region
for pve/coop; the result is decompiled to extract/live/<region>_scripted.py.
"""
import sys, os, marshal
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = HERE.parent / "extract" / "live"
sys.setrecursionlimit(100000)


def main():
    import oracle_record as R
    from pydec38 import Decompiler
    sys.stdout.reconfigure(encoding="utf-8")
    duel = R.build({"map": "家院", "seed": 3, "_name": "dump"})
    coop = R.build({"map": "家院", "seed": 3, "mode": "coop", "campaign_deck": True,
                    "director": {"day": 1, "seed": 3}, "_name": "dump"})
    for name, code in coop.engine.regions.items():
        other = duel.engine.regions.get(name)
        if other is not None and other.co_code == code.co_code and other.co_names == code.co_names:
            continue
        print("differs:", name, len(code.co_code), "vs", len(other.co_code) if other else None)
        (OUT / (name + "_scripted.marshal")).write_bytes(marshal.dumps(code))
        d = Decompiler(code, 0, len(code.co_code), tramp_base=168832)
        lines = d.decompile_lines()
        t = "\n".join(lines)
        (OUT / (name + "_scripted.py")).write_text("# live PvP71 co-op region %s\n" % name + t + "\n", encoding="utf-8")
        print("%-24s lines=%5d gotos=%d unk=%d dup=%d" % (name, len(lines), t.count("# goto"), t.count("# ??"), t.count("GOTO")))
    for name in ("physics",):
        pass


if __name__ == "__main__":
    main()
