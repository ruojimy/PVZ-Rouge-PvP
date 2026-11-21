"""Alternate a neural zombie action scorer and neural plant economy readout, then open the held-out games."""
import itertools
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

from position_study import OUT, R, H, BIN, TOOL, BASE, MODELS, EXPORT, read, write, sha, cmd, inputs_ok
from home_pool import score, jointly_idle, transitions
from overnight_eval import footer, measure

MODEL_DIR=OUT/'models'
HOME=OUT/'plain'
TRANSFER=OUT/'transfer/plain'
FP=re.search('"([^"]+)"',(BIN.parent/'ai_nn_build.h').read_text()).group(1)
SPATIAL_KEYS=('weights','hidden','bias','output')


def group(name, ids, plant, zombie, tactical=None, limit=600, corpus=HOME, binary=TOOL):
    folder=OUT/'games'/name
    params=dict(ids=ids,plant=sha(plant) if plant else None,zombie=sha(zombie) if zombie else None,
                tactical=sha(tactical) if tactical else None,limit=limit,corpus=sha(corpus/'index.json'),binary=sha(binary))
    signature=folder/'parameters.json'
    if signature.exists():
        assert read(signature)==params,name
    else:write(signature,params)
    if not (folder/'summary.json').exists():
        args=[sys.executable,H/'eval.py','--bin',binary,'--corpus',corpus,'--out-dir',folder,
              '--ids',','.join(ids),'--jobs',4,'--limit-seconds',limit,'--resume']
        extra=['--telemetry','--no-records']
        if plant or zombie:
            args+=['--planner','nn']
            extra+=['--model',plant or zombie,'--nn-seat','both' if plant and zombie else 'plant' if plant else 'zombie']
            if plant and zombie:extra+=['--zombie-model',zombie]
        if tactical:extra+=['--position-model',tactical]
        print(name,len(ids),flush=True)
        cmd(*args,'--',*extra)
    summary=read(folder/'summary.json')
    assert set(summary['matches'])==set(ids) and not summary['crashed'],name
    rows={}
    for uid,m in summary['matches'].items():
        path=folder/'matches'/(uid+'.jsonl')
        assert not m['ai_error'] and sha(path)==m['file_sha256'],(name,uid)
        if tactical:
            with path.open(encoding='utf8') as stream:header=json.loads(next(stream))
            assert header['zombie_position_sha256']==params['tactical']
        rows[uid]=dict(match=m,trace=str(path))
    return rows


def initial(rng):
    # Priors for continuing to play and saving when the original macro planner is saving.
    # The source grave and target coordinates are deliberately absent from the prior.
    w=np.zeros(32)
    w[:10]=[0.,-.35,-.25,-.75,.4,-.35,-.35,2.5,1.3,1.7]
    w[10:]=[.2,.1,.55,-.38,.12,.17,.33,-.12,.05,.06,-.3,.22,1.25,-.28,.3,-.1,.08,.08,-.1,.05,2.5,.6]
    return dict(weights=w,hidden=rng.normal(0,.22,(8,32)),bias=rng.normal(0,.07,8),output=rng.normal(0,.12,8))


def store_spatial(name,params):
    path=MODEL_DIR/(name+'.json')
    doc=dict(format='pvz-legal-action-readout-1',sim_fingerprint=FP,**{k:v.tolist() for k,v in params.items()})
    if path.exists():assert read(path)==doc
    else:write(path,doc)
    return path


def store_plant(name,delta):
    doc=read(BASE)
    # Only the final 28 context columns in the plant economic logits are updated.
    for i,row in enumerate(delta):
        doc['heads']['weight'][i][-28:]=(np.array(doc['heads']['weight'][i][-28:])+row).tolist()
    doc['training_source']=dict(parent=sha(BASE),method='paired native-return parameter search against newly frozen zombie controller',checkpoint=name)
    path=MODEL_DIR/(name+'.json')
    if path.exists():assert read(path)==doc
    else:write(path,doc)
    return path


def metrics(rows,side):
    counts=Counter(score(r['match'],side) for r in rows.values())
    return dict(win=counts[1],timeout=counts[0],loss=counts[-1],utility=counts[1]-counts[-1])


def selection(after,before,side):
    per=[]
    for opponent in after:
        rows=after[opponent];ref=before[opponent]
        values=[]
        for uid,row in rows.items():
            val=score(row['match'],side)
            if row['match']['timeout'] and score(ref[uid]['match'],side)<0 and jointly_idle(row,ref[uid]):
                val=-1
            values.append(val)
        per.append(sum(values))
    return (sum(per),min(per))


def search_zombie(plan,opponents):
    rng=np.random.default_rng(118228)
    init=initial(rng)
    sigma={'weights':.65,'hidden':.13,'bias':.12,'output':.22}
    directions=[{k:rng.normal(0,sigma[k],s.shape) for k,s in init.items()} for _ in range(2)]
    paths={};train={}
    paths['init']=store_spatial('z-init',init)
    for i,direction in enumerate(directions):
        for sign,label in [(1,'p'),(-1,'m')]:
            paths[str(i)+label]=store_spatial('z-'+str(i)+label,{k:init[k]+sign*direction[k] for k in init})
    def evaluate(name,model,split):
        return {o:group('z-'+split+'-'+name+'-'+o,plan[split],MODELS[o],BASE,model) for o in opponents}
    train['parent']=evaluate('parent',None,'train')
    for name,model in paths.items():train[name]=evaluate(name,model,'train')
    objective={n:selection(g,train['parent'],'zombie') for n,g in train.items()}
    gradient=np.array([objective[str(i)+'p'][0]-objective[str(i)+'m'][0] for i in range(2)],float)
    coeff=gradient/max(1.,abs(gradient).sum())
    updated={k:init[k]+sum(c*d[k] for c,d in zip(coeff,directions)) for k in init}
    from position_refine import refine
    nominated=max(paths,key=lambda n:(*objective[n],n=='init',n))
    paths['demo']=refine(train,paths,opponents,init,store_spatial)
    paths['step']=store_spatial('z-step',updated)
    # Cross-check the return-weighted step and the best explored weights with unopened validation seeds.
    final=['step',nominated,'demo']
    validation={'parent':evaluate('parent',None,'validation')}
    for name in final:validation[name]=evaluate(name,paths[name],'validation')
    validation_score={n:selection(g,validation['parent'],'zombie') for n,g in validation.items()}
    best=max(final,key=lambda n:(*validation_score[n],n=='step'))
    model=paths[best]
    write(OUT/'zombie-frozen.json',dict(selected=best,model=str(model),sha256=sha(model),objective=objective,
          return_weighted_step=coeff.tolist(),validation=validation_score,opponents=opponents,
          selected_before_plant_training=True,heldout_unopened=True))
    return model


def search_plant(plan,zombie):
    rng=np.random.default_rng(11023)
    # Smooth adjacent economic-goal biases so small changes can cross a class boundary.
    zero=np.zeros((12,28))
    dirs=[]
    for _ in range(2):
        direction=rng.normal(0,.065,zero.shape)
        direction+=np.linspace(-1,1,12)[:,None]*rng.normal(0,.19,(1,28))
        dirs.append(direction)
    paths={}
    for i,d in enumerate(dirs):
        for sign,s in [(1,'p'),(-1,'m')]:paths[str(i)+s]=store_plant('p-'+str(i)+s,sign*d)
    def evaluate(name,model,split):
        return {'new-zombie':group('p-'+split+'-'+name,plan[split],model,BASE,zombie)}
    train={'parent':evaluate('parent',BASE,'train')}
    for n,m in paths.items():train[n]=evaluate(n,m,'train')
    obj={n:selection(g,train['parent'],'plant') for n,g in train.items()}
    g=np.array([obj[str(i)+'p'][0]-obj[str(i)+'m'][0] for i in range(2)],float)
    coeff=g/max(1.,abs(g).sum())
    paths['step']=store_plant('p-step',sum(c*d for c,d in zip(coeff,dirs)))
    nominees=['step',max(paths.keys()-{'step'},key=lambda n:(*obj[n],n))]
    val={'parent':evaluate('parent',BASE,'validation')}
    for n in nominees:val[n]=evaluate(n,paths[n],'validation')
    vs={n:selection(rows,val['parent'],'plant') for n,rows in val.items()}
    best=max(nominees,key=lambda n:(*vs[n],n=='step'))
    model=paths[best]
    cmd(BIN/'neural_contract.exe',model)
    write(OUT/'plant-frozen.json',dict(selected=best,model=str(model),sha256=sha(model),objective=obj,
          return_weighted_step=coeff.tolist(),validation=vs,frozen_zombie=sha(zombie),heldout_unopened=True))
    return model


def transfer_setup(plan):
    sub=OUT/'transfer'
    if (sub/'plain/index.json').exists():return
    seeds=set(plan['seeds'][18:])
    draft=read(OUT/'draft.json')
    rows=[]
    for name in ['山地','铁道']:
        for night in [False,True]:
            options=[s for s in draft if s['map']==name and s['night']==night and s['seed'] in seeds]
            rows.extend((options[0],options[-1]))
    assert len(rows)==8
    write(sub/'scenarios.json',rows)
    cmd(sys.executable,H/'export_corpus.py',sub/'scenarios.json',sub/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',sub/'corpus',sub/'plain')


def report_comparison(domain,label,side,before,after,plant,zombie,tactical,corpus):
    ids=list(before)
    changes=transitions({i:r['match'] for i,r in before.items()},{i:r['match'] for i,r in after.items()},ids,side)
    horizons={}
    lt=[i for i in ids if score(before[i]['match'],side)==-1 and after[i]['match']['timeout']]
    if lt:
        long=group(domain+'-1200-'+label,lt,plant,zombie,tactical,1200,corpus)
        for uid in lt:
            short=footer(Path(after[uid]['trace']));ext=footer(Path(long[uid]['trace']))
            assert [e for e in ext['activity'] if e['time']<600]==[e for e in short['activity'] if e['time']<600]
            horizons[uid]=long[uid]['match']
    return dict(before=metrics(before,side),after=metrics(after,side),paired=changes,
                idle_flags=[i for i in ids if after[i]['match']['timeout'] and jointly_idle(after[i],before[i])],horizons=horizons)


def test(plan,zmodel,pmodel):
    results={}
    for domain,corpus,ids,opps in [('home',HOME,plan['test'],'roh'),('away',TRANSFER,[f'{i:03}' for i in range(8)],'rh')]:
        records={}
        for side in ['zombie','plant']:
            for o in opps:
                anchor=MODELS[o]
                if side=='zombie':p0,p1,z0,z1,sp=anchor,anchor,BASE,BASE,zmodel
                else:p0,p1,z0,z1,sp=BASE,pmodel,anchor,anchor,None
                key=side+'-'+o
                a=group(domain+'-'+key+'-parent',ids,p0,z0,None,corpus=corpus)
                b=group(domain+'-'+key+'-candidate',ids,p1,z1,sp,corpus=corpus)
                records[key]=report_comparison(domain,key,side,a,b,p1,z1,sp,corpus)
        if domain=='home':
            a=group('home-joint-parent',ids,BASE,BASE,None)
            b=group('home-joint-candidate',ids,pmodel,BASE,zmodel)
            records['joint']={side:report_comparison(domain,'joint-'+side,side,a,b,pmodel,BASE,zmodel,corpus) for side in ['plant','zombie']}
        results[domain]=records
        write(OUT/(domain+'-results.json'),records)
    write(OUT/'complete.json',dict(results=results,zombie=sha(zmodel),plant=sha(pmodel),release=plan['release_sha256'],
          official_promoted=False,openings={'home_train':12,'home_validation':6,'home_test':18,'map_transfer':8}))


def run():
    inputs_ok()
    assert sha(TOOL)==read(OUT/'build.json')['binary']
    plan=read(OUT/'plan.json');opps=read(OUT/'opponents.json')['selected']
    assert all(sha(MODELS[k])==read(OUT/'opponents.json')['model_sha256'][k] for k in opps)
    transfer_setup(plan)
    # The original and isolated binaries must produce precisely the same battle without the new decision head.
    for name,binary in [('original',BIN/'headless_match.exe'),('isolated',TOOL)]:
        group('parity-'+name,plan['train'][:2],BASE,BASE,binary=binary)
    a,b=[read(OUT/'games'/('parity-'+n)/'summary.json')['matches'] for n in ['original','isolated']]
    assert all(a[i]['log_sha256']==b[i]['log_sha256'] and a[i]['time']==b[i]['time'] for i in a)
    z=search_zombie(plan,opps)
    p=search_plant(plan,z)
    assert sha(z)==read(OUT/'zombie-frozen.json')['sha256'] and sha(p)==read(OUT/'plant-frozen.json')['sha256']
    test(plan,z,p)

import sys

