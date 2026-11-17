from pathlib import Path
import os,subprocess,json
root=Path.cwd();out=root/'test_results/pvp743/t24-queue-20261116';release=root/'build/app-typed72-v2/Release'
env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'validation-userdata'))
records=[]
for name,exe,options in [('transport-contract','pvp743_transport_queue_audit',{}),('before-r2','pvp743_snapshot_queue_audit',{'PVP743_SNAPSHOT_PACK':'0'}),('after-r2','pvp743_snapshot_queue_audit',{'PVP743_SNAPSHOT_PACK':'1'}),('after-r3','pvp743_snapshot_queue_audit',{'PVP743_SNAPSHOT_PACK':'1'}),('before-r3','pvp743_snapshot_queue_audit',{'PVP743_SNAPSHOT_PACK':'0'}),('app-refresh-r3','pvp742_network_refresh_audit',{'PVP741_PROFILE':'1'})]:
 with (out/(name+'.log')).open('wb') as log:r=subprocess.run([str(release/(exe+'.exe')),str(out/(name+'.json'))],env=dict(env,**options),stdout=log,stderr=subprocess.STDOUT,timeout=300)
 print(name,r.returncode,flush=True)
 records.append({'name':name,'exit':r.returncode});(out/'verification-jobs.json').write_text(json.dumps(records,indent=2),encoding='utf8')
 if r.returncode:print((out/(name+'.log')).read_text('utf8',errors='replace')[-2500:],flush=True);break
