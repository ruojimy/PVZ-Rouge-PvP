"""Isolated home-map study for reversible, one-decision neural selection."""
import os,re,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import numpy as np
from switch_study import ROOT,R,H,BUILD,EXPORT,OLD_Z,PARENT,STRONG,PLANTS,PREV,NIGHT,PRIOR_HOME,PRIOR,RESERVE,FREE_FLOOR,kill_owned,write,size,sha,read,fixed,cmd,inputs_ok,deck,replace_once
from switch_study import OUT as LAST, CORPUS as PREVIOUS_CORPUS, CONTEXT as PREVIOUS_NATIVE
from option_games import Game,MODELS,play,trace,outcome,slow,extend
import option_games
OUT=ROOT/'single'
CORPUS=OUT/'plain'
NATIVE=OUT/'native/Release/position_match.exe'
ACTIVE=Path(read(LAST/'final-zombie.json')['active'])
PLANT=Path(read(LAST/'final-plant.json')['path'])
TEACHERS={'p':STRONG,'o':PLANT,'h':MODELS['h']}
CAP=5*2**30
def setup():
    for p in (OUT,OUT/'temp',OUT/'models'):p.mkdir(exist_ok=True)
    assert sha(ACTIVE)==read(LAST/'final-zombie.json')['active_sha'] and sha(PLANT)==read(LAST/'final-plant.json')['sha256']
    release=read(R/'dist/latest-native-release.json')
    assert sha(Path(release['target']))==release['exe_sha256'] and release['revision']=='pvp744-r3'
    fixed(OUT/'design.json',dict(release=release['version'],active=sha(ACTIVE),z16=sha(PARENT),plant=sha(PLANT),cap=CAP,
        review='All 7 losses turned wins and all 11 regressed wins from the previous active blind comparison. Replay both complete input streams. At first difference continue z16, replay active through that single decision then return to z16, or continue the original active head. Pair on complete public native state and RNG.',
        trial='No card-specific reward. Renew choice at public events and regular action opportunities. Fit marginal one-decision returns using previous cases, fresh fixed-plant rollouts and paired arrival build/defer interventions. Rank trained variants on fresh development wins, original win retention and common-window deployment.',
        blind='24 disjoint new home openings, equal day/night, paired against r22,H,B. Both trained seats frozen before testing. Count true wins and deployment on common windows. Extend all loss to timeout through 1200.'))
def batch(label,games):
    games=list(dict.fromkeys(games));print(label,len(games),flush=True)
    with ThreadPoolExecutor(max_workers=4 if label.startswith('extend') else int(os.environ.get('PVZ_SINGLE_JOBS','8'))) as pool:
        for _ in pool.map(play,games):pass
option_games.batch=batch

def game(i,plant,policy,corpus=CORPUS,**kw):
    return Game(i,plant,policy=policy,storage=OUT,corpus=corpus,binary=kw.pop('binary',NATIVE),**kw)
def policy(name,config):
    path=OUT/'models'/(name+'.json')
    fixed(path,{**read(ACTIVE),'switch':config});return path
def scans():
    rows=read(LAST/'test.json')['results']['active']['all']['rows']
    rows=[r for r in rows if (r['old']==-1 and r['new']==1) or (r['old']==1 and r['new']!=1)]
    assert len(rows)==18 and sum(r['old']==-1 for r in rows)==7
    old=policy('old-inputs',dict(start='old',full_inputs=True));new=policy('persistent-inputs',{**read(ACTIVE)['switch'],'full_inputs':True})
    groups=[]
    for r in rows:
        i,o=r['id'],r['opponent']
        a,b=[game(i,MODELS[o],p,PREVIOUS_CORPUS,binary=PREVIOUS_NATIVE) for p in (old,new)]
        groups.append((r,a,b))
    return groups
def history():
    from switch_fit import divergence
    option_games.batch=batch
    groups=scans();batch('18 previous pairs with full zombie input streams',[g for _,a,b in groups for g in (a,b)])
    rows=[]
    for r,a,b in groups:
        for g,k in ((a,'baseline'),(b,'candidate')):
            assert trace(g)['log_sha256']==read(LAST/'games'/(r[k]+'.jsonl.receipt.json'))['battle']
        t,x,y=divergence(a,b);assert t is not None
        rows.append(dict(id=a.uid,opponent=r['opponent'],old=r['old'],persistent=r['new'],tick=t,commands=[x,y],keys=[a.key(),b.key()]))
    fixed(OUT/'disagreements.json',dict(rows=rows))
def prepare():
    if (OUT/'splits.json').exists():return
    paths=[R/p for p in read(LAST/'splits.json')['indexes']]+[PREVIOUS_CORPUS/'index.json']
    known=[set(),set()];seeds=set()
    for path in paths:
        for r in read(path)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                seeds.add(r['seed'])
                for k,d in zip(known,deck(r)):k.add(d)
    pool=[]
    for d in (LAST,LAST.parent/'event',ROOT/'advantage',ROOT/'confirm',ROOT):
        for p in sorted(d.glob('draft-*.json')):
            pool.extend(r for r in read(p) if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'))
    rng=np.random.default_rng(839721)
    for n in range(15):
        p=OUT/f'draft-{n}.json'
        if not p.exists():cmd(EXPORT/'deck73_corpus.exe',p,3,16,3410000+10000*n,53433+119*n)
        pool.extend(r for r in read(p) if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'))
        for _ in range(100):
            used=[set(x) for x in known];held=[]
            for j in range(24):
                ok=[r for r in pool if bool(r['night'])==bool(j%2) and all(v not in s for v,s in zip(deck(r),used)) and (j>=12 or r['seed']>=3410000)]
                if not ok:break
                r=ok[rng.integers(len(ok))];held.append(r)
                for k,v in zip(used,deck(r)):k.add(v)
            if len(held)==24:break
        if len(held)!=24:continue
        used=[{deck(r)[j] for r in held} for j in range(2)];dev=[]
        for j in range(16):
            ok=[r for r in pool if bool(r['night'])==bool(j%2) and all(v not in s for v,s in zip(deck(r),used))]
            if not ok:break
            r=ok[rng.integers(len(ok))];dev.append(r)
            for k,v in zip(used,deck(r)):k.add(v)
        if len(dev)==16:break
    assert len(held)==24 and len(dev)==16 and len({r['seed'] for r in dev+held})==40
    fixed(OUT/'scenarios.json',dev+held)
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',CORPUS)
    entries=read(CORPUS/'index.json')['entries'];ids=[r['id'] for r in entries]
    assert [(r['seed'],deck(r)) for r in entries]==[(r['seed'],deck(r)) for r in dev+held]
    fixed(OUT/'splits.json',dict(train=ids[:8],val=ids[8:16],a=ids[16:28],b=ids[28:],corpus=sha(CORPUS/'index.json'),indexes=[str(p.relative_to(R)) for p in paths],excluded=[len(s) for s in known]))
def monitor(stage):
    setup();old=sum(size(d) for d in (PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR));disk=OUT/('disk-'+stage+'.json')
    peak=read(disk)['peak'] if disk.exists() else 0
    def check():
        nonlocal peak
        try:used=old+size(ROOT)
        except FileNotFoundError:used=old+size(ROOT)
        peak=max(used,peak);write(disk,dict(used=used,peak=peak,cap=CAP))
        if used>CAP-RESERVE or shutil.disk_usage(OUT).free<FREE_FLOOR or (ROOT/'STOP').exists():raise RuntimeError('storage guard')
    check()
    with (OUT/(stage+'.log')).open('ab') as log:
        env=dict(os.environ,TEMP=str(OUT/'temp'),TMP=str(OUT/'temp'),PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        job=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',stage],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        try:
            while job.poll() is None:check();time.sleep(3)
            check()
            if job.returncode:raise RuntimeError('See '+str(OUT/(stage+'.log')))
        except BaseException:kill_owned(job);raise
def worker(stage):
    if stage=='prepare':prepare()
    elif stage=='history':history()
    elif stage=='build-live':
        from single_build import build_live
        build_live()
    elif stage=='probe-build':
        from single_build import build_arrival_probe
        build_arrival_probe()
    elif stage=='build':
        from single_build import build
        build()
    else:
        from single_fit import run
        run(stage)
if __name__=='__main__':
    if sys.argv[1]=='worker':worker(sys.argv[2])
    else:monitor(sys.argv[1])
