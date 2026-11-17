"""Stage, verify and install this local revision without touching user saves."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'delivery'
STAGE=ROOT/'dist/PvZ-PvP-Native-20261116-pvp743-r3'
OLD=ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r2'
REV='pvp743-r3'
VERSION='1.6.0.74.3-typed.20261114'
OUT.mkdir(exist_ok=True)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def dump(p,value):
    temp=p.with_name(p.name+'.next');assert not temp.exists()
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,p)
def read(p):return json.loads(p.read_text('utf-8-sig'))
def tree(folder):return {p.relative_to(folder).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
def users():
    return {str(p):tree(p) if p.exists() else None for p in [ROOT/'PVZ_rougePvP_native/pvp_userdata',Path(os.environ['APPDATA'])/'PVZ-PvP-Native']}
def import_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class UTF8Info(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):return self.filename.encode('utf8'),self.flag_bits|0x800
def archive(target,entries,prefix):
    assert not target.exists(),target
    hashes={n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in entries.items()}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n,p in sorted(entries.items()):
            info=UTF8Info(prefix+n);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,p.read_bytes() if isinstance(p,Path) else p)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None and len(z.infolist())==len(hashes)
        for info in z.infolist():assert info.flag_bits&0x800 and hashlib.sha256(z.read(info)).hexdigest()==hashes[info.filename[len(prefix):]]
    digest=sha(target);target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n',encoding='utf8')
    return {'path':str(target),'sha256':digest,'files':len(entries),'crc_and_payload_verified':True,'utf8_all':True}
def stage():
    assert not STAGE.exists()
    assert sha(OLD/'PvZPvPNative.exe')=='4d0fe7c5762d4e2a1a949b21d5e7bca202d9cdbaf7500a18b3114fd60de80f5e'
    shutil.copytree(OLD,STAGE)
    build=ROOT/'build/app-typed72-v2/Release'
    for name in ['PvZPvPNative.exe','relay.json']+[p.name for p in build.glob('SDL2*.dll')]:shutil.copy2(build/name,STAGE/name)
    # Refresh current resources; no production atlas is modified by this release.
    for relative in ['extract/data','extract/assets','fonts']:
        old_files=tree(STAGE/relative);new_files=tree(ROOT/relative)
        assert not old_files.keys()-new_files.keys(),'Resource removal requires an explicit migration'
        shutil.copytree(ROOT/relative,STAGE/relative,dirs_exist_ok=True)
    refresh_docs()
    dump(STAGE/'release-revision.json',{'compatibility_build':VERSION,'delivery_revision':REV,'neural_ai_optimization':'paused','physical_device_acceptance':False})
    dump(OUT/'stage.json',{'exe_sha256':sha(STAGE/'PvZPvPNative.exe'),'files':len(tree(STAGE))})
    print('PC staged',STAGE,flush=True)
def refresh_docs():
    for name in ['更新说明-PvP74.3-r3.md','更新公告-PvP74.3-r3.txt']:shutil.copy2(ROOT/name,STAGE/name)
    shutil.copy2(ROOT/'更新公告-PvP74.3-r3.txt',STAGE/'更新公告-PvP74.3.txt')
    shutil.copy2(ROOT/'待办清单.md',STAGE/'当前待办清单.md')
def smoke():
    work=OUT/'pc-smoke'
    recovered=work.exists()
    if recovered:
        before=read(OUT/'userdata-before-smoke.json')
        assert 'PVP72_DIAGNOSTIC_COMPLETE' in (work/'stdout.log').read_text('utf8',errors='replace')
    else:
        before=users();dump(OUT/'userdata-before-smoke.json',before);work.mkdir(exist_ok=False)
        config=work/'config.json';dump(config,{'scenario':'ordinary','units':20,'warmup_seconds':0,'seconds':3})
        env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',APPDATA=str(work/'default-appdata'))
        env.pop('PVP_USERDATA',None)
        with (work/'stdout.log').open('wb') as log:
            result=subprocess.run([str(STAGE/'PvZPvPNative.exe'),'--diagnostic',str(config)],cwd=STAGE,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        assert result.returncode==0,'Packaged EXE diagnostic failed'
    reports=list((STAGE/'reports').glob('*.json'));assert len(reports)==1
    report=read(reports[0]);assert report['completed'] is True and report['native72']['build']==VERSION
    assert (STAGE/'reports').resolve().is_relative_to(ROOT) and (work/'reports').resolve().is_relative_to(ROOT)
    shutil.move(str(STAGE/'reports'),str(work/'reports'))
    assert before==users(),'User data changed during isolated diagnostic'
    assert not (STAGE/'pvp_userdata').exists()
    dump(work/'verification.json',{'passed':True,'exe_sha256':sha(STAGE/'PvZPvPNative.exe'),'default_APPDATA_isolated':True,'PVP_USERDATA_was_unset':True,'default_path_source':'src/app/main.cpp:259-263','diagnostic_completed':True,'user_data_unchanged':True,'validation_resumed_after_encoding_alias_error':recovered,'scope':'Packaged EXE launches and completes real typed/render diagnostic; SDL dummy, not FPS/device acceptance.'})
    print('Packaged PC diagnostic passed',flush=True)
def packages():
    full=read(OUT.parent/'full-comparison.json');assert not full['new_nonpass'] and full['pure_typed_passed'] and full['tests']==2366
    assert read(OUT/'pc-smoke/verification.json')['passed']
    assert read(OUT/'android-package-verification.json')['passed']
    frozen=read(OUT.parent/'additional-freeze.json')
    assert all(sha(ROOT/name)==digest for name,digest in frozen.items()),'Build/vendor changed after full regression'
    assert sha(STAGE/'PvZPvPNative.exe')==frozen['build/app-typed72-v2/Release/PvZPvPNative.exe']
    refresh_docs()
    files={p.relative_to(STAGE).as_posix():p for p in STAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert not any(Path(n).parts[0] in ('reports','pvp_userdata') for n in files)
    (STAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  ./'+n+'\n' for n,p in sorted(files.items())),encoding='utf8')
    files['SHA256SUMS']=STAGE/'SHA256SUMS'
    pc=archive(STAGE.with_suffix('.zip'),files,'PvZ-PvP-Native/');pc.update(passed=True,exe_sha256=sha(STAGE/'PvZPvPNative.exe'),payload=tree(STAGE))
    dump(OUT/'pc-package-verification.json',pc);print('PC ZIP verified',pc['files'],flush=True)
    previous=OLD.with_name(OLD.name+'-Developer-Package.zip');entries={};inherited=[]
    with zipfile.ZipFile(previous) as z:
        for info in z.infolist():
            if info.is_dir():continue
            rel=info.filename.split('/',1)[1]
            if rel in ('SHA256SUMS.txt','MANIFEST-PvP74.3.json','STAGING_STATUS.json'):continue
            path=(ROOT/rel).resolve();assert path.is_relative_to(ROOT)
            if path.is_file():entries[rel]=path
            else:
                assert Path(rel).suffix in ('.md','.txt','.json');entries[rel]=z.read(info);inherited.append(rel)
    base=import_file('dev_base',ROOT/'build/pvp743-tools/package_dev743.py')
    for scope in ['src','tools','android','docs','developer-tools','extract/data','extract/schema','third_party/zlib-1.3.2-compress']:
        entries.update(dict(base.walk(ROOT/scope,scope)))
    # Only explicit, small current evidence; never enumerate private user data.
    extra=['更新说明-PvP74.3-r3.md','更新公告-PvP74.3-r3.txt','待办清单.md','交接_游戏待办与验收_20261115.md',
      'test_results/pvp743/t24-queue-20261116/assessment.md','test_results/pvp743/t24-queue-20261116/packing-comparison.json','test_results/pvp743/t24-queue-20261116/full-comparison.json',
      'test_results/pvp743/t24-full-20261116/summary.json','test_results/pvp743/t24-full-20261116/waivers-applied.json','test_results/pvp743/t24-full-20261116/pure-typed-gate/pure-typed-gate.json']
    for folder in ['final-checks','cloud-native']:
        extra += [p.relative_to(ROOT).as_posix() for p in (OUT.parent/folder).rglob('*.json') if not any('userdata' in x for x in p.relative_to(OUT.parent).parts)]
    extra += [p.relative_to(ROOT).as_posix() for p in OUT.parent.glob('*.py')]
    extra += ['test_results/pvp743/t24-queue-20261116/'+n for n in ['nonpass-detail-review.json','application-header-review.json']]
    extra += ['test_results/pvp743/t24-queue-20261116/'+n for n in ['before-r2.json','before-r3.json','after-r2.json','after-r3.json','tcp-load-r1.json','tcp-deferred-reserved-contention.json','tcp-snd64-r1.json','linux-socket-buffer-readback.json','application-scope-check.json','additional-freeze.json']]
    extra += [p.relative_to(ROOT).as_posix() for p in (ROOT/'test_results/pvp743/t24-full-20261116').glob('test_*.json')]
    extra += ['test_results/pvp743/t24-full-20261116/'+n for n in ['source-hashes.json','input-versions.json','collection.json','test-identities.json']]
    extra += [(OUT.parent/'build_android_release.sh').relative_to(ROOT).as_posix(),(OUT/'android-package-verification.json').relative_to(ROOT).as_posix(),(OUT/'pc-smoke/verification.json').relative_to(ROOT).as_posix()]
    extra += [(OUT/'verification-recovery.json').relative_to(ROOT).as_posix()]
    for rel in extra:assert (ROOT/rel).is_file(),rel;entries[rel]=ROOT/rel
    entries['README.md']=('# PvP74.3 r3 开发者包\n\n本包包含当前生产源码、资源、生成桥和精选原始证据。网络与发布结果见 `更新说明-PvP74.3-r3.md`；完整回归非全绿，实机验收未完成，神经网络研究暂停。\n\n构建说明见 `build/pvp743-tools/README-PvP74.3-dev.md`，其中旧发布状态属于历史。新增构建门禁为 `python tools/pvp743_network_sources.py --check`。该脚本默认执行时只更新网络拥有方法，保留原生生命周期适配。生产内核与组合层位置见 `AGENTS.md`。\n').encode('utf8')
    status={'revision':REV,'compatibility_build':VERSION,'full_suite_counts':full['counts'],'new_nonpass_ids':0,'unwaived':full['unwaived'],'product_acceptance_passed':False,'physical_device_verified':False,'neural_ai':'paused','local_network_and_private_cloud_checks':'passed'}
    entries['STAGING_STATUS.json']=(json.dumps(status,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    hashes={n:sha(p) if isinstance(p,Path) else hashlib.sha256(p).hexdigest() for n,p in entries.items()}
    manifest={'revision':REV,'base_archive_sha256':sha(previous),'historical_metadata_retained':inherited,'files':hashes,'validation':status}
    entries['MANIFEST-PvP74.3.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    hashes['MANIFEST-PvP74.3.json']=hashlib.sha256(entries['MANIFEST-PvP74.3.json']).hexdigest()
    entries['SHA256SUMS.txt']=''.join(v+'  '+n+'\n' for n,v in sorted(hashes.items())).encode('utf8')
    source=archive(STAGE.with_name(STAGE.name+'-Developer-Package.zip'),entries,'PvZ-PvP-Native-PvP74.3-src/')
    source.update(passed=True,full_previous_source_set_retained=True);dump(OUT/'source-package-verification.json',source)
    print('SOURCE ZIP verified',source['files'],flush=True)
def promote():
    import psutil
    pc=read(OUT/'pc-package-verification.json');source=read(OUT/'source-package-verification.json');apk=read(OUT/'android-package-verification.json')
    assert pc['passed'] and source['passed'] and apk['passed']
    assert tree(STAGE)==pc['payload'] and sha(Path(pc['path']))==pc['sha256'] and sha(Path(source['path']))==source['sha256'] and sha(Path(apk['apk']))==apk['sha256']
    previous=read(ROOT/'dist/latest-native-release.json');assert previous['revision']=='pvp743-r2'
    dest=ROOT/'PVZ_rougePvP_native';assert sha(dest/'PvZPvPNative.exe')==previous['exe_sha256']
    running=[p.info['pid'] for p in psutil.process_iter(['pid','name','exe']) if p.info['exe'] and Path(p.info['exe']).resolve()==(dest/'PvZPvPNative.exe').resolve()]
    assert not running,'Close the running installed game before replacing its executable'
    launchers={p:sha(p) for p in [ROOT/'启动PvP.cmd',dest/'launch_pvp.cmd']}
    assert 'PVZ_rougePvP_native\\launch_pvp.cmd' in (ROOT/'启动PvP.cmd').read_text('utf-8-sig')
    assert '%~dp0pvp_userdata' in (dest/'launch_pvp.cmd').read_text('utf-8-sig')
    before=users();dump(OUT/'userdata-before.json',before)
    backup=ROOT/'backup-latest';records=[]
    for key,hashkey,name in [('pc_zip','pc_zip_sha256','previous-release.zip'),('developer_package','developer_sha256','previous-source.zip')]:
        origin=Path(previous[key]);assert sha(origin)==previous[hashkey]
        temp=backup/(name+'.next');assert not temp.exists();shutil.copy2(origin,temp);assert sha(temp)==previous[hashkey]
        os.replace(temp,backup/name);records.append({'file':str(backup/name),'version':previous['version'],'revision':previous['revision'],'sha256':previous[hashkey]})
    dump(backup/'manifest.json',records)
    changed=[]
    for name,digest in pc['payload'].items():
        target=(dest/name).resolve();assert target.is_relative_to(dest.resolve()) and 'pvp_userdata' not in target.relative_to(dest).parts
        if not target.is_file() or sha(target)!=digest:
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.next');assert not temp.exists()
            shutil.copy2(STAGE/name,temp);assert sha(temp)==digest;os.replace(temp,target);changed.append(name)
        assert sha(target)==digest
    assert all(sha(p)==digest for p,digest in launchers.items())
    after=users();dump(OUT/'userdata-after.json',after);assert before==after
    result={'passed':True,'version':VERSION,'revision':REV,'updated_at':datetime.datetime.now().isoformat(),'launcher':str(ROOT/'启动PvP.cmd'),'target':str(dest/'PvZPvPNative.exe'),'exe_sha256':sha(dest/'PvZPvPNative.exe'),'release':str(STAGE),'pc_zip':pc['path'],'pc_zip_sha256':pc['sha256'],'developer_package':source['path'],'developer_sha256':source['sha256'],'source_package':'complete','apk':apk['apk'],'apk_sha256':apk['sha256'],'android_version_code':1114083,'android_signature_continuity_verified':True,'android_real_device_verified':False,'all_user_files_preserved':True,'userdata_files_verified':sum(len(x) for x in before.values() if x is not None),'shipped_files_verified':len(pc['payload']),'changed_managed_files':changed,'launcher_files_preserved':True,'root_launcher_executed':False,'pc_packaged_exe_run':True,'backup_revisions':[previous['revision']],'backup_folder':str(backup),'backup_files':2,'full_regression':str(OUT.parent/'full-comparison.json'),'product_acceptance_passed':False,'github':'not_published_this_revision','release_notes':str(ROOT/'更新说明-PvP74.3-r3.md'),'verification':str(OUT/'local-delivery-verification.json')}
    dump(OUT/'local-delivery-verification.json',result);dump(ROOT/'dist/latest-native-release.json',result);dump(ROOT/'dist/PvP74.3-r3-发行清单.json',result)
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','smoke','packages','promote']);args=p.parse_args();globals()[args.action]()
