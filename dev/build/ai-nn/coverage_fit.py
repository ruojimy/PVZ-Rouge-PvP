"""Fit two strategic readouts with paired real-game preferences and a frozen strong prior."""
import collections
import copy
import json
import sys
import hashlib
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from coverage_extract import lift
from coverage_study import OUT, OLD_MODEL, SIDES, LINEUPS, BIN, H, OLD, cmd, inputs_ok
from overnight_common import read, write, sha
from overnight_eval import footer, measure

def prefers_teacher(teacher, old, side):
    # Both games start identically and use the same fixed opponent.
    old_win=old['result'] and old['result'].get('winner')==side and not old['timeout']
    win=teacher['result'] and teacher['result'].get('winner')==side and not teacher['timeout']
    if not win or teacher['time']>old['time'] or (old_win and teacher['time']>.9*old['time']):
        return False
    window=teacher['time']
    for seat in SIDES:
        better=measure(teacher['activity'],seat,window)
        ref=measure(old['activity'],seat,window)
        if better['rich_idle']>ref['rich_idle']+30: return False
        if ref['deploys']>=10 and better['deploys']<.75*ref['deploys'] and better['mean_resource']>1.5*ref['mean_resource']: return False
    return True

def data():
    ids=read(OUT/'plan.json')['splits']['train']
    pieces={s:[] for s in SIDES};prefs=[]; hashes=set(); row_count=0
    distinct={'r22':0,'old':0}
    for idx,uid in enumerate(ids):
        folders={k:OUT/'train'/(f'{idx//12*12:03}-'+k) for k in LINEUPS}
        traces={k:footer(p/'matches'/(uid+'.jsonl')) for k,p in folders.items()}
        arrays={}
        for arm,p in folders.items():
            assert (p/'ready.json').exists()
            cache=p/'cache'/(uid+'.npz');assert sha(cache)==read(p/'receipts'/(uid+'.json'))['cache_sha256']
            with np.load(cache) as f: arrays[arm]={k:f[k] for k in ['g','y','logits']}
            row_count+=len(arrays[arm]['g'])
            hashes.update(hashlib.sha256(np.ascontiguousarray(row).tobytes()).digest() for row in arrays[arm]['g'])
        for seat,side in enumerate(SIDES):
            for opponent in 'ro':
                def arm(who):
                    return who+opponent if seat==0 else opponent+who
                r,o=arm('r'),arm('o')
                use_teacher=prefers_teacher(traces[r],traces[o],side)
                prefs.append(dict(id=uid,seat=side,opponent=opponent,use_teacher=bool(use_teacher),different_battle=traces[r]['log_sha256']!=traces[o]['log_sha256']))
                # Use both actually visited trajectories, with equal weight per pair and per trajectory.
                for key in [r,o]:
                    a=arrays[key]; mask=(a['g'][:,0]>.5)==(seat==0)
                    g=np.maximum(0,a['g'][mask])
                    z=a['logits'][mask,0:12] if seat==0 else a['logits'][mask,14:25]
                    y=a['y'][mask,0 if seat==0 else 2]
                    pieces[side].append((g,z,y,np.full(len(y),bool(use_teacher)),np.full(len(y),1./len(y))))
    write(OUT/'preferences.json',prefs)
    write(OUT/'coverage.json',dict(openings=len(ids),matches=4*len(ids),recorded_samples=row_count,unique_global_summary_vectors=len(hashes),preferences={s:{o:sum(p['use_teacher'] for p in prefs if p['seat']==s and p['opponent']==o) for o in 'ro'} for s in SIDES},changed_by_policy={s:{o:sum(p['different_battle'] for p in prefs if p['seat']==s and p['opponent']==o) for o in 'ro'} for s in SIDES}))
    return pieces

def readout(parts):
    g,z,y,pos,w=[torch.from_numpy(np.concatenate(v)) for v in zip(*parts)]
    y=y.long()
    if not pos.any():
        # Without a preferred teacher trajectory, the exact optimum is zero correction.
        return np.zeros((z.shape[1],g.shape[1]),dtype=np.float32),dict(epochs=0,initial_loss=0.,last_objective_before_last_step=0.,changed_argmax=0,samples=len(y),positive_rows=0,loss_history=[],reason='no_positive_pairs')
    probabilities=z.softmax(1)
    # Unit-scaled context features keep resource and time units from setting the step size.
    scale=(g.square()*w[:,None]).sum(0).div(w.sum()).sqrt().clamp_min(.1)
    x=g/scale
    delta=torch.zeros((z.shape[1],g.shape[1]),dtype=torch.double,requires_grad=True)
    opt=torch.optim.Adam([delta],lr=.012)
    history=[]
    for epoch in range(48):
        opt.zero_grad()
        corrected=z+x@delta.T
        imitation=F.cross_entropy(corrected[pos],y[pos],reduction='none')
        imitation=(imitation*w[pos]).sum()/w[pos].sum() if pos.any() else delta.sum()*0
        trust=(F.kl_div(corrected.log_softmax(1),probabilities,reduction='none').sum(1)*w).sum()/w.sum()
        loss=imitation+3.*trust+.20*delta.square().sum()/z.shape[1]
        loss.backward();opt.step()
        history.append(float(loss.detach()))
    coef=(delta.detach()/scale).float().numpy()
    prediction=z+g@torch.from_numpy(coef).double().T
    return coef,dict(epochs=48,initial_loss=history[0],last_objective_before_last_step=history[-1],changed_argmax=int((prediction.argmax(1)!=z.argmax(1)).sum()),samples=len(y),positive_rows=int(pos.sum()),loss_history=history)

def fit():
    inputs_ok();torch.set_num_threads(2)
    pieces=data()
    model=copy.deepcopy(lift());body=model['body'];heads=model['heads']
    # Preserve the old unit embeddings and all 64 hidden activations exactly.
    # The added 28 neurons expose positive global features to the two trained readouts.
    model['hidden']+=28
    body['weight']+=np.eye(28,60).tolist();body['bias'] += [0.]*28
    heads['weight']=[row+[0.]*28 for row in heads['weight']]
    stats={}
    for side,offset in [('plant',0),('zombie',14)]:
        coeff,stats[side]=readout(pieces[side])
        for k,vector in enumerate(coeff):heads['weight'][offset+k][-28:]=vector.tolist()
    model['training_source']=dict(initial_sha256=sha(OLD_MODEL),method='paired winner and tempo filtered imitation with anchored logits',preferences_sha256=sha(OUT/'preferences.json'),plan_sha256=sha(OUT/'plan.json'))
    folder=OUT/'model';folder.mkdir(exist_ok=True)
    write(folder/'model.json',model)
    st={name+'.'+field:torch.tensor(model[name][field],dtype=torch.double) for name in ('unit','body','heads') for field in ('weight','bias')}
    torch.save(dict(state_dict=st),folder/'selected.pt')
    cmd(BIN/'neural_contract.exe',folder/'model.json')
    cmd(sys.executable,H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',folder/'model.json','--checkpoint',folder/'selected.pt','--out',folder/'verify',OLD/'development-r22/matches/010.jsonl')
    assert read(folder/'verify/report.json')['passed']
    write(OUT/'fit.json',stats)
    write(OUT/'frozen.json',dict(model_sha256=sha(folder/'model.json'),checkpoint_sha256=sha(folder/'selected.pt'),source_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('coverage_*.py')},validation_outcomes_unopened=not (OUT/'validation').exists(),test_outcomes_unopened=not (OUT/'test').exists()))
