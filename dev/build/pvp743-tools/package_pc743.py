"""PC payload staging, UTF-8 archive and save-preserving local delivery; no game launch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[2]
VERSION='1.6.0.74.3-typed.20261114'
STAGE=ROOT/'dist/PvZ-PvP-Native-20261114-pvp743-r1'
ARCHIVE=STAGE.with_suffix('.zip')
EVIDENCE=ROOT/'test_results/pvp743'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def write(p,j):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(j,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))

def safe(p,base=ROOT):
    p=p.resolve();base=base.resolve()
    if not p.is_relative_to(base) or p==base:raise RuntimeError('unexpected target: '+str(p))
    return p

class UTF8Info(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):return self.filename.encode('utf-8'),self.flag_bits|0x800

def files(folder):
    result={}
    for p in sorted(folder.rglob('*')):
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise RuntimeError('link in payload: '+str(p))
        if p.is_file():result[p.relative_to(folder).as_posix()]=sha(p)
    return result

def stage():
    safe(STAGE)
    if STAGE.exists() or ARCHIVE.exists():raise RuntimeError('fresh candidate already exists')
    version=json.loads((ROOT/'extract/data/__init__.json').read_text('utf-8'))['BUILD']
    if version!=VERSION:raise RuntimeError('wrong source version')
    build=ROOT/'build/app-typed72-v2/Release'
    STAGE.mkdir(parents=True)
    for name in ['PvZPvPNative.exe','relay.json']:
        shutil.copy2(build/name,STAGE/name)
    dlls=sorted(build.glob('SDL2*.dll'))
    if len(dlls)!=4:raise RuntimeError('expected four SDL DLLs')
    for p in dlls:shutil.copy2(p,STAGE/p.name)
    for name in ['图片','音乐','音效']:shutil.copytree(build/name,STAGE/name)
    for name in ['data','assets']:shutil.copytree(ROOT/'extract'/name,STAGE/'extract'/name)
    shutil.copytree(ROOT/'fonts',STAGE/'fonts')
    shutil.copy2(ROOT/'tools/启动说明.txt',STAGE/'启动说明.txt')
    prior=ROOT/'dist/PvZ-PvP-Native-20261114-pvp742-r2'
    for name in ['debug-run.cmd','崩溃诊断说明.txt']:shutil.copy2(prior/name,STAGE/name)
    shutil.copy2(ROOT/'更新说明-PvP74.3.md',STAGE/'更新说明-PvP74.3.md')
    shutil.copy2(ROOT/'更新公告-PvP74.3.txt',STAGE/'更新公告-PvP74.3.txt')
    shutil.copy2(ROOT/'PvP74.3_任务总清单.md',STAGE/'任务总清单-PvP74.3.md')
    payload=files(STAGE)
    (STAGE/'SHA256SUMS').write_bytes(''.join(f'{digest}  ./{name}\n' for name,digest in payload.items()).encode('utf-8'))
    payload=files(STAGE)
    with zipfile.ZipFile(ARCHIVE,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in payload:
            p=STAGE/name
            info=UTF8Info('PvZ-PvP-Native/'+name);info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC mismatch')
        entries=z.infolist()
        if len(entries)!=len(payload):raise RuntimeError('ZIP file count mismatch')
        for e in entries:
            name=e.filename.removeprefix('PvZ-PvP-Native/')
            if not e.flag_bits&0x800 or hashlib.sha256(z.read(e)).hexdigest()!=payload[name]:raise RuntimeError('ZIP payload mismatch: '+name)
    report={'passed':True,'version':VERSION,'stage':str(STAGE),'zip':str(ARCHIVE),'zip_sha256':sha(ARCHIVE),
            'exe_sha256':payload['PvZPvPNative.exe'],'files':len(payload),'utf8_all':True,'crc_all':True,
            'game_launched':False,'new_gameplay_tests_run':False,'payload':payload}
    write(EVIDENCE/'pc-package-verification.json',report)
    return report

def userdata_snapshot():
    roots=[ROOT/'PVZ_rougePvP_native/pvp_userdata',Path(os.environ['APPDATA'])/'PVZ-PvP-Native']
    return {str(p):files(p) if p.exists() else None for p in roots}

def parse_sums(p):
    result={}
    for line in p.read_text('utf-8').splitlines():
        rel=line[64:].strip().lstrip('*').removeprefix('./')
        if rel:result[rel]=line[:64]
    return result

def deploy():
    proof=json.loads((EVIDENCE/'pc-package-verification.json').read_text('utf-8'))
    if not proof['passed'] or sha(ARCHIVE)!=proof['zip_sha256'] or files(STAGE)!=proof['payload']:raise RuntimeError('candidate drift')
    dest=safe(ROOT/'PVZ_rougePvP_native');backup=safe(ROOT/'backup-latest')
    previous=json.loads((ROOT/'dist/latest-native-release.json').read_text('utf-8-sig'))
    if previous['version']==VERSION:raise RuntimeError('already deployed')
    before=userdata_snapshot();write(EVIDENCE/'userdata-before.json',before)
    backup.mkdir(exist_ok=True)
    records=[]
    for source_key,hash_key,name in [('pc_zip','pc_zip_sha256','previous-release.zip'),('developer_package','developer_sha256','previous-source.zip')]:
        source=Path(previous[source_key]);expected=previous[hash_key]
        if sha(source)!=expected:raise RuntimeError('previous archive drift')
        target=safe(backup/name,backup);temp=safe(backup/(name+'.next'),backup)
        if temp.exists():raise RuntimeError('previous unfinished backup exists')
        shutil.copy2(source,temp)
        if sha(temp)!=expected:raise RuntimeError('backup copy mismatch')
        os.replace(temp,target);records.append({'file':str(target),'version':previous['version'],'sha256':expected})
    write(backup/'manifest.json',records)
    old=parse_sums(dest/'SHA256SUMS')
    for name,digest in proof['payload'].items():
        target=safe(dest/name,dest);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(STAGE/name,target)
        if sha(target)!=digest:raise RuntimeError('installed payload mismatch: '+name)
    removed=[]
    for name in old.keys()-proof['payload'].keys():
        rel=Path(name)
        if rel.parts[0] not in ['extract','fonts','图片','音乐','音效']:continue
        target=safe(dest/rel,dest)
        if target.is_file():target.unlink();removed.append(name)
    # Keep the established independent user-data launcher byte-for-byte.
    launcher=ROOT/'启动PvP.cmd'
    if 'PVZ_rougePvP_native\\launch_pvp.cmd' not in launcher.read_text('utf-8-sig'):raise RuntimeError('unexpected root launcher')
    inner=(dest/'launch_pvp.cmd').read_text('utf-8-sig')
    if '%~dp0pvp_userdata' not in inner or 'PvZPvPNative.exe' not in inner:raise RuntimeError('independent data launcher changed')
    after=userdata_snapshot();write(EVIDENCE/'userdata-after.json',after)
    if before!=after:raise RuntimeError('user data changed during delivery')
    report={'passed':True,'version':VERSION,'launcher':str(launcher),'target':str(dest/'PvZPvPNative.exe'),
            'exe_sha256':sha(dest/'PvZPvPNative.exe'),'release':str(STAGE),'pc_zip':str(ARCHIVE),'pc_zip_sha256':sha(ARCHIVE),
            'shipped_files_verified':len(proof['payload']),'userdata_files_verified':sum(len(v) for v in before.values() if v is not None),
            'all_user_files_preserved':True,'backup_versions':[previous['version']],'backup_files':len(records),'backup_folder':str(backup),
            'removed_old_managed_files':removed,'source_package':'pending','github':'pending','game_launched':False,'new_gameplay_tests_run':False}
    write(EVIDENCE/'local-delivery-verification.json',report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','deploy']);args=p.parse_args()
    result=stage() if args.action=='stage' else deploy()
    print(json.dumps({k:v for k,v in result.items() if k!='payload'},ensure_ascii=True,indent=2))
