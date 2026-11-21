"""Unattended r4 continuation with a common wall-clock cutoff, owned process trees, and morning evaluation."""
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

from ranked_night_native import OUT as STAGING,PREVIOUS,WORK,R,read,write,sha
os.environ['PVZ_RANKED_PROFILE']=os.getenv('PVZ_NIGHT_CONFIG',str(STAGING/'profile.json'))
from ranked_draft import BATTLE,DRAFT,PROFILE
OUT=Path(PROFILE['output'])
from league_data import ROOTS,TOTAL_LIMIT,local
import league_run as win

END=PROFILE['deadline']
MARKERS={'references':BATTLE/'reference-cache.json','battle-eval':BATTLE/'assessment.json',
         'draft-eval':DRAFT/'results.json','battle-review':BATTLE/'review.json','draft-review':DRAFT/'morning-complete.json'}

def worker(role):
    for _ in range(300):
        admit=OUT/(role+'-admit.json')
        if admit.exists() and read(admit)['pid']==os.getpid():break
        time.sleep(.05)
    else:raise RuntimeError('worker must be attached to its supervisor')
    if role in ('battle','references','battle-eval'):
        if PROFILE.get('day_league'):
            import ranked_day_league as day
            {'battle':day.train,'references':day.references,'battle-eval':day.blind}[role]()
            return
        import zombie_special_train as z
        if role=='battle':z.train()
        elif role=='references':z.fixed_blind_references()
        else:z.blind()
    elif role in ('draft','draft-eval'):
        import ranked_draft_train as d
        d.main()
    elif role=='battle-review':
        if PROFILE.get('day_league'):
            from ranked_day_league import report
            report();return
        from zombie_special_run import report
        from zombie_special_review import review
        review();report('已完成',read(BATTLE/'clock.json'))
    elif role=='draft-review':
        import ranked_draft_joint,ranked_draft_probe,ranked_draft_review
        ranked_draft_joint.main();ranked_draft_probe.main();ranked_draft_review.review()
        write(MARKERS[role],dict(time=local(time.time()),frozen=sha(DRAFT/'frozen.npz'),joint=sha(DRAFT/'joint.json')))
    else:raise ValueError(role)

class Child:
    def __init__(self,role):
        self.job=win.required(win.create(None,None));self.proc=None
        try:
            limit=win.Extended();limit.basic.flags=0x2000
            win.required(win.set_info(self.job,9,ctypes.byref(limit),ctypes.sizeof(limit)))
            scratch=OUT/'scratch'/role;scratch.mkdir(parents=True,exist_ok=True)
            env={**os.environ,'TEMP':str(scratch),'TMP':str(scratch),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONUTF8':'1'}
            with (OUT/(role+'.log')).open('ab') as log:
                self.proc=subprocess.Popen([sys.executable,'-X','utf8','-u',__file__,'worker',role],env=env,cwd=R,
                           stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000)
            win.required(win.assign(self.job,win.handle(int(self.proc._handle))))
            write(OUT/(role+'-admit.json'),dict(pid=self.proc.pid,supervisor=os.getpid(),time=time.time()))
        except BaseException:
            if self.proc:self.proc.kill()
            win.close(self.job);raise
    def close(self):
        if self.job:win.close(self.job);self.job=None
        if self.proc:self.proc.wait(20)

def seal():
    if PROFILE.get('day_league'):
        from ranked_day_league import freeze
        freeze()
    if not (BATTLE/'sealed.json').exists():
        st=read(BATTLE/'state.json');models={'擂主':st['champion']}
        if st.get('research') and st['research']!=st['champion']:models['研究候选']=st['research']
        write(BATTLE/'sealed.json',dict(time=local(time.time()),cutoff=local(END),round=st['round'],models=models,
              hashes={k:sha(Path(p)) for k,p in models.items()},fixture_sha=sha(BATTLE/'fixtures.json'),
              playable_fixture_sha=sha(BATTLE/'playable.json')))
    if not (DRAFT/'cutoff.json').exists():
        with sqlite3.connect(DRAFT/'draft.sqlite') as db:
            row=db.execute('select id,weights from checkpoints order by id desc limit 1').fetchone()
            if not row:raise RuntimeError('draft trainer has no committed weights')
            part=DRAFT/'frozen.partial';part.write_bytes(row[1]);os.replace(part,DRAFT/'frozen.npz')
        digest=sha(DRAFT/'frozen.npz')
        write(DRAFT/'freeze.json',dict(actual=local(time.time()),epoch=row[0],sha256=digest))
        write(DRAFT/'cutoff.json',dict(cutoff=local(END),completed=row[0],sha=digest))

def summary():
    if PROFILE.get('day_league'):
        st=read(BATTLE/'sealed.json');draft=read(DRAFT/'results.json');review=read(DRAFT/'review.json')
        lines=['# 白天家院七槽晨测','',f"北京时间 {local(END)} 冻结。共完成 {st['round']} 轮双方擂主变异。",'']
        for s,label in [('plant','植物'),('zombie','僵尸')]:
            e=st['sides'][s];dr=draft['blind'][s];w=dr['transitions']
            lines.append(f"- {label}局内擂主晋级 {e['promotions']} 次，最终温度 {e['temp']}。选卡头独立复测 {dr['pairs']} 组，保住 {w.get('WW',0)}/{sum(v for k,v in w.items() if k[0]=='W')} 个旧胜，旧败转真胜 {w.get('LW',0)} 个。")
        lines+=['',f"选卡训练完成 {draft['attempts']} 组同前缀对照，其中 {draft['unstartable']} 组未进入实战。",'',
                (BATTLE/'双擂主晨测.md').read_text('utf8').partition('\n')[2],
                '[分对手实战结果](battle/review.json) · [选卡复盘](draft/选卡复盘.md) · [双方选卡交叉复测](draft/joint.json)']
        (OUT/'晨测结果.md').write_text('\n'.join(lines)+'\n','utf8')
        return
    s=read(BATTLE/'state.json');report=read(BATTLE/'assessment.json');d=read(DRAFT/'results.json')
    lines=['# 家院胜率七槽晨测','',f"本轮于 {local(END)} 截止。游戏版本 {PROFILE['version']}，僵尸局内完成 {s['round']} 轮，晋级 {s['promotions']} 次。",'',
           '| 僵尸候选 | 同阵营基线 | 基线胜/未决/负 | 候选胜/未决/负 | 保住旧胜 | 旧败真胜 | 出兵/分 |','|---|---|---|---|---:|---:|---|']
    for k,v in report.items():
        for n,label in [('r22','r22'),('previous_candidate','上次冻结候选'),('night','历史僵尸强头')]:
            r=v[n];a,b=r['rates']['troops']
            lines.append(f"| {k} | {label} | {r['old']} | {r['new']} | {r['kept']}/{r['old'][0]} | {r['gain']}/{r['old'][2]} | {a:.2f} → {b:.2f} |")
    lines+=['',f"双方选卡训练共提交 {d['attempts']} 组对照，其中 {d['unstartable']} 组未进入战斗。每次只换一方选卡头，对照为同局面上次冻结权重。",'',
           '| 选卡方 | 有效对照 | 旧败转胜 | 丢掉旧胜 | 双方共同存活期间实际出兵/分 |','|---|---:|---:|---:|---|']
    for k,v in d['blind'].items():
        w=v['transitions'];a,b=v['troops_per_minute']
        lines.append(f"| {k} | {v['pairs']} | {w.get('LW',0)} | {w.get('WL',0)+w.get('WT',0)} | {a:.2f} → {b:.2f} |")
    lines+=['','[局内训练及复测](battle/特训结果.md) · [选卡复盘与环境测试](draft/选卡复盘.md) · [四种权重组合](draft/joint.json)']
    (OUT/'晨测结果.md').write_text('\n'.join(lines)+'\n','utf8')

def supervise():
    assert (OUT/'ready.json').exists()
    with (OUT/'supervisor.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        if (OUT/'completion.json').exists():return
        clock=BATTLE/'clock.json'
        if not clock.exists():write(clock,dict(started=time.time(),train_until=END,slots=6 if PROFILE.get('day_league') else 5))
        children={};failures={};failed={};phase='训练中';retried_at={}
        previous_tools=R/'build/pvp73-tools/build'
        earlier=sum(max(4096,((p.stat().st_size+4095)//4096)*4096) for p in previous_tools.rglob('*') if
                    p.is_file() and any(n in str(p.relative_to(previous_tools)) for n in ('ranked_draft_room','ranked_secret_effects')))
        # Historic runs and the native build are frozen. Measure their NTFS allocation once.
        # Count the mutable run separately at least every 20s, including in-flight raw traces.
        def run_usage():
            if not PROFILE.get('day_league'):return win.disk_bytes(OUT)
            # This isolated tree has no hardlinks and inherits NTFS compression.
            compressed=ctypes.windll.kernel32.GetCompressedFileSizeW
            compressed.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
            compressed.restype=ctypes.c_ulong
            total=0
            for folder,_,files in os.walk(OUT):
                for name in files:
                    p=os.path.join(folder,name);hi=ctypes.c_ulong()
                    lo=compressed(p,ctypes.byref(hi))
                    if lo==0xffffffff:
                        try:size=os.stat(p).st_size
                        except FileNotFoundError:continue
                    else:size=(hi.value<<32)+lo
                    total+=max(4096,((size+4095)//4096)*4096)
            return total
        initial_run=run_usage();run_size=initial_run
        previous=read(OUT/'status.json') if (OUT/'status.json').exists() else {}
        if PROFILE.get('day_league') and not previous:
            receipt=read(STAGING/'status.json')
            assert receipt['phase']=='已手动停止' and not receipt['children'] and receipt['disk_ceiling']==TOTAL_LIMIT
            baseline=receipt['controlled_bytes']+initial_run+8*2**20
        elif previous.get('phase')=='已手动停止' and time.time()-(OUT/'status.json').stat().st_mtime<60:
            baseline=previous['controlled_bytes']+max(0,initial_run-previous['run_bytes'])+16*2**20
        else:baseline=win.physical([*ROOTS,WORK])+earlier
        used=baseline;peak=used;next_measure=time.monotonic()+15;last_status=0
        def status():
            snap=dict(phase=phase,updated=local(time.time()),started=local(read(clock)['started']),train_until=local(END),pid=os.getpid(),
                 children={k:v.proc.pid for k,v in children.items()},failures=failed,retries=failures,controlled_bytes=used,peak_bytes=peak,
                 disk_ceiling=TOTAL_LIMIT,run_bytes=run_size)
            for k,p in [('battle',BATTLE/'state.json'),('battle_progress',BATTLE/'train-progress.json'),('draft',DRAFT/'status.json')]:
                if p.exists():snap[k]=read(p)
            write(OUT/'status.json',snap)
        try:
            while True:
                now=time.time()
                if time.monotonic()>=next_measure:
                    run_size=run_usage()
                    used=baseline+max(0,run_size-initial_run);peak=max(used,peak)
                    next_measure=time.monotonic()+15
                if used>=TOTAL_LIMIT-48*2**20 or shutil.disk_usage(OUT).free<24*2**30:
                    phase='磁盘保护已停止';break
                if (OUT/'STOP').exists():phase='已手动停止';break
                if now<END:
                    desired=['battle','draft']
                    if not MARKERS['references'].exists():desired.append('references')
                else:
                    for role in ('battle','draft','references'):
                        if role in children:children.pop(role).close()
                    phase='权重已冻结，晨测中';seal()
                    desired=[]
                    for ev,review in [('battle-eval','battle-review'),('draft-eval','draft-review')]:
                        if not MARKERS[ev].exists():desired.append(ev)
                        elif not MARKERS[review].exists():desired.append(review)
                    if not desired and all(c.proc.poll() is not None for c in children.values()):
                        summary();phase='已完成'
                        write(OUT/'completion.json',dict(time=local(time.time()),cutoff=local(END),disk_bytes=used,peak_bytes=peak));break
                for role,ch in list(children.items()):
                    code=ch.proc.poll()
                    if code is None:continue
                    ch.close();del children[role]
                    if code or (role in MARKERS and not MARKERS[role].exists()):
                        failures[role]=failures.get(role,0)+1
                        retried_at[role]=now+min(60,failures[role]*4)
                        if failures[role]>=4:failed[role]=dict(code=code,log=role+'.log')
                for role in desired:
                    if role not in children and role not in failed and now>=retried_at.get(role,0):children[role]=Child(role)
                if not children and desired and all(r in failed for r in desired):phase='任务失败';break
                if now-last_status>=20:
                    ac=(ctypes.c_ubyte*12)()
                    if win.power_status(ac):win.power(0x80000001 if ac[0]==1 else 0x80000000)
                    status();last_status=now
                time.sleep(min(2,max(.02,END-time.time())) if now<END else 2)
        except BaseException:
            phase='监督程序异常';(OUT/'failure.log').write_text(traceback.format_exc(),'utf8');raise
        finally:
            for ch in children.values():ch.close()
            children.clear();win.power(0x80000000);status()

if __name__=='__main__':
    if sys.argv[1:2]==['worker']:worker(sys.argv[2])
    else:supervise()
