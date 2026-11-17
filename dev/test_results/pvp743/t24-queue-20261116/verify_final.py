"""Final bounded queue/native integration checks. Preserve every raw report."""
from pathlib import Path
import hashlib, json, os, subprocess, sys
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent/'final-checks'
out.mkdir(exist_ok=False)
release=root/'build/app-typed72-v2/Release'
py38=Path('C:/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe')
env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP741_PROFILE='0',PVP_USERDATA=str(out/'userdata'))
jobs=[('codec',[str(release/'pvp743_network_codec_audit.exe'),str(out/'codec.json')],120),
      ('transport',[str(release/'pvp743_transport_queue_audit.exe'),str(out/'transport.json')],120),
      ('snapshot',[str(release/'pvp743_snapshot_queue_audit.exe'),str(out/'snapshot.json')],120),
      ('guest-chain',[str(py38),str(root/'tools/test/pvp742_guest_snapshot_memory_audit.py'),str(release/'pvp742_guest_snapshot_memory_audit.exe'),str(out/'guest-chain'),'--iterations','64','--units','100'],800),
      ('app-refresh',[str(py38),str(root/'tools/test/pvp742_network_refresh_audit.py'),str(release/'pvp742_network_refresh_audit.exe'),str(out/'app-refresh')],650),
      ('tcp-idle',[sys.executable,str(root/'tools/test/pvp743_tcp_load_audit.py'),str(release/'pvp743_tcp_load_audit.exe'),str(out/'room-payload.json'),str(out/'tcp-idle.json'),'--seconds','20','--rate','131072'],100)]
records=[]
for name,cmd,timeout in jobs:
    print('START',name,flush=True)
    with (out/(name+'.driver.log')).open('wb') as log:
        result=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    records.append({'name':name,'exit_code':result.returncode,'command':cmd})
    (out/'jobs.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    print('EXIT',name,result.returncode,flush=True)
    if result.returncode:
        print((out/(name+'.driver.log')).read_text('utf8',errors='replace')[-5000:]);raise SystemExit(result.returncode)
(out/'executables.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in release.glob('*.exe')},indent=2),encoding='utf8')
print('FINAL_TARGETED_CHECKS_FINISHED',flush=True)
