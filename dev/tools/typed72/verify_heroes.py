"""Independent hero-chain oracle: current PvP72 AST + original hurt bytecode.

No game replacement is asserted. This probes the typed target/hero chain only;
ordinary zombie wrappers, full tick, renderer and transport need separate proof.
"""
import argparse
import ast
import builtins
import copy
import dis
import hashlib
import json
import marshal
import math
import random
import shutil
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

# Embedded CPython intentionally ignores most script sys.path defaults.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_stages import difference, sha, Sprite
import proxy_reference
import evidence_store
import evidence_archive

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71'
TARGETS = ROOT/'tools/pvp72_sources/native_targets.py'
BATTLE = ROOT/'tools/pvp72_sources/native_battle.py'
BALANCE = REF/'modkit/pvp/balance68006.py'
ZSECRETS = ROOT/'tools/pvp72_sources/zombie_secrets.py'
ZCATALOG = ROOT/'tools/pvp72_sources/zombie_secret_catalog.py'
PHYSICS = REF/'modkit/pvp/native_physics.py'
CATALOG = REF/'modkit/pvp/pvp64_catalog.py'
RAW = REF/'reverse_engineered/raw/pvzrouge.pyc'
PROJECTILES = REF/'modkit/pvp/native_projectiles.py'
PROXY_REFERENCE_PATHS=proxy_reference.paths()


def selected_class(path, names, class_name, env):
    tree = ast.parse(path.read_text(encoding='utf8'), str(path))
    selected = [n for c in tree.body if isinstance(c, ast.ClassDef)
                for n in c.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if set(n.name for n in selected) != set(names):raise ValueError('missing reference method')
    cls = ast.ClassDef(name=class_name, bases=[], keywords=[], body=selected, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    exec(compile(module, str(path), 'exec'), env)
    return env[class_name]


def constant(path, key):
    tree = ast.parse(path.read_text(encoding='utf8'), str(path))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id==key for t in n.targets):
            return ast.literal_eval(n.value)
    raise ValueError('missing reference constant '+key)


def load_reference():
    physics = ast.parse(PHYSICS.read_text(encoding='utf8'),str(PHYSICS))
    state_keys = next(ast.literal_eval(n.value) for c in physics.body if isinstance(c,ast.ClassDef) and c.name=='NativePhysics'
                      for n in c.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='state_keys' for t in n.targets))
    env = dict(__builtins__=builtins.__dict__, math=math, dis=dis, types=types, contextmanager=contextmanager,
               NativePhysics=types.SimpleNamespace(state_keys=state_keys))
    exec(compile(BALANCE.read_text(encoding='utf8'),str(BALANCE),'exec'),env)
    tree = ast.parse(TARGETS.read_text(encoding='utf8'),str(TARGETS))
    # Do not import/install cppcore: the oracle executes the Python source.
    body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.Assign))]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(TARGETS),'exec'),env)
    # Load only the real projectile birth helpers for tag_entity's relative
    # import; do not load a live game or replace their source implementations.
    package='_typed72_oracle_pvp';parent=types.ModuleType(package);parent.__path__=[]
    sys.modules[package]=parent;module=types.ModuleType(package+'.native_projectiles')
    ptree=ast.parse(PROJECTILES.read_text(encoding='utf8'),str(PROJECTILES))
    pbody=[n for n in ptree.body if isinstance(n,ast.Assign) or isinstance(n,ast.FunctionDef) and n.name in ('fire_form','begin_flight')]
    exec(compile(ast.Module(body=pbody,type_ignores=[]),str(PROJECTILES),'exec'),module.__dict__)
    sys.modules[module.__name__]=module;env['__package__']=package;env['_begin_flight']=module.begin_flight
    env.update(STURDY_SECRET=constant(CATALOG,'STURDY_SECRET'),STURDY_REDUCTION=constant(CATALOG,'STURDY_REDUCTION'),
               team_of=lambda s:'plant' if s.startswith('plant') else 'zombie',
               LAST_STAND_SECONDS=constant(ZSECRETS,'LAST_STAND_SECONDS'))
    env['PREFIX']=constant(ZCATALOG,'PREFIX')
    ztree=ast.parse(ZCATALOG.read_text(encoding='utf8'),str(ZCATALOG))
    exec(compile(ast.Module(body=[n for n in ztree.body if isinstance(n,ast.FunctionDef) and n.name in ('names','is_zombie_secret')],type_ignores=[]),str(ZCATALOG),'exec'),env)
    battle=selected_class(BATTLE,('_hero_damage_factor','_hero_damaged'),'BattleOracle',env)
    secrets=selected_class(ZSECRETS,('seat_has','hero_amount','_last_stand_step'),'SecretsOracle',env)
    raw=marshal.loads(RAW.read_bytes())
    functions={c.co_name:c for c in raw.co_consts if isinstance(c,types.CodeType)}
    hurt=functions['掉血']
    if hurt.co_firstlineno!=197 or len(hurt.co_code)!=96:raise ValueError('unexpected original hurt function')
    patched=bytearray(hurt.co_code);patched[:2]=bytes((dis.opmap['JUMP_ABSOLUTE'],8))
    return env,battle,secrets,functions,hurt.replace(co_code=bytes(patched))


def decode_attack(value):
    if isinstance(value,dict) and set(value)=={'tuple'}:return tuple(decode_attack(v) for v in value['tuple'])
    if isinstance(value,list):return [decode_attack(v) for v in value]
    return value


def oracle(case, reference, extension_factory=None):
    env,Battle,Secrets,functions,pvp_hurt=reference
    rng=random.Random(case.get('seed',1));events=[];sounds=[];particles=[];states=[];chili_keys=[];held_proxy_sources=[]
    c=env['NativeTargets'].__new__(env['NativeTargets'])
    b=Battle();b.targets=c;b.avatars=copy.deepcopy(case['heroes']);b.hero_states=dict(b.avatars)
    for key,value in case.get('aliases',{}).items():b.avatars[key]=b.hero_states[value]
    b.players={k:dict(secrets=list(v.get('secrets',[])),hp=v.get('hp',40.),marked_until=v.get('marked_until',0.),
                     stats=dict(hero_damage=v.get('hero_damage',0.))) for k,v in case['players'].items()}
    b.engine=types.SimpleNamespace(native_tick=case.get('tick',0));b.time=case.get('time',0.)
    b.rules=dict(mark_seconds=case.get('mark_seconds',8.))
    def emit(event_type,**data):events.append(dict(type=event_type,**data))
    b._emit=emit;z=Secrets();b.zsecrets=z;z.b=b;z.by_seat={k:env['names'](v['secrets']) for k,v in b.players.items() if k.startswith('zombie')}
    z.last_stand={};z.last_stand_used=set()
    presentation=case.get('presentation',{})
    g=copy.deepcopy(case['globals']);g.update(__builtins__=builtins.__dict__,随=rng.randint,c=copy.deepcopy,jdz=abs,plk=.0048,比=48.,
        设置={'粒子效果':presentation.get('enabled',False)},摄像机=presentation.get('camera',[0.,0.]),
        总宽=presentation.get('screen_width',1152.),图集={k:Sprite(v) for k,v in presentation.get('atlas',{}).items()},粒子=[],
        _pvp_native_tick=b.engine.native_tick,_pvp_water_ice=0.,random=rng,僵尸=[],实体=[])
    constructor_patch=proxy_reference.install(g,functions)
    g['播音']=lambda name:sounds.append(name)
    emitter=types.FunctionType(functions['增粒子'],g)
    def particle(name,pos,count):
        particles.append([name,copy.deepcopy(pos),count]);return emitter(name,pos,count)
    g['增粒子']=particle
    c.g=g;c.heroes=b.avatars;c.context_keys=env['_HERO_KEY_SET'];c.active=None;c.damage_kind='normal';c.sequence=0;c.budgets={};c.proxies={}
    c.native_hurt=types.FunctionType(pvp_hurt,g);c.originals={'掉血':types.FunctionType(functions['掉血'],g)}
    c.proxy_factory=g['新增僵尸']
    if case.get('damage_factors',True):c.damage_factor=b._hero_damage_factor
    if case.get('last_stand',True):c.last_stand=z.hero_amount
    c.on_damage=b._hero_damaged if case.get('damage_events',True) else None
    sources=copy.deepcopy(case['sources'])
    for s in sources:
        if s is not None and '_pvp_instant_attack' in s:s['_pvp_instant_attack']=decode_attack(s['_pvp_instant_attack'])
    for phase,indexes in case.get('phase_sources',{}).items():
        g[{'plants':'植物','zombies':'僵尸','entities':'实体'}[phase]]=[sources[i] if i is not None else None for i in indexes]
    def get_proxy(side):
        return c.hero_proxy(side)
    extension=extension_factory(types.SimpleNamespace(controller=c,battle=b,globals=g,secrets=z,sources=sources,
        get_proxy=get_proxy,functions=functions,sounds=sounds,particles=particles,events=events,constructor_patch=constructor_patch)) if extension_factory else None
    hero_keys=env['_HERO_KEYS']
    def snap():
        row=dict(heroes=b.avatars,
            players={k:dict(hp=p['hp'],marked_until=p['marked_until'],hero_damage=p['stats']['hero_damage'],secrets=p['secrets']) for k,p in b.players.items()},
            globals={k:g[k] for k in hero_keys if k in g},water_ice=g['_pvp_water_ice'],sequence=c.sequence,
            budgets=[[list(k),list(v)] for k,v in c.budgets.items()],events=events,
            proxies={k:dict(p) for k,p in c.proxies.items()},
            sounds=sounds,particles=particles,particle_state=g['粒子'],rng=list(rng.getstate()[1]),
            last_stand=z.last_stand,last_stand_used=[s for s in ('plant','zombie','plant2','zombie2') if s in z.last_stand_used],
            source_ids=[s.get('_pvp_id') if s is not None else None for s in sources],
            active={k:c.active[k] for k in ('target','owner','phase')} if c.active else None)
        if case.get('tagging'):
            row['source_state']=[]
            for source in sources:
                item=copy.deepcopy(source)
                if item is not None and '_pvp_instant_attack' in item:item['_pvp_instant_attack_text']=str(item.pop('_pvp_instant_attack'))
                row['source_state'].append(item)
        if extension:extension.snapshot(row)
        return copy.deepcopy(row)
    def operations(ops,record=True):
        for op in ops:
            action=op['op'];result=None
            if action=='context':
                source=extension.entity_source(op['entity_source']) if 'entity_source' in op else extension.source(op['unit_source']) if 'unit_source' in op else sources[op['source']] if op.get('source') is not None else None
                with c.context(op['target'],op['owner'],op['phase'],source,decode_attack(op.get('attack'))):operations(op['body'],record)
            elif action=='batch':operations(op['body'],False)
            elif action=='damage':result=c.damage_hero(op['target'],op['amount'],op.get('kind','normal'))
            elif action=='player_damage':result=c._player_damage(op['amount'])
            elif action=='source_amount':result=c.hero_source_amount(0.,op['target'])
            elif action=='write':
                target=g if op['target']=='globals' else c.heroes[op['target']]
                target.update(copy.deepcopy(op.get('values',{})))
                for key in op.get('erase',[]):target.pop(key,None)
            elif action=='position':(g if op['target']=='globals' else c.heroes[op['target']])['玩家位置'][:]=op['values']
            elif action=='proxy':get_proxy(op['target'])
            elif action=='proxy_try':
                roster=g['僵尸'];before=list(roster);caught=False
                try:get_proxy(op['target'])
                except Exception:caught=True
                result=dict(caught=caught,roster_preserved=g['僵尸'] is roster and len(roster)==len(before) and all(a is b for a,b in zip(roster,before)))
            elif action=='proxy_inspect':
                p=c.proxies[op['target']];h=c.heroes[op['target']]
                result=dict(position_alias=p['位置'] is h.get('玩家位置'),source_kind=p.get('僵尸'),source_owner=p.get('_pvp_owner'),
                    in_world_units=any(u is p for u in g['僵尸']))
            elif action=='rng_advance':result=rng.randint(op['low'],op['high'])
            elif action=='proxy_hold':held_proxy_sources.append(get_proxy(op['target']))
            elif action=='proxy_forget':c.proxies.pop(op['target'],None)
            elif action=='proxy_held_kinds':result=[p.get('僵尸') for p in held_proxy_sources]
            elif action=='proxy_write':
                # Existing proxies are not resynced before native writes.
                if op['target'] not in c.proxies:get_proxy(op['target'])
                c.proxies[op['target']][op['key']]=op['value']
            elif action=='clock':b.engine.native_tick=op['tick'];g['_pvp_native_tick']=op['tick'];b.time=op['time']
            elif action=='last_stand_step':z._last_stand_step()
            elif action=='index':g['l']=op['value']
            elif action=='owner':result=c.owner()
            elif action=='tag':
                c.tag_entity(sources[op['entity']],op.get('owner'),sources[op['source']] if op.get('source') is not None else None)
            elif action=='begin_flight':
                env['_begin_flight'](sources[op['entity']],sources[op['source']] if op.get('source') is not None else None)
            elif action=='source_position':sources[op['source']]['位置']=list(op['value'])
            elif action=='chili_key':
                source=c.source()
                token=source.get('_pvp_instant_attack',(c.source_id(source),int(g.get('_pvp_native_tick',0))))
                key=(c.owner(),tuple(token) if isinstance(token,list) else token);hash(key)
                if key not in chili_keys:chili_keys.append(key)
                result=chili_keys.index(key)
            elif extension:result=extension.operation(op)
            else:raise ValueError(action)
            if record:
                row=snap();row.update(op=action,result=result);states.append(row)
    if extension:extension.operations=operations
    operations(case['operations'])
    return states


def base():
    frame={'玩家位置':[120.,240.,0.,0.],'玩家血量':40.,'玩家倒地':0.,'玩家恢复':0.,'玩家受伤':0.,'玩家方向':1.,
           '玩家皮肤':'普通戴夫','模式':'我是僵尸','冻水':0.,'秘籍':[]}
    return dict(seed=73,globals=copy.deepcopy(frame),heroes={s:dict(copy.deepcopy(frame),_pvp_max_hp=40.) for s in ('plant','zombie','plant2','zombie2')},
                players={s:dict(secrets=[],hp=40.) for s in ('plant','zombie','plant2','zombie2')},sources=[],operations=[])


def context(body,target='zombie',owner='plant',phase='entities',source=None,**extra):
    return dict(op='context',target=target,owner=owner,phase=phase,source=source,body=body,**extra)


def make_cases():
    cases=[]
    def add(label,c):cases.append((label,c))
    # Compare the full source precedence cross-product, including missing vs
    # explicit None, obsolete shadowed rules, reflected projectiles and seats.
    sources=[None,{}, {'名':None}, {'植物':None,'_pvp_plant_kind':'小喷菇'},
        {'植物':'忧郁蘑菇'},{'名':'尖刺','_pvp_cattail':True}]
    for name in ('豌豆','冰豆','火豆','蓝火豆','僵尸豌豆','星星','西瓜','冰瓜','玉米粒','玉米','黄油','卷心菜','窝瓜x','未知'):
        for splash in (False,True):sources.append({'名':name,'_pvp_melon_splash':splash})
    for plant in ('胆小菇','胆小鬼','海蘑菇','小喷菇','大喷菇','雷蘑菇','寒冰菇','地刺','地刺王','钢地刺','未知'):
        sources.extend([{'植物':plant},{'_pvp_plant_kind':plant},{'植物':plant,'_pvp_content':'忧郁藤蔓'}])
    for content in ('原始豌豆射手','甜椒投手','忧郁藤蔓'):
        for color in ('','fire','blue','unknown'):
            for splash in (False,True):sources.append({'名':'火豆','_pvp_content':content,'_pvp_fire_color':color,'_pvp_melon_splash':splash})
    sources += [{'_pvp_fire_color':None,'__pvz_sb_zombie_pea_fire':'blue','名':'火豆','_pvp_melon_splash':True},
                {'僵尸':'墓碑吞噬者僵尸'},{'僵尸':'普通僵尸','_pvp_variant':'黑普通僵尸'},
                {'僵尸':None,'_pvp_variant':'黑橄榄僵尸'}, {'名':'豌豆','_pvp_no_hero_attack':True}]
    for blue in (False,True):
        for side in ('plant','zombie','plant2','zombie2'):
            for i,source in enumerate(sources):
                c=base();c['sources']=[source];c['globals']['秘籍']=['蓝火'] if blue else []
                body=[dict(op='source_amount',target=side),dict(op='player_damage',amount=1.),dict(op='player_damage',amount=1.25)]
                c['operations']=[context(body,target=side,owner='zombie' if side.startswith('plant') else 'plant',source=0)]
                add('balance-%s-%s-%s'%(blue,side,i),c)
    for target in ('plant','zombie','plant2','zombie2'):
        for owner in ('plant','zombie','plant2','zombie2'):
            for source in (None,{}, {'_pvp_owner':'zombie'},{'_pvp_owner':'unknown'}, {'魅惑':None},{'魅惑':0},{'_pvp_owner':'plant2'}):
                c=base();c['sources']=[source];c['operations']=[dict(op='proxy',target=target),context([
                    dict(op='owner'),dict(op='damage',target=target,amount=.125),
                    dict(op='proxy_write',target=target,key='冰冻',value=1200.),
                    dict(op='proxy_write',target=target,key='黄油',value=-2.),
                    dict(op='proxy_write',target=target,key='眩晕',value=88.),
                    dict(op='proxy_write',target=target,key='血量',value=-1024.),
                    dict(op='proxy_write',target=target,key='灰烬',value=0.),
                    dict(op='proxy_write',target=target,key='血量',value=999.),
                ],target=target,owner=owner,source=0)]
                add('allegiance-%s-%s-%s'%(target,owner,len(cases)),c)
    for target,secret in (('plant','secret:强健'),('zombie','zsecret:石更！'),('zombie','zsecret:最后攻势'),('plant','强健'),('zombie','最后攻势')):
        for down in (0.,1.,90.):
            for maximum in (None,20.,40.,120.):
                c=base();c['heroes'][target]['玩家血量']=50.;c['heroes'][target]['玩家倒地']=down
                if maximum is None:c['heroes'][target].pop('_pvp_max_hp')
                else:c['heroes'][target]['_pvp_max_hp']=maximum
                c['players'][target]['secrets']=[secret]
                c['sources']=[{'植物':'火爆辣椒'},{'名':'火','_pvp_instant_attack':{'tuple':['a',1]}},{'名':'火','_pvp_instant_attack':{'tuple':['a',1]}}]
                c['operations']=[context([dict(op='damage',target=target,amount=100.,kind=k) for k in ('ash','ash','swallow','normal')],
                    target=target,owner='zombie' if target=='plant' else 'plant',source=i) for i in range(3)]
                c['operations']+=[dict(op='last_stand_step'),dict(op='clock',tick=9999,time=39.999),dict(op='last_stand_step'),dict(op='clock',tick=10000,time=40.),dict(op='last_stand_step')]
                add('cap-reduction-%s-%s-%s'%(secret,down,maximum),c)
    # Nested contexts expose stale snapshot healing, direct writes, aliases,
    # None-vs-missing fields, noncombat restoration and position list identity.
    for missing in (False,True):
        for alias in (False,True):
            c=base();c['sources']=[{'植物':'火爆辣椒'},{'魅惑':0}]
            if missing:
                for f in ('玩家恢复','玩家受伤','玩家皮肤','辣飞天'):
                    for h in c['heroes'].values():h.pop(f,None)
                    c['globals'].pop(f,None)
                c['globals']['__pvz_sb_chili_launch_lock_until']=None
            if alias:
                c['heroes']['zombie2']['_pvp_seat']='zombie2';c['aliases']={'zombie':'zombie2'}
                c['players']['zombie2']['secrets']=['zsecret:石更！']
            c['operations']=[dict(op='proxy',target='zombie'),context([
                dict(op='write',target='globals',values={'玩家血量':33.,'玩家倒地':3.,'speedmax':88.,'冻水':25.}),
                dict(op='position',target='globals',values=[99.,77.,-2.,3.]),
                context([dict(op='damage',target='zombie',amount=7.),dict(op='damage',target='plant',amount=1.),
                         dict(op='write',target='globals',values={'辣飞天':42.,'玩家血量':37.})],target='plant',owner='zombie',source=1),
                dict(op='damage',target='zombie',amount=3.),
                dict(op='write',target='globals',erase=['玩家恢复'])],phase='plants',source=0)]
            add('nested-%s-%s'%(missing,alias),c)
    for phase in ('plants','zombies','entities','other'):
        c=base();c['sources']=[{'名':'豌豆'},{'魅惑':None}];c['phase_sources']={p:[0,1,None] for p in ('plants','zombies','entities')}
        ops=[]
        for i in (-1,0,1,2,3,None):ops.extend([dict(op='index',value=i),dict(op='owner'),dict(op='player_damage',amount=1.)])
        c['operations']=[context(ops,phase=phase)]
        add('implicit-'+phase,c)
    for attack in (None,'',0,False,[],['x',4],{'tuple':['x',4]},"('native:1', None)"):
        for projectile in (False,True):
            c=base();s={'_pvp_instant_attack':attack}
            if projectile:s['名']=None
            c['sources']=[s];body=[dict(op='damage',target='zombie',amount=3.,kind='ash')]*4
            c['operations']=[context(body,source=0),dict(op='clock',tick=1,time=.004),context(body,source=0)]
            add('attack-'+str(len(cases)),c)
    # Force both pruning paths, stable timestamp ties and updates of old keys.
    for prune in (False,True):
        c=base();c['heroes']['zombie']['玩家血量']=1e6;c['sources']=[{}];ops=[]
        for i in range(2100):
            tick=(i*3 if prune else (i//7)%17)
            ops.extend([dict(op='clock',tick=tick,time=tick/250.),context([dict(op='damage',target='zombie',amount=.001,kind='ash')],source=0,attack='a:%s'%i)])
        c['operations']=[dict(op='batch',body=ops)]
        add('budget-pruning-'+str(prune),c)
    for enabled in (False,True):
        c=base();c['heroes']['zombie']['玩家皮肤']='疯狂戴夫';c['sources']=[{'_pvp_id':''}]
        c['presentation']=dict(enabled=enabled,camera=[0.,0.],screen_width=1152.,atlas={'血':dict(width=2,height=2,pixels=[[255,0,0,255],[0,0,0,0],[128,1,2,0],[255,0,0,255]])})
        c['operations']=[context([dict(op='damage',target='zombie',amount=.125),dict(op='write',target='globals',values={'玩家倒地':0.}),
                                  dict(op='damage',target='zombie',amount=2.7)],source=0)]
        add('blood-particles-'+str(enabled),c)
    for mode in ('正常模式','我是僵尸'):
        c=base();c['globals']['模式']=mode;c['globals']['玩家皮肤']='疯狂戴夫'
        c['operations']=[dict(op='player_damage',amount=2.),dict(op='damage',target='zombie',amount=999.)]
        add('outside-context-'+mode,c)
    parents=[{}, {'植物':'香蒲'}, {'植物':'杨桃'}, {'植物':'胆小菇'}, {'植物':'小喷菇'},
             {'_pvp_id':'hero:plant2'}, {'_pvp_owner':None}, {'_pvp_original_owner':None,'_pvp_root_source':None},
             {'_pvp_owner':'plant2','_pvp_original_owner':'zombie','_pvp_root_source':'root'},
             {'_pvp_flight_limit_tiles':None}, {'_pvp_flight_limit_tiles':64.}, {'_pvp_flight_limit_tiles':1.},
             {'_pvp_instant_attack':None}, {'_pvp_instant_attack':{'tuple':['parent',27]}},
             {'_pvp_instant_attack':['parent',27]}, {'_pvp_cattail':None}]
    names=('豌豆','冰豆','火豆','蓝火豆','僵尸豌豆','篮球','泡泡','海泡泡','尖刺','星星','其他',None)
    for i,parent in enumerate(parents):
        for n,name in enumerate(names):
            for preset in (False,True):
                c=base();c['tagging']=True;entity={'名':name}
                if (i+n)%3:entity['位置']=[12.,-48.,1.,2.]
                if preset:entity.update(_pvp_owner=None,_pvp_original_owner='zombie',_pvp_source_entity=None,
                    _pvp_root_source='old-root',_pvp_instant_attack=None,_pvp_cattail=True,火了=None,
                    _pvp_flight_last=[1.,2.],_pvp_flight_distance=17.,_pvp_flight_form=['old',False,'fire'],_pvp_flight_limit_tiles=17.)
                c['sources']=[copy.deepcopy(parent),entity]
                c['operations']=[context([dict(op='tag',entity=1,source=0),dict(op='chili_key'),
                    dict(op='source_position',source=1,value=[99.,88.,2.,3.]),dict(op='tag',entity=1,source=0)],source=0)]
                add('tag-source-%d-%d-%s'%(i,n,preset),c)
    for source in (None,{}, {'名':'尖刺','位置':[3.,4.,0.,0.]}, {'名':'豌豆','位置':[3.,4.,0.,0.]}):
        c=base();c['tagging']=True;c['sources']=[source,{'名':'豌豆','位置':[1.,2.,0.,0.]}]
        c['operations']=[context([dict(op='tag',entity=1),dict(op='begin_flight',entity=1)],source=0),
                         dict(op='tag',entity=1,owner='zombie',source=1)]
        add('tag-implicit-self-'+str(len(cases)),c)
    # Hero keys deliberately collapse str(tuple) with a literal of that text;
    # ordinary chili keys must distinguish them. Lists normalize to tuples.
    c=base();c['tagging']=True;c['sources']=[{'植物':'火爆辣椒','_pvp_instant_attack':token} for token in
        ({'tuple':['x',1]},['x',1],"('x', 1)",0,False,'0',True,1,'True',None,[],{'tuple':[]})]
    c['sources']+=[{'植物':'火爆辣椒'}]
    c['operations']=[context([dict(op='chili_key'),dict(op='damage',target='zombie',amount=.1,kind='ash')],source=i) for i in range(len(c['sources']))]
    c['operations'] += [dict(op='clock',tick=1,time=.004)]+[context([dict(op='chili_key')],source=i) for i in range(len(c['sources']))]
    add('tag-attack-key-equivalence',c)
    for seed in (0,1,73,721,4294967297):
        for side in ('plant','zombie','plant2','zombie2'):
            for mode in ('正常模式','我是僵尸','极难模式','末日模式'):
                c=base();c['seed']=seed;c['globals']['模式']=mode
                c['heroes'][side]['玩家位置']=[32.+seed%19,144.,-7.,11.];c['heroes'][side]['玩家方向']=-1.
                c['operations']=[dict(op='proxy_try',target=side),dict(op='proxy_inspect',target=side),
                    dict(op='rng_advance',low=-999,high=999),dict(op='proxy',target=side),
                    dict(op='position',target=side,values=[320.,-64.,7.,-11.]),dict(op='proxy_inspect',target=side),
                    dict(op='write',target=side,values={'玩家位置':[800.,96.,1.,2.]}),dict(op='proxy_inspect',target=side),
                    dict(op='proxy',target=side),dict(op='proxy_inspect',target=side),dict(op='rng_advance',low=-999,high=999)]
                add('proxy-template-%s-%s-%s'%(seed,side,mode),c)
    for side in ('plant','zombie','plant2','zombie2'):
        for key in ('魅惑','死亡','消亡','出土','僵尸','大小','防具','防具血量','手持','手持血量'):
            c=base();c['operations']=[dict(op='proxy_write',target=side,key=key,value=value) for value in (None,0,999,'converted')]
            c['operations'].append(dict(op='proxy_inspect',target=side));add('proxy-conversion-%s-%s'%(side,key),c)
        for cached in (False,True):
            for target in (side,'globals'):
                for key in ('玩家血量','玩家位置'):
                    if target=='globals' and key=='玩家血量':continue
                    c=base();c['operations']=([dict(op='proxy',target=side)] if cached else [])
                    c['operations'] += [dict(op='write',target=target,erase=[key]),dict(op='proxy_try',target=side),
                        dict(op='rng_advance',low=0,high=100),dict(op='write',target=target,values={key:40. if key=='玩家血量' else [120.,240.,0.,0.]}),
                        dict(op='proxy_try',target=side),dict(op='proxy_inspect',target=side)]
                    add('proxy-failure-%s-%s-%s-%s'%(side,cached,target,key),c)
        c=base();c['operations']=[dict(op='proxy_hold',target=side),dict(op='proxy_forget',target=side),
            dict(op='proxy_held_kinds'),dict(op='rng_advance',low=-500,high=500),dict(op='proxy_try',target=side),
            dict(op='proxy_inspect',target=side),dict(op='proxy_forget',target=side),dict(op='proxy_held_kinds')]
        add('proxy-retained-source-'+side,c)
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--filter',default='');args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(args.exe).resolve()
    paths=[TARGETS,BATTLE,BALANCE,ZSECRETS,ZCATALOG,PHYSICS,CATALOG,PROJECTILES,RAW,exe,Path(__file__).resolve(),ROOT/'tools/typed72/verify_stages.py',
           ROOT/'tools/typed72/hero_probe.cpp',ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths+=PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'))
    paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths}
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    cases=[(label,c) for label,c in make_cases() if args.filter in label]
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    reference=load_reference()
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=oracle(c,reference)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n')
                diff=difference(want,got);row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%100==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    summary=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-hero-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),
        tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['ordinary unit damage wrappers','full tick','render entry','network','replay'])
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=summary['passed'])


if __name__=='__main__':sys.exit(main())
