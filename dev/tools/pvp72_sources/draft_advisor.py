"""Deterministic draft suggestions, with map, dependencies and role coverage."""
from .catalog import CARDS, RULES, allowed, map_card_error, starter_grave, starting_resource
from .room import Room


def _roles(c):
    roles=set()
    name=c['name']; behavior=c.get('behavior','')
    if c.get('producer'):roles.add('经济')
    if (c.get('damage') or 0)>0 and behavior not in ('grave','produce'):
        roles.add('输出')
        if c['cost']<=100:roles.add('前期')
    if behavior in ('ash','doom','chili','squash','mine','suicide','ghost'):roles.add('应急')
    if c.get('splash') or c.get('pierce') or c.get('star') or c.get('radial') or '大喷菇' in name or name in ('幽灵辣椒','芦笋战机','旋转芜菁'):roles.add('群攻')
    if c.get('anti_air') or c.get('homing') or name in ('香蒲','杨桃','仙人掌','旋转芜菁','芦笋战机','三叶草'):roles.add('对空')
    if c.get('slow') or c.get('butter') or behavior in ('freeze','garlic','charm'):roles.add('控制')
    if (c.get('hp') or 0)>=400 or behavior=='wall':roles.add('承伤')
    if c.get('flying') or c.get('vault') or '矿工' in name or '梯子' in name:roles.add('突破')
    if behavior in ('magnet','gold_magnet') or name in ('磁力菇','吸金磁','雷蘑菇'):roles.add('破甲')
    if c.get('aquatic') or c.get('requires_water'):roles.add('水域')
    if name in ('花盆','石块','草坪','睡莲','梯子僵尸','传送带僵尸'):roles.add('地形')
    # PvP64 cards whose role is not visible from their numbers alone.
    extra={'甜薯':('承伤','控制'),'弹簧草':('控制','前期'),'豌豆迫击炮':('群攻',),
           '原始土豆地雷':('应急','群攻'),'传送带僵尸':('突破',),'掷弹兵僵尸':('应急','前期'),
           '史莱姆僵尸':('承伤',),'红眼巨人':('承伤','突破')}
    roles.update(extra.get(name,()))
    return roles


def recommend(view, side, preferred=None):
    """Keep locked cards, then fill legal slots with explained complementary picks."""
    terrain=view.get('map') or view.get('terrain') or {}
    if hasattr(terrain,'to_dict'):terrain=terrain.to_dict()
    rules=view.get('rules') or RULES; bans=view.get('bans') or []
    limit=rules.get(side+'_slots',7); locked=list((view.get('decks') or {}).get(side,[]))
    deck=list(dict.fromkeys(locked)); reasons={k:'已锁定，保留阵容位置' for k in deck}
    tiles=terrain.get('tiles',[]); wet=any(c.get('water') for row in tiles for c in row)
    night=bool(terrain.get('environment',{}).get('night'))
    opponent=(view.get('decks') or {}).get('zombie' if side=='plant' else 'plant',[])
    enemy=[CARDS[k] for k in opponent if k in CARDS]
    armored=any(c.get('metal') or c.get('armor') or c.get('armor2') for c in enemy)
    flying=any(c.get('flying') or '气球' in c['name'] for c in enemy)
    walls=any(c.get('behavior')=='wall' or (c.get('hp') or 0)>=1000 for c in enemy)
    budget=starting_resource('zombie',rules,terrain)
    # A locked 水盆 (PvP70) makes aquatic plants legal on a dry map.
    legal={k:c for k,c in CARDS.items() if c['side']==side and allowed(k,bans) and not map_card_error(k,terrain,deck)}
    preferences=set(preferred or [])
    weights={'经济':35,'输出':26,'前期':24,'应急':20,'群攻':18,'控制':12,'承伤':12,'对空':12,'突破':18,'破甲':4,'地形':10,'水域':8 if wet else 0}
    if flying:weights['对空']=45
    if armored:weights['破甲']=32
    if walls:weights['突破']=35
    # Cheap cards with broad uses are preferred inside each role, without
    # forcing the same seven cards after a ban or a terrain change.
    base={'黄金蓓蕾':22,'向日葵':12,'阳光菇':20 if night else -45,
          '豌豆射手':10,'幽灵辣椒':14,'旋转芜菁':12,'芦笋战机':10,
          '坚果':10,'土豆地雷':8,'寒冰射手':7,'磁力菇':5,
          '脑光墓碑':18,'成长脑光墓碑':14,'水上脑光墓碑':20 if wet else -80,
          '水上成长脑光墓碑':16 if wet else -80,'普通僵尸':15,'路障僵尸':12,
          '垃圾桶僵尸':12,'梯子僵尸':8,'矿工僵尸':10,'舞王僵尸':9}

    def closure(key):
        todo=[key]; added=[]
        while todo:
            k=todo.pop()
            if k in deck or k in added:continue
            if k not in legal:return None
            added.append(k)
            dep=legal[k].get('dependency')
            if dep:todo.append(dep)
            if not night and legal[k].get('mushroom'):todo.append('plant:咖啡豆')
        return list(reversed(added))

    def reserve_ok(candidate):
        free=limit-len(candidate)
        if free<0:return False
        if side=='zombie' and not any(starter_grave(k,budget) for k in candidate):
            if free<1 or not any(starter_grave(k,budget) for k in legal):return False
        if side=='plant' and night and any(CARDS[k].get('dependency') for k in candidate):
            if not any(CARDS[k].get('producer') for k in candidate):
                if free<1 or not any(c.get('producer') for c in legal.values()):return False
        return True

    # Fill prerequisite closures first, including a precursor chosen on a
    # previous turn. Newly banned or malformed saved cards cannot be suggested.
    for key in list(deck):
        dependencies=[CARDS.get(key,{}).get('dependency')]
        if not night and CARDS.get(key,{}).get('mushroom'):dependencies.append('plant:咖啡豆')
        for dep in dependencies:
            bundle=closure(dep) if dep and dep not in deck else None
            if bundle and reserve_ok(deck+bundle):
                for k in bundle:deck.append(k); reasons[k]='白天唤醒蘑菇' if k=='plant:咖啡豆' else '补齐已选秘籍前体'
    while len(deck)<limit:
        covered={r for k in deck if k in CARDS for r in _roles(CARDS[k])}
        candidates=[]
        for key,c in legal.items():
            if key in deck:continue
            bundle=closure(key)
            if not bundle or not reserve_ok(deck+bundle):continue
            roles=_roles(c); missing=roles-covered
            score=sum(weights.get(r,0) for r in missing)+base.get(c['name'],0)-c['cost']/30.
            score-=max(0,len(bundle)-1)*20
            if c['category']=='secret':score-=6
            if c.get('mushroom') and not night and 'plant:咖啡豆' not in deck:score-=25
            if '经济' in roles and '经济' in covered:score-=45
            if '地形' in roles and '地形' in covered:score-=25
            if key in preferences:score+=16
            if side=='zombie' and not any(starter_grave(k,budget) for k in deck) and starter_grave(key,budget):score+=150
            if side=='plant' and '经济' not in covered and c.get('producer'):score+=25
            detail='补充'+('、'.join(sorted(missing)) if missing else '持续作战能力')
            if flying and '对空' in missing:detail='应对对方已选飞行单位'
            elif armored and '破甲' in missing:detail='应对对方已选金属防具'
            elif walls and '突破' in missing:detail='绕过对方高血量防线'
            elif starter_grave(key,budget):detail='开局资源可负担，提供脑光和出兵口'
            elif c.get('producer'):detail='补充'+('夜间' if night else '持续')+'经济'
            if c.get('requires_water'):detail+='；适合本图水域'
            candidates.append((score,key,bundle,detail))
        if not candidates:break
        _,key,bundle,detail=sorted(candidates,key=lambda item:(-item[0],item[1]))[0]
        for k in bundle:
            deck.append(k);reasons[k]=detail if k==key else '白天唤醒蘑菇' if k=='plant:咖啡豆' else '搭配秘籍所需前体'
    env=('黑夜' if night else '白天')+(' · 有水域' if wet else ' · 陆地')
    summary=env+'；按经济、前期作战与对方已选卡补齐阵容'
    if len(deck)<limit:summary+='；当前禁选或前体限制使阵容未能补满'
    return dict(deck=deck,reasons=reasons,summary=summary)


# ---------------------------------------------------------------- PvP66 AI
class _DraftRoom(Room):
    """Just enough of Room for the built-in AI draft evaluator, built from a view."""

    def __init__(self, view):
        from .maps import MapSnapshot
        from .room import Room
        terrain = view.get('map') or view.get('terrain') or {}
        self.map = terrain if hasattr(terrain, 'to_dict') else MapSnapshot.from_dict(terrain)
        self.rules = dict(view.get('rules') or RULES)
        self.bans = list(view.get('bans') or [])
        self.decks = {s: list(d) for s, d in (view.get('decks') or {}).items()}
        self.decks.setdefault('plant', []);self.decks.setdefault('zombie', [])
        self.draft_index = 0
        self._draft_map_hash = None;self._draft_map_errors = {}
        self.mode=view.get('mode','duel')

    def _map_error(self, key):
        return super()._map_error(key)

    def _deck_map_error(self, key, deck):
        return super()._deck_map_error(key, deck)

    def _completion_error(self, side, deck, bans=None):
        return super()._completion_error(side, deck, bans)


_AI_CACHE = {}


def ai_complete(view, side, preferred=None):
    """The built-in AI's (r13 draft evaluator) best legal completion and per-card gains."""
    from .rv_r22 import Drafter
    from .rv_draft13 import DEAD_WEIGHT, ANTIAIR_WEIGHT
    from .rv_draft66 import SECRETS66_WEIGHT, TEAM66_WEIGHT
    from .catalog import rules_hash, catalog_hash
    room = _DraftRoom(view)
    foe = 'zombie' if side == 'plant' else 'plant'
    key = (side, room.mode, room.map.terrain_hash, tuple(room.bans), tuple(room.decks[side]), tuple(room.decks[foe]),
           rules_hash(room.rules),catalog_hash(),tuple(preferred or ()))
    if key in _AI_CACHE:
        return _AI_CACHE[key]
    drafter = Drafter(side, '选卡知识65.json', 0, None, {'margin': 0., 'temp': 0., 'taste': 0.})
    weights = {'recurring':45., 'potted':30., 'graves2':30., 'dead':DEAD_WEIGHT,
               'secrets66':SECRETS66_WEIGHT,'team66':TEAM66_WEIGHT,'antiair66':ANTIAIR_WEIGHT}
    weights.update(drafter.extra_weights)
    drafter.room = room
    drafter.ev = drafter.evaluator(room, drafter.kb_path, 'none', weights)
    drafter.completed = {};drafter.legal_cache = {};drafter.cerr={}
    mine, enemy = list(room.decks[side]), room.decks[foe]
    for card in preferred or ():
        if card not in mine and card in CARDS and not room._completion_error(side,mine+[card]):
            mine.append(card)
    enemy_guess = drafter.complete(foe, enemy, mine, room.bans, branches=1)
    full = drafter.complete(side, mine, enemy_guess, room.bans, branches=2)
    total = drafter.ev.value(side, full, enemy_guess)
    gains = {}
    for k in full:
        rest = [x for x in full if x != k]
        gains[k] = round(total - drafter.ev.value(side, rest, enemy_guess), 1)
    result = (full, gains, enemy_guess)
    if len(_AI_CACHE) > 32:
        _AI_CACHE.clear()
    _AI_CACHE[key] = result
    return result


def recommend_ai(view, side, preferred=None, seat=None):
    """Heuristic explanations on top of the AI's own choice of cards."""
    # Evaluate the requesting seat's own locked cards and reserve cards which
    # only its teammate may carry; do not confuse faction with seat 2.
    from .teams import team_of
    from .catalog import team_repeatable
    seat=seat or side;side=team_of(seat)
    decks=view.get('decks') or {}
    mate=side+'2' if seat==side else side
    scoped=dict(view,decks=dict(decks))
    scoped['decks'][side]=list(decks.get(seat,()))
    scoped['bans']=list(view.get('bans') or ())
    if view.get('mode')=='duo':
        scoped['bans'] += [k for k in decks.get(mate,()) if not team_repeatable(k)]
    view=scoped
    base = recommend(view, side, preferred)
    try:
        full, gains, enemy_guess = ai_complete(view, side, preferred)
    except Exception as exc:
        base['summary']+='；AI评估暂不可用：'+str(exc)[:100]
        return base
    locked = list((view.get('decks') or {}).get(side, []))
    reasons = {}
    for k in full:
        if k in locked:
            reasons[k] = '已锁定，保留阵容位置'
            continue
        roles = '、'.join(sorted(_roles(CARDS[k]))) or '综合'
        if CARDS[k]['category'] == 'secret':
            text = (CARDS[k].get('description') or '').split('。')[0]
            why = '秘籍：' + (text[:22] + '…' if len(text) > 22 else text)
        else:
            why = base['reasons'].get(k) if k in base['deck'] else '补充' + roles
        reasons[k] = '%s · 阵容评估贡献 %+.0f' % (why, gains.get(k, 0.))
    guess = [CARDS[k]['name'] for k in enemy_guess if k in CARDS][:4]
    summary = base['summary'].split('；')[0] + '；由内置 AI（大厅房间同款选卡评估：昼夜/地形修正、实战使用率、对手回应推演）补全'
    if guess:
        summary += '；预计对方：' + '、'.join(guess)
    return dict(deck=full, reasons=reasons, summary=summary, ai=True)
