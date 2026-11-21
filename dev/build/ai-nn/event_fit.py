"""Native event rollouts, shared action fitting and paired evaluation."""
from collections import Counter, defaultdict
from dataclasses import replace
import json
from pathlib import Path
import numpy as np

from event_study import OUT,CORPUS,NATIVE,PROBE,LIVE,START,LAST,ROOT,PARENT,STRONG,PROGRAM,PLANTS,fixed,read,sha
from advantage_fit import training_scans
from option_games import Game,MODELS,batch,trace,outcome,slow,extend
from option_fit import paired_result

def g(uid,plant,**kw):
    kw.setdefault('binary',NATIVE)
    return Game(uid,plant,storage=OUT,corpus=CORPUS,**kw)

def historical():
    scans=training_scans()
    former=[(s,i,o,x) for s,i,o,x in scans if not trace(x)['options']]
    blocked={(str(x.corpus),i) for _,i,_,x in former}
    extra=[];used=set()
    for s,i,o,x in scans:
        key=str(x.corpus),i
        if key in used|blocked or o!=('p','o','r')[len(extra)%3]:continue
        extra.append((s,i,o,replace(x,binary=NATIVE,policy=START,storage=OUT)))
        used.add(key)
        if len(extra)==8:break
    return extra,former

def scans():
    return historical()[0]+[('fresh',i,o,g(i,opp,policy=START)) for i in read(OUT/'splits.json')['train'] for o,opp in PLANTS.items()]

def at_tick(tr,t):
    return [c for c in tr['accepted_commands'] if c['tick']==round(30*t) and c['accepted']]

def command_ok(e,tr):
    cmd=e['command'];actual=at_tick(tr,e['time'])
    if cmd[0]=='deploy':
        return any([c['card'],c.get('grave',''),c['x'],c['y'],c['facing']]==cmd[1:] for c in actual if c['kind']=='deploy')
    if any(c['kind']=='deploy' for c in actual):return False
    moves=[c for c in actual if c['kind']=='move']
    if not cmd[1]:return not moves
    return any(all(c.get(k,False)==cmd[1].get(k,False) for k in ('move','jump','edge') if k in c or k!='edge') for c in moves)

def choose_roots(all_scans):
    possible=[];seen=set()
    for source,uid,o,ref in all_scans:
        opening=source+'/'+uid
        for e in trace(ref)['options']:
            pool=e.get('pool',[])
            if len(pool)<2 or e['mask']==16:continue
            assert len({json.dumps(p['cmd'],sort_keys=True) for p in pool})==len(pool)
            key=(opening,round(30*e['time']),json.dumps(pool,sort_keys=True),e['mask'])
            if key in seen:continue
            seen.add(key)
            sp=[p['act'] for p in pool if p['act'][0]==2]
            possible.append((opening,o,ref,e,len({s[2] for s in sp})>1,len({s[1] for s in sp})>1))
    selected=[];counts=Counter();masks=Counter();rivals=Counter();buckets=Counter()
    while possible and len(selected)<52:
        bit=(1,2,4,8)[len(selected)%4]
        valid=[i for i,item in enumerate(possible) if counts[item[0]]<5]
        if not valid:break
        def priority(i):
            opening,o,ref,e,multi,card=possible[i];mask=e['mask'];bucket=int(e['time']//45)
            return (-counts[opening],bool(mask&bit),-rivals[o],-buckets[bucket],int(multi)+int(card),-masks[mask],len(e['pool']),-i)
        item=possible.pop(max(valid,key=priority));opening,o,ref,e,_,_=item
        counts[opening]+=1;masks[e['mask']]+=1;rivals[o]+=1;buckets[int(e['time']//45)]+=1;selected.append(item)
    assert len(selected)>=32 and len(counts)>=8
    return selected

def routes():
    all_scans=scans()
    batch('event-first scans against frozen plants',[a for *_,a in all_scans])
    selected=choose_roots(all_scans);groups=[]
    for opening,o,ref,e,_,_ in selected:
        groups.append([ref]+[replace(ref,forced=j,after=e['time']) for j in range(1,len(e['pool']))])
    fixed(OUT/'roots.json',dict(roots=[dict(opening=s[0],opponent=s[1],game=s[2].key(),time=s[3]['time'],
          mask=s[3]['mask'],commands=[p['cmd'] for p in s[3]['pool']]) for s in selected]))
    neutral=[replace(selected[j][2],forced=0,after=selected[j][3]['time']) for j in (0,len(selected)//2)]
    batch('distinct commands, reusing default continuations',[g for gs in groups for g in gs[1:]]+neutral)
    for j,g0 in zip((0,len(selected)//2),neutral):
        ref=trace(selected[j][2]);z=trace(g0)
        assert z['log_sha256']==ref['log_sha256'] and z['accepted_commands']==ref['accepted_commands']
    ex=extend((a,b,'zombie') for gs in groups for a in gs for b in gs if a!=b)
    targets={r['candidate']:r for r in ex};rows=[]
    for (opening,o,ref,e,_,_),gs in zip(selected,groups):
        root_time=e['time'];root_tick=round(root_time*30);parent=trace(ref)
        prefix=set();scores=[];commands=[];realized=set();actuals=[]
        for j,a in enumerate(gs):
            tr=trace(a);ev=e if j==0 else next(x for x in tr['options'] if x.get('forked'))
            assert ev['pool']==e['pool'] and ev['choice']==j and ev['time']==root_time
            if j:prefix.add(ev['prefix'])
            assert [x for x in tr['accepted_commands'] if x['tick']<root_tick]==[x for x in parent['accepted_commands'] if x['tick']<root_tick]
            assert command_ok(ev,tr),(opening,o,root_time,j,ev['command'],at_tick(tr,root_time))
            sent=[{k:v for k,v in x.items() if k not in ('seq','time','tick','event','accepted','side')} for x in at_tick(tr,root_time)]
            signature=json.dumps(sent,sort_keys=True);realized.add(signature);commands.append(signature)
            value=outcome(tr,'zombie')
            if a.key() in targets:
                ext=targets[a.key()]
                value=-1. if any(slow(trace(b),tr) for b in gs if outcome(trace(b),'zombie')<0) else .5*outcome(trace(replace(a,limit=1200)),'zombie')
            scores.append(value);actuals.append(outcome(tr,'zombie'))
        assert len(prefix)==1
        idx=[i for i,c in enumerate(commands) if c not in commands[:i]]
        rows.append(dict(opening=opening,opponent=o,mask=e['mask'],time=root_time,prefix=prefix.pop(),
            outcomes=actuals,targets=scores,keep=idx,keys=[a.key() for a in gs],pool=e['pool'],actual_commands=commands))
    fixed(OUT/'routes.json',dict(rows=rows,extensions=ex,neutral_parity=len(neutral),scan_games=len(all_scans)))

def fit_actions(rows,initial=START,sources=('routes.json','supplement.json')):
    start=read(initial);x=[];y=[];bases=[];weights=[]
    opening_counts=Counter(r['opening'] for r in rows)
    for r in rows:
        keep=r['keep']
        for ix in keep:
            x.append(r['pool'][ix]['x']);bases.append(r['pool'][ix]['base'])
            y.append(r['targets'][ix]-np.mean([r['targets'][j] for j in keep]))
            weights.append(1./(opening_counts[r['opening']]*len(keep)))
    x=np.array(x);y=np.array(y);bases=np.array(bases);weight=np.array(weights);weight/=weight.sum()
    # Learn a correction relative to the incumbent's ordering, measured within
    # each state. Tied actions keep their previous ordering as a low-weight anchor.
    target=np.zeros_like(y);strength=np.ones_like(y);offset=0
    for row in rows:
        n=len(row['keep']);sl=slice(offset,offset+n);offset+=n
        if np.ptp(y[sl])>0:target[sl]=y[sl]-(bases[sl]-bases[sl].mean())
        else:strength[sl]=.18
    h=np.array(start['event_hidden']);bias=np.array(start['event_bias']);head=np.array(start['event_head'])*start['scale']
    tied=strength<1
    target[tied]=(np.tanh(x[tied]@h.T+bias)@head)
    params=[h,bias,head];anchors=[p.copy() for p in params]
    first=[np.zeros_like(p) for p in params];second=[p.copy() for p in first]
    for step in range(1,121):
        layer=np.tanh(x@h.T+bias);value=layer@head
        dz=2*(value-target)*weight*strength
        back=dz[:,None]*head*(1-layer**2)
        for i,(p,d) in enumerate(zip(params,[back.T@x,back.sum(0),layer.T@dz])):
            grad=d+.015*(p-anchors[i]);first[i]=.9*first[i]+.1*grad;second[i]=.999*second[i]+.001*grad**2
            p-=.009*(first[i]/(1-.9**step))/(np.sqrt(second[i]/(1-.999**step))+1e-8)
    training=dict(data=[sha(OUT/n) for n in sources],updates=120,distinct_commands=len(y))
    if initial!=START:training['initial']=sha(initial)
    return {**start,'event_hidden':h.tolist(),'event_bias':bias.tolist(),'event_head':head.tolist(),'training':training}

def detail_pairs(pool,field):
    # Choose a controlled swap: same grave/different card or same card/different grave.
    sp=[(j,p['act']) for j,p in enumerate(pool) if p['act'][0]==2]
    return next(((j,k) for j,a in sp for k,b in sp if k>j and a[field]!=b[field] and a[3-field]==b[3-field]),())

def supplemental(name='supplement',binary=PROBE,policy=START):
    if (OUT/(name+'.json')).exists():return
    games=defaultdict(list)
    for s,i,o,ref in scans():games[s+'/'+i].append((o,ref))
    sample=[]
    for j,(opening,options) in enumerate(games.items()):
        o,ref=options[j%len(options)]
        sample.append((opening,o,ref,replace(ref,binary=binary,policy=policy)))
    batch('inspect topology events and card/grave alternatives once per opening',[x for *_,x in sample])
    excluded={(r['game'],round(r['time']*30)) for r in read(OUT/'roots.json')['roots']}
    available=[];equal=0
    other_points=set()
    if name!='supplement':
        for prev in ('routes','supplement'):
            for r in read(OUT/(prev+'.json'))['rows']:other_points.add((r['opening'],r['opponent'],round(r['time']*30)))
    for opening,o,ref,x in sample:
        tr=trace(x);same=tr['log_sha256']==trace(ref)['log_sha256'] and tr['accepted_commands']==trace(ref)['accepted_commands']
        equal+=same
        if name=='supplement':assert same
        for e in tr['options']:
            pool=e.get('pool',[])
            if (ref.key(),round(e['time']*30)) in excluded or not e['mask']&15 or len(pool)<2:continue
            if (opening,o,round(e['time']*30)) in other_points:continue
            tags={'birth':bool(e['mask']&1),'loss':bool(e['mask']&2),'card':bool(detail_pairs(pool,1)),
                  'grave':bool(detail_pairs(pool,2)),'forward':any(p['act'][0]==3 for p in pool)}
            if any(tags.values()):available.append((opening,o,x,e,tags))
    chosen=[];counts=Counter()
    labels=['birth','loss','card','grave','forward']
    for iteration in range(30):
        label=labels[iteration%len(labels)]
        valid=[j for j,(k,_,_,_,tags) in enumerate(available) if tags[label] and counts[k]<4]
        if not valid:continue
        j=max(valid,key=lambda j:(-counts[available[j][0]],sum(available[j][4].values()),-j))
        opening,o,x,e,_=available.pop(j);counts[opening]+=1
        pool=e['pool'];indices=[0]
        def add(j):
            if j not in indices and len(indices)<4:indices.append(j)
        if label in ('grave','card'):
            for k in detail_pairs(pool,1 if label=='card' else 2):add(k)
        for kind in (3,2,0,1):
            for k,p in enumerate(pool):
                if p['act'][0]==kind:add(k);break
        for k in range(len(pool)):add(k)
        gs=[x if k==0 else replace(x,forced=k,after=e['time']) for k in indices]
        chosen.append((opening,o,x,e,label,indices,gs))
    fixed(OUT/(name+'-roots.json'),dict(roots=[dict(opening=op,tag=tag,root=x.key(),time=e['time'],indices=idx) for op,_,x,e,tag,idx,_ in chosen]))
    batch('distinct topology and swap branches',[a for *_,gs in chosen for a in gs[1:]])
    ex=extend((a,b,'zombie') for *_,gs in chosen for a in gs for b in gs if a!=b)
    longs={r['candidate'] for r in ex};rows=[]
    for opening,o,x,e,label,indices,gs in chosen:
        pool=[e['pool'][k] for k in indices];assert len({json.dumps(p['cmd'],sort_keys=True) for p in pool})==len(pool)
        scores=[];actual=[];cmds=[];prefix=set();root_tick=round(e['time']*30)
        for k,g0 in zip(indices,gs):
            tr=trace(g0);evt=e if k==0 else next(v for v in tr['options'] if v.get('forked'))
            assert evt['choice']==k and evt['pool']==e['pool'] and command_ok(evt,tr)
            if k:prefix.add(evt['prefix'])
            assert [c for c in tr['accepted_commands'] if c['tick']<root_tick]==[c for c in trace(x)['accepted_commands'] if c['tick']<root_tick]
            cmds.append(json.dumps([{j:v for j,v in c.items() if j not in ('seq','time','tick','event','accepted','side')}
                for c in at_tick(tr,e['time'])],sort_keys=True))
            val=outcome(tr,'zombie');actual.append(val)
            if g0.key() in longs:
                val=-1. if any(slow(trace(b),tr) for b in gs if outcome(trace(b),'zombie')<0) else .5*outcome(trace(replace(g0,limit=1200)),'zombie')
            scores.append(val)
        assert len(prefix)==1
        rows.append(dict(opening=opening,opponent=o,tag=label,prefix=prefix.pop(),mask=e['mask'],time=e['time'],pool=pool,
            outcomes=actual,targets=scores,keys=[a.key() for a in gs],actual_commands=cmds,keep=[j for j,c in enumerate(cmds) if c not in cmds[:j]]))
    receipt=dict(rows=rows,extensions=ex,scan_parity=equal)
    if name!='supplement':receipt.update(binary=sha(binary),parent=sha(policy),scans=len(sample))
    fixed(OUT/(name+'.json'),receipt)

def gains(pairs,side):
    report={}
    for o,rs in pairs.items():
        diff=[(outcome(trace(a),side),outcome(trace(b),side),slow(trace(a),trace(b))) for a,b in rs]
        report[o]=dict(net=sum(b-a-int(a<0 and b==0 and stall) for a,b,stall in diff),
                       lost_wins=sum(a==1 and b!=1 for a,b,_ in diff),gain_wins=sum(b==1 and a!=1 for a,b,_ in diff))
    return report

def order(report):
    return (-sum(v['lost_wins'] for v in report.values()),min(v['net'] for v in report.values()),sum(v['net'] for v in report.values()))

def flat(pairs):
    return [g for rows in pairs.values() for pair in rows for g in pair]

def train_zombie(live=False):
    fixed(OUT/'fine-test-design.json',dict(limit_per_kind=4,unique_openings=True,
        selection='On both sealed cohorts, only real nonopening event probes. Chosen spawn vs same card from another grave; chosen spawn vs another card from same grave; chosen vs another approach. Prefer old silent games, then closest to 120 seconds. No result filter or update.'))
    if live:
        initial=Path(read(OUT/'zombie.json')['path']);binary=LIVE
        legacy_cases=[]
        for _,_,_,ref in historical()[0][:2]:
            a=replace(ref,binary=PROGRAM,policy=PARENT,storage=LAST)
            legacy_cases.append((a,replace(a,binary=LIVE,storage=OUT)))
        batch('final native build with legacy weights',[b for _,b in legacy_cases])
        for a,b in legacy_cases:
            assert trace(a)['log_sha256']==trace(b)['log_sha256'] and trace(a)['accepted_commands']==trace(b)['accepted_commands']
        fixed(OUT/'live-parity.json',dict(pairs=[[a.key(),b.key()] for a,b in legacy_cases],binary=sha(LIVE)))
        supplemental('live-routes',binary,initial)
        model=fit_actions(read(OUT/'live-routes.json')['rows'],initial,('live-routes.json',))
    else:
        initial=START;binary=NATIVE;supplemental()
        model=fit_actions(read(OUT/'routes.json')['rows']+read(OUT/'supplement.json')['rows'])
    paths={}
    for tag,scale in [('light',.35),('full',.85)]:
        p=OUT/'models'/(('live-' if live else 'event-')+tag+'.json');fixed(p,{**model,'scale':scale});paths[tag]=p
    ids=read(OUT/'splits.json')['val'];pairs={}
    for tag,p in {**paths,'start':initial}.items():
        pairs[tag]={o:[(g(i,p0,policy=PARENT,binary=PROGRAM),g(i,p0,policy=p,binary=binary)) for i in ids] for o,p0 in PLANTS.items()}
    batch('native zombie validation and entry-only ablation',[z for d in pairs.values() for z in flat(d)])
    reports={tag:gains(rs,'zombie') for tag,rs in pairs.items()}
    best=max(paths,key=lambda k:order(reports[k]))
    ex=extend((a,b,'zombie') for sets in pairs.values() for pairs0 in sets.values() for a,b in pairs0)
    # The native learned score must match the serialized checkpoint on actual deck choices.
    m=read(paths[best]);checked=0
    for _,b in (p for rs in pairs[best].values() for p in rs):
        for e in trace(b)['options']:
            for p in e.get('pool',[]):
                v=np.tanh(np.array(m['event_hidden'])@p['x']+m['event_bias'])@m['event_head']
                assert np.isclose(p['base']+m['scale']*v,p['v']);checked+=1
    assert checked>0
    fixed(OUT/('zombie-live.json' if live else 'zombie.json'),dict(selected=best,path=str(paths[best]),model=sha(paths[best]),validation=reports,
        native_predictions=checked,extensions=ex))

def train_plant():
    if not (OUT/'zombie-live.json').exists():train_zombie(live=True)
    splits=read(OUT/'splits.json');zlock=read(OUT/'zombie-live.json')
    z=Path(zlock['path']);assert sha(z)==zlock['model']
    parent=read(STRONG);w=np.array(parent['heads']['weight'])[:12,-28:]
    from option_study import OLD_P
    prev=w-np.array(read(OLD_P)['heads']['weight'])[:12,-28:]
    rng=np.random.default_rng(58289)
    other=rng.normal(size=w.shape);other-=np.sum(other*prev)/np.sum(prev**2)*prev
    other*=np.linalg.norm(prev)/np.linalg.norm(other)
    paths={}
    for name,d in [('along',prev),('orthogonal',other)]:
        for sign,tag in [(1,'p'),(-1,'m')]:
            m=read(STRONG)
            for j,row in enumerate(w+sign*.35*d):m['heads']['weight'][j][-28:]=row.tolist()
            m['training_source']=dict(parent=sha(STRONG),frozen_zombie=sha(z),kind='native paired returns')
            p=OUT/'models'/f'plant-{name}-{tag}.json';fixed(p,m);paths[name+tag]=p
    def pairs(p,ids):
        return dict(event=[(g(i,STRONG,policy=z,binary=LIVE),g(i,p,policy=z,binary=LIVE)) for i in ids],
                    r=[(g(i,STRONG,zombie=None,position=None),g(i,p,zombie=None,position=None)) for i in ids])
    train={k:pairs(p,splits['train']) for k,p in paths.items()}
    batch('plant search against frozen event zombie and r22',[z0 for d in train.values() for z0 in flat(d)])
    training={k:gains(rs,'plant') for k,rs in train.items()}
    selected=sorted(paths,key=lambda k:order(training[k]),reverse=True)[:2]
    val={k:pairs(paths[k],splits['val']) for k in selected}
    batch('plant validation',[z0 for d in val.values() for z0 in flat(d)])
    validation={k:gains(rs,'plant') for k,rs in val.items()}
    best=max(selected,key=lambda k:order(validation[k]))
    ex=extend((a,b,'plant') for sets in (train,val) for rs in sets.values() for group in rs.values() for a,b in group)
    fixed(OUT/'plant.json',dict(selected=best,path=str(paths[best]),model=sha(paths[best]),frozen_zombie=sha(z),
         training=training,validation=validation,extensions=ex))

def event_summary(tr):
    events=[e for e in tr['options'] if e['mask']&15]
    masks={str(m):sum(bool(e['mask']&m) for e in events) for m in (1,2,4,8)}
    pools=[e for e in events if len(e.get('pool',[]))>=2]
    actual=Counter()
    for e in events:
        assert command_ok(e,tr),(e['action'],e['command'],e['time'],at_tick(tr,e['time']))
        actual[str(e['action'][0])]+=1
    return dict(events=len(events),reasons=masks,actions=dict(actual),multiple_command_samples=len(pools),
        multiple_grave_samples=sum(len({p['act'][2] for p in e['pool'] if p['act'][0]==2})>=2 for e in pools),
        multiple_card_samples=sum(len({p['act'][1] for p in e['pool'] if p['act'][0]==2})>=2 for e in pools))

def select_trained_zombie():
    first=read(OUT/'zombie.json');last=read(OUT/'zombie-live.json')
    # The first pass is a trained challenger this round as well. Apply the same
    # win-retention / worst-opponent / total rule to all trained checkpoints.
    reports=last['validation'];best=max(reports,key=lambda k:order(reports[k]))
    path=Path(first['path']) if best=='start' else OUT/'models'/('live-'+best+'.json')
    fixed(OUT/'zombie-selected.json',dict(path=str(path),model=sha(path),selected=best,validation=reports[best],
        source=sha(OUT/'zombie-live.json'),first=first['model'],refinement=last['model']))
    return path

def select_plant():
    z=select_trained_zombie();other=Path(read(OUT/'zombie-live.json')['path'])
    previous=read(OUT/'plant.json')
    if sha(z)==sha(other):
        fixed(OUT/'plant-selected.json',dict(**previous,sparring=[sha(z)]));return
    split=read(OUT/'splits.json')
    directions={a+b:OUT/'models'/f'plant-{a}-{b}.json' for a in ('along','orthogonal') for b in ('p','m')}
    def pairs(p,ids):
        return {'leader':[(g(i,STRONG,policy=z,binary=LIVE),g(i,p,policy=z,binary=LIVE)) for i in ids],
                'refined':[(g(i,STRONG,policy=other,binary=LIVE),g(i,p,policy=other,binary=LIVE)) for i in ids],
                'r':[(g(i,STRONG,zombie=None,position=None),g(i,p,zombie=None,position=None)) for i in ids]}
    train={k:pairs(p,split['train']) for k,p in directions.items()}
    batch('plant training against both fixed trained zombie checkpoints and r22',[v for rs in train.values() for v in flat(rs)])
    report={k:gains(rs,'plant') for k,rs in train.items()}
    shortlist=sorted(directions,key=lambda k:order(report[k]),reverse=True)[:2]
    val={k:pairs(directions[k],split['val']) for k in shortlist}
    batch('plant validation against frozen leader, refinement and r22',[v for rs in val.values() for v in flat(rs)])
    validation={k:gains(rs,'plant') for k,rs in val.items()};best=max(shortlist,key=lambda k:order(validation[k]))
    ex=extend((a,b,'plant') for sets in (train,val) for rs in sets.values() for group in rs.values() for a,b in group)
    frozen=directions[best];fixed(OUT/'plant-selected.json',dict(selected=best,path=str(frozen),model=sha(frozen),
        frozen_zombie=sha(z),sparring=[sha(z),sha(other)],training=report,validation=validation,extensions=ex))

def paired_coverage(old,start,new,o,opening):
    tx=trace(old);tz=trace(new)
    row=dict(opening=opening,opponent=o,before=old.key(),after=new.key(),old_triggers=len(tx['options']),
        old=outcome(tx,'zombie'),new=outcome(tz,'zombie'),**event_summary(tz))
    if start is not None:
        start_tr=trace(start)
        row.update(start_key=start.key(),start=outcome(start_tr,'zombie'),start_events=sum(bool(e['mask']&15) for e in start_tr['options']))
    return row

def locks():
    z,p=[read(OUT/(n+'.json')) for n in ('zombie-selected','plant-selected')]
    assert z['model']==p['frozen_zombie']
    paths=Path(z['path']),Path(p['path']);assert [sha(a) for a in paths]==[z['model'],p['model']]
    return paths

def test():
    if not (OUT/'plant-selected.json').exists():select_plant()
    z,p=locks();split=read(OUT/'splits.json');ids=split['a']+split['b']
    matrix={'plant':{},'zombie':{}}
    for o in 'rhb':
        opp=MODELS[o]
        matrix['zombie'][o]=[(g(i,opp,binary=PROGRAM,policy=PARENT),g(i,opp,policy=z,binary=LIVE)) for i in ids]
        matrix['plant'][o]=[(g(i,STRONG,zombie=opp,position=None,binary=LIVE),g(i,p,zombie=opp,position=None,binary=LIVE)) for i in ids]
    batch('paired sealed home matches vs r22/H/B',[v for pairs in matrix.values() for v in flat(pairs)])
    ablation=[replace(b,policy=START) for rs in matrix['zombie'].values() for a,b in rs if not trace(a)['options']]
    batch('entry-only diagnostics on previously silent blind games',ablation)
    reports={};extensions=[];coverage=[];rank_checks=Counter()
    model=read(z);hidden=np.array(model['event_hidden']);bias=np.array(model['event_bias']);head=np.array(model['event_head'])
    for side,groups in matrix.items():
        report={}
        for label,subset in [('a',split['a']),('b',split['b']),('all',ids)]:
            subset_pairs={o:[(a,b) for a,b in rs if a.uid in subset] for o,rs in groups.items()}
            report[label]=paired_result(subset_pairs,side,subset)
        rows=report['all']['rows']
        report['stable']=bool(all(report[k]['adjusted_net']>0 and min(x['net'] for x in report[k]['per_opponent'].values())>=0 for k in ('a','b'))
            and report['all']['paired_mean95'][0]>0 and all(not x['stall'] and (x['old']!=1 or x['new']==1) for x in rows))
        reports[side]=report
        extensions+=extend((a,b,side) for rs in groups.values() for a,b in rs)
        if side=='zombie':
            abpairs=[]
            for o,rs in groups.items():
                for a,b in rs:
                    warm=None
                    if not trace(a)['options']:
                        warm=replace(b,policy=START)
                        abpairs.extend([(a,warm,side),(warm,b,side)])
                    coverage.append(paired_coverage(a,warm,b,o,a.uid))
                    for e in trace(b)['options']:
                        pool=e.get('pool',[])
                        if len(pool)<2 or e['mask']==16:continue
                        base=np.array([v['base'] for v in pool]);x=np.array([v['x'] for v in pool])
                        values=base+model['scale']*(np.tanh(x@hidden.T+bias)@head)
                        assert np.allclose(values,[v['v'] for v in pool]) and values[0]>=max(values)-1e-9
                        rank_checks['compared']+=1
                        j=int(np.argmax(base))
                        if base[j]>base[0]+1e-7:
                            rank_checks['changed_vs_raw_prior']+=1
                            before,chosen=pool[j]['act'],pool[0]['act']
                            if before[0]==chosen[0]==2:
                                rank_checks['different_card']+=before[1]!=chosen[1]
                                rank_checks['different_grave']+=before[2]!=chosen[2]
            extensions+=extend(abpairs)
    fixed(OUT/'test.json',dict(zombie=sha(z),plant=sha(p),results=reports,coverage=coverage,extensions=extensions,
        native_rank_checks=dict(rank_checks)))

def regression():
    z,_=locks();_,former=historical();groups=[]
    for source,i,o,old in former:
        warm=replace(old,binary=LIVE,policy=START,storage=OUT)
        groups.append((source+'/'+i,o,old,warm,replace(warm,policy=z)))
    batch('revisit all 25 exact formerly silent encounters',[a for _,_,_,w,b in groups for a in (w,b)])
    rows=[paired_coverage(a,w,b,o,i) for i,o,a,w,b in groups]
    assert all(r['old_triggers']==0 for r in rows) and len(rows)==25
    extensions=extend((a,b,'zombie') for _,_,old,warm,new in groups for a,b in ((old,new),(old,warm),(warm,new)))
    fixed(OUT/'regression.json',dict(rows=rows,extensions=extensions))

def fine_test():
    z,_=locks();test=read(OUT/'test.json');samples=[]
    for r in test['coverage']:
        g0=g(r['opening'],MODELS[r['opponent']],policy=z,binary=LIVE)
        assert g0.key()==r['after']
        for e in trace(g0)['options']:
            if not e['mask']&15:continue
            pool=e.get('pool',[]);chosen=e['action']
            for j,p in enumerate(pool[1:],1):
                a=p['act'];tag=None
                if chosen[0]==2 and a[0]==2:
                    if chosen[1]==a[1] and chosen[2]!=a[2]:tag='grave'
                    if chosen[1]!=a[1] and chosen[2]==a[2]:tag='card'
                if a[0]!=chosen[0] and 3 in (a[0],chosen[0]):tag='move'
                if tag:samples.append((tag,r,g0,e,j,p['v']))
    picked=[];used=set()
    for _ in range(4):
        for tag in ('card','grave','move'):
            opts=[x for x in samples if x[0]==tag and x[1]['opening'] not in used]
            if not opts:continue
            item=min(opts,key=lambda v:(v[1]['old_triggers']!=0,abs(v[3]['time']-120),v[1]['opening'],v[1]['opponent'],-v[5]))
            used.add(item[1]['opening']);picked.append(item)
    groups=[(a,replace(a,forced=j,after=e['time'])) for _,_,a,e,j,_ in picked]
    batch('sealed one-decision source/card/movement checks; reuse actual chosen games',[b for _,b in groups])
    rows=[]
    for (tag,r,a,e,j,_),(_,b) in zip(picked,groups):
        tr=trace(b);ev=next(v for v in tr['options'] if v.get('forked'))
        assert ev['pool']==e['pool'] and ev['action']==e['pool'][j]['act'] and ev['command']!=e['command']
        assert command_ok(e,trace(a)) and command_ok(ev,tr)
        t=round(e['time']*30)
        assert [c for c in tr['accepted_commands'] if c['tick']<t]==[c for c in trace(a)['accepted_commands'] if c['tick']<t]
        rows.append(dict(tag=tag,opening=a.uid,opponent=r['opponent'],old_triggers=r['old_triggers'],time=e['time'],prefix=ev['prefix'],
            chosen=e['action'],alternative=ev['action'],actual=[outcome(trace(a),'zombie'),outcome(tr,'zombie')],keys=[a.key(),b.key()]))
    ex=extend((a,b,'zombie') for a0,b0 in groups for a,b in ((a0,b0),(b0,a0)))
    fixed(OUT/'fine-test.json',dict(rows=rows,extensions=ex,
        possible={tag:len({x[1]['opening'] for x in samples if x[0]==tag}) for tag in ('card','grave','move')}))

def horizons():
    z,p=locks();test=read(OUT/'test.json');checks=[]
    for side,group in test['results'].items():
        for r in group['all']['rows']:
            if r['old']==r['new'] or 0 not in (r['old'],r['new']):continue
            opp=MODELS[r['opponent']]
            if side=='plant':
                a=g(r['id'],STRONG,zombie=opp,position=None,binary=LIVE);b=replace(a,plant=p)
            else:
                a=g(r['id'],opp,policy=PARENT,binary=PROGRAM);b=replace(a,policy=z,binary=LIVE)
            assert [a.key(),b.key()]==[r['baseline'],r['candidate']]
            timed,finished=(a,b) if r['old']==0 else (b,a)
            if not trace(timed)['timeout']:continue
            loser='zombie' if trace(finished)['result']['winner']=='plant' else 'plant'
            checks.append((r,side,timed,finished,loser))
    ex=extend((f,t,loser) for _,_,t,f,loser in checks)
    assert len(ex)==len(checks)
    rows=[dict(side=side,opening=r['id'],opponent=r['opponent'],old=r['old'],new=r['new'],timed=t.key(),
        long=e['extended'],winner=e['winner'],end=e['end'],timeout=e['timeout']) for (r,side,t,_,_),e in zip(checks,ex)]
    fixed(OUT/'horizons.json',dict(test=sha(OUT/'test.json'),rows=rows))

def run_stage(stage):
    if stage=='pilot':batch('old development event scans',[a for *_,a in historical()[0]])
    elif stage=='coverage':batch('previously unreachable regression openings with initial event scorer',
        [replace(a,binary=NATIVE,policy=START,storage=OUT) for *_,a in historical()[1]])
    elif stage=='preflight':
        originals=historical()[0];cases=[];pairs=[]
        for src,uid,o,ref in originals[:2]:
            prev=replace(ref,binary=PROGRAM,policy=PARENT,storage=LAST)
            twin=replace(ref,policy=PARENT)
            batch('legacy path equivalence',[twin])
            assert trace(prev)['log_sha256']==trace(twin)['log_sha256']
            e=next(x for x in trace(ref)['options'] if len(x.get('pool',[]))==4 and x['mask']!=16)
            variants=[replace(ref,forced=j,after=e['time']) for j in range(4)]
            batch('verify distinct native commands',variants)
            for v in variants:
                tr=trace(v);evt=next(x for x in tr['options'] if x.get('forked'))
                assert command_ok(evt,tr),(evt['command'],at_tick(tr,evt['time']))
            assert trace(variants[0])['log_sha256']==trace(ref)['log_sha256']
            pairs.extend((a,b,'zombie') for a in variants for b in variants if a!=b)
            cases.append(dict(reference=ref.key(),legacy=prev.key(),twin=twin.key(),variants=[v.key() for v in variants]))
        fixed(OUT/'preflight.json',dict(cases=cases,extensions=extend(pairs)))
    elif stage=='routes':routes()
    elif stage=='zombie':train_zombie()
    elif stage=='plant':train_plant()
    elif stage=='test':test()
    elif stage=='regression':regression()
    elif stage=='fine-test':fine_test()
    elif stage=='horizons':horizons()
    else:raise ValueError(stage)
