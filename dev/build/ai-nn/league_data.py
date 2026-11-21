"""Home-map fixtures and immutable inputs for the November 19 overnight league."""
import datetime as dt
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from tempo_pool import ROOT, R, H, OUT as PRIOR_RUN, CORPUS as OLD_CORPUS, EXPORT, BUILD, PREV, NIGHT, PRIOR_HOME, PRIOR, CARDS, deck, read, write, sha
from tempo_build import EXE
from tempo_train import PARENT, OLD_Z, MODELS, STRONG, PLANT, LAST_Z, ACTIVE
from option_games import BASE

RUN=ROOT/'league-20261119'
NEW=RUN/'plain'
TZ=dt.timezone(dt.timedelta(hours=8))
END=dt.datetime(2026,11,19,9,tzinfo=TZ).timestamp()
SEAL=END-60*60
GIB=2**30
RUN_LIMIT=896*2**20
TOTAL_LIMIT=5*GIB
ROOTS=(ROOT,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR)
P_START=Path(read(PRIOR_RUN/'plant.json')['path'])
Z_START=Path(read(PRIOR_RUN/'zombie.json')['path'])
Z_ACTIVE=Path(read(PRIOR_RUN/'contrast.json')['path'])

def local(t):
    return dt.datetime.fromtimestamp(t,TZ).isoformat(timespec='seconds')

def check_inputs():
    release=read(R/'dist/latest-native-release.json')
    assert release['revision']=='pvp744-r3' and release['exe_sha256']==sha(Path(release['target']))
    b=read(PRIOR_RUN/'build.json')
    assert b['binary']==sha(EXE)
    assert all(sha(BUILD/'Release'/k)==v for k,v in b['libraries'].items())
    for key,p in [('plant',P_START),('zombie',Z_START),('contrast',Z_ACTIVE)]:
        assert sha(p)==read(PRIOR_RUN/(key+'.json'))['sha256']
    return dict(version=release['version'],release=release['exe_sha256'],binary=b['binary'],catalog=sha(CARDS),
                plant=sha(P_START),zombie=sha(Z_START),explorer=sha(Z_ACTIVE),z16=sha(PARENT))

def cleanup_tree(folder,allowed):
    target=folder.resolve();parent=allowed.resolve()
    if not target.is_relative_to(parent) or target==parent or not parent.is_relative_to(RUN.resolve()):
        raise ValueError(f'Invalid temporary path {target}')
    if target.exists():shutil.rmtree(target)

def prepare():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'fixtures.json').exists():
        return
    check_inputs()
    work=RUN/'setup';work.mkdir(exist_ok=True)
    tmp=work/'temp';tmp.mkdir(exist_ok=True)
    env={**os.environ,'TEMP':str(tmp),'TMP':str(tmp),'PATH':str(EXPORT)+os.pathsep+os.environ['PATH']}
    indexes=[R/s for s in read(PRIOR_RUN/'split.json')['indexes']]+[OLD_CORPUS/'index.json']
    prior=[x for f in indexes for x in read(f)['entries'] if x.get('map')=='家院' and 'decks' in x]
    seeds={x['seed'] for x in prior};known=[{deck(x)[j] for x in prior} for j in (0,1)]
    tool=PRIOR_RUN/'home-draft/Release/deck73_corpus.exe'
    assert sha(tool)==read(PRIOR_RUN/'draft-build.json')['binary']
    pool=[];rng=np.random.default_rng(198109)
    def select(rows,n,used):
        result=[]
        for j in range(n):
            valid=[x for x in rows if bool(x['night'])==bool(j%2) and all(d not in s for s,d in zip(used,deck(x)))]
            if not valid:break
            x=valid[rng.integers(len(valid))];result.append(x)
            for s,d in zip(used,deck(x)):s.add(d)
        return result
    for batch in range(24):
        f=work/f'draft-{batch:02}.json'
        if not f.exists():
            part=f.with_suffix('.partial')
            subprocess.run([str(v) for v in (tool,part,4,24,5260000+10000*batch,88683+251*batch)],cwd=R,env=env,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=360)
            os.replace(part,f)
        pool.extend(x for x in read(f) if x.get('map')=='家院' and x['seed'] not in seeds and not x.get('error') and not x.get('invalid'))
        held=select(pool,24,[set(s) for s in known])
        if len(held)!=24:continue
        dev=select(pool,32,[{deck(x)[j] for x in held} for j in (0,1)])
        if len(dev)==32:break
    assert len(held)==24 and len(dev)==32
    rows=dev+held;assert len({x['seed'] for x in rows})==len(rows)
    write(work/'scenarios.json',rows)
    for folder in (work/'compressed',work/'materialized'):
        cleanup_tree(folder,work)
    cmd=[sys.executable,'-X','utf8']
    subprocess.run([*cmd,str(H/'export_corpus.py'),str(work/'scenarios.json'),str(work/'compressed'),'3',str(EXPORT/'cold73_export.exe')],cwd=R,env=env,check=True)
    subprocess.run([*cmd,str(H/'materialize_corpus.py'),str(work/'compressed'),str(work/'materialized')],cwd=R,env=env,check=True)
    entries=read(work/'materialized/index.json')['entries']
    assert [(x['seed'],deck(x)) for x in entries]==[(x['seed'],deck(x)) for x in rows]
    if NEW.exists():
        assert sha(NEW/'index.json')==sha(work/'materialized/index.json')
    else:
        (work/'materialized').rename(NEW)
    ids=[x['id'] for x in entries]
    write(RUN/'fixtures.json',dict(fresh_train=ids[:16],fresh_confirm=ids[16:32],blind=ids[32:],
          previous=sha(OLD_CORPUS/'index.json'),fresh=sha(NEW/'index.json'),historical_indexes=len(indexes),
          previous_decks=[len(s) for s in known],drafts=batch+1,blind_seeds=[x['seed'] for x in held]))
    cleanup_tree(work/'compressed',work)

if __name__=='__main__':prepare()
