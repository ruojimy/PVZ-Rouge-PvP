"""Sequential acceptance from a physically isolated release plus extracted tools."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'test_results/developer-tools-20261104'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--label',required=True);p.add_argument('--skip-smoke',action='store_true');a=p.parse_args()
    layout=json.loads((E/'test-layout.json').read_text('utf8'))
    base=Path(layout['root']);game=Path(layout['candidate']);stock=Path(layout['stock']);tools=a.tools.resolve()
    out=E/a.label;out.mkdir(exist_ok=False)
    unrelated=base/'无关 cwd';unrelated.mkdir(exist_ok=True)
    result={'label':a.label,'tool_source':str(tools),'game':str(game),'game_sha256':sha(game/'PvZPvPNative.exe'),'cases':[],'all_passed':False}
    tool=tools/'tools/pvz_tools.py'
    def save():write(out/'summary.json',result)
    def case(name,command,check,expected=0,target=game):
        argv=[sys.executable,'-I','-X','utf8',str(tool),'--game',str(target),'--work',str(base/a.label),'--timeout','240']+command
        started=time.monotonic();r=subprocess.run(argv,cwd=unrelated,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        (out/(name+'.log')).write_bytes(r.stdout)
        try:data=json.loads(r.stdout.decode('utf8').splitlines()[-1])
        except Exception:data={'raw':r.stdout.decode('utf8','replace')}
        passed=r.returncode==expected and check(data)
        row={'name':name,'passed':passed,'exit_code':r.returncode,'expected_exit_code':expected,'seconds':time.monotonic()-started,'response':data}
        result['cases'].append(row);save();print(name,'PASS' if passed else 'FAIL',flush=True)
        if not passed:raise RuntimeError('Acceptance failed: '+name)
        return data
    listing=case('discovery',['list'],lambda d:len(d['result']['skills'])==14)
    cap=case('capabilities',['capabilities'],lambda d:d['result']['identity']['adapter']=='native-devtools.1')
    ident=cap['result']['identity']
    exported=base/(a.label+' 导出.json')
    data=case('runtime-export',['export','--output',str(exported)],lambda d:d['result']['cards']>100)
    runtime=json.loads(exported.read_text('utf8'))
    assert runtime['result']['cards']['plant:原始土豆地雷']['hp']==18
    assert runtime['result']['raw_templates']['plant:原始土豆地雷']['hp']==6
    assert runtime['identity']['rules_hash']==json.loads((ROOT/'dist/PVP72-20261104-release-manifest.json').read_text('utf8'))['rules_hash']
    contextual=base/(a.label+' 夜间硬化.json')
    case('runtime-export-context',['export','--night','--secret','secret:硬化','--output',str(contextual)],lambda d:d['ok'])
    context=json.loads(contextual.read_text('utf8'))
    assert context['result']['context']['night'] is True
    assert context['result']['cards']['plant:原始土豆地雷']['hp']>18
    case('invalid-secret-rejected',['export','--secret','not-a-secret'],lambda d:'Unknown secret id' in d['result']['error'],2)
    mapfile=base/(a.label+' 地图.json')
    case('map-new',['map-new','--blank','--name','中文地图 测试','--output',str(mapfile)],lambda d:d['ok'])
    checked=case('map-check',['map-check',str(mapfile)],lambda d:d['result']['room_accepted'] and d['result']['battle_tick']==2 and d['result']['terrain_hash']==d['result']['room_terrain_hash'])
    store=base/a.label/'隔离地图 maps'
    imported=case('map-import',['map-import',str(mapfile),'--store',str(store)],lambda d:d['result']['store_roundtrip'])
    saved=Path(imported['result']['saved_file']);before=sha(saved)
    case('duplicate-map-rejected',['map-import',str(mapfile),'--store',str(store)],lambda d:'already exists' in d['result']['error'],2)
    assert sha(saved)==before
    badmap=json.loads(mapfile.read_text('utf8'));badmap['spawns']['plant']={'col':0,'row':0}
    invalid=base/(a.label+' 错误地图.json');write(invalid,badmap)
    case('invalid-map-rejected',['map-check',str(invalid)],lambda d:'NATIVE_REJECTED' in d['result']['error'],2)
    replay=base/(a.label+' 回放.json')
    case('replay-record-and-playback',['replay-demo','--ticks','30','--output',str(replay)],lambda d:d['result']['playback']['verified'] and d['result']['recording']['input_accepted'])
    replay_data=json.loads(replay.read_text('utf8'))
    changed=dict(replay_data);changed['final_hash']='0'*64
    invalid=base/(a.label+' 错误终点.json');write(invalid,changed)
    case('bad-replay-final-rejected',['replay-check',str(invalid)],lambda d:'NATIVE_REJECTED' in d['result']['error'],2)
    changed=dict(replay_data);changed['build']='deliberately-wrong-build'
    invalid=base/(a.label+' 版本错误回放.json');write(invalid,changed)
    case('bad-replay-version-rejected',['replay-check',str(invalid)],lambda d:'NATIVE_REJECTED' in d['result']['error'],2)
    case('native-relay-roundtrip',['relay-test'],lambda d:d['result']['host_received'] and d['result']['guest_received'] and d['result']['invalid_protocol_rejected'])
    case('stock-api-rejected',['capabilities'],lambda d:'MISSING_NATIVE_API' in d['result']['error'],2,target=stock)
    def direct(name,request,code):
        d=out/name;d.mkdir();req=d/'request.json';response=d/'response.json';write(req,request)
        env=os.environ.copy();env['PVP_USERDATA']=str(base/a.label/'userdata')
        r=subprocess.run([str(game/'PvZPvPNative.exe'),'--developer-tools',str(req),str(response)],cwd=unrelated,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (d/'process.log').write_bytes(r.stdout)
        data=json.loads(response.read_text('utf8')) if response.exists() else {}
        passed=r.returncode!=0 and data.get('error',{}).get('code')==code
        result['cases'].append({'name':name,'passed':passed,'exit_code':r.returncode,'response':data});save();print(name,'PASS' if passed else 'FAIL',flush=True)
        if not passed:raise RuntimeError(name)
    direct('protocol-mismatch',{'protocol':999,'operation':'capabilities','arguments':{}},'PROTOCOL_MISMATCH')
    direct('identity-mismatch',{'protocol':1,'operation':'export','arguments':{},'expected':ident|{'build':'wrong'}},'VERSION_MISMATCH')
    direct('unknown-field',{'protocol':1,'operation':'capabilities','unexpected':True},'INVALID_REQUEST')
    direct('unknown-operation',{'protocol':1,'operation':'does-not-exist','expected':ident},'UNKNOWN_OPERATION')
    direct('integer-overflow-rejected',{'protocol':1,'operation':'map-new','arguments':{'seed':4294967297},'expected':ident},'INVALID_REQUEST')
    direct('fractional-seed-rejected',{'protocol':1,'operation':'map-new','arguments':{'seed':1.5},'expected':ident},'INVALID_REQUEST')
    cli=subprocess.run([str(game/'PvZPvPNative.exe'),'--developer-tools'],cwd=unrelated,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    result['cases'].append({'name':'missing-cli-arguments','passed':cli.returncode==2 and b'Usage:' in cli.stdout,'exit_code':cli.returncode})
    save();assert result['cases'][-1]['passed']
    protected=out/'protected-response.json';protected.write_bytes(b'keep-original-response')
    req=out/'protected-request.json';write(req,{'protocol':1,'operation':'capabilities'})
    cli=subprocess.run([str(game/'PvZPvPNative.exe'),'--developer-tools',str(req),str(protected)],cwd=unrelated,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    result['cases'].append({'name':'existing-response-protected','passed':cli.returncode==6 and protected.read_bytes()==b'keep-original-response','exit_code':cli.returncode})
    save();assert result['cases'][-1]['passed']
    case('invalid-diagnostic-rejected',['diagnostic','--units','0'],lambda d:'DIAGNOSTIC_BOUNDS' in d['result']['error'],2)
    if not a.skip_smoke:
        case('candidate-smoke',['smoke'],lambda d:d['result']['native_tick']==1250 and d['result']['native_checks_passed'] and d['result']['rematched'])
        case('stock-smoke',['smoke'],lambda d:d['result']['native_tick']==1250 and d['result']['native_checks_passed'] and d['result']['rematched'],target=stock)
    case('candidate-diagnostic',['diagnostic','--scene','ordinary','--units','2','--warmup','0','--seconds','1'],lambda d:d['result']['completed'] and d['result']['native72']['build']==ident['build'])
    case('stock-diagnostic',['diagnostic','--scene','ordinary','--units','2','--warmup','0','--seconds','1'],lambda d:d['result']['completed'] and d['result']['native72']['build']==ident['build'],target=stock)
    manifest=json.loads((ROOT/'dist/PVP72-20261104-release-manifest.json').read_text('utf8'))
    case('apk-local-structure',['apk-inspect',manifest['android']['apk']],lambda d:d['result']['identity']['versionCode']==1104003 and d['result']['pc_build_matches'] and not d['result']['all_16k_aligned'] and not d['result']['signature_verified'])
    if (tools/'manifest.json').exists():
        case('extension-allowlist',['audit','--target',str(tools),'--manifest',str(tools/'manifest.json')],lambda d:d['result']['allowlist_verified'] and d['result']['sha256_verified'])
        tamper=base/(a.label+' tamper');shutil.copytree(tools,tamper)
        original=(tamper/'README.md').read_bytes();(tamper/'README.md').write_bytes(original+b'\nchanged\n')
        case('tampered-file-rejected',['audit','--target',str(tamper),'--manifest',str(tools/'manifest.json')],lambda d:'Hash mismatch' in d['result']['error'],2)
        (tamper/'README.md').write_bytes(original);(tamper/'unexpected.txt').write_text('deliberate negative control',encoding='utf8')
        case('extra-file-rejected',['audit','--target',str(tamper),'--manifest',str(tools/'manifest.json')],lambda d:'allowlist mismatch' in d['result']['error'],2)
    forbidden=[ROOT/'src',Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71'),Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\modkit')]
    count=0
    for trace in (base/a.label).rglob('paths.json'):
        d=json.loads(trace.read_text('utf8'));count+=1
        for opened in d['actual_python_file_opens']:
            if any(Path(opened).is_relative_to(path) for path in forbidden):raise RuntimeError('Implicit old/source dependency: '+opened)
    result['path_traces_checked']=count
    result['no_source_files_adjacent']=not any((game/f).exists() for f in ['src','modkit','reverse_engineered','AI','tests'])
    assert result['no_source_files_adjacent']
    result['all_passed']=True;save()

if __name__=='__main__':main()
