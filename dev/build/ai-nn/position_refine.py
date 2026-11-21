"""Fit the same shared neural action scorer on better-returning native behavior."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import struct
import subprocess
import numpy as np
import torch
from position_study import OUT, MODELS, BASE, read, write, sha, score, jointly_idle
from overnight_eval import footer


def winner_records(train,paths,opponents):
    requests=[]
    for opp in opponents:
        for j,(uid,reference) in enumerate(train['init'][opp].items()):
            base=score(reference['match'],'zombie')
            options=[]
            for key in paths:
                candidate=train[key][opp][uid]
                value=score(candidate['match'],'zombie')
                if value==0 and base==-1 and jointly_idle(candidate,reference):continue
                options.append((value,key))
            maxscore=max(v for v,k in options)
            winners=sorted(k for v,k in options if v==maxscore)
            if maxscore>base and maxscore>=score(train['parent'][opp][uid]['match'],'zombie'):
                key=winners[j%len(winners)];weight=1.
            elif j%4==0 and 'init' in winners:
                key='init';weight=.20
            else:continue
            requests.append((opp,uid,key,paths[key],train[key][opp][uid]['match'],weight))
    return requests


def capture(task):
    opp,uid,key,policy,match,weight=task
    name=opp+'-'+uid+'-'+key
    root=OUT/'examples'
    root.mkdir(exist_ok=True)
    raw=root/(name+'.bin');replay=root/(name+'.jsonl')
    receipt=root/(name+'.json')
    if not receipt.exists():
        args=[OUT/'capture-build/Release/position_match.exe','--corpus',OUT/'plain','--id',uid,'--out',replay,
              '--planner','nn','--model',MODELS[opp],'--zombie-model',BASE,'--nn-seat','both','--position-model',policy,
              '--telemetry','--no-records','--control-hz','15','--limit-seconds','600']
        subprocess.run([str(x) for x in args],check=True,env=dict(os.environ,PVZ_POSITION_EXAMPLES=str(raw)),
                       stdout=subprocess.DEVNULL)
        f=footer(replay)
        assert not f['ai_error'] and f['log_sha256']==match['log_sha256'] and f['time']==match['time']
        write(receipt,dict(sha256=sha(raw),battle=match['log_sha256'],policy=sha(policy),replay=sha(replay)))
    assert sha(raw)==read(receipt)['sha256']
    data=raw.read_bytes();offset=0;rows=[]
    while offset<len(data):
        n=struct.unpack_from('<I',data,offset)[0];offset+=4
        assert 2<=n<=12
        count=n*32
        a=np.frombuffer(data,dtype='<f4',count=count,offset=offset).reshape(n,32)
        assert np.isfinite(a).all()
        rows.append(a);offset+=count*4
    assert offset==len(data) and rows
    return rows,weight


def refine(train,paths,opps,init,store):
    tasks=winner_records(train,paths,opps)
    assert tasks
    print('action-distillation',len(tasks),'replays',flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:samples=list(pool.map(capture,tasks))
    xs=[];weights=[];flags=[]
    for rows,importance in samples:
        per=np.array([.18 if r[0,0] else 1. for r in rows]);per*=importance/per.sum()
        for row,w in zip(rows,per):
            pad=np.zeros((12,32));pad[:len(row)]=row;xs.append(pad)
            flags.append(np.arange(12)<len(row));weights.append(w)
    x=torch.from_numpy(np.stack(xs)).double();valid=torch.from_numpy(np.stack(flags))
    importance=torch.tensor(weights,dtype=torch.double)
    torch.set_num_threads(2)
    params={n:torch.nn.Parameter(torch.from_numpy(v.copy()).double()) for n,v in init.items()}
    def logits(batch,mask):
        hidden=torch.tanh(batch@params['hidden'].T+params['bias'])
        return (batch@params['weights']+hidden@params['output']).masked_fill(~mask,-1e5)
    with torch.no_grad():baseline=logits(x,valid).softmax(-1)
    opt=torch.optim.Adam(params.values(),lr=.006)
    gen=np.random.default_rng(1182026)
    sampling=importance.numpy()/float(importance.sum())
    for _ in range(144):
        idx=gen.choice(len(x),192,replace=True,p=sampling)
        values=logits(x[idx],valid[idx]).log_softmax(-1)
        kl=torch.nn.functional.kl_div(values,baseline[idx],reduction='batchmean')
        loss=-values[:,0].mean()+1.8*kl
        opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(list(params.values()),1.);opt.step()
    updated={k:v.detach().numpy().copy() for k,v in params.items()}
    with torch.no_grad():
        scores=logits(x,valid)
        changes=int((scores.argmax(-1)!=baseline.argmax(-1)).sum())
    result=store('z-demo',updated)
    write(OUT/'action-fit.json',dict(model=sha(result),games=len(tasks),positive_games=sum(t[-1]==1 for t in tasks),
         rows=len(x),steps=144,action_argmax_changed=changes,pairs=[dict(opponent=t[0],id=t[1],teacher=t[2],weight=t[-1]) for t in tasks],
         objective='Outcome-selected demonstrations, legal candidate ranking cross-entropy and KL to initialized neural action policy. Equalized across games.'))
    return result

