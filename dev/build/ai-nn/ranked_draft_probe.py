"""Prespecified fresh-state diagnostics. Tests may identify card categories. Policies never receive test labels."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import time
import numpy as np

from ranked_draft_train import DRAFT,HOME,ROOM,SIDES,Room,DraftNet,draft,fight,reward,controllers,local,read,write,sha,PROFILE

TESTS=('opening_secret','visible_parent_ban','visible_multi_target_ban','environment_tool')
TOOLS={'plant:花盆','plant:睡莲','plant:咖啡豆'}

def candidates(test,net,step,hist,offers,scores):
    a=hist[step];side=a['side'];op=SIDES[1-SIDES.index(side)]
    visible={s:{h['card'] for h in hist[:step] if h['side']==s and h['kind']=='pick'} for s in SIDES}
    best=lambda ks:max(ks,key=lambda k:scores[offers.index(k)])
    if test=='opening_secret':
        if a['stage']!='opening_pick':return None
        secrets=[k for k in offers if k and net.parents[k]-visible[side] and net.parents[k].intersection(offers)]
        if secrets:
            k=best(secrets);return k,best(net.parents[k].intersection(offers))
    if test in ('visible_parent_ban','visible_multi_target_ban'):
        if a['category']!='secret' or a['stage']!='second_ban':return None
        def related(k):
            if not k:return False
            if test=='visible_parent_ban':return bool(net.parents[k]&visible[op])
            targets=set(net.cards[k].get('targets') or [])
            return len(targets)>1 and bool(targets&visible[op])
        plus=[k for k in offers if related(k)];minus=[k for k in offers if not related(k)]
        if plus and minus:return best(plus),best(minus)
    if test=='environment_tool':
        if a['kind']!='pick' or side!='plant':return None
        plus=TOOLS.intersection(offers);minus=[k for k in offers if k not in TOOLS]
        if plus and minus:return best(plus),best(minus)
    return None

def main():
    path=DRAFT/'diagnostics.json'
    if path.exists():return
    freeze=DRAFT/'frozen.npz'
    while not freeze.exists():time.sleep(20)
    room=Room()
    try:
        first=DraftNet(room.catalog).load(DRAFT/'initial.npz');net=DraftNet(room.catalog).load(freeze)
        planned=[];attempts=[];selected={t:set() for t in TESTS}
        for i in range(48):
            arg=dict(seed=9820000+PROFILE.get('seed_offset',0)+i,map_name=HOME if i%4!=3 else room.catalog['maps'][i%len(room.catalog['maps'])],
                     night=bool(i%2),weather='rain' if i%3==1 else 'clear',greedy=True,width=256)
            if PROFILE.get('day_league'):arg.update(map_name=HOME,night=False,weather='clear')
            base,dec=draft(room,dict.fromkeys(SIDES,net),**arg)
            for test in TESTS:
                slot=('day' if not arg['night'] else 'night') if test=='environment_tool' else SIDES[i%2]
                if PROFILE.get('day_league') and test=='environment_tool':slot=('day-a','day-b')[i%2]
                if slot in selected[test]:continue
                for j,(s,f,p,_,offers) in enumerate(dec):
                    if test!='environment_tool' and s!=slot:continue
                    score=net.predict(f);choice=candidates(test,net,j,base['draft_history'],offers,score)
                    if not choice:continue
                    a,b=choice;arms=[]
                    for k in choice:
                        arm=base if k==offers[p] else draft(room,dict.fromkeys(SIDES,net),**arg,diagnostic_action=(j,k))[0]
                        assert arm['draft_history'][:j]==base['draft_history'][:j]
                        arms.append(arm)
                    attempts.append(dict(test=test,slot=slot,seed=arg['seed'],step=j+1,errors=[sc['battle_error'] for sc in arms]))
                    if any(sc['battle_error'] for sc in arms):break
                    idx=[offers.index(k) for k in choice]
                    s0,ban,ids,x=f;orig=x.copy();orig[:,30:42]=first.embed[s0,ids]
                    old=first.predict((s0,ban,ids,orig))
                    history=base['draft_history'][:j]
                    item=dict(test=test,slot=slot,side=s,seed=arg['seed'],night=arg['night'],map=arg['map_name'],weather=arg['weather'],
                              step=j+1,alternatives=[a,b],legal=len(offers),global_choice=offers[p],frozen_margin=float(score[idx[0]]-score[idx[1]]),
                              initial_margin=float(old[idx[0]]-old[idx[1]]),controllers=controllers(i),prefix=history)
                    planned.append((item,arms,i));selected[test].add(slot);break
            if all(len(v)==2 for v in selected.values()):break
    finally:room.close()
    def finish(probe):
        item,arms,i=probe
        with tempfile.TemporaryDirectory(prefix='audit',dir=DRAFT/'scratch') as temp:
            rs=[fight(sc,i,Path(temp)/str(n)) for n,sc in enumerate(arms)]
        item['arms']=rs;item['utility']=[reward(r,item['side']) for r in rs]
        item['decks']=[a['decks'] for a in arms];item['bans']=[a['bans'] for a in arms]
        return item
    with ThreadPoolExecutor(2) as pool:result=list(pool.map(finish,planned))
    write(path,dict(frozen=sha(freeze),room=sha(ROOM),generated=local(time.time()),cases=result,attempts=attempts,
                    missing={t:2-len(v) for t,v in selected.items()}))

if __name__=='__main__':main()
