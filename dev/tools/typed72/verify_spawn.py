"""All original zombie constructor branches against shipped raw bytecode.

This is the raw constructor. Current PvP/patch admission, card registration,
plant-zombie constructors and proxy factory composition remain separate gates.
"""
import argparse
import ast
import builtins
import copy
import json
import marshal
import random
import shutil
import subprocess
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_heroes as hero
from verify_stages import sha,difference
import evidence_store
import evidence_archive
ROOT=hero.ROOT


def reference():
    raw=marshal.loads(hero.RAW.read_bytes())
    return {n.co_name:n for n in raw.co_consts if isinstance(n,types.CodeType)}


def oracle(case,functions):
    rng=random.Random(case['seed']);sounds=[]
    g=dict(__builtins__=builtins.__dict__,僵尸=[],实体=[],模式=case['mode'],玩家位置=list(case['player']),比=case['tile'],plk=case['plk'],
        ditu=[[{} for _ in range(case['cols'])] for _ in range(case['rows'])],总高=case['height'],boss=case['bosses'],
        c=copy.deepcopy,随=rng.randint,沉浸播音=lambda name,pos:sounds.append([name,pos]))
    g['新增实体']=types.FunctionType(functions['新增实体'],g);spawn=types.FunctionType(functions['新增僵尸'],g);states=[]
    for op in case['operations']:
        pos=list(op['position']);spawn(op['name'],pos,op['facing']);after=list(pos)
        if op.get('mutate_after'):pos[:]=[9000.,8000.,7000.,6000.]
        states.append(copy.deepcopy(dict(input_after=after,units=g['僵尸'],entities=g['实体'],sounds=sounds,rng=list(rng.getstate()[1]),
            source_kinds=[u['僵尸'] for u in g['僵尸']],roster_matches_store=True)))
    return states


def make_cases():
    # Derive every literal kind compared in the actual decompiled constructor,
    # then independently execute the bytecode (not this source) as the oracle.
    path=ROOT/'extract/original/functions.py';tree=ast.parse(path.read_text(encoding='utf8'),str(path))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='新增僵尸');names=['普通僵尸']
    for n in ast.walk(fn):
        if isinstance(n,ast.Compare) and isinstance(n.left,ast.Name) and n.left.id=='name':
            for value in n.comparators:
                if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value not in names:names.append(value.value)
    names.append('未识别原始种类') # The original intentionally falls through.
    cases=[]
    for mode in ('正常模式','极难模式','末日模式','无尽模式','测试模式','抽奖模式','其他模式'):
        for tile in (32.,48.,80.):
            for seed in (721,726):
                c=dict(seed=seed,tile=tile,plk=tile/10000.,mode=mode,player=[100.,240.,0.,0.],rows=24,cols=33,height=900.,
                    bosses=['巨人僵尸','舞王僵尸','普通僵尸'],operations=[])
                for i,name in enumerate(names):c['operations'].append(dict(name=name,position=[(90.,100.,110.)[i%3],300.+i,-.25,1.],facing=1. if i%2 else -1.,mutate_after=True))
                cases.append((mode+'-'+str(tile)+'-'+str(seed),c))
    return cases,names


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);exe=Path(args.exe).resolve()
    paths=[exe,Path(__file__).resolve(),hero.RAW,ROOT/'extract/original/functions.py',ROOT/'tools/typed72/spawn_probe.cpp',
        ROOT/'tools/typed72/targets_probe.cpp',ROOT/'tools/typed72/hero_probe.cpp',ROOT/'tools/typed72/verify_stages.py',
        ROOT/'tools/typed72/verify_heroes.py',ROOT/'src/core/pyrandom.h',ROOT/'third_party/nlohmann/json.hpp']
    paths+=list((ROOT/'src/sim/typed').glob('*.*'));paths.extend((Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()));pinned={str(p):sha(p) for p in paths}
    (out/'pinned.json').write_text(json.dumps(pinned,indent=2),encoding='utf8')
    for p in paths:
        try:relative=p.relative_to(ROOT)
        except ValueError:relative=Path('reference')/p.name
        dest=out/'frozen'/relative;dest.parent.mkdir(parents=True,exist_ok=True);evidence_store.freeze_file(p,dest,expected_sha256=pinned[str(p)])
    cases,names=make_cases();functions=reference()
    with (out/'inputs.jsonl').open('w',encoding='utf8') as f:
        for label,c in cases:f.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
        run=subprocess.run([str(exe),str(out/'inputs.jsonl'),str(out/'actual.jsonl')],stdout=stdout,stderr=stderr,timeout=240)
    results=[]
    with (out/'actual.jsonl').open(encoding='utf8') as actual,(out/'expected.jsonl').open('w',encoding='utf8') as expected:
        for i,(label,c) in enumerate(cases):
            row=dict(case=i,label=label,passed=False)
            try:
                got=json.loads(next(actual));want=oracle(c,functions);diff=difference(want,got)
                expected.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');row.update(passed=diff is None,steps=len(want),first_difference=diff)
            except Exception as exc:row['error']=repr(exc)
            results.append(row)
            if not row['passed']:(out/('failure-%04d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            print(i,label,'PASS' if row['passed'] else 'FAIL',flush=True)
        extra=next(actual,None)
    changed=[str(p) for p in paths if sha(p)!=pinned[str(p)]]
    report=dict(passed=bool(results) and all(r['passed'] for r in results) and run.returncode==0 and not changed and extra is None,
        backend_actual='typed72-original-zombie-constructor',full_battle_acceptance=False,full_product_claim=False,process_exit_code=run.returncode,
        cases=len(results),passed_cases=sum(r['passed'] for r in results),compared_steps=sum(r.get('steps',0) for r in results),tolerance=1e-9,
        changed_inputs=changed,results=results,input_kinds=names,
        excluded=['1.5.0.1 spawn wrapper/plant-zombie constructors','PvP spawn admission and registration','proxy factory composition','full world tick'])
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','input_kinds')}));return evidence_archive.finish_verification(out,producer=run,closed_streams=(actual,expected),behavior_passed=report['passed'])


if __name__=='__main__':sys.exit(main())
