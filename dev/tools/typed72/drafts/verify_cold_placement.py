"""Retained V/hand versus typed original placement and PvP legality wrappers."""
import argparse
import copy
import json
import random
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import evidence_archive
import evidence_store
from verify_cold_catalog import difference

def cases():
    export=json.loads((ROOT/'test_results/cold-catalog-work/v-export-v1.json').read_text(encoding='utf8'))
    names=list(dict.fromkeys(c['native_input_name'] for c in export['raw_templates'].values() if c['side']=='plant' and c['category']!='secret'))
    names+=['铲子','未知植物','']
    blocks=['土','草','石','花盆块','铁路','水','黑水','海水','梯子块','空','基岩','坟墓']
    roster=[[],[dict(植物='向日葵',坐标=[2,2])],[dict(植物='南瓜头',坐标=[2,2])],
        [dict(植物='南瓜头',坐标=[2,2]),dict(植物='向日葵',坐标=[2,2])],
        [dict(植物='向日葵',坐标=[2,2]) for i in range(3)],
        [dict(植物='向日葵',坐标=[2,2]) for i in range(4)],
        [dict(植物='南瓜头',坐标=[2,2],vine=True)],
        [dict(植物='南瓜头',坐标=[2,2],vine=True,睡觉=True)],
        [dict(植物='模仿者',坐标=[2,2],basin=True)],
        [dict(植物='水盆',坐标=[2,2],basin=True)],
        [dict(植物='向日葵',坐标=[2,2],air=True)],
        [dict(植物='阳光菇',坐标=[2,2],睡觉=True)],
        [dict(植物='阳光菇',坐标=[2,2],睡觉=False)],
        [dict(植物='阳光菇',坐标=[2,2],睡觉=None)],
        [dict(植物='睡莲',坐标=[3,2])],[dict(植物='香蒲',坐标=[3,2])],
        [dict(植物='南瓜头',坐标=[2,2]),dict(植物='阳光菇',坐标=[2,2],睡觉=True)]]
    for below in blocks:
        for plants in roster:
            for secrets in ([],['密植'],['无土栽培'],['密植','无土栽培','石果']):
                grid=[[dict(方块='空') for x in range(5)] for y in range(5)]
                for x in range(5):grid[3][x]['方块']=below
                for p in plants:grid[p['坐标'][0]][p['坐标'][1]]['植物']=True
                queries=[dict(op='accepts',name=name,row=2,col=x) for name in names for x in (2,7,-3)]
                queries += [dict(op=op,row=2,col=2,vine=vine) for op in ('shell','idle','grass','water') for vine in (False,True)]
                queries += [dict(op='dense_error',name=name,row=2,col=2) for name in names]
                yield dict(grid=grid,plants=plants,secrets=secrets,empty_blocks=['空','水','黑水','海水','梯子块'],queries=queries)
    rng=random.Random(721106)
    for index in range(96):
        grid=[[dict(方块=rng.choice(blocks)) for x in range(5)] for y in range(5)]
        plants=[]
        for i in range(10):
            row=rng.randrange(5);col=rng.randrange(5);name=rng.choice(('向日葵','南瓜头','睡莲','阳光菇'))
            item=dict(植物=name,坐标=[row,col]);grid[row][col]['植物']=True
            if rng.random()<.3:item['睡觉']=rng.choice((True,False,None))
            if name=='南瓜头':item['vine']=rng.choice((True,False))
            plants.append(item)
        queries=[dict(op=op,name=rng.choice(names),row=rng.choice((-1,0,2,4,5)),col=rng.choice((-100000000003,-1,0,2,4,5,100000000002)),vine=bool(index%2))
                 for op in ('accepts','dense_error','shell','idle','grass','water') for i in range(20)]
        yield dict(grid=grid,plants=plants,secrets=['密植'] if index%2 else [],empty_blocks=['空','水','黑水','海水','梯子块'],queries=queries,
                   source='custom:ea660000000000000000000000000009' if index%3 else '')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True,type=Path);ap.add_argument('--build',required=True,type=Path);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);build=a.build.resolve()
    built=json.loads((build/'build-report.json').read_text(encoding='utf8'))
    paths=[Path(__file__).resolve(),Path(evidence_archive.__file__).resolve(),Path(evidence_store.__file__).resolve(),Path(__file__).resolve().parent/'verify_cold_catalog.py',build/'build-report.json']
    names=('cold_placement_probe','v_cold_placement_probe')
    paths += [build/'build/Release'/(n+'.exe') for n in names]
    paths += [ROOT/'tools/typed72/drafts'/n for n in ('cold_placement_rules.h','cold_placement_rules.cpp','cold_placement_probe.cpp','v_cold_placement_probe.cpp')]
    pins={str(p):evidence_store.sha256_file(p) for p in paths};(out/'pinned.json').write_text(json.dumps(pins,indent=2),encoding='utf8')
    for p in paths:evidence_store.freeze_file(p,out/'frozen'/p.relative_to(ROOT),expected_sha256=pins[str(p)])
    total=queries=0
    with (out/'inputs.jsonl').open('w',encoding='utf8') as inputs:
        for case in cases():inputs.write(json.dumps(case,ensure_ascii=False,separators=(',',':'))+'\n');total+=1;queries+=len(case['queries'])
    runs={}
    for name,output in ((names[1],'expected.jsonl'),(names[0],'actual.jsonl')):
        with (out/(name+'.log')).open('wb') as log:runs[name]=subprocess.run([str(build/'build/Release'/(name+'.exe')),str(out/'inputs.jsonl'),str(out/output)],cwd=built['runtime_workdir'],stdout=log,stderr=subprocess.STDOUT,timeout=600)
    failures=[];compared=0
    with (out/'inputs.jsonl').open(encoding='utf8') as inputs,(out/'expected.jsonl').open(encoding='utf8') as expected,(out/'actual.jsonl').open(encoding='utf8') as actual:
        for i,line in enumerate(inputs):
            try:found=difference(json.loads(next(expected)),json.loads(next(actual)))
            except Exception as error:found=dict(error=repr(error))
            if found:
                row=dict(case=i,input=json.loads(line),difference=found);failures.append(dict(case=i,difference=found))
                if len(failures)<=50:(out/('failure-%06d.json'%i)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            compared+=1
        extra=next(expected,None) is not None or next(actual,None) is not None
    drift=[str(p) for p in paths if evidence_store.sha256_file(p)!=pins[str(p)]]
    report=dict(passed=not failures and not extra and not drift and all(r.returncode==0 for r in runs.values()),cases=total,queries=queries,passed_cases=compared-len(failures),failures=failures,
                process_exit_code=runs[names[0]].returncode,reference_exit_code=runs[names[1]].returncode,changed_inputs=drift,extra_rows=extra,
                reference='existing-v-hand-NativePlacementRules',library_provenance=built['library_provenance'],full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='failures'}),flush=True)
    return evidence_archive.finish_verification(out,producer=runs[names[0]],closed_streams=(actual,expected),behavior_passed=report['passed'])

if __name__=='__main__':sys.exit(main())
