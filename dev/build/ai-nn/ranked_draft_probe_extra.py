"""Follow-up for missing or broad-effect ban states using legal stochastic prefixes, before looking at payoffs."""
from ranked_draft_probe import *

def main():
    dest=DRAFT/'additional-diagnostics.json'
    if dest.exists():return
    previous=read(DRAFT/'diagnostics.json')
    catalog=read(DRAFT/'catalog-effects.json')
    desired={(t,s) for t in ('visible_parent_ban','visible_multi_target_ban','broad_effect_ban') for s in SIDES}
    desired-=set((r['test'],r['side']) for r in previous['cases'])
    room=Room();tasks=[];inspected=0
    try:
        frozen=DraftNet(room.catalog).load(DRAFT/'frozen.npz');initial=DraftNet(room.catalog).load(DRAFT/'initial.npz')
        both=dict.fromkeys(SIDES,frozen)
        for i in range(48):
            inspected+=1;arg=dict(seed=9830000+i,map_name=HOME,night=bool(i%2),weather='rain' if i%3==1 else 'clear',width=256)
            baseline,dec=draft(room,both,**arg)
            for j,(s,f,p,_,offers) in enumerate(dec):
                h=baseline['draft_history'][j]
                if h['stage']!='second_ban' or h['category']!='secret':continue
                foe=SIDES[1-SIDES.index(s)]
                opponents={a['card'] for a in baseline['draft_history'][:j] if a['side']==foe and a['kind']=='pick'}
                g=catalog['night' if arg['night'] else 'day'][foe];unit_count=len(g['units'])
                def affected(k):
                    return set(g['effects'].get(k,[]))|set(frozen.cards.get(k,{}).get('targets') or [])
                weights=frozen.predict(f);maxkey=lambda subset:max(subset,key=lambda k:weights[offers.index(k)])
                for test in ('visible_parent_ban','visible_multi_target_ban','broad_effect_ban'):
                    if (test,s) not in desired:continue
                    def matches(k):
                        if test=='visible_parent_ban':return bool(frozen.parents[k]&opponents)
                        reach=affected(k);n=len(reach)
                        return bool(reach&opponents) and (n*2>=unit_count if test=='broad_effect_ban' else 2<=n and n*2<unit_count)
                    relevant=[k for k in offers if matches(k)];other=[k for k in offers if not matches(k)]
                    if not relevant or not other:continue
                    keys=[maxkey(relevant),maxkey(other)]
                    arms=[draft(room,both,**arg,greedy_after=j,diagnostic_action=(j,k))[0] for k in keys]
                    assert all(a['draft_history'][:j]==baseline['draft_history'][:j] for a in arms)
                    if any(a['battle_error'] for a in arms):continue
                    ix=[offers.index(k) for k in keys];s0,ban,ids,x=f;raw=x.copy();raw[:,30:42]=initial.embed[s0,ids]
                    old=initial.predict((s0,ban,ids,raw))
                    item=dict(test=test,side=s,step=j+1,seed=arg['seed'],night=arg['night'],weather=arg['weather'],
                              alternatives=keys,global_choice=maxkey(offers),initial_margin=float(old[ix[0]]-old[ix[1]]),
                              frozen_margin=float(weights[ix[0]]-weights[ix[1]]),visible=sorted(opponents),
                              overlap=sorted((frozen.parents[keys[0]] if test=='visible_parent_ban' else affected(keys[0]))&opponents),
                              affected=len(affected(keys[0])),unit_count=unit_count,controllers=controllers(i))
                    tasks.append((item,arms,i));desired.remove((test,s))
            if not desired:break
    finally:room.close()
    def finish(task):
        item,arms,i=task
        with tempfile.TemporaryDirectory(prefix='ban',dir=DRAFT/'scratch') as temp:
            rs=[fight(a,i,Path(temp)/str(n)) for n,a in enumerate(arms)]
        item['arms']=rs;item['utility']=[reward(r,item['side']) for r in rs]
        item['decks']=[a['decks'] for a in arms];item['bans']=[a['bans'] for a in arms];return item
    with ThreadPoolExecutor(2) as pool:cases=list(pool.map(finish,tasks))
    write(dest,dict(frozen=sha(DRAFT/'frozen.npz'),inspected=inspected,missing=sorted(desired),cases=cases))

if __name__=='__main__':main()
