"""PvP66 plant secret enhancements (植物秘籍强化).

| 秘籍 | PvP66 |
|---|---|
| 补光 | dropped sun on a plant's death is 25 (was the small 15) |
| 石果 | the stone fruit never wears away (still not eaten to death) |
| 尖刺 | cactus thorns reflect +250% (5 -> 17.5; native +100% was 10); attack interval halved |
| 压顶 | the squash's landing also deals its 500 to enemies within 2.4 tiles |
| 核平 | the doom-shroom ashes every non-hero unit it hits outright |
| 雷霆 | thunder shroom costs 100 |
| 水兵 | the sea-shroom becomes an air plant: plantable in any idle cell; costs +50 |
| 光疗 | each lantern heal pulse also deals 12 to enemy units in its reach |
| 龙蒺藜 | caltrop health 18 |
| 大帝 | starfruit costs 300 |
| 正午 (new) | natural sky sun interval halved, including the first drop |

Every native predicate below is replaced in every match, whatever the decks:
the C++ core compiles the regions as they run, so one stable code shape keeps
them compiled; each callback answers the original question when its secret
is absent, so nothing changes without the secret.
"""
import math


def wrap_delta(a, b, width):
    """Shortest signed horizontal offset on the ring (same formula as simulation)."""
    return (b - a + width / 2.) % width - width / 2.

SECRET_NOON = "secret:正午"
SUPPLEMENT_SUN = 25
CACTUS_REFLECT = 17.5          # 5 x (1 + 250%)
CACTUS_NATIVE_SECRET = 10.     # what the native branch already deals with 尖刺
SQUASH_SPLASH_TILES = 2.4
SQUASH_DAMAGE = 500.
LANTERN_DAMAGE = 12.
LANTERN_REACH_TILES = 3.
CALTROP_HP = 18.
THUNDER_COST = 100
STARFRUIT_COST = 300
SEA_SHROOM_SURCHARGE = 50

DESCRIPTIONS = {
    "补光": "植物去世时掉落阳光（25）；对战中的临时召唤与重复死亡不重复计奖。",
    "石果": ("高坚果替换为石果子，费用变为 175 阳光，生命 180。普通啃咬不能将其吃死，且永远不会自行消失；"
             "黑普通、黑路障、黑铁桶、黑撑杆、黑橄榄、黑旗帜僵尸每次啃咬造成 3 点伤害。"),
    "尖刺": "仙人掌反伤增加 250%，攻击间隔减半。",
    "压顶": "窝瓜会长时间坐晕普通僵尸，落地时对半径 2.4 格内的敌方单位造成同等伤害；英雄控制仍受限制。",
    "核平": "毁灭菇直接秒杀范围内任何非英雄单位；对英雄仍为原伤害且受单轮上限保护。",
    "雷霆": "大喷菇替换为雷蘑菇，费用变为 100；攻击麻痹带金属的僵尸。",
    "水兵": "海蘑菇变为飞行植物：可种在任意闲置格（含空中），在水中仍潜藏于水面之下，无法选中；海蘑菇费用 +50 阳光，种植冷却翻倍。",
    "光疗": "路灯花治疗效果翻倍，生命翻倍；路灯花每次生效（约4.8秒一次，无论是否有植物需要治疗）都唤醒横纵3格内沉睡的己方植物，并对范围内敌方单位造成 12 点伤害。",
    "龙蒺藜": "大嘴花替换为龙蒺藜，费用变为 150，生命 18；咀嚼时间减少 80%。",
    "大帝": "场上僵尸越多，杨桃攻击速度越快；杨桃费用变为 300 阳光。",
    "正午": "植物方的天降阳光间隔减半（包括第一次掉落的时间）。",
}


def install_catalog(cards):
    """Card text, prices and the new 正午 secret (called from catalog.py)."""
    from copy import deepcopy
    for name, text in DESCRIPTIONS.items():
        key = "secret:" + name
        if key in cards:
            cards[key]["description"] = text
    noon = deepcopy(cards["secret:补光"])
    noon.update(id=SECRET_NOON, base_id=SECRET_NOON, resolved_id=SECRET_NOON, family=SECRET_NOON,
                name="正午", asset="阳光球", native_secret_name="正午", dependency="", economy="none",
                effect="noon", pvp_added=True, description=DESCRIPTIONS["正午"],
                native_description=DESCRIPTIONS["正午"])
    cards[SECRET_NOON] = noon


def secrets_of(battle):
    return set(battle.team_secrets["plant"])


class PlantSecrets66(object):
    def __init__(self, battle):
        from .native_gate import replace_predicate
        self.b = battle
        self.g = battle.g
        self.secrets = secrets_of(battle)
        self.death_points = []
        regions = battle.engine.regions
        g = self.g
        g["_pvp66_cactus"] = self.cactus
        regions["zombies"] = replace_predicate(regions["zombies"], 74756, 74764, "_pvp66_cactus", [
            ("LOAD_CONST", "尖刺"), ("LOAD_NAME", "秘籍"), ("COMPARE_OP", "in")])
        g["_pvp66_squash"] = self.squash
        regions["entities"] = replace_predicate(regions["entities"], 100102, 100110, "_pvp66_squash", [
            ("LOAD_CONST", "压顶"), ("LOAD_NAME", "秘籍"), ("COMPARE_OP", "in")])
        g["_pvp66_doom"] = self.doom
        regions["plant_maintenance"] = replace_predicate(regions["plant_maintenance"], 114080, 114088, "_pvp66_doom", [
            ("LOAD_CONST", "核平"), ("LOAD_NAME", "秘籍"), ("COMPARE_OP", "in")])
        g["_pvp66_lantern"] = self.lantern
        regions["plants"] = replace_predicate(regions["plants"], 136478, 136486, "_pvp66_lantern", [
            ("LOAD_CONST", "光疗"), ("LOAD_NAME", "秘籍"), ("COMPARE_OP", "in")])
        g["_pvp66_stone_wears"] = self.stone_wears
        regions["plants"] = replace_predicate(regions["plants"], 137892, 137898, "_pvp66_stone_wears", [
            ("LOAD_NAME", "name"), ("LOAD_CONST", "石果子"), ("COMPARE_OP", "==")])

    # ------------------------------------------------------------- 尖刺
    def cactus(self):
        if "secret:尖刺" not in self.secrets:
            return False
        # The native branch deals 10 next; add the rest of the +250% here.
        index = self.g["l"]
        z = self.g["僵尸"][index]
        self.g["伤害僵尸"](index, 1 if z.get("方向", 1) >= 0 else -1, CACTUS_REFLECT - CACTUS_NATIVE_SECRET)
        return True

    # ------------------------------------------------------------- 压顶
    def squash(self):
        if "secret:压顶" not in self.secrets:
            return False
        b, g = self.b, self.g
        roster = g["僵尸"]
        z = g.get("z")
        if not isinstance(z, int) or not 0 <= z < len(roster):
            return True
        center = roster[z]
        cx, cy = center["位置"][0], center["位置"][1] - b.tile * .5
        owner = b.targets.owner()
        reach = SQUASH_SPLASH_TILES * b.tile
        for index, other in enumerate(list(roster)):
            if index == z or other.get("_pvp_hero") or other.get("血量", 0) <= 0 or "灰烬" in other:
                continue
            if b.targets.owner(other) == owner:
                continue
            ox, oy = other["位置"][0], other["位置"][1] - b.tile * .5
            if math.hypot(wrap_delta(cx, ox, b.width), oy - cy) <= reach:
                g["伤害僵尸"](index, 1, SQUASH_DAMAGE)
        b._emit("squash_splash", entity=center.get("_pvp_id"))
        return True

    # ------------------------------------------------------------- 核平
    def doom(self):
        if "secret:核平" not in self.secrets:
            return False
        g = self.g
        z = g.get("z")
        roster = g["僵尸"]
        if not isinstance(z, int) or not 0 <= z < len(roster):
            return True
        target = roster[z]
        if target.get("_pvp_hero"):
            return True          # heroes keep the native second ash (capped)
        if self.b.targets.owner(target) == self.b.targets.owner():
            return False
        target["灰烬"] = 0      # any non-hero unit: ashed outright
        return False

    # ------------------------------------------------------------- 光疗
    def lantern(self):
        """Native heal-branch predicate: 光疗 doubles the heal. The burn is not
        here - this branch only runs when a plant actually needs healing."""
        return "secret:光疗" in self.secrets

    def lantern_pulses(self):
        """Burn on every native lantern pulse (its 路灯 timer resetting), healed
        or not. Called once per tick after the native plant pass."""
        if "secret:光疗" not in self.secrets:
            return
        for plant in self.g["植物"]:
            if plant.get("植物") != "路灯花" or plant.get("植物血", 0) <= 0 or "死" in plant:
                continue
            timer = plant.get("路灯")
            previous = plant.get("_pvp_lantern_timer")
            plant["_pvp_lantern_timer"] = timer
            if isinstance(timer, (int, float)) and isinstance(previous, (int, float)) and timer > previous:
                self.lantern_burn(plant)

    def lantern_burn(self, plant):
        b = self.b
        row, col = plant["坐标"]
        x, y = (col + .5) * b.tile, (row + .5) * b.tile
        reach = LANTERN_REACH_TILES * b.tile
        owner = b.targets.owner(plant)
        woken=[]
        for target in self.g['植物']:
            if (target.get('植物血',0)<=0 or '死' in target or '睡觉' not in target
                    or b.targets.owner(target)!=owner):continue
            tr,tc=target['坐标']
            if abs(wrap_delta(col,tc,b.map['cols']))<=LANTERN_REACH_TILES and abs(tr-row)<=LANTERN_REACH_TILES:
                target.pop('睡觉',None)
                woken.append(target.get('_pvp_id'))
                # Tentacles share sleep with their root, as with coffee.
                root=b._native_objects.get(target.get('_pvp_parent')) if b.content.pvp70.is_head(target) else target
                if root and root.get('_pvp_content')=='抓人草':
                    root.pop('睡觉',None);root['_pvp_was_asleep']=True
                    for head in b.content.pvp70.heads(root):head.pop('睡觉',None)
        if woken:b._emit('lantern_wake',entity=plant.get('_pvp_id'),targets=woken)
        hit = 0
        for target in b.content.enemies(plant):
            if target.get("_pvp_hero") or "植物" in target:
                continue
            if b.targets.owner(target) == owner:
                continue
            tx, ty = target["位置"][0], target["位置"][1] - b.tile * .5
            if abs(wrap_delta(x, tx, b.width)) <= reach and abs(ty - y) <= reach:
                b.content.damage_target(plant, target, LANTERN_DAMAGE)
                hit += 1
        if hit:
            b._emit("lantern_burn", entity=plant.get("_pvp_id"), targets=hit)

    # ------------------------------------------------------------- 石果
    def stone_wears(self):
        # PvP66: the stone fruit never wears away.
        return False

    # ------------------------------------------------------------- 补光
    def note_death_sun(self):
        """Record where a 补光 death sun appears (called from the supplement gate)."""
        plant = self.g["植物"][self.g["l"]]
        row, col = plant["坐标"]
        self.death_points.append(((col + .5) * self.b.tile, (row + .5) * self.b.tile))

    def death_sun_amount(self, sun):
        """25 for a fresh small sun at a recorded death point, else None."""
        if not self.death_points or sun[-1] != 0:
            return None
        x, y = sun[1][0], sun[1][1]
        for point in self.death_points:
            if abs(wrap_delta(point[0], x, self.b.width)) <= self.b.tile and abs(point[1] - y) <= self.b.tile * 1.5:
                self.death_points.remove(point)
                return SUPPLEMENT_SUN
        return None

    def end_economy(self):
        self.death_points = []
