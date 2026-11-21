"""Count states attributable to varying the opponent on the same opening and friendly policy."""
from collections import Counter
import hashlib
import numpy as np
from coverage_guard import OUT
from overnight_common import read, write

def measure():
    counts=Counter()
    deck_counts={}
    scenarios=read(OUT/'scenarios.json')
    ids=read(OUT/'plan.json')['splits']['train']
    for side in ['plant','zombie']:
        deck_counts[side]=len({tuple(scenarios[int(uid)]['decks'][side]) for uid in ids})
    for index,uid in enumerate(ids):
        batch=f'{index//12*12:03}'
        if not (OUT/'train'/(batch+'-oo')/'ready.json').exists():continue
        counts['openings']+=1
        arms={}
        for arm in ['rr','or','ro','oo']:
            root=OUT/'train'/(batch+'-'+arm)
            with np.load(root/'cache'/(uid+'.npz')) as data:
                g=data['g'];tick=data['ticks']
                arms[arm]=[{int(t):row for t,row in zip(tick[g[:,0]==seat],g[g[:,0]==seat])} for seat in [1,0]]
        for i,side in enumerate(['plant','zombie']):
            for own in 'ro':
                r,o=[arms[own+opp if i==0 else opp+own][i] for opp in 'ro']
                shared=r.keys() & o.keys()
                changed=sum(not np.array_equal(r[t],o[t]) for t in shared)
                counts[side+'_paired_trajectories']+=1
                counts[side+'_changed_trajectories']+=changed>0
                counts[side+'_paired_observations']+=len(shared)
                counts[side+'_changed_observations']+=changed
    result=dict(counts=counts,training_decks=deck_counts,scope='Matched exact room tick, same map/seed/decks and own policy; compare 28 native global inputs on every third replan until either game ends.')
    if counts['openings']==len(ids):write(OUT/'opponent-coverage.json',result)
    print(dict(counts))
if __name__=='__main__':measure()
