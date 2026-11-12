"""Literal projectile, flying collision and content damage functions, no cppcore.

The selected live source methods execute unmodified against a fixture world.
This proves the indicated component chain, not a completed match or backend.
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
import verify_entities as entities
import verify_patch as patch
from verify_stages import sha,difference,Sprite
import evidence_store
import evidence_archive
ROOT=hero.ROOT
CONTENT=ROOT/'tools/pvp72_sources/native_content.py'
SIMULATION=ROOT/'tools/pvp72_sources/simulation.py'
FLYING=hero.REF/'modkit/pvp/pvp56_plants.py'
SCALE=hero.REF/'modkit/pvp/native_scale.py'
CATALOG61=hero.REF/'modkit/pvp/pvp61_catalog.py'


def functions(path,names,env):
    nodes=[n for n in ast.parse(path.read_text(encoding='utf8'),str(path)).body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes}!=set(names):raise ValueError('missing reference functions '+str(path))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)


def load_projectiles():
    env=dict(__builtins__=builtins.__dict__,math=math)
    functions(SIMULATION,['wrap_delta'],env);functions(SCALE,['factor','unit_root'],env)
    functions(hero.BALANCE,['fire_color'],env);env['ZOMBIE_FIRE']=hero.constant(hero.BALANCE,'ZOMBIE_FIRE')
    tree=ast.parse(hero.PROJECTILES.read_text(encoding='utf8'),str(hero.PROJECTILES))
    body=[n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef,ast.ClassDef))]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(hero.PROJECTILES),'exec'),env)
    hero.selected_class(FLYING,['target_contact'],'FlyingPlants',env)
    hero.selected_class(CONTENT,['point','damage_target'],'NativeContent',env)
    env['FLYERS']=('海盗鹦鹉',hero.constant(CATALOG61,'CROW'))
    constants,_=patch.patch_reference();env.update(constants);env[patch.PREFIX+'math']=math
    functions(patch.PATCH,[patch.PREFIX+n for n in ('float','sign','plant_zombie_head_center','plant_zombie_head_radius','segment_hits_ellipse')],env)
    return env


class ProjectileExtension(entities.EntityExtension):
    def __init__(self,ctx,case,pref,reference):
        super().__init__(ctx,case,pref);self.cfg=case['projectiles'];self.projectile_events=[];self.hit_hook=[]
        # Functions keep this one environment; data changes here are limited to
        # immutable catalog/atlas fixture inputs between independent cases.
        env=reference;env['FACTOR']=copy.deepcopy(self.cfg.get('scale',{}));env[patch.PREFIX+'PLANT_ZOMBIE_CONFIG']=copy.deepcopy(self.cfg.get('heads',{}))
        for u,fields in zip(self.units,self.cfg.get('units',[])):u.update(copy.deepcopy(fields))
        self.b.g=self.g;self.b.width=self.cfg.get('width',1920.);self.b.tile=48.;self.b.patch=types.SimpleNamespace(ns=env)
        self.b.rules['melon_splash_damage']=self.cfg['melon_splash_damage']
        for name,height in self.cfg.get('flyers',{}).items():self.g['图集'][name+'-帧0']=Sprite(dict(width=1,height=height,pixels=[]))
        p=env['NativeProjectiles'].__new__(env['NativeProjectiles']);p.b=self.b;self.b.projectile_rules=p;self.rules=p
        c=env['NativeContent']();c.b=self.b;c.g=self.g;self.b.content=c
        flying=env['FlyingPlants']();flying.b=self.b;flying.c=c;c.flying=flying;self.flying=flying
        old_emit=self.b._emit
        def emit(event_type,**data):
            if event_type in ('zombie_basket_hit','melon_splash'):self.projectile_events.append(dict(type=event_type,**data))
            old_emit(event_type,**data)
        self.b._emit=emit;self.env=env
        old_damage=self.c.originals['伤害僵尸']
        def hooked_damage(*args):
            result=old_damage(*args);body,self.hit_hook=self.hit_hook,[]
            if body:self.operations(body,False)
            return result
        self.c.originals['伤害僵尸']=hooked_damage

    def operation(self,op):
        action=op['op'];result=None
        if action=='fixture_entity':
            e=copy.deepcopy(op['values']);e['方向']=op.get('facing',1.)
            if '_pvp_instant_attack' in e:e['_pvp_instant_attack']=hero.decode_attack(e['_pvp_instant_attack'])
            self.g['实体'].append(e);self.retained.append(e);self.handles_alive.append(True)
        elif action=='projectile_write':
            e=self.retained[op['entity']]
            for k in op.get('erase',[]):e.pop(k,None)
            e.update(copy.deepcopy(op.get('values',{})))
        elif action=='expired':result=self.rules.expired(self.retained[op['entity']])
        elif action=='cull':
            self.rules.cull_flight();self.retire_handles()
        elif action=='entity_roster_replace':
            self.g['实体']=[self.retained[i] for i in op['entities']];self.retire_handles()
        elif action=='entity_roster_append':self.g['实体'].append(self.retained[op['entity']])
        elif action=='hit_hook':self.hit_hook=op['body']
        elif action=='impact':
            self.throw_raw=op.get('throw_raw',False)
            try:self.rules.impact(self.retained[op['entity']])
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
            finally:self.throw_raw=False
        elif action=='head_geometry':result=self.rules.head_geometry(self.units[op['unit']])
        elif action=='head_area':result=self.rules.head_overlaps_area(self.units[op['unit']],*op['center'],*op['radii'])
        elif action=='contact':result=self.flying.target_contact({},self.units[op['unit']],*op['start'],*op['delta'])
        elif action=='segment':result=self.env[patch.PREFIX+'segment_hits_ellipse'](*op['a'],*op['b'],*op['center'],*op['radii'])
        else:return super().operation(op)
        # The shared JSON evidence schema intentionally encodes Python tuples
        # as arrays, including geometry return values.
        return json.loads(json.dumps(result,ensure_ascii=False))

    def snapshot(self,row):
        super().snapshot(row);row['projectile_events']=self.projectile_events

    def retire_handles(self):
        for i,e in enumerate(self.retained):
            if not any(e is live for live in self.g['实体']):self.handles_alive[i]=False


def base():
    c=hero.base();c.update(tagging=True,units=[],damage=dict(watch_armor=True),projectiles=dict(width=1920.,units=[],melon_splash_damage=50.));return c


def unit(x=100.,y=200.,owner='plant',kind='普通僵尸'):
    return dict(body={'僵尸':kind,'防具':'','手持':'','血量':200.,'防具血量':0.,'手持血量':0.,'方向':1.,'位置':[x,y,0.,0.],'受伤':0.,'手持受伤':0.},source={'_pvp_owner':owner})


def make_cases():
    cases=[];rng=random.Random(72404)
    names=('豌豆','冰豆','火豆','蓝火豆','僵尸豌豆','泡泡','海泡泡','尖刺','星星','篮球','西瓜','其他')
    for name in names:
        for parent in ({},{'植物':'香蒲'},{'植物':'小喷菇'},{'植物':'胆小菇'},{'_pvp_flight_limit_tiles':64.},{'_pvp_flight_limit_tiles':1.}):
            c=base();c['sources']=[copy.deepcopy(parent)];ops=[dict(op='spawn_entity',name=name,position=[1890.,160.,2.,0.])]
            for n in range(15):
                ops.extend([dict(op='entity_position',entity=0,position=[(1890.+n*48.)%1920.,160.+(n%3)*2.,2.,0.]),dict(op='expired',entity=0)])
                if n in (3,6,9):
                    values=({'名':'火豆','火了':None},{'名':'冰豆'},{'__pvz_sb_zombie_pea_fire':'blue'})[(n//3)-1]
                    ops.append(dict(op='projectile_write',entity=0,values=values,erase=['火了'] if n==6 else []))
            c['operations']=[hero.context(ops,phase='plants',source=0)];cases.append(('flight-birth-'+str(len(cases)),c))
    # Exact range boundary, seam half-width ties, reversals, and explicitly
    # absent/None form fields are all distinct source paths.
    for i in range(32):
        c=base();e={'名':names[i%len(names)],'位置':[0.,160.,0.,0.],'_pvp_flight_last':[0.,160.],'_pvp_flight_distance':float(i%4)*10.,'_pvp_flight_limit_tiles':float(i%3+1)}
        if i%3==0:e['_pvp_flight_form']=None
        if i%5==0:e['_pvp_flight_last']=None
        if i%7==0:e['_pvp_cattail']=True
        c['operations']=[dict(op='fixture_entity',values=e)]
        for x in (48.,96.,144.,143.999,0.,960.,-960.,1920.,1921.):
            c['operations'] += [dict(op='entity_position',entity=0,position=[x,160.,0.,0.]),dict(op='expired',entity=0)]
        cases.append(('flight-range-'+str(i),c))
    for i in range(192):
        c=base();owner=('plant','zombie','plant2','zombie2')[i%4];x=(1910.,10.,100.,900.)[(i//4)%4];y=(160.,120.,30.)[(i//16)%3]
        e={'名':'篮球','位置':[x,y,0.,0.],'_pvp_owner':owner,'_pvp_original_owner':'zombie' if i%7 else 'plant','_pvp_source_entity':'launcher',
            '_pvp_basket_last':[(x-40.)%1920.,y+8.]}
        c['units']=[unit((x+dx)%1920.,y+48.+dy,owner if n%4==0 else ('zombie' if owner=='plant' else 'plant')) for n,(dx,dy) in enumerate(((0.,0.),(-2.,0.),(2.,0.),(-2.,0.),(5.,-55.),(0.,0.),(0.,0.)))]
        c['projectiles']['units']=[{} for u in c['units']]
        c['units'][1]['body'].update(防具='路障',防具血量=5.,手持='钢门' if i%2 else '',手持血量=5. if i%2 else 0.)
        c['units'][2]['source']['_pvp_id']='a-tie';c['units'][3]['source']['_pvp_id']='z-tie'
        c['units'][4]['source']['_pvp_content']=('海盗鹦鹉','乌鸦','抓人草触手')[i%3]
        c['projectiles']['units'][4]['_pvp_head_point']=[x,y]
        c['projectiles']['scale']={'海盗鹦鹉':.3,'乌鸦':.2,'抓人草触手':.4}
        if i%2:c['projectiles']['flyers']={'海盗鹦鹉':66.,'乌鸦':17.}
        c['units'][5]['state']={'_pvp_grave':True};c['projectiles']['units'][6]['_pvp_orphan_barrel']=True
        if i%3==0:c['units'][1]['body']['血量']=0.
        if i%5==0:c['units'][2]['source']['魅惑']=None
        if i%11==0:c['units'][3]['state']={'_pvp_hero':True}
        c['damage']['hero_targets']=['plant','zombie']
        c['operations']=[dict(op='fixture_entity',values=e,facing=-1.),dict(op='expired',entity=0),dict(op='entity_position',entity=0,position=[(x+30.)%1920.,y+20.,0.,0.]),dict(op='expired',entity=0)]
        cases.append(('basket-candidates-'+str(i),c))
    for i in range(96):
        c=base();x=(1910.,10.,100.)[i%3];y=200.;c['units']=[unit(x,y)];u=c['units'][0];u['body']['方向']=(-1.,0.,1.)[i%3]
        c['projectiles']['units']=[{'植物僵尸':bool(i%7),'植物僵尸名':'测试头部','植物僵尸鸭子':bool(i%2),'植物僵尸发射动画':(-2.,0.,1.,6.,12.,24.,48.,None)[i%8]}]
        if i%3:c['projectiles']['heads']={'测试头部':dict(head_x=.22,head_y=2.6,duck_head_x=-.15,duck_head_y=.85,head_scale=.3 if i%2 else 1.4,fire_anim=0. if i%5 else 270.,fumeshroom=bool(i%2))}
        ops=[dict(op='head_geometry',unit=0)]
        for dy in (-140.,-120.,-80.,-48.,0.):
            ops.extend([dict(op='contact',unit=0,start=[(x-50.)%1920.,y+dy],delta=[100.,0.]),
                dict(op='head_area',unit=0,center=[(x+30.)%1920.,y+dy],radii=[15.,5.])])
        c['operations']=ops;cases.append(('head-and-body-'+str(i),c))
    for i in range(12):
        c=base();c['operations']=[]
        for n in range(40):
            a=[rng.uniform(-10.,10.) for _ in range(2)];b=[a[0]+rng.choice([0.,1e-8,1e-4,2.,20.]),a[1]]
            c['operations'].append(dict(op='segment',a=a,b=b,center=[rng.uniform(-4.,4.),rng.uniform(-4.,4.)],radii=[rng.choice([-.1,0.,.2,1.,5.]),rng.choice([0.,.2,2.,8.])]))
        cases.append(('ellipse-boundary-'+str(i),c))
    for i in range(160):
        c=base();owner=('plant','zombie','plant2','zombie2')[i%4];enemy='zombie' if owner=='plant' else 'plant';x=120. if i%2 else 1910.;y=160.
        name=('西瓜','冰瓜','火豆','蓝火豆','豌豆')[(i//4)%5]
        e={'名':name,'位置':[x,y,0.,0.],'_pvp_owner':owner,'_pvp_source_entity':'splash-source'}
        if i%3:e['_pvp_melon_hits']=['direct']
        if i%7==0:e['_pvp_splash_done']=True
        if i%11==0:e['_pvp_content']='甜椒投手'
        if i%13==0:e['_pvp_content']='原始豌豆射手'
        if i%6==0:e['_pvp_fire_color']='blue'
        if i%8==0:e['__pvz_sb_zombie_pea_fire']='fire'
        if i%9==0:e['_pvp_melon_splash']=None
        c['units']=[unit((x+dx)%1920.,y+dy,enemy) for dx,dy in ((0.,48.),(0.,48.),(62.4,48.),(62.4000001,48.),(62.3999999,48.),(0.,129.6),(0.,129.5999999),(0.,-48.),(0.,-47.9999999),(0.,200.))]
        for n,u in enumerate(c['units']):u['source']['_pvp_id']='direct' if n==0 else 'target:'+str(n)
        c['units'][0]['source']['_pvp_owner']=owner if i%3==0 else enemy
        if i%5==0:c['units'][1]['body'].update(手持='钢门',手持血量=5.)
        if i%9==0:c['units'][4]['body']['血量']=0.
        c['projectiles']['units']=[{} for _ in c['units']];c['projectiles']['units'][9]={'植物僵尸':True,'植物僵尸名':'高头'}
        c['projectiles']['heads']={'高头':dict(head_y=4.1,head_scale=.9)}
        c['projectiles']['melon_splash_damage']=(0.,.5,50.,125.)[i%4]
        c['heroes'][enemy]['秘籍']=['蓝火'] if i%2 else []
        c['damage'].update(hero_targets=['plant','zombie','plant2','zombie2'],shield_first=bool(i%2))
        body=[dict(op='impact',entity=0,throw_raw=i%17==0,catch=True),dict(op='impact',entity=0),
            dict(op='projectile_write',entity=0,values={'_pvp_splash_done':False}),dict(op='impact',entity=0)]
        c['operations']=[dict(op='fixture_entity',values=e),dict(op='context',target=enemy,owner=owner,phase='entities',entity_source=0,body=body)]
        cases.append(('splash-source-'+str(i),c))
    for i in range(8):
        c=base();c['units']=[unit(120.,200.,'zombie') for _ in range(4)]
        e={'名':'西瓜','位置':[120.,160.,0.,0.],'_pvp_owner':'plant'}
        if i%2:e['_pvp_melon_hits']=None
        hook=([dict(op='remove_unit',unit=0)],[dict(op='roster_replace',targets=[3,2,1,0])],
              [dict(op='roster_replace',targets=[0])],[dict(op='roster_append',target=3)])[i//2]
        c['operations']=[dict(op='fixture_entity',values=e),dict(op='hit_hook',body=hook),
            dict(op='context',target='zombie',owner='plant',phase='entities',entity_source=0,body=[dict(op='impact',entity=0,catch=True)])]
        cases.append(('splash-mutation-'+str(i),c))
    for i in range(16):
        c=base();c['units']=[unit(120.,200.,'plant')]
        basket={'名':'篮球','位置':[120.,152.,0.,0.],'_pvp_owner':'zombie','_pvp_original_owner':'zombie','_pvp_basket_last':[100.,152.], '_pvp_flight_limit_tiles':1.}
        pea={'名':'豌豆','位置':[500.,500.,0.,0.],'_pvp_owner':'plant','_pvp_flight_last':[400.,500.],'_pvp_flight_distance':0.,'_pvp_flight_limit_tiles':1. if i%2 else 32.}
        hook=[]
        if i%4==0:hook=[dict(op='entity_roster_replace',entities=[1])]
        elif i%4==1:hook=[dict(op='entity_roster_append',entity=1)]
        elif i%4==2:hook=[dict(op='erase_entity',entity=0)]
        hook += [dict(op='spawn_entity',name='豌豆',position=[10.,900.,0.,0.]),dict(op='entity_position',entity=2,position=[500.,900.,0.,0.])]
        c['operations']=[dict(op='fixture_entity',values=basket),dict(op='fixture_entity',values=pea),dict(op='hit_hook',body=hook),dict(op='cull'),dict(op='cull')]
        cases.append(('cull-live-list-'+str(i),c))
    for i in range(4):
        c=base();c['units']=[unit(120.,240.,'zombie'),unit(120.,240.,'zombie')]
        c['units'][0]['body']['血量']=10.;c['units'][0]['state']={'_pvp_grave':True}
        c['players']['zombie']['secrets']=['zsecret:遗骸','zsecret:最后攻势'];c['heroes']['zombie']['玩家血量']=1.
        c['damage']['hero_targets']=['plant','zombie'];c['damage']['deathmatch']=bool(i%2)
        melon={'名':'西瓜','位置':[120.,192.,0.,0.],'_pvp_owner':'plant'}
        basket={'名':'篮球','位置':[120.,192.,0.,0.],'_pvp_owner':'plant','_pvp_original_owner':'zombie','_pvp_basket_last':[100.,192.]}
        c['operations']=[dict(op='fixture_entity',values=melon),dict(op='fixture_entity',values=basket),
            dict(op='context',target='zombie',owner='plant',phase='entities',entity_source=0,body=[dict(op='impact',entity=0)]),
            dict(op='expired',entity=1),dict(op='clock',tick=10000,time=40.),dict(op='last_stand_step')]
        cases.append(('cross-system-event-order-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),CONTENT,SIMULATION,FLYING,SCALE,CATALOG61,patch.PATCH,
        ROOT/'tools/typed72/projectiles_probe.cpp',ROOT/'tools/typed72/entity_probe.cpp',ROOT/'tools/typed72/targets_probe.cpp',ROOT/'tools/typed72/hero_probe.cpp',
        ROOT/'tools/typed72/verify_entities.py',ROOT/'tools/typed72/verify_targets.py',ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_protection.py',ROOT/'tools/typed72/verify_patch.py',ROOT/'tools/typed72/verify_stages.py',
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,
        protection.PROTECTION,protection.TEAMS,ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths}
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=protection.reference();pr=load_projectiles();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:ProjectileExtension(ctx,c,pref,pr));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%32==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-projectile-rules',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,excluded=['full entity motion tick','production atlas loading','full synchronous death effects','whole battle','network/replay'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
