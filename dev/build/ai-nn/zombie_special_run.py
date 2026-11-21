"""Own the two-hour compute budget, stop the training process tree, then evaluate the frozen heads."""
import concurrent.futures
import ctypes
import msvcrt
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

import league_run as win
from league_data import ROOTS, TOTAL_LIMIT, local, check_inputs
from ranked_special_setup import OUT,EXE,R,read,write,sha

def count():
    db=OUT/'matches.sqlite'
    if not db.exists():return 0
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
        try:return c.execute('select count(*) from games').fetchone()[0]
        except sqlite3.OperationalError:return 0

def report(phase,cfg):
    st=read(OUT/'state.json') if (OUT/'state.json').exists() else {}
    lines=['# 家院僵尸特训','',f"状态为 **{phase}**。训练从 {local(cfg['started'])} 至 {local(cfg['train_until'])}。",'',
           f"训练已提交 {st.get('round',0)} 轮，晋级 {st.get('promotions',0)} 次，当前有 {count()} 场去重原生对局（含同局面分支及评估）。",
           '','固定植物为现任家院植物 away、历史 H、旧植物 across。r22 植物另作参考，历史 B 加入终测。']
    if (OUT/'assessment.json').exists():
        results=read(OUT/'assessment.json')
        lines+=['','48 个独立家院开局含 24 个自由轮选和 24 个参考历史可战牌组的轮选，各打五个固定对手。胜、未决和负按 600 秒时限统计。出兵频率取两条路线共同存活的窗口，墓碑单列。','',
                '| 冻结权重 | 同阵营基线 | 基线胜/未决/负 | 实测胜/未决/负 | 旧胜保留 | 旧败转胜 | 两批增胜 | 出兵/分 | 局长（秒） |',
                '|---|---|---|---|---:|---:|---|---|---|']
        for role,ar in results.items():
            for k in ('r22','night'):
                v=ar[k];speed=v['rates']['troops'];end=v['seconds']
                lines.append(f"| {role} | {k} | {v['old']} | {v['new']} | {v['kept']}/{v['old'][0]} | {v['gain']}/{v['old'][2]} | {v['cohorts']} | {speed[0]:.2f} → {speed[1]:.2f} | {end[0]:.1f} → {end[1]:.1f} |")
        lines+=['','| 留出同阵营 r22 对照 | 植物 | r22 僵尸胜/未决/负 | 特训僵尸胜/未决/负 |','|---|---|---|---|']
        opps=read(OUT/'opponents.json')['pool']
        for role,ar in results.items():
            for o,(old,new) in ar['r22']['by'].items():
                label=next((n for n,p in opps.items() if p==o),Path(o).stem)
                lines.append(f'| {role} | {label} | {old} | {new} |')
            reg=ar['regression']
            late=[v['late']['value'] for v in ar['r22']['rows'] if v['old']==-1 and v['late']]
            lines+=['',f"{role} 在胜率七槽训练配对中，守住 {reg['kept']}/{reg['old'][0]} 个 r22 旧胜，在 {reg['old'][2]} 个旧败中打赢 {reg['gain']} 个。新开局旧败转超时续到 1,200 秒，共 {len(late)} 场，分别为 {late.count(1)} 胜、{late.count(0)} 未决、{late.count(-1)} 负。",'']
        lines+=['[逐场结果](assessment.json) · [冻结权重](sealed.json) · [对手与训练旧局](opponents.json)']
    (OUT/'特训结果.md').write_text('\n'.join(lines)+'\n','utf8')

class Worker:
    def __init__(self,role):
        self.job=win.required(win.create(None,None));self.proc=None
        try:
            limits=win.Extended();limits.basic.flags=0x2000
            win.required(win.set_info(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)))
            temp=OUT/'scratch'/role/'temp';temp.mkdir(exist_ok=True,parents=True)
            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
                 'TEMP':str(temp),'TMP':str(temp),'PYTHONUTF8':'1'}
            with (OUT/(role+'.log')).open('ab') as log:
                self.proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',role],
                    env=env,cwd=R,creationflags=0x08000000,stdout=log,stderr=log,stdin=subprocess.DEVNULL)
            win.required(win.assign(self.job,win.handle(int(self.proc._handle))))
            write(OUT/(role+'-admit.json'),dict(pid=self.proc.pid))
        except BaseException:
            if self.proc:self.proc.kill()
            win.close(self.job);self.job=None;raise
    def close(self):
        if self.job:win.close(self.job);self.job=None
        if self.proc:self.proc.wait(timeout=25)

def supervisor():
    import zombie_special_train as z
    with (OUT/'run.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        if (OUT/'assessment.json').exists():return
        if not (OUT/'clock.json').exists():
            assert check_inputs()==read(z.NIGHT/'config.json')['inputs']
            assert sha(EXE)==read(OUT/'build.json')['binary']
            now=time.time();write(OUT/'clock.json',dict(started=now,train_until=now+7200,slots=z.JOBS,limit=640*2**20,global_limit=TOTAL_LIMIT))
        cfg=read(OUT/'clock.json')
        phase='训练中';worker=None;role=None;usage=0;peak=0;tries=0;next_report=0
        base=read(z.NIGHT/'status.json')['controlled_bytes_estimate']
        executor=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        def measure_base():return win.physical(ROOTS)-win.physical([OUT])
        gauge=executor.submit(measure_base);next_gauge=time.time()+600
        def status():
            write(OUT/'status.json',dict(phase=phase,updated=local(time.time()),started=local(cfg['started']),stop_training=local(cfg['train_until']),
                  games=count(),run_bytes=usage,peak_bytes=peak,total_estimate=base+usage,worker=worker.proc.pid if worker else None))
            report(phase,cfg)
        try:
            while True:
                now=time.time()
                if gauge and gauge.done():
                    try:base=gauge.result()
                    except (FileNotFoundError,PermissionError):pass
                    gauge=None
                if not gauge and now>=next_gauge:gauge=executor.submit(measure_base);next_gauge=now+600
                usage=win.disk_bytes(OUT);peak=max(peak,usage)
                if usage>cfg['limit']-32*2**20 or base+usage>TOTAL_LIMIT-128*2**20 or shutil.disk_usage(OUT).free<24*2**30:
                    phase='磁盘保护停止';break
                if (OUT/'STOP').exists():phase='已手动停止';break
                desired='train' if now<cfg['train_until'] else 'blind'
                if desired!=role and worker:worker.close();worker=None;tries=0
                if desired=='blind' and not (OUT/'sealed.json').exists():
                    st=read(OUT/'state.json');models={'擂主':st['champion']}
                    if st['research'] and st['research']!=st['champion']:models['研究候选']=st['research']
                    if len(models)==1 and not st['research'] and st['round']:
                        alt=read(OUT/'rounds'/f"{st['round']:03d}.json")['challenger']
                        if alt!=st['champion']:models['研究候选']=alt
                    write(OUT/'sealed.json',dict(time=local(now),round=st['round'],models=models,
                          hashes={k:sha(Path(p)) for k,p in models.items()},fixture_sha=sha(OUT/'fixtures.json')))
                if desired=='blind' and (OUT/'assessment.json').exists():phase='已完成';break
                if worker and worker.proc.poll() is not None:
                    code=worker.proc.returncode;worker.close();worker=None
                    if code:
                        tries+=1
                        if tries>=3:raise RuntimeError(f'{desired} worker failed three times; inspect {desired}.log')
                        time.sleep(2*tries)
                if not worker:
                    role=desired;phase='训练中' if role=='train' else '权重已冻结，独立终测中'
                    worker=Worker(role);next_report=0
                if now>=next_report:
                    ac=(ctypes.c_ubyte*12)()
                    if win.power_status(ac):win.power(0x80000001 if ac[0]==1 else 0x80000000)
                    status();next_report=now+20
                time.sleep(min(2,max(.1,cfg['train_until']-now)) if desired=='train' else 2)
        except BaseException:
            phase='监督程序异常';(OUT/'failure.log').write_text(traceback.format_exc(),'utf8');raise
        finally:
            if worker:worker.close();worker=None
            win.power(0x80000000)
            if (OUT/'matches.sqlite').exists():
                with sqlite3.connect(OUT/'matches.sqlite',timeout=15) as db:db.execute('pragma wal_checkpoint(truncate)')
            usage=win.disk_bytes(OUT);status();executor.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__':
    if sys.argv[1:2]==['worker']:
        role=sys.argv[2]
        for _ in range(200):
            p=OUT/(role+'-admit.json')
            if p.exists() and read(p)['pid']==os.getpid():break
            time.sleep(.05)
        else:raise RuntimeError('unsupervised worker')
        from zombie_special_train import train,blind
        (train if role=='train' else blind)()
    else:supervisor()
