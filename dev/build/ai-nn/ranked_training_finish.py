"""Complete local checks and write the reports when both bounded native trainers finish."""
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil

from ranked_draft import BATTLE,DRAFT,R,RUN,read,write
from league_data import ROOTS,local
from league_run import physical

def running(script):
    for p in psutil.process_iter(['name','cmdline']):
        args=p.info['cmdline'] or []
        if (p.info['name'] or '').lower().startswith('python') and any(Path(a).name==script for a in args):
            return True
    return False

def main():
    pending={'battle':(BATTLE,'assessment.json','zombie_special_run.py','zombie_special_review.py'),
             'draft':(DRAFT,'results.json','ranked_draft_train.py','ranked_draft_review.py')}
    attempts={k:0 for k in pending}
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'}
    last={}
    while pending:
        for name,(folder,result,trainer,reviewer) in list(pending.items()):
            if (folder/result).exists():
                with (folder/'final-audit.log').open('ab') as log:
                    subprocess.run([sys.executable,'-X','utf8',Path(__file__).with_name(reviewer)],cwd=R,env=env,stdout=log,stderr=log,check=True)
                if name=='battle':
                    from zombie_special_run import report
                    report('已完成',read(BATTLE/'clock.json'))
                last[name]=dict(complete=local(time.time()),results=result,review='review.json')
                del pending[name]
            elif not running(trainer):
                status=read(folder/'status.json') if (folder/'status.json').exists() else {}
                if (folder/'STOP').exists() or '磁盘' in status.get('phase','') or attempts[name]>=2:
                    last[name]=dict(stopped=local(time.time()),status=status)
                    del pending[name];continue
                attempts[name]+=1
                with (folder/f'recovery-{attempts[name]}.log').open('ab') as log:
                    subprocess.Popen([sys.executable,'-X','utf8','-u',Path(__file__).with_name(trainer)],
                                     cwd=R,env=env,stdout=log,stderr=log,creationflags=0x08000000)
        if pending:time.sleep(30)
    write(RUN/'completion.json',dict(tasks=last,controlled_bytes=physical(ROOTS),done=local(time.time())))

if __name__=='__main__':main()
