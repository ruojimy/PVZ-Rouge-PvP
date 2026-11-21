"""v2 combat league: same paired two-population evolution as ranked_day_league, plus
  * three deck strata (free / drafted / template); screening and validation draw from every stratum;
  * promotion additionally requires no net loss of true wins inside any single stratum
    and against r22 itself (deck generalisation, no specialising on one deck family);
  * zombie challengers are also compared against pure r22 zombie on the validation suite.
"""
import copy
from functools import lru_cache
from pathlib import Path
import time
import numpy as np
import ranked_day_league as day
from ranked_day_league import R22,Arena,combat_game,kind
from ranked_draft import BATTLE,PROFILE,SIDES,check_game,read,write
from league_data import sha,local
import league_evolve as evolution
import league_matches as matches

STRATA=tuple(PROFILE.get('strata',('free','drafted','template')))

@lru_cache(None)
def fixtures():
    f=read(BATTLE/'fixtures.json')
    ids=f['train']+f['validation']+f['blind'];assert len(set(ids))==len(ids)==40*len(STRATA)
    for name,src in f['sources'].items():
        folder=Path(src['path']);assert sha(folder/'index.json')==src['sha']
        for e in read(folder/'index.json')['entries']:
            assert name+'/'+e['id'] in ids and check_game(e) and sha(folder/e['cold'])==e['cold_sha256']
    return f
day.fixtures=fixtures          # Arena.pair_game resolves cases through day.fixtures()

def sample(gen,stage,take):
    f=fixtures();rng=np.random.default_rng(20261121+gen*181+(0 if stage=='train' else 97))
    return [str(v) for name in STRATA for v in
            rng.choice([c for c in f[stage] if f['strata'][c]==name],take,replace=False)]

def stratum_ok(report):
    """No stratum may lose net true wins; r22 opponent row may not lose net true wins either."""
    by={}
    for r in report['rows']:
        k=fixtures()['strata'][r['case']];d=by.setdefault(k,[0,0])
        d[0]+=r['old']==1;d[1]+=r['new']==1
    r22=report['by'].get(R22)
    report['strata']=by
    return all(n>=o for o,n in by.values()) and (r22 is None or r22[1][0]>=r22[0][0])

def run_round(st,lanes):
    gen=st['round']+1;learn=sample(gen,'train',2);confirm=sample(gen,'validation',4)
    store=Arena('train',lanes);pop={};origins={}
    try:
        for s in SIDES:
            old=st['sides'][s];base=old['champ'];exp=old['explorer'];alt=old.get('alternate',exp)
            trials=[evolution.mutate(s,parent,gen,j,old['temp']) for j,parent in
                    enumerate([base,base,exp,alt if gen%3==1 else exp])]
            pop[s]=[v for v,_ in trials];origins[s]=[d for _,d in trials]
        screen={}
        for s in SIDES:
            op=evolution.other(s);foes=evolution.unique([R22,st['sides'][op]['champ'],day.historical(op,st,gen),*pop[op]])
            for m in pop[s]:screen[m]=(s,matches.pairs(store,s,st['sides'][s]['champ'],m,foes,learn))
        scores=matches.evaluate(store,screen,'population-crossplay')
        best={s:max(pop[s],key=lambda m:(scores[m]['changed']>0,scores[m]['score'],scores[m]['gain'])) for s in SIDES}
        validation={}
        for s in SIDES:
            op=evolution.other(s);foes=evolution.unique([R22,st['sides'][op]['champ'],day.historical(op,st,gen+1),best[op]])
            validation[s]=(s,matches.pairs(store,s,st['sides'][s]['champ'],best[s],foes,confirm))
            # Anchor: same seat played by r22 itself. A challenger may not fall further behind r22.
            validation[s+'-anchor']=(s,matches.pairs(store,s,R22,best[s],[R22,st['sides'][op]['champ']],confirm))
        tested=matches.evaluate(store,validation,'independent-challenge')
        nex=copy.deepcopy(st);nex['round']=nex['completed_rounds']=gen;changes={}
        for s in SIDES:
            tested[s]['protect_both_tempos']=True
            explorer=evolution.choose_explorer({m:scores[m] for m in pop[s]},st['sides'][s]['champ'])
            ok=stratum_ok(tested[s])
            anchor=tested[s+'-anchor'];op=evolution.other(s)
            champ_wins=sum(r['old']==1 for r in tested[s]['rows'] if r['opp'] in (R22,st['sides'][op]['champ']))
            # The challenger may not fall further behind the r22 seat than the champion already is.
            anchor_ok=anchor['new'][0]>=min(anchor['old'][0],champ_wins) and anchor['speed']>=.97
            nex['sides'][s],changes[s]=update(s,st['sides'][s],best[s],explorer,tested[s],ok and anchor_ok,'/'.join(sorted(confirm)))
            tested[s]['stratum_ok']=ok;tested[s]['anchor_ok']=anchor_ok
        detail=BATTLE/'rounds'/f'{gen:04d}.json.gz'
        evolution.save_detail(detail,dict(gen=gen,train=learn,confirm=confirm,origins=origins,screen=scores,validation=tested,
                                         finalists=best,changes=changes))
        nex['last']=dict(time=local(time.time()),promotions=changes,validation={s:evolution.brief(tested[s]) for s in SIDES},
                         record=str(detail),new_games=store.completed)
        if time.time()<PROFILE['deadline']:write(BATTLE/'state.json',nex)
    finally:store.db.close()

PASS_ANCHOR=dict(new=[1,0,0],old=[0,0,0],speed=1.)

def update(side,st,challenger,explorer,report,extra_ok,suite):
    """league_evolve.update_champion with an extra veto that still counts as a defended round."""
    new=copy.deepcopy(st);report['side']=side
    promoted=extra_ok and evolution.passes(report,PASS_ANCHOR)
    if promoted:
        new['champ']=challenger;new['promotions']+=1;new['defenses']=0;new['last_suites']=[]
        new['hall']=evolution.unique(st['hall']+[challenger])[-5:]
    elif suite not in st['last_suites'] and report['changed']>=3 and report['old'][0]>=2 and (report['new'][0]<=report['old'][0] or not extra_ok):
        new['last_suites']=(st['last_suites']+[suite])[-12:]
        new['defenses']+=1
        if new['defenses']%3==0:new['temp']=max(.14,round(st['temp']*.72,5))
    if explorer and explorer!=new['champ']:new['explorer']=explorer
    return new,promoted

def train():
    while time.time()<PROFILE['deadline']:run_round(read(BATTLE/'state.json'),int(PROFILE.get('battle_lanes',8)))

def start(side):
    return read(BATTLE/'state.json')['start'][side]

def blind_foes(s):
    op=evolution.other(s);st=read(BATTLE/'state.json')
    return [R22,st['start'][op],*day.histories(op)[:2]]

def references():
    store=Arena('reference',4);cases=fixtures()['blind']
    try:
        all_games=[store.pair_game(c,s,base,op) for s in SIDES for base in [R22,start(s)]
                   for op in blind_foes(s) for c in cases]
        store.ensure(all_games,'frozen-baselines')
        write(BATTLE/'reference-cache.json',dict(unique=len({g.key() for g in all_games}),cases=len(cases)))
    finally:store.db.close()

def freeze():
    path=BATTLE/'sealed.json'
    if path.exists():return read(path)
    st=read(BATTLE/'state.json')
    doc=dict(at=local(time.time()),cutoff=local(PROFILE['deadline']),round=st['round'],sides=st['sides'],start=st['start'],
             fixtures=sha(BATTLE/'fixtures.json'))
    for s,e in doc['sides'].items():
        for k in ['champ','explorer']:e[k+'_sha']=sha(Path(e[k]))
    write(path,doc);return doc

def blind():
    seal=read(BATTLE/'sealed.json');assert seal['fixtures']==sha(BATTLE/'fixtures.json')
    store=Arena('blind',int(PROFILE.get('battle_lanes',8)));out={};cases=fixtures()['blind']
    try:
        for s in SIDES:
            e=seal['sides'][s];out[s]={}
            for role in ('champ','explorer'):
                model=e[role];assert sha(Path(model))==e[role+'_sha']
                refs=[('r22',R22),('start',seal['start'][s])]
                table={tag:(s,matches.pairs(store,s,base,model,blind_foes(s),cases)) for tag,base in refs}
                result=matches.evaluate(store,table,s+'/'+role)
                for r in result.values():stratum_ok(r)
                out[s][role]=result
                evolution.save_detail(BATTLE/'blind'/f'{s}-{role}.json.gz',result)
        write(BATTLE/'assessment.json',dict(round=seal['round'],by_side=out))
    finally:store.db.close()

def init_state(plant_champ,plant_explorer,zombie_champ,zombie_explorer,zombie_alternate=None):
    if (BATTLE/'state.json').exists():return
    st=dict(round=0,completed_rounds=0,start=dict(plant=plant_champ,zombie=zombie_champ),sides={})
    for s,c,e,a in [('plant',plant_champ,plant_explorer,None),('zombie',zombie_champ,zombie_explorer,zombie_alternate)]:
        st['sides'][s]=dict(champ=c,explorer=e,hall=[c],defenses=0,temp=.6,promotions=0,last_suites=[],**({'alternate':a} if a else {}))
    write(BATTLE/'state.json',st)
