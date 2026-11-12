"""Actual NativeTargets._new_entity/tag_entity with retained dictionary identity."""
import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
import verify_protection as protection
import verify_targets as targets
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT


class EntityExtension(targets.TargetExtension):
    def __init__(self,ctx,case,pref):
        super().__init__(ctx,case,pref);self.retained=[];self.handles_alive=[];self.original_entity_roster=self.g['实体']
    def entity_source(self,index):return self.retained[index]
    def operation(self,op):
        action=op['op'];result=None
        if action=='spawn_entity':
            self.g['新增实体'](op['name'],op.get('facing',1.),list(op['position']))
            self.retained.append(self.g['实体'][-1]);self.handles_alive.append(True)
        elif action=='erase_entity':
            i=op['entity'];result=self.handles_alive[i]
            if result:self.g['实体'][:]=[e for e in self.g['实体'] if e is not self.retained[i]];self.handles_alive[i]=False
        elif action=='release_entity':self.retained[op['entity']]=None
        elif action=='entity_kind':self.retained[op['entity']]['名']=op['name']
        elif action=='entity_position':self.retained[op['entity']]['位置'][:]=op['position']
        elif action=='tag_retained':self.c.tag_entity(self.retained[op['entity']],op.get('owner'),self.ctx.sources[op['source']] if 'source' in op else None)
        else:return super().operation(op)
        return result
    def snapshot(self,row):
        super().snapshot(row);retained=copy.deepcopy(self.retained)
        for e in retained:
            if e is not None:
                e.pop('方向',None)
                if '_pvp_instant_attack' in e:e['_pvp_instant_attack_text']=str(e.pop('_pvp_instant_attack'))
        row['retained_entities']=retained;row['entity_handles_alive']=list(self.handles_alive)
        row['original_entity_roster_identity']=self.g['实体'] is self.original_entity_roster


def make_cases():
    cases=[]
    names=('豌豆','冰豆','火豆','蓝火豆','僵尸豌豆','泡泡','海泡泡','尖刺','星星','篮球','西瓜','普通僵尸-首')
    parents=({'植物':'香蒲'},{'植物':'小喷菇'},{'植物':'胆小菇'},{'_pvp_id':'hero:plant2'},
        {'植物':'杨桃','_pvp_instant_attack':['blast',73]}, {'_pvp_owner':None,'_pvp_original_owner':None,'_pvp_root_source':None})
    for side in ('plant','zombie','plant2','zombie2'):
        for name in names:
            for parent in parents:
                c=hero.base();c['sources']=[copy.deepcopy(parent)];c['tagging']=True;c['units']=[];c['damage']={}
                c['operations']=[dict(op='context',target='zombie' if side.startswith('plant') else 'plant',owner=side,phase='plants',source=0,body=[
                    dict(op='spawn_entity',name=name,position=[150.,240.,2.,-.5],facing=-1.),
                    dict(op='entity_position',entity=0,position=[170.,230.,-2.,.5]),
                    dict(op='context',target='zombie',owner='plant',phase='entities',entity_source=0,body=[
                        dict(op='entity_kind',entity=0,name='火豆'),dict(op='source_amount',target='zombie'),
                        dict(op='erase_entity',entity=0),dict(op='erase_entity',entity=0),
                        dict(op='spawn_entity',name='尖刺',position=[170.,230.,1.,0.]),
                        dict(op='release_entity',entity=0),dict(op='source_amount',target='zombie'),
                        dict(op='spawn_entity',name='豌豆',position=[172.,230.,1.,0.])]),
                    dict(op='tag_retained',entity=1,owner=side,source=0)])]
                cases.append(('entity-lifetime-%d'%len(cases),c))
    for i in range(8):
        c=hero.base();c['tagging']=True;c['units']=[];c['sources']=[{'植物':'火爆辣椒'}];c['damage']={}
        c['operations']=[dict(op='spawn_entity',name='豌豆',position=[0.,0.,0.,0.]),
            dict(op='erase_entity',entity=0),dict(op='spawn_entity',name='西瓜',position=[1.,2.,3.,4.]),
            dict(op='context',target='zombie',owner='plant',phase='entities',entity_source=0,body=[
                dict(op='spawn_entity',name=names[i],position=[9.,8.,7.,6.]),dict(op='release_entity',entity=0),
                dict(op='spawn_entity',name='火',position=[0.,0.,0.,0.])])]
        cases.append(('inactive-birth-'+str(i),c))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(a.exe).resolve()
    paths=[exe,Path(__file__).resolve(),ROOT/'tools/typed72/entity_probe.cpp',ROOT/'tools/typed72/targets_probe.cpp',ROOT/'tools/typed72/hero_probe.cpp',
        ROOT/'tools/typed72/verify_targets.py',ROOT/'tools/typed72/verify_heroes.py',ROOT/'tools/typed72/verify_protection.py',ROOT/'tools/typed72/verify_stages.py',
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
                got=json.loads(next(actual));want=hero.oracle(c,ref,lambda ctx:EntityExtension(ctx,c,pref));diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            if i%32==0 or not row['passed']:print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-entity-lifetime',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,excluded=['full entity motion/collision/cull tick','full synchronous death effects','whole battle','network/replay'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
