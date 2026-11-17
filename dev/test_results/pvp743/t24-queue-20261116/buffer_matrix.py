import os,subprocess,json
from pathlib import Path
out=Path('test_results/pvp743/t24-queue-20261116')
for name,send,backlog in [('tcp-default-r2',0,98304),('tcp-snd64-r2',65536,98304),('tcp-snd16-back32-r1',16384,32768)]:
 env=dict(os.environ,PVP_AUDIT_SNDBUF=str(send),PVP_AUDIT_BACKLOG_BYTES=str(backlog))
 cmd=['python','tools/test/pvp743_tcp_load_audit.py','build/app-typed72-v2/Release/pvp743_tcp_load_audit.exe',str(out/'room-payload.json'),str(out/(name+'.json')),'--seconds','16']
 result=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=70)
 (out/(name+'.driver.log')).write_text(result.stdout,encoding='utf8')
 r=json.loads((out/(name+'.json')).read_text('utf8'));print(name,r.get('passed'),r.get('socket_send_buffers'),[(p['peer'],round(p['snapshot_age_p95_ms'],1),p['input_acks'],p['input_commands']) for p in r.get('peers',[])],flush=True)
