"""PvP66 PvE: the day campaign and the zombie wave director.

PvE runs on the very same NativeBattle as PvP (original 250 Hz engine, C++
core, every PvP card), with the zombie seat dormant and this director in its
place. Zombies come from tiered pools modelled on the original game's A/B/C
lists (A尸/B尸/C尸) and the plant-zombie mode's additions. Solo unlocks C/B/A
on days 4/6/8 with a three-day ramp; co-op uses days 6/10/14 and a five-day
ramp. Untiered zombies and ladder support start on day 1. The wave budget
grows with the day, so later days bring stronger zombies.

Plants are unlocked by clearing days: each cleared day offers three cards to
choose one from. The deck for a day carries up to slots_for_day(day) cards;
starting tools are selectable and each takes one slot. A new campaign selects
flower pot so its first solid-ground map is playable.
"""
import json
import math
import random
from pathlib import Path

from .catalog import CARDS, map_card_error
from .native_bridge import MAP_NAMES

# Tiers. 0 = untiered basics, 1 = C, 2 = B, 3 = A (the strongest).
TIERS = {
    0: ("普通僵尸", "路障僵尸", "铁桶僵尸", "撑杆跳僵尸", "小鬼僵尸", "垃圾桶僵尸", "伴舞僵尸",
        "稻草人", "豌豆僵尸", "坚果僵尸", "黑普通僵尸"),
    1: ("小丑僵尸", "气球僵尸", "蹦蹦僵尸", "钢门普通僵尸", "毁灭菇僵尸", "三叶草僵尸", "萝卜伞僵尸",
        "掷弹兵僵尸", "倭瓜僵尸", "海盗鹦鹉", "黑路障僵尸", "雪人僵尸", "钩索僵尸"),
    2: ("铁桶钢门僵尸", "橄榄球僵尸", "矿工僵尸", "投篮车僵尸", "梯子僵尸", "辣椒僵尸", "路灯花僵尸",
        "吸金磁僵尸", "史莱姆僵尸", "传送带僵尸", "滚桶僵尸", "乌鸦", "舞王僵尸", "海盗船长",
        "黑铁桶僵尸", "黑撑杆僵尸", "大喷菇僵尸", "雪橇车小队", "死神僵尸"),
    3: ("报纸僵尸", "巨人僵尸", "雪橇车僵尸", "高坚果僵尸", "墓碑吞噬者僵尸", "机枪僵尸", "红眼巨人",
        "角斗士巨人", "小鬼炮", "黑橄榄僵尸"),
}
TIER_NAMES = {0: "普通", 1: "C 档", 2: "B 档", 3: "A 档"}
TIER_UNLOCK_DAY = {0: 1, 1: 4, 2: 6, 3: 8}
COOP_TIER_UNLOCK_DAY = {0: 1, 1: 6, 2: 10, 3: 14}
TIER_WEIGHT = {0: 6., 1: 4., 2: 3., 3: 2.}
FLAG_ZOMBIE = "zombie:旗帜僵尸"

STARTER_PLANTS = ("plant:向日葵", "plant:豌豆射手", "plant:坚果", "plant:土豆地雷")
# Tools every Dave owns from the start.  They are ordinary deck cards now: the
# player picks them on the selection board and each one takes a slot (花盆 and
# 睡莲 used to ride along unseen and slot-free, which is what players reported
# as "not selectable").
FREE_TOOLS = ("plant:花盆", "plant:睡莲", "plant:咖啡豆")
NOT_REWARDS = frozenset(FREE_TOOLS) | {"plant:石块", "plant:模仿者"}
# 68004: solo runs and co-op retire the same cards (co-op first lost 甜薯 and
# 稻草人; 垃圾桶僵尸 now leaves both, and solo matches co-op).
CAMPAIGN_DISABLED = frozenset(('plant:甜薯', 'zombie:稻草人', 'zombie:垃圾桶僵尸'))
COOP_DISABLED = CAMPAIGN_DISABLED


def disabled_message(coop=False):
    return '合作模式禁用此卡' if coop else '闯关模式禁用此卡'


def campaign_card_allowed(key, coop=False):
    """Mode restrictions include secret precursor chains, not saved ownership."""
    if not isinstance(key, str) or key not in CARDS:
        return False
    seen = set()
    while key:
        if key in seen or key not in CARDS or key in CAMPAIGN_DISABLED:
            return False
        seen.add(key)
        key = CARDS[key].get('dependency')
    return True

FIRST_WAVE = 25.       # seconds before the first wave: time to build economy
WAVE_INTERVAL = 30.    # days 1-3 retain the original economy-building buffer
STAGGER = 4.           # a wave's zombies arrive over this many seconds
COOP_BUDGET = 1.7      # two Daves face this much more per wave
SPAWN_PRESSURE_RATIO = .7    # engine share of one core above which waves are paced
LADDER_SUPPORT = 'zombie:梯子僵尸'
LADDER_SUPPORT_RESERVE = 15  # native campaign reserve at normal protection
DEFAULT_MAX_ZOMBIES = 40
MAX_ZOMBIE_LIMIT = 200
WAVE_CLEAR_PERCENT = 80


def valid_zombie_limit(value):
    return type(value) is int and 1 <= value <= MAX_ZOMBIE_LIMIT


def zombie_limit(value):
    """Old/corrupt saves use the default; explicit room commands validate."""
    return value if valid_zombie_limit(value) else DEFAULT_MAX_ZOMBIES


def tier_of(key):
    name = key.split(":", 1)[1]
    return next((tier for tier, names in TIERS.items() if name in names), None)


def _with_tools(keys):
    """Owned list with the three starting tools, in a stable order."""
    owned = list(keys)
    owned.extend(k for k in FREE_TOOLS if k not in owned)
    return owned


def slots_for_day(day):
    return min(10, 4 + (day + 1) // 2)


def waves_for_day(day):
    return 4 + min(day, 8) // 2


def zombie_pool(day, terrain=None, coop=False):
    """(key, tier, weight) of every zombie that may appear on this day."""
    pool = []
    for tier, names in TIERS.items():
        unlock = (COOP_TIER_UNLOCK_DAY if coop else TIER_UNLOCK_DAY)[tier]
        if day < unlock and not (tier == 2 and day >= 1):
            continue
        ramp = min(1., (day - unlock + 1) / (5. if coop else 3.))
        for name in names:
            if day < unlock and name != '梯子僵尸':
                continue
            key = "zombie:" + name
            card = CARDS.get(key)
            if not campaign_card_allowed(key, coop):
                continue
            if card is None or card.get("aquatic") or card.get("behavior") in ("grave", "thief"):
                continue
            if terrain is not None and map_card_error(key, terrain):
                continue
            # Late pressure favors expensive B/A zombies rather than merely
            # filling the screen with ever more cheap bodies.
            late_weight = min(2., 1. + (.1 if coop else .2) * max(0, day - (15 if coop else 9))) if tier >= 2 else 1.
            admitted_ramp=max(ramp,1./3.) if key==LADDER_SUPPORT else ramp
            pool.append((key, tier, TIER_WEIGHT[tier] * admitted_ramp * late_weight))
    return pool


def difficulty_for_day(day):
    """Budget multiplier and interval: buffer days 1-3, ramp through day 8."""
    ramp = min(5, max(0, int(day) - 3))
    return 1. + .2 * ramp, WAVE_INTERVAL - 1.5 * ramp


def wave_plan(day, coop=False):
    """Start time, brain budget and flag marker of each wave of a day."""
    count = waves_for_day(day)
    multiplier, interval = difficulty_for_day(day)
    base = (40. + 30. * day) * (COOP_BUDGET if coop else 1.) * multiplier
    plan = []
    for index in range(count):
        flag = index == count - 1
        budget = base * (1. + .25 * index) * (2. if flag else 1.)
        plan.append(dict(time=FIRST_WAVE + interval * index, budget=round(budget), flag=flag))
    return plan


def coin_drop(key, rng):
    """(amount, kind): silver by the zombie's price, sometimes gold, rarely a money bag."""
    cost = CARDS[key]["cost"] if key in CARDS else 25
    roll = rng.random()
    if key == FLAG_ZOMBIE or roll < .03:
        return 100, "bag"
    base = max(5, int(round(cost / 50.)) * 5)
    if roll < .18:
        return base + 25, "gold"
    return base, "silver"


def health_scale(day):
    """Day 10+ also toughens existing bodies; entity count is not the only lever."""
    return min(1.8, 1. + .08 * max(0, day - 9))


class WaveDirector:
    def __init__(self, day, seed=1, coop=False, max_zombies=DEFAULT_MAX_ZOMBIES):
        self.day = int(day)
        self.coop = bool(coop)
        self.seed = int(seed)
        self.rng = random.Random((int(seed) * 1000003) ^ (self.day * 7919) ^ 0x66)
        self.plan = wave_plan(self.day, self.coop)
        self.next_wave = 0
        self.queue = []          # (time, key, point index, owning wave)
        self.spawned = []
        self.points = []
        self.pool = []
        self.last_spawn_time = None
        self._battle = None
        self.cycle = None       # optional until bind installs a co-op clock
        self.alive = {}          # uid -> (card key, last position) of our zombies
        self.paced = 0           # spawns held back because the engine was busy
        self.pressure_seconds = 0.
        self.pending_ladders=[]
        self.last_flag=False
        self.max_zombies = zombie_limit(max_zombies)
        self.wave_members = {}  # wave -> every stable id ever born, children included
        self.wave_started = {}

    # -------------------------------------------------------------- setup
    def bind(self, battle):
        from .maps import MapSnapshot
        from .team_maps import derive_layout
        self._battle = battle
        size = battle.tile
        points = battle.map.get("environment", {}).get("zombie_points")
        if not points:
            snapshot = MapSnapshot.from_dict(battle.map)
            layout = derive_layout(snapshot)
            points = [[(col + .5) * size, float(row * size)] for col, row in layout["zombie_points"]]
        self.points = [tuple(p) for p in points]
        self.pool = zombie_pool(self.day, battle.map, self.coop)
        battle.g['梯子尸数']=LADDER_SUPPORT_RESERVE
        battle.g['梯子cd']=0
        # The dormant zombie seat lists today's zombies for the almanac.
        battle.players["zombie"]["deck"] = [key for key, tier, weight in self.pool]
        self.cycle = None
        if self.coop:
            from .coop_cycle import CoopCycle
            self.cycle = CoopCycle(self, battle)

    # --------------------------------------------------------------- run
    def _compose(self, budget, flag):
        chosen = []
        if flag and FLAG_ZOMBIE in CARDS:
            chosen.append(FLAG_ZOMBIE)
            budget -= CARDS[FLAG_ZOMBIE]["cost"]
        pool = [(key, weight) for key, tier, weight in self.pool if weight > 0]
        while pool:
            affordable = [(key, weight) for key, weight in pool if CARDS[key]["cost"] <= budget]
            if not affordable:
                break
            total = sum(weight for key, weight in affordable)
            pick = self.rng.random() * total
            for key, weight in affordable:
                pick -= weight
                if pick <= 0:
                    break
            chosen.append(key)
            budget -= CARDS[key]["cost"]
        return chosen

    def step(self, battle):
        now = battle.time
        self._observe_wave_members(battle)
        self._pay_bounties(battle)
        # Only the opening preparation is timed. Later waves depend on actual
        # clear progress; a full spawn queue can never be mistaken for kills.
        if self._can_advance(battle, now):
            wave_index = self.next_wave
            wave = self.plan[self.next_wave]
            self.last_flag=bool(wave['flag'])
            keys = self._compose(wave["budget"], wave["flag"])
            if self.next_wave == 0:
                # An initial helper guarantees day-one ladder availability;
                # it is support, outside the unchanged wave budget.
                keys.insert(0,LADDER_SUPPORT)
                battle.g['梯子尸数']=max(0,battle.g['梯子尸数']-1)
                battle._emit('pve_ladder_support',source='opening',day=self.day)
            fronts = self.fronts(wave)
            for index, key in enumerate(keys):
                at = now + STAGGER * index / max(1, len(keys))
                self.queue.append((at, key, fronts[index % len(fronts)], wave_index))
            self.wave_members.setdefault(wave_index, set())
            self.wave_started[wave_index] = now
            battle._emit("pve_wave", day=self.day, wave=self.next_wave + 1, waves=len(self.plan),
                         flag=wave["flag"], count=len(keys))
            self.next_wave += 1
        for point in self.pending_ladders:
            self.queue.append((now,LADDER_SUPPORT,point,max(0,self.next_wave-1)))
        self.pending_ladders=[]
        # Late days can queue a wave faster than the original engine simulates
        # it, and that backlog is what makes the last days stutter. Under load
        # the director releases the same zombies one at a time instead of the
        # whole wave at once: composition, totals and clear condition never
        # change, only the spacing.
        pressure = getattr(battle, "native_cost_ratio", None) or 0.
        due = [entry for entry in self.queue if entry[0] <= now + 1e-9]
        if pressure >= SPAWN_PRESSURE_RATIO and len(due) > 1:
            self.paced += len(due) - 1
            due = due[:1]
        budget = getattr(battle, 'scripted_spawn_budget', None)
        # Native one-shot summons get their reserved retry before new waves.
        if budget is not None and budget.pending_count():
            due = []
        for entry in due:
            available = budget.available() if budget is not None else self.max_zombies-self.remaining(battle)
            if available <= 0:
                break
            at, key, point = entry[:3]
            wave_index = entry[3] if len(entry)>3 else max(0,self.next_wave-1)
            if self._spawn(battle, key, point, wave_index):
                self.queue.remove(entry)
            else:
                break
        if pressure >= SPAWN_PRESSURE_RATIO:
            self.pressure_seconds += 1. / 30.

    def _observe_wave_members(self, battle):
        for obj in (getattr(battle,'g',{}) or {}).get('僵尸',()):
            index, uid = obj.get('_pvp_wave_index'), obj.get('_pvp_id')
            if type(index) is int and uid is not None:
                self.wave_members.setdefault(index,set()).add(uid)

    def _wave_progress(self, battle, index):
        from .scripted_spawn_budget import is_live_enemy
        self._observe_wave_members(battle)
        members = self.wave_members.get(index,set())
        budget = getattr(battle,'scripted_spawn_budget',None)
        pending = budget.pending_count(index) if budget is not None else 0
        live = 0
        for uid in members:
            obj = getattr(battle,'_native_objects',{}).get(uid)
            if obj is not None:
                if budget is not None:
                    live += bool(is_live_enemy(obj))
                else:
                    live += bool(obj.get('血量',0)>0 and '魅惑' not in obj and '灰烬' not in obj)
            elif uid in battle.units:
                unit=battle.units[uid]
                live += bool(unit.get('hp',0)>0 and unit.get('side')=='zombie')
        total = len(members)+pending
        killed = max(0,total-live-pending)
        queued = sum(1 for entry in self.queue
                     if (entry[3] if len(entry)>3 else max(0,self.next_wave-1))==index)
        return dict(total=total,remaining=live+pending,cleared=killed,
                    clear_percent=(100*killed//total) if total else 100,queued=queued,pending=pending)

    def _can_advance(self, battle, now):
        if self.next_wave>=len(self.plan):return False
        if self.next_wave==0:return now+1e-9>=self.plan[0]['time']
        progress=self._wave_progress(battle,self.next_wave-1)
        return progress['queued']==0 and progress['clear_percent']>=WAVE_CLEAR_PERCENT

    def request_ladder(self,battle,zombie):
        """A native blocked-unit trigger can request support anywhere on map."""
        if not self.points or battle.g['梯子尸数']<=0 or battle.g['梯子cd']>0:
            return
        x,y=zombie['位置'][:2]
        point=min(range(len(self.points)),key=lambda i:
            min(abs(self.points[i][0]-x),battle.width-abs(self.points[i][0]-x))**2+(self.points[i][1]-y)**2)
        self.pending_ladders.append(point)
        battle.g['梯子尸数']-=1
        battle.g['梯子cd']=2000 if self.last_flag else 10000
        battle._emit('pve_ladder_support',source='blocked',point=point,day=self.day)

    def fronts(self, wave):
        """Spawn points of one wave: co-op splits every wave over all points so
        each Dave holds a front; solo gets one front (two from day 6, and on
        the flag wave)."""
        count = len(self.points)
        if not count:
            return [0]
        if self.coop:
            start = self.rng.randrange(count)
            return [(start + i) % count for i in range(count)]
        width = 2 if (self.day >= 6 or wave["flag"]) and count > 1 else 1
        return self.rng.sample(range(count), width)

    def _spawn(self, battle, key, point, wave_index=None):
        if not self.points:
            return False
        budget = getattr(battle,'scripted_spawn_budget',None)
        if (budget is not None and not budget.can_spawn()) or (budget is None and self.remaining(battle)>=self.max_zombies):
            return False
        x, y = self.points[point % len(self.points)]
        origin = (self.cycle.origin(point % len(self.points), battle._card('zombie', key), max(0,self.next_wave-1) if wave_index is None else wave_index)
                  if self.cycle else None)
        if origin:
            x, y = origin[1]
        else:
            x = (x + (self.rng.random() - .5) * battle.tile * .8) % battle.width
        target = min(battle.team_seats("plant", alive=True) or ["plant"],
                     key=lambda seat: abs(battle.players[seat]["x"] - x))
        facing = 1 if ((battle.players[target]["x"] - x + battle.width / 2.) % battle.width - battle.width / 2.) >= 0 else -1
        wave_index = max(0,self.next_wave-1) if wave_index is None else wave_index
        missing=object();previous=getattr(battle,'_scripted_spawn_wave',missing)
        battle._scripted_spawn_wave=wave_index
        try:
            with battle._ban_free_spawn():
                unit = battle.spawn(key, "zombie", x, y, facing)
        finally:
            if previous is missing:del battle._scripted_spawn_wave
            else:battle._scripted_spawn_wave=previous
        if unit is None:
            return False
        native = battle._native_objects.get(unit["id"])
        self.wave_members.setdefault(wave_index,set()).add(unit['id'])
        if native is not None:native['_pvp_wave_index']=wave_index
        if native is not None and origin:native['_pvp_spawn_grave']=origin[0]
        scale = health_scale(self.day)
        if native is not None and scale > 1.:
            native["血量"] *= scale
            native["_pvp_max_hp"] = native["血量"]
        self.spawned.append(unit["id"])
        self.alive[unit["id"]] = (key, None)
        self.last_spawn_time = battle.time
        return True

    def _pay_bounties(self, battle):
        """Coins where our zombies fall (or turn charmed), as the original drops money."""
        for uid, (key, last) in list(self.alive.items()):
            obj = battle._native_objects.get(uid)
            if obj is not None and obj.get("血量", 0) > 0 and "魅惑" not in obj and "灰烬" not in obj:
                position = obj.get("位置")
                if position:
                    self.alive[uid] = (key, (position[0], position[1] - battle.tile))
                continue
            del self.alive[uid]
            if last is None:
                continue
            amount, kind = coin_drop(key, self.rng)
            battle.drop_coin(amount, last[0], last[1], kind)

    def remaining(self, battle):
        budget=getattr(battle,'scripted_spawn_budget',None)
        if budget is not None:return budget.count()
        return sum(1 for unit in battle.units.values()
                   if unit["side"] == "zombie" and unit["hp"] > 0 and unit.get("mobile", True))

    def cleared(self):
        battle = getattr(self, "_battle", None)
        return False if battle is None else self._cleared(battle)

    def _cleared(self, battle):
        budget=getattr(battle,'scripted_spawn_budget',None)
        return (self.next_wave >= len(self.plan) and not self.queue and not self.pending_ladders
                and not (budget is not None and budget.pending_count()) and self.remaining(battle) == 0)

    def snapshot(self):
        battle = getattr(self, "_battle", None)
        upcoming = self.plan[self.next_wave] if self.next_wave < len(self.plan) else None
        progress=self._wave_progress(battle,self.next_wave-1) if battle and self.next_wave else None
        return dict(day=self.day, wave=self.next_wave, waves=len(self.plan),
                    next_in=round(max(0., upcoming["time"] - battle.time), 1) if upcoming and battle and self.next_wave==0 else None,
                    next_flag=bool(upcoming and upcoming["flag"]),
                    remaining=self.remaining(battle) if battle else 0,
                    max_zombies=self.max_zombies,clear_required=WAVE_CLEAR_PERCENT,
                    clear_percent=progress['clear_percent'] if progress else 0,
                    wave_remaining=progress['remaining'] if progress else 0,
                    spawn_queued=len(self.queue),pending_summons=progress['pending'] if progress else 0,
                    waiting_for_clear=bool(upcoming and self.next_wave),
                    engine_load=round(getattr(battle, "native_cost_ratio", None) or 0., 2),
                    paced=self.paced)



# -------------------------------------------------------------- campaign
def reward_pool(unlocked, coop=False):
    owned = set(unlocked) | set(FREE_TOOLS)
    pool = []
    for key, card in sorted(CARDS.items()):
        if not campaign_card_allowed(key, coop):
            continue
        if card["side"] != "plant" or not card.get("selectable", True) or key in owned or key in NOT_REWARDS:
            continue
        if card.get("category") == "derived":
            continue
        dependency = card.get("dependency")
        if dependency and dependency not in owned:
            continue
        pool.append(key)
    return pool


def map_for_day(day, coop=False):
    """(source, name, night) of the map a day is played on."""
    night = day % 4 == 3
    from .team_maps import bundled_index
    index = bundled_index()
    if not index:
        raise ValueError('扩展地图资源缺失，请重新安装')
    entry = index[(day - 1) % len(index)]
    return "team", entry["id"], night


# Dave's shop (the original sells premium plants, secrets, a slot and starting sun
# from his car boot for coins). Prices are in coins.
SKIP_PRICE = 10000         # PvP73: coins to count a day as cleared without playing it
SLOT_PRICE = 150          # x (slots bought + 1)
SUN_PRICE = 100           # x (sun upgrades + 1), +25 starting sun each
SUN_STEP = 25
MAX_EXTRA_SLOTS = 3
MAX_SUN_UPGRADES = 6


def shop_price(base, day):
    """Co-op prices grow 10% of the base per day, rounded up to 5 coins."""
    return ((int(base)*(10+max(0,int(day)-1))+49)//50)*5


def plant_price(key):
    return int(round((75 + CARDS[key]["cost"] * 1.2) / 5.)) * 5


def clear_bonus(day, coop=False, fallen=0):
    bonus = 50 + 20 * day
    if coop and not fallen:
        bonus += 100      # teamwork: nobody fell all day
    return bonus // 2


class Campaign:
    VERSION = 4

    def __init__(self, seed=None, coop=False):
        self.coop = bool(coop)
        self.seed = int(seed if seed is not None else random.randrange(1, 2 ** 31))
        self.day = 1
        self.best_day = 0
        self.unlocked = _with_tools(STARTER_PLANTS)
        if self.coop:self.unlocked.append('secret:阳光')
        # The first map has solid ground: keep a usable starter deck after
        # tools became ordinary, slot-consuming cards. Players can remove it.
        self.deck = list(STARTER_PLANTS) + ["plant:花盆"]
        self.rewards = []
        self.history = []
        self.coins = 0
        # One half-coin carried between results. Existing integer savings keep
        # their full value; only newly earned money is reduced.
        self.coin_half = 0
        self.extra_slots = 0
        self.sun_upgrades = 0
        self.max_zombies = DEFAULT_MAX_ZOMBIES
        self.shop = []
        self.stock_shop()

    # persistence
    def to_dict(self):
        return dict(version=self.VERSION, coop=self.coop, seed=self.seed, day=self.day, best_day=self.best_day,
                    unlocked=list(self.unlocked), deck=list(self.deck), rewards=list(self.rewards),
                    history=list(self.history[-50:]), coins=self.coins, coin_half=self.coin_half, extra_slots=self.extra_slots,
                    sun_upgrades=self.sun_upgrades, max_zombies=self.max_zombies,shop=[dict(item) for item in self.shop])

    @classmethod
    def from_dict(cls, value):
        result = cls(value.get("seed", 1), coop=value.get('coop', False))
        day = value.get("day", 1)
        result.day = day if type(day) is int and day >= 1 else 1
        result.max_zombies = zombie_limit(value.get('max_zombies'))
        result.best_day = int(value.get("best_day", 0) or 0)
        result.unlocked = _with_tools([k for k in value.get("unlocked", ()) if k in CARDS and CARDS[k]["side"] == "plant"]
                                      or list(STARTER_PLANTS))
        if result.coop and 'secret:阳光' not in result.unlocked:result.unlocked.append('secret:阳光')
        result.deck = [k for k in value.get("deck", ()) if k in result.unlocked]
        result.rewards = [k for k in value.get("rewards", ()) if campaign_card_allowed(k, result.coop)]
        result.history = list(value.get("history", ()))[-50:]
        result.coins = max(0, int(value.get("coins", 0) or 0))
        result.coin_half = max(0, min(1, int(value.get("coin_half", 0) or 0)))
        result.extra_slots = max(0, min(MAX_EXTRA_SLOTS, int(value.get("extra_slots", 0) or 0)))
        result.sun_upgrades = max(0, min(MAX_SUN_UPGRADES, int(value.get("sun_upgrades", 0) or 0)))
        shop = value.get("shop")
        restored_shop = isinstance(shop, list) and all(isinstance(i, dict) and i.get("kind") in ("plant", "secret", "slot", "sun") for i in shop)
        if restored_shop:
            result.shop = [dict(kind=i["kind"], key=i.get("key"), price=int(i.get("price", 0)), sold=bool(i.get("sold")))
                           for i in shop if i["kind"] in ("slot", "sun") or campaign_card_allowed(i.get("key"), result.coop)]
        else:
            result.stock_shop()
        saved_version=value.get('version',0)
        legacy_version=type(saved_version) is not int or saved_version<4
        if result.coop and legacy_version and restored_shop:
            for item in result.shop:item['price']=shop_price(item['price'],result.day)
        result.fit_deck()
        return result

    @classmethod
    def load(cls, path):
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + ".pending")
        pending.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        pending.replace(path)

    # deck
    def slots(self):
        return slots_for_day(self.day) + self.extra_slots

    def available_unlocked(self):
        return [k for k in self.unlocked if campaign_card_allowed(k, self.coop)]

    def restrict_coop(self):
        """Preserve ownership while retiring unavailable active choices."""
        if not self.coop:
            for item in self.shop:item['price']=shop_price(item['price'],self.day)
        self.coop = True
        if 'secret:阳光' not in self.unlocked:self.unlocked.append('secret:阳光')
        self.deck = [k for k in self.deck if campaign_card_allowed(k, True)]
        self.rewards = [k for k in self.rewards if campaign_card_allowed(k, True)]
        self.shop = [i for i in self.shop if i['kind'] in ('slot', 'sun')
                     or campaign_card_allowed(i.get('key'), True)]

    # shop
    def stock_shop(self):
        """Three plants, two secrets, a card slot and starting sun - the original's boot."""
        rng = random.Random(self.seed * 7 + self.day * 101)
        pool = reward_pool(self.unlocked, self.coop)
        plants = [k for k in pool if CARDS[k]["category"] != "secret"]
        secrets = [k for k in pool if CARDS[k]["category"] == "secret"]
        items = [dict(kind="plant", key=k, price=plant_price(k), sold=False)
                 for k in rng.sample(plants, min(3, len(plants)))]
        items += [dict(kind="secret", key=k, price=250 + rng.randrange(0, 21) * 5, sold=False)
                  for k in rng.sample(secrets, min(2, len(secrets)))]
        if self.extra_slots < MAX_EXTRA_SLOTS:
            items.append(dict(kind="slot", key=None, price=SLOT_PRICE * (self.extra_slots + 1), sold=False))
        if self.sun_upgrades < MAX_SUN_UPGRADES:
            items.append(dict(kind="sun", key=None, price=SUN_PRICE * (self.sun_upgrades + 1), sold=False))
        self.shop = items
        if self.coop:
            for item in items:
                item['price'] = shop_price(item['price'], self.day)
        return items

    def buy(self, index):
        if not isinstance(index, int) or not 0 <= index < len(self.shop):
            return "商品不存在"
        item = self.shop[index]
        if item['kind'] in ('plant', 'secret') and not campaign_card_allowed(item.get('key'), self.coop):
            return disabled_message(self.coop)
        if item["sold"]:
            return "已售"
        if self.coins < item["price"]:
            return "金币不足（还差 %d）" % (item["price"] - self.coins)
        if item["kind"] in ("plant", "secret"):
            if item["key"] in self.unlocked:
                return "已拥有这张卡"
            self.unlocked.append(item["key"])
        elif item["kind"] == "slot":
            self.extra_slots += 1
        else:
            self.sun_upgrades += 1
        self.coins -= item["price"]
        item["sold"] = True
        self.fit_deck()          # a new card or slot joins the deck while there is room
        return ""

    def start_sun(self):
        return 150 + SUN_STEP * self.sun_upgrades

    def fit_deck(self):
        deck = [k for k in self.deck if k in self.available_unlocked()]
        for key in self.available_unlocked():
            if len(deck) >= self.slots():
                break
            # Tools are a choice, not filler: only real plants are auto-added.
            if key not in deck and not CARDS[key].get("dependency") and key not in FREE_TOOLS:
                deck.append(key)
        self.deck = deck[:self.slots()]
        # A secret needs its precursor carried too.
        self.deck = [k for k in self.deck if not CARDS[k].get("dependency") or CARDS[k]["dependency"] in self.deck]

    def toggle(self, key, limit=None, day=None):
        """Put a card in or out of today's deck (one slot each).

        ``limit``/``day`` let a co-op guest fill the day the host chose while
        spending its own campaign's slots.
        """
        if not campaign_card_allowed(key, self.coop):
            return disabled_message(self.coop) if isinstance(key, str) and key in CARDS else '尚未解锁这张卡'
        if key not in self.unlocked:
            return "尚未解锁这张卡"
        capacity = self.slots() if limit is None else max(0, int(limit))
        shown_day = self.day if day is None else int(day)
        if key in self.deck:
            if any(CARDS[k].get("dependency") == key for k in self.deck):
                return "请先移除依赖它的秘籍"
            self.deck.remove(key)
            return ""
        if len(self.deck) >= capacity:
            return "卡槽已满（第 %d 天可带 %d 张）" % (shown_day, capacity)
        dependency = CARDS[key].get("dependency")
        if dependency and dependency not in self.deck:
            return "需要同时携带前体：" + CARDS[dependency]["name"]
        self.deck.append(key)
        return ""

    def battle_deck(self):
        return [k for k in self.deck if campaign_card_allowed(k, self.coop)]

    # progress
    def offer_rewards(self):
        pool = reward_pool(self.unlocked, self.coop)
        rng = random.Random(self.seed * 31 + self.day)
        self.rewards = rng.sample(pool, min(3, len(pool))) if pool else []
        return self.rewards

    def win(self, coins=0, coop=False, fallen=0, played_day=None):
        # The host's day determines the challenge and payout. A guest keeps
        # its own reward/unlock progression, which may be on an earlier day.
        bonus_day = self.day if played_day is None else max(1, int(played_day))
        bonus = clear_bonus(bonus_day, coop, fallen)
        earned = self._credit_pickups(coins)
        self.coins += bonus
        self.history.append(dict(day=self.day, played_day=bonus_day, result="win", coins=earned, raw_coins=int(coins),
                                 bonus=bonus, coin_half=self.coin_half))
        self.best_day = max(self.best_day, self.day)
        self.offer_rewards()
        return bonus

    def skip_day(self, pay=True):
        """PvP73: pay SKIP_PRICE coins to count today as cleared. No pickups and
        no clear bonus, but the usual reward pick (taking it advances the day
        and restocks the shop, exactly like a won day)."""
        if self.rewards:
            return "请先领取通关奖励"
        if pay:
            if self.coins < SKIP_PRICE:
                return "金币不足：跳关需要 $%d（还差 %d）" % (SKIP_PRICE, SKIP_PRICE - self.coins)
            self.coins -= SKIP_PRICE
        self.history.append(dict(day=self.day, played_day=self.day, result="win", coins=0, raw_coins=0,
                                 bonus=0, coin_half=self.coin_half, skipped=True))
        self.best_day = max(self.best_day, self.day)
        self.offer_rewards()
        return ""

    def lose(self, coins=0):
        # Coins picked up before the defeat are kept, as the original keeps money.
        earned = self._credit_pickups(coins)
        self.history.append(dict(day=self.day, result="lose", coins=earned, raw_coins=int(coins),
                                 coin_half=self.coin_half))

    def _credit_pickups(self, raw_coins):
        """Half the original integer pickup value without losing odd halves."""
        earned, self.coin_half = divmod(max(0, int(raw_coins)) + self.coin_half, 2)
        self.coins += earned
        return earned

    def choose_reward(self, key):
        if key is not None and not campaign_card_allowed(key, self.coop):
            return disabled_message(self.coop) if isinstance(key, str) and key in CARDS else '奖励卡无效'
        # Reward buttons can deliver two clicks before the next render. Once
        # this cleared day advances, a stale "skip" must not advance it again.
        # A fully unlocked collection may legitimately have no offered cards;
        # the recorded win still authorizes exactly one skip for that day.
        won_today = bool(self.history and self.history[-1].get("result") == "win"
                         and self.history[-1].get("day") == self.day)
        if not self.rewards and not won_today:
            return "当前没有待领取的通关奖励"
        if key is not None and key not in self.rewards:
            return "请选择奖励卡牌"
        if key is not None:
            self.unlocked.append(key)
        self.rewards = []
        self.day += 1
        self.stock_shop()
        if key is not None and len(self.deck) < self.slots():
            dependency = CARDS[key].get("dependency")
            if not dependency or dependency in self.deck:
                self.deck.append(key)
        self.fit_deck()
        return ""



def pve_rules(base_rules, deck, start_sun=150, slots=None):
    """PvE day rules.  ``slots`` lets co-op use the widest seat deck, because
    each Dave brings their own cards."""
    rules = dict(base_rules)
    rules.update(deathmatch_seconds=10. ** 9, plant_start=int(start_sun), night_plant_start=int(start_sun) + 50,
                 plant_slots=max(1, int(slots if slots is not None else len(deck))), ranked=False)
    return rules


def describe_day(day, coop=False):
    tiers = [TIER_NAMES[t] for t, unlock in sorted((COOP_TIER_UNLOCK_DAY if coop else TIER_UNLOCK_DAY).items()) if day >= unlock]
    source, name, night = map_for_day(day, coop)
    if source == "team":
        from .team_maps import bundled_index
        name = next((e["name"] for e in bundled_index() if e["id"] == name), name)
    return "第 %d 天 · %s%s · %d 波 · 僵尸：%s" % (day, name, "（夜）" if night else "", waves_for_day(day), "、".join(tiers))
