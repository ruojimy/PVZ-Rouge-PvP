"""Unattended v2 run supervisor (2026-11-20): battle league + draft trainer until the deadline,
then freeze and blind tests.  Usage:  python ranked_v2_run.py            (supervise)
Stop early by creating <run>/STOP; weights committed so far are kept and evaluated."""
import ctypes
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

H=Path(__file__).resolve().parent
RUN=H.parents[1]/'test_results/ai-nn-home-options-20261118/ranked-v2-20261120'
os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
from ranked_draft import BATTLE,DRAFT,PROFILE,read,write
from league_data import local,sha
import league_run as win

assert BATTLE==RUN/'battle' and PROFILE.get('v2')
END=PROFILE['deadline']
RUN_LIMIT=int(PROFILE.get('run_limit_bytes',2*2**30))
MARKERS={'references':BATTLE/'reference-cache.json','battle-eval':BATTLE/'assessment.json','draft':DRAFT/'results.json'}

def worker(role):
    for _ in range(300):
        admit=RUN/(role+'-admit.json')
        if admit.exists() and read(admit)['pid']==os.getpid():break
        time.sleep(.05)
    else:raise RuntimeError('worker must be attached to its supervisor')
    import ranked_v2_league as v2
    if role=='battle':v2.train()
    elif role=='references':v2.references()
    elif role=='battle-eval':v2.blind()
    elif role=='draft':
        import ranked_draft_train as d
        d.main()                      # trains until the deadline, then freezes and runs its own blind test
    else:raise ValueError(role)

class Child:
    def __init__(self,role):
        self.job=win.required(win.create(None,None));self.proc=None
        try:
            limit=win.Extended();limit.basic.flags=0x2000      # kill the process tree with the job
            win.required(win.set_info(self.job,9,ctypes.byref(limit),ctypes.sizeof(limit)))
            scratch=RUN/'scratch'/role;scratch.mkdir(parents=True,exist_ok=True)
            env={**os.environ,'TEMP':str(scratch),'TMP':str(scratch),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1',
                 'MKL_NUM_THREADS':'1','PYTHONUTF8':'1'}
            with (RUN/(role+'.log')).open('ab') as log:
                self.proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',role],env=env,cwd=H,
                           stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000|0x00004000)  # no window, below-normal priority
            win.required(win.assign(self.job,win.handle(int(self.proc._handle))))
            write(RUN/(role+'-admit.json'),dict(pid=self.proc.pid,supervisor=os.getpid(),time=time.time()))
        except BaseException:
            if self.proc:self.proc.kill()
            win.close(self.job);raise
    def close(self):
        if self.job:win.close(self.job);self.job=None
        if self.proc:self.proc.wait(30)

def usage():
    total=0
    for folder,_,files in os.walk(RUN):
        for name in files:
            try:total+=os.stat(os.path.join(folder,name)).st_size
            except FileNotFoundError:pass
    return total

def supervise():
    assert (RUN/'ready.json').exists() and (BATTLE/'state.json').exists()
    with (RUN/'supervisor.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        if (RUN/'completion.json').exists():return
        if not (RUN/'clock.json').exists():write(RUN/'clock.json',dict(started=time.time(),train_until=END))
        children={};failures={};failed={};retry_at={};phase='训练中';used=usage();peak=used;last=0;next_measure=0
        def status():
            snap=dict(phase=phase,updated=local(time.time()),started=local(read(RUN/'clock.json')['started']),train_until=local(END),
                      pid=os.getpid(),children={k:v.proc.pid for k,v in children.items()},failures=failed,retries=failures,
                      run_bytes=used,peak_bytes=peak,run_limit=RUN_LIMIT)
            for k,p in [('battle',BATTLE/'state.json'),('battle_progress',BATTLE/'train-progress.json'),('draft',DRAFT/'status.json')]:
                if p.exists():
                    try:snap[k]=read(p)
                    except ValueError:pass
            write(RUN/'status.json',snap)
        try:
            while True:
                now=time.time()
                if time.monotonic()>=next_measure:used=usage();peak=max(peak,used);next_measure=time.monotonic()+20
                if used>=RUN_LIMIT or shutil.disk_usage(RUN).free<24*2**30:phase='磁盘保护已停止';break
                if (RUN/'STOP').exists():phase='已手动停止';break
                if now<END:
                    # NO_BATTLE (2026-11-20 21:40): battle evolution paused, its CPU goes to the deck-value corpus.
                    desired=['draft'] if (RUN/'NO_BATTLE').exists() else ['battle','draft']
                    if not MARKERS['references'].exists() and 'battle' in desired:desired.append('references')
                    for role in [r for r in children if r not in desired]:children.pop(role).close()
                else:
                    for role in ('battle','references'):
                        if role in children:children.pop(role).close()
                    if not (BATTLE/'sealed.json').exists():
                        import ranked_v2_league as v2
                        v2.freeze()
                    phase='权重已冻结，盲测中'
                    desired=[r for r in ('battle-eval','draft') if not MARKERS[r].exists()]
                    if not desired and not children:
                        phase='已完成';write(RUN/'completion.json',dict(time=local(time.time()),cutoff=local(END),run_bytes=used,peak_bytes=peak));break
                for role,ch in list(children.items()):
                    code=ch.proc.poll()
                    if code is None:continue
                    ch.close();del children[role]
                    if code or (role in MARKERS and not MARKERS[role].exists() and (role!='draft' or now>=END)):
                        failures[role]=failures.get(role,0)+1;retry_at[role]=now+min(120,failures[role]*10)
                        if failures[role]>=5:failed[role]=dict(code=code,log=role+'.log')
                for role in desired:
                    if role not in children and role not in failed and now>=retry_at.get(role,0):children[role]=Child(role)
                if desired and all(r in failed for r in desired):phase='任务失败';break
                if now-last>=20:
                    win.power(0x80000001);status();last=now
                time.sleep(2)
        except BaseException:
            phase='监督程序异常';(RUN/'failure.log').write_text(traceback.format_exc(),'utf8');raise
        finally:
            for ch in children.values():ch.close()
            children.clear();win.power(0x80000000);status()

if __name__=='__main__':
    if sys.argv[1:2]==['worker']:worker(sys.argv[2])
    else:supervise()
