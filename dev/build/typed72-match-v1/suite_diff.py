"""Per-test outcome diff between two run_cpp_suite outputs (same suite, same interpreter):
typed build vs the frozen V build. Usage: suite_diff.py <typed-dir> <v-dir> [report.json]"""
import collections,json,sys
from pathlib import Path
def load(d):
    out={}
    for p in Path(d).glob('test_*.json'):
        try:rows=json.loads(p.read_text(encoding='utf8'))
        except Exception:continue
        if not isinstance(rows,list):continue
        for t in rows:
            if isinstance(t,dict) and 'test' in t:
                out[(t.get('module'),t.get('class'),t.get('test'))]=(t.get('outcome'),str(t.get('detail') or '').strip().splitlines()[-1:] or [''])
    return out
typed=load(sys.argv[1]);base=load(sys.argv[2])
# ONLY_TYPED_MODULES: a targeted typed run covers some modules; compare only those.
mods={k[0] for k in typed};base={k:v for k,v in base.items() if k[0] in mods}
counts=lambda d:dict(collections.Counter(v[0] for v in d.values()))
cat=collections.defaultdict(list)
for k in sorted(set(typed)|set(base)):
    a=typed.get(k,('MISSING',['']))[0];b=base.get(k,('MISSING',['']))[0]
    if a=='PASS' and b=='PASS':continue
    if a==b:kind='both_nonpass_same'
    elif a=='PASS':kind='fixed_in_typed'
    elif b=='PASS':kind='typed_regression'
    else:kind='both_nonpass_differ'
    cat[kind].append({'id':'.'.join(map(str,k)),'typed':a,'v':b,'typed_detail':typed.get(k,('',['']))[1][0][:300],'v_detail':base.get(k,('',['']))[1][0][:300]})
summary={'typed':counts(typed),'v_baseline':counts(base),'identities':{'typed':len(typed),'v':len(base),'only_typed':len(set(typed)-set(base)),'only_v':len(set(base)-set(typed))},'categories':{k:len(v) for k,v in cat.items()}}
print(json.dumps(summary,ensure_ascii=False,indent=1))
for row in cat.get('typed_regression',[]):print('REG',row['id'][-110:],'|',row['typed_detail'][:160])
if len(sys.argv)>3:Path(sys.argv[3]).write_text(json.dumps({'summary':summary,'details':cat},ensure_ascii=False,indent=1),encoding='utf-8')
