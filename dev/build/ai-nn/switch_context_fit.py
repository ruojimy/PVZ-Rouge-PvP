"""Fit a switch using the current offer and resolved deck attributes, then freeze both sides."""
import gzip
import json
from collections import Counter,defaultdict
from dataclasses import replace
from pathlib import Path
import numpy as np
from switch_study import OUT,CORPUS,OLD_CORPUS,CONTEXT,ARRIVAL,DEPLOY,PARENT,STRONG,PLANTS,fixed,read,sha
from switch_fit import game,model,learning_rows,cases,batch,flat,rank,paired,plant_pairs
from option_games import trace,extend,outcome

def context_data():
    gates,_=learning_rows(True);sites={}
    for name in ('review','positive','fresh','later','ready','visited'):
        for r in read(OUT/(name+'.json'))['rows']:
            key=r['keys'][0]
            if 'site' in r:site=r['site']
            else:
                with gzip.open(OUT/'games'/(key+'.jsonl.gz'),'rt',encoding='utf8') as f:
                    f.readline();site=json.loads(f.readline())['switches'][0]['site']
            sites[r['prefix']]=site
    ids=sorted({i for i,*_ in gates})
    deck_games={i:game(i[-3:],STRONG,model('old-short',dict(start='old')),CORPUS if i.startswith('fresh') else OLD_CORPUS,
                       forced=0,after=0,limit=1,binary=CONTEXT) for i in ids}
    batch('public deck attributes on fitting openings',deck_games.values())
    decks={i:trace(g)['switches'][0]['deck'] for i,g in deck_games.items()}
    unique=sorted({(i,p,tuple(x),y) for i,p,x,y in gates});counts=Counter(i for i,*_ in unique)
    rows=[]
    for i,p,state,y in unique:
        site=sites[p]
        x=[state[k] for k in (6,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29)]
        x.extend(site[k] for k in (3,4,5,6,11,12,13,19));x.extend(decks[i])
        rows.append(dict(x=x,target=y,weight=1/counts[i]))
    matrix=np.array([v['x'] for v in rows])
    scale=(1/np.maximum(np.std(matrix,axis=0),.19))/np.sqrt(matrix.shape[1])
    return dict(scale=scale.tolist(),centers=rows,prior=.18,inverse_width=2.0)

def context_zombie():
    prev=read(OUT/'zombie-selected.json');parent=Path(prev['path']);config=read(parent)['switch']
    if 'arrival' not in config:config={**config,**{k:read(OUT/'models/arrival-guarded.json')['switch'][k] for k in ('arrival','arrival_margin')}}
    radial=context_data()
    paths={k:model('context-'+k,{**config,'context':radial,'margin':margin,'front_margin':site})
           for k,margin,site in [('responsive',.09,.18),('guarded',.24,.30)]}
    val=read(OUT/'splits.json')['val'];hist=cases('review')+cases('positive')
    reports={'parent':prev['validation'][prev['selected']]};historical={'parent':prev['regression_training'][prev['selected']]};ext=[]
    groups={k:{o:[(game(i,p,PARENT,binary=DEPLOY),game(i,p,path,binary=CONTEXT)) for i in val] for o,p in PLANTS.items()} for k,path in paths.items()}
    refs={k:[(i,o,old,ev,replace(old,policy=path,binary=CONTEXT)) for i,o,(old,ev),_ in hist] for k,path in paths.items()}
    batch('context network on validation and previous first-disagreement cases',
          [g for gs in groups.values() for g in flat(gs)]+[b for rs in refs.values() for *_,b in rs])
    for k,gr in groups.items():
        reports[k]=paired(gr,'zombie');ext.extend((a,b,'zombie') for rs in gr.values() for a,b in rs)
        rows=[];by_open=defaultdict(list)
        for i,o,a,e,b in refs[k]:
            old=outcome(trace(a),'zombie');new=outcome(trace(b),'zombie')
            rows.append(dict(id=i,opponent=o,old=old,new=new,previous=outcome(trace(e),'zombie'),key=b.key()))
            if old==1:by_open[i].append(int(new==1))
            ext.extend([(a,b,'zombie'),(e,b,'zombie')])
        historical[k]=dict(rows=rows,kept=sum(r['old']==r['new']==1 for r in rows),
             true_gains=sum(r['old']==-1 and r['new']==1 for r in rows),opening_retention=float(np.mean([np.mean(v) for v in by_open.values()])))
    def selection(k):
        base=rank(reports[k]);h=historical[k];nwin=sum(r['old']==1 for r in reports[k]['rows']);keep=1+base[0]/max(1,nwin)
        return min(keep,h['opening_retention']),keep,h['opening_retention'],base[1],h['true_gains'],*base[2:]
    checks=0
    for k,gr in groups.items():
        for rs in gr.values():
            for _,b in rs:
                for ev in trace(b)['switches']:
                    if ev['phase']!='decision':continue
                    x=[ev['state'][j] for j in (6,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29)]+[ev['site'][j] for j in (3,4,5,6,11,12,13,19)]+ev['deck']
                    sq=np.array([np.sum(((np.array(x)-row['x'])*radial['scale'])**2) for row in radial['centers']])
                    weight=np.exp(-sq*radial['inverse_width'])*[row['weight'] for row in radial['centers']]
                    q=np.dot(weight,[row['target'] for row in radial['centers']])/(radial['prior']+weight.sum())
                    assert abs(q-ev['q'])<1e-9;checks+=1
    pathmap={**paths,'parent':parent};best=max(pathmap,key=selection)
    different={k:sum(trace(a)['log_sha256']!=trace(b)['log_sha256'] for gs in gr.values() for a,b in gs) for k,gr in groups.items()}
    # Report an active challenger when exact old-win retention selects a dormant
    # switch. This choice uses development trajectories only.
    competitors=[k for k in paths if different[k]>0]
    if not competitors:
        active=OUT/'models/gate-responsive.json';active_tag='first-responsive'
    else:
        active_tag=max(competitors,key=lambda k:(rank(reports[k])[1]+historical[k]['true_gains'],selection(k)))
        active=paths[active_tag]
    z=pathmap[best]
    fixed(OUT/'final-zombie.json',dict(path=str(z),sha256=sha(z),selected=best,active=str(active),active_sha=sha(active),
        active_tag=active_tag,different=different,rank_checks=checks,parent=sha(parent),centers=len(radial['centers']),validation=reports,
        regression_training=historical,extensions=extend(ext)))

def final_plant():
    z=read(OUT/'final-zombie.json');primary=Path(z['path']);active=Path(z['active'])
    old=Path(read(OUT/'zombie-selected.json')['path']);split=read(OUT/'splits.json')
    paths={a+b:OUT/'models'/('plant-'+a+'-'+b+'.json') for a in ('along','across') for b in ('p','m')}
    def groups(ids,p):
        base=plant_pairs(ids,p,old);out={'r22':base['r22']}
        for name,opponent in [('primary',primary),('active',active)]:
            if name=='active' and active==primary:continue
            out[name]=base['frozen'] if opponent==old else [(game(i,STRONG,opponent,binary=CONTEXT),game(i,p,opponent,binary=CONTEXT)) for i in ids]
        return out
    train={k:groups(split['train'],p) for k,p in paths.items()}
    batch('plant with frozen protection and active switch opponents',[g for gr in train.values() for g in flat(gr)])
    reports={k:paired(gr,'plant') for k,gr in train.items()}
    selected=sorted(paths,key=lambda k:rank(reports[k]),reverse=True)[:2]
    val={k:groups(split['val'],paths[k]) for k in selected}
    batch('final plant validation against fixed opponents',[g for gr in val.values() for g in flat(gr)])
    validation={k:paired(gr,'plant') for k,gr in val.items()};win=max(selected,key=lambda k:rank(validation[k]))
    ex=extend((a,b,'plant') for table in (train,val) for gr in table.values() for rs in gr.values() for a,b in rs)
    fixed(OUT/'final-plant.json',dict(selected=win,path=str(paths[win]),sha256=sha(paths[win]),zombie=z['sha256'],active=z['active_sha'],
                                      training=reports,validation=validation,extensions=ex))

def complete():
    from switch_study import guard
    if not (OUT/'final-zombie.json').exists():guard('context-zombie')
    if not (OUT/'final-plant.json').exists():final_plant()
def parity():
    plan=[]
    for i in read(OUT/'splits.json')['val'][::5]:
        for m in (PARENT,OUT/'models/gate-responsive.json'):
            a=game(i,STRONG,m,binary=DEPLOY);plan.append((a,replace(a,binary=CONTEXT)))
    batch('same old and event-switch weights on final simulator',[b for _,b in plan])
    for a,b in plan:assert trace(a)['log_sha256']==trace(b)['log_sha256']
    fixed(OUT/'context-parity.json',dict(pairs=[[a.key(),b.key()] for a,b in plan],binary=sha(CONTEXT)))
