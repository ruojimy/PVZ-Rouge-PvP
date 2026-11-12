"""Equal-pixel render microbench, retained scalar path vs optimized path."""
import argparse,ctypes,hashlib,json,os,statistics,subprocess,time
from pathlib import Path
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--exe',required=True);ap.add_argument('--out',required=True);ap.add_argument('--repeats',type=int,default=3);ap.add_argument('--cpu',type=int);args=ap.parse_args()
    if args.repeats<3:raise ValueError('At least 3 measured repetitions')
    exe=Path(args.exe).resolve();before=sha(exe);out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False);rows=[]
    for repeat in range(args.repeats+1):
        order=['reference','optimized'] if repeat%2==0 else ['optimized','reference']
        for mode in order:
            env=os.environ.copy();env.pop('PVZ72_REFERENCE',None);env.pop('PVZ72_RENDER_STATS',None)
            if mode=='reference':env['PVZ72_REFERENCE']='1'
            name=mode+'-'+str(repeat);log=out/(name+'.log')
            with log.open('wb') as stream:
                process=subprocess.Popen([str(exe),'120'],env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if args.cpu is not None:
                    if not ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(int(process._handle)),ctypes.c_size_t(1<<args.cpu)):process.kill();raise ctypes.WinError()
                if process.wait(timeout=180):raise RuntimeError('Render benchmark failed: '+str(log))
            report=json.loads(next(line.split('BENCH_RENDER ',1)[1] for line in log.read_text(encoding='utf8').splitlines() if line.startswith('BENCH_RENDER ')))
            rows.append(dict(report,mode=mode,repeat=repeat,warmup=not repeat));print(name,report['blit_seconds'],report['scale_seconds'],flush=True)
    summary={'exe':str(exe),'exe_sha256':before,'script_sha256':sha(__file__),'cpu':args.cpu,
        'scope':'Software blit/scale microbenchmark only; not real-game or Android FPS','raw':rows,'medians':{}}
    for metric in ('blit_seconds','scale_seconds'):
        summary['medians'][metric]={mode:statistics.median(row[metric] for row in rows if row['mode']==mode and not row['warmup']) for mode in ('reference','optimized')}
        summary['medians'][metric]['reference_over_optimized']=summary['medians'][metric]['reference']/summary['medians'][metric]['optimized']
    summary['inputs_unchanged']=sha(exe)==before
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    if not summary['inputs_unchanged']:raise RuntimeError('Benchmark binary changed')
if __name__=='__main__':main()
