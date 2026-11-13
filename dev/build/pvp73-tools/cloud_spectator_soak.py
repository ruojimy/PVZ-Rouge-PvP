"""Private real-relay watcher soak. Isolated native apps; never uses player saves."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'test_results/pvp73/r3-cloud-spectator-long'
OUT.mkdir(parents=True,exist_ok=True)
token=OUT/'private-room.txt'
token.unlink(missing_ok=True)
exe=ROOT/'build/app-typed72-v2/Release/app_run.exe'
env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_RELAY_ENDPOINT='47.119.190.111:24562',NETWATCH_SECONDS='660',NETPERF='665')
procs=[];streams=[];started=time.time();report={'private':True,'endpoint':env['PVP_RELAY_ENDPOINT'],'watch_seconds':660,'passed':False}
def spawn(role):
    stream=open(OUT/(role+'.log'),'wb');streams.append(stream)
    p=subprocess.Popen([str(exe),'netpeer',role,'0',str(token),'relay'],cwd=str(ROOT),env=dict(env,PVP_USERDATA=str(OUT/(role+'-userdata'))),stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08000000)
    procs.append((role,p));return p
try:
    host=spawn('host')
    while not token.exists() and time.time()-started<45 and host.poll() is None:time.sleep(.2)
    if not token.exists():raise RuntimeError('private cloud room did not open')
    guest=spawn('guest');watcher=spawn('spectate')
    while watcher.poll() is None and time.time()-started<900:time.sleep(.5)
    if watcher.poll() is None:raise RuntimeError('spectator soak timed out')
    log=(OUT/'spectate.log').read_text('utf8',errors='replace')
    report.update(exit=watcher.returncode,passed=watcher.returncode==0 and 'NET spectate PASS watching battle' in log,
        last_lines=log.splitlines()[-12:],elapsed=round(time.time()-started,1))
except Exception as e:report['error']=str(e)
finally:
    for role,p in procs:
        if p.poll() is None:p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    for stream in streams:stream.close()
    token.unlink(missing_ok=True) if sys.version_info>=(3,8) else None
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))
raise SystemExit(0 if report['passed'] else 1)
