"""Stream all-card and secret-context comparisons against retained V/hand."""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'))
import evidence_archive
import evidence_store

def cases(export):
    cards=export['raw_templates'];keys=export['card_order']
    secrets=[key for key in keys if cards[key]['category']=='secret']
    active=[key for key in secrets if cards[key]['selectable']]
    contexts=[[],secrets,active]+[[secret] for secret in secrets]
    rng=random.Random(72061106)
    contexts += [rng.sample(active,rng.randrange(1,len(active)+1)) for unused in range(16)]
    for context in contexts:
        for night in (False,True):
            for key in keys:yield dict(op='actual',key=key,secrets=context,night=night)
    for key in keys:
        card=cards[key]
        for context in ([],active):
            for bans in ([],[key],[card['family']],secrets):
                for spawn in (False,True):yield dict(op='allowed',key=key,secrets=context,bans=bans,for_spawn=spawn)
                for night in (False,True):yield dict(op='resolve',key=key,secrets=context,bans=bans,night=night)
    for context in ([],active,list(reversed(active)),active+active,['unknown'],['plant:向日葵'],['坏'*90]):
        for bans in ([],active[:4]):yield dict(op='native_secrets',key='',secrets=context,bans=bans)
    for context in (['secret:肆意模仿'],['secret:肆意模仿','secret:速植','secret:蓝火'],active):
        for target in keys:
            if cards[target]['side']!='plant':continue
            for bans in ([],[target]):
                for night in (False,True):
                    for op in ('player','unit'):
                        yield dict(op=op,key='plant:模仿者',secrets=context,bans=bans,night=night,last_copy_card=target)
    for key in keys:
        for op in ('player','unit'):yield dict(op=op,key=key,secrets=active,bans=[key],side=cards[key]['side'])
    for op in ('allowed','resolve'):yield dict(op=op,key='unknown',secrets=[])

def difference(want,got,path=''):
    if isinstance(want,dict) and isinstance(got,dict):
        if set(want)!=set(got):return dict(path=path,expected_keys=sorted(want),actual_keys=sorted(got))
        for key in want:
            found=difference(want[key],got[key],path+'/'+key)
            if found:return found
    elif isinstance(want,list) and isinstance(got,list):
        if len(want)!=len(got):return dict(path=path,expected_length=len(want),actual_length=len(got))
        for index,(a,b) in enumerate(zip(want,got)):
            found=difference(a,b,path+'/'+str(index))
            if found:return found
    elif isinstance(want,bool) or isinstance(got,bool) or want is None or got is None:
        if type(want)!=type(got) or want!=got:return dict(path=path,expected=want,actual=got)
    elif isinstance(want,(int,float)) and isinstance(got,(int,float)):
        if abs(want-got)>1e-9:return dict(path=path,expected=want,actual=got)
    elif want!=got:return dict(path=path,expected=want,actual=got)
    return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True,type=Path);ap.add_argument('--build',type=Path,default=ROOT/'build/typed72-cold-catalog-v2');a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    build=a.build.resolve();built=json.loads((build/'build-report.json').read_text(encoding='utf8'))
    export=json.loads((ROOT/'test_results/cold-catalog-work/v-export-v1.json').read_text(encoding='utf8'))
    paths=[Path(__file__).resolve(),Path(evidence_archive.__file__).resolve(),Path(evidence_store.__file__).resolve(),build/'build-report.json']
    paths += [build/'build/Release'/(n+'.exe') for n in ('cold_catalog_probe','v_cold_catalog_probe')]
    paths += [ROOT/'tools/typed72/drafts'/n for n in ('cold_catalog.cpp','cold_catalog.h','cold_card_fields.h','cold_catalog_data.cpp','cold_catalog_probe.cpp','v_cold_catalog_probe.cpp')]
    pins={str(p):evidence_store.sha256_file(p) for p in paths}
    (out/'pinned.json').write_text(json.dumps(pins,indent=2),encoding='utf8')
    for p in paths:evidence_store.freeze_file(p,out/'frozen'/p.relative_to(ROOT),expected_sha256=pins[str(p)])
    total=0
    with (out/'inputs.jsonl').open('w',encoding='utf8') as inputs:
        for case in cases(export):inputs.write(json.dumps(case,ensure_ascii=False,separators=(',',':'))+'\n');total+=1
    runs={}
    for name,output in (('v_cold_catalog_probe','expected.jsonl'),('cold_catalog_probe','actual.jsonl')):
        with (out/(name+'.log')).open('wb') as log:
            runs[name]=subprocess.run([str(build/'build/Release'/(name+'.exe')),str(out/'inputs.jsonl'),str(out/output)],cwd=built['runtime_workdir'],stdout=log,stderr=subprocess.STDOUT,timeout=600)
    failures=[];compared=0
    with (out/'inputs.jsonl').open(encoding='utf8') as inputs,(out/'expected.jsonl').open(encoding='utf8') as expected,(out/'actual.jsonl').open(encoding='utf8') as actual:
        for index,line in enumerate(inputs):
            try:
                want=json.loads(next(expected));got=json.loads(next(actual));found=difference(want,got)
            except Exception as error:found=dict(error=repr(error))
            if found:
                row=dict(case=index,input=json.loads(line),difference=found);failures.append(row)
                if len(failures)<=50:(out/('failure-%06d.json'%index)).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
            compared+=1
        extra=next(expected,None) is not None or next(actual,None) is not None
    drift=[str(p) for p in paths if evidence_store.sha256_file(p)!=pins[str(p)]]
    report=dict(passed=not failures and not extra and not drift and all(r.returncode==0 for r in runs.values()),
                cases=total,compared=compared,passed_cases=compared-len(failures),failures=len(failures),failure_samples=failures[:50],
                process_exit_code=runs['cold_catalog_probe'].returncode,reference_exit_code=runs['v_cold_catalog_probe'].returncode,
                changed_inputs=drift,extra_rows=extra,backend_actual='typed-cold-catalog',reference='existing-v-hand-catalog',
                library_provenance=built['library_provenance'],full_product_acceptance=False)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='failure_samples'},ensure_ascii=False),flush=True)
    return evidence_archive.finish_verification(out,producer=runs['cold_catalog_probe'],closed_streams=(actual,expected),behavior_passed=report['passed'])

if __name__=='__main__':sys.exit(main())
