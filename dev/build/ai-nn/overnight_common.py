"""Bounded overnight jobs. Only this run's files count toward its 4 GiB budget."""
import datetime,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import psutil
R=Path(__file__).resolve().parents[2];H=R/'build/ai-nn'
B=R/'test_results/ai-nn-overnight-20261118'
BUILD=H/'windows-policy2-20261118';BIN=BUILD/'Release'
OLD=R/'test_results/ai-nn-dagger-20261117'
TZ=datetime.timezone(datetime.timedelta(hours=8))
DEADLINE=datetime.datetime(2026,11,18,9,tzinfo=TZ).timestamp()
FIT_END=datetime.datetime(2026,11,18,8,20,tzinfo=TZ).timestamp()
LIMIT=4*2**30;RESERVE=256*2**20;FREE_FLOOR=100*2**30
read=lambda p:json.loads(p.read_text('utf-8'))
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+f'.tmp-{os.getpid()}');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
    for attempt in range(40):
        try:os.replace(tmp,path);break
        except PermissionError:
            if attempt==39:raise
            time.sleep(.01)
def usage():
    size=0
    for base in [B,BUILD]:
        for root,_,files in os.walk(base):
            for name in files:
                try:size+=(Path(root)/name).stat().st_size
                except FileNotFoundError:pass
    return size,shutil.disk_usage(R).free
def guard(stop=DEADLINE):
    stop=min(stop,DEADLINE-10)
    if time.time()>=stop:raise RuntimeError('TIME_LIMIT')
    used,free=usage();p=B/'disk.json'
    own=B/f'disk-{os.getpid()}.json'
    old=read(own) if own.exists() else (read(p) if p.exists() else {})
    record=dict(checked_at=datetime.datetime.now(TZ).isoformat(),new_bytes=used,new_bytes_peak=max(used,old.get('new_bytes_peak',0)),
        free_bytes=free,minimum_free_bytes=min(free,old.get('minimum_free_bytes',free)),cap_bytes=LIMIT,reserve_bytes=RESERVE,free_floor_bytes=FREE_FLOOR,
        roots=[str(B),str(BUILD)],deadline='2026-11-18T09:00:00+08:00')
    write(own,record);write(p,record)
    if time.time()>=stop:raise RuntimeError('TIME_LIMIT')
    if (B/'STOP').exists():raise RuntimeError('USER_STOP_FILE')
    if used>LIMIT-RESERVE or free<FREE_FLOOR:raise RuntimeError('DISK_LIMIT')
def kill_owned(proc):
    try:
        root=psutil.Process(proc.pid);children=root.children(recursive=True)
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        root.terminate();psutil.wait_procs([*children,root],timeout=3)
        for p in [*children,root]:
            try:
                if p.is_running():p.kill()
            except psutil.NoSuchProcess:pass
    except psutil.NoSuchProcess:pass
def command(name,args,stop=DEADLINE):
    stop=min(stop,DEADLINE-10)
    guard(stop);start=time.monotonic();p=B/(name+'.log');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('wb') as f:
        proc=subprocess.Popen([str(a) for a in args],cwd=R,stdout=f,stderr=subprocess.STDOUT,creationflags=0x08004000)
        try:
            while proc.poll() is None:
                guard(stop);time.sleep(min(5,max(.001,stop-time.time())))
            if proc.returncode:raise RuntimeError(f'{name}: exit {proc.returncode}; see {p}')
        except BaseException:
            kill_owned(proc);raise
    return dict(name=name,wall_seconds=time.monotonic()-start,log=str(p))
def delete_temporary_file(path):
    path=path.resolve();root=(B/'tmp').resolve()
    if root not in path.parents or not path.is_file():raise RuntimeError('Cleanup refused outside the temporary files directory')
    path.unlink()
