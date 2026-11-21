"""Train and evaluate single tactical actions with matched troop deployment exposure."""
import gzip
import json
import math
from collections import Counter,defaultdict
from dataclasses import replace
from functools import lru_cache

import numpy as np
from tempo_pool import *
from tempo_build import EXE
from option_games import MODELS,extend
from single_fit import extend_groups,probe,stats,troop_tempo,pair_report,flatten
from switch_fit import fit
from single_study import ACTIVE,PLANT,STRONG

NAMES=('one_head','trip_head','arrival_live')
def live(i,p,z,**kw):return game(i,p,z,binary=EXE,**kw)

@lru_cache(maxsize=20)
def receipt(folder,key):
    path=folder/'games'/(key+'.jsonl.gz')
    meta=read(path.with_suffix('.receipt.json'));assert meta['sha256']==sha(path)
    with gzip.open(path,'rt',encoding='utf8') as f:
        header=json.loads(f.readline());result=json.loads(f.readline())
    return header,result

def times(tr):
    result=[[],[]]
    for e in tr['accepted_commands']:
        if e['kind']=='deploy' and e['accepted'] and e['card'].startswith('zombie:'):
            result[int(CATALOG[e['card']]['behavior']=='grave')].append(e['tick'])
    return result

def history_features(tr,tick):
    x=[]
    for ticks in times(tr):
        past=[v for v in ticks if v<tick]
        x.append(min(1800,tick-past[-1])/1800 if past else 1.)
        x.extend(math.tanh(sum(v>=tick-span for v in past)/4) for span in (450,1800))
    return x

def target(folder,stage,row,choice,extended):
    keys=row['keys'];a,b=keys[0],keys[choice]
    header,base=receipt(folder,a);_,candidate=receipt(folder,b)
    tick=row['tick'] if 'tick' in row else round(row['t']*30)
    end=min(round(r['time']*30) for r in (base,candidate))
    def exposure(tr):
        troops,graves=times(tr)
        return [sum(tick<=v<=end for v in t) for t in (troops,graves)]
    ca,cb=exposure(base),exposure(candidate)
    def value(key,other,tr):
        if not tr['timeout']:return float(outcome(tr,'zombie'))
        long=extended.get((other,key))
        if long:return .45 if long['winner']=='zombie' and not long['joint_idle'] else -1.
        return -.60
    delta=value(b,a,candidate)-value(a,b,base)
    reduction=max(0.,(ca[0]-cb[0])/max(2,ca[0]))
    lost_old_win=outcome(base,'zombie')==1 and outcome(candidate,'zombie')!=1
    y=delta-.9*reduction-.4*int(lost_old_win)
    extra=history_features(base,tick)
    if len(row['x']) in (63,48):
        assert np.allclose(row['x'][-6:],extra,rtol=0,atol=1e-9),(stage,row['id'],tick,row['x'][-6:],extra)
        x=row['x']
    else:x=row['x']+extra
    return dict(seed=header['seed'],prefix=row['prefix'],x=x,y=y,tick=tick,
                old=outcome(base,'zombie'),new=outcome(candidate,'zombie'),troops=[ca[0],cb[0]],graves=[ca[1],cb[1]],keys=[a,b],stage=stage)

def previous_rows():
    rows={k:[] for k in NAMES}
    for stage in ('review','fresh','visited','arrivals','earlier-arrivals','visited-arrivals'):
        doc=read(PREVIOUS/(stage+'.json'));ext={(v['base'],v['candidate']):v for v in doc['extensions']}
        for r in doc['rows']:
            if stage.endswith('arrivals'):choices=[('arrival_live',1)]
            elif stage=='review':choices=[('one_head',1)]
            else:choices=list(zip(NAMES[:2],range(1,len(r['keys']))))
            for name,k in choices:rows[name].append(target(PREVIOUS,stage,r,k,ext))
    return rows

def policy(name,doc):
    p=OUT/'models'/(name+'.json');fixed(p,doc);return p

def widened(sample=False):
    d=read(LAST_Z);cfg=d['switch'];cfg.update(troop_tempo=True,sample=sample)
    for name in NAMES:
        m=cfg[name]
        m['linear'] += [0.]*6
        for row in m['hidden']:row += [0.]*6
    return d

def prediction(x,m):
    x=np.asarray(x)
    return float(m['bias']+x@np.asarray(m['linear'])+np.dot(m['head'],np.tanh(np.asarray(m['hidden'])@x+m['hb'])))

def weight(name,rows,strength,margins):
    d=widened();cfg=d['switch'];infos={}
    for key in NAMES:
        old=cfg[key];samples=rows[key]
        items=[(str(r['seed']),r['prefix'],r['x'],r['y']-prediction(r['x'],old)) for r in samples]
        change,infos[key]=fit(items)
        old['bias']+=strength*change['bias']
        old['linear']=(np.asarray(old['linear'])+strength*np.asarray(change['linear'])).tolist()
        old['hidden']+=change['hidden'];old['hb']+=change['hb']
        old['head']+=(strength*np.asarray(change['head'])).tolist()
    cfg['one_margin'],cfg['trip_margin'],cfg['arrival_margin']=margins
    d['troop_training']=dict(parent=sha(LAST_Z),sample_counts=infos,residual=strength)
    return policy(name,d)

def relabel():
    rows=previous_rows()
    fixed(OUT/'old-labels.json',rows)
    weight('provisional',rows,.8,(.12,.16,.06))
    policy('previous-sampled',widened(True))

def parity():
    ids=read(PREVIOUS/'splits.json')['train'][:3]
    instrument=OUT/'models/previous-sampled.json';cfg=read(instrument)['switch']
    cases=[]
    for j,i in enumerate(ids):
        plant=list(TEACHERS.values())[j]
        gs=[Game(i,plant,policy=p,corpus=PREVIOUS/'plain',binary=b,storage=OUT)
            for b,p in ((LIVE,LAST_Z),(EXE,LAST_Z),(EXE,instrument),(LIVE,PARENT),(EXE,PARENT))]
        cases.append(gs)
    batch('unchanged source decisions, padded heads and native history feature parity',[g for gs in cases for g in gs])
    count=Counter()
    for gs in cases:
        ts=[trace(g) for g in gs];assert len({r['log_sha256'] for r in ts[:3]})==1 and ts[3]['log_sha256']==ts[4]['log_sha256']
        for e in ts[2]['switches']:
            if 'x' not in e:continue
            if e['phase'] not in ('lease','arrival_vote'):continue
            tick=round(e['t']*30);expect=history_features(ts[2],tick)
            assert np.allclose(e['x'][-6:],expect,rtol=0,atol=1e-8),(e['phase'],tick,e['x'][-6:],expect)
            if e['phase']=='arrival_vote':assert abs(prediction(e['x'],cfg['arrival_live'])-e['gain'])<1e-8
            else:
                assert abs(prediction(e['x'],cfg['one_head'])-e['v'])<1e-8
                if e['offered']:assert abs(prediction(e['x'],cfg['trip_head'])-e['trip'])<1e-8
            count[e['phase']]+=1
    fixed(OUT/'parity.json',dict(pairs=[[g.key() for g in gs] for gs in cases],checks=dict(count)))

def actual_difference(a,b):
    def inputs(tr):
        events=defaultdict(list)
        for e in tr['accepted_commands']:
            if e['kind'] not in ('deploy','rally') or not e['accepted']:continue
            events[e['tick']].append(tuple(e.get(k) for k in ('kind','card','grave','x','y','clear')))
        return events
    x,y=inputs(trace(a)),inputs(trace(b))
    return next((t/30 for t in sorted(set(x)|set(y)) if x[t]!=y[t]),0.)

def interventions():
    selected=read(OUT/'screen.json')['train'];teachers=list(TEACHERS)
    provisional=read(OUT/'models/provisional.json');provisional['switch']['sample']=True
    working=policy('provisional-sampled',provisional);enc=[]
    for j,r in enumerate(selected):
        o=r['opponent']
        for opp in (o,teachers[(teachers.index(o)+1)%len(teachers)]):
            g=live(r['id'],TEACHERS[opp],working);ref=game(r['id'],TEACHERS[opp],PARENT)
            enc.append((r['id'],opp,g,ref))
    batch('actual tactical differences and trained deployment states',[v for _,_,a,b in enc for v in (a,b)])
    roots=[];arrival_pool=[]
    for j,(i,o,g,ref) in enumerate(enc):
        tr=trace(g);leases=[e for e in tr['switches'] if e['phase']=='lease'];dt=actual_difference(g,ref)
        fired={c['tick'] for c in tr['accepted_commands'] if c['kind']=='deploy' and c['accepted']}
        first=min(leases,key=lambda e:(e['t']>dt,abs(e['t']-dt),e['t']))
        second=min(leases,key=lambda e:(e['t']==first['t'],not e['offered'] if j%2 else not bool(e['mask']&15),
                           round(30*e['t']) not in fired,abs(e['t']-(60,100,135)[j%3])))
        for e in [first]+([second] if second!=first else []):
            opts=list(range(3 if e['offered'] else 2))
            short=min(599,math.ceil(e['t']+6))
            if short<=e['t']:continue
            roots.append((i,o,g,e,[replace(g,after=e['t'],forced=k,limit=short) for k in opts]))
        for e in tr['switches']:
            if e['phase']=='arrival_vote':arrival_pool.append((i,o,g,e))
    batch('short native comparisons before committing full continuations',[a for *_,gs in roots for a in gs])
    groups=[];probes=[];rescued=0
    for i,o,g,e,gs in roots:
        marks=[probe(a) for a in gs]
        assert all(m['prefix']==marks[0]['prefix'] and m['x']==marks[0]['x'] and round(m['t']*30)==round(e['t']*30) for m in marks)
        natural=trace(g);match=trace(gs[e['choice']]);end=gs[0].limit
        for field,clock in (('activity','time'),('accepted_commands','time'),('spatial_actions','t')):
            assert [v for v in natural[field] if v[clock]<end]==[v for v in match[field] if v[clock]<end],(i,o,e['t'],field)
        hashes=[trace(a)['log_sha256'] for a in gs]
        picked=[k for k in range(1,len(gs)) if hashes[k]!=hashes[0]]
        duplicate=[k for k in range(1,len(gs)) if hashes[k]==hashes[0]]
        # A delayed divergence can escape the short screen. Keep four sentinel pairs.
        if duplicate and rescued<4:picked.append(duplicate[0]);rescued+=1
        probes.append(dict(id=i,opponent=o,t=e['t'],keys=[a.key() for a in gs],hashes=hashes,full=picked))
        if picked:
            full={k:(g if k==e['choice'] else replace(gs[k],limit=600)) for k in [0,*picked]}
            groups.append((i,o,e,marks[0],full,hashes))
    batch('complete selected same-state pairs',[a for *_,gr,_ in groups for a in gr.values()])
    ext=extend_groups([list(gr.values()) for *_,gr,_ in groups]);ex={(v['base'],v['candidate']):v for v in ext};trained={k:[] for k in NAMES}
    for i,o,e,m,gr,hashes in groups:
        for k in gr:
            if not k:continue
            row=dict(id=i,t=e['t'],prefix=m['prefix'],x=m['x'],keys=[gr[0].key(),gr[k].key()])
            result=target(OUT,'fresh',row,1,ex)
            result.update(opponent=o,short_distinct=hashes[0]!=hashes[k],
                          full_distinct=trace(gr[0])['log_sha256']!=trace(gr[k])['log_sha256'])
            trained[NAMES[k-1]].append(result)
    arrival_probe=read(working);arrival_probe['switch']['arrival_probe']=True
    ap=policy('arrival-probe',arrival_probe);used=Counter();arr=[]
    while arrival_pool and len(arr)<16:
        k=min(range(len(arrival_pool)),key=lambda j:(used[arrival_pool[j][0]],abs(arrival_pool[j][3]['t']-60),arrival_pool[j][1]))
        i,o,g,e=arrival_pool.pop(k);used[i]+=1
        arr.append((i,o,g,e,[replace(g,policy=ap,after=e['t'],forced=k) for k in (0,1)]))
    batch('reached sites: build vs wait once',[a for *_,gs in arr for a in gs])
    ae=extend_groups([gs for *_,gs in arr]);ax={(v['base'],v['candidate']):v for v in ae}
    for i,o,g,e,gs in arr:
        marks=[probe(a) for a in gs];assert marks[0]['prefix']==marks[1]['prefix']
        votes=[next(v for v in trace(a)['switches'] if v['phase']=='arrival_vote' and round(30*v['t'])==round(30*e['t'])) for a in gs]
        assert [v['place'] for v in votes]==[False,True] and votes[0]['x']==votes[1]['x']==e['x']
        assert trace(gs[int(e['place'])])['log_sha256']==trace(g)['log_sha256']
        r=dict(id=i,t=e['t'],x=e['x'],prefix=marks[0]['prefix'],keys=[a.key() for a in gs])
        trained['arrival_live'].append(target(OUT,'arrival',r,1,ax))
    fixed(OUT/'rollouts.json',dict(probes=probes,rows=trained,extensions=ext+ae))

def run(stage):
    if stage=='relabel':relabel()
    elif stage=='parity':parity()
    elif stage=='interventions':interventions()
    else:
        from tempo_eval import run as evaluate
        evaluate(stage)
