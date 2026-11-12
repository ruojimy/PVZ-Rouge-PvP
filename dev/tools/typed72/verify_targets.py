"""Current NativeTargets + protection + original damage, with raw patch boundary explicit.

This verifies target dispatch, packet identity, ash selection, hero routing,
armor notification order and roster identity. The full 1.5.0.1 raw patch/death
chain is a required subsequent implementation, not replaced by this fixture.
"""
import argparse
import copy
import json
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import verify_protection as protection
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT


class TargetExtension:
    def __init__(self,ctx,case,policy_reference):
        self.ctx=ctx;self.case=case;self.c=ctx.controller;self.b=ctx.battle;self.g=ctx.globals
        self.units=[];self.raw_calls=[];self.armor_events=[];self.unit_events=[];self.ordered_events=[];self.unit_sounds=[];self.throw_raw=False;self.throw_watch=False
        cfg=case.get('damage',{})
        for item in case['units']:
            unit=copy.deepcopy(item['body']);unit.update(copy.deepcopy(item.get('source',{})));unit.update(copy.deepcopy(item.get('state',{})))
            if 'armor_max' in item:unit['_pvp_armor_max']=item['armor_max']
            if 'hand_max' in item:unit['_pvp_zs_hand_max']=item['hand_max']
            self.units.append(unit)
        self.alive=set(range(len(self.units)));self.original_roster=list(self.units);self.g['僵尸']=self.original_roster
        self.original_roster.extend(ctx.get_proxy(s) for s in cfg.get('hero_targets',[]))
        self.g['实体']=[];self.g['boss']=cfg.get('bosses',[])
        self.c.originals['新增实体']=types.FunctionType(ctx.functions['新增实体'],self.g)
        self.g['新增实体']=self.c._new_entity
        raw={name:types.FunctionType(ctx.functions[name],self.g) for name in ('伤害僵尸','表面伤害僵尸','灰烬僵尸')}
        def ordinary(index,facing,amount):
            self.raw_calls.append(['ordinary',self.unit_index(self.g['僵尸'][index]),facing,amount])
            result=raw['伤害僵尸'](index,facing,amount)
            if self.throw_raw:raise RuntimeError('injected raw callback failure')
            return result
        def surface(index,facing,amount):
            self.raw_calls.append(['surface',self.unit_index(self.g['僵尸'][index]),facing,amount])
            result=raw['表面伤害僵尸'](index,facing,amount)
            if self.throw_raw:raise RuntimeError('injected raw callback failure')
            return result
        def ash(index):
            self.raw_calls.append(['ash',self.unit_index(self.g['僵尸'][index])]);result=raw['灰烬僵尸'](index)
            if self.throw_raw:raise RuntimeError('injected raw callback failure')
            return result
        def armor(unit,slot,kind,maximum):
            self.armor_events.append([self.unit_index(unit),slot,kind,maximum])
            if self.throw_watch:raise RuntimeError('injected armor callback failure')
        self.c.originals.update(伤害僵尸=ordinary,表面伤害僵尸=surface,灰烬僵尸=ash)
        self.g.update(伤害僵尸=self.c._zombie_damage,表面伤害僵尸=self.c._surface_damage,灰烬僵尸=self.c._ash_damage)
        self.c._damage_packets=set();self.c.armor_break=armor if cfg.get('watch_armor',False) else None
        env,Secrets,Policy=policy_reference;z=ctx.secrets
        for name,value in Secrets.__dict__.items():
            if callable(value):setattr(z,name,types.MethodType(value,z))
        z.team=set().union(*z.by_seat.values());z.enabled=bool(z.team)
        self.b.deathmatch=cfg.get('deathmatch',False)
        for seat,uid in cfg.get('selected',{}).items():self.b.players[seat]['selected_grave']=uid
        env['CARDS']={k:dict(producer=v) for k,v in cfg.get('cards',{}).items()}
        # NativeTargets references the actual primal constants in its globals.
        self.c._ash_damage.__func__.__globals__['PRIMAL_MINE']=hero.constant(hero.CATALOG,'PRIMAL_MINE')
        self.c._ash_damage.__func__.__globals__['PRIMAL_ASH_DAMAGE']=hero.constant(hero.CATALOG,'PRIMAL_ASH_DAMAGE')
        p=Policy();p.b=self.b;p.until=cfg.get('until',0);p.factor=cfg.get('factor',1.)
        if cfg.get('adjust',True):self.g['_pvp_damage_amount']=p.amount
        self.c.unshielded=z.shield_first if cfg.get('shield_first',False) else None
        emit=self.b._emit
        def routed_emit(event_type,**data):
            self.ordered_events.append(dict(type=event_type,**data))
            if event_type=='zsecret_relic':self.unit_events.append(dict(type=event_type,**data))
            elif event_type not in ('zombie_basket_hit','melon_splash'):emit(event_type,**data)
        self.b._emit=routed_emit
        def immersive(name,pos):ctx.sounds.append(name);self.unit_sounds.append([name,list(pos)])
        def sound(name):ctx.sounds.append(name);self.unit_sounds.append([name,[0.,0.]])
        self.g['沉浸播音']=immersive;self.g['播音']=sound

    def source(self,index):return self.units[index]
    def unit_index(self,target):return next(i for i,u in enumerate(self.units) if u is target)
    def target(self,label):return self.ctx.get_proxy(label) if isinstance(label,str) else self.units[label]
    def label(self,target):
        if isinstance(target,hero_proxy_type(self.c)):return target.side
        return self.unit_index(target)
    def operation(self,op):
        action=op['op'];result=None
        if action=='unit_hit':
            target=self.target(op['target']);index=next(i for i,t in enumerate(self.g['僵尸']) if t is target)
            self.throw_raw=op.get('throw_raw',False);self.throw_watch=op.get('throw_watch',False)
            try:
                kind=op['kind']
                if kind=='ash':result=self.c._ash_damage(index)
                elif kind=='surface':result=self.c._surface_damage(index,op.get('facing',1.),op['amount'])
                elif kind=='ordinary':result=self.c._zombie_damage(index,op.get('facing',1.),op['amount'])
                else:raise ValueError(kind)
            except RuntimeError:
                if not op.get('catch',False):raise
                result={'caught':True}
            finally:self.throw_raw=False;self.throw_watch=False
        elif action=='expose':
            extras=[self.target(t) for t in op['extras']];old=self.g.get('_pvp_target_extras')
            self.g['_pvp_target_extras']=(lambda:extras) if op.get('provider',True) else None
            try:
                with self.c.full_targets():self.operations(op['body'])
            finally:self.g['_pvp_target_extras']=old
        elif action=='roster_replace':self.g['僵尸']=[self.target(t) for t in op['targets']]
        elif action=='roster_append':self.g['僵尸'].append(self.target(op['target']))
        elif action=='remove_unit':
            index=op['unit'];result=index in self.alive
            if result:
                self.alive.remove(index);self.g['僵尸'][:]=[t for t in self.g['僵尸'] if t is not self.units[index]]
        else:raise ValueError(action)
        return result
    def snapshot(self,row):
        row['battle_units']=[]
        for u in self.units:
            keep={k:u[k] for k in ('僵尸','防具','手持','血量','防具血量','手持血量','方向','位置','受伤','手持受伤','灰烬','气球',
                                  '_pvp_id','_pvp_owner','魅惑','_pvp_zs_hurt','_pvp_zs_relic_until','_pvp_reaper_hurt','_pvp_zs_locked') if k in u}
            if '_pvp_chili_ash_hits' in u:keep['chili_hit_count']=len(u['_pvp_chili_ash_hits'])
            row['battle_units'].append(keep)
        entities=copy.deepcopy(self.g['实体'])
        for entity in entities:
            if '_pvp_instant_attack' in entity:entity['_pvp_instant_attack_text']=str(entity.pop('_pvp_instant_attack'))
        row.update(packets=[id(u) in self.c._damage_packets for u in self.units],roster=[self.label(t) for t in self.g['僵尸']],
            original_roster_identity=self.g['僵尸'] is self.original_roster,raw_calls=self.raw_calls,armor_events=self.armor_events,
            entities=entities,unit_events=self.unit_events,unit_sounds=self.unit_sounds,ordered_events=self.ordered_events)


def hero_proxy_type(controller):return controller._proxy.__func__.__globals__['HeroProxy']


def make_cases():
    rng=random.Random(72138);cases=[]
    def unit(kind='普通僵尸',hp=200.,armor='',armor_hp=0.,hand='',hand_hp=0.):
        return dict(body={'僵尸':kind,'防具':armor,'手持':hand,'血量':hp,'防具血量':armor_hp,'手持血量':hand_hp,
                          '方向':1.,'位置':[240.,400.,0.,0.],'受伤':0.,'手持受伤':0.},source={'_pvp_owner':'zombie'})
    for i in range(144):
        c=hero.base();c['tagging']=True;c['sources']=[{'名':('星星','西瓜','火豆','豌豆')[i%4]}]
        c['units']=[unit(hp=100.,armor=('','路障','铁桶')[i%3],armor_hp=(0.,10.,50.)[i%3],
                        hand=('','钢门','气球','报纸','梯子','玩偶匣')[i%6],hand_hp=(0.,10.,25.)[i%3])]
        c['units'][0]['state']={'_pvp_card':'producer','_pvp_zs_crowd_factor':(.25,1.,0.)[i%3]}
        c['units'][0]['armor_max']=(None,0.,100.)[i%3];c['units'][0]['hand_max']=(None,0.,200.)[(i//3)%3]
        c['players']['zombie']['secrets']=['zsecret:'+s for bit,s in enumerate(('狂暴','专注啃咬','阿姆斯特朗','坤坤')) if i&(1<<bit)]
        c['damage']=dict(adjust=i%5!=0,watch_armor=bool(i%2),shield_first=bool(i%3),until=2500,factor=.25,cards={'producer':True},deathmatch=True,hero_targets=['plant','zombie'])
        ops=[]
        for n in range(10):
            ops.append(dict(op='clock',tick=(0,1249,1250,2500,5000)[n%5],time=n*.004))
            ops.append(dict(op='unit_hit',target=0,kind='surface' if n%2 else 'ordinary',facing=-1.,amount=(.25,1.,10.,30.,80.)[n%5]))
        ops += [dict(op='unit_hit',target='zombie',kind='surface',amount=3.),dict(op='unit_hit',target='plant',kind='ordinary',amount=3.)]
        c['operations']=[hero.context(ops,source=0)]
        cases.append(('damage-packets-%d'%i,c))
    sources=[{}, {'植物':'火爆辣椒'}, {'僵尸':'辣椒僵尸'}, {'名':'火'}, {'_pvp_content':'原始土豆地雷'}, {'名':'星星'}]
    for i in range(96):
        c=hero.base();c['tagging']=True;c['sources']=[copy.deepcopy(sources[i%len(sources)])]
        if i%3==0:c['sources'][0]['_pvp_instant_attack']=None
        elif i%3==1:c['sources'][0]['_pvp_instant_attack']=['blast',7]
        c['units']=[unit('巨人僵尸' if i%2 else '普通僵尸',(10.,300.,501.,750.,1000.,2000.)[i%6],armor='铁桶',armor_hp=50.,hand='钢门',hand_hp=100.)]
        c['units'][0]['state']={'_pvp_card':'producer','_pvp_grave':i%7==0}
        if i%11==0:c['units'][0]['body']['灰烬']=0.
        c['damage']=dict(adjust=True,watch_armor=True,shield_first=i%2==0,until=2500,factor=(0.,.25,1.)[i%3],cards={'producer':True},bosses=['巨人僵尸'],hero_targets=['zombie'])
        c['players']['zombie']['secrets']=['zsecret:专注啃咬']+(['zsecret:遗骸','zsecret:解除封印'] if i%4==0 else [])
        c['operations']=[hero.context([dict(op='unit_hit',target=0,kind='ash'),dict(op='unit_hit',target=0,kind='ash'),
            dict(op='clock',tick=1250,time=5.),dict(op='unit_hit',target=0,kind='ash'),
            dict(op='unit_hit',target='zombie',kind='ash')],source=0)]
        cases.append(('ash-packets-%d'%i,c))
    for throw_raw,throw_watch in ((True,False),(False,True),(True,True)):
        c=hero.base();c['tagging']=True;c['sources']=[{'名':'火豆'}];c['units']=[unit(armor='路障',armor_hp=5.,hand='钢门',hand_hp=5.)]
        c['damage']=dict(watch_armor=True)
        c['operations']=[hero.context([dict(op='unit_hit',target=0,kind='surface',amount=10.,throw_raw=throw_raw,throw_watch=throw_watch,catch=True),
            dict(op='unit_hit',target=0,kind='ordinary',amount=10.,throw_raw=throw_raw,throw_watch=throw_watch,catch=True),
            dict(op='unit_hit',target=0,kind='ordinary',amount=5.)],source=0)]
        cases.append(('exception-cleanup-%s-%s'%(throw_raw,throw_watch),c))
    for provider in (False,True):
        c=hero.base();c['sources']=[{}];c['units']=[unit() for _ in range(4)];c['damage']=dict(hero_targets=['zombie'])
        c['operations']=[dict(op='roster_replace',targets=[0,1]),dict(op='expose',provider=provider,extras=[1,2,2,'zombie'],body=[
            dict(op='roster_replace',targets=[2,3,0,'zombie']),dict(op='remove_unit',unit=0),
            dict(op='expose',extras=[1,3,'plant'],body=[dict(op='roster_append',target=2)]),dict(op='roster_append',target=1)]),
            dict(op='remove_unit',unit=0)]
        cases.append(('target-roster-'+str(provider),c))
    c=hero.base();c['tagging']=True;c['sources']=[];c['units']=[unit('墓碑吞噬者僵尸'),unit()]
    c['units'][0]['source']={'_pvp_owner':'zombie','魅惑':None};c['damage']=dict(hero_targets=['plant','zombie'])
    c['operations']=[dict(op='context',target='zombie',owner='plant',phase='zombies',unit_source=0,body=[
        dict(op='player_damage',amount=1.),dict(op='unit_hit',target=1,kind='ordinary',amount=10.)])]
    cases.append(('authoritative-unit-source',c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(args.exe).resolve()
    paths=[exe,Path(__file__).resolve(),ROOT/'tools/typed72/hero_probe.cpp',ROOT/'tools/typed72/targets_probe.cpp',
           ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_protection.py',ROOT/'tools/typed72/verify_stages.py',
           hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,
           protection.PROTECTION,protection.TEAMS,ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths}
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=protection.reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:TargetExtension(ctx,c,pref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n')
                row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%32==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-target-dispatch',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,excluded=['1.5.0.1 raw damage/death patch bodies','full world tick','production constructor chain','full multiplayer/replay'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
