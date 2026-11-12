"""Modules of the PvP battle core (import closure of native_battle minus UI/net/AI/assets/tests)."""
import ast, sys, re
from pathlib import Path
PVP = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\pvp")
EXCLUDE_RE = re.compile(r"^(app|room|lobby_room|network|relay|rendering|world_view|battle_view|hud|menu_view|draft_view|pve_ui|touch|scaled_display|smoke.*|acceptance.*|map_editor_.*|replay_ui|spectator_ui|team_chat|tutorial|presentation|display_.*|performance_window|result_.*|deathmatch_presentation|preview|rv_.*|native_multiworker|native_candidates|cppcore|gc_policy|hero_guard|.*_assets|.*atlas.*|pvp66_material_data|pvp56_plants_parts|pvp54_native_parts|native_style|native_animation|native_audio|game_audio|ui_data|almanac_text|userdata|profiles|player_profile|identity_check|latency|snapshot_delivery|replay_transfer|perf_hooks|performance|draft_advisor|team_hud|custom_maps|native_bridge|native_bytecode|native_runtime|native_physics|native_gate|native_assets|native_loading|reference|controllers|coop_ai|bounded_cache|native_scale|pvp66_icons|map_deletions)$")
deps = {}
for f in PVP.glob("*.py"):
    t = ast.parse(f.read_text(encoding="utf-8"))
    d = set()
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            if n.module: d.add(n.module.split(".")[0])
            else: d.update(a.name for a in n.names)
    deps[f.stem] = {x for x in d if (PVP / (x + ".py")).exists()}
seen, work = set(), sys.argv[1:] or ["native_battle"]
while work:
    m = work.pop()
    if m in seen or EXCLUDE_RE.match(m): continue
    seen.add(m); work += deps.get(m, ())
print(" ".join(sorted(seen)))
