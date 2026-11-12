"""Explicit PvP-only definitions. Never mutates the native single-player tables."""
import hashlib
import json
from copy import deepcopy
from . import cppcore as _cppcore
deepcopy = _cppcore.fast_deepcopy(deepcopy)
from . import BUILD
from .balance import (PLANT_COOLDOWNS, ZOMBIE_COOLDOWNS, GRAVE_BALANCE, COSTS,
                      FAST_PLANT_COOLDOWN_FACTOR, MINE_EMERGENCE_SECONDS,
                      SPIKE_SECRET_STEP, SPIKE_SECRET_MIN_COST, GOLD_MAGNET_BUCKET_HP,
                      HARDENING_MIN_BASE_HP, HARDENING_HP_FACTOR,
                      DOOM_ZOMBIE_AUTO_EXPLODE_TICKS, HEALTH, ABSORB_TICKS,
                      ENGINE_ABSORB_TICKS,
                      initial_cooldown, deployment_cooldown)

CARDS = {}


def _card(name, side, cost, hp=180, damage=20, interval=1.5, reach=520,
          speed=0, behavior="shoot", **extra):
    key = side + ":" + name
    value = dict(id=key, name=name, side=side, cost=cost, hp=hp, damage=damage,
                 interval=interval, range=reach, speed=speed, behavior=behavior,
                 cooldown=7.5, category="plant" if side == "plant" else "zombie",
                 producer=False, ban_protected=False, family=key, asset=name,
                 description="", economy="none", selectable=True)
    value.update(extra)
    CARDS[key] = value
    return value


# Values are independent starting balance, in health units and seconds.
_card("向日葵", "plant", 50, behavior="produce", producer=True, economy="periodic_sun", period=20., yield_amount=25)
_card("双子向日葵", "plant", 150, behavior="produce", producer=True, economy="periodic_sun", period=20., yield_amount=50, family="plant:向日葵")
_card("阳光菇", "plant", 25, behavior="produce", producer=True, economy="periodic_sun", period=18., yield_amount=15, mature_at=90., mature_yield=25, mushroom=True)
for name,cost,hp in [("坚果",50,1440),("高坚果",125,2880),("南瓜头",125,1440)]:
    _card(name,"plant",cost,hp,behavior="wall",cooldown=20.,height=90 if name=="高坚果" else 44)
for name,cost,damage,interval,extra in [
    ("豌豆射手",100,20,1.5,{}),("寒冰射手",175,20,1.5,{"slow":2.}),
    ("双发射手",200,20,1.5,{"burst":2}),("机枪射手",325,20,1.5,{"burst":4}),
    ("小喷菇",0,20,1.5,{"range":200,"mushroom":True,"lifetime":120.}),
    ("胆小菇",25,30,1.5,{"mushroom":True,"timid":True}),
    ("大喷菇",75,30,1.5,{"range":260,"pierce":True,"mushroom":True}),
    ("仙人掌",125,25,1.5,{"anti_air":True,"pierce":True}),
    ("裂荚射手",125,20,1.5,{"rear_burst":2}),
    ("三向射手",325,20,1.5,{"burst":3,"spread":True}),
    ("海蘑菇",0,20,1.5,{"range":220,"aquatic":True,"mushroom":True,"lifetime":120.}),
    ("忧郁蘑菇",225,20,.9,{"range":150,"radial":True,"mushroom":True}),
    ("卷心菜投手",100,60,2.7,{"lob":True}),
    ("玉米投手",100,10,2.,{"lob":True,"butter":True}),
    ("西瓜投手",300,80,2.7,{"lob":True,"splash":90}),
    ("冰瓜投手",450,80,2.7,{"lob":True,"splash":90,"slow":3.}),
    ("香蒲",225,20,.75,{"homing":True,"range":650,"anti_air":True,"aquatic":True}),
    ("杨桃",125,30,1.5,{"star":True,"pierce":True})]:
    reach=extra.pop("range",520)
    _card(name,"plant",cost,damage=damage,interval=interval,reach=reach,**extra)
for name,cost,behavior,radius in [("樱桃炸弹",150,"ash",140),("毁灭菇",200,"doom",230),
                                  ("火爆辣椒",125,"chili",650),("寒冰菇",75,"freeze",650),
                                  ("窝瓜",50,"squash",95),("土豆地雷",25,"mine",75)]:
    _card(name,"plant",cost,damage=1800,behavior=behavior,reach=radius,cooldown=30.,
          fuse=1. if behavior in ("ash","doom","chili","freeze") else 0.,
          arm_time=MINE_EMERGENCE_SECONDS if behavior=="mine" else 0.,mushroom=name in ("毁灭菇","寒冰菇"))
_card("大嘴花","plant",150,damage=1200,interval=14.,reach=75,behavior="chomp",hero_cap=True)
_card("魅惑菇","plant",75,behavior="charm",mushroom=True,reach=60,cooldown=20.)
_card("地刺","plant",100,damage=20,interval=.8,reach=46,behavior="spike",hp=280)
_card("地刺王","plant",250,damage=40,interval=.4,reach=46,behavior="spike",hp=800,family="plant:地刺")
_card("大蒜","plant",50,behavior="garlic",hp=400)
_card("火炬树桩","plant",175,behavior="torch")
_card("磁力菇","plant",100,behavior="magnet",interval=8.,reach=240,mushroom=True)
_card("吸金磁","plant",150,behavior="magnet",interval=6.,reach=280,family="plant:磁力菇",economy="no_coin_conversion")
_card("三叶草","plant",100,behavior="wind",fuse=1.,reach=700,cooldown=20.)
_card("缠绕海草","plant",25,behavior="chomp",damage=1200,interval=20.,reach=60,aquatic=True,hero_cap=True)
_card("墓碑吞噬者","plant",75,behavior="gravebuster",damage=120,interval=1.,reach=70,cooldown=15.)
_card("玉米加农炮","plant",500,damage=1000,interval=25.,reach=900,behavior="cannon",splash=160,cooldown=25.,hero_cap=True)
_card("路灯花","plant",25,behavior="lantern",reach=220)
_card("萝卜伞","plant",100,behavior="umbrella",reach=150)
for name,cost,behavior in [("花盆",25,"pot"),("睡莲",25,"lily"),("咖啡豆",75,"coffee"),("石块",25,"stone"),("模仿者",50,"copy")]:
    _card(name,"plant",cost,behavior=behavior,category="tool",ban_protected=name in ("花盆","咖啡豆"),
          cooldown=5. if name=="石块" else 7.5,hp=180)
CARDS["plant:石块"]["asset"]="石"

for name,cost,hp,speed,extra in [
    ("普通僵尸",50,200,28,{}),("路障僵尸",100,500,28,{"armor":300}),
    ("铁桶僵尸",175,950,28,{"armor":750,"metal":True}),
    ("钢门普通僵尸",150,750,28,{"armor":550,"metal":True}),
    ("铁桶钢门僵尸",275,1500,25,{"armor":1300,"metal":True}),
    ("报纸僵尸",100,350,28,{"rage":True}),("橄榄球僵尸",250,1200,60,{"armor":900,"metal":True}),
    ("撑杆跳僵尸",125,260,42,{"vault":True}),("梯子僵尸",150,500,35,{"ladder":True,"metal":True}),
    ("蹦蹦僵尸",200,350,38,{"pogo":True,"metal":True}),
    ("气球僵尸",175,240,38,{"flying":True}),("矿工僵尸",200,350,35,{"burrow":True,"metal":True}),
    ("潜水僵尸",125,300,40,{"aquatic":True}),("海豚僵尸",175,350,60,{"aquatic":True,"vault":True}),
    ("鸭子普通僵尸",75,200,32,{"aquatic":True}),
    ("鸭子路障僵尸",125,500,32,{"aquatic":True,"armor":300}),
    ("鸭子铁桶僵尸",200,950,32,{"aquatic":True,"armor":750,"metal":True}),
    ("旗帜僵尸",75,240,42,{}),("伴舞僵尸",50,180,60,{}),
    ("巨人僵尸",450,2400,22,{"damage":180,"interval":2.,"throw_imp":True,"heavy":True}),
    ("小鬼僵尸",25,120,60,{}),
    ("雪橇车僵尸",350,1600,40,{"damage":120,"heavy":True}),
    ("投篮车僵尸",325,1000,22,{"behavior":"lob","range":540,"damage":80,"interval":2.5}),
    ("小丑僵尸",175,300,36,{"behavior":"suicide","damage":1000,"range":140,"fuse":12.}),
    ("飞贼僵尸",200,300,45,{"flying":True,"behavior":"thief"})]:
    kw=dict(damage=35,interval=1.,reach=55,behavior="bite");kw.update(extra)
    if "range" in kw:kw["reach"]=kw.pop("range")
    _card(name,"zombie",cost,hp,speed=speed,**kw)

# Existing plant-zombie variants preserve distinct attack families in the PvP simulator.
for name,plant,cost,hp,speed,behavior in [
    ("豌豆僵尸","豌豆射手",150,350,27,"shoot"),
    ("机枪僵尸","机枪射手",375,550,23,"shoot"),
    ("大喷菇僵尸","大喷菇",200,400,27,"shoot"),
    ("坚果僵尸","坚果",175,1200,24,"bite"),
    ("高坚果僵尸","高坚果",350,2400,20,"bite"),
    ("毁灭菇僵尸","毁灭菇",350,400,25,"suicide"),
    ("辣椒僵尸","火爆辣椒",275,350,28,"suicide"),
    ("倭瓜僵尸","窝瓜",150,450,32,"squash"),
    ("墓碑吞噬者僵尸","墓碑吞噬者",150,450,30,"bite"),
    ("三叶草僵尸","三叶草",200,400,30,"blover"),
    ("路灯花僵尸","路灯花",275,600,28,"lantern_zombie"),
    ("萝卜伞僵尸","萝卜伞",225,500,25,"umbrella"),
    ("吸金磁僵尸","吸金磁",250,400,27,"gold_magnet")]:
    base=deepcopy(CARDS["plant:"+plant]);base.update(id="zombie:"+name,name=name,side="zombie",category="zombie",cost=cost,hp=hp,speed=speed,behavior=behavior,asset=name,family="zombie:"+name,producer=False,cooldown=10.)
    if behavior=="suicide":base.update(fuse=12.,death_explosion=True)
    if behavior=="bite":base.update(damage=45,interval=1.,range=58)
    if behavior=="blover":base.update(interval=6.,range=240,damage=0)
    if behavior=="lantern_zombie":base.update(interval=4.,range=240,damage=0,heal_amount=40,description="周期治疗范围内己方僵尸；不治疗英雄，不生产脑光。")
    if behavior=="gold_magnet":base.update(interval=8.,range=220,damage=0,armor_grant=GOLD_MAGNET_BUCKET_HP,description="为无头盔己方僵尸配备 250 生命铁桶；魅惑后拆除敌方金属，不生产脑光。")
    if name=="墓碑吞噬者僵尸":base.update(death_spawn="zombie:残骸墓碑（非生产）",description="正常死亡时在原地释放一根骨头：落地格可放墓碑则生成可被攻击、可出兵、不产脑光的骨头墓碑，否则不生成；魅惑后死亡改为植物方墓碑吞噬者，仍受禁选约束。灰烬或吞噬不触发。")
    CARDS[base["id"]]=base

for name,cost,hp,period,yield_amount,extra in [
    ("脑光墓碑",50,400,12.,25,{}),("双生脑光墓碑",150,450,12.,50,{}),
    ("成长脑光墓碑",50,400,14.,20,{"mature_at":90.,"mature_yield":40}),
    ("坚固脑光墓碑",125,1000,16.,25,{})]:
    _card(name,"zombie",cost,hp,behavior="grave",category="economy",producer=True,economy="periodic_brain",period=period,yield_amount=yield_amount,cooldown=10.,asset=name,**extra)

# A combat death can leave this targetable deployment point. It is never a
# selectable card, never a producer, and never an unattackable legacy tile.
_card("残骸墓碑（非生产）","zombie",0,300,damage=0,behavior="grave",category="derived",
      cooldown=0,selectable=False,spawn_only=True,asset="脑光墓碑",
      description="墓碑吞噬者僵尸正常死亡留下的实体。可被攻击，可作为己方出兵点；不产脑光，不占卡槽，死斗期间仍能由死亡产生。")

SECRET_EFFECTS = {
    "无土栽培":("", "允许在坚实地面直接种植，无需花盆。", "soil"),
    "疾行":("", "移速增加25%，植物方戴夫解锁三段跳；第三跳起跳速度提高25%，跳得更高。", "run"),
    "补光":("", "植物去世时掉落小阳光；对战中的临时召唤与重复死亡不重复计奖。", "death_sun"),
    "速植":("", "所有植物基础种植冷却减少 25%，仍遵守死斗禁放生产单位。", "cooldown"),
    "硬化":("", "基础生命为 6 的植物生命 +3，高于 6 的增加 25%。", "wall_hp"),
    "体香":("", "香喷喷的身体，僵尸吃了都说好；沿用原戴夫受击逻辑。", "garlic"),
    "猫尾":("", "开局满120秒后戴夫获得猫尾射击，优先追踪最近目标，对僵尸戴夫每发2伤害；敌方英雄须近距标记且可见才能被追踪，命中不刷新英雄标记。", "hero_tail"),
    "石果":("高坚果", "高坚果替换为石果子，费用变为 175 阳光。啃咬不能将其吃死，但会自行消失。", "native_replace"),
    "胆大":("胆小菇", "胆小菇基础费用增加 25 阳光；接近的僵尸越多，射得越猛。", "brave"),
    "尖刺":("仙人掌", "仙人掌反伤增加 100%。", "cactus"),
    "压顶":("窝瓜", "窝瓜会长时间坐晕普通僵尸；英雄控制仍受限制。", "squash"),
    "蓝火":("火炬树桩", "火炬树桩变为蓝火树桩，费用变为 200；沿用原蓝火豌豆增强机制，蓝火豆命中附带 1/3 溅射。蓝火豆对僵尸戴夫直击8，敌方英雄溅射2，不叠加直击目标。", "native_replace"),
    "地雷":("土豆地雷", "对战土豆地雷出土时间由 16 秒减半至 8 秒，部署冷却额外减少 25%。", "mine"),
    "核平":("毁灭菇", "毁灭菇伤害增加 100%；英雄单轮上限保持。", "doom"),
    "魅惑":("魅惑菇", "增强被魅惑的僵尸，并使魅惑菇部署冷却额外减半。", "charm"),
    "雷霆":("大喷菇", "大喷菇替换为雷蘑菇，费用变为 150；攻击麻痹带金属的僵尸。", "native_replace"),
    "磁力":("磁力菇", "磁力菇磁吸范围变为无限；英雄目标仍受对战约束。", "magnet"),
    "黄油":("玉米投手", "玉米投手黄油概率提高；英雄控制仍受限制。", "butter"),
    "卷心菜":("卷心菜投手", "卷心菜弹丸可以撞墙反弹 5 次。", "cabbage"),
    "地刺":("地刺", "每种一个地刺，后续地刺所需阳光减少 10，最低 15。", "spike_cost"),
    "水兵":("海蘑菇", "海蘑菇潜藏在水面之下。", "sea"),
    "光疗":("路灯花", "路灯花治疗效果翻倍，生命翻倍。", "heal"),
    "龙蒺藜":("大嘴花", "大嘴花替换为龙蒺藜，费用变为 150；咀嚼时间减少 80%。", "native_replace"),
    "咖啡":("咖啡豆", "咖啡豆费用降为 50，冷却缩短 75%。", "coffee"),
    "小喷":("小喷菇", "小喷菇基础费用增加 25 阳光，刚种下时攻击速度提高。", "puff"),
    "大帝":("杨桃", "场上僵尸越多，杨桃攻击速度越快。", "star"),
    "三向蓝火":("三向射手", "多向红火：三向射手、裂荚射手、豌豆迫击炮发射红火豌豆；费用各增加50；对僵尸戴夫直击6、敌方英雄溅射1.5，不叠加直击目标。", "tripea_blue"),
}
for name,(dep,description,effect) in SECRET_EFFECTS.items():
    previous=CARDS.get("plant:"+name)
    art={"无土栽培":"花盆","疾行":"三叶草","补光":"向日葵","速植":"阳光菇","猫尾":"香蒲","硬化":"坚果","体香":"大蒜"}.get(name,dep or "秘籍卡")
    _card(name,"plant",0,behavior="secret",category="secret",dependency=("plant:"+dep) if dep else "",
          effect=effect,description=description,asset=art,cooldown=0,native_secret_name=name)
    # A secret and a plant may have the same name; IDs remain distinct.
    value=CARDS.pop("plant:"+name)
    value.update(id="secret:"+name,family="secret:"+name)
    CARDS[value["id"]]=value
    if previous:CARDS[previous["id"]]=previous

CARDS["secret:补光"]["economy"]="event_enemy_kill_refund"

EXCLUDED = {"plant:金盏花":"PvP 无商店金币用途，尚未定义战斗功能。",
            "zombie:舞王僵尸":"原版 boss 列表中的 Boss，不进入对战卡池或召唤白名单。",
            "secret:防守":"依赖单人末波，PvP 无波次。", "secret:气球":"两英雄死亡结算，不启用濒死逃生。"}
BOSS_NAMES = ("Boss", "boss", "僵王", "舞王僵尸", "向日葵舞王", "雪人僵尸", "红眼巨人僵尸", "黑橄榄球僵尸", "超级", "博士", "机械巨人")
# Read-only evidence captured by executing the shipped creation, price and CD
# functions in isolated globals. The parity tests re-execute these functions.
# HP is the native object's unit (plant 6, hero 20, zombie normal 50); do not
# rescale or overwrite a native instance from the provisional PvP balance fields.
NATIVE_EVIDENCE = {'marshal_path': 'reverse_engineered/raw/pvzrouge.pyc', 'marshal_sha256': '6f10bada57913dd51bc4c87900d38ba875841d04febe3daafaeaa2d2f4cdf914', 'patch_path': 'modkit/pvzrouge_runtime_patch_source_20260904.py', 'patch_sha256': 'cba637e4d6a643a97e1e4bbae57c4c8eb6d4fc21a1bcede1c51b1d529dc2eb75', 'baseline_mode': '正常模式', 'baseline_version': 'v1.4.8', 'plk': 1, 'random_choice': 'integer midpoint; speed jitter is otherwise -5..5', 'cd_unit': 'raw native planting clock, not PvP seconds', 'hp_unit': 'native object units; armor and handheld separately', 'speed_unit': 'native 移速 at plk=1', 'null_policy': 'not an entity, no native price, or no corresponding native field'}
NATIVE_HERO = {'hp': 20, 'plant_pea_damage_to_zombie': 20, 'plant_zombie_pea_damage_to_plant': 2, 'plant_zombie_pea_damage_to_hero': 1, 'source': 'marshal module:3851; patch NORMAL_PEA_DAMAGE/PLANT_ZOMBIE_PEA_DAMAGE/PLANT_ZOMBIE_DAVE_DAMAGE'}
_NATIVE_COLUMNS = ('native_cost', 'native_hp', 'native_speed', 'native_cd', 'native_name', 'native_armor_hp', 'native_handheld_hp', 'native_izombie_hp', 'native_izombie_speed', 'native_izombie_armor_hp', 'native_izombie_handheld_hp', 'native_hard_hp', 'native_hard_armor_hp', 'native_hard_handheld_hp')
_NATIVE_ROWS = {
    'plant:向日葵': (50, 6, None, 3000, '向日葵', None, None, None, None, None, None, None, None, None),
    'plant:双子向日葵': (100, 6, None, 5000, '双子向日葵', None, None, None, None, None, None, None, None, None),
    'plant:阳光菇': (25, 6, None, 3000, '阳光菇', None, None, None, None, None, None, None, None, None),
    'plant:坚果': (50, 72, None, 5000, '坚果', None, None, None, None, None, None, None, None, None),
    'plant:高坚果': (125, 144, None, 9000, '高坚果', None, None, None, None, None, None, None, None, None),
    'plant:南瓜头': (125, 72, None, 6000, '南瓜头', None, None, None, None, None, None, None, None, None),
    'plant:豌豆射手': (100, 6, None, 1000, '豌豆射手', None, None, None, None, None, None, None, None, None),
    'plant:寒冰射手': (175, 6, None, 3000, '寒冰射手', None, None, None, None, None, None, None, None, None),
    'plant:双发射手': (200, 6, None, 2000, '双发射手', None, None, None, None, None, None, None, None, None),
    'plant:机枪射手': (350, 6, None, 8000, '机枪射手', None, None, None, None, None, None, None, None, None),
    'plant:小喷菇': (0, 6, None, 1500, '小喷菇', None, None, None, None, None, None, None, None, None),
    'plant:胆小菇': (50, 6, None, 1000, '胆小菇', None, None, None, None, None, None, None, None, None),
    'plant:大喷菇': (100, 6, None, 1500, '大喷菇', None, None, None, None, None, None, None, None, None),
    'plant:仙人掌': (150, 36, None, 3000, '仙人掌', None, None, None, None, None, None, None, None, None),
    'plant:裂荚射手': (250, 6, None, 3000, '裂荚射手', None, None, None, None, None, None, None, None, None),
    'plant:三向射手': (325, 6, None, 5000, '三向射手', None, None, None, None, None, None, None, None, None),
    'plant:海蘑菇': (0, 6, None, 1500, '海蘑菇', None, None, None, None, None, None, None, None, None),
    'plant:忧郁蘑菇': (500, 6, None, 5000, '忧郁蘑菇', None, None, None, None, None, None, None, None, None),
    'plant:卷心菜投手': (175, 6, None, 1000, '卷心菜投手', None, None, None, None, None, None, None, None, None),
    'plant:玉米投手': (175, 6, None, 1000, '玉米投手', None, None, None, None, None, None, None, None, None),
    'plant:西瓜投手': (400, 6, None, 5000, '西瓜投手', None, None, None, None, None, None, None, None, None),
    'plant:冰瓜投手': (625, 6, None, 7000, '冰瓜投手', None, None, None, None, None, None, None, None, None),
    'plant:香蒲': (300, 6, None, 10000, '香蒲', None, None, None, None, None, None, None, None, None),
    'plant:杨桃': (250, 6, None, 4000, '杨桃', None, None, None, None, None, None, None, None, None),
    'plant:樱桃炸弹': (300, 6, None, 30000, '樱桃炸弹', None, None, None, None, None, None, None, None, None),
    'plant:毁灭菇': (250, 6, None, 40000, '毁灭菇', None, None, None, None, None, None, None, None, None),
    'plant:火爆辣椒': (250, 6, None, 30000, '火爆辣椒', None, None, None, None, None, None, None, None, None),
    'plant:寒冰菇': (75, 6, None, 12000, '寒冰菇', None, None, None, None, None, None, None, None, None),
    'plant:窝瓜': (100, 6, None, 10000, '窝瓜', None, None, None, None, None, None, None, None, None),
    'plant:土豆地雷': (25, 6, None, 500, '土豆地雷', None, None, None, None, None, None, None, None, None),
    'plant:大嘴花': (150, 6, None, 3000, '大嘴花', None, None, None, None, None, None, None, None, None),
    'plant:魅惑菇': (75, 6, None, 10000, '魅惑菇', None, None, None, None, None, None, None, None, None),
    'plant:地刺王': (200, 6, None, 5000, '地刺王', None, None, None, None, None, None, None, None, None),
    'plant:大蒜': (200, 18, None, 12000, '大蒜', None, None, None, None, None, None, None, None, None),
    'plant:火炬树桩': (175, 6, None, 8000, '火炬树桩', None, None, None, None, None, None, None, None, None),
    'plant:磁力菇': (200, 6, None, 8000, '磁力菇', None, None, None, None, None, None, None, None, None),
    'plant:吸金磁': (400, 6, None, 8000, '吸金磁', None, None, None, None, None, None, None, None, None),
    'plant:三叶草': (100, 6, None, 12000, '三叶草', None, None, None, None, None, None, None, None, None),
    'plant:缠绕海草': (25, 6, None, 1500, '缠绕海草', None, None, None, None, None, None, None, None, None),
    'plant:墓碑吞噬者': (75, 6, None, 500, '墓碑吞噬者', None, None, None, None, None, None, None, None, None),
    'plant:玉米加农炮': (1000, 6, None, 30000, '玉米加农炮', None, None, None, None, None, None, None, None, None),
    'plant:路灯花': (25, 6, None, 1000, '路灯花', None, None, None, None, None, None, None, None, None),
    'plant:萝卜伞': (100, 6, None, 3000, '萝卜伞', None, None, None, None, None, None, None, None, None),
    'plant:花盆': (25, 6, None, 400, '花盆', None, None, None, None, None, None, None, None, None),
    'plant:睡莲': (25, 6, None, 750, '睡莲', None, None, None, None, None, None, None, None, None),
    'plant:咖啡豆': (75, 6, None, 3000, '咖啡豆', None, None, None, None, None, None, None, None, None),
    'plant:石块': (100, None, None, 4000, '石块', None, None, None, None, None, None, None, None, None),
    'plant:模仿者': (0, None, None, 20000, '模仿者', None, None, None, None, None, None, None, None, None),
    'zombie:普通僵尸': (50, 50, 40, 5000, '普通僵尸', 0, 0, 50, 40, 0, 0, 100, 0, 0),
    'zombie:路障僵尸': (100, 50, 40, 5000, '普通僵尸', 100, 0, 50, 40, 100, 0, 100, 200, 0),
    'zombie:铁桶僵尸': (175, 50, 40, 5000, '普通僵尸', 250, 0, 50, 40, 250, 0, 100, 500, 0),
    'zombie:钢门普通僵尸': (300, 50, 40, 5000, '普通僵尸', 0, 500, 50, 40, 0, 500, 100, 0, 500),
    'zombie:铁桶钢门僵尸': (400, 50, 40, 5000, '普通僵尸', 250, 500, 50, 40, 250, 500, 100, 500, 500),
    'zombie:报纸僵尸': (900, 500, 30, 5000, '报纸僵尸', 0, 100, 500, 30, 0, 100, 1000, 0, 100),
    'zombie:橄榄球僵尸': (500, 50, 80, 5000, '橄榄球僵尸', 400, 0, 50, 80, 400, 0, 100, 800, 0),
    'zombie:撑杆跳僵尸': (125, 75, 100, 5000, '撑杆跳僵尸', 0, 0, 75, 100, 0, 0, 150, 0, 0),
    'zombie:梯子僵尸': (350, 75, 60, 5000, '梯子僵尸', 0, 250, 75, 60, 0, 250, 150, 0, 250),
    'zombie:蹦蹦僵尸': (100, 75, 40, 5000, '蹦蹦僵尸', 0, 0, 75, 40, 0, 0, 150, 0, 0),
    'zombie:气球僵尸': (500, 75, 40, 5000, '气球僵尸', 0, 1, 75, 40, 0, 1, 150, 0, 1),
    'zombie:矿工僵尸': (500, 75, 40, 5000, '矿工僵尸', 0, 0, 75, 40, 0, 0, 150, 0, 0),
    'zombie:潜水僵尸': (125, 50, 60, 5000, '潜水僵尸', 0, 0, 50, 60, 0, 0, 100, 0, 0),
    'zombie:海豚僵尸': (100, 75, 80, 5000, '海豚僵尸', 0, 0, 75, 80, 0, 0, 150, 0, 0),
    'zombie:鸭子普通僵尸': (75, 50, 40, 5000, '鸭子僵尸', 0, 0, 50, 40, 0, 0, 100, 0, 0),
    'zombie:鸭子路障僵尸': (125, 50, 40, 5000, '鸭子僵尸', 100, 0, 50, 40, 100, 0, 100, 200, 0),
    'zombie:鸭子铁桶僵尸': (200, 50, 40, 5000, '鸭子僵尸', 250, 0, 50, 40, 250, 0, 100, 500, 0),
    'zombie:旗帜僵尸': (75, 50, 80, 5000, '旗帜僵尸', 0, 0, 50, 80, 0, 0, 100, 0, 0),
    'zombie:伴舞僵尸': (None, 75, 40, 5000, '伴舞僵尸', 0, 0, 75, 40, 0, 0, 150, 0, 0),
    'zombie:巨人僵尸': (1200, 1000, 30, 5000, '巨人僵尸', 0, 0, 1000, 30, 0, 0, 2000, 0, 0),
    'zombie:小鬼僵尸': (25, 30, 60, 5000, '小鬼僵尸', 0, 0, 30, 60, 0, 0, 60, 0, 0),
    'zombie:雪橇车僵尸': (600, 300, 40, 5000, '雪橇车僵尸', 0, 0, 300, 40, 0, 0, 600, 0, 0),
    'zombie:投篮车僵尸': (400, 200, 40, 5000, '投篮车僵尸', 0, 0, 200, 40, 0, 0, 400, 0, 0),
    'zombie:小丑僵尸': (150, 75, 60, 5000, '小丑僵尸', 0, 0, 75, 60, 0, 0, 150, 0, 0),
    'zombie:飞贼僵尸': (400, 100, 10, 5000, '飞贼僵尸', 0, 0, 100, 10, 0, 0, 200, 0, 0),
    'zombie:豌豆僵尸': (100, 100, 40, 5000, '豌豆僵尸', 0, 0, 100, 40, 0, 0, 200, 0, 0),
    'zombie:机枪僵尸': (500, 100, 40, 5000, '机枪僵尸', 0, 0, 100, 40, 0, 0, 200, 0, 0),
    'zombie:大喷菇僵尸': (400, 200, 40, 5000, '大喷菇僵尸', 0, 0, 200, 40, 0, 0, 400, 0, 0),
    'zombie:坚果僵尸': (300, 600, 40, 5000, '坚果僵尸', 0, 0, 600, 40, 0, 0, 1200, 0, 0),
    'zombie:高坚果僵尸': (750, 2000, 40, 5000, '高坚果僵尸', 0, 0, 2000, 40, 0, 0, 4000, 0, 0),
    'zombie:毁灭菇僵尸': (200, 150, 120.0, 5000, '毁灭菇僵尸', 0, 0, 150, 120.0, 0, 0, 300, 0, 0),
    'zombie:辣椒僵尸': (350, 100, 40, 5000, '辣椒僵尸', 0, 0, 100, 40, 0, 0, 200, 0, 0),
    'zombie:倭瓜僵尸': (100, 150, 120.0, 5000, '倭瓜僵尸', 0, 0, 150, 120.0, 0, 0, 300, 0, 0),
    'zombie:墓碑吞噬者僵尸': (600, 600, 40.0, 5000, '墓碑吞噬者僵尸', 0, 0, 600, 40.0, 0, 0, 1200, 0, 0),
    'zombie:三叶草僵尸': (175, 200, 120.0, 5000, '三叶草僵尸', 0, 0, 200, 120.0, 0, 0, 400, 0, 0),
    'zombie:路灯花僵尸': (400, 300, 120.0, 5000, '路灯花僵尸', 0, 0, 300, 120.0, 0, 0, 600, 0, 0),
    'zombie:萝卜伞僵尸': (300, 300, 40, 5000, '萝卜伞僵尸', 0, 0, 300, 40, 0, 0, 600, 0, 0),
    'zombie:吸金磁僵尸': (400, 200, 40, 5000, '吸金磁僵尸', 0, 0, 200, 40, 0, 0, 400, 0, 0),
    'plant:地刺': (100, 6, None, 750, '地刺', None, None, None, None, None, None, None, None, None),
}
NATIVE_CARD_EVIDENCE = {key: dict(zip(_NATIVE_COLUMNS, row)) for key, row in _NATIVE_ROWS.items()}
NATIVE_DESCRIPTIONS = {'花盆': '要是没有花盆，我只能老老实实地把植物种在泥土或者草地上。',
 '向日葵': '向日葵可以生产阳光，不过在晚上的时候，它的产光速度会大幅下降。',
 '豌豆射手': '豌豆射手是我们刚开始唯一的输出植物。',
 '坚果': '坚果能够承受72次啃咬，但两个坚果的种植冷却时间大于一个高坚果。',
 '土豆地雷': '种下土豆地雷后，需要等待一段时间它才会冒出来。',
 '阳光菇': '白天0阳光；夜晚蘑菇费用+25（即25阳光）。未长大时每次生产15阳光，长大后每次25阳光。种下6秒首次生产，之后每16秒一次，夜晚不减慢。',
 '小喷菇': '小喷菇虽然攻击没有击退，但火力等同于1.25个豌豆射手。对僵尸戴夫每次2.5伤害。弹幕累计飞行超过8格后清除。',
 '樱桃炸弹': '樱桃炸弹会把周围的僵尸炸成灰。',
 '寒冰射手': '寒冰射手能射出冰豆，冰豆会使僵尸减速。',
 '双发射手': '双发射手能连续射两发豌豆。',
 '咖啡豆': '咖啡豆可以给蘑菇们提神。',
 '胆小菇': '胆小菇虽然攻击没有击退，但火力相当于1.5个豌豆射手，它唯一的缺点就是胆子小。弹幕累计飞行超过16格后清除。',
 '大蒜': '香喷喷的大蒜，僵尸吃了都说好。',
 '窝瓜': '窝瓜会坐扁靠近的僵尸，它的起跳方向是你种下的方向，当心不要种反了。压到英雄固定 16 伤害。',
 '大喷菇': '大喷菇的泡泡攻击可以穿透僵尸，对植物僵尸伤害大幅提升。',
 '毁灭菇': '在种下毁灭菇之前，请注意离植物们远一点。',
 '寒冰菇': '寒冰菇可以冻住全图的僵尸，还会造成一颗豌豆的伤害。',
 '魅惑菇': '魅惑菇可以让僵尸变成你的手下。',
 '火炬树桩': '豌豆掠过火树时会变成火豆，伤害+100%，且会穿透僵尸的手持防具；火豆命中附带 1/3 溅射。火豆对僵尸戴夫直击6、敌方英雄溅射1.5；蓝火直击8、溅射2，溅射不叠加直击目标。寒冰豌豆在同一树桩只解冻，经过另一根树桩可点燃。',
 '杨桃': '杨桃会按五角星方向发射五颗星星，对普通僵尸每颗造成30伤害，对僵尸戴夫每颗6伤害。星星不受重力影响，可穿透僵尸与方块，累计飞行超过32格后清除。',
 '卷心菜投手': '卷心菜投手会投掷卷心菜，基础伤害30，末速越高重力增伤越高。对植物戴夫固定12。',
 '玉米投手': '玉米粒基础伤害5，黄油基础伤害10，抛物线末速越高重力增伤越高。黄油仍可定住僵尸。',
 '西瓜投手': '西瓜基础伤害150，根据落地末速获得额外重力增伤；碎裂时对附近敌人造成50溅射伤害，直接目标不重复计算。对植物戴夫直接命中固定16、溅射2。',
 '地刺': '地刺会给僵尸提供脚底按摩服务，它不能种在花盆或者睡莲上。',
 '火爆辣椒': '生成贴地火焰，逐段锁到脚下地面，不把梯子当落点。对普通僵尸造成750伤害，对英雄16伤害；同次爆炸及其火焰对同一目标只结算一次。',
 '墓碑吞噬者': '墓碑吞噬者能吞掉墓碑。天数越多晚上墓碑越多，雨夜的墓碑会更多。',
 '三叶草': '三叶草能把僵尸吹飞，它能把气球僵尸吹很远，但吹不死气球僵尸。',
 '仙人掌': '仙人掌不能伸长身体打气球但它能够承受36次啃咬，且咬的僵尸会被它的刺反伤。它的攻击可以穿透方块。',
 '高坚果': '对战生命180。它虽然看起来很给人安全感，但拦不住海豚、撑杆跳、蹦蹦僵尸。',
 '冰瓜投手': '冰瓜基础伤害150，享受重力增伤；碎裂时对附近敌人造成50溅射伤害并减速，直接目标不重复计算伤害。对植物戴夫直接命中固定16、溅射2。',
 '机枪射手': '机枪射手能连续射四发豌豆。',
 '睡莲': '睡莲只能种在水面上，然后其它植物能种在睡莲上。',
 '海蘑菇': '海蘑菇只能种在水面上，火力相当于2.5个豌豆射手！',
 '缠绕海草': '缠绕海草只能种在水面上它会把僵尸们拖进水里进行亲密接触。',
 '双子向日葵': '双子向日葵能同时生产两坨阳光，比向日葵省空间。',
 '忧郁蘑菇': '坚果配上忧郁蘑菇，称它为最强防线也不为过。',
 '磁力菇': '铁做的玩意都能被磁力菇吸光光。',
 '香蒲': '香蒲只能种在水面上1个香蒲的火力相当于3个豌豆射手，它的尖刺还会追踪。',
 '玉米加农炮': '玉米加农炮阳光250，开炮后会慢速重新装填。',
 '路灯花': '路灯花能治疗7×7范围内的植物们。不过路灯花似乎很讨厌大蒜的味道，它拒绝为大蒜提供治疗。',
 '地刺王': '地刺王的输出是地刺的两倍，还能抗巨人锤三下！',
 '吸金磁': '吸金磁能和磁力菇一样吸铁，但它的冷却时间更快，它还能把铁转化为金币！',
 '大嘴花': '一口一个僵尸。',
 '裂荚射手': '前后各有一个豌豆头；后方连发两颗。携带豌豆杂交时，两头分别向各自前方上下45度瞄准，镜像朝向也适用。',
 '萝卜伞': '萝卜伞可以弹飞3格范围的僵尸，能保护周围植物，免受蹦极僵尸啃咬。弹飞不分敌我：己方魅惑僵尸与己方戴夫同样会被弹；不弹弹幕。',
 '模仿者': '默认复制上一次种下的植物，可切换已携带目标；不能模仿花盆、睡莲、咖啡豆或墓碑吞噬者。携带肆意模仿时费用为当前目标实际费用减100，可为负值。部分强大植物无法模仿太久，比如玉米加农炮。',
 '南瓜头': '保护同格植物，可与输出植物叠种；南瓜头害怕机枪僵尸。',
 '辣椒僵尸': '死亡时按新版火爆辣椒生成贴地火焰，敌方自爆只改伤害对象：植物、戴夫与魅惑僵尸。被魅惑后完全套用新版火爆辣椒打僵尸。',
 '三向射手': '三个豌豆头各自瞄准僵尸，优先攻击不同目标，并沿头部方向直射。',
 '石块': '放置一块原生石头，不会自然消失。八邻域需有实体方块；可被炸毁。上方可放花盆。费用为-25：每放置一块获得25阳光。',
 '倭瓜僵尸': '两格内有目标时抛出头顶倭瓜，砸向面朝方向的植物、魅惑僵尸或戴夫。投出后本体死亡；魅惑后按原倭瓜攻击僵尸。',
 '毁灭菇僵尸': '死亡时触发毁灭菇爆炸，基础生命150，移速与跳跃高度跟三叶草僵尸一致。魅惑后只改变阵营，死亡爆炸不改变。',
 '三叶草僵尸': '每隔较长时间旋转三叶草，按原版三叶草吹飞前方僵尸、气球和雨。魅惑后只改变阵营，吹风机制不改变。',
 '路灯花僵尸': '每隔一段时间点亮路灯花，治疗附近同阵营目标60点生命。原版路灯花也会治疗魅惑僵尸。',
 '墓碑吞噬者僵尸': '死亡时在原地释放一根骨头，落地处可放墓碑则生成骨头墓碑。生命300，只受35%击退效果；高于半血每口3伤害，半血及以下每口6伤害。被魅惑后死亡生成植物方墓碑吞噬者。',
 '萝卜伞僵尸': '两格内有僵尸或植物方投掷物时张开萝卜伞。击退僵尸；反转投掷物横向速度。基础生命300，只受25%击退效果。魅惑后只处理敌方僵尸、戴夫与篮球。',
 '吸金磁僵尸': '每隔较长时间给附近无头顶防具的非魅惑僵尸一顶铁桶。持有梯子、报纸、气球或钢门的僵尸也可获赠。基础生命200。魅惑后按植物方吸金磁吸走敌方金属。',
 '大喷菇僵尸': '索敌半径9格，发射6格直线穿透大泡泡串。对植物与戴夫每次1伤害，对敌对僵尸每次10伤害，魅惑前后相同；雷霆秘籍下变为雷蘑菇头、蓝泡泡并麻痹金属目标。'}

# PvP combat-card descriptions.  Values, armour and cooldowns are rendered
# separately from the same card data; these lines explain the tactical role
# instead of repeating raw numbers or falling back to a generic source note.
PVP_ZOMBIE_DESCRIPTIONS = {
 '普通僵尸': '基础近战单位。没有额外装备或位移能力，适合低成本跟随推进、探路或消耗防线。',
 '路障僵尸': '头顶路障会先承受伤害，是基础单位的耐久升级；用来为后排或跳跃单位争取接近时间。',
 '铁桶僵尸': '铁桶提供更厚的金属头部防具。磁力类植物能针对其装备，普通火力则需先打穿铁桶。',
 '钢门普通僵尸': '手持钢门推进，前方防护很强；磁力类植物可拆除金属手持物，侧后方火力也更容易绕开它。',
 '铁桶钢门僵尸': '同时具备铁桶与钢门，是最重的基础防护组合；成本和部署间隔也相应更高。',
 '报纸僵尸': '报纸会先替本体承伤；报纸被破坏后会进入狂怒状态并加速，是中距离压迫与诱导火力的单位。',
 '橄榄球僵尸': '高速重甲突进单位。适合抢节奏、穿过开阔地带；面对磁力拆甲或密集控制时风险较高。',
 '撑杆跳僵尸': '可用撑杆完成一次越障跳跃，适合跨过前排阻挡；落地后转为普通近战推进。',
 '梯子僵尸': '携带可部署的梯子，可为后续僵尸处理高坚果等高墙阻挡；梯子属于金属装备，注意磁力反制。',
 '蹦蹦僵尸': '持续跳跃越过植物防线，适合压制单层地面布阵；落点与前方控制会决定它能否安全通过。',
 '气球僵尸': '以空中路线绕开多数地面阻挡。针对它需要对空火力、三叶草等对应手段；气球本身也可被金属互动影响。',
 '矿工僵尸': '会在地下行进并从植物防线后侧出土，威胁后排与生产单位；预留背后拦截和近身防守可限制它。',
 '潜水僵尸': '水域单位，可在水中潜行接近目标；离开水域后的正面战斗能力有限，适合配合水路进攻。',
 '海豚僵尸': '借海豚完成一次高速跃过前方阻挡，水路突击能力强；跳跃结束后仍要按普通路线继续推进。',
 '鸭子普通僵尸': '水面基础近战单位。无额外防具，适合用低成本占住水路或为更强的水路单位探路。',
 '鸭子路障僵尸': '水路的路障版本，路障先承伤；适合在水面为潜水、海豚或后续鸭子单位提供掩护。',
 '鸭子铁桶僵尸': '水路的铁桶版本，拥有金属头部防具；面对磁力或专门水路火力时需要配合推进。',
 '旗帜僵尸': '高机动的号令单位。部署时会以每座存活且出口可用的己方墓碑为源额外召来一只普通僵尸，不额外扣费。召唤不受禁选影响，只受单位上限与墓碑出口限制。',
 '伴舞僵尸': '移速 60，极快。普通近战骨架的辅助进攻单位。没有独立经济或召唤规则。',
 '巨人僵尸': '高生命重型攻城单位，近战砸击威胁大，并会按原逻辑投掷小鬼施压远处目标；部署间隔很长。',
 '小鬼僵尸': '低成本、高机动的小型近战单位。适合补刀、绕侧或在巨人投掷后迅速接近，但本体很脆。',
 '雪橇车僵尸': '重型载具单位，依靠车体生命与近战冲击推进。投入较高，适合在已有墓碑出口和前排掩护下发起压力。',
 '投篮车僵尸': '远程投掷单位，篮球以抛物线攻击，可越过部分地面阻挡；需要保护它免受贴身单位和快速突袭。出场80秒后自毁，不造成范围伤害；冰冻、减速、黄油、眩晕与坤坤锁血均不延长寿命。',
 '小丑僵尸': '自爆威胁单位。接近目标或引爆后会造成范围伤害，适合逼迫对手分散或提前处理；英雄仍受单次攻击保护。',
 '飞贼僵尸': '从空中选择一株存活敌方植物下降并执行原偷取行为，不需要墓碑出场；优先针对关键后排或防线核心。',
 '豌豆僵尸': '远程单发火力单位，会沿行进方向射击植物与敌方英雄；用前排保护后可持续输出。豌豆过火炬树桩会点燃（伤害 x2，蓝火 x3），并附带 1/3 溅射（对敌方英雄红火溅射1.5、蓝火溅射2，不叠加直击目标）。',
 '机枪僵尸': '远程连发火力单位，短时间内能投出多发豌豆；适合在安全距离压制固定防线。豌豆过火炬树桩会点燃（伤害 x2，蓝火 x3），并附带 1/3 溅射（对敌方英雄红火溅射1.5、蓝火溅射2，不叠加直击目标）。',
 '大喷菇僵尸': '直线穿透泡泡攻击，尤其擅长压制同一路径上的多个目标；魅惑后会切换为植物方攻击逻辑。',
 '坚果僵尸': '高生命移动肉盾，没有复杂位移或远程能力；适合顶在射手与服务型僵尸前面吸收火力。',
 '高坚果僵尸': '极高生命的重型移动壁垒。冷却和费用都很重，适合作为一次关键推进或保护核心输出。',
 '毁灭菇僵尸': '爆炸型植物僵尸，死亡会触发毁灭菇爆炸；PvP 会按当前阵营过滤友伤，且不继承植物方核平。',
 '辣椒僵尸': '死亡时沿地面生成贴地火焰，烧尽范围内敌方植物与魅惑僵尸，并对敌方戴夫造成一次 10 点伤害（与小丑自爆相同，不会秒杀）；我方戴夫踏入火焰会被辣飞天击飞，同一爆炸不会重复判定，贴图范围即伤害范围。',
 '倭瓜僵尸': '发现近距离目标后会掷出倭瓜砸击，投出后本体死亡；适合处理关键前排或创造一次爆发窗口。',
 '墓碑吞噬者僵尸': '厚血近战单位，高于半血每口 3 伤害，半血及以下每口 6 伤害（植物与戴夫相同，魅惑互咬为 10 倍）；正常死亡在原地释放骨头，落地可放墓碑时生成可攻击、可出兵但不产脑光的骨头墓碑；灰烬和吞噬不会触发。',
 '三叶草僵尸': '周期吹风干扰单位，可按原三叶草逻辑吹飞前方目标、气球与雨；更适合拆解空中或密集推进。',
 '路灯花僵尸': '服务型僵尸，周期治疗附近同阵营僵尸，不治疗英雄也不生产脑光；需要由前排保护。',
 '萝卜伞僵尸': '反投射物与击退单位。附近出现敌方投掷物或目标时会展开叶片，反转投掷物横向速度并击退敌人。',
 '吸金磁僵尸': '服务型金属支援。会给附近无头顶防具的非魅惑友军赠予 250 生命铁桶；魅惑后改为吸走敌方金属。',
}
NATIVE_DESCRIPTIONS.update(PVP_ZOMBIE_DESCRIPTIONS)

# Plant wording that PvP balance invalidated.  Raw numbers stay out of these
# lines on purpose - the value lines below render them from the card data - so
# only the claims that stopped being true are restated here.
PVP_PLANT_DESCRIPTIONS = {
 '仙人掌': '仙人掌不能伸长身体打气球，但它比普通植物更耐啃咬，且咬它的僵尸会被刺反伤。它的攻击可以穿透方块。',
 '南瓜头': '南瓜头的血量高于坚果，种植冷却与坚果相同，南瓜头害怕机枪僵尸。',
}
NATIVE_DESCRIPTIONS.update(PVP_PLANT_DESCRIPTIONS)
NATIVE_SECRET_DESCRIPTIONS = {'咖啡': '咖啡豆阳光降至50,且种植冷却-75%', '无土栽培': '种植物不再需要花盆', '疾行': '移速增加25%', '补光': '植物去世时会掉一个小阳光', '速植': '种植cd-10%', '硬化': '所有植物血量+3', '体香': '香喷喷的身体,僵尸吃了都说好', '猫尾': '屁股长出猫尾巴', '胆大': '接近的僵尸越多,胆小菇射越猛', '尖刺': '仙人掌的反伤伤害增+100%', '压顶': '窝瓜会坐晕僵尸很长一段时间', '蓝火': '冒蓝火的树桩,增加火豆伤害', '地雷': '土豆地雷的启动时间-50%', '核平': '毁灭菇伤害+100%', '魅惑': '增强被魅惑的僵尸', '磁力': '磁力菇的磁吸范围变无限', '防守': '最后一波到来时种植冷却清零', '气球': '第一次濒死时会吹气球逃生', '黄油': '玉米投手投出黄油的概率提高', '卷心菜': '卷心菜可以撞墙反弹5次', '地刺': '每种一个地刺减少10点所需阳光', '水兵': '海蘑菇会潜藏在水面之下', '石果': '高坚果啃不死但会自己消失', '雷霆': '大喷菇攻击会麻痹带金属僵尸', '光疗': '路灯花治疗效果翻倍', '龙蒺藜': '大嘴花咀嚼时间-80%', '小喷': '小喷菇在刚种下时攻速加快', '大帝': '场上僵尸越多,杨桃攻速越快'}
NATIVE_SECRET_SHOP_COSTS = {'无土栽培': 2000, '疾行': 600, '补光': 2000, '速植': 1500, '硬化': 1000, '体香': 400, '猫尾': 3000, '石果': 1500, '胆大': 800, '尖刺': 400, '压顶': 400, '蓝火': 3000, '地雷': 400, '核平': 500, '魅惑': 600, '雷霆': 1500, '磁力': 3000, '防守': 400, '气球': 600, '黄油': 500, '卷心菜': 500, '地刺': 600, '水兵': 500, '光疗': 1000, '龙蒺藜': 1500, '咖啡': 800, '小喷': 300, '大帝': 0}
NATIVE_SECRET_DESCRIPTIONS["三向蓝火"] = "多向红火：三向射手、裂荚射手、豌豆迫击炮发射红火豌豆"
NATIVE_SECRET_SHOP_COSTS["三向蓝火"] = 800
for _key, _c in CARDS.items():
    _c.update({field: None for field in _NATIVE_COLUMNS})
    _c.update(base_id=_key, resolved_id=_key, native_input_name=_c["name"])
    if _key in NATIVE_CARD_EVIDENCE:
        _c.update(NATIVE_CARD_EVIDENCE[_key])
        _c["native_source"] = "marshal+1.5.0.1-patch"
        _c["native_cd_fallback"] = _c["side"] == "zombie"
        if _c["native_cost"] is not None:_c["cost"] = _c["native_cost"]
        _c["native_deploy_cd"] = 0 if _c["side"] == "zombie" else _c["native_cd"]
        _c["cooldown"] = _c["native_deploy_cd"] / 250.
        if _c["native_hp"] is not None:_c["hp"] = _c["native_hp"]
        if _key in HEALTH:_c["hp"] = HEALTH[_key]
        _c["native_description"] = NATIVE_DESCRIPTIONS.get(_c["name"], "")
    elif _c["category"] == "secret":
        _c["native_name"] = _c["name"]
        _c["native_source"] = "native-secret; not a spawned entity"
        _c["native_description"] = NATIVE_SECRET_DESCRIPTIONS[_c["name"]]
        _c["native_shop_cost"] = NATIVE_SECRET_SHOP_COSTS[_c["name"]]
    else:
        _c["native_source"] = "PvP-only entity; no native equivalent"

# Only these four forms replace a base planting/card image in the shipped game.
# The blue torch retains its native plant name; the native secret changes both
# its displayed image and the original projectile conversion branch.
REPLACEMENTS = {
    "plant:高坚果": dict(secret="secret:石果", resolved_id="plant:石果子", native_name="石果子", cost=175,
                       description="石果秘籍替换高坚果：生命 180，普通啃咬不将其吃死，沿用原虚血；"
                                   "六种黑化僵尸每次啃咬造成 3 点伤害。"),
    "plant:大喷菇": dict(secret="secret:雷霆", resolved_id="plant:雷蘑菇", native_name="雷蘑菇", cost=100,
                       description="雷霆秘籍替换大喷菇：沿用原喷射及金属僵尸麻痹机制。"),
    "plant:火炬树桩": dict(secret="secret:蓝火", resolved_id="plant:蓝火树桩", native_name="火炬树桩", cost=200,
                         description="蓝火秘籍改变树桩图像与原豌豆转火逻辑；实际原生植物仍为火炬树桩。"),
    "plant:大嘴花": dict(secret="secret:龙蒺藜", resolved_id="plant:龙蒺藜", native_name="龙蒺藜", cost=150,
                       description="龙蒺藜秘籍替换大嘴花：咀嚼时间减少80%，沿用原吞噬机制；英雄单源伤害受限。"),
}
DERIVED_BASES = {value["resolved_id"]: key for key, value in REPLACEMENTS.items()}
for _base, _r in REPLACEMENTS.items():
    _c = deepcopy(CARDS[_base])
    _name = _r["resolved_id"].split(":", 1)[1]
    _c.update(id=_r["resolved_id"], base_id=_base, resolved_id=_r["resolved_id"],
              name=_name, asset=_name, native_name=_r["native_name"],
              family=_base, selectable=False, spawn_only=True, category="derived",
              required_secret=_r["secret"], cost=_r["cost"],
              native_cost=250 if _base=="plant:高坚果" else _r["cost"],
              hp=_c["native_hp"], description=_r["description"], native_description=_r["description"])
    CARDS[_c["id"]] = _c
# 68004: the stone fruit's real health (its native 虚血 shields stay separate).
CARDS["plant:石果子"]["hp"] = HEALTH["plant:石果子"]

PROTECTED = frozenset(("plant:咖啡豆","plant:花盆","plant:睡莲","zombie:梯子僵尸"))
for _key in PROTECTED:
    CARDS[_key]["ban_protected"] = True

# Hero notes are appended once after all content installers.





for _key, _cost in COSTS.items():
    if _key in CARDS:CARDS[_key]["cost"] = _cost
for _key, _seconds in PLANT_COOLDOWNS.items():
    CARDS[_key]["cooldown"] = _seconds
for _key, _seconds in ZOMBIE_COOLDOWNS.items():
    if _key in CARDS:CARDS[_key]["cooldown"] = _seconds
for _key, _values in GRAVE_BALANCE.items():
    CARDS[_key].update(_values,first_production=6.)
for _name in ("向日葵","双子向日葵","阳光菇"):
    CARDS["plant:"+_name].update(period=16.,first_production=6.)
CARDS["plant:磁力菇"]["mushroom"]=True
for _key,_card_value in CARDS.items():
    if _card_value.get("selectable",True) and _card_value["category"]!="secret":
        _card_value["family"]=_key
CARDS["secret:咖啡"]["description"]="咖啡豆维持对战费用 25，冷却缩短 75%。"
from .expansion_catalog import install as _install_expansion
_install_expansion(CARDS)
from .content_catalog import install as _install_content
_install_content(CARDS, REPLACEMENTS, DERIVED_BASES)
from .september_catalog import install as _install_september, BASIC_GRAVES
_install_september(CARDS)
from .pvp56_plants_catalog import install as _install_pvp56_plants
_install_pvp56_plants(CARDS)
from .pvp56_zombie_catalog import install as _install_pvp56_zombies
_install_pvp56_zombies(CARDS)
from .pvp58_catalog import install as _install_pvp58
_install_pvp58(CARDS)
from .pvp61_catalog import install as _install_pvp61
_install_pvp61(CARDS)
from .pvp64_catalog import install as _install_pvp64, multi_blue_cost as _multi_blue_cost
_install_pvp64(CARDS)
from .pvp66_secrets import install_catalog as _install_pvp66_secrets, STARFRUIT_COST, SEA_SHROOM_SURCHARGE
_install_pvp66_secrets(CARDS)
from .zombie_secret_catalog import install as _install_zombie_secrets, apply_card as _zombie_secret_card
_install_zombie_secrets(CARDS)
from .pvp70_catalog import install as _install_pvp70
_install_pvp70(CARDS)
from .pvp71_catalog import install as _install_pvp71, IMITATE_SECRET, IMITATE_COOLDOWN_FACTOR
# Added cards and aquatic copies share the same match balance as base cards.

# 68006 hero balance notes, after every content installer.
for _name,_note in {'豌豆射手': '普通豌豆对僵尸戴夫直击4。', '寒冰射手': '寒冰豌豆对僵尸戴夫直击4。', '双发射手': '普通豌豆对僵尸戴夫直击4。', '机枪射手': '普通豌豆对僵尸戴夫直击4。', '裂荚射手': '普通豌豆对僵尸戴夫直击4。', '三向射手': '普通豌豆对僵尸戴夫直击4。', '胆小菇': '对僵尸戴夫每次2.5伤害。', '大喷菇': '对僵尸戴夫每次5伤害（雷蘑菇相同）。', '玉米投手': '对僵尸戴夫玉米粒直击2、黄油直击8。', '卷心菜投手': '对僵尸戴夫直击8。', '寒冰菇': '对僵尸戴夫伤害8。', '地刺': '对僵尸戴夫单次2.5伤害。', '地刺王': '对僵尸戴夫单次2.5伤害。', '弹簧草': '对僵尸戴夫单次3伤害。', '西瓜投手': '对僵尸戴夫直击16、溅射4，溅射不叠加直击目标。', '冰瓜投手': '对僵尸戴夫直击16、溅射4，溅射不叠加直击目标。', '甜椒投手': '对僵尸戴夫直击10、溅射10，溅射不叠加直击目标。'}.items():
    for _key,_card in CARDS.items():
        if _card.get("name")==_name and _card["side"]=="plant":
            for _field in ("description","native_description"):_card[_field]+=" "+_note

for _key, _cost in COSTS.items():
    CARDS[_key]["cost"] = _cost
for _key, _seconds in ZOMBIE_COOLDOWNS.items():
    CARDS[_key]["cooldown"] = _seconds
from .balance import PVP73_PLANT_COOLDOWNS as _pvp73_cooldowns
for _key, _seconds in _pvp73_cooldowns.items():
    # resolve/actual_card derive the cooldown from native_cd for cards outside PLANT_COOLDOWNS
    CARDS[_key].update(cooldown=_seconds, native_cd=int(_seconds*250), native_deploy_cd=int(_seconds*250))
EXCLUDED.pop('zombie:舞王僵尸', None)

for _field in ('description','native_description'):
    CARDS['zombie:投篮车僵尸'][_field] = NATIVE_DESCRIPTIONS['投篮车僵尸']
    CARDS['zombie:路灯花僵尸'][_field] += '移速与吸金磁僵尸相同，不再增强移速与跳跃。'
    CARDS['zombie:海盗鹦鹉'][_field] += '啃咬大蒜或携带体香秘籍的戴夫后眩晕0.5秒。'
    CARDS['secret:体香'][_field] += '海盗鹦鹉与乌鸦啃咬携带者后眩晕0.5秒。'
    CARDS['plant:香蒲'][_field] = '优先追踪最近的敌方目标；僵尸戴夫需已被标记、处于锁定范围且可见，每发2伤害，命中不刷新英雄标记。'
    for _name in ('闪电芦苇','超载芦苇','回旋镖射手','毒镖射手'):
        CARDS['plant:'+_name][_field] += '伤害穿透二类防具，但僵王出品可抵消穿透；中毒效果不可阻挡。'
# 71002 after the text overrides above, so its notes extend the final wording.
_install_pvp71(CARDS)

# PvP behaviour of original plants that their almanac text did not state. The
# brief almanac reads `description`, empty for these, so it keeps the original
# sentence first and then the PvP note.
for _key,_note in {
        'plant:路灯花': ('对战：横纵2.75格内、视线无遮挡的敌方僵尸戴夫会被标记，植物可锁定并攻击他。'
                       '站立的植物戴夫靠近僵尸戴夫（约2.75格内且可见）时同样会标记他。'),
        'plant:大蒜': '对战：海盗鹦鹉、乌鸦啃咬大蒜后眩晕0.5秒。',
        'plant:南瓜头': ('保护壳：可直接套在己方植物上（含空中的飞行植物），每格限一个南瓜头或藤蔓；'
                       '僵尸啃咬与豌豆优先打保护壳。铲子左键先铲保护壳，右键跳过保护壳。'),
        'plant:咖啡豆': '唤醒同一格内全部沉睡植物（含被催眠的藤蔓等保护壳）；密植时不占主体或保护壳名额。',
        'plant:花盆': '花盆上的植物可以作为植物戴夫的传送目标。'}.items():
    _base=CARDS[_key].get('native_description','')
    for _field in ('description','native_description'):
        CARDS[_key][_field]=(CARDS[_key].get(_field) or _base)+_note

RULES = dict(tick_rate=30,deathmatch_seconds=420.,production_multiplier=1.5,teleport_cooldown=20.,
             pve_max_zombies=40,
             tail_activation_seconds=120.,
             melon_splash_damage=50.,
             plant_slots=7,zombie_slots=7,unit_bans=4,secret_bans=4,ranked=False,extra_slot=False,
             opening_unit_bans=2,second_unit_bans=2,opening_picks=4,
             ban_seconds=30.,pick_seconds=30.,ready_seconds=60.,
             plant_start=75,night_plant_start=150,zombie_start=75,night_zombie_start=150,hero_hp=40.,hero_regen_delay=8.,hero_regen_interval=2.,hero_regen_amount=1.,hero_speed=155.,
             hero_jump=450.,hero_ash_cap=.4,hero_control_max=.65,hero_control_immunity=2.,
             hero_lock_range=360.,mark_seconds=3.,sky_interval=8.,sky_amount=25,sun_lifetime=20.,
             day_brain_interval=12.,day_brain_amount=25,
             producer_protection_seconds=80.,producer_protection_multiplier=.25,
             producer_rest_seconds=12.,producer_rest_ramp_seconds=36.,producer_rest_bonus=.5,
             sky_reference_cols=72,sky_reference_rows=24,sky_max_scale=2.,
             command_key="f",page_key="tab",build=BUILD)

# Included in the negotiated/replay rule hash, including non-catalog mechanics.
RULES['ruleset'] = 'pvp73'
RULES['rule_schema'] = 2
RULES['mechanics72'] = dict(chili_damage=750., chili_hero=16., tentacle_hero=4.,
    gravebuster_hp=300., gravebuster_bite=3., gravebuster_low_bite=6., gravebuster_bone=True,
    thunder_contact_stun_ticks=250, taco_speed=.75, trinity_speed=.25,
    additive_movement=True, imitate_discount=100, stone_down_factor=.75,
    masochist_rise_ticks=1000, duo_ai_sun=25, duo_ai_interval=8.,
    flyer_interception=True, charm_chases_dave=True, shell_preserves_contents=True)

for _key, _note in {
    'plant:火爆辣椒':'每次爆炸对普通僵尸造成750伤害，对英雄16伤害；同次火焰不重复结算。',
    'zombie:墓碑吞噬者僵尸':'高于半血每口3伤害，半血及以下每口6伤害；与敌对僵尸互咬时为其10倍。',
    'secret:雷霆':'雷蘑菇受到啃咬时，使啃食者眩晕1秒。',
    'zsecret:玉米卷':'特化移动的植物僵尸同样生效。',
    'zsecret:海陆空':'移速加成与其他秘籍加算。',
}.items():
    for _field in ('description','native_description'):
        _text = CARDS[_key].get(_field,'')
        CARDS[_key][_field] = _text + ('' if not _text or _text[-1] in '。；！？.!?' else '。') + _note
# Player-facing text states the current numbers only.
for _field in ('description','native_description'):
    CARDS['secret:抖M'][_field] = CARDS['secret:抖M'][_field].replace('（原为8秒）','')
    CARDS['plant:草坪'][_field] = CARDS['plant:草坪'][_field].replace('40阳光，8秒冷却。','25阳光，16秒冷却。')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()


def catalog_hash():
    return digest(CARDS)


# Room tick rates a battle may run at.  The rate only sets how many original
# 0.004 s ticks one room step advances (250/rate, integer accumulator) and how
# often inputs are sampled; unit speed and timers are native-tick based.
ROOM_TICK_RATES = (30, 60)


def rules_hash(rules=None):
    return digest(rules or RULES)


def starting_resource(side, rules=None, terrain=None):
    """Return the side's opening resource for the selected map environment."""
    rulebook = rules or RULES
    key = side + "_start"
    environment = terrain.environment if hasattr(terrain, "environment") else (terrain or {}).get("environment", {})
    if environment.get("night", False):
        key = "night_" + key
    return rulebook.get(key, rulebook[side + "_start"])


def allowed(card_id, bans=(), for_spawn=False, secrets=()):
    if not isinstance(card_id,str):return False
    card=CARDS.get(card_id)
    if not card or (any(n in card["name"] for n in BOSS_NAMES) and not card.get('pvp_regular_unit')):
        return False
    if not card.get("selectable",True) and not (for_spawn and card.get("spawn_only")):
        return False
    if card_id in PROTECTED:
        return True
    if card_id in bans or card["family"] in bans:
        return False
    dep=card.get("dependency")
    if dep and (dep in bans or CARDS[dep]["family"] in bans):
        return False
    required=card.get("required_secret")
    if required and (required not in secrets or not allowed(required,bans)):
        return False
    return True


def map_card_error(card_id, terrain=None, deck=()):
    if terrain is None or card_id in ("plant:咖啡豆", "plant:花盆"):return ""
    c=CARDS.get(card_id)
    if not c:return "未知卡牌"
    if c.get("aquatic") or c.get('requires_water') or c["behavior"]=="lily":
        tiles=terrain.tiles if hasattr(terrain,"tiles") else terrain.get("tiles",[])
        if not any(cell.get("water") for row in tiles for cell in row):
            if not (c['side']=='plant' and 'plant:水盆' in deck):return "当前地图没有可用水面："+c["name"]
        if c["side"]=="zombie" and c.get("aquatic"):
            from .preview import has_aquatic_grave_exit
            if not has_aquatic_grave_exit(terrain,c):return "此地图没有可用的水生墓碑出兵口"
    return ""


STARTER_GRAVE_ERROR = "必须保留一种开局可负担的经济墓碑"


def starter_grave(card_id, budget=None):
    card=CARDS.get(card_id,{})
    return (card.get("side")=="zombie" and card.get("behavior")=="grave"
            and bool(card.get("producer")) and card.get("selectable",True)
            and card["cost"] <= (RULES["zombie_start"] if budget is None else budget))


def team_repeatable(card_id):
    """2v2: may both teammates carry this card? (user rule, 10-12)

    Economy plants, selectable graves and the four unbannable cards (flower
    pot, coffee bean, lily pad, ladder zombie) may be carried by both; every
    other card, secrets included, belongs to one teammate. Independent of
    whether the card can be banned.
    """
    card = CARDS.get(card_id)
    if card is None or card.get("selectable") is False:
        return False
    if card_id in PROTECTED:
        return True
    if card["category"] == "secret":
        return False
    if card["side"] == "plant" and (card.get("producer") or card.get("economy") not in (None, "", "none")):
        return True
    return card["side"] == "zombie" and card.get("behavior") == "grave"


def validate_deck(side, deck, bans=(), slots=None, terrain=None, starter_budget=None):
    if not isinstance(deck,list) or not all(isinstance(x,str) for x in deck):return "卡组格式错误"
    if len(deck)!=len(set(deck)):return "卡牌不能重复"
    if len(deck)>(slots or RULES[side+"_slots"]):return "卡槽已满"
    for key in deck:
        if not allowed(key,bans):return "卡牌不可用："+key
        c=CARDS[key]
        if c["side"]!=side:return "不能携带另一阵营的卡牌"
        error=map_card_error(key,terrain,deck)
        if error:return error
        if c.get("dependency") and c["dependency"] not in deck:return "秘籍缺少依赖："+c["dependency"]
    if side=="zombie" and not any(starter_grave(k,starter_budget) for k in deck):return STARTER_GRAVE_ERROR
    if not deck:return "请选择卡组"
    return ""


def apply_secret_effects(card, secrets=()):
    """Compatibility display adapter; caller-supplied stats are never trusted.

    Actual combat secrets run once in the native per-side namespace. The former
    synthetic projectile/HP/range buffs must not be applied a second time here.
    Creation paths use resolve_card for the additional spawn/ban validation.
    """
    return actual_card(card["id"],secrets)


def actual_card(card_id, secrets=(), night=False):
    """Resolve a display definition while keeping its seven-slot base ID.

    This pure helper does not authorize deployment. native_* values are evidence
    and preview values; the engine creates and updates its actual native dict.
    """
    source=CARDS[card_id]
    s=set(secrets)
    base_id=DERIVED_BASES.get(card_id,card_id)
    replacement=REPLACEMENTS.get(base_id)
    derived=card_id in DERIVED_BASES
    if replacement and (derived or replacement["secret"] in s):
        c=deepcopy(CARDS[replacement["resolved_id"]])
        c.update(id=base_id,base_id=base_id)
        # A resolved choice still occupies the original selectable slot.
        c["category"]=CARDS[base_id]["category"]
        c["selectable"]=CARDS[base_id]["selectable"]
    else:
        c=deepcopy(source)
    if c["side"]=="plant" and c["category"]!="secret":
        if "secret:咖啡" in s and base_id=="plant:咖啡豆":
            c.update(cost=50,native_cost=50,native_cd=750)
        if "secret:三向蓝火" in s and base_id=="plant:三向射手":
            # The original engine still reports 450 here; the PvP price is the
            # ordinary one plus the 多向蓝火 surcharge applied below.
            c.update(native_cost=450,projectile_asset="火豆")
        if "secret:速植" in s and c.get("native_cd") is not None:
            c["native_cd"]*=FAST_PLANT_COOLDOWN_FACTOR
        if "secret:硬化" in s and c.get("native_hp") is not None:
            if c["native_hp"] > HARDENING_MIN_BASE_HP:
                c["native_hp"]*=HARDENING_HP_FACTOR
            elif c["native_hp"] == HARDENING_MIN_BASE_HP:
                c["native_hp"]+=3
    if c.get("native_cd") is not None:
        c["native_deploy_cd"]=0 if c["side"]=="zombie" and not c.get('expansion') else c["native_cd"]
        c["cooldown"]=c["native_deploy_cd"]/250.
    if c.get("native_hp") is not None:c["hp"]=c["native_hp"]
    # PvP health override.  Kept apart from native_hp so the engine-evidence
    # parity test keeps seeing the engine's own number.  Hardening has to be
    # folded in here too: it scales whatever base the plant ended up with, and
    # the deployed object gets HEALTH x factor from `_apply_pvp_health`, so
    # letting the override overwrite the hardened number would leave the
    # catalogue showing 18 for a plant that fights at 22.5.
    if base_id in HEALTH and c["resolved_id"]==base_id or c["resolved_id"]=="plant:石果子":
        c["hp"]=HEALTH[c["resolved_id"]]
        if base_id=="plant:路灯花" and "secret:光疗" in s:
            c["hp"]*=2
        if c['side']=='plant' and "secret:硬化" in s:
            c["hp"]=c["hp"]*HARDENING_HP_FACTOR if c["hp"]>HARDENING_MIN_BASE_HP else c["hp"]+3
    if base_id in COSTS and c["resolved_id"]==base_id:
        c["cost"] = COSTS[base_id]
    c["cost"] = _multi_blue_cost(base_id, c["cost"], s)
    if base_id=="plant:胆小菇" and "secret:胆大" in s:
        c["cost"]+=25
    # PvP66 plant secret enhancements (pvp66_secrets).
    if base_id=="plant:杨桃" and "secret:大帝" in s:
        c["cost"]=STARFRUIT_COST
    if c.get("resolved_id")=="plant:龙蒺藜":
        c["hp"]=18.
    if base_id=="plant:海蘑菇" and "secret:水兵" in s:
        c["allow_air"]=True
        c["cost"]+=SEA_SHROOM_SURCHARGE
        for field in ('description','native_description'):
            c[field]=c.get(field,'')+'水兵：无法选中，种植冷却翻倍。'
    if base_id=="plant:小喷菇" and "secret:小喷" in s:
        c["cost"]+=25
    if base_id=="plant:抓人草" and "secret:触手" in s:
        c["cost"]+=50       # 触手秘籍 (three tentacles) surcharge
    if base_id in PLANT_COOLDOWNS:
        c["cooldown"] = PLANT_COOLDOWNS[base_id] * (FAST_PLANT_COOLDOWN_FACTOR if "secret:速植" in s else 1.)
    if base_id=="plant:海蘑菇" and "secret:水兵" in s:
        c["cooldown"]*=2
    if base_id in ("plant:土豆地雷","plant:原始土豆地雷") and "secret:地雷" in s:
        c["cooldown"]*=.75
    if base_id=="plant:魅惑菇" and "secret:魅惑" in s:
        c["cooldown"]*=.25
    if base_id=="plant:模仿者" and IMITATE_SECRET in s:
        c["cooldown"]*=IMITATE_COOLDOWN_FACTOR      # 71002 肆意模仿
    if base_id in ZOMBIE_COOLDOWNS:c["cooldown"] = ZOMBIE_COOLDOWNS[base_id]
    if night and c["side"]=="plant" and c.get("mushroom"):c["cost"]+=25
    if night and base_id in ("plant:向日葵","plant:双子向日葵","zombie:脑光墓碑","zombie:双生脑光墓碑","zombie:水上脑光墓碑","zombie:水上双生脑光墓碑"):c["period"]=20.
    if c["side"]=="zombie":c=_zombie_secret_card(c,base_id,s)
    if base_id=='plant:火爆辣椒':c['damage']=750.
    c["native_secret_names"]=[CARDS[k]["native_secret_name"] for k in sorted(s)
                              if k in CARDS and CARDS[k]["category"]=="secret" and CARDS[k]["side"]=="plant"]
    return c


def native_secret_names(secrets=(), bans=()):
    """Strict conversion of selected secret IDs to the original engine names."""
    if not isinstance(secrets,(list,tuple,set,frozenset)):
        raise ValueError("秘籍必须是所选秘籍 ID 的集合")
    result=[]
    for key in secrets:
        if not isinstance(key,str) or not allowed(key,bans) or CARDS[key]["category"]!="secret":
            raise ValueError("秘籍不可用："+str(key)[:80])
        if CARDS[key]["side"]!="plant":continue   # zombie secrets: zombie_secrets.py
        name=CARDS[key]["native_secret_name"]
        if name not in result:result.append(name)
    return sorted(result)


def resolve_card(card_id, secrets=(), bans=(), night=False):
    """Authorize every direct, copied or summoned entity before native creation.

    Only catalogue IDs are accepted. Both precursor and resolved form are checked;
    a secret form cannot be injected as a standalone copy/summon or forged dict.
    Inventory, resource, cooldown and placement checks belong to the host caller.
    """
    names=native_secret_names(secrets,bans)
    if not isinstance(card_id,str) or not allowed(card_id,bans,for_spawn=True,secrets=secrets):
        raise ValueError("生成卡牌不可用")
    if CARDS[card_id]["category"]=="secret":
        raise ValueError("秘籍为常驻卡槽，不能生成实体")
    c=actual_card(card_id,secrets,night)
    if not allowed(c["base_id"],bans,for_spawn=True,secrets=secrets):
        raise ValueError("基础卡牌已被禁用")
    if c["resolved_id"]!=c["base_id"] and not allowed(c["resolved_id"],bans,for_spawn=True,secrets=secrets):
        raise ValueError("派生形态缺少秘籍或已被禁用")
    c["native_secret_names"]=names
    return c


def describe(card_id, secrets=(), night=False, detailed=True):
    """Native card text and actual deployment values, plus explicit PvP rules."""
    c=actual_card(card_id,secrets,night)
    if not detailed:
        from .almanac_text import brief
        return brief(c)
    if c["category"]=="secret":
        return c["description"]+"\n常驻，占 1 个"+("僵尸" if c["side"]=="zombie" else "植物")+"卡槽。"+("\n需要携带："+CARDS[c["dependency"]]["name"] if c.get("dependency") else "")
    lines=["费用 %d · 冷却 %.1f 秒"%(c["cost"],c["cooldown"])]
    lines.append("开局冷却 %.1f 秒" % initial_cooldown(c["cooldown"]))
    if night and c.get("mushroom"):lines.append("夜晚蘑菇费用已增加 25。")
    lines.append("死斗部署冷却 %.1f 秒" % deployment_cooldown(c,True))
    if c["resolved_id"]!=c["base_id"]:
        lines.insert(0,CARDS[c["base_id"]]["name"]+" → "+c["name"])
    hp=c.get("hp") if c.get("hp") is not None else c.get("native_hp")
    if hp is not None and c["behavior"] not in ("coffee","stone","grass","copy"):
        lines.append("生命 %g"%hp)
    absorb=ABSORB_TICKS.get(c["name"])
    if absorb:
        lines.append("每 %.0f 秒吸取一次金属防具。"%(absorb/250.))
    if c.get("native_armor_hp") or c.get("native_handheld_hp"):
        lines.append("头顶防具 %g · 手持物 %g"%(c.get("native_armor_hp") or 0,c.get("native_handheld_hp") or 0))
    if c.get("riding_armor_hp"):
        lines.append("背上小鬼防具 %g（独立受赠者，可被磁力单独取下）"%c["riding_armor_hp"])
    if c["behavior"]=="grave":
        if c.get("producer"):
            lines.append("每 %.1f 秒产出 %d 脑光"%(c["period"],c["yield_amount"]))
            if c.get("mature_at"):lines.append("自然成长 %.0f 秒后每次产出 %d"%(c["mature_at"],c["mature_yield"]))
            surface = c.get('grave_surface', 'auto')
            lines.append(("地面、水面或己方墓碑上放置，水面上不带救生圈。" if c.get('shell') else
                          "只可地面放置，不自动转换水面形态。" if surface=='land' else
                          "只可水面放置，自带鸭子救生圈。" if surface=='water' else
                          "地面或水面放置；水上自动携带鸭子救生圈并浮在水面。") +
                         "可被植物攻击，作为僵尸出兵点，脑光自动收集。")
            lines.append("白天全局补给：第%g秒起，每%g秒自动补充%d脑光，不占卡槽；夜晚无补给，死斗不加速。"%
                         (RULES["day_brain_interval"],RULES["day_brain_interval"],RULES["day_brain_amount"]))
            if c['base_id'] in BASIC_GRAVES:
                lines.append("脑光墓碑和成长脑光墓碑最多禁用一个；有水地图也只保护这两种基础陆地型。")
            elif surface=='water':
                lines.append("水系墓碑不享受基础陆地墓碑的禁选保护。")
        elif c.get("description"):lines.append(c["description"])
    else:
        original=c.get("native_description")
        if original:lines.append(original)
        elif c.get("native_source","").startswith("marshal"):
            lines.append("沿用原"+c["name"]+"的移动、攻击、装备与受击机制。")
        elif c.get("description"):lines.append(c["description"])
    if c.get("producer"):
        lines.append("本局前%g秒数值伤害减少%g%%，不分昼夜或天气；后种不会重新计时。"%
                     (RULES["producer_protection_seconds"],(1-RULES["producer_protection_multiplier"])*100))
        lines.append("模仿者复制后沿用本局截止时间。吞噬、碾压、直接焚毁及自然退场、铲除保留原机制。")
        if c.get("first_production"):lines.append("种植后 6 秒首次生产；之后每 %.0f 秒生产。" % c["period"])
        from .balance import DEATHMATCH_ALLOWED_PRODUCERS
        if c["base_id"] in DEATHMATCH_ALLOWED_PRODUCERS:
            lines.append("死斗期间仍可放置；已有生产单位按原生产逻辑提速 1.5 倍。")
        else:
            lines.append("7 分钟后禁止新增；已有生产单位按原生产逻辑提速 1.5 倍。")
    if c["base_id"]=="zombie:坚固脑光墓碑":
        lines.append("携带后僵尸戴夫生命上限 +8（48）；濒死气球在生命降到 12 时触发，每局一次。")
    if c["base_id"]=="plant:土豆地雷":
        lines.append("对战出土时间 16 秒；携带地雷秘籍时为 8 秒，部署冷却额外减少 25%。")
    if c["base_id"]=="plant:地刺" and "secret:地刺" in secrets:
        lines.append("地刺秘籍下，每次成功种植后下一株费用减少 %d，最低 %d 阳光。" %
                     (SPIKE_SECRET_STEP, SPIKE_SECRET_MIN_COST))
    if c["behavior"] in ("ash","doom","chili","squash","mine","chomp","cannon","suicide"):
        lines.append("英雄受到单攻击来源伤害上限保护，不会被一轮灰烬或吞噬直接击杀。")
    if c["base_id"]=="plant:香蒲":
        lines.append("优先追踪最近目标；追踪英雄需要合法近距标记和视线，对僵尸戴夫每发2伤害，命中不刷新英雄标记。")
    if c["base_id"]=="plant:吸金磁":
        lines.append("对战中金币不转换为阳光。")
    if c["base_id"]=="plant:裂荚射手" and "secret:豌豆杂交" in secrets:
        lines.append("豌豆杂交：前后两颗头分别朝各自前方上下 45 度瞄准；镜像朝向下同样生效。")
    if c["base_id"]=="plant:模仿者":
        lines.append("默认复制上一次成功种下的可复制植物；通过模仿目标按键切换已携带目标（默认 V，可在设置改键）。不能复制工具、秘籍或墓碑吞噬者，仍验证秘籍、禁选与死斗生产限制。")
    if c["base_id"]=="zombie:墓碑吞噬者僵尸":
        lines.append("死亡释放的骨头按死神僵尸骨头规则落地：水面、已有植物或下方无实体方块时不生成墓碑；昼夜均生效；魅惑后的派生植物仍受禁选限制。")
    if c["base_id"]=="zombie:毁灭菇僵尸":
        lines.append("对战自动自爆寿命 %g tick（原补丁按每秒60 tick累计，约 %g 秒）。" %
                     (DOOM_ZOMBIE_AUTO_EXPLODE_TICKS, DOOM_ZOMBIE_AUTO_EXPLODE_TICKS / 60.))
        lines.append("对战爆炸按当前阵营过滤友伤，不继承植物方核平强化。")
    if c["base_id"]=="zombie:吸金磁僵尸":
        lines.append("对战中赠予其它僵尸的铁桶固定为 %d 生命。" % GOLD_MAGNET_BUCKET_HP)
    from .pvp59_catalog import NOTES as _PVP59_NOTES, GRAVE_IDLE_NOTE
    if c["base_id"] in _PVP59_NOTES:lines.append(_PVP59_NOTES[c["base_id"]])
    if c["behavior"]=="grave" and c.get("producer"):lines.append(GRAVE_IDLE_NOTE)
    if c.get("ban_protected"):lines.append("不可禁选；仍须满足地形条件，死斗部署冷却按上述数值计算。")
    if c.get("required_secret"):
        lines.append("由本方秘籍替换基础卡；复制、召唤同样需要该秘籍并继承前体禁选。")
    elif c.get("spawn_only"):lines.append("战斗派生实体，不可作为独立卡槽选择。")
    if c["side"]=="zombie" and c["behavior"]!="grave":
        lines.append("与敌对僵尸互相攻击时，普通数值伤害为对应植物伤害的10倍，魅惑前后对称；吞噬、碾压和灰烬等特殊消灭沿用各自机制。")
        if c["base_id"] in ("zombie:豌豆僵尸","zombie:机枪僵尸"):
            lines.append("豌豆对植物普通/红火/蓝火直击2/4/6，对敌对僵尸20/40/60；火焰溅射为直击的1/3。")
        if c["base_id"]=="zombie:投篮车僵尸":
            lines.append("篮球对植物2伤害，对敌对僵尸20伤害；魅惑后也可命中敌方僵尸，不伤害己方植物。")
        if c["base_id"]=="zombie:飞贼僵尸":
            lines.append("选择存活的敌方植物召唤，不要求先选择墓碑；保留原下降与偷取行为。")
        else:lines.append("从己方存活墓碑出场，服从跟随 / 进攻指挥。")
        if c["base_id"]=="zombie:旗帜僵尸":
            lines.append("部署后每座存活、出口可用的己方墓碑额外召唤一只普通僵尸；不额外扣费，召唤不受禁选影响，仍遵守单位上限。")
    return "\n".join(lines)
