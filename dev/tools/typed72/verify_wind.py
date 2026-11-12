"""Actual native wind + installed PvP59/56/70 wrappers and per-frame hero wind.

The oracle uses the installed raw patch namespace and literal wrapper bodies,
composed with the already verified actual damage/death and sourced chain.
"""
import argparse
import ast
import copy
import functools
import importlib
import json
import math
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_registry as registry
import proxy_reference
import evidence_store
import evidence_archive
death=registry.death;hero=death.hero;plants=death.plants;projectiles=death.projectiles;chili=death.chili;doom=death.doom;patch=death.patch
ROOT=hero.ROOT;P=death.P;sha=death.sha;difference=death.difference
WIND=hero.REF/'modkit/pvp/pvp59_wind.py'
PVP70=ROOT/'tools/pvp72_sources/pvp70_content.py'
WIND_FIELDS=('植物僵尸发射动画','植物僵尸角','射',P+'blover_zombie_cd',P+'blover_zombie_wind_tick')


def closure(path,method,name):
    tree=ast.parse(path.read_text(encoding='utf8'),str(path))
    matches=[f for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==method
             for f in n.body if isinstance(f,ast.FunctionDef) and f.name==name]
    if len(matches)!=1:raise ValueError('ambiguous wrapper '+str(path))
    return compile(ast.Module(body=matches,type_ignores=[]),str(path),'exec')


def reference():
    env=registry.reference()
    env['flying_wind_code']=closure(projectiles.FLYING,'install_wind','zombie_wind')
    env['pvp70_wind_code']=closure(PVP70,'_install','zombie_wind')
    proxy_reference.load()
    env['Wind']=importlib.import_module(proxy_reference.PACKAGE+'.pvp59_wind').Wind
    return env


class WindExtension(death.DeathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        cfg=case['wind'];self.ns=ctx.constructor_patch.ns;self.ns[P+'blover_zombie_blow_count']=0
        self.held_positions=[];self.wind_callbacks=[]
        for u,v in zip(self.units,cfg['units']):u.update(copy.deepcopy(v))
        self.g['伤害实体']=list(cfg['names']);self.g['雨']=[];self.g['zbspeedmax']=10.
        self.original_lists=[self.g[k] for k in ('实体','雨','伤害实体')]
        self.b.width=cfg.get('width',1920.);self.b.tile=self.g['比'];self.b.patch=ctx.constructor_patch
        self.b.mode=cfg.get('mode','duel');teams=ref['teams'];self.b.seats=teams['seats_for'](self.b.mode)
        self.b.scripted=teams['scripted'](self.b.mode);self.b.team_mode=teams['team_mode'](self.b.mode)
        self.b.team_seats=types.MethodType(ref['RegistryBattleOracle'].team_seats,self.b)
        self.wind_content=types.SimpleNamespace(b=self.b,g=self.g,pvp64=types.SimpleNamespace(grenades=[]))
        self.raw_wind=self.ns[P+'apply_blover_zombie_wind'];self.raw_update=self.ns[P+'update_blover_zombie']
        self.wind=ref['Wind'](self.wind_content)
        self.flying=types.SimpleNamespace(shots=[])
        closure_env=dict(self=self.flying,original=self.ns[P+'apply_blover_zombie_wind'])
        exec(ref['flying_wind_code'],closure_env);self.ns[P+'apply_blover_zombie_wind']=closure_env['zombie_wind']
        self.pvp70=types.SimpleNamespace(shots=[],c=self.wind_content,g=self.g)
        closure_env=dict(self=self.pvp70,wind=self.ns[P+'apply_blover_zombie_wind'],ns=self.ns,b=self.b,math=math,
                         wrap_delta=importlib.import_module(proxy_reference.PACKAGE+'.simulation').wrap_delta)
        exec(ref['pvp70_wind_code'],closure_env);self.ns[P+'apply_blover_zombie_wind']=closure_env['zombie_wind']
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        bind_env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',
            noop_unless_kind={},hero_free_bodies=frozenset(),telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),
            wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],bind_env);bind_env['bind']('update_blover_zombie',1,'zombie','zombies')
        surface=self.g['表面伤害僵尸']
        def observe_surface(index,direction,amount):
            self.wind_callbacks.append(dict(index=index,roster=[self.label(t) for t in self.g['僵尸']],
                entities=[e['名'] for e in self.g['实体']],rain=len(self.g['雨']),names=list(self.g['伤害实体'])))
            self.before('wind_surface');result=surface(index,direction,amount);self.after('wind_surface');return result
        self.g['表面伤害僵尸']=observe_surface

    def operation(self,op):
        action=op['op']
        if action=='wind_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='wind_hold':
            obj=self.births[op['entity']] if 'entity' in op else self.ctx.get_proxy(op['hero']) if 'hero' in op else self.units[op['unit']]
            self.held_positions.append(obj['位置'])
        elif action=='wind_alias':self.units[op['to']]['位置']=self.units[op['from']]['位置']
        elif action=='wind_entity':self.add_entity(op['name'],op.get('direction',1.),list(op['position']))
        elif action=='wind_flying':self.flying.shots=[self.births[i] for i in op['entities']]
        elif action=='wind_shot':
            (self.pvp70.shots if op['list']=='shots' else self.wind_content.pvp64.grenades).append(copy.deepcopy(op['values']))
        elif action=='wind_rain':self.g['雨']=copy.deepcopy(op['values'])
        elif action=='wind_environment':
            for k,name in (('speed','zbspeedmax'),('plk','plk'),('names','伤害实体')):
                if k in op:self.g[name]=copy.deepcopy(op[k])
        elif action=='wind_capture_lists':self.original_lists=[self.g[k] for k in ('实体','雨','伤害实体')]
        elif action=='wind_apply':
            fn=self.raw_wind if op.get('raw',False) else self.ns[P+'apply_blover_zombie_wind']
            return fn(self.g,self.units[op['unit']],op.get('strength',1.))
        elif action=='wind_update':
            cfg=copy.deepcopy(self.ns[P+'PLANT_ZOMBIE_CONFIG']['三叶草僵尸']);values=dict(op.get('config',{}))
            missing=values.pop('missing',[]);cfg.update(values)
            for k in missing:cfg.pop(k,None)
            fn=self.ns[P+'update_blover_zombie'] if op.get('sourced',True) else self.raw_update
            return fn(self.g,self.units[op['unit']],cfg)
        elif action=='wind_before_plants':return self.wind.before_plants()
        elif action=='wind_after_plants':return self.wind.after_plants()
        elif action=='wind_after_zombies':return self.wind.after_zombies()
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row)
        row['wind_units']=[{k:u[k] for k in WIND_FIELDS if k in u} for u in self.units]
        row['wind_held']=copy.deepcopy(self.held_positions)
        row['wind_rain']=[copy.deepcopy(p['位置'] if isinstance(p,dict) else p) for p in self.g['雨']]
        row['wind_names']=list(self.g['伤害实体']);row['wind_blows']=self.ns[P+'blover_zombie_blow_count']
        row['wind_callbacks']=copy.deepcopy(self.wind_callbacks)
        row['wind_list_identity']=[self.g[k] is old for k,old in zip(('实体','雨','伤害实体'),self.original_lists)]
        row['wind_pre']=copy.deepcopy(self.wind._pre);row['shots']=copy.deepcopy(self.pvp70.shots);row['grenades']=copy.deepcopy(self.wind_content.pvp64.grenades)


def base():
    c=death.base();c['units']=[projectiles.unit(x,432.,owner='zombie' if i%2==0 else 'plant') for i,x in enumerate((240.,340.,440.,1200.))]
    for u in c['units']:u['body']['血量']=100.
    c['wind']=dict(units=[{'植物僵尸':True,'植物僵尸名':'三叶草僵尸'},{},{},{}],width=1920.,mode='duel',
        names=['豌豆','冰豆','泡泡','海泡泡','火豆','蓝火豆','卷心菜','星星','西瓜','玉米粒','黄油','尖刺','冰瓜'])
    return c


def unit_write(index,**values):return dict(op='wind_unit',unit=index,values=values)


def make_cases():
    cases=[]
    for i in range(72):
        c=base();c['seed']=72000+i;direction=(-1.,0.,1.)[i%3];strength=(-2.,0.,.1,1.,3.,100.)[i//3%6]
        c['units'][0]['body']['方向']=direction
        for n,hand in enumerate(('报纸','气球','')):
            u=c['units'][n+1];u['body'].update(手持=hand,手持血量=.5 if i%2 else 200.,位置=[240.+(-1 if direction<0 else 1)*(n+1)*80.,432.,(-1000.,0.,1000.)[i%3],3.])
            c['wind']['units'][n+1].update(大小=(.1,.35,1.,2.)[i%4],气球=1. if n==2 and i%2 else 0.)
        c['wind']['units'][1]['死']=False
        c['operations']=[dict(op='wind_environment',speed=(.1,1.,10.,100.)[i%4],plk=(0.,.0048,1.)[i%3]),
            dict(op='wind_entity',name='豌豆',position=[260.,380.,1.,2.]),dict(op='wind_entity',name='装饰',position=[260.,380.,1.,2.]),
            dict(op='wind_rain',values=[[260.,380.,0.],{'位置':[1200.,380.,0.,3.]},[260.,380.]]),
            dict(op='wind_capture_lists'),dict(op='wind_hold',unit=1),dict(op='wind_hold',entity=0),
            dict(op='wind_apply',unit=0,strength=strength,raw=i<36)]
        cases.append(('wind-impulse-'+str(i),c))
    for i in range(32):
        c=base();c['seed']=72100+i;c['units'][1]['body'].update(手持='报纸',手持血量=100.)
        c['units'][2]['body'].update(手持='报纸',手持血量=100.)
        # Index 1 is out of range: the filtered roster must map index 1 to
        # the original index 2 before invoking native surface damage.
        c['units'][1]['body']['位置']=[1200.,432.,0.,0.];c['units'][2]['body']['位置']=[340.,432.,0.,0.]
        body=[unit_write(2,位置=[900.,432.,25.,5.],气球=1.),dict(op='roster_replace',targets=[3]),
            dict(op='effect_roster_replace',births=[]),dict(op='wind_rain',values=[[10.,10.,50.]]),
            dict(op='wind_environment',names=['装饰'])]
        if i%4==1:body=[unit_write(2,气球=1.,手持='气球')]
        if i%4==2:body=[dict(op='wind_alias',**{'from':2,'to':3}),unit_write(2,位置=[900.,432.,25.,5.])]
        if i%4==3:body=[dict(op='roster_append',target=2),dict(op='wind_unit',unit=0,values={'方向':-1.})]
        c['operations']=[dict(op='wind_entity',name='豌豆',position=[340.,380.,0.,0.]),
            dict(op='wind_rain',values=[[340.,380.,0.]]),dict(op='wind_capture_lists'),dict(op='wind_hold',unit=2),
            dict(op='lifecycle_hook',name='wind_surface',body=body,fail_before=i>=24,fail_after=16<=i<24),
            dict(op='wind_apply',unit=0,raw=i%2==0,strength=3.)]
        cases.append(('wind-callback-retain-'+str(i),c))
    for i in range(24):
        c=base();c['units'][0]['body']['位置'][0]=1900. if i%2 else 10.;c['units'][0]['body']['方向']=(-1.,0.,1.)[i%3]
        center=c['units'][0]['body']['位置'][0]
        c['operations']=[]
        for n,(kind,offset) in enumerate((('芜菁球弹',40.),('芦笋线弹',380.),('豌豆',500.),('芜菁球弹',-30.))):
            c['operations'].append(dict(op='wind_entity',name=kind,position=[(center+offset)%1920.,365.,0.,0.]))
        c['operations'] += [dict(op='wind_flying',entities=[0,1,3,3]),dict(op='effect_roster_replace',births=[0,2]),
            dict(op='wind_capture_lists'),dict(op='wind_hold',entity=1)]
        for name in ('shots','grenades'):
            for kind,x in (('hook',20.),('bone',1900.),(None,60.),('bone',900.)):
                v=dict(x=x,y=365.,vx=0.,vy=0.)
                if kind is not None:v['kind']=kind
                c['operations'].append(dict(op='wind_shot',list=name,values=v))
        c['operations'].append(dict(op='wind_apply',unit=0,strength=(-2.,0.,1.,3.)[i%4]))
        cases.append(('wind-wrapped-projectiles-'+str(i),c))
    for i in range(64):
        c=base();c['seed']=72200+i;c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        c['wind']['units'][0].update(植物僵尸发射动画=(0.,1.,6.,None)[i%4],植物僵尸角=(None,20.,-90.,180.)[i%4])
        c['wind']['units'][0][P+'blover_zombie_wind_tick']=(None,1.,2.,5.9)[i//4%4]
        cd=('missing',None,0.,1.,2.9,-2.,500.,10.)[i//8]
        if cd!='missing':c['wind']['units'][0][P+'blover_zombie_cd']=cd
        cfg=({'fire_anim':None,'cooldown':None},{'fire_anim':0.,'cooldown':-1.},{'missing':['fire_anim','cooldown']},{'fire_anim':6.9,'cooldown':3.9})[i%4]
        c['operations']=[dict(op='wind_update',unit=0,sourced=i%2==0,config=cfg) for unused in range(5)]
        cases.append(('wind-update-'+str(i),c))
    for i in range(48):
        c=base();c['wind']['mode']=('duel','duo','pve','coop')[i%4]
        c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i//4%4]
        c['wind']['units'][0].update(植物僵尸发射动画=1.,方向=(-1.,0.,1.)[i%3])
        if i>=32:c['wind']['units'][0]['魅惑']=None
        if i%8==1:c['wind']['units'][0]['死']=False
        if i%8==2:c['wind']['units'][0]['灰烬']=None
        if i%8==3:c['units'][0]['body']['血量']=0.
        for n,h in enumerate(c['heroes'].values()):h['玩家位置']=[240.+n*30.,432.,(0.,89.99,-89.99,200.)[n],0.]
        if i%7==0:c['heroes']['plant']['玩家血量']=0.
        c['operations']=[dict(op='wind_after_zombies'),dict(op='wind_after_zombies')]
        cases.append(('wind-hero-zombies-'+str(i),c))
    for i in range(32):
        c=base();c['wind']['mode']=('duel','duo','pve','coop')[i%4]
        for h in c['heroes'].values():h['玩家位置']=[400.,432.,89.99,0.]
        c['operations']=[dict(op='plant_original',cell=[8,4],name='三叶草',facing=1.),
            dict(op='plant_original',cell=[8,10],name='三叶草',facing=0. if i%2 else -1.),
            dict(op='wind_before_plants'),dict(op='position',target='zombie',values=[400.,432.,1.,0.])]
        if i%8==2:c['operations'].append(dict(op='write',target='zombie',values={'玩家血量':0.}))
        if i%8==3:c['operations'].append(dict(op='fire_plant_write',plant=0,values={'死':False}))
        if i%8==4:c['operations'].append(dict(op='plant_roster_replace',plants=[]))
        if i%8==5:c['operations'].append(dict(op='write',target='zombie',values={'玩家位置':[900.,432.,1.,0.]}))
        if i%8==6:c['operations'].append(dict(op='wind_environment',speed=0.,plk=0.))
        if i%8==7:c['operations'].append(dict(op='wind_environment',speed=-2.,plk=.0048))
        c['operations'] += [dict(op='wind_after_plants'),dict(op='wind_before_plants'),dict(op='wind_after_plants')]
        cases.append(('wind-hero-plants-'+str(i),c))
    for i in range(24):
        c=base();c['seed']=2**40+i
        c['units'][1]['body'].update(手持='报纸',手持血量=100.)
        c['units'][2]['body'].update(手持='报纸',手持血量=100.)
        c['units'][3]['body']['位置']=[1200.,432.,0.,0.]
        c['wind']['units'][0][P+'blover_zombie_cd']=0.
        body=[dict(op='wind_apply',unit=0,strength=.1,raw=i%2==0),
            unit_write(1,位置=[300.,432.,100.,1.]),dict(op='roster_replace',targets=[2,0])]
        c['operations']=[dict(op='wind_hold',unit=1),dict(op='wind_alias',**{'from':1,'to':2}),
            dict(op='lifecycle_hook',name='wind_surface',body=body,fail_after=i%3==0)]
        c['operations'].append(dict(op='wind_update',unit=0,sourced=i%2==0) if i>=12 else dict(op='wind_apply',unit=0,raw=i%2==0))
        cases.append(('wind-nested-'+str(i),c))
    for i in range(24):
        c=base();direction=-1. if i%2 else 1.;c['units'][0]['body']['方向']=direction
        # Unknown kind uses the original literal fallback head offset.
        c['wind']['units'][0]['植物僵尸名']='未知'
        cx=240.+direction*48.*.08;cy=432.-48.*1.35
        delta=(-1e-8,0.,1e-8)[i//2%3]
        c['units'][1]['body']['位置']=[cx+direction*(384.+delta),cy+48.,0.,0.]
        c['units'][2]['body']['位置']=[cx-direction*(12.+delta),cy+48.,0.,0.]
        c['operations']=[dict(op='wind_entity',name='豌豆',position=[cx+direction*(384.+delta),cy,0.,0.]),
            dict(op='wind_rain',values=[[cx,cy+384.+delta,0.],[cx-direction*100.,cy,0.]]),
            dict(op='wind_shot',list='shots',values=dict(kind='bone',x=cx+direction*(384.+delta),y=cy,vx=0.,vy=0.)),
            dict(op='wind_capture_lists'),dict(op='wind_apply',unit=0,strength=1.)]
        if i>=12:c['operations']+=[dict(op='wind_unit',unit=0,values={'位置':[cx-1920.,432.,0.,0.]}),dict(op='wind_apply',unit=0)]
        cases.append(('wind-radius-boundary-'+str(i),c))
    for i in range(16):
        c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2'];c['wind']['mode']='duo'
        for h in c['heroes'].values():h['玩家位置']=[340.,432.,1000.,0.]
        c['units'][0]['body']['方向']=-1. if i%2 else 1.
        c['operations']=[dict(op='wind_hold',hero='plant'),dict(op='wind_apply',unit=0,raw=i<8,strength=100.),
            dict(op='write',target='plant',values={'玩家位置':[340.,432.,0.,0.]}),
            dict(op='wind_apply',unit=0,raw=i<8,strength=100.)]
        cases.append(('wind-proxy-position-'+str(i),c))
    for seat in ('plant','zombie','plant2','zombie2'):
        for charm in (False,True):
            c=base();c['units'][0]['source']['_pvp_owner']=seat
            if charm:c['wind']['units'][0]['魅惑']=None
            c['wind']['units'][0][P+'blover_zombie_cd']=0.
            c['units'][1]['body'].update(手持='报纸',手持血量=.5)
            c['operations']=[dict(op='lifecycle_hook',name='wind_surface',body=[dict(op='source_observe')]),
                dict(op='wind_update',unit=0,sourced=True),dict(op='source_observe')]
            cases.append(('wind-sourced-update-%s-%s'%(seat,charm),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[WIND,PVP70,exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('wind_probe.cpp','verify_registry.py','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:WindExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-native-pvp-wind-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks and whole native driver','complete custom projectile movement','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
