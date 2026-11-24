"""Value-search drafter and its blind test.

At each own decision the searcher takes the native legal set, keeps the top-M candidates by a value-derived card
prior (plus every candidate for small sets), and for each candidate plays K rollouts of the rest of the draft in a
second native Room (both seats follow the value prior with Gumbel noise; common random numbers across candidates).
Final decks are scored by the value-net ensemble; the candidate with the best mean for its seat is played.
Legality is always native: rollouts ask the Room for the first legal key in prior order.

Blind test (paired, fresh seeds): the tested seat drafts with (a) the v2 draft head, greedy, or (b) the searcher;
the opposing seat samples the v2 head (noise .55) with per-step common random numbers, so both arms face the same
opponent policy draw.  Both decks are then played r22 vs r22 (1200 s continuation on timeout).
"""
import os,sys,json,time,random,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np

H=Path(__file__).resolve().parent
RUN=Path(os.environ['DV_RUN']) if os.environ.get('DV_RUN') else H.parents[1]/'test_results/ai-nn-home-options-20261118/deck-value-20261120'
os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
import torch
from ranked_draft import Room,DraftNet,SIDES,HOME,environment,check_game,read,write
import deckvalue_model as dm

def keys_for(cards,a):
    target=a.get('target',a['category'])
    return [k for k,c in cards.items() if c['side']==target and ((a['category']=='secret')==(c['category']=='secret') or a['kind']=='pick')]

class Value:
    def __init__(self,path=None):
        self.nets,self.vocab=dm.load(path)
        self.cache={}
    def __call__(self,deck_list):
        """deck_list -> plant-seat score in [-1,1]: P(plant true win) - P(zombie true win) (ensemble mean).
        A regular-time stall scores 0 for both seats, so neither seat's search is drawn toward slow matchups."""
        out=np.empty(len(deck_list));todo=[]
        for j,d in enumerate(deck_list):
            key=(tuple(sorted(d['plant'])),tuple(sorted(d['zombie'])))
            if key in self.cache:out[j]=self.cache[key]
            else:todo.append((j,key,d))
        if todo:
            X=torch.stack([self.vocab.multihot(d) for _,_,d in todo])
            q=dm.predict(self.nets,X).mean(0).numpy();p=q[:,0]-q[:,2]
            for (j,key,_),v in zip(todo,p):self.cache[key]=out[j]=v
        return out
    def card_prior(self,decks_sample):
        """Mean value change from swapping each card into sampled real decks (seat-relative: + is good for its owner)."""
        prior={}
        rng=random.Random(5)
        for k in self.vocab.keys:
            s=self.vocab.side[k];batch=[];base=[]
            for d in rng.sample(decks_sample,min(48,len(decks_sample))):
                if k in d[s]:continue
                new={**d,s:[*d[s][1:],k] if d[s] else [k]}
                j=rng.randrange(len(d[s]));new[s]=[*d[s][:j],*d[s][j+1:],k]
                batch.append(new);base.append(d)
            if not batch:prior[k]=0.;continue
            delta=(self(batch)-self(base)).mean()
            prior[k]=float(delta if s=='plant' else -delta)
        return prior

class Replay:
    """Second native Room that replays a prefix and finishes the draft with a prior-ordered policy."""
    def __init__(self,ban_targets=None):
        self.room=Room();self.cards=self.room.catalog['cards'];self.ban_targets=ban_targets
    def close(self):self.room.close()
    def rollout(self,seed,prefix,prior,rng,temp=.04):
        st=self.room.request(op='start',seed=seed,map=HOME,night=False,weather='clear')
        for k in prefix:st=self.room.request(op='act',key=k)
        while st['action'] is not None:
            a=st['action'];keys=keys_for(self.cards,a)
            # Picks favour own valuable cards; bans remove the opponent's valuable cards (prior is owner-relative).
            keys.sort(key=lambda k:-(prior.get(k,0.)+temp*rng.gumbel()))
            if self.ban_targets and a['kind']=='ban':
                preferred=[k for k in self.ban_targets(a) if k in keys]
                keys=preferred+[k for k in keys if k not in preferred]
            legal=self.room.request(op='legal',keys=keys,count=1)
            if not legal and a['kind']=='ban':legal=[None]
            if not legal:return None
            st=self.room.request(op='act',key=legal[0])
        if st.get('battle_error'):return None
        return st['decks']

class Searcher:
    def __init__(self,value,prior,M=24,K=3,explore=0,ban_targets=None):
        self.value=value;self.prior=prior;self.M=M;self.K=K
        self.explore=explore;self.replay=Replay(ban_targets)
    def close(self):self.replay.close()
    def choose(self,seed,prefix,side,offers):
        if len(offers)==1:return offers[0],{}
        ordered=sorted(offers,key=lambda k:-(self.prior.get(k,0.) if k else -1e9))
        cand=ordered[:self.M]
        if self.explore and len(ordered)>self.M:
            cand=cand[:-self.explore]+random.Random(seed*97+len(prefix)).sample(
                ordered[self.M:],min(self.explore,len(ordered)-self.M))
        if None in offers and None not in cand:cand.append(None)
        decks=[];owner=[]
        for c in cand:
            for r in range(self.K):
                rng=np.random.default_rng([seed,len(prefix),r,991])   # common random numbers across candidates
                d=self.replay.rollout(seed,[*prefix,c],self.prior,rng)
                decks.append(d);owner.append(c)
        vals=np.full(len(decks),np.nan)
        ok=[j for j,d in enumerate(decks) if d]
        if ok:vals[ok]=self.value([decks[j] for j in ok])
        score={}
        for c in cand:
            v=np.array([vals[j] for j in range(len(decks)) if owner[j]==c])
            v=np.where(np.isnan(v),-1. if side=='plant' else 1.,v)       # an unstartable finish counts as a loss for the chooser
            score[c]=float(v.mean() if side=='plant' else -v.mean())
        best=max(cand,key=lambda c:score[c])
        return best,score

def head_choice(net,state,env,offers,seed,step,greedy,scale=.55):
    feat=net.features(state,env,offers);s=net.predict(feat)
    if not greedy:
        rng=np.random.default_rng([seed,step,7129])
        s=s+scale*rng.gumbel(size=len(offers))
    return offers[int(np.argmax(s))]

def run_draft(room,seed,policies):
    """policies[side] = ('head',net,greedy) | ('search',Searcher)."""
    state=room.request(op='start',seed=seed,map=HOME,night=False,weather='clear')
    terrain=state.pop('terrain');env=environment(terrain);prefix=[];notes=[]
    cards=room.catalog['cards']
    while state['action'] is not None:
        a=state['action'];side=a['side'];step=state['step']
        keys=keys_for(cards,a)
        if a['category']=='secret':keys=[*keys,None]
        offers=room.request(op='legal',keys=keys,count=1000)
        if not offers and a['kind']=='ban':offers=[None]
        pol=policies[side]
        if pol[0]=='head':k=head_choice(pol[1],state,env,offers,seed,step,pol[2])
        elif pol[0]=='distill':k=pol[1].choose(side,a,state,offers)
        elif pol[0]=='prior':
            # Fast drafter: value-derived card prior (owner-relative) plus small Gumbel noise, no search.
            rng=np.random.default_rng([seed,step,4417])
            k=max(offers,key=lambda c:(pol[1].get(c,0.) if c else -.5)+pol[2]*rng.gumbel())
        else:
            k,score=pol[1].choose(seed,prefix,side,offers)
            notes.append(dict(step=step,kind=a['kind'],chosen=k,legal=len(offers),top=sorted(score.items(),key=lambda x:-x[1])[:3],
                              side=side,stage=a['stage'],category=a['category'],decks=state['decks'],bans=state['bans'],
                              offers=offers,scores=[[c,v] for c,v in score.items()]))
        prefix.append(k);state=room.request(op='act',key=k)
    sc=dict(map=HOME,seed=seed,night=False,weather='clear',rules=state['rules'],decks=state['decks'],bans=state['bans'],
            draft_history=state['history'],terrain_hash=terrain['terrain_hash'],battle_error=state.get('battle_error'))
    return check_game(sc),notes

def corpus_prior(value):
    from deckvalue_corpus import load_rows
    rows=[r for r in load_rows() if 'y' in r]
    return value.card_prior([r['decks'] for r in rows])

BLIND0=49000000

def save_prior():
    value=Value();prior=corpus_prior(value)
    write(RUN/'prior.json',dict(model=sha_of(RUN/'models/value-latest.pt'),prior=prior));return prior

def sha_of(p):
    import hashlib;return hashlib.sha256(Path(p).read_bytes()).hexdigest()

CROSS0=49300000

def cross_case(j,value,prior,head_path,out,base=CROSS0):
    """Tested seat: head (greedy) vs searcher; opposing seat: the fast prior drafter (a competent opponent)."""
    from ranked_draft_train import fight
    seat=SIDES[j%2];foe=SIDES[1-j%2];seed=base+j
    path=out/f'{j:04d}.json'
    if path.exists():return read(path)
    room=Room();searcher=Searcher(value,prior)
    try:
        head=DraftNet(room.catalog).load(head_path)
        t=time.time()
        a,_=run_draft(room,seed,{seat:('head',head,True),foe:('prior',prior,.04)})
        b,notes=run_draft(room,seed,{seat:('search',searcher),foe:('prior',prior,.04)})
        c,_=run_draft(room,seed,{seat:('prior',prior,.04),foe:('prior',prior,.04)})
        search_seconds=time.time()-t
    finally:room.close();searcher.close()
    rec=dict(j=j,seat=seat,seed=seed,arms_policy=['head','search','prior'],decks=[a['decks'],b['decks'],c['decks']],
             predicted=[float(value([x['decks']])[0]) for x in (a,b,c)],notes=notes,search_seconds=search_seconds,
             errors=[a['battle_error'],b['battle_error'],c['battle_error']])
    if not any(rec['errors']):
        keep=lambda r:{k:r[k] for k in ('winner','timeout','seconds','hp','extension') if k in r}|{
            'deploys':{s:len(r['actions'][s]) for s in SIDES},'actions':r['actions']}
        arms=[];seen={}
        with tempfile.TemporaryDirectory(prefix='x',dir=RUN/'scratch') as tmp:
            for n,sc in enumerate((a,b,c)):
                key=json.dumps(sc['decks'],sort_keys=True,ensure_ascii=False)
                if key not in seen:seen[key]=keep(fight(sc,j,Path(tmp)/f'a{n}',('r22','r22')))
                arms.append(seen[key])
        rec['arms']=arms
    write(path,rec);return rec

def cross(n=96,lanes=6,tag='cross-1',base=CROSS0,head_path=None):
    out=RUN/tag;out.mkdir(exist_ok=True);(RUN/'scratch').mkdir(exist_ok=True)
    value=Value();prior=corpus_prior(value)
    head_path=Path(head_path or RUN/'draft-head.npz')
    write(out/'setup.json',dict(n=n,seed_base=base,value=sha_of(RUN/'models/value-latest.pt'),head=str(head_path),
          value_report=torch.load(RUN/'models/value-latest.pt',weights_only=False)['report'],opponent='prior drafter, noise .04'))
    with ThreadPoolExecutor(lanes) as pool:
        recs=list(pool.map(lambda j:cross_case(j,value,prior,head_path,out,base),range(n)))
    write(out/'summary.json',summarize(recs,3));return recs

def blind_case(j,value,prior,head_path,out,base=BLIND0):
    from ranked_draft_train import fight
    seat=SIDES[j%2];foe=SIDES[1-j%2];seed=base+j
    path=out/f'{j:04d}.json'
    if path.exists():return read(path)
    room=Room();searcher=Searcher(value,prior)
    try:
        head=DraftNet(room.catalog).load(head_path)
        t=time.time()
        a,_=run_draft(room,seed,{seat:('head',head,True),foe:('head',head,False)})
        b,notes=run_draft(room,seed,{seat:('search',searcher),foe:('head',head,False)})
        search_seconds=time.time()-t
    finally:room.close();searcher.close()
    rec=dict(j=j,seat=seat,seed=seed,decks=[a['decks'],b['decks']],predicted=[float(value([a['decks']])[0]),float(value([b['decks']])[0])],
             notes=notes,search_seconds=search_seconds,errors=[a['battle_error'],b['battle_error']])
    if not any(rec['errors']):
        with tempfile.TemporaryDirectory(prefix='b',dir=RUN/'scratch') as tmp:
            x=fight(a,j,Path(tmp)/'a',('r22','r22'))
            y=x if a['decks']==b['decks'] else fight(b,j,Path(tmp)/'b',('r22','r22'))
        keep=lambda r:{k:r[k] for k in ('winner','timeout','seconds','hp','extension') if k in r}|{
            'deploys':{s:len(r['actions'][s]) for s in SIDES},'actions':r['actions']}
        rec['arms']=[keep(x),keep(y)]
    write(path,rec);return rec

def blind(n=96,lanes=6,tag='blind-1',head_path=None,base=BLIND0):
    out=RUN/tag;out.mkdir(exist_ok=True);(RUN/'scratch').mkdir(exist_ok=True)
    value=Value();prior=corpus_prior(value)
    head_path=Path(head_path or RUN/'draft-head.npz')
    write(out/'setup.json',dict(n=n,value=str(dm.RUN/'models/value-latest.pt'),value_report=torch.load(dm.RUN/'models/value-latest.pt',weights_only=False)['report'],
          head=str(head_path),seed_base=base,prior_top={s:sorted([(k,v) for k,v in prior.items() if value.vocab.side[k]==s],key=lambda x:-x[1])[:12] for s in SIDES}))
    with ThreadPoolExecutor(lanes) as pool:
        recs=list(pool.map(lambda j:blind_case(j,value,prior,head_path,out,base),range(n)))
    write(out/'summary.json',summarize(recs));return recs

def summarize(recs,arms=2):
    def label(r,side):
        if r['timeout']:
            e=r.get('extension') or {}
            return 'T' if e.get('timeout') or e.get('winner') in (None,'draw') else ('t' if e['winner']==side else 'l')   # t/l: decided in continuation
        return 'W' if r['winner']==side else 'L' if r['winner'] not in (None,'draw') else 'T'
    out={}
    for side in SIDES:
        rs=[r for r in recs if r['seat']==side and 'arms' in r]
        from collections import Counter
        trans=Counter(label(r['arms'][0],side)+'>'+label(r['arms'][1],side) for r in rs)
        wins=[sum(label(r['arms'][k],side)=='W' for r in rs) for k in range(arms)]
        same=sum(r['decks'][0]==r['decks'][1] for r in rs)
        secs=[float(np.mean([r['arms'][k]['seconds'] for r in rs])) if rs else 0 for k in range(arms)]
        pred=[float(np.mean([r['predicted'][k] for r in rs])) if rs else 0 for k in range(arms)]
        if arms==3:
            trans['head>prior']=dict(Counter(label(r['arms'][0],side)+'>'+label(r['arms'][2],side) for r in rs))
        out[side]=dict(cases=len(rs),true_wins_head_vs_search=wins,transitions=dict(trans),same_decks=same,mean_seconds=secs,
                       predicted_plant_p=pred,errors=sum(any(r['errors']) for r in recs if r['seat']==side))
    return out

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='blind':blind(int(sys.argv[2]),int(sys.argv[3]),sys.argv[4] if len(sys.argv)>4 else 'blind-1')
    elif cmd=='cross':cross(int(sys.argv[2]),int(sys.argv[3]),sys.argv[4],int(sys.argv[5]))
    elif cmd=='save-prior':save_prior()
    elif cmd=='probe':
        value=Value();prior=corpus_prior(value)
        for s in SIDES:print(s,sorted([(k,round(v,3)) for k,v in prior.items() if value.vocab.side[k]==s],key=lambda x:-x[1])[:15])
        room=Room();se=Searcher(value,prior)
        head=DraftNet(room.catalog).load(RUN/'draft-head.npz')
        t=time.time();sc,notes=run_draft(room,BLIND0+999,{'plant':('search',se),'zombie':('head',head,False)})
        print('search draft s',round(time.time()-t,1),sc['decks'],value([sc['decks']]))
        room.close();se.close()
