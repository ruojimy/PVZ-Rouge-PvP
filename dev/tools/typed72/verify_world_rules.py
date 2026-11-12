"""Differential checks for the installed torch, shell and entity contact paths."""
import ast
import copy
import dis
import functools
import importlib
import marshal
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_shooting as shooting

hero=shooting.hero
peas=shooting.peas
P=shooting.P
ROOT=hero.ROOT
PVP=hero.REF/'modkit/pvp'
LOCAL=ROOT/'tools/pvp72_sources'
TORCH=PVP/'torch_rules.py'
PLANT_ZOMBIES=PVP/'native_plant_zombies.py'
VINES=LOCAL/'pvp58_vines.py'
BATTLE=LOCAL/'native_battle.py'
SEPTEMBER=LOCAL/'native_september_content.py'
ENTITIES=ROOT/'extract/original/regions/entities.py'
SCALE=shooting.projectiles.SCALE
PACKAGE='_typed72_world_rules_reference'

def install_region_code(r,gate):
    physics=importlib.import_module(PACKAGE+'.native_physics')
    bytecode=importlib.import_module(PACKAGE+'.native_bytecode')
    runtime=PVP/'native_runtime.py'
    env=dict(__package__=PACKAGE,source_instructions=bytecode.instructions,_instruction=physics._instruction,
             slice_original=physics.slice_original,REGIONS=hero.constant(runtime,'REGIONS'),_COMPILED={},_GATES={},
             replace_predicate=gate.replace_predicate,inject_iteration_gate=gate.inject_iteration_gate)
    shooting.projectiles.functions(runtime,['original_regions'],env)
    shooting.projectiles.functions(BATTLE,['_gated_regions'],env)
    engine=types.SimpleNamespace(root=r['root'],regions=env['original_regions'](r['root']))
    engine.regions=env['_gated_regions'](engine)
    protection=LOCAL/'native_protection.py'
    env.update(lru_cache=functools.lru_cache,dis=dis,instruction_window=bytecode.instruction_window,
               NativeGateError=gate.NativeGateError)
    shooting.projectiles.functions(protection,['replace_damage_write','plant_write_expected'],env)
    cls=hero.selected_class(protection,('install_basketball',),'Basket',env)
    basket=cls();basket.b=types.SimpleNamespace(engine=engine,g={});basket.install_basketball()
    def install_from(path,count):
        tree=ast.parse(path.read_text(encoding='utf8'))
        statements=[node for node in ast.walk(tree) if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call)
                    and isinstance(node.value.func,ast.Name) and node.value.func.id=='replace_predicate'
                    and isinstance(node.value.args[0],ast.Subscript)
                    and ast.dump(node.value.args[0])==ast.dump(ast.parse("regions['entities']",mode='eval').body)]
        assert len(statements)==count,(path,len(statements))
        env['regions']=engine.regions
        exec(compile(ast.Module(body=sorted(statements,key=lambda n:n.lineno),type_ignores=[]),str(path),'exec'),env)
    install_from(shooting.projectiles.CONTENT,2)
    r['region_base']=engine.regions['entities']
    r['target_code']=engine.regions['unit_target_index']
    r['basket']=cls
    r['visible']=hero.selected_class(BATTLE,('_engine_draws_entity',),'EntityRender',env)._engine_draws_entity

def compile_contact_regions():
    loop=ast.parse(ENTITIES.read_text(encoding='utf8')).body[0]
    def block(source):
        predicate=ast.dump(ast.parse(source,mode='eval').body)
        rows=[n for n in loop.body if isinstance(n,ast.If) and ast.dump(n.test)==predicate]
        assert len(rows)==1,source
        return copy.deepcopy(rows[0])
    class Gate(ast.NodeTransformer):
        def __init__(self,replacements):
            self.lookup={ast.dump(ast.parse(old,mode='eval').body):[name,0] for old,name in replacements}
        def visit(self,n):
            match=self.lookup.get(ast.dump(n))
            if not match:return super().visit(n)
            match[1]+=1
            return ast.copy_location(ast.Call(func=ast.Name(id=match[0],ctx=ast.Load()),args=[],keywords=[]),n)
        def apply(self,tree):
            result=self.visit(tree)
            assert all(count==1 for name,count in self.lookup.values())
            return result
    contact=Gate([("'火了' not in 实体[l]",'_pvp_native_torch_scan'),
                  ("'魅惑' in 僵尸[zz]",'_pvp_plant_zombie_collision_skip'),
                  ("实体[l]['位置'][1] < 僵尸[zz]['位置'][1]",'_pvp_projectile_body_contact')]).apply(block("name in 伤害实体"))
    home=Gate([("僵尸[z]['位置'][1] - 比",'_pvp_homing_aim_y')]).apply(block("'追踪' in 实体[l]"))
    deletion=block('shanchu')
    freeze=next(n for n in ast.walk(deletion) if isinstance(n,ast.If) and ast.dump(n.test)==ast.dump(ast.parse("name == '冰瓜'",mode='eval').body))
    return [compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),str(ENTITIES),'exec') for n in (contact,home,freeze)]

def reference():
    ref=shooting.reference()
    package=types.ModuleType(PACKAGE);package.__path__=[str(LOCAL),str(PVP)];sys.modules[PACKAGE]=package
    gate=importlib.import_module(PACKAGE+'.native_gate')
    env={'replace_predicate':gate.replace_predicate,'math':math,'PREFIX':P}
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    for name in ('PETRIFIED_TORCH_BRAIN_CAP','PETRIFIED_TORCH_REWARD','PETRIFIED_TORCH_SLEEP_SECONDS','PETRIFIED_TORCH_DEATHMATCH_SLEEP_SECONDS'):
        env[name]=hero.constant(PVP/'expansion_catalog.py',name)
    env['PETRIFIED_TORCH_KEY']='zombie:'+hero.constant(PVP/'expansion_catalog.py','PETRIFIED_TORCH')
    for name in ('RAGE_TORCH_SLEEP','RAGE_TORCH_RANGE'):env[name]=hero.constant(LOCAL/'zombie_secret_catalog.py',name)
    vines_catalog=ast.parse((LOCAL/'pvp58_catalog.py').read_text(encoding='utf8'))
    constants=[n for n in vines_catalog.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None) in ('SUN_VINE','PUFF_VINE','PLANT_VINES')]
    exec(compile(ast.Module(body=constants,type_ignores=[]),str(LOCAL/'pvp58_catalog.py'),'exec'),env)
    env['DENSE_SECRET']=hero.constant(LOCAL/'pvp58_catalog.py','DENSE_SECRET')
    shooting.projectiles.functions(VINES,['is_shell'],env)
    env['Torch']=hero.selected_class(TORCH,('__init__','points','convert','tick'),'Torch',env)
    env['TorchBattle']=hero.selected_class(BATTLE,('_petrified_torches','_petrified_torch_reward'),'TorchBattle',env)
    env['Secrets']=hero.selected_class(hero.ZSECRETS,('has','torch_range_scale','torch_sleep_scale'),'TorchSecrets',env)
    env['Vines']=hero.selected_class(VINES,('lookup','dense','_shell_first_peas'),'WorldVines',env)
    env['September']=hero.selected_class(SEPTEMBER,('targetable',),'September',env)
    pz_tree=ast.parse(PLANT_ZOMBIES.read_text(encoding='utf8'))
    pz_cls=next(n for n in pz_tree.body if isinstance(n,ast.ClassDef) and n.name=='NativePlantZombies')
    exec(compile(ast.Module(body=[pz_cls],type_ignores=[]),str(PLANT_ZOMBIES),'exec'),env)
    scale_env=dict(HIT_TOLERANCE_TILES=hero.constant(SCALE,'HIT_TOLERANCE_TILES'))
    shooting.projectiles.functions(SCALE,['allows_hit','factor','unit_root'],scale_env)
    env['native_scale_allows_hit']=scale_env['allows_hit']
    env['Content']=hero.selected_class(shooting.projectiles.CONTENT,('allows_hit','barrel_overlap'),'WorldContent',env)
    env['scale_env']=scale_env
    shrunk=types.ModuleType(PACKAGE+'.native_scale');shrunk.unit_root=scale_env['unit_root']
    assets=types.ModuleType(PACKAGE+'.content_assets');assets.SCALE_TILES={}
    sys.modules[shrunk.__name__]=shrunk;sys.modules[assets.__name__]=assets
    env['shrunk']=shrunk;env['__package__']=PACKAGE
    shooting.projectiles.functions(shooting.projectiles.CONTENT,['homing_aim_y'],env)
    tree=ast.parse(shooting.projectiles.CONTENT.read_text(encoding='utf8'))
    body_contact=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='body_contact')
    env['body_code']=compile(ast.Module(body=[body_contact],type_ignores=[]),str(shooting.projectiles.CONTENT),'exec')
    env['root']=marshal.loads(hero.RAW.read_bytes())
    install_region_code(env,gate)
    env['regions']=compile_contact_regions()
    ref['world_rules']=env
    return ref

class WorldRulesExtension(shooting.ShootingExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        cfg=case['world_rules'];r=ref['world_rules'];b=self.b;g=self.g
        b.width=cfg['width'];b.g=g;b.targets=self.c;b.deathmatch=cfg['deathmatch']
        b.engine.regions={'entities':r['region_base']}
        b._petrified_fire_key=P+'zombie_pea_fire';b._petrified_pea_xy=self.ns[P+'zombie_pea_xy']
        for name in ('_petrified_torches','_petrified_torch_reward'):setattr(b,name,types.MethodType(getattr(r['TorchBattle'],name),b))
        if cfg['rage']:b.zsecrets.team.add('暴怒');b.zsecrets.enabled=True
        for name in ('torch_range_scale','torch_sleep_scale'):
            setattr(b.zsecrets,name,types.MethodType(getattr(r['Secrets'],name),b.zsecrets))
        b.team_secrets={'plant':{'secret:密植'} if cfg['dense'] else set()}
        def resource(side,amount,x,y,source):
            assert (side,source)==('zombie','petrified_torch')
            self.calls.append(['petrified_resource',amount,x,y]);self.before('petrified_resource');self.after('petrified_resource')
        b.resource=resource
        self.vines=r['Vines']();self.vines.b=b;self.vines.g=g;self.vines._targetable=r['September'].targetable
        if self.vines.dense():self.vines._shell_first_peas()
        b.team_seats=lambda team:[team]
        self.ns[P+'doom_zombie_ash_targets']=self.env[P+'doom_zombie_ash_targets']
        g['_pvp_projectile_impact']=b.projectile_rules.impact
        self.pz=r['NativePlantZombies'](b)
        self.torches=r['Torch'](b)
        content=r['Content']();content.b=b;content.g=g
        env={'self':content,'g':g};exec(r['body_code'],env)
        self.regions=r['regions']
        r['scale_env']['FACTOR']=cfg['scale']
        g.update(_pvp_projectile_body_contact=env['body_contact'],_pvp_plant_zombie_collision_skip=self.pz.skip_native_collision,
                 伤害实体=cfg['damaging'],投掷物=cfg['thrown'],math=math)
        r['shrunk'].SCALE_TILES=cfg['heights']
        g['_pvp_homing_aim_y']=lambda:r['homing_aim_y'](g['僵尸'][g['z']],g['比'])
        self.render_log=[]
        if any(op['op'] in ('region_run','track_setup') for op in case['operations']):
            self.bind_region(ctx,r,cfg)

    def bind_region(self,ctx,r,cfg):
        b=self.b;g=self.g;self.periodic=True
        # Use the exact two closures from install_basketball with its original
        # numeric protection service. The bytecode writes are already installed.
        basket=r['basket']();basket.b=b;basket.amount=b.protection.amount
        code=basket.install_basketball.__func__.__code__
        def closure(value):return (lambda:value).__closure__[0]
        for const in code.co_consts:
            if not isinstance(const,types.CodeType) or const.co_name not in ('hit','enemy_plant'):continue
            captures={'self':basket,'b':b}
            fn=types.FunctionType(const,g,closure=tuple(closure(captures[k]) for k in const.co_freevars))
            g['_pvp_basketball_plant_damage' if const.co_name=='hit' else '_pvp_basket_enemy_plant']=fn
        rule=b.projectile_rules;b.rules['melon_splash_damage']=cfg.get('splash',20./3.)
        self.nearest=-1
        def track():
            self.render_log.append(['source',g['l']]);g['离玩家最近']=self.nearest
        g.update(_pvp_entity_gate=track,_pvp_flight_expired=lambda:rule.expired(g['实体'][g['l']]),
                 _pvp_entity_visible=lambda:r['visible'](b),_pvp_plant_squash_area=self.pz.native_squash_area,
                 按时归位=types.FunctionType(ctx.functions['按时归位'],g),
                 实体出界=lambda y,x:y>=len(g['ditu']),摧毁方块=self.destroy_pvp,新增实体=self.add_entity,
                 哪个植物=lambda y,x:self.vines.lookup(y,x),总高=g.get('总高',576.))
        log=self.render_log
        class Surface:
            def __init__(self,key,flip=False,size=None,pixels=None):self.key=key;self.flip=flip;self.size=size;self.pixels=pixels
            def set_alpha(self,value):log.append(['alpha',self.key,value])
            def get_size(self):return self.pixels.get_size()
            def get_at(self,xy):return self.pixels.get_at(xy)
            def __deepcopy__(self,memo):return self
        class Atlas(dict):
            def __missing__(self,key):return Surface(key)
        self.surface=Surface
        def draw(surface,pos,angle=None):log.append(['draw',surface.key,list(pos),surface.flip,angle,surface.size])
        g.update(图集=Atlas({k:Surface(k,pixels=v) for k,v in g['图集'].items()}),摄像显示=draw,旋转摄像显示=draw,反=lambda s:Surface(s.key,True,s.size),
                 变图=lambda s,w,h:Surface(s.key,s.flip,[w,h]))
        native=types.FunctionType(ctx.functions['方向性增粒子'],g)
        def directed(name,pos,count,direction):
            # Both particle functions share one request ledger and battle RNG.
            ctx.particles.append([name,list(pos),count]);return native(name,pos,count,direction)
        g['方向性增粒子']=directed

    def operation(self,op):
        action=op['op'];g=self.g
        if action=='region_fields':
            values=copy.deepcopy(op['values'])
            if '扁' in values:values['扁']=self.surface(values['扁'])
            self.births[op['entity']].update(values);return
        if action=='region_run':
            self.nearest=op.get('nearest',-1)
            g.update(开车=op.get('driving',0.),水=op.get('water','水'));g['摄像机'][1]=op.get('camera_y',0.)
            exec(self.b.engine.regions['entities'],g);return
        if action=='rules_torch_tick':return self.torches.tick()
        if action=='rules_zombie_torch':return self.torches.convert(self.births[op['entity']],True)
        if action=='rules_charmed_tick':return self.pz.ignite_charmed_peas()
        if action=='rules_point':
            p=self.ns[P+'plant_world_point'](g,self.all_plants[op['plant']]);return list(p) if p is not None else None
        if action=='rules_lookup':return self.vines.lookup(*op['cell'],skip_shell=op.get('skip',False))
        if action=='rules_position':self.births[op['entity']]['位置']=list(op['position']);return
        if action=='rules_grave':
            u=self.units[op['unit']]
            for a,k in [('grave','_pvp_grave'),('card','_pvp_card'),('paid','_pvp_torch_brain'),('until','_pvp_torch_sleep_until'),('id','_pvp_id'),('position','位置')]:
                if a in op:u[k]=copy.deepcopy(op[a])
            return
        if action=='rules_plant':
            p=self.all_plants[op['plant']]
            for a,k in [('copy_card','_pvp_copy_card'),('content','_pvp_content'),('id','_pvp_id'),('kind','植物')]:
                if a in op:p[k]=op[a]
            return
        if action in ('rules_strike','rules_home','rules_freeze'):
            l=op['index'];saved=g.get('l');g['l']=l
            try:
                g.update(name=g['实体'][l]['名'],shanchu=False,开车=op.get('driving',0.),离玩家最近=-1 if op.get('nearest') is None else op['nearest'])
                exec(self.regions[('rules_strike','rules_home','rules_freeze').index(action)],g)
                return g['shanchu'] if action=='rules_strike' else None
            finally:
                if saved is None:g.pop('l',None)
                else:g['l']=saved
        return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        row['region_trace']=self.render_log
        for key in ('entities','effect_births','legacy_peas'):
            for entity in row[key]:
                if '扁' in entity:entity['扁']=entity['扁'].key
        row['grave_clocks']=[{k:u[k] for k in ('_pvp_torch_brain','_pvp_torch_sleep_until','_pvp_id') if k in u} for u in self.units]

def cases():
    result=[]
    cfg=dict(dense=False,rage=False,deathmatch=False,width=960.,heights={'小鬼僵尸':1.},scale={'小鬼僵尸':.5})
    table=ast.parse(shooting.plants.TABLES.read_text(encoding='utf8'))
    for key,name in [('damaging','伤害实体'),('thrown','投掷物')]:
        cfg[key]=next(ast.literal_eval(n.value) for n in table.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)==name)
    def base():
        c=shooting.base();c['world_rules']=copy.deepcopy(cfg)
        for unit in c['services']['units']:unit.setdefault('大小',2.)
        for row in c['plant_world']['grid']:
            row.extend(copy.deepcopy(row[-1]) for _ in range(20-len(row)))
        return c
    def plant(col,name):return dict(op='plant_original',cell=[8,col],name=name)
    for i in range(72):
        c=base();c['world_rules'].update(deathmatch=i%2==0,rage=i%3==0)
        c['globals']['秘籍']=['蓝火'] if i%4==1 else []
        y=(408.,432.,600.)[i%3]
        c['operations']=[plant(0,'火炬树桩'),plant(19,'火炬树桩'),
            dict(op='rules_grave',unit=0,grave=True,card='zombie:石化火炬',paid=(0.,135.,150.)[i//3%3],until=0.,position=[940.,y,0.,0.]),
            peas.entity((880.,y,0.,0.),('冰豆','豌豆','僵尸豌豆')[i%3]),dict(op='rules_torch_tick'),
            dict(op='rules_position',entity=0,position=[45.,y+(0.,24.,80.)[i//9%3],0.,0.]),dict(op='rules_torch_tick'),
            dict(op='rules_zombie_torch',entity=0),dict(op='rules_torch_tick')]
        result.append(('torch-periodic-'+str(i),c))
    for i in range(48):
        c=base();c['world_rules'].update(rage=i%2==0,deathmatch=i%4<2)
        c['operations']=[dict(op='rules_grave',unit=0,grave=True,card='zombie:石化火炬',paid=135.,until=100.,position=[240.,400.,0.,0.]),
            dict(op='pea_environment',tick=99),peas.entity(),dict(op='rules_zombie_torch',entity=0),dict(op='pea_environment',tick=100),
            dict(op='rules_zombie_torch',entity=0),peas.entity(name='豌豆'),peas.write(1,**{P+'charmed_plant_zombie_pea':True}),
            dict(op='pea_environment',tick=(3099,3100,4599,4600,6099,6100,9099,9100)[i//4%8]),dict(op='rules_charmed_tick')]
        result.append(('torch-cap-and-wake-'+str(i),c))
    for i in range(64):
        c=base();c['world_rules']['dense']=i%2==0
        kind=('南瓜头','模仿者','向日葵','忧郁藤蔓')[i//2%4]
        c['operations']=[plant(5,'向日葵'),plant(5,'南瓜头'),plant(5,'向日葵'),
            dict(op='rules_plant',plant=1,kind=kind,copy_card=('plant:抓人草','plant:幽灵辣椒')[i//8%2],content=('','抓人草','阳光藤蔓','幽灵辣椒')[i//16]),
            dict(op='rules_lookup',cell=[8,5]),dict(op='rules_lookup',cell=[8,5],skip=True),
            dict(op='chili_scope',unit_source=0,target='plant',owner='zombie',phase='entities',body=[dict(op='rules_lookup',cell=[8,5]),dict(op='rules_lookup',cell=[8,5],skip=True)]),
            peas.entity((264.,405.6,0.,0.)),peas.write(0,**{P+'zombie_pea_fire':'blue'}),dict(op='pea_hit',entity=0),dict(op='rules_point',plant=0)]
        result.append(('shell-lookup-and-splash-'+str(i),c))
    for i in range(104):
        c=base();kind=cfg['damaging'][i%len(cfg['damaging'])]
        c['operations']=[dict(op='roster_replace',targets=[1]),shooting.write(1,位置=[300.,430.,0.,0.],方向=1. if i//13%2 else -1.),
            peas.entity((300.+(0.,14.4,-14.4,0.)[i//26],400.,0.,0.),kind),
            dict(op='rules_strike',index=0,driving=i%2),peas.write(0,追踪=1.),dict(op='rules_home',index=0,nearest=0)]
        if kind=='冰瓜':c['operations'].append(dict(op='rules_freeze',index=0))
        result.append(('native-contact-'+str(i),c))
    def fields(i,v):return dict(op='region_fields',entity=i,values=v)
    for i in range(98):
        c=base();c['seed']=92800+i
        kind=('爆炸','大泡泡','蓝泡泡','模仿','小丑爆炸','毁灭2','火','火豆','篮球x','玉米炮','窝瓜x','尖刺','星星','僵尸豌豆')[i%14]
        v={'消亡':(0,899,929,959,989,1009,1023)[i//14]}
        if i%2:v['黑白']=False
        if i%3==0:v['旋转']=17
        if i%4==0:v['穿墙']=0
        if i%7==2:v['扁']=137
        if kind=='火豆':v['火了']=i
        if kind=='窝瓜x':v.update(大坐=2,坐下=i//14)
        if kind=='玉米炮':v.update(锁敌=i%2,落点=i%20)
        if kind=='尖刺':v['追踪']=1
        c['operations']=[dict(op='roster_replace',targets=[1]),peas.entity((411.,175.,1.,-2.),kind,1 if i%2 else -1),fields(0,v)]
        c['operations'] += [dict(op='region_run',nearest=0) for _ in range(3)]
        result.append(('region-animation-'+str(i),c))
    for i in range(84):
        c=base();c['seed']=92900+i;water=i%3==0
        row,col=5,6
        c['plant_world']['grid'][row][col]={'方块':'水' if water else '空'}
        c['plant_world']['grid'][row+1][col]={'方块':'土块'}
        c['plant_world']['empty_blocks']=['空','水']
        kind=('钢门','玉米粒','窝瓜x','缠绕海草x','豌豆','西瓜','冰瓜')[i%7]
        v={'牛顿':0}
        if i%2:v['入水']=True
        if i%4==1:v['弹跳x']=3
        if kind=='窝瓜x':v.update(大坐=5,坐下=0)
        if kind=='缠绕海草x':v['消亡']=100
        if i//7%3==1:v['消亡']=1023
        c['operations']=[dict(op='roster_replace',targets=[]),peas.entity((312.,(263.,287.9,288.1,580.)[i//7%4],(0.,-.01,4.)[i%3],2.),kind),fields(0,v)]
        c['operations'] += [dict(op='region_run') for _ in range(3)]
        result.append(('region-water-and-impact-'+str(i),c))
    for i in range(36):
        c=base();c['operations']=[dict(op='roster_replace',targets=[]),peas.entity((510.,225.,1.,1.),'金属'),
            fields(0,{'吸引':(True,48,49,50,98,99)[i%6],'吸引初位置':[510.,225.],'吸引末位置':[440.,370.]}),
            peas.entity((650.,380.,-2.,1.),'爆炸'),fields(1,{'消亡':1024}),
            dict(op='squash_roster',entities=([0,1,0],[1,0,1],[0,0,1])[i//6%3])]
        c['operations'] += [dict(op='region_run') for _ in range(3)]
        result.append(('region-list-and-attract-'+str(i),c))
    for i in range(52):
        c=base();kind=cfg['damaging'][i%len(cfg['damaging'])];facing=1 if i%2 else -1
        # The pixels are admitted on both sides, so the native particle code
        # samples color and velocity and advances the real match RNG.
        pixels=[[0,0,0,0] if (x+i)%5==0 else [51,82,31,255] for x in range(64)]
        c['presentation']=dict(enabled=True,atlas={kind:dict(width=8,height=8,pixels=pixels)})
        c['operations']=[dict(op='roster_replace',targets=[1]),shooting.write(1,位置=[300.,430.,0.,0.],方向=-facing),
                         peas.entity((300.,400.,0.,0.),kind,facing)]
        v={'大坐':3,'坐下':0} if kind=='窝瓜x' else {'火了':1} if kind=='火豆' else {}
        if v:c['operations'].append(fields(0,v))
        c['operations'] += [dict(op='region_run'),dict(op='region_run')]
        result.append(('region-directional-particles-'+str(i),c))
    for i in range(16):
        c=base();col=(0,19)[i%2]
        c['plant_world']['grid'][5][(col+(-1 if col==0 else 1))%20]={'方块':'梯子块'}
        c['operations']=[dict(op='roster_replace',targets=[]),peas.entity(((col+.5)*48.,264.,0.,0.),'玉米炮'),
                         fields(0,{'消亡':1024,'锁敌':1,'落点':col}),dict(op='region_run'),dict(op='region_run')]
        result.append(('region-cannon-seam-'+str(i),c))
    return result

if __name__=='__main__':
    extra=[Path(__file__).resolve(),ROOT/'tools/typed72/verify_shooting.py',ROOT/'tools/typed72/world_rules_probe.cpp',TORCH,PLANT_ZOMBIES,VINES,BATTLE,SEPTEMBER,ENTITIES,PVP/'native_gate.py',PVP/'native_bytecode.py',PVP/'native_physics.py',PVP/'expansion_catalog.py',LOCAL/'zombie_secret_catalog.py',LOCAL/'pvp58_catalog.py']
    sys.exit(shooting.main(extra,reference,cases,WorldRulesExtension,'typed72-installed-torch-shell-and-contact'))
