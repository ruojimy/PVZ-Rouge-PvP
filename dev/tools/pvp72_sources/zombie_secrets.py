"""PvP66 zombie secret effects (僵尸秘籍 v4), one controller per match.

Rules fixed with the user (docs/PVP66_DECISIONS.md):
  * speed bonuses from different secrets add up (+100% and +50% = x2.5);
  * damage reductions multiply (75% crowd x 25% berserk -> takes 0.1875);
  * 狂暴 reduces damage by 25% (takes 75%).
Defaults chosen where the spec is silent are recorded there as well.  In 2v2
a unit/team effect follows the zombie team's secrets (like plant secrets do);
a Dave's own ability (石更, 生生不息, 玉米卷, 起床) belongs to its holder.

Everything here hangs off existing PvP seams: spawn registration, the
match-local damage amount (``NativeProtection.multiplier``), the 30 Hz room
step, the plant death gate, the economy and the public death sweep.  Without
any zombie secret every hook returns at its first line.
"""
import math

from .zombie_secret_catalog import names, RAGE_TORCH_RANGE, RAGE_TORCH_SLEEP
from .teams import team_of
from .native_expansion import (IMP_ARMOR, IMP_ARMOR_HP, IMP_BLACK_ARMOR,
                               CARRIER_BODY_MARK, worn_black_armor)

TILE_HZ = 250

SPRINT = ("zombie:雪橇车僵尸", "zombie:滚桶僵尸")
ATHLETES = ("zombie:撑杆跳僵尸", "zombie:橄榄球僵尸", "zombie:黑撑杆僵尸", "zombie:黑橄榄僵尸")
GIANTS = ("zombie:巨人僵尸", "zombie:红眼巨人", "zombie:角斗士巨人")
CROWD = ("zombie:普通僵尸", "zombie:鸭子普通僵尸", "zombie:黑普通僵尸")
FLAGS = ("zombie:旗帜僵尸", "zombie:黑旗帜僵尸")
# 海陆空: water units (the plant zombies are not water units) and the air units:
# the two birds, plus (68003) the balloon and the bungee thief. 71002: the four
# pirate units count as water, not land (the captain is no longer air). They
# keep their land placement: only this secret's grouping changes, never the
# aquatic "water map and water beside the grave" requirement.
PIRATES = ("zombie:滚桶僵尸", "zombie:钩索僵尸", "zombie:海盗船长", "zombie:小鬼炮")
WATER = ("zombie:潜水僵尸", "zombie:海豚僵尸", "zombie:鸭子普通僵尸", "zombie:鸭子路障僵尸",
         "zombie:鸭子铁桶僵尸") + PIRATES
AIR = ("zombie:海盗鹦鹉", "zombie:乌鸦", "zombie:气球僵尸", "zombie:飞贼僵尸")

CROWD_RADIUS = 6.
CROWD_STEP = .15
CROWD_MAX = .75
HEAL_PERIOD = 12.
HEAL_RADIUS = 8.
HEAL_AMOUNT = 40.
HEAL_DAVE = 4.                       # 生生不息: the holder Dave, up to its cap
TACO_PERIOD = 20.
BRAIN_PER_KILL = 15
RALLY_RADIUS = 6.
RALLY_REFUND = 15
RALLY_DAVE_SPEED = 1.25              # 汇流: a zombie Dave inside the rally reach
WAKE_RADIUS = 2.4
WAKE_HEAL = 4.                       # 起床！: per teleport, may pass the cap
CROW_SURCHARGE = 50
FOCUS_TICKS = 5 * TILE_HZ            # 专注啃咬: 5 s without damage
FOCUS_GUARD = .75                    # 专注啃咬: takes 75% while focused
RELIC_SECONDS = 3.                   # 遗骸
RELIC_DEATHMATCH_SECONDS = 36.
LAST_STAND_SECONDS = 40.             # 最后攻势
VOLLEY_TICKS = 200                   # 散弹攻击: one machine-gun burst
SHOTGUN_FAN = (-30., -18., -6., 6., 18., 30.)
PICKUP_SECONDS = 30.                 # 二手: a dropped piece lies this long
PICKUP_REACH = .7                    # tiles, feet to the piece
PEA_PERIOD = 2.                      # 豌豆: the pea-zombie head's cadence
PEA_RANGE = 8.                       # tiles ahead of the Dave
HEAD_ARMOR = ("路障", "铁桶", "黑路障", "黑铁桶", "橄榄球头盔", "黑橄榄球头盔")
BLAST_RADIUS = 2.4                   # 自爆
BLAST_SHARE = 1. / 25.
PRESSURE_RADIUS = 6.                 # 威压
PRESSURE_FACTOR = 1. / 1.3           # intervals x1.3 -> progress /1.3
POLE_REACH = 2.                      # 立棍！小子: two tiles ahead
POLE_DAMAGE = 4.
KING_ARMOR = 1.25                    # 僵王出品
TYPE2 = ("报纸", "钢门", "梯子", "铁栅门", "传送带")
SHARED_HAND_ARMOR = ("钢门", "垃圾桶", "梯子", "传送带")
SHOT_TIMERS = ("植物僵尸射cd", "篮球cd")
# 植物僵尸: plant -> its plant-zombie form (only pairs that exist in the pool).
PLANT_ZOMBIES = {"豌豆射手": "豌豆僵尸", "机枪射手": "机枪僵尸", "坚果": "坚果僵尸", "高坚果": "高坚果僵尸",
                 "火爆辣椒": "辣椒僵尸", "毁灭菇": "毁灭菇僵尸", "三叶草": "三叶草僵尸", "路灯花": "路灯花僵尸",
                 "倭瓜": "倭瓜僵尸", "窝瓜": "倭瓜僵尸", "墓碑吞噬者": "墓碑吞噬者僵尸", "萝卜伞": "萝卜伞僵尸",
                 "吸金磁": "吸金磁僵尸", "大喷菇": "大喷菇僵尸"}


def hand_kind(z):
    """Equipment identity; native steel-door/ladder slots retain their mechanics."""
    kind = z.get('_pvp_zs_hand_kind')
    if kind:
        return kind
    return {'垃圾桶僵尸': '垃圾桶', '传送带僵尸': '传送带'}.get(z.get('_pvp_content'), z.get('手持'))


def scale_speed(z, tag, bonus):
    """Add one additive speed bonus to a native zombie (each tag once)."""
    bonuses = z.setdefault("_pvp_zs_speed", {})
    if tag in bonuses:
        return False
    before = 1. + sum(bonuses.values())
    bonuses[tag] = bonus
    factor = (1. + sum(bonuses.values())) / before
    z["移速"] = z.get("移速", 0.) * factor
    if "_pvp_base_speed" in z:
        z["_pvp_base_speed"] *= factor
    return True


def scale_hp(z, factor):
    z["血量"] = z.get("血量", 0.) * factor
    z["_pvp_max_hp"] = z.get("_pvp_max_hp", z["血量"]) * factor


class ZombieSecrets(object):
    def __init__(self, battle):
        self.b = battle
        self.g = battle.g
        self.by_seat = {seat: names(battle.players[seat]["secrets"]) for seat in battle.team_seats("zombie")}
        self.team = set()
        for value in self.by_seat.values():
            self.team |= value
        self.enabled = bool(self.team)
        self.clock = {}
        self.subsidy_phase = 0
        self.converts = []          # 植物僵尸: queued (plant name, x, y, facing, seat)
        self.last_stand = {}        # seat -> end time (最后攻势)
        self.last_stand_used = set()
        self._pressure = (None, ())
        self.pickups = []           # 二手: dropped half-life armour
        self.pickup_serial = 0
        self.effects = []
        # 海陆空: decided once at the lock, from the holder's own final deck.
        self.trinity = set()
        for seat, held in self.by_seat.items():
            if '豌豆' in held:
                battle.hero_states[seat]['_pvp_pea_head'] = True
            if "海陆空" in held and self._trinity_deck(battle.players[seat]["deck"]):
                self.trinity.add(seat)

    # ------------------------------------------------------------ queries
    def has(self, name):
        return name in self.team

    def holders(self, name):
        return [seat for seat, held in sorted(self.by_seat.items()) if name in held]

    def seat_has(self, seat, name):
        return name in self.by_seat.get(seat, ())

    @staticmethod
    def _trinity_deck(deck):
        from .catalog import CARDS
        units = [k for k in deck if CARDS[k]["category"] != "secret" and CARDS[k].get("behavior") != "grave"]
        water = any(k in WATER for k in units)
        air = any(k in AIR for k in units)
        land = any(k not in WATER and k not in AIR and not CARDS[k].get("plant_zombie_water") for k in units)
        return water and air and land

    def _zombie(self, z):
        """A live, moving zombie unit (not a grave, a Dave or a loose barrel)."""
        return (isinstance(z, dict) and not z.get("_pvp_grave") and not z.get("_pvp_hero")
                and z.get('_pvp_content')!='抓人草触手'
                and not z.get("_pvp_orphan_barrel") and z.get("血量", 0) > 0 and "植物" not in z)

    def _own(self, z):
        return self.b.targets.owner(z) == "zombie"

    def _distance(self, ax, ay, bx, by):
        from .simulation import wrap_delta
        return math.hypot(wrap_delta(ax, bx, self.b.width), by - ay)

    def movement_factor(self, z):
        """For native/custom movers whose base velocity is a fixed constant."""
        if not self._own(z):return 1.
        return 1.+sum(z.get('_pvp_zs_speed',{}).values())

    # ------------------------------------------------------------ spawn
    def on_spawn(self, native, card, parent=None):
        if not self.enabled or card.get("side") != "zombie" or native.get("_pvp_grave"):
            return
        key = card.get("base_id", card.get("id"))
        if key=='zombie:萝卜伞僵尸' and self.seat_has(native.get('_pvp_seat','zombie'),'萝卜伞'):
            scale_hp(native,2.)
            native['_pvp_umbrella_secret']=True
        if self.has("散弹攻击") and key=="zombie:机枪僵尸":scale_hp(native,2.)
        if self.has("大运！小子") and key in SPRINT:
            scale_speed(native, "大运", 1.)
        if self.has("体育生") and key in ATHLETES:
            scale_hp(native, 1.25)
            scale_speed(native, "体育生", .25)
            if key == "zombie:黑橄榄僵尸":
                native["_pvp_charge_cd"] = 750
        if self.has("斩首行动") and key == "zombie:雪人僵尸":
            scale_hp(native, 2.)
            native.pop("_pvp_no_hero_attack", None)
            native["_pvp_zs_headhunt"] = True
        native["_pvp_zs_hurt"] = self.b.engine.native_tick
        if self.has("僵王出品"):
            for slot in ("防具血量", "手持血量"):
                if native.get(slot, 0) > 0:
                    native[slot] *= KING_ARMOR
            if native.get("_pvp_armor_max"):
                native["_pvp_armor_max"] *= KING_ARMOR
        if native.get("手持") in TYPE2:
            native["_pvp_zs_hand"] = native["手持"]
            native["_pvp_zs_hand_max"] = native.get("手持血量", 0)
        if self.has("立棍！小子") and key in ("zombie:撑杆跳僵尸", "zombie:黑撑杆僵尸"):
            native["_pvp_zs_pole"] = native.get("手持") == "撑杆"
        seat = native.get("_pvp_seat", "zombie")
        if seat in self.trinity and (key in WATER or key in AIR):
            scale_hp(native, 1.5)
            scale_speed(native, "海陆空", .25)
        if self.has("三五成群") and key in CROWD:
            flag_child = bool(parent) and (parent.get("card_id") in FLAGS)
            native["_pvp_zs_crowd"] = not flag_child

    def on_deployed(self, entity, grave_id):
        """头兵: the first unit sent out of each grave (+50% life)."""
        if not self.has("头兵") or not entity or not grave_id:
            return
        grave = self.b._native_objects.get(grave_id)
        native = self.b._native_objects.get(entity["id"])
        if grave is None or native is None or grave.get("_pvp_zs_first_used"):
            return
        grave["_pvp_zs_first_used"] = True
        scale_hp(native, 1.5)
        self.b._emit("zsecret_first_soldier", grave=grave_id, entity=entity["id"])

    # ------------------------------------------------------------ damage
    def adjust(self, target, amount):
        """Final amount of a positive hit on a native unit (zombie secrets)."""
        if "植物" in target or target.get("_pvp_hero"):
            return amount
        if target.get("_pvp_grave"):
            return self._relic(target, amount)
        amount *= self.damage_factor(target)
        if self.has("专注啃咬"):
            target["_pvp_zs_hurt"] = self.b.engine.native_tick
        if (self.has("坤坤") and target.get("_pvp_card") == "zombie:投篮车僵尸" and self._own(target)
                and not target.get("_pvp_zs_lock_done")):
            hp = target.get("血量", 0)
            if target.get("篮球", 0) > 0 and amount >= hp - 1:
                target["_pvp_zs_locked"] = True
                return max(0., hp - 1.)
        return amount

    def shield_first(self, target):
        """僵王出品: hits that would pass a type-II shield must break it first."""
        return (target.get("手持血量", 0) > 0 and target.get("手持") in TYPE2 and self._own(target))

    def selected_grave(self, grave):
        """解除封印: is this grave some holder's currently selected grave?"""
        uid = grave.get("_pvp_id")
        return any(self.b.players[seat].get("selected_grave") == uid for seat in self.holders("解除封印"))

    def _relic(self, grave, amount):
        """遗骸: a destroyed grave lingers, invulnerable, for 3 s (36 s in deathmatch)."""
        if not self.has("遗骸") or team_of(grave.get("_pvp_owner", "")) != "zombie":
            return amount
        tick = self.b.engine.native_tick
        until = grave.get("_pvp_zs_relic_until")
        if until is not None:
            return 0. if tick < until else amount
        hp = grave.get("血量", 0)
        if amount < hp:
            return amount
        # 最后攻势 puts the team in deathmatch state, 遗骸 included.
        seconds = RELIC_DEATHMATCH_SECONDS if self.b.deathmatch or self.last_stand else RELIC_SECONDS
        grave["_pvp_zs_relic_until"] = tick + int(seconds * TILE_HZ)
        self.b._emit("zsecret_relic", entity=grave.get("_pvp_id"), seconds=seconds)
        return max(0., hp - .01)

    def damage_factor(self, target):
        """Damage multiplier for a zombie unit taking a hit (1 = unchanged)."""
        if not self.enabled or "植物" in target or target.get("_pvp_grave") or target.get("_pvp_hero"):
            return 1.
        if not self._own(target):
            return 1.
        factor = 1.
        if self.berserk(target):
            factor *= .75
        if self.focused(target):
            factor *= FOCUS_GUARD     # the hit that ends the focus is still guarded
        if self.has("阿姆斯特朗") and target.get("_pvp_card") == "zombie:报纸僵尸" and not target.get("手持"):
            factor *= .5
        crowd = target.get("_pvp_zs_crowd_factor")
        if crowd:
            factor *= crowd
        return factor

    # ------------------------------------------------------------ 30 Hz step
    def step(self, dt):
        if not self.enabled:
            return
        if self.has("三五成群"):
            self._crowd()
        if self.has("不可撼动"):
            self._steady_giants()
        if self.has("远离诱惑"):
            self._slow_charmed()
        if self.has("汇流"):
            self._rally_dave_speed()
        for seat in self.holders("生生不息"):
            if self._tick(seat + ":heal", dt, HEAL_PERIOD):
                self._heal(seat)
        for seat in self.holders("玉米卷"):
            if self._tick(seat + ":taco", dt, TACO_PERIOD):
                self._taco(seat)
        if self.has("狂暴") or self.has("坤坤"):
            self._fast_shots()
        if self.has("坤坤"):
            self._basket_lock()
        if self.has("立棍！小子"):
            self._pole_smash()
        if self.has("遗骸"):
            self._relic_expiry()
        if self.converts:
            self._convert()
        if self.last_stand:
            self._last_stand_step()
        if self.pickups:
            self._pickups()
        for seat in self.holders("豌豆"):
            if self._tick(seat + ":pea", dt, PEA_PERIOD):
                self._hero_pea(seat)

    def _tick(self, key, dt, period):
        value = self.clock.get(key, 0.) + dt
        due = value + 1e-9 >= period
        self.clock[key] = value - period if due else value
        return due

    def _crowd(self):
        members = [z for z in self.g["僵尸"] if z.get("_pvp_zs_crowd") and self._zombie(z) and self._own(z)]
        reach = CROWD_RADIUS * self.b.tile
        # Columns at least `reach` wide that tile the ring exactly, so two
        # members within reach across the seam are always adjacent columns.
        cols = max(1, int(self.b.width // reach))
        cell = self.b.width / cols
        grid = {}
        for z in members:
            grid.setdefault((int(z["位置"][0] // cell) % cols, int(z["位置"][1] // reach)), []).append(z)
        for z in self.g["僵尸"]:
            if "_pvp_zs_crowd_factor" in z:
                z.pop("_pvp_zs_crowd_factor")
        for z in members:
            x, y = z["位置"][:2]
            gx, gy = int(x // cell) % cols, int(y // reach)
            count = 0
            for col in {(gx + dx) % cols for dx in (-1, 0, 1)}:   # unique even when cols < 3
                for dy in (-1, 0, 1):
                    for other in grid.get((col, gy + dy), ()):
                        if other is not z and self._distance(x, y, other["位置"][0], other["位置"][1]) <= reach:
                            count += 1
            if count:
                z["_pvp_zs_crowd_factor"] = 1. - min(CROWD_MAX, CROWD_STEP * count)

    def _steady_giants(self):
        """不可撼动: newly applied ice/butter/stun on a giant lasts half as long."""
        for z in self.g["僵尸"]:
            if z.get("_pvp_card") not in GIANTS or not self._zombie(z):
                continue
            seen = z.setdefault("_pvp_zs_control", {})
            for key in ("冰冻", "黄油", "眩晕"):
                now = z.get(key, 0) or 0
                before = seen.get(key, 0)
                if now > before + 1:
                    if key == "冰冻" and now > 1000:
                        # Halve the frozen part only; the slow tail stays native.
                        now = 1000 + (now - 1000) / 2. if before <= 1000 else before + (now - before) / 2.
                    else:
                        now = before + (now - before) / 2.
                    z[key] = now
                seen[key] = now

    def _slow_charmed(self):
        """远离诱惑: a charmed zombie is kept in the native slowed state."""
        for z in self.g["僵尸"]:
            if "魅惑" in z and self._zombie(z) and (z.get("冰冻", 0) or 0) < 100:
                z["冰冻"] = 100

    def _hero(self, seat):
        avatar = self.b.hero_states[seat]
        if avatar.get("玩家血量", 0) <= 0:
            return None
        return avatar["玩家位置"][:2]

    def _heal(self, seat):
        spot = self._hero(seat)
        if spot is None:
            return
        reach = HEAL_RADIUS * self.b.tile
        healed = 0
        for z in self.g["僵尸"]:
            if not self._zombie(z) or not self._own(z):
                continue
            if self._distance(spot[0], spot[1], z["位置"][0], z["位置"][1]) > reach:
                continue
            top = z.get("_pvp_max_hp", z["血量"])
            if z["血量"] < top:
                z["血量"] = min(top, z["血量"] + HEAL_AMOUNT)
                healed += 1
        avatar = self.b.hero_states[seat]
        hp = avatar["玩家血量"]
        top = avatar.get("_pvp_max_hp", self.b.players[seat]["max_hp"])
        # Never lowers a life raised past the cap (起床！ may do that).
        avatar["玩家血量"] = max(hp, min(top, hp + HEAL_DAVE))
        if avatar["玩家血量"] > hp:
            self.b._emit("heal", target=seat, amount=avatar["玩家血量"] - hp, kind="zsecret_heal")
        self.b._emit("zsecret_heal", side=seat, units=healed)

    def _rally_dave_speed(self):
        """汇流: a zombie Dave inside the rally reach runs 25% faster (native speedmax)."""
        reach = RALLY_RADIUS * self.b.tile
        for seat in self.b.team_seats("zombie"):
            avatar = self.b.hero_states[seat]
            base = avatar.setdefault("_pvp_base_speedmax", avatar.get("speedmax"))
            if base is None:
                continue
            point = self.b.rally_for(seat)
            spot = avatar["玩家位置"]
            near = (point is not None and avatar.get("玩家血量", 0) > 0
                    and self._distance(point["x"], point["y"], spot[0], spot[1]) <= reach)
            avatar["speedmax"] = base * RALLY_DAVE_SPEED if near else base

    def _taco(self, seat):
        spot = self._hero(seat)
        if spot is None:
            return
        best = None
        for z in self.g["僵尸"]:
            if not self._zombie(z) or not self._own(z) or "玉米卷" in z.get("_pvp_zs_speed", {}):
                continue
            d = self._distance(spot[0], spot[1], z["位置"][0], z["位置"][1])
            key = (d, z.get("_pvp_id", ""))
            if best is None or key < best[0]:
                best = (key, z)
        if best is None:
            return
        scale_speed(best[1], "玉米卷", .75)
        self.effects=[e for e in self.effects if e['until']>self.b.time]
        self.effects.append(dict(kind='taco',seat=seat,target=best[1].get('_pvp_id'),
                                 x=spot[0],y=spot[1]-self.b.tile*1.2,
                                 tx=best[1]['位置'][0],ty=best[1]['位置'][1]-self.b.tile,
                                 born=self.b.time,until=self.b.time+.8))
        self.b._emit("zsecret_taco", side=seat, entity=best[1].get("_pvp_id"))

    # ------------------------------------------------------------ attack rate
    def berserk(self, z=None):
        """狂暴 is live in deathmatch, or for the team while a Dave makes its last stand."""
        return self.has("狂暴") and (self.b.deathmatch or bool(self.last_stand))

    def focused(self, z):
        """专注啃咬: no damage taken for 5 s (any hit restarts the clock in adjust)."""
        return self.has("专注啃咬") and self.b.engine.native_tick - z.get("_pvp_zs_hurt", 0) >= FOCUS_TICKS

    def bite_rate(self, z):
        """Bite damage multiplier: 专注啃咬 and 狂暴 each add +100% (summed)."""
        if not self.enabled or not self._own(z):
            return 1.
        rate = 1.
        if self.focused(z):
            rate += 1.
        if self.berserk(z):
            rate += 1.
        return rate

    def shot_rate(self, z):
        rate = 1.
        if self.berserk(z):
            rate += 1.
        if self.has("坤坤") and z.get("_pvp_card") == "zombie:投篮车僵尸":
            rate += 1.
        return rate

    def _fast_shots(self):
        """Run shot and basket countdowns faster: add the extra share of what
        the native clock took off this frame (never touches a fresh reset).

        The original engine arms a shot only when its own single decrement lands
        exactly on 0 (`篮球cd == 0` for the cart, `植物僵尸射cd` for the pea-headed
        shooter).  So the accelerated timer must never be pushed to 0 here: that
        skips the arming frame, and because the engine only counts down while the
        timer is above 0, the unit would fire once and then sit at 0 forever
        (坤坤's cart stopped after one basketball).  Leave the last tick to the
        engine, which keeps the doubled rate within a single native frame.
        """
        for z in self.g["僵尸"]:
            if not self._zombie(z) or not self._own(z):
                continue
            rate = self.shot_rate(z)
            seen = z.setdefault("_pvp_zs_timer", {})
            for key in SHOT_TIMERS:
                if key not in z:
                    continue
                now = z[key]
                before = seen.get(key)
                if rate > 1. and before is not None and 0 < now < before:
                    now = max(1, now - (before - now) * (rate - 1.))
                    z[key] = now
                seen[key] = now

    def _basket_lock(self):
        for z in self.g["僵尸"]:
            if z.get("_pvp_zs_locked") and z.get("篮球", 0) <= 0:
                z.pop("_pvp_zs_locked")
                z["_pvp_zs_lock_done"] = True

    # ------------------------------------------------------------ 斩首行动
    def hide_plants(self, z):
        tile = self.b.tile
        rows = self.g["ditu"]
        x, y = z["位置"][:2]
        zr, zc = int(y // tile), int(x // tile)
        hidden = self.b.content.pvp64.hidden_cells
        for row in range(zr - 3, zr + 2):
            if not 0 <= row < len(rows):
                continue
            line = rows[row]
            for col in range(zc - 2, zc + 3):
                cell = line[col % len(line)]
                if "植物" in cell:
                    hidden.append((cell, cell.pop("植物")))

    # ------------------------------------------------------------ 立棍！小子
    def _pole_smash(self):
        for z in self.g["僵尸"]:
            if not z.get("_pvp_zs_pole"):
                if z.get("_pvp_card") in ("zombie:撑杆跳僵尸", "zombie:黑撑杆僵尸") and z.get("手持") == "撑杆":
                    z["_pvp_zs_pole"] = True     # the black pole is picked up again
                continue
            if z.get("手持") == "撑杆" or not self._zombie(z):
                continue
            z["_pvp_zs_pole"] = False
            self.smash(z)

    def smash(self, z):
        b = self.b
        x, y = z["位置"][:2]
        facing = 1 if z.get("方向", 1) >= 0 else -1
        tile = b.tile
        owner = b.targets.owner(z)
        from .simulation import wrap_delta
        def ahead(px, py):
            dx = wrap_delta(x, px, b.width) * facing
            return -tile * .3 <= dx <= POLE_REACH * tile and abs(py - y) < tile
        hit = 0
        for plant in self.g["植物"]:
            if plant.get("植物血", 0) <= 0 or b.targets.owner(plant) == owner:
                continue
            row, col = plant["坐标"]
            if ahead((col + .5) * tile, (row + 1) * tile):
                plant["植物血"] -= b.protection.amount(plant, POLE_DAMAGE)
                plant["受伤"] = 1
                if plant["植物血"] <= 0:
                    plant["植物血"] = 0
                    plant["死"] = 0
                hit += 1
        foe = "plant" if owner == "zombie" else "zombie"
        with b.targets.full_targets(), b.targets.context(foe, owner, "status", z):
            for index, other in enumerate(self.g["僵尸"]):
                if other is z or other.get("_pvp_hero") or other.get("血量", 0) <= 0 or b.targets.owner(other) == owner:
                    continue
                if ahead(other["位置"][0], other["位置"][1]):
                    self.g["伤害僵尸"](index, facing, POLE_DAMAGE * 10.)
                    hit += 1
            for seat in b.team_seats(foe):
                hero = b.targets.hero_proxy(seat)
                if hero["血量"] > 0 and ahead(hero["位置"][0], hero["位置"][1]):
                    b.targets.damage_hero(seat, POLE_DAMAGE, "pole")
                    hit += 1
        b._emit("zsecret_pole_smash", entity=z.get("_pvp_id"), targets=hit)

    # ------------------------------------------------------------ 二手
    def on_armor_break(self, z, slot, name, top):
        """A piece broke on a zombie: leave a half-life second-hand copy."""
        if not self.has("二手") or not name or z.get("_pvp_hero") or z.get("_pvp_grave"):
            return
        if team_of(z.get("_pvp_owner", "zombie")) != "zombie":
            return
        if (z.get("_pvp_zs_secondhand") or {}).get(slot):
            return              # a second-hand piece never drops again
        if top <= 0:
            return
        self.pickup_serial += 1
        x, y = z["位置"][:2]
        black = worn_black_armor(z) if slot == "防具" else None
        self.pickups.append(dict(id="zs%d" % self.pickup_serial, slot=slot, name=name, hp=top / 2.,
                                 kind=(hand_kind(z) or name) if slot == '手持' else name,
                                 dropper=id(z),
                                 x=x, y=y, until=self.b.time + PICKUP_SECONDS,
                                 black=black if black in ("黑路障僵尸", "黑铁桶僵尸") else None))
        self.b._emit("zsecret_armor_drop", name=name, slot=slot)

    def _wearer(self, z, item):
        if not self._zombie(z) or not self._own(z) or "魅惑" in z:
            return False
        if item["slot"] == "防具":
            check = self.b.patch.ns.get("__pvz_sb_zombie_has_head_armor")
            worn = check(z) if callable(check) else bool(z.get("防具"))
            return ("防具" in z and "防具血量" in z and not worn and not z.get("手持") == "撑杆")
        if item.get('kind', item['name']) in SHARED_HAND_ARMOR:
            return ('手持' in z and '手持血量' in z and not z['手持'] and z['手持血量'] <= 0)
        # Newspapers retain their native newspaper-zombie rage controller.
        return not z.get("手持") and z.get("_pvp_zs_hand") == item["name"]

    def _riding_wearer(self, z, item):
        return (item['slot'] == '防具' and self._zombie(z) and self._own(z)
                and '魅惑' not in z and CARRIER_BODY_MARK in str(z.get('僵尸', ''))
                and '丢小鬼' not in z and not z.get(IMP_ARMOR) and z.get(IMP_ARMOR_HP, 0) <= 0)

    def _pickups(self):
        keep = []
        reach = PICKUP_REACH * self.b.tile
        for item in self.pickups:
            if self.b.time >= item["until"]:
                continue
            taker = None
            riding = False
            for z in self.g["僵尸"]:
                if id(z) == item['dropper'] or not self._zombie(z):continue
                if self._distance(item['x'], item['y'], z['位置'][0], z['位置'][1]) > reach:continue
                if self._wearer(z, item):
                    taker = z
                    break
                if self._riding_wearer(z, item):
                    taker, riding = z, True
                    break
            if taker is None:
                keep.append(item)
                continue
            slot = item["slot"]
            if riding:
                art = {'黑路障僵尸':'黑路障', '黑铁桶僵尸':'黑铁桶'}.get(item.get('black'), item['name'])
                taker[IMP_ARMOR], taker[IMP_ARMOR_HP] = art, item['hp']
                taker.setdefault('_pvp_zs_secondhand', {})[IMP_ARMOR] = True
                self.b._emit('zsecret_armor_pickup', entity=taker.get('_pvp_id'), name=art, wearer='riding_imp')
                continue
            taker[slot] = item["name"]
            taker[slot + "血量"] = item["hp"]
            if slot == '手持':
                taker['_pvp_zs_hand_kind'] = item.get('kind', item['name'])
                taker['_pvp_zs_hand_max'] = item['hp']
            taker.setdefault("_pvp_zs_secondhand", {})[slot] = True
            if slot == '防具':
                taker[IMP_BLACK_ARMOR] = item.get('black')
                taker['_pvp_armor_max'] = item['hp']
                # Only ordinary bodies can use the black-regiment body art.
                if item.get('black') and taker.get('僵尸') in ('普通僵尸', '旗帜僵尸', '鸭子普通僵尸'):
                    taker['_pvp_variant'] = taker.get('_pvp_variant') or item['black']
                taker.pop('_pvp_armor_triggered', None)
            self.b._emit("zsecret_armor_pickup", entity=taker.get("_pvp_id"), name=item["name"])
        self.pickups = keep

    def public_pickups(self):
        # Keep the native logic name for AI/pickup rules, and carry the colour
        # separately so guests/replays use the armour's existing black artwork.
        art = {"黑路障僵尸": "黑路障", "黑铁桶僵尸": "黑铁桶"}
        return [dict(id=i["id"], name=i.get('kind', i['name']), asset=art.get(i.get("black"), i.get('kind', i['name'])),
                     x=i["x"], y=i["y"]) for i in self.pickups]

    # ------------------------------------------------------------ 豌豆
    def jump_cap(self, seat):
        pea=self.seat_has(seat,"豌豆");pressure=self.seat_has(seat,"威压")
        return (2 if pressure else 1) if pea else 3 if pressure else None

    def _hero_pea(self, seat):
        avatar = self.b.hero_states[seat]
        if avatar.get("玩家血量", 0) <= 0:
            return
        x, y = avatar["玩家位置"][:2]
        facing = 1 if avatar.get("玩家方向", 1) >= 0 else -1
        tile = self.b.tile
        head_y = y - tile * 1.6
        from .simulation import wrap_delta
        def ahead(px, py):
            dx = wrap_delta(x, px, self.b.width) * facing
            return 0 < dx <= PEA_RANGE * tile and abs(py - head_y) < tile * 1.6
        targets=[]
        for p in self.g['植物']:
            if p.get('植物血',0)>0 and self.b.targets.owner(p)=='plant':
                px,py=(p['坐标'][1]+.5)*tile,(p['坐标'][0]+.5)*tile
                if ahead(px,py):targets.append((px,py))
        for side in self.b.team_seats('plant'):
            hero=self.b.hero_states[side]
            px,py=hero['玩家位置'][0],hero['玩家位置'][1]-tile
            if hero.get('玩家血量',0)>0 and ahead(px,py):targets.append((px,py))
        if not targets:
            return
        px,py=min(targets,key=lambda point:math.hypot(wrap_delta(x,point[0],self.b.width),point[1]-head_y))
        angle=math.degrees(math.atan2(py-head_y,wrap_delta(x,px,self.b.width)))
        avatar['_pvp_pea_angle']=angle
        spawn = self.b.patch.ns.get("__pvz_sb_spawn_zombie_pea")
        if not callable(spawn):
            return
        proxy = self.b.targets.hero_proxy(seat)
        before = len(self.g['实体'])
        with self.b.targets.context("plant", "zombie", "entities", proxy):
            spawn(self.g, x + facing * tile * .2, head_y, angle, source_zombie=proxy)
            # The patch helper calls its saved original 增实体, bypassing
            # NativeTargets' normal add-entity wrapper. Give these shots the
            # same allegiance/source metadata as ordinary zombie shots.
            for entity in self.g['实体'][before:]:
                self.b.targets.tag_entity(entity, 'zombie', proxy)
                entity['_pvp_seat'] = seat
        self.b._emit("zsecret_hero_pea", side=seat)

    # ------------------------------------------------------------ late hooks
    def install_late(self):
        """Hooks on patch functions, after the combat targets are bound."""
        if not self.has("散弹攻击"):
            return
        ns = self.b.patch.ns
        name = "__pvz_sb_spawn_zombie_pea"
        original = ns[name]
        def spawn(g, x, y, angle, friendly=False, source_zombie=None):
            mode = self.shotgun_volley(source_zombie) if isinstance(source_zombie, dict) and not friendly else None
            if mode is None:
                return original(g, x, y, angle, friendly, source_zombie)
            if mode is False:
                return True          # 散弹攻击: this burst pea is part of the fan
            fired = False
            for offset in SHOTGUN_FAN:
                fired = original(g, x, y, angle + offset, friendly, source_zombie) or fired
            return fired
        spawn.__wrapped__ = original
        ns[name] = spawn

    # ------------------------------------------------------------ 散弹攻击
    def shotgun_volley(self, source):
        """None: ordinary pea. True: the first pea of a machine-gun burst, to
        be fanned into six. False: a later pea of that burst (dropped)."""
        if (not self.enabled or not self.has("散弹攻击") or source.get("_pvp_card") != "zombie:机枪僵尸"
                or not self._own(source)):
            return None
        tick = self.b.engine.native_tick
        last = source.get("_pvp_zs_volley")
        if last is not None and tick - last < VOLLEY_TICKS:
            return False
        source["_pvp_zs_volley"] = tick
        return True

    # ------------------------------------------------------------ 自爆
    def can_blast(self, z):
        return self._zombie(z) and self._own(z) and "灰烬" not in z and not z.get("_pvp_zs_blasted")

    def self_destruct(self, seat, uid):
        """自爆: ceil(current life / 25) within 2.4 tiles."""
        if not self.seat_has(seat, "自爆"):
            return "需要携带自爆秘籍"
        b = self.b
        z = b._native_objects.get(uid) if isinstance(uid, str) else None
        if z is None or not self.can_blast(z):
            return "只能引爆己方存活的僵尸"
        if z.get("_pvp_seat", seat) != seat:
            return "只能引爆自己的僵尸（队友的单位不能引爆）"
        z["_pvp_zs_blasted"] = True
        amount = math.ceil(max(0., z.get("血量", 0)) * BLAST_SHARE)
        x, y = z["位置"][0], z["位置"][1] - b.tile * .5
        reach = BLAST_RADIUS * b.tile
        hit = 0
        for plant in self.g["植物"]:
            if plant.get("植物血", 0) <= 0 or b.targets.owner(plant) != "plant":
                continue
            row, col = plant["坐标"]
            if self._distance(x, y, (col + .5) * b.tile, (row + .5) * b.tile) <= reach:
                plant["植物血"] -= b.protection.amount(plant, amount)
                plant["受伤"] = 1
                if plant["植物血"] <= 0:
                    plant["植物血"] = 0
                    plant["死"] = 0
                hit += 1
        with b.targets.full_targets(), b.targets.context("plant", "zombie", "status", z):
            for index, other in enumerate(self.g["僵尸"]):
                if other is z or other.get("_pvp_hero") or other.get("血量", 0) <= 0 or b.targets.owner(other) == "zombie":
                    continue
                if self._distance(x, y, other["位置"][0], other["位置"][1] - b.tile * .5) <= reach:
                    self.g["伤害僵尸"](index, 1, amount * 10.)
                    hit += 1
            for side in b.team_seats("plant"):
                hero = b.targets.hero_proxy(side)
                if hero["血量"] > 0 and self._distance(x, y, hero["位置"][0], hero["位置"][1] - b.tile * .5) <= reach:
                    b.targets.damage_hero(side, amount, "blast")
                    hit += 1
        z["血量"] = 0
        b._emit("zsecret_blast", side=seat, entity=uid, damage=amount, targets=hit)
        b._sync_public()
        return ""

    # ------------------------------------------------------------ 遗骸
    def _relic_expiry(self):
        tick = self.b.engine.native_tick
        for obj in self.b._native_objects.values():
            until = obj.get("_pvp_zs_relic_until")
            if until is not None and tick >= until and obj.get("血量", 0) > 0:
                obj["血量"] = 0

    # ------------------------------------------------------------ 最后攻势
    def hero_amount(self, seat, avatar, amount):
        """Damage to a zombie Dave: the last stand turns the fatal hit into 1 HP."""
        if not self.seat_has(seat, "最后攻势"):
            return amount
        hp = avatar.get("玩家血量", 0)
        if seat in self.last_stand:
            return min(amount, max(0., hp - 1.))
        if amount >= hp and seat not in self.last_stand_used and hp > 0:
            self.last_stand_used.add(seat)
            self.last_stand[seat] = self.b.time + LAST_STAND_SECONDS
            self.b._emit("zsecret_last_stand", side=seat, seconds=LAST_STAND_SECONDS)
            return max(0., hp - 1.)
        return amount

    def in_last_stand(self, seat):
        return seat in self.last_stand

    def team_last_stand(self):
        return bool(self.last_stand)

    def _last_stand_step(self):
        for seat, until in list(self.last_stand.items()):
            avatar = self.b.hero_states[seat]
            if self.b.time >= until:
                self.last_stand.pop(seat)
                avatar["玩家血量"] = 0
                self.b.players[seat]["hp"] = 0
                self.b._emit("zsecret_last_stand_end", side=seat)
            else:
                avatar["玩家血量"] = max(1.,avatar.get('玩家血量',0))
                avatar["玩家倒地"] = 0
                avatar['玩家恢复'] = 0

    # ------------------------------------------------------------ 威压
    def pressure(self, plant):
        """Interval factor for a plant near a 威压 Dave (progress /1.3)."""
        if not self.enabled or not self.has("威压") or self.b.targets.owner(plant) != "plant":
            return 1.
        tick = self.b.engine.native_tick
        if self._pressure[0] != tick:
            spots = [self._hero(seat) for seat in self.holders("威压")]
            self._pressure = (tick, [s for s in spots if s is not None])
        row, col = plant["坐标"]
        x, y = (col + .5) * self.b.tile, (row + .5) * self.b.tile
        reach = PRESSURE_RADIUS * self.b.tile
        for hx, hy in self._pressure[1]:
            if self._distance(hx, hy - self.b.tile, x, y) <= reach:
                return PRESSURE_FACTOR
        return 1.

    # ------------------------------------------------------------ 植物僵尸
    def _queue_conversion(self, plant):
        name = PLANT_ZOMBIES.get(plant.get("植物"))
        if not name or "zombie:" + name not in self._cards():
            return
        holders = self.holders("植物僵尸")
        row, col = plant["坐标"]
        self.converts.append((name, (col + .5) * self.b.tile, (row + 1) * self.b.tile,
                              -(plant.get("方向", 1) or 1), holders[0]))

    @staticmethod
    def _cards():
        from .catalog import CARDS
        return CARDS

    def _convert(self):
        queued, self.converts = self.converts, []
        b = self.b
        for name, x, y, facing, seat in queued:
            saved = b._acting_seat
            b._acting_seat = seat
            try:
                unit = b.spawn("zombie:" + name, "zombie", x, y, facing, True)
            except ValueError:
                unit = None      # a banned form is not created
            finally:
                b._acting_seat = saved
            if unit is None:
                continue
            native = b._native_objects.get(unit["id"])
            if native is not None:
                scale_hp(native, .5)
                native["_pvp_zs_converted"] = True
            b._emit("zsecret_plant_zombie", side=seat, entity=unit["id"], card="zombie:" + name)

    # ------------------------------------------------------------ economy
    def day_income_count(self, previous, now, interval):
        """补贴: number of day brain payments between two native ticks."""
        if not self.has("补贴"):
            return None
        empty = not any(self._zombie(z) and self._own(z) for z in self.g["僵尸"])
        self.subsidy_phase += (now - previous) * (2 if empty else 1)
        count, self.subsidy_phase = divmod(self.subsidy_phase, interval)
        return int(count)

    def pay(self, seat, amount, x, y, reason):
        rid = self.b.resource(seat, amount, x, y, reason)
        self.b._sun_motion.pop(rid, None)
        self.b._collect(rid)

    def on_plant_killed(self, plant):
        """Called from the native plant death gate (a plant reduced to 0)."""
        if not self.enabled or self.b.targets.owner(plant) != "plant" or plant.get("_pvp_zs_killed"):
            return
        plant["_pvp_zs_killed"] = True      # one reward per plant death
        row, col = plant["坐标"]
        x, y = (col + .5) * self.b.tile, (row + 1) * self.b.tile
        for seat in self.holders("脑光"):
            self.pay(seat, BRAIN_PER_KILL, x, y, "zsecret_brain")
        if self.has("植物僵尸") and not plant.get("_pvp_temporary"):
            self._queue_conversion(plant)

    def on_unit_gone(self, obj):
        """汇流: a zombie that dies near the rally flag refunds 15 brains."""
        if not self.enabled or not self.has("汇流"):
            return
        point = self.b.rally_for(obj)
        if point is None or obj.get("_pvp_grave") or obj.get("_pvp_hero") or "植物" in obj:
            return
        if obj.get("_pvp_owner") != "zombie" or "魅惑" in obj or obj.get("血量", 0) > 0:
            return
        if self._distance(point["x"], point["y"], obj["位置"][0], obj["位置"][1]) > RALLY_RADIUS * self.b.tile:
            return
        # The refund goes to whoever paid for the fallen unit (2v2: its seat).
        seat = obj.get("_pvp_seat", "zombie")
        if seat not in self.b.players:
            seat = "zombie"
        self.pay(seat, RALLY_REFUND, obj["位置"][0], obj["位置"][1], "zsecret_rally")

    # ------------------------------------------------------------ graves
    def on_teleport(self, seat):
        """起床！: graves within 2.4 tiles of the arrival never sleep again."""
        if not self.seat_has(seat, "起床！"):
            return
        spot = self._hero(seat)
        if spot is None:
            return
        woken = 0
        for uid, obj in self.b._native_objects.items():
            if obj.get("_pvp_grave") and obj.get("血量", 0) > 0 and team_of(obj.get("_pvp_owner", "")) == "zombie":
                if self._distance(spot[0], spot[1], obj["位置"][0], obj["位置"][1]) <= WAKE_RADIUS * self.b.tile:
                    woken += not obj.get("_pvp_zs_awake")
                    obj["_pvp_zs_awake"] = True
                    obj["_pvp_idle"] = 0.
        # Like the plant 闪现 heal: added on every successful teleport, past the cap.
        self.b.hero_states[seat]["玩家血量"] += WAKE_HEAL
        self.b._emit("heal", target=seat, amount=WAKE_HEAL, kind="zsecret_wake")
        self.b._emit("zsecret_wake", side=seat, graves=woken)

    def flag_summon(self, flag):
        """一大波僵尸: the plain flag pulls a cone zombie from each grave."""
        if flag.get("card_id") == "zombie:旗帜僵尸" and self.has("一大波僵尸"):
            return "zombie:路障僵尸"
        return None

    def torch_range_scale(self):
        """暴怒: petrified torch reach doubles."""
        return RAGE_TORCH_RANGE if self.has("暴怒") else 1.

    def torch_sleep_scale(self):
        """暴怒: petrified torch sleep halves."""
        return RAGE_TORCH_SLEEP if self.has("暴怒") else 1.

    def blast_scale(self):
        """沉默: black cone/bucket drop reach doubles."""
        return 2. if self.has("沉默") else 1.

    # ------------------------------------------------------------ crows
    def scarecrows(self):
        return [z for z in self.b.content.pvp61.scarecrows() if self._own(z) and z.get("血量", 0) > 0]

    def crow_surcharge(self, seat):
        if not self.seat_has(seat, "鸦群"):
            return 0
        return CROW_SURCHARGE * len(self.scarecrows())

    def crow_flock(self, crow, seat):
        """鸦群: every living scarecrow calls one crow (replaces the echo)."""
        b = self.b
        made = []
        for scarecrow in sorted(self.scarecrows(), key=lambda z: z.get("_pvp_id", "")):
            sx, sy = scarecrow["位置"][:2]
            with b._ban_free_spawn():
                child = b.spawn("zombie:乌鸦", "zombie", sx, sy - b.tile, scarecrow.get("方向", 1), True,
                                parent={"id": crow["id"]})
            if child is not None:
                made.append(child["id"])
        b._emit("zsecret_crows", side=seat, source=crow["id"], entities=made)
        return made
