"""One home-map response update against an empirical zero-sum pool of frozen opponents."""
import gzip
import hashlib
import itertools
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import linprog

from home_pool import OUT, POOL, CURRENT, SIDES, BIN, H, PREV, cmd, footer, score, inactive, jointly_idle, transitions, inputs_ok, arm_game
from coverage_fit import readout
from overnight_common import OLD, read, write, sha

def load_stage(split,policies):
    return {p+z:read(OUT/split/(p+z)/'ready.json')['rows'] for p in policies for z in policies}
def empirical(rows,policies):
    matrix=[];stats={}
    for p in policies:
        line=[]
        for z in policies:
            arm=p+z;group=rows[arm]
            values=[score(x['match'],'plant') for x in group.values()]
            counts=Counter(values)
            idle=sum(inactive(footer(Path(x['trace']))) for x in group.values())
            stats[arm]=dict(plant=counts[1],zombie=counts[-1],draw_or_timeout=counts[0],timeouts=sum(x['match']['timeout'] for x in group.values()),idle_timeout=idle,mean_time=np.mean([x['match']['time'] for x in group.values()]))
            line.append(np.mean(values))
        matrix.append(line)
    return np.array(matrix),stats
def maximize(matrix):
    rows,cols=matrix.shape
    res=linprog([0]*rows+[-1],A_ub=np.column_stack([-matrix.T,np.ones(cols)]),b_ub=np.zeros(cols),A_eq=[([1]*rows+[0])],b_eq=[1],bounds=[(0,1)]*rows+[(None,None)],method='highs')
    if not res.success:raise RuntimeError(res.message)
    return res.x[:-1],res.x[-1]
def solve(matrix):
    p,v=maximize(matrix);q,negv=maximize(-matrix.T)
    assert abs(v+negv)<1e-7 and min(p@matrix)>v-1e-7 and max(matrix@q)<v+1e-7
    return dict(plant=p.tolist(),zombie=q.tolist(),value=v)
def divergence():
    root=OUT/'train/nn';tmp=OUT/'temp';result={s:Counter() for s in SIDES}
    for uid in read(OUT/'plan.json')['train']:
        archive=root/'archives'/(uid+'.jsonl.gz')
        original=tmp/'nn-record.jsonl';teacher=tmp/'teacher-record.jsonl'
        with gzip.open(archive,'rb') as f,original.open('wb') as o:shutil.copyfileobj(f,o)
        assert sha(original)==read(root/'receipts'/(uid+'.json'))['raw_sha256']
        cmd(BIN/'teacher_trace.exe',original,teacher)
        with teacher.open(encoding='utf8') as f:
            for line in f:
                row=__import__('json').loads(line)
                if row['type']!='plan':continue
                side=row['seat'];counts=result[side];counts['replans']+=1
                a=row['executed_plan'];b=row['plan'];counts['any_plan_difference']+=a!=b
                for k in (['econ_goal','mode'] if side=='plant' else ['grave_start','grave_max']):
                    counts[k]+=a[k]!=b[k]
        original.unlink();teacher.unlink()
    write(OUT/'current-vs-r22.json',result)
def fit():
    inputs_ok();torch.set_num_threads(2)
    rows=load_stage('train',POOL);matrix,stats=empirical(rows,POOL);eq=solve(matrix)
    distribution={s:((np.asarray(eq[s])+.0)*.5+np.ones(len(POOL))*.5/len(POOL)).tolist() for s in SIDES}
    write(OUT/'training-matrix.json',dict(order=POOL,matrix=matrix.tolist(),stats=stats,equilibrium=eq,training_weights=distribution))
    divergence()
    variants={'home-model':distribution,
              'r22-only':{s:[1.,0.,0.] for s in SIDES},
              'snapshot-only':{s:[0.,0.,1.] for s in SIDES}}
    for name,weights in variants.items():fit_variant(rows,name,weights)
def fit_variant(rows,name,distribution):
    doc=read(CURRENT);report={}
    for seat,side in enumerate(SIDES):
        start,stop=(0,12) if seat==0 else (14,25)
        # The native compressed cache carries logits for the lifted old policy.
        # The current parent adds exactly the last 28 context columns.
        head_weights=np.array(doc['heads']['weight'])[start:stop,-28:]
        parts=[];events=Counter();choices=[]
        opponents=distribution[SIDES[1-seat]]
        for opp,opp_weight in zip(POOL,opponents):
            if not opp_weight:continue
            arm=lambda own:own+opp if seat==0 else opp+own
            own_arm=arm('n');folder=OUT/'train'/own_arm
            for uid,current in rows[own_arm].items():
                u0=score(current['match'],side);options=[]
                for policy in 'ro':
                    alt=rows[arm(policy)][uid];u1=score(alt['match'],side)
                    if u1>u0 and not (alt['match']['timeout'] and jointly_idle(alt,current)):
                        options.append((u1,policy))
                targets=[p for val,p in options if val==max(x[0] for x in options)] or ['anchor']
                choices.append(dict(id=uid,opponent=opp,parent_outcome=u0,targets=targets))
                for target in targets:events[opp+'-'+target]+=1
                cache=folder/'cache'/(uid+'.npz')
                assert sha(cache)==read(folder/'receipts'/(uid+'.json'))['cache_sha256']
                with np.load(cache) as f:
                    mask=(f['g'][:,0]>.5)==(seat==0);x=f['g'][mask].clip(min=0)
                    z=f['logits'][mask,start:stop];teacher=f['y'][mask,0 if seat==0 else 2]
                parent=z+x@head_weights.T
                for target in targets:
                    labels=z.argmax(1) if target=='o' else teacher
                    weight=np.full(len(labels),opp_weight/(len(labels)*len(targets)))
                    parts.append((x,parent,labels,np.full(len(labels),target!='anchor'),weight))
        coef,training=readout(parts)
        for i,vector in enumerate(coef):
            doc['heads']['weight'][start+i][-28:]=(head_weights[i]+vector).tolist()
        report[side]=dict(fit=training,targets=dict(events),pairs=choices)
    doc['training_source']=dict(initial_sha256=sha(CURRENT),method='one independent outcome-ranked imitation response per seat against frozen opponents',variant=name,opponent_weights=distribution,empirical_matrix_sha256=sha(OUT/'training-matrix.json'),plan_sha256=sha(OUT/'plan.json'))
    model=OUT/name/'model.json';write(model,doc)
    st={k+'.'+v:torch.tensor(doc[k][v],dtype=torch.double) for k in ('unit','body','heads') for v in ('weight','bias')}
    torch.save(dict(state_dict=st),model.parent/'selected.pt')
    cmd(BIN/'neural_contract.exe',model)
    cmd(sys.executable,H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',model,'--checkpoint',model.parent/'selected.pt','--out',model.parent/'verify',OLD/'development-r22/matches/010.jsonl')
    assert read(model.parent/'verify/report.json')['passed'] and not (OUT/'test').exists()
    path=OUT/'frozen.json' if name=='home-model' else model.parent/'frozen.json'
    write(path,dict(model_sha256=sha(model),report=report,test_outcomes_unopened=True,source_sha256={p.name:sha(p) for p in [H/'home_pool.py',H/'home_response.py',H/'coverage_fit.py']}))
def report():
    inputs_ok();frozen=read(OUT/'frozen.json')
    assert sha(OUT/'home-model/model.json')==frozen['model_sha256']
    assert all(sha(H/k)==v for k,v in frozen['source_sha256'].items())
    policies=POOL+'h';rows=load_stage('test',policies);matrix,stats=empirical(rows,policies);comparisons={}
    for seat,side in enumerate(SIDES):
        for opponent in policies:
            arm=lambda own:own+opponent if seat==0 else opponent+own
            for ref in 'rn':
                a=rows[arm(ref)];b=rows[arm('h')]
                matches=lambda group:{uid:x['match'] for uid,x in group.items()}
                comparison=transitions(matches(a),matches(b),list(a),side)
                comparison['jointhold_flags']=[uid for uid in a if b[uid]['match']['timeout'] and jointly_idle(b[uid],a[uid])]
                comparisons['/'.join([side,opponent,ref])]=comparison
    for split,pool in [('test',policies),('train',POOL)]:
        for group in load_stage(split,pool).values():
            for uid,x in group.items():
                trace=Path(x['trace']);meta=footer(trace)
                assert meta['log_sha256']==x['match']['log_sha256'] and not meta['ai_error']
                h=sha(trace);rec=trace.parent.parent/'receipts'/(trace.stem+'.json')
                assert h==(read(rec)['compact_sha256'] if rec.exists() else x['match']['file_sha256'])
    controls={}
    for key,name in [('a','r22-only'),('b','snapshot-only')]:
        assert sha(OUT/name/'model.json')==read(OUT/name/'frozen.json')['model_sha256']
        for seat,side in enumerate(SIDES):
            for opp in POOL:
                arm=lambda own:own+opp if seat==0 else opp+own
                print('controlled-test',arm(key),flush=True);arm_game('test',arm(key))
                group=read(OUT/'test'/arm(key)/'ready.json')['rows']
                matches={uid:x['match'] for uid,x in group.items()}
                for uid,x in group.items():
                    assert x['match']['file_sha256']==sha(Path(x['trace'])) and not x['match']['ai_error']
                counts=Counter(score(x,side) for x in matches.values())
                controls[arm(key)]=dict(win=counts[1],timeout=sum(x['timeout'] for x in matches.values()),loss=counts[-1],utility=sum(score(x,side) for x in matches.values()),idle_timeout=sum(inactive(footer(Path(x['trace']))) for x in group.values()),vs_parent=transitions({i:x['match'] for i,x in rows[arm('n')].items()},matches,list(group),side))
    horizon={}
    for side,arm in [('plant','nr'),('zombie','rn')]:
        folder=OUT/'horizon-106'/side
        cmd(sys.executable,H/'eval.py','--bin',BIN/'headless_match.exe','--corpus',PREV/'plain','--out-dir',folder,'--ids','106','--jobs',1,'--limit-seconds',1200,'--planner','nn','--','--model',CURRENT,'--nn-seat',side,'--telemetry','--no-records')
        match=read(folder/'summary.json')['matches']['106']
        assert not match['ai_error']
        full=footer(folder/'matches/106.jsonl')
        short=footer(PREV/'validation'/arm/'matches/106.jsonl')
        assert short['timeout'] and [e for e in full['activity'] if e['time']<600]==[e for e in short['activity'] if e['time']<600]
        horizon[side]=match
    write(OUT/'completion.json',dict(heldout_openings=12,order=policies,test_matrix=matrix.tolist(),stats=stats,comparisons=comparisons,controls=controls,restricted_test_equilibrium=solve(matrix),train_games=144,new_train_games=112,reused_train_games=32,new_test_games=336,new_home_games=448,additional_railway_probes=horizon,formal_promoted=False))
