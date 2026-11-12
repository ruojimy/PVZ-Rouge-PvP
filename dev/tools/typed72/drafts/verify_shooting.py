"""Literal native plant-zombie shooting loop over the installed typed chains."""
import argparse
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
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_peas as peas
import verify_wind as wind
services=peas.services;death=peas.death;hero=peas.hero;plants=peas.plants;projectiles=peas.projectiles;chili=peas.chili;doom=peas.doom;patch=peas.patch
ROOT=hero.ROOT;P=peas.P;sha=peas.sha;difference=peas.difference;PVP70=peas.PVP70;PVP66=peas.PVP66
FIELDS=('植物僵尸射cd','植物僵尸连发','植物僵尸连发cd',P+'plant_zombie_jump_cd',P+'blover_zombie_cd',P+'blover_zombie_wind_tick',P+'lantern_zombie_cd',P+'fumeshroom_zombie_cd',P+'fumeshroom_zombie_attack_angle',P+'fumeshroom_zombie_damage_done',P+'fumeshroom_zombie_bubble_tick','移速','跳跃cd','撑杆','眩晕','气球','牛顿')
COUNTERS=('plant_zombie_motion_fix_count','blover_zombie_blow_count','lantern_zombie_heal_count','native_lantern_charmed_heal_count','fumeshroom_zombie_attack_count')
KINDS=('豌豆僵尸','机枪僵尸','坚果僵尸','高坚果僵尸','辣椒僵尸','毁灭菇僵尸','三叶草僵尸','路灯花僵尸','倭瓜僵尸','墓碑吞噬者僵尸','萝卜伞僵尸','吸金磁僵尸','大喷菇僵尸')

def reference():
    env=peas.reference();env.update(wind.reference());return env

class ShootingExtension(peas.PeaExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        for u,v in zip(self.units,case['shooting']['units']):u.update(copy.deepcopy(v))
        for key in COUNTERS:self.ns[P+key]=0
        self.ns[P+'fumeshroom_bubbles']=[];self.ns[P+'fumeshroom_bubble_last_update']=0.
        self.g.update(伤害实体=[],雨=[],zbspeedmax=10.)
        self.b.width=960.;self.b.patch=ctx.constructor_patch;self.b.mode='duel';teams=ref['teams']
        self.b.seats=teams['seats_for']('duel');self.b.scripted=teams['scripted']('duel');self.b.team_mode=teams['team_mode']('duel')
        self.b.team_seats=types.MethodType(ref['RegistryBattleOracle'].team_seats,self.b)
        self.shoot_wind_content=types.SimpleNamespace(b=self.b,g=self.g,pvp64=types.SimpleNamespace(grenades=[]))
        self.shoot_wind=ref['Wind'](self.shoot_wind_content);self.shoot_flying=types.SimpleNamespace(shots=[])
        env=dict(self=self.shoot_flying,original=self.ns[P+'apply_blover_zombie_wind']);exec(ref['flying_wind_code'],env);self.ns[P+'apply_blover_zombie_wind']=env['zombie_wind']
        self.shoot_pvp70=types.SimpleNamespace(shots=[],c=self.shoot_wind_content,g=self.g)
        env=dict(self=self.shoot_pvp70,wind=self.ns[P+'apply_blover_zombie_wind'],ns=self.ns,b=self.b,math=math,
            wrap_delta=importlib.import_module(wind.proxy_reference.PACKAGE+'.simulation').wrap_delta)
        exec(ref['pvp70_wind_code'],env);self.ns[P+'apply_blover_zombie_wind']=env['zombie_wind']
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env)
        for name in ('update_plant_zombie_target','update_blover_zombie','update_lantern_zombie','update_fumeshroom_zombie','apply_fumeshroom_line_attack'):env['bind'](name,1,'zombie','zombies')

    def operation(self,op):
        action=op['op'];ns=self.ns;g=self.g
        if action=='shoot_unit':
            u=self.units[op['unit']];u.update(copy.deepcopy(op.get('values',{})))
            for key in op.get('erase',[]):u.pop(key,None)
        elif action=='shoot_config':
            c=ns[P+'PLANT_ZOMBIE_CONFIG'][op['kind']];v=copy.deepcopy(op['values']);missing=v.pop('missing',[]);c.update(v)
            for key in missing:c.pop(key,None)
        elif action=='shoot_live':return ns[P+'has_live_plant_zombies'](g['僵尸'],op.get('names'))
        elif action in ('shoot_motion','shoot_jump'):
            u=self.units[op['unit']];c=ns[P+'PLANT_ZOMBIE_CONFIG'][op.get('kind',u['植物僵尸名'])]
            return ns[P+('enforce_plant_zombie_motion' if action=='shoot_motion' else 'update_plant_zombie_jump_assist')](g,u,c)
        elif action=='shoot_step':return ns[P+'update_plant_zombie_shooting'](g)
        elif action=='shoot_projectiles':
            ns[P+'update_zombie_peas'](g);ns[P+'finish_squash_entities'](g);ns[P+'update_squash_zombie_entities'](g)
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row);row['shoot_counts']=[self.ns[P+n] for n in COUNTERS]
        row['shoot_units']=[{k:u[k] for k in FIELDS if k in u} for u in self.units]
        row['shoot_bubbles']=copy.deepcopy(self.ns[P+'fumeshroom_bubbles'])

def base():
    c=peas.base();c['shooting']=dict(units=[{},{},{},{}]);c['units'][0]['body']['血量']=300.;return c

def write(i,**values):return dict(op='shoot_unit',unit=i,values=values)
def config(kind,**values):return dict(op='shoot_config',kind=kind,values=values)

def make_cases():
    cases=[]
    for k,kind in enumerate(KINDS):
        for i in range(12):
            c=base();c['seed']=78000+k*12+i;c['services']['units'][0]['植物僵尸名']=kind
            if i%2:c['services']['units'][0]['魅惑']=None
            c['services']['units'][1].update(魅惑=None,手持='钢门',手持血量=30.);c['services']['units'][2].update(防具='铁桶',防具血量=30.)
            c['shooting']['units'][0].update(植物僵尸射cd=(-1.,0.,1.)[i%3],植物僵尸连发=(0.,1.,3.)[i//3%3],植物僵尸连发cd=(0.,1.,6.)[i//3%3],射=1.,植物僵尸发射动画=(0.,1.,24.)[i%3])
            c['operations']=[dict(op='plant_original',cell=[8,5],name='向日葵'),dict(op='plant_original',cell=[8,6],name='火炬树桩')]
            c['operations'] += [dict(op='shoot_step') for n in range(8)]
            c['operations'] += [dict(op='batch',body=[dict(op='shoot_step') for n in range(25)]),dict(op='shoot_projectiles')]
            cases.append(('shoot-kind-'+str(k)+'-'+str(i),c))
    for i in range(96):
        c=base();kind=('豌豆僵尸','机枪僵尸')[i%2];c['services']['units'][0]['植物僵尸名']=kind
        c['operations']=[config(kind,cooldown=(None,-1.,0.,2.)[i%4],initial_cooldown_max=(None,0.,5.)[i//4%3],burst_gap=(None,-1.,0.,2.)[i//12%4],fire_anim=(None,0.,2.)[i//32],burst=(None,1.,2.,4.)[i%4]),
            write(0,植物僵尸射cd=(-1.,0.,1.,None)[i%4],植物僵尸连发=(None,0.,1.,2.)[i//4%4],植物僵尸连发cd=(None,0.,1.,2.)[i//16%4]),
            dict(op='shoot_step'),dict(op='shoot_step'),dict(op='batch',body=[dict(op='shoot_step') for n in range(20)])]
        cases.append(('shoot-burst-clock-'+str(i),c))
    for i in range(96):
        c=base();kind=('豌豆僵尸','倭瓜僵尸')[i%2];c['services']['units'][0]['植物僵尸名']=kind
        c['shooting']['units'][0].update(手持=('撑杆','弹跳杆','钢门','')[i%4],手持血量=25.,移速=(None,0.,1.,100.)[i//4%4],撑杆=(None,0.,1.)[i//16%3],位置=[240.,432.,(-50.,0.,50.)[i//32],-5.])
        c['operations']=[config(kind,move_speed=(None,0.,100.,1000.)[i%4],jump_speed=(None,0.,330.)[i//4%3]),dict(op='shoot_motion',unit=0),dict(op='shoot_motion',unit=0)]
        cases.append(('shoot-motion-enforcement-'+str(i),c))
    for i in range(80):
        c=base();c['services']['units'][0]['植物僵尸名']='倭瓜僵尸';c['shooting']['units'][0].update(位置=[240.,432.,3.,(-1.00001,-1.,0.,1.,1.00001)[i%5]],方向=(-1.,1.)[i//5%2],牛顿=(None,0.,1.)[i//10%3],**{P+'plant_zombie_jump_cd':(None,0.,1.,75.)[i//20]})
        c['operations']=[dict(op='tile_replace',cell=[8,5 if i//5%2 else 4],value={'方块':('空','石','水','梯子块')[i%4]}),dict(op='shoot_jump',unit=0),dict(op='shoot_jump',unit=0)]
        cases.append(('shoot-jump-assist-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][1].update(植物僵尸=True,植物僵尸名='机枪僵尸')
        marker=('死','灰烬')[i%2];c['services']['units'][0][marker]=False if marker=='死' else None
        c['units'][1]['body']['血量']=0. if i%4<2 else 300.
        if i%8==0:c['services']['units'][0]['植物僵尸名']='未知'
        c['operations']=[dict(op='shoot_live',names=(None,[],['豌豆僵尸'],['机枪僵尸'])[i//4%4]),dict(op='shoot_step'),dict(op='roster_replace',targets=[0]),dict(op='shoot_live'),dict(op='shoot_step')]
        cases.append(('shoot-live-precheck-'+str(i),c))
    for i in range(64):
        c=base();c['services']['units'][1].update(植物僵尸=True,植物僵尸名='机枪僵尸');c['services']['units'][2].update(植物僵尸=True,植物僵尸名='大喷菇僵尸')
        body=[dict(op='roster_replace',targets=([3],[3,0,2,1],[])[i%3]),write(1,魅惑=None),dict(op='source_observe')]
        c['operations']=[dict(op='lifecycle_hook',name='add',body=body,fail_before=i%4==0,fail_after=i%4==1),dict(op='shoot_step'),dict(op='shoot_step')]
        cases.append(('shoot-captured-roster-'+str(i),c))
    for i in range(48):
        c=base();c['services']['units'][0]['植物僵尸名']='机枪僵尸';c['peas']['units'][0]['_pvp_card']='zombie:机枪僵尸';c['shooting']['units'][0]['植物僵尸射cd']=-1.
        c['operations']=[dict(op='pea_environment',enabled=True,shotgun=True,tick=(0,199,200,400)[i%4]),dict(op='shoot_step'),dict(op='batch',body=[dict(op='shoot_step') for n in range(30)]),dict(op='pea_environment',tick=400),dict(op='batch',body=[dict(op='shoot_step') for n in range(110)])]
        cases.append(('shoot-pvp-shotgun-'+str(i),c))
    return cases

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[PVP66,PVP70,exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('shooting_probe.cpp','verify_peas.py','verify_wind.py','verify_registry.py','pea_probe.cpp','verify_squash.py','verify_fume.py','squash_probe.cpp','service_probe.cpp','verify_services.py','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:ShootingExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-plant-zombie-shooting',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks','whole native driver','complete custom content scheduler','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
