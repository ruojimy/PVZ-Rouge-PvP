"""Two matched training controls, using the full study's fixed optimizer and native evaluator."""
import copy
import numpy as np
import torch
from coverage_fit import readout
from coverage_study import OUT, OLD, H, BIN, SIDES, cmd, run_group
from coverage_guard import run
from overnight_common import read, write, sha
from overnight_eval import screen

def design():
    plan=read(OUT/'plan.json')
    scenarios=read(OUT/'scenarios.json')
    chosen=[]
    maps=list(dict.fromkeys(x['map'] for x in scenarios))
    for m,name in enumerate(maps):
        pool=[uid for uid in plan['splits']['train'] if scenarios[int(uid)]['map']==name and scenarios[int(uid)]['night']==bool(m%2)]
        chosen.append(pool[m%len(pool)])
    assert len(set(chosen))==12
    write(OUT/'control-design.json',dict(frozen_before_validation=not (OUT/'validation').exists(),models={'twelve-both':dict(ids=chosen,opponents='ro'),'all-r22':dict(ids=plan['splits']['train'],opponents='r')},optimizer='identical to full study',evaluation='24 validation openings per seat against fixed r22; diagnostics only, not selectable',script_sha256=sha(__file_path())))
def __file_path():
    from pathlib import Path
    return Path(__file__)
def fit_controls():
    torch.set_num_threads(2)
    pref={(p['id'],p['seat'],p['opponent']):p['use_teacher'] for p in read(OUT/'preferences.json')}
    for name,spec in read(OUT/'control-design.json')['models'].items():
        doc=copy.deepcopy(read(OUT/'model/model.json'))
        report={}
        for seat,side in enumerate(SIDES):
            parts=[]
            for uid in spec['ids']:
                for opponent in spec['opponents']:
                    for which in 'ro':
                        lineup=which+opponent if seat==0 else opponent+which
                        folder=OUT/'train'/f'{int(uid)//12*12:03}-{lineup}'
                        with np.load(folder/'cache'/(uid+'.npz')) as a:
                            mask=(a['g'][:,0]>.5)==(seat==0)
                            x=a['g'][mask].clip(min=0)
                            z=a['logits'][mask,0:12] if seat==0 else a['logits'][mask,14:25]
                            y=a['y'][mask,0 if seat==0 else 2]
                            parts.append((x,z,y,np.full(len(y),pref[(uid,side,opponent)]),np.full(len(y),1./len(y))))
            coeff,report[side]=readout(parts)
            for k,row in enumerate(coeff):
                doc['heads']['weight'][(0 if seat==0 else 14)+k][-28:]=row.tolist()
        folder=OUT/'controls'/name
        doc['training_source']['control']=name
        write(folder/'model.json',doc);write(folder/'fit.json',report)
        st={k+'.'+v:torch.tensor(doc[k][v],dtype=torch.double) for k in ('unit','body','heads') for v in ('weight','bias')}
        torch.save(dict(state_dict=st),folder/'selected.pt')
        cmd(BIN/'neural_contract.exe',folder/'model.json')
        cmd(__import__('sys').executable,H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',folder/'model.json','--checkpoint',folder/'selected.pt','--out',folder/'verify',OLD/'development-r22/matches/010.jsonl')
        write(folder/'freeze.json',dict(sha256=sha(folder/'model.json'),validation_unopened=not (OUT/'validation').exists()))
def eval_controls():
    results={}
    for name in read(OUT/'control-design.json')['models']:
        folder=OUT/'controls'/name;model=folder/'model.json'
        assert sha(model)==read(folder/'freeze.json')['sha256']
        for side in SIDES:
            game=run_group('validation',name+'-'+side,model if side=='plant' else None,model if side=='zombie' else None)
            for ref in ['rr', 'or' if side=='plant' else 'ro']:
                assessment=screen(OUT/'validation'/ref,game,side)
                results[name+'-'+side+'-'+ref]={k:v for k,v in assessment.items() if k!='activity'}
    write(OUT/'control-results.json',results)
if __name__=='__main__':
    import sys
    {'design':design,'fit':fit_controls,'evaluate':eval_controls}[sys.argv[1]]()
