from pathlib import Path
p=Path('make_duel.py');t=p.read_text(encoding='utf8')
a="""    for t in range(200,room_ticks,400):
        add(t,side='zombie',type='move',move=1,jump=False);add(t+60,side='zombie',type='move',move=0,jump=False)
"""
b="""    # The horde follows its hero, so the zombie hero walks to the plant hero and stays.
    add(200,side='zombie',type='move',move=1,jump=False);add(200+walk,side='zombie',type='move',move=0,jump=False)
"""
assert t.count(a)==1;t=t.replace(a,b)
a="def duel(seed,room_ticks,zombie_col,plant_col,row):";assert t.count(a)==1
t=t.replace(a,"def duel(seed,room_ticks,zombie_col,plant_col,row,walk=60):")
a="{'duel_settle_1':duel(7,6000,36,50,17)}";assert t.count(a)==1
t=t.replace(a,"{'duel_settle_1':duel(7,4000,36,50,17)}")
p.write_text(t,encoding='utf8')
p=Path('compare_match.py');t=p.read_text(encoding='utf8')
a=t[t.index("    a=[json.loads(l) for l in ref.read_text"):t.index("    (out/'comparison.json')")]
b="""    # Streamed: a full match trace is around a gigabyte. Missing keys are tracked across
    # the run; real value differences stop at the first tick.
    missing={};first=None;compared=0;ref_lines=typed_lines=0;last={};rng_changes=0;previous_rng=None;events=[]
    with ref.open(encoding='utf8') as left,(typed.open(encoding='utf8') if typed.exists() else open(os.devnull)) as right:
        for i,(lx,ly) in enumerate(itertools.zip_longest(left,right)):
            if lx is not None:ref_lines+=1
            if ly is not None:typed_lines+=1
            if lx is None or ly is None or first is not None:continue
            x=json.loads(lx);y=json.loads(ly);found=[];keys=('t','g','avatars','inp','battle','rng')
            walk({k:x.get(k) for k in keys},{k:y.get(k) for k in keys},'',found)
            real=[f for f in found if f[0] in('diff','length')]
            for kind,path,_,_ in found:
                if kind.startswith('only_in'):missing.setdefault(kind+':'+re.sub(r'/[0-9]+','/*',path),i)
            if real:first=dict(line=i,t=x.get('t'),rt=x.get('rt'),differences=[[f[0],f[1],f[2],f[3]] for f in real[:25]],count=len(real),rng_reference=x.get('rng'),rng_typed=y.get('rng'))
            else:compared=i+1
            if x.get('rng')!=previous_rng:rng_changes+=1;previous_rng=x.get('rng')
            last=dict(t=x['t'],rt=x['rt'],plants=len(x['g']['植物']),zombies=len(x['g']['僵尸']),entities=len(x['g']['实体']),hp={k:v.get('玩家血量') for k,v in x['avatars'].items()},result=x['battle'].get('result'))
    summary.update(reference_lines=ref_lines,typed_lines=typed_lines,compared_until_first_difference=compared,first_difference=first,field_gaps=dict(sorted(missing.items())),last_compared_state=last,reference_rng_changes=rng_changes,
        identical=first is None and not missing and ref_lines==typed_lines and run.returncode==0,
        traces=dict(reference_sha256=sha(ref),typed_sha256=sha(typed) if typed.exists() else None))
    if summary['identical'] and '--keep' not in sys.argv:ref.unlink();typed.unlink();(out/'atlas.bin').unlink();summary['traces']['discarded_after_identical']=True
"""
t=t.replace(a,b)
a="import json,math,os,re,subprocess,sys";assert t.count(a)==1
t=t.replace(a,"import hashlib,itertools,json,math,os,re,subprocess,sys")
a="def main():";assert t.count(a)==1
t=t.replace(a,"def sha(path):\n    h=hashlib.sha256()\n    with Path(path).open('rb') as f:\n        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)\n    return h.hexdigest()\n"+a)
a="    source=ROOT/'tools/scenarios'/('_expanded_'+name+'.json')\n    if not source.exists():source=ROOT/'tools/scenarios'/(name+'.json')\n"
assert t.count(a)==1
t=t.replace(a,a+"    if (STAGE/'scenarios'/(name+'.json')).exists():source=STAGE/'scenarios'/(name+'.json')\n")
a="timeout=900)";assert t.count(a)==1;t=t.replace(a,"timeout=1800)")
a="    summary.update(reference_lines=len(a),typed_lines=len(b))\n"
t=t.replace(a,"")
p.write_text(t,encoding='utf8')
