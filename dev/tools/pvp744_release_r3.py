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
sys.path.insert(0,str(ROOT/'tools'))
from native_regression_report import combat_errors, digest, fire_errors, full_inventory, compare
OUT = ROOT / 'test_results/pvp744/r3-feedback-20261117'
STAGE = ROOT / 'dist/PvZ-PvP-Native-20261117-pvp744-r3'
BUILD = ROOT / 'build/app-typed72-v2/Release'
VERSION = '1.6.0.74.4-typed.20261117-r3'
REV = 'pvp744-r3'
CODE = 1117003
NATIVE_RUN = 'pvp744-release-20261117-r3-gift-final'
WSL = Path(r'\\wsl.localhost\Ubuntu\home\ruojimy\pvz-native-android')

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

helpers = module('r4_release_helpers', ROOT / 'tools/pvp743_release_r4.py')
sha, read, dump, tree, users, archive = (getattr(helpers, n) for n in ('sha','read','dump','tree','users','archive'))
helpers.VERSION, helpers.OUT, helpers.STAGE = VERSION, OUT, STAGE

PREVIOUS_REV = 'pvp744-r2'
APK_DIR = ROOT/'dist/apk-pvp744-r3-20261117'
EXTRA_AUDITS = []

def regression_status():
    summary=OUT/'full-suite/summary.json'
    result=read(summary)
    ids=full_inventory(result,summary.parent)
    if result.get('scope')!='full' or result.get('build_version')!=VERSION:
        raise ValueError('Release requires a current full-suite report for '+VERSION)
    binaries={'game':'PvZPvPNative.exe','cpp_tests':'cpp_tests.exe','app_run':'app_run.exe','audit':'pvp744_r4_audit.exe',
              'fire':'fire741_production_audit.exe'}
    if (result.get('changed_binaries')!=[] or result['source_changed_during_run'] or result['fixture_changed_during_run']
            or result['exe_changed_during_run'] or result['binary_sha256']!={k:digest(BUILD/v) for k,v in binaries.items()}
            or digest(STAGE/'PvZPvPNative.exe')!=result['binary_sha256']['game']):
        raise ValueError('Release binaries or test inputs differ from full-suite evidence')
    for name,expected in read(summary.parent/'source-hashes.json').items():
        if digest(ROOT/name)!=expected: raise ValueError('Source changed after full-suite run: '+name)
    if (not result['pure_typed_gate']['passed'] or result['pure_typed_gate']['exit']!=0
            or not result['combat_r4_gate']['passed'] or result['combat_r4_gate']['exit']!=0
            or combat_errors(read(summary.parent/'combat-r4/results.json')) or not result['fire_gate']['passed']
            or fire_errors(read(summary.parent/'combat-r4/fire-matrix.json'))):
        raise ValueError('Required production gates missing or failed')
    comparison=result['triage']
    baseline=Path(comparison['baseline'])
    last=read(OUT/'promotion-before.json')['previous'].get('full_regression_report')
    if (baseline.resolve()==summary.resolve() or (last and Path(last).resolve()!=baseline.resolve())
            or digest(baseline)!=comparison['baseline_sha256']):
        raise ValueError('Previous full-suite baseline missing or changed')
    previous=read(baseline)
    delta=compare(result,previous,ids,full_inventory(previous,baseline.parent))
    if comparison['comparison']!=delta: raise ValueError('Full-suite comparison differs from raw evidence')
    return dict(full_regression_rerun=True, full_regression_passed=result['success'],
                full_regression_counts=result['counts'], full_regression_report=str(summary),
                full_regression_baseline=str(baseline),full_regression_diff={k:len(v) for k,v in delta.items()},
                unwaived=len(result['waivers']['unexpected_nonpass']))

def prepare():
    before=read(OUT/'before.json'); previous=read(ROOT/'dist/latest-native-release.json')
    current=users()
    differences=[]
    for folder in set(current)|set(before['users']):
        old=before['users'].get(folder) or {}; new=current.get(folder) or {}
        for name in sorted(set(old)|set(new)):
            if old.get(name)!=new.get(name): differences.append(dict(folder=folder,path=name,before=old.get(name),after=new.get(name)))
    dump(OUT/'userdata-drift-before-release.json',dict(changes=differences,note='Current user files are preserved at promotion.'))
    dump(OUT/'promotion-before.json',dict(before,users=current,work_baseline=str(OUT/'before.json')))
    before=read(OUT/'promotion-before.json')
    assert previous==before['previous'] and previous['revision']==PREVIOUS_REV
    assert sha(Path(previous['target']))==previous['exe_sha256'] and users()==before['users']
    for name,key in [('previous-release.zip','pc_zip_sha256'),('previous-source.zip','developer_sha256'),('previous-android.apk','apk_sha256')]:
        assert sha(ROOT/'backup-latest'/name)==previous[key]
    assert all(sha(Path(p))==h for p,h in before['launchers'].items())
    dump(OUT/'backup-verification.json',dict(passed=True,revision=previous['revision'],latest_group_only=True))
    init=ROOT/'extract/data/__init__.json'
    if read(init).get('BUILD')!=VERSION: dump(init,{'BUILD':VERSION,'PROTOCOL':1})
    print(PREVIOUS_REV, 'backup verified for', REV, flush=True)


def stage():
    assert read(ROOT/'dist/latest-native-release.json')['revision']==PREVIOUS_REV
    if STAGE.exists(): assert read(STAGE/'release-revision.json')['delivery_revision']==REV
    assert read(ROOT/'extract/data/__init__.json')['BUILD'] == VERSION
    STAGE.mkdir(exist_ok=True); (STAGE/'extract').mkdir(exist_ok=True)
    for name in ['PvZPvPNative.exe','relay.json']+[p.name for p in BUILD.glob('SDL2*.dll')]:
        shutil.copy2(BUILD/name, STAGE/name)
    for name in ['图片','音乐','音效']: shutil.copytree(BUILD/name, STAGE/name,dirs_exist_ok=True)
    for name in ['extract/data','extract/assets','fonts']: shutil.copytree(ROOT/name, STAGE/name,dirs_exist_ok=True)
    for name in ['更新说明-PvP74.4.md','更新公告-PvP74.4.txt']: shutil.copy2(ROOT/name, STAGE/name)
    (STAGE/'启动PvP.cmd').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"%~dp0PvZPvPNative.exe" %*\r\nexit /b %errorlevel%\r\n')
    (STAGE/'启动说明.txt').write_text('PvP74.4 正式版\n\n完整解压后双击 启动PvP.cmd 或 PvZPvPNative.exe，无需 Python。\n默认存档与设置：%APPDATA%\\PVZ-PvP-Native\\pvp_userdata。\n保持 extract、图片、音乐、音效、fonts、relay.json 和 DLL 与 EXE 同目录。\n本地演练 → 测试模式 可体验三个 Boss 和作弊器；合作第 8/16/24 关新增 Boss。\n联机请双方使用本次 '+REV+'。详细功能与验证范围见 更新说明-PvP74.4.md。\n异常退出请保留 crash-native.txt 和 reports 反馈。\n', 'utf-8-sig')
    dump(STAGE/'release-revision.json', dict(compatibility_build=VERSION, delivery_revision=REV,
         formal_release=True, release_authorized_by_user=True, android_real_device_verified=False,
         default_performance_options={**{k:1 for k in helpers.FLAGS}, 'PVP744_STEP_BUDGET_MS':8}))
    dump(OUT/'stage.json', dict(exe_sha256=sha(STAGE/'PvZPvPNative.exe'), files=len(tree(STAGE))))
    print('PC release staged', flush=True)

def smoke():
    diagnostic_folder=OUT/'gift-pc-exe2';diagnostic_folder.mkdir(exist_ok=True)
    helpers.OUT=diagnostic_folder
    try: helpers.smoke()
    finally: helpers.OUT=OUT
    shutil.copy2(diagnostic_folder/'pc-smoke-verification.json',OUT/'pc-smoke-verification.json')
    # Exercise the current production-linked UI audit against the staged resources.
    cases = [('pvp744_testmode_audit','boss'), ('pvp744_controls_audit','controls'),
             ('pvp744_sky_weather_audit','weather'), ('pvp744_material_pixels_audit','material'), ('pvp744_feedback_audit','feedback'), ('pvp744_r3_audit','r3')] + EXTRA_AUDITS
    results = []
    for name, label in cases:
        folder = OUT/('packaged-gift-'+label); assert not folder.exists(); folder.mkdir()
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
    assert users() == read(OUT/'promotion-before.json')['users']
    dump(OUT/'packaged-feature-verification.json', dict(passed=True,cases=results))
    print('Staged resources, Boss/UI, controls, weather and material checks passed', flush=True)

def apk():
    native = WSL/'candidates'/NATIVE_RUN
    assemblies = list(native.glob('apk-'+str(CODE)+'-*')); assert len(assemblies) == 1
    assembly = assemblies[0]
    source = WSL/'out'/f'PvZ-PvP-Native-{VERSION}-{CODE}-{NATIVE_RUN}.apk'
    folder = APK_DIR; folder.mkdir(exist_ok=True)
    dest = folder/source.name
    if not dest.exists(): shutil.copy2(source,dest)
    assert sha(dest) == sha(source)
    badging = (assembly/'badging.txt').read_text('utf8')
    assert f"package: name='org.pvzrouge.pvzpvpnative' versionCode='{CODE}' versionName='{VERSION}'" in badging
    assert "native-code: 'arm64-v8a'" in badging
    assert "application-label:'肉鸽植物大战僵尸'" in badging
    cert = (assembly/'certificate.txt').read_text('utf8')
    previous_cert = (assembly/'previous-certificate.txt').read_text('utf8')
    cert_sha = [x for x in cert.splitlines() if 'certificate SHA-256 digest:' in x]
    assert cert_sha and cert_sha == [x for x in previous_cert.splitlines() if 'certificate SHA-256 digest:' in x]
    assert CODE > read(OUT/'promotion-before.json')['previous']['android_version_code']
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
    regression=regression_status()
    for filename in ['pc-smoke-verification.json','packaged-feature-verification.json','android-package-verification.json']:
        assert read(OUT/filename)['passed']
    files={p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert not any(Path(n).parts[0] in ('reports','pvp_userdata') for n in files)
    (STAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  ./'+n+'\n' for n,p in sorted(files.items())),'utf8')
    files['SHA256SUMS']=STAGE/'SHA256SUMS'
    pc=archive(STAGE.with_suffix('.zip'),files,'PvZ-PvP-Native/'); pc.update(passed=True,payload=tree(STAGE))
    dump(OUT/'pc-package-verification.json',pc)
    previous=Path(read(OUT/'promotion-before.json')['previous']['developer_package']); entries={}; inherited=[]
    with zipfile.ZipFile(previous) as z:
        for info in z.infolist():
            if info.is_dir(): continue
            rel=info.filename.split('/',1)[1]
            if rel in ('SHA256SUMS.txt','MANIFEST-PvP74.3.json','MANIFEST-PvP74.4.json','STAGING_STATUS.json'): continue
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
    feedback=ROOT/'test_results/pvp744/feedback-20261117'
    for rel in ['final-audit/results.json','texture-final/summary.json','controls/results.json','boss/results.json']:
        p=feedback/rel;entries[p.relative_to(ROOT).as_posix()]=p
    for p in OUT.glob('*verification.json'): entries[p.relative_to(ROOT).as_posix()]=p
    for p in list(OUT.glob('packaged-*/results.json'))+[OUT/'source-change-review.json']:
        entries[p.relative_to(ROOT).as_posix()]=p
    entries['README.md']=('# PvP74.4 开发者包\n\n完整生产源码、生成器、冻结内核/组合层与资源；新增功能及验证边界见更新说明-PvP74.4.md。\n构建步骤见 build/pvp743-tools/README-PvP74.3-dev.md 与 AGENTS.md；旧版本说明/证据按历史保留。\nAndroid 构建使用独立本机 SDK/SDL/签名依赖，签名私钥不包含在开发者包中。\n').encode('utf8')
    status=dict(revision=REV,compatibility_build=VERSION,formal_release=True,
                release_authorized_by_user=True,pc_package_verified=True,android_package_verified=True,
                android_real_device_verified=False,**regression,product_acceptance_passed=False)
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
    regression=regression_status()
    if not regression['full_regression_passed']:
        raise ValueError('Full regression has unresolved failures; see '+regression['full_regression_report'])
    import psutil
    pc=read(OUT/'pc-package-verification.json'); source=read(OUT/'source-package-verification.json'); apk=read(OUT/'android-package-verification.json')
    assert tree(STAGE)==pc['payload'] and all(x['passed'] for x in [pc,source,apk])
    for obj,key in [(pc,'path'),(source,'path'),(apk,'apk')]: assert sha(Path(obj[key]))==obj['sha256']
    before=read(OUT/'promotion-before.json'); previous=before['previous']
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
        **regression,product_acceptance_passed=False,
        github='not_published_this_revision',release_notes=str(ROOT/'更新说明-PvP74.4.md'),
        verification=str(OUT/'local-delivery-verification.json'))
    dump(OUT/'local-delivery-verification.json',result); dump(ROOT/'dist/latest-native-release.json',result)
    dump(ROOT/('dist/PvP74.4-'+REV.split('-')[-1]+'-发行清单.json'),result)
    print(json.dumps({k:result[k] for k in ['passed','revision','exe_sha256','userdata_files_verified','shipped_files_verified','root_launcher_executed']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','stage','smoke','apk','packages','promote'])
    globals()[p.parse_args().action]()
