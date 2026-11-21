"""Stream canonical policy-v2 features into a compressed ragged numeric cache."""
import argparse,json,random,subprocess
import numpy as np
from overnight_common import *
ap=argparse.ArgumentParser();ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--stride',type=int,default=4);ap.add_argument('--augment',type=int,default=2);ap.add_argument('--limit',type=int,default=90000)
args=ap.parse_args();assert not args.out.exists();guard()
paths=[Path(p) for p in read(args.sources)];rng=random.Random(181118);rows=[];seen=0
input_list=args.out.with_suffix('.inputs.txt');input_list.parent.mkdir(parents=True,exist_ok=True)
input_list.write_text('\n'.join(map(str,paths))+'\n','utf-8')
cmd=[str(BIN/'neural_dataset.exe'),'-','-','--feature-version','2','--policy-version','2','--relabel','1',
     '--stride',str(args.stride),'--augment',str(args.augment),'--seed','181118','--inputs-list',str(input_list)]
with args.out.with_suffix('.encoder.log').open('wb') as log:
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',creationflags=0x08004000)
    try:
        header=json.loads(proc.stdout.readline());dim=16+len(header['behaviors'])
        assert header['policy_version']==2 and header['feature_version']==2
        for line in proc.stdout:
            r=json.loads(line);seen+=1
            index=seen-1 if len(rows)<args.limit else rng.randrange(seen)
            if index>=args.limit:continue
            row=(np.asarray(r['x']['global'],dtype=np.float32),np.asarray(r['y'],dtype=np.int16),
                 np.asarray(r['x']['own'],dtype=np.float32).reshape(-1,dim),np.asarray(r['x']['enemy'],dtype=np.float32).reshape(-1,dim),
                 .25 if r.get('aug') else 1.,str(r['id']),r['tick'])
            if index==len(rows):rows.append(row)
            else:rows[index]=row
            if seen%2000==0:guard()
        if proc.wait()!=0:raise RuntimeError('Canonical encoder failed')
    except BaseException:kill_owned(proc);raise
assert rows
out=dict(g=np.stack([r[0] for r in rows]),y=np.stack([r[1] for r in rows]),weight=np.array([r[4] for r in rows],dtype=np.float32),
         ids=np.array([r[5] for r in rows]),ticks=np.array([r[6] for r in rows]),header=np.array(json.dumps(header)))
out['hashes']=np.asarray([list(hashlib.sha256(r[0].tobytes()+r[2].tobytes()+r[3].tobytes()).digest()) for r in rows],dtype=np.uint8)
for key,col in [('own',2),('enemy',3)]:
    arrays=[r[col] for r in rows];out[key]=np.concatenate(arrays)
    out[key+'_offsets']=np.r_[0,np.cumsum([len(a) for a in arrays])]
guard();args.out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(args.out,**out)
with np.load(args.out,allow_pickle=False) as check:
    assert all(np.array_equal(check[k],v) for k,v in out.items())
write(args.out.with_suffix('.json'),dict(samples=len(rows),seen=seen,source_count=len(paths),stride=args.stride,augment=args.augment,
    encoded_sha256=sha(args.out),bytes=args.out.stat().st_size,verified_round_trip=True,
    goal_11_samples=int(((out['g'][:,0]>.5)&(out['y'][:,0]==11)).sum()),
    transition_samples=int(((out['g'][:,0]>.5)&(out['y'][:,1]!=(out['g'][:,11]>.5))).sum()),
    sources={str(p):sha(p) for p in paths}))
guard();print(json.dumps(dict(samples=len(rows),seen=seen,compressed_bytes=args.out.stat().st_size)))
