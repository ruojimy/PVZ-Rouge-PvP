from pathlib import Path
import importlib.util,json,hashlib,shutil,os,datetime
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'test_results/pvp743/hotfix-r2-delivery';STAGE=ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r2';DEST=ROOT/'PVZ_rougePvP_native'
spec=importlib.util.spec_from_file_location('base_package',ROOT/'build/pvp743-tools/package_pc743.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def sha(p):return base.sha(p)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
pc=read(OUT/'pc-package-verification.json');source=read(OUT/'source-package-verification.json');android=read(OUT/'android-r2-static-verification.json');previous=read(ROOT/'dist/latest-native-release.json')
for info in [pc,source,android]:assert info['passed']
assert sha(Path(pc['path']))==pc['sha256'] and sha(Path(source['path']))==source['sha256'] and sha(Path(android['apk']))==android['sha256']
assert base.files(STAGE)==pc['payload']
assert sha(DEST/'PvZPvPNative.exe')==previous['exe_sha256'] and previous['exe_sha256']!=pc['exe_sha256']
assert all((DEST/rel).resolve().is_relative_to(DEST.resolve()) for rel in pc['payload'])
root_launcher=ROOT/'启动PvP.cmd';inner=DEST/'launch_pvp.cmd';launcher_hashes={str(p):sha(p) for p in [root_launcher,inner]}
assert 'PVZ_rougePvP_native\\launch_pvp.cmd' in root_launcher.read_text(encoding='utf-8-sig')
assert '%~dp0pvp_userdata' in inner.read_text(encoding='utf-8-sig') and 'PvZPvPNative.exe' in inner.read_text(encoding='utf-8-sig')
before=base.userdata_snapshot();write(OUT/'userdata-before.json',before)
backup=(ROOT/'backup-latest').resolve();assert backup.is_relative_to(ROOT.resolve()) and backup!=ROOT.resolve();backup.mkdir(exist_ok=True);records=[]
for source_key,hash_key,name in [('pc_zip','pc_zip_sha256','previous-release.zip'),('developer_package','developer_sha256','previous-source.zip')]:
 old=Path(previous[source_key]);expected=previous[hash_key];assert sha(old)==expected
 target=backup/name;temp=backup/(name+'.next');assert not temp.exists() and target.resolve().is_relative_to(backup)
 shutil.copy2(old,temp);assert sha(temp)==expected;os.replace(temp,target)
 records.append({'file':str(target),'version':previous['version'],'revision':previous.get('revision','pvp743-r1'),'sha256':expected})
write(backup/'manifest.json',records)
changed=[]
for rel,expected in pc['payload'].items():
 target=DEST/rel
 if target.exists() and sha(target)==expected:continue
 target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.pvp-r2-next');assert not temp.exists()
 shutil.copy2(STAGE/rel,temp);assert sha(temp)==expected;os.replace(temp,target);changed.append(rel)
for rel,expected in pc['payload'].items():assert sha(DEST/rel)==expected,rel
assert all(sha(Path(p))==digest for p,digest in launcher_hashes.items())
after=base.userdata_snapshot();write(OUT/'userdata-after.json',after);assert before==after
report={'passed':True,'version':'1.6.0.74.3-typed.20261114','revision':'pvp743-r2','updated_at':datetime.datetime.now().isoformat(),'launcher':str(root_launcher),'target':str(DEST/'PvZPvPNative.exe'),'exe_sha256':sha(DEST/'PvZPvPNative.exe'),'release':str(STAGE),'pc_zip':pc['path'],'pc_zip_sha256':pc['sha256'],'developer_package':source['path'],'developer_sha256':source['sha256'],'source_package':'complete','apk':android['apk'],'apk_sha256':android['sha256'],'android_version_code':1114082,'android_signature_continuity_verified':True,'android_real_device_verified':False,'android_real_device_status':'Not installed or tested on a physical device in this revision.','all_user_files_preserved':True,'userdata_files_verified':sum(len(v) for v in before.values() if v is not None),'shipped_files_verified':len(pc['payload']),'changed_managed_files':changed,'launcher_files_preserved':True,'backup_folder':str(backup),'backup_files':2,'backup_versions':[previous['version']],'backup_revisions':[previous.get('revision','pvp743-r1')],'new_gameplay_tests_run':True,'pc_packaged_exe_run':True,'root_launcher_executed':False,'targeted_checks':25,'real_coop_profile_flows':4,'real_coop_memory_seconds':300,'complete_memory_plateau_claimed':False,'github':'not_uploaded_this_revision','previous_github_release':previous.get('github_release'),'release_notes':str(ROOT/'更新说明-PvP74.3-r2.md'),'announcement':str(ROOT/'更新公告-PvP74.3-r2.txt'),'verification':str(OUT/'local-delivery-verification.json')}
write(OUT/'local-delivery-verification.json',report);write(ROOT/'dist/latest-native-release.json',report);write(ROOT/'dist/PvP74.3-r2-发行清单.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in ('changed_managed_files',)},ensure_ascii=False,indent=2))
