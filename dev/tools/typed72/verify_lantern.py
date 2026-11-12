"""Independent installed lantern patch, healing helpers and source-context oracle."""
import argparse
import copy
import functools
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_death as death
import evidence_store
import evidence_archive
hero=death.hero;plants=death.plants;projectiles=death.projectiles;chili=death.chili;doom=death.doom;patch=death.patch
ROOT=hero.ROOT;P=death.P;sha=death.sha;difference=death.difference
FIELDS=('植物僵尸发射动画','植物僵尸角','射',P+'lantern_zombie_cd')
MARK=P+'native_lantern_charm_heal_mark'


def reference():return death.reference()


class LanternExtension(death.DeathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.ns=ctx.constructor_patch.ns
        for name in ('lantern_zombie_heal_count','native_lantern_charmed_heal_count'):self.ns[P+name]=0
        for u,v in zip(self.units,case['lantern']['units']):u.update(copy.deepcopy(v))
        self.raw_update=self.ns[P+'update_lantern_zombie']
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env);env['bind']('update_lantern_zombie',1,'zombie','zombies')

    def operation(self,op):
        action=op['op'];ns=self.ns
        if action=='lantern_unit':
            u=self.units[op['unit']];u.update(copy.deepcopy(op.get('values',{})))
            for k in op.get('erase',[]):u.pop(k,None)
        elif action=='lantern_plant':self.all_plants[op['plant']].update(copy.deepcopy(op['values']))
        elif action=='lantern_proxy':self.ctx.get_proxy(op['target']).update(copy.deepcopy(op['values']))
        elif action=='lantern_track':return ns[P+'track_zombie_max_hp'](self.g)
        elif action=='lantern_heal_zombie':return ns[P+'heal_zombie'](self.target(op['target']),op['amount'])
        elif action=='lantern_heal_plant':return ns[P+'heal_plant'](self.all_plants[op['plant']],op['amount'])
        elif action=='lantern_targets':return ns[P+'heal_lantern_zombie_targets'](self.g,self.units[op['unit']],op['point'])
        elif action=='lantern_effects':return ns[P+'spawn_lantern_heal_effects'](self.g,op['point'],op.get('count',1))
        elif action=='lantern_range':return ns[P+'point_in_square_radius'](self.g,op['center'],op['point'],op.get('tiles',3.))
        elif action=='lantern_update':
            cfg=copy.deepcopy(ns[P+'PLANT_ZOMBIE_CONFIG']['路灯花僵尸']);v=dict(op.get('config',{}));missing=v.pop('missing',[]);cfg.update(v)
            for k in missing:cfg.pop(k,None)
            return (ns[P+'update_lantern_zombie'] if op.get('sourced',True) else self.raw_update)(self.g,self.units[op['unit']],cfg)
        elif action=='lantern_native':return ns[P+'update_native_lantern_charmed_healing'](self.g)
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row)
        row['lantern_counts']=[self.ns[P+n] for n in ('lantern_zombie_heal_count','native_lantern_charmed_heal_count')]
        row['lantern_units']=[{k:u[k] for k in FIELDS if k in u} for u in self.units]
        row['lantern_plants']=[{MARK:p[MARK]} if MARK in p else {} for p in self.all_plants]


def base():
    c=death.base();c['units']=[projectiles.unit(240.+i*40.,432.,owner='zombie') for i in range(4)]
    for u in c['units']:u['body']['血量']=100.
    c['lantern']=dict(units=[{'植物僵尸':True,'植物僵尸名':'路灯花僵尸'},{},{},{}])
    return c


def write(i,**v):return dict(op='lantern_unit',unit=i,values=v)


def make_cases():
    cases=[]
    for i in range(96):
        c=base();hp=(0.,1.,50.,100.)[i%4];observed=('missing',None,0.,100.)[i//4%4];specific=('missing',None,0.,200.)[i//16%4]
        c['units'][0]['body']['血量']=hp
        if observed!='missing':c['lantern']['units'][0][P+'zombie_observed_max_hp']=observed
        if specific!='missing':c['lantern']['units'][0][P+'plant_zombie_max_hp']=specific
        if i%8==1:c['lantern']['units'][0]['灰烬']=None
        if i%8==2:c['lantern']['units'][0]['死']=False
        amount=(-1.,0.,10.,1000.)[i//4%4]
        c['operations']=[dict(op='lantern_heal_zombie',target=0,amount=amount),dict(op='lantern_track'),dict(op='native_hit',target=0,kind='ordinary',amount=2.),
            dict(op='lantern_heal_zombie',target=0,amount=amount),write(0,血量=500.),dict(op='lantern_track')]
        cases.append(('lantern-health-'+str(i),c))
    for i in range(48):
        c=base();c['operations']=[dict(op='plant_original',cell=[8,4],name='坚果')]
        values={'植物血':(0.,1.,5.,10.)[i%4],'植物血上限':(None,0.,10.)[i//4%3]}
        if i%8==1:values['死']=False
        if i%8==2:values['铲死']=None
        c['operations'] += [dict(op='lantern_plant',plant=0,values=values),dict(op='lantern_heal_plant',plant=0,amount=(-1.,0.,2.,100.)[i//12]),
            dict(op='lantern_range',center=[240.,400.],point=[384.+(-1e-8,0.,1e-8)[i%3],544.])]
        cases.append(('lantern-plant-health-'+str(i),c))
    for i in range(64):
        c=base();c['seed']=72300+i
        for n,u in enumerate(c['lantern']['units']):
            u[P+'zombie_observed_max_hp']=200.
            if n%2:u['魅惑']=None
        c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        if i%2:c['lantern']['units'][0]['魅惑']=None
        c['lantern']['units'][0].update(植物僵尸发射动画=(0.,5.,None,125.)[i%4],植物僵尸角=(None,30.,-90.,180.)[i%4])
        cd=('missing',None,0.,1.,2.,-1.,100.,5.9)[i//8]
        if cd!='missing':c['lantern']['units'][0][P+'lantern_zombie_cd']=cd
        for h in c['heroes'].values():h['秘籍']=['光疗'] if i%3==0 else []
        c['globals']['秘籍']=['光疗'] if i%3==1 else []
        c['operations']=[dict(op='plant_original',cell=[8,4],name='向日葵'),dict(op='plant_original',cell=[8,5],name='大蒜'),
            dict(op='lantern_plant',plant=0,values={'植物血':1.}),dict(op='lantern_plant',plant=1,values={'植物血':1.})]
        cfg=({'fire_anim':None,'cooldown':None},{'fire_anim':0.,'cooldown':-1.},{'missing':['fire_anim','cooldown']},{'fire_anim':5.9,'cooldown':2.9})[i%4]
        c['operations'] += [dict(op='lantern_update',unit=0,sourced=i%2==0,config=cfg) for unused in range(5)]
        cases.append(('lantern-update-'+str(i),c))
    for i in range(32):
        c=base();c['seed']=2**40+i
        for u in c['lantern']['units']:u[P+'zombie_observed_max_hp']=200.
        c['operations']=[dict(op='lifecycle_hook',name='add',fail_before=i%4==0,fail_after=i%4==1)]
        if i%4>=2:
            body=[dict(op='effect_roster_replace',births=[]),dict(op='roster_replace',targets=[2]),
                write(0,魅惑=None),write(2,魅惑=0.)]
            if i%4==3:body=[write(2,血量=0.),write(3,位置=[1200.,432.,0.,0.])]
            c['operations']=[dict(op='lifecycle_hook',name='add',body=body)]
        c['operations'] += [dict(op='lantern_targets',unit=0,point=[250.,370.]),dict(op='lantern_effects',point=[240.,400.],count=(-1,0,1,2)[i%4])]
        cases.append(('lantern-callback-'+str(i),c))
    for i in range(48):
        c=base();c['globals']['秘籍']=['光疗'] if i%2 else []
        for n,u in enumerate(c['lantern']['units']):
            u[P+'zombie_observed_max_hp']=500.
            if n!=3:u['魅惑']=None
        if i%4==1:c['lantern']['units'][1]['死']=False
        if i%4==2:c['lantern']['units'][1]['灰烬']=None
        if i%4==3:
            for u in c['lantern']['units']:u['死']=False
        c['operations']=[dict(op='plant_original',cell=[8,4],name='路灯花'),dict(op='lantern_plant',plant=0,values={'爆了':(0.,1.,124.,125.,126.,None)[i%6]}),
            dict(op='lantern_native'),dict(op='lantern_native'),dict(op='lantern_plant',plant=0,values={'爆了':0.}),dict(op='lantern_native'),
            dict(op='lantern_plant',plant=0,values={'爆了':125.}),dict(op='lantern_native')]
        cases.append(('lantern-native-pulse-'+str(i),c))
    for i,seat in enumerate(('plant','zombie','plant2','zombie2')):
        c=base();c['damage']['hero_targets']=[seat];c['heroes'][seat]['玩家血量']=20.
        c['operations']=[dict(op='lantern_track'),dict(op='lantern_proxy',target=seat,values={P+'zombie_observed_max_hp':100.}),
            dict(op='lantern_heal_zombie',target=seat,amount=60.),dict(op='lantern_targets',unit=0,point=[250.,370.])]
        cases.append(('lantern-hero-no-heal-'+seat,c))
    for seat in ('plant','zombie','plant2','zombie2'):
        for charm in ('missing',None,0.):
            c=base();c['units'][0]['source']['_pvp_owner']=seat
            if charm!='missing':c['lantern']['units'][0]['魅惑']=charm
            c['lantern']['units'][0][P+'lantern_zombie_cd']=0.
            c['lantern']['units'][1].update({P+'zombie_observed_max_hp':500.,'魅惑':None})
            c['lantern']['units'][2][P+'zombie_observed_max_hp']=500.
            c['globals']['秘籍']=[]
            for h in c['heroes'].values():h['秘籍']=['光疗']
            c['operations']=[dict(op='plant_original',cell=[8,4],name='向日葵'),
                dict(op='lantern_plant',plant=0,values={'植物血':1.}),
                dict(op='lifecycle_hook',name='add',body=[dict(op='source_observe')]),dict(op='lantern_update',unit=0)]
            cases.append(('lantern-update-source-%s-%s'%(seat,charm),c))
    for i in range(16):
        c=base();c['globals']['秘籍']=['光疗'];c['lantern']['units'][0]['魅惑']=None
        for n,u in enumerate(c['lantern']['units']):
            u[P+'zombie_observed_max_hp']=500.
            if n%2:u['魅惑']=None
        c['operations']=[dict(op='plant_original',cell=[8,4],name='向日葵'),
            dict(op='plant_original',cell=[8,5],name='大蒜'),dict(op='lantern_plant',plant=0,values={'植物血':1.}),
            dict(op='lantern_plant',plant=1,values={'植物血':1.})]
        body=[dict(op='roster_replace',targets=[2,3]),dict(op='lantern_unit',unit=0,erase=['魅惑'])]
        if i%4==1:body=[dict(op='plant_roster_replace',plants=[]),dict(op='roster_replace',targets=[3])]
        if i%4==2:body=[write(2,魅惑=None),dict(op='roster_append',target=2),dict(op='effect_roster_replace',births=[])]
        if i%4==3:body=[write(0,位置=[1000.,432.,0.,0.]),write(1,死=False)]
        c['operations'] += [dict(op='lifecycle_hook',name='add',body=body,fail_after=i>=8),dict(op='lantern_targets',unit=0,point=[250.,370.])]
        cases.append(('lantern-plant-callback-roster-'+str(i),c))
    for i in range(16):
        c=base()
        for n,u in enumerate(c['lantern']['units']):
            u[P+'zombie_observed_max_hp']=500.
            if n<3:u['魅惑']=None
        c['operations']=[dict(op='plant_original',cell=[8,4],name='路灯花'),dict(op='plant_original',cell=[8,5],name='路灯花'),
            dict(op='lantern_plant',plant=0,values={'爆了':125.}),dict(op='lantern_plant',plant=1,values={'爆了':125.})]
        body=[dict(op='roster_replace',targets=[3]),dict(op='plant_roster_replace',plants=[])]
        if i%2:body=[dict(op='roster_append',target=2),write(1,死=False)]
        c['operations'] += [dict(op='lifecycle_hook',name='add',body=body,fail_after=i>=8),dict(op='lantern_native')]
        cases.append(('lantern-native-captured-roster-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('lantern_probe.cpp','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:LanternExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-lantern-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks','whole native driver','PvP66 lantern burn/wake scheduler','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
