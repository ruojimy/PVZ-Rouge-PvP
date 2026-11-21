"""Exercise real stop paths in an isolated subdirectory, without filling the disk."""
import sys,time,argparse,subprocess
import overnight_common as c
ap=argparse.ArgumentParser();ap.add_argument('--label',default='guard-check');args=ap.parse_args()
assert args.label.replace('-','').isalnum()
base=c.B;c.B=base/args.label;c.B.mkdir();c.BUILD=base/(args.label+'-build')
(c.B/'fixture').write_bytes(b'xx')
def rejects(expected,fn):
    try:fn()
    except RuntimeError as e:assert str(e)==expected;return True
    raise AssertionError('Guard failed to reject '+expected)
results={};limit=c.LIMIT;floor=c.FREE_FLOOR
c.LIMIT=c.RESERVE+1;results['run_size_limit']=rejects('DISK_LIMIT',lambda:c.guard())
c.LIMIT=limit;c.FREE_FLOOR=c.shutil.disk_usage(c.R).free+2**30
results['free_space_floor']=rejects('DISK_LIMIT',lambda:c.guard());c.FREE_FLOOR=floor
results['expired_deadline']=rejects('TIME_LIMIT',lambda:c.guard(time.time()-1))
pid_file=c.B/'owned-child.pid'
code='import os,time,pathlib;pathlib.Path('+repr(str(pid_file))+').write_text(str(os.getpid()));time.sleep(60)'
started=time.monotonic()
results['running_child_deadline']=rejects('TIME_LIMIT',lambda:c.command('owned-child',[sys.executable,'-c',code],stop=time.time()+2))
pid=int(pid_file.read_text());assert not c.psutil.pid_exists(pid)
results['owned_child_terminated']=True;results['termination_seconds']=time.monotonic()-started
assert results['termination_seconds']<8
c.guard()
target=c.B/'parallel.json'
code='import sys,pathlib;sys.path.insert(0,"build/ai-nn");import overnight_common as c;[c.write(pathlib.Path('+repr(str(target))+'),{"index":i}) for i in range(80)]'
children=[subprocess.Popen([sys.executable,'-c',code],cwd=c.R,creationflags=0x08004000,stdout=subprocess.PIPE,stderr=subprocess.STDOUT) for _ in range(2)]
outputs=[p.communicate(timeout=15)[0] for p in children]
for i,output in enumerate(outputs):(c.B/f'writer-{i}.log').write_bytes(output)
assert all(p.returncode==0 for p in children),[(p.returncode,v.decode('utf-8','replace')) for p,v in zip(children,outputs)]
assert c.read(target)['index']==79 and not list(c.B.glob('parallel.json.tmp-*'))
results['concurrent_atomic_status_writes']=True
c.write(base/(args.label+'-contract.json'),dict(passed=True,checks=results,scope='Only this test process and its owned children; no historical files removed.'))
print(c.json.dumps(results))
