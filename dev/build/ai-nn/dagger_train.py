"""State-summary warm start, transition-weighted imitation, then dataset aggregation."""
import argparse,copy,hashlib,json,random,time
from pathlib import Path
import numpy as np
import torch
from train import DeepSet,read_data,collate,OFFSETS

class Network(DeepSet):
    def __init__(self,unit_dim):
        super().__init__(unit_dim,8,64)
        self.body=torch.nn.Linear(28+32,64)

def from_old(doc,header):
    model=Network(16+len(header['behaviors']))
    with torch.no_grad():
        model.unit.weight.zero_()
        model.unit.weight[:,:16].copy_(torch.tensor(doc['unit']['weight'])[:,:16])
        for i,name in enumerate(header['behaviors']):
            if name in doc['behaviors']:
                model.unit.weight[:,16+i].copy_(torch.tensor(doc['unit']['weight'])[:,16+doc['behaviors'].index(name)])
        model.unit.bias.copy_(torch.tensor(doc['unit']['bias']))
        old=torch.tensor(doc['body']['weight']);model.body.weight.zero_()
        model.body.weight[:,:20].copy_(old[:,:20]);model.body.weight[:,28:].copy_(old[:,20:])
        model.body.bias.copy_(torch.tensor(doc['body']['bias']))
        model.heads.weight.copy_(torch.tensor(doc['heads']['weight']));model.heads.bias.copy_(torch.tensor(doc['heads']['bias']))
    return model

def loss(logits,side,y,g,weights):
    terms=[]
    for h in range(3):
        mask=side if h<2 else ~side
        if not mask.any():continue
        w=weights[mask]
        if h==1:w=w*torch.where(y[mask,1]!=(g[mask,11]>.5).long(),3.,1.)
        ce=torch.nn.functional.cross_entropy(logits[mask,OFFSETS[h]:OFFSETS[h+1]],y[mask,h],reduction='none')
        terms.append((2 if h==1 else 1)*(ce*w).sum()/w.sum())
    return torch.stack(terms).mean()

def batches(rows,shuffle=False):
    order=list(range(len(rows)))
    if shuffle:random.shuffle(order)
    for start in range(0,len(order),256):
        part=[rows[i] for i in order[start:start+256]]
        x,side,y=collate(part)
        yield x,side,y,torch.tensor([r.get('sample_weight',1.) for r in part])

@torch.no_grad()
def score(model,rows):
    total=0.;n=0;counts=[0]*3;correct=[0]*3;trans_n=trans_ok=0
    for x,side,y,w in batches(rows):
        z=model(*x);total+=float(loss(z,side,y,x[0],torch.ones(len(y))))*len(y);n+=len(y)
        for h in range(3):
            mask=side if h<2 else ~side;pred=z[:,OFFSETS[h]:OFFSETS[h+1]].argmax(1)
            counts[h]+=int(mask.sum());correct[h]+=int(((pred==y[:,h])&mask).sum())
            if h==1:
                changed=mask&(y[:,1]!=(x[0][:,11]>.5).long());trans_n+=int(changed.sum());trans_ok+=int(((pred==y[:,1])&changed).sum())
    return dict(samples=n,weighted_loss=total/n,accuracy=[c/max(1,k) for c,k in zip(correct,counts)],
                transition_count=trans_n,transition_accuracy=trans_ok/max(1,trans_n))

def export(model,header,folder,source):
    folder.mkdir(parents=True)
    doc={k:header[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint']}
    doc.update(format='pvz-deepset-hybrid-1',feature_version=2,embedding=8,hidden=64,
               enabled_heads=[True,True,True,False],training_source=source)
    for key in ['unit','body','heads']:
        layer=getattr(model,key);doc[key]=dict(weight=layer.weight.detach().tolist(),bias=layer.bias.detach().tolist())
    (folder/'model.json').write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),'utf-8')
    torch.save(dict(state_dict=model.state_dict(),feature_header=header,spec=dict(embedding=8,hidden=64,feature_version=2)),folder/'selected.pt')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',type=Path,required=True);ap.add_argument('--stage',type=int,required=True);args=ap.parse_args()
    b=args.study;out=b/f'training-{args.stage}';assert not out.exists();out.mkdir()
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    header,train=read_data(b/f'train-{args.stage}.jsonl');vh,val=read_data(b/'validation-data.jsonl');assert header==vh
    digest=lambda r:hashlib.sha256(r['g'].numpy().tobytes()+r['own'].numpy().tobytes()+r['enemy'].numpy().tobytes()).digest()
    held={digest(r) for r in val};before=len(train);train=[r for r in train if digest(r) not in held]
    starts=[('old',b/'warm/old.json'),('compact',b/'warm/compact.json')] if args.stage==0 else [('aggregated',b/'training-0/selected/model.json')]
    epochs=35 if args.stage==0 else 25;lr=.0003 if args.stage==0 else .0002
    report=dict(stage=args.stage,train_rows=len(train),removed_overlap=before-len(train),validation_rows=len(val),candidates=[],test_used=False)
    best=float('inf');beststate=None;start=time.perf_counter()
    for name,path in starts:
        random.seed(1744);np.random.seed(1744);torch.manual_seed(1744)
        doc=json.loads(path.read_text('utf-8'))
        if args.stage==0:model=from_old(doc,header)
        else:
            model=Network(16+len(header['behaviors']))
            model.load_state_dict(torch.load(path.with_name('selected.pt'),weights_only=True)['state_dict'])
        opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=.0001)
        initial=score(model,val);local=initial['weighted_loss'];state=copy.deepcopy(model.state_dict());stale=0;history=[]
        for epoch in range(epochs):
            model.train()
            for x,side,y,w in batches(train,True):
                opt.zero_grad(set_to_none=True);v=loss(model(*x),side,y,x[0],w);v.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
            model.eval();s=score(model,val);history.append(dict(epoch=epoch+1,**s))
            if s['weighted_loss']<local:local=s['weighted_loss'];state=copy.deepcopy(model.state_dict());stale=0
            else:stale+=1
            if epoch%5==0:print(json.dumps(dict(stage=args.stage,start=name,epoch=epoch+1,**s)),flush=True)
            if stale>=8:break
        model.load_state_dict(state);export(model,header,out/name,dict(start=str(path),stage=args.stage))
        report['candidates'].append(dict(name=name,initial=initial,history=history,selected_validation=score(model,val)))
        if local<best:best=local;beststate=state;selected=name
    model.load_state_dict(beststate);export(model,header,out/'selected',dict(selected=selected,stage=args.stage))
    report.update(selected=selected,selected_validation=score(model,val),wall_seconds=time.perf_counter()-start)
    (out/'report.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report['selected_validation']),flush=True)

if __name__=='__main__':main()
