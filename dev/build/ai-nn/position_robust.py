"""A second, opponent-robust update with entirely fresh home acceptance openings."""
from pathlib import Path
import sys
import numpy as np
from position_train import OUT,BASE,HOME,H,EXPORT,MODELS,read,write,sha,cmd,score,group,metrics,report_comparison,store_spatial,store_plant,SPATIAL_KEYS
from home_pool import jointly_idle

ROOT=OUT/'robust'
OPP='ronb'


def mapped(name,ids):
    base=OUT/'games'/name
    data=read(base/'summary.json')['matches']
    return {i:dict(match=data[i],trace=str(base/'matches'/(i+'.jsonl'))) for i in ids}


def stages():
    d=read(OUT/'plan.json')
    train=[d['train'][i] for i in (0,1,3,6,9,10)]
    return train,d['validation']


def diversify():
    """Select complementary legal home decks using training decks only."""
    folder=ROOT/'diverse'
    if (folder/'ready.json').exists():return
    folder.mkdir(exist_ok=True)
    cmd(EXPORT/'deck73_corpus.exe',folder/'draft.json',2,6,1011000,793123)
    candidates=[r for r in read(folder/'draft.json') if r['map']=='家院' and not r.get('error') and not r.get('invalid')]
    existing=read(OUT/'scenarios.json')[:12]
    def distance(a,b):
        terms=[]
        for side in ('plant','zombie'):
            x,y=set(a['decks'][side]),set(b['decks'][side])
            terms.append(1.-len(x&y)/len(x|y))
        return sum(terms)/2.
    selected=[];distances=[]
    for dark in [False,True]*3:
        eligible=[r for r in candidates if r['night']==dark and r not in selected]
        rank=lambda r:(min(distance(r,k) for k in existing+selected),r['seed'])
        winner=max(eligible,key=rank)
        distances.append(rank(winner)[0]);selected.append(winner)
    assert min(distances)>0 and len({r['seed'] for r in selected})==6
    write(folder/'scenarios.json',selected)
    cmd(sys.executable,H/'export_corpus.py',folder/'scenarios.json',folder/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',folder/'corpus',folder/'plain')
    write(folder/'ready.json',dict(ids=[f'{i:03}' for i in range(6)],minimum_deck_distances=distances,
          fresh_seeds=[v['seed'] for v in selected],method='Maximize minimum mean per-side Jaccard distance to existing training decks and selected decks; 3 day/3 night. No test outcomes or test decks used.'))


def add_training(rows,name,plant,zombie,spatial):
    folder=ROOT/'diverse'
    extra=group('r2-extra-'+name,read(folder/'ready.json')['ids'],plant,zombie,spatial,corpus=folder/'plain')
    return {**rows,**{'diverse-'+i:x for i,x in extra.items()}}


def frozen_orig(name):
    return Path(read(OUT/(name+'-frozen.json'))['model'])


def objective(batch,reference,side):
    margins={}
    for key,rows in batch.items():
        m=0
        for i,trial in rows.items():
            old=score(reference[key][i]['match'],side)
            new=score(trial['match'],side)
            if old<0 and new==0 and jointly_idle(trial,reference[key][i]):new=old
            m+=new-old
        margins[key]=m
    return margins


def rvalue(margins):
    return (min(margins.values()),sum(margins.values()))


def prepare():
    ROOT.mkdir(exist_ok=True)
    if (ROOT/'prepared.json').exists():return
    cmd(EXPORT/'deck73_corpus.exe',ROOT/'draft.json',3,3,993000,771815)
    draft=read(ROOT/'draft.json')
    prior={r['seed'] for r in read(OUT/'scenarios.json')}
    home=[r for r in draft if r['map']=='家院']
    assert len(home)==18 and not prior.intersection(r['seed'] for r in home)
    # All 18 new home openings get primary retests; four additional cross-map seeds per map.
    transfer=[]
    for arena in ['山地','铁道']:
        for dark in [False,True]:
            opts=[r for r in draft if r['map']==arena and r['night']==dark]
            transfer.extend([opts[0],opts[-1]])
    cases=home+transfer
    assert all(not r.get('error') and not r.get('invalid') for r in cases)
    write(ROOT/'scenarios.json',cases)
    cmd(sys.executable,H/'export_corpus.py',ROOT/'scenarios.json',ROOT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',ROOT/'corpus',ROOT/'plain')
    write(ROOT/'prepared.json',dict(index=sha(ROOT/'plain/index.json'),test=[f'{i:03}' for i in range(18)],
          transfer=[f'{i:03}' for i in range(18,26)],original_test_unused_for_fitting=True))


def zombie_fit(train_ids,val_ids):
    rng=np.random.default_rng(44988)
    first=frozen_orig('zombie')
    z0={k:np.array(v) for k,v in read(first).items() if k in SPATIAL_KEYS}
    # Search locally around the winner, avoiding the severe collapses of large exploratory steps.
    scale={'weights':.17,'hidden':.04,'bias':.045,'output':.065}
    directions=[{k:rng.normal(0,scale[k],v.shape) for k,v in z0.items()} for _ in range(2)]
    paths={'first':first}
    for i,d in enumerate(directions):
        for sign,tag in [(1,'p'),(-1,'m')]:
            paths[str(i)+tag]=store_spatial('r2-z-'+str(i)+tag,{k:z0[k]+sign*d[k] for k in z0})
    def evaluate(tag,path,ids,split):
        result={}
        for o in OPP:
            if o!='r' and tag=='parent':result[o]=mapped('z-'+split+'-parent-'+o,ids)
            elif o!='r' and tag=='first' and split=='validation':result[o]=mapped('z-validation-step-'+o,ids)
            else:result[o]=group('r2-z-'+split+'-'+tag+'-'+o,ids,MODELS[o],BASE,path)
            if split=='train':result[o]=add_training(result[o],'z-'+tag+'-'+o,MODELS[o],BASE,path)
        return result
    ref=evaluate('parent',None,train_ids,'train')
    train={n:objective(evaluate(n,m,train_ids,'train'),ref,'zombie') for n,m in paths.items()}
    # Optimize the weakest paired margin first; mean margin breaks ties.
    scalar=lambda d:min(d.values()) + .2*np.mean(list(d.values()))
    grad=np.array([scalar(train[str(i)+'p'])-scalar(train[str(i)+'m']) for i in range(2)])
    coeff=grad/max(1.,abs(grad).sum())
    step={k:z0[k]+sum(c*d[k] for c,d in zip(coeff,directions)) for k in z0}
    explored=max((n for n in paths if n!='first'),key=lambda n:(rvalue(train[n]),n))
    paths['step']=store_spatial('r2-z-step',step)
    rv=evaluate('parent',None,val_ids,'validation')
    validation={n:objective(evaluate(n,paths[n],val_ids,'validation'),rv,'zombie') for n in ['first',explored,'step']}
    best=max(validation,key=lambda n:(rvalue(validation[n]),n=='first',n=='step'))
    write(ROOT/'zombie-frozen.json',dict(model=str(paths[best]),selected=best,sha256=sha(paths[best]),training_margins=train,
          validation_margins=validation,coeff=coeff.tolist(),heldout_unopened=True))
    return paths[best]


def plant_fit(zombie,train_ids,val_ids):
    # Optimize the plant after the robust zombie is frozen. The second anchor protects its r22 matchup.
    models={'first':frozen_orig('plant')}
    old=np.array(read(BASE)['heads']['weight'])[:12,-28:]
    first=np.array(read(models['first'])['heads']['weight'])[:12,-28:]-old
    rng=np.random.default_rng(1177)
    direction=rng.normal(0,.04,first.shape)+np.linspace(-1,1,12)[:,None]*rng.normal(0,.10,(1,28))
    for sign,n in [(1,'p'),(-1,'m')]:models[n]=store_plant('r2-p-'+n,first+sign*direction)
    def evaluate(name,model,ids,split):
        rows={}
        for o in ('frozen','r'):
            z,sp=(BASE,zombie) if o=='frozen' else (None,None)
            group_rows=group('r2-p-'+split+'-'+name+'-'+o,ids,model,z,sp)
            rows[o]=add_training(group_rows,'p-'+name+'-'+o,model,z,sp) if split=='train' else group_rows
        return rows
    ref=evaluate('parent',BASE,train_ids,'train')
    margins={n:objective(evaluate(n,m,train_ids,'train'),ref,'plant') for n,m in models.items()}
    f=lambda v:min(v.values())+.2*np.mean(list(v.values()))
    grad=f(margins['p'])-f(margins['m'])
    coeff=float(np.clip(grad/2.,-1.,1.))
    models['step']=store_plant('r2-p-step',first+coeff*direction)
    rv=evaluate('parent',BASE,val_ids,'validation')
    val={n:objective(evaluate(n,models[n],val_ids,'validation'),rv,'plant') for n in ('first','step')}
    best=max(val,key=lambda n:(rvalue(val[n]),n=='first'))
    write(ROOT/'plant-frozen.json',dict(model=str(models[best]),selected=best,sha256=sha(models[best]),training_margins=margins,
          validation_margins=val,coeff=coeff,frozen_zombie=sha(zombie),heldout_unopened=True))
    return models[best]


def test(z,p):
    split=read(ROOT/'prepared.json');corpus=ROOT/'plain';reports={}
    # For each seat compare the chosen policy with the same parent on the same seed and frozen opponent.
    # H was not a training opponent for either update. B is the older pooled leader.
    for arena,ids,opps in [('house',split['test'],'rhb'),('transfer',split['transfer'],'rh')]:
        reports[arena]={}
        parents={}
        for side in ('zombie','plant'):
            for o in opps:
                opp=MODELS[o]
                key=side+'-'+o
                oldp,oldz=(opp,BASE) if side=='zombie' else (BASE,opp)
                newp,newz,sp=(opp,BASE,z) if side=='zombie' else (p,opp,None)
                pair=(oldp,oldz)
                if pair not in parents:
                    parents[pair]=group('r2-'+arena+'-'+key+'-parent',ids,oldp,oldz,corpus=corpus)
                ref=parents[pair]
                trial=group('r2-'+arena+'-'+key+'-candidate',ids,newp,newz,sp,corpus=corpus)
                report=report_comparison('r2-'+arena,key,side,ref,trial,newp,newz,sp,corpus)
                report['parent_group']=Path(next(iter(ref.values()))['trace']).parents[1].name
                if arena=='house' and o in 'rh':
                    first=frozen_orig(side)
                    final=z if side=='zombie' else p
                    if sha(first)==sha(final):
                        original=trial
                    else:
                        firstp,firstz,firstsp=(opp,BASE,first) if side=='zombie' else (first,opp,None)
                        original=group('r2-house-'+key+'-first',ids,firstp,firstz,firstsp,corpus=corpus)
                    report['vs_first']=report_comparison('r2-first',key,side,original,trial,newp,newz,sp,corpus)
                reports[arena][key]=report
        write(ROOT/(arena+'-results.json'),reports[arena])
    write(ROOT/'complete.json',dict(results=reports,zombie=sha(z),plant=sha(p),official_promoted=False))


def run():
    prepare()
    diversify()
    train,val=stages()
    z=zombie_fit(train,val)
    p=plant_fit(z,train,val)
    assert sha(z)==read(ROOT/'zombie-frozen.json')['sha256'] and sha(p)==read(ROOT/'plant-frozen.json')['sha256']
    test(z,p)

