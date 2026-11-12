"""Native frame identity: V REF_FRAMES (ref72_record v3) against typed MATCH_FRAMES.

usage: compare_frames.py reference.frames.jsonl typed.frames.jsonl [report.json]
Each V frame (published only when it changed) is matched with the typed frame of the
same native tick. Commands compare exactly (numbers to 1e-9 relative); positions too.
Reports per-frame first difference plus missing/extra command tallies by source kind."""
import collections,difflib,json,math,sys
TOL=1e-9
def num_eq(a,b):
    if isinstance(a,bool) or isinstance(b,bool):return a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return a==b or abs(a-b)<=TOL*max(1.,abs(a),abs(b))
    return None
def same(a,b):
    r=num_eq(a,b)
    if r is not None:return r
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b
def root_key(surface):
    d=surface
    while isinstance(d,dict):
        img=d.get('image',d)
        if not isinstance(img,dict):return None
        if img.get('op')=='asset':return img.get('key')
        d=img.get('source')
    return None
def chain(surface):
    out=[];d=surface
    while isinstance(d,dict):
        img=d.get('image',d)
        if not isinstance(img,dict):break
        out.append(img.get('op'));d=img.get('source')
    return '<'.join(out)
def label(c):
    if c.get('op')!='image':return 'prim:'+str(c.get('primitive',c.get('op')))
    e=c.get('entity');return '%s|%s|%s'%((e or '-')[:1],chain(c['surface']),root_key(c['surface']))
def signature(c):
    # Coarse identity for alignment: kind, source, recipe chain and root asset.
    return '%s|%s'%(label(c),c.get('entity'))
def load(path):
    frames={}
    for line in open(path,encoding='utf8'):
        r=json.loads(line);f=r['frame'];frames[f['tick']]=f
    return frames
def first_diff(a,b,path=''):
    r=num_eq(a,b)
    if r is not None:return None if r else (path,a,b)
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a:
            if k not in b:return (path+'.'+k,a[k],'<missing>')
            d=first_diff(a[k],b[k],path+'.'+k)
            if d:return d
        for k in b:
            if k not in a:return (path+'.'+k,'<missing>',b[k])
        return None
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return (path+'#len',len(a),len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            d=first_diff(x,y,path+'/%d'%i)
            if d:return d
        return None
    return None if a==b else (path,a,b)
def main():
    ref=load(sys.argv[1]);typ=load(sys.argv[2])
    missing=collections.Counter();extra=collections.Counter();detail=collections.Counter()
    identical=0;absent=[];first=None;rows=[]
    for tick in sorted(ref):
        a=ref[tick];b=typ.get(tick)
        if b is None:absent.append(tick);continue
        if same(a['commands'],b['commands']) and same(a['positions'],b['positions']):identical+=1;continue
        sa=[signature(c) for c in a['commands']];sb=[signature(c) for c in b['commands']]
        m=difflib.SequenceMatcher(None,sa,sb,autojunk=False)
        for op,i1,i2,j1,j2 in m.get_opcodes():
            if op=='equal':
                for i,j in zip(range(i1,i2),range(j1,j2)):
                    d=first_diff(a['commands'][i],b['commands'][j])
                    if d:
                        detail[(label(a['commands'][i]),d[0])]+=1
                        if first is None:first={'tick':tick,'index':i,'path':d[0],'reference':d[1],'typed':d[2],'command':a['commands'][i]}
                continue
            for i in range(i1,i2):missing[label(a['commands'][i])]+=1
            for j in range(j1,j2):extra[label(b['commands'][j])]+=1
        pd=first_diff(a['positions'],b['positions'],'positions')
        rows.append({'tick':tick,'ref':len(a['commands']),'typed':len(b['commands']),'positions':pd and pd[0]})
    report={'reference_frames':len(ref),'typed_frames':len(typ),'identical':identical,'absent_ticks':absent[:20],'absent':len(absent),
            'missing':missing.most_common(60),'extra':extra.most_common(60),'value_diffs':[[k[0],k[1],v] for k,v in detail.most_common(40)],
            'first_value_diff':first,'frames':rows[:30]}
    text=json.dumps(report,ensure_ascii=False,indent=1)
    if len(sys.argv)>3:open(sys.argv[3],'w',encoding='utf8').write(text)
    print('frames identical %d of %d (typed %d, absent %d)'%(identical,len(ref),len(typ),len(absent)))
    print('missing',sum(missing.values()),'extra',sum(extra.values()),'value-diff commands',sum(detail.values()))
    for k,v in missing.most_common(25):print('  -',v,k)
    for k,v in extra.most_common(15):print('  +',v,k)
    for k,v in detail.most_common(15):print('  ~',v,k[0],k[1])
    if first:print('first value diff',json.dumps(first,ensure_ascii=False)[:600])
if __name__=='__main__':main()
