"""Matched one-decision training, zombie-only policy selection and sealed evaluation."""
from collections import Counter,defaultdict
from dataclasses import replace
from functools import lru_cache
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import time
import zlib

import numpy as np
import league_matches as lm
from league_data import BASE, OLD_Z, OLD_CORPUS, NEW,local
from option_games import Game
from ranked_special_setup import OUT,EXE,FRESH,NIGHT,REVIEW,read,write,sha
from ranked_draft import RULES,check_game,PROFILE
from ranked_combat_pool import SUPPORT

R22='r22'
JOBS=5
if PROFILE:
    BASE=OUT/'weights/macro.json';OLD_Z=OUT/'weights/position.json'
lm.RUN=OUT
ORIGINAL_COMPACT=lm.compact
CAPTURE=set()

@lru_cache(None)
def metadata():return read(OUT/'opponents.json')
@lru_cache(None)
def fixtures():return read(OUT/'fixtures.json')
@lru_cache(None)
def model(path):return read(Path(path))

@lru_cache(None)
def ranked_cases(tag):
    corpus,plan=(FRESH,fixtures()) if tag=='fresh' else (OUT/tag,read(OUT/f'{tag}.json'))
    assert plan['index_sha']==sha(corpus/'index.json') and fixtures()['rules']==RULES
    return {e['id'] for e in read(corpus/'index.json')['entries'] if check_game(e)}

def make_game(case,plant,zombie,storage):
    tag,uid=case.split('/')
    assert tag in (('fresh','playable','replay') if PROFILE else ('fresh','playable')) and uid in ranked_cases(tag)
    corpus=FRESH if tag=='fresh' else OUT/tag
    stem=Game(uid,None if plant==R22 else Path(plant),zombie=None,position=None,policy=None,corpus=corpus,binary=EXE,storage=storage)
    if zombie==R22:return stem
    specialist='native_gate' in model(zombie)['switch']
    return replace(stem,zombie=None if specialist else BASE,position=OLD_Z,policy=Path(zombie))

def compact(g):
    r=ORIGINAL_COMPACT(g)
    with gzip.open(g.path(),'rt',encoding='utf8') as f:
        header=json.loads(f.readline());tr=json.loads(f.readline())
    if PROFILE:
        assert header['ranked_rules']['build']==PROFILE['version']
        assert all(header['ranked_rules'][k]==v for k,v in RULES.items())
    spec=bool(g.policy and 'native_gate' in model(str(g.policy))['switch'])
    if spec:assert header['planners']['zombie']=='r22' and header['option_sha256']==sha(g.policy)
    switches=[e for e in tr['switches'] if e['phase']=='special']
    r['special_actions']=[sum(e['choice']==j for e in switches) for j in (1,2)]
    if spec and model(str(g.policy))['switch']['native_gate']['record']:
        r['sites']=[[round(e['t']*30),e['mask'],e['choice'],e['x']] for e in switches]
    if g.forced>=0:
        stamp=next(e for e in tr['options'] if e.get('forked'))
        tick=round(stamp['time']*30)
        ev=next(e for e in switches if e.get('prefix')==stamp['prefix'] and round(e['t']*30)==tick)
        assert ev['choice']==g.forced and tick==round(g.after*30)
        r['probe']={'tick':tick,'prefix':ev['prefix'],'x':ev['x'],'mask':ev['mask']}
    if g.key() in CAPTURE:
        r['commands']=[[e['tick'],{k:v for k,v in e.items() if k not in ('seq','time','tick','side','accepted','event')}]
                       for e in tr['accepted_commands'] if e['accepted']]
    return r

lm.compact=compact

class Arena(lm.Matches):
    def pair_game(self,case,side,m,opp):
        assert side=='zombie'
        return make_game(case,opp,m,self.storage)

def save_model(tag,body):
    p=OUT/'models'/(tag+'.json');p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert read(p)==body
    else:write(p,body)
    return str(p)

def gate(body,settings):
    return {**body,'switch':{**body['switch'],'native_gate':settings}}

def empty_gate():
    rng=np.random.default_rng(79235)
    return dict(linear=np.zeros((2,22)).tolist(),hidden=rng.normal(0,.55,(8,22)).tolist(),
                head=np.zeros((2,8)).tolist(),hidden_bias=rng.normal(0,.4,8).tolist(),bias=[-10.,-10.],record=False)

def logged(m):
    d=model(m);return save_model('trace-'+sha(Path(m))[:18],gate(d,{**d['switch']['native_gate'],'record':True}))

def teams():
    return [metadata()['pool'][n] for n in metadata()['selected']]

def label(path):
    return next((n for n,p in metadata()['pool'].items() if p==path),Path(path).stem)

def baseline_key(key):
    for folder in (REVIEW,NIGHT):
        with sqlite3.connect((folder/'matches.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            row=db.execute('select payload from games where id=?',(key,)).fetchone()
        if row:return json.loads(zlib.decompress(row[0]))
    raise KeyError(key)

def divergence(a,b):
    def at(trace):
        d=defaultdict(list)
        for tick,command in trace:d[tick].append(command)
        return d
    x,y=at(a),at(b);start=None;significant=None
    for tick in sorted(x.keys()|y.keys()):
        if x[tick]==y[tick]:continue
        if start is None:start=tick
        filtered=lambda v:[cmd for cmd in v if cmd['kind'] in ('deploy','rally','command')]
        if filtered(x[tick])!=filtered(y[tick]):significant=tick;break
    return start,significant

def bootstrap(store):
    p=OUT/'bootstrap.json'
    if p.exists():return read(p)
    meta=metadata();prior=meta.get('start_zombie',meta['champion'])
    base=save_model('r22-anchor',gate(model(prior),empty_gate()))
    stream=logged(base)
    tuples=[];candidates=[]
    pairs=[(c,op) for c in fixtures()['train'] for op in teams()]
    if PROFILE:pairs.extend((r['case'],r['plant']) for r in read(OUT/'replay.json')['pairs'])
    for c,op in dict.fromkeys(pairs):
        gs=[make_game(c,op,m,store.storage) for m in (R22,prior)]
        candidates.append((c,op,gs));CAPTURE.update(g.key() for g in gs)
    store.ensure((g for _,_,gs in candidates for g in gs),'ranked-baseline-screen')
    flips=[];others=[]
    for c,op,gs in candidates:
        a,b=[lm.value(store.get(g),'zombie') for g in gs]
        r=dict(case=c,plant=op,r22=a,night=b,keys=[g.key() for g in gs])
        (flips if (a==1 and b!=1) or (a==-1 and b==1) else others).append((r,gs))
    include=flips+others[:max(4,10-len(flips))]
    include.extend(pair for pair in others if pair[0]['case'].startswith('replay/') and pair not in include)
    for r,gs in include:
        tuples.append((r,[*gs,make_game(r['case'],r['plant'],stream,store.storage)]))
    store.ensure((gs[-1] for _,gs in tuples),'ranked-anchor-parity')
    roots=[];coverage=[]
    for j,(r,gs) in enumerate(tuples):
        a,b,c=[store.get(g) for g in gs]
        assert a['battle']==c['battle'] and a['activity']==c['activity']
        first,first_deploy=divergence(a['commands'],b['commands'])
        sites=c['sites']
        add=lambda t:max((e for e in sites if e[0]<=t),key=lambda e:e[0],default=sites[0])[0]
        ticks={add(first if first is not None else 0)}
        if first_deploy is not None:ticks.add(add(first_deploy))
        late=[e for e in sites if e[0]>=300 and e[1]&15]
        if late:ticks.add(late[(j*29+11)%len(late)][0])
        for tick in sorted(ticks):roots.append(dict(case=r['case'],plant=r['plant'],tick=tick,parent=base))
        coverage.append(dict(**r,first_command=first,first_deploy_or_flag=first_deploy,game_ticks=[a['tick'],b['tick']]))
    summary={}
    for op in teams():
        matches=[store.get(gs[0]) for _,o,gs in candidates if o==op]
        summary[label(op)]=dict(plant_wins=sum(lm.value(g,'plant')==1 for g in matches),games=len(matches))
    doc=dict(base=base,roots=roots,coverage=coverage,regression=[r for r,_ in tuples],screened=len(candidates),
             paired_flips=len(flips),plant_strength=summary,parity_pairs=len(tuples))
    write(p,doc);return doc

def probes(store,roots,stage):
    games=[]
    for site in roots:
        g=make_game(site['case'],site['plant'],site['parent'],store.storage)
        games.append([replace(g,forced=j,after=site['tick']/30) for j in range(3)])
    store.ensure((g for group in games for g in group),stage)
    extended=[]
    for gs in games:
        rows=[store.get(g) for g in gs]
        for j,r in enumerate(rows):
            if r['timeout'] and any(lm.value(a,'zombie')<0 for a in rows):extended.append(replace(gs[j],limit=1200))
    if extended:store.ensure(extended,stage+'-extended')
    longkeys={g.key() for g in extended};result=[]
    for site,gs in zip(roots,games):
        rs=[store.get(g) for g in gs];mark=rs[0]['probe']
        assert all(r['probe']==mark for r in rs)
        taken=[]
        for j,(g,r) in enumerate(zip(gs,rs)):
            v=lm.value(r,'zombie');lg=replace(g,limit=1200)
            late=None
            if lg.key() in longkeys:
                t=store.get(lg);assert t['prefix']==r['prefix'];late=lm.value(t,'zombie')
            taken.append(dict(w=v,late=late,key=g.key(),battle=r['battle']))
        ys=[]
        def utility(j):
            d=taken[j]
            return d['w'] if d['w'] else (.55 if d['late']==1 else -1. if d['late']==-1 else -.5)
        for j in (1,2):
            end=min(rs[0]['tick'],rs[j]['tick'])
            counts=[sum(v<=end for v in r['activity']['troops']) for r in (rs[0],rs[j])]
            slower=max(0.,(counts[0]-counts[1])/max(4,counts[0]))
            ys.append(utility(j)-utility(0)-.45*min(1.,slower)-.4*int(taken[0]['w']==1 and taken[j]['w']!=1))
        result.append(dict(**site,prefix=mark['prefix'],x=mark['x'],mask=mark['mask'],arms=taken,y=ys))
    return result

def paired(store,model_path,refs,matchups,stage):
    table={k:('zombie',[(o,c,make_game(c,o,m,store.storage),make_game(c,o,model_path,store.storage)) for c,o in matchups])
           for k,m in refs.items()}
    return lm.evaluate(store,table,stage)

def fit_gate(samples,base,round_no,slot):
    rng=np.random.default_rng(11003*round_no+419*slot)
    g=empty_gate()
    if slot in (1,3):
        g['hidden']=rng.normal(0,.55,(8,22)).tolist()
        g['hidden_bias']=rng.normal(0,.4,8).tolist()
    h=np.array(g['hidden']);hb=np.array(g['hidden_bias'])
    # Identical native continuations for both alternate choices carry one combined weight.
    # Repeated states across opponent snapshots are given one vote in the regression.
    groups=Counter(r['prefix'] for r in samples)
    X=np.array([s['x'] for s in samples]);terms=np.column_stack([np.ones(len(X)),X,np.tanh(X@h.T+hb)])
    for arm in range(2):
        y=np.array([s['y'][arm] for s in samples])
        w=np.array([(1.+1.2*abs(target))/groups[s['prefix']]*
                    (.5 if s['arms'][1]['battle']==s['arms'][2]['battle'] else 1.)
                    for target,s in zip(y,samples)])
        if slot==3:w*=rng.uniform(.5,1.5,len(w))
        reg=(1.75,2.,3.,1.25)[slot];ridge=np.eye(terms.shape[1])*reg;ridge[0,0]=.2
        beta=np.linalg.solve((terms.T*w)@terms+ridge,(terms.T*w)@y)
        # Calibrate the fraction of observed states in which to deviate. Winning a new
        # fight, retaining old wins, and actual troop tempo decide which fraction survives.
        q=(.93,.83,.97,.68)[slot]
        margin=max((.08,.05,.12,.025)[slot],float(np.quantile(terms@beta,q)))
        g['bias'][arm]=float(beta[0]-margin);g['linear'][arm]=beta[1:23].tolist();g['head'][arm]=beta[23:].tolist()
    return save_model(f'round-{round_no:03d}-{slot}',gate(model(base),g))

def rank(r):
    delta=r['new'][0]-r['old'][0]
    return (delta-.80*r['lost']-.30*max(0,r['new'][1]-r['old'][1])
            +.25*r['gain']-len(r['rows'])*1.15*max(0.,1.-r['speed'])
            +len(r['rows'])*.30*(r['worst'][1]-r['worst'][0]))

def wins_gate(r):
    return (r['new'][0]>r['old'][0] and r['gain']>=1 and r['lost']<=max(1,len(r['rows'])//32)
            and r['new'][1]<=r['old'][1] and r['speed']>=1. and r['worst'][1]>=r['worst'][0]
            and r['seconds'][1]<=1.05*r['seconds'][0])

def write_samples(i,rows):
    path=OUT/'probes'/f'{i:03d}.json.gz';path.parent.mkdir(exist_ok=True)
    part=path.with_suffix('.partial');part.write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),5,mtime=0));part.replace(path)

def all_samples():
    return [r for p in sorted((OUT/'probes').glob('*.json.gz')) for r in json.loads(gzip.decompress(p.read_bytes()))]

def warmup(store):
    boot=bootstrap(store);p=OUT/'state.json'
    if p.exists():return read(p)
    samples=probes(store,boot['roots'],'r22-one-decision-replays')
    write_samples(0,samples)
    state=dict(round=0,champion=boot['base'],research=metadata().get('start_zombie'),best_score=None,promotions=0)
    write(p,state);return state

def playable_screen(store):
    p=OUT/'playable-baselines.json'
    if p.exists():return read(p)
    pool=teams();plan=read(OUT/'playable.json')
    pairs=[(c,o,make_game(c,o,R22,store.storage),make_game(c,o,metadata()['champion'],store.storage))
           for c in plan['train'] for o in pool]
    store.ensure((g for _,_,a,b in pairs for g in (a,b)),'playable-ranked-screen')
    rows=[dict(case=c,plant=o,r22=lm.value(store.get(a),'zombie'),night=lm.value(store.get(b),'zombie')) for c,o,a,b in pairs]
    write(p,rows);return rows

def round_worker(store,state):
    gen=state['round']+1;rng=np.random.default_rng(19731+gen*51)
    base=read(OUT/'bootstrap.json')['base'];pool=teams();f=fixtures()
    subset=lambda items,n:[items[i] for i in rng.choice(len(items),min(n,len(items)),replace=False)]
    rules=read(OUT/'bootstrap.json')['regression']
    scan=[(c,o) for c in subset(f['train'],4) for o in pool]
    scan.extend((r['case'],r['plant']) for k in (1,-1) for r in subset([v for v in rules if v['r22']==k],3))
    scan=list(dict.fromkeys(scan))
    if gen>=2 or PROFILE:
        extra=read(OUT/'playable.json');screen=playable_screen(store)
        scan.extend((c,o) for c in subset(extra['train'],3) for o in pool)
        scan.extend((r['case'],r['plant']) for r in subset([v for v in screen if v['r22']!=1],5))
        scan=list(dict.fromkeys(scan))
    teach=state['research'] if state['research'] and gen%2==0 else state['champion']
    visits=[(c,o,make_game(c,o,logged(teach),store.storage)) for c,o in subset(scan,5)]
    corrections=[]
    if gen>=4 and state['research']:
        active=state['research'];window=[v for v in scan if v[0].startswith('playable/')]
        review=[(c,o,make_game(c,o,R22,store.storage),make_game(c,o,active,store.storage)) for c,o in window]
        store.ensure((g for _,_,a,b in review for g in (a,b)),f'{gen}/train-reversals')
        for v in (1,-1):
            changed=[(c,o) for c,o,a,b in review if lm.value(store.get(a),'zombie')==v and
                     (lm.value(store.get(b),'zombie')!=1 if v==1 else lm.value(store.get(b),'zombie')==1)]
            for c,o in subset(changed,2):
                corrections.append((c,o,make_game(c,o,logged(active),store.storage)))
        store.ensure((g for _,_,g in corrections),f'{gen}/trace-reversals')
    store.ensure((g for _,_,g in visits),f'{gen}/visit')
    roots=[]
    for c,o,g in corrections:
        first=next((s for s in store.get(g)['sites'] if s[2]!=0),None)
        if first:roots.append(dict(case=c,plant=o,tick=first[0],parent=state['research']))
    for c,o,g in visits:
        sites=store.get(g)['sites'];live=[s for s in sites if s[0]>60 and s[1]&15]
        for r in (subset(live or sites,1)[0],subset(sites,1)[0]):
            local_site=dict(case=c,plant=o,tick=r[0],parent=teach)
            if local_site not in roots:roots.append(local_site)
    rows=probes(store,roots,f'{gen}/branches')
    write_samples(gen,rows)
    samples=all_samples()
    variants=[fit_gate(samples,base,gen,j) for j in range(4)]
    if PROFILE:
        parent=state['research'] or metadata()['start_zombie']
        # Blend outputs of two gates with the same hidden basis. The first proposal preserves
        # prior hidden weights and refits a residual linear correction to its logit.
        old=model(parent)['switch']['native_gate']
        X=np.array([r['x'] for r in samples]);features=np.column_stack([np.ones(len(X)),X])
        old_scores=X@np.array(old['linear']).T+np.tanh(X@np.array(old['hidden']).T+old['hidden_bias'])@np.array(old['head']).T+old['bias']
        error=np.array([r['y'] for r in samples])-old_scores
        beta=np.linalg.solve(features.T@features+4*np.eye(features.shape[1]),features.T@error)
        residual={**old,'record':False,'linear':(np.array(old['linear'])+.25*beta[1:].T).tolist(),
                  'bias':(np.array(old['bias'])+.25*beta[0]-.03).tolist()}
        variants.append(save_model(f'round-{gen:03d}-continued',gate(model(parent),residual)))
    rs=lm.evaluate(store,{m:('zombie',[(o,c,make_game(c,o,R22,store.storage),make_game(c,o,m,store.storage)) for c,o in scan])
                          for m in variants},f'{gen}/screen')
    finalist=max(variants,key=lambda m:(rank(rs[m]),rs[m]['changed']))
    refs={'r22':R22,'incumbent':state['champion'],'night':metadata()['champion']}
    validation=[(c,o) for c in f['validation'] for o in [*pool,R22]]
    if gen>=2 or PROFILE:validation.extend((c,o) for c in extra['validation'] for o in [*pool,R22])
    check=paired(store,finalist,refs,validation,f'{gen}/validation')
    r=check['r22'];inc=check['incumbent']
    promoted=wins_gate(r) and wins_gate(inc) and r['by'][R22][1][0]>=r['by'][R22][0][0]
    quality=rank(r)
    # Raw scores from the first (free-draft only) validation do not compare with
    # scores from the mixed suite. Recalibrate the incumbent research head on the same cases.
    cohort=lm.hash_json(validation)
    if state['research'] and state.get('research_validation')!=cohort:
        old=paired(store,state['research'],{'r22':R22},validation,f'{gen}/recalibrate')['r22']
        state['best_score']=rank(old) if old['changed'] else None
    state['research_validation']=cohort
    # Track the strongest active research candidate even when a conservative r22 incumbent holds.
    if r['changed'] and (state['best_score'] is None or quality>state['best_score']):
        state['best_score']=quality;state['research']=finalist
    if promoted:state['champion']=finalist;state['promotions']+=1
    state['round']=gen
    detail=dict(generation=gen,challenger=finalist,promoted=promoted,new_samples=len(rows),samples=len(samples),
                scores={m:rank(v) for m,v in rs.items()},validation=check)
    write(OUT/'rounds'/f'{gen:03d}.json',detail)
    write(OUT/'state.json',state)
    return state

def train():
    store=Arena('train',JOBS);st=warmup(store)
    while time.time()<read(OUT/'clock.json')['train_until']:
        st=round_worker(store,st)

def fixed_blind_references():
    store=Arena('reference',2)
    extra=read(OUT/'playable.json')
    models=[R22,metadata()['champion']]
    if PROFILE:models.append(metadata()['start_zombie'])
    pool=[*teams(),R22,metadata()['pool']['B']]
    cases=fixtures()['blind']+extra['blind']
    assert set(cases).isdisjoint(fixtures()['train']+fixtures()['validation']+extra['train']+extra['validation'])
    # Only immutable references. The trainer's screen, fitting and promotion pools exclude these IDs.
    store.ensure((make_game(c,o,m,store.storage) for c in cases for o in pool for m in models),'fixed-blind-references')
    write(OUT/'reference-cache.json',dict(cases=len(cases),games=len(cases)*len(pool)*len(models),
                                         sides=[m if m==R22 else sha(Path(m)) for m in models],completed=local(time.time())))

def blind():
    seal=read(OUT/'sealed.json');store=Arena('blind',JOBS)
    cases=fixtures()['blind'];pool=[*teams(),R22,str(metadata()['pool']['B'])]
    assert len(set(cases))==24 and set(cases).isdisjoint(fixtures()['train']+fixtures()['validation'])
    extra=read(OUT/'playable.json')
    assert len(extra['blind'])==24 and set(extra['blind']).isdisjoint(extra['train']+extra['validation'])
    pairs=[(c,o) for c in cases+extra['blind'] for o in pool]
    outputs={}
    for role,path in seal['models'].items():
        assert sha(Path(path))==seal['hashes'][role]
        refs={'r22':R22,'night':metadata()['champion']}
        if PROFILE:refs['previous_candidate']=metadata()['start_zombie']
        outputs[role]=paired(store,path,refs,pairs,'sealed/'+role)
        for r in outputs[role].values():
            r['cohorts']=[sum(int(x['new']==1)-int(x['old']==1) for x in r['rows'] if x['case'] in block)
                          for block in (cases,extra['blind'])]
        reg=[(r['case'],r['plant']) for r in read(OUT/'bootstrap.json')['regression']]
        outputs[role]['regression']=paired(store,path,{'r22':R22},reg,'ranked-regression/'+role)['r22']
        write(OUT/'assessment-partial.json',outputs)
    write(OUT/'assessment.json',outputs)

if __name__=='__main__':
    {'train':train,'blind':blind,'fixed-references':fixed_blind_references}[sys.argv[1]]()
