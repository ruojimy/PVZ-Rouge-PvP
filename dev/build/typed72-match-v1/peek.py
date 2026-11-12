"""peek.py <dir> <t0> <t1> <section> <index|-> <fields...>: one field path per side, per tick."""
import json,sys
d,t0,t1,section,idx=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4],sys.argv[5]
fields=sys.argv[6:]
def pick(x):
    s=x['g'][section] if section in x['g'] else x[section]
    return s if idx=='-' else (s[int(idx)] if isinstance(s,list) and int(idx)<len(s) else s.get(idx) if isinstance(s,dict) else None)
with open(d+'/reference.jsonl',encoding='utf8') as a,open(d+'/typed.jsonl',encoding='utf8') as b:
    for i,(x,y) in enumerate(zip(a,b)):
        if i<t0:continue
        if i>t1:break
        X,Y=json.loads(x),json.loads(y);px,py=pick(X),pick(Y)
        if not fields:
            print(i,'R',json.dumps(px,ensure_ascii=False)[:1400]);print(i,'T',json.dumps(py,ensure_ascii=False)[:1400]);continue
        print(i,'R',[px.get(f) if isinstance(px,dict) else None for f in fields],'T',[py.get(f) if isinstance(py,dict) else None for f in fields])
