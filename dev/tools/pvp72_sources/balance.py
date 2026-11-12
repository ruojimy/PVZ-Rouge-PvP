"""Match-only card balance; never changes original single-player tables."""

FAST_PLANT_COOLDOWN_FACTOR = .75
MINE_EMERGENCE_SECONDS = 16.
SPIKE_SECRET_STEP = 10
SPIKE_SECRET_MIN_COST = 15
GOLD_MAGNET_BUCKET_HP = 250
HARDENING_MIN_BASE_HP = 6
HARDENING_HP_FACTOR = 1.25
DOOM_ZOMBIE_AUTO_EXPLODE_TICKS = 9000.

PLANT_COOLDOWNS = {}
for seconds, names in (
    (36, "窝瓜 魅惑菇"), (40, "坚果 仙人掌"), (60, "高坚果 南瓜头 樱桃炸弹 毁灭菇"), (80, "火爆辣椒"),
    (8, "豌豆射手 小喷菇 胆小菇 大喷菇 海蘑菇 卷心菜投手 玉米投手 缠绕海草 地刺 阳光菇"),
    (20, "石块"), (24, "墓碑吞噬者"), (16, "双发射手 土豆地雷 吸金磁"),
    (32, "冰瓜投手 三叶草 萝卜伞"), (40, "路灯花"), (24, "杨桃 裂荚射手"),
    (6, "花盆 睡莲"), (90,"玉米加农炮"), (16,"大嘴花 龙蒺藜"),
):
    PLANT_COOLDOWNS.update({"plant:"+name: float(seconds) for name in names.split()})

# PvP prices that differ from the original card's own price.  Everything not
# listed here keeps the native cost the original creation function charges.
COSTS = {"plant:路灯花": 75, "plant:萝卜伞": 75, "plant:大喷菇": 75,
         "plant:石块": 0, "plant:阳光菇": 0,
         "plant:花盆": 0, "plant:睡莲": 0}
for cost, names in (
    (125, "钢门普通僵尸 三叶草僵尸"),
    (175, "梯子僵尸"),
    (150, "坚果僵尸 萝卜伞僵尸"),
    (200, "铁桶钢门僵尸 路灯花僵尸"),
    (250, "橄榄球僵尸 大喷菇僵尸 辣椒僵尸"),
    (275, "机枪僵尸 投篮车僵尸"),
    (300, "报纸僵尸"),
    (400, "墓碑吞噬者僵尸"),
    (200, "气球僵尸"), (225, "矿工僵尸"),
    (350, "雪橇车僵尸 吸金磁僵尸"),
    (500, "巨人僵尸"), (450, "高坚果僵尸"),
    (50, "潜水僵尸 路障僵尸 鸭子路障僵尸"), (75, "豌豆僵尸 伴舞僵尸 撑杆跳僵尸"), (100, "倭瓜僵尸"),
    (175, "蹦蹦僵尸"),
    (25, "普通僵尸 鸭子普通僵尸"), (100, "铁桶僵尸"),
    (100, "鸭子铁桶僵尸"), (40, "小鬼僵尸"),
    (150, "飞贼僵尸"), (175, "旗帜僵尸"),
    (75, "双生脑光墓碑"),
):
    COSTS.update({"zombie:"+name: cost for name in names.split()})

for cost, names in (
    (25,"胆小菇 咖啡豆"),(50,"窝瓜"),(90,"墓碑吞噬者"),(60,"豌豆射手"),
    (75,"南瓜头 地刺 磁力菇"),(90,"寒冰射手"),
    (100,"双发射手 大蒜"), (125,"裂荚射手 玉米投手"),
    (150,"原始豌豆射手 卷心菜投手 樱桃炸弹 毁灭菇 地刺王 火炬树桩 吸金磁"),
    (175,"三向射手 火爆辣椒 仙人掌"),
    (175,"机枪射手 忧郁蘑菇"), (275,"西瓜投手"),
    (350,"冰瓜投手"),(375,"杨桃"),(300,"玉米加农炮"),
):
    COSTS.update({"plant:"+name: cost for name in names.split()})

COSTS.update({"zombie:雪橇车小队":90, "zombie:成长脑光墓碑":60,
              "zombie:水上成长脑光墓碑":60, "zombie:海豚僵尸":60})

# PvP63 deployment/almanac overrides. Secret replacement prices are separate.
COSTS.update({"plant:"+name: cost for name, cost in (
    ("萝卜伞",60), ("路灯花",40), ("三叶草",0), ("大嘴花",90),
    ("金盏花",100), ("磁力菇",25), ("吸金磁",100), ("玉米加农炮",250))})
COSTS.update({"zombie:"+name: cost for name, cost in (
    ("撑杆跳僵尸",60), ("铁桶钢门僵尸",175), ("黑铁桶僵尸",175),
    ("橄榄球僵尸",200), ("报纸僵尸",275), ("墓碑吞噬者僵尸",350),
    ("黑橄榄僵尸",400), ("飞贼僵尸",75), ("蹦蹦僵尸",125),
    ("气球僵尸",150), ("矿工僵尸",150), ("高坚果僵尸",350),
    ("巨人僵尸",400), ("角斗士巨人",600))})

ZOMBIE_COOLDOWNS = {}
for seconds, names in (
    (6,"普通僵尸 小鬼僵尸 鸭子普通僵尸"),(8,"潜水僵尸 伴舞僵尸"),
    (12,"路障僵尸 豌豆僵尸 脑光墓碑 成长脑光墓碑 鸭子路障僵尸 三叶草僵尸"),
    (16,"铁桶僵尸 撑杆跳僵尸 海豚僵尸 鸭子铁桶僵尸"),
    (20,"倭瓜僵尸 钢门普通僵尸 机枪僵尸 坚果僵尸 萝卜伞僵尸 双生脑光墓碑"),
    (24,"梯子僵尸 墓碑吞噬者僵尸"),
    (32,"铁桶钢门僵尸 小丑僵尸 飞贼僵尸 坚固脑光墓碑 雪橇车小队"),
    (36,"橄榄球僵尸 大喷菇僵尸"),(40,"路灯花僵尸 吸金磁僵尸"),
    (48,"报纸僵尸 蹦蹦僵尸 投篮车僵尸 毁灭菇僵尸"),
    (60,"气球僵尸 矿工僵尸 旗帜僵尸 雪橇车僵尸 辣椒僵尸 高坚果僵尸"),(80,"巨人僵尸"),
):
    ZOMBIE_COOLDOWNS.update({"zombie:"+name:float(seconds) for name in names.split()})
ZOMBIE_COOLDOWNS["zombie:铁桶钢门僵尸"] = 24.
ZOMBIE_COOLDOWNS.update({"zombie:蹦蹦僵尸":32.,"zombie:巨人僵尸":60.,"zombie:角斗士巨人":80.})
COSTS.update({"plant:甜薯":90,"zombie:蹦蹦僵尸":90})
COSTS.update({"plant:大嘴花":100, "plant:回旋镖射手":75,
              "plant:大喷菇":50, "zombie:小丑僵尸":100})
COSTS.update({"zombie:"+name: cost for name, cost in (
    ("黑撑杆僵尸",175), ("报纸僵尸",250), ("墓碑吞噬者僵尸",300),
    ("巨人僵尸",300), ("角斗士巨人",450), ("红眼巨人",500),
    ("高坚果僵尸",325), ("路灯花僵尸",175), ("吸金磁僵尸",325),
    ("黑橄榄僵尸",350), ("滚桶僵尸",200), ("海盗船长",225),
    ("舞王僵尸",225), ("大喷菇僵尸",200), ("气球僵尸",100),
    ("矿工僵尸",125))})

GRAVE_BALANCE = {
    "zombie:脑光墓碑":dict(hp=75,period=16.),
    "zombie:双生脑光墓碑":dict(hp=30,period=16.),
    "zombie:成长脑光墓碑":dict(hp=75,period=16.,mature_hp=150),
    "zombie:坚固脑光墓碑":dict(hp=900,period=12.),
}

# PvP health, in the native object's own unit.  The engine's template health is
# captured verbatim in `NATIVE_CARD_EVIDENCE` and a parity test re-executes the
# engine's creation functions against it, so the evidence table must keep the
# original numbers.  A PvP health change therefore lives here and is applied to
# the deployed native object (and to the hardening formula) instead.
HEALTH = {"plant:路灯花":18., "plant:萝卜伞":18., "plant:睡莲":18., "plant:大蒜":36., "plant:高坚果":180.,
          "plant:龙蒺藜":18., "plant:石果子":180.,
          "plant:仙人掌":54., "plant:南瓜头":108.}

# PvP72 decisions, applied before catalog construction; native evidence remains 71.
COSTS.update({'plant:萝卜伞':100, 'plant:寒冰辣椒':150,
              'plant:双子向日葵':90, 'zombie:橄榄球僵尸':175,
              'zombie:毁灭菇僵尸':250, 'zombie:辣椒僵尸':175,
              'zombie:墓碑吞噬者僵尸':225})
HEALTH.update({'plant:原始土豆地雷':18., 'plant:萝卜伞':36.,
               'zombie:墓碑吞噬者僵尸':300.})
ZOMBIE_COOLDOWNS.update({'zombie:毁灭菇僵尸':60., 'zombie:辣椒僵尸':48.})

# PvP73 decisions. 石块 costs -25: planting one pays 25 sun. 草坪 is installed by a
# later content module, so its cooldown is applied by catalog.py (PVP73_PLANT_COOLDOWNS).
COSTS.update({'plant:草坪':25, 'plant:石块':-25,
              'zombie:小鬼炮':275, 'zombie:报纸僵尸':275,
              'zombie:滚桶僵尸':225, 'zombie:海盗船长':250})
ZOMBIE_COOLDOWNS.update({'zombie:石化火炬':48.})
PVP73_PLANT_COOLDOWNS = {'plant:草坪':16.}

# The magnet family re-arms on the engine's own constant (magnet 13000 ticks,
# gold magnet 9000).  PvP caps that re-arm to a shorter clock; the cap is only
# applied when the engine has just armed it, so the golden-flower aura keeps
# being able to run the clock down faster.
ABSORB_TICKS = {"磁力菇":9000, "吸金磁":6000}
ENGINE_ABSORB_TICKS = {"磁力菇":13000, "吸金磁":9000}


def sky_interval(rules, cols, rows):
    """Seconds between sky suns on a cols x rows map.

    72x24 (every built-in map) keeps rules['sky_interval'] (8 s per 25 sun).
    The drop rate grows linearly with the map's linear size,
    sqrt(area / 72x24), up to twice the rate on 144x48 (4 s); smaller
    canvases keep the base interval.
    """
    reference = float(rules['sky_reference_cols'] * rules['sky_reference_rows'])
    size = (max(1., float(cols) * float(rows)) / reference) ** .5
    return rules['sky_interval'] / min(float(rules['sky_max_scale']), max(1., size))


def rest_factor(plant, native_tick, rules):
    """Production speed of a producer that has not been attacked.

    Any drop of the plant's own HP restarts the quiet clock (healing does
    not). After producer_rest_seconds of quiet the speed rises linearly over
    producer_rest_ramp_seconds to 1 + producer_rest_bonus.
    """
    hp = plant.get('植物血', 0)
    last = plant.get('_pvp_rest_hp')
    if last is None or hp < last:
        plant['_pvp_rest_since'] = native_tick
    plant['_pvp_rest_hp'] = hp
    quiet = (native_tick - plant['_pvp_rest_since']) / 250.
    ramp = (quiet - rules['producer_rest_seconds']) / max(1e-9, rules['producer_rest_ramp_seconds'])
    return 1. + rules['producer_rest_bonus'] * min(1., max(0., ramp))


def initial_cooldown(seconds):
    return 0. if seconds <= 12 else seconds / 2. if seconds <= 48 else seconds


def deathmatch_factor(seconds):
    return .5 if seconds <= 12 else 2./3. if seconds <= 48 else .75


def deployment_cooldown(card, deathmatch=False):
    seconds = card["cooldown"]
    return seconds * deathmatch_factor(seconds) if deathmatch else seconds


def cooldown_mask_scale(seconds, remaining, time, deathmatch=False):
    """Full height of a card slot's cooldown mask, in the same units as `remaining`.

    The slot draws `remaining / scale` of the card as shade, so `scale` has to be
    the length of the cooldown actually in progress.  Scaling by the card's own
    cooldown is right after a deployment, but the opening cooldown is only
    `initial_cooldown(seconds)`: every 12s < cooldown <= 48s card therefore began
    the match with the mask at 50%, which reads as "already half cooled down"
    when the card has never been played.  A card whose remaining time still
    equals its opening cooldown has provably never been deployed (a deployment
    arms either `seconds` or, for cooldowns above the floor, a value that can
    coincide with it only when the two scales are already equal), so that is the
    duration to draw against.
    """
    opening = initial_cooldown(seconds)
    if remaining > 0. and abs(remaining - max(0., opening - time)) < 1e-3:
        return max(.01, opening)
    return max(.01, seconds * deathmatch_factor(seconds) if deathmatch else seconds)


# PvP65: a zombie deck carrying the sturdy grave gives zombie Dave 8 more HP
# and starts the native balloon escape at 12 HP instead of the native 10.
STURDY_GRAVE = "zombie:坚固脑光墓碑"
STURDY_GRAVE_HERO_HP = 8.
STURDY_GRAVE_BALLOON_HP = 12
NATIVE_BALLOON_HP = 10


def hero_hp(rules, side, deck):
    bonus = STURDY_GRAVE_HERO_HP if side == "zombie" and STURDY_GRAVE in deck else 0.
    if side == "zombie" and "zsecret:石更！" in deck:
        bonus += 20.     # PvP66 zombie secret 石更！, stacks with the sturdy grave
    return float(rules["hero_hp"]) + bonus


def balloon_hp(side, deck):
    return STURDY_GRAVE_BALLOON_HP if side == "zombie" and STURDY_GRAVE in deck else NATIVE_BALLOON_HP


# Producers still deployable in deathmatch (PvP65).
DEATHMATCH_ALLOWED_PRODUCERS = frozenset(("zombie:坚固脑光墓碑", "zombie:石化火炬"))


def deathmatch_blocked(card):
    """True when deathmatch forbids deploying this card (new producers)."""
    return bool(card.get("producer")) and card.get("base_id", card.get("id")) not in DEATHMATCH_ALLOWED_PRODUCERS
