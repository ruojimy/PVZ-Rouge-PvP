"""Serial benchmarks selected by immutable baseline/candidate manifests.

No SHA gate is removed from the legacy r2 tool. This mode measures the exact
specified binaries/inputs and refuses in-run drift. Rule differences are
reported explicitly; C/D same-rule comparison uses PVZ72_REFERENCE in C.
"""
import argparse,ctypes,hashlib,json,os,re,statistics,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from benchmark_release import process_memory

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def manifest(path):
    path=Path(path).resolve();data=json.loads(path.read_text(encoding='utf8'))
    for key in ('id','ruleset','executable','executable_sha256','cwd','files'):
        if key not in data:raise RuntimeError('Missing manifest field '+key)
    files={str(path):sha(path)}
    exe=Path(data['executable']).resolve()
    if sha(exe)!=data['executable_sha256']:raise RuntimeError('Executable SHA mismatch: '+str(exe))
    files[str(exe)]=data['executable_sha256']
    for name,digest in data['files'].items():
        p=Path(name);p=p if p.is_absolute() else Path(data['cwd'])/p
        if sha(p)!=digest:raise RuntimeError('Input SHA mismatch: '+str(p))
        files[str(p)]=digest
    return data,files

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--baseline-manifest',required=True);ap.add_argument('--candidate-manifest',required=True)
    ap.add_argument('--scenarios',required=True);ap.add_argument('--scene',action='append');ap.add_argument('--out',required=True)
    ap.add_argument('--repeats',type=int,default=3);ap.add_argument('--cpu',type=int);args=ap.parse_args(argv)
    if args.repeats<3:raise ValueError('At least three measured repeats are required')
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir();(out/'scenarios').mkdir()
    baseline,bfiles=manifest(args.baseline_manifest);candidate,cfiles=manifest(args.candidate_manifest)
    pinned=dict(bfiles);pinned.update(cfiles)
    scenes=args.scene or ['empty','basic','zombie_swarm','projectile_storm','mixed_late_game']
    configs={}
    for name in scenes:
        p=Path(args.scenarios)/('_expanded_'+name+'.json')
        if not p.exists():p=Path(args.scenarios)/(name+'.json')
        config=json.loads(p.read_text(encoding='utf8'));pinned[str(p.resolve())]=sha(p)
        if config.get('inputs'):raise RuntimeError('--bench does not dispatch input schedules: '+name)
        if name=='empty':config['room_ticks']=300
        dest=out/'scenarios'/(name+'.json');save(dest,config);configs[name]=dest;pinned[str(dest)]=sha(dest)
    metadata={'baseline':baseline,'candidate':candidate,'same_rules':baseline['ruleset']==candidate['ruleset'],
        'rule_difference_warning':None if baseline['ruleset']==candidate['ruleset'] else 'Mixed engine/rule comparison; not a pure optimization speedup.',
        'repeats':args.repeats,'warmups':1,'cpu_requested':args.cpu,'script_sha256':sha(__file__),
        'order':'alternating, serial, separate process for every sample','timing_scope':'battle.step; excludes actual window rendering and AI decisions'}
    save(out/'metadata.json',metadata);save(out/'pinned-inputs.json',pinned);rows=[]
    for scene in scenes:
        for repeat in range(args.repeats+1):
            variants=[('baseline',baseline),('candidate',candidate)]
            if repeat%2:variants.reverse()
            for label,build in variants:
                name=scene+'-'+label+'-'+str(repeat);env=os.environ.copy()
                for key in list(env):
                    if key.startswith(('PVZ_','PVP_','PVZ72_')):env.pop(key)
                env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'userdata'/name))
                env.update({str(k):str(v) for k,v in build.get('environment',{}).items()})
                log=out/'logs'/(name+'.log');peak={};started=time.perf_counter()
                with log.open('wb') as stream:
                    process=subprocess.Popen([build['executable'],str(configs[scene]),'--bench'],cwd=build['cwd'],env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    if args.cpu is not None:
                        if os.name!='nt' or not 0<=args.cpu<(os.cpu_count() or 1):process.kill();raise ValueError('Invalid Windows logical CPU')
                        handle=ctypes.c_void_p(int(process._handle));mask=1<<args.cpu
                        if not ctypes.windll.kernel32.SetProcessAffinityMask(handle,ctypes.c_size_t(mask)):process.kill();raise ctypes.WinError()
                        actual,system=ctypes.c_size_t(),ctypes.c_size_t()
                        if not ctypes.windll.kernel32.GetProcessAffinityMask(handle,ctypes.byref(actual),ctypes.byref(system)) or actual.value!=mask:process.kill();raise RuntimeError('CPU affinity verification failed')
                    while process.poll() is None:
                        for key,value in process_memory(process).items():peak[key]=max(value,peak.get(key,0))
                        if time.perf_counter()-started>300:process.kill();process.wait();raise RuntimeError('Benchmark timed out')
                        time.sleep(.05)
                raw=log.read_text(encoding='utf8',errors='replace')
                match=re.search(r'init ([0-9.]+)s, (\d+) room ticks ([0-9.]+)s',raw)
                if process.returncode or not match:raise RuntimeError('Benchmark failed: '+name+' '+raw[-1000:])
                row={'scene':scene,'variant':label,'repeat':repeat,'warmup':repeat==0,'init_seconds':float(match[1]),'room_ticks':int(match[2]),'step_seconds':float(match[3]),'memory':peak}
                rows.append(row);save(out/'raw.json',rows);print(name,row['step_seconds'],'WARMUP' if not repeat else '',flush=True)
    changed=[path for path,digest in pinned.items() if sha(path)!=digest]
    groups={}
    for scene in scenes:
        groups[scene]={}
        for label in ('baseline','candidate'):
            times=[row['step_seconds'] for row in rows if row['scene']==scene and row['variant']==label and not row['warmup']]
            groups[scene][label]={'median_seconds':statistics.median(times),'min_seconds':min(times),'max_seconds':max(times),'samples_seconds':times}
        groups[scene]['baseline_over_candidate']=groups[scene]['baseline']['median_seconds']/groups[scene]['candidate']['median_seconds']
    save(out/'summary.json',{'complete':True,'success':not changed,'same_rules':metadata['same_rules'],'groups':groups,'changed_inputs':changed})
    if changed:raise RuntimeError('Inputs changed during benchmark')
    print('BENCHMARK_COMPLETE',str(out),flush=True)

if __name__=='__main__':main()
