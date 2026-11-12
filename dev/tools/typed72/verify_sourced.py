"""Literal bind_targets wrapper over instrumented typed bodies, not full binding."""
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
import verify_chili as chili
import evidence_store
import evidence_archive
doom=chili.doom;plants=chili.plants;projectiles=chili.projectiles;hero=chili.hero;patch=chili.patch;ROOT=chili.ROOT;P=chili.P
sha=chili.sha;difference=chili.difference


def reference():
    env=chili.reference();tree=ast.parse(doom.NATIVE_PATCH.read_text(encoding='utf8'),str(doom.NATIVE_PATCH))
    outer=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='bind_targets')
    matches=[n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='bind']
    if len(matches)!=1:raise ValueError('source wrapper ambiguity')
    env['bind_code']=compile(ast.Module(body=matches,type_ignores=[]),str(doom.NATIVE_PATCH),'exec')
    names={'kind_key','noop_unless_kind','hero_free_bodies'}
    assignments=[n for n in outer.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
    if len(assignments)!=len(names):raise ValueError('source fast-path configuration ambiguity')
    env['fast_config_code']=compile(ast.Module(body=assignments,type_ignores=[]),str(doom.NATIVE_PATCH),'exec');return env


class SourcedExtension(chili.ChiliExtension):
    def __init__(self,*args):super().__init__(*args);self.observations=[]
    def operation(self,op):
        action=op['op']
        if action=='source_call':
            source=self.births[op['entity_source']] if 'entity_source' in op else self.units[op['unit_source']] if 'unit_source' in op else self.ctx.sources[op['source']] if op.get('source') is not None else None
            name,position,phase={'regular':('update_squash_zombie',1,'zombies'),'spawn':('spawn_zombie_pea',5,'zombies'),'player':('chili_fire_player_hit',1,'entities')}[op['kind']]
            def body(*unused,**kwargs):self.operations(op['body'],False);return op.get('return')
            ns={P+name:body};obj=types.SimpleNamespace(ns=ns,g=self.g,_target_originals={})
            env=dict(PREFIX=P,targets=self.c,self=obj,ns=ns,fast=False,kind_key='植物僵尸名',noop_unless_kind={},hero_free_bodies=frozenset(),
                telemetry=dict(noop_contexts=0,hero_free_contexts=0,full_contexts=0),wraps=functools.wraps,NativePatchError=RuntimeError)
            exec(self.env['bind_code'],env);env['bind'](name,position,'source_zombie' if position==5 else 'entity' if op['kind']=='player' else 'zombie',phase)
            try:return ns[P+name](*([self.g]+[0]*(position-1)+[source]))
            except Exception:
                if not op.get('catch',False):raise
                return {'caught':True}
        if action=='source_write':
            source=self.births[op['entity_source']] if 'entity_source' in op else self.units[op['unit_source']] if 'unit_source' in op else self.ctx.sources[op['source']]
            values=copy.deepcopy(op['values'])
            if '_pvp_instant_attack' in values:values['_pvp_instant_attack']=hero.decode_attack(values['_pvp_instant_attack'])
            source.update(values);return None
        if action=='source_throw':raise RuntimeError('injected sourced body failure')
        if action=='source_observe':
            self.observations.append(copy.deepcopy(dict(active={k:self.c.active[k] for k in ('owner','target','phase')} if self.c.active else None,
                globals={k:v for k,v in self.g.items() if k in self.c.context_keys})));return None
        return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row);row['source_observations']=self.observations;row['launch_tokens']={};row['heroes']=copy.deepcopy(row['heroes'])
        for side,h in row['heroes'].items():
            if '_pvp_launch_attack' in h:row['launch_tokens'][side]=str(h.pop('_pvp_launch_attack'))


def make_cases():
    cases=[]
    sources=[{}, {'_pvp_owner':'plant'},{'_pvp_owner':'zombie'},{'_pvp_owner':'plant2'},{'_pvp_owner':'zombie2'},
        {'_pvp_owner':None},{'_pvp_owner':'invalid'},{'_pvp_owner':None,'魅惑':None}, {'魅惑':0.},
        {'_pvp_owner':'plant','_pvp_instant_attack':None},{'_pvp_owner':'zombie','_pvp_instant_attack':['tag',7]},
        {'_pvp_owner':'plant','_pvp_id':'hero:plant','植物':'香蒲'}]
    for i,s in enumerate(sources):
        for kind in ('regular','spawn','player'):
            for fail in (False,True):
                c=chili.base();c['sources']=[s];body=[dict(op='source_observe'),dict(op='player_damage',amount=3.),chili.fire(name='尖刺'),dict(op='source_observe')]
                if kind=='player':body.append(dict(op='write',target='globals',values={'辣飞天':150.}))
                if fail:body.append(dict(op='source_throw'))
                c['operations']=[dict(op='source_call',kind=kind,source=0,body=body,catch=True,**{'return':True})]
                cases.append(('source-selection-'+str(i)+'-'+kind+'-'+str(fail),c))
    for i in range(48):
        c=chili.base();c['sources']=[dict(sources[i%len(sources)]),dict(_pvp_owner='plant')]
        inner=dict(op='source_call',kind='player' if i%2 else 'spawn',source=None if i%3 else 1,catch=True,
            body=[dict(op='source_observe'),dict(op='player_damage',amount=2.),chili.fire(),dict(op='write',target='globals',values={'辣飞天':150.})])
        c['operations']=[dict(op='source_call',kind='regular',source=0,catch=True,body=[dict(op='player_damage',amount=1.),inner,dict(op='source_observe')])]
        cases.append(('source-nested-fallback-'+str(i),c))
    for i in range(24):
        c=chili.base();c['sources']=[{'_pvp_owner':'plant','植物':'香蒲'}]
        body=[chili.fire(name='尖刺'),dict(op='effect_roster_replace',births=[0,1] if i%2 else [0]),dict(op='source_observe')]
        if i%3==0:body.append(dict(op='source_throw'))
        c['operations']=[chili.fire(name='尖刺'),dict(op='source_call',kind='spawn',source=0,body=body,catch=True),dict(op='source_call',kind='player',source=None,body=[],catch=True)]
        cases.append(('source-spawn-list-'+str(i),c))
    for i in range(24):
        c=chili.base();c['sources']=[{'_pvp_owner':'plant','植物':'向日葵'}]
        body=[chili.fire(name='尖刺'),dict(op='source_write',source=0,values={'植物':'香蒲','_pvp_owner':'zombie'}),dict(op='source_observe')]
        if i%3==0:body.append(dict(op='source_throw'))
        if i%3==1:body.append(dict(op='effect_roster_replace',births=[0,1]))
        c['operations']=[chili.fire(name='尖刺'),dict(op='source_call',kind='spawn',source=0,body=body,catch=True)]
        cases.append(('source-retag-mutated-shooter-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),doom.LEGACY,doom.NATIVE_PATCH,patch.PATCH,plants.TABLES,plants.FUNCTIONS,projectiles.CONTENT,projectiles.FLYING,projectiles.SCALE,projectiles.SIMULATION,projectiles.CATALOG61,
        hero.TARGETS,hero.BATTLE,hero.BALANCE,hero.ZSECRETS,hero.ZCATALOG,hero.PHYSICS,hero.CATALOG,hero.PROJECTILES,hero.RAW,plants.protection.PROTECTION,plants.protection.TEAMS,
        ROOT/'src/core/pyrandom.h',ROOT/'src/core/pymath.h',ROOT/'third_party/nlohmann/json.hpp']
    paths += [ROOT/'tools/typed72'/n for n in ('sourced_probe.cpp','verify_chili.py','chili_probe.cpp','doom_probe.cpp','plants_probe.cpp','targets_probe.cpp','hero_probe.cpp','verify_doom.py','verify_plants.py','verify_targets.py','verify_heroes.py','verify_protection.py','verify_patch.py','verify_projectiles.py','verify_entities.py','verify_stages.py')]
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:SourcedExtension(ctx,c,pref,chili_ref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%16==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-sourced-context',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,changed_inputs=changed,results=results,
        excluded=['actual sourced body composition','remaining bind_targets hooks','full fastpath comparison','full HeroProxy template constructor','full battle','network/replay','dynamic invalid record schemas'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
