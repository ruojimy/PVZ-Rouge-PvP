"""Runtime facts the hand-written C++ init needs (from a constructed PvP71 battle)."""
import sys, os, json, types
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
os.chdir(str(REF))
import multiworker_fixtures as F
b = F.new_battle(seed=1)
ph = b.engine.physics
g = b.g
facts = {
    "physics_changed_names": sorted(ph.changed_names),
    "physics_tracking_scratch": sorted(ph.tracking_scratch),
    "physics_state_keys": list(ph.state_keys),
    "physics_jump_limit_regions": {str(k): v for k, v in ph.jump_limit_regions.items()},
    "physics_balloon_regions": {str(k): v for k, v in ph.balloon_regions.items()},
    "graphics_callables": sorted(k for k, v in g.items() if callable(v) and getattr(getattr(v, "__code__", None), "co_filename", "").endswith("native_animation.py")),
    "g_callable_sources": {k: (getattr(getattr(v, "__code__", None), "co_filename", type(v).__name__).split("\\")[-1].split("/")[-1])
                           for k, v in g.items() if callable(v)},
    "native_scale_FACTOR": __import__("pvp.native_scale", fromlist=["x"]).FACTOR,
    "native_scale_LIFT": __import__("pvp.native_scale", fromlist=["x"]).LIFT,
    "template_art": __import__("pvp.expansion_assets", fromlist=["x"]).TEMPLATE_ART,
    "atlas_sizes": {k: list(v.get_size()) for k, v in list(g["图集"].items())[:5]},
}
(ROOT / "extract/schema/runtime_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
print(Counter(facts["g_callable_sources"].values()))
print("graphics:", facts["graphics_callables"])
print([k for k, v in facts["g_callable_sources"].items() if v in ("native_animation.py", "type", "method", "NativeImage")][:80])
b.close()
