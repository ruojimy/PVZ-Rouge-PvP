"""PvP71 additions (71002). Stable IDs are shared by draft, native play and replay."""
from copy import deepcopy

IMITATE_SECRET = 'secret:肆意模仿'
IMITATER = 'plant:模仿者'
IMITATE_COOLDOWN_FACTOR = .5
IMITATE_TEXT = '模仿者部署冷却减半（80秒→40秒），阳光消耗为当前模仿目标的实际费用减100，可为负值以获得阳光；目标的其他秘籍与昼夜费用修正一并计入。锁定前体：模仿者。变身时间不变，复制出的植物仍是灰色。'
# How a zombie Dave becomes trackable for the cattail family (native_battle._hero_lock).
MARK_TEXT = ('标记：僵尸戴夫受伤后3秒内、或位于路灯花或站立的植物戴夫约2.75格内且可见时视为被标记；'
             '香蒲与猫尾秘籍只能在标记期间、近距且可见时锁定僵尸戴夫。')


def install(cards):
    c = deepcopy(cards['secret:补光'])
    c.update(id=IMITATE_SECRET, base_id=IMITATE_SECRET, resolved_id=IMITATE_SECRET,
             family=IMITATE_SECRET, name='肆意模仿', native_secret_name='肆意模仿', asset='模仿者',
             dependency=IMITATER, targets=[IMITATER], effect='imitate_cooldown', economy='none',
             pvp_added=True, description=IMITATE_TEXT, native_description=IMITATE_TEXT)
    cards[IMITATE_SECRET] = c
    for key, note in (('plant:香蒲', MARK_TEXT), ('secret:猫尾', MARK_TEXT),
                      (IMITATER, '携带肆意模仿秘籍时部署冷却减半。')):
        for field in ('description', 'native_description'):
            cards[key][field] = cards[key].get(field, '') + note
