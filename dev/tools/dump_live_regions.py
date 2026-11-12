"""Dump the live (PvP-gated) region code objects of a PvP71 match and decompile them.

Output: extract/live/<region>.py (+ .marshal); these are what the PvP match actually runs.
"""
import sys, os, marshal
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
OUT = HERE.parent / "extract" / "live"
sys.setrecursionlimit(100000)

def main():
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
    os.chdir(str(REF))
    import multiworker_fixtures as F
    from pydec38 import Decompiler
    b = F.new_battle(seed=3)
    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8")
    allregions = dict(b.engine.regions)
    allregions.update({'physics_' + k: v for k, v in b.engine.physics.regions.items()})
    from pvp.native_physics import slice_original, _instruction
    from pvp.native_bytecode import instructions as src_ins
    root = b.engine.root
    ins = src_ins(root)
    allregions['dave_draw'] = slice_original(root, 66870, 67400, None, ins)
    allregions['dave_state'] = slice_original(root, 67018, 67400, {67240: _instruction('JUMP_ABSOLUTE', 67400)}, ins)
    for name, code in allregions.items():
        (OUT / (name + ".marshal")).write_bytes(marshal.dumps(code))
        d = Decompiler(code, 0, len(code.co_code), tramp_base=168832)
        try:
            lines = d.decompile_lines()
        except Exception as ex:
            import traceback
            lines = ["# CRASH %r" % ex] + ["# " + l for l in traceback.format_exc().splitlines()]
        t = "\n".join(lines)
        (OUT / (name + ".py")).write_text("# live PvP71 region %s\n" % name + t + "\n", encoding="utf-8")
        print("%-24s lines=%5d gotos=%d unk=%d dup=%d" % (name, len(lines), t.count("# goto"), t.count("# ??"), t.count("GOTO")))
    b.close()

if __name__ == "__main__":
    main()
