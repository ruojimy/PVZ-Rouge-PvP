"""Room snapshot identity: V REF_SNAPSHOTS (recorder v4) against typed MATCH_SNAPSHOTS.
usage: compare_snapshots.py ref.snap.jsonl typed.snap.jsonl [report.json]
native_frame is compared by compare_frames.py and skipped here. Numbers to 1e-9 relative.
Lists of dicts with an "id" are matched by id; key order is ignored."""
import collections,json,math,re,sys
TOL=1e-9
# engine_load is V's wall-clock native cost ratio (nondeterministic, not battle state).
SKIP={'native_frame','engine_load'}
def norm(path):return re.sub(r'/\d+','/#',re.sub(r'\[[^\]]*\]','[*]',path))
def walk(a,b,path,out):
    if isinstance(a,bool) or isinstance(b,bool):
        if a!=b:out.append((path,a,b))
        return
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if a==b or abs(a-b)<=TOL*max(1.,abs(a),abs(b)):return
        out.append((path,a,b));return
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a:
            if k in SKIP:continue
            if k not in b:out.append((path+'.'+k,'<present>','<missing>'))
            else:walk(a[k],b[k],path+'.'+k,out)
        for k in b:
            if k not in a and k not in SKIP:out.append((path+'.'+k,'<missing>','<present>'))
        return
    if isinstance(a,list) and isinstance(b,list):
        if a and all(isinstance(x,dict) and 'id' in x for x in a) and all(isinstance(x,dict) and 'id' in x for x in b):
            ia={x['id']:x for x in a};ib={x['id']:x for x in b}
            if list(ia)!=list(ib):out.append((path+'#ids',list(ia)[:8],list(ib)[:8]))
            for k in ia:
                if k in ib:walk(ia[k],ib[k],path+'[%s]'%k,out)
            return
        if len(a)!=len(b):out.append((path+'#len',len(a),len(b)))
        for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/%d'%i,out)
        return
    if a!=b:out.append((path,a,b))
def load(p):return {json.loads(l)['rt']:json.loads(l)['snapshot'] for l in open(p,encoding='utf8')}
def main():
    ref=load(sys.argv[1]);typ=load(sys.argv[2])
    counts=collections.Counter();first={};same=0
    for rt in sorted(ref):
        if rt not in typ:counts['<absent>']+=1;continue
        out=[];walk(ref[rt],typ[rt],'',out)
        if not out:same+=1
        for path,a,b in out:
            k=norm(path);counts[k]+=1
            if k not in first:first[k]=(rt,path,a,b)
    print('snapshots identical %d of %d'%(same,len(ref)))
    for k,v in counts.most_common(40):
        rt,path,a,b=first.get(k,(None,None,None,None))
        print('  %5d %s  e.g. rt=%s %s V=%s T=%s'%(v,k,rt,path,json.dumps(a,ensure_ascii=False)[:80],json.dumps(b,ensure_ascii=False)[:80]))
    if len(sys.argv)>3:json.dump({'identical':same,'total':len(ref),'counts':counts.most_common()},open(sys.argv[3],'w',encoding='utf8'),ensure_ascii=False,indent=1)
if __name__=='__main__':main()
