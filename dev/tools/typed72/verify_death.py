"""Actual raw damage patches, sourced wrappers and synchronous death bodies.

The reference executes original bytecode and literal current patch AST.
This remains a chain-level proof; the complete native driver is not present.
"""
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
import verify_sourced as sourced
import evidence_store
import evidence_archive
chili=sourced.chili;doom=chili.doom;plants=chili.plants;projectiles=chili.projectiles;hero=chili.hero;patch=chili.patch;ROOT=chili.ROOT;P=chili.P
sha=chili.sha;difference=chili.difference


def reference():
    env=sourced.reference();unused,code=patch.patch_reference();env['damage_patch_code']=code
    projectiles.functions(patch.PATCH,[P+'update_doom_zombie_auto_explode'],env);return env


class DeathExtension(sourced.SourcedExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        for n,fn in self.raw_chili.items():self.env[P+n]=fn
        empty=types.SimpleNamespace(f_code=types.SimpleNamespace(co_name='callback'),f_lasti=-1,f_locals={},f_globals={})
        self.env[P+'sys']=types.SimpleNamespace(_getframe=lambda depth:empty)
        exec(self.env['damage_patch_code'],self.env)
        for key in patch.COUNTERS.values():self.env[P+key]=0
        for key in ('damage','surface_damage','ash','knockback'):self.env[P+key+'_wrap_done']=False
        for name in ('伤害僵尸','表面伤害僵尸','灰烬僵尸','击退僵尸'):self.g[name]=types.FunctionType(ctx.functions[name],self.g)
        for name in ('damage_zombie','surface_damage_zombie','ash_zombie','knockback_zombie'):self.env[P+'wrap_'+name](self.g)
        self.c.originals.update({n:self.g[n] for n in ('伤害僵尸','表面伤害僵尸','灰烬僵尸')})
        self.g.update(伤害僵尸=self.c._zombie_damage,表面伤害僵尸=self.c._surface_damage,灰烬僵尸=self.c._ash_damage)
        obj=types.SimpleNamespace(ns=self.env,g=self.g,_target_originals={})
        env=dict(PREFIX=P,targets=self.c,self=obj,ns=self.env,fast=case.get('death_config',{}).get('fast',True),
            telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
        exec(self.env['fast_config_code'],env)
        exec(self.env['bind_code'],env)
        for name in ('update_chili_zombie_row_hint','spawn_chili_zombie_fire_row','spawn_doom_zombie_explosion',
            'update_doom_zombie_auto_explode','maybe_trigger_plant_zombie_death_effects'):
            env['bind'](name,1,'zombie','zombies')
        for name in ('chili_zombie_enemy_fire_scan','chili_fire_player_hit','chili_fire_hit_zombies'):
            env['bind'](name,1,'entity','entities')

    def operation(self,op):
        action=op['op'];result=None
        if action=='native_write_unit':self.units[op['unit']].update(copy.deepcopy(op['values']))
        elif action.startswith('native_'):
            try:
                s=op.get('scale',self.g['比']);e=self.births[op['entity']] if 'entity' in op else None
                args=([self.g,e]+op['box']+[s]) if 'box' in op else []
                if action=='native_deaths':result=self.env[P+'maybe_trigger_plant_zombie_death_effects'](self.g,op['index'] if 'index' in op else self.units[op['unit']])
                elif action=='native_auto':result=self.env[P+'update_doom_zombie_auto_explode'](self.g,self.units[op['unit']],op.get('now'))
                elif action=='native_spawn_chili':result=self.env[P+'spawn_chili_zombie_fire_row'](self.g,self.units[op['unit']],op.get('friendly',False))
                elif action=='native_doom':result=self.env[P+'spawn_doom_zombie_explosion'](self.g,self.units[op['unit']])
                elif action=='native_scan':result=self.env[P+'chili_fire_scan'](self.g)
                elif action in ('native_hint','native_hint_cached'):
                    target=self.c.proxies[op['target']] if action=='native_hint_cached' else self.target(op['target'])
                    result=self.env[P+'update_chili_zombie_row_hint'](self.g,target,op.get('force',False))
                elif action=='native_player_hit':result=self.env[P+'chili_fire_player_hit'](*args)
                elif action=='native_enemy':result=self.env[P+'chili_zombie_enemy_fire_scan'](*args)
                elif action=='native_hit_units':result=self.env[P+'chili_fire_hit_zombies'](*args,charmed_only=op.get('charmed_only',False),target_rows=None if op.get('rows') is None else set(op['rows']))
                elif action in ('native_hit','native_hit_slot'):
                    if action=='native_hit_slot':index=op['index']
                    else:
                        t=self.target(op['target']);index=next(i for i,v in enumerate(self.g['僵尸']) if v is t)
                    if op['kind']=='ash':result=self.c._ash_damage(index)
                    elif op['kind']=='ordinary':result=self.c._zombie_damage(index,op.get('facing',1.),op['amount'])
                    elif op['kind']=='surface':result=self.c._surface_damage(index,op.get('facing',1.),op['amount'])
                    else:raise ValueError('unknown native damage')
                else:raise ValueError(action)
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row)
        names=('chili_zombie_exploded','doom_zombie_exploded','gravebuster_zombie_done','doom_zombie_life_ticks','doom_zombie_life_time','zombie_observed_max_hp','plant_zombie_max_hp')
        row['death_units']=[{P+k:u[P+k] for k in names if P+k in u} for u in self.units]
        row['patch_counters']={key:self.env[P+value] for key,value in patch.COUNTERS.items()}


def base():
    c=chili.base();c['units'][0]['body']['位置']=[240.,432.,0.,0.];c['units'][0]['body']['血量']=1.
    c['sources']=[{'名':'豌豆','_pvp_owner':'plant'}]
    for h in c['heroes'].values():h['玩家位置']=[240.,432.,0.,0.]
    return c


def set_unit(i,**fields):return dict(op='native_write_unit',unit=i,values=fields)


def make_cases():
    cases=[]
    for i in range(72):
        c=base();c['seed']=12000+i;kind=('辣椒僵尸','毁灭菇僵尸','墓碑吞噬者僵尸')[i%3]
        if i%2:c['units'][0]['source']['魅惑']=None if i%4==1 else 0.
        for n in range(3):
            u=projectiles.unit(220.+n*30.,432.,owner='plant' if n%2 else 'zombie');u['body']['血量']=(100.,800.,500.)[n]
            if n%2:u['source']['魅惑']=0.
            c['units'].append(u)
        c['doom_world']['extras']=['plant','zombie','plant2','zombie2']
        body=[set_unit(0,植物僵尸名=kind,植物僵尸=True),dict(op='plant_original',cell=[9,4],name='向日葵'),dict(op='plant_original',cell=[9,5],name='南瓜头')]
        if i%6==0:body.append(dict(op='lifecycle_hook',name='add',fail_before=i%12==0,fail_after=i%12!=0))
        if i%6==1:body.append(dict(op='lifecycle_hook',name='clear',fail_after=True))
        body += [dict(op='native_hit',target=0,kind=('ordinary','surface','ash')[i//3%3],amount=2.),dict(op='native_deaths',unit=0),dict(op='native_scan')]
        c['operations']=[chili.scope(body,source=0)];cases.append(('death-composed-'+str(i),c))
    for i in range(72):
        c=base();c['units'][0]['body']['血量']=100.;age=(0.,9499.,9500.,9501.,None,-2.)[i%6];last=(None,0.,10.)[i//6%3]
        values={'植物僵尸名':'毁灭菇僵尸',P+'doom_zombie_life_ticks':age,P+'doom_zombie_life_time':last}
        if i%2:c['units'][0]['source']['魅惑']=0.
        if i>=54:
            key=('死','灰烬',P+'doom_zombie_exploded')[i%3];values[key]=None if i%2 else 0. if key=='灰烬' else True
        c['operations']=[dict(op='native_write_unit',unit=0,values=values),dict(op='fire_globals',time=10.),
            dict(op='native_auto',unit=0,now=(0.,.004,10.,10.0000001,-.1,None)[i%6]),dict(op='native_auto',unit=0,now=10.004),dict(op='native_auto',unit=0,now=20.004)]
        cases.append(('death-auto-timer-'+str(i),c))
    for i in range(32):
        c=base();c['units'][0]['body']['血量']=0.;c['units'].append(projectiles.unit(240.,432.,owner='plant'));c['units'][1]['body']['血量']=0.
        c['units'][1]['source']['魅惑']=0.
        body=[set_unit(0,植物僵尸名='辣椒僵尸'),set_unit(1,植物僵尸名='毁灭菇僵尸' if i%2 else '墓碑吞噬者僵尸'),
            dict(op='lifecycle_hook',name='add',body=[dict(op='roster_replace',targets=[1]),dict(op='effect_roster_replace',births=[])]),
            dict(op='native_deaths',catch=True,**({'index':0} if i%4<2 else {'unit':0})),dict(op='native_deaths',index=-1,catch=True)]
        c['operations']=[chili.scope(body,source=0)] if i%8<4 else body
        cases.append(('death-live-selector-'+str(i),c))
    for i in range(32):
        c=base();c['damage']['hero_targets']=['plant','zombie','plant2','zombie2']
        v={P+'chili_zombie_fire':True,P+'chili_fire_damage_mode':'enemy',P+'chili_fire_no_hero':i%2==0}
        source={'_pvp_owner':('plant','zombie','plant2','zombie2')[i%4]}
        if i%6==0:source['魅惑']=None
        if i%7==0:source['_pvp_instant_attack']=None
        if i%5==0:v[chili.EXP]='launch-tail'
        c['operations']=[chili.fire(v,source=source,pos=(240.,432.,0.,0.)),dict(op='native_hint',target='plant',force=True),
            dict(op='native_enemy',entity=0,box=[200.,280.,350.,480.]),dict(op='native_enemy',entity=0,box=[200.,280.,350.,480.]),dict(op='native_scan')]
        cases.append(('death-owner-launch-'+str(i),c))
    for i in range(24):
        c=base();c['damage']['hero_targets']=['plant','zombie'];c['units'][0]['body']['血量']=100.
        body=[dict(op='tile_replace',cell=[4,2],value={'方块':'石'}),
            dict(op='write',target='globals',values={'玩家位置':[120.,192.,0.,0.]}),dict(op='native_hint_cached',target='zombie',force=True),
            dict(op='native_deaths',unit=0),dict(op='native_auto',unit=0)]
        if i%3==0:body.insert(0,dict(op='write',target='zombie',erase=['玩家恢复','玩家受伤','辣飞天']))
        if i%3==1:body.insert(0,dict(op='write',target='globals',values={'玩家受伤':None}))
        c['operations']=[chili.scope(body,source=0)];cases.append(('death-fast-context-'+str(i),c))
    for i in range(24):
        c=base();c['units'][0]['body']['血量']=600.;c['units'][0]['state']={'_pvp_card':'producer'}
        c['units'][0]['body'].update({'防具':'铁桶','防具血量':100.})
        c['damage'].update(cards={'producer':True},until=5000,factor=2.,watch_armor=True)
        c['units'].append(projectiles.unit(260.,432.,owner='zombie'));c['units'][1]['body']['血量']=0.
        if i%2:c['units'][1]['source']['魅惑']=0.
        body=[set_unit(0,植物僵尸名='墓碑吞噬者僵尸'),set_unit(1,植物僵尸名='毁灭菇僵尸' if i%3 else '辣椒僵尸'),
            dict(op='lifecycle_hook',name='clear',body=[dict(op='roster_replace',targets=[1])]),
            dict(op='native_hit_slot',index=0,kind='ash') if i%2 else dict(op='native_hit',target=0,kind='ash')]
        c['operations']=[chili.scope(body,source=0)];cases.append(('death-raw-ash-current-index-'+str(i),c))
    return [(label+('-fast' if fast else '-full'),dict(copy.deepcopy(c),death_config=dict(fast=fast))) for label,c in cases for fast in (False,True)]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:DeathExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-native-death-chain',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['remaining bind_targets hooks','full native call-site driver','production plant admission and extra-target registry','fast paths outside the death chain','full HeroProxy template constructor','full battle','network/replay','dynamic invalid record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
