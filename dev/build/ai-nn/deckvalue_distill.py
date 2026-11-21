"""Distil the value-search drafter into a fast pick/ban scorer (2026-11-21).

collect: one seat drafts with the searcher, the other with a mixed fast opponent (value prior at two noise levels,
         or the v2 head sampled); every searched decision stores the public state, the native legal set and the
         searcher's score for each candidate.  The drafted matchup is also played once (regular time, r22 vs r22)
         and appended to the value corpus under ids >= 10,000,000.
fit:     listwise distillation - softmax over candidates toward the searcher's scores, plus a centred regression.
Usage:   python deckvalue_distill.py collect LANES [UNTIL_EPOCH]   |   python deckvalue_distill.py fit
"""
import os,sys,json,time,zlib,sqlite3,tempfile,random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import numpy as np
import torch
from torch import nn
import deckvalue_search as ds
import deckvalue_model as dm
from ranked_draft import Room,DraftNet,SIDES,read,write

RUN=ds.RUN
SEED0=47000000
ID0=10_000_000
STAGES=['opening_ban','opening_pick','second_ban','final_pick']

def opponent(j,prior,head):
    r=random.Random(SEED0+j*13).random()
    if r<.55:return ('prior',prior,.04),'prior-.04'
    if r<.8:return ('prior',prior,.2),'prior-.2'
    return ('head',head,False),'head-warm'

def collect_one(j,value,prior,head_path):
    from deckvalue_corpus import fight_once,outcome,label
    seat=SIDES[j%2];foe=SIDES[1-j%2];seed=SEED0+j
    room=Room();searcher=ds.Searcher(value,prior)
    try:
        head=DraftNet(room.catalog).load(head_path)
        opp,name=opponent(j,prior,head)
        t=time.time();sc,notes=ds.run_draft(room,seed,{seat:('search',searcher),foe:opp});secs=time.time()-t
    finally:room.close();searcher.close()
    game=dict(i=ID0+j,seed=seed,policy={seat:'search',foe:name},decks=sc['decks'],bans=sc['bans'],
              history=[[h['side'],h['kind'],h['card']] for h in sc['draft_history']],terrain=sc['terrain_hash'])
    if sc['battle_error']:game['unstartable']=sc['battle_error']
    else:
        (RUN/'scratch').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='d',dir=RUN/'scratch') as tmp:
            r=fight_once(sc,Path(tmp)/'a')
        game['result']={k:r[k] for k in ('winner','timeout','seconds','hp')}
        game['deploys']={s:len(r['actions'][s]) for s in SIDES};game['troops']=0
        game['y']=label(r);game['outcome']=outcome(r)
    return dict(j=j,seat=seat,opponent=name,search_seconds=secs,notes=notes),game

def compress(o):return zlib.compress(json.dumps(o,ensure_ascii=False,separators=(',',':')).encode(),6)

def collect(lanes=8,until=None):
    value=ds.Value();prior=ds.corpus_prior(value);head=RUN/'draft-head.npz'
    db=sqlite3.connect(RUN/'distill.sqlite',timeout=60);db.execute('pragma journal_mode=wal')
    db.execute('create table if not exists drafts(id integer primary key,data blob not null)');db.commit()
    corpus=sqlite3.connect(RUN/'corpus.sqlite',timeout=120)
    done={r[0] for r in db.execute('select id from drafts')};nxt=0;pending={}
    with ThreadPoolExecutor(lanes) as pool:
        while not (RUN/'STOP_DISTILL').exists() and (until is None or time.time()<until):
            while len(pending)<lanes:
                while nxt in done:nxt+=1
                pending[pool.submit(collect_one,nxt,value,prior,head)]=nxt;nxt+=1
            fin,_=wait(pending,timeout=30,return_when=FIRST_COMPLETED)
            for f in fin:
                j=pending.pop(f)
                try:rec,game=f.result()
                except Exception as e:rec,game=dict(j=j,error=repr(e)[:400]),None
                with db:db.execute('insert or replace into drafts values(?,?)',(j,compress(rec)))
                if game:
                    with corpus:corpus.execute('insert or replace into games values(?,?)',(game['i'],compress(game)))
            n=db.execute('select count(*) from drafts').fetchone()[0]
            write(RUN/'distill-status.json',dict(drafts=n,updated=time.strftime('%Y-%m-%dT%H:%M:%S')))
        for f in pending:f.cancel()

# ---------------- distilled scorer ----------------
class Fast(nn.Module):
    def __init__(self,vocab,dim=24,hidden=96):
        super().__init__()
        n=len(vocab.keys);self.register_buffer('fixed',torch.cat([vocab.fixed,torch.zeros(1,30)]))
        self.embed=nn.Parameter(torch.randn(n+1,dim)*.1)        # last row = "no secret ban"
        self.card=nn.Sequential(nn.Linear(dim+30,hidden),nn.GELU(),nn.Linear(hidden,hidden))
        self.ctx=nn.Sequential(nn.Linear(4*hidden+11,hidden),nn.GELU())
        self.score=nn.Sequential(nn.Linear(2*hidden,hidden),nn.GELU(),nn.Linear(hidden,1))
    def cards(self):return self.card(torch.cat([self.embed,self.fixed],1))
    def forward(self,batch):
        C=self.cards();out=[]
        for b in batch:
            parts=[C[i].sum(0) if len(i) else torch.zeros(C.shape[1]) for i in b['sets']]
            ctx=self.ctx(torch.cat([*parts,b['flags']]))
            cand=C[b['cand']]
            out.append(self.score(torch.cat([ctx.expand(len(cand),-1),cand],1)).squeeze(1))
        return out

class Encoder:
    def __init__(self,vocab):self.v=vocab;self.none=len(vocab.keys)
    def idx(self,k):return self.none if k is None else self.v.index[k]
    def encode(self,side,stage,kind,decks,bans,offers):
        foe=SIDES[1-SIDES.index(side)]
        ban_own=[self.idx(k) for k in bans if k and self.v.side[k]==side]
        ban_foe=[self.idx(k) for k in bans if k and self.v.side[k]==foe]
        flags=torch.tensor([float(stage==t) for t in STAGES]+[float(kind=='pick'),float(kind=='ban'),float(side=='plant'),float(side=='zombie'),
                            len(decks[side])/7,len(decks[foe])/7,len(bans)/16])
        L=lambda xs:torch.tensor(xs,dtype=torch.long)
        return dict(sets=[L([self.idx(k) for k in decks[side]]),L([self.idx(k) for k in decks[foe]]),L(ban_own),L(ban_foe)],
                    flags=flags,cand=L([self.idx(k) for k in offers]))

def decisions():
    db=sqlite3.connect(RUN/'distill.sqlite',timeout=60)
    rows=[json.loads(zlib.decompress(b)) for (b,) in db.execute('select data from drafts order by id')];db.close()
    out=[]
    for r in rows:
        for n in r.get('notes',[]):
            if len(n['scores'])>1:out.append((r['j'],n))
    return out,rows

def fit(epochs=40):
    torch.manual_seed(3)
    vocab=dm.Vocab();enc=Encoder(vocab);data,rows=decisions()
    items=[]
    for j,n in data:
        cands=[c for c,_ in n['scores']];sc=torch.tensor([v for _,v in n['scores']],dtype=torch.float32)
        e=enc.encode(n['side'],n['stage'],n['kind'],n['decks'],n['bans'],cands);e['target']=sc;e['j']=j;items.append(e)
    val=[e for e in items if e['j']%10==0];tr=[e for e in items if e['j']%10!=0]
    net=Fast(vocab);opt=torch.optim.AdamW(net.parameters(),lr=2e-3,weight_decay=1e-3)
    def loss_of(batch):
        outs=net(batch);L=0
        for o,b in zip(outs,batch):
            t=b['target'];p=torch.softmax((t-t.max())/.03,0)
            L=L-(p*torch.log_softmax(o,0)).sum()+((o-o.mean())-(t-t.mean())).pow(2).mean()*5
        return L/len(batch)
    @torch.no_grad()
    def metrics(batch):
        net.eval();outs=net(batch);net.train()
        agree=regret=0
        for o,b in zip(outs,batch):
            t=b['target'];k=int(o.argmax());agree+=int(k==int(t.argmax()));regret+=float(t.max()-t[k])
        return dict(top1=agree/max(1,len(batch)),regret=regret/max(1,len(batch)),n=len(batch))
    best=(1e9,None,None,-1)
    for ep in range(epochs):
        random.Random(ep).shuffle(tr)
        for b in range(0,len(tr),64):
            L=loss_of(tr[b:b+64]);opt.zero_grad();L.backward();opt.step()
        m=metrics(val)
        if m['regret']<best[0]:best=(m['regret'],{k:v.clone() for k,v in net.state_dict().items()},m,ep)
    net.load_state_dict(best[1])
    rep=dict(drafts=len(rows),decisions=len(items),train=len(tr),validation=len(val),best_epoch=best[3],
             validation_metrics=best[2],train_metrics=metrics(tr[:2000]))
    # Reference: the value-prior drafter on the same validation decisions.
    pr=read(RUN/'prior.json')['prior'];agree=regret=0
    for j,n in data:
        if j%10:continue
        sc=dict((c,v) for c,v in n['scores']);k=max(sc,key=lambda c:pr.get(c,0.) if c else -.5)
        agree+=int(sc[k]==max(sc.values()));regret+=max(sc.values())-sc[k]
    rep['prior_validation']=dict(top1=agree/max(1,len(val)),regret=regret/max(1,len(val)))
    torch.save(dict(state=net.state_dict(),keys=vocab.keys,report=rep),RUN/'models/distill-latest.pt')
    (RUN/'models/distill-report.json').write_text(json.dumps(rep,ensure_ascii=False,indent=1),'utf8')
    print(json.dumps(rep,ensure_ascii=False,indent=1))

class FastDrafter:
    """Greedy distilled drafter for run_draft (policy ('distill', FastDrafter()))."""
    def __init__(self,path=None):
        self.vocab=dm.Vocab();self.enc=Encoder(self.vocab)
        d=torch.load(path or RUN/'models/distill-latest.pt',weights_only=False);assert d['keys']==self.vocab.keys
        self.net=Fast(self.vocab);self.net.load_state_dict(d['state']);self.net.eval()
    @torch.no_grad()
    def choose(self,side,a,state,offers):
        if len(offers)==1:return offers[0]
        e=self.enc.encode(side,a['stage'],a['kind'],state['decks'],state['bans'],offers)
        return offers[int(self.net([e])[0].argmax())]

if __name__=='__main__':
    if sys.argv[1]=='collect':collect(int(sys.argv[2]),float(sys.argv[3]) if len(sys.argv)>3 else None)
    elif sys.argv[1]=='fit':fit()
