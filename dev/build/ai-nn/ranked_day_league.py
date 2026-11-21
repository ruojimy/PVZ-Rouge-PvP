"""Paired two-population evolution with fixed, public rule and independent draft training."""
import copy
from dataclasses import replace
from functools import lru_cache
import gzip
import json
from pathlib import Path
import time
import numpy as np
from ranked_draft import BATTLE,HOME,NATIVE,PROFILE,RUN,RULES,SIDES,check_game,read,write
from league_data import sha,local
import league_evolve as evolution
import league_matches as matches
from option_games import Game

R22='r22'
W=Path(PROFILE['weights_dir'])
evolution.RUN=matches.RUN=BATTLE

@lru_cache(None)
def meta():return read(BATTLE/'opponents.json')

@lru_cache(None)
def fixtures():
    f=read(BATTLE/'fixtures.json')
    ids=f['train']+f['validation']+f['blind'];assert len(set(ids))==len(ids)==96
    for name,src in f['sources'].items():
        folder=Path(src['path']);assert sha(folder/'index.json')==src['sha']
        for e in read(folder/'index.json')['entries']:
            assert name+'/'+e['id'] in ids
            assert check_game(e) and sha(folder/e['cold'])==e['cold_sha256']
    return f

@lru_cache(256)
def kind(z):
    d=read(Path(z))
    if 'switch' not in d:return 'neural'
    return 'special' if 'native_gate' in d['switch'] else 'option'

def combat_game(corpus,uid,plant,zombie,storage):
    neural=None if plant==R22 else Path(plant)
    g=Game(uid,neural,zombie=None,position=None,policy=None,corpus=corpus,binary=NATIVE/'position_match.exe',storage=storage)
    if zombie==R22:return g
    mode=kind(zombie)
    if mode=='neural':return replace(g,zombie=Path(zombie))
    return replace(g,zombie=None if mode=='special' else W/'macro.json',position=W/'position.json',policy=Path(zombie))

class Arena(matches.Matches):
    def pair_game(self,case,side,m,op):
        tag,uid=case.split('/')
        assert case in fixtures()['strata']
        p,z=(m,op) if side=='plant' else (op,m)
        return combat_game(Path(fixtures()['sources'][tag]['path']),uid,p,z,self.storage)

def start(side):return meta()['pool']['away'] if side=='plant' else meta()['champion']

def histories(side):
    m=meta()
    return [m['pool'][n] for n in ('H','B','across')] if side=='plant' else [m['start_zombie'],m['pool']['H'],m['pool']['B']]

def historical(side,st,g):
    options=evolution.unique(histories(side)+st['sides'][side]['hall'][:-1])
    return options[(g-1)%len(options)]

def sample(gen,stage,take):
    f=fixtures();rng=np.random.default_rng(20261120+gen*181+(0 if stage=='train' else 97))
    return [str(v) for name in ['free','template'] for v in
            rng.choice([c for c in f[stage] if f['strata'][c]==name],take,replace=False)]

def run_round(st,lanes):
    gen=st['round']+1;learn=sample(gen,'train',2);confirm=sample(gen,'validation',5)
    store=Arena('train',lanes);pop={};origins={}
    try:
        for s in SIDES:
            old=st['sides'][s];base=old['champ'];exp=old['explorer']
            alternate=meta()['start_zombie'] if s=='zombie' else meta()['pool']['explorer']
            trials=[evolution.mutate(s,parent,gen,j,old['temp']) for j,parent in
                    enumerate([base,base,exp,alternate if gen%3==1 else exp])]
            pop[s]=[v for v,_ in trials];origins[s]=[d for _,d in trials]
        screen={}
        for s in SIDES:
            op=evolution.other(s);foes=evolution.unique([R22,st['sides'][op]['champ'],historical(op,st,gen),*pop[op]])
            for m in pop[s]:screen[m]=(s,matches.pairs(store,s,st['sides'][s]['champ'],m,foes,learn))
        scores=matches.evaluate(store,screen,'population-crossplay')
        best={s:max(pop[s],key=lambda m:(scores[m]['changed']>0,scores[m]['score'],scores[m]['gain'])) for s in SIDES}
        validation={}
        for s in SIDES:
            op=evolution.other(s);foes=evolution.unique([R22,st['sides'][op]['champ'],historical(op,st,gen+1),best[op]])
            validation[s]=(s,matches.pairs(store,s,st['sides'][s]['champ'],best[s],foes,confirm))
            validation[s+'-anchor']=(s,matches.pairs(store,s,start(s),best[s],[R22,st['sides'][op]['champ']],confirm))
        tested=matches.evaluate(store,validation,'independent-challenge')
        nex=copy.deepcopy(st);nex['round']=nex['completed_rounds']=gen;changes={}
        for s in SIDES:
            tested[s]['protect_both_tempos']=True
            explorer=evolution.choose_explorer({m:scores[m] for m in pop[s]},st['sides'][s]['champ'])
            nex['sides'][s],changes[s]=evolution.update_champion(s,st['sides'][s],best[s],explorer,tested[s],
                                        tested[s+'-anchor'],'/'.join(sorted(confirm)))
        detail=BATTLE/'rounds'/f'{gen:04d}.json.gz'
        evolution.save_detail(detail,dict(gen=gen,train=learn,confirm=confirm,origins=origins,screen=scores,validation=tested,
                                         finalists=best,changes=changes))
        nex['last']=dict(time=local(time.time()),promotions=changes,validation={s:evolution.brief(tested[s]) for s in SIDES},
                         record=str(detail),new_games=store.completed)
        if time.time()<PROFILE['deadline']:write(BATTLE/'state.json',nex)
    finally:store.db.close()

def train():
    while time.time()<PROFILE['deadline']:run_round(read(BATTLE/'state.json'),6)

def freeze():
    path=BATTLE/'sealed.json'
    if path.exists():return read(path)
    st=read(BATTLE/'state.json')
    doc=dict(at=local(time.time()),cutoff=local(PROFILE['deadline']),round=st['round'],sides=st['sides'],
             fixtures=sha(BATTLE/'fixtures.json'))
    for s,e in doc['sides'].items():
        for k in ['champ','explorer']:e[k+'_sha']=sha(Path(e[k]))
        e['first_cooled']=None
    for gen in range(1,st['round']+1):
        with gzip.open(BATTLE/'rounds'/f'{gen:04d}.json.gz','rt',encoding='utf8') as f:r=json.load(f)
        for s,e in doc['sides'].items():
            parent=r['origins'][s][0]
            if e['first_cooled'] is None and parent['temperature']<1:
                assert sha(Path(parent['parent']))==parent['parent_sha']
                e['first_cooled']=dict(round=gen,champ=parent['parent'],sha=parent['parent_sha'],temp=parent['temperature'])
    write(path,doc);return doc

def blind_foes(s):
    op=evolution.other(s);return [R22,start(op),*histories(op)[:2]]

def references():
    store=Arena('reference',2);cases=fixtures()['blind']
    try:
        all_games=[store.pair_game(c,s,base,op) for s in SIDES for base in [R22,start(s),histories(s)[0]]
                   for op in blind_foes(s) for c in cases]
        store.ensure(all_games,'frozen-baselines')
        write(BATTLE/'reference-cache.json',dict(unique=len({g.key() for g in all_games}),cases=len(cases)))
    finally:store.db.close()

def blind():
    seal=read(BATTLE/'sealed.json');assert seal['fixtures']==sha(BATTLE/'fixtures.json')
    store=Arena('blind',6);out={};cases=fixtures()['blind']
    try:
        for s in SIDES:
            e=seal['sides'][s];out[s]={}
            for role in ('champ','explorer'):
                model=e[role];assert sha(Path(model))==e[role+'_sha']
                refs=[('r22',R22),('start',start(s)),('history',histories(s)[0])]
                if role=='champ' and e.get('first_cooled'):
                    ref=e['first_cooled'];assert sha(Path(ref['champ']))==ref['sha']
                    refs.append(('first_cooled',ref['champ']))
                table={tag:(s,matches.pairs(store,s,base,model,blind_foes(s),cases)) for tag,base in refs}
                result=matches.evaluate(store,table,s+'/'+role)
                out[s][role]=result
                evolution.save_detail(BATTLE/'blind'/f'{s}-{role}.json.gz',result)
        write(BATTLE/'assessment.json',dict(round=seal['round'],by_side=out))
    finally:store.db.close()

def report():
    from collections import Counter
    seal=read(BATTLE/'sealed.json');result=read(BATTLE/'assessment.json')['by_side']
    lines=['# 白天家院双擂主晨测','',f"冻结于 {seal['cutoff']}，共完成 {seal['round']} 轮。48 个留出开局，每个开局打四个固定对手。",'',
           '| 阵营与权重 | 同方对照 | 保住旧胜 | 旧败真胜 | 败转超时延长（胜/未决/负） | 己方部署或出兵/分 | 平均局长（秒） |',
           '|---|---|---:|---:|---|---|---|']
    short={}
    for s,name in [('plant','植物'),('zombie','僵尸')]:
        short[s]={}
        for role,tag in [('champ','擂主'),('explorer','探索头')]:
            short[s][role]={}
            labels=[('r22','r22'),('start','开训擂主'),('history','历史强头')]
            if 'first_cooled' in result[s][role]:
                labels.append(('first_cooled',f"首次降温第 {seal['sides'][s]['first_cooled']['round']} 轮擂主"))
            for key,label in labels:
                r=result[s][role][key];rows=r['rows']
                assert set((v['case'],v['opp']) for v in rows)=={(c,o) for c in fixtures()['blind'] for o in blind_foes(s)}
                late=Counter(v['late']['value'] for v in rows if v['old']==-1 and v['late'])
                a,b=r['rates']['plant' if s=='plant' else 'troops'];t,u=r['seconds']
                lines.append(f"| {name}{tag} | {label} | {r['kept']}/{r['old'][0]} | {r['gain']}/{r['old'][2]} | {late[1]}/{late[0]}/{late[-1]} | {a:.2f} → {b:.2f} | {t:.1f} → {u:.1f} |")
                short[s][role][key]=dict(by_opponent=r['by'],extended=dict(late),rates=r['rates'],seconds=r['seconds'])
    (BATTLE/'双擂主晨测.md').write_text('\n'.join(lines)+'\n','utf8')
    write(BATTLE/'review.json',dict(sides=short,round=seal['round'],fixtures=seal['fixtures']))
