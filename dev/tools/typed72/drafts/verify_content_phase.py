"""Literal NativeContent damage, projectile and custom-plant composition.

The retained whole-state channels are compared in addition to the new typed
fields. Native drawing commands remain explicit presentation observations.
"""
import ast
import copy
import contextlib
import importlib.util
import math
import sys
import types
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('phase_content_controllers',HERE/'verify_content_controllers.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
shared=base.shared;hero=base.hero;shooting=base.shooting
SOURCE=base.base.SOURCE
VINES=shared.LOCAL/'pvp58_vines.py'
SECRETS=shared.LOCAL/'pvp66_secrets.py'
ENTITY_FIELDS=('名','位置','方向','_pvp_content_ready','_pvp_dart','_pvp_return','_pvp_turned','_pvp_distance',
    '_pvp_speed','_pvp_launch_direction','_pvp_leg_hits','_pvp_primal_knock_hits','_pvp_barrel_contact','_pvp_art_name',
    '_pvp_content','_pvp_plant_kind','_pvp_mortar_bonus_done','上次制导','制导次数')
PLANT_FIELDS=('植物','坐标','植物血','_pvp_content','_pvp_id','睡觉','_pvp70_clock','_pvp_head_clock','_pvp_head_age',
    '_pvp_head_phase','_pvp_parent','_pvp_head_target','_pvp_head_color','_pvp_head_gone','_pvp_head_crushed',
    '_pvp_basin_removed','_pvp_head_hits','_pvp_heads','_pvp_was_asleep','_pvp_head_point','_pvp_head_goal',
    '_pvp_head_start','_pvp_head_aim','_pvp_interval','_pvp_before_shot','_pvp_before_cd','_pvp_vine_clock',
    '_pvp_vine_produced','_pvp_awake_forever','_pvp_lantern_timer','_pvp_max_hp','_pvp_hardening_form',
    '冰冻','黄油','眩晕','灰烬','_pvp_basin_terrain','_pvp_content_age','_pvp_attack_clock')


def selected_body(path,outer,names):
    tree=ast.parse(path.read_text(encoding='utf8'))
    parent,=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==outer]
    found=[n for n in parent.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if len(found)!=len(names):raise ValueError('literal wrapper source ambiguity')
    return compile(ast.Module(body=found,type_ignores=[]),str(path),'exec')


def reference():
    ref=base.reference();env=dict(math=math,sys=sys,types=types,contextmanager=contextlib.contextmanager,__package__=shared.PACKAGE)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    for key in ('GAS','DARTS'):env[key]=hero.constant(SOURCE,key)
    env['FLYERS']=ref['content_zombies']['FLYERS']
    env['PLANTS']=hero.constant(base.base.CATALOG,'PLANTS')
    scale=dict(FACTOR={},HIT_TOLERANCE_TILES=hero.constant(shooting.projectiles.SCALE,'HIT_TOLERANCE_TILES'))
    shooting.projectiles.functions(shooting.projectiles.SCALE,['factor','unit_root','allows_hit'],scale)
    env['native_scale_allows_hit']=scale['allows_hit']
    hero.selected_class(SOURCE,['allows_hit','multi_blue_direct','content_projectile','head_impact','gas_hit',
        'primal_damage','primal_knockback','prepare_dart','clover_blow','apply_frost','projectiles','before_tick','after_plants','barrel_projectiles','plant_art'],
        'Phase',env)
    env['damage_install']=selected_body(SOURCE,'_install',('hit','surface_hit','freeze_hit','knockback','cold_flame','hero_damage'))
    env['gates_install']=selected_body(SOURCE,'_install',('entity','plant_gate','projectile_art'))
    env['particle_install']=selected_body(SOURCE,'_install_plant_visual_lifecycles',('card_particles',))
    install,=[n for n in ast.walk(ast.parse(SOURCE.read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef) and n.name=='_install']
    first,=[i for i,n in enumerate(install.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='solver' for t in n.targets)]
    last,=[i for i,n in enumerate(install.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='add' for t in n.targets)]
    env['ballistics_install']=compile(ast.Module(body=install.body[first:last],type_ignores=[]),str(SOURCE),'exec')
    admission=dict(env,BLACK_ZOMBIES=ref['controller_bites']['BLACK_ZOMBIES'],ZOMBIES=ref['content_zombies']['ZOMBIES'])
    hero.selected_class(SOURCE,['configure'],'Admission',admission);ref['content_admission']=admission
    # A direct dart-step operation executes the exact tail of projectiles;
    # the complete operation below still executes the full original method.
    method=copy.deepcopy(next(n for n in ast.walk(ast.parse(SOURCE.read_text(encoding='utf8')))
                             if isinstance(n,ast.FunctionDef) and n.name=='projectiles'))
    start,=[i for i,n in enumerate(method.body) if isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=='b' for t in n.targets)]
    method.name='dart_step';method.body=method.body[start:]
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(SOURCE),'exec'),env)
    p70=ref['controller70']
    p70['TENTACLE_SECRET']=hero.constant(base.CAT70,'TENTACLE_SECRET')
    hero.selected_class(base.S70,['plant_rate','plant_tick','heads','spawn_head','head_targets','update_heads','head_rest',
        'head_hit','anchor_head','head_only_cells','plant_in','restore_marks','before_tick','remove_basin',
        'water_component','target_in_water','freeze','try_lettuce'],'Plants70',p70)
    vines=dict(__package__=shared.PACKAGE,rest_factor=ref['economy']['rest_factor'])
    for key in ('PUFF_VINE','SUN_VINE','VINE_FIRST','VINE_PERIOD','VINE_YIELD'):
        vines[key]=hero.constant(shared.PVP/'pvp58_catalog.py',key)
    node,=[n for n in ast.parse((shared.PVP/'pvp58_catalog.py').read_text(encoding='utf8')).body
           if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PLANT_VINES' for t in n.targets)]
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(VINES),'exec'),vines)
    vines['VINE_HP']=hero.constant(VINES,'VINE_HP')
    vines['HARDENING_MIN_BASE_HP']=hero.constant(shared.LOCAL/'balance.py','HARDENING_MIN_BASE_HP')
    hero.selected_class(VINES,['configure','coffee_target','wake_cell','tick'],'Vines',vines)
    lantern=dict(math=math)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],lantern)
    for key in ('LANTERN_REACH_TILES','LANTERN_DAMAGE'):lantern[key]=hero.constant(SECRETS,key)
    hero.selected_class(SECRETS,['lantern_pulses','lantern_burn'],'Lantern',lantern)
    p64=ref['mortar_plants']
    for key in ('SWIPE_TICKS','BLAST_TICKS'):p64[key]=hero.constant(shared.PVP/'pvp64_content.py',key)
    hero.selected_class(shared.PVP/'pvp64_content.py',['draw_projectiles','draw_effects'],'MortarDraw',p64)
    sep=ref['controller_september']
    for key in ('PLANTS','ZOMBIES'):sep[key]=hero.constant(shared.SEPTEMBER,key)
    hero.selected_class(shared.SEPTEMBER,['configure','living_enemies','inside','attack','plant_tick','draw_effects'],'SeptemberPlants',sep)
    reeds=dict(math=math,wrap_delta=env['wrap_delta'])
    reed_catalog=shared.PVP/'pvp61_catalog.py';reed_source=shared.PVP/'pvp61_content.py'
    for key in ('LIGHTNING_REED','OVERLOAD_REED','SCARECROW','CROW','ELECTRO_SECRET','ELECTRO_STUN_SECONDS','REED_RANGE','REED_HALF_ANGLE',
        'REED_INTERVAL','LIGHTNING_DAMAGE','LIGHTNING_HERO_DAMAGE','LIGHTNING_JUMPS','LIGHTNING_JUMP_RADIUS',
        'OVERLOAD_DAMAGE','OVERLOAD_CONTACT_DAMAGE','OVERLOAD_HERO_CONTACT','OVERLOAD_HERO_DIRECT'):
        reeds[key]=hero.constant(reed_catalog,key)
    for path,names in ((reed_catalog,('REEDS',)),(reed_source,('ZOMBIES','STUN_TICKS','BOLT_TICKS','COLORS'))):
        nodes=[n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),reeds)
    hero.selected_class(reed_source,['configure','enemies','in_cone','reed_target','plant_tick','strike','lightning',
        'contacts','overload','add_bolt','draw_effects'],'Reeds',reeds)
    ref.update(content_phase=env,content_vines=vines,content_lantern=lantern,phase_scale=scale,phase_reeds=reeds)
    return ref


def native_reference():
    from native_math import NativeMath
    ref=reference();native=NativeMath()
    for key in ('content_phase','content_zombies','controller70','mortar_plants'):
        ref[key]['math']=native
    return ref


class ContentPhaseExtension(base.ContentControllersExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;g=self.g;r=self.controller;env=ref['content_phase']
        self.phase_env=env
        self.phase_seen=False;self.full_content=False;self.phase_events=[];self.phase_draws=[]
        self.damage_installed=False;self.phase_hooks_installed=False;r.damage_depth=0;r.pending_frost=[];r.dart_entities=[];r.dart_broad_phase=True
        ref['phase_scale']['FACTOR']=copy.deepcopy(case['world_rules']['scale'])
        for name,method in env['Phase'].__dict__.items():
            if callable(method):setattr(r,name,types.MethodType(method,r))
        self.phase_before=r.before_tick;self.phase_projectiles=r.projectiles;self.phase_after=r.after_plants
        def before():
            self.record('content_before')
            if self.full_content:self.phase_before()
        def projectiles():
            self.record('content_projectiles')
            if self.full_content:self.phase_projectiles()
        def after():
            self.record('content_after')
            if self.full_content:self.phase_after()
        r.before_tick=before;r.projectiles=projectiles;r.after_plants=after
        self.dart_step=types.MethodType(env['dart_step'],r)
        for name,method in ref['controller70']['Plants70'].__dict__.items():
            if callable(method):setattr(self.z70,name,types.MethodType(method,self.z70))
        self.z70.basins={};self.z70.flashes=[];self.z70.head_cells=set()
        r.zombies56.before_tick=self.z56.before_tick;r.barrels.tick=self.barrels.tick
        r.carts.configure=self.carts.configure;r.zombies56.configure=self.z56.configure;r.barrels.track=self.barrels.track
        self.admit=types.MethodType(ref['content_admission']['Admission'].configure,r)
        # _grave_native_factory is captured before admission wrappers. The
        # later fixture's g factory also appends to its observed unit store,
        # which would incorrectly retain this temporary constructor template.
        b._grave_native_factory=types.FunctionType(ctx.functions['新增僵尸'],g)
        for name in ('before_entities','plant_tick','split_pea_blue','projectile_damage'):setattr(r.pvp64,name,getattr(self.mortars,name))
        r.pvp64.grenades=self.grenadiers.grenades;r.pvp64.update_grenades=self.grenadiers.update_grenades
        for name,method in ref['mortar_plants']['MortarDraw'].__dict__.items():
            if callable(method):setattr(self.mortars,name,types.MethodType(method,self.mortars))
        r.pvp64.draw_projectiles=self.mortars.draw_projectiles
        def draw64():
            self.mortars.blasts=self.grenadiers.blasts;self.mortars.grenades=self.grenadiers.grenades
            self.mortars.draw_effects();self.grenadiers.blasts=self.mortars.blasts
        r.pvp64.draw_effects=draw64
        r.september.c=r;r.september.b=b;r.september.g=g;r.september.effects=[];r.september.bloom_sun_amounts={}
        for name,method in ref['controller_september']['SeptemberPlants'].__dict__.items():
            if callable(method):setattr(r.september,name,types.MethodType(method,r.september))
        self.phase_reeds=ref['phase_reeds']['Reeds']();self.phase_reeds.c=r;self.phase_reeds.b=b;self.phase_reeds.g=g;self.phase_reeds.bolts=[]
        r.pvp61.plant_tick=self.phase_reeds.plant_tick;r.pvp61.draw_effects=self.phase_reeds.draw_effects
        r.vines=ref['content_vines']['Vines']();r.vines.b=b;r.vines.g=g;r.vines.c=r
        self.content_lantern=ref['content_lantern']['Lantern']();self.content_lantern.b=b;self.content_lantern.g=g;self.content_lantern.secrets=set()
        b.secrets66=self.content_lantern
        self.phase_damage_env=dict(env,self=r,b=b,g=g,ns=self.ns,
            damage=g['伤害僵尸'],surface=g['表面伤害僵尸'],ash=g['灰烬僵尸'],knock=g['击退僵尸'],
            flame_hit=self.ns[shooting.P+'chili_fire_hit_one_zombie'],hero=g['掉血'],
            head_scan_code=self.ns[shooting.P+'plant_zombie_head_hit_scan'].__code__)
        r._primal_native_knock=self.phase_damage_env['knock']
        exec(env['damage_install'],self.phase_damage_env)
        r.pvp64.projectile_damage=self.mortars.projectile_damage
        r.draw_dart=lambda e:self.phase_draws.append(['dart',self.birth_index(e),list(e['位置'][:2]),b.engine.native_tick*12%360]) if not g.get('补帧') else None
        old_register=b._register
        def register(obj,card,owner,free,parent):
            if card['id']!='plant:抓人草触手':return old_register(obj,card,owner,free,parent)
            uid='tentacle:'+str(len(self.all_plants));obj.update(_pvp_id=uid,_pvp_owner='plant',_pvp_card=card['id']);b._native_objects[uid]=obj
            self.phase_events.append(['register_tentacle',uid,parent.get('id')])
        b._register=register
        old_spawn=b.engine.spawn_plant
        def spawn(name,row,col,facing,**kwargs):
            if name!='坚果':return old_spawn(name,row,col,facing,**kwargs)
            before=len(self.all_plants);self.spawn(row,col,name,facing);return self.all_plants[before:]
        b.engine.spawn_plant=spawn
        emit=b._emit
        def event(name,**fields):
            if name=='tentacle_spawn':self.phase_events.append([name,fields['source'],fields['entity']])
            elif name=='tentacle_hit':self.phase_events.append([name,fields['source'],fields['head'],fields['target']])
            elif name=='lettuce_freeze':self.phase_events.append([name,fields['source'],[list(v) for v in fields['water']],fields['targets']])
            elif name=='lantern_wake':self.phase_events.append([name,fields['entity'],fields['targets']]);return
            elif name=='lantern_burn':self.phase_events.append([name,fields['entity'],fields['targets']]);return
            else:return emit(name,**fields)
            self.before('phase_event');self.after('phase_event')
        b._emit=event
        b._sync_terrain=lambda:self.phase_events.append(['sync_terrain'])
        gates=dict(env,self=r,b=b,g=g,source_gate=g['_pvp_plant_gate'],entity_gate=g['_pvp_entity_gate'],
            add=lambda name,facing,pos:super(ContentPhaseExtension,self).add_entity(name,facing,pos))
        exec(env['gates_install'],gates);self.phase_gates=gates

    def add_entity(self,name,facing,pos):
        if getattr(self,'full_content',False):return self.phase_gates['entity'](name,facing,pos)
        return super().add_entity(name,facing,pos)

    def install_damage(self):
        if self.damage_installed:return
        g=self.g;e=self.phase_damage_env
        for key,name in (('伤害僵尸','hit'),('表面伤害僵尸','surface_hit'),('灰烬僵尸','freeze_hit'),('击退僵尸','knockback')):g[key]=e[name]
        self.ns[shooting.P+'chili_fire_hit_one_zombie']=e['cold_flame']
        launch=self.ns[shooting.P+'chili_fire_player_hit']
        self.ns[shooting.P+'chili_fire_player_hit']=lambda game,entity,*args,**kwargs:False if entity.get('_pvp_content')=='寒冰辣椒' else launch(game,entity,*args,**kwargs)
        self.damage_installed=True
        g['掉血']=e['hero_damage']

    def operation(self,op):
        name=op['op'];r=self.controller;g=self.g
        if name=='phase_setup':
            self.phase_seen=True;self.full_content=op.get('installed',False);self.installed=self.full_content
            if op.get('damage',True):self.install_damage()
            if not self.phase_hooks_installed:
                hooks=dict(self.phase_env,self=r,b=self.b,g=g,ns=self.ns,particles=g['增粒子'])
                exec(self.phase_env['ballistics_install'],hooks);exec(self.phase_env['particle_install'],hooks)
                g['增粒子']=hooks['card_particles'];self.phase_hooks_installed=True
            secrets=self.b.team_secrets.setdefault('plant',set())
            for enabled,key in ((op.get('gas',False),'secret:毒气'),(op.get('hardening',False),'secret:硬化')):
                if enabled:secrets.add(key)
                else:secrets.discard(key)
            self.content_lantern.secrets={'secret:光疗'} if op.get('phototherapy',False) else set()
            self.phase_damage_env['PLANTS']=list(op.get('custom',[]))
            self.phase_gates['PLANTS']=list(op.get('custom',[]))
            self.phase_env['PLANTS']=list(op.get('custom',[]))
            if self.full_content:
                g['_pvp_plant_gate']=self.phase_gates['plant_gate'];g['_pvp_entity_gate']=self.phase_gates['projectile_art']
                self.phase_damage_env['PLANTS']=list(op.get('custom',[]))
        elif name=='phase_entity':self.add_entity(op['name'],op.get('facing',1.),list(op['position']));self.births[-1].update(copy.deepcopy(op.get('fields',{})))
        elif name=='phase_admit':return self.admit(self.all_plants[op['plant']] if 'plant' in op else self.units[op['unit']],copy.deepcopy(op['card']))
        elif name=='phase_reaim':
            self.ctx.constructor_patch._set_time(op['now']);self.native_time=op['now']
            self.ns[shooting.P+'reaim_projectile'](g,self.births[op['entity']])
        elif name=='phase_particles':
            if op['source_index'] is None:g.pop('l',None)
            else:g['l']=op['source_index']
            g['增粒子'](op['name'],list(op['point']),op['count'])
        elif name=='phase_entity_fields':self.births[op['entity']].update(copy.deepcopy(op['fields']))
        elif name=='phase_prepare_dart':r.prepare_dart(self.births[op['entity']])
        elif name=='phase_darts_separate':
            r.dart_entities=[e for e in g['实体'] if e.get('_pvp_dart')];g['实体']=[e for e in g['实体'] if not e.get('_pvp_dart')]
        elif name=='phase_darts_step':self.dart_step()
        elif name=='phase_frost':r.apply_frost()
        elif name=='phase_before':self.phase_before()
        elif name=='phase_projectiles':self.phase_projectiles()
        elif name=='phase_after':self.phase_after()
        elif name=='phase_vines':r.vines.tick()
        elif name=='phase_lantern':self.content_lantern.lantern_pulses()
        elif name=='phase_plants70_before':self.z70.before_tick()
        elif name=='phase_plant_tick':self.z70.plant_tick(self.all_plants[op['plant']])
        elif name=='phase_configure':
            p=self.all_plants[op['plant']];card=dict(content=op['name'],hp=op.get('hp',6.))
            return self.z70.configure(p,card) or r.vines.configure(p,card)
        elif name=='phase_plant_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='phase_player':
            source=self.units[op['unit']] if 'unit' in op else self.births[op['entity']];owner=self.c.owner(source)
            with self.c.context(op['target'],owner,'zombies' if 'unit' in op else 'entities',source):return g['掉血'](op['amount'])
        elif name=='native_hit_units' and self.phase_seen:
            # The older isolated DeathExtension keeps a private AST namespace.
            # Composition must call the actual installed constructor namespace,
            # where NativeContent replaced hit_one with cold_flame.
            e=self.births[op['entity']];owner=self.c.owner(e)
            with self.c.context('zombie' if owner=='plant' else 'plant',owner,'entities',e):
                return self.ns[shooting.P+'chili_fire_hit_zombies'](g,e,*op['box'],op.get('scale',g['比']),
                    charmed_only=op.get('charmed_only',False),target_rows=None if op.get('rows') is None else set(op['rows']))
        elif name=='phase_hit':
            e=self.births[op['entity']];owner=self.c.owner(e);kind=op.get('kind','ordinary');index=op['target']
            with self.c.context('zombie' if owner=='plant' else 'plant',owner,'entities',e):
                if kind=='ash':return g['灰烬僵尸'](index)
                if kind=='knock':return g['击退僵尸'](index,op['amount'])
                callback=g['表面伤害僵尸' if kind=='surface' or op.get('surface',False) else '伤害僵尸']
                if kind=='head':return r.head_impact(e,index,e.get('方向',1.),op['amount'],callback)
                return callback(index,e.get('方向',1.),op['amount'])
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.phase_seen:return
        row['chili_counts']=[self.ns[shooting.P+name] for name in shooting.peas.chili.COUNTERS]
        def fields(obj,keys):return {key:copy.deepcopy(obj[key]) for key in keys if key in obj}
        records=[fields(p,PLANT_FIELDS) for p in self.all_plants]
        for record in records:
            for key in ('_pvp_head_point','_pvp_head_start','_pvp_head_goal','_pvp_head_aim'):
                if key in record:record[key]=list(record[key])
        for channel in ('all_plants','plants'):
            for record in row[channel]:
                for key in ('_pvp_head_point','_pvp_head_start','_pvp_head_goal','_pvp_head_aim'):
                    if key in record:record[key]=list(record[key])
        row['content_phase']=dict(entities=[fields(e,ENTITY_FIELDS) for e in self.births],plants=records,
            darts=[self.birth_index(e) for e in self.controller.dart_entities],frost=[self.label(t) for t in self.controller.pending_frost],
            depth=self.controller.damage_depth,events=self.phase_events,draws=self.phase_draws,
            cold_hits=[None if '_pvp_ice_chili_hits' not in unit else sorted(unit['_pvp_ice_chili_hits'],key=lambda v:(v is not None,str(v))) for unit in self.units])


def cases():
    output=[];prototype=base.cases()[0][1]
    for index,(content,name) in enumerate((('原始豌豆射手','豌豆'),('原始豌豆射手','蓝火豆'),('甜椒投手','西瓜'),('寒冰辣椒','火'))):
        case=copy.deepcopy(prototype);case['seed']=1290000+index
        ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_entity',name=name,position=[264.,384.,8.,0.],
            fields={'_pvp_owner':'plant','_pvp_content':content,'_pvp_source_entity':'phase-source'}),
            dict(op='phase_hit',entity=0,target=0,amount=5.,kind='ash' if content=='寒冰辣椒' else 'ordinary'),
            dict(op='phase_hit',entity=0,target=0,amount=5.,kind='ash' if content=='寒冰辣椒' else 'surface'),dict(op='phase_frost')])
        output.append(('native-content-damage-'+str(index),case))
    for index,content in enumerate(('回旋镖射手','毒镖射手')):
        case=copy.deepcopy(prototype);case['seed']=1290100+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_entity',name='豌豆',position=[240.,384.,24.,0.],
            fields={'_pvp_owner':'plant','_pvp_content':content}),dict(op='phase_prepare_dart',entity=0)])
        for unused in range(4):ops.extend([dict(op='phase_darts_separate'),dict(op='phase_darts_step')])
        output.append(('native-content-dart-'+str(index),case))
    for index,fire in enumerate((None,'','blue','fire','other')):
        case=copy.deepcopy(prototype);case['seed']=1290200+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_entity',name='僵尸豌豆',position=[264.,384.,8.,0.],
            fields={'_pvp_owner':'zombie','__pvz_sb_zombie_pea_fire':fire}),
            dict(op='phase_player',entity=0,target='plant',amount=1.),dict(op='phase_player',entity=0,target='plant',amount=4.)])
        output.append(('native-content-zombie-pea-player-'+str(index),case))
    for index,(blocked,bite) in enumerate(((False,1.),(False,3.),(True,3.),(None,None))):
        case=copy.deepcopy(prototype);case['seed']=1290300+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='content_zombie_fields',unit=0,
            fields={'_pvp_no_attack':blocked,'_pvp_bite_plant':bite,'_pvp_content':'乌鸦'}),
            dict(op='phase_player',unit=0,target='plant',amount=1.),dict(op='phase_player',unit=0,target='plant',amount=2.)])
        output.append(('native-content-unit-player-'+str(index),case))
    for index,name in enumerate(('','忧郁藤蔓','阳光藤蔓','水盆')):
        case=copy.deepcopy(prototype);case['seed']=1290400+index;ops=case['operations']=case['operations'][:22]
        ops.append(dict(op='phase_setup',installed=True,custom=['原始豌豆射手','回旋镖射手','甜椒投手']))
        if name:
            ops.extend([dict(op='plant_original',name='南瓜头',cell=[8,7],facing=1.),
                dict(op='phase_plant_fields',plant=0,fields={'_pvp_id':'phase-plant','_pvp_owner':'plant'}),
                dict(op='phase_configure',plant=0,name=name)])
        ops.extend([dict(op='phase_entity',name='豌豆',position=[240.,384.,8.,0.],fields={'_pvp_owner':'plant','_pvp_content':'原始豌豆射手'}),
            dict(op='phase_before'),dict(op='phase_projectiles'),dict(op='phase_after')])
        output.append(('native-content-full-phases-'+str(index),case))
    for index,(first,second) in enumerate(((None,None),('cold','cold'),('cold','other'),(None,'cold'))):
        case=copy.deepcopy(prototype);case['seed']=1290500+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='content_zombie_fields',unit=0,fields={'血量':1000.,'冰冻':900.}),
            dict(op='phase_entity',name='火',position=[264.,384.,0.,0.],fields={'_pvp_owner':'plant','_pvp_content':'寒冰辣椒','_pvp_source_entity':first}),
            dict(op='native_hit_units',entity=0,box=[200.,330.,300.,450.]),
            dict(op='fire_write',entity=0,values={'智能火命中':[]}),dict(op='native_hit_units',entity=0,box=[200.,330.,300.,450.]),
            dict(op='phase_entity',name='火',position=[264.,384.,0.,0.],fields={'_pvp_owner':'plant','_pvp_content':'寒冰辣椒','_pvp_source_entity':second}),
            dict(op='native_hit_units',entity=1,box=[200.,330.,300.,450.]),dict(op='phase_frost')])
        output.append(('native-content-cold-flame-repeat-'+str(index),case))
    for index,content in enumerate(('原始豌豆射手','回旋镖射手')):
        case=copy.deepcopy(prototype);case['seed']=1290600+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup',installed=True,custom=[content]),dict(op='plant_original',name='豌豆射手',cell=[8,3],facing=1.),
            dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','射':49.,'射cd':-1.,'植物血':100.},erase=['睡觉']),
            dict(op='phase_plant_fields',plant=0,fields={'_pvp_id':'phase-shooter','_pvp_content':content,'_pvp_interval':100.})])
        ops.extend(dict(op='native_tick',draw=False) for unused in range(3))
        output.append(('native-content-installed-native-shooter-'+str(index),case))
    for index,(projectile,source) in enumerate((('',''),('甜椒投手',''),('','甜椒投手'),('甜椒投手','甜椒投手'))):
        case=copy.deepcopy(prototype);case['seed']=1290700+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_entity',name='西瓜',position=[264.,384.,4.,-1.],fields={'_pvp_owner':'plant','_pvp_content':projectile}),
            dict(op='phase_entity',name='豌豆',position=[0.,0.,0.,0.],fields={'_pvp_owner':'plant','_pvp_content':source}),
            dict(op='chili_scope',entity_source=1,target='zombie',owner='plant',phase='entities',body=[
                dict(op='squash_compute',entity=0,target={'unit':0},point=[480.,330.],velocity=[.4,-.2],speed=4.,direction=1.),
                dict(op='squash_compute',entity=0,target={'unit':0},point=[480.,330.],velocity=[100.,0.],speed=4.,direction=1.)])])
        output.append(('native-content-pepper-ballistic-'+str(index),case))
    for index,content in enumerate(('甜椒投手','原始豌豆射手','阳光藤蔓','水盆','甜薯','原始土豆地雷')):
        case=copy.deepcopy(prototype);case['seed']=1290800+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='plant_original',name='向日葵',cell=[8,7],facing=1.),
            dict(op='phase_plant_fields',plant=0,fields={'_pvp_id':'admitted-plant','_pvp_owner':'plant'}),
            dict(op='phase_admit',plant=0,card=dict(id='plant:'+content,content=content,hp=18.)),dict(op='phase_before')])
        output.append(('native-content-admit-plant-'+str(index),case))
    for index,content in enumerate(('滚桶僵尸','小鬼炮','海盗船长','海盗鹦鹉','雪人僵尸','垃圾桶僵尸')):
        case=copy.deepcopy(prototype);case['seed']=1290900+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_admit',unit=0,card=dict(id='zombie:'+content,content=content,hp=155.,native_hp=177.))])
        output.append(('native-content-admit-zombie-'+str(index),case))
    for index,(projectile,source) in enumerate((('',''),('甜椒投手',''),('','甜椒投手'),('甜椒投手','甜椒投手'))):
        case=copy.deepcopy(prototype);case['seed']=1291000+index;ops=case['operations']=case['operations'][:22]
        ops.extend([dict(op='phase_setup'),dict(op='phase_entity',name='西瓜',position=[100.,330.,5.,-2.],fields={'_pvp_owner':'plant','_pvp_content':projectile}),
            dict(op='service_entity_write',entity=0,values={'智能弹道':{'target_index':0,'initial_speed':5.}}),
            dict(op='phase_entity',name='豌豆',position=[0.,0.,0.,0.],fields={'_pvp_owner':'plant','_pvp_content':source}),
            dict(op='chili_scope',entity_source=1,target='zombie',owner='plant',phase='entities',body=[
                dict(op='phase_reaim',entity=0,now=1.),dict(op='phase_reaim',entity=0,now=1.1)])])
        output.append(('native-content-pepper-reaim-'+str(index),case))
    for index,(source,content,point,name) in enumerate(((0,'甜椒投手',[360.,408.],'向日葵'),(None,'甜椒投手',[360.,408.],'向日葵'),
            (0,'甜椒投手',[360.02,408.],'向日葵'),(0,'',[360.,408.],'向日葵'),(0,'甜椒投手',[360.,408.],'豌豆'))):
        case=copy.deepcopy(prototype);case['seed']=1291100+index;ops=case['operations']=case['operations'][:22]
        case['presentation']=dict(enabled=True,camera=[0.,0.],screen_width=1152.,atlas={
            key:dict(width=8,height=8,pixels=[color]*64) for key,color in (('向日葵',[240,40,30,255]),('甜椒投手',[40,230,50,255]),('豌豆',[10,30,240,255]))})
        ops.extend([dict(op='phase_setup'),dict(op='plant_original',name='向日葵',cell=[8,7],facing=1.),
            dict(op='phase_plant_fields',plant=0,fields={'_pvp_content':content}),
            dict(op='phase_particles',name=name,point=point,count=3,source_index=source),
            dict(op='phase_particles',name='向日葵',point=[361.,408.],count=3,source_index=0)])
        output.append(('native-content-particle-alias-'+str(index),case))
    return output


def paths():return base.paths()+[Path(__file__).resolve(),SOURCE,VINES,SECRETS,shared.LOCAL/'balance.py',
    shared.PVP/'pvp58_catalog.py',HERE/'content_phase_probe.cpp']


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,ContentPhaseExtension,'typed72-native-content-phase',probe_timeout=600))
