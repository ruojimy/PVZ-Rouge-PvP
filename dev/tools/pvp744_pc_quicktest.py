"""Stage and verify the Windows-only local test package, without promotion."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,time,zipfile

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'dist/PvZ-PvP-74.4-PC-QuickTest-20261116'
OUT=ROOT/'test_results/pvp744/pc-quicktest-20261116'
BUILD=ROOT/'build/app-typed72-v2/Release'
LAUNCH=ROOT/'测试PvP74.4.cmd'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
def read(p):return json.loads(p.read_text('utf8'))
def tree(p):return {x.relative_to(p).as_posix():sha(x) for x in sorted(p.rglob('*')) if x.is_file()} if p.exists() else None
def users():return {str(p):tree(p) for p in [ROOT/'PVZ_rougePvP_native/pvp_userdata',Path(os.environ['APPDATA'])/'PVZ-PvP-Native']}
def stage():
 OUT.mkdir(parents=True,exist_ok=True);assert not STAGE.exists();assert not LAUNCH.exists()
 dump(OUT/'before.json',{'users':users(),'formal_exe':sha(ROOT/'PVZ_rougePvP_native/PvZPvPNative.exe'),'formal_launcher':sha(ROOT/'启动PvP.cmd'),'latest_release':sha(ROOT/'dist/latest-native-release.json')})
 STAGE.mkdir();(STAGE/'extract').mkdir()
 for name in ['PvZPvPNative.exe','relay.json']+[p.name for p in BUILD.glob('SDL2*.dll')]:shutil.copy2(BUILD/name,STAGE/name)
 for name in ['图片','音乐','音效']:shutil.copytree(BUILD/name,STAGE/name)
 for name in ['extract/data','extract/assets','fonts']:shutil.copytree(ROOT/name,STAGE/name)
 text='''PvP74.4 电脑快速测试包 · 2026-11-16

解压后双击“启动快速测试.cmd”，不需要 Python。
主页 → 本地演练 → 测试模式：双方各 13 个空卡槽，直接进入对局。
局内“测试选卡”可以换卡；“作弊器”可修改经济、血量、防御、冷却、昼夜，以及一键清场。
切换到僵尸方选卡，可以找到克苏鲁之眼、世界吞噬者、骷髅王（0 脑光，仅测试模式可召唤）。眼球建议夜间测试，骷髅王白天会狂暴。

包含本轮材质隔离、PvP/2v2/合作模式夜晚与雨天掉阳光修复。
通过启动脚本运行时，存档与设置放在本包的 pvp_userdata，保留既有正式版存档。
这是 Windows 本地快速测试包；未做手机或双机验收。联机测试请双方使用同一测试包。
保持 extract、图片、音乐、音效、fonts 和 DLL 与 EXE 的目录结构完整。
如需反馈，请附上操作步骤及本目录产生的 crash-native.txt 或 reports。
'''
 (STAGE/'快速测试说明.txt').write_text(text,'utf-8-sig')
 script='@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nif not defined PVP_USERDATA set "PVP_USERDATA=%~dp0pvp_userdata"\r\nif not exist "%PVP_USERDATA%" mkdir "%PVP_USERDATA%"\r\n"%~dp0PvZPvPNative.exe" %*\r\nexit /b %errorlevel%\r\n'
 (STAGE/'启动快速测试.cmd').write_bytes(script.encode('utf8'))
 # A separate candidate entry leaves the latest formal launcher and its saves intact.
 LAUNCH.write_bytes(('@echo off\r\ncall "%~dp0dist\\'+STAGE.name+'\\启动快速测试.cmd" %*\r\n').encode('gbk'))
 dump(STAGE/'quicktest-revision.json',{'revision':'pvp744-pc-quicktest-20261116','kind':'local_test_candidate','formal_release':False,'source_verification':'test_results/pvp744/testmode-terraria-20261116/修复验证.json','exe_sha256':sha(STAGE/'PvZPvPNative.exe')})
 shutil.copy2(ROOT/'test_results/pvp744/testmode-terraria-20261116/实现与验证.md',STAGE/'源码验证记录.md')
 files=tree(STAGE);assert all('terraria/'+name in '\n'.join(files) for name in ['NPC_4.png','NPC_5.png','NPC_13.png','NPC_14.png','NPC_15.png','NPC_35.png','NPC_36.png','Arm_Bone.png'])
 dump(OUT/'payload.json',files);print('staged',len(files),sha(STAGE/'PvZPvPNative.exe'),flush=True)

def smoke():
 import psutil
 case=OUT/'packaged-exe';case.mkdir(exist_ok=False)
 cfg=case/'config.json';dump(cfg,{'scenario':'ordinary','units':20,'warmup_seconds':0,'seconds':3,'audit_userdata':True})
 env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',APPDATA=str(case/'appdata'))
 env.pop('PVP_USERDATA',None);env.pop('PVZ_TEST_ROOT',None)
 for name in list(env):
  if name.startswith('PVP744_') or name=='PVP741_PROFILE':env.pop(name)
 observed=[]
 with (case/'stdout.log').open('wb') as log:
  proc=subprocess.Popen([str(STAGE/'PvZPvPNative.exe'),'--diagnostic',str(cfg)],cwd=case,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
  observed.append({'pid':proc.pid,'exe':psutil.Process(proc.pid).exe(),'sha256':sha(STAGE/'PvZPvPNative.exe')})
  code=proc.wait(timeout=120)
 assert code==0,(case/'stdout.log').read_text('utf8',errors='replace')[-2500:]
 reports=[p for p in (STAGE/'reports').glob('*.json') if not p.name.endswith('.live.json')]
 assert len(reports)==1
 report=read(reports[0]);assert report['completed'] and report['userdata_audit']['unchanged']
 # Validate the actual root candidate launcher as well, using isolated user data.
 env['PVP_USERDATA']=str(case/'launcher-userdata')
 with (case/'launcher.log').open('wb') as log:
  proc=subprocess.Popen(['cmd.exe','/d','/c',str(LAUNCH),'--diagnostic',str(cfg)],cwd=case,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
  seen=False;deadline=time.monotonic()+120
  while proc.poll() is None:
   if time.monotonic()>deadline:proc.terminate();raise TimeoutError('launcher diagnostic')
   try:
    for p in psutil.Process(proc.pid).children(recursive=True):
     try:
      if Path(p.exe()).resolve()==(STAGE/'PvZPvPNative.exe').resolve():seen=True
     except (psutil.NoSuchProcess,psutil.AccessDenied):pass
   except psutil.NoSuchProcess:pass
   time.sleep(.1)
 assert proc.returncode==0 and seen
 source=(STAGE/'reports').resolve();dest=(case/'reports').resolve()
 assert source.is_relative_to(STAGE.resolve()) and dest.is_relative_to(OUT.resolve())
 shutil.move(str(source),str(dest))
 assert not (STAGE/'pvp_userdata').exists()
 before=read(OUT/'before.json');assert before['users']==users()
 dump(case/'verification.json',{'passed':True,'default_userdata_isolated':True,'launcher_executed':True,'observed':observed,'user_data_unchanged':True})
 print('packaged EXE and root quick-test launcher passed',flush=True)

def archive():
 assert read(OUT/'packaged-exe/verification.json')['passed']
 assert read(OUT/'package-feature-audit/results.json')['passed']
 before=read(OUT/'before.json');assert before['users']==users()
 assert before['formal_exe']==sha(ROOT/'PVZ_rougePvP_native/PvZPvPNative.exe')
 assert before['formal_launcher']==sha(ROOT/'启动PvP.cmd') and before['latest_release']==sha(ROOT/'dist/latest-native-release.json')
 files=read(OUT/'payload.json');assert tree(STAGE)==files
 (STAGE/'SHA256SUMS').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())),'utf8');files['SHA256SUMS']=sha(STAGE/'SHA256SUMS')
 target=STAGE.with_name(STAGE.name+'.zip');assert not target.exists()
 class UTF8Info(zipfile.ZipInfo):
  def _encodeFilenameFlags(self):return self.filename.encode('utf8'),self.flag_bits|0x800
 with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,h in sorted(files.items()):
   p=STAGE/n;assert sha(p)==h;info=UTF8Info(STAGE.name+'/'+n);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,p.read_bytes())
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for info in z.infolist():assert hashlib.sha256(z.read(info)).hexdigest()==files[info.filename.split('/',1)[1]]
 digest=sha(target);target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n','utf8')
 result={'passed':True,'path':str(target),'bytes':target.stat().st_size,'sha256':digest,'files':len(files),'exe_sha256':sha(STAGE/'PvZPvPNative.exe'),'launcher':str(LAUNCH),'packaged_exe_executed':True,'test_mode_checks':20,'all_archive_files_verified':True,'source_user_data_unchanged':True,'formal_launcher_unchanged':True,'formal_release':False}
 dump(OUT/'delivery.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','smoke','archive']);globals()[p.parse_args().action]()
