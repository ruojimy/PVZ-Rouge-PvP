import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/typed72'))
from evidence_archive import open_evidence
def diffs(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        for key in sorted(set(a)|set(b)):
            if key not in a or key not in b:yield path+'/'+key,repr(a.get(key,'MISSING')),repr(b.get(key,'MISSING'))
            else:yield from diffs(a[key],b[key],path+'/'+key)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):yield path+'/length',len(a),len(b)
        for i,(x,y) in enumerate(zip(a,b)):yield from diffs(x,y,path+'/'+str(i))
    elif a!=b and not (isinstance(a,(float,int)) and isinstance(b,(float,int)) and abs(a-b)<1e-9):yield path,a,b
run=ROOT/'test_results/content_zombies_child/phase41_v8_r1'
with open_evidence(run/'actual.jsonl') as actual,open_evidence(run/'expected.jsonl') as expected:
    for index,(a,e) in enumerate(zip(actual,expected)):
        if index not in (23,33,35,36):continue
        got=json.loads(a);want=json.loads(e);print('CASE',index)
        for i,item in enumerate(diffs(want,got)):
            if i>=45:break
            print(json.dumps(item,ensure_ascii=False))
