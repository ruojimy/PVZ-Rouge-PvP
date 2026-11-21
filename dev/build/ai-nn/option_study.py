"""Bounded native home-map study of the value of multi-step zombie decisions."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from position_study import (OUT as PRIOR, R, H, PREV, NIGHT, BUILD, PRIOR_HOME, EXPORT,
                            inputs_ok, size, read, write, sha, cmd, kill_owned, LIMIT, RESERVE, FREE_FLOOR)

ROOT = R/'test_results/ai-nn-home-options-20261118'
ROOT.mkdir(exist_ok=True)
OLD_Z = Path(read(PRIOR/'robust/zombie-frozen.json')['model'])
OLD_P = Path(read(PRIOR/'robust/plant-frozen.json')['model'])
PROGRAM = ROOT/'native/Release/position_match.exe'


def prepare():
    inputs_ok()
    if (ROOT/'splits.json').exists():
        assert sha(ROOT/'plain/index.json')==read(ROOT/'splits.json')['corpus']
        return
    prior = []
    indexes = set()
    for parent in [*R.joinpath('test_results').glob('ai-nn-*'), H]:
        if parent == ROOT:
            continue
        for index in parent.rglob('index.json'):
            data = read(index)
            if isinstance(data,dict) and 'entries' in data and data['entries'] and 'decks' in data['entries'][0]:
                prior.extend(e for e in data['entries'] if e.get('map')=='家院' and 'decks' in e)
                indexes.add(str(index.relative_to(R)))
    sides = ('plant','zombie')
    def decks(row):
        return tuple(tuple(sorted(row['decks'][s])) for s in sides)
    existing = {decks(e) for e in prior}
    known = [{pair[j] for pair in existing} for j in range(2)]
    known_seeds = {e['seed'] for e in prior}
    drafted = []
    def pick():
        chosen=[]; seen=set()
        for dark in [False,True]*9:
            opts = [e for e in drafted if e['night']==dark and decks(e) not in seen|existing
                    and all(d not in seen_side for d,seen_side in zip(decks(e),known))]
            if not opts:
                return None
            def spread(e):
                pair=decks(e)
                return (sum(all(p[j]!=pair[j] for p in seen) for j in range(2)), -e['seed'])
            x=max(opts,key=spread); chosen.append(x); seen.add(decks(x))
        reserved=[{p[j] for p in seen} for j in range(2)]
        development=[]
        for dark in [False,True]*9:
            opts=[e for e in drafted if e['night']==dark and decks(e) not in seen
                  and all(d not in s for d,s in zip(decks(e),reserved))]
            if not opts:return None
            def diversity(e):
                ds=decks(e)
                return min((sum(1-len(set(a)&set(b))/len(set(a)|set(b)) for a,b in zip(ds,decks(other)))
                            for other in development), default=2),-e['seed']
            x=max(opts,key=diversity); development.append(x); seen.add(decks(x))
        return development+chosen
    for batch in range(8):
        path=ROOT/f'draft-{batch}.json'
        if not path.exists():
            cmd(EXPORT/'deck73_corpus.exe',path,3,12,1300000+batch*10000,94139+batch*437)
        drafted.extend(e for e in read(path) if e['map']=='家院' and not e.get('error') and not e.get('invalid') and e['seed'] not in known_seeds)
        cases=pick()
        if cases is not None:break
    if cases is None:raise ValueError('Insufficient disjoint home drafts')
    assert len({e['seed'] for e in cases})==36 and len({decks(e) for e in cases})==36
    for j in range(2):
        assert not ({decks(e)[j] for e in cases[18:]} & (known[j]|{decks(e)[j] for e in cases[:18]}))
    write(ROOT/'scenarios.json',cases)
    if not (ROOT/'corpus/index.json').exists():
        cmd(sys.executable,H/'export_corpus.py',ROOT/'scenarios.json',ROOT/'corpus',3,EXPORT/'cold73_export.exe')
    if not (ROOT/'plain/index.json').exists():
        cmd(sys.executable,H/'materialize_corpus.py',ROOT/'corpus',ROOT/'plain')
    ids=[e['id'] for e in read(ROOT/'plain/index.json')['entries']]
    assert len(ids)==36
    write(ROOT/'splits.json',dict(train=ids[:12],validation=ids[12:18],test=ids[18:],
        corpus=sha(ROOT/'plain/index.json'),past_indexes=sorted(indexes),past_home_combinations=len(existing),
        past_home_plant_decks=len(known[0]),past_home_zombie_decks=len(known[1]),
        independently_unseen_each_side=True, unique_test_each_side=[len({decks(e)[j] for e in cases[18:]}) for j in range(2)]))


def guarded(stage):
    temp=ROOT/'temp';temp.mkdir(exist_ok=True)
    old=sum(size(d) for d in (PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR))
    monitor=ROOT/'disk.json'
    peak=read(monitor)['new_peak'] if monitor.exists() else 0
    def check():
        nonlocal peak
        try:used=size(ROOT)
        except FileNotFoundError:return
        peak=max(peak,used,read(monitor)['new_peak'] if monitor.exists() else 0)
        free=shutil.disk_usage(ROOT).free
        write(monitor,dict(prior=old,current=used,new_peak=peak,combined=old+used,combined_sampled_peak=old+peak,
                           cap=LIMIT,headroom=RESERVE,free=free))
        if old+used>=LIMIT-RESERVE or free<FREE_FLOOR or (ROOT/'STOP').exists():
            raise RuntimeError('Storage or stop guard')
    check()
    with (ROOT/(stage+'.log')).open('ab') as log:
        env=dict(os.environ,TMP=str(temp),TEMP=str(temp),PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        job=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',stage],cwd=R,env=env,
                             stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        try:
            while job.poll() is None:
                check()
                time.sleep(2)
            check()
            if job.returncode:raise RuntimeError('See '+str(ROOT/(stage+'.log')))
        except BaseException:
            kill_owned(job)
            raise


if __name__=='__main__':
    if sys.argv[1]!='worker':guarded(sys.argv[1])
    elif sys.argv[2]=='prepare':prepare()
    elif sys.argv[2]=='build':
        from option_build import build
        build()
    elif sys.argv[2]=='preflight':
        from option_games import preflight
        preflight()
    elif sys.argv[2] in ('confirm-prepare','confirm-test'):
        import option_confirm
        (option_confirm.prepare if sys.argv[2]=='confirm-prepare' else option_confirm.test)()
    elif sys.argv[2].startswith('event-'):
        from event_study import run
        run(sys.argv[2][6:])
    elif sys.argv[2].startswith('adv-'):
        from advantage_study import run
        run(sys.argv[2][4:])
    else:
        from option_fit import run
        run(sys.argv[2])
