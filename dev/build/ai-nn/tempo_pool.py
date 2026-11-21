"""Construct independent home openings and sample actual z16 winning styles."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from single_study import (R, ROOT, H, BUILD, EXPORT, PRIOR_HOME, PRIOR, PREV, NIGHT,
                          CAP, RESERVE, FREE_FLOOR, TEACHERS, PARENT, OLD_Z,
                          read, write, fixed, deck, cmd, sha, size, kill_owned, batch)
from single_study import OUT as PREVIOUS, LAST
from option_games import Game, trace, outcome

OUT=ROOT/'troop-tempo'
CORPUS=OUT/'plain'
LIVE=PREVIOUS/'live/Release/position_match.exe'
LAST_Z=Path(read(PREVIOUS/'zombie.json')['path'])
LAST_P=Path(read(PREVIOUS/'plant.json')['path'])
CARDS=Path(read(R/'dist/latest-native-release.json')['target']).parent/'extract/data/_resolved_cards.json'
CATALOG=read(CARDS)['day']

def game(i,p,z,**changes):
    return Game(i,p,**{'policy':z,'binary':LIVE,'storage':OUT,'corpus':CORPUS,**changes})

def prepare():
    if (OUT/'split.json').exists():
        assert read(OUT/'split.json')['corpus']==sha(CORPUS/'index.json')
        return
    last=read(PREVIOUS/'splits.json')
    indexes=[R/p for p in last['indexes']]+[PREVIOUS/'plain/index.json']
    known=[set(),set()];seeds=set()
    for path in indexes:
        for r in read(path)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                seeds.add(r['seed'])
                for group,value in zip(known,deck(r)):group.add(value)
    pool={}
    def collect(path):
        for r in read(path):
            if r.get('map')=='家院' and r['seed'] not in seeds and not r.get('error') and not r.get('invalid'):
                pool[r['seed']]=r
    for folder in (PREVIOUS,LAST,ROOT/'event',ROOT/'advantage',ROOT/'confirm',ROOT):
        for p in sorted(folder.glob('draft-*.json')):collect(p)
    for p in sorted(OUT.glob('draft-[0-9]*.json')):collect(p)
    rng=np.random.default_rng(948271)
    for n in range(16):
        f=OUT/f'draft-{n}.json'
        if not f.exists():cmd(EXPORT/'deck73_corpus.exe',f,3,16,4210000+n*10000,79395+291*n)
        collect(f)
        rows=list(pool.values())
        for attempt in range(50):
            used=[set(s) for s in known];held=[]
            for j in range(24):
                ok=[r for r in rows if r['seed']>=4210000 and bool(r['night'])==bool(j%2) and all(d not in s for s,d in zip(used,deck(r)))]
                if not ok:break
                r=ok[rng.integers(len(ok))];held.append(r)
                for s,d in zip(used,deck(r)):s.add(d)
            if len(held)==24:break
        if len(held)==24:break
    assert len(held)==24
    blocked=[{deck(r)[j] for r in held} for j in range(2)]
    used=[set(s) for s in blocked];dev=[]
    for j in range(96):
        candidates=[r for r in rows if bool(r['night'])==bool(j%2) and all(d not in s for s,d in zip(used,deck(r)))]
        if not candidates:raise RuntimeError('Insufficient distinct development decks')
        r=candidates[rng.integers(len(candidates))];dev.append(r)
        for s,d in zip(used,deck(r)):s.add(d)
    all_rows=dev+held
    assert len({r['seed'] for r in all_rows})==len(all_rows)
    fixed(OUT/'scenarios.json',all_rows)
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',3,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',CORPUS)
    entries=read(CORPUS/'index.json')['entries'];ids=[r['id'] for r in entries]
    assert [(r['seed'],deck(r)) for r in entries]==[(r['seed'],deck(r)) for r in all_rows]
    fixed(OUT/'split.json',dict(train_pool=ids[:48],val_pool=ids[48:96],a=ids[96:108],b=ids[108:],
          indexes=[str(p.relative_to(R)) for p in indexes],corpus=sha(CORPUS/'index.json'),excluded=list(map(len,known))))

def behavior(g):
    tr=trace(g);deploys=[e for e in tr['accepted_commands'] if e['kind']=='deploy' and e.get('accepted') and e['time']<60 and e['card'].startswith('zombie:')]
    troops=[e for e in deploys if CATALOG[e['card']]['behavior']!='grave']
    graves=[e for e in deploys if CATALOG[e['card']]['behavior']=='grave']
    values=[]
    for group in (troops,graves):
        values.extend([min(8,sum(e['time']<t for e in group))/4 for t in (15,30,60)])
        for e in (group+[None,None])[:2]:
            values.extend([e['time']/60,e['x']/2000,e['y']/1100] if e else [1.2,-.25,-.25])
    flags=[e for e in tr['accepted_commands'] if e['kind']=='rally' and e.get('accepted') and e['time']<60]
    values.extend([len({e.get('grave') for e in troops})/4,min(6,len(flags))/4])
    return dict(x=values,signature=[[e['card'],e.get('grave'),round(e['time'],2),e['x'],e['y']] for e in deploys[:6]],
                troops=len(troops),graves=len(graves))

def screen():
    split=read(OUT/'split.json');samples={};labels=list(TEACHERS)
    def collect(ids,offset):
        work=[(i,labels[(int(i)+offset)%len(labels)]) for i in ids]
        runs=[game(i,TEACHERS[o],PARENT) for i,o in work]
        batch('screen z16 starts',runs)
        for (i,o),g in zip(work,runs):
            samples[i,o]=dict(id=i,opponent=o,result=outcome(trace(g),'zombie'),key=g.key(),**behavior(g))
    collect(split['train_pool']+split['val_pool'],0)
    sets={}
    for name in ('train_pool','val_pool'):
        ids=split[name]
        for offset in (1,2):
            if len({i for (i,o),r in samples.items() if i in ids and r['result']==1})>=9:break
            collect([i for i in ids if not any(r['result']==1 for (k,o),r in samples.items() if k==i)],offset)
        chosen=[];used=set()
        for want in (1,-1):
            options=[r for (i,o),r in samples.items() if i in ids and r['result']==want]
            group=[]
            while len(group)<8:
                live=[r for r in options if r['id'] not in used]
                if not live:break
                def value(r):
                    distances=[np.linalg.norm(np.asarray(r['x'])-s['x']) for s in group]
                    same=sum(s['signature']==r['signature'] for s in group)
                    return (not same,min(distances,default=0.),-sum(s['opponent']==r['opponent'] for s in group),r['id'])
                r=max(live,key=value);group.append(r);used.add(r['id'])
            assert len(group)>=5,(name,want,len(group))
            chosen+=group
        sets[name.split('_')[0]]=chosen
    fixed(OUT/'screen.json',dict(samples=list(samples.values()),**sets))

def setup():
    for p in (OUT,OUT/'temp',OUT/'models'):p.mkdir(exist_ok=True)
    release=read(R/'dist/latest-native-release.json')
    assert release['revision']=='pvp744-r3' and sha(Path(release['target']))==release['exe_sha256']
    build=read(PREVIOUS/'live-build.json')
    assert sha(LIVE)==build['binary'] and all(sha(BUILD/'Release'/k)==v for k,v in build['libraries'].items())
    fixed(OUT/'design.json',dict(official=release['version'],release=release['exe_sha256'],binary=sha(LIVE),
          previous_z=sha(LAST_Z),previous_p=sha(LAST_P),catalog=sha(CARDS),cap=CAP,
          development='Independent train and validation pools. Enrich for distinct z16 winning and losing seeds using only baseline outcomes and actual first-minute deployment times, source and locations.',
          training='Compare actual zombie troops separately from grave construction on the same time window. No direct reward for building, movement or card identities. Use frozen plant snapshots, reverse sides after selection.',
          test='Freeze both candidates before 24 unseen day/night-balanced home starts, 3 opponents each per seat. Check against z16 and previous heads. Require no lost baseline wins, win gains in both batches, nondecreasing troop tempo, and positive clustered win-delta lower bound for promotion. Continue decisive-to-timeout pairs through 1200.'))

def monitor(stage):
    setup();old=sum(size(p) for p in (PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR));disk=OUT/f'disk-{stage}.json'
    peak=read(disk)['peak'] if disk.exists() else 0
    def check():
        nonlocal peak
        try:used=old+size(ROOT)
        except FileNotFoundError:used=old+size(ROOT)
        peak=max(used,peak);write(disk,dict(used=used,peak=peak,cap=CAP))
        if used>CAP-RESERVE or shutil.disk_usage(OUT).free<FREE_FLOOR or (ROOT/'STOP').exists():raise RuntimeError('storage guard')
    check()
    with (OUT/(stage+'.log')).open('ab') as log:
        env=dict(os.environ,TEMP=str(OUT/'temp'),TMP=str(OUT/'temp'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUTF8='1')
        proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',stage],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        try:
            while proc.poll() is None:check();time.sleep(3)
            check()
            if proc.returncode:raise RuntimeError(str(OUT/(stage+'.log')))
        except BaseException:kill_owned(proc);raise

def monitor_test():
    import msvcrt
    setup()
    with (OUT/'test.lock').open('a+b') as lock:
        if lock.tell()==0:
            lock.write(b'0');lock.flush()
        while True:
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:time.sleep(3)
        try:
            if not (OUT/'test.json').exists():monitor('test')
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    if sys.argv[1]=='test':monitor_test()
    elif sys.argv[1]!='worker':monitor(sys.argv[1])
    elif sys.argv[2]=='prepare':prepare()
    elif sys.argv[2]=='screen':screen()
    elif sys.argv[2]=='build':
        from tempo_build import build
        build()
    elif sys.argv[2]=='draft':
        from tempo_draft import generate
        generate()
    else:
        from tempo_train import run
        run(sys.argv[2])
