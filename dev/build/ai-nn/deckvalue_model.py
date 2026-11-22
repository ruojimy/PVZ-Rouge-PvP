"""Matchup value network: P(plant wins | plant deck, zombie deck), daytime home, r22 on both seats.

Cards enter as a learned embedding plus the catalog descriptor vector DraftNet already derives from public card
fields (cost, hp, damage, producer flag, family/category hashes, ...).  No card-specific rule is written here.
Each deck is a set (DeepSets: per-card MLP, summed, then a deck MLP); the head sees both deck vectors and their
elementwise product so it can learn counters.  A small ensemble gives the search an uncertainty estimate.

Usage:  python deckvalue_model.py fit      (reads corpus.sqlite, writes models/value-*.pt and report)
"""
import json,os,sys,time,math
from pathlib import Path
import numpy as np
import torch
from torch import nn

H=Path(__file__).resolve().parent
RUN=Path(os.environ['DV_RUN']) if os.environ.get('DV_RUN') else H.parents[1]/'test_results/ai-nn-home-options-20261118/deck-value-20261120'
SIDES=('plant','zombie')
torch.set_num_threads(int(os.environ.get('DV_THREADS','6')))

def catalog():
    p=RUN/'catalog.json'
    if not p.exists():
        os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
        from ranked_draft import Room
        room=Room()
        try:cat=room.catalog
        finally:room.close()
        p.write_text(json.dumps(cat,ensure_ascii=False),'utf8')
    return json.loads(p.read_text('utf8'))

class Vocab:
    def __init__(self):
        os.environ.setdefault('PVZ_RANKED_PROFILE',str(RUN/'profile.json'))
        from ranked_draft import DraftNet
        cat=catalog();net=DraftNet(cat)
        self.keys=net.keys[1:];self.index={k:i for i,k in enumerate(self.keys)}
        self.side={k:cat['cards'][k]['side'] for k in self.keys}
        self.fixed=torch.tensor(net.fixed[1:],dtype=torch.float32)
    def multihot(self,decks):
        x=torch.zeros(2,len(self.keys))
        for j,s in enumerate(SIDES):
            for k in decks[s]:x[j,self.index[k]]=1.
        return x

class ValueNet(nn.Module):
    def __init__(self,vocab,dim=24,hidden=64):
        super().__init__()
        n=len(vocab.keys);self.register_buffer('fixed',vocab.fixed)
        self.embed=nn.Parameter(torch.randn(n,dim)*.1)
        self.card=nn.ModuleList([nn.Sequential(nn.Linear(dim+30,hidden),nn.GELU(),nn.Linear(hidden,hidden)) for _ in SIDES])
        self.deck=nn.ModuleList([nn.Sequential(nn.GELU(),nn.Linear(hidden,hidden),nn.GELU()) for _ in SIDES])
        self.head=nn.Sequential(nn.Linear(3*hidden,hidden),nn.GELU(),nn.Dropout(.1),nn.Linear(hidden,4))
    def deck_vectors(self,x):                       # x: (B,2,n) multi-hot
        c=torch.cat([self.embed,self.fixed],1)
        return [self.deck[j](x[:,j]@self.card[j](c)) for j in range(2)]
    def forward(self,x):
        p,z=self.deck_vectors(x)
        out=self.head(torch.cat([p,z,p*z],1))
        return out[:,:3],torch.tanh(out[:,3])       # logits [plant true win, timeout, zombie true win], hero-damage margin

def dataset(rows,vocab):
    keep=[r for r in rows if 'y' in r]
    def cls(r):
        res=r['result']
        if res['timeout'] or res['winner'] in (None,'draw'):return 1
        return 0 if res['winner']=='plant' else 2
    X=torch.stack([vocab.multihot(r['decks']) for r in keep])
    y=torch.tensor([cls(r) for r in keep],dtype=torch.long)
    def margin(r):
        hp=r['result'].get('hp') or {'plant':40,'zombie':40}     # regular-time hero HP
        return ((40-hp['zombie'])-(40-hp['plant']))/40
    m=torch.tensor([margin(r) for r in keep],dtype=torch.float32)
    ids=np.array([r['i'] for r in keep])
    return keep,X,y,m,ids

def train_one(X,y,m,seed,epochs=60,vocab=None,Xv=None,yv=None):
    torch.manual_seed(seed)
    net=ValueNet(vocab);opt=torch.optim.AdamW(net.parameters(),lr=3e-3,weight_decay=1e-3)
    n=len(y);ce=nn.CrossEntropyLoss()
    best=(1e9,None)
    for ep in range(epochs):
        net.train();perm=torch.randperm(n)
        for b in range(0,n,256):
            idx=perm[b:b+256];logit,mar=net(X[idx])
            loss=ce(logit,y[idx])+.3*((mar-m[idx])**2).mean()
            opt.zero_grad();loss.backward();opt.step()
        if Xv is not None and (ep%5==4 or ep==epochs-1):
            v=evaluate([net],Xv,yv)['logloss']
            if v<best[0]:best=(v,{k:t.clone() for k,t in net.state_dict().items()})
    if best[1] is not None:net.load_state_dict(best[1])
    return net

@torch.no_grad()
def predict(nets,X):
    for n in nets:n.eval()
    return torch.stack([torch.softmax(n(X)[0],-1) for n in nets])   # (E,B,3)

def evaluate(nets,X,y):
    p=predict(nets,X).mean(0).clamp(1e-5,1)
    ll=-p[torch.arange(len(y)),y].log().mean().item()
    freq=torch.bincount(y,minlength=3).float()/len(y)
    ll0=-freq.clamp(1e-5,1)[y].log().mean().item()
    def auc(score,pos):
        order=score.argsort();yy=pos[order].float();P=yy.sum().item();N=len(yy)-P
        ranks=torch.arange(1,len(yy)+1,dtype=torch.float32)
        return ((ranks*yy).sum().item()-P*(P+1)/2)/max(1,P*N)
    return dict(logloss=ll,base_logloss=ll0,n=len(y),class_rates=freq.tolist(),
                plant_win_auc=auc(p[:,0],y==0),zombie_win_auc=auc(p[:,2],y==2),
                plant_win_brier=((p[:,0]-(y==0).float())**2).mean().item(),mean_pred=p.mean(0).tolist())

def fit(ensemble=5,epochs=60):
    from deckvalue_corpus import load_rows
    vocab=Vocab();rows=load_rows()
    keep,X,y,m,ids=dataset(rows,vocab)
    val=torch.tensor(ids%10==0);tr=~val
    report=dict(rows=len(rows),usable=len(keep),errors=sum('error' in r for r in rows),
                unstartable=sum('unstartable' in r for r in rows),train=int(tr.sum()),validation=int(val.sum()))
    nets=[train_one(X[tr],y[tr],m[tr],s,epochs,vocab,X[val],y[val]) for s in range(ensemble)]
    report['validation_metrics']=evaluate(nets,X[val],y[val])
    # Linear multi-hot baseline (same split) tells whether the deep-set head is earning its keep.
    from sklearn.linear_model import LogisticRegression
    flat=X.reshape(len(X),-1).numpy()
    lr=LogisticRegression(C=.5,max_iter=3000).fit(flat[tr.numpy()],y[tr].numpy())
    pl=np.full((int(val.sum()),3),1e-5);pl[:,lr.classes_]=lr.predict_proba(flat[val.numpy()])
    yv=y[val].numpy();report['linear_logloss']=float(-np.log(np.clip(pl[np.arange(len(yv)),yv],1e-5,1)).mean())
    out=RUN/'models';out.mkdir(exist_ok=True)
    stamp=time.strftime('%m%d-%H%M')
    torch.save(dict(states=[n.state_dict() for n in nets],keys=vocab.keys,report=report),out/f'value-{stamp}.pt')
    torch.save(dict(states=[n.state_dict() for n in nets],keys=vocab.keys,report=report),out/'value-latest.pt')
    # Final ensemble refit on all data for the drafter.
    report['saved']=str(out/f'value-{stamp}.pt')
    (out/f'report-{stamp}.json').write_text(json.dumps(report,ensure_ascii=False,indent=1),'utf8')
    print(json.dumps(report,ensure_ascii=False,indent=1))
    return nets,vocab

def load(path=None):
    vocab=Vocab();d=torch.load(path or RUN/'models/value-latest.pt',weights_only=False)
    assert d['keys']==vocab.keys
    nets=[]
    for s in d['states']:
        n=ValueNet(vocab);n.load_state_dict(s);n.eval();nets.append(n)
    return nets,vocab

if __name__=='__main__':
    if sys.argv[1:2]==['fit']:fit(*(int(a) for a in sys.argv[2:4]))
