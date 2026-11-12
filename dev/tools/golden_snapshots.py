"""Reference pvp.maps.build_snapshot output for all maps x seeds x weather."""
import sys, json
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.path[:0] = [str(REF / "modkit")]
from pvp.native_bridge import NativeBridge, MAP_NAMES
from pvp.maps import build_snapshot, audit_snapshot
br = NativeBridge.from_marshaled(str(REF / "reverse_engineered/raw/pvzrouge.pyc"))
out = {}
for name in MAP_NAMES:
    for seed in range(12):
        for weather in ("clear", "rain"):
            try:
                s = build_snapshot(br, name, seed, weather=weather)
            except Exception as ex:
                out["%s|%d|%s" % (name, seed, weather)] = {"error": str(ex)}; continue
            out["%s|%d|%s" % (name, seed, weather)] = {
                "tiles": [["%s/%d%d%d/%s/%s" % (c["kind"], c["solid"], c["water"], c["ladder"], c["background"],
                            "1" if "里方块" in c["native"] else "0") for c in row] for row in s.tiles],
                "spawns": [s.spawns["plant"]["x"], s.spawns["plant"]["y"], s.spawns["zombie"]["x"], s.spawns["zombie"]["y"]],
                "changes": len(s.changes), "waterline": s.environment["waterline_row"],
                "audit": audit_snapshot(s)["valid"]}
p = Path(__file__).resolve().parents[1] / "extract" / "golden" / "snapshots.json"
p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(out), sum(1 for v in out.values() if "error" in v), "errors")
