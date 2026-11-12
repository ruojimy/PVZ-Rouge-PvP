"""Card coverage scenarios: every plant / zombie card in batches against a fixed opposing line.

  cards_p<i>.json : 9 plant cards (row 18, cols 28-36, facing right) vs a fixed zombie column
  cards_z<i>.json : 9 zombie cards (row 18, x 50..66 tiles, facing left) vs a fixed plant line
Map 家院 seed 7 (tests/multiworker_fixtures ROADS: row 18 is open ground from col 27 to 70).
"""
import sys, os, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
REF = Path(r"C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71")
sys.path[:0] = [str(REF / "modkit")]
os.chdir(str(REF))
from pvp.catalog import CARDS

FIXED_ZOMBIES = ["普通僵尸", "路障僵尸", "铁桶僵尸", "撑杆跳僵尸", "报纸僵尸", "普通僵尸", "橄榄球僵尸"]
FIXED_PLANTS = ["豌豆射手", "双发射手", "寒冰射手", "坚果", "向日葵", "机枪射手", "卷心菜投手"]
BATCH = 9


def main():
    plants = sorted(k.split(":", 1)[1] for k, v in CARDS.items() if v["category"] == "plant" and k.startswith("plant:"))
    zombies = sorted(k.split(":", 1)[1] for k, v in CARDS.items() if v["category"] == "zombie" and k.startswith("zombie:"))
    names = []
    for i in range(0, len(plants), BATCH):
        batch = plants[i:i + BATCH]
        setup = [{"op": "plant", "name": n, "row": 18, "col": 28 + j} for j, n in enumerate(batch)]
        setup += [{"op": "zombie", "name": n, "row": 18, "x_tiles": 48 + 2.5 * j} for j, n in enumerate(FIXED_ZOMBIES)]
        name = "cards_p%d" % (i // BATCH)
        names.append(name)
        (HERE / "scenarios" / (name + ".json")).write_text(json.dumps(
            {"map": "家院", "seed": 7, "durable_heroes": True, "room_ticks": 72, "setup": setup, "cards": batch},
            ensure_ascii=False), encoding="utf-8")
    for i in range(0, len(zombies), BATCH):
        batch = zombies[i:i + BATCH]
        setup = [{"op": "plant", "name": n, "row": 18, "col": 28 + j} for j, n in enumerate(FIXED_PLANTS)]
        setup += [{"op": "zombie", "name": n, "row": 18, "x_tiles": 46 + 2 * j} for j, n in enumerate(batch)]
        name = "cards_z%d" % (i // BATCH)
        names.append(name)
        (HERE / "scenarios" / (name + ".json")).write_text(json.dumps(
            {"map": "家院", "seed": 7, "durable_heroes": True, "room_ticks": 72, "setup": setup, "cards": batch},
            ensure_ascii=False), encoding="utf-8")
    # tools / derived / economy cards (both sides), spawned like the batches above
    extra = sorted(k for k, v in CARDS.items() if v["category"] in ("tool", "derived", "economy"))
    for i in range(0, len(extra), BATCH):
        batch = extra[i:i + BATCH]
        setup = [{"op": "plant", "name": n, "row": 18, "col": 28 + j} for j, n in enumerate(FIXED_PLANTS[:3])]
        setup += [{"op": "zombie", "name": n, "row": 18, "x_tiles": 50 + 2.5 * j} for j, n in enumerate(FIXED_ZOMBIES[:3])]
        for j, key in enumerate(batch):
            side = "plant" if key.startswith("plant:") else "zombie"
            x = (32 + j + .5) * 48 if side == "plant" else (44 + 1.5 * j) * 48
            setup.append({"op": "spawn", "card": key, "side": side, "x": x, "y": 18 * 48, "facing": 1 if side == "plant" else -1})
        name = "cards_t%d" % (i // BATCH)
        names.append(name)
        (HERE / "scenarios" / (name + ".json")).write_text(json.dumps(
            {"map": "家院", "seed": 7, "durable_heroes": True, "room_ticks": 72, "setup": setup, "cards": batch},
            ensure_ascii=False), encoding="utf-8")
    # secrets: six per side in the decks, a fixed fight, and deploys that pass through the secret rules
    psec = sorted(k for k, v in CARDS.items() if v["category"] == "secret" and k.startswith("secret:"))
    zsec = sorted(k for k, v in CARDS.items() if v["category"] == "secret" and k.startswith("zsecret:"))
    T = 48
    for i in range(0, max(len(psec), len(zsec)), 6):
        decks = {"plant": ["plant:向日葵", "plant:豌豆射手", "plant:坚果", "plant:寒冰射手"] + psec[i:i + 6],
                 "zombie": ["zombie:脑光墓碑", "zombie:普通僵尸", "zombie:路障僵尸"] + zsec[i:i + 6]}
        setup = [{"op": "plant", "name": n, "row": 18, "col": 43 + j} for j, n in enumerate(("豌豆射手", "坚果", "寒冰射手"))]
        setup += [{"op": "zombie", "name": n, "row": 18, "x_tiles": 56 + 2.5 * j} for j, n in enumerate(FIXED_ZOMBIES[:5])]
        # secrets that modify a card need that card in the deck; put the unit on the field too
        deps = []
        for k in psec[i:i + 6] + zsec[i:i + 6]:
            d = CARDS[k].get("dependency")
            if d and d not in deps:
                deps.append(d)
        for j, d in enumerate(deps):
            side = "plant" if d.startswith("plant:") else "zombie"
            if d not in decks[side]:
                decks[side].insert(0, d)
            x = (40 - j + .5) * T if side == "plant" else (60 + 1.5 * j) * T
            setup.append({"op": "spawn", "card": d, "side": side, "x": x, "y": 18 * T, "facing": 1 if side == "plant" else -1})
        inputs = {"0": [{"side": "plant", "type": "deploy", "card": "plant:向日葵", "x": 47.5 * T, "y": 840},
                        {"side": "zombie", "type": "deploy", "card": "zombie:脑光墓碑", "x": -264, "y": 744}]}
        for rt in range(6, 240, 12):
            inputs.setdefault(str(rt), []).append({"side": "zombie", "type": "deploy", "card": "zombie:普通僵尸", "x": -264, "y": 744, "grave": "$grave"})
        for rt in range(30, 240, 7):
            inputs.setdefault(str(rt), []).append({"side": "plant", "type": "collect", "resource": "$sun"})
        for k, rt in enumerate(range(60, 240, 45)):
            inputs.setdefault(str(rt), []).append({"side": "plant", "type": "deploy", "card": "plant:豌豆射手", "x": (48 + k + .5) * T, "y": 840})
        inputs.setdefault("20", []).append({"side": "plant", "type": "move", "move": 1, "jump": False})
        inputs.setdefault("50", []).append({"side": "plant", "type": "move", "move": 0, "jump": True, "edge": True})
        inputs.setdefault("51", []).append({"side": "plant", "type": "move", "move": 0, "jump": False})
        inputs.setdefault("25", []).append({"side": "zombie", "type": "move", "move": 1, "jump": False})
        name = "secrets_%d" % (i // 6)
        names.append(name)
        (HERE / "scenarios" / (name + ".json")).write_text(json.dumps(
            {"map": "家院", "seed": 3, "durable_heroes": True, "room_ticks": 240, "decks": decks,
             "rules": {"plant_start": 1000, "night_plant_start": 1000, "zombie_start": 1000, "night_zombie_start": 1000, "plant_slots": 20, "zombie_slots": 20},
             "setup": setup, "inputs": inputs, "cards": psec[i:i + 6] + zsec[i:i + 6]},
            ensure_ascii=False), encoding="utf-8")
    print(" ".join(names))


if __name__ == "__main__":
    main()
