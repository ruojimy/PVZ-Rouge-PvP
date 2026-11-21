"""Compact replayable native receipts and matched-window empirical payoffs."""
import bisect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import zlib

from league_data import RUN,NEW,OLD_CORPUS,EXE,BASE,OLD_Z,MODELS,CARDS,read,write
from option_games import Game,play

CATALOG=read(CARDS)['day']
R22='r22'
NEURAL_Z={str(MODELS[k]) for k in ('h','b')}

def hash_json(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def native_game(case,plant,zombie,storage):
    root,opening=case.split('/')
    corpus={'old':OLD_CORPUS,'new':NEW}[root]
    p=None if plant==R22 else Path(plant)
    if zombie==R22 or zombie in NEURAL_Z:
        z=None if zombie==R22 else Path(zombie)
        return Game(opening,p,zombie=z,position=None,policy=None,binary=EXE,corpus=corpus,storage=storage)
    return Game(opening,p,zombie=BASE,position=OLD_Z,policy=Path(zombie),binary=EXE,corpus=corpus,storage=storage)

def compact(g):
    play(g)
    path=g.path()
    with gzip.open(path,'rt',encoding='utf8') as f:
        header=json.loads(f.readline());tr=json.loads(f.readline())
    assert header['map']=='家院' and header['control_hz']==15 and not tr['ai_error']
    assert header['planners']['plant']==('nn' if g.plant else 'r22')
    assert header['planners']['zombie']==('nn' if g.zombie else 'r22')
    assert header['limit_seconds']==g.limit and header['id']==tr['id']==g.uid
    winner=(tr['result'] or {}).get('winner')
    assert winner in ('plant','zombie','draw') or tr['timeout']
    times={'plant':[],'troops':[],'graves':[]}
    for e in tr['activity']:
        if e['kind']!='deploy':continue
        if e['side']=='plant':kind='plant'
        elif e['card'].startswith('zombie:'):kind='graves' if CATALOG[e['card']]['behavior']=='grave' else 'troops'
        else:continue
        times[kind].append(round(e['time']*30))
    prefix={}
    for field,clock in [('activity','time'),('accepted_commands','time'),('switches','t'),('spatial_actions','t')]:
        prefix[field]=hash_json([v for v in tr.get(field,[]) if round(v[clock]*30)<18000])
    votes=[v for v in tr.get('switches',[]) if v['phase']=='lease']
    arrivals=[v for v in tr.get('switches',[]) if v['phase']=='arrival_vote']
    result=dict(key=g.key(),params=g.parameters(),seed=header['seed'],battle=tr['log_sha256'],winner=winner,timeout=tr['timeout'],
                tick=round(tr['time']*30),activity=times,prefix=prefix,lease=len(votes),alternate=sum(v['choice']!=0 for v in votes),
                arrive=len(arrivals),defer=sum(not v['place'] for v in arrivals))
    return result

class Matches:
    def __init__(self,role,jobs):
        self.role=role;self.jobs=jobs;self.storage=RUN/'scratch'/role
        (self.storage/'temp').mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(RUN/'matches.sqlite',timeout=40)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        self.db.commit()
        self.cache={};self.started=time.monotonic();self.completed=0

    def pair_game(self,case,side,m,opp):
        return native_game(case,m,opp,self.storage) if side=='plant' else native_game(case,opp,m,self.storage)

    def ensure(self,games,label):
        games=list(dict.fromkeys(games));todo=[]
        for g in games:
            k=g.key()
            if k in self.cache:continue
            row=self.db.execute('SELECT payload FROM games WHERE id=?',(k,)).fetchone()
            if row:self.cache[k]=json.loads(zlib.decompress(row[0]))
            else:todo.append(g)
        progress=RUN/(self.role+'-progress.json')
        def point(n):
            write(progress,dict(stage=label,requested=len(games),cached=len(games)-len(todo),finished=n,
                                new_this_worker=self.completed,worker=os.getpid(),updated=time.time()))
        point(0)
        def one(g):
            for attempt in range(2):
                try:return compact(g)
                except (OSError,RuntimeError):
                    if attempt:raise
                    time.sleep(1.)
        with ThreadPoolExecutor(max_workers=self.jobs) as pool:
            # Receive completions out of order so one long timeout never blocks persistence.
            from concurrent.futures import as_completed
            futures={pool.submit(one,g):g for g in todo}
            for n,f in enumerate(as_completed(futures),1):
                g=futures[f];r=f.result();k=r['key']
                self.db.execute('INSERT OR IGNORE INTO games VALUES (?,?)',(k,zlib.compress(json.dumps(r,separators=(',',':')).encode(),4)))
                self.db.commit();self.cache[k]=r;self.completed+=1
                # Retain a small deterministic sample of full native traces. All matches retain seed, model hashes and deployments.
                raw=g.path();receipt=raw.with_suffix('.receipt.json')
                samples=RUN/'samples'
                if int(k[:6],16)%223==0 and raw.stat().st_size<=512*1024:
                    samples.mkdir(exist_ok=True)
                    if len(list(samples.glob('*.gz')))<96 and not (samples/raw.name).exists():
                        import shutil
                        shutil.copyfile(raw,samples/raw.name)
                for p in (raw,receipt):
                    assert p.parent.resolve()==(self.storage/'games').resolve()
                    p.unlink(missing_ok=True)
                if n==1 or n%4==0 or n==len(todo):point(n)
        return games

    def get(self,g):
        return self.cache[g.key()]

def value(r,side):
    if r['timeout'] or r['winner']=='draw':return 0
    return 1 if r['winner']==side else -1

def pairs(store,side,ref,candidate,opponents,cases):
    return [(o,c,store.pair_game(c,side,ref,o),store.pair_game(c,side,candidate,o)) for o in dict.fromkeys(opponents) for c in cases]

def evaluate(store,table,label):
    # table maps comparison names to (side, same-opening paired games).
    store.ensure((g for _,rs in table.values() for _,_,a,b in rs for g in (a,b)),label)
    tails=[]
    for side,rs in table.values():
        for _,_,a,b in rs:
            if value(store.get(a),side)!=0 and store.get(b)['timeout']:tails.append(replace(b,limit=1200))
    if tails:store.ensure(tails,label+'/extend')
    result={}
    for name,(side,rs) in table.items():
        rows=[]
        for o,c,a,b in rs:
            x,y=store.get(a),store.get(b);tick=min(x['tick'],y['tick'])
            old,new=value(x,side),value(y,side)
            extra=None
            if old and y['timeout']:
                lg=replace(b,limit=1200);z=store.get(lg)
                assert y['prefix']==z['prefix']
                extra=dict(key=z['key'],value=value(z,side),timeout=z['timeout'],tick=z['tick'])
            deploy={s:[bisect.bisect_right(t['activity'][s],tick) for t in (x,y)] for s in ('plant','troops','graves')}
            rows.append(dict(opp=o,case=c,old=old,new=new,window=tick,ends=[x['tick'],y['tick']],deploy=deploy,
                             different=x['battle']!=y['battle'],keys=[x['key'],y['key']],late=extra))
        result[name]=summarize(rows,side)
    return result

def summarize(rows,side):
    import numpy as np
    groups={}
    for r in rows:groups.setdefault(r['opp'],[]).append(r)
    def counts(xs,arm):return [sum(r[arm]==v for r in xs) for v in (1,0,-1)]
    by={o:[counts(xs,'old'),counts(xs,'new')] for o,xs in groups.items()}
    frac=[(w[1][0]-w[0][0])/sum(w[0]) for w in by.values()]
    worst=[min(w[j][0]/sum(w[j]) for w in by.values()) for j in (0,1)]
    total=sum(r['window'] for r in rows)
    freq={k:[1800*sum(r['deploy'][k][j] for r in rows)/max(1,total) for j in (0,1)] for k in ('troops','graves','plant')}
    rate=freq['troops' if side=='zombie' else 'plant'];speed=rate[1]/max(.001,rate[0]) if rate[0]>0 else 1.
    old,new=counts(rows,'old'),counts(rows,'new')
    gain=sum(r['old']==-1 and r['new']==1 for r in rows);lost=sum(r['old']==1 and r['new']!=1 for r in rows)
    changed=sum(r['different'] for r in rows)
    # True wins drive ranking. Passive timeouts have no win credit.
    score=.55*min(frac)+.45*float(np.mean(frac))+.25*(worst[1]-worst[0])-.4*lost/len(rows)-.65*max(0.,1-speed)
    return dict(old=old,new=new,kept=old[0]-lost,lost=lost,gain=gain,by=by,worst=worst,speed=speed,rates=freq,
                seconds=[sum(r['ends'][j] for r in rows)/(30*len(rows)) for j in (0,1)],changed=changed,score=score,rows=rows)
