"""Fit a value head on matched native continuations, then reverse the training seat."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import numpy as np
from option_games import (ROOT,PRIOR,OLD_Z,OLD_P,BASE,MODELS,Game,trace,play,batch,extend,outcome,slow,measure,read,write,sha)
from option_study import inputs_ok

CHOICES=['continue','deploy now','advance, build, deploy from new grave','save for six seconds']
MODELS_DIR=ROOT/'models'

def freeze_plan():
    inputs_ok()
    split=read(ROOT/'splits.json');pilot=read(ROOT/'preflight.json')
    prev=read(PRIOR/'opponents.json')
    assert all(sha(MODELS[o])==prev['model_sha256'][o] for o in 'onb')
    assert sha(OLD_Z)==read(PRIOR/'robust/zombie-frozen.json')['sha256']
    assert sha(OLD_P)==read(PRIOR/'robust/plant-frozen.json')['sha256']
    spec=dict(corpus=split['corpus'],splits={k:split[k] for k in ('train','validation','test')},
              choices=CHOICES,training_plants={o:sha(MODELS[o]) for o in 'onb'},
              parent_zombie=sha(OLD_Z),parent_plant=sha(OLD_P),parity=pilot['parity'],forced_seconds=[12,55,105],
              loss='Same-state centered 600s return plus 0.12 times bounded 35s hero damage differential. No duration or resource bonus. Remove credit for bilateral inactivity.',
              validation='Compare inference margins .04 and .16 against the unmodified immediate parent on O,N,B. Freeze the best learned challenger; keep incumbent in production unless independent tests pass.',
              plant_fit='After zombie freeze, two symmetric directions on 28 economic context inputs, paired train returns and validation against frozen zombie. Keep parent on validation tie.',
              test='18 new home starts, separately unseen plant and zombie decks, vs r22, independent H and historical B. Single-seat substitutions. Both halves positive, no losing opponent margin, clustered 95% lower bound positive, no bilateral stall credit. Extend all matched loss-to-timeout.',
              kernel=read(ROOT/'build.json')['binary'])
    if (ROOT/'design.json').exists():assert read(ROOT/'design.json')==spec
    else:write(ROOT/'design.json',spec)
    return split

def branches():
    s=freeze_plan()
    groups=[]
    for i,uid in enumerate(s['train']):
        for j,opp in enumerate('onb'):
            after=(12,55,105)[(i+j)%3]
            groups.append((uid,opp,[Game(uid,MODELS[opp],forced=o,after=after) for o in range(4)]))
    collect_branches(groups,'branches')

def extra_branches():
    # This secondary corpus contains only the preceding study's training IDs.
    # The sealed plant decks and zombie decks were separately screened against both corpora.
    configs=[(PRIOR/'plain',read(PRIOR/'plan.json')['train']),
             (PRIOR/'robust/diverse/plain',read(PRIOR/'robust/diverse/ready.json')['ids'])]
    groups=[];spec=[]
    for k,(corpus,ids) in enumerate(configs):
        for j,i in enumerate(ids):
            o='onb'[(j+k)%3];after=(30,75,125)[(j//3+k)%3]
            games=[Game(i,MODELS[o],forced=c,after=after,corpus=corpus) for c in range(4)]
            groups.append((i,o,games));spec.append(dict(id=i,opp=o,corpus=str(corpus),after=after))
    write(ROOT/'extra-design.json',dict(scenarios=spec,selection='Previous training only, deterministic seat and time rotation, no score-based selection.'))
    collect_branches(groups,'branches-extra')

def collect_branches(groups,name):
    batch('same-state terminal continuations',[g for _,_,gs in groups for g in gs])
    comparisons=[(gs[0],g,'zombie') for _,_,gs in groups for g in gs[1:]]
    extensions=extend(comparisons)
    dataset=[];missing=[]
    for uid,opp,gs in groups:
        rows=[trace(g) for g in gs]
        if not rows[0]['options']:
            assert all(not d['options'] and d['log_sha256']==rows[0]['log_sha256'] for d in rows)
            missing.append([uid,opp]);continue
        assert all(len(r['options'])==1 for r in rows)
        events=[r['options'][0] for r in rows];target=events[0];t=target['time']
        for e,r in zip(events,rows):
            assert all(e[k]==target[k] for k in ('time','prefix','x','proposed_front','proposed_spawn'))
            for field,key in [('activity','time'),('accepted_commands','time'),('spatial_actions','t')]:
                assert [a for a in r[field] if round(a[key]*30)<round(t*30)]==[a for a in rows[0][field] if round(a[key]*30)<round(t*30)]
            if e.get('spawn'):
                assert any(c.get('grave')==e['spawn']['source'] and c['card']==e['spawn']['card'] and c['tick']==round(e['spawn']['time']*30) and c['accepted'] for c in r['accepted_commands'] if c['kind']=='deploy')
            if e.get('built'):
                assert any(c['card']==e['built']['card'] and c['tick']==round(e['built']['time']*30) and c['accepted'] for c in r['accepted_commands'] if c['kind']=='deploy')
        labels=[];outcomes=[]
        for r in rows:
            result=outcome(r,'zombie');outcomes.append(result)
            if result==0 and r['timeout'] and outcome(rows[0],'zombie')<0 and slow(rows[0],r):result=-1
            def damage(side):
                plans=[a for a in r['activity'] if a['kind']=='plan' and a['side']==side and a['time']<=t+35]
                start=next((a['hp'] for a in reversed(plans) if a['time']<=t),None)
                if start is None:return 0.
                final=r['hp'][side] if r['time']<=t+35 else plans[-1]['hp']
                return start-final
            labels.append(result+.12*np.tanh((damage('plant')-damage('zombie'))/20.))
        dataset.append(dict(id=uid,corpus=str(gs[0].corpus),after=gs[0].after,opponent=opp,time=t,x=target['x'],prefix=target['prefix'],labels=labels,outcomes=outcomes,
                            statuses=[e['status'] for e in events],built=bool(events[2].get('built')),
                            keys=[g.key() for g in gs]))
    assert dataset
    write(ROOT/(name+'.json'),dict(groups=dataset,unavailable=missing,extensions=extensions))

def training_groups():
    return [g for f in ('branches','branches-extra','branches-timed') if (ROOT/(f+'.json')).exists()
            for g in read(ROOT/(f+'.json'))['groups']]

def enrich():
    # Action legality can make a clock-selected fork unavailable. On training data
    # only, discover real opportunities with a neutral value policy before picking
    # additional early/middle/late decisions. No outcome or damage is used to pick.
    if (ROOT/'branches-timed.json').exists():return
    zero=MODELS_DIR/'neutral-discovery.json'
    write(zero,dict(format='pvz-native-option-value-1',sim_fingerprint=read(OLD_Z)['sim_fingerprint'],
                    hidden=np.zeros((8,23)).tolist(),head=np.zeros((4,9)).tolist(),margin=1.))
    source=[(ROOT/'plain',read(ROOT/'splits.json')['train']),
            (PRIOR/'plain',read(PRIOR/'plan.json')['train']),
            (PRIOR/'robust/diverse/plain',read(PRIOR/'robust/diverse/ready.json')['ids'])]
    jobs=[(i,'onb'[(j+k)%3],Game(i,MODELS['onb'[(j+k)%3]],policy=zero,corpus=d))
          for k,(d,ids) in enumerate(source) for j,i in enumerate(ids)]
    batch('locate eligible training states without changing actions',[g for _,_,g in jobs])
    existing=training_groups()
    prev={(str(g.get('corpus',ROOT/'plain')),g['id'],g['opponent']):[] for g in existing}
    for g in existing:prev[(str(g.get('corpus',ROOT/'plain')),g['id'],g['opponent'])].append(g['time'])
    chosen={};eligible=0
    for uid,o,g in jobs:
        row=trace(g);events=row['options']
        assert all(e['choice']==0 for e in events)
        prior=prev.get((str(g.corpus),uid,o),[])
        avail=[e['time'] for e in events if all(abs(t-e['time'])>12 for t in prior)]
        eligible+=len(avail)
        if avail:
            indexes=[0,len(avail)-1,(len(avail)-1)//2]
            chosen[g]=list(dict.fromkeys(avail[j] for j in indexes))
    groups=[];targets=[]
    for pass_id in range(3):
        for uid,o,g in jobs:
            if len(chosen.get(g,[]))<=pass_id or len(groups)>=48:continue
            t=chosen[g][pass_id]
            gs=[replace(g,policy=None,forced=c,after=t) for c in range(4)]
            groups.append((uid,o,gs));targets.append(dict(id=uid,opponent=o,corpus=str(g.corpus),time=t,scan=g.key()))
    write(ROOT/'timed-design.json',dict(scan_games=len(jobs),eligible=eligible,targets=targets,
          selection='Round-robin openings, first/last/middle legal occasions, at least 12 seconds from a matching prior fork; maximum 48 roots. Outcomes unused.'))
    if groups:
        collect_branches(groups,'branches-timed')
        rows=read(ROOT/'branches-timed.json')['groups']
        assert len(rows)==len(groups)
        for r,target in zip(rows,targets):
            assert abs(r['time']-target['time'])<1e-5
            z=next(g for _,_,g in jobs if g.key()==target['scan'])
            assert trace(z)['log_sha256']==trace(Game(r['id'],MODELS[r['opponent']],forced=0,after=r['after'],corpus=Path(r['corpus'])))['log_sha256']
    else:write(ROOT/'branches-timed.json',dict(groups=[],unavailable=[],extensions=[]))

def train_values():
    data=training_groups()
    assert len(data)>=16 and any(g['statuses'][2]=='front built and deployed' for g in data)
    x=np.array([g['x'] for g in data]);y=np.array([g['labels'] for g in data]);y-=y.mean(axis=1,keepdims=True)
    # Each opening gets equal total weight if individual opponents never offer a three-way decision.
    # Collapse identical prefixes with identical counterfactual labels within each opening.
    # Distinct responses after an identical state can still inform its estimated value.
    openings=[(g.get('corpus',str(ROOT/'plain')),g['id']) for g in data]
    keys=[(o,g['prefix'],tuple(g['labels'])) for o,g in zip(openings,data)]
    duplicates=Counter(keys);counts=Counter(k[0] for k in duplicates)
    w=np.array([1./(counts[o]*duplicates[k]) for o,k in zip(openings,keys)]);w/=w.sum()
    mean=w@x;scale=np.maximum(.12,np.sqrt(w@((x-mean)**2)));x=(x-mean)/scale
    rng=np.random.default_rng(58211)
    ih=rng.normal(0,.17,(8,x.shape[1]));bh=np.zeros(8);oh=rng.normal(0,.04,(4,8));bo=np.zeros(4)
    params=[ih,bh,oh,bo];mom=[np.zeros_like(p) for p in params];vel=[v.copy() for v in mom]
    for step in range(1,121):
        hidden=np.tanh(x@ih.T+bh);pred=hidden@oh.T+bo
        deriv=2*(pred-y)*w[:,None]/4
        dh=(deriv@oh)*(1.-hidden**2)
        grads=[dh.T@x+.022*ih,dh.sum(0),deriv.T@hidden+.045*oh,deriv.sum(0)]
        for p,m,v,g in zip(params,mom,vel,grads):
            m*=.9;m+=.1*g;v*=.999;v+=.001*g*g
            p-=.011*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
    fused=ih/scale
    for margin in (.04,.16):
        model=dict(format='pvz-native-option-value-1',sim_fingerprint=read(OLD_Z)['sim_fingerprint'],
                   hidden=np.column_stack([fused,bh-fused@mean]).tolist(),head=np.column_stack([oh,bo]).tolist(),
                   margin=margin,position_parent=sha(OLD_Z),training=[sha(ROOT/(f+'.json')) for f in ('branches','branches-extra','branches-timed')],choices=CHOICES)
        path=MODELS_DIR/f'z{int(100*margin):02}.json';write(path,model)
    write(ROOT/'fit.json',dict(positions=len(x),unique_openings=len(counts),effective_label_sets=len(duplicates),distinct_prefixes=len({g['prefix'] for g in data}),steps=120,
         outcome_sensitive=sum(len(set(g['outcomes']))>1 for g in data),
         pressure_or_outcome_sensitive=sum(bool(np.ptp(g['labels'])>1e-6) for g in data),
         advance=Counter(g['statuses'][2] for g in data),advance_built=sum(g['built'] for g in data),
         features=x.shape[1],hidden=8,train_mse=float(np.mean((np.tanh(x@ih.T+bh)@oh.T+bo-y)**2))))

def ranked(pairs,side):
    margins={}
    for opp,values in pairs.items():
        delta=0
        for a,b in values:
            old=trace(a);new=trace(b);v=outcome(new,side)
            if old['timeout']==False and outcome(old,side)<0 and new['timeout'] and slow(old,new):v=-1
            delta+=v-outcome(old,side)
        margins[opp]=delta
    return margins

def zombie():
    enrich()
    # Check the other three-way contrasts as well. A save or advance may survive
    # a root where another branch loses even if the default itself also survives.
    groups=training_groups()
    alternatives=[]
    for group in groups:
        corpus=Path(group.get('corpus',ROOT/'plain'))
        if 'after' in group:after=group['after']
        else:
            i=read(ROOT/'splits.json')['train'].index(group['id']);j='onb'.index(group['opponent']);after=(12,55,105)[(i+j)%3]
        gs=[Game(group['id'],MODELS[group['opponent']],forced=o,after=after,corpus=corpus) for o in range(4)]
        assert [g.key() for g in gs]==group['keys']
        alternatives.extend((a,b,'zombie') for a in gs for b in gs if a!=b)
    write(ROOT/'branch-horizons.json',dict(cases=extend(alternatives)))
    train_values()
    ids=read(ROOT/'splits.json')['validation'];scores={};pairs={}
    for tag in ('04','16'):
        model=MODELS_DIR/f'z{tag}.json'
        pairs[tag]={o:[(Game(i,MODELS[o]),Game(i,MODELS[o],policy=model)) for i in ids] for o in 'onb'}
    batch('frozen plant validation',[g for p in pairs.values() for rows in p.values() for row in rows for g in row])
    chosen=lambda m:(min(m.values()),sum(m.values()))
    for tag,p in pairs.items():scores[tag]=ranked(p,'zombie')
    best=max(scores,key=lambda t:(chosen(scores[t]),t=='16'))
    ex=extend((a,b,'zombie') for p in pairs.values() for rows in p.values() for a,b in rows)
    path=MODELS_DIR/f'z{best}.json'
    # Check numerical parity between the native inference and training representation.
    model=read(path);h=np.array(model['hidden']);v=np.array(model['head']);checked=0
    for rows in pairs[best].values():
        for _,g in rows:
            for e in trace(g)['options']:
                q=v@np.r_[np.tanh(h@np.r_[e['x'],1.]),1.]
                assert np.allclose(q,e['values'],rtol=1e-8,atol=1e-8)
                c=int(np.argmax(q));assert e['choice']==(c if q[c]-q[0]>=model['margin'] else 0)
                checked+=1
    assert checked>0
    write(ROOT/'zombie-frozen.json',dict(model=str(path),sha256=sha(path),scores=scores,selected=best,
          parent=sha(OLD_Z),native_scores_verified=checked,extensions=ex))

def plant():
    zf=read(ROOT/'zombie-frozen.json');z=Path(zf['model']);assert sha(z)==zf['sha256']
    s=read(ROOT/'splits.json');parent=read(OLD_P)
    base=np.array(parent['heads']['weight'])[:12,-28:]
    rng=np.random.default_rng(80619)
    directions=[rng.normal(0,.09,base.shape)+np.linspace(-1,1,12)[:,None]*rng.normal(0,.24,(1,28)) for _ in range(2)]
    paths={'parent':OLD_P}
    def save(tag,delta):
        doc=read(OLD_P)
        for j,row in enumerate(base+delta):doc['heads']['weight'][j][-28:]=row.tolist()
        doc['training_source']=dict(parent=sha(OLD_P),frozen_zombie=sha(z),method='symmetric paired native game returns')
        path=MODELS_DIR/f'plant-{tag}.json';write(path,doc);return path
    for j,d in enumerate(directions):
        for tag,sign in [('p',1),('m',-1)]:paths[f'{j}{tag}']=save(f'{j}{tag}',sign*d)
    def pairs(tag,ids):
        return [(Game(i,OLD_P,policy=z),Game(i,paths[tag],policy=z)) for i in ids]
    train={t:pairs(t,s['train']) for t in paths if t!='parent'}
    batch('train plant against frozen learned zombie',[g for rows in train.values() for pair in rows for g in pair])
    gains=ranked(train,'plant');coeff=np.array([gains[f'{j}p']-gains[f'{j}m'] for j in range(2)])
    coeff=coeff/max(1.,sum(abs(coeff)));best_probe=max(gains,key=gains.get)
    candidates=[best_probe]
    if np.any(coeff):
        paths['step']=save('step',sum(c*d for c,d in zip(coeff,directions)));candidates.append('step')
    v={t:pairs(t,s['validation']) for t in candidates}
    batch('plant validation against same frozen zombie',[g for rows in v.values() for a in rows for g in a])
    val=ranked(v,'plant');val['parent']=0
    best=max(val,key=lambda t:(val[t],t=='parent',t=='step'))
    ex=extend((a,b,'plant') for p in (train,v) for rows in p.values() for a,b in rows)
    write(ROOT/'plant-frozen.json',dict(model=str(paths[best]),sha256=sha(paths[best]),selected=best,
          training=gains,validation=val,coefficients=coeff.tolist(),frozen_zombie=sha(z),extensions=ex,
          parents={'plant':sha(OLD_P),'position':sha(OLD_Z)}))

def paired_result(groups,side,ids):
    rng=np.random.default_rng(619207)
    opp=list(groups);returns=np.zeros((len(ids),len(opp)));adjusted=returns.copy()
    result={};allrows=[]
    for j,o in enumerate(opp):
        rows=[]
        for i,(a,b) in enumerate(groups[o]):
            assert a.uid==b.uid==ids[i]
            old=trace(a);new=trace(b);before=outcome(old,side);after=outcome(new,side)
            flag=bool(before==-1 and new['timeout'] and slow(old,new))
            d=after-before;returns[i,j]=d;adjusted[i,j]=d-int(flag)
            end=min(old['time'],new['time'])
            tempo={}
            for team in ('plant','zombie'):
                x=measure(old['activity'],team,end);y=measure(new['activity'],team,end)
                tempo[team]=[dict(deploys=v['deploys'],rich_idle=v['rich_idle'],mean_resource=v['mean_resource']) for v in (x,y)]
            rows.append(dict(id=a.uid,opponent=o,baseline=a.key(),candidate=b.key(),old=before,new=after,
                             old_end=old['time'],new_end=new['time'],window=end,tempo=tempo,stall=flag))
        allrows+=rows
        def counts(k):return [sum(v[k]==n for v in rows) for n in (1,0,-1)]
        result[o]=dict(before=counts('old'),after=counts('new'),net=int(returns[:,j].sum()),
                       transitions=dict(Counter(f"{r['old']}/{r['new']}" for r in rows)))
    paired=adjusted.mean(axis=1);interval=np.quantile(paired[rng.integers(0,len(ids),(20000,len(ids)))].mean(axis=1),[.025,.975]).tolist()
    halves=[int(block.sum()) for block in np.array_split(adjusted,2)]
    passed=all(v>0 for v in halves) and min(adjusted.sum(axis=0))>=0 and interval[0]>0 and not any(r['stall'] for r in allrows)
    timing={}
    for name,k in [('parent',0),('candidate',1)]:
        exposure=sum(r['window'] for r in allrows)
        timing[name]=dict(mean_capped_seconds=np.mean([r['old_end' if k==0 else 'new_end'] for r in allrows]),
                          common_window_deploys_per_min={s:60*sum(r['tempo'][s][k]['deploys'] for r in allrows)/exposure for s in ('plant','zombie')},
                          common_window_rich_idle_fraction={s:sum(r['tempo'][s][k]['rich_idle'] for r in allrows)/exposure for s in ('plant','zombie')})
    return dict(per_opponent=result,net=int(returns.sum()),adjusted_net=int(adjusted.sum()),paired_mean95=interval,tempo=timing,
                two_halves=halves,stable=bool(passed),rows=allrows)

def route_audit(z,ids):
    # Secondary held-out test. The starting states are visited by the same frozen
    # parent used during training; each treatment restores it after one option.
    plan=read(ROOT/'route-test-plan.json')
    assert plan['ids']==ids[::3]
    h=np.array(read(z)['hidden']);v=np.array(read(z)['head']);margin=read(z)['margin']
    groups=[]
    for j,i in enumerate(plan['ids']):
        for k,o in enumerate(plan['opponents']):
            when=plan['trigger_times'][(j+k)%3]
            groups.append((i,o,[Game(i,MODELS[o],forced=c,after=when) for c in range(4)]))
    batch('sealed same-state option ranking',[g for _,_,gs in groups for g in gs])
    def inspect(uid,o,gs):
        ts=[trace(g) for g in gs];episodes=[t['options'] for t in ts]
        if not episodes[0]:
            assert all(not events for events in episodes)
            return None
        root=episodes[0][0]
        assert all(len(events)==1 and events[0]['prefix']==root['prefix'] and events[0]['x']==root['x'] for events in episodes)
        q=v@np.r_[np.tanh(h@np.r_[root['x'],1.]),1.]
        choice=int(np.argmax(q))
        if q[choice]-q[0]<margin:choice=0
        scores=[outcome(t,'zombie') for t in ts]
        return dict(id=uid,opponent=o,at=root['time'],prefix=root['prefix'],q=q.tolist(),choice=choice,
             outcomes=scores,actual=scores[choice],default=scores[0],best=max(scores),keys=[g.key() for g in gs])
    result=[];missing=[];pairs=[];extra=[]
    for uid,o,gs in groups:
        row=inspect(uid,o,gs)
        if row is None:missing.append([uid,o]);continue
        result.append(row);pairs.extend((a,b,'zombie') for a in gs for b in gs if a!=b)
    # Take one verified decision per additional seed, using only the opportunity's
    # time and inputs. This stratified diagnostic has its own denominator.
    used={r['id'] for r in result}
    supplement=read(ROOT/'route-support-plan.json')
    for i in ids:
        if i in used or len(extra)>=supplement['max_extra']:continue
        for o in supplement['opponents']:
            roots=trace(Game(i,MODELS[o],policy=z))['options']
            if roots:
                t=roots[0]['time'];gs=[Game(i,MODELS[o],forced=c,after=t) for c in range(4)]
                extra.append((i,o,gs));break
    if extra:batch('fresh legal decision diagnostic',[g for _,_,gs in extra for g in gs])
    supported=[]
    for uid,o,gs in extra:
        r=inspect(uid,o,gs);e=trace(Game(uid,MODELS[o],policy=z))['options'][0]
        assert r and abs(r['at']-e['time'])<1e-6 and r['choice']==e['choice']
        supported.append(r);pairs.extend((a,b,'zombie') for a in gs for b in gs if a!=b)
    write(ROOT/'route-test.json',dict(rows=result,unavailable=missing,additional_eligible=supported,extensions=extend(pairs)))

def test():
    zf=read(ROOT/'zombie-frozen.json');pf=read(ROOT/'plant-frozen.json')
    z=Path(zf['model']);p=Path(pf['model'])
    assert sha(z)==zf['sha256']==pf['frozen_zombie'] and sha(p)==pf['sha256']
    split=read(ROOT/'splits.json');ids=split['test']
    def decks(g):return tuple(tuple(sorted(g['decks'][k])) for k in ('plant','zombie'))
    entries=read(ROOT/'plain/index.json')['entries'];assert sha(ROOT/'plain/index.json')==split['corpus']
    old=[decks(g) for g in entries if g['id'] not in ids]
    for index in split['past_indexes']:
        old.extend(decks(g) for g in read(ROOT.parents[1]/index)['entries'] if g.get('map')=='家院' and 'decks' in g)
    tests=[decks(g) for g in entries if g['id'] in ids]
    assert len(tests)==18 and all(not {g[j] for g in tests}&{g[j] for g in old} for j in (0,1))
    groups={'zombie_parent':{},'zombie_legacy':{},'plant_parent':{}}
    for o in 'rhb':
        rival=MODELS[o]
        groups['zombie_parent'][o]=[(Game(i,rival),Game(i,rival,policy=z)) for i in ids]
        groups['zombie_legacy'][o]=[(Game(i,rival,position=None),Game(i,rival,policy=z)) for i in ids]
        groups['plant_parent'][o]=[(Game(i,OLD_P,rival,None),Game(i,p,rival,None)) for i in ids]
    batch('sealed home cross-play',[g for gs in groups.values() for rows in gs.values() for ab in rows for g in ab])
    summary={}
    for name,gs in groups.items():
        seat=name.split('_')[0];summary[name]=paired_result(gs,seat,ids)
        summary[name]['extensions']=extend((a,b,seat) for rows in gs.values() for a,b in rows)
    option_uses=Counter();status=Counter();successful_builds=0;total=0;native_spawns=0
    for rows in groups['zombie_parent'].values():
        for _,g in rows:
            r=trace(g)
            for e in r['options']:
                total+=1;option_uses[e['choice']]+=1;status[e['status']]+=1;successful_builds+=bool(e.get('built'))
                if e.get('spawn'):
                    assert any(c.get('grave')==e['spawn']['source'] and c['card']==e['spawn']['card'] and c['accepted'] and c['tick']==round(e['spawn']['time']*30) for c in r['accepted_commands'] if c['kind']=='deploy')
                    native_spawns+=1
    inputs_ok()
    route_audit(z,ids)
    write(ROOT/'complete.json',dict(comparisons=summary,openings=len(ids),unique_paired_decks=len(set(tests)),
          zombie=sha(z),plant=sha(p),dispatch=dict(total=total,choices=option_uses,status=status,builds=successful_builds,spawns=native_spawns),
          research_only=True))

def plant_trial():
    spec=read(ROOT/'plant-trial-frozen.json')
    p=Path(spec['model']);assert sha(p)==spec['sha256'] and sha(p)!=sha(OLD_P)
    ids=read(ROOT/'splits.json')['test']
    pairs={o:[(Game(i,OLD_P,MODELS[o],None),Game(i,p,MODELS[o],None)) for i in ids] for o in 'rhb'}
    batch('independent test of the actually updated plant weights',[g for rows in pairs.values() for ab in rows for g in ab])
    r=paired_result(pairs,'plant',ids)
    r['extensions']=extend((a,b,'plant') for rows in pairs.values() for a,b in rows)
    write(ROOT/'plant-trial.json',dict(frozen=spec,results=r))

def explain():
    # Retrospective mechanics check; these rows never participate in fitting or
    # estimating accuracy on independently sampled decision points.
    primary=read(ROOT/'complete.json')['comparisons']['zombie_parent']
    z=Path(read(ROOT/'zombie-frozen.json')['model']);jobs=[];cases=[];seen=set()
    for row in primary['rows']:
        if row['old']==row['new']:continue
        uid=row['id'];o=row['opponent'];base=Game(uid,MODELS[o]);actual=replace(base,policy=z)
        a,b=trace(base),trace(actual);changes=[e for e in b['options'] if e['choice']]
        if len(changes)!=1:continue
        key=(a['log_sha256'],b['log_sha256'])
        if key in seen:continue
        seen.add(key);event=changes[0]
        gs=[replace(base,forced=c,after=event['time']) for c in range(4)]
        jobs.append((uid,o,event,base,actual,gs))
    batch('reproduce unique changed endings with one treatment',[g for *_,gs in jobs for g in gs])
    pairs=[]
    for uid,o,e,base,actual,gs in jobs:
        rows=[trace(g) for g in gs]
        assert len({r['options'][0]['prefix'] for r in rows})==1
        assert all(r['options'][0]['x']==e['x'] for r in rows)
        assert rows[0]['log_sha256']==trace(base)['log_sha256']
        assert rows[e['choice']]['log_sha256']==trace(actual)['log_sha256']
        cases.append(dict(id=uid,opponent=o,at=e['time'],choice=e['choice'],values=e['values'],prefix=rows[0]['options'][0]['prefix'],
                     outcomes=[outcome(r,'zombie') for r in rows],times=[r['time'] for r in rows],keys=[g.key() for g in gs],
                     statuses=[r['options'][0]['status'] for r in rows],exact_original_log=True))
        pairs.extend((a,b,'zombie') for a in gs for b in gs if a!=b)
    write(ROOT/'changed-home-branches.json',dict(cases=cases,extensions=extend(pairs),postselected=True))

def run(stage):
    if stage=='branches':branches()
    elif stage=='extra':extra_branches()
    elif stage=='zombie':zombie()
    elif stage=='plant':plant()
    elif stage=='test':test()
    elif stage=='plant-trial':plant_trial()
    elif stage=='explain':explain()
    else:raise ValueError(stage)
