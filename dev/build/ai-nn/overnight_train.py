"""Policy-v2 cloning with optional independent mode network and transition targets."""
import argparse,copy,random
import numpy as np
import torch
from overnight_common import *
from train import DeepSet,collate
OFFSETS=(0,12,14,25,28)

class PolicyNetwork(DeepSet):
    def __init__(self,unit_dim,mode_hidden=0):
        super().__init__(unit_dim,8,64)
        self.body=torch.nn.Linear(60,64);self.heads=torch.nn.Linear(64,28)
        self.mode_hidden=mode_hidden
        if mode_hidden:
            self.mode_body=torch.nn.Linear(28,mode_hidden);self.mode_output=torch.nn.Linear(mode_hidden,2)
    def forward(self,g,own,enemy,own_mask,enemy_mask):
        result=super().forward(g,own,enemy,own_mask,enemy_mask)
        if self.mode_hidden:
            result=result.clone();result[:,12:14]=self.mode_output(torch.relu(self.mode_body(g)))
        return result

def load_cache(path,boost=1.):
    with np.load(path,allow_pickle=False) as f: data={k:f[k] for k in f.files}
    header=json.loads(str(data['header']));g=torch.from_numpy(data['g']);y=torch.from_numpy(data['y'].astype(np.int64))
    unit={k:torch.from_numpy(data[k]) for k in ['own','enemy']};empty=torch.zeros((1,unit['own'].shape[1]))
    rows=[]
    for i in range(len(g)):
        row=dict(g=g[i],y=y[i],plant=bool(g[i,0]>.5),sample_weight=float(data['weight'][i])*boost,hash=bytes(data['hashes'][i]))
        for k in ['own','enemy']:
            a,b=data[k+'_offsets'][i:i+2];row[k+'_count']=int(b-a);row[k]=unit[k][a:b] if b>a else empty
        rows.append(row)
    return header,rows

def initialize(doc,mode_hidden,transition):
    model=PolicyNetwork(16+len(doc['behaviors']),mode_hidden)
    assert doc.get('feature_version',1)==2 and not doc.get('residual',False)
    with torch.no_grad():
        for k in ['unit','body']:
            layer=getattr(model,k);layer.weight.copy_(torch.tensor(doc[k]['weight']));layer.bias.copy_(torch.tensor(doc[k]['bias']))
        if doc.get('policy_version',1)==2:
            model.heads.weight.copy_(torch.tensor(doc['heads']['weight']));model.heads.bias.copy_(torch.tensor(doc['heads']['bias']))
        else:
            w=torch.tensor(doc['heads']['weight']);b=torch.tensor(doc['heads']['bias'])
            model.heads.weight[:11].copy_(w[:11]);model.heads.bias[:11].copy_(b[:11])
            model.heads.weight[11].copy_(w[10]);model.heads.bias[11]=b[10]-2
            model.heads.weight[12:].copy_(w[11:]);model.heads.bias[12:].copy_(b[11:])
        if mode_hidden:
            if doc.get('mode_hidden')==mode_hidden and bool(doc.get('mode_transition'))==transition:
                for k in ['mode_body','mode_output']:
                    layer=getattr(model,k);layer.weight.copy_(torch.tensor(doc[k]['weight']));layer.bias.copy_(torch.tensor(doc[k]['bias']))
            else:
                model.mode_output.weight.mul_(.1);model.mode_output.bias.zero_()
        elif transition != bool(doc.get('mode_transition')):
            model.heads.weight[12:14].zero_();model.heads.bias[12:14].zero_();model.heads.bias[12]=1.
    return model

def batches(rows,shuffle=False):
    order=list(range(len(rows)))
    if shuffle:random.shuffle(order)
    for start in range(0,len(order),256):
        part=[rows[i] for i in order[start:start+256]];x,side,y=collate(part)
        yield x,side,y,torch.tensor([r['sample_weight'] for r in part])

def loss(logits,side,y,g,weights,transition,transition_weight):
    terms=[]
    for h in range(3):
        mask=side if h<2 else ~side
        if not mask.any():continue
        target=y[mask,h];w=weights[mask]
        if h==1:
            changed=target!=(g[mask,11]>.5).long();w=w*torch.where(changed,transition_weight,1.)
            if transition:target=changed.long()
        if h==0:w=w*torch.where(target==11,3.,1.)
        ce=torch.nn.functional.cross_entropy(logits[mask,OFFSETS[h]:OFFSETS[h+1]],target,reduction='none')
        terms.append((2 if h==1 else 1)*(ce*w).sum()/w.sum())
    return torch.stack(terms).mean()

@torch.no_grad()
def score(model,rows,transition,transition_weight):
    n=0;total=0.;counts=[0]*3;correct=[0]*3;sw_n=sw_ok=pred_sw=goal_n=goal_ok=0
    for x,side,y,w in batches(rows):
        z=model(*x);n+=len(y);total+=float(loss(z,side,y,x[0],torch.ones(len(y)),transition,transition_weight))*len(y)
        for h in range(3):
            mask=side if h<2 else ~side;pred=z[:,OFFSETS[h]:OFFSETS[h+1]].argmax(1)
            if h==1 and transition:pred=pred^(x[0][:,11]>.5).long()
            counts[h]+=int(mask.sum());correct[h]+=int(((pred==y[:,h])&mask).sum())
            if h==1:
                changed=mask&(y[:,1]!=(x[0][:,11]>.5).long());sw_n+=int(changed.sum());sw_ok+=int(((pred==y[:,1])&changed).sum());pred_sw+=int((mask&(pred!=(x[0][:,11]>.5).long())).sum())
            if h==0:
                m=mask&(y[:,0]==11);goal_n+=int(m.sum());goal_ok+=int((m&(pred==11)).sum())
    return dict(samples=n,loss=total/n,accuracy=[c/max(1,k) for c,k in zip(correct,counts)],transition_count=sw_n,
                transition_recall=sw_ok/max(1,sw_n),transition_precision=sw_ok/max(1,pred_sw),transition_f1=2*sw_ok/max(1,sw_n+pred_sw),
                goal_11_count=goal_n,goal_11_accuracy=goal_ok/max(1,goal_n))

def export(model,header,folder,transition,source):
    folder.mkdir(parents=True,exist_ok=True)
    doc={k:header[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint']}
    doc.update(format='pvz-deepset-hybrid-1',feature_version=2,policy_version=2,embedding=8,hidden=64,mode_transition=transition,
               enabled_heads=[True,True,True,False],training_source=source)
    keys=['unit','body','heads']
    if model.mode_hidden:doc['mode_hidden']=model.mode_hidden;keys+=['mode_body','mode_output']
    for k in keys:
        layer=getattr(model,k);doc[k]=dict(weight=layer.weight.detach().tolist(),bias=layer.bias.detach().tolist())
    write(folder/'model.json',doc)
    target=folder/'selected.pt';tmp=folder/'selected.pt.tmp'
    torch.save(dict(state_dict=model.state_dict(),feature_header=header,spec=dict(embedding=8,hidden=64,feature_version=2,policy_version=2,mode_hidden=model.mode_hidden,mode_transition=transition)),tmp)
    os.replace(tmp,target)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,nargs='+',required=True);ap.add_argument('--validation',type=Path,required=True)
    ap.add_argument('--initial',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--mode-hidden',type=int,default=0);ap.add_argument('--transition',action='store_true')
    ap.add_argument('--transition-weight',type=float,default=12);ap.add_argument('--epochs',type=int,default=80)
    ap.add_argument('--lr',type=float,default=.0003);ap.add_argument('--seed',type=int,default=181118);args=ap.parse_args()
    assert not args.out.exists();guard(FIT_END)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True);random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    header,val=load_cache(args.validation);held={r['hash'] for r in val};train=[];removed=0
    for i,p in enumerate(args.data):
        h,rows=load_cache(p,1. if i==0 else 2.)
        for key in ['catalog_hash','rules_hash','behaviors','sim_fingerprint','feature_version','policy_version']:assert h[key]==header[key]
        kept=[r for r in rows if r['hash'] not in held];removed+=len(rows)-len(kept);train+=kept
    doc=read(args.initial);assert all(doc[k]==header[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint'])
    model=initialize(doc,args.mode_hidden,args.transition)
    opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=.0001)
    source=dict(initial=str(args.initial),initial_sha256=sha(args.initial),data={str(p):sha(p) for p in args.data},validation_sha256=sha(args.validation),
                transition_weight=args.transition_weight,seed=args.seed,learning_rate=args.lr)
    initial=score(model,val,args.transition,args.transition_weight);best=initial['loss'];state=copy.deepcopy(model.state_dict());stale=0;history=[];best_epoch=0;reason='epochs'
    export(model,header,args.out,args.transition,source)
    for epoch in range(args.epochs):
        if time.time()>FIT_END-20:reason='time_limit';break
        guard(FIT_END);model.train()
        for x,side,y,w in batches(train,True):
            opt.zero_grad(set_to_none=True);v=loss(model(*x),side,y,x[0],w,args.transition,args.transition_weight);v.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
        model.eval();s=score(model,val,args.transition,args.transition_weight);history.append(dict(epoch=epoch+1,**s))
        if s['loss']<best:
            best=s['loss'];state=copy.deepcopy(model.state_dict());stale=0;best_epoch=epoch+1;export(model,header,args.out,args.transition,source)
        else:stale+=1
        write(args.out/'progress.json',dict(epoch=epoch+1,best_epoch=best_epoch,validation=s,train_rows=len(train),stale=stale))
        if epoch%5==0:print(json.dumps(history[-1]),flush=True)
        if stale>=15:reason='early_stop';break
    model.load_state_dict(state);export(model,header,args.out,args.transition,source)
    report=dict(initial=initial,history=history,selected=score(model,val,args.transition,args.transition_weight),selected_epoch=best_epoch,
                train_rows=len(train),removed_overlap=removed,stop_reason=reason,test_used=False,source=source)
    write(args.out/'report.json',report);print(json.dumps(report['selected']),flush=True)

if __name__=='__main__':main()
