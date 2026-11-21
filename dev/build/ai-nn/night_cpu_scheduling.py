"""Let Windows place the existing bounded workers across available cores."""
import argparse
from overnight_common import *

ap=argparse.ArgumentParser();ap.add_argument('--study',choices=['main','supplement'],required=True);args=ap.parse_args()
expected=H/('overnight_run.py' if args.study=='main' else 'night_supplement_run.py')
roots=[];started=datetime.datetime.fromisoformat(read(B/'plan.json')['started_at']).timestamp()
for p in psutil.process_iter(['name','pid']):
    if not p.info['name'].lower().startswith('python'):continue
    try:
        if p.create_time()<started:continue
        if any(Path(a).resolve()==expected.resolve() for a in p.cmdline() if a.endswith('.py')):roots.append(p)
    except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):pass
assert len(roots)==1, [p.pid for p in roots]
target=B/f'cpu-scheduling-{args.study}.json';assert not target.exists()
root=roots[0];all_cores=list(range(psutil.cpu_count()));records=[]
for p in [root,*root.children(recursive=True)]:
    try:
        before=p.cpu_affinity();p.cpu_affinity(all_cores)
        records.append(dict(pid=p.pid,name=p.name(),before=before,after=p.cpu_affinity(),priority=int(p.nice())))
    except psutil.NoSuchProcess:pass
write(target,dict(changed_at=datetime.datetime.now(TZ).isoformat(),study=args.study,root_pid=root.pid,
    purpose='Remove artificial placement restriction; worker count remains four games or two main fit threads. Windows may schedule those workers across the machine.',
    simulation_or_model_changes=False,processes=records))
print(json.dumps(dict(study=args.study,processes=len(records),allowed_logical_cores=len(all_cores))))
