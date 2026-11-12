"""Actual installed plant-zombie targeting, catalog and sourced update oracle."""
import argparse
import ast
import copy
import functools
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import verify_plants as plants
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT;P='__pvz_sb_';NATIVE_PATCH=hero.REF/'modkit/pvp/native_patch.py'


def binding_code():
    tree=ast.parse(NATIVE_PATCH.read_text(encoding='utf8'),str(NATIVE_PATCH))
    outer=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='bind_targets')
    functions=[n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='bind']
    assert len(functions)==1
    return compile(ast.Module(body=functions,type_ignores=[]),str(NATIVE_PATCH),'exec')


class AimExtension(plants.PlantExtension):
    def __init__(self,ctx,case,pref,reference,binder):
        super().__init__(ctx,case,pref,reference);self.aim_ns=ctx.constructor_patch.ns;self.held_aims=[]
        for u,fields in zip(self.units,case['aim']['units']):u.update(copy.deepcopy(fields))
        self.raw_update=self.aim_ns[P+'update_plant_zombie_target']
        patch=ctx.constructor_patch;patch._target_originals={}
        env=dict(PREFIX=P,targets=self.c,self=patch,ns=self.aim_ns,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
            fast=False,telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(binder,env);env['bind']('update_plant_zombie_target',1,'zombie','zombies')

    def describe(self,target):
        if target is None:return None
        kind,index,obj,point,direction,angle=target
        label={'plant':next(i for i,p in enumerate(self.all_plants) if p is obj)} if kind=='plant' else self.label(obj) if kind=='zombie' else None
        return [kind,index,label,list(point),direction,angle]

    def operation(self,op):
        action=op['op'];ns=self.aim_ns
        if action=='aim_catalog':return copy.deepcopy(ns[P+'PLANT_ZOMBIE_CONFIG'])
        if action=='aim_write':
            u=self.units[op['unit']];u.update(copy.deepcopy(op.get('values',{})))
            for k in op.get('erase',[]):u.pop(k,None)
            return None
        if action=='aim_plant':self.all_plants[op['plant']].update(copy.deepcopy(op['values']));return None
        if action=='aim_head':return list(ns[P+'plant_zombie_head_center'](self.g,self.units[op['unit']]))
        if action=='aim_sync':return list(ns[P+'sync_plant_zombie_head_angle'](self.units[op['unit']]))
        if action in ('aim_pick','aim_update'):
            if action=='aim_pick':target=ns[P+'pick_plant_zombie_target'](self.g,self.units[op['unit']]);result=self.describe(target)
            else:
                fn=ns[P+'update_plant_zombie_target'] if op.get('sourced',True) else self.raw_update
                target,center=fn(self.g,self.units[op['unit']]);result=[self.describe(target),list(center) if center is not None else None]
            if op.get('hold'):self.held_aims.append(target)
            return result
        if action=='aim_point':
            point=ns[P+'plant_zombie_target_point'](self.g,self.held_aims[op['held']],op['center'])
            return list(point) if point is not None else None
        if action=='aim_cone':
            a,d=op['angle'],op['direction'];kwargs={'limit':op['limit']} if 'limit' in op else {}
            return [ns[P+'direction_angle'](d),ns[P+'direction_angle_diff'](a,d),ns[P+'angle_in_direction'](a,d,**kwargs)]
        return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row);row['aim_fields']=[{k:u[k] for k in ('大小','植物僵尸角','死') if k in u} for u in self.units]
        row['held_aims']=[self.describe(t) for t in self.held_aims]


def base():
    c=plants.base();c['units']=[plants.unit(120.,240.),plants.unit(260.,240.),plants.unit(260.,240.),plants.unit(60.,240.)]
    for u in c['units']:u['body']['血量']=100.
    c['aim']={'units':[{'植物僵尸':True,'植物僵尸名':'豌豆僵尸','大小':2.},{'魅惑':None,'大小':2.},{'大小':2.},{'大小':2.}]}
    return c


def make_cases():
    cases=[];c=base();c['operations']=[dict(op='aim_catalog')];cases.append(('aim-catalog',c))
    kinds=('豌豆僵尸','机枪僵尸','坚果僵尸','高坚果僵尸','辣椒僵尸','毁灭菇僵尸','三叶草僵尸','路灯花僵尸','倭瓜僵尸','墓碑吞噬者僵尸','萝卜伞僵尸','吸金磁僵尸','大喷菇僵尸','未知')
    for ki,kind in enumerate(kinds):
        for duck in (False,True):
            for animation in (0.,6.,80.):
                for facing in (-1.,0.,1.):
                    c=base();c['units'][0]['body']['方向']=facing;c['aim']['units'][0].update(植物僵尸名=kind,植物僵尸鸭子=duck,植物僵尸发射动画=animation)
                    if ki%2:c['aim']['units'][0]['魅惑']=None
                    if ki%3==0:c['damage']['hero_targets']=['zombie'];c['heroes']['zombie']['玩家位置']=[300.,240.,0.,0.]
                    c['operations']=[dict(op='plant_original',cell=[3,4],name='向日葵'),dict(op='plant_original',cell=[2,1],name='坚果'),
                        dict(op='aim_head',unit=0),dict(op='aim_pick',unit=0,hold=True),dict(op='aim_update',unit=0),dict(op='aim_sync',unit=0),
                        dict(op='aim_point',held=0,center=[120.,80.])]
                    cases.append(('aim-geometry-%s-%s-%s-%s'%(kind,duck,animation,facing),c))
    for charmed in (False,True):
        for marker in ('none','dead','ash','zero','negative'):
            for owner in ('plant','zombie','plant2','zombie2'):
                c=base();c['aim']['units'][0]['植物僵尸名']='未知';c['units'][0]['source']['_pvp_owner']=owner
                c['aim']['units'][1].pop('魅惑',None)
                if charmed:c['aim']['units'][0]['魅惑']=0
                else:
                    c['aim']['units'][1]['魅惑']=None;c['aim']['units'][2]['魅惑']=0
                if marker=='dead':c['aim']['units'][1]['死']=False
                if marker=='ash':c['aim']['units'][1]['灰烬']=None
                if marker in ('zero','negative'):c['units'][1]['body']['血量']=0. if marker=='zero' else -1.
                c['operations']=[dict(op='aim_pick',unit=0,hold=True),dict(op='aim_update',unit=0),dict(op='roster_replace',targets=[0,3]),
                    dict(op='aim_write',unit=1,values={'位置':[480.,288.,0.,0.]}),dict(op='aim_point',held=0,center=[100.,200.]),
                    dict(op='aim_write',unit=2,values={'位置':[400.,300.,0.,0.]}),dict(op='aim_point',held=0,center=[100.,200.])]
                cases.append(('aim-tie-retain-%s-%s-%s'%(charmed,marker,owner),c))
    for marker in ('none','dead','shovel','hpzero','hpnull'):
        c=base();c['aim']['units'][1].pop('魅惑');c['units'][1]['body']['血量']=0.;c['operations']=[dict(op='plant_original',cell=[3,4],name='向日葵'),dict(op='plant_original',cell=[3,4],name='豌豆射手')]
        if marker!='none':c['operations'].append(dict(op='aim_plant',plant=0,values={'死':None} if marker=='dead' else {'铲死':False} if marker=='shovel' else {'植物血':None if marker=='hpnull' else 0.}))
        c['operations'] += [dict(op='aim_pick',unit=0,hold=True),dict(op='plant_roster_replace',plants=[]),dict(op='aim_plant',plant=0,values={'坐标':[1,6]}),dict(op='aim_point',held=0,center=[120.,240.]),
            dict(op='aim_update',unit=0),dict(op='write',target='globals',erase=['玩家位置']),dict(op='aim_pick',unit=0)]
        cases.append(('aim-plant-retain-'+marker,c))
    for direction in (-1.,0.,1.):
        for angle in (-720.,-270.,-180.,-90.00000001,-90.,-89.99999999,0.,89.99999999,90.,90.00000001,180.,270.,360.,720.):
            c=base();c['units'][0]['body']['方向']=direction;c['aim']['units'][0]['植物僵尸角']=angle
            c['operations']=[dict(op='aim_cone',angle=angle,direction=direction),dict(op='aim_cone',angle=angle,direction=direction,limit=None),dict(op='aim_sync',unit=0),
                dict(op='aim_write',unit=0,values={'植物僵尸角':None}),dict(op='aim_sync',unit=0),dict(op='aim_write',unit=0,erase=['植物僵尸角']),dict(op='aim_sync',unit=0)]
            cases.append(('aim-cone-%s-%s'%(direction,angle),c))
    for side in ('plant','zombie','plant2','zombie2'):
        for health in (0.,40.):
            c=base();c['aim']['units']=[c['aim']['units'][0]];c['units']=[c['units'][0]];c['units'][0]['source']['_pvp_owner']=side
            for h in c['heroes'].values():h['玩家血量']=health;h['玩家位置']=[400.,240.,0.,0.]
            c['operations']=[dict(op='aim_update',unit=0,hold=True),dict(op='write',target='globals',values={'玩家位置':[800.,400.,0.,0.]}),dict(op='aim_point',held=0,center=[0.,0.])]
            cases.append(('aim-player-fallback-%s-%s'%(side,health),c))
    for mode in ('正常模式','我是僵尸','极难模式',None):
        for nohero in (False,True):
            c=base();c['aim']['units']=[c['aim']['units'][0]];c['units']=[c['units'][0]]
            c['units'][0]['source']['_pvp_no_hero_attack']=nohero;c['globals']['模式']=mode;c['globals']['玩家位置']=[400.,240.,0.,0.]
            c['heroes']['plant']['玩家位置']=[600.,240.,0.,0.]
            c['operations']=[dict(op='aim_pick',unit=0),dict(op='aim_update',unit=0,sourced=False),dict(op='aim_update',unit=0),dict(op='aim_pick',unit=0)]
            cases.append(('aim-legacy-mode-%s-%s'%(mode,nohero),c))
    for kind in ('豌豆僵尸','大喷菇僵尸','未知'):
        for flag in ('missing',None,False):
            c=base();c['aim']['units'][0]['植物僵尸名']=kind
            if flag=='missing':c['aim']['units'][0].pop('植物僵尸')
            else:c['aim']['units'][0]['植物僵尸']=flag
            c['operations']=[dict(op='aim_head',unit=0),dict(op='aim_update',unit=0),dict(op='aim_head',unit=0)]
            cases.append(('aim-ungated-head-%s-%s'%(kind,flag),c))
    for dead in (False,True):
        for facing in (-1.,1.):
            c=base();c['globals']['模式']='正常模式';c['globals']['玩家位置']=[120.+facing*10.,223.2,0.,0.]
            c['units'][0]['body']['方向']=facing;c['aim']['units'][0]['植物僵尸名']='未知'
            col=1 if facing<0 else 4;c['aim']['units'][1]['位置']=[col*48.+24.,237.6,0.,0.]
            c['operations']=[dict(op='plant_original',cell=[3,col],name='向日葵')]
            if dead:c['operations'].append(dict(op='aim_plant',plant=0,values={'死':False}))
            c['operations'] += [dict(op='aim_pick',unit=0,hold=True),dict(op='roster_replace',targets=[0]),dict(op='plant_roster_replace',plants=[]),
                dict(op='aim_write',unit=1,values={'位置':[900.,300.,0.,0.]}),dict(op='aim_plant',plant=0,values={'坐标':[6,6]}),dict(op='aim_point',held=0,center=[100.,200.])]
            cases.append(('aim-priority-%s-%s'%(dead,facing),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),NATIVE_PATCH,plants.TABLES,plants.FUNCTIONS,hero.RAW,hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,
        plants.protection.PROTECTION,plants.protection.TEAMS,plants.projectiles.CONTENT,plants.projectiles.SIMULATION,plants.projectiles.FLYING,plants.projectiles.SCALE,plants.projectiles.CATALOG61,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']+hero.PROXY_REFERENCE_PATHS
    paths += [ROOT/'tools/typed72'/n for n in ('aim_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    cases=make_cases();ref=hero.load_reference();pref=plants.protection.reference();plant_ref=plants.load_terrain_reference();binder=binding_code()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:AimExtension(ctx,c,pref,plant_ref,binder));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%32==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-plant-zombie-aim',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['malformed unadmitted entity records','remaining twelve sourced hooks and shooting scheduler','complete main loop','AI/network/replay','full product verification'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
