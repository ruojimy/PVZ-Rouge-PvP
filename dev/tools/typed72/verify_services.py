"""Actual installed umbrella/gold-magnet bodies and literal PvP70 wrapper."""
import argparse
import ast
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
PVP70=ROOT/'tools/pvp72_sources/pvp70_content.py'
FIELDS=('植物僵尸发射动画','植物僵尸角','射',P+'umbrella_zombie_cd',P+'gold_magnet_zombie_cd','_pvp_umbrella_secret','_pvp_umbrella_initialized')
COUNTERS=('umbrella_zombie_trigger_count','gold_magnet_zombie_gift_count','gold_magnet_zombie_absorb_count')


def reference():
    env=death.reference();tree=ast.parse(PVP70.read_text(encoding='utf8'),str(PVP70))
    nodes=[f for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_install' for f in n.body if isinstance(f,ast.FunctionDef) and f.name=='update_umbrella']
    assert len(nodes)==1;env['umbrella_code']=compile(ast.Module(body=nodes,type_ignores=[]),str(PVP70),'exec');return env


class ServiceExtension(death.DeathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.ns=ctx.constructor_patch.ns
        for n in COUNTERS:self.ns[P+n]=0
        for u,v in zip(self.units,case['services']['units']):u.update(copy.deepcopy(v))
        self.raw_umbrella=self.ns[P+'update_umbrella_zombie'];self.raw_magnet=self.ns[P+'update_gold_magnet_zombie']
        env=dict(ns=self.ns,umbrella=self.raw_umbrella);exec(ref['umbrella_code'],env);self.raw_pvp_umbrella=env['update_umbrella']
        obj=types.SimpleNamespace(ns=self.ns,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(ref['bind_code'],env)
        for n in ('update_umbrella_zombie','update_gold_magnet_zombie'):env['bind'](n,1,'zombie','zombies')
        env=dict(ns=self.ns,umbrella=self.ns[P+'update_umbrella_zombie']);exec(ref['umbrella_code'],env);self.ns[P+'update_umbrella_zombie']=env['update_umbrella']

    def config(self,op,name):
        c=copy.deepcopy(self.ns[P+'PLANT_ZOMBIE_CONFIG'][name]);v=copy.deepcopy(op.get('config',{}));missing=v.pop('missing',[]);c.update(v)
        for k in missing:c.pop(k,None)
        return c

    def entity_values(self,e,values):
        values=copy.deepcopy(values);key=P+'umbrella_reflected_by'
        if key in values and values[key] is not None:values[key]=id(self.units[values[key]['unit']])
        e.update(values)

    def operation(self,op):
        action=op['op'];ns=self.ns;g=self.g
        if action=='service_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action=='service_entity':self.add_entity(op['name'],op.get('facing',1.),list(op['position']));self.entity_values(self.births[-1],op.get('values',{}))
        elif action=='service_entity_write':self.entity_values(self.births[op['entity']],op['values'])
        elif action=='service_live':return ns[P+'live_zombie'](self.target(op['target']))
        elif action=='service_armor':return ns[P+'zombie_has_head_armor'](self.target(op['target']))
        elif action=='service_animate':return ns[P+'animate_service_plant_zombie_head'](self.units[op['unit']],self.config(op,'萝卜伞僵尸'),op.get('spread',35.))
        elif action in ('service_reflect','service_bounce','service_knock_units','service_knock_player'):
            name={'service_reflect':'umbrella_reflect_projectiles','service_bounce':'umbrella_bounce_basketballs','service_knock_units':'umbrella_knock_zombies','service_knock_player':'umbrella_knock_player'}[action]
            args=[g]+([self.units[op['unit']]] if action in ('service_reflect','service_knock_units') else [])+[op['center'],op.get('radius',2.)]
            return ns[P+name](*args)
        elif action in ('service_umbrella','service_magnet'):
            try:
                if action=='service_magnet':return (ns[P+'update_gold_magnet_zombie'] if op.get('sourced',True) else self.raw_magnet)(g,self.units[op['unit']],self.config(op,'吸金磁僵尸'))
                return (ns[P+'update_umbrella_zombie'] if op.get('sourced',True) else self.raw_pvp_umbrella if op.get('pvp',True) else self.raw_umbrella)(g,self.units[op['unit']],self.config(op,'萝卜伞僵尸'))
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        elif action=='service_pick':
            a=op.get('absorb',False);t=ns[P+('pick_gold_magnet_absorb_target' if a else 'pick_gold_magnet_bucket_target')](g,self.units[op['unit']],op['center'],op.get('radius',9. if a else 5.))
            return None if t is None else [self.label(t[0]),list(t[1])]+([t[2]] if a else [])
        elif action=='service_gift':return ns[P+'gift_bucket_to_zombie'](g,self.units[0],self.target(op['target']),op['center'],[0.,0.])
        elif action=='service_absorb':return ns[P+'absorb_metal_from_zombie'](g,self.units[0],self.target(op['target']),op['point'],op['center'],op['slot'])
        elif action=='service_attract':
            e=ns[P+'spawn_magnet_attract_effect'](g,op['name'],op['start'],op['end']);return next(i for i,x in enumerate(self.births) if x is e) if e is not None else None
        else:return super().operation(op)
        return None

    def snapshot(self,row):
        super().snapshot(row);row['service_counts']=[self.ns[P+n] for n in COUNTERS];row['service_units']=[{k:u[k] for k in FIELDS if k in u} for u in self.units]
        for name in ('entities','effect_births'):
            for e in row[name]:
                k=P+'umbrella_reflected_by'
                if k in e and e[k] is not None:e[k]={'unit':next(i for i,u in enumerate(self.units) if id(u)==e[k])}


def base():
    c=death.base();c['units']=[projectiles.unit(240.+i*40.,432.,owner='zombie') for i in range(4)]
    c['services']=dict(units=[{'植物僵尸':True,'植物僵尸名':'萝卜伞僵尸'},{},{},{}]);return c


def write(i,**v):return dict(op='service_unit',unit=i,values=v)
def entity(name,position,**v):return dict(op='service_entity',name=name,position=position,values=v)


def make_cases():
    cases=[]
    for i in range(72):
        c=base();c['seed']=74100+i;c['services']['units'][0].update(方向=(-1.,0.,1.)[i%3],植物僵尸发射动画=('missing',None,0.,1.,25.,50.,100.,-1.)[i//9])
        if c['services']['units'][0]['植物僵尸发射动画']=='missing':del c['services']['units'][0]['植物僵尸发射动画']
        c['operations']=[dict(op='service_animate',unit=0,config={'fire_anim':f},spread=s) for f,s in ((None,35.),(0.,55.),(5.9,-28.))]
        cases.append(('service-animation-'+str(i),c))
    for i in range(72):
        c=base();x=240.+(-96.00001,-96.,0.,96.,96.00001,200.)[i%6];vx=(-8.,-.001,0.,.001,.002,8.)[i//6%6]
        for j,n in enumerate(('卷心菜','西瓜','冰瓜','玉米粒','黄油','豌豆','篮球','篮球x')):
            v={'智能弹道':None if i%3==0 else {} if i%3==1 else {'target_index':1,'initial_speed':8.,'gravity':.1},'消亡':(None,0.,950.)[i%3]}
            if j%2:v[P+'umbrella_reflected_by']={'unit':0 if i%2 else 1}
            c['operations'].append(entity(n,[x,350.+(j%3)*40.,vx,(-10.,0.,10.)[i%3]],**v))
        c['operations'] += [dict(op='service_reflect',unit=u,center=[240.,400.],radius=(2.,-1.)[i//36]) for u in (0,0,1)]
        c['operations'] += [dict(op='service_bounce',center=[240.,400.],radius=2.)]
        cases.append(('service-reflection-'+str(i),c))
    for i in range(64):
        c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2'];c['units'][1]['body']['位置']=[240.,431.2,3.,4.];c['units'][1]['body']['方向']=-1.
        if i%2:c['services']['units'][0]['魅惑']=None
        c['services']['units'][2]['魅惑']=0.
        if i%4==0:c['services']['units'][1]['死']=False
        if i%4==1:c['services']['units'][1]['灰烬']=None
        if i%4==2:c['units'][1]['body']['血量']=0.
        c['services']['units'][3]['牛顿']=(None,0.,10.,-.1)[i%4]
        c['globals']['玩家位置']=[(144.,240.,336.,337.)[i//4%4],400.,0.,(0.,-20.)[i//32]]
        c['operations']=[dict(op='service_knock_units',unit=0,center=[240.,400.],radius=(0.,1.,2.,-1.)[i//16]),
            dict(op='service_knock_player',center=[240.,400.],radius=2.)]
        for t in (0,1,'zombie'):c['operations']+=[dict(op='service_live',target=t),dict(op='service_armor',target=t)]
        cases.append(('service-knock-'+str(i),c))
    for i in range(128):
        c=base();c['seed']=74200+i;c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        if i%2:c['services']['units'][0]['魅惑']=None
        c['services']['units'][0].update(_pvp_umbrella_secret=bool(i%4<2),_pvp_umbrella_initialized=bool(i%8<4))
        cd=('missing',None,0.,1.,2.,-1.,100.,5.9)[i//16]
        if cd!='missing':c['services']['units'][0][P+'umbrella_zombie_cd']=cd
        c['services']['units'][0]['植物僵尸发射动画']=(0.,5.,None,50.)[i%4]
        if i%4==3:
            for u in c['units'][1:]:u['body']['位置']=[1200.,432.,0.,0.]
        c['operations']=[entity('卷心菜',[240.,400.,.0001,0.]),entity('篮球',[240.,400.,4.,1.])]
        cfg=({'fire_anim':None,'cooldown':None},{'fire_anim':0.,'cooldown':-1.},{'missing':['fire_anim','cooldown']},{'fire_anim':5.9,'cooldown':2.9,'radius':1.})[i%4]
        c['operations'] += [dict(op='service_umbrella',unit=0,sourced=i%3!=0,pvp=i%8!=0,config=cfg,catch=True) for unused in range(6)]
        cases.append(('service-umbrella-update-'+str(i),c))
    armors=('','路障','铁桶','橄榄球头盔','黑橄榄球头盔','南瓜头防具','钢门','梯子','矿镐','弹跳杆','木板')
    for i in range(88):
        c=base();c['units'][1]['body']['位置']=[280.,432.,0.,0.];c['units'][2]['body']['位置']=[280.,432.,0.,0.]
        c['units'][3]['body']['位置']=[1200.,432.,0.,0.];c['damage']['hero_targets']=['plant','zombie']
        c['services']['units'][1].update(防具=armors[i%11],防具血量=(0.,1.,100.,-1.)[i//11%4],手持=armors[(i+3)%11],手持血量=1.)
        c['services']['units'][2].update(防具='铁桶',防具血量=100.,手持='钢门',手持血量=(0.,1.)[i%2])
        if i%8==1:c['services']['units'][1]['死']=False
        if i%8==2:c['services']['units'][1]['灰烬']=None
        if i%8==3:c['services']['units'][1]['魅惑']=0.
        c['operations']=[dict(op='service_pick',unit=0,center=[240.,400.],absorb=a) for a in (False,True)]
        c['operations'] += [dict(op='service_absorb',target=1,point=[280.,400.],center=[240.,400.],slot=s) for s in ('handheld','armor','armor')]
        c['operations'] += [dict(op='service_gift',target=1,center=[240.,400.]),dict(op='service_pick',unit=0,center=[240.,400.],absorb=False)]
        cases.append(('service-metal-selection-'+str(i),c))
    for i in range(64):
        c=base();c['seed']=74300+i;c['services']['units'][0]['植物僵尸名']='吸金磁僵尸'
        c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        if i%2:c['services']['units'][0]['魅惑']=None
        cd=('missing',None,0.,1.,2.,-1.,100.,5.9)[i//8]
        if cd!='missing':c['services']['units'][0][P+'gold_magnet_zombie_cd']=cd
        c['services']['units'][1].update(手持='钢门',手持血量=100.,防具='铁桶',防具血量=1.)
        if i%4==3:
            for u in c['units'][1:]:u['body']['位置']=[1200.,432.,0.,0.]
        c['operations']=[dict(op='lifecycle_hook',name='add',body=[dict(op='source_observe')])]
        cfg=({'fire_anim':None,'cooldown':None},{'fire_anim':0.,'cooldown':-1.},{'missing':['fire_anim','cooldown']},{'fire_anim':5.9,'cooldown':2.9})[i%4]
        c['operations'] += [dict(op='service_magnet',unit=0,sourced=i%3!=0,config=cfg) for unused in range(6)]
        cases.append(('service-magnet-update-'+str(i),c))
    for i,mode in enumerate(('正常模式','极难模式','末日模式','无尽模式','测试模式','植物僵尸','我是僵尸','未知模式')):
        for seat in (0,'plant','zombie','plant2','zombie2'):
            c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2'];c['globals']['模式']=mode
            c['operations']=[dict(op='service_gift',target=seat,center=[240.,400.]),dict(op='service_armor',target=seat)]
            cases.append(('service-gift-mode-%d-%s'%(i,seat),c))
    for i in range(32):
        c=base();c['services']['units'][0].update(植物僵尸名='吸金磁僵尸',魅惑=None,**{P+'gold_magnet_zombie_cd':0.})
        c['services']['units'][1].update(防具='铁桶',防具血量=100.)
        body=[dict(op='effect_roster_replace',births=[]),dict(op='roster_replace',targets=[3]),write(1,防具='路障',防具血量=7.)]
        if i%4==1:body=[write(0,位置=[1000.,432.,0.,0.]),dict(op='source_observe')]
        if i%4==2:body=[dict(op='source_observe'),dict(op='effect_roster_replace',births=[0])]
        c['operations']=[dict(op='lifecycle_hook',name='add',body=body,fail_before=i>=24,fail_after=16<=i<24),
            dict(op='service_magnet',unit=0),dict(op='service_attract',name='矿镐',start=[240.,400.],end=[(240.,200.)[i%2],500.])]
        cases.append(('service-magnet-callback-'+str(i),c))
    for i,owner in enumerate((None,'invalid','plant','zombie','plant2','zombie2')):
        for cd in (None,0.,25.,100.):
            c=base();c['units'][0]['source']['_pvp_owner']=owner
            c['services']['units'][0].update(_pvp_umbrella_secret=True,**{P+'umbrella_zombie_cd':cd})
            c['operations']=[dict(op='service_umbrella',unit=0,catch=True),dict(op='service_umbrella',unit=0,catch=True)]
            cases.append(('service-wrapper-order-%d-%s'%(i,cd),c))
    for i in range(16):
        c=base();c['services']['units'][0].update(植物僵尸名='吸金磁僵尸',魅惑=None,**{P+'gold_magnet_zombie_cd':0.})
        c['units'][0]['source']['_pvp_owner']=('plant','zombie','plant2','zombie2')[i%4]
        c['services']['units'][1].update(防具='铁桶',防具血量=100.)
        body=[dict(op='source_observe'),dict(op='service_unit',unit=0,values={P+'gold_magnet_zombie_cd':0.}),
            dict(op='service_magnet',unit=0,config={'cooldown':2.}),dict(op='source_observe')]
        c['services']['units'][2].update(手持='钢门',手持血量=100.)
        c['operations']=[dict(op='lifecycle_hook',name='add',body=body,fail_after=i>=8),dict(op='service_magnet',unit=0)]
        cases.append(('service-nested-source-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[PVP70,exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('service_probe.cpp','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:ServiceExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-service-plants',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining sourced hooks','whole native driver','complete custom content scheduler','full battle','AI/network/replay','invalid unadmitted record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
