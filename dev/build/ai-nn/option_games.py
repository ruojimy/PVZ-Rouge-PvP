"""Content-addressed native games and matched outcome checks for the option study."""
import gzip
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass,replace
from functools import lru_cache
from pathlib import Path

from option_study import ROOT,PRIOR,OLD_Z,OLD_P,PROGRAM,read,write,sha
from position_study import BASE,MODELS,TOOL
from overnight_eval import measure
from home_pool import inactive

@lru_cache(maxsize=40)
def digest(path):
    return sha(path) if path else None

@dataclass(frozen=True)
class Game:
    uid:str
    plant:Path|None
    zombie:Path|None=BASE
    position:Path|None=OLD_Z
    policy:Path|None=None
    forced:int=-1
    after:int=0
    limit:int=600
    corpus:Path=ROOT/'plain'
    binary:Path=PROGRAM
    storage:Path=ROOT

    def parameters(self):
        return dict(opening=self.uid,plant=digest(self.plant),zombie=digest(self.zombie),
                    position=digest(self.position),policy=digest(self.policy),force=self.forced,after=self.after,
                    limit=self.limit,corpus=digest(self.corpus/'index.json'),binary=digest(self.binary))
    def key(self):
        return hashlib.sha256(json.dumps(self.parameters(),sort_keys=True).encode()).hexdigest()[:24]
    def path(self):
        return self.storage/'games'/(self.key()+'.jsonl.gz')

def play(g):
    if g.policy:
        parent=read(g.policy).get('position_parent')
        if parent and parent!=digest(g.position):raise ValueError('Option policy requires its frozen position scorer')
    dest=g.path();meta=dest.with_suffix('.receipt.json')
    if meta.exists() and dest.exists():
        m=read(meta);assert m['parameters']==g.parameters() and m['sha256']==sha(dest)
        return
    dest.parent.mkdir(exist_ok=True)
    raw=g.storage/'temp'/(g.key()+'.jsonl');tmp=dest.with_suffix('.partial')
    args=[g.binary,'--corpus',g.corpus,'--id',g.uid,'--out',raw,'--limit-seconds',g.limit,
          '--control-hz',15,'--telemetry','--no-records']
    if g.plant or g.zombie:
        args+=['--planner','nn','--model',g.plant or g.zombie,'--nn-seat',
               'both' if g.plant and g.zombie else 'plant' if g.plant else 'zombie']
        if g.plant and g.zombie:args+=['--zombie-model',g.zombie]
    if g.position:args+=['--position-model',g.position]
    if g.policy:args+=['--option-model',g.policy]
    if g.forced>=0:args+=['--force-option',g.forced,'--fork-after',g.after]
    result=subprocess.run([str(x) for x in args],capture_output=True,check=False)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf8','replace')[-2000:])
    raw_data=raw.read_bytes();head,tail=[json.loads(s) for s in raw_data.splitlines()]
    assert head['id']==tail['id']==g.uid and not tail['ai_error']
    assert tail['finished'] or (tail['timeout'] and abs(tail['time']-g.limit)<.01)
    if g.policy:assert head['option_sha256']==digest(g.policy)
    if g.position:assert head['zombie_position_sha256']==digest(g.position)
    if g.forced>=0:
        if g.policy:
            interventions=[x for x in tail['options'] if x.get('forked')]
            assert len(interventions)==1 and interventions[0]['choice']==g.forced
        else:assert all(x['choice']==g.forced for x in tail['options'])
    tmp.write_bytes(gzip.compress(raw_data,compresslevel=4,mtime=0))
    os.replace(tmp,dest)
    write(meta,dict(parameters=g.parameters(),sha256=sha(dest),winner=(tail['result'] or {}).get('winner'),
                    timeout=tail['timeout'],time=tail['time'],battle=tail['log_sha256'],events=len(tail.get('options',[]))))
    raw.unlink()

def batch(label,games):
    games=list(dict.fromkeys(games))
    print(label,len(games),flush=True)
    workers=min(4,max(1,int(os.environ.get('PVZ_OPTION_JOBS','4'))))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(play,games):pass

@lru_cache(maxsize=12)
def trace(g):
    with gzip.open(g.path(),'rt',encoding='utf8') as f:
        f.readline()
        return json.loads(f.readline())

def outcome(r,side):
    winner=(r['result'] or {}).get('winner')
    return 0 if r['timeout'] or winner=='draw' else 1 if winner==side else -1

def slow(old,new):
    t=min(old['time'],new['time'])
    def slower(s):
        x=measure(old['activity'],s,t);y=measure(new['activity'],s,t)
        return y['rich_idle']>x['rich_idle']+30 or (x['deploys']>=10 and y['deploys']<.75*x['deploys'] and y['mean_resource']>1.5*x['mean_resource'])
    return inactive(new) or all(slower(s) for s in ('plant','zombie'))

def extend(pairs):
    # Suffix comparison uses all actions plus separate accepted native deployments and commands.
    tests = [(base,new,side) for base,new,side in pairs if outcome(trace(base),side)<0 and trace(new)['timeout']]
    if tests:batch('extend matched losses', [replace(new,limit=1200) for _,new,_ in tests])
    results=[]
    for base,new,side in tests:
        long=replace(new,limit=1200);a=trace(new);b=trace(long)
        for field,key in [('activity','time'),('accepted_commands','time'),('spatial_actions','t')]:
            assert [x for x in a[field] if x[key]<600]==[x for x in b[field] if x[key]<600]
        def option_prefix(r):
            retained=[]
            for e in r.get('options',[]):
                if e['time']>=600:continue
                if 'mask' in e:
                    retained.append(e)
                    continue
                r0={k:e[k] for k in ('time','x','values','choice','origin','proposed_spawn','proposed_front')}
                if e.get('end',float('inf'))<600:r0.update(end=e['end'],status=e['status'])
                for k in ('built','spawn'):
                    if k in e and e[k]['time']<600:r0[k]=e[k]
                retained.append(r0)
            return retained
        assert option_prefix(a)==option_prefix(b)
        results.append(dict(side=side,id=new.uid,base=base.key(),candidate=new.key(),extended=long.key(),
                            before_loss_at=trace(base)['time'],winner=(b['result'] or {}).get('winner'),
                            timeout=b['timeout'],end=b['time'],joint_idle=slow(trace(base),a)))
    return results

def preflight():
    base=Game('000',MODELS['o'],corpus=PRIOR/'plain')
    ancestor=replace(base,binary=TOOL)
    branches=[replace(base,forced=o,after=12) for o in range(4)]
    batch('ancestor parity and fork smoke',[ancestor,base,*branches])
    assert trace(ancestor)['log_sha256']==trace(base)['log_sha256']==trace(branches[0])['log_sha256']
    states=[trace(g)['options'][0] for g in branches]
    assert all((s['prefix'],s['time'],s['x'])==(states[0]['prefix'],states[0]['time'],states[0]['x']) for s in states)
    write(ROOT/'preflight.json',dict(parity=trace(base)['log_sha256'],prefix=states[0]['prefix'],
            branches=[dict(key=g.key(),choice=e['choice'],time=e['time'],status=e['status'],built=e.get('built'),spawn=e.get('spawn')) for g,e in zip(branches,states)]))
