"""Additional cards on the native constructors, clocks and combat callbacks.

Only returning darts and the parrot's free flight need new motion rules.
Ordinary projectiles, plant attacks, zombie physics and death still run in the
shipped engine. All hooks and state belong to this match's private namespace.
"""
import math
import dis
import sys
import types
from contextlib import contextmanager
from .content_catalog import PLANTS, ZOMBIES
from .expansion_catalog import BLACK_ZOMBIES
from .simulation import wrap_delta
from .native_gate import replace_predicate,inject_iteration_gate
from .native_scale import allows_hit as native_scale_allows_hit
from .pvp61_catalog import SCARECROW, CROW

FLYERS=('海盗鹦鹉',CROW)
CAPTAIN='海盗船长'


def homing_aim_y(target,tile):
    """Height a homing spike steers at: the centre of the body as drawn."""
    from .native_scale import SCALE_TILES as SHRUNK, unit_root
    from .content_assets import SCALE_TILES as CONTENT
    root=unit_root(target)
    height=SHRUNK.get(root,CONTENT.get(root,2.))
    return target['位置'][1]-tile*min(1.,height/2.)
PVP61_ZOMBIES=(SCARECROW,CROW)

DARTS=('回旋镖射手','毒镖射手')
GAS=('小喷菇','胆小菇','大喷菇','忧郁蘑菇','忧郁菇','海蘑菇')


class NativeContent:
    def __init__(self,battle):
        self.b=battle;self.g=battle.g;self.last_zombie=None
        from .cart_lifecycle import CartLifecycle
        self.carts=CartLifecycle(battle)
        self.damage_depth=0;self.dart_entities=[];self.pending_frost=[]
        from .performance import enabled
        self.dart_broad_phase=enabled('DART_BROADPHASE')
        from .native_barrels import NativeBarrels
        self.barrels=NativeBarrels(self)
        self._install()
        from .native_september_content import SeptemberContent
        self.september=SeptemberContent(self)
        from .pvp56_zombies import PvP56Zombies
        self.zombies56=PvP56Zombies(self)
        # Before FlyingPlants: its wind wrapper then sees the reach limit.
        from .pvp59_wind import Wind
        self.wind=Wind(self)
        from .pvp56_plants import FlyingPlants
        self.flying=FlyingPlants(self)
        from .pvp58_vines import Vines
        self.vines=Vines(self)
        from .pvp59_sea import SeaShroom
        self.sea=SeaShroom(self)
        from .pvp61_content import PvP61Content
        self.pvp61=PvP61Content(self)
        from .pvp64_content import PvP64Content
        self.pvp64=PvP64Content(self)
        from .pvp70_content import PvP70Content
        self.pvp70=PvP70Content(self)
        self._install_plant_visual_lifecycles()

    @contextmanager
    def plant_art(self, plant):
        """Native crush/death functions keep their logic and use the real card art."""
        name=plant.get('_pvp_content');template=plant.get('植物')
        atlas=self.g['图集'];saved={}
        if name and name in atlas:
            for suffix in ('','-受伤','-黑白'):
                old,new=template+suffix,name+suffix
                if old in atlas and new in atlas and old!=new:
                    saved[old]=atlas[old];atlas[old]=atlas[new]
        try:yield
        finally:
            for key,image in saved.items():atlas[key]=image

    def _install_plant_visual_lifecycles(self):
        g=self.g;crush=g['扁死'];particles=g['增粒子']
        def card_crush(row,col,*args,**kwargs):
            index=g['哪个植物'](row,col)
            if index==-1:return crush(row,col,*args,**kwargs)
            source=self.b.targets.source()
            if (isinstance(source,dict) and '僵尸' in source
                    and self.b.targets.owner(source)==self.b.targets.owner(g['植物'][index])):
                return False
            # PvP70: a crushed 抓人草 flattens its tentacle heads as well.
            if g['植物'][index].get('_pvp_content')=='抓人草':g['植物'][index]['_pvp_crushed']=True
            with self.plant_art(g['植物'][index]):
                return crush(row,col,*args,**kwargs)
        def card_particles(name,position,*args,**kwargs):
            # Native maintenance knows its plant index. Verify identity and
            # centre before borrowing an atlas, so zombie/projectile particles
            # at an unrelated point never inherit plant art.
            index=g.get('l',-1)
            if isinstance(index,int) and 0<=index<len(g['植物']):
                plant=g['植物'][index];row,col=plant['坐标'];tile=self.b.tile
                if (name==plant['植物'] and len(position)>=2 and
                        abs(position[0]-(col+.5)*tile)<.01 and abs(position[1]-(row+.5)*tile)<.01):
                    with self.plant_art(plant):
                        return particles(name,position,*args,**kwargs)
            return particles(name,position,*args,**kwargs)
        g['扁死']=card_crush;g['增粒子']=card_particles

    def draw_custom_plant(self, plant, key, x, y, bottom=False, angle=0.):
        """Display native status flags without advancing any gameplay clock."""
        g=self.g;pg=g['pygame'];tile=self.b.tile;now=self.b.engine.native_tick
        if g.get('补帧'):return
        atlas=g['图集']
        base_key=key
        if '黑白' in plant and key+'-黑白' in atlas:key+='-黑白'
        image=atlas[key].copy()
        sleeping='睡觉' in plant
        hurt=plant.get('受伤',0)
        if hurt>0:
            white=atlas.get(base_key+'-受伤')
            if white is not None:
                overlay=white.copy();overlay.set_alpha(round(abs(math.sin(hurt/50.*math.pi))*200))
                image.blit(overlay,(0,0))
        if plant.get('_pvp_poison'):
            from .native_status import tint_poison
            image=tint_poison(image,plant['_pvp_poison']['level'],pg)
        if plant.get('方向',1)<0:image=g['反'](image)
        if '死' in plant or plant.get('植物血',1)<=0:
            image=pg.transform.scale(image,(round(tile*1.2),max(1,round(tile*.3))))
            row,col=plant['坐标'];x,y=(col+.5)*tile,(row+1)*tile
            bottom=True
            image.set_alpha(185)
        else:
            if sleeping:
                # A drooping, breathing body and rising native Z marker; the
                # presence flag also covers 黑铁桶's value-zero sleep record.
                image.fill((180,190,210),special_flags=self.b.pg.BLEND_RGB_MULT)
                angle=plant.get('方向',1)*(8+math.sin(now/85.)*2)
            elif hurt>0:
                angle+=plant.get('方向',1)*math.sin(hurt/5.)*3
            if angle:image=pg.transform.rotate(image,angle)
        w,h=image.get_size()
        g['摄像显示'](image,(x-w/2,y-h if bottom else y-h/2))
        if sleeping and '死' not in plant and plant.get('植物血',1)>0:
            mark=pg.transform.scale(atlas['睡觉'],(round(tile*.4),round(tile*.4)))
            lift=(now%200)/200.*tile*.3
            g['摄像显示'](mark,(x+tile*.22,y-(h if bottom else h/2)-tile*.2-lift))

    def configure(self,obj,card):
        self.carts.configure(obj,card)
        if self.pvp70.configure(obj,card):return
        if self.pvp64.configure(obj,card):return
        if self.pvp61.configure(obj,card):return
        if self.vines.configure(obj,card):return
        if self.zombies56.configure(obj,card):return
        if self.flying.configure(obj,card):return
        if self.september.configure(obj,card):return
        if obj.get('_pvp_variant') in BLACK_ZOMBIES:obj['_pvp_bite_plant']=3.
        name=card.get('content')
        if not name:return
        obj['_pvp_content']=name
        if name in PLANTS:
            obj['_pvp_interval']=round(PLANTS[name][3]*250)
            obj['射cd']=0
            return
        obj['血量']=ZOMBIES[name][3];obj['_pvp_max_hp']=obj['血量']
        if name in ('滚桶僵尸','小鬼炮'):
            template='巨人僵尸' if name=='滚桶僵尸' else '撑杆跳僵尸'
            old=self.g['僵尸'];state=self.g['random'].getstate()
            try:
                self.g['僵尸']=[]
                self.b._grave_native_factory(template,[0.,0.,0.,0.],1)
                obj['移速']=self.g['僵尸'][0]['移速']
            finally:self.g['僵尸']=old;self.g['random'].setstate(state)
        obj['_pvp_base_speed']=obj['移速']
        obj['_pvp_summon_clock']=0.
        if name=='滚桶僵尸':
            obj.update(手持='滚桶',手持血量=400.,_pvp_barrel_direction=obj['方向'])
            obj['_pvp_barrel_position']=[(obj['位置'][0]+obj['方向']*self.b.tile*.9)%self.b.width,obj['位置'][1],0.,0.]
            self.barrels.track(obj)
        if name=='海盗船长':obj['_pvp_bite_plant']=4.
        if name=='海盗鹦鹉':
            obj.update(手持='',手持血量=0,大小=2)
            obj.pop('气球',None)
            obj['_pvp_flight']=True

    def _install(self):
        b,g=self.b,self.g;ns=b.patch.ns
        # Fixed-speed plant zombies must retain the same additive bonuses.
        motion=ns['__pvz_sb_enforce_plant_zombie_motion']
        def secret_motion(game,z,cfg):
            factor=b.zsecrets.movement_factor(z)
            if factor!=1. and cfg.get('move_speed') is not None:
                # Native motion floors per-tick speed at 1, so apply the
                # secret after that floor rather than letting it erase +75%.
                step=game['plk']
                cfg=dict(cfg,move_speed=max(1.,cfg['move_speed']*step)*factor/step)
            return motion(game,z,cfg)
        ns['__pvz_sb_enforce_plant_zombie_motion']=secret_motion
        # Complete native bites already use the per-attacker 3/6 contract.
        ns['__pvz_sb_update_gravebuster_zombie_plant_damage']=lambda game:None
        displacement=g['__native_displacement']
        # Native collision/gravity with the barrel's 1.2 x 1.2 tile footprint.
        # Ordinary zombie displacement keeps its own tall body samples.
        constants=tuple({1.5:1.2,.3:.6,.75:.6,.2:.01}.get(c,c) if type(c) is float else c
                        for c in displacement.__code__.co_consts)
        code=displacement.__code__.replace(co_consts=constants)
        # The original six points sample only the left/right edges. A barrel
        # is wider than one block: add middle points so it cannot straddle and
        # fall through a one-block obstacle. Keep the entire native integrator.
        def barrel_samples():
            local=sys._getframe(1).f_locals;x,y=local['weizhi'][:2]
            local['dian'].extend([[x,y-g['比']*height] for height in (1.2,.6,.01)])
        g['_pvp_barrel_samples']=barrel_samples
        offset=len(code.co_code)
        code=inject_iteration_gate(code,268,'_pvp_barrel_samples')
        data=bytearray(code.co_code)
        assert data[offset]==dis.opmap['LOAD_NAME']
        data[offset]=dis.opmap['LOAD_GLOBAL']  # optimized function, not exec region
        code=code.replace(co_code=bytes(data))
        self.barrel_displacement=types.FunctionType(code,
            displacement.__globals__,displacement.__name__,displacement.__defaults__)
        # Reuse the native interception solver, selecting its high arc only for
        # pepper. The original solver chooses the earliest (almost flat) root.
        solver=ns['__pvz_sb_solve_intercept']
        high_solver=types.FunctionType(solver.__code__.replace(
            co_names=tuple('max' if n=='min' else n for n in solver.__code__.co_names)),
            solver.__globals__,solver.__name__,solver.__defaults__)
        compute=ns['__pvz_sb_compute_solution']
        def pepper_solution(game,e,target,velocity,speed):
            source=b.targets.source()
            if e.get('_pvp_content')=='甜椒投手' or isinstance(source,dict) and source.get('_pvp_content')=='甜椒投手':
                # Native 位移处理 byte 382..400 adds 4*plk per tick.
                # The legacy aim helper assumes 2*plk, landing a high lob
                # roughly halfway to its target when guidance is disabled.
                gravity=4.*g['plk']
                solution=high_solver(tuple(e['位置'][:2]),target[2],velocity,speed,gravity,2000.)
                if solution is None:solution=high_solver(tuple(e['位置'][:2]),target[2],(0.,0.),speed,gravity,2000.)
                return solution,gravity
            return compute(game,e,target,velocity,speed)
        ns['__pvz_sb_compute_solution']=pepper_solution
        reaim=ns['__pvz_sb_reaim_projectile']
        ns['__pvz_sb_reaim_projectile']=lambda game,e:None if e.get('_pvp_content')=='甜椒投手' else reaim(game,e)
        add=g['新增实体']
        def entity(*args,**kwargs):
            before=len(g['实体']);source=b.targets.source()
            if isinstance(source,dict) and source.get('_pvp_content')=='甜椒投手' and len(args)>=3 and args[0]=='西瓜':
                pos=list(args[2]);pos[2]*=1.5;pos[3]*=1.5
                args=args[:2]+(pos,)+args[3:]
            result=add(*args,**kwargs)
            if isinstance(source,dict):
                content=source.get('_pvp_content')
                for e in g['实体'][before:]:
                    if content:e['_pvp_content']=content
                    e['_pvp_plant_kind']=source.get('植物',source.get('_pvp_plant_kind'))
                    if content in DARTS and e.get('名')=='豌豆':self.prepare_dart(e)
                    if content=='寒冰辣椒' and e.get('名')=='火':
                        e['_pvp_art_name']='寒冰地火'
                    if source.get('植物')=='裂荚射手':self.pvp64.split_pea_blue(e)
            return result
        g['新增实体']=entity
        damage=g['伤害僵尸'];surface=g['表面伤害僵尸'];ash=g['灰烬僵尸'];knock=g['击退僵尸']
        self._primal_native_knock=knock
        head_scan_code=ns['__pvz_sb_plant_zombie_head_hit_scan'].__code__
        def hit(index,facing,amount):
            source=b.targets.source();target=g['僵尸'][index]
            if b.engine.native_tick<target.get('_pvp_anchor_until',0):return 0
            # These are the two original reciprocal charm-bite call sites.
            # Inspect here, before the existing adapter layers obscure caller.
            frame=sys._getframe(1);offset=frame.f_lasti
            if frame.f_code is head_scan_code and self.content_projectile(frame.f_locals.get('entity')):
                return self.head_impact(frame.f_locals['entity'],index,facing,amount,hit)
            if frame.f_code is b.engine.regions['zombies'] and 72380<=offset<=72590:
                current=g['僵尸'][g['l']];other=g['僵尸'][g['z']]
                attacker=other if target is current else current
                amount=self.bite_damage(attacker,target)
                owner=b.targets.owner(attacker)
                with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'zombies',attacker):
                    return damage(index,facing,amount)
            # A unit drawn at a smaller size is also a smaller target; a bite is
            # adjacency and stays untouched, which is why this sits below the
            # reciprocal-bite branch rather than above it.
            if not self.allows_hit(target,source):return 0
            if not self.damage_depth and isinstance(source,dict):
                content=source.get('_pvp_content')
                if content=='原始豌豆射手' and source.get('名') in ('豌豆','冰豆','火豆','蓝火豆'):
                    amount=self.primal_damage(source) if not source.get('_pvp_melon_splash') else self.primal_damage(source)/3.
                elif content=='甜椒投手' and source.get('名')=='西瓜':
                    amount=60.
                if self.multi_blue_direct(source):amount=20. if source.get("_pvp_fire_color")=="fire" else 30.
                from .balance68006 import fire_color
                if content!='原始豌豆射手' and source.get('名') in ('火豆','蓝火豆') and not source.get('_pvp_melon_splash'):
                    amount=30. if fire_color(source,g['秘籍'])=='blue' else 20.
                if source.get('_pvp_mortar'):amount=self.pvp64.projectile_damage(source,target,amount)
                if source.get('__pvz_sb_charmed_plant_zombie_pea') and source.get('名') in ('火豆','蓝火豆'):
                    # The zombie pea deals 2/4/6 to plants, so its charmed
                    # fire forms deal 40/60 to bodies, with 1/3 splash.
                    amount=(60. if fire_color(source,g['秘籍'])=='blue' else 40.)
                    if source.get('_pvp_melon_splash'):amount/=3.
            barrel_hp=target.get('手持血量',0)
            self.damage_depth+=1
            try:result=damage(index,facing,amount)
            finally:self.damage_depth-=1
            if target.get('_pvp_orphan_barrel'):
                # After the pusher dies the wood is an ordinary damageable
                # target, with one HP pool instead of a type-II shield/body.
                target['手持血量']=max(0.,target['血量'])
                target['_pvp_barrel_remaining']=target['手持血量']
                if target['手持血量']<=0:self.break_barrel(target)
            if target.get('血量',0)<=0:self.barrels.detach(target,barrel_hp)
            if amount>0:self.gas_hit(source,target)
            if (isinstance(source,dict) and source.get('_pvp_content')=='原始豌豆射手'
                    and source.get('名') in ('豌豆','冰豆','火豆','蓝火豆')
                    and not source.get('_pvp_melon_splash')):
                self.primal_knockback(index,source.get('方向',1)*g['plk']*200,source)
            return result
        def surface_hit(index,facing,amount):
            if b.engine.native_tick<g['僵尸'][index].get('_pvp_anchor_until',0):return 0
            frame=sys._getframe(1)
            if frame.f_code is head_scan_code and self.content_projectile(frame.f_locals.get('entity')):
                return self.head_impact(frame.f_locals['entity'],index,facing,amount,surface_hit)
            source=b.targets.source()
            # Armour belongs to the body: a shot that misses a smaller unit must
            # not strip its helmet either.
            if not self.allows_hit(g['僵尸'][index],source):return 0
            # 多向蓝火 shots (tripea, split pea, mortar) are native 蓝火豆 that
            # the native code hands to surface damage for 10. The patch lifts
            # them to 30 and lets them pass a steel door or ladder by
            # inspecting its caller frame, which these adapters hide. Treat
            # them as the torchwood blue fire pea: a 30 body hit through any
            # type-II shield (僵王出品 still blocks it inside hit).
            if self.multi_blue_direct(source) or isinstance(source,dict) and source.get('名') in ('火豆','蓝火豆') and not source.get('_pvp_melon_splash'):
                if (g['僵尸'][index].get('手持') in (ns['__pvz_sb_K_STEEL_DOOR'],ns['__pvz_sb_K_LADDER'])
                        and g['僵尸'][index].get('手持血量',0)>0 and ns['__pvz_sb_K_TRACKING'] not in source):
                    knock(index,facing*g['plk']*200.)
                return hit(index,facing,amount)
            if isinstance(source,dict):
                if source.get('_pvp_content')=='原始豌豆射手':amount=self.primal_damage(source)
                elif source.get('_pvp_content')=='甜椒投手':amount=60.
                if source.get('_pvp_mortar'):amount=self.pvp64.projectile_damage(source,g['僵尸'][index],amount)
            target=g['僵尸'][index]
            if target.get('_pvp_orphan_barrel'):return hit(index,facing,amount)
            if target.get('_pvp_content')=='滚桶僵尸' and target.get('手持血量',0)>0:
                # Its wooden armour must never enter the native steel-door
                # drop branch. Shots over the barrel can still hit the body.
                if isinstance(source,dict) and '名' in source and not source.get('_pvp_barrel_contact') and not self.barrel_overlap(target,source):
                    return hit(index,facing,amount)
                target['手持血量']=max(0.,target['手持血量']-amount)
                target['_pvp_barrel_remaining']=target['手持血量']
                if target.get('_pvp_orphan_barrel'):target['血量']=target['手持血量']
                target['手持受伤']=1
                if target['手持血量']<=0:self.break_barrel(target)
                return True
            self.damage_depth+=1
            try:result=surface(index,facing,amount)
            finally:self.damage_depth-=1
            if amount>0:self.gas_hit(source,g['僵尸'][index])
            if (isinstance(source,dict) and source.get('_pvp_content')=='原始豌豆射手'
                    and source.get('名') in ('豌豆','冰豆','火豆','蓝火豆')):
                self.primal_knockback(index,source.get('方向',1)*g['plk']*200,source)
            return result
        def freeze_hit(index):
            source=b.targets.source()
            target=g['僵尸'][index]
            if b.engine.native_tick<target.get('_pvp_anchor_until',0):return 0
            if target.get('_pvp_orphan_barrel') and not(isinstance(source,dict) and source.get('_pvp_content')=='寒冰辣椒'):
                self.break_barrel(target)
                return
            if isinstance(source,dict) and source.get('_pvp_content')=='寒冰辣椒':
                target=g['僵尸'][index]
                attack=source.get('_pvp_source_entity',source.get('_pvp_id'))
                seen=target.setdefault('_pvp_ice_chili_hits',set())
                if attack in seen:return
                seen.add(attack)
                if target.get('_pvp_hero'):b.targets.damage_hero(target['_pvp_hero'],16.,'chili')
                else:hit(index,source.get('方向',1),250.)
                # Original >1000 means frozen; last 1000 ticks mean slow.
                target['冰冻']=max(target.get('冰冻',0),2250)
                self.pending_frost.append(target)
                return
            barrel_hp=target.get('手持血量',0)
            result=ash(index)
            if target.get('血量',0)<=0 or '灰烬' in target:self.barrels.detach(target,barrel_hp)
            return result
        def knockback(index,speed):
            source=b.targets.source()
            if isinstance(source,dict) and source.get('_pvp_content')=='原始豌豆射手':
                return self.primal_knockback(index,speed,source)
            return knock(index,speed)
        g['伤害僵尸']=hit;g['表面伤害僵尸']=surface_hit;g['灰烬僵尸']=freeze_hit;g['击退僵尸']=knockback
        flame_hit=ns['__pvz_sb_chili_fire_hit_one_zombie']
        def cold_flame(game,entity,index,zombie,*args,**kwargs):
            previous=zombie.get('冰冻',0)
            owner=b.targets.owner(entity)
            with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'entities',entity):
                result=flame_hit(game,entity,index,zombie,*args,**kwargs)
            if result and entity.get('_pvp_content')=='寒冰辣椒':
                # Another segment of this same cold flame may hit later. Its
                # original chilli helper clears ice after the damage callback.
                with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'entities',entity):
                    zombie['冰冻']=max(previous,zombie.get('冰冻',0),2250 if any(t is zombie for t in self.pending_frost) else 0)
            return result
        ns['__pvz_sb_chili_fire_hit_one_zombie']=cold_flame
        launch=ns['__pvz_sb_chili_fire_player_hit']
        ns['__pvz_sb_chili_fire_player_hit']=lambda game,e,*args,**kwargs:False if e.get('_pvp_content')=='寒冰辣椒' else launch(game,e,*args,**kwargs)
        ns['__pvz_sb_zombie_bite_damage']=lambda game,s,t,amount:self.bite_damage(s,t)
        hero=g['掉血']
        def hero_damage(amount):
            source=b.targets.source()
            bite=amount==1 and isinstance(source,dict) and source.get('_pvp_content') in FLYERS
            frame=sys._getframe(1)
            native_bite=(frame.f_code is b.engine.regions['zombies'] and 75606<=frame.f_lasti<=75612)
            if isinstance(source,dict):
                if source.get('_pvp_no_attack'):return None
                if native_bite:
                    amount=self.bite_damage(source,b.targets.hero_proxy(b.targets.active['target']))
                elif source.get('_pvp_bite_plant') and amount==1:amount=source['_pvp_bite_plant']
                if source.get('名')==ns['__pvz_sb_K_ZOMBIE_PEA']:
                    fire=source.get(ns['__pvz_sb_K_ZOMBIE_PEA_FIRE'])
                    if fire:amount=3. if fire=='blue' else 2.
            result=hero(amount)
            if bite and result:
                self.flyer_bite_effect(source,b.targets.hero_proxy(b.targets.active['target']))
            return result
        g['掉血']=hero_damage
        class ContentBaseDamage(dict):
            def get(table,key,default=None):
                e=sys._getframe(1).f_locals.get('entity')
                if isinstance(e,dict) and e.get('_pvp_content')=='甜椒投手':return 60.
                return dict.get(table,key,default)
        ns['__pvz_sb_BASE_DAMAGE']=ContentBaseDamage(ns['__pvz_sb_BASE_DAMAGE'])
        tripea_spawn=ns['__pvz_sb_spawn_tripea_projectile']
        def red_tripea(game,*args,**kwargs):
            before=len(g['实体']);result=tripea_spawn(game,*args,**kwargs)
            for e in g['实体'][before:]:
                if e.get(ns['__pvz_sb_K_TRIPEA_BLUE_SHOT']):self.pvp64.red_pea(e)
            return result
        ns['__pvz_sb_spawn_tripea_projectile']=red_tripea
        # Preserve both original chomper branches, changing just size eligibility.
        regions=dict(b.engine.regions)
        # Reject a small-body miss while the native loop is still choosing a
        # target. A damage-only rejection is too late: it has already selected
        # deletion, and will still knock back/thaw the victim with zero damage.
        # Keep the original lower-bound test and all subsequent hit mechanics.
        regions['entities']=replace_predicate(regions['entities'],102192,102232,'_pvp_projectile_body_contact',[
            ('LOAD_NAME','实体'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('LOAD_CONST','位置'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',1),('BINARY_SUBSCR',None),
            ('LOAD_NAME','僵尸'),('LOAD_NAME','zz'),('BINARY_SUBSCR',None),('LOAD_CONST','位置'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',1),('BINARY_SUBSCR',None),('COMPARE_OP','<')])
        def body_contact():
            projectile=g['实体'][g['l']];target=g['僵尸'][g['zz']]
            # Detached wood is an ordinary damageable target, but only its
            # visible circle exists. The tall former pusher silhouette must
            # not consume overhead shots. The swept pass also catches fast
            # projectiles before they can cross that circle in one tick.
            if target.get('_pvp_orphan_barrel'):return self.barrel_overlap(target,projectile)
            return projectile['位置'][1]<target['位置'][1] and self.allows_hit(target,projectile)
        g['_pvp_projectile_body_contact']=body_contact
        # Homing spikes (香蒲, 猫尾) steer at 位置[1]-比: the centre of a full
        # two-tile body. A unit drawn and hit smaller (小鬼, 鹦鹉, 小型史莱姆)
        # has its centre lower, so the spike circled above it and never landed.
        regions['entities']=replace_predicate(regions['entities'],103664,103688,'_pvp_homing_aim_y',[
            ('LOAD_NAME','僵尸'),('LOAD_NAME','z'),('BINARY_SUBSCR',None),('LOAD_CONST','位置'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',1),('BINARY_SUBSCR',None),
            ('LOAD_GLOBAL','比'),('BINARY_SUBTRACT',None)])
        g['_pvp_homing_aim_y']=lambda:homing_aim_y(g['僵尸'][g['z']],g['比'])
        for key in ('__pvz_sb_tripea_zombie_point','__pvz_sb_zombie_target_point'):
            original=ns[key]
            def aim_point(game,zombie,_original=original):
                if zombie.get('_pvp_orphan_barrel') and self.barrel_active(zombie):
                    x,y=zombie['_pvp_barrel_position'][:2]
                    return x,y-b.tile*.6
                return _original(game,zombie)
            ns[key]=aim_point
        regions['plants']=replace_predicate(regions['plants'],135288,135296,'_pvp_pitcher_columns',[
            ('LOAD_NAME','range'),('LOAD_CONST',16),('CALL_FUNCTION',1)])
        g['_pvp_pitcher_columns']=lambda:range(36 if g['植物'][g['l']].get('_pvp_content')=='甜椒投手' else 16)
        regions['plants']=replace_predicate(regions['plants'],117138,117154,'_pvp_chili_thaws',[
            ('LOAD_CONST','冰冻'),('LOAD_NAME','僵尸'),('LOAD_NAME','z'),('BINARY_SUBSCR',None),('COMPARE_OP','in')])
        g['_pvp_chili_thaws']=lambda:g['植物'][g['l']].get('_pvp_content')!='寒冰辣椒' and '冰冻' in g['僵尸'][g['z']]
        regions['plants']=replace_predicate(regions['plants'],117250,117272,'_pvp_chili_launches',[
            ('LOAD_NAME','jdz'),('LOAD_NAME','玩家位置'),('LOAD_CONST',1),('BINARY_SUBSCR',None),
            ('LOAD_NAME','yy'),('BINARY_SUBTRACT',None),('CALL_FUNCTION',1),('LOAD_GLOBAL','比'),('COMPARE_OP','<=')])
        g['_pvp_chili_launches']=lambda:g['植物'][g['l']].get('_pvp_content')!='寒冰辣椒' and abs(g['玩家位置'][1]-g['yy'])<=b.tile
        regions['zombies']=replace_predicate(regions['zombies'],76934,76942,'_pvp_fixed_heading',[
            ('LOAD_NAME','hs'),('LOAD_CONST',2),('COMPARE_OP','<=')])
        g['_pvp_fixed_heading']=lambda:g['hs']<=2 or self.barrel_active(g['僵尸'][g['l']])
        regions['plants']=replace_predicate(regions['plants'],134002,134022,'_pvp_content_edible',[
            ('LOAD_NAME','僵尸'),('LOAD_NAME','z'),('BINARY_SUBSCR',None),('LOAD_CONST','大小'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',2),('COMPARE_OP','==')])
        regions['zombies']=replace_predicate(regions['zombies'],80666,80692,'_pvp_car_speed',[
            ('LOAD_NAME','僵尸'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('LOAD_CONST','方向'),
            ('BINARY_SUBSCR',None),('LOAD_GLOBAL','plk'),('BINARY_MULTIPLY',None),('LOAD_CONST',40),('BINARY_MULTIPLY',None)])
        # The original cart reloads a three-ball magazine, then kills itself
        # when its total stock runs out. PvP66 carts carry twenty finite balls
        # and keep the original car body after spending them. Match on the
        # real card, so the imp cannon's borrowed cart body is untouched.
        regions['zombies']=replace_predicate(regions['zombies'],96932,96950,'_pvp_cart_ammo_death',[
            ('LOAD_NAME','僵尸'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('LOAD_CONST','篮球总量'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',0),('COMPARE_OP','<=')])
        regions['zombies']=replace_predicate(regions['zombies'],96986,97004,'_pvp_cart_ammo_reload',[
            ('LOAD_NAME','僵尸'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('LOAD_CONST','篮球'),
            ('BINARY_SUBSCR',None),('LOAD_CONST',0),('COMPARE_OP','==')])
        def cart_ammo_death():
            z=g['僵尸'][g['l']]
            return z.get('_pvp_card')!='zombie:投篮车僵尸' and z['篮球总量']<=0
        def cart_ammo_reload():
            z=g['僵尸'][g['l']]
            return z.get('_pvp_card')!='zombie:投篮车僵尸' and z['篮球']==0
        g['_pvp_cart_ammo_death']=cart_ammo_death
        g['_pvp_cart_ammo_reload']=cart_ammo_reload
        from .native_bites import install as install_bite_scaling
        regions['zombies']=install_bite_scaling(self,regions['zombies'])
        b.engine.regions=regions
        g['_pvp_content_edible']=self.edible
        g['_pvp_car_speed']=lambda:g['僵尸'][g['l']]['方向']*(g['僵尸'][g['l']]['移速'] if g['僵尸'][g['l']].get('_pvp_content')=='小鬼炮' else g['plk']*40*b.zsecrets.movement_factor(g['僵尸'][g['l']]))
        gate=g['_pvp_zombie_gate']
        # The solo loop clears a lone charmed zombie. PvP still has an enemy
        # Dave outside that roster; retain the original charm timeout only.
        self.g['_pvp_charm_alone']=lambda: len(self.g['僵尸'])==1 and b.avatars['zombie']['玩家血量']<=0
        regions['zombies']=replace_predicate(regions['zombies'],78908,78920,'_pvp_charm_alone',[
            ('LOAD_NAME','len'),('LOAD_NAME','僵尸'),('CALL_FUNCTION',1),
            ('LOAD_CONST',1),('COMPARE_OP','==')])
        def zombie_gate():
            self.finish_zombie();gate();self.zombie_gate()
        g['_pvp_zombie_gate']=zombie_gate
        source_gate=g['_pvp_plant_gate']
        def plant_gate():
            source_gate()
            p=b.targets.source()
            if isinstance(p,dict):self.sea.gate(p)
            if isinstance(p,dict):self.september.plant_tick(p)
            if isinstance(p,dict):self.flying.plant_tick(p)
            if isinstance(p,dict):self.pvp61.plant_tick(p)
            if isinstance(p,dict):self.pvp64.plant_tick(p)
            if isinstance(p,dict):self.pvp70.plant_tick(p)
            if isinstance(p,dict) and p.get('_pvp_content') in PLANTS:
                p['_pvp_before_shot']=p.get('射',0)
                p['_pvp_before_cd']=p.get('射cd',0)
        g['_pvp_plant_gate']=plant_gate
        entity_gate=g['_pvp_entity_gate']
        def projectile_art():
            entity_gate()
            e=b.targets.source()
            if not isinstance(e,dict):return
            if e.get('_pvp_content')=='原始豌豆射手' and e.get('名') in ('火豆','蓝火豆'):
                b.expansion.restore_art()
                # Keep the native fire mechanics with the same larger faceted
                # projectile silhouette in both ignition states.
                from .balance68006 import fire_color
                blue=fire_color(e,g['秘籍'])=='blue'
                b.expansion.alias_art(e['名'],'原始蓝火豆' if blue else '原始火豆')
                if blue and e['名']=='火豆':b.expansion.alias_art('蓝火豆','原始蓝火豆')
            if e.get('_pvp_content')=='寒冰辣椒':
                for fire in ('火1.1','火1.2','火1.3','火2','火3','火尾1','火尾2','火尾3'):
                    if fire in g['图集']:b.expansion.alias_art(fire,'寒冰-'+fire)
        g['_pvp_entity_gate']=projectile_art
        draw=g['显示植物']
        def draw_plant(index,*args,**kwargs):
            p=g['植物'][index];name=p.get('_pvp_content')
            if name in ('旋转芜菁','芦笋战机'):
                return self.flying.draw_plant(p)
            if name in ('闪电芦苇','超载芦苇'):
                return self.pvp61.draw_plant(p)
            if name in ('甜薯','豌豆迫击炮','弹簧草'):
                return self.pvp64.draw_plant(p)
            if name=='原始土豆地雷':
                return self.pvp64.draw_primal(p)
            if name in ('幽灵辣椒','黄金蓓蕾'):
                return self.september.draw_plant(p)
            if name in ('阳光藤蔓','忧郁藤蔓'):
                start=len(b.recorder.commands)
                result=self.vines.draw_plant(p)
                for command in b.recorder.commands[start:]:
                    command['layer']='vine_foreground'
                return result
            if name not in PLANTS:
                start=len(b.recorder.commands)
                result=draw(index,*args,**kwargs)
                # 埋在土里的土豆地雷同胆小菇：贴图必须落在地形前景（方块/花盆）之下。
                # 引擎只按 `埋藏==0` 换"亮起"那张图，遮挡关系得在这里补。
                below = p.get('植物')=='胆小菇' or (p.get('植物')=='土豆地雷' and p.get('埋藏',0)>0)
                if below:
                    for command in b.recorder.commands[start:]:command['layer']='below_ground'
                return result
            # Original roots, sway, attack arm, squash/stretch, flower-pot lift
            # and water bob all remain in 显示植物. Replace its sprite layers.
            template=p['植物'];atlas=g['图集'];saved={}
            parts=('','-投','-投空') if name=='甜椒投手' else ('',)
            try:
                for part in parts:
                    for suffix in ('','-受伤','-冰冻','-灰烬','-魅惑'):
                        old=template+part+suffix;new=name+part+suffix
                        if old in atlas and new in atlas:
                            saved[old]=atlas[old];atlas[old]=atlas[new].copy()
                return draw(index,*args,**kwargs)
            finally:
                for key,image in saved.items():atlas[key]=image
        g['显示植物']=draw_plant

    def allows_hit(self,target,source):
        """Whether a shot at `source` lands on this unit's own, possibly smaller,
        hit box.

        Only units whose art was shrunk are filtered; every full-size body keeps
        the original contact test untouched.
        """
        if isinstance(source,dict) and ('名' not in source or source.get('_pvp_melon_splash') or source.get('_pvp_area_damage')):
            return True
        return native_scale_allows_hit(target,source,self.g['比'])

    def edible(self):
        z=self.g['僵尸'][self.g['z']]
        if self.pvp70.invulnerable(z):return False
        if z.get('_pvp_variant')=='角斗士巨人' or z.get('_pvp_content')=='红眼巨人':return False
        if z.get('_pvp_content') or z.get('_pvp_variant'):return True
        return z.get('大小')==2

    def multi_blue_direct(self,e):
        """A 多向蓝火 pea's own direct hit (its 1/3 splash is not)."""
        return (isinstance(e,dict) and bool(e.get(self.b.patch.ns['__pvz_sb_K_TRIPEA_BLUE_SHOT']) or e.get('_pvp_multi_red'))
                and not e.get('_pvp_melon_splash'))

    def content_projectile(self,e):
        return isinstance(e,dict) and (e.get('_pvp_content') in ('原始豌豆射手','甜椒投手') or
            e.get('_pvp_plant_kind') in GAS or e.get('名') in ('西瓜','冰瓜','火豆','蓝火豆'))

    def head_impact(self,e,index,facing,amount,callback):
        # The native head scan runs inside the bonus pass, whose enclosing
        # source is Dave. Restore the actual projectile at its damage boundary.
        b=self.b;owner=b.targets.owner(e)
        with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'entities',e):
            result=callback(index,facing,amount)
            if e.get('_pvp_content') in ('原始豌豆射手','甜椒投手'):
                # Native API takes signed pixels/native-tick, not the nominal
                # 200 speed. Omitting plk launched umbrella zombies at 50 px/tick.
                self.g['击退僵尸'](index,facing*self.g['plk']*200)
            b.projectile_rules.impact(e)
            return result

    def bite_damage(self,source,target):
        if source.get('_pvp_no_attack'):return 0.
        base=self.plant_bite(source)
        if source.get('_pvp_card') in ('zombie:巨人僵尸','zombie:红眼巨人','zombie:角斗士巨人'):
            # Plants are crushed outright; use the native 10-point Dave
            # hammer as the numeric reference for reciprocal zombie combat.
            base=10.
        rate=(4. if '狂暴' in source else 1.) * self.b.zsecrets.bite_rate(source)
        if target.get('_pvp_hero'):
            from .native_targets import HERO_BITE_DAMAGE,HERO_BLACK_BITE_DAMAGE,BLACK_BITE_VARIANTS
            base=HERO_BLACK_BITE_DAMAGE if source.get('_pvp_variant') in BLACK_BITE_VARIANTS else base
            return base*rate
        if '植物' in target:return base*rate
        amount=base*rate*10.
        if ('魅惑' in target and '魅惑' not in source
                and 'secret:魅惑' in self.b.team_secrets['plant']):amount*=.5
        return amount

    def plant_bite(self,source):
        if source.get('_pvp_variant') in BLACK_ZOMBIES:return 3.
        if source.get('_pvp_card')=='zombie:墓碑吞噬者僵尸' or source.get('僵尸')=='墓碑吞噬者僵尸':
            from .native_targets import gravebuster_bite
            return gravebuster_bite(source)
        return source.get('_pvp_bite_plant',1.)

    def flyer_bite_effect(self,source,target):
        """Native contact bites and the flight controller share this effect."""
        if (target.get('植物')=='雷蘑菇' or target.get('_pvp_card')=='plant:雷蘑菇'
                or target.get('植物')=='大喷菇' and '雷霆' in self.g['秘籍']):
            source['眩晕']=max(source.get('眩晕',0),250)
        if source.get('_pvp_content') not in FLYERS:return
        hero=target.get('_pvp_hero')
        if target.get('植物')=='大蒜' or hero and 'secret:体香' in self.b.players[hero]['secrets']:
            source['眩晕']=max(source.get('眩晕',0),125)

    def gas_hit(self,source,target):
        if not isinstance(source,dict) or 'secret:毒气' not in self.b.team_secrets['plant']:return
        if source.get('植物',source.get('_pvp_plant_kind')) in GAS and self.b.targets.owner(source)=='plant':
            self.b.status.apply(target,1,4.,'plant')

    def primal_damage(self,e):
        from .balance68006 import fire_color
        if fire_color(e,self.g['秘籍'])=='blue':return 90.
        return 60. if e.get('名')=='火豆' else 30.

    def primal_knockback(self,index,speed,source):
        if source.get('_pvp_melon_splash') or source.get('名') not in ('豌豆','冰豆','火豆','蓝火豆'):
            return
        from .balance68006 import fire_color
        blue=fire_color(source,self.g['秘籍'])=='blue'
        radius,scale=(1.,1.5) if blue else (.75,1.25) if source.get('名')=='火豆' else (.5,1.)
        x,y=source['位置'][:2]
        roster=self.g['僵尸'];owner=self.b.targets.owner(source)
        seen=source.setdefault('_pvp_primal_knock_hits',[])
        # NativeContent captured the original knock callback before wrapping it.
        native=self._primal_native_knock
        for candidate,target in enumerate(roster):
            if (target.get('血量',0)<=0 or self.b.targets.owner(target)==owner or
                    target.get('_pvp_hero') and candidate!=index or
                    target.get('手持') and target.get('手持血量',0)>0):
                continue
            tx,ty=target['位置'][:2]
            if candidate!=index and math.hypot(wrap_delta(x,tx,self.b.width),y-(ty-self.b.tile))>radius*self.b.tile:
                continue
            key=self.b.targets.source_id(target)
            if key in seen:continue
            seen.append(key)
            target['位置'][2]+=source.get('方向',1)*self.g['plk']*200*scale
            native(candidate,speed*scale)

    def before_tick(self):
        self.pvp70.before_tick()
        self.pvp64.before_entities()
        self.pvp64.landed()
        self.zombies56.before_tick()
        self.flying.before_tick()
        self.barrels.tick()
        self.barrel_projectiles()
        # Darts are kept out of the native one-hit pea loop; the same native
        # shooter creates them and this module implements only return physics.
        self.dart_entities=[e for e in self.g['实体'] if e.get('_pvp_dart')]
        self.g['实体']=[e for e in self.g['实体'] if not e.get('_pvp_dart')]

    def after_plants(self):
        secrets66=getattr(self.b,'secrets66',None)
        if secrets66 is not None:secrets66.lantern_pulses()
        self.vines.tick()
        self.apply_frost()
        self.september.draw_effects()
        self.pvp61.draw_effects()
        self.pvp64.draw_effects()
        self.clover_blow()
        for p in self.g['植物']:
            if p.get('_pvp_content') not in PLANTS:continue
            # Shot cooldown includes the original windup. Replace its reset,
            # never skip the native animation's exact emission frame.
            if p.get('射cd',0)>p.get('_pvp_before_cd',0)+2:
                p['射cd']=max(0,p['_pvp_interval']-1)
        for e in self.g['实体']:
            name=e.get('_pvp_content')
            if e.get('_pvp_content_ready') or name not in PLANTS:continue
            if e.get('名') not in ('豌豆','冰豆','火豆','蓝火豆','西瓜'):continue
            e['_pvp_content_ready']=True
            if name=='甜椒投手':
                e['_pvp_art_name']='甜椒弹'
            elif name in DARTS:
                self.prepare_dart(e)
            elif name=='原始豌豆射手':e['_pvp_art_name']='原始豌豆弹'

    def clover_blow(self):
        """Give the parrot the balloon-strength clover blow.

        The engine's clover branch keys its strong push on ``手持 == '气球'``:
        every frame the plant is alive it adds ``plk*20`` to 位置[2] and clamps
        to the balloon limit ``zbspeedmax*10`` (a ground unit gets plk*6 with the
        size-scaled limit instead).  A parrot carries no 手持, and it also flies
        on this module's controller, which rebuilds its position from
        ``_pvp_content_position_before`` every frame and keeps external momentum
        only in the hurt state - so the engine's own push never lands at all.
        Mirror the balloon branch here and flag each frame for the controller.
        """
        b, g = self.b, self.g
        clovers = [p for p in g['植物'] if p.get('植物') == '三叶草']
        if not clovers:
            return
        plk = float(g.get('plk', 1.) or 1.)
        # Same clamp the engine's balloon branch uses; ``zbspeedmax`` is the
        # real per-tick speed budget, so it must not be floored at 1.
        limit = float(g.get('zbspeedmax', 10.) or 10.) * 10.
        for p in clovers:
            row, col = p['坐标']
            xx = (col + .5) * b.tile
            direction = 1 if p.get('方向', 1) >= 0 else -1
            for z in g['僵尸']:
                if z.get('_pvp_content') not in FLYERS or z.get('血量', 0) <= 0:
                    continue
                pos = z.get('位置')
                if not isinstance(pos, list) or len(pos) < 4:
                    continue
                if (pos[0] - xx) * direction < 0:
                    continue
                # This controller decays the carried momentum by 10% every
                # frame, so an additive push only settles at a tenth of itself.
                # Hold the outgoing speed at the balloon's own clamped strength
                # instead, and never slow a parrot that is already flying faster.
                if pos[2] * direction < limit:
                    pos[2] = direction * limit
                pos[3] = min(pos[3], -14. * plk)
                z['_pvp_blown'] = True

    def prepare_dart(self,e):
        # A distinct projectile name also excludes native bonus/head scans
        # on the emission tick, before the next native entity loop starts.
        art='毒镖弹' if e['_pvp_content']==DARTS[1] else '回旋镖弹'
        e.update(名=art,_pvp_content_ready=True,_pvp_dart=True,_pvp_art_name=art,
                 _pvp_distance=0.,_pvp_leg_hits=[],_pvp_return=False,_pvp_turned=False,
                 _pvp_launch_direction=e.get('方向',1))
        e['位置'][3]=0.
        e['_pvp_speed']=abs(e['位置'][2])

    def point(self,obj):
        if obj.get('_pvp_content')=='抓人草触手':return obj['_pvp_head_point']
        if '植物' in obj:
            row,col=obj['坐标'];return ((col+.5)*self.b.tile,(row+.45)*self.b.tile)
        if obj.get('_pvp_content') in FLYERS:
            image=self.g['图集'].get(obj['_pvp_content']+'-帧0')
            half=image.get_height()/2. if image is not None else self.b.tile*.4
            return (obj['位置'][0],obj['位置'][1]-half)
        pos=obj['位置'];return (pos[0],pos[1]-self.b.tile)

    def enemies(self,source):
        b=self.b;owner=b.targets.owner(source)
        candidates=[z for z in self.g['僵尸'] if z.get('血量',0)>0 and not z.get('_pvp_hero') and b.targets.owner(z)!=owner]
        if owner=='zombie':candidates += [p for p in self.g['植物'] if self.september.targetable(p)]
        for seat in b.team_seats('zombie' if owner=='plant' else 'plant'):
            proxy=b.targets.hero_proxy(seat)
            if proxy['血量']>0:candidates.append(proxy)
        return candidates

    def nearest(self,source):
        return self.nearest_dynamic(source)

    def nearest_dynamic(self,source):
        x,y=self.point(source)
        enemies=self.enemies(source)
        if source.get('_pvp_no_hero_attack'):enemies=[z for z in enemies if not z.get('_pvp_hero')]
        nearest=min(enemies,key=lambda z:wrap_delta(x,self.point(z)[0],self.b.width)**2+(self.point(z)[1]-y)**2,default=None)
        if '魅惑' in source:
            heroes=[z for z in enemies if z.get('_pvp_hero')]
            if heroes:
                nearest=min(heroes,key=lambda z:wrap_delta(x,self.point(z)[0],self.b.width)**2+(self.point(z)[1]-y)**2)
                nearest=self.route_target(source,nearest,enemies)
        return self.pvp64.taunt_target(source,nearest)

    def route_target(self,source,goal,candidates):
        return self.route_target_dynamic(source,goal,candidates)

    def route_target_dynamic(self,source,goal,candidates):
        """Nearest opposing body intersecting the route to the intended goal."""
        if goal is None:return None
        x,y=self.point(source);tx,ty=self.point(goal)
        dx=wrap_delta(x,tx,self.b.width);dy=ty-y;length2=dx*dx+dy*dy
        if length2<=1e-12:return goal
        chosen=goal;first=1.
        for obj in candidates:
            if obj is goal:continue
            ox,oy=self.point(obj);ox=wrap_delta(x,ox,self.b.width);oy-=y
            along=(ox*dx+oy*dy)/length2
            if 0.<=along<first and (ox-along*dx)**2+(oy-along*dy)**2<=(self.b.tile*.65)**2:
                chosen=obj;first=along
        return chosen

    def damage_target(self,source,target,amount,surface=False,hero_kind='content'):
        b=self.b;owner=b.targets.owner(source)
        if b.targets.owner(target)==owner:return
        with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'content',source):
            if '植物' in target:
                if target.get('植物')=='魅惑菇' and '魅惑' not in source:
                    source['魅惑']=0
                target['植物血']-=b.protection.amount(target,amount);target['受伤']=1
                if target['植物血']<=0:target['死']=0
            elif target.get('_pvp_hero'):
                b.targets.damage_hero(target['_pvp_hero'],amount,hero_kind)
            else:
                roster=self.g['僵尸']
                index=next((i for i,z in enumerate(roster) if z is target),None)
                if index is not None:self.g['表面伤害僵尸' if surface else '伤害僵尸'](index,source.get('方向',1),amount)

    def projectiles(self):
        for grenade in self.pvp64.grenades:
            self.pvp70.wind(grenade)
            self.pvp70.reflect(grenade)
        self.pvp64.update_grenades()
        self.pvp70.projectiles()
        self.pvp64.draw_projectiles()
        self.flying.projectiles()
        self.sea.bubbles()
        self.apply_frost()
        b=self.b;survivors=[]
        for e in self.dart_entities:
            pos=e['位置'];oldx,oldy=pos[:2];direction=e['_pvp_launch_direction']
            if e['_pvp_return']:pos[2]-=direction*e['_pvp_speed']/125.
            if e['_pvp_return'] and not e['_pvp_turned'] and pos[2]*direction<=0:
                e['_pvp_turned']=True;e['_pvp_leg_hits']=[]
            pos[0]=(oldx+pos[2])%b.width;pos[1]+=pos[3]
            e['_pvp_distance']+=math.hypot(pos[2],pos[3])
            if e['_pvp_distance']>=64*b.tile:continue
            shooter=b._native_objects.get(e.get('_pvp_source_entity'))
            if e['_pvp_turned'] and shooter and shooter.get('植物血',0)>0:
                sx,sy=self.point(shooter)
                if abs(wrap_delta(sx,pos[0],b.width))<b.tile*.6 and abs(sy-pos[1])<b.tile:continue
            for target in self.enemies(e):
                uid=b.targets.source_id(target)
                if uid in e['_pvp_leg_hits']:continue
                tx,ty=self.point(target)
                dx=wrap_delta(oldx,tx,b.width)
                # Ordinary dart contact is the unchanged .5 x .8-tile ellipse.
                # The swept segment's enclosing box is conservative, including
                # reverse flight and the horizontal seam. Extended heads and
                # pushed/detached barrels retain the original full checks.
                if (self.dart_broad_phase and type(target) is dict
                        and target.get('_pvp_content')!='滚桶僵尸'
                        and not target.get('_pvp_orphan_barrel')
                        and not target.get(b.patch.ns['__pvz_sb_K_PLANT_ZOMBIE'])
                        and (abs(dx)>abs(pos[2])+max(1.,b.tile*.5)+1e-6
                             or abs(ty-oldy)>abs(pos[1]-oldy)+max(1.,b.tile*.8)+1e-6)):
                    continue
                segment=b.patch.ns['__pvz_sb_segment_hits_ellipse']
                contact=segment(0.,oldy,pos[2],pos[1],dx,ty,b.tile*.5,b.tile*.8)
                barrel_contact=False
                if self.barrel_active(target):
                    bx,by=target['_pvp_barrel_position'][:2]
                    barrel_contact=segment(0.,oldy,pos[2],pos[1],wrap_delta(oldx,bx,b.width),by-b.tile*.6,b.tile*.65,b.tile*.65)
                    if target.get('_pvp_orphan_barrel'):contact=barrel_contact
                    if barrel_contact:contact=True;tx,ty=bx,by-b.tile*.6
                head=b.projectile_rules.head_geometry(target)
                if not contact and head:
                    (hx,hy),(rx,ry)=head
                    contact=segment(0.,oldy,pos[2],pos[1],wrap_delta(oldx,hx,b.width),hy,rx,ry)
                    if contact:tx,ty=hx,hy
                if not contact:continue
                e['_pvp_leg_hits'].append(uid)
                poison=e['_pvp_content']=='毒镖射手'
                if barrel_contact:e['_pvp_barrel_contact']=True
                try:self.damage_target(e,target,8. if poison else 4.)
                finally:e.pop('_pvp_barrel_contact',None)
                if poison:
                    b.status.apply(target,2,4.,b.targets.owner(e))
                    for other in self.enemies(e):
                        if other is target:continue
                        ox,oy=self.point(other)
                        if (abs(wrap_delta(tx,ox,b.width))<1.3*b.tile and abs(ty-oy)<1.3*b.tile or
                                b.projectile_rules.head_overlaps_area(other,tx,ty,1.3*b.tile,1.3*b.tile)):
                            e['_pvp_area_damage']=True
                            try:self.damage_target(e,other,8.)
                            finally:e.pop('_pvp_area_damage',None)
                            b.status.apply(other,2,4.,b.targets.owner(e))
                if not e['_pvp_return'] and len(e['_pvp_leg_hits'])>=4:
                    e['_pvp_return']=True
                    break
            if e['_pvp_distance']>20*b.tile:e['_pvp_return']=True
            e['方向']=1 if pos[2]>=0 else -1
            self.draw_dart(e);survivors.append(e)
        self.g['实体'].extend(survivors)
        self.dart_entities=[]

    def apply_frost(self):
        with self.b.targets.context('zombie','plant','status',{'_pvp_owner':'plant'}):
            for target in self.pending_frost:
                target['冰冻']=max(target.get('冰冻',0),2250)
        self.pending_frost=[]

    def draw_dart(self,e):
        if self.g.get('补帧'):return
        key=e['_pvp_art_name'];image=self.g['图集'].get(key,self.g['图集']['豌豆'])
        self.draw_center(image,e['位置'][0],e['位置'][1],self.b.engine.native_tick*12%360)

    def draw_center(self,image,x,y,angle):
        image=self.g['pygame'].transform.rotate(image,angle)
        self.g['摄像显示'](image,(x-image.get_width()/2,y-image.get_height()/2))

    def zombie_gate(self):
        b=self.b;z=self.g['僵尸'][self.g['l']];self.last_zombie=z
        self.carts.before_zombie(z)
        name=z.get('_pvp_content')
        self.september.zombie_gate(z)
        self.zombies56.zombie_gate(z)
        # PvE / co-op waves hunt the Daves (see SeptemberContent.wave_chase).
        if '_pvp_ai_player_position' not in z:
            self.september.wave_chase(z)
        z['_pvp_content_position_before']=list(z['位置'])
        self.pvp64.zombie_gate(z)
        self.pvp70.zombie_gate(z)
        if name=='滚桶僵尸' and '魅惑' not in z and z.get('手持血量',0)>0:
            if b.rally_for(z) is not None:
                dx=wrap_delta(z['位置'][0],b.rally_destination(z)[0],b.width)
                if abs(dx)>b.tile*.4:z['_pvp_barrel_direction']=1 if dx>0 else -1
            self.barrels.correct_pair(z)
            z['方向']=z['_pvp_barrel_direction']
            # Fixed-heading pushers cannot use the F-selected path field to
            # choose their jump direction. Test the obstacle in front of their
            # own feet, and leave the jump arc/collision to native physics.
            x,y,vx,vy=z['位置'];direction=z['方向']
            held=z.get('冰冻',0)>1000 or z.get('黄油',0)>0 or z.get('眩晕',0)>0
            obstacle=b.cell(x+direction*b.tile*.4,y-b.tile*.4).get('solid')
            grounded=b.cell(x,y-b.tile*.19).get('solid')
            if not held and vy>=0 and grounded and obstacle and not b.cell(x,y-b.tile*1.8).get('solid'):
                z['位置'][3]=-self.g['plk']*400
        if name=='小鬼炮':
            # Keep the native car body/physics, suppress only basketball launch.
            z['篮球cd']=10**9
        if z.get('僵尸')=='投篮车僵尸':
            # Wave chasing may already have borrowed this slot. Keep the real
            # Dave reference, rather than saving the temporary chase target.
            z.setdefault('_pvp_ai_player_position',self.g['玩家位置'])
            side='zombie' if '魅惑' in z or b.command_for(z)=='follow' else 'plant'
            if side=='zombie' and z.get('_pvp_seat') in b.present:side=z['_pvp_seat']
            rally=b.rally_for(z) is not None and '魅惑' not in z
            if not rally:self.g['玩家位置']=list(b.avatars[side]['玩家位置'])
            goal=b.rally_destination(z) if rally else self.g['玩家位置']
            dx=wrap_delta(z['位置'][0],goal[0],b.width)
            if name=='小鬼炮' or b.command_for(z)=='follow' or rally:
                stopping=.4 if rally else 2. if b.command_for(z)=='follow' and '魅惑' not in z else 20.
                z['方向']=1 if dx>=0 else -1
                z['前进']=2 if abs(dx)>stopping*b.tile else 0
                if not z['前进']:z['位置'][2]=0.
            if z.get('_pvp_card')=='zombie:投篮车僵尸' and z.get('篮球',0)<=0:
                z['篮球']=0
                z['投篮']=0
                z['篮球cd']=10**9
                if b.command_for(z)!='follow' and not rally:
                    z['前进']=2
            if (b.command_for(z)=='follow' or rally) and '魅惑' not in z and name!='小鬼炮':
                z['_pvp_saved_basketball_cd']=z.get('篮球cd',0)
                z['篮球cd']=10**9
        if name==CAPTAIN:
            # The captain ships native body/head layers per walk frame, so the
            # original code lowers the head to bite and tips the body over.
            moving=z.get('血量',0)>0 and not z.get('啃咬',0) and abs(z['位置'][2])>.01
            frame=1+(b.engine.native_tick//35)%2 if moving else 0
            for part in ('-身','-首'):b.expansion.alias_art(z['僵尸']+part,name+part+str(frame))
        elif name in ZOMBIES or name in PVP61_ZOMBIES:
            # Original body and head use different origins. Suppress these
            # layers and draw the new full-body art once at the native feet.
            for part in ('-身','-首'):
                for suffix in ('','-受伤','-冰冻','-灰烬','-魅惑'):
                    b.expansion.alias_art(z['僵尸']+part+suffix,'_pvp_content_blank')
            if name=='滚桶僵尸' and z.get('手持')=='滚桶':
                for suffix in ('','-受伤','-冰冻','-灰烬','-魅惑'):b.expansion.alias_art('滚桶'+suffix,'_pvp_content_blank')
            if name=='小鬼炮':
                for part in ('轮子','投篮臂','投篮臂-空'):b.expansion.alias_art(part,'_pvp_content_blank')
            if z.get('黄油',0)>0:b.expansion.alias_art('黄油砸','_pvp_content_blank')
        if z.get('_pvp_poison'):b.status.tint_zombie(z)

    def release_pending_destination(self):
        """Undo a pending body's temporary destination on the global player slot.

        A chase borrows ``玩家位置`` so the original chase reads the goal, and a
        gate chain finishes the previous body only after the plant alias has
        already switched for the next one. Committing that borrowed slot inside
        the switch is not a teleport: production reported both co-op Daves on
        one spot, sunk into the ground and bobbing (2026-10-15). Release it
        first, while the Dave it belongs to is still the alias.
        """
        z=self.last_zombie
        if z is None:return
        if '_pvp_ai_player_position' in z:self.g['玩家位置']=z.pop('_pvp_ai_player_position')
        self.september.finish_zombie(z)

    def finish_zombie(self):
        z=self.last_zombie;self.last_zombie=None
        if not z:return
        b=self.b;name=z.get('_pvp_content');alive=z.get('血量',0)>0 and '灰烬' not in z
        self.september.finish_zombie(z)
        self.zombies56.finish_zombie(z)
        if '_pvp_ai_player_position' in z:self.g['玩家位置']=z.pop('_pvp_ai_player_position')
        # The order suppression above keeps the cart walking by parking its shot
        # timer; give the countdown back, but never at exactly 0. The engine arms
        # a shot only when its own decrement lands on 0, and it only decrements
        # above 0, so a 0 written from outside is a timer that never fires again
        # (player report 10-15: 点跟随/追击后投篮车僵尸再也不投篮, 坤坤 doubles the
        # rate so the countdown expires inside the order window).
        if '_pvp_saved_basketball_cd' in z:z['篮球cd']=max(1,z.pop('_pvp_saved_basketball_cd')-1)
        if name=='滚桶僵尸' and not alive:
            self.barrels.detach(z,z.get('手持血量',0) or z.get('_pvp_barrel_remaining',0))
        if name=='滚桶僵尸' and z.get('手持血量',0)<=0 and '魅惑' not in z:
            self.break_barrel(z)
        self.pvp64.finish_zombie(z,alive)
        if not alive:
            self.draw_zombie(z)
            return
        if name==SCARECROW:self.pvp61.scarecrow_step(z,0. if (z.get('冰冻',0)>1000 or z.get('黄油',0)>0 or z.get('眩晕',0)>0) else .5 if z.get('冰冻',0)>0 else 1.)
        if z.get('眩晕',0)>0 and not self.g.get('补帧'):
            x,y=z['位置'][:2]
            from .native_scale import factor,unit_root
            height=(b.tile*1.9 if name=='小鬼炮' else self.g['图集'][name+'-帧0'].get_height() if name in ZOMBIES or name in PVP61_ZOMBIES or name=='抓人草触手'
                    else b.tile*(3 if z.get('大小')==3 else 2)*factor(unit_root(z)))
            spark=b.g['pygame'].transform.scale(self.g['图集']['星星'],(max(1,int(b.tile*.2)),max(1,int(b.tile*.2))))
            for n in range(3):
                angle=b.engine.native_tick/50.+n*math.pi*2/3
                self.g['摄像显示'](spark,(x+math.cos(angle)*b.tile*.4-b.tile*.1,y-height-b.tile*.3+math.sin(angle)*b.tile*.08))
        held=z.get('冰冻',0)>1000 or z.get('黄油',0)>0 or z.get('眩晕',0)>0 or '魅惑' in z and z['魅惑']<200
        factor=0. if held else .5 if z.get('冰冻',0)>0 else 1.
        target=self.nearest(z) if '魅惑' in z or name in FLYERS else None
        # Original charm reciprocal melee remains in the native loop. Supply
        # nearest-enemy direction and its missing opposing-Dave melee branch.
        if '魅惑' in z and target:
            tx,ty=self.point(target);x,y=self.point(z)
            z['方向']=1 if wrap_delta(x,tx,b.width)>=0 else -1
            z['_pvp_target']=b.targets.source_id(target)
            if z.get('大小')==2 and not z.get('_pvp_no_attack') and target.get('_pvp_hero') and abs(wrap_delta(x,tx,b.width))+abs(y-ty)<=b.tile and factor and z.get('啃咬',0)<=0:
                self.damage_target(z,target,self.bite_damage(z,target));z['啃咬']=110
        if name=='滚桶僵尸':
            if '魅惑' in z:
                z.update(手持='',手持血量=0);z['_pvp_barrel_discarded']=True
            elif not z.get('_pvp_barrel_broken') and not z.get('_pvp_poison_killed'):
                self.move_barrel(z,factor)
                self.barrels.contact_plants(z,factor)
            if z.get('手持血量',0)>0:z['方向']=z['_pvp_barrel_direction']
        if name in ('海盗船长','小鬼炮'):
            active=True
            fired=False
            if name=='小鬼炮':
                factor=z.get('_pvp_cannon_rate',factor)
                hero=b.avatars['zombie' if '魅惑' in z or b.command_for(z)=='follow' else 'plant']
                if hero.get('_pvp_owner')=='zombie' and z.get('_pvp_seat') in b.present:hero=b.hero_states[z['_pvp_seat']]
                goal=b.rally_destination(z) if b.rally_for(z) is not None and '魅惑' not in z else hero['玩家位置']
                dx=wrap_delta(z['位置'][0],goal[0],b.width)
                z['方向']=1 if dx>=0 else -1
                follow=(b.command_for(z)=='follow' or b.rally_for(z) is not None) and '魅惑' not in z
                active=not follow and abs(dx)<=20*b.tile
                if active:
                    z['位置'][0]=z['_pvp_content_position_before'][0];z['位置'][2]=0.
            if active:z['_pvp_summon_clock']+=factor
            period=1000 if name=='小鬼炮' else 2000
            if active and factor>0 and z['_pvp_summon_clock']>=period:
                if self.summon(z,'海盗鹦鹉' if name=='海盗船长' else '小鬼僵尸',throw=name=='小鬼炮',defer=False):
                    z['_pvp_summon_clock']-=period
                    fired=True
                else:z['_pvp_summon_clock']=period
            if name=='小鬼炮':self.carts.animate(z,active,fired)
        parrot_rally=name in FLYERS and b.rally_for(z) is not None and '魅惑' not in z
        parrot_follow=name in FLYERS and (b.command_for(z)=='follow' or parrot_rally) and '魅惑' not in z
        if parrot_follow:
            hero=b.targets.hero_proxy(z['_pvp_seat'] if z.get('_pvp_seat') in b.present else 'zombie')
            goal=b.rally_for(z) if parrot_rally else None
            goal={'位置':[goal['x'],goal['y']+b.tile,0.,0.]} if goal else hero
            blocker=self.route_target(z,goal,self.enemies(z))
            taunted=self.pvp64.taunt_target(z,None)
            target=taunted or blocker
            if taunted is not None or blocker is not goal:
                parrot_rally=False;parrot_follow=False
        if name in FLYERS and target:
            before=z['_pvp_content_position_before'];z['位置'][:]=before
            tx,ty=self.point(target);sx,sy=self.point(z);dx=wrap_delta(sx,tx,b.width);dy=ty-sy
            if parrot_rally:
                dx=wrap_delta(before[0],b.rally_for(z)['x'],b.width);dy=b.rally_for(z)['y']-sy
            z['_pvp_target']=b.targets.source_id(target)
            if factor:
                length=max(1.,math.hypot(dx,dy));speed=self.g['plk']*110*factor*(.5 if name==CROW else 1.)*b.zsecrets.movement_factor(z)
                # Retain external knockback momentum while discarding the
                # balloon template's constant buoyancy and ground walking.
                # 三叶草's blow is applied as a one-frame flag because this
                # controller rebuilds position from the pre-tick snapshot.
                impulse=before[2] if z.get('受伤',0) or z.pop('_pvp_blown',0) else 0.
                travel=0. if parrot_follow and length<=(.4 if parrot_rally else 2)*b.tile else min(speed,max(0.,length-b.tile*.08))
                z['位置'][0]=(before[0]+dx/length*travel+impulse)%b.width;z['位置'][1]+=dy/length*travel
                z['位置'][2:]=[impulse*.9,0.];z['方向']=1 if dx>=0 else -1
                if not parrot_follow and length<b.tile*.75 and z.get('啃咬',0)<=0:
                    amount=self.bite_damage(z,target)
                    self.damage_target(z,target,amount);z['啃咬']=110
                    self.flyer_bite_effect(z,target)
        self.draw_zombie(z)

    def break_barrel(self,z):
        if z.get('_pvp_barrel_broken') or z.get('_pvp_barrel_discarded') or z.get('_pvp_barrel_detached') or z.get('_pvp_poison_killed'):return
        z['_pvp_barrel_broken']=True;z['手持']='';z['手持血量']=0
        if z.get('_pvp_orphan_barrel'):z['血量']=0
        self.g['增粒子']('滚桶',list(z['_pvp_barrel_position'][:2]),12)
        for n in range(2):self.summon(z,'小鬼僵尸',throw=True,offset=n*.2)

    def barrel_active(self,z):
        return z.get('_pvp_content')=='滚桶僵尸' and z.get('手持血量',0)>0 and '魅惑' not in z

    def barrel_overlap(self,z,e):
        bx,by=z['_pvp_barrel_position'][:2];x,y=e.get('位置',(bx,by))[:2]
        return (wrap_delta(bx,x,self.b.width)/(self.b.tile*.65))**2+((y-(by-self.b.tile*.6))/(self.b.tile*.65))**2<=1.

    def barrel_projectiles(self):
        """Swept round wooden shield, at the drawn barrel rather than the hand.

        The native body collision still runs for shots above/behind the barrel.
        Fire peas penetrate a pushed type-II shield. A detached barrel instead
        takes ordinary damage, including fire, at its own visible circle.
        """
        b=self.b;g=self.g;barrels=[z for z in g['僵尸'] if self.barrel_active(z)]
        if not barrels:return
        amounts={'豌豆':20.,'冰豆':20.,'卷心菜':30.,'玉米粒':5.,'黄油':10.,'西瓜':150.,'冰瓜':150.,'尖刺':10.,'火豆':20.,'蓝火豆':30.}
        kept=[]
        for e in g['实体']:
            name=e.get('名');pos=e.get('位置')
            if name not in amounts or not pos or e.get('_pvp_dart') or e.get('消亡',0)>0:
                kept.append(e);continue
            hit=None
            for z in barrels:
                if not self.barrel_active(z) or b.targets.owner(z)==b.targets.owner(e):continue
                if name in ('火豆','蓝火豆') and not z.get('_pvp_orphan_barrel'):continue
                bx,by=z['_pvp_barrel_position'][:2];radius=b.tile*.68
                dx=wrap_delta(pos[0],bx,b.width);dy=by-b.tile*.6-pos[1]
                vx,vy=pos[2:];length=vx*vx+vy*vy
                t=max(0.,min(1.,(dx*vx+dy*vy)/length)) if length else 0.
                if (dx-vx*t)**2+(dy-vy*t)**2<=radius**2:
                    hit=z;break
            if hit is None:kept.append(e);continue
            # Mark the physical contact so the damage adapter doesn't re-test
            # the pre-step position on the outer edge of the swept circle.
            e['_pvp_barrel_contact']=True
            owner=b.targets.owner(e)
            with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'entities',e):
                index=next(i for i,z in enumerate(g['僵尸']) if z is hit)
                amount=30. if name=='火豆' and '蓝火' in g.get('秘籍',()) else amounts[name]
                if hit.get('_pvp_orphan_barrel') and name in ('豌豆','冰豆'):amount=10.
                g['表面伤害僵尸'](index,e.get('方向',1),amount)
                if hit.get('_pvp_orphan_barrel') and hit.get('血量',0)>0:
                    # The swept impact consumes the projectile before the
                    # native post-hit effects at 103178..103326 can run.
                    if name=='冰豆':hit['冰冻']=1200
                    elif name=='黄油':hit['黄油']=3000
                    elif name in ('火豆','蓝火豆'):hit.pop('冰冻',None)
                # Removing a lob at the forward shield must not skip the
                # original velocity bonus pass. Same formula and done flag;
                # preserve its body-damage semantics independently of armour.
                ns=b.patch.ns;smart=e.get(ns['__pvz_sb_K_SMART'])
                if smart and not e.get(ns['__pvz_sb_K_DAMAGE_DONE']):
                    base=60. if e.get('_pvp_content')=='甜椒投手' else ns['__pvz_sb_BASE_DAMAGE'].get(name,0.)
                    speed=math.hypot(*pos[2:]);initial=max(1.,smart.get('initial_speed',speed))
                    extra=base*.45*max(0.,speed/initial-1.)
                    e[ns['__pvz_sb_K_DAMAGE_DONE']]=True
                    if extra>.5:
                        self.damage_depth+=1
                        try:g['伤害僵尸'](index,e.get('方向',1),extra)
                        finally:self.damage_depth-=1
                b.targets._record_melon_hit(index)
                with b.targets.full_targets():b.projectile_rules.impact(e)
            e.pop('_pvp_barrel_contact',None)
        # A rupture can append two imps, but never discard entities emitted by
        # another synchronous callback while processing this projectile list.
        g['实体']=kept

    def move_barrel(self,z,factor):
        b=self.b;pos=z['_pvp_barrel_position'];direction=z['_pvp_barrel_direction']
        # Horizontal displacement is supplied only by the pusher. The barrel
        # owns its vertical momentum and uses the original collision/gravity.
        distance=wrap_delta(z['位置'][0],pos[0],b.width)*direction
        pushed=max(0.,wrap_delta(z['_pvp_content_position_before'][0],z['位置'][0],b.width)*direction)
        pos[2]=direction*pushed if factor and distance<=1.8*b.tile else 0.
        landed=self.barrel_displacement(pos)
        self.barrels.float_on_water(pos)
        pos[0]%=b.width
        obstacle=b.cell(pos[0]+direction*b.tile*.65,pos[1]-b.tile*.3).get('solid')
        grounded=landed==1 or b.cell(pos[0],pos[1]+b.tile*.1).get('solid')
        if factor and grounded and obstacle:pos[3]=-self.g['plk']*400
        distance=wrap_delta(z['位置'][0],pos[0],b.width)*direction
        if distance<b.tile*.6:
            candidate=(pos[0]-direction*b.tile*.6)%b.width
            if not b.cell(candidate,z['位置'][1]-b.tile*.5).get('solid'):
                z['位置'][0]=candidate
            # Keep walking intent: zeroing vx here puts the next acceleration
            # below native friction's cutoff, permanently stalling both bodies.
        pos[2]=0.  # never retain a self-propelling horizontal velocity

    def draw_zombie(self,z):
        if self.pvp70.draw_zombie(z):return
        name=z.get('_pvp_content')
        if name in PVP61_ZOMBIES:return self.pvp61.draw_zombie(z)
        if name not in ZOMBIES or name==CAPTAIN or self.g.get('补帧'):return
        if name=='小鬼炮':return self.carts.draw(z)
        frame=1+(self.b.engine.native_tick//35)%2 if z.get('啃咬',0) or abs(z['位置'][2])>.01 or name=='海盗鹦鹉' else 0
        if z.get('血量',0)<=0:frame=3
        key=name+'-帧'+str(frame)
        suffix='-灰烬' if '灰烬' in z else '-受伤' if z.get('受伤',0)>0 else ''
        image=self.g['图集'][key+suffix].copy()
        if '灰烬' not in z:
            for enabled,state in ((z.get('冰冻',0)>0,'-冰冻'),('魅惑' in z,'-魅惑')):
                if enabled:
                    overlay=self.g['图集'][key+state].copy();overlay.set_alpha(100)
                    image.blit(overlay,(0,0))
        if z.get('_pvp_poison'):
            from .native_status import tint_poison
            image=tint_poison(image,z['_pvp_poison']['level'],self.b.pg)
        if z.get('方向',1)<0:image=self.g['反'](image)
        x,y=z['位置'][:2];w,h=image.get_size()
        if name=='海盗鹦鹉' and z.get('血量',0)<=0:
            age=max(0,-z['血量'])
            image=self.g['pygame'].transform.rotate(image,-z.get('方向',1)*min(80,age*.35))
            image.set_alpha(max(0,255-int(max(0,age-150)*255/200)))
            w,h=image.get_size()
        self.g['摄像显示'](image,(x-w/2,y-h))
        if z.get('黄油',0)>0 and z.get('血量',0)>0:
            butter=self.b.expansion.saved_atlas.get('黄油砸',self.g['图集']['黄油砸'])
            self.g['摄像显示'](butter,(x-butter.get_width()/2,y-h-butter.get_height()/2))
        if name=='滚桶僵尸' and z.get('手持血量',0)>0:
            self.barrels.draw(z)

    def summon(self,source,name,throw=False,offset=0.,defer=True):
        b=self.b;owner=b.targets.owner(source);x,y=source['位置'][:2]
        budget=b.scripted_spawn_budget
        if not budget.can_spawn(source=source):
            if defer:
                from .scripted_spawn_budget import source_snapshot
                snapshot=source_snapshot(source)
                budget.defer(source,'content:'+name,offset,
                             lambda:self.summon(snapshot,name,throw,offset,defer=False))
            return False
        with b.targets.context('zombie',owner,'summon',source), b._ban_free_spawn():
            from .scripted_spawn_budget import source_snapshot
            child=b.spawn('zombie:'+name,'zombie',x,y-b.tile,source['方向'],True,parent=source_snapshot(source))
        if child is None:return False
        z=b._native_objects[child['id']]
        if owner=='plant':z['魅惑']=200
        if throw:
            z['出场']=500
            z['旋转']=0
            z['位置'][1]=y-1.5*b.tile
            z['位置'][0]+=source['方向']*offset*b.tile
            # Original giant's launch values (native bytes 93390..93496).
            z['位置'][2:]=[source['方向']*b.g['plk']*800,-b.g['plk']*600]
            if source.get('_pvp_content')=='滚桶僵尸':
                bx,by=source['_pvp_barrel_position'][:2]
                z['位置'][:]=[(bx+source['方向']*offset*b.tile)%b.width,by-.75*b.tile,
                              source['方向']*b.g['plk']*(150+offset*100),-b.g['plk']*180]
        b._emit('content_summon',source=source.get('_pvp_id'),entity=z['_pvp_id'],card='zombie:'+name,owner=owner)
        return True
