"""Detached watchdog, bounded storage and morning report for the home-map league."""
import ctypes
from ctypes import wintypes
import json
import msvcrt
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

from league_evolve import initial,state,round_worker,blind_worker,freeze
from league_data import RUN,R,H,TZ,END,SEAL,GIB,TOTAL_LIMIT,RUN_LIMIT,ROOTS,NEW,OLD_CORPUS,check_inputs,local,read,write,sha
from switch_fit import allocated

class Limit(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',wintypes.DWORD),
              ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',wintypes.DWORD),
              ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]

class Extended(ctypes.Structure):
    _fields_=[('basic',Limit),('io',ctypes.c_ulonglong*6),('memory',ctypes.c_size_t*4)]

K=ctypes.WinDLL('kernel32',use_last_error=True)
def api(name,args,ret):
    fn=getattr(K,name);fn.argtypes=args;fn.restype=ret;return fn
handle=wintypes.HANDLE
create=api('CreateJobObjectW',[ctypes.c_void_p,wintypes.LPCWSTR],handle)
set_info=api('SetInformationJobObject',[handle,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD],wintypes.BOOL)
assign=api('AssignProcessToJobObject',[handle,handle],wintypes.BOOL)
close=api('CloseHandle',[handle],wintypes.BOOL)
power=api('SetThreadExecutionState',[wintypes.DWORD],wintypes.DWORD)
power_status=api('GetSystemPowerStatus',[ctypes.c_void_p],wintypes.BOOL)

def required(ok):
    if not ok:raise ctypes.WinError(ctypes.get_last_error())
    return ok

class Child:
    def __init__(self,role,jobs):
        self.role=role;self.jobs=jobs
        self.job=required(create(None,None));self.proc=None
        limits=Extended();limits.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            required(set_info(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)))
            scratch=RUN/'scratch'/role
            for d in [scratch/'temp',scratch/'games']:
                d.mkdir(parents=True,exist_ok=True)
                for p in d.iterdir():
                    if p.is_file() and p.parent.resolve()==d.resolve() and p.name.endswith(('.jsonl','.partial','.jsonl.gz','.receipt.json')):
                        p.unlink()
            log=RUN/(role+'-worker.log')
            if log.exists() and log.stat().st_size>256*1024:os.replace(log,log.with_suffix('.previous.log'))
            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONUTF8':'1',
                 'TEMP':str(scratch/'temp'),'TMP':str(scratch/'temp')}
            with log.open('ab') as stream:
                self.proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',role,str(jobs)],
                    env=env,cwd=R,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08000000)
            required(assign(self.job,handle(int(self.proc._handle))))
            write(RUN/f'admit-{role}.json',dict(pid=self.proc.pid,supervisor=os.getpid(),issued=time.time()))
        except BaseException:
            if self.proc and self.proc.poll() is None:self.proc.kill()
            close(self.job);raise
    def stop(self):
        if self.job:close(self.job);self.job=None
        if self.proc:self.proc.wait(timeout=15)

def disk_bytes(folder):
    # Conservative allocation estimate for this run; the global baseline uses native NTFS allocation.
    total=0
    for base,_,files in os.walk(folder):
        for name in files:
            try:total+=max(4096,((os.stat(os.path.join(base,name)).st_size+4095)//4096)*4096)
            except FileNotFoundError:pass
    return total

def physical(dirs):
    for attempt in range(4):
        try:return allocated(dirs)
        except (FileNotFoundError,PermissionError):
            if attempt==3:raise
            time.sleep(.1)

def total_games():
    p=RUN/'matches.sqlite'
    if not p.exists():return 0
    con=sqlite3.connect(p,timeout=2)
    try:return con.execute('select count(*) from games').fetchone()[0]
    except sqlite3.OperationalError:return 0
    finally:con.close()

def status(reason,children,usage,base,peak,errors,started):
    st=state();now=time.time()
    report=dict(status=reason,updated=local(now),start=started,deadline=local(END),blind_freeze=local(SEAL),
         supervisor=os.getpid(),workers={r:dict(pid=w.proc.pid,slots=w.jobs) for r,w in children.items()},
         completed_rounds=st.get('completed_rounds',0),round_cursor=st['round'],completed_native_games=total_games(),
         run_bytes_estimate=usage,controlled_bytes_estimate=base+usage,run_peak_estimate=peak,
         total_limit=TOTAL_LIMIT,run_limit=RUN_LIMIT,retries=errors)
    write(RUN/'status.json',report)
    title='家院夜训运行与结果'
    lines=['# '+title,'',f"状态 **{reason}**。更新时间 {report['updated']}，停止时间 {local(END)}。",
           '',f"已完整提交 {report['completed_rounds']} 轮，已保存 {report['completed_native_games']} 场去重原生对局。"
              f"本任务估算占用 {usage/2**20:.1f} MiB，含既有受控训练数据约 {(base+usage)/GIB:.3f} GiB。",'',
           '| 阵营 | 擂主 | 晋级次数 | 有效守擂轮数 | 当前温度 |','|---|---|---:|---:|---:|']
    for side,title in [('zombie','僵尸'),('plant','植物')]:
        s=st['sides'][side];p=Path(s['champ'])
        lines.append(f"| {title} | [{p.name}]({os.path.relpath(p,RUN).replace(chr(92),'/')}) | {s['promotions']} | {s['defenses']} | {s['temp']:.3f} |")
    if st.get('last'):
        lines+=['','最近完整一轮的独立对照如下。每格依次为胜、未决、负。','',
                '| 阵营 | 擂主 | 挑战者 | 旧败转胜 | 旧胜丢失 | 本方每分钟部署 |','|---|---|---|---:|---:|---|']
        for s,title in [('zombie','僵尸'),('plant','植物')]:
            a=st['last']['validation'][s];rate=a['rates']['troops' if s=='zombie' else 'plant']
            lines.append(f"| {title} | {a['old']} | {a['new']} | {a['gain']} | {a['lost']} | {rate[0]:.2f} → {rate[1]:.2f} |")
    p=RUN/'blind-progress-results.json'
    if p.exists():
        b=read(p);lines+=['',f"晨测冻结于第 {b['round']} 轮。每项含 24 个新开局，对 r22、H 和 B 各 24 局。"
                   '冻结后的训练轮次单独记入上表。晨测结果不参与选模。','',
                   '| 阵营与模型 | 对照胜/未决/负 | 实测胜/未决/负 | 保住旧胜 | 旧败转胜 | 败转超时续局（胜/未决/负） | 两批真胜增量 |',
                   '|---|---|---|---:|---:|---|---|']
        for key,a in b['completed'].items():
            side,mode=key.split('-');label={'zombie':'僵尸','plant':'植物'}[side]+{'champ':'擂主对固定基线','explorer':'探索头对固定基线','start':'擂主对起训模型'}[mode]
            raw=RUN/'blind'/(key+'.json.gz')
            import gzip
            with gzip.open(raw,'rt',encoding='utf8') as f:details=json.load(f)
            ext=[r['late']['value'] for r in details['rows'] if r['old']==-1 and r['late']]
            lines.append(f"| {label} | {a['old']} | {a['new']} | {a['kept']}/{a['old'][0]} | {a['gain']} | {[ext.count(x) for x in (1,0,-1)]} | {a['cohorts']} |")
    elif reason not in ('训练中','启动中'):
        lines+=['','晨测尚无完成的对照组。']
    lines+=['','[运行状态](status.json) · [配置与输入指纹](config.json) · [训练种子与封存开局](fixtures.json)']
    out=RUN/'夜训进度与晨测.md';tmp=out.with_suffix('.tmp')
    tmp.write_text('\n'.join(lines)+'\n','utf8');os.replace(tmp,out)

def checkpoint_db():
    if not (RUN/'matches.sqlite').exists():return
    con=sqlite3.connect(RUN/'matches.sqlite',timeout=8)
    try:con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:con.close()

def supervisor():
    RUN.mkdir(exist_ok=True)
    with (RUN/'supervisor.lock').open('a+b') as lock:
        if lock.tell()==0:lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        if time.time()>=END:return
        inputs=check_inputs();fixtures=read(RUN/'fixtures.json')
        assert fixtures['previous']==sha(OLD_CORPUS/'index.json') and fixtures['fresh']==sha(NEW/'index.json')
        config=RUN/'config.json'
        if not config.exists():write(config,dict(inputs=inputs,started=local(time.time()),stop=local(END),seal=local(SEAL),
            cap_bytes=TOTAL_LIMIT,new_cap=RUN_LIMIT,free_floor_bytes=24*GIB,concurrency=8,mutants_per_side=4,
            learning='Four mutations per side, full cross-play, r22 and rotating history. Both challengers confirmed on independent cases against frozen lineups before simultaneous replacement. Separate explorers. Anneal fraction and amplitude by .72 after three distinct genuine defenses.',
            final='Freeze both champions and explorers at 08:00 for two unused 12-opening home cohorts versus r22/H/B. Continue independent training until 09:00. Retain all committed genomes and summaries; stop before reaching quota.'))
        else:assert read(config)['inputs']==inputs and read(config)['stop']==local(END)
        if not (RUN/'state.json').exists():write(RUN/'state.json',initial())
        children={};base=physical(ROOTS)-physical([RUN]);peak=0;start=read(config)['started']
        errors={'train':0,'blind':0};next_try={s:0 for s in errors};last_gauge=0;next_global=0;reason='启动中'
        usage=disk_bytes(RUN)
        try:
            status(reason,children,usage,base,peak,errors,start)
            while time.time()<END:
                now=time.time()
                if (RUN/'STOP').exists():reason='已手动停止';break
                for role,ch in list(children.items()):
                    code=ch.proc.poll()
                    if code is None:continue
                    ch.stop();del children[role]
                    if code==0:errors[role]=0;next_try[role]=0
                    else:
                        errors[role]+=1;next_try[role]=now+min(60,3*errors[role])
                        if role=='train' and errors[role]%3==0:
                            s=state();n=s['round']+1
                            write(RUN/'failed'/f'{n:04d}.json',dict(round=n,reason='three worker failures',time=local(now)))
                            s['round']=n;write(RUN/'state.json',s)
                if now>=next_global:
                    try:base=physical(ROOTS)-physical([RUN])
                    except (FileNotFoundError,PermissionError):pass
                    next_global=now+180
                usage=disk_bytes(RUN);peak=max(usage,peak)
                if usage>=RUN_LIMIT-64*2**20 or base+usage>=TOTAL_LIMIT-128*2**20 or shutil.disk_usage(RUN).free<24*GIB:
                    reason='磁盘保护已停止';break
                if now>=SEAL and not (RUN/'frozen.json').exists():
                    if 'train' in children:children.pop('train').stop()
                    freeze()
                testing=(RUN/'frozen.json').exists() and not (RUN/'blind-results.json').exists()
                if testing and 'blind' not in children and now>=next_try['blind']:
                    children['blind']=Child('blind',4 if now<END-900 else 8)
                # Reserve the final 15 minutes for an unfinished blind suite.
                if testing and now>=END-900:
                    if 'train' in children:children.pop('train').stop()
                elif 'train' not in children and now>=next_try['train'] and now<END-30:
                    children['train']=Child('train',4 if testing else 8)
                if now-last_gauge>=12:
                    ac=(ctypes.c_ubyte*12)()
                    if power_status(ac):power(0x80000001 if ac[0]==1 else 0x80000000)
                    status('训练与封存晨测中' if testing else '训练中',children,usage,base,peak,errors,start);last_gauge=now
                time.sleep(min(2,max(0,END-time.time())))
            else:reason='已到时停止'
        except BaseException:
            reason='监督程序异常';(RUN/'supervisor-error.log').write_text(traceback.format_exc(),'utf8');raise
        finally:
            for child in children.values():child.stop()
            children.clear();power(0x80000000);checkpoint_db()
            # Drop interrupted native working files; committed rows and evidence samples are retained.
            for role in ('train','blind'):
                for sub in ('temp','games'):
                    d=RUN/'scratch'/role/sub
                    if d.exists():
                        for p in d.iterdir():
                            if p.is_file() and p.parent.resolve()==d.resolve() and p.name.endswith(('.jsonl','.partial','.jsonl.gz','.receipt.json')):p.unlink()
            usage=disk_bytes(RUN)
            status(reason,children,usage,base,peak,errors,start)

def worker(role,jobs):
    entry=RUN/f'admit-{role}.json'
    start=time.monotonic()
    while time.monotonic()-start<15:
        if entry.exists() and read(entry)['pid']==os.getpid():break
        time.sleep(.1)
    else:raise RuntimeError('Worker did not enter supervised Windows job')
    if time.time()>=END:return
    (round_worker if role=='train' else blind_worker)(jobs)

if __name__=='__main__':
    if sys.argv[1:2]==['worker']:worker(sys.argv[2],int(sys.argv[3]))
    else:supervisor()
