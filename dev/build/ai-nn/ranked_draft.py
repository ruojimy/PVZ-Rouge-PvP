"""Two-seat draft policies. Production Room supplies the schedule and legality of every action."""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
import subprocess

import numpy as np

from league_data import R, ROOT, EXPORT, read, write

HOME = '家院'
PROFILE = read(Path(os.environ['PVZ_RANKED_PROFILE'])) if os.environ.get('PVZ_RANKED_PROFILE') else {}
RUN = Path(PROFILE['output']) if PROFILE else ROOT / 'ranked-seven-20261119'
BATTLE = RUN / 'battle'
DRAFT = RUN / 'draft'
NATIVE = Path(PROFILE.get('native_dir',RUN/'native'))
ROOM = NATIVE/'ranked_draft_room.exe' if PROFILE else R / 'build/pvp73-tools/build/Release/ranked_draft_room.exe'
DATA_ROOT = Path(PROFILE['data_root']) if PROFILE else R
SIDES = ('plant', 'zombie')
RULES = {'ranked': True, 'extra_slot': False, 'plant_slots': 7, 'zombie_slots': 7}
STAGES = ['opening_ban', 'opening_pick', 'second_ban', 'final_pick']

def stable(text):
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], 'little')

class Room:
    def __init__(self):
        env = {**os.environ, 'PATH': str(EXPORT) + os.pathsep + os.environ['PATH']}
        self.p = subprocess.Popen([ROOM], cwd=DATA_ROOT, stdin=-1, stdout=-1, stderr=subprocess.DEVNULL,
                                  creationflags=0x08000000, env=env)
        self.catalog = self.request(op='catalog')

    def request(self, **message):
        self.p.stdin.write(json.dumps(message, ensure_ascii=False).encode() + b'\n')
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError(f'native draft process exited ({self.p.poll()})')
        response = json.loads(line)
        if isinstance(response, dict) and 'error' in response:
            raise RuntimeError(response['error'])
        return response

    def close(self):
        self.p.stdin.close()
        try:self.p.wait(8)
        finally:
            if self.p.poll() is None:self.p.kill()
            self.p.stdout.close()

def check_game(sc):
    if PROFILE.get('day_league'):
        assert sc['map']==HOME and sc['night'] is False and sc['weather']=='clear'
    assert all(sc['rules'][k] == v for k,v in RULES.items())
    if PROFILE:assert sc['rules']['build']==PROFILE['version']
    hist=sc['draft_history']
    assert hist and [h['step'] for h in hist] == list(range(1,len(hist)+1))
    assert set(h['stage'] for h in hist)==set(STAGES)
    for s in SIDES:
        assert [h['card'] for h in hist if h['side']==s and h['kind']=='pick']==sc['decks'][s]
        assert len(set(sc['decks'][s]))==7
    assert [h['card'] for h in hist if h['kind']=='ban' and h['card'] is not None]==sc['bans']
    return sc

def environment(terrain):
    cells=[x for row in terrain['tiles'] for x in row]
    counts=Counter(x['kind'] for x in cells)
    e=np.zeros(21)
    for k,v in counts.items():e[stable(k)%12]+=v/len(cells)
    e[12]=sum(bool(x.get('water')) for x in cells)/len(cells)
    e[13]=sum(bool(x.get('solid')) for x in cells)/len(cells)
    e[14]=bool(terrain['environment'].get('night'))
    e[15]=terrain['environment'].get('waterline_row',0)/max(1,terrain['rows'])
    for i,s in enumerate(SIDES):
        e[16+i*2]=terrain['spawns'][s]['x']/terrain['width']
        e[17+i*2]=terrain['spawns'][s]['y']/terrain['height']
    e[20]=terrain['environment'].get('weather')!='clear'
    return e

class DraftNet:
    """Public card identity, shared traits and relationships enter a context-dependent nonlinear scorer."""
    def __init__(self, catalog):
        self.cards=catalog['cards'];self.keys=[None,*sorted(self.cards)];self.index={k:i for i,k in enumerate(self.keys)}
        fields=('cost','hp','damage','interval','range','speed','cooldown','native_cost','native_hp')
        self.parents={};self.children={k:set() for k in self.keys}
        self.mentions={k:set() for k in self.keys}
        self.mentioned_by={k:set() for k in self.keys}
        enc=np.random.default_rng(21431)
        self.fixed=enc.normal(0,.26,(len(self.keys),30))
        for i,k in enumerate(self.keys):
            card=self.cards.get(k,{})
            parents=set()
            for prop in ('dependency','dependencies','prerequisites','precursors'):
                p=card.get(prop)
                parents.update(x for x in (p if isinstance(p,list) else [p]) if isinstance(x,str) and x in self.cards)
            self.parents[k]=parents
            for parent in parents:self.children[parent].add(k)
            if card.get('category')=='secret':
                desc=' '.join(str(card.get(n,'')) for n in ('description','native_description'))
                declared=set(card.get('targets') or [])
                for target,unit in self.cards.items():
                    if target in declared or (unit['category']!='secret' and unit.get('name') and unit['name'] in desc):
                        self.mentions[k].add(target)
                        self.mentioned_by[target].add(k)
            self.fixed[i,:len(fields)]=[np.log1p(max(0.,card.get(f) or 0.))/7 for f in fields]
            for name in ('family','behavior','category','effect','economy'):
                if card.get(name):self.fixed[i,10+stable(name+str(card[name]))%20]+=.8
            self.fixed[i,9]=card.get('producer',False)
        self.embed=enc.normal(0,.24,(2,len(self.keys),12))
        self.w=enc.normal(0,.13,(2,30+12+3*30+21+4+3+12,32))
        self.head=enc.normal(0,.10,(2,32))
        self.bias=np.zeros((2,len(self.keys),2))

    def save(self,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.partial')
        with tmp.open('wb') as f:np.savez_compressed(f,embed=self.embed,w=self.w,head=self.head,bias=self.bias,
                                                       keys=json.dumps(self.keys,ensure_ascii=False))
        os.replace(tmp,path)

    def load(self,path):
        with np.load(path,allow_pickle=False) as f:
            assert json.loads(str(f['keys']))==self.keys
            for k in ('embed','w','head','bias'):setattr(self,k,f[k].copy())
        return self

    def features(self,state,env,offers):
        a=state['action'];s=SIDES.index(a['side']);other=SIDES[1-s]
        own=state['decks'][a['side']];foe=state['decks'][other];banned=state['bans']
        idx=np.array([self.index[k] for k in offers])
        chosen=self.fixed[idx]
        def average(keys):
            return self.fixed[[self.index[k] for k in keys]].sum(axis=0)/(1+len(keys)) if keys else np.zeros(30)
        # Interactions expose the actual public draft prefix, including an adversary's picks.
        shared=np.concatenate([env,[float(a['stage']==t) for t in STAGES],
                               [len(own)/7,len(foe)/7,len(banned)/16]])
        related=np.array([[len(family & set(pool))/max(1,len(family))
                           for family in (self.parents[k],self.children[k],self.mentions[k],self.mentioned_by[k])
                           for pool in (own,foe,banned)] for k in offers])
        return s,int(a['kind']=='ban'),idx,np.column_stack([chosen,self.embed[s,idx],
             *(chosen*average(keys) for keys in (own,foe,banned)),np.tile(shared,(len(idx),1)),related])

    def predict(self,features):
        s,ban,idx,x=features
        h=np.tanh(x@self.w[s])
        return h@self.head[s]+self.bias[s,idx,ban]

    def prefer(self,features,win,lose,weight):
        # A same-prefix, same-seed counterfactual supplies the preference and its sign.
        s,ban,idx,x=features
        pair=np.array([win,lose]);xx=x[pair].copy()
        xx[:,30:42]=self.embed[s,idx[pair]]
        h=np.tanh(xx@self.w[s])
        delta=(h[0]-h[1])@self.head[s]+self.bias[s,idx[win],ban]-self.bias[s,idx[lose],ban]
        step=.021*weight/(1+np.exp(np.clip(delta,-12,12)))
        grad=(np.array([1.,-1.])[:,None]*self.head[s])*(1-h*h)
        self.embed[s,idx[pair]]+=step*(grad@self.w[s][30:42].T)
        self.w[s]+=step*xx.T@grad
        self.head[s]+=step*(h[0]-h[1])
        self.bias[s,idx[pair],ban]+=step*np.array([1.,-1.])

    def reinforce(self,features,pick,advantage):
        s,ban,idx,x=features
        if len(idx)<2:return
        x=x.copy();x[:,30:42]=self.embed[s,idx]
        h=np.tanh(x@self.w[s])
        scores=(h@self.head[s]+self.bias[s,idx,ban])/.55
        prob=np.exp(scores-scores.max());prob/=prob.sum()
        direction=-prob;direction[pick]+=1.
        step=.0018*advantage/.55
        grad=(direction[:,None]*self.head[s])*(1-h*h)
        self.embed[s,idx]+=step*(grad@self.w[s][30:42].T)
        self.w[s]+=step*x.T@grad
        self.head[s]+=step*direction@h
        self.bias[s,idx,ban]+=step*direction

def draft(room,nets,seed,map_name=HOME,night=False,fork=None,greedy=False,weather='clear',width=14,combat_template=None,
          diagnostic_action=None,greedy_after=None,greedy_sides=None,noise_scale=.55):
    state=room.request(op='start',seed=seed,map=map_name,night=night,weather=weather)
    terrain=state.pop('terrain');env=environment(terrain);decisions=[]
    if PROFILE.get('day_league'):
        assert map_name==HOME and not night and weather=='clear' and not terrain['environment'].get('night')
    while state['action'] is not None:
        a=state['action'];step=state['step'];side=a['side'];net=nets[side]
        # Common randomness per step also holds the continuation policy fixed across forks.
        rng=np.random.default_rng([seed,step,7129])
        target=a.get('target',a['category'])
        keys=[k for k,c in net.cards.items() if c['side']==target and
              ((a['category']=='secret')==(c['category']=='secret') or a['kind']=='pick')]
        keys=[keys[i] for i in rng.permutation(len(keys))]
        if a['category']=='secret':keys.insert(int(rng.integers(0,min(width,len(keys))+1)),None)
        offers=room.request(op='legal',keys=keys,count=width)
        if not offers and a['kind']=='ban':offers=room.request(op='legal',keys=[None],count=1)
        if not offers:raise RuntimeError(f'no legal action at {a}, {state["decks"]}')
        feat=net.features(state,env,offers);scores=net.predict(feat)
        if combat_template and a['kind']=='pick':
            # Combat curriculum only. Every preferred card still has to pass this turn's native mask.
            scores=scores+np.array([3. if k in combat_template[side] else 0. for k in offers])
        noise=np.array([rng.gumbel() for _ in keys])
        jitter=dict(zip(keys,noise))
        deterministic=greedy or (greedy_after is not None and step>=greedy_after) or bool(greedy_sides and side in greedy_sides)
        # greedy_sides (draft_v2 blind): only the tested seat is deterministic; the other seat samples from
        # the same per-step common random numbers, so each seed is a different matchup but both arms share it.
        order=np.argsort(-(scores+(0 if deterministic else noise_scale)*np.array([jitter[k] for k in offers])))
        pick=int(order[0]);alt=int(order[1]) if len(order)>1 else pick
        if fork and step==fork[0]:
            assert offers[pick]==fork[1] and fork[1]!=fork[2] and fork[2] in offers
            pick=offers.index(fork[2])
        if diagnostic_action and diagnostic_action[0]==step:
            pick=offers.index(diagnostic_action[1])
        decisions.append((side,feat,pick,alt,offers))
        state=room.request(op='act',key=offers[pick])
    sc=dict(map=map_name,seed=seed,night=night,weather=weather,rules=state['rules'],decks=state['decks'],
            bans=state['bans'],draft_history=state['history'],terrain_hash=terrain['terrain_hash'],battle_error=state.get('battle_error'))
    return check_game(sc),decisions
