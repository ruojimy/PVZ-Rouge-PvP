"""PC candidate verification: SHA256SUMS check, exe == built exe, ZIP, independent unpack,
real entry --smoke-report from an unrelated cwd with its own user data (must start a typed72
session), and a summary with every hash. Usage: verify_pc_package.py <candidate-id> <build-tree>"""
import hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ID,BUILD=sys.argv[1],ROOT/sys.argv[2]
pc=ROOT/'dist'/('PvZ-PvP-Native-'+ID)
ev=ROOT/'test_results/typed72-20261108'/('pc-package-'+ID);assert not ev.exists();ev.mkdir(parents=True)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
out={'candidate':str(pc),'build_tree':str(BUILD)}
# 1. every packaged file against SHA256SUMS
bad=[];n=0
for line in (pc/'SHA256SUMS').read_text('utf-8').splitlines():
    digest,name=line.split(None,1);name=name.lstrip('*').lstrip('./')
    n+=1
    if sha(pc/name)!=digest:bad.append(name)
out['sha256sums']={'files':n,'mismatch':bad}
out['exe_sha256']=sha(pc/'PvZPvPNative.exe');out['built_exe_sha256']=sha(BUILD/'Release/PvZPvPNative.exe')
assert out['exe_sha256']==out['built_exe_sha256'] and not bad
# 2. assets identical to the previous release (static files only): the newest other
# PvZ-PvP-Native-* package directory in dist (old packages are pruned; r9b was removed 11-11).
others=[p for p in (ROOT/'dist').glob('PvZ-PvP-Native-*') if p.is_dir() and p!=pc and (p/'SHA256SUMS').is_file()]
prev=max(others,key=lambda p:(p/'SHA256SUMS').stat().st_mtime) if others else None
out['static_assets_reference']=str(prev) if prev else None
diff=[]
if prev:
    for d in ('图片','音乐','音效','extract/assets','fonts'):
        for p in (pc/d).rglob('*'):
            if p.is_file():
                q=prev/p.relative_to(pc)
                if not q.exists() or sha(q)!=sha(p):diff.append(str(p.relative_to(pc)))
out['static_assets_differing_from_previous']=diff
# 3. zip + independent unpack
archive=pc.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(pc.rglob('*')):
        if p.is_file():z.write(p,str(Path(pc.name)/p.relative_to(pc)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
out['zip']=str(archive);out['zip_sha256']=sha(archive)
(archive.with_suffix('.zip.sha256')).write_text(out['zip_sha256']+' *'+archive.name+'\n',encoding='utf-8')
unpacked=ev/'unpacked';unpacked.mkdir()
with zipfile.ZipFile(archive) as z:z.extractall(unpacked)
root=unpacked/pc.name
assert sha(root/'PvZPvPNative.exe')==out['exe_sha256']
# 4. real entry smoke from an unrelated cwd, private user data
launch=ev/'launch-cwd';launch.mkdir();report=ev/'smoke-report.json'
env=dict(os.environ);env['PVP_USERDATA']=str(ev/'userdata');env['SDL_VIDEODRIVER']='dummy';env['SDL_AUDIODRIVER']='dummy'
t0=time.time()
with open(ev/'smoke-stdout.txt','wb') as so,open(ev/'smoke-stderr.txt','wb') as se:
    rc=subprocess.run([str(root/'PvZPvPNative.exe'),'--smoke-report',str(report)],cwd=str(launch),env=env,stdout=so,stderr=se,timeout=900).returncode
out['smoke_exit']=rc;out['smoke_seconds']=round(time.time()-t0,1)
stderr=(ev/'smoke-stderr.txt').read_text('utf-8',errors='replace')
out['typed_session_lines']=[l for l in stderr.splitlines() if '[typed72] battle session started' in l]
res=json.loads(report.read_text('utf-8')) if report.exists() else {}
out['smoke']={k:res.get(k) for k in ('passed',)};out['smoke_detail']=res.get('smoke')
out['passed']=bool(rc==0 and res.get('passed') and out['typed_session_lines'])
(ev/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps({k:out[k] for k in ('passed','exe_sha256','zip_sha256','smoke_exit','smoke_seconds','typed_session_lines','static_assets_reference','static_assets_differing_from_previous')},ensure_ascii=False,indent=1))
