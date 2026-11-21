"""Select on independent z16 win styles, then reverse seats and open the sealed sets."""
import numpy as np
from tempo_train import *
from single_fit import score as deployment_score

def summarize(gr,side):
    report=pair_report(gr,side)
    report['counts']=stats(report['rows'])
    report['troops']=troop_tempo(gr,side,CATALOG)
    report['different']=sum(trace(a)['log_sha256']!=trace(b)['log_sha256'] for pairs in gr.values() for a,b in pairs)
    ids=sorted({r['id'] for r in report['rows']})
    changes=[np.mean([int(r['new']==1)-int(r['old']==1) for r in report['rows'] if r['id']==i]) for i in ids]
    rng=np.random.default_rng(110823)
    boot=np.asarray(changes)[rng.integers(0,len(ids),(20000,len(ids)))].mean(axis=1)
    report['win_delta95']=np.quantile(boot,[.025,.975]).tolist()
    return report

def longer(groups,side,also_wins=False):
    matched=[]
    for group in groups:
        for pairs in group.values():
            for a,b in pairs:
                old=outcome(trace(a),side)
                if trace(b)['timeout'] and (old==-1 or (also_wins and old==1)):
                    loser=side if old==-1 else ('zombie' if side=='plant' else 'plant')
                    matched.append((a,b,loser))
    return extend(dict.fromkeys(matched))

def troop_score(report):
    counts=report['counts'];x,y=report['troops']['all']['troops_per_min']
    n=len(report['rows'])
    return (counts['new'][0]-counts['old'][0]-1.3*counts['lost']-.3*sum(r['stall'] for r in report['rows']))/n-1.5*max(0.,1-y/max(.01,x))

def zombie():
    prior=read(OUT/'old-labels.json');added=read(OUT/'rollouts.json')['rows']
    rows={key:prior[key]+added[key] for key in NAMES}
    params={'balanced':(.85,(.12,.16,.04)),'protected':(1.,(.54,.60,.05)),'selective':(.75,(1.06,1.10,.02))}
    paths={name:weight(name,rows,s,m) for name,(s,m) in params.items()}
    val=[r['id'] for r in read(OUT/'screen.json')['val']]
    ordinary=[i for i in read(OUT/'split.json')['val_pool'] if i not in val][:8]
    def pairs(ids,p):
        return {o:[(live(i,teacher,PARENT),live(i,teacher,p)) for i in ids] for o,teacher in TEACHERS.items()}
    tests={name:{'enriched':pairs(val,p),'ordinary':pairs(ordinary,p)} for name,p in {**paths,'previous':LAST_Z}.items()}
    batch('validation against three frozen plants on enriched and unselected starts',[g for table in tests.values() for gr in table.values() for g in flatten(gr)])
    reports={name:{s:summarize(gr,'zombie') for s,gr in table.items()} for name,table in tests.items()}
    def rank(name):
        r=reports[name];score=.68*troop_score(r['enriched'])+.32*troop_score(r['ordinary'])
        speed=[v['troops']['all']['troops_per_min'] for v in r.values()]
        return (any(v['different'] for v in r.values()),all(y>=x for x,y in speed),score,-r['enriched']['counts']['lost'])
    selected=max(paths,key=rank)
    ex=longer([gr for table in tests.values() for gr in table.values()],'zombie')
    fixed(OUT/'zombie.json',dict(selected=selected,path=str(paths[selected]),sha256=sha(paths[selected]),enriched=val,ordinary=ordinary,
          validation=reports,ranking={k:list(rank(k)) for k in paths},extensions=ex))

def plant():
    contrast()
    z=read(OUT/'zombie.json');locked=Path(z['path']);assert sha(locked)==z['sha256']
    current=read(LAST_P);old=read(PLANT)
    w=np.array(current['heads']['weight'])[:12,-28:]
    back=np.array(old['heads']['weight'])[:12,-28:]-w
    rng=np.random.default_rng(130687)
    direct=rng.normal(size=w.shape)
    direct-=np.sum(direct*back)/np.sum(back**2)*back;direct*=np.linalg.norm(back)/np.linalg.norm(direct)
    def model(name,x):
        d=read(LAST_P)
        for j,row in enumerate(x):d['heads']['weight'][j][-28:]=row.tolist()
        d['training_source']=dict(parent=sha(LAST_P),anchor=sha(PLANT),frozen_zombie=sha(locked),method='paired search on independent opening styles')
        return policy('plant-'+name,d)
    ws={'toward':w+.65*back,'away':w-.45*back,'crossp':w+.55*direct,'crossm':w-.55*direct}
    paths={name:model(name,x) for name,x in ws.items()}
    sel=read(OUT/'screen.json')
    def balanced(group,n):
        return [r['id'] for sign in (1,-1) for r in [s for s in group if s['result']==sign][:n]]
    train=balanced(sel['train'],4);val=balanced(sel['val'],5)
    def pairs(ids,p):
        return {'new':[(live(i,LAST_P,locked),live(i,p,locked)) for i in ids],
                'previous':[(live(i,LAST_P,LAST_Z),live(i,p,LAST_Z)) for i in ids],
                'r22':[(live(i,LAST_P,None,zombie=None,position=None),live(i,p,None,zombie=None,position=None)) for i in ids]}
    trainsets={k:pairs(train,p) for k,p in paths.items()}
    batch('reverse seats: train plant against fixed new and previous zombies and r22',[g for gr in trainsets.values() for g in flatten(gr)])
    trainrep={k:summarize(gr,'plant') for k,gr in trainsets.items()}
    ranked=sorted(paths,key=lambda k:deployment_score(trainrep[k],'plant'),reverse=True)
    best,runner=ranked[:2]
    blend=model('paired',w+.65*(ws[best]-w)+.25*(ws[runner]-w)+.15*back)
    finalists={best:paths[best],runner:paths[runner],'paired':blend}
    validsets={k:pairs(val,p) for k,p in finalists.items()}
    batch('select plant on separate starts',[g for gr in validsets.values() for g in flatten(gr)])
    vr={k:summarize(gr,'plant') for k,gr in validsets.items()}
    winner=max(finalists,key=lambda k:(deployment_score(vr[k],'plant'),-vr[k]['counts']['lost'],vr[k]['counts']['gain']))
    ex=longer([*trainsets.values(),*validsets.values()],'plant')
    fixed(OUT/'plant.json',dict(selected=winner,path=str(finalists[winner]),sha256=sha(finalists[winner]),zombie=sha(locked),
          training=trainrep,validation=vr,extensions=ex))

def regression():
    p=Path(read(OUT/'zombie.json')['path'])
    secondary=Path(read(OUT/'contrast.json')['path'])
    prior=read(PREVIOUS/'test.json')['results']['z16']['all']['rows']
    reviewed=[r for r in prior if r['old']==1 or r['new']==1]
    groups=[]
    for r in reviewed:
        gs=[live(r['id'],MODELS[r['opponent']],z,corpus=PREVIOUS/'plain') for z in (PARENT,LAST_Z,p,secondary)]
        groups.append((r,gs))
    batch('prior 19 z16 wins and all previous conversions',[g for _,gs in groups for g in gs])
    rows=[]
    for r,gs in groups:
        a,b,c,other=gs
        assert trace(a)['log_sha256']==receipt(PREVIOUS,r['baseline'])[1]['log_sha256']
        assert trace(b)['log_sha256']==receipt(PREVIOUS,r['candidate'])[1]['log_sha256']
        rows.append(dict(id=r['id'],opponent=r['opponent'],z16=r['old'],previous=r['new'],new=outcome(trace(c),'zombie'),
                         secondary=outcome(trace(other),'zombie'),keys=[g.key() for g in gs]))
    ex=longer([{'history':[(g[j],g[k]) for _,g in groups]} for j in (0,1) for k in (2,3)],'zombie',True)
    fixed(OUT/'regression.json',dict(rows=rows,extensions=ex))

def fixed_history_control(z):
    """Clamp only the six new inputs; keep all learned scores at the training means."""
    model=read(z);old=read(OUT/'old-labels.json');fresh=read(OUT/'rollouts.json')['rows'];means={}
    for name in NAMES:
        by_seed=defaultdict(set)
        for r in old[name]+fresh[name]:by_seed[r['seed']].add((r['prefix'],tuple(r['x'][-6:])))
        mean=np.mean([np.mean([x for _,x in sorted(values)],axis=0) for values in by_seed.values()],axis=0)
        old_head=model['switch'][name];means[name]=mean.tolist()
        linear=np.asarray(old_head['linear']);hidden=np.asarray(old_head['hidden'])
        old_head['bias']+=float(linear[-6:]@mean)
        old_head['hb']=(np.asarray(old_head['hb'])+hidden[:,-6:]@mean).tolist()
        linear[-6:]=0.;hidden[:,-6:]=0.
        old_head['linear']=linear.tolist();old_head['hidden']=hidden.tolist()
        original=read(z)['switch'][name]
        example=(old[name]+fresh[name])[0]['x']
        assert abs(prediction(example,old_head)-prediction(example[:-6]+mean.tolist(),original))<1e-8
    model['diagnostic']=dict(parent=sha(z),training_means=means)
    return policy('fixed-troop-history',model)

def contrast():
    z=read(OUT/'zombie.json')
    def rank(k):
        reps=z['validation'][k].values()
        return (-sum(r['counts']['lost'] for r in reps),sum(r['counts']['gain'] for r in reps),
                sum(r['counts']['new'][0]-r['counts']['old'][0] for r in reps))
    k=max(z['ranking'],key=rank)
    p=OUT/'models'/(k+'.json')
    fixed(OUT/'contrast.json',dict(primary=z['selected'],selected=k,path=str(p),sha256=sha(p),
          reason='Secondary validation-only challenger: minimize lost baseline wins, then maximize true loss-to-win conversions. Freeze before plant selection and blind play.'))

def test():
    sp=read(OUT/'split.json');zl=read(OUT/'zombie.json');pl=read(OUT/'plant.json')
    z,p=Path(zl['path']),Path(pl['path']);ids=sp['a']+sp['b']
    assert sha(z)==zl['sha256']==pl['zombie'] and sha(p)==pl['sha256']
    control=fixed_history_control(z)
    alt=read(OUT/'contrast.json');other=Path(alt['path']);assert sha(other)==alt['sha256']
    fixed(OUT/'sealed.json',dict(zombie=sha(z),plant=sha(p),secondary=sha(other),history_control=sha(control),corpus=sp['corpus'],ids=ids,
          control='Only the six additional deployment-history input values are clamped to equal-seed means from fitting rows. Same weights and margins, no tuning on either cohort.'))
    matrix={k:{} for k in ('z16','single','persistent','history_fixed','plant_latest','plant_anchor')}
    if other!=z:matrix['secondary_z16']={}
    for o in 'rhb':
        for k,baseline in [('z16',PARENT),('single',LAST_Z),('persistent',ACTIVE),('history_fixed',control)]:
            matrix[k][o]=[(live(i,MODELS[o],baseline),live(i,MODELS[o],z)) for i in ids]
        if other!=z:matrix['secondary_z16'][o]=[(live(i,MODELS[o],PARENT),live(i,MODELS[o],other)) for i in ids]
        for k,baseline in [('plant_latest',LAST_P),('plant_anchor',PLANT)]:
            matrix[k][o]=[(live(i,baseline,None,zombie=MODELS[o],position=None),live(i,p,None,zombie=MODELS[o],position=None)) for i in ids]
    batch('held-out cohorts, both seats against r22/H/B',[g for gr in matrix.values() for g in flatten(gr)])
    reports={};extensions=[]
    for name,gr in matrix.items():
        side='plant' if name.startswith('plant') else 'zombie'
        rep={'all':summarize(gr,side)}
        for k in ('a','b'):
            rep[k]=summarize({o:[pair for pair in pairs if pair[0].uid in sp[k]] for o,pairs in gr.items()},side)
        allrep=rep['all'];old,new=allrep['troops']['all']['troops_per_min'] if side=='zombie' else [allrep['tempo'][k]['common_window_deploys_per_min'][side] for k in ('parent','candidate')]
        rep['stable']=bool(allrep['counts']['lost']==0 and all(rep[k]['counts']['new'][0]>rep[k]['counts']['old'][0] for k in ('a','b')) and allrep['win_delta95'][0]>0 and new>=old and not any(r['stall'] for r in allrep['rows']))
        rep['native_draws']=[sum(outcome(trace(pair[j]),side)==0 and not trace(pair[j])['timeout'] for pairs in gr.values() for pair in pairs) for j in (0,1)]
        if name=='z16':
            buckets=defaultdict(list)
            for pairs in gr.values():
                for a,b in pairs:
                    old,new=(outcome(trace(g),side) for g in (a,b))
                    buckets[f'{old}/{new}'].append((a,b))
            rep['by_transition']={k:troop_tempo({'group':v},side,CATALOG)['all'] for k,v in buckets.items()}
        reports[name]=rep
        ex=longer([gr],side,True)
        outcomes={(r['baseline'],r['candidate']):r for r in allrep['rows']}
        for e in ex:
            r=outcomes[e['base'],e['candidate']]
            extensions.append(dict(comparison=name,opponent=r['opponent'],old=r['old'],late=0 if e['winner'] not in ('plant','zombie') else (1 if e['winner']==side else -1),**e))
    dynamics=[]
    for o,pairs in matrix['z16'].items():
        for a,b in pairs:
            tr=trace(b);leases=[e for e in tr['switches'] if e['phase']=='lease'];votes=[e for e in tr['switches'] if e['phase']=='arrival_vote']
            dynamics.append(dict(id=b.uid,opponent=o,changed=trace(a)['log_sha256']!=tr['log_sha256'],
                leases=len(leases),returns=sum(e['from']==1 and e['choice']==0 for e in leases),public_returns=sum(e['from']==1 and e['choice']==0 and bool(e['mask']&15) for e in leases),
                trips=sum(e['choice']==2 for e in leases),arrivals=len(votes),defer=sum(not e['place'] for e in votes)))
    fixed(OUT/'test.json',dict(zombie=sha(z),plant=sha(p),results=reports,extensions=extensions,dynamics=dynamics))

def run(stage):
    if stage=='zombie':zombie()
    elif stage=='contrast':contrast()
    elif stage=='plant':plant()
    elif stage=='regression':regression()
    elif stage=='test':test()
    else:
        from tempo_report import audit
        if stage!='audit':raise ValueError(stage)
        audit()
