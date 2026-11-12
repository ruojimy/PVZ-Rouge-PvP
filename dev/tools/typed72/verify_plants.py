"""Raw plant bytecode + literal grave/chili-terrain AST on the same world.

Raw placement is exercised in full. This does not substitute it for the
pending PvP admission/registration or the remaining death-effect chain.
"""
import argparse
import ast
import builtins
import copy
import json
import math
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import verify_protection as protection
import verify_targets as targets
import verify_patch as patch
import verify_projectiles as projectiles
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT
TABLES=ROOT/'extract/original/regions/unit_tables.py'
FUNCTIONS=ROOT/'extract/original/functions.py'


def load_terrain_reference():
    names=('float','randint','sign','grid','tile_at','block_name','empty_block_names','chili_surface_overlay_names',
        'chili_has_plant_slot','is_chili_pass_through_block_name','is_chili_surface_overlay','is_chili_ground_block',
        'chili_fire_column','chili_cell_at','chili_lane_row_from_pos','chili_int_or_none','update_chili_zombie_row_hint',
        'gravebuster_zombie_cell','clear_gravebuster_grave_cell','place_grave_from_gravebuster_zombie',
        'spawn_gravebuster_plant_from_zombie','play_named_sound')
    tree=ast.parse(patch.PATCH.read_text(encoding='utf8'),str(patch.PATCH));wanted={patch.PREFIX+n for n in names}
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    if {n.name for n in selected}!=wanted:raise ValueError('missing terrain reference functions')
    constants,_=patch.patch_reference();env=dict(constants,__builtins__=builtins.__dict__)
    env[patch.PREFIX+'log']=lambda *a:None;env[patch.PREFIX+'math']=math
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(patch.PATCH),'exec'),env)
    env['content_reference']=projectiles.load_projectiles()
    nodes=[n for n in ast.walk(ast.parse(hero.BATTLE.read_text(encoding='utf8'),str(hero.BATTLE))) if isinstance(n,ast.FunctionDef) and n.name=='keep_bedrock']
    if len(nodes)!=1:raise ValueError('bedrock source ambiguity')
    env['bedrock_code']=compile(ast.Module(body=nodes,type_ignores=[]),str(hero.BATTLE),'exec')
    env['bedrock_name']=hero.constant(hero.BATTLE,'BEDROCK');return env


class PlantExtension(targets.TargetExtension):
    def __init__(self,ctx,case,pref,reference):
        super().__init__(ctx,case,pref);self.cfg=case['plant_world'];cfg=self.cfg;self.all_plants=[];self.held=[];self.calls=[];self.hooks={};self.periodic=False
        outer=self
        class Row(list):
            def __getitem__(self,index):
                return super().__getitem__(index%len(self) if outer.periodic and isinstance(index,int) else index)
        self.g.update(ditu=[Row(copy.deepcopy(row)) for row in cfg['grid']],植物=[],重要方块=[],kong=list(cfg['empty_blocks']),
            水平面=cfg['water_surface'],比=cfg.get('tile',48.),plk=cfg.get('tile',48.)/10000.,天=cfg.get('day',''),tian=cfg.get('sky',''),
            模仿=cfg.get('imitation',''),boss战=cfg.get('boss_battle',False),所有植物=list(cfg['catalog']['plants']),投手植物=list(cfg['catalog']['lobbers']),
            夜间植物=list(cfg['catalog']['night_plants']),参战僵尸图=list(cfg['catalog']['lottery_zombies']))
        self.g['出界']=lambda y,x:y<0 or y>=len(self.g['ditu']) or (not self.periodic and (x<0 or x>=len(self.g['ditu'][0])))
        self.g['不封顶出界']=lambda y,x:y>=len(self.g['ditu']) or (not self.periodic and (x<0 or x>=len(self.g['ditu'][0])))
        names=('种植植物','清除植物','哪个植物','哪个无南瓜植物','摧毁方块','摧毁实方块','增加重要方块','位移处理')
        self.raw={n:types.FunctionType(ctx.functions[n],self.g) for n in names};self.g.update(self.raw)
        self.g.update(清除植物=self.clear,种植植物=self.plant,增加重要方块=self.important)
        self.env=reference
        for n in ('gravebuster_zombie_grave_count','gravebuster_zombie_plant_count'):self.env[patch.PREFIX+n]=0
        for u,fields in zip(self.units,cfg.get('units',[])):u.update(copy.deepcopy(fields))
        env=reference['content_reference'];env['FACTOR']={};env[patch.PREFIX+'PLANT_ZOMBIE_CONFIG']={}
        self.b.g=self.g;self.b.width=1920.;self.b.tile=self.g['比'];self.b.patch=types.SimpleNamespace(ns=env)
        self.b.protection=types.SimpleNamespace(amount=self.g['_pvp_damage_amount'])
        self.content=env['NativeContent']();self.content.b=self.b;self.content.g=self.g
        self.flying=env['FlyingPlants']();self.flying.b=self.b;self.flying.c=self.content
        self.b.projectile_rules=env['NativeProjectiles'].__new__(env['NativeProjectiles']);self.b.projectile_rules.b=self.b
        bedrock_env=dict(self=self.b,destroy_block=self.raw['摧毁方块'],BEDROCK=reference['bedrock_name'])
        exec(reference['bedrock_code'],bedrock_env);self.destroy_pvp=bedrock_env['keep_bedrock']

    def spawn(self,*args):
        try:return self.raw['种植植物'](*args)
        finally:
            for p in self.g['植物']:
                if not any(p is old for old in self.all_plants):self.all_plants.append(p)

    def before(self,name):
        if self.hooks.get(name,{}).get('fail_before'):raise RuntimeError('injected lifecycle failure')

    def after(self,name):
        cfg=self.hooks.pop(name,{})
        if 'body' in cfg:self.operations(cfg['body'],False)
        if cfg.get('fail_after'):raise RuntimeError('injected lifecycle failure')

    def clear(self,y,x):
        self.calls.append(['clear',y,x]);self.before('clear');result=self.raw['清除植物'](y,x);self.after('clear');return result

    def plant(self,y,x,name,facing):
        self.calls.append(['plant',y,x,name,facing]);self.before('plant');result=self.spawn(y,x,name,facing);self.after('plant');return result

    def important(self,y,x,name):
        self.calls.append(['important',y,x,name]);self.before('important');result=self.raw['增加重要方块'](y,x,name);self.after('important');return result

    def operation(self,op):
        action=op['op'];result=None
        if action=='plant_original':
            try:self.spawn(*op['cell'],op['name'],op.get('facing',1.))
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
        elif action=='plant_write':self.all_plants[op['plant']].update(copy.deepcopy(op['values']))
        elif action=='content_hit':
            source=self.all_plants[op['plant_source']] if 'plant_source' in op else self.units[op['unit_source']] if 'unit_source' in op else self.ctx.sources[op['source']]
            target=self.all_plants[op['target']['plant']] if isinstance(op['target'],dict) else self.target(op['target'])
            self.throw_raw=op.get('throw_raw',False)
            old=source.get('方向','__missing__');source['方向']=op.get('facing',1.)
            try:self.content.damage_target(source,target,op['amount'],op.get('surface',False),op.get('kind','content'))
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
            finally:
                self.throw_raw=False
                if old=='__missing__':source.pop('方向',None)
                else:source['方向']=old
        elif action in ('content_point','content_contact'):
            target=self.all_plants[op['target']['plant']] if isinstance(op['target'],dict) else self.target(op['target'])
            result=list(self.content.point(target)) if action=='content_point' else self.flying.target_contact({},target,*op['start'],*op['delta'])
        elif action=='find_plant':result=self.raw['哪个无南瓜植物' if op.get('exclude_pumpkin',False) else '哪个植物'](*op['cell'])
        elif action=='clear_plant':result=self.clear(*op['cell'])
        elif action=='destroy_block':
            try:(self.destroy_pvp if op.get('pvp',False) else self.raw['摧毁实方块' if op.get('solid_only',False) else '摧毁方块'])(*op['cell'])
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
        elif action=='tile_replace':
            y,x=op['cell'];self.g['ditu'][y][x]=copy.deepcopy(op['value'])
        elif action=='hold_tile':
            y,x=op['cell'];self.held.append(self.g['ditu'][y][x])
        elif action=='plant_roster_replace':self.g['植物']=[self.all_plants[i] for i in op['plants']]
        elif action=='lifecycle_hook':self.hooks[op['name']]={k:v for k,v in op.items() if k not in ('op','name')}
        elif action in ('grave','grave_plant','grave_cell','chili_hint'):
            unit=self.units[op['unit']]
            name={'grave':'place_grave_from_gravebuster_zombie','grave_plant':'spawn_gravebuster_plant_from_zombie',
                  'grave_cell':'gravebuster_zombie_cell','chili_hint':'update_chili_zombie_row_hint'}[action]
            fn=self.env[patch.PREFIX+name]
            result=fn(self.g,unit,force=op.get('force',False)) if action=='chili_hint' else fn(self.g,unit)
            if action=='grave_cell':result=list(result[:2]) if result[2] is not None else None
        elif action=='chili_lane':result=self.env[patch.PREFIX+'chili_lane_row_from_pos'](self.g,list(op['position']),self.g['比'])
        elif action=='terrain_query':
            y,x=op['cell'];name=self.g['ditu'][y][x%len(self.g['ditu'][0])]['方块'];result=[name in self.g['kong'],name in ('水','黑水')]
        elif action=='displace':
            pos=list(op['position']);self.periodic=op.get('periodic',False)
            try:collision=self.raw['位移处理'](pos,op.get('size',0.))
            finally:self.periodic=False
            result=dict(motion=pos,collision=collision)
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row);row.update(plants=self.g['植物'],all_plants=self.all_plants,terrain=self.g['ditu'],held_tiles=self.held,
            important_blocks=self.g['重要方块'],imitation=self.g['模仿'],lifecycle_calls=self.calls,
            grave_counts=[self.env[patch.PREFIX+n] for n in ('gravebuster_zombie_grave_count','gravebuster_zombie_plant_count')],
            row_hints=[{k:u[k] for k in ('牛顿','__pvz_sb_chili_zombie_row_hint') if k in u} for u in self.units])


def catalog():
    return dict(plants=hero.constant(TABLES,'所有植物'),lobbers=hero.constant(TABLES,'投手植物'),night_plants=hero.constant(TABLES,'夜间植物'),lottery_zombies=['普通僵尸','撑杆僵尸','铁桶僵尸'])


def base(rows=8,cols=7):
    c=hero.base();c.update(tagging=True,units=[],damage={})
    c['plant_world']=dict(grid=[[{'方块':'空' if y<rows-2 else '草'} for x in range(cols)] for y in range(rows)],
        empty_blocks=['空','水','黑水','梯子块'],water_surface=rows-1,tile=48.,day='白天',sky='蓝天',imitation='双发射手',boss_battle=False,catalog=catalog(),units=[])
    return c


def unit(x=120.,y=240.,facing=1.):
    return dict(body={'僵尸':'普通僵尸','防具':'','手持':'','血量':0.,'防具血量':0.,'手持血量':0.,'方向':facing,'位置':[x,y,0.,0.],'受伤':0.,'手持受伤':0.},source={'_pvp_owner':'zombie'})


def make_cases():
    cases=[];tree=ast.parse(FUNCTIONS.read_text(encoding='utf8'),str(FUNCTIONS));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='种植植物')
    names=list(catalog()['plants'])
    for n in ast.walk(fn):
        if isinstance(n,ast.Compare) and isinstance(n.left,ast.Name) and n.left.id=='拿中':
            for v in n.comparators:
                values=[v.value] if isinstance(v,ast.Constant) and isinstance(v.value,str) else ast.literal_eval(v) if isinstance(v,(ast.Tuple,ast.List)) else []
                for value in values:
                    if value not in names:names.append(value)
    names+=['自定义投手','自定义夜草','未知原始植物']
    secrets=['石果','龙蒺藜','雷霆','地雷','小喷','早八','硬化']
    configurations=[(mode,held,day,sky,seed) for mode in ('正常模式','我是僵尸','抽奖模式') for held in ([],secrets)
        for day,sky in (('白天','蓝天'),('白天','红天'),('黑夜','蓝天')) for seed in (725,727)]
    configurations += [('正常模式',[s],'白天','蓝天',730+i) for i,s in enumerate(secrets)]
    for mode,held,day,sky,seed in configurations:
        c=base();c['seed']=seed;c['globals']['模式']=mode;c['globals']['秘籍']=list(held);cfg=c['plant_world'];cfg.update(day=day,sky=sky)
        cfg['catalog']['lobbers'].append('自定义投手');cfg['catalog']['night_plants'].append('自定义夜草')
        c['operations']=[dict(op='plant_original',cell=[n%5,(n//5)%7],name=name,facing=-1. if n%2 else 1.) for n,name in enumerate(names)]
        c['operations'] += [dict(op='find_plant',cell=[0,0]),dict(op='clear_plant',cell=[0,0]),dict(op='find_plant',cell=[0,0],exclude_pumpkin=True)]
        cases.append(('plant-constructor-'+str(len(cases)),c))
    for i in range(48):
        c=base();c['seed']=810+i;c['globals']['模式']='抽奖模式';c['units']=[unit() for _ in range((0,9,10,39)[i%4])]
        c['plant_world']['boss_battle']=bool(i%2);c['plant_world']['catalog']['plants']=['睡莲','咖啡豆','豌豆射手']
        c['operations']=[dict(op='plant_original',cell=[2,2],name='模仿者') for n in range(8)];cases.append(('lottery-retries-'+str(i),c))
    for n,name in enumerate(('空','草','石','水','黑水','雪','花盆块','坟墓','车底')):
        for surface in (2.,6.):
            for solid in (False,True):
                c=base();c['plant_world']['water_surface']=surface
                c['operations']=[dict(op='plant_original',cell=[2,2],name='向日葵'),dict(op='plant_original',cell=[3,2],name='坚果'),
                    dict(op='plant_original',cell=[3,2],name='南瓜头'),dict(op='plant_original',cell=[3,2],name='豌豆射手'),
                    dict(op='tile_replace',cell=[3,2],value={'方块':name,'植物':False}),dict(op='hold_tile',cell=[3,2]),
                    dict(op='find_plant',cell=[3,2]),dict(op='find_plant',cell=[3,2],exclude_pumpkin=True),
                    dict(op='destroy_block',cell=[3,2],solid_only=solid),dict(op='clear_plant',cell=[3,2]),
                    dict(op='terrain_query',cell=[3,-5]),dict(op='displace',position=[120.,143.99,.5,1.],size=0.),
                    dict(op='destroy_block',cell=[7,2]),dict(op='destroy_block',cell=[-1,2])]
                if n%3==0:
                    pixels=[[180,50,30,255],[0,0,0,0],[80,100,20,255],[0,0,0,255]]
                    c['presentation']=dict(enabled=True,camera=[0.,0.],screen_width=1152.,atlas={k:dict(width=2,height=2,pixels=pixels) for k in ('花盆',name)})
                cases.append(('terrain-destroy-'+str(len(cases)),c))
    for i in range(32):
        c=base();coords=([-1,-1],[8,0],[0,7],[-9,0])[i%4];name=('豌豆射手','花盆','睡莲','模仿者')[(i//4)%4]
        c['operations']=[dict(op='plant_original',cell=coords,name=name,catch=True)];cases.append(('plant-partial-'+str(i),c))
    positions=[(x,y) for x in (-48.,0.,24.,72.,216.,240.,288.) for y in (0.,48.,240.,288.,400.)]
    for i,(x,y) in enumerate(positions):
        for block in ('草','水','黑水',None):
            c=base(7,5);c['units']=[unit(x,y,facing=(-1.,0.,1.)[i%3])]
            c['plant_world']['grid'][4][2]=None if block is None else {'方块':block,'植物':True,'里方块':'石','长出':5.,'水纹':2.}
            c['operations']=[dict(op='plant_original',cell=[4,2],name='向日葵'),dict(op='plant_original',cell=[4,2],name='南瓜头')]
            if block is None:c['operations']=[]
            c['operations'] += [dict(op='hold_tile',cell=[4,2]),dict(op='grave_cell',unit=0),dict(op='grave',unit=0),dict(op='grave_plant',unit=0)]
            cases.append(('grave-position-'+str(len(cases)),c))
    for i in range(72):
        c=base();u=unit(120.,(144.,191.999,240.)[i%3]);u['body']['位置'][3]=(.999,1.,1.001)[(i//3)%3];c['units']=[u]
        fields={'牛顿':(None,0.,.1,.100001)[i%4]}
        if i%3:fields['__pvz_sb_chili_zombie_row_hint']=None if i%3==1 else 10.75
        c['plant_world']['units']=[fields];names_overlay=('花盆块','梯子块','自定义梯子块','坟墓','雪','睡莲块','自定义空','石')
        c['plant_world']['empty_blocks'].append('自定义空');c['plant_world']['grid'][4][2]={'方块':names_overlay[i%8],'植物':i%7==0}
        c['operations']=[dict(op='chili_lane',position=u['body']['位置']),dict(op='chili_hint',unit=0),dict(op='chili_hint',unit=0,force=True),dict(op='grave_cell',unit=0)]
        cases.append(('chili-row-hint-'+str(i),c))
    for i in range(12):
        c=base();c['units']=[unit(120.,240.)];c['plant_world']['grid'][4][2].update(植物=False,kong=True,花盆=True,智能石块占位=True,里方块='石',摧=1.,雪消失=2.,长出=3.,水纹=4.,水纹cd=5.,睡莲=-1.)
        replacement=({'方块':'水','植物':True},{'方块':'石','植物':True},None)[i%3]
        hook=dict(op='lifecycle_hook',name='clear',fail_before=i%4==0,fail_after=i%4==1,body=[dict(op='tile_replace',cell=[4,2],value=replacement)])
        c['operations']=[dict(op='plant_original',cell=[4,2],name='向日葵'),dict(op='plant_original',cell=[4,2],name='南瓜头'),dict(op='hold_tile',cell=[4,2]),hook,
            dict(op='lifecycle_hook',name='important',fail_before=i%3==0,fail_after=i%3==1),dict(op='grave',unit=0),
            dict(op='lifecycle_hook',name='plant',fail_before=i%3==0,fail_after=i%3==1),dict(op='grave_plant',unit=0),dict(op='clear_plant',cell=[4,2])]
        # A before-failure hook remains installed, as in the actual callback.
        # Do not ask the final explicit clear to ignore an unhandled exception.
        if i%4==0:c['operations'].pop()
        cases.append(('grave-callback-'+str(i),c))
    for i in range(144):
        c=base();plant=('魅惑菇','向日葵','坚果','自定义')[i%4]
        owner=('zombie','plant','plant2','zombie2')[i%4];target_owner=('plant','zombie',None)[i//4%3]
        c['sources']=[{'_pvp_owner':owner,'名':'豌豆'}]
        if i%7==0:c['sources'][0]['魅惑']=None
        c['damage']=dict(until=50,factor=.25,cards={'plant:test':True})
        c['operations']=[dict(op='plant_original',cell=[3,2],name=plant),dict(op='plant_write',plant=0,values={
            '_pvp_owner':target_owner,'_pvp_card':'plant:test','_pvp_anchor_until':100. if i%5==0 else 0.,'植物血':(1.,30.,300.)[i//12%3]}),
            dict(op='content_point',target={'plant':0}),dict(op='content_hit',source=0,target={'plant':0},amount=(-2.,0.,5.,100.)[i//36]),
            dict(op='content_hit',source=0,target={'plant':0},amount=500.)]
        cases.append(('content-plant-damage-'+str(i),c))
    for i in range(64):
        c=base();c['units']=[projectiles.unit(owner='zombie')];side=('plant','zombie','plant2','zombie2')[i%4]
        c['sources']=[{'_pvp_owner':'plant','名':'西瓜'}];c['damage']=dict(watch_armor=True)
        c['operations']=[dict(op='content_point',target=side),dict(op='content_hit',source=0,target=side,amount=30.,kind=('content','ash','swallow','normal')[i//4%4]),
            dict(op='content_hit',source=0,target=0,amount=3.,surface=i%2==0,throw_raw=i%3==0,catch=True),
            dict(op='remove_unit',unit=0),dict(op='content_hit',source=0,target=0,amount=3.,surface=True)]
        c['operations']=[hero.context(c['operations'],owner='plant2',target='zombie2',source=0)] if i>=32 else c['operations']
        cases.append(('content-target-routing-'+str(i),c))
    for i in range(48):
        c=base();t={'plant':0} if i%3 else ('plant','zombie2')[i%2];x=(24.,1896.,120.)[i%3];y=165.6
        c['operations']=[dict(op='plant_original',cell=[3,2],name='向日葵')]
        if i%5==0:c['operations'].append(dict(op='plant_write',plant=0,values={'_pvp_content':'抓人草触手','_pvp_head_point':[1896.,144.]}))
        c['operations'] += [dict(op='content_point',target=t),dict(op='content_contact',target=t,start=[x,y+(i//3-8)*6.],delta=[(-48.,0.,48.)[i%3],0.])]
        cases.append(('content-contact-'+str(i),c))
    for i in range(12):
        c=base();c['sources']=[{'_pvp_owner':'zombie'}]
        c['operations']=[dict(op='plant_original',cell=[8,0],name='魅惑菇',catch=True),dict(op='plant_write',plant=0,values={'_pvp_owner':'plant'}),
            dict(op='content_hit',source=0,target={'plant':0},amount=3.,catch=True),dict(op='content_hit',source=0,target='plant',amount=3.)]
        if i%3==0:c['sources'][0]['魅惑']=None
        if i%3==1:c['operations'][1]['values']['植物血']=None
        c['operations']=[hero.context(c['operations'],owner='zombie',target='plant',source=0)] if i>=6 else c['operations']
        cases.append(('content-partial-plant-'+str(i),c))
    for i in range(24):
        c=base();block=('基岩','石',None)[i%3];y=(-1,3,8)[i//3%3];x=(-5,2,9)[i//9%3]
        c['plant_world']['grid'][3][2]=None if block is None else {'方块':block,'植物':False}
        c['operations']=[dict(op='hold_tile',cell=[3,2]),dict(op='destroy_block',cell=[y,x],pvp=True,catch=True)]
        cases.append(('pvp-bedrock-'+str(i),c))
    return cases,names


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),patch.PATCH,TABLES,FUNCTIONS,ROOT/'tools/typed72/plants_probe.cpp',ROOT/'tools/typed72/targets_probe.cpp',ROOT/'tools/typed72/hero_probe.cpp',
        ROOT/'tools/typed72/verify_targets.py',ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_protection.py',ROOT/'tools/typed72/verify_patch.py',ROOT/'tools/typed72/verify_stages.py',
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,protection.PROTECTION,protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [projectiles.CONTENT,projectiles.SIMULATION,projectiles.FLYING,projectiles.SCALE,projectiles.CATALOG61,ROOT/'tools/typed72/verify_projectiles.py']
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=protection.reference();tr=load_terrain_reference();cases,names=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:PlantExtension(ctx,c,pref,tr));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-plant-terrain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,original_plant_kinds=names,
        excluded=['PvP/patch plant admission and constructors','complete gravebuster death wrapper binding','chili/doom effect bodies','whole battle','network/replay'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','original_plant_kinds')}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
