"""Record the Python PvP71 battle state for a scenario, per native tick.

Scenario JSON (tools/scenarios/<name>.json):
  {"map": "家院", "seed": 1, "weather": "clear", "night": false,
   "decks": {"plant": [...], "zombie": [...]},          (optional; fixture DECKS default)
   "durable_heroes": true,
   "setup": [ {"op": "plant", "name": "豌豆射手", "row": 18, "col": 47},
              {"op": "zombie", "name": "普通僵尸", "row": 18, "x_tiles": 60} ],
   "inputs": { "<room tick>": [ {"side": "plant", "move": 1, "jump": false}, ... ] },
   "room_ticks": 30}
Output: extract/oracle/<name>.jsonl   one line per native tick:
  {"t": native_tick, "rt": room_tick, "g": {...}, "avatars": {...}, "players": {...}}
"""
import sys, os, json, math
from pathlib import Path
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "extract" / "oracle"

GKEYS = ("植物", "僵尸", "实体", "粒子", "阳光球", "收集阳光", "同横尸", "同竖尸", "冻水", "水波",
         "目标植物", "目标位置", "人洪水cd", "植洪水cd", "人洪水覆盖", "植洪水覆盖", "梯子cd", "_pvp_water_ice")


BKEYS = ("tick", "command", "commands", "rally_point", "rally_points", "result", "deathmatch")


def plain(v, depth=0):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return repr(v)
        return v
    if depth > 8:
        return "<deep>"
    if isinstance(v, (list, tuple)):
        return [plain(x, depth + 1) for x in v]
    if isinstance(v, dict):
        return {str(k): plain(x, depth + 1) for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        return sorted(plain(x, depth + 1) for x in v)
    return "<%s>" % type(v).__name__


def build(sc):
    sys.path[:0] = [str(REF / "tests"), str(REF / "modkit")]
    os.chdir(str(REF))
    import multiworker_fixtures as F
    from pvp.maps import build_snapshot
    from pvp.native_battle import NativeBattle
    terrain = build_snapshot(F.bridge(), sc.get("map", "家院"), sc.get("seed", 1), weather=sc.get("weather", "clear"))
    if sc.get("night"):
        terrain.environment["night"] = True
    from pvp.catalog import RULES
    rules = dict(RULES)
    decks = sc.get("decks") or F.DECKS
    director = None
    if sc.get("campaign_deck"):
        # PvE / co-op: the campaign's opening deck and its rules (tests/test_pvp_66_teams.PveTests)
        from pvp.pve import Campaign, pve_rules
        deck = Campaign().battle_deck()
        rules = pve_rules(rules, deck)
        decks = {"plant": deck, "zombie": []}
        if sc.get("mode") == "coop":
            decks["plant2"] = list(deck)
    rules.update(sc.get("rules", {}))
    if sc.get("director"):
        from pvp.pve import WaveDirector
        d = sc["director"]
        director = WaveDirector(d.get("day", 1), seed=d.get("seed", 1), coop=sc.get("mode") == "coop")
    b = NativeBattle(terrain, decks, rules=rules, bridge=F.bridge(), pygame=F.pygame_module(), seed=sc.get("seed", 1),
                     mode=sc.get("mode", "duel"), director=director)
    if sc.get("clear_cooldowns"):
        for player in b.players.values():
            player["cooldowns"].clear()
    for seat, (col, row) in sc.get("place", {}).items():
        b.hero_states[seat]["玩家位置"][:] = [col * b.tile, row * b.tile, 0., 0.]
    if sc.get("durable_heroes"):
        F.durable_heroes(b)
    expanded = bool(sc.get("fixture"))   # fixture spawns already ran; their recorded ops are for the C++ runner
    if sc.get("fixture"):
        # expand a tests/multiworker_fixtures scenario into exact spawn calls for the C++ runner
        calls = []
        original = b.spawn
        def logged(card, side, x, y, facing=1, *a, **k):
            calls.append({"op": "spawn", "card": card, "side": side, "x": x, "y": y, "facing": facing})
            return original(card, side, x, y, facing, *a, **k)
        b.spawn = logged
        getattr(F, sc["fixture"])(b)
        b.spawn = original
        sc["setup"] = calls + sc.get("setup", [])
        sc.pop("fixture")
        (HERE / "scenarios" / ("_expanded_" + sc["_name"] + ".json")).write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    for op in sc.get("setup", []):
        if op["op"] == "plant":
            F._plant(b, op["name"], op["row"], op["col"], op.get("facing", 1))
        elif op["op"] == "zombie":
            F._zombie(b, op["name"], op["row"], op["x_tiles"] * b.tile, op.get("facing", -1))
        elif op["op"] == "spawn" and not expanded:
            try:
                b.spawn(op["card"], op["side"], op["x"], op["y"], op.get("facing", 1))
            except ValueError:
                pass   # e.g. derived units that need a living parent (C++ runner skips them the same way)
        elif op["op"] == "command":
            b.command = op["value"]
    return b


def resolve(b, side, v):
    """Scenario placeholders for runtime ids (same rule in the C++ runner):
    $grave = newest live grave unit of the zombie team, $sun = first resource this seat may collect."""
    if v == "$grave":
        ids = [u["id"] for u in b.units.values() if u.get("behavior") == "grave" and u.get("hp", 0) > 0
               and u.get("side") == "zombie"]
        return ids[-1] if ids else None
    if v == "$sun":
        ids = [rid for rid, r in b.resources.items() if r.get("side") == side]
        return ids[0] if ids else None
    return v


def main():
    name = sys.argv[1]
    sc = json.loads((HERE / "scenarios" / (name + ".json")).read_text(encoding="utf-8"))
    sc["_name"] = name
    b = build(sc)
    OUT.mkdir(parents=True, exist_ok=True)
    out = open(OUT / (name + ".jsonl"), "w", encoding="utf-8")
    state = {"rt": 0}
    orig = b._step_original

    def dump():
        g = b.g
        rec = {"t": b.engine.native_tick, "rt": state["rt"],
               "g": {k: plain(g.get(k)) for k in GKEYS + tuple(sc.get("extra_g", ()))},
               "avatars": {s: plain(a) for s, a in b.avatars.items()},
               "players": {s: plain({k: v for k, v in p.items() if k not in ("deck", "secrets")})
                           for s, p in b.players.items()},
               "inp": state.pop("inp", []),
               "battle": plain({k: getattr(b, k, None) for k in BKEYS + tuple(sc.get("extra_battle", ()))}),
               "rng": b.engine.rng.getstate()[1][b.engine.rng.getstate()[1][-1] % 624] if False else None}
        out.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")

    def wrapped(draw=True):
        orig(draw)
        dump()

    b._step_original = wrapped
    dump()
    inputs = sc.get("inputs", {})
    seqs = {}
    for rt in range(sc.get("room_ticks", 30)):
        state["rt"] = rt
        for cmd in inputs.get(str(rt), []):
            side = cmd["side"]
            seqs[side] = seqs.get(side, -1) + 1
            payload = {k: resolve(b, side, v) for k, v in cmd.items() if k != "side"}
            payload["seq"] = seqs[side]
            err = b.command_input(side, payload)
            state.setdefault("inp", []).append([side, payload.get("type"), err])
        b.step()
    out.close()
    b.close()
    print("recorded", name, b.engine.native_tick, "native ticks")


if __name__ == "__main__":
    main()
