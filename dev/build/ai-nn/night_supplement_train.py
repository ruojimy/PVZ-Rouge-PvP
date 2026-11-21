"""Predeclared lower-weight/summary-only comparison with retained checkpoints."""
import argparse, copy, random
import numpy as np
import torch
from overnight_common import *
from overnight_train import PolicyNetwork, load_cache, initialize, batches, loss, score, export

class SummaryNetwork(PolicyNetwork):
    def forward(self, g, own, enemy, own_mask, enemy_mask):
        return self.heads(torch.relu(torch.nn.functional.linear(g, self.body.weight[:, :28], self.body.bias)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True)
    ap.add_argument('--mode-hidden',type=int,default=0);ap.add_argument('--summary-only',action='store_true')
    args=ap.parse_args();out=B/'supplement/models'/args.name;assert not out.exists()
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    random.seed(181118);np.random.seed(181118);torch.manual_seed(181118)
    header,val=load_cache(B/'data/validation.npz');held={r['hash'] for r in val};train=[];removed=0
    sources=[B/'data/train.npz',B/'data/collection-r1.npz']
    for i,path in enumerate(sources):
        h,rows=load_cache(path,1. if i==0 else 2.)
        for key in ['catalog_hash','rules_hash','behaviors','sim_fingerprint','feature_version','policy_version']:assert h[key]==header[key]
        kept=[r for r in rows if r['hash'] not in held];removed+=len(rows)-len(kept);train+=kept
    initial_path=OLD/'training-1/selected/model.json';doc=read(initial_path)
    assert all(doc[k]==header[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint'])
    model=initialize(doc,args.mode_hidden,False)
    if args.summary_only:
        assert not args.mode_hidden
        simpler=SummaryNetwork(16+len(doc['behaviors']))
        simpler.load_state_dict(model.state_dict());model=simpler
        with torch.no_grad():model.body.weight[:,28:].zero_()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
    source=dict(initial_sha256=sha(initial_path),data={str(p):sha(p) for p in sources},
        validation_sha256=sha(B/'data/validation.npz'),seed=181118,transition_weight=1.,
        mode_hidden=args.mode_hidden,summary_only=args.summary_only,learning_rate=.0003)
    initial=score(model,val,False,1.);best=initial['loss'];best_epoch=0
    best_state=copy.deepcopy(model.state_dict());history=[];export(model,header,out/'selected',False,source)
    for epoch in range(1,61):
        guard(FIT_END);model.train()
        for x,side,y,w in batches(train,True):
            optimizer.zero_grad(set_to_none=True);v=loss(model(*x),side,y,x[0],w,False,1.)
            v.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
        model.eval();s=score(model,val,False,1.);history.append(dict(epoch=epoch,**s))
        if s['loss']<best:
            best=s['loss'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
            export(model,header,out/'selected',False,source)
        if epoch in [20,60]:export(model,header,out/f'epoch-{epoch:02d}',False,source)
        write(out/'progress.json',dict(epoch=epoch,best_epoch=best_epoch,validation=s))
    model.load_state_dict(best_state)
    write(out/'report.json',dict(initial=initial,history=history,selected=score(model,val,False,1.),
        selected_epoch=best_epoch,train_rows=len(train),removed_overlap=removed,source=source,test_used=False))
    print(json.dumps(dict(name=args.name,epochs=60,best_epoch=best_epoch)))

if __name__=='__main__':main()
