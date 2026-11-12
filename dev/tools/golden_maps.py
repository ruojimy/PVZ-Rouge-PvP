"""Reference output of the original 生成地图 (as PvP's bridge runs it) for every map x seeds."""
import sys, json
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.path[:0] = [str(REF / "modkit")]
from pvp.native_bridge import NativeBridge, MAP_NAMES
br = NativeBridge.from_marshaled(str(REF / "reverse_engineered/raw/pvzrouge.pyc"))
out = {}
for name in MAP_NAMES:
    for seed in list(range(40)) + [123456, 987654321]:
        grid = br.generate_map(name, seed)
        out["%s|%d" % (name, seed)] = [[[c.get("方块", ""), c.get("里方块", "")] for c in row] for row in grid]
p = Path(__file__).resolve().parents[1] / "extract" / "golden"
p.mkdir(parents=True, exist_ok=True)
(p / "maps.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(out), "maps; keys sample", sorted({k for g in out.values() for row in g for c in row for k in c})[:80])
