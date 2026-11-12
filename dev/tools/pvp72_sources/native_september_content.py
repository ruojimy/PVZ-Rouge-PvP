"""PvP54 native records: haunting pepper, one-shot bloom and two zombies."""
import copy
import math
from contextlib import contextmanager

from .native_gate import replace_predicate
from .native_physics import TRACKING_KEYS
from .simulation import wrap_delta
from .teams import team_of
from .pvp56_plants_catalog import AIR_PLANTS

PLANTS = ('幽灵辣椒', '黄金蓓蕾')
ZOMBIES = ('雪人僵尸', '垃圾桶僵尸')


class SeptemberContent:
    def __init__(self, content):
        self.c = content
        self.b = content.b
        self.g = content.g
        self.paths = {}
        self.effects = []
        self.bloom_sun_amounts = {}
        # Native zombie attacks and basketball collisions query both the cell
        # marker and the original plant-index helpers. Keep the real plant and
        # its grid registration intact outside zombie-owned combat phases.
        for name in ('哪个植物', '哪个无南瓜植物'):
            original = self.g[name]
            def visible_plant(*args, _original=original, **kwargs):
                index = _original(*args, **kwargs)
                active = self.b.targets.active
                if not active or active['owner'] != 'zombie' or active['phase'] not in ('zombies', 'entities'):
                    return index
                if index == -1 or self.targetable(self.g['植物'][index]):
                    return index
                row, col = args[:2]
                return next((i for i, plant in enumerate(self.g['植物'])
                    if plant.get('坐标') == [row, col] and self.targetable(plant)), -1)
            self.g[name] = visible_plant
        # Keep the entire native status/health/one-shot maintenance loop. Only
        # its unsupported-air predicate changes, including pending imitators.
        self.g['_pvp_needs_plant_support'] = self.needs_support
        self.b.engine.regions['plants'] = replace_predicate(
            self.b.engine.regions['plants'], 121250, 121270,
            '_pvp_needs_plant_support', [
                ('LOAD_NAME','植物'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),
                ('LOAD_CONST','植物'),('BINARY_SUBSCR',None),
                ('LOAD_CONST',('花盆','墓碑吞噬者')),('COMPARE_OP','not in')])
        self.g['_pvp_supplement_death'] = self.supplement_death
        self.b.engine.regions['plant_maintenance'] = replace_predicate(
            self.b.engine.regions['plant_maintenance'],118280,118288,
            '_pvp_supplement_death',[
                ('LOAD_CONST','补光'),('LOAD_NAME','秘籍'),('COMPARE_OP','in')])
        # Reject acquisition as well as damage: otherwise the native melee
        # block spends its bite cooldown on the virtual path destination (or a
        # nearby real Dave) before the yeti reaches a plant's smaller hit box.
        self.g['_pvp_can_bite_dave'] = lambda: (self.g['模式']!='我是僵尸' and
            not self.g['僵尸'][self.g['l']].get('_pvp_no_hero_attack'))
        self.b.engine.regions['zombies'] = replace_predicate(
            self.b.engine.regions['zombies'],75136,75144,
            '_pvp_can_bite_dave',[
                ('LOAD_NAME','模式'),('LOAD_CONST','我是僵尸'),('COMPARE_OP','!=')])

    def supplement_death(self):
        zs = getattr(self.b, 'zsecrets', None)
        if zs is not None and zs.enabled:
            zs.on_plant_killed(self.g['植物'][self.g['l']])
        due = '补光' in self.g['秘籍'] and not self.g['植物'][self.g['l']].get('_pvp_transform_succeeded')
        if due and getattr(self.b, 'secrets66', None) is not None:
            self.b.secrets66.note_death_sun()
        return due

    def needs_support(self):
        p = self.g['植物'][self.g['l']]
        if p.get('植物') == '海蘑菇' and '水兵' in self.g['秘籍']:
            return False
        if p.get('_pvp_content') in AIR_PLANTS:
            return False
        if p.get('植物') == '模仿者' and p.get('_pvp_copy_card', '')[6:] in AIR_PLANTS:
            return False
        return p.get('植物') not in ('花盆', '墓碑吞噬者')

    @staticmethod
    def targetable(plant):
        return (plant.get('植物血', 0) > 0 and '死' not in plant and
                plant.get('_pvp_content') != '幽灵辣椒' and
                not (plant.get('植物') == '模仿者' and
                     plant.get('_pvp_copy_card', '') == 'plant:幽灵辣椒'))

    @contextmanager
    def hide_ghost_cells(self):
        hidden = []
        occupied = {tuple(p['坐标']) for p in self.g['植物'] if self.targetable(p)}
        for p in self.g['植物']:
            coord = tuple(p['坐标'])
            if (self.targetable(p) or coord in occupied or
                    p.get('_pvp_content') != '幽灵辣椒' and
                    not (p.get('植物') == '模仿者' and p.get('_pvp_copy_card', '') == 'plant:幽灵辣椒')):
                continue
            row, col = coord
            cell = self.g['ditu'][row][col]
            if '植物' in cell:
                hidden.append((cell, cell.pop('植物')))
        try:
            yield
        finally:
            for cell, marker in hidden:
                cell['植物'] = marker

    def configure(self, obj, card):
        name = card.get('content')
        if name not in PLANTS + ZOMBIES:
            return False
        obj['_pvp_content'] = name
        if name in PLANTS:
            # Independent species prevent template squash, sunflower bursts,
            # template death explosions and producer clocks from running.
            obj['植物'] = name
            obj['_pvp_one_shot'] = True
            obj['_pvp_content_age'] = 0
            obj['_pvp_effect_done'] = False
            obj.pop('爆了', None)
            return True
        obj['血量'] = float(card['native_hp'])
        obj['_pvp_max_hp'] = obj['血量']
        # The native lantern tracks observed maxima, so seed the new unit's
        # actual pool before an immediate first-frame hit can lower it.
        obj[self.b.patch.ns['__pvz_sb_K_ZOMBIE_OBSERVED_MAX_HP']] = obj['血量']
        if name == '雪人僵尸':
            obj['_pvp_no_hero_attack'] = True
        else:
            # Steel-door identity gives native type-II shielding, fire bypass,
            # magnet stripping and thunder stun. Only its visual is a bin.
            obj.update(手持='钢门', 手持血量=200.)
            obj['移速'] *= .25
        obj['_pvp_base_speed'] = obj['移速']
        return True

    def living_enemies(self, p):
        # One record per target; native plant-zombie heads are geometry, never
        # extra victims. Hero proxies are already de-duplicated by this helper.
        return self.c.enemies(p)

    def inside(self, p, target, horizontal, vertical):
        x,y = self.c.point(p)
        tx,ty = self.c.point(target)
        body=(abs(wrap_delta(x,tx,self.b.width))<=horizontal*self.b.tile
              and abs(ty-y)<=vertical*self.b.tile)
        return body or self.b.projectile_rules.head_overlaps_area(
            target,x,y,horizontal*self.b.tile,vertical*self.b.tile)

    def attack(self, p, amount, horizontal, vertical, hero_amount, hero_kind='content'):
        for target in self.living_enemies(p):
            if not self.inside(p,target,horizontal,vertical):
                continue
            self.c.damage_target(p,target,hero_amount if target.get('_pvp_hero') else amount,
                                 hero_kind=hero_kind)

    def plant_tick(self, p):
        name = p.get('_pvp_content')
        if name not in PLANTS or p.get('_pvp_effect_done'):
            return
        if p.get('植物血',0)<=0 or '死' in p or '睡觉' in p:
            return
        p['_pvp_content_age'] += 1
        if name == '黄金蓓蕾':
            if p['_pvp_content_age'] < 125:
                return
            p['_pvp_effect_done'] = True
            x,y = self.c.point(p)
            # These are native sun-motion records. The existing economy takes
            # them over, including collection, expiry and the sunlight secret.
            amount = 15 if self.b.engine.native_tick < 120*250 else 25
            for n in range(8):
                angle = math.pi * (n+.5)/8.
                sun = [0,[x,y,math.cos(angle)*self.g['plk']*100,
                            -math.sin(angle)*self.g['plk']*150],0,1]
                self.g['阳光球'].append(sun)
                self.bloom_sun_amounts[id(sun)] = amount
            p['死'] = 0
            self.b._emit('gold_bloom',source=p.get('_pvp_id'),suns=8,amount=8*amount)
            return
        if '_pvp_ghost_started' not in p:
            # 71002: the enemy Dave (a hero proxy) starts it as well.
            if not any(not target.get('_pvp_grave')
                       and target.get('血量',0)>0 and self.inside(p,target,5.,.85)
                       for target in self.living_enemies(p)):
                return
            p['_pvp_ghost_started'] = self.b.engine.native_tick
            p['_pvp_ghost_clock'] = 0.
            self.b._emit('ghost_activated',source=p.get('_pvp_id'))
            return
        elapsed = self.b.engine.native_tick-p['_pvp_ghost_started']
        p['_pvp_ghost_clock'] += 1./max(.01,float(p.get('_pvp_aura_factor',1.)))
        if p['_pvp_ghost_clock'] + 1e-8 >= 250:
            p['_pvp_ghost_clock'] -= 250
            self.attack(p,25.,5.,.85,2.5)
            p['_pvp_ghost_pulse'] = self.b.engine.native_tick
        if elapsed >= 2500:
            p['_pvp_effect_done'] = True
            self.attack(p,250.,1.25,1.25,250.,hero_kind='ash')
            self.effects.append((self.b.engine.native_tick,self.c.point(p)))
            p['死'] = 0
            self.b._emit('ghost_exploded',source=p.get('_pvp_id'))

    def draw_plant(self, p):
        if self.g.get('补帧'):
            return
        name=p['_pvp_content']; age=p.get('_pvp_content_age',0)
        frame=(age//35)%2
        if name=='幽灵辣椒' and '_pvp_ghost_started' in p:
            frame=2+(age//35)%2
        elif name=='黄金蓓蕾' and age>75:
            frame=2
        if '睡觉' in p:frame=0
        x,y=self.c.point(p)
        if name=='幽灵辣椒':
            self.draw_ghost_range(p,x,y)
            y+=math.sin(age/40.)*self.b.tile*.04
        self.c.draw_custom_plant(p,name+'-帧'+str(frame),x,y)

    def draw_ghost_range(self,p,x,y):
        started=p.get('_pvp_ghost_started')
        if (started is None or p.get('_pvp_effect_done') or '死' in p or
                p.get('植物血',0)<=0 or self.b.engine.native_tick-started>=2500):
            return
        tile=self.b.tile
        frame=((self.b.engine.native_tick-started)//25)%8
        fog=self.g['图集']['幽灵白雾-帧'+str(frame)]
        # Inclusive cells -5..+5: extend half a cell beyond either outer centre.
        # Two short strips keep each origin near its visible cells on wrap maps.
        split=tile*6
        for offset,width in ((0,split),(split,tile*5)):
            piece=fog.subsurface((offset,0,width,fog.get_height()))
            self.g['摄像显示'](piece,(x-tile*5.5+offset,y-fog.get_height()/2))

    def draw_effects(self):
        now=self.b.engine.native_tick
        self.effects=[item for item in self.effects if now-item[0]<100]
        if self.g.get('补帧'):return
        for born,(x,y) in self.effects:
            age=now-born;size=max(1,round(self.b.tile*2.5))
            pg=self.g['pygame'];s=pg.Surface((size,size),pg.SRCALPHA)
            radius=max(1,round(size*.5*min(1.,(age+8)/60.)))
            pg.draw.circle(s,(185,248,230,max(0,160-int(age*1.6))),
                           (size//2,size//2),radius,max(1,round(self.b.tile*.06)))
            self.g['摄像显示'](s,(x-size/2,y-size/2))

    def chase_goal(self, z, goal, cache_key=None, tracking_goal=None):
        """Point one zombie's native chase at ``goal`` for this frame.

        Shared by the yeti's plant hunt and by the PvE/co-op wave zombies, which
        must come after the Daves instead of only marching to the lawn edge.
        The returned restore key is popped in ``finish_zombie``.
        """
        saved={key:self.g[key] for key in TRACKING_KEYS if key in self.g}
        z['_pvp_yeti_tracking']=saved
        z['_pvp_ai_player_position']=self.g['玩家位置']
        state=self.paths.get(cache_key)
        if state is None:
            state=copy.deepcopy(saved);state.update(人洪水圈=[],人洪水cd=0)
            self.paths[cache_key]=state
            if len(self.paths)>64:self.paths={cache_key:state}
        self.g.update(state)
        if state.get('_pvp_path_tick')!=self.b.engine.native_tick:
            target = goal if tracking_goal is None else tracking_goal
            # 我是僵尸 suppresses plant selection but deliberately retains
            # 目标位置. Expired 分兵 bodies read the second flood field, so
            # an explicit hunt must aim both fields at the same destination.
            # Otherwise that field can still lead to an old, unrelated plant.
            self.g['目标位置'] = [int((target[1]-.5*self.b.tile)//self.b.tile),
                                int(target[0]//self.b.tile)]
            self.b.engine.physics.update_tracking(dict(self.b.avatars['plant'],
                玩家位置=target),'我是僵尸')
            state.update({key:self.g[key] for key in TRACKING_KEYS if key in self.g})
            state['_pvp_path_tick']=self.b.engine.native_tick
        self.g['玩家位置']=goal

    def zombie_gate(self, z):
        name=z.get('_pvp_content')
        if name=='雪人僵尸':
            # Keep ordinary-zombie logic; borrow the shipped yeti layers.
            for part in ('-身','-首'):
                self.b.expansion.alias_art(z['僵尸']+part,'雪人僵尸'+part)
        from .zombie_secrets import hand_kind
        if hand_kind(z)=='垃圾桶' and z.get('手持')=='钢门' and z.get('手持血量',0)>0:
            self.b.expansion.alias_art('钢门','垃圾桶-手持')
        if name!='雪人僵尸' or '魅惑' in z or z.get('血量',0)<=0:
            return
        if z.get('_pvp_zs_headhunt'):
            # 斩首行动: keep the native chase of the Plant Dave, and hide the
            # plant markers around it so plants neither block nor get bitten.
            self.b.zsecrets.hide_plants(z)
            return
        if self.b.command_for(z)=='follow' or self.b.rally_for(z) is not None:
            return
        plants=[p for p in self.g['植物'] if self.targetable(p)]
        x,y=self.c.point(z)
        target=min(plants,key=lambda p:wrap_delta(x,self.c.point(p)[0],self.b.width)**2+
                   (self.c.point(p)[1]-y)**2,default=None)
        tx,ty=self.c.point(target) if target is not None else (x,y)
        goal=[tx,ty+self.b.tile*.55,0.,0.]
        z['_pvp_target']=target.get('_pvp_id') if target is not None else None
        cache_key=(int(tx//self.b.tile),int(goal[1]//self.b.tile),self.b.terrain_revision)
        self.chase_goal(z,goal,cache_key)

    def wave_chase(self, z):
        """PvE / co-op: every mobile wave zombie hunts the nearest living Dave.

        Without this the scripted waves only march to the lawn edge, so a Dave
        standing away from the lane was never approached (player report 10-14).
        """
        # Built-in scripted modes use persistent Dave fields (one in solo,
        # two in co-op). Do not run a second, competing flood per zombie.
        if self.b.mode in ('pve', 'coop'):
            return False
        if not self.b.scripted or '魅惑' in z or z.get('_pvp_grave') or z.get('_pvp_orphan_barrel'):
            return False
        if z.get('_pvp_zs_headhunt') or self.b.command_for(z)=='follow' or self.b.rally_for(z) is not None:
            return False
        if z.get('血量',0)<=0 or z.get('_pvp_content')=='雪人僵尸':
            return False
        seats=[seat for seat in self.b.present if team_of(seat)=='plant']
        # avatars temporarily swaps plant/plant2 inside the native zombie
        # region. True seat liveness and positions must come from one mapping.
        avatars=[self.b.hero_states[seat] for seat in seats
                 if self.b.hero_states[seat]['玩家血量']>0]
        if not avatars:
            return False
        x,y=self.c.point(z)
        avatar=min(avatars,key=lambda a: wrap_delta(x,a['玩家位置'][0],self.b.width)**2+
                   (a['玩家位置'][1]-y)**2)
        ax,ay=avatar['玩家位置'][:2]
        goal=[ax,ay+self.b.tile*.55,0.,0.]
        # The collision-facing target keeps the native body offset. Flood
        # routing must start at Dave's actual feet: the offset can enter solid
        # ground at a ladder exit and leave the whole wave below the platform.
        self.chase_goal(z,goal,('wave',int(ax//self.b.tile),int(ay//self.b.tile),
                              self.b.terrain_revision),tracking_goal=avatar['玩家位置'])
        return True

    def finish_zombie(self,z):
        saved=z.pop('_pvp_yeti_tracking',None)
        if saved:self.g.update(saved)
