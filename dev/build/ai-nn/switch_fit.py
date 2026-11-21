"""Reconstruct native command disagreements and fit state-conditional continuation returns."""
from collections import Counter,defaultdict
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import os
import time
import msvcrt
import option_games
import json
from pathlib import Path
import numpy as np
from switch_study import OUT,PREVIOUS,CORPUS,OLD_CORPUS,STRONG,PLANTS,EVENT,NATIVE,DEPLOY,ARRIVAL,CONTEXT,PARENT,PROGRAM,sha,read,fixed
from event_study import LIVE
from option_games import Game,MODELS,trace,play,slow,outcome,extend
from option_fit import paired_result

def limited_play(g):
    locks=OUT/'locks';locks.mkdir(exist_ok=True)
    # A comparison can be requested by two stages while a long match is running.
    # Protect the content-addressed raw file as well as the process count.
    bucket=int(g.key()[:4],16)%127
    with (locks/f'receipt-{bucket}.lock').open('a+b') as row_lock:
        if not row_lock.tell():row_lock.write(b'0');row_lock.flush()
        while True:
            row_lock.seek(0)
            try:msvcrt.locking(row_lock.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:time.sleep(.2)
        try:return run_with_slot(g)
        finally:
            row_lock.seek(0);msvcrt.locking(row_lock.fileno(),msvcrt.LK_UNLCK,1)

def run_with_slot(g):
    locks=OUT/'locks';locks.mkdir(exist_ok=True)
    while True:
        for slot in range(6):
            with (locks/f'game-{slot}.lock').open('a+b') as lock:
                if not lock.tell():lock.write(b'0');lock.flush()
                lock.seek(0)
                try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                except OSError:continue
                try:return play(g)
                finally:
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        time.sleep(.3)

def batch(label,games):
    games=list(dict.fromkeys(games))
    workers=max(1,min(6,int(os.environ.get('PVZ_SWITCH_JOBS','6'))))
    print(label,len(games),flush=True)
    if label.startswith('extend'):workers=min(workers,4)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(limited_play,games):pass

option_games.batch=batch

def model(tag,config):
    path=OUT/'models'/(tag+'.json')
    fixed(path,{**read(EVENT),'switch':config})
    return path

def game(i,plant,policy,corpus=CORPUS,**kw):
    binary=kw.pop('binary',NATIVE)
    return Game(i,plant,policy=policy,corpus=corpus,storage=OUT,binary=binary,**kw)

def scan(i,p,corpus):
    return [game(i,p,model(tag+'-scan',dict(start=tag,full_inputs=True)),corpus) for tag in ('old','event')]

def original(r):
    a=Game(r['id'],MODELS[r['opponent']],policy=PARENT,corpus=OLD_CORPUS,storage=PREVIOUS,binary=PROGRAM)
    b=replace(a,policy=EVENT,binary=LIVE)
    assert [a.key(),b.key()]==[r['baseline'],r['candidate']]
    return a,b

def prior_rows():
    return read(PREVIOUS/'test.json')['results']['zombie']['all']['rows']

def cases(name):
    if name=='review':
        rows=[r for r in prior_rows() if r['old']==1 and r['new']!=1]
        assert len(rows)==11
    elif name=='positive':
        rows=[r for r in prior_rows() if r['old']==-1 and r['new']==1]
    else:
        return [(i,o,scan(i,p,CORPUS),None) for i in read(OUT/'splits.json')['train'] for o,p in PLANTS.items()]
    return [(r['id'],r['opponent'],scan(r['id'],MODELS[r['opponent']],OLD_CORPUS),original(r)) for r in rows]

def commands(g):
    out=defaultdict(list)
    for c in trace(g)['accepted_commands']:
        out[c['tick']].append({k:v for k,v in c.items() if k not in ('time','tick','seq','event','side')})
    return out

def divergence(a,b):
    x,y=commands(a),commands(b)
    for t in sorted(x.keys()|y.keys()):
        if x[t]!=y[t]:return t,x[t],y[t]
    return None,[],[]

def interventions(name):
    cases0=cases(name)
    batch(name+' both natural heads',[g for _,_,pair,_ in cases0 for g in pair])
    chosen=[]
    for i,o,(a,b),prior in cases0:
        if prior:
            for x,y in zip((a,b),prior):
                assert trace(x)['log_sha256']==trace(y)['log_sha256'],(name,i,o,x.key(),y.key())
        t,x,y=divergence(a,b)
        if t is None:
            assert trace(a)['log_sha256']==trace(b)['log_sha256']
            continue
        # Both natural continuations preserve their latent policy state. A third
        # branch explicitly hands the z16 controller over at the same tick.
        gs=[replace(a,forced=0,after=t/30),replace(b,forced=1,after=t/30),replace(a,forced=1,after=t/30)]
        chosen.append((i,o,a,b,t,x,y,gs))
    batch(name+' replay from first actual disagreement',[g for *_,gs in chosen for g in gs])
    rows=[];ex=[]
    for i,o,a,b,t,x,y,gs in chosen:
        markers=[next(e for e in trace(g)['switches'] if e['phase']=='decision') for g in gs]
        assert len({e['prefix'] for e in markers})==1 and all(round(e['t']*30)==t for e in markers),(i,o,t,markers)
        assert [trace(g)['log_sha256'] for g in gs[:2]]==[trace(g)['log_sha256'] for g in (a,b)],(i,o)
        z,ev,sw=[outcome(trace(g),'zombie') for g in gs]
        change=commands(gs[2])[t]
        rows.append(dict(id=i,opponent=o,tick=t,seconds=t/30,commands=[x,y,change],prefix=markers[0]['prefix'],
                         mask=markers[0]['mask'],state=markers[0]['state'],old=z,event=ev,switched=sw,keys=[g.key() for g in gs],
                         equivalent=trace(gs[0])['log_sha256']==trace(gs[2])['log_sha256'],slow=slow(trace(gs[0]),trace(gs[2]))))
        ex.extend((f,k,'zombie') for f in gs for k in gs if outcome(trace(f),'zombie')==-1 and trace(k)['timeout'])
    fixed(OUT/(name+'.json'),dict(scanned=len(cases0),rows=rows,extensions=extend(ex)))

def run(stage):
    if stage in ('review','positive','fresh'):interventions(stage)
    elif stage=='front':front()
    elif stage=='ready':ready()
    elif stage=='later':
        if not (OUT/'later.json').exists():later()
        from switch_study import guard
        guard('walk')
    elif stage=='walk':walk_control()
    elif stage=='zombie':train_zombie()
    elif stage=='plant':train_plant()
    elif stage=='context-zombie':
        from switch_context_fit import parity,context_zombie
        parity();context_zombie()
    elif stage=='test':
        from switch_context_fit import complete
        complete()
        test()
    elif stage=='audit':audit()
    elif stage=='horizons':blind_horizons()
    elif stage=='final-audit':audit(final=True)
    else:raise ValueError(stage)
def front(roots_only=False):
    eligible=defaultdict(list);count=forward=chosen=0
    for r in prior_rows():
        _,g=original(r)
        for e in trace(g)['options']:
            if not e['mask']&15:continue
            offers=[p for p in e.get('pool',[]) if p['act'][0]==3]
            if not offers:continue
            count+=1;chosen+=int(e['action'][0]==3)
            offers=[p for p in offers if p['x'][11]>np.tanh(1.25/6)+1e-8]
            if not offers:continue
            forward+=1
            a=offers[0]
            eligible[r['id']].append((r['opponent'],g,e['time'],a,round(6*np.arctanh(min(.999999999,a['x'][11])),2)))
    assert (count,chosen)==(643,0)
    # Select without outcomes. Spread over times, opponents and distances, with
    # a second state at least 10 seconds away from the first on each opening.
    rng=np.random.default_rng(430767);samples=[]
    for j,(i,pool) in enumerate(sorted(eligible.items())):
        old_t=-999
        for k in range(2):
            target=(3,7,18,32)[(j+2*k)%4]
            candidates=[p for p in pool if abs(p[2]-old_t)>=10]
            if not candidates:continue
            opponent='rhb'[(j+k)%3]
            p=min(candidates,key=lambda p:(p[0]!=opponent,abs(np.log(p[4]/target))+.18*abs(p[2]-(30 if not k else 125))/100+rng.random()*.06))
            o,ref,t,a,dist=p;old_t=t
            w=model(f'front-{i}-{k}',dict(start='event',target=a['act']))
            base=game(i,MODELS[o],w,OLD_CORPUS)
            gs=[replace(base,forced=n,after=t) for n in (1,2,3)]
            samples.append((i,o,ref,t,a,dist,gs))
    batch('same-state natural / travel then build / direct same-site build',[g for *_,gs in samples for g in gs])
    rows=[];extensions=[]
    for i,o,ref,t,a,dist,gs in samples:
        evs=[trace(g)['switches'] for g in gs]
        starts=[next(e for e in em if e['phase']=='decision') for em in evs]
        assert len({e['prefix'] for e in starts})==1 and all(e['front']==a['act'] and abs(e['t']-t)<.01 for e in starts),(i,o,t,starts)
        assert trace(ref)['log_sha256']==trace(gs[0])['log_sha256']
        results=[outcome(trace(g),'zombie') for g in gs]
        rows.append(dict(id=i,opponent=o,t=t,distance=dist,mask=starts[0]['mask'],target=a['act'],site=starts[0]['site'],state=starts[0]['state'],
                         keys=[g.key() for g in gs],results=results,prefix=starts[0]['prefix'],phases=[em[1:] for em in evs],
                         distinct=len({trace(g)['log_sha256'] for g in gs}),slow=slow(trace(gs[0]),trace(gs[1]))))
        extensions.extend((f,k,'zombie') for f in gs for k in gs if outcome(trace(f),'zombie')<0 and trace(k)['timeout'])
    if roots_only:return rows
    fixed(OUT/'front.json',dict(total=count,forward=forward,chosen=chosen,rows=rows,extensions=extend(extensions)))
def later():
    # Sample a later real deployment from each fixed-plant training game,
    # across opening, midgame and late play. Check which native event bits
    # actually fired when the zombie next observes that deployment.
    items=[]
    for j,(i,o,(g,_),_) in enumerate(cases('fresh')):
        tr=trace(g);deadline=min(tr['time']*.75,(24,75,145)[(j+j//3)%3])
        acts=[e for e in tr['spatial_actions'] if e['kind'] in ('spawn','build') and e['t']+1<tr['time']]
        if not acts:continue
        e=min(acts,key=lambda v:(0 if v['kind']=='build' and abs(deadline-v['t'])<25 else 1,abs(v['t']-deadline)))
        t=(round(e['t']*30)+2)/30
        clean=replace(g,policy=model('old-short',dict(start='old')))
        items.append((i,o,replace(clean,forced=0,after=t)))
    batch('later training roots on z16 paths',[a for _,_,a in items])
    groups=[]
    for i,o,a in items:
        m=next(e for e in trace(a)['switches'] if e['phase']=='decision')
        gs=[a,replace(a,forced=1)]
        if m['front'] is not None:gs.append(replace(a,forced=2))
        groups.append((i,o,m,gs))
    batch('continue z16 or hand over, with forward branch where available',[g for *_,gs in groups for g in gs[1:]])
    rows=[];extension=[]
    for i,o,m,gs in groups:
        evs=[trace(g)['switches'] for g in gs]
        assert all(e[0]['prefix']==m['prefix'] for e in evs)
        results=[outcome(trace(g),'zombie') for g in gs]
        rows.append(dict(id=i,opponent=o,mask=m['mask'],t=m['t'],state=m['state'],site=m['site'],front=m['front'],
                         results=results,keys=[g.key() for g in gs],phases=[es[1:] for es in evs],prefix=m['prefix'],
                         slow=[slow(trace(gs[0]),trace(g)) for g in gs]))
        extension.extend((f,k,'zombie') for f in gs for k in gs if outcome(trace(f),'zombie')<0 and trace(k)['timeout'])
    fixed(OUT/'later.json',dict(rows=rows,extensions=extend(extension)))

def learning_rows(with_visited=False):
    gates=[];fronts=[]
    def supervision(r,keys,vals,extensions,old,j,stall):
        a,b=vals[old],vals[j]
        # Finishing within the ordinary horizon is preferred. Extra time only
        # earns credit for a verified win against a matched losing continuation.
        def utility(idx,other):
            if vals[idx]==1:return 1.
            if vals[idx]==-1:return -1.
            if vals[other]!=-1:return -.45
            tail=extensions.get((keys[other],keys[idx]))
            if not tail:return -.45 # native draw rather than time limit
            if tail['winner']=='zombie' and not tail['joint_idle']:return .55
            return -1.
        return utility(j,old)-utility(old,j)-.35*int(stall and b<=a)
    for stage in ('review','positive','fresh','later','ready','front')+(('visited',) if with_visited else ()):
        data=read(OUT/(stage+'.json'));extended={(e['base'],e['candidate']):e for e in data['extensions']}
        for r in data['rows']:
            keys=r['keys'];vals=r['results'] if 'results' in r else [r['old'],r['event'],r['switched']]
            ident=r.get('corpus','previous' if stage in ('review','positive','front') else 'fresh')+r['id']
            if stage!='front':
                j=1 if stage in ('later','ready','visited') else 2
                sd=r['slow'][1] if stage in ('later','ready','visited') else r['slow']
                value=supervision(r,keys,vals,extended,0,j,sd)
                gates.append((ident,r['prefix'],r['state'],value))
            if stage=='front' or (stage in ('later','ready','visited') and len(vals)==3):
                a,b=(0,1) if stage=='front' else (1,2)
                value=supervision(r,keys,vals,extended,a,b,r['slow'] if stage=='front' else r['slow'][2])
                if stage=='front':
                    value=min(value,supervision(r,keys,vals,extended,2,1,False))
                fronts.append((ident,r['prefix'],r['site'],value))
    return gates,fronts

def fit(samples):
    # Share an opening's mass across all of its probes and collapse identical
    # prefix/return pairs. Different responses from distinct opponents remain.
    filtered={ (i,p,tuple(x),float(y)) for i,p,x,y in samples }
    rows=sorted(filtered)
    x=np.array([v[2] for v in rows]);y=np.array([v[3] for v in rows])
    counts=Counter(v[0] for v in rows)
    w=np.array([1/counts[v[0]] for v in rows]);w*=len(w)/w.sum()
    rng=np.random.default_rng(761649)
    h=rng.normal(0,.55,(12,x.shape[1]));hb=rng.normal(0,.18,12)
    ph=np.c_[np.ones(len(x)),x,np.tanh(x@h.T+hb)]
    penalty=np.diag([1.2]+[3.]*(ph.shape[1]-1))
    beta=np.linalg.solve(ph.T@(w[:,None]*ph)+penalty,ph.T@(w*y))
    m=dict(bias=beta[0],linear=beta[1:1+x.shape[1]].tolist(),hidden=h.tolist(),hb=hb.tolist(),head=beta[1+x.shape[1]:].tolist())
    return m,dict(input=len(samples),unique=len(rows),openings=len(counts),positive=int((y>0).sum()),negative=int((y<0).sum()),
                  rms=float(np.average((ph@beta-y)**2,weights=w)**.5))

def paired(groups,side):
    sample=next(iter(groups.values()))
    return paired_result(groups,side,[a.uid for a,_ in sample])

def flat(groups):
    return [g for rs in groups.values() for pair in rs for g in pair]

def rival_groups(ids,path):
    return {o:[(game(i,p,PARENT,binary=DEPLOY),game(i,p,path,binary=DEPLOY)) for i in ids] for o,p in PLANTS.items()}

def rank(rep):
    rows=rep['rows'];lost=sum(r['old']==1 and r['new']!=1 for r in rows)
    true=sum(r['old']==-1 and r['new']==1 for r in rows)
    net=sum((r['new']==1)-(r['old']==1) for r in rows)
    worst=min(v['after'][0]-v['before'][0] for v in rep['per_opponent'].values())
    return (-lost,true,worst,net,-sum(r['stall'] for r in rows))

def train_zombie():
    if not (OUT/'ready.json').exists():ready()
    m,f=learning_rows()
    visited(m,f)
    m,f=learning_rows(with_visited=True)
    gate,gs=fit(m);front,fs=fit(f)
    twins=[]
    for _,_,_,prior in cases('review')[::6]:
        for ref in prior:
            twins.append((ref,replace(ref,binary=DEPLOY,storage=OUT)))
    batch('unmodified policies on final native runtime',[b for _,b in twins])
    for a,b in twins:assert trace(a)['log_sha256']==trace(b)['log_sha256']
    fixed(OUT/'live-parity.json',dict(pairs=[[a.key(),b.key()] for a,b in twins],binary=sha(DEPLOY)))
    ids=read(OUT/'splits.json')['val'];paths={};reports={};ext=[]
    for tag,margin,site in [('responsive',.00,.10),('guarded',.22,.33),('selective',.42,.50)]:
        paths[tag]=model('gate-'+tag,dict(start='old',gate=gate,front=front,margin=margin,front_margin=site,adaptive=True))
    groups={k:rival_groups(ids,p) for k,p in paths.items()}
    batch('validation against three fixed plant opponents',[g for gr in groups.values() for g in flat(gr)])
    for tag,gr in groups.items():
        reports[tag]=paired(gr,'zombie')
        ext.extend((a,b,'zombie') for rs in gr.values() for a,b in rs)
    historical=cases('review')+cases('positive')
    reviews={tag:[(i,o,old,ev,replace(old,policy=p,binary=DEPLOY)) for i,o,(old,ev),_ in historical] for tag,p in paths.items()}
    batch('training regressions for all thresholds before unsealing new openings',[b for rs in reviews.values() for *_,b in rs])
    history={}
    for tag,rs in reviews.items():
        rows=[dict(id=i,opponent=o,old=outcome(trace(a),'zombie'),previous=outcome(trace(e),'zombie'),
            new=outcome(trace(b),'zombie'),key=b.key()) for i,o,a,e,b in rs]
        by_open=defaultdict(list)
        for r in rows:
            if r['old']==1:by_open[r['id']].append(int(r['new']==1))
        history[tag]=dict(rows=rows,opening_retention=float(np.mean([np.mean(v) for v in by_open.values()])),
            kept=sum(r['old']==r['new']==1 for r in rows),true_gains=sum(r['old']==-1 and r['new']==1 for r in rows))
        ext.extend((a,b,'zombie') for _,_,old,ev,b in rs for a in (old,ev))
    def selection(tag):
        base=rank(reports[tag]);h=history[tag];valid=reports[tag]['rows']
        nwin=sum(r['old']==1 for r in valid);keep=1+base[0]/max(1,nwin)
        return (min(keep,h['opening_retention']),keep,h['opening_retention'],base[1],h['true_gains'],*base[2:])
    winner=max(paths,key=selection)
    fixed(OUT/'zombie.json',dict(selected=winner,path=str(paths[winner]),sha256=sha(paths[winner]),
        gate=gs,front=fs,validation=reports,regression_training=history,extensions=extend(ext),order='worst retention across fresh validation and opening-weighted previous regressions, validation retention, review retention, validation true gains, old true gains, then worst opponent and tempo'))

def plant_pairs(ids,p,z):
    return dict(frozen=[(game(i,STRONG,z,binary=ARRIVAL),game(i,p,z,binary=ARRIVAL)) for i in ids],
                r22=[(game(i,STRONG,None,zombie=None,position=None,binary=ARRIVAL),game(i,p,None,zombie=None,position=None,binary=ARRIVAL)) for i in ids])

def train_plant():
    if not (OUT/'zombie-selected.json').exists():refine_arrival()
    lock=read(OUT/'zombie-selected.json');z=Path(lock['path']);assert sha(z)==lock['sha256']
    split=read(OUT/'splits.json')
    previous=read(PREVIOUS/'models/plant-along-p.json');parent=read(STRONG)
    w=np.array(parent['heads']['weight'])[:12,-28:]
    direction=np.array(previous['heads']['weight'])[:12,-28:]-w
    rng=np.random.default_rng(421005);alt=rng.normal(size=w.shape)
    alt-=np.sum(alt*direction)/np.sum(direction**2)*direction
    alt*=np.linalg.norm(direction)/np.linalg.norm(alt)
    paths={}
    for nm,d in [('along',direction),('across',alt)]:
        for sign,tag in [(1,'p'),(-1,'m')]:
            m=read(STRONG)
            for j,row in enumerate(w+sign*.65*d):m['heads']['weight'][j][-28:]=row.tolist()
            m['training_source']=dict(parent=sha(STRONG),frozen_zombie=sha(z),method='paired native returns on fixed-zombie and r22 games')
            p=OUT/'models'/f'plant-{nm}-{tag}.json';fixed(p,m);paths[nm+tag]=p
    train={k:plant_pairs(split['train'],p,z) for k,p in paths.items()}
    batch('reverse sides: plant training against frozen zombie and r22',[g for gr in train.values() for g in flat(gr)])
    reports={k:paired(gr,'plant') for k,gr in train.items()}
    selected=sorted(paths,key=lambda k:rank(reports[k]),reverse=True)[:2]
    val={k:plant_pairs(split['val'],paths[k],z) for k in selected}
    batch('plant validation',[g for gr in val.values() for g in flat(gr)])
    validation={k:paired(gr,'plant') for k,gr in val.items()}
    win=max(selected,key=lambda k:rank(validation[k]))
    ext=extend((a,b,'plant') for table in (train,val) for gr in table.values() for rs in gr.values() for a,b in rs)
    fixed(OUT/'plant.json',dict(selected=win,path=str(paths[win]),sha256=sha(paths[win]),zombie=sha(z),training=reports,validation=validation,extensions=ext))
def visited(m,f):
    """One on-policy data aggregation pass before selecting thresholds on validation."""
    gate,_=fit(m);front,_=fit(f)
    policy=model('aggregation',dict(start='old',gate=gate,front=front,margin=.15,front_margin=.22))
    encounters=cases('review')+cases('positive')+cases('fresh')
    records=[]
    for i,o,(old,_),_ in encounters:
        candidate=replace(old,policy=policy)
        records.append((i,o,old,candidate))
    batch('on-policy training switches on old wins, gains and fixed-plant starts',[b for _,_,_,b in records])
    selected=[]
    for i,o,old,candidate in records:
        decisions=[e for e in trace(candidate)['switches'] if e['phase']=='decision']
        assert len(decisions)<=1
        if not decisions:
            assert trace(old)['log_sha256']==trace(candidate)['log_sha256']
            continue
        ev=decisions[0]
        root=replace(old,policy=model('old-short',dict(start='old')),after=ev['t'])
        gs=[replace(root,forced=n) for n in range(ev['choice']+1)]
        selected.append((i,o,old,candidate,ev,gs))
    batch('counterfactuals at the switches the fitted network actually takes',[g for *_,gs in selected for g in gs])
    ext=extend((a,b,'zombie') for *_,gs in selected for a in gs for b in gs if a!=b)
    rows=[]
    for i,o,old,candidate,ev,gs in selected:
        es=[trace(g)['switches'][0] for g in gs]
        assert len({e['prefix'] for e in es})==1
        assert all(e['state']==ev['state'] and e['front']==ev['front'] for e in es)
        assert trace(old)['log_sha256']==trace(gs[0])['log_sha256']
        assert trace(candidate)['log_sha256']==trace(gs[-1])['log_sha256']
        rows.append(dict(id=i,opponent=o,corpus='fresh' if old.corpus==CORPUS else 'previous',mask=ev['mask'],t=ev['t'],choice=ev['choice'],
                         state=ev['state'],site=ev['site'],front=ev['front'],keys=[g.key() for g in gs],results=[outcome(trace(g),'zombie') for g in gs],
                         slow=[slow(trace(gs[0]),trace(g)) for g in gs],prefix=es[0]['prefix']))
    fixed(OUT/'visited.json',dict(scans=len(records),rows=rows,extensions=ext))
def test():
    split=read(OUT/'splits.json')
    zl,pl=[read(OUT/(s+'.json')) for s in ('final-zombie','final-plant')]
    z,p,active=Path(zl['path']),Path(pl['path']),Path(zl['active'])
    assert sha(active)==zl['active_sha']==pl['active']
    assert sha(z)==pl['zombie']==zl['sha256'] and sha(p)==pl['sha256']
    ids=split['a']+split['b'];comparisons={}
    # Every new blind encounter starts only after both neural checkpoints are fixed.
    for label in ('z16','previous_event','plant')+(('active',) if active!=z else ()):
        gr={}
        for o in 'rhb':
            opponent=MODELS[o]
            if label=='plant':
                gr[o]=[(game(i,STRONG,None,zombie=opponent,position=None,binary=CONTEXT),game(i,p,None,zombie=opponent,position=None,binary=CONTEXT)) for i in ids]
            else:
                gr[o]=[(game(i,opponent,EVENT if label=='previous_event' else PARENT,binary=CONTEXT),game(i,opponent,active if label=='active' else z,binary=CONTEXT)) for i in ids]
        comparisons[label]=gr
    batch('two sealed home cohorts, r22/H/B, both sides and previous event zombie',[g for gr in comparisons.values() for g in flat(gr)])
    reports={};extensions=[]
    for label,gr in comparisons.items():
        side='plant' if label=='plant' else 'zombie'
        report={}
        for k,subset in [('a',split['a']),('b',split['b']),('all',ids)]:
            local={o:[(a,b) for a,b in gs if a.uid in subset] for o,gs in gr.items()}
            report[k]=paired(local,side)
            rr=report[k]['rows']
            change=np.array([np.mean([int(r['new']==1)-int(r['old']==1) for r in rr if r['id']==i]) for i in subset])
            rng=np.random.default_rng(61817)
            report[k]['true_win_rate_delta95']=np.quantile(change[rng.integers(0,len(change),(20000,len(change)))].mean(axis=1),[.025,.975]).tolist()
        rows=report['all']['rows'];tempo=report['all']['tempo']
        both_slower=all(tempo['candidate']['common_window_deploys_per_min'][s]<tempo['parent']['common_window_deploys_per_min'][s] for s in ('plant','zombie'))
        report['stable']=bool(not both_slower and not any(r['stall'] or (r['old']==1 and r['new']!=1) for r in rows)
             and report['all']['paired_mean95'][0]>0 and report['all']['true_win_rate_delta95'][0]>0 and all(sum(r['new']==1 for r in report[k]['rows'])>sum(r['old']==1 for r in report[k]['rows'])
             and min(v['net'] for v in report[k]['per_opponent'].values())>=0 for k in ('a','b')))
        report['ordinary_draws']=[sum(not trace(pair[j])['timeout'] and outcome(trace(pair[j]),side)==0 for gs in gr.values() for pair in gs) for j in (0,1)]
        both_less=[r for r in rows if all(r['tempo'][s][1]['deploys']<r['tempo'][s][0]['deploys'] for s in ('plant','zombie'))]
        kept=[r for r in rows if r['old']==r['new']==1]
        report['tempo_detail']=dict(both_fewer_deploys_on_common_window=len(both_less),
            both_fewer_in_loss_to_win=sum(r['old']==-1 and r['new']==1 for r in both_less),
            stall_loss_to_timeout=sum(r['stall'] for r in rows), old_wins_kept=len(kept),
            median_duration_kept=([float(np.median([r[k] for r in kept])) for k in ('old_end','new_end')] if kept else []))
        reports[label]=report
        ex=extend((a,b,side) for gs in gr.values() for a,b in gs)
        extensions.extend(dict(comparison=label,**e) for e in ex)
    decisions=[]
    for tag in ('z16','active'):
        if tag not in comparisons:continue
        for o,gs in comparisons[tag].items():
            for a,b in gs:
                tr=trace(b);ev=tr['switches'];d=[v for v in ev if v['phase']=='decision']
                decisions.append(dict(comparison=tag,id=b.uid,opponent=o,legacy_triggers=len(trace(a)['options']),post_handoff_events=sum(bool(v.get('mask',0)&15) for v in tr['options']),choice=d[0]['choice'] if d else 0,time=d[0]['t'] if d else None,
                    mask=d[0]['mask'] if d else None,old=outcome(trace(a),'zombie'),new=outcome(tr,'zombie'),
                    built=any(e['phase']=='built' for e in ev),grave=any(e['phase']=='grave' for e in ev),
                    arrival_choices=sum(e['phase']=='arrival_vote' for e in ev),arrival_deferred=sum(e['phase']=='arrival_vote' and not e['place'] for e in ev),new_trips=sum(e['phase']=='start_trip' for e in ev),canceled=sum(e['phase']=='cancel_trip' for e in ev),kept=sum(e['phase']=='keep_trip' for e in ev),active_transfer=d[0]['choice'] if d and trace(a)['log_sha256']!=tr['log_sha256'] else 0))
    fixed(OUT/'test.json',dict(zombie=sha(z),active=sha(active),plant=sha(p),results=reports,decisions=decisions,extensions=extensions))
    regression(z)

def regression(z):
    cases0=cases('review')+cases('positive');groups=[]
    for i,o,(old,ev),_ in cases0:
        groups.append((i,o,old,ev,replace(old,policy=z,binary=CONTEXT)))
    batch('exact old-wins and old-losses regression after freezing the model',[b for *_,b in groups])
    rows=[]
    for i,o,old,ev,b in groups:
        switch=[e for e in trace(b)['switches'] if e['phase']=='decision']
        rows.append(dict(id=i,opponent=o,z16=outcome(trace(old),'zombie'),event=outcome(trace(ev),'zombie'),new=outcome(trace(b),'zombie'),
             first_handoff=switch[0]['t'] if switch else None,choice=switch[0]['choice'] if switch else 0,key=b.key()))
    ex=extend((a,b,'zombie') for _,_,old,ev,b in groups for a in (old,ev))
    fixed(OUT/'regression.json',dict(rows=rows,extensions=ex))

def audit(final=False):
    if not (OUT/'sealed-routes.json').exists():blind_routes()
    from option_audit import verify_games
    from switch_study import ROOT,R,size,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR,LIMIT
    index,limits=verify_games(OUT,expected_map='家院')
    material=read(OUT/'build.json')
    assert sha(NATIVE)==material['binary']
    for name,h in material['sources'].items():assert sha(OUT/'native-src'/name)==h
    for name,h in material['libraries'].items():assert sha(BUILD/'Release'/name)==h
    live=read(OUT/'live-build.json');assert sha(DEPLOY)==live['binary']
    for name,h in live['sources'].items():assert sha(OUT/'live-src'/name)==h
    from switch_study import WALK
    for label,src,exe in [('walk-build','walk-src',WALK),('arrival-build','arrival-src',ARRIVAL),('context-build','context-src',CONTEXT)]:
        rr=read(OUT/(label+'.json'));assert sha(exe)==rr['binary']
        for name,h in rr['sources'].items():assert sha(OUT/src/name)==h
    release=read(R/'dist/latest-native-release.json');assert sha(Path(release['target']))==release['exe_sha256']
    total=sum(size(d) for d in (ROOT,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR))
    assert total<LIMIT and read(OUT/'disk.json')['peak']<LIMIT
    styles={}
    for i in read(OUT/'splits.json')['train']:
        programs={}
        for o,p in PLANTS.items():
            a,_=scan(i,p,CORPUS);tr=trace(a)
            programs[o]=[[e['card'],e['time']] for e in tr['activity'] if e['kind']=='deploy' and e['side']=='plant']
        differences={}
        for a,b in (('p','o'),('p','r'),('o','r')):
            pairs=zip(programs[a],programs[b])
            first=next((j for j,(old,new) in enumerate(pairs) if old!=new),min(len(programs[a]),len(programs[b])))
            differences[a+b]=dict(distinct=programs[a]!=programs[b],common_prefix=first,
                first_a=programs[a][first] if first<len(programs[a]) else None,first_b=programs[b][first] if first<len(programs[b]) else None)
        styles[i]=differences
    fixed(OUT/'plant-styles.json',dict(models={o:sha(p) if p else 'r22' for o,p in PLANTS.items()},rows=styles))
    from switch_study import deck
    split=read(OUT/'splits.json');entries=read(CORPUS/'index.json')['entries']
    assert sha(CORPUS/'index.json')==split['corpus'] and len(entries)==40
    seen=[set(),set()];known_seeds=set()
    for path in split['indexes']:
        for r in read(R/path)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                known_seeds.add(r['seed'])
                for a,b in zip(seen,deck(r)):a.add(b)
    assert [len(v) for v in seen]==split['excluded']
    assert not {r['seed'] for r in entries}&known_seeds and len({r['seed'] for r in entries})==40
    for j in range(2):
        assert len({deck(r)[j] for r in entries})==40
        assert not {deck(r)[j] for r in entries if r['id'] in split['a']+split['b']}&seen[j]
    for cohort in ('a','b'):
        subset=[r for r in entries if r['id'] in split[cohort]]
        assert len(subset)==12 and sum(bool(r['night']) for r in subset)==6
    groups={};checked_suffixes=set()
    for name in ('review','positive','fresh','front','walk','later','ready','visited','zombie','zombie-selected','plant','final-zombie','final-plant','test','regression','sealed-routes')+(('blind-horizons',) if final else ()):
        extensions=read(OUT/(name+'.json'))['extensions']
        for e in extensions:
            a,b=index[e['candidate']],index[e['extended']]
            assert {**a['parameters'],'limit':1200}==b['parameters'] and a['timeout']
            assert b['winner']==e['winner'] and b['timeout']==e['timeout'] and index[e['base']]['winner'] in ('plant','zombie')
            if e['extended'] not in checked_suffixes:
                import gzip
                records=[]
                for key in (e['candidate'],e['extended']):
                    with gzip.open(OUT/'games'/(key+'.jsonl.gz'),'rt',encoding='utf8') as f:
                        f.readline();records.append(json.loads(f.readline()))
                assert [x for x in records[0].get('switches',[]) if x['t']<600]==[x for x in records[1].get('switches',[]) if x['t']<600]
                checked_suffixes.add(e['extended'])
        groups[name]=len({e['extended'] for e in extensions})
    roots=(ROOT,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR)
    before_alloc=allocated(roots);assert before_alloc<LIMIT
    assert len(checked_suffixes)==limits[1200]
    cleanup=OUT/'disk-cleanup.json'
    if not cleanup.exists():
        removed={}
        for stage in ('native','live','walk','arrival','context'):
            obj=(OUT/stage/'position_match.dir'/'Release').resolve()
            assert obj.is_relative_to(OUT.resolve())
            for name in ('position_match.obj','tactical_session.obj'):
                path=obj/name
                if path.is_file():
                    removed[str(path.relative_to(OUT))]=path.stat().st_size;path.unlink()
        fixed(cleanup,dict(rebuildable_objects=removed,bytes=sum(removed.values())))
    for raw in (OUT/'temp').glob('*.jsonl'):
        # A Windows sharing delay may leave the raw file after the verified
        # compressed receipt. Only discard a byte-identical temporary duplicate.
        import gzip
        key=raw.stem
        if key in index and raw.read_bytes()==gzip.decompress((OUT/'games'/(key+'.jsonl.gz')).read_bytes()):raw.unlink()
    assert not list((OUT/'temp').glob('*.jsonl'))
    after_alloc=allocated(roots);assert after_alloc<LIMIT
    if not (OUT/'allocation.json').exists():fixed(OUT/'allocation.json',dict(before_cleanup=before_alloc,after_cleanup=after_alloc,cap=LIMIT))
    if final:fixed(OUT/'final-allocation.json',dict(after_cleanup=after_alloc,cap=LIMIT))
    fixed(OUT/('final-audit.json' if final else 'audit.json'),dict(games=len(index),limits=dict((str(k),v) for k,v in limits.items()),extensions=groups,
         official=release['version'],official_sha=release['exe_sha256'],source_build=sha(OUT/'build.json'),
         overnight_frozen_kernel=material['libraries'],verified='native headers, planners, controls, map, full trace hashes, model checksums, 600/1200 receipts'))

def walk_control():
    from switch_study import WALK
    source=read(OUT/'front.json')['rows'] if (OUT/'front.json').exists() else front(roots_only=True)
    files={sha(p):p for p in (OUT/'models').glob('front-*.json')}
    groups=[]
    for r in source:
        built=next((e for e in r['phases'][1] if e['phase']=='built'),None)
        # All realized builds, plus the one winning trip without a build as a parity control.
        if not built and not (r['results'][1]==1 and r['results'][0]!=1):continue
        cfg=read(OUT/'games'/(r['keys'][1]+'.jsonl.receipt.json'))['parameters']
        a=game(r['id'],MODELS[r['opponent']],files[cfg['policy']],OLD_CORPUS,forced=2,after=cfg['after'])
        assert a.key()==r['keys'][1]
        groups.append((r,a,replace(a,binary=WALK,forced=4),built))
    batch('matched journey with the arrival build omitted',[b for _,_,b,_ in groups])
    rows=[]
    for r,a,b,built in groups:
        s=trace(a);t=trace(b);stamp=t['switches'][0]
        assert stamp['prefix']==r['prefix'] and stamp['front']==r['target']
        skipped=next((e for e in t['switches'] if e['phase']=='omit_build'),None)
        if built:
            assert skipped and built['t']==skipped['t'] and built['target']==skipped['target'] and built['move_tiles']==skipped['move_tiles']
            for k,timekey in [('spatial_actions','t'),('accepted_commands','time'),('activity','time')]:
                # Native input telemetry rounds to 4 decimals. Use integer logic ticks.
                tick=round(30*built['t'])
                assert [v for v in s[k] if round(30*v[timekey])<tick]==[v for v in t[k] if round(30*v[timekey])<tick]
            gc=lambda g:[x for x in g['accepted_commands'] if x['accepted'] and x['kind']=='deploy' and x['card']==r['target'][1] and
                        x['x']==r['target'][3] and x['y']==r['target'][4] and round(30*x['time'])==tick]
            assert gc(s) and not gc(t)
        else:assert s['log_sha256']==t['log_sha256']
        rows.append(dict(id=r['id'],opponent=r['opponent'],t=r['t'],prefix=r['prefix'],distance=r['distance'],target=r['target'],
             arrival=skipped,results=[*r['results'],outcome(t,'zombie')],keys=[*r['keys'],b.key()]))
    ex=extend((m,n,'zombie') for _,a,b,_ in groups for m,n in ((a,b),(b,a)))
    fixed(OUT/'walk.json',dict(rows=rows,extensions=ex))
def ready():
    split=read(OUT/'splits.json');roots=[]
    for j,i in enumerate(split['train']):
        for k,o in enumerate(('p','o')):
            ref,_=scan(i,PLANTS[o],CORPUS)
            events=[e for e in trace(ref)['spatial_actions'] if e['kind']=='build']
            if not events:continue
            # Select the pre-payment state of a real legal placement. With the
            # same card still affordable this can expose forward play on z16 paths.
            goal=(20,80,155)[(j+k)%3];e=min(events,key=lambda a:abs(a['t']-goal))
            a=replace(ref,policy=model('old-short',dict(start='old')),forced=0,after=e['t'])
            roots.append((i,o,ref,a))
    batch('pre-payment placements on the frozen z16 trajectory',[a for *_,a in roots])
    groups=[]
    for i,o,ref,a in roots:
        assert trace(ref)['log_sha256']==trace(a)['log_sha256']
        m=trace(a)['switches'][0]
        gs=[a,replace(a,forced=1)]
        if m['front'] is not None:gs.append(replace(a,forced=2))
        groups.append((i,o,m,gs))
    batch('compare spending at once, handoff, and traveling before spending',[g for *_,gs in groups for g in gs[1:]])
    rows=[]
    for i,o,m,gs in groups:
        traces=[trace(g) for g in gs]
        assert all(t['switches'][0]['prefix']==m['prefix'] for t in traces)
        rows.append(dict(id=i,opponent=o,mask=m['mask'],t=m['t'],state=m['state'],site=m['site'],front=m['front'],
                         results=[outcome(t,'zombie') for t in traces],keys=[g.key() for g in gs],prefix=m['prefix'],
                         slow=[slow(traces[0],t) for t in traces]))
    extend_rows=extend((a,b,'zombie') for *_,gs in groups for a in gs for b in gs if a!=b)
    fixed(OUT/'ready.json',dict(rows=rows,extensions=extend_rows))
def refine_arrival():
    from switch_study import ARRIVAL
    prev=read(OUT/'zombie.json');parent=Path(prev['path'])
    refs={r['prefix']:r for r in read(OUT/'front.json')['rows']}
    data=read(OUT/'walk.json');tails={(e['base'],e['candidate']):e for e in data['extensions']};samples=[]
    for r in data['rows']:
        arrival=r['arrival']
        if not arrival:continue
        root=refs[r['prefix']]
        x=root['site']+[float(np.tanh((arrival['t']-r['t'])/5)),float(np.tanh(arrival['move_tiles']/8))]
        def value(j,k):
            outcome0=r['results'][j]
            if outcome0:return float(outcome0)
            if r['results'][k]!=-1:return -.45
            e=tails.get((r['keys'][k],r['keys'][j]))
            return .55 if e and e['winner']=='zombie' and not e['joint_idle'] else -1.
        samples.append((r['id'],r['prefix'],x,value(1,3)-value(3,1)))
    head,info=fit(samples)
    paths={k:model('arrival-'+k,{**read(parent)['switch'],'arrival':head,'arrival_margin':margin})
           for k,margin in [('guarded',.14),('responsive',.025)]}
    ids=read(OUT/'splits.json')['val'];history=cases('review')+cases('positive')
    bases=rival_groups(ids,parent)
    records=[(i,o,old,ev,replace(old,policy=parent,binary=DEPLOY)) for i,o,(old,ev),_ in history]
    universe=list(dict.fromkeys([b for rs in bases.values() for _,b in rs]+[b for *_,b in records]))
    active=[g for g in universe if any(e['phase']=='built' for e in trace(g)['switches'])]
    twins=list(dict.fromkeys(universe[:1]+active[:1]+universe[-1:]))
    batch('arrival runtime with previous weights',[replace(g,binary=ARRIVAL) for g in twins])
    assert all(trace(g)['log_sha256']==trace(replace(g,binary=ARRIVAL))['log_sha256'] for g in twins)
    def alternate(g,k):
        # Before the first legal arrival this readout cannot
        # change any native command. Blind testing always runs the full game.
        return replace(g,policy=paths[k],binary=ARRIVAL) if g in active else g
    batch('arrival decisions on reachable training and validation states',[alternate(g,k) for k in paths for g in active])
    reports={'parent':prev['validation'][prev['selected']]};historical={'parent':prev['regression_training'][prev['selected']]};ext=[]
    for k in paths:
        gr={o:[(a,alternate(b,k)) for a,b in rs] for o,rs in bases.items()}
        reports[k]=paired(gr,'zombie')
        ext.extend((a,b,'zombie') for rs in gr.values() for a,b in rs)
        rows=[];by_open=defaultdict(list)
        for i,o,a,e,ref in records:
            b=alternate(ref,k);v=outcome(trace(a),'zombie');n=outcome(trace(b),'zombie')
            rows.append(dict(id=i,opponent=o,old=v,previous=outcome(trace(e),'zombie'),new=n,key=b.key()))
            if v==1:by_open[i].append(int(n==1))
            ext.extend([(a,b,'zombie'),(e,b,'zombie')])
        historical[k]=dict(rows=rows,kept=sum(r['old']==r['new']==1 for r in rows),true_gains=sum(r['old']==-1 and r['new']==1 for r in rows),
            opening_retention=float(np.mean([np.mean(v) for v in by_open.values()])))
    def selection(k):
        base=rank(reports[k]);h=historical[k];nwin=sum(r['old']==1 for r in reports[k]['rows'])
        keep=1+base[0]/max(1,nwin)
        return min(keep,h['opening_retention']),keep,h['opening_retention'],base[1],h['true_gains'],*base[2:]
    win=max([*paths,'parent'],key=selection);p=parent if win=='parent' else paths[win]
    fixed(OUT/'zombie-selected.json',dict(path=str(p),sha256=sha(p),selected=win,parent=sha(parent),model=info,validation=reports,
         regression_training=historical,active=len(active),denominator=len(universe),runtime_parity=[g.key() for g in twins],extensions=extend(ext)))
def allocated(dirs):
    """Read the native allocation size once per file identity on this NTFS volume."""
    import ctypes
    import msvcrt
    from ctypes import wintypes
    class Standard(ctypes.Structure):
        _fields_=[('allocation',ctypes.c_int64),('end',ctypes.c_int64),('links',wintypes.DWORD),
                  ('deleted',ctypes.c_ubyte),('directory',ctypes.c_ubyte)]
    query=ctypes.WinDLL('kernel32',use_last_error=True).GetFileInformationByHandleEx
    query.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];query.restype=wintypes.BOOL
    seen=set();total=0
    for d in dirs:
        for p in d.rglob('*'):
            if p.parent==OUT and p.name.startswith('disk.json.tmp-'):continue
            if not p.is_file():continue
            st=p.stat();key=(st.st_dev,st.st_ino)
            if key in seen:continue
            seen.add(key)
            with p.open('rb') as f:
                info=Standard()
                if not query(msvcrt.get_osfhandle(f.fileno()),1,ctypes.byref(info),ctypes.sizeof(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
            total+=info.allocation
    return total
def blind_routes():
    """At actual held-out trips, substitute ordinary event play at one decision."""
    zl=read(OUT/'final-zombie.json');path=Path(zl['active']);assert sha(path)==zl['active_sha']
    split=read(OUT/'splits.json');possible=defaultdict(list)
    for i in split['a']+split['b']:
        for o in 'rhb':
            a=game(i,MODELS[o],path,binary=CONTEXT)
            for ev in trace(a)['switches']:
                if ev['phase']=='start_trip' or (ev['phase']=='decision' and ev['choice']==2):
                    if ev['mask']&15:
                        possible[o].append((i,ev['t'],a,ev.get('target',ev.get('front'))))
    used=set();groups=[]
    for _ in range(2):
        for o in 'rhb':
            opts=[x for x in possible[o] if x[0] not in used]
            if not opts:continue
            i,t,orig,target=min(opts,key=lambda x:(abs(x[1]-90),x[0],x[1]))
            used.add(i);groups.append((i,o,t,target,orig,replace(orig,forced=2,after=t),replace(orig,forced=1,after=t)))
    batch('one held-out trip vs ordinary event play at the same root',[g for *_,a,b in groups for g in (a,b)])
    rows=[]
    for i,o,t,target,original,a,b in groups:
        x,y=trace(a),trace(b)
        es=[next(e for e in tr['switches'] if 'prefix' in e) for tr in (x,y)]
        assert es[0]['prefix']==es[1]['prefix'] and es[0]['front']==target and all(round(30*e['t'])==round(30*t) for e in es)
        assert x['log_sha256']==trace(original)['log_sha256']
        following=[e for e in x['switches'] if e['t']>=t and e['phase'] in ('built','cancel_trip','expired','arrival_vote')]
        rows.append(dict(id=i,opponent=o,t=t,target=target,prefix=es[0]['prefix'],travel=outcome(x,'zombie'),ordinary=outcome(y,'zombie'),
               distinct=x['log_sha256']!=y['log_sha256'],next=following[0] if following else None,keys=[a.key(),b.key()]))
    ex=extend((u,v,'zombie') for *_,a,b in groups for u,v in ((a,b),(b,a)))
    fixed(OUT/'sealed-routes.json',dict(model=sha(path),eligible=sum(map(len,possible.values())),rows=rows,extensions=ex))
def blind_horizons():
    z=read(OUT/'final-zombie.json');pl=Path(read(OUT/'final-plant.json')['path'])
    primary,active=Path(z['path']),Path(z['active'])
    ids=read(OUT/'splits.json')['a']+read(OUT/'splits.json')['b']
    cases0=[];against=defaultdict(list)
    for i in ids:
        for o in 'rhb':
            opp=MODELS[o]
            old=game(i,opp,PARENT,binary=CONTEXT);previous=replace(old,policy=EVENT)
            safe=replace(old,policy=primary);new=replace(old,policy=active)
            plant=game(i,STRONG,None,zombie=opp,position=None,binary=CONTEXT)
            pairs=[('z16','zombie',old,safe),('active','zombie',old,new),('plant','plant',plant,replace(plant,plant=pl)),
                   ('previous_event','zombie',previous,safe),('active_previous_event','zombie',previous,new)]
            against[o].append((previous,new))
            for label,side,a,b in pairs:
                if not trace(b)['timeout'] or outcome(trace(a),side)==0:continue
                lost='plant' if trace(a)['result']['winner']=='zombie' else 'zombie'
                cases0.append((label,side,o,a,b,lost))
    ex=extend((a,b,lost) for _,_,_,a,b,lost in cases0)
    assert len(cases0)==len(ex)
    rows=[dict(comparison=label,side=side,opponent=o,id=a.uid,old=outcome(trace(a),side),new=0,late=outcome(trace(replace(b,limit=1200)),side),
               end=e['end'],timeout=e['timeout'],extended=e['extended']) for (label,side,o,a,b,_),e in zip(cases0,ex)]
    fixed(OUT/'blind-horizons.json',dict(rows=rows,extensions=ex,active_previous=paired(against,'zombie')))
