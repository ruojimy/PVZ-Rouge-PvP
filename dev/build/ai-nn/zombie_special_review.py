"""Audit a completed training and sealed test, including one-action replays of distinct new openings."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
import zlib
import json
import numpy as np

from zombie_special_train import OUT,NIGHT,FRESH,EXE,R22,metadata,fixtures,make_game,read,write,sha,label,all_samples
from option_games import play,trace
from ranked_combat_pool import SUPPORT

def review():
    seal=read(OUT/'sealed.json');result=read(OUT/'assessment.json')
    support=read(OUT/'playable.json')
    assert sha(SUPPORT/'index.json')==support['index_sha']
    cases=fixtures()['blind']+support['blind']
    assert sha(OUT/'fixtures.json')==seal['fixture_sha'] and sha(FRESH/'index.json')==fixtures()['index_sha']
    inputs=metadata()
    for n,sig in inputs['plant_sha'].items():assert sha(Path(inputs['pool'][n]))==sig
    expected={inputs['pool'][n] for n in [*inputs['selected'],'r22','B']}
    cases_in_training={r['case'] for r in all_samples()}
    assert len(expected)==5 and len(set(cases))==48 and not set(cases)&cases_in_training
    with sqlite3.connect((OUT/'matches.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('pragma quick_check').fetchone()==('ok',)
        def receipt(k):
            blob=db.execute('select payload from games where id=?',(k,)).fetchone()[0]
            return json.loads(zlib.decompress(blob))
        summaries={};chosen=[]
        for role,data in result.items():
            path=seal['models'][role];assert sha(Path(path))==seal['hashes'][role]
            summaries[role]={}
            for base,baseline_model in [('r22',R22),('night',inputs['champion'])]:
                item=data[base];rows=item['rows']
                assert len(rows)==len(cases)*len(expected) and {(r['case'],r['opp']) for r in rows}=={(c,o) for c in cases for o in expected}
                transitions=Counter();active=0;actions=[0,0];differences=Counter()
                for r in rows:
                    a,b=[receipt(k) for k in r['keys']]; assert a['seed']==b['seed'] and a['params']['plant']==b['params']['plant']
                    assert r['keys']==[make_game(r['case'],r['opp'],m,OUT).key() for m in (baseline_model,path)]
                    assert b['params']['binary']==sha_binary and b['params']['corpus']==(support if r['case'].startswith('playable/') else fixtures())['index_sha']
                    if r['late']:
                        z=receipt(r['late']['key'])
                        assert z['prefix']==b['prefix'] and z['params']=={**b['params'],'limit':1200}
                    transitions[r['old'],r['new']]+=1;active+=int(sum(b['special_actions'])>0)
                    for j,n in enumerate(b['special_actions']):actions[j]+=n
                    differences[r['case']]+=int(r['new']==1)-int(r['old']==1)
                deltas=np.array([differences[c]/5 for c in cases])
                ci=np.quantile(np.random.default_rng(7192).choice(deltas,(20000,len(cases))).mean(axis=1)*100,[.025,.975]).tolist()
                summaries[role][base]=dict(transitions={f'{a}/{b}':v for (a,b),v in transitions.items()},cluster_95pp=ci,
                    changed_win_openings=sum(v!=0 for v in differences.values()),decisions=actions,active_games=active)
            for a,b in [(-1,1),(1,-1),(0,1)]:
                item=next((r for r in data['r22']['rows'] if r['old']==a and r['new']==b
                           and not any(r['case']==other['case'] for _,other in chosen)),None)
                if item and len(chosen)<3:chosen.append((role,item))
    folder=OUT/'review';(folder/'temp').mkdir(parents=True,exist_ok=True)
    examples=[]
    for role,r in chosen:
        g=make_game(r['case'],r['opp'],seal['models'][role],folder)
        play(g);t=trace(g)
        assert g.key()==r['keys'][1]
        with sqlite3.connect((OUT/'matches.sqlite').as_uri()+'?mode=ro',uri=True) as con:
            pay=con.execute('select payload from games where id=?',(g.key(),)).fetchone()[0]
        assert t['log_sha256']==json.loads(zlib.decompress(pay))['battle']
        site=next(e for e in t['switches'] if e['phase']=='special' and e['choice']>0)
        arms=[replace(g,forced=j,after=site['t']) for j in (0,1,2)]
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(play,arms))
        branches=[trace(a) for a in arms]
        stamps=[next(e for e in tr['switches'] if e['phase']=='special' and 'prefix' in e) for tr in branches]
        assert all(e['prefix']==stamps[0]['prefix'] and e['x']==stamps[0]['x'] and e['t']==site['t'] for e in stamps)
        assert branches[site['choice']]['log_sha256']==t['log_sha256']
        examples.append(dict(role=role,case=r['case'],opponent=label(r['opp']),old=r['old'],new=r['new'],t=site['t'],
            choice=site['choice'],mask=site['mask'],prefix=stamps[0]['prefix'],keys=[a.key() for a in arms],
            branches=[dict(winner=(tr['result'] or {}).get('winner'),timeout=tr['timeout'],seconds=tr['time'],
                       first=[c for c in tr['accepted_commands'] if c['accepted'] and round(site['t']*30)<=c['tick']<=round(site['t']*30)+30][:4]) for tr in branches]))
    profile=all_samples()
    stats=dict(n=len(profile),distinct_prefixes=len({r['prefix'] for r in profile}),
               changed_outcome=sum(len({a['w'] for a in r['arms']})>1 for r in profile),
               actual_action_difference=sum(len({a['battle'] for a in r['arms']})>1 for r in profile))
    write(OUT/'review.json',dict(summary=summaries,examples=examples,samples=stats,sealed_sha=sha(OUT/'sealed.json')))
    return stats

sha_binary=sha(EXE) if EXE.is_file() else None
if __name__=='__main__':print(review())
