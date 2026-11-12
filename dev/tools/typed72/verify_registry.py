"""Actual NativeBattle omitted-target collector over ordered native records.

Executes the literal collector lambda, zombie_hero_proxies and team_seats.
HeroProxy template construction and card admission remain separate integrations.
"""
import argparse
import ast
import copy
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
TEAMS=plants.protection.TEAMS


def reference():
    env=death.reference();source=ast.parse(hero.BATTLE.read_text(encoding='utf8'),str(hero.BATTLE))
    assignments=[n for n in ast.walk(source) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Lambda)
        and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Index) and isinstance(t.slice.value,ast.Constant)
            and t.slice.value.value=='_pvp_target_extras' for t in n.targets)]
    if len(assignments)!=1:raise ValueError('ambiguous native target provider')
    env['native_provider']=compile(ast.Expression(assignments[0].value),str(hero.BATTLE),'eval')
    # The exact participating-seat method determines that dormant PvE zombie
    # avatars stay out, while dead heroes in duel/duo remain target records.
    team_env={};exec(compile(TEAMS.read_text(encoding='utf8'),str(TEAMS),'exec'),team_env)
    env['teams']=team_env
    methods=[]
    for path,cls,names in [(hero.BATTLE,'NativeBattle',('zombie_hero_proxies',)),(projectiles.SIMULATION,'Battle',('team_seats',))]:
        tree=ast.parse(path.read_text(encoding='utf8'),str(path))
        # Use exact method ownership; reject a second implementation.
        matches=[n for c in tree.body if isinstance(c,ast.ClassDef) and c.name==cls for n in c.body if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(matches)!=len(names):raise ValueError('missing native registry method '+str(path))
        methods+=matches
    cls=ast.ClassDef(name='RegistryBattleOracle',bases=[],keywords=[],body=methods,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(hero.BATTLE),'exec'),team_env)
    env['RegistryBattleOracle']=team_env['RegistryBattleOracle'];return env


class RegistryExtension(death.DeathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.registry_held=[];self.native=ref['RegistryBattleOracle']()
        self.native._native_objects={};self.native.players=ctx.battle.players
        # Collider templates are covered by the separate hero chain. This
        # adapter preserves its known cache and does not assert full factories.
        self.native.targets=types.SimpleNamespace(hero_proxy=ctx.get_proxy)
        self.set_mode('duel');self.collect=eval(ref['native_provider'],dict(self=self.native))
        self.g['_pvp_target_extras']=self.extra_targets

    def set_mode(self,value):
        t=self.env['teams'];self.native.mode=value;self.native.seats=t['seats_for'](value)
        self.native.scripted=t['scripted'](value);self.native.team_mode=t['team_mode'](value)

    def obj(self,label):return self.all_plants[label['plant']] if isinstance(label,dict) else self.units[label]
    def label(self,obj):
        for i,u in enumerate(self.units):
            if u is obj:return i
        for i,p in enumerate(self.all_plants):
            if p is obj:return {'plant':i}
        for seat,p in self.c.proxies.items():
            if p is obj:return seat
        raise ValueError('unowned native object')

    def extra_targets(self):
        self.calls.append(['extras']);self.before('extras');result=self.collect();self.after('extras');return result

    def operation(self,op):
        action=op['op'];records=self.native._native_objects;result=None
        if action=='registry_set':records[op['key']]=self.obj(op['target'])
        elif action=='registry_erase':result=op['key'] in records;records.pop(op['key'],None)
        elif action in ('registry_get','registry_hold'):
            obj=records.get(op['key'])
            if obj is not None:
                result=self.label(obj)
                if action=='registry_hold':self.registry_held.append(obj)
        elif action=='registry_mode':self.set_mode(op['value'])
        elif action=='registry_flags':
            u=self.units[op['unit']]
            for k,v in (('grave','_pvp_grave'),('orphan','_pvp_orphan_barrel'),('hp','血量')):
                if k in op:u[v]=op[k]
        elif action=='registry_collect':result=[self.label(o) for o in self.collect()]
        elif action=='registry_scope':
            # Use the real full_targets context and real provider. The native
            # collector itself has no fixture hook in this direct operation.
            saved=self.g['_pvp_target_extras'];self.g['_pvp_target_extras']=self.collect
            try:
                with self.c.full_targets():self.operations(op['body'])
            except Exception:
                if not op.get('catch',False):raise
                result={'caught':True}
            finally:self.g['_pvp_target_extras']=saved
        else:return super().operation(op)
        return result

    def snapshot(self,row):
        super().snapshot(row);row['registry']=[[key,self.label(obj)] for key,obj in self.native._native_objects.items()]
        row['registry_held']=[self.label(obj) for obj in self.registry_held]
        row['registry_flags']=[[bool(u.get('_pvp_grave')),bool(u.get('_pvp_orphan_barrel'))] for u in self.units]
        row['match_seats']=list(self.native.seats)


def make_cases():
    cases=[]
    for mode in ('duel','duo','pve','coop'):
        for i in range(32):
            c=death.base();c['units']=[projectiles.unit(240.+n*24.,432.,owner='zombie') for n in range(8)]
            setup=[dict(op='registry_mode',value=mode),dict(op='plant_original',cell=[5,5],name='向日葵')]
            for n in range(8):setup.append(dict(op='registry_flags',unit=n,grave=(n+i)%3==0,orphan=(n+i)%4==1,hp=(-1.,0.,1.,80.)[(n+i)%4]))
            for n in (4,1,6,0,7,2,5,3):setup.append(dict(op='registry_set',key='u'+str(n),target=n))
            setup += [dict(op='registry_set',key='plant',target={'plant':0}),dict(op='registry_collect'),
                dict(op='registry_hold',key='u1'),dict(op='registry_set',key='u1',target=6),dict(op='registry_set',key='alias',target=6),
                dict(op='registry_collect'),dict(op='registry_erase',key='u4'),dict(op='registry_set',key='u4',target=4),dict(op='registry_erase',key='missing'),
                dict(op='registry_flags',unit=1,hp=20.,grave=True),dict(op='registry_get',key='u1'),dict(op='registry_get',key='missing'),dict(op='registry_collect')]
            if i%2:setup += [dict(op='remove_unit',unit=4),dict(op='registry_collect')]
            if i%4==0:setup += [dict(op='write',target='zombie',values={'玩家血量':0.}),dict(op='write',target='zombie2',values={'玩家血量':-2.}),dict(op='registry_collect')]
            c['operations']=setup;cases.append(('registry-order-'+mode+'-'+str(i),c))
        for i in range(16):
            c=death.base();c['units'] += [projectiles.unit(240.+n*20.,432.,owner='zombie') for n in range(4)]
            body=[dict(op='roster_replace',targets=[0,3]),dict(op='registry_erase',key='a'),dict(op='registry_set',key='c',target=4),
                dict(op='registry_scope',body=[dict(op='roster_append',target=2),dict(op='registry_collect')]),dict(op='registry_collect')]
            if i%2:body.append(dict(op='source_throw'))
            c['operations']=[dict(op='registry_mode',value=mode),dict(op='registry_flags',unit=1,grave=True),dict(op='registry_flags',unit=2,orphan=True),
                dict(op='registry_flags',unit=4,grave=True),dict(op='registry_set',key='a',target=1),dict(op='registry_set',key='b',target=1),
                dict(op='registry_set',key='d',target=2),dict(op='roster_replace',targets=[0,1] if i%4==0 else [0]),dict(op='registry_scope',body=body,catch=True),dict(op='registry_collect')]
            c['operations'] += [dict(op='registry_flags',unit=1,hp=0.),dict(op='registry_collect')]
            c['death_config']={'fast':bool(i%2)};cases.append(('registry-full-targets-'+mode+'-'+str(i),c))
        for i in range(12):
            c=death.base();c['units'] += [projectiles.unit(240.+n*24.,432.,owner='zombie') for n in range(4)]
            if i%2:c['units'][0]['source']['魅惑']=0.
            setup=[dict(op='registry_mode',value=mode),dict(op='registry_flags',unit=1,grave=True),dict(op='registry_flags',unit=2,orphan=True),
                dict(op='registry_flags',unit=3,grave=True,hp=0.),dict(op='registry_set',key='a',target=1),dict(op='registry_set',key='b',target=2),dict(op='registry_set',key='c',target=3),
                dict(op='roster_replace',targets=[0]),death.set_unit(0,血量=0.,植物僵尸名='毁灭菇僵尸',植物僵尸=True)]
            body=[dict(op='native_deaths',unit=0),dict(op='registry_collect')]
            if i%3==0:body.insert(0,dict(op='lifecycle_hook',name='extras',body=[dict(op='roster_replace',targets=[0,4])]))
            c['operations']=setup+[chili.scope(body,unit_source=0)];c['death_config']={'fast':bool(i%2)}
            cases.append(('registry-doom-'+mode+'-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('registry_probe.cpp','verify_death.py','death_probe.cpp','verify_sourced.py','sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
    paths+=hero.PROXY_REFERENCE_PATHS+list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    ref=hero.load_reference();pref=plants.protection.reference();registry_ref=reference();cases=make_cases()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:RegistryExtension(ctx,c,pref,registry_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-native-registry',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['card admission and automatic registration callers','full HeroProxy template constructor','complete main battle driver','all remaining mechanics','AI/network/replay','full original suite and product performance'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
