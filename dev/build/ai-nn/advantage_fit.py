"""Matched native rollouts, opening-level ranking checks, and alternating best responses."""
from collections import Counter
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import numpy as np
from advantage_study import OUT,ROOT,PRIOR,CORPUS,FORK,PARENT,STRONG,PLANTS,OPPONENTS,game,fixed
from option_study import OLD_P,inputs_ok,read,sha
from option_games import Game,MODELS,batch,trace,outcome,slow,extend
from option_fit import ranked,paired_result

def training_scans(legacy=False):
    sources=[(ROOT/'plain',read(ROOT/'splits.json')['train'],'old')]
    sources.append((PRIOR/'robust/diverse/plain',read(PRIOR/'robust/diverse/ready.json')['ids'],'diverse'))
    if not legacy:sources.insert(0,(CORPUS,read(OUT/'splits.json')['train'],'new'))
    scans=[]
    for corpus,ids,name in sources:
        for j,i in enumerate(ids):
            opponents=list(PLANTS) if name=='new' else ['r','p' if j%2==0 else 'o']
            for o in opponents:
                g=Game(i,PLANTS[o],policy=PARENT,corpus=corpus,storage=OUT)
                scans.append((name,i,o,g))
    return scans

def routes():
    scans=training_scans()
    batch('scan frozen parent in home openings',[g for _,_,_,g in scans])
    # Farthest-point selection in the public feature vector. Cycle through
    # incumbent actions, openings, and later states reached after an earlier change.
    available=[]; signatures=set()
    for name,uid,o,g in scans:
        changed=False
        for e in trace(g)['options']:
            sig=(name,uid,round(e['time']*30),tuple(e['x']))
            if sig not in signatures:
                available.append(dict(opening=name+'/'+uid,uid=uid,opponent=o,corpus=str(g.corpus),time=e['time'],
                    x=e['x'],incumbent=e['choice'],previous_change=changed,scan=g.key()))
                signatures.add(sig)
            changed|=bool(e['choice'])
    assert available
    x=np.array([r['x'] for r in available]);x/=np.maximum(.12,np.std(x,axis=0))
    used=set();selected=[];counts=Counter();cover=np.ones(len(x))*100.
    action_counts=Counter();history_counts=Counter()
    for _ in range(min(64,len(x))):
        possible=[i for i,r in enumerate(available) if i not in used and counts[r['opening']]<5]
        if not possible:break
        def priority(i):
            r=available[i]
            return (-counts[r['opening']],-action_counts[r['incumbent']],-history_counts[r['previous_change']],cover[i],-i)
        i=max(possible,key=priority);used.add(i);r=available[i];selected.append(r)
        counts[r['opening']]+=1;action_counts[r['incumbent']]+=1;history_counts[r['previous_change']]+=1
        cover=np.minimum(cover,np.mean((x-x[i])**2,axis=1))
    fixed(OUT/'sample.json',dict(available=len(available),scan_games=len(scans),roots=selected,by_incumbent={str(k):v for k,v in action_counts.items()},
        after_previous_intervention=sum(r['previous_change'] for r in selected)))
    groups=[];scan_by_key={g.key():g for _,_,_,g in scans}
    for r in selected:
        ref=scan_by_key[r['scan']]
        forks=[replace(ref,binary=FORK,forced=j,after=r['time']) for j in range(4)]
        groups.append((r,ref,forks))
    batch('one intervention then frozen neural continuation',[g for _,_,gs in groups for g in gs])
    matched=[(a,b,'zombie') for _,_,gs in groups for a in gs for b in gs if a!=b]
    extensions=extend(matched)
    informative_timeouts=[g for _,_,gs in groups if len({outcome(trace(x),'zombie') for x in gs})>1 for g in gs if trace(g)['timeout']]
    batch('resolve remaining informative training timeouts',[replace(g,limit=1200) for g in informative_timeouts])
    dataset=[]
    for description,ref,gs in groups:
        roots=[[e for e in trace(g)['options'] if e.get('forked')][0] for g in gs]
        t=description['time'];original=trace(ref)
        assert len({e['prefix'] for e in roots})==1 and all(e['x']==description['x'] and e['time']==t for e in roots)
        assert all((e['proposed_spawn'],e['proposed_front'])==(roots[0]['proposed_spawn'],roots[0]['proposed_front']) for e in roots)
        parity=trace(gs[description['incumbent']])
        assert parity['log_sha256']==original['log_sha256']
        for field in ('activity','spatial_actions','accepted_commands'):
            assert parity[field]==original[field]
        returns=[outcome(trace(g),'zombie') for g in gs]
        label=[];longs=[];suffixes=[]
        for g,e in zip(gs,roots):
            tr=trace(g);v=outcome(tr,'zombie');long=None
            assert all([a for a in tr[f] if round(a[k]*30)<round(t*30)]==[a for a in original[f] if round(a[k]*30)<round(t*30)]
                       for f,k in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')])
            for kind in ('built','spawn'):
                if e.get(kind):
                    action=e[kind]
                    assert any(c['kind']=='deploy' and c['accepted'] and c['tick']==round(action['time']*30)
                        and c['card']==action['card'] and (kind=='built' or c.get('grave')==action['source']) for c in tr['accepted_commands'])
            if tr['timeout'] and len(set(returns))>1:
                long=replace(g,limit=1200);l=trace(long)
                for f,k in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')]:
                    assert [a for a in tr[f] if a[k]<600]==[a for a in l[f] if a[k]<600]
                v=.5*outcome(l,'zombie')
                if any(slow(trace(h),tr) for h in gs if outcome(trace(h),'zombie')<0):v=-1.
            label.append(v);longs.append(long.key() if long else None)
            suffixes.append(sum(z['time']>t for z in tr['options']))
        dataset.append(dict(**description,keys=[g.key() for g in gs],prefix=roots[0]['prefix'],outcomes=returns,
            targets=label,extended=longs,followup_decisions=suffixes,advance_status=roots[2]['status']))
    fixed(OUT/'training.json',dict(rows=dataset,extensions=extensions))

def predict(model,x):
    h=np.array(model['hidden']);v=np.array(model['head'])
    return np.tanh(x@h[:,:-1].T+h[:,-1])@v[:,:-1].T+v[:,-1]

def choices(q,margin):
    action=np.argmax(q,axis=1)
    return np.where(q[np.arange(len(q)),action]-q[:,0]>=margin,action,0)

def fit(rows,method):
    prior=read(PARENT)
    x=np.array([r['x'] for r in rows]);y=np.array([r['targets'] for r in rows])
    counts=Counter(r['opening'] for r in rows);w=np.array([1/counts[r['opening']] for r in rows]);w/=w.sum()
    mean=w@x;scale=np.maximum(.12,np.sqrt(w@((x-mean)**2)));x=(x-mean)/scale
    h=np.array(prior['hidden']);v=np.array(prior['head'])
    ih=h[:,:-1]*scale;bh=h[:,-1]+h[:,:-1]@mean;oh=v[:,:-1].copy();bo=v[:,-1].copy()
    params=[ih,bh,oh,bo];anchor=[p.copy() for p in params]
    parent_q=np.tanh(x@ih.T+bh)@oh.T+bo;parent_q-=parent_q.mean(1,keepdims=True)
    y-=y.mean(1,keepdims=True)
    mom=[np.zeros_like(p) for p in params];vel=[p.copy() for p in mom]
    for step in range(1,91):
        hidden=np.tanh(x@ih.T+bh);q=hidden@oh.T+bo;q-=q.mean(1,keepdims=True)
        if method=='mean':
            dq=(q-y)/2
        else:
            dq=np.zeros_like(q)
            for a,b in combinations(range(4),2):
                target=y[:,a]-y[:,b];delta=q[:,a]-q[:,b];sign=np.sign(target)
                # A loss-to-win mistake costs twice a loss-to-timeout mistake.
                direction=-sign*np.abs(target)/(1+np.exp(np.clip(sign*delta/.5,-40,40)))
                d=np.where(sign==0,.10*delta,direction)/3.
                dq[:,a]+=d;dq[:,b]-=d
        dq=w[:,None]*(dq+.07*(q-parent_q));dq-=dq.mean(1,keepdims=True)
        dh=(dq@oh)*(1-hidden**2)
        grads=[dh.T@x,dh.sum(0),dq.T@hidden,dq.sum(0)]
        for p,p0,m,u,g in zip(params,anchor,mom,vel,grads):
            g+=.018*(p-p0);m*=.9;m+=.1*g;u*=.999;u+=.001*g*g
            p-=.009*(m/(1-.9**step))/(np.sqrt(u/(1-.999**step))+1e-8)
    fused=ih/scale
    return {**prior,'hidden':np.column_stack([fused,bh-fused@mean]).tolist(),'head':np.column_stack([oh,bo]).tolist(),
            'training':sha(OUT/'training.json'),'training_method':method,'option_parent':sha(PARENT)}

def zombie():
    rows=read(OUT/'training.json')['rows'];assert len({r['opening'] for r in rows})>=8
    openings=sorted({r['opening'] for r in rows});np.random.default_rng(474972).shuffle(openings)
    folds={o:i%4 for i,o in enumerate(openings)};cv={};paths={}
    for method in ('mean','rank'):
        tests=[]
        for fold in range(4):
            train=[r for r in rows if folds[r['opening']]!=fold];hold=[r for r in rows if folds[r['opening']]==fold]
            model=fit(train,method);x=np.array([r['x'] for r in hold]);action=choices(predict(model,x),model['margin'])
            for r,a in zip(hold,action):
                y=r['targets'];base=y[r['incumbent']]
                tests.append(dict(opening=r['opening'],picked=int(a),incumbent=r['incumbent'],gain=y[a]-base,
                                  regret=max(y)-y[a],incumbent_regret=max(y)-base,informative=len(set(y))>1))
        cv[method]=tests
        path=OUT/'models'/f'z-{method}.json';fixed(path,fit(rows,method));paths[method]=path
    ids=read(OUT/'splits.json')['validation']
    pairs={m:{o:[(game(i,PLANTS[o],policy=PARENT),game(i,PLANTS[o],policy=p)) for i in ids] for o in PLANTS} for m,p in paths.items()}
    batch('full-game zombie validation',[g for targets in pairs.values() for rs in targets.values() for ab in rs for g in ab])
    val={k:ranked(v,'zombie') for k,v in pairs.items()}
    def order(k):
        v=val[k]
        grouped={o:np.mean([r['gain'] for r in cv[k] if r['opening']==o]) for o in openings}
        return min(v.values()),sum(v.values()),np.mean(list(grouped.values())),k=='rank'
    best=max(paths,key=order);p=paths[best]
    ex=extend((a,b,'zombie') for targets in pairs.values() for rs in targets.values() for a,b in rs)
    checked=0
    for rs in pairs[best].values():
        for _,b in rs:
            for e in trace(b)['options']:
                v=predict(read(p),np.array([e['x']]))
                assert np.allclose(v[0],e['values']) and choices(v,read(p)['margin'])[0]==e['choice'];checked+=1
    assert checked
    fixed(OUT/'zombie.json',dict(path=str(p),model=sha(p),selected=best,cv=cv,validation=val,extensions=ex,
          native_predictions=checked,validation_gate=min(val[best].values())>=0 and sum(val[best].values())>0))

def plant():
    lock=read(OUT/'zombie.json');challenger=Path(lock['path']);assert sha(challenger)==lock['model']
    z=challenger if lock['validation_gate'] else PARENT
    splits=read(OUT/'splits.json')
    base=np.array(read(STRONG)['heads']['weight'])[:12,-28:]
    previous=base-np.array(read(OLD_P)['heads']['weight'])[:12,-28:]
    assert np.linalg.norm(previous)>0
    rng=np.random.default_rng(412588)
    new=rng.normal(size=base.shape)+np.linspace(-1,1,12)[:,None]*rng.normal(0,2,(1,28))
    new-=np.sum(new*previous)/np.sum(previous**2)*previous
    new*=np.linalg.norm(previous)/np.linalg.norm(new)
    directions=[previous*.60,new*.60];paths={}
    def save(tag,delta):
        model=read(STRONG)
        for j,row in enumerate(base+delta):model['heads']['weight'][j][-28:]=row.tolist()
        model['training_source']=dict(plant_parent=sha(STRONG),fixed_zombie=sha(z),kind='paired game returns')
        p=OUT/'models'/f'p-{tag}.json';fixed(p,model);return p
    for j,d in enumerate(directions):
        for sign,name in ((1,'p'),(-1,'m')):paths[f'{j}{name}']=save(f'{j}{name}',sign*d)
    def pairs(model,ids):
        return {'z':[ (game(i,STRONG,policy=z),game(i,model,policy=z)) for i in ids],
                'r':[ (game(i,STRONG,zombie=None,position=None),game(i,model,zombie=None,position=None)) for i in ids]}
    train={tag:pairs(p,splits['train']) for tag,p in paths.items()}
    def play_targets(label,targets):
        batch(label,[g for tags in targets.values() for rows in tags.values() for ab in rows for g in ab])
        return {tag:ranked(rs,'plant') for tag,rs in targets.items()}
    gains=play_targets('train plant against frozen zombie and r22',train)
    score=lambda v:(min(v.values()),sum(v.values()))
    best_train=max(gains,key=lambda k:score(gains[k]))
    grad=np.array([sum(gains[f'{j}p'].values())-sum(gains[f'{j}m'].values()) for j in (0,1)])
    coeff=grad/max(1.,sum(abs(grad)));candidates=[best_train]
    if sum(abs(grad)):
        step=sum(c*d for c,d in zip(coeff,directions))
        same=next((f'{j}{name}' for j,d in enumerate(directions) for sign,name in ((1,'p'),(-1,'m'))
                   if np.array_equal(step,sign*d)),None)
        if same is None:
            paths['step']=save('step',step);candidates.append('step')
        elif same!=best_train:candidates.append(same)
    valpairs={tag:pairs(paths[tag],splits['validation']) for tag in candidates}
    val=play_targets('validate plant',valpairs)
    best=max(candidates,key=lambda k:(score(val[k]),k==best_train))
    ex=extend((a,b,'plant') for sets in (train,valpairs) for tags in sets.values() for rs in tags.values() for a,b in rs)
    fixed(OUT/'plant.json',dict(selected=best,path=str(paths[best]),model=sha(paths[best]),parent=sha(STRONG),
        frozen_zombie=sha(z),train=gains,validation=val,coeff=coeff.tolist(),extensions=ex,
        validation_gate=min(val[best].values())>=0 and sum(val[best].values())>0))

def test():
    inputs_ok();locks=[read(OUT/(s+'.json')) for s in ('zombie','plant')]
    z,p=[Path(r['path']) for r in locks]
    assert [sha(z),sha(p)]==[r['model'] for r in locks]
    split=read(OUT/'splits.json');assert sha(CORPUS/'index.json')==split['corpus']
    all_ids=split['a']+split['b'];matrix={}
    for side in ('zombie','plant'):
        matrix[side]={}
        for o in OPPONENTS:
            rival=MODELS[o]
            matrix[side][o]=[(game(i,rival,policy=PARENT),game(i,rival,policy=z)) if side=='zombie' else
                (game(i,STRONG,zombie=rival,position=None),game(i,p,zombie=rival,position=None)) for i in all_ids]
    batch('two sealed home cohorts, single-seat substitutions',[g for v in matrix.values() for rs in v.values() for ab in rs for g in ab])
    summary={};extensions=[]
    for side,groups in matrix.items():
        report={}
        for label,ids in [('a',split['a']),('b',split['b']),('all',all_ids)]:
            rs={o:[(a,b) for a,b in pairs if a.uid in ids] for o,pairs in groups.items()}
            report[label]=paired_result(rs,side,ids)
        report['stable']=bool(all(report[k]['adjusted_net']>0 and min(r['net'] for r in report[k]['per_opponent'].values())>=0 for k in ('a','b'))
                          and report['all']['paired_mean95'][0]>0 and not any(r['stall'] for r in report['all']['rows']))
        summary[side]=report
        extensions+=extend((a,b,side) for rs in groups.values() for a,b in rs)
    decision_counts={};changed=Counter()
    for o,rs in matrix['zombie'].items():
        counts=Counter()
        for old,new in rs:
            a=trace(old);b=trace(new)
            changed[o]+=a['log_sha256']!=b['log_sha256']
            for e in b['options']:counts[e['choice']]+=1
        decision_counts[o]={str(k):v for k,v in counts.items()}
    fixed(OUT/'test.json',dict(results=summary,extensions=extensions,actions=decision_counts,changed_logs=changed,
        zombie=sha(z),plant=sha(p),n_openings=len(all_ids)))

def ranking_test():
    z=Path(read(OUT/'zombie.json')['path'])
    split=read(OUT/'splits.json');seen={};wanted=[]
    for c in ('a','b'):
        count=0
        for j,uid in enumerate(split[c]):
            o=('r','h','b')[j%3];ref=game(uid,MODELS[o],policy=PARENT)
            options=trace(ref)['options']
            if not options:continue
            target=min(options,key=lambda e:abs(e['time']-(50 if j%2==0 else 150)))
            gs=[replace(ref,binary=FORK,forced=a,after=target['time']) for a in range(4)]
            seen[(c,uid)]=(ref,target,gs,o);wanted.extend(gs);count+=1
            if count==6:break
    batch('unseen single-decision ranking, outcome-blind selection',wanted)
    records=[];ex=extend((a,b,'zombie') for _,_,gs,_ in seen.values() for a in gs for b in gs if a!=b)
    for (c,uid),(ref,e,gs,o) in seen.items():
        rs=[trace(g) for g in gs];events=[next(a for a in r['options'] if a.get('forked')) for r in rs]
        assert len({a['prefix'] for a in events})==1 and all(a['x']==e['x'] for a in events)
        assert rs[e['choice']]['log_sha256']==trace(ref)['log_sha256']
        model=read(z);q=predict(model,np.array([e['x']]));pick=int(choices(q,model['margin'])[0])
        scores=[outcome(r,'zombie') for r in rs]
        records.append(dict(cohort=c,uid=uid,opponent=o,at=e['time'],parent=e['choice'],candidate=pick,actual=scores,
            regret_old=max(scores)-scores[e['choice']],regret_new=max(scores)-scores[pick],keys=[g.key() for g in gs]))
    fixed(OUT/'ranking-test.json',dict(rows=records,extensions=ex))

def continuation_check():
    # Compare the old and new label definitions with the same state and same
    # intervention. No test starts and no outcome-based choice of examples.
    rows=read(OUT/'training.json')['rows'];selected=[];used=set()
    for r in rows:
        if r['previous_change'] or r['opening'] in used:continue
        if min(r['followup_decisions'])<1:continue
        selected.append(r);used.add(r['opening'])
        if len(selected)==8:break
    groups=[[Game(r['uid'],PLANTS[r['opponent']],corpus=Path(r['corpus']),storage=OUT,forced=j,after=r['time'])
             for j in range(4)] for r in selected]
    batch('measure label changes from subsequent policy alone',[g for gs in groups for g in gs])
    results=[];unmatched=[]
    for r,gs in zip(selected,groups):
        ts=[trace(g) for g in gs]
        if any(not t['options'] or t['options'][0]['prefix']!=r['prefix'] or t['options'][0]['x']!=r['x'] for t in ts):
            unmatched.append(r['opening']);continue
        old=[outcome(t,'zombie') for t in ts]
        results.append(dict(opening=r['opening'],opponent=r['opponent'],time=r['time'],prefix=r['prefix'],
                         spatial_only_followup=old,option_policy_followup=r['outcomes'],before_keys=[g.key() for g in gs],after_keys=r['keys']))
    # Include timeouts introduced either by changing the initial choice or by
    # changing the continuation, but compare continuations only for identical roots.
    pairs=[(a,b,'zombie') for gs in groups for a in gs for b in gs if a!=b]
    for r,gs in zip(selected,groups):
        if r['opening'] in unmatched:continue
        for j,a in enumerate(gs):
            b=replace(a,binary=FORK,policy=PARENT)
            assert b.key()==r['keys'][j]
            pairs.extend([(a,b,'zombie'),(b,a,'zombie')])
    fixed(OUT/'continuation.json',dict(rows=results,unmatched=unmatched,extensions=extend(pairs)))

def freeze_rules():
    fixed(OUT/'reverse-policy.json',dict(rule='For reverse training, replace the incumbent zombie sparring partner only if the challenger has nonnegative margin on every validation plant and positive total. Also train against r22. Retain the actual zombie challenger for blind testing whichever sparring partner wins.'))
    fixed(OUT/'selection.json',dict(max_train_roots=64,per_opening=5,lr=.009,updates=90,width=8,margin=read(PARENT)['margin'],
        validation='Zombie: highest worst fixed-opponent margin, then sum, then grouped cross-fit gain. Plant: strongest train probe or normalized two-direction step, selected by worst validation margin then sum. Freeze actual challengers for both blind cohorts independent of incumbent adoption.',
        ranking_probe='Per cohort, scan ascending ids with r22/H/B rotated, first six eligible unique ids. Nearest eligible parent decision to 50/150s by index parity; one override then same parent, four outcomes. Do not tune.',
        split=sha(OUT/'design.json')))

def blind_timeout_followup():
    test=read(OUT/'test.json')
    plant=Path(read(OUT/'plant.json')['path'])
    zombie=Path(read(OUT/'zombie.json')['path'])
    cases=[]
    for side,groups in test['results'].items():
        for r in groups['all']['rows']:
            if r['old']==r['new'] or 0 not in (r['old'],r['new']):continue
            rival=MODELS[r['opponent']]
            if side=='plant':
                before=game(r['id'],STRONG,zombie=rival,position=None)
                after=replace(before,plant=plant)
            else:
                before=game(r['id'],rival,policy=PARENT)
                after=replace(before,policy=zombie)
            assert [before.key(),after.key()]==[r['baseline'],r['candidate']]
            timed,finished=(before,after) if r['old']==0 else (after,before)
            winner=trace(finished)['result']['winner']
            loser='plant' if winner=='zombie' else 'zombie'
            cases.append((r,side,finished,timed,loser))
    # Use the same verified prefix extension whichever seat or model timed out.
    extensions=extend((f,t,loser) for _,_,f,t,loser in cases)
    assert len(extensions)==len(cases)
    rows=[dict(id=r['id'],opponent=r['opponent'],side=side,old=r['old'],new=r['new'],
               timed_model='parent' if r['old']==0 else 'candidate',timed=t.key(),long=e['extended'],
               winner=e['winner'],end=e['end'],timeout=e['timeout']) for (r,side,_,t,_),e in zip(cases,extensions)]
    fixed(OUT/'blind-timeouts.json',dict(test=sha(OUT/'test.json'),rows=rows))

def run(stage):
    freeze_rules()
    if stage=='scan-old':
        batch('frozen plant training opponents on previous development openings',[g for _,_,_,g in training_scans(True)])
    elif stage=='routes':routes()
    elif stage=='zombie':zombie()
    elif stage=='plant':plant()
    elif stage=='test':test()
    elif stage=='ranking-test':ranking_test()
    elif stage=='continuation':
        continuation_check()
        blind_timeout_followup()
    elif stage=='blind-timeouts':blind_timeout_followup()
    else:raise ValueError(stage)
