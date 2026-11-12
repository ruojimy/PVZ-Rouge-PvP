"""Export the PvP71 match namespace globals after battle construction.
Static (identical across two different matches) -> extract/data/_match_static.json
Per-match names are listed in extract/schema/match_dynamic.json for the C++ init."""
import sys, os, json, math
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from oracle_record import plain
sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
os.chdir(str(REF))
import multiworker_fixtures as F
from pvp.maps import build_snapshot
from pvp.native_battle import NativeBattle
def make(name, seed):
    t = build_snapshot(F.bridge(), name, seed)
    return NativeBattle(t, F.DECKS, bridge=F.bridge(), pygame=F.pygame_module(), seed=seed)
a, b = make("家院", 1), make("大桥", 7)
static, dynamic, skipped = {}, [], []
for k in sorted(set(a.g) | set(b.g)):
    va, vb = a.g.get(k), b.g.get(k)
    if callable(va) or type(va).__name__ in ("module", "Font", "DrawRecorder", "TemplateAtlas", "MatchCopy", "Random", "_Pygame", "NativeTargets"):
        skipped.append(k); continue
    pa, pb = plain(va), plain(vb)
    s = json.dumps(pa, ensure_ascii=False, sort_keys=True)
    if "<" in s and ">" in s and ("<Surface" in s or "<NativeImage" in s or "<deep>" in s):
        skipped.append(k); continue
    if k in ("图集", "ui图集", "背景图集", "近景图集", "拟人图集"):
        skipped.append(k); continue
    if s == json.dumps(pb, ensure_ascii=False, sort_keys=True):
        static[k] = pa
    else:
        dynamic.append(k)
(ROOT / "extract/data/_match_static.json").write_text(json.dumps(static, ensure_ascii=False), encoding="utf-8")
(ROOT / "extract/schema/match_dynamic.json").write_text(json.dumps({"dynamic": dynamic, "skipped": skipped}, ensure_ascii=False, indent=0), encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
print(len(static), "static;", "dynamic:", dynamic); print("skipped:", skipped)
