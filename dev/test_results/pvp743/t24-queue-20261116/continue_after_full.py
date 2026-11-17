"""Wait for the single full run, audit its denominator, then build Android serially."""
from pathlib import Path
import hashlib,json,subprocess,time
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
old=root/'test_results/pvp743/t07-full-py38-r8-w2-20261115'
current=root/'test_results/pvp743/t24-full-20261116'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
paths=list((root/'third_party/zlib-1.3.2-compress').rglob('*'))+[root/'tools/pvp743_network_sources.json']
paths=[p for p in paths if p.is_file()]
paths += [root/'build/app-typed72-v2/Release'/name for name in ('cpp_tests.exe','app_run.exe','PvZPvPNative.exe')]
frozen={p.relative_to(root).as_posix():sha(p) for p in paths}
(out/'additional-freeze.json').write_text(json.dumps(frozen,indent=2),encoding='utf8')
print('Waiting for full regression; Android starts only after source/denominator/no-new-failure checks.',flush=True)
deadline=time.monotonic()+7200
while not (current/'summary.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Full suite summary unavailable')
    time.sleep(5)
time.sleep(2)
summary=json.loads((current/'summary.json').read_text('utf8'))
def rows(folder):
    return {'.'.join(r[k] for k in ('module','class','test')):r for m in json.loads((folder/'summary.json').read_text('utf8'))['modules'] for r in json.loads((folder/(m['module']+'.json')).read_text('utf8'))}
a,b=rows(old),rows(current)
new=[{'id':name,'old':a.get(name),'new':row} for name,row in b.items() if row['outcome']!='PASS' and (name not in a or a[name]['outcome']!=row['outcome'])]
nonpass=[{'id':name,'outcome':row['outcome'],'old_detail':a.get(name,{}).get('detail'),'new_detail':row['detail'],'detail_identical':a.get(name,{}).get('detail')==row['detail']} for name,row in b.items() if row['outcome']!='PASS']
changed=[name for name,value in frozen.items() if sha(root/name)!=value]
post_source=json.loads((current/'source-hashes.json').read_text('utf8'))
changed_source=[name for name,value in post_source.items() if sha(root/name)!=value]
gate=summary.get('pure_typed_gate',summary.get('pure_gate',{}))
if not gate:gate=json.loads((current/'pure-typed-gate/pure-typed-gate.json').read_text('utf8'))
comparison={'modules':len(summary['modules']),'tests':len(b),'counts':summary['counts'],'missing':summary['missing'],'waived':summary['waived'],'unwaived':len(summary['waivers']['unexpected_nonpass']),'new_nonpass':new,'all_nonpass':nonpass,'additional_freeze_changed':changed,'post_gate_source_changed':changed_source,'pure_typed_passed':gate.get('passed',False),'product_acceptance_passed':summary['success']}
(out/'full-comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf8')
assert len(summary['modules'])==204 and len(b)==2366 and not summary['missing'] and not new
assert not summary['source_changed_during_run'] and not summary['fixture_changed_during_run'] and not summary['exe_changed_during_run'] and not summary['collection_mismatch']
assert not changed and not changed_source and gate.get('passed')
print('Full run completed, no new nonpass IDs; known raw failures preserved.',flush=True)
with (out/'android-build.log').open('wb') as log:
    result=subprocess.run(['wsl','-d','Ubuntu','--','taskset','-c','22,23','nice','-n','10','bash','/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native/test_results/pvp743/t24-queue-20261116/build_android_release.sh'],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
print('ANDROID EXIT',result.returncode,flush=True)
print((out/'android-build.log').read_text('utf8',errors='replace')[-5000:],flush=True)
raise SystemExit(result.returncode)
