from pathlib import Path
import importlib.util,json,os,subprocess,time
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent/'cloud-native'
out.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('relay_health',root/'developer-tools/tools/relay/health.py')
health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
def capture(name):
    value=health.health('47.119.190.111',24562)
    (out/(name+'.json')).write_text(json.dumps(value,indent=2),encoding='utf8')
    print(name,json.dumps(value),flush=True)
    return value
before=capture('before')
if before['rooms']!=0:raise SystemExit('Relay busy; preserve zero-impact read-only health evidence')
env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'userdata'))
with (out/'native.log').open('wb') as log:
    process=subprocess.Popen([str(root/'build/app-typed72-v2/Release/pvp743_relay_load_audit.exe'),str(out/'native.json'),str(out.parent/'final-checks/room-payload.json'),'47.119.190.111:24562'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    time.sleep(8)
    capture('during')
    try:code=process.wait(timeout=70)
    except subprocess.TimeoutExpired:process.kill();process.wait();raise
capture('after-close')
print('Native exit',code,flush=True)
print((out/'native.json').read_text('utf8') if (out/'native.json').exists() else (out/'native.log').read_text('utf8',errors='replace')[-2000:],flush=True)
time.sleep(25)
after=capture('after-ttl')
(out/'assessment.json').write_text(json.dumps({'native_exit':code,'room_count_returned_to_baseline':after['rooms']==before['rooms'],'server_configuration_changed':False,'scope':'One private native relay session; no device or public capacity claim'},indent=2),encoding='utf8')
raise SystemExit(code)
