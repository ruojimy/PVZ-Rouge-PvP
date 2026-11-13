"""PvP66 zombie secrets (僵尸秘籍 v4): catalogue entries and static values.

IDs use their own ``zsecret:`` prefix so a zombie secret never collides with
a plant secret of the same name (both sides have a 豌豆).  They are ordinary
``category="secret"`` cards on the zombie side: one slot each, kept at the end
of the bank, never spawned.  They do not enter the original engine's 秘籍 list;
their effects run in ``zombie_secrets.ZombieSecrets``.

``dependency`` is used only for the seven secrets the rules lock to a precursor
(the draft then keeps that card in the deck and protects it from bans).  Every
other secret merely names the units it affects in ``targets``.
"""
from copy import deepcopy

PREFIX = "zsecret:"

# name: (description, locked precursor, affected cards, art)
ZOMBIE_SECRETS = {
    "专注啃咬": ("所有僵尸 5 秒未受到伤害时，啃咬速度增加 100%，并获得 25% 免伤（与其他减伤相乘）；受到伤害后立即解除。", None, (), "普通僵尸"),
    "大运！小子": ("雪橇车僵尸与滚桶僵尸移速增加 100%，两者脑光消耗各 +50。", None,
                ("zombie:雪橇车僵尸", "zombie:滚桶僵尸"), "雪橇车僵尸"),
    "阿姆斯特朗": ("报纸僵尸的报纸掉落后，狂暴的它获得 50% 减伤。锁定前体：报纸僵尸。", "zombie:报纸僵尸",
               ("zombie:报纸僵尸",), "报纸僵尸"),
    "立棍！小子": ("撑杆跳僵尸与黑撑杆僵尸起跳后用杆子砸击前方两格，对植物与戴夫造成4伤害，对敌对僵尸造成40伤害。", None,
               ("zombie:撑杆跳僵尸", "zombie:黑撑杆僵尸"), "撑杆跳僵尸"),
    "散弹攻击": ("机枪僵尸生命翻倍，脑光消耗降为 200，每次射击改为 6 枚豌豆，以朝向为中线 ±30° 散射。锁定前体：机枪僵尸。", "zombie:机枪僵尸",
             ("zombie:机枪僵尸",), "机枪僵尸"),
    "坤坤": ("投篮车僵尸投篮速度翻倍；濒死时若篮球未投完则锁血至投完。脑光消耗 350。锁定前体：投篮车僵尸。",
           "zombie:投篮车僵尸", ("zombie:投篮车僵尸",), "投篮车僵尸"),
    "脑光": ("僵尸击杀植物时自动收集 15 脑光。", None, (), "脑子"),
    "二手": ("防具被打爆后留下破损版（一半防具生命）。钢门、垃圾桶、梯子、传送带可由所有具备空闲二类防具槽的己方僵尸拾取；拾取梯子/传送带后可铺设对应设施，沿用原生穿透交互（僵王出品可阻挡穿透）。黑路障/黑铁桶保留颜色及破碎效果，其他本体保留原形；巨人头槽优先，背上小鬼可用独立空槽拾取，抛出后继承防具和二手状态。二手防具再碎不再掉落。", None, (), "路障"),
    "玉米卷": ("僵尸戴夫每20秒向全图最近的未投喂己方僵尸投掷玉米卷，使其永久移速+75%；每单位只投喂一次，与其他秘籍移速加成加算。", None, (), "玉米投手"),
    "植物僵尸": ("僵尸击杀植物时，若该植物有对应的植物僵尸，则在原地生成该僵尸，生命值折半。", None, (), "豌豆僵尸"),
    "僵王出品": ("所有一类、二类防具生命 +25%；二类防具挡住穿透攻击（先扣防具血量），中毒持续伤害仍直接扣本体生命。", None, (), "铁桶"),
    "生生不息": ("僵尸戴夫每 12 秒治疗半径 8 格内己方僵尸 40 生命（不含墓碑），同时治疗自身 4 生命（不超过上限）。", None, (), "路灯花僵尸"),
    "补贴": ("场上没有僵尸时，周期脑光补给的间隔减半。", None, (), "脑子"),
    "狂野舞步": ("舞王僵尸生成的伴舞成为独立的伴舞僵尸，不再固定队形。舞王脑光消耗 300。锁定前体：舞王僵尸。",
             "zombie:舞王僵尸", ("zombie:舞王僵尸",), "舞王僵尸"),
    "三五成群": ("普通/鸭子普通/黑普通僵尸脑光消耗 -25；半径 6 格内每有一只同类，获得 15% 减伤（上限 75%）；旗帜召唤的不参与。", None,
             ("zombie:普通僵尸", "zombie:鸭子普通僵尸", "zombie:黑普通僵尸"), "普通僵尸"),
    "不可撼动": ("巨人僵尸、红眼巨人、角斗士巨人受到的冰冻、黄油、眩晕时长减半。", None,
             ("zombie:巨人僵尸", "zombie:红眼巨人", "zombie:角斗士巨人"), "巨人僵尸"),
    "体育生": ("撑杆跳、橄榄球、黑撑杆、黑橄榄僵尸生命与移速 +25%；黑橄榄冲刺冷却减半。", None,
            ("zombie:撑杆跳僵尸", "zombie:橄榄球僵尸", "zombie:黑撑杆僵尸", "zombie:黑橄榄僵尸"), "橄榄球僵尸"),
    "斩首行动": ("雪人僵尸生命翻倍，只追踪植物戴夫、无视植物。锁定前体：雪人僵尸。", "zombie:雪人僵尸",
             ("zombie:雪人僵尸",), "雪人僵尸"),
    "加急": ("所有僵尸卡牌部署冷却减少 25%（墓碑除外）。", None, (), "旗帜僵尸"),
    "石更！": ("僵尸戴夫生命+20（可与坚固脑光墓碑叠加），倒地期间获得25%免伤。", None, (), "坚果僵尸"),
    "一大波僵尸": ("旗帜僵尸从每个墓碑拉出一只路障僵尸。旗帜僵尸脑光消耗 250。锁定前体：旗帜僵尸。", "zombie:旗帜僵尸",
              ("zombie:旗帜僵尸",), "旗帜僵尸"),
    "威压": ("僵尸戴夫解锁三段跳，第三跳纵向强化25%；与豌豆秘籍同时携带时保留二段跳、不启用三段跳。半径 6 格内的植物，攻击、生产等所有间隔延长 30%。", None, (), "稻草人"),
    "海陆空": ("同时携带陆地、水系与空中（鹦鹉、乌鸦、气球、飞贼）僵尸时生效：水系和空中僵尸生命+50%、移速+25%。"
              "滚桶僵尸、钩索僵尸、海盗船长与小鬼炮算作水系，但仍可在无水地图和普通墓碑出兵。", None, (), "海盗鹦鹉"),
    "最后攻势": ("僵尸戴夫阵亡时改为锁 1 血立即起身，40 秒内不会再被击倒，到时自动阵亡；期间己方进入死斗状态。", None, (), "黑旗帜僵尸"),
    "汇流": ("召集旗半径 6 格内的僵尸死亡时返还 15 脑光（自动收集）；范围内的僵尸戴夫移速 +25%。", None, (), "黑旗帜僵尸"),
    "头兵": ("每个墓碑第一次产出的单位生命 +50%（每个墓碑各一次）。", None, (), "路障僵尸"),
    "自爆": ("点击一只己方僵尸使其自爆，对半径2.4格内敌方造成伤害：对植物与戴夫为自爆时每25点当前生命转1点伤害（向上取整），对敌对僵尸为该伤害的10倍。", None, (), "小丑僵尸"),
    "解除封印": ("放置僵尸不再受距离限制；可用方向键切换选择的墓碑（仍可用鼠标点选，小地图标出）；被选择的墓碑获得 75% 免伤（与开局生产单位免伤为同一效果，不叠加）。", None, (), "飞贼僵尸"),
    "豌豆": ("僵尸戴夫头顶豌豆僵尸的脑袋，自动向前方射击豌豆；失去二段跳。", None, (), "豌豆僵尸"),
    "起床！": ("传送后半径 2.4 格内的墓碑永久不再休眠，并治疗自身 4 生命（可突破生命上限）。", None, (), "矿工僵尸"),
    "狂暴": ("进入死斗后所有僵尸获得 25% 减伤与 100% 攻速（新释放的僵尸同样享受）。", None, (), "黑橄榄僵尸"),
    "远离诱惑": ("被魅惑的僵尸受到减速；甜薯对僵尸的吸引半径减半。", None, (), "魅惑菇"),
    "沉默": ("黑路障与黑铁桶掉落时的作用范围翻倍。", None, (), "黑铁桶僵尸"),
    "遗骸": ("墓碑被破坏时进入 3 秒无敌（死斗时 36 秒），期间保留所有互动。", None, (), "墓碑吞噬者僵尸"),
    "鸦群": ("释放乌鸦时，每个存活的稻草人都召唤一只乌鸦；每个稻草人使乌鸦脑光消耗 +50。", None, (), "乌鸦"),
    "暴怒": ("石化火炬变为蓝火态，生效范围翻倍，休眠时长减半；普通、僵尸、三向和原始豌豆点燃为蓝火，寒冰豌豆先解冻，需另一根树桩继续点燃。每次有效转换仍产15脑光，满150后休眠。锁定前体：石化火炬。", "zombie:石化火炬",
           ("zombie:石化火炬",), "石化火炬-蓝火"),
}

# Implemented in zombie_secrets.ZombieSecrets (all 36). A secret left out of
# this set stays out of the pool (not selectable).
IMPLEMENTED = {"加急", "石更！", "大运！小子", "体育生", "海陆空", "头兵", "补贴", "脑光", "汇流",
               "生生不息", "玉米卷", "起床！", "沉默", "鸦群", "一大波僵尸", "三五成群", "不可撼动",
               "远离诱惑", "阿姆斯特朗", "专注啃咬", "狂暴", "坤坤", "遗骸", "最后攻势", "威压",
               "立棍！小子", "植物僵尸", "僵王出品", "斩首行动", "散弹攻击", "狂野舞步", "自爆",
               "解除封印", "豌豆", "二手", "暴怒"}

# Static card values (actual_card applies these; the engine charges them).
COST_SET = {"散弹攻击": {"zombie:机枪僵尸": 200}, "坤坤": {"zombie:投篮车僵尸": 350}, "狂野舞步": {"zombie:舞王僵尸": 300},
            "一大波僵尸": {"zombie:旗帜僵尸": 250},
            "船锚": {"zombie:钩索僵尸": 125}, "黏糊糊": {"zombie:史莱姆僵尸": 400}}
COST_ADD = {"大运！小子": {"zombie:雪橇车僵尸": 50, "zombie:滚桶僵尸": 50},
            "三五成群": {"zombie:普通僵尸": -25, "zombie:鸭子普通僵尸": -25, "zombie:黑普通僵尸": -25}}
HP_FACTOR = {"体育生": (1.25, ("zombie:撑杆跳僵尸", "zombie:橄榄球僵尸", "zombie:黑撑杆僵尸", "zombie:黑橄榄僵尸")),
             "斩首行动": (2., ("zombie:雪人僵尸",)),"散弹攻击":(2.,("zombie:机枪僵尸",))}
RUSH_COOLDOWN = .75          # 加急
STONE_HERO_HP = 20.          # 石更！
SUBSIDY_START_BRAINS = 0     # PvP73.1: no opening bonus; recurring subsidy is unchanged
RAGE_TORCH_RANGE = 2.       # 暴怒: petrified torch reach x2
RAGE_TORCH_SLEEP = .5       # 暴怒: its sleep x0.5
RAGE_TORCH_ART = "石化火炬-蓝火"   # 暴怒 icon, and the torch card while 暴怒 is carried


def key(name):
    return PREFIX + name


def is_zombie_secret(card_id):
    return isinstance(card_id, str) and card_id.startswith(PREFIX)


def names(secrets):
    """Zombie secret names among card IDs."""
    return {k[len(PREFIX):] for k in secrets if is_zombie_secret(k)}


def install(cards):
    """Add the 36 entries to the card table (called from catalog.py)."""
    template = cards["secret:补光"]
    from .pvp66_icons import ART
    for name, (text, lock, targets, art) in ZOMBIE_SECRETS.items():
        value = deepcopy(template)
        ident = key(name)
        value.update(id=ident, base_id=ident, resolved_id=ident, family=ident, name=name, side="zombie",
                     category="secret", behavior="secret", asset=ART.get(name, art),
                     dependency=lock or "", effect="zombie_secret", economy="none", targets=list(targets),
                     native_secret_name=None, native_name=name, native_input_name=name,
                     description=text, native_description=text, native_shop_cost=None,
                     native_source="PvP66 zombie secret; not a spawned entity",
                     selectable=name in IMPLEMENTED, pvp_added=True, pvp_regular_unit=True, cost=0, cooldown=0)
        cards[ident] = value


def apply_card(c, base_id, secrets):
    """Static zombie-card values under the holder's zombie secrets."""
    active = names(secrets)
    if not active or c.get("side") != "zombie" or c.get("category") == "secret":
        return c
    for name, table in COST_SET.items():
        if name in active and base_id in table:
            c["cost"] = table[base_id]
    for name, table in COST_ADD.items():
        if name in active and base_id in table:
            c["cost"] = max(0, c["cost"] + table[base_id])
    for name, (factor, targets) in HP_FACTOR.items():
        if name in active and base_id in targets and c.get("hp") is not None:
            c["hp"] = c["hp"] * factor
    if "加急" in active and c.get("behavior") != "grave" and c.get("cooldown"):
        c["cooldown"] = c["cooldown"] * RUSH_COOLDOWN
    if "暴怒" in active and base_id == "zombie:石化火炬":
        c["asset"] = RAGE_TORCH_ART    # the card shows the blue flame it will burn with
    if "黏糊糊" in active and base_id in ("zombie:史莱姆僵尸", "zombie:中型史莱姆", "zombie:小型史莱姆"):
        c["slime_sticky"] = True
    if "萝卜伞" in active and base_id == "zombie:萝卜伞僵尸":
        c['hp'] *= 2
        c['umbrella_secret'] = True
    if '手雷' in active and base_id=='zombie:掷弹兵僵尸':
        c['cooldown']*=.5
        c['grenade_secret']=True
    if '空输' in active and base_id=='zombie:飞贼僵尸':
        c['cost']=100
        c['cooldown']*=.5
    return c
