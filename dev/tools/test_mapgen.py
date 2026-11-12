"""Decompile 生成地图 and compare its output with the original code object
for every map and many seeds (semantic check by execution)."""
import sys, marshal, types, random, copy
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from slice_regions import ROOT
from pydec38 import Decompiler
sys.setrecursionlimit(100000)
root = marshal.loads((ROOT / "reverse_engineered/raw/pvzrouge.pyc").read_bytes())
code = next(c for c in root.co_consts if isinstance(c, types.CodeType) and c.co_name == "生成地图")
sys.path[:0] = [str(ROOT / "modkit")]
from pvp.native_bridge import NativeBridge
br = NativeBridge.from_marshaled(str(ROOT / "reverse_engineered/raw/pvzrouge.pyc"))
mapdata = br._map_data
for limit in (1, 2, 4, 8, 16):
    d = Decompiler(code); d.dup_limit = limit
    lines = d.decompile_lines()
    txt = "\n".join(lines)
    if "GOTO" in txt or "# goto" in txt or "# ??" in txt:
        print("limit", limit, "still has gotos", txt.count("GOTO"), txt.count("# goto"), len(lines)); continue
    print("limit", limit, "clean,", len(lines), "lines"); break
src = "def 生成地图(name):\n" + "\n".join("    " + l for l in lines) + "\n"
(HERE.parent / "extract" / "original" / "mapgen.py").write_text(src, encoding="utf-8")
def env(rng):
    return {"__builtins__": {"range": range, "len": len, "str": str, "int": int, "float": float, "abs": abs},
            "c": copy.deepcopy, "随": lambda a, b: rng.randint(int(a), int(b)), "地图数据": copy.deepcopy(mapdata), "jdz": abs}
bad = 0
for name in ("山地", "沙城", "家院", "要塞", "大桥", "铁道", "遗迹", "绿洲", "小镇", "古堡", "木船", "大楼"):
    for seed in range(60):
        r1 = random.Random(seed); f1 = types.FunctionType(code, env(r1)); a = f1(name)
        r2 = random.Random(seed); g = env(r2); exec(compile(src, "dec", "exec"), g); b = g["生成地图"](name)
        if a != b or r1.getstate() != r2.getstate():
            bad += 1
            if bad < 5: print("MISMATCH", name, seed)
print("mismatches:", bad)
