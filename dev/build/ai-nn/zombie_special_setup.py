"""Freeze plant opponents, regression pairs and independent home fixtures for the two-hour run."""
import itertools
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import zlib

import numpy as np
import league_data as previous
from league_data import ROOT, R, H, OLD_CORPUS, NEW, PRIOR_RUN, MODELS, EXPORT, deck, read, write, sha, check_inputs
from league_matches import native_game, value

OUT=ROOT/'zombie-special-2h-20261119'
NIGHT=previous.RUN
REVIEW=NIGHT/'review/r22-replacement'
SOURCE=PRIOR_RUN/'native-src'
EXE=OUT/'native/Release/position_match.exe'
FRESH=OUT/'plain'

def select_opponents():
    frozen=read(NIGHT/'frozen.json')['sides']
    pool={'away':frozen['plant']['champ'],'H':str(MODELS['h']),'B':str(MODELS['b']),
          'across':str(previous.PLANT),'explorer':frozen['plant']['explorer'],'r22':'r22'}
    databases=[sqlite3.connect((p/'matches.sqlite').as_uri()+'?mode=ro',uri=True) for p in (NIGHT,REVIEW)]
    def receipt(g):
        for db in databases:
            row=db.execute('select payload from games where id=?',(g.key(),)).fetchone()
            if row:return json.loads(zlib.decompress(row[0]))
        raise RuntimeError(g.key())
    ids=read(NIGHT/'fixtures.json')['blind']
    runs={n:[receipt(native_game('new/'+i,m,'r22',OUT)) for i in ids] for n,m in pool.items()}
    wins={n:sum(value(r,'plant')==1 for r in rs) for n,rs in runs.items()}
    def distance(a,b):
        count=0
        for x,y in zip(runs[a],runs[b]):
            end=min(3600,x['tick'],y['tick'])
            count+=([t for t in x['activity']['plant'] if t<=end]!=[t for t in y['activity']['plant'] if t<=end])
        return count
    selected=['away']
    while len(selected)<3:
        eligible=[n for n in pool if n not in selected and wins[n]>=wins['away']-1 and n!='r22']
        selected.append(max(eligible,key=lambda n:(min(distance(n,s) for s in selected),wins[n])))
    study=read(REVIEW/'comparison.json')['report']['zombie']['rows']
    pairs=[dict(case=r['case'],plant=r['opp'],r22=r['old'],night=r['new'],keys=r['keys']) for r in study
           if (r['old']==1 and r['new']!=1) or (r['old']==-1 and r['new']==1)]
    assert len(pairs)==27 and sum(r['r22']==1 for r in pairs)==19
    for db in databases:db.close()
    return dict(pool=pool,wins=wins,distance={a+' / '+b:distance(a,b) for a,b in itertools.combinations(pool,2)},
                selected=selected,plant_sha={n:sha(Path(m)) for n,m in pool.items() if n!='r22'},regression=pairs,
                champion=frozen['zombie']['champ'],champion_sha=frozen['zombie']['champ_sha'])

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'fixtures.json').exists():return
    check_inputs()
    write(OUT/'opponents.json',select_opponents())
    work=OUT/'setup';work.mkdir(exist_ok=True)
    temp=work/'temp';temp.mkdir(exist_ok=True)
    env={**os.environ,'PATH':str(EXPORT)+os.pathsep+os.environ['PATH'],'TEMP':str(temp),'TMP':str(temp)}
    indexes=[*(R/p for p in read(PRIOR_RUN/'split.json')['indexes']),OLD_CORPUS/'index.json',NEW/'index.json']
    known=[v for p in indexes for v in read(p)['entries'] if v.get('map')=='家院' and 'decks' in v]
    used=[{deck(v)[seat] for v in known} for seat in (0,1)]
    seen={v['seed'] for v in known}; chosen=[]
    generator=PRIOR_RUN/'home-draft/Release/deck73_corpus.exe'
    assert sha(generator)==read(PRIOR_RUN/'draft-build.json')['binary']
    for batch in range(22):
        path=work/f'draft-{batch}.json'
        if not path.exists():subprocess.run([str(x) for x in (generator,path,4,24,6840000+batch*10000,11888+batch*197)],cwd=R,check=True,stdout=subprocess.DEVNULL,env=env)
        rows=read(path);np.random.default_rng(3309+batch).shuffle(rows)
        for _ in range(48):
            eligible=[v for v in rows if v.get('map')=='家院' and not v.get('error') and not v.get('invalid')
                      and v['seed'] not in seen and bool(v['night'])==bool(len(chosen)%2)
                      and all(d not in u for u,d in zip(used,deck(v)))]
            if not eligible:break
            v=eligible[0];chosen.append(v);seen.add(v['seed'])
            for u,d in zip(used,deck(v)):u.add(d)
            if len(chosen)==48:break
        if len(chosen)==48:break
    assert len(chosen)==48
    write(work/'scenarios.json',chosen)
    subprocess.run([sys.executable,'-X','utf8',str(H/'export_corpus.py'),str(work/'scenarios.json'),str(work/'compressed'),'3',str(EXPORT/'cold73_export.exe')],check=True,cwd=R,env=env)
    subprocess.run([sys.executable,'-X','utf8',str(H/'materialize_corpus.py'),str(work/'compressed'),str(FRESH)],check=True,cwd=R,env=env)
    entries=read(FRESH/'index.json')['entries']
    assert [(v['seed'],deck(v)) for v in chosen]==[(v['seed'],deck(v)) for v in entries]
    ids=['fresh/'+v['id'] for v in entries]
    write(OUT/'fixtures.json',dict(train=ids[:16],validation=ids[16:24],blind=ids[24:],index_sha=sha(FRESH/'index.json'),
          prior_indexes=len(indexes),blind_seeds=[v['seed'] for v in entries[24:]]))

if __name__=='__main__':prepare()
