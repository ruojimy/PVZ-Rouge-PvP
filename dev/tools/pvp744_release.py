"""Build-independent staging, verification and promotion of the authorized 74.4 release.

Native Windows/Android builds run separately; no signing secrets are handled here.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test_results/pvp744/release-20261117'
STAGE = ROOT / 'dist/PvZ-PvP-Native-20261117-pvp744-r1'
BUILD = ROOT / 'build/app-typed72-v2/Release'
VERSION = '1.6.0.74.4-typed.20261117'
REV = 'pvp744-r1'
CODE = 1117001
NATIVE_RUN = 'pvp744-release-20261117-r1'
WSL = Path(r'\\wsl.localhost\Ubuntu\home\ruojimy\pvz-native-android')

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

helpers = module('r4_release_helpers', ROOT / 'tools/pvp743_release_r4.py')
sha, read, dump, tree, users, archive = (getattr(helpers, n) for n in ('sha','read','dump','tree','users','archive'))
helpers.VERSION, helpers.OUT, helpers.STAGE = VERSION, OUT, STAGE

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'before.json').exists()
    previous = read(ROOT / 'dist/latest-native-release.json')
    assert previous['revision'] == 'pvp743-r4'
    assert sha(Path(previous['target'])) == previous['exe_sha256']
    launchers = {str(p): sha(p) for p in (ROOT/'启动PvP.cmd', ROOT/'PVZ_rougePvP_native/launch_pvp.cmd')}
    before = dict(previous=previous, users=users(), launchers=launchers,
                  version=read(ROOT/'extract/data/__init__.json'), recorded_at=datetime.now().isoformat())
    dump(OUT/'before.json', before)
    backup = (ROOT/'backup-latest').resolve()
    assert backup.parent == ROOT.resolve() and backup.name == 'backup-latest'
    backup.mkdir(exist_ok=True)
    old_files = [p for p in backup.iterdir() if p.is_file()]
    records = []
    for key, hashkey, name in [('pc_zip','pc_zip_sha256','previous-release.zip'),
                               ('developer_package','developer_sha256','previous-source.zip'),
                               ('apk','apk_sha256','previous-android.apk')]:
        source = Path(previous[key]); assert sha(source) == previous[hashkey]
        temp = backup/(name+'.next'); assert not temp.exists()
        shutil.copy2(source, temp); assert sha(temp) == previous[hashkey]
        os.replace(temp, backup/name)
        records.append(dict(file=str(backup/name), revision=previous['revision'],
                            sha256=sha(backup/name), original_file=str(source)))
    source_snapshot = {'extract/data/__init__.json': ROOT/'extract/data/__init__.json',
                       'dist/latest-native-release.json': ROOT/'dist/latest-native-release.json',
                       '启动PvP.cmd': ROOT/'启动PvP.cmd',
                       'PVZ_rougePvP_native/launch_pvp.cmd': ROOT/'PVZ_rougePvP_native/launch_pvp.cmd'}
    snapshot = backup/'release-state-before.zip'
    assert not snapshot.exists()
    a = archive(snapshot, source_snapshot, 'before-74.4/')
    records.append(dict(file=a['path'], revision='pre-pvp744-release', sha256=a['sha256']))
    dump(backup/'manifest.json', records)
    keep = {Path(r['file']).name for r in records} | {'manifest.json', 'release-state-before.zip.sha256'}
    for p in old_files:
        assert p.resolve().parent == backup
        if p.name not in keep: p.unlink()
    dump(OUT/'backup-verification.json', dict(passed=True, records=records, latest_group_only=True))
    dump(ROOT/'extract/data/__init__.json', {'BUILD':VERSION, 'PROTOCOL':1})
    notes = '''# PvP74.4 正式版

2026-11-17，构建 1.6.0.74.4-typed.20261117，发布修订 pvp744-r1。

- 修复材质覆盖串用：火焰、投射物、头部缓存、透明顺序与工坊跨范围回退；覆盖仅改变显示。
- 修复 PvP、2v2 与合作模式在夜晚、雨天生成天空阳光；保留各模式的地图和合作昼夜规则。
- 本地演练新增“测试模式”：立即开局、双方各 13 个空卡槽；局内换卡、修改经济/血量/防御、重置冷却、切换昼夜、清理植物或僵尸。
- 测试模式加入克苏鲁之眼、世界吞噬者、骷髅王，僵尸方 0 脑光召唤，包含仆从、独立身体分节/双手、阶段变化和昼夜行为；采用普通模式数值。对植物和植物戴夫伤害除以 10，对魅惑僵尸保持原值；免疫魅惑和甜薯。Boss 使用基于原版的材质、声音、碎片；已按 PvZ 地图和阵营规则适配，未包含泰拉瑞亚掉落和生物群系系统。
- 修复密集同时爆炸超过绘制指令上限造成的异常退出：瞬时特效超预算时降级，保留单位绘制，不改变爆炸伤害与战斗随机数。
- 触控布局支持方形/圆形按键、圆盘摇杆/移动键/关闭移动控件、上拉跳跃角度范围、左-自动-右滑动按钮；新增可开关、校准与调阈值的陀螺仪移动，默认关闭。
- 保留 74.3 r4 已启用的调度、快照与呈现优化。

使用：本地演练 → 测试模式 → 测试选卡/作弊器。切到僵尸方选三个 Boss；克苏鲁之眼建议夜间测试，骷髅王白天会狂暴。
触控设置：进入自定义按键布局，点击对应按键切换；摇杆跳跃角度范围为 20°–160°，默认 60°。

PC 解压后运行“启动PvP.cmd”或 PvZPvPNative.exe，无需 Python。发布包默认使用 %APPDATA%\\PVZ-PvP-Native\\pvp_userdata；项目根启动入口继续使用原独立存档目录。
Android：arm64-v8a，包名 org.pvzrouge.pvzpvpnative，versionCode=1117001，沿用正式版签名，支持覆盖升级。联机双方应使用本次 74.4；新旧 BUILD 不混用。

验证范围：PC 生产库、实际 UI/渲染与回放定向检查；发布 EXE 启动、资源完整性与默认存档路径；APK 签名、递增版本、原生库与资源逐项哈希。
当前无连接手机，本次未做 Android 实机安装、触控/陀螺仪手感或低配手机长时压力验收。旧版本玩家反馈的所有闪退原因不能据此认定均已排除。完整产品回归本次未重跑，历史未豁免问题继续保留。
详细记录见 test_results/pvp744/release-20261117/；此前功能证据见 test_results/pvp744/explosion-controls-boss-20261116/实现与验证.md。
'''
    (ROOT/'更新说明-PvP74.4.md').write_text(notes, 'utf8')
    (ROOT/'更新公告-PvP74.4.txt').write_text('PvP74.4 正式版\n\n新增本地测试模式、三个泰拉瑞亚 Boss、局内作弊器；修复材质串用、夜晚/雨天掉阳光与密集爆炸绘制溢出。触控可切换形状、摇杆和三键滑动按钮，新增可选陀螺仪移动。\n\nAndroid 同签名覆盖升级，存档保留；本次尚未完成手机实机验证。联机请双方更新到 74.4。\n', 'utf8')
    print('Backup verified; 74.4 version and release notes prepared', flush=True)

def stage():
    assert not STAGE.exists()
    assert read(ROOT/'extract/data/__init__.json')['BUILD'] == VERSION
    STAGE.mkdir(); (STAGE/'extract').mkdir()
    for name in ['PvZPvPNative.exe','relay.json']+[p.name for p in BUILD.glob('SDL2*.dll')]:
        shutil.copy2(BUILD/name, STAGE/name)
    for name in ['图片','音乐','音效']: shutil.copytree(BUILD/name, STAGE/name)
    for name in ['extract/data','extract/assets','fonts']: shutil.copytree(ROOT/name, STAGE/name)
    for name in ['更新说明-PvP74.4.md','更新公告-PvP74.4.txt']: shutil.copy2(ROOT/name, STAGE/name)
    (STAGE/'启动PvP.cmd').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"%~dp0PvZPvPNative.exe" %*\r\nexit /b %errorlevel%\r\n')
    (STAGE/'启动说明.txt').write_text('PvP74.4 正式版\n\n完整解压后双击 启动PvP.cmd 或 PvZPvPNative.exe，无需 Python。\n默认存档与设置：%APPDATA%\\PVZ-PvP-Native\\pvp_userdata。\n保持 extract、图片、音乐、音效、fonts、relay.json 和 DLL 与 EXE 同目录。\n本地演练 → 测试模式 可体验三个 Boss 和作弊器。\n联机请双方使用 74.4。详细功能与验证范围见 更新说明-PvP74.4.md。\n异常退出请保留 crash-native.txt 和 reports 反馈。\n', 'utf-8-sig')
    dump(STAGE/'release-revision.json', dict(compatibility_build=VERSION, delivery_revision=REV,
         formal_release=True, release_authorized_by_user=True, android_real_device_verified=False,
         default_performance_options={**{k:1 for k in helpers.FLAGS}, 'PVP744_STEP_BUDGET_MS':8}))
    dump(OUT/'stage.json', dict(exe_sha256=sha(STAGE/'PvZPvPNative.exe'), files=len(tree(STAGE))))
    print('PC release staged', flush=True)

def smoke():
    helpers.smoke()
    # Exercise the current production-linked UI audit against the staged resources.
    cases = [('pvp744_testmode_audit','boss'), ('pvp744_controls_audit','controls'),
             ('pvp744_sky_weather_audit','weather'), ('pvp744_material_pixels_audit','material')]
    results = []
    for name, label in cases:
        folder = OUT/('packaged-'+label); assert not folder.exists(); folder.mkdir()
        target = folder/'results.json' if label == 'material' else folder
        env = dict(os.environ, PVZ_TEST_ROOT=str(STAGE), PVP_USERDATA=str(folder/'userdata'),
                   SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        with (folder/'audit.log').open('wb') as log:
            r = subprocess.run([str(BUILD/(name+'.exe')),str(target)], cwd=STAGE, env=env,
                               stdout=log, stderr=subprocess.STDOUT, timeout=300, creationflags=0x08000000)
        assert r.returncode == 0, (label,r.returncode)
        report = read(folder/'results.json')
        assert report.get('failures',report.get('errors',0)) == 0
        results.append(dict(case=label, checks=len(report['checks']), passed=True,
                            executable_sha256=sha(BUILD/(name+'.exe')), report=str(folder/'results.json')))
    assert users() == read(OUT/'before.json')['users']
    dump(OUT/'packaged-feature-verification.json', dict(passed=True,cases=results))
    print('Staged resources, Boss/UI, controls, weather and material checks passed', flush=True)

def apk():
    native = WSL/'candidates'/NATIVE_RUN
    assemblies = list(native.glob('apk-'+str(CODE)+'-*')); assert len(assemblies) == 1
    assembly = assemblies[0]
    source = WSL/'out'/f'PvZ-PvP-Native-{VERSION}-{CODE}-{NATIVE_RUN}.apk'
    folder = ROOT/'dist/apk-pvp744-r1-20261117'; folder.mkdir(exist_ok=True)
    dest = folder/source.name
    if not dest.exists(): shutil.copy2(source,dest)
    assert sha(dest) == sha(source)
    badging = (assembly/'badging.txt').read_text('utf8')
    assert f"package: name='org.pvzrouge.pvzpvpnative' versionCode='{CODE}' versionName='{VERSION}'" in badging
    assert "native-code: 'arm64-v8a'" in badging
    cert = (assembly/'certificate.txt').read_text('utf8')
    previous_cert = (assembly/'previous-certificate.txt').read_text('utf8')
    cert_sha = [x for x in cert.splitlines() if 'certificate SHA-256 digest:' in x]
    assert cert_sha and cert_sha == [x for x in previous_cert.splitlines() if 'certificate SHA-256 digest:' in x]
    assert CODE > read(OUT/'before.json')['previous']['android_version_code']
    hashes = {}; assets = {}; native_hashes = {}
    # Android's asset names are UTF-8 even when aapt leaves ZIP flag 11 unset.
    with zipfile.ZipFile(dest, metadata_encoding='utf-8') as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist()))
        assert json.loads(z.read('assets/extract/data/__init__.json'))['BUILD'] == VERSION
        for p in (native/'jniLibs/arm64-v8a').glob('*.so'):
            assert hashlib.sha256(z.read('lib/arm64-v8a/'+p.name)).hexdigest() == sha(p)
            native_hashes[p.name] = sha(p)
        for p in (assembly/'assets').rglob('*'):
            if not p.is_file(): continue
            rel = p.relative_to(assembly/'assets').as_posix()
            assert hashlib.sha256(z.read('assets/'+rel)).hexdigest() == sha(p), rel
            assets[rel] = sha(p)
        # In particular, all current Terraria sound/graphics files and current data must ship.
        for scope in ['extract/data','extract/assets','fonts']:
            for rel,h in tree(ROOT/scope).items(): assert assets[scope+'/'+rel] == h, scope+'/'+rel
    for name in ['badging.txt','previous-badging.txt','certificate.txt','previous-certificate.txt','signature.log','sdl-java-patches.json']:
        shutil.copy2(assembly/name, OUT/('android-'+name))
    shutil.copy2(native/'source-arm64-v8a.after.sha256', OUT/'android-source.sha256')
    digest=sha(dest); dest.with_suffix('.apk.sha256').write_text(digest+'  '+dest.name+'\n','utf8')
    dump(OUT/'android-package-verification.json', dict(passed=True,apk=str(dest),sha256=digest,
         bytes=dest.stat().st_size,package='org.pvzrouge.pvzpvpnative',version_name=VERSION,
         version_code=CODE,abi=['arm64-v8a'],certificate_continuity_verified=True,
         certificate_sha256=cert_sha,zip_crc_verified=True,native_libraries=native_hashes,
         all_assets=assets,source_fingerprint_verified=True,real_device_verified=False,installed=False))
    print('Signed APK identity, upgrade continuity, libraries and all assets verified', flush=True)

def packages():
    for filename in ['pc-smoke-verification.json','packaged-feature-verification.json','android-package-verification.json']:
        assert read(OUT/filename)['passed']
    files={p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert not any(Path(n).parts[0] in ('reports','pvp_userdata') for n in files)
    (STAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  ./'+n+'\n' for n,p in sorted(files.items())),'utf8')
    files['SHA256SUMS']=STAGE/'SHA256SUMS'
    pc=archive(STAGE.with_suffix('.zip'),files,'PvZ-PvP-Native/'); pc.update(passed=True,payload=tree(STAGE))
    dump(OUT/'pc-package-verification.json',pc)
    previous=Path(read(OUT/'before.json')['previous']['developer_package']); entries={}; inherited=[]
    with zipfile.ZipFile(previous) as z:
        for info in z.infolist():
            if info.is_dir(): continue
            rel=info.filename.split('/',1)[1]
            if rel in ('SHA256SUMS.txt','MANIFEST-PvP74.3.json','STAGING_STATUS.json'): continue
            p=(ROOT/rel).resolve(); assert p.is_relative_to(ROOT.resolve())
            if p.is_file(): entries[rel]=p
            else: entries[rel]=z.read(info); inherited.append(rel)
    dev=module('developer_filter', ROOT/'build/pvp743-tools/package_dev743.py')
    for scope in dev.OWNED_DIRS+['third_party/zlib-1.3.2-compress']:
        entries.update(dict(dev.walk(ROOT/scope,scope)))
    for name in ['CMakeLists.txt','AGENTS.md','更新说明-PvP74.4.md','更新公告-PvP74.4.txt']:
        entries[name]=ROOT/name
    evidence=ROOT/'test_results/pvp744/explosion-controls-boss-20261116'
    work=read(evidence/'work.json')
    for rel in ['work.json','实现与验证.md','source-sha256.json']+[v['path'] for v in work['verification']]:
        entries[(evidence/rel).relative_to(ROOT).as_posix()]=evidence/rel
    for p in OUT.glob('*verification.json'): entries[p.relative_to(ROOT).as_posix()]=p
    entries['README.md']=('# PvP74.4 开发者包\n\n完整生产源码、生成器、冻结内核/组合层与资源；新增功能及验证边界见更新说明-PvP74.4.md。\n构建步骤见 build/pvp743-tools/README-PvP74.3-dev.md 与 AGENTS.md；旧版本说明/证据按历史保留。\nAndroid 构建使用独立本机 SDK/SDL/签名依赖，签名私钥不包含在开发者包中。\n').encode('utf8')
    status=dict(revision=REV,compatibility_build=VERSION,formal_release=True,
                release_authorized_by_user=True,pc_package_verified=True,android_package_verified=True,
                android_real_device_verified=False,full_regression_rerun=False,product_acceptance_passed=False)
    entries['STAGING_STATUS.json']=json.dumps(status,ensure_ascii=False,indent=2).encode('utf8')
    for n,p in entries.items():
        if Path(n).suffix in dev.TEXT_SUFFIXES:
            assert not dev.SECRET.search(p.read_bytes() if isinstance(p,Path) else p), 'Secret pattern in '+n
    hashes={n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in entries.items()}
    entries['MANIFEST-PvP74.4.json']=json.dumps(dict(revision=REV,base_archive_sha256=sha(previous),
       historical_metadata_retained=inherited,files=hashes,validation=status),ensure_ascii=False,indent=2).encode('utf8')
    hashes['MANIFEST-PvP74.4.json']=hashlib.sha256(entries['MANIFEST-PvP74.4.json']).hexdigest()
    entries['SHA256SUMS.txt']=''.join(h+'  '+n+'\n' for n,h in sorted(hashes.items())).encode('utf8')
    source=archive(STAGE.with_name(STAGE.name+'-Developer-Package.zip'),entries,'PvZ-PvP-Native-PvP74.4-src/')
    source.update(passed=True,previous_source_set_retained=True)
    dump(OUT/'source-package-verification.json',source)
    print('PC and developer ZIP CRC and every payload hash verified',flush=True)

def promote():
    import psutil
    pc=read(OUT/'pc-package-verification.json'); source=read(OUT/'source-package-verification.json'); apk=read(OUT/'android-package-verification.json')
    assert tree(STAGE)==pc['payload'] and all(x['passed'] for x in [pc,source,apk])
    for obj,key in [(pc,'path'),(source,'path'),(apk,'apk')]: assert sha(Path(obj[key]))==obj['sha256']
    before=read(OUT/'before.json'); previous=before['previous']
    assert read(ROOT/'dist/latest-native-release.json')==previous
    dest=ROOT/'PVZ_rougePvP_native'; assert sha(dest/'PvZPvPNative.exe')==previous['exe_sha256']
    running=[p.info['pid'] for p in psutil.process_iter(['pid','exe']) if p.info['exe'] and Path(p.info['exe']).resolve()==(dest/'PvZPvPNative.exe').resolve()]
    assert not running, 'Existing game is running: '+str(running)
    assert users()==before['users']
    assert '%~dp0pvp_userdata' in (dest/'launch_pvp.cmd').read_text('utf-8-sig')
    changed=[]
    for name,digest in pc['payload'].items():
        target=dest/name
        if not target.exists() or sha(target)!=digest:
            target.parent.mkdir(parents=True,exist_ok=True); temp=target.with_name(target.name+'.next'); assert not temp.exists()
            shutil.copy2(STAGE/name,temp); assert sha(temp)==digest; os.replace(temp,target); changed.append(name)
        assert sha(target)==digest
    assert all(sha(Path(p))==h for p,h in before['launchers'].items()) and users()==before['users']
    d=helpers.run_diagnostic(dest/'PvZPvPNative.exe',OUT/'root-launcher-check',
       dict(scenario='ordinary',units=20,warmup_seconds=0,seconds=3,audit_userdata=True),launcher=True)
    assert d['scheduling']['configuration']['metadata_view'] and d['backend_audit']['metadata_view']['private_adoptions']>0
    after=users(); dump(OUT/'userdata-after-promote.json',after); assert before['users']==after
    assert all(sha(Path(p))==h for p,h in before['launchers'].items())
    result=dict(passed=True,version=VERSION,revision=REV,updated_at=datetime.now().isoformat(),
        launcher=str(ROOT/'启动PvP.cmd'),target=str(dest/'PvZPvPNative.exe'),exe_sha256=sha(dest/'PvZPvPNative.exe'),
        release=str(STAGE),pc_zip=pc['path'],pc_zip_sha256=pc['sha256'],developer_package=source['path'],
        developer_sha256=source['sha256'],source_package='complete',apk=apk['apk'],apk_sha256=apk['sha256'],
        android_version_code=CODE,android_signature_continuity_verified=True,android_real_device_verified=False,
        all_user_files_preserved=True,userdata_files_verified=sum(len(x or {}) for x in before['users'].values()),
        shipped_files_verified=len(pc['payload']),changed_managed_files=changed,launcher_files_preserved=True,
        root_launcher_executed=True,pc_packaged_exe_run=True,defaults_verified=True,release_authorized_by_user=True,
        backup_revisions=[previous['revision']],backup_folder=str(ROOT/'backup-latest'),
        full_regression_rerun=False,historical_unwaived=27,product_acceptance_passed=False,
        github='not_published_this_revision',release_notes=str(ROOT/'更新说明-PvP74.4.md'),
        verification=str(OUT/'local-delivery-verification.json'))
    dump(OUT/'local-delivery-verification.json',result); dump(ROOT/'dist/latest-native-release.json',result)
    dump(ROOT/'dist/PvP74.4-r1-发行清单.json',result)
    print(json.dumps({k:result[k] for k in ['passed','revision','exe_sha256','userdata_files_verified','shipped_files_verified','root_launcher_executed']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','stage','smoke','apk','packages','promote'])
    globals()[p.parse_args().action]()
