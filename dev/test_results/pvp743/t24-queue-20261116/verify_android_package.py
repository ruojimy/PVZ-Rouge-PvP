"""Run in WSL after signed assembly; copy only public build evidence and APK."""
from pathlib import Path
import hashlib,json,re,shutil,struct,subprocess,zipfile
root=Path('/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native')
out=root/'test_results/pvp743/t24-queue-20261116/delivery'
work=Path.home()/'pvz-native-android'
candidate=work/'candidates/20261116-pvp743-r3'
assemblies=list(candidate.glob('apk-1114083-*'));assert len(assemblies)==1
assembly=assemblies[0]
name='PvZ-PvP-Native-1.6.0.74.3-typed.20261114-r3-1114083-20261116-pvp743-r3.apk'
apk=work/'out'/name
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
digest=sha(apk)
folder=root/'dist/apk-pvp743-20261116';folder.mkdir(exist_ok=True)
target=folder/name
if target.exists():assert sha(target)==digest,'Existing APK differs'
else:shutil.copy2(apk,target)
assert sha(target)==digest
target.with_suffix('.apk.sha256').write_text(digest+'  '+name+'\n',encoding='utf8')
evidence=out/'android';evidence.mkdir(exist_ok=True)
for n in ['badging.txt','previous-badging.txt','certificate.txt','previous-certificate.txt','signature.log','gradle.log','sdl-java-patches.json','sdl-java-backport.patch']:
    shutil.copy2(assembly/n,evidence/n)
cert=(evidence/'certificate.txt').read_text();oldcert=(evidence/'previous-certificate.txt').read_text()
certsha=re.findall(r'certificate SHA-256 digest: (\S+)',cert);assert certsha and certsha==re.findall(r'certificate SHA-256 digest: (\S+)',oldcert)
badging=(evidence/'badging.txt').read_text();assert "package: name='org.pvzrouge.pvzpvpnative'" in badging and "versionCode='1114083'" in badging
assert "versionName='1.6.0.74.3-typed.20261114-r3'" in badging
native={p.name:p for p in (candidate/'jniLibs/arm64-v8a').glob('*.so')}
assets={p.relative_to(assembly/'assets').as_posix():p for p in (assembly/'assets').rglob('*') if p.is_file()}
# aapt keeps UTF-8 asset name bytes but does not set ZIP bit 11. Its names
# must be read as UTF-8; CP437 defaults produce false missing-file errors.
with zipfile.ZipFile(target,metadata_encoding='utf-8') as z:
    assert z.testzip() is None
    libs=[n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
    assert set(libs)=={'lib/arm64-v8a/'+n for n in native}
    for n,p in native.items():assert hashlib.sha256(z.read('lib/arm64-v8a/'+n)).hexdigest()==sha(p)
    for n,p in assets.items():assert hashlib.sha256(z.read('assets/'+n)).hexdigest()==sha(p)
    for n,p in assets.items():
        if n.startswith(('extract/data/','extract/assets/','fonts/')) and (root/n).is_file():assert sha(p)==sha(root/n)
    assert not any('/pvp_userdata/' in n or '/keystore' in n for n in z.namelist())
    lib=z.read('lib/arm64-v8a/libmain.so');assert lib[:4]==b'\x7fELF' and lib[4]==2 and struct.unpack_from('<H',lib,18)[0]==183
report={'passed':True,'apk':str(target).replace('/mnt/c/','C:/'),'sha256':digest,'version_code':1114083,'version_name':'1.6.0.74.3-typed.20261114-r3','package':'org.pvzrouge.pvzpvpnative','signature_continuity_verified':True,'signing_certificate_sha256':certsha,'zip_crc_verified':True,'abi':['arm64-v8a'],'elf_machine':'AArch64','native_libraries':{n:sha(p) for n,p in native.items()},'assets_verified':len(assets),'source_before_after_equal':(candidate/'source-arm64-v8a.before.sha256').read_bytes()==(candidate/'source-arm64-v8a.after.sha256').read_bytes(),'physical_device_verified':False}
assert report['source_before_after_equal']
(out/'android-package-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,indent=2),flush=True)
