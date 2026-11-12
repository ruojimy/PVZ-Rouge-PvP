"""Actual installed squash target, ballistic, source, spawn and hit chains."""
import argparse
import ast
import copy
import functools
import json
import math
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_services as services
death=services.death;hero=services.hero;plants=services.plants;projectiles=services.projectiles;chili=services.chili;doom=services.doom;patch=services.patch
ROOT=hero.ROOT;P=death.P;sha=death.sha;difference=death.difference;PVP70=services.PVP70
COUNTERS=('squash_patch_count','squash_zombie_attack_count','squash_zombie_damage_count')
PVP66=ROOT/'tools/pvp72_sources/pvp66_secrets.py'
def reference():
    env=services.reference();tree=ast.parse(PVP66.read_text(encoding='utf8'),str(PVP66));nodes=[m for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='PlantSecrets66' for m in c.body if isinstance(m,ast.FunctionDef) and m.name=='squash']
    assert len(nodes)==1;env['squash_secret_code']=compile(ast.Module(body=nodes,type_ignores=[]),str(PVP66),'exec');return env


class SquashExtension(services.ServiceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        for u,v in zip(self.units,case['squash']['units']):u.update(copy.deepcopy(v))
        for n in COUNTERS:self.ns[P+n]=0
        self.ns[P+'last_zombie_pos']={};ctx.constructor_patch._clock=lambda:self.native_time;self.squash_held=[]
        self.raw_squash={n:self.ns[P+n] for n in ('update_squash_zombie','spawn_squash_zombie_entity','apply_squash_zombie_hit')}
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env)
        for n in ('update_squash_zombie','spawn_squash_zombie_entity'):env['bind'](n,1,'zombie','zombies')
        env['bind']('apply_squash_zombie_hit',1,'entity','entities')
        old_ash=self.g['灰烬僵尸'];old_damage=self.g['伤害僵尸'];old_player=self.g['掉血']
        def ash(index):
            self.calls.append(['squash_ash',index]);self.before('squash_ash');old_ash(index);self.after('squash_ash')
        def damage(index,direction,amount):
            self.calls.append(['squash_damage',index,direction,amount]);self.before('squash_damage');old_damage(index,direction,amount);self.after('squash_damage')
        def player(amount):
            self.calls.append(['squash_player',amount]);self.before('squash_player');old_player(amount);self.after('squash_player')
        self.g.update(灰烬僵尸=ash,伤害僵尸=damage,掉血=player)
        secret_env=dict(math=math,SQUASH_SPLASH_TILES=hero.constant(PVP66,'SQUASH_SPLASH_TILES'),SQUASH_DAMAGE=hero.constant(PVP66,'SQUASH_DAMAGE'))
        projectiles.functions(PVP66,['wrap_delta'],secret_env);exec(ref['squash_secret_code'],secret_env);self.squash_secret=secret_env['squash']

    def identity(self,value):
        if value is None:return None
        v=self.encode_key(value);return {'temporary':True} if isinstance(v,int) else v

    def decode_record(self,r):
        r=copy.deepcopy(r)
        if isinstance(r,dict) and r.get('target_id') is not None:r['target_id']=self.decode_key(r['target_id'])
        return r

    def entity_fields(self,e,v):
        v=copy.deepcopy(v)
        for k in ('智能窝瓜',P+'squash_zombie_target'):
            if k in v:v[k]=self.decode_record(v[k])
        if v.get(P+'source_zombie_id') is not None:v[P+'source_zombie_id']=self.decode_key(v[P+'source_zombie_id'])
        self.entity_values(e,v)

    def describe(self,t):
        if t is None:return None
        kind,index,obj,point,direction,angle=t
        label=self.identity(id(obj)) if kind=='plant' else self.label(obj) if kind=='zombie' else None
        return [kind,index,label,list(point),direction,angle]

    def aim_json(self,a):
        t,v=a
        return [None,None] if t is None else [[t[0],self.identity(id(t[1])),list(t[2]),t[3]],list(v)]

    def operation(self,op):
        action=op['op'];ns=self.ns;g=self.g
        if action=='squash_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='squash_entity_write':self.entity_fields(self.births[op['entity']],op['values'])
        elif action=='squash_roster':g['实体']=[self.births[i] for i in op['entities']]
        elif action=='squash_splash':
            b=types.SimpleNamespace(targets=self.c,tile=g['比'],width=op.get('width',960.),_emit=self.b._emit)
            obj=types.SimpleNamespace(b=b,g=g,secrets={'secret:压顶'} if op.get('enabled',True) else set())
            if 'index' in op:g['z']=op['index']
            else:g.pop('z',None)
            try:return self.squash_secret(obj)
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        elif action=='squash_solve':return ns[P+'solve_intercept'](op['origin'],op['point'],op['velocity'],op['speed'],op['gravity'],op.get('max_time',95.))
        elif action=='squash_candidate':return ns[P+'squash_zombie_candidate'](op['origin'],op['point'],op['direction'],op.get('scale',48.),op.get('size',2.))
        elif action=='squash_velocity':return ns[P+'zombie_velocity'](self.target(op['target']),op.get('direction',1.))
        elif action=='squash_resolve':
            kind,resolved,p=ns[P+'resolve_squash_zombie_target'](g,self.decode_record(op['record']))
            obj=None if resolved is None else [resolved[0],self.identity(id(resolved[1])) if kind=='plant' else self.label(resolved[1])]
            return [kind,obj,p]
        elif action in ('squash_pick','squash_update','squash_spawn'):
            u=self.units[op['unit']]
            try:
                # Test selection mirrors only an explicit operation. Updating
                # calls the installed function, which performs its own pick.
                if action=='squash_update':return (ns[P+'update_squash_zombie'] if op.get('sourced',True) else self.raw_squash['update_squash_zombie'])(g,u,self.config(op,'倭瓜僵尸'))
                t,origin=ns[P+'pick_squash_zombie_target'](g,u)
                if action=='squash_pick':self.squash_held.append(t);return [self.describe(t),list(origin)]
                t=None if op.get('none') else self.squash_held[op['held']] if 'held' in op else t
                return (ns[P+'spawn_squash_zombie_entity'] if op.get('sourced',True) else self.raw_squash['spawn_squash_zombie_entity'])(g,u,t,origin,self.config(op,'倭瓜僵尸'))
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        elif action=='squash_finish':return ns[P+'finish_squash_entities'](g)
        elif action=='squash_pending':return ns[P+'has_pending_enemy_squash_zombie_entity'](g['实体'])
        elif action=='squash_tick':return ns[P+'update_squash_zombie_entities'](g)
        elif action=='squash_kill':return ns[P+'squash_zombie_kill_plant'](g,self.all_plants[op['plant']])
        elif action=='squash_damage_unit':return ns[P+'squash_zombie_damage_charmed_zombie'](g,op['index'],self.target(op['target']),op.get('direction',1.))
        elif action.startswith('squash_'):
            e=self.births[op['entity']]
            try:
                if action=='squash_ballistic_pick':return self.aim_json(ns[P+('pick_squash_target' if op.get('squash',False) else 'pick_target')](g,e))
                if action=='squash_current':return self.aim_json(ns[P+'current_target_from_index'](g,e,op['index']))
                if action=='squash_locked':return self.aim_json(ns[P+'squash_target_from_lock'](g,e,self.decode_record(op['lock'])))
                if action in ('squash_apply','squash_compute'):
                    obj=self.units[op['target']['unit']] if 'unit' in op['target'] else self.all_plants[op['target']['plant']] if 'plant' in op['target'] else self.target(op['target']['hero'])
                    t=(op.get('index',0),obj,op['point'],op.get('direction',1.))
                    if action=='squash_compute':return ns[P+'compute_solution'](g,e,t,op['velocity'],op['speed'])
                    return ns[P+'apply_squash_solution'](g,e,t,op['velocity'],op['speed'],op.get('late',False))
                if action=='squash_patch':return ns[P+'patch_squash_entity'](g,e)
                if action=='squash_enemy':return ns[P+'is_enemy_squash_zombie_entity'](e)
                if action=='squash_damage_player':return ns[P+'squash_zombie_damage_player'](g,e,op['impact_x'],op.get('direction',1.))
                if action=='squash_hit':return (ns[P+'apply_squash_zombie_hit'] if op.get('sourced',True) else self.raw_squash['apply_squash_zombie_hit'])(g,e,self.decode_record(op['record']) if 'record' in op else e.get(P+'squash_zombie_target'),op['impact_x'])
                raise ValueError(action)
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row);row['squash_counts']=[self.ns[P+n] for n in COUNTERS]
        row['squash_units']=[{k:u[k] for k in ('移速',P+'squash_zombie_used') if k in u} for u in self.units]
        for name in ('entities','effect_births'):
            for e in row[name]:
                if P+'source_zombie_id' in e:e[P+'source_zombie_id']=self.identity(e[P+'source_zombie_id'])
                for k in ('智能窝瓜',P+'squash_zombie_target'):
                    if isinstance(e.get(k),dict) and 'target_id' in e[k]:e[k]['target_id']=self.identity(e[k]['target_id'])
        observations=[[self.identity(k)]+list(v) for k,v in self.ns[P+'last_zombie_pos'].items()]
        row['velocity_observations']=sorted(observations,key=lambda v:json.dumps(v[0],ensure_ascii=False,sort_keys=True,separators=(',',':')))


def base():
    c=services.base();c['services']['units'][0]['植物僵尸名']='倭瓜僵尸';c['squash']=dict(units=[{},{},{},{}]);return c


def write(i,**v):return dict(op='squash_unit',unit=i,values=v)
def entity(position=(240.,400.,2.,-4.)):return dict(op='service_entity',name='窝瓜x',position=list(position))
def rec(kind='zombie',index=1,identity=None,point=None,direction=1.):return dict(kind=kind,target_index=index,target_id=identity,point=point or [280.,400.],direction=direction)


def make_cases():
    cases=[];rng=random.Random(72917)
    for i in range(128):
        c=base();ops=[]
        for unused in range(4):
            ops.append(dict(op='squash_solve',origin=[rng.uniform(-600,600),rng.uniform(-600,600)],point=[rng.uniform(-600,600),rng.uniform(-600,600)],velocity=[rng.uniform(-10,10),rng.uniform(-10,10)],speed=rng.uniform(.01,35.),gravity=rng.choice([0.,.0096,-.1,.1,2.]),max_time=rng.choice([.05,.1,.6,95.,130.])))
        c['operations']=ops;cases.append(('squash-intercept-random-'+str(i),c))
    for i in range(32):
        c=base();t=(.05,.1,.6,1.1,94.6,95.1,129.6,130.1)[i%8];speed=(0.,1.,10.,100.)[i//8]
        c['operations']=[dict(op='squash_solve',origin=[0.,0.],point=[speed*t+d,0.],velocity=[0.,0.],speed=speed,gravity=0.,max_time=95.) for d in (-1e-10,0.,1e-10)]
        cases.append(('squash-intercept-boundary-'+str(i),c))
    for i in range(72):
        c=base();d=(-1.,0.,1.)[i%3];c['operations']=[dict(op='squash_candidate',origin=[240.,432.],point=[240.+offset,432.+y],direction=d,size=size)
            for offset in (-4.800001,-4.8,0.,112.8,112.800001) for y in (0.,43.2,43.200001) for size in ((.1,.8,2.,4.)[i//3%4],)]
        cases.append(('squash-candidate-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][0]['方向']=(-1.,1.)[i%2]
        if i%3:c['services']['units'][0]['魅惑']=None
        c['services']['units'][1]['魅惑']=0.;c['services']['units'][2]['死']=False
        if i%4==0:c['services']['units'][3]['灰烬']=None
        c['damage']['hero_targets']=['plant','zombie','plant2','zombie2'];c['globals']['模式']='我是僵尸' if i%4==0 else '正常模式'
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_original',cell=[8,6],name='坚果'),dict(op='squash_pick',unit=0),dict(op='roster_replace',targets=[3,2,1,0]),dict(op='squash_pick',unit=0)]
        cases.append(('squash-target-'+str(i),c))
    for i in range(48):
        c=base();c['operations']=[write(1,移速=(None,0.,1.,-2.)[i%4],位置=[280.,432.,(-.001,0.,.001,.002)[i//4%4],0.]),dict(op='fire_globals',time=1.),dict(op='squash_velocity',target=1),
            write(1,位置=[281.,430.,0.,0.]),dict(op='fire_globals',time=(1.,1.001,2.)[i//16]),dict(op='squash_velocity',target=1),dict(op='squash_velocity',target=1)]
        cases.append(('squash-velocity-'+str(i),c))
    for i in range(64):
        c=base();c['operations']=[entity(),dict(op='squash_entity_write',entity=0,values={'智能窝瓜':(None,{},dict(created=0.5,late_armed=False),dict(late_armed=True))[i%4],'坐下':None,'弹跳x':None}),
            dict(op='squash_apply',entity=0,index=1,target={'unit':1},point=[280.,400.],direction=(-1.,1.)[i%2],velocity=[(0.,1.,50.,-50.)[i//4%4],0.],speed=(.01,1.,5.,20.)[i//16],late=i%2==0,catch=True)]
        cases.append(('squash-solution-'+str(i),c))
    for i in range(64):
        c=base();c['operations']=[entity(),dict(op='fire_globals',time=1.),dict(op='squash_patch',entity=0),dict(op='squash_ballistic_pick',entity=0,squash=i%2==0),dict(op='roster_replace',targets=[3,2,1,0]),dict(op='fire_globals',time=(1.,1.009,1.01,1.02)[i%4]),dict(op='squash_finish')]
        if i>=32:c['operations'].insert(2,dict(op='squash_entity_write',entity=0,values={'智能窝瓜':dict(target_index=1,target_id={'unit':1},initial_speed=5.,created=1.,late_armed=i%3==0)}))
        cases.append(('squash-late-lock-'+str(i),c))
    for i in range(64):
        c=base();c['seed']=74900+i;c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        if i%2:c['services']['units'][0]['魅惑']=None
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='squash_update',unit=0,sourced=i%3!=0,config={'jump_speed':(None,0.,100.,330.)[i//4%4],'fire_anim':(None,1.,24.,90.)[i//16]}),dict(op='squash_update',unit=0),dict(op='squash_pending'),dict(op='squash_tick')]
        cases.append(('squash-update-'+str(i),c))
    for i in range(48):
        c=base();c['services']['units'][1]['魅惑']=0.;c['operations']=[dict(op='squash_pick',unit=0),dict(op='lifecycle_hook',name='add',fail_before=i%4==0,fail_after=i%4==1,
            body=[write(0,魅惑=None),dict(op='roster_replace',targets=[3,0]),dict(op='source_observe')]),dict(op='squash_spawn',unit=0,held=0,none=i%6==0,sourced=i%3!=0,catch=True)]
        cases.append(('squash-spawn-callback-'+str(i),c))
    for i in range(48):
        c=base();c['services']['units'][1]['魅惑']=0.;c['globals']['模式']='我是僵尸' if i%2 else '正常模式';r=rec(('zombie','plant','player','invalid')[i%4],(1,99,-1)[i//4%3],({'unit':1},None)[i//12%2])
        if r['kind']=='plant':r['target_id']={'plant':0}
        c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='squash_resolve',record=r),dict(op='roster_replace',targets=[3,2,1,0]),dict(op='squash_resolve',record=r)]
        cases.append(('squash-record-resolve-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][1]['魅惑']=None;c['operations']=[entity(),dict(op='plant_original',cell=[8,5],name='向日葵'),
            dict(op='lifecycle_hook',name='squash_ash',fail_before=i%4==0,fail_after=i%4==1,body=[dict(op='roster_replace',targets=[3,2,0]),dict(op='source_observe')]),
            dict(op='lifecycle_hook',name='squash_damage',fail_before=i%3==0,fail_after=i%3==1),dict(op='lifecycle_hook',name='clear',fail_before=i%5==0),
            dict(op='squash_hit',entity=0,record=rec(('zombie','plant')[i%2],1,{'unit':1} if i%2==0 else {'plant':0}),impact_x=240.,sourced=i%3!=0)]
        cases.append(('squash-hit-callback-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['模式']='我是僵尸' if i%3==0 else '正常模式';c['operations']=[entity(),dict(op='lifecycle_hook',name='squash_player',fail_before=i%4==0,fail_after=i%4==1),
            dict(op='squash_damage_player',entity=0,impact_x=240.,direction=(-1.,0.,1.)[i//16]),dict(op='squash_hit',entity=0,record=rec('player',-1),impact_x=240.,sourced=i%2==0)]
        cases.append(('squash-player-fallback-'+str(i),c))
    for i in range(48):
        c=base();c['services']['units'][1]['魅惑']=None;r=rec('zombie',1,{'unit':1})
        c['operations']=[entity((240.+(0.,40.,100.,-100.)[i%4],400.,0.,0.)),dict(op='squash_entity_write',entity=0,values={P+'squash_zombie_entity':True,P+'squash_zombie_target':r,P+'squash_zombie_age':(0.,17.,20.,100.)[i//4%4],P+'squash_zombie_friendly':i%3==0,'智能窝瓜':(None,{},dict(hit_t=4.))[i//16]}),dict(op='squash_tick'),dict(op='squash_pending'),dict(op='squash_tick')]
        cases.append(('squash-entity-hit-timing-'+str(i),c))
    for i,owner in enumerate((None,'invalid','plant','zombie','plant2','zombie2')):
        for j in range(4):
            c=base();c['units'][0]['source']['_pvp_owner']=owner
            c['squash']['units'][0][P+'squash_zombie_used']=True
            c['operations']=[dict(op='squash_update',unit=0,sourced=j%2==0,catch=True),dict(op='source_observe')]
            cases.append(('squash-update-context-'+str(i)+'-'+str(j),c))
    for i in range(24):
        c=base();c['services']['units'][1]['魅惑']=None
        body=[dict(op='squash_roster',entities=[0])]
        if i%3==1:body+=[dict(op='service_entity',name='卷心菜',position=[500.,500.,0.,0.])]
        if i%3==2:body+=[write(0,魅惑=None)]
        c['operations']=[entity(),dict(op='squash_pick',unit=0),dict(op='lifecycle_hook',name='add',body=body,fail_after=i>=12),dict(op='squash_spawn',unit=0,held=0,sourced=i%2==0,catch=True)]
        cases.append(('squash-birth-list-identity-'+str(i),c))
    for i in range(16):
        c=base();c['services']['units'][0]['魅惑']=None;c['services']['units'][1]['死']=False
        c['units'][2]['body']['血量']=0.;c['units'][3]['body']['血量']=0.
        c['operations']=[dict(op='squash_pick',unit=0),entity(),dict(op='squash_ballistic_pick',entity=0,squash=True)]
        cases.append(('squash-dead-positive-target-'+str(i),c))
    for i in range(16):
        c=base();c['globals']['模式']='正常模式';c['globals']['玩家位置']=[240.,432.,5.,7.]
        c['operations']=[entity(),dict(op='squash_entity_write',entity=0,values={P+'squash_zombie_entity':True,P+'squash_zombie_target':rec('player',-1),P+'squash_zombie_age':100.}),dict(op='squash_tick'),dict(op='squash_pending'),dict(op='squash_tick')]
        cases.append(('squash-hit-once-'+str(i),c))
    for i in range(48):
        c=base();c['units'][1]['body']['血量']=0. if i%3==0 else 10.;c['services']['units'][2]['灰烬']=None
        c['operations']=[entity(),dict(op='squash_current',entity=0,index=(-1,0,1,2,99)[i%5]),dict(op='squash_locked',entity=0,lock=dict(target_index=(1,2,99)[i%3],target_id=(None,{'unit':1},{'unit':3})[i//3%3])),
            dict(op='squash_compute',entity=0,index=1,target={'unit':1},point=[(280.,500.,900.)[i//16],400.],velocity=[(0.,1.,50.,-50.)[i%4],0.],speed=(1.,3.,10.)[i//4%3]),dict(op='squash_ballistic_pick',entity=0)]
        cases.append(('squash-ballistic-fallback-'+str(i),c))
    for i in range(24):
        c=base();c['services']['units'][0]['魅惑']=None
        c['operations']=[entity(),dict(op='squash_pick',unit=0),write(1,位置=[350.,400.,1.,2.]),
            dict(op='lifecycle_hook',name='add',body=[dict(op='squash_entity_write',entity=1,values={'智能窝瓜':(None,{},dict(created=0.))[i%3],'坐下':None,'弹跳x':0.}),dict(op='source_observe')]),
            dict(op='squash_spawn',unit=0,held=0,sourced=i%2==0,catch=True)]
        cases.append(('squash-spawn-lock-presence-'+str(i),c))
    for i in range(64):
        c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2']
        c['units'][0]['body']['位置']=[5.,432.,0.,0.];c['units'][1]['body']['位置']=[955.,432.,0.,0.];c['units'][2]['body']['位置']=[(110.,120.2)[i%2],432.,0.,0.]
        if i%3==0:c['services']['units'][1]['魅惑']=None
        if i%4==0:c['services']['units'][2].update(死=False,魅惑=None)
        if i%8==0:c['services']['units'][3]['灰烬']=None
        ops=[dict(op='lifecycle_hook',name='squash_damage',body=[dict(op='roster_replace',targets=[3,2,1,0])],fail_after=i%4==0),dict(op='squash_splash',index=(0,1,99,-1)[i//16],enabled=i%5!=0,catch=True)]
        c['operations']=[dict(op='chili_scope',unit_source=0,target='zombie',owner='plant',phase='entities',body=ops)] if i%2 else ops
        cases.append(('squash-pvp66-splash-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[PVP66,PVP70,exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('squash_probe.cpp','service_probe.cpp','verify_services.py','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(str(p),str(dest))
    ref=hero.load_reference();pref=plants.protection.reference();chili_ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:SquashExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-squash-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks','whole native driver','complete custom content scheduler','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
