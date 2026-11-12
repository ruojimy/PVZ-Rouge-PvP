"""PvP58 cards: two shell vines, the petrified vine grave and two secrets."""
from copy import deepcopy

SUN_VINE = '阳光藤蔓'
PUFF_VINE = '忧郁藤蔓'
GRAVE_VINE = '石化藤蔓'
PLANT_VINES = (SUN_VINE, PUFF_VINE, '抓人草')
VINE_PERIOD = 16.
VINE_FIRST = 6.
VINE_YIELD = 15
DENSE_SECRET = 'secret:密植'
DENSE_PLANT_LIMIT = 3
MASOCHIST_SECRET = 'secret:抖M'
TURN_SECRET = 'secret:转向'
MASOCHIST_EARLY_SECONDS = 120.
MASOCHIST_EARLY_SUN = 15
MASOCHIST_LATE_SUN = 25
MASOCHIST_COOLDOWN = 3.
# Native Dave stands up once 玩家恢复 passes 2000 frames (8 s at 250 Hz);
# with 抖M the knocked-down Dave starts rising after 3 s.
NATIVE_RISE_FRAMES = 2000
MASOCHIST_RISE_FRAMES = 1000

SHELL_RULE = ('与南瓜头同为保护壳层：可直接种在己方植物上（含空中的飞行植物），每格至多一个南瓜头或藤蔓；'
              '僵尸优先攻击壳层。铲子左键先铲藤蔓，右键跳过藤蔓与南瓜头。'
              '也可直接种在水面上，此后该水面格可像睡莲一样种植其它植物（睡莲在水下格，藤蔓在水面格）。')
DESCRIPTIONS = {
    SUN_VINE: ('25阳光，20秒冷却，6生命。种下6秒首次生产，之后每16秒生产15阳光。' + SHELL_RULE +
               '属于生产单位：前80秒减伤、死斗禁止新增与1.5倍生产、金盏花加速均适用。'),
    PUFF_VINE: ('25阳光，20秒冷却，6生命。完全按小喷菇向面朝方向吐泡泡：同样的索敌距离、伤害与8格弹幕清除，'
                '享受毒气秘籍与金盏花加速；不是蘑菇，白天不睡觉，不受小喷秘籍影响。'
                '种在蘑菇或沉睡植物上时永久唤醒同格植物。' + SHELL_RULE),
    GRAVE_VINE: ('25脑光，20秒冷却，30生命。种下6秒首次生产，之后每16秒生产15脑光。'
                 '可直接种在水面或己方墓碑上，每格至多一个石化藤蔓。种在水面后，该处可再放陆地墓碑；'
                 '水上墓碑可放在其中，也可先放水上墓碑再放石化藤蔓。'
                 '可被植物攻击和墓碑吞噬者吞掉，作为僵尸出兵点。'),
}


def install(cards):
    added = {}
    for name, template in ((SUN_VINE, '坚果'), (PUFF_VINE, '小喷菇')):
        key = 'plant:' + name
        card = deepcopy(cards['plant:南瓜头'])
        card.update(id=key, base_id=key, resolved_id=key, family=key, name=name,
                    asset=name, native_name=name, native_input_name=template,
                    content=name, content_art='vine58', behavior='vine', category='tool',
                    cost=25, native_cost=25, cooldown=20., native_cd=5000, native_deploy_cd=5000,
                    hp=6, native_hp=6, mushroom=False, shell=True, height=44,
                    producer=name == SUN_VINE, ban_protected=False, selectable=True, spawn_only=False,
                    pvp_added=True, native_source='PvP58 shell vine on a native plant record',
                    description=DESCRIPTIONS[name], native_description=DESCRIPTIONS[name])
        if name == SUN_VINE:
            card.update(economy='periodic_sun', period=VINE_PERIOD, yield_amount=VINE_YIELD,
                        first_production=VINE_FIRST, damage=0, interval=0.)
        else:
            card.update(damage=cards['plant:小喷菇']['damage'], interval=cards['plant:小喷菇']['interval'],
                        range=cards['plant:小喷菇']['range'], economy='none', gas_family=True)
        added[key] = card
    key = 'zombie:' + GRAVE_VINE
    card = deepcopy(cards['zombie:脑光墓碑'])
    card.update(id=key, base_id=key, resolved_id=key, family=key, name=GRAVE_VINE,
                asset=GRAVE_VINE, native_name=GRAVE_VINE, native_input_name='普通僵尸',
                cost=25, cooldown=20., native_cd=5000, native_deploy_cd=5000, hp=30,
                producer=True, economy='periodic_brain', period=VINE_PERIOD, yield_amount=VINE_YIELD,
                first_production=VINE_FIRST, behavior='grave', category='economy',
                expansion=GRAVE_VINE, grave_surface='auto', shell=True, requires_water=False,
                selectable=True, spawn_only=False, ban_protected=False, pvp_added=True,
                native_source='PvP58 grave shell on the native grave record',
                description=DESCRIPTIONS[GRAVE_VINE], native_description=DESCRIPTIONS[GRAVE_VINE])
    card.pop('mature_at', None); card.pop('mature_yield', None); card.pop('mature_hp', None)
    added[key] = card
    ordered = {}
    for key, value in cards.items():
        ordered[key] = value
        if key == 'plant:睡莲':
            ordered.update((k, added.pop(k)) for k in ('plant:' + SUN_VINE, 'plant:' + PUFF_VINE))
        if key == 'zombie:石化火炬':
            ordered['zombie:' + GRAVE_VINE] = added.pop('zombie:' + GRAVE_VINE)
    ordered.update(added)
    cards.clear(); cards.update(ordered)
    for key, desc in (
        (DENSE_SECRET, '同一格最多种植3个主体植物，另可额外种植1个南瓜头或藤蔓（两者共享保护壳名额）；'
                       '同格内后种的植物优先被攻击，地形条件仍按原版判断。'
                       '咖啡豆不占主体或保护壳名额，可独立种在含沉睡植物的满额格子上，一次唤醒同格全部沉睡植物。'),
        (MASOCHIST_SECRET, '植物方戴夫受到伤害时获得阳光：本局前2分钟每次15阳光，之后每次25阳光；'
                           '两次奖励至少间隔3秒。被击倒后4秒即开始起身（原为8秒）。'),
        (TURN_SECRET, '空手再次点击己方存活植物可改变朝向：鼠标左键向左、右键向右，与种植时相同；'
                      '触屏使用种植朝向设置。同格所有己方植物一起转向，包括密植主体、南瓜头、藤蔓及待变身模仿者；'
                      '不消耗阳光或卡片冷却。铲子、传送、玉米炮操作优先。')):
        card = deepcopy(cards['secret:补光'])
        name = key.split(':', 1)[1]
        card.update(id=key, base_id=key, resolved_id=key, family=key, name=name,
                    asset={DENSE_SECRET:'密植', MASOCHIST_SECRET:'疯狂戴夫', TURN_SECRET:'裂荚射手'}[key], native_secret_name=name,
                    dependency='', economy='none', effect={DENSE_SECRET:'dense', MASOCHIST_SECRET:'masochist', TURN_SECRET:'turn'}[key],
                    pvp_added=True, description=desc, native_description=desc)
        cards[key] = card
