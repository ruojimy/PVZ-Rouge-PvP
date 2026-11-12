import json,sys,collections
s=json.load(open('test_results/typed72-20261106/batch-%s/batch.json'%sys.argv[1],encoding='utf8'))
print('identical',s['identical'],'of',s['total'])
gapc=collections.Counter()
for r in s['rows']:
    f=r.get('first')
    print(r['scenario'].ljust(19),'ID' if r.get('identical') else '--',r.get('typed_rc'),str(r.get('compared'))+'/'+str(r.get('ref_lines')),'gaps',r.get('gaps'),(r.get('failure') or '')[:44],(r.get('unsupported') or [])[:2],(f and (f['t'],f['count'],json.dumps(f['head'][:2],ensure_ascii=False)[:150])) or '',(r.get('stderr') or '')[:90].replace('\n',' '),r.get('error','')[:100])
for r in s['rows']:
    try:
        c=json.load(open('test_results/typed72-20261106/batch-%s/%s/comparison.json'%(sys.argv[1],r['scenario']),encoding='utf8'))
        for k in c.get('field_gaps',{}):gapc[k.replace('only_in_reference:','R ').replace('only_in_typed:','T ')]+=1
    except Exception:pass
print(len(gapc));print(gapc.most_common(int(sys.argv[2]) if len(sys.argv)>2 else 60))
