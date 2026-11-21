"""Two-population evolution with frozen opponents, a fixed r22 anchor and exploratory lineages."""
import copy
import gzip
import json
import math
import os
import time
from pathlib import Path

import numpy as np
from league_data import *
from league_matches import R22,Matches,pairs,evaluate

SIDES=('zombie','plant')
START={'plant':str(P_START),'zombie':str(Z_START)}
ANCHOR={'plant':str(PLANT),'zombie':str(PARENT)}
REPLAY_BASE={'plant':str(STRONG),'zombie':str(LAST_Z)}

def other(side):return 'plant' if side=='zombie' else 'zombie'

def unique(items):return list(dict.fromkeys(items))

def initial():
    return dict(round=0,completed_rounds=0,games_database='matches.sqlite',sides={
        s:dict(champ=START[s],explorer=str(Z_ACTIVE if s=='zombie' else PLANT),hall=[START[s]],
               defenses=0,temp=1.,promotions=0,last_suites=[]) for s in SIDES})

def state():
    p=RUN/'state.json'
    return read(p) if p.exists() else initial()

def mutate(side,source,generation,slot,temp):
    # Antithetic siblings share a mask and perturbations. Two additional children
    # can explore from lineages that won new matchups before winning the league.
    seed=831119+generation*1601+(0 if side=='zombie' else 571)+[0,0,27,53][slot]
    rng=np.random.default_rng(seed);sign=-1. if slot==1 else 1.
    d=read(Path(source));fraction=max(.035,.27*temp);amp=max(.10,.80*temp)
    changed=0
    def perturb(obj,k,floor,gain=1.,full=False):
        nonlocal changed
        v=np.asarray(obj[k],dtype=float);a=v.copy().reshape(-1)
        n=len(a) if full else max(1,int(round(len(a)*fraction)))
        idx=rng.choice(len(a),n,replace=False)
        scale=max(floor,float(np.sqrt(np.mean(a*a))))
        a[idx]+=sign*amp*gain*scale*np.clip(rng.normal(size=n),-2.5,2.5)
        obj[k]=a.reshape(v.shape).tolist()
        assert np.isfinite(a).all()
        changed+=n
    if side=='zombie':
        cfg=d['switch']
        for key in ('one_head','trip_head','arrival_live'):
            m=cfg[key]
            for k,floor in [('linear',.09),('hidden',.15),('hb',.15),('head',.12),('bias',.38)]:
                perturb(m,k,floor)
        for k,floor in [('event_hidden',.22),('event_head',.24),('event_bias',.15),('scale',.30)]:perturb(d,k,floor)
        for k in ('one_margin','trip_margin','arrival_margin'):
            perturb(cfg,k,.55 if k!='arrival_margin' else .25)
            if slot==3 and k!='arrival_margin':cfg[k]-=.45*temp
            cfg[k]=float(np.clip(cfg[k],-2.5,3.))
        cfg['sample']=False
        if 'native_gate' in cfg:
            for k,floor in [('linear',.10),('hidden',.20),('hidden_bias',.12),('head',.15),('bias',.35)]:
                perturb(cfg['native_gate'],k,floor)
    else:
        for layer,gain in [('unit',.6),('body',.65),('heads',1.)]:
            for key,floor in [('weight',.075),('bias',.12)]:
                perturb(d[layer],key,floor,gain)
    path=RUN/'models'/f'{generation:04d}-{side}-{slot}.json'
    desc=dict(seed=seed,parent=str(source),parent_sha=sha(Path(source)),slot=slot,round=generation,temperature=temp,
              fraction=fraction,amplitude=amp,changed=changed)
    d['league_mutation']=desc
    if path.exists():
        if read(path)!=d:raise RuntimeError('Non-deterministic resumed mutation')
    else:write(path,d)
    return str(path),desc

def cases_for(gen):
    fresh=read(RUN/'fixtures.json');old=read(PRIOR_RUN/'split.json');sample=read(PRIOR_RUN/'screen.json')
    rng=np.random.default_rng(5171+gen*119)
    def choose(items,n):
        return [items[int(j)] for j in rng.choice(len(items),n,replace=False)]
    def cases(role,nfresh,nextra):
        pool=sample[role]
        selected=['old/'+i for v in (1,-1) for i in choose([r['id'] for r in pool if r['result']==v],3 if role=='val' else 1)]
        selected+=choose(['old/'+i for i in old[role+'_pool'] if 'old/'+i not in selected],nextra)
        selected+=choose(['new/'+i for i in fresh['fresh_'+('train' if role=='train' else 'confirm')]],nfresh)
        return selected
    train=cases('train',2,0);confirm=cases('val',4,2)
    assert set(train).isdisjoint(confirm)
    return train,confirm

def history(st,side,gen):
    h=st['sides'][side]['hall']
    options=unique([ANCHOR[side],REPLAY_BASE[side],str(MODELS['h']),str(MODELS['b']),*h[:-1]])
    return options[(gen-1)%len(options)]

def choose_explorer(scored,champ):
    eligible=[m for m,r in scored.items() if r['changed'] and m!=champ]
    if not eligible:return None
    return max(eligible,key=lambda m:(scored[m]['gain']>0,scored[m]['gain']-.35*scored[m]['lost'],
                                      scored[m]['score'],scored[m]['changed']))

def passes(r,anchor):
    r22=r['by'][R22];n=len(r['rows'])
    own=r['rates']['troops' if r['side']=='zombie' else 'plant']
    forward=(r['new'][0]-r['old'][0]>=2 and r['gain']>=max(1,2*r['lost']) and r['lost']<=max(1,n//50))
    other_tempo=r['rates']['plant' if r['side']=='zombie' else 'troops']
    return bool((not r.get('protect_both_tempos') or other_tempo[1]>=.95*other_tempo[0])
        and forward and r['changed'] and r22[1][0]>=r22[0][0] and r['worst'][1]>=r['worst'][0]
        and own[1]>=own[0] and r['new'][1]<=r['old'][1] and r['seconds'][1]<=1.05*r['seconds'][0]
        and anchor['new'][0]>=anchor['old'][0] and anchor['speed']>=.97)

def update_champion(side,st,challenger,explorer,report,anchor,suite):
    new=copy.deepcopy(st);report['side']=side
    promoted=passes(report,anchor)
    if promoted:
        new['champ']=challenger;new['promotions']+=1;new['defenses']=0;new['last_suites']=[]
        new['hall']=unique(st['hall']+[challenger])[-5:]
    elif suite not in st['last_suites'] and report['changed']>=3 and report['old'][0]>=2 and report['new'][0]<=report['old'][0]:
        new['last_suites']=(st['last_suites']+[suite])[-12:]
        new['defenses']+=1
        if new['defenses']%3==0:new['temp']=max(.14,round(st['temp']*.72,5))
    if explorer and explorer!=new['champ']:new['explorer']=explorer
    return new,promoted

def save_detail(path,doc):
    raw=json.dumps(doc,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_bytes(gzip.compress(raw,compresslevel=5,mtime=0));os.replace(tmp,path)

def brief(report):
    return {k:v for k,v in report.items() if k not in ('rows','by')}

def round_worker(jobs):
    st=state();gen=st['round']+1;train,confirm=cases_for(gen);pop={};origins={}
    for side in SIDES:
        s=st['sides'][side];roots=[s['champ'],s['champ'],s['explorer'],str(Z_ACTIVE if side=='zombie' else PLANT) if gen%3==1 else s['explorer']]
        children=[mutate(side,p,gen,j,s['temp']) for j,p in enumerate(roots)]
        pop[side]=[m for m,_ in children];origins[side]=[v for _,v in children]
    store=Matches('train',jobs)
    table={}
    for side in SIDES:
        opp=other(side);champ=st['sides'][side]['champ']
        foes=unique([R22,st['sides'][opp]['champ'],history(st,opp,gen),*pop[opp]])
        for m in pop[side]:table[m]=(side,pairs(store,side,champ,m,foes,train))
    scores=evaluate(store,table,'population-crossplay')
    finalists={s:max(pop[s],key=lambda m:(scores[m]['changed']>0,scores[m]['score'],scores[m]['gain'])) for s in SIDES}
    validate={}
    for side in SIDES:
        opp=other(side);m=finalists[side]
        foes=unique([R22,st['sides'][opp]['champ'],history(st,opp,gen+1),finalists[opp],str(MODELS['h' if gen%2 else 'b'])])
        validate[side]=(side,pairs(store,side,st['sides'][side]['champ'],m,foes,confirm))
        validate[side+'-anchor']=(side,pairs(store,side,ANCHOR[side],m,[R22,st['sides'][opp]['champ']],confirm))
    vr=evaluate(store,validate,'independent-challenge')
    nxt=copy.deepcopy(st);nxt['round']=gen;nxt['completed_rounds']=st.get('completed_rounds',0)+1;changes={}
    for s in SIDES:
        explorer=choose_explorer({m:scores[m] for m in pop[s]},st['sides'][s]['champ'])
        nxt['sides'][s],changes[s]=update_champion(s,st['sides'][s],finalists[s],explorer,vr[s],vr[s+'-anchor'],'/'.join(sorted(confirm)))
    detail=RUN/'rounds'/f'{gen:04d}.json.gz'
    save_detail(detail,dict(gen=gen,train=train,confirm=confirm,origins=origins,screen=scores,validation=vr,finalists=finalists,changes=changes))
    nxt['last']=dict(time=local(time.time()),promotions=changes,validation={s:brief(vr[s]) for s in SIDES},record=str(detail),new_games=store.completed)
    write(RUN/'state.json',nxt)

def freeze():
    p=RUN/'frozen.json'
    if p.exists():return read(p)
    st=state()
    doc=dict(at=local(time.time()),round=st['round'],sides=st['sides'],fixtures=sha(RUN/'fixtures.json'))
    for s in SIDES:
        doc['sides'][s]['champ_sha']=sha(Path(doc['sides'][s]['champ']))
        doc['sides'][s]['explorer_sha']=sha(Path(doc['sides'][s]['explorer']))
    write(p,doc);return doc

def blind_worker(jobs):
    frozen=read(RUN/'frozen.json');f=read(RUN/'fixtures.json')
    assert sha(RUN/'fixtures.json')==frozen['fixtures'] and sha(NEW/'index.json')==f['fresh']
    cases=['new/'+i for i in f['blind']];store=Matches('blind',jobs)
    completed={}
    for mode in ('champ','explorer','start'):
        for side in SIDES:
            champ=frozen['sides'][side]['champ'];explorer=frozen['sides'][side]['explorer']
            assert sha(Path(champ))==frozen['sides'][side]['champ_sha'] and sha(Path(explorer))==frozen['sides'][side]['explorer_sha']
            m=explorer if mode=='explorer' else champ
            ref=START[side] if mode=='start' else ANCHOR[side]
            k=side+'-'+mode
            gr=pairs(store,side,ref,m,[R22,str(MODELS['h']),str(MODELS['b'])],cases)
            result=evaluate(store,{k:(side,gr)},'blind/'+k)[k]
            save_detail(RUN/'blind'/(k+'.json.gz'),result)
            result['cohorts']=[sum(int(r['new']==1)-int(r['old']==1) for r in result['rows'] if r['case'] in subset)
                               for subset in (cases[:12],cases[12:])]
            completed[k]={**brief(result),'opponents':result['by'],'extended':[r['late'] for r in result['rows'] if r['late']]}
            write(RUN/'blind-progress-results.json',dict(round=frozen['round'],completed=completed))
    write(RUN/'blind-results.json',dict(round=frozen['round'],completed=completed,time=local(time.time())))
