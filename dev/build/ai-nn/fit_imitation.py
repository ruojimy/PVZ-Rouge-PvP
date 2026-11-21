"""Continue feature-v2 imitation from a model with explicit train/validation files."""
import argparse
import copy
import hashlib
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from dagger_train import Network, batches, export, from_old, loss, score
from train import read_data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--validation',type=Path,required=True)
    ap.add_argument('--initial',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--epochs',type=int,default=25)
    ap.add_argument('--learning-rate',type=float,default=.0002)
    args = ap.parse_args()
    if args.out.exists():raise SystemExit('Use a new output directory')
    if args.epochs < 1 or not args.learning_rate > 0:raise SystemExit('Epochs and learning rate must be positive')
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    random.seed(1744);np.random.seed(1744);torch.manual_seed(1744)
    header,train = read_data(args.data)
    vh,val = read_data(args.validation)
    for h in [header,vh]:
        for key in ['augment','augment_seed']:h.pop(key,None)
    if header != vh or header.get('feature_version',1) != 2:
        raise SystemExit('This continuation trainer requires matching feature-v2 train and validation data')
    if not train or not val:raise SystemExit('Empty training or validation set')
    for row in train:row.setdefault('sample_weight',.25 if row.get('aug') else 1.)
    doc = json.loads(args.initial.read_text('utf-8'))
    if doc.get('policy_version',1)!=1:raise SystemExit('Use the policy-v2 trainer for policy-v2 weights')
    if any(doc[k] != header[k] for k in ['sim_fingerprint','behaviors','catalog_hash','rules_hash']):
        raise SystemExit('Initial model must match the current simulation and vocabulary')
    if doc.get('format') != 'pvz-deepset-hybrid-1' or doc.get('residual',False) or (doc['embedding'],doc['hidden']) != (8,64):
        raise SystemExit('This trainer accepts absolute 8/64 hybrid models only')
    if doc.get('feature_version',1)==1:
        model = from_old(doc,header)
    elif doc['feature_version']==2:
        model = Network(16+len(header['behaviors']))
        with torch.no_grad():
            for name in ['unit','body','heads']:
                layer=getattr(model,name)
                layer.weight.copy_(torch.tensor(doc[name]['weight']))
                layer.bias.copy_(torch.tensor(doc[name]['bias']))
    else:raise SystemExit('Unsupported feature version')
    digest = lambda r:hashlib.sha256(r['g'].numpy().tobytes()+r['own'].numpy().tobytes()+r['enemy'].numpy().tobytes()).digest()
    held={digest(r) for r in val};before=len(train);train=[r for r in train if digest(r) not in held]
    if not train:raise SystemExit('No non-overlapping training states')
    initial=score(model,val);best=initial['weighted_loss'];state=copy.deepcopy(model.state_dict());stale=0;history=[]
    opt=torch.optim.AdamW(model.parameters(),lr=args.learning_rate,weight_decay=.0001)
    start=time.perf_counter()
    for epoch in range(args.epochs):
        model.train()
        for x,side,y,w in batches(train,True):
            opt.zero_grad(set_to_none=True);value=loss(model(*x),side,y,x[0],w)
            value.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
        model.eval();s=score(model,val);history.append(dict(epoch=epoch+1,**s))
        print(json.dumps(history[-1]),flush=True)
        if s['weighted_loss']<best:best=s['weighted_loss'];state=copy.deepcopy(model.state_dict());stale=0
        else:stale+=1
        if stale>=8:break
    model.load_state_dict(state)
    source={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.data,args.validation,args.initial]}
    export(model,header,args.out,dict(inputs=source,method='transition-weighted imitation; no reward training'))
    report=dict(initial=initial,history=history,selected_validation=score(model,val),train_rows=len(train),
                removed_overlap=before-len(train),test_used=False,wall_seconds=time.perf_counter()-start,
                promotion='Requires separate paired games, completion and productive-action review')
    (args.out/'report.json').write_text(json.dumps(report,indent=2),'utf-8')


if __name__=='__main__':main()
