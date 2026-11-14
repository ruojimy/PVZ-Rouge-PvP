from pathlib import Path
import hashlib,json,zipfile,datetime,importlib.util
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'test_results/pvp743/hotfix-r2-delivery'
STAGE=ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r2'
spec=importlib.util.spec_from_file_location('base_package',ROOT/'build/pvp743-tools/package_pc743.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def sha(p):return base.sha(p)
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def build_zip(target,entries,prefix):
 assert not target.exists(),target
 hashes={name:sha(item) if isinstance(item,Path) else hashlib.sha256(item).hexdigest() for name,item in entries.items()}
 with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,item in sorted(entries.items()):
   info=base.UTF8Info(prefix+name);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,item.read_bytes() if isinstance(item,Path) else item)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  assert len(z.infolist())==len(hashes)
  for entry in z.infolist():assert entry.flag_bits&0x800 and hashlib.sha256(z.read(entry)).hexdigest()==hashes[entry.filename.removeprefix(prefix)]
 target.with_suffix(target.suffix+'.sha256').write_text(sha(target)+'  '+target.name+'\n',encoding='utf-8')
 return {'path':str(target),'sha256':sha(target),'files':len(entries),'crc_and_payload_verified':True,'utf8_all':True}
# PC candidate already contains the verified actual shipped EXE and unchanged resources.
assert sha(STAGE/'PvZPvPNative.exe')=='4d0fe7c5762d4e2a1a949b21d5e7bca202d9cdbaf7500a18b3114fd60de80f5e'
assert not (STAGE/'reports').exists() and not (STAGE/'pvp_userdata').exists()
files={p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
(STAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  ./'+n+'\n' for n,p in sorted(files.items())),encoding='utf-8')
files['SHA256SUMS']=STAGE/'SHA256SUMS'
pc=build_zip(STAGE.with_suffix('.zip'),files,'PvZ-PvP-Native/')
pc.update(passed=True,revision='pvp743-r2',version='1.6.0.74.3-typed.20261114',exe_sha256=sha(STAGE/'PvZPvPNative.exe'),payload={n:sha(p) for n,p in files.items()})
write(OUT/'pc-package-verification.json',pc)
print('PC',json.dumps({k:v for k,v in pc.items() if k!='payload'}),flush=True)
# Retain the full previous developer source set; refresh actual owned files and add curated hotfix evidence.
old=ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r1-Developer-Package.zip';entries={};inherited=[]
with zipfile.ZipFile(old) as z:
 for info in z.infolist():
  if info.is_dir():continue
  rel=info.filename.split('/',1)[1]
  if rel in ('SHA256SUMS.txt','MANIFEST-PvP74.3.json','STAGING_STATUS.json'):continue
  current=(ROOT/rel).resolve();assert current.is_relative_to(ROOT.resolve())
  if current.is_file():entries[rel]=current
  else:
   assert Path(rel).suffix.lower() in ('.md','.json','.txt'),rel
   entries[rel]=z.read(info);inherited.append(rel)
extra=['build/pvp743-tools/package_hotfix_r2.py','src/uitools/pvp743_profile_lifecycle_audit.cpp','src/uitools/pvp743_alias_retention_audit.cpp','更新说明-PvP74.3-r2.md','更新公告-PvP74.3-r2.txt',
 'test_results/pvp743/hotfix-r2-investigation.md','test_results/pvp743/performance-recording-fix-20261114.md','test_results/pvp743/profile-fix-final-regression/summary.json','test_results/pvp743/performance-start-investigation/results-click-before.json','test_results/pvp743/performance-start-investigation/results-coop-click-after-r3.json',
 'test_results/pvp743/alias-retention-r1/assessment.md','test_results/pvp743/alias-retention-r1/comparison.json','test_results/pvp743/alias-retention-r1/final960.json',
 'test_results/pvp743/coop-rail-api-memory-r6/assessment.md','test_results/pvp743/coop-rail-api-memory-r6/r5-comparison.json','test_results/pvp743/coop-rail-api-memory-r6/completion-verification.json',
 'test_results/pvp743/coop-rail-live-stack-r1/assessment.md','test_results/pvp743/coop-rail-live-stack-r2/assessment.md','test_results/pvp743/coop-rail-live-stack-r2/live-stack-summary-60-120.json',
 'test_results/pvp743/hotfix-r2-delivery/android-r2-static-verification.json']
for rel in extra:
 assert (ROOT/rel).is_file(),rel
 entries[rel]=ROOT/rel
status={'revision':'pvp743-r2','production_fixes':['complete-frame profiling lifecycle','unbind profiler callback ownership','elide production alias observer only'],'targeted_native_checks':25,'real_coop_profile_flows':4,'real_coop_memory_seconds':300,'android_version_code':1114082,'android_device_acceptance':'not_run_this_revision','foreground_fps_acceptance':'not_run_locked_desktop','long_term_cross_match_memory':'not_verified','memory_growth_completely_zero':False}
entries['STAGING_STATUS.json']=(json.dumps(status,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
manifest={'version':'1.6.0.74.3-typed.20261114','revision':'pvp743-r2','base_developer_archive_sha256':sha(old),'historical_metadata_retained':inherited,'current_files':{n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in sorted(entries.items())},'validation':status}
entries['MANIFEST-PvP74.3.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
source_hashes={n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in entries.items()}
entries['SHA256SUMS.txt']=''.join(h+'  '+n+'\n' for n,h in sorted(source_hashes.items())).encode('utf-8')
source=build_zip(ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r2-Developer-Package.zip',entries,'PvZ-PvP-Native-PvP74.3-src/')
source.update(passed=True,revision='pvp743-r2',version='1.6.0.74.3-typed.20261114',full_previous_source_set_retained=True,new_curated_evidence=len(extra))
write(OUT/'source-package-verification.json',source);print('SOURCE',json.dumps(source),flush=True)
