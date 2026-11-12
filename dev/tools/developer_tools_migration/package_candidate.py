"""Companion game candidate from explicit official-release entries, no worktree walk."""
from pathlib import Path,PurePosixPath
import hashlib
import json
import shutil
import zipfile

R=Path(__file__).resolve().parents[2];E=R/'test_results/developer-tools-20261104'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    release=json.loads((R/'dist/PVP72-20261104-release-manifest.json').read_text('utf8'))
    original=Path(release['pc']['zip']);assert sha(original)==release['pc']['sha256']
    exe=R/'build/Release/PvZPvPNativeDev.exe'
    directory=R/'dist/PvP72-devtools-api1';directory.mkdir(exist_ok=False)
    paths=[];base_hashes={}
    with zipfile.ZipFile(original) as z:
        for info in z.infolist():
            if info.is_dir():continue
            name=PurePosixPath(*PurePosixPath(info.filename).parts[1:]).as_posix()
            assert name and '..' not in PurePosixPath(name).parts
            if name=='SHA256SUMS':continue
            target=directory/name;target.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(info)
            base_hashes[name]=hashlib.sha256(data).hexdigest()
            target.write_bytes(exe.read_bytes() if name=='PvZPvPNative.exe' else data)
            paths.append(name)
    (directory/'DEVELOPER_API.txt').write_text(
      'PvP72 native-devtools.1 companion candidate (Windows x64).\n'
      'Extract to a short path; normal game entry is PvZPvPNative.exe.\n'
      'Base: official 1.6.0.72-native.20261104 Windows r1.\n'
      'Only the opt-in application CLI and build target changed. Rules, catalog, RNG and network protocol are unchanged.\n'
      'Requires the separate developer-tools extension and Python 3.10+ for tooling.\n'
      'Do not overwrite your existing game or saves. No new Android candidate.\n'
      'Existing legacy-suite 30 FAIL / 12 ERROR are not declared fixed.\n',encoding='utf8')
    candidate={'build':release['build'],'adapter':'native-devtools.1','developer_api':1,
               'base_pc_zip':original.name,'base_pc_zip_sha256':sha(original),'exe_sha256':sha(exe),
               'catalog_hash':release['catalog_hash'],'rules_hash':release['rules_hash'],'network_protocol':1,
               'modified_base_files':['PvZPvPNative.exe','SHA256SUMS'],'new_files':['DEVELOPER_API.txt','developer-candidate.json'],
               'game_source_included':False,'android_candidate_built':False}
    write(directory/'developer-candidate.json',candidate)
    paths+=['DEVELOPER_API.txt','developer-candidate.json']
    (directory/'SHA256SUMS').write_text(''.join(sha(directory/name)+'  '+name+'\n' for name in sorted(paths)),encoding='utf8')
    paths.append('SHA256SUMS')
    target=R/'dist/PvZ-PvP-Native-20261104-devtools-api1-r1.zip'
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(paths):z.write(directory/name,'PvP72-devtools-api1/'+name)
    # Independently extract the actual distribution bytes into a Unicode/space path.
    layout=json.loads((E/'test-layout.json').read_text('utf8'))
    independent=Path(layout['root'])/'候选 game';independent.mkdir(exist_ok=False)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))==len(paths)
        for info in z.infolist():
            name=PurePosixPath(*PurePosixPath(info.filename).parts[1:]).as_posix()
            dest=independent/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
            assert sha(dest)==sha(directory/name)
            if name in base_hashes and name!='PvZPvPNative.exe':assert sha(dest)==base_hashes[name]
    layout['candidate']=str(independent);write(E/'test-layout.json',layout)
    candidate.update({'zip':str(target),'zip_sha256':sha(target),'bytes':target.stat().st_size,'files':len(paths),
                      'all_base_resources_identical':True,'independent_game_directory':str(independent)})
    write(E/'candidate-package.json',candidate)
    target.with_suffix('.zip.sha256').write_text(sha(target)+'  '+target.name+'\n',encoding='utf8')
    print(json.dumps(candidate,ensure_ascii=True))

if __name__=='__main__':main()
