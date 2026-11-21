"""Home-map empirical opponent pool. Outcome and joint inactivity are recorded separately."""
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import time

from overnight_common import B as NIGHT, BUILD, R, H, BIN, read, write, sha, kill_owned
from coverage_study import OUT as PREV, OLD_MODEL, EXPORT, cmd, inputs_ok
from overnight_eval import footer, measure
from coverage_guard import size

OUT=R/'test_results/ai-nn-home-pool-20261118'
CURRENT=PREV/'model/model.json'
POOL='ron'
SIDES=('plant','zombie')
def score(result, side):
    if result['ai_error']:raise ValueError('AI error')
    if result['timeout'] or result['winner']=='draw':return 0
    assert result['winner'] in SIDES
    return 1 if result['winner']==side else -1
def transitions(ref, new, ids, side):
    names={1:'W',0:'T',-1:'L'}
    counts=Counter(names[score(ref[i],side)]+names[score(new[i],side)] for i in ids)
    return dict(n=len(ids),changes=dict(sorted(counts.items())),delta=sum(score(new[i],side)-score(ref[i],side) for i in ids),
                different_logs=sum(ref[i]['log_sha256']!=new[i]['log_sha256'] for i in ids))
def historical():
    result={}
    for split in ('test','validation'):
        arms={a:read(PREV/split/a/'summary.json')['matches'] for a in ['rr','or','ro','oo','nr','no','rn','on']}
        for seat,side in enumerate(SIDES):
            for opp in 'ro':
                arm=lambda policy:policy+opp if seat==0 else opp+policy
                for ref in 'ro':
                    a,b=arms[arm(ref)],arms[arm('n')]
                    for domain in ['all','家院']:
                        ids=[i for i in a if domain=='all' or a[i]['map']==domain]
                        result['/'.join([split,side,opp,ref,domain])]=transitions(a,b,ids,side)
    write(OUT/'rescored.json',result)
def setup():
    inputs_ok();historical()
    assert sha(CURRENT)==read(PREV/'frozen.json')['model_sha256']
    old=read(PREV/'scenarios.json')
    existing=[(uid,old[int(uid)]) for uid in read(PREV/'plan.json')['splits']['train'] if old[int(uid)]['map']=='家院']
    cmd(EXPORT/'deck73_corpus.exe',OUT/'draft.json',4,3,941000,812311)
    draft=[s for s in read(OUT/'draft.json') if s['map']=='家院']
    assert len(draft)==24 and all(not s.get('error') and not s.get('invalid') for s in draft)
    fresh_train=[s for s in draft if s['seed']<944000 and s['seed']%500<34]
    test=[s for s in draft if s['seed']>=944000]
    assert len(fresh_train)==8 and len(test)==12 and len(existing)==8
    scenarios=[s for _,s in existing]+fresh_train+test
    assert len({s['seed'] for s in scenarios})==28
    write(OUT/'scenarios.json',scenarios)
    write(OUT/'plan.json',dict(train=[f'{i:03}' for i in range(16)],test=[f'{i:03}' for i in range(16,28)],previous={f'{i:03}':uid for i,(uid,_) in enumerate(existing)},initial_sha256=sha(CURRENT),old_sha256=sha(OLD_MODEL),release=read(NIGHT/'plan.json')['release_sha256'],payoffs=dict(win=1,draw_or_timeout=0,loss=-1),protocol='Only home map, balanced day/night. Train 3x3 r22,old,current pool. Restricted minimax via primal/dual LP; mix equilibrium weights half with uniform for opponent coverage. Freeze opponent snapshots. Fit both seat heads independently on their own current trajectories when an alternative beats their paired outcome. Penalize no game duration directly. Exclude preferable timeouts with bilateral inactivity. Freeze candidate before 4x4 test. Report pair transitions, timeout, joint idle, worst-opponent value. No automatic release.'))
    cmd(sys.executable,H/'export_corpus.py',OUT/'scenarios.json',OUT/'corpus',4,EXPORT/'cold73_export.exe')
    cmd(sys.executable,H/'materialize_corpus.py',OUT/'corpus',OUT/'plain')
    align_existing()
def align_existing():
    a=read(PREV/'plain/index.json');b=read(OUT/'plain/index.json')
    assert a['atlas_sha256']==b['atlas_sha256'] and a['recipes_sha256']==b['recipes_sha256']
    if not (OUT/'index-as-exported.json').exists():write(OUT/'index-as-exported.json',b)
    for idx,uid in read(OUT/'plan.json')['previous'].items():
        old=a['entries'][int(uid)];entry=b['entries'][int(idx)]
        assert all(old[k]==entry[k] for k in ['cold_sha256','map','night','seed','decks','bans'])
        source=PREV/'plain'/old['draw']
        dest=OUT/'plain/draw'/('frozen-'+old['draw_sha256']+'.json')
        shutil.copyfile(source,dest)
        assert sha(dest)==old['draw_sha256']
        entry.update(draw=dest.relative_to(OUT/'plain').as_posix(),draw_sha256=old['draw_sha256'])
    write(OUT/'plain/index.json',b)
def arm_game(split,arm):
    from coverage_extract import compact
    root=OUT/split/arm;plan=read(OUT/'plan.json');ids=plan[split];prior=plan['previous']
    if (root/'ready.json').exists():return
    reuse=split=='train' and 'n' not in arm
    simulate=[i for i in ids if not (reuse and i in prior)]
    models={'r':None,'o':OLD_MODEL,'n':CURRENT,'h':OUT/'home-model/model.json',
            'a':OUT/'r22-only/model.json','b':OUT/'snapshot-only/model.json'}
    p,z=[models[a] for a in arm]
    full=split=='train' and 'n' in arm
    args=[sys.executable,H/'eval.py','--bin',BIN/'headless_match.exe','--corpus',OUT/'plain','--out-dir',root,'--ids',','.join(simulate),'--jobs',4,'--limit-seconds',600]
    extras=['--telemetry']
    if p or z:
        args+=['--planner','nn']
        extras+=['--model',p or z,'--nn-seat','both' if p and z else 'plant' if p else 'zombie']
        if p and z: extras+=['--zombie-model',z]
    if not full:extras+=['--no-records']
    if not (root/'summary.json').exists():cmd(*args,'--',*extras)
    summary=read(root/'summary.json')
    assert set(summary['matches'])==set(simulate) and not summary['crashed'] and all(not x['ai_error'] for x in summary['matches'].values())
    rows={}
    for uid in ids:
        if uid in simulate:
            if full:compact(root,uid)
            rows[uid]=dict(match=summary['matches'][uid],trace=str(root/'matches'/(uid+'.jsonl')))
        else:
            prev=prior[uid];folder=PREV/'train'/(f'{int(prev)//12*12:03}-'+arm)
            rows[uid]=dict(match=read(folder/'summary.json')['matches'][prev],trace=str(folder/'matches'/(prev+'.jsonl')))
    write(root/'ready.json',dict(rows=rows,new=len(simulate),reused=len(ids)-len(simulate)))
def inactive(record):
    # Conservative diagnostic proxy. Active combat between units may continue.
    if not record['timeout']:return False
    t=record['time'];events=record['activity'];tail=[e for e in events if e['time']>=t-60]
    if any(e['kind']=='deploy' for e in tail):return False
    for side in SIDES:
        hp=[e['hp'] for e in tail if e['kind']=='plan' and e['side']==side]
        if len(hp)<2 or max(hp)-min(hp)>1e-6:return False
    return True
def jointly_idle(new,ref):
    a=footer(Path(new['trace']));b=footer(Path(ref['trace']))
    stop=min(a['time'],b['time'])
    def slowed(side):
        x=measure(b['activity'],side,stop);y=measure(a['activity'],side,stop)
        return y['rich_idle']>x['rich_idle']+30 or (x['deploys']>=10 and y['deploys']<.75*x['deploys'] and y['mean_resource']>1.5*x['mean_resource'])
    return inactive(a) or all(slowed(s) for s in SIDES)
def study(resume=False):
    if resume:inputs_ok();align_existing()
    else:setup()
    for arm in map(''.join,itertools.product(POOL,repeat=2)):
        print('train',arm,flush=True);arm_game('train',arm)
    from home_response import fit,report
    fit()
    for arm in map(''.join,itertools.product(POOL+'h',repeat=2)):
        print('test',arm,flush=True);arm_game('test',arm)
    report()
def guarded(resume=False):
    OUT.mkdir(exist_ok=resume);scratch=OUT/'temp';scratch.mkdir(exist_ok=resume);peak=read(OUT/'disk.json')['peak'] if resume else 0
    prior=size(PREV)+size(NIGHT)+size(BUILD)
    def guard():
        nonlocal peak
        try:used=size(OUT)
        except FileNotFoundError:return
        free=shutil.disk_usage(OUT).free;peak=max(peak,used)
        write(OUT/'disk.json',dict(current=used,peak=peak,prior=prior,free=free))
        if free<100*2**30 or prior+used>4*2**30-256*2**20 or (OUT/'STOP').exists():raise RuntimeError('Space or STOP guard')
    guard()
    with (OUT/('resume.log' if resume else 'run.log')).open('ab') as log:
        proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'resume-study' if resume else 'study'],cwd=R,env=dict(os.environ,TMP=str(scratch),TEMP=str(scratch),OPENBLAS_NUM_THREADS='1',PYTHONUTF8='1'),creationflags=0x08004000,stdout=log,stderr=subprocess.STDOUT)
        try:
            while proc.poll() is None:guard();time.sleep(2)
            guard()
            if proc.returncode:raise RuntimeError('Home study failed')
        except BaseException:kill_owned(proc);raise
if __name__=='__main__':
    if sys.argv[1:] in (['study'],['resume-study']):study(sys.argv[1]=='resume-study')
    else:guarded(sys.argv[1:]==['resume'])
