"""Package the user-accepted r4 performance revision; preserve all user data."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test_results/pvp744/release-r4-20261116'
OLD=ROOT/'dist/PvZ-PvP-Native-20261116-pvp743-r3'
STAGE=ROOT/'dist/PvZ-PvP-Native-20261116-pvp743-r4'
VERSION='1.6.0.74.3-typed.20261114'
REV='pvp743-r4'
FLAGS=['PVP744_PACING','PVP744_VIEW_REUSE','PVP744_LOCAL_FRAME','PVP744_STATE_VIEW','PVP744_METADATA_VIEW']

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=load_module('r3_packaging_helpers',ROOT/'test_results/pvp743/t24-queue-20261116/package_release.py')
sha,read,dump,tree,users,archive=base.sha,base.read,base.dump,base.tree,base.users,base.archive

def notes():
    text='''# PvP74.3 r4：性能与交互优化版

2026-11-16。用户完成本轮体验并认可交付；正式启动默认启用此前已测试的优化，无需实验入口。

- 玩家、放置、资源与触手元数据直接投影，本机快照接管新对象，减少JSON转换与重复复制。
- 单位/HUD一次提取、可见帧延迟投影与版本复用；修复重复刷新打断插值，让绘制与逻辑更协调。
- 完整模拟步边界按8ms预算让出，保持债务；持续高负载才慢放，250Hz战斗、规则、伤害与随机顺序不变。
- 用户反馈：按键响应及时，绘制与逻辑匹配比之前好。

PC快照复制均值0.534→0.002ms；安卓抓人草新状态刷新18.98→14.98ms，呈现6.84→7.08次/秒，模拟/墙钟约0.295→0.296。后者为单轮短时手机对照，并非所有场景或稳定30FPS承诺。PC AB/BA同场景终态和RNG一致，139/139定向检查通过。

正常PC/Android入口默认开启PVP744_PACING、VIEW_REUSE、LOCAL_FRAME、STATE_VIEW、METADATA_VIEW，STEP_BUDGET_MS=8。显式进程开关和诊断参数仍可覆盖；函数计时默认关闭。普通联网公开快照保留原协议和复制契约，本机私有呈现只用于本地作用域。

兼容BUILD保持1.6.0.74.3-typed.20261114；APK版本为1.6.0.74.3-typed.20261114-r4，versionCode=1114085。PC正式根启动器同步更新，既有独立存档路径保留；Android同包名同签名覆盖升级。

完整2366项产品回归本次未重跑，历史27项未豁免问题不改写为通过；高密度绘制、长时内存与跨场景物理输入延迟继续跟踪。T01/T02/T24仍开放，T22神经网络研究保持暂停。局部功能已获用户认可交付，与全产品性能目标分开记录。

详细原始对照：test_results/pvp744/metadata-20261116/assessment.md。
本次正式包验证：test_results/pvp744/release-r4-20261116/local-delivery-verification.json。
'''
    (ROOT/'更新说明-PvP74.3-r4.md').write_text(text,'utf8')
    notice='PvP74.3 r4 性能与交互优化版\n\n正常启动默认启用新快照、状态提取和呈现优化，减少重复转换与复制，改善按键响应和绘制/逻辑协调。保持战斗规则与原存档。\n\n139项定向检查通过，已完成安卓实机对照与用户体验；高密度场景仍可能明显掉帧，后续继续优化。\n'
    (ROOT/'更新公告-PvP74.3-r4.txt').write_text(notice,'utf8')
    for name,body in [('更新说明-PvP74.3.md',text),('更新公告-PvP74.3.txt',notice)]:
        (ROOT/name).write_text(body,'utf8')
    for file,heading in [('待办清单.md','## 2026-11-16 r4正式交付'),('交接_性能与交互体验优化_20261116.md','## 13. r4正式交付')]:
        p=ROOT/file;body=p.read_text('utf8')
        if heading not in body:
            body+='\n'+heading+'\n\n用户确认当前体验足够交付，r4在PC/Android正常启动时默认启用已测试的五项呈现/调度开关和8ms步预算。候选历史记录保持不变。正式包、启动器及存档验证见[交付记录](test_results/pvp744/release-r4-20261116/local-delivery-verification.json)，功能变化见[更新说明](更新说明-PvP74.3-r4.md)。T01/T02/T24和历史27项未豁免仍开放，T22仍暂停。\n'
        if file=='待办清单.md':body=body.replace('（PvP74.3 r3）','（PvP74.3 r4）',1)
        if file=='待办清单.md':
            lines=body.splitlines()
            for i,line in enumerate(lines):
                if line.startswith('2026-11-16 性能体验接手入口：'):
                    lines[i]='2026-11-16 最新正式交付为PvP74.3 r4，正常启动默认启用已验证的调度、快照和呈现优化；用户已反馈按键及时、绘制与逻辑更匹配并认可交付。高压稳定30FPS等长期目标仍开放。详见[更新说明](更新说明-PvP74.3-r4.md)、[交付核验](test_results/pvp744/release-r4-20261116/local-delivery-verification.json)及[性能交接](交接_性能与交互体验优化_20261116.md)。'
            body='\n'.join(lines)+'\n'
        else:
            body=body.replace('最新续建结果见第12节及[元数据与安卓候选验收](test_results/pvp744/metadata-20261116/assessment.md)。前节保留历轮历史结果。','最新正式交付见第13节及[更新说明](更新说明-PvP74.3-r4.md)。第1–12节保留实施与候选验收历史。')
            body=body.replace('生产版本仍为 PvP74.3 r3；本轮实验工具未改正式游戏的控制器。建议实施方案不能当成已完成优化。','当前正式版本为 PvP74.3 r4；已验收配置默认启用，完整交付核验见第13节。下文早期建议与r3状态属于历史，不能覆盖最新交付记录。')
        p.write_text(body,'utf8')

def refresh_docs():
    for name in ['更新说明-PvP74.3-r4.md','更新公告-PvP74.3-r4.txt','更新说明-PvP74.3.md','更新公告-PvP74.3.txt']:
        shutil.copy2(ROOT/name,STAGE/name)
    shutil.copy2(ROOT/'待办清单.md',STAGE/'当前待办清单.md')

def stage():
    assert not STAGE.exists()
    assert sha(OLD/'PvZPvPNative.exe')==read(OUT/'before.json')['official']
    notes();shutil.copytree(OLD,STAGE)
    build=ROOT/'build/app-typed72-v2/Release'
    for name in ['PvZPvPNative.exe','relay.json']+[p.name for p in build.glob('SDL2*.dll')]:shutil.copy2(build/name,STAGE/name)
    for relative in ['extract/data','extract/assets','fonts']:
        assert not tree(STAGE/relative).keys()-tree(ROOT/relative).keys()
        shutil.copytree(ROOT/relative,STAGE/relative,dirs_exist_ok=True)
    refresh_docs()
    dump(STAGE/'release-revision.json',dict(compatibility_build=VERSION,delivery_revision=REV,user_accepted_release=True,
        default_performance_options={**{k:1 for k in FLAGS},'PVP744_STEP_BUDGET_MS':8},neural_ai_optimization='paused'))
    dump(OUT/'stage.json',dict(exe_sha256=sha(STAGE/'PvZPvPNative.exe'),files=len(tree(STAGE))))
    print('PC staged',flush=True)

def run_diagnostic(exe,folder,config,default_path=False,launcher=False):
    import psutil
    folder.mkdir(exist_ok=False)
    cfg=folder/'config.json';dump(cfg,config)
    env={k:v for k,v in os.environ.items() if not k.startswith('PVP744_')}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP741_PROFILE='0')
    if default_path:
        env.pop('PVP_USERDATA',None);env['APPDATA']=str(folder/'default-appdata')
        fixture=Path(env['APPDATA'])/'PVZ-PvP-Native/pvp_userdata';fixture.mkdir(parents=True)
        (fixture/'preserve.bin').write_bytes(bytes(range(256)))
    elif not launcher:env['PVP_USERDATA']=str(folder/'userdata')
    else:env.pop('PVP_USERDATA',None)
    reportdir=exe.parent/'reports';old=set(reportdir.glob('*')) if reportdir.exists() else set()
    cmd=['cmd.exe','/d','/c',str(ROOT/'启动PvP.cmd'),'--diagnostic',str(cfg)] if launcher else [str(exe),'--diagnostic',str(cfg)]
    observed=[]
    with (folder/'stdout.log').open('wb') as log:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        deadline=time.monotonic()+120
        while proc.poll() is None:
            if time.monotonic()>deadline:proc.terminate();raise TimeoutError('Diagnostic deadline')
            try:
                parent=psutil.Process(proc.pid)
                children=[parent]+parent.children(recursive=True)
            except psutil.NoSuchProcess:
                children=[]  # process can exit between poll() and enumeration
            for child in children:
                try:
                    path=Path(child.exe()).resolve()
                    if path==exe.resolve() and not observed:observed.append(dict(pid=child.pid,exe=str(path),sha256=sha(path)))
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            time.sleep(.1)
    assert proc.returncode==0,(folder/'stdout.log').read_text('utf8',errors='replace')[-1500:]
    assert observed,'Actual EXE process was not observed'
    fresh=set(reportdir.glob('*'))-old
    reports=[p for p in fresh if p.suffix=='.json' and not p.name.endswith('.live.json')]
    assert len(reports)==1
    report=read(reports[0]);assert report['completed'] and report['native72']['build']==VERSION
    assert report['userdata_audit']['unchanged'] and report['backend_audit']['performance']['function_profile']=={}
    for f in fresh:
        assert f.resolve().is_relative_to(ROOT) and folder.resolve().is_relative_to(ROOT)
        shutil.copy2(f,folder/f.name);f.unlink()
    dump(folder/'report.json',report);dump(folder/'process.json',observed)
    return report

def smoke():
    before=users()
    cfg=dict(scenario='ordinary',units=20,warmup_seconds=0,seconds=3,audit_userdata=True)
    d=run_diagnostic(STAGE/'PvZPvPNative.exe',OUT/'pc-default',cfg,default_path=True)
    effective=d['scheduling']['configuration']
    assert all(effective[k] for k in ['candidate','view_reuse','local_frame','state_view','metadata_view']) and effective['step_budget_ms']==8
    assert d['backend_audit']['metadata_view']['private_adoptions']>0
    cfg['engine_options']={**{k:False for k in FLAGS},'PVP744_STEP_BUDGET_MS':0}
    d=run_diagnostic(STAGE/'PvZPvPNative.exe',OUT/'pc-explicit-off',cfg)
    assert not d['scheduling']['configuration']['candidate'] and d['backend_audit']['metadata_view']['builds']==0
    assert d['scheduling']['configuration']['step_budget_ms']==0 and not d['scheduling']['configuration']['local_frame']
    assert before==users() and not (STAGE/'pvp_userdata').exists()
    dump(OUT/'pc-smoke-verification.json',dict(passed=True,defaults=effective,explicit_opt_out_passed=True,
        default_userdata_path_isolated=True,actual_user_data_unchanged=True,exe_sha256=sha(STAGE/'PvZPvPNative.exe')))
    print('Default-on and explicit-off packaged EXE checks passed',flush=True)

def packages():
    assert read(OUT/'pc-smoke-verification.json')['passed']
    assert read(OUT/'android-package-verification.json')['passed']
    assert read(OUT/'android-device-verification.json')['passed']
    refresh_docs()
    files={p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert not any(Path(n).parts[0] in ('reports','pvp_userdata') for n in files)
    (STAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  ./'+n+'\n' for n,p in sorted(files.items())),'utf8')
    files['SHA256SUMS']=STAGE/'SHA256SUMS'
    pc=archive(STAGE.with_suffix('.zip'),files,'PvZ-PvP-Native/');pc.update(passed=True,payload=tree(STAGE))
    dump(OUT/'pc-package-verification.json',pc)
    previous=Path(read(OUT/'before.json')['previous']['developer_package']);entries={};inherited=[]
    with zipfile.ZipFile(previous) as z:
        for info in z.infolist():
            if info.is_dir():continue
            rel=info.filename.split('/',1)[1]
            if rel in ('SHA256SUMS.txt','MANIFEST-PvP74.3.json','STAGING_STATUS.json'):continue
            p=(ROOT/rel).resolve();assert p.is_relative_to(ROOT)
            if p.is_file():entries[rel]=p
            else:entries[rel]=z.read(info);inherited.append(rel)
    dev=load_module('developer_file_filter',ROOT/'build/pvp743-tools/package_dev743.py')
    for scope in ['src','tools','android','docs','developer-tools','extract/data','extract/schema','third_party/zlib-1.3.2-compress']:
        entries.update(dict(dev.walk(ROOT/scope,scope)))
    extra=set(read(OUT/'before.json')['files'])|{'tools/pvp743_release_r4.py','更新说明-PvP74.3-r4.md','更新公告-PvP74.3-r4.txt','待办清单.md'}
    evidence=ROOT/'test_results/pvp744/metadata-20261116'
    extra|={p.relative_to(ROOT).as_posix() for p in (evidence/'checks-final').glob('*.json')}
    extra|={(evidence/n).relative_to(ROOT).as_posix() for n in ['assessment.md','delivery-verification.json','ab/summary.json','ba/summary.json','wall-ab/summary.json','profile/summary.json','android-clean-final/summary.json']}
    extra|={p.relative_to(ROOT).as_posix() for p in OUT.glob('*verification.json')}
    extra|={(OUT/n).relative_to(ROOT).as_posix() for n in ['pc-default/report.json','pc-explicit-off/report.json']}
    for rel in extra:entries[rel]=ROOT/rel
    entries['README.md']=('# PvP74.3 r4 开发者包\n\n包含完整继承的生产内核、组合层、资源、生成器和当前源码。正式默认配置拥有者为src/app/main.cpp；运行开关可覆盖，战斗规则不变。\n\n本轮139项定向检查和安卓实机对照、用户交付认可见更新说明-PvP74.3-r4.md。完整2366项回归本次未重跑，历史27项未豁免继续开放。旧说明和证据作为历史保留。构建步骤见build/pvp743-tools/README-PvP74.3-dev.md和AGENTS.md。\n').encode('utf8')
    status=dict(revision=REV,compatibility_build=VERSION,user_accepted_release=True,targeted_checks=139,
        defaults_verified_pc_android=True,full_suite_rerun=False,historical_unwaived=27,product_acceptance_passed=False)
    entries['STAGING_STATUS.json']=json.dumps(status,ensure_ascii=False,indent=2).encode('utf8')
    hashes={n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in entries.items()}
    entries['MANIFEST-PvP74.3.json']=json.dumps(dict(revision=REV,base_archive_sha256=sha(previous),historical_metadata_retained=inherited,files=hashes,validation=status),ensure_ascii=False,indent=2).encode('utf8')
    hashes['MANIFEST-PvP74.3.json']=hashlib.sha256(entries['MANIFEST-PvP74.3.json']).hexdigest()
    entries['SHA256SUMS.txt']=''.join(h+'  '+n+'\n' for n,h in sorted(hashes.items())).encode('utf8')
    source=archive(STAGE.with_name(STAGE.name+'-Developer-Package.zip'),entries,'PvZ-PvP-Native-PvP74.3-src/')
    source.update(passed=True,previous_source_set_retained=True)
    dump(OUT/'source-package-verification.json',source)
    print('PC and complete developer archives verified',flush=True)

def promote():
    import psutil
    pc=read(OUT/'pc-package-verification.json');source=read(OUT/'source-package-verification.json');apk=read(OUT/'android-package-verification.json')
    assert tree(STAGE)==pc['payload'] and all(x['passed'] for x in [pc,source,apk])
    for obj,key in [(pc,'path'),(source,'path'),(apk,'apk')]:assert sha(Path(obj[key]))==obj['sha256']
    previous=read(ROOT/'dist/latest-native-release.json');assert previous['revision']=='pvp743-r3'
    dest=ROOT/'PVZ_rougePvP_native';assert sha(dest/'PvZPvPNative.exe')==previous['exe_sha256']
    assert not [p.info['pid'] for p in psutil.process_iter(['pid','exe']) if p.info['exe'] and Path(p.info['exe']).resolve()==(dest/'PvZPvPNative.exe').resolve()]
    launchers={p:sha(p) for p in [ROOT/'启动PvP.cmd',dest/'launch_pvp.cmd']}
    assert '%~dp0pvp_userdata' in (dest/'launch_pvp.cmd').read_text('utf-8-sig')
    before=users();dump(OUT/'userdata-before-promote.json',before)
    backup=ROOT/'backup-latest';records=[]
    for key,hashkey,name in [('pc_zip','pc_zip_sha256','previous-release.zip'),('developer_package','developer_sha256','previous-source.zip'),('apk','apk_sha256','previous-android.apk')]:
        origin=Path(previous[key]);assert sha(origin)==previous[hashkey]
        if not (backup/name).exists() or sha(backup/name)!=sha(origin):shutil.copy2(origin,backup/name)
        records.append(dict(file=str(backup/name),revision=previous['revision'],sha256=sha(backup/name),original_file=str(origin)))
    records += [r for r in read(backup/'manifest.json') if Path(r['file']).name=='performance-before.zip']
    dump(backup/'manifest.json',records)
    changed=[]
    for name,digest in pc['payload'].items():
        target=dest/name
        if not target.exists() or sha(target)!=digest:
            target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.next');assert not temp.exists()
            shutil.copy2(STAGE/name,temp);assert sha(temp)==digest;os.replace(temp,target);changed.append(name)
        assert sha(target)==digest
    assert all(sha(p)==h for p,h in launchers.items()) and before==users()
    d=run_diagnostic(dest/'PvZPvPNative.exe',OUT/'root-launcher-check',dict(scenario='ordinary',units=20,warmup_seconds=0,seconds=3,audit_userdata=True),launcher=True)
    assert d['scheduling']['configuration']['metadata_view'] and d['backend_audit']['metadata_view']['private_adoptions']>0
    after=users();dump(OUT/'userdata-after-promote.json',after);assert before==after
    result=dict(passed=True,version=VERSION,revision=REV,updated_at=datetime.now().isoformat(),launcher=str(ROOT/'启动PvP.cmd'),target=str(dest/'PvZPvPNative.exe'),
        exe_sha256=sha(dest/'PvZPvPNative.exe'),release=str(STAGE),pc_zip=pc['path'],pc_zip_sha256=pc['sha256'],developer_package=source['path'],developer_sha256=source['sha256'],source_package='complete',
        apk=apk['apk'],apk_sha256=apk['sha256'],android_version_code=1114085,android_signature_continuity_verified=True,android_real_device_verified=True,
        all_user_files_preserved=True,userdata_files_verified=sum(len(x or {}) for x in before.values()),shipped_files_verified=len(pc['payload']),changed_managed_files=changed,
        launcher_files_preserved=True,root_launcher_executed=True,pc_packaged_exe_run=True,defaults_verified=True,user_accepted_release=True,
        backup_revisions=[previous['revision']],backup_folder=str(backup),targeted_checks=139,full_regression_rerun=False,historical_unwaived=27,product_acceptance_passed=False,
        github='not_published_this_revision',release_notes=str(ROOT/'更新说明-PvP74.3-r4.md'),verification=str(OUT/'local-delivery-verification.json'))
    dump(OUT/'local-delivery-verification.json',result);dump(ROOT/'dist/latest-native-release.json',result);dump(ROOT/'dist/PvP74.3-r4-发行清单.json',result)
    print(json.dumps({k:result[k] for k in ['passed','revision','exe_sha256','userdata_files_verified','shipped_files_verified','root_launcher_executed']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','smoke','packages','promote']);a=p.parse_args();globals()[a.action]()
