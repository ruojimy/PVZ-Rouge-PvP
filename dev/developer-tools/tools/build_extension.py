"""Build this extension from a literal file allowlist, never by walking a project."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

BASE=Path(__file__).resolve().parents[1]
SKILLS=['native-export','native-maps','native-replay','native-relay','native-acceptance',
        'native-performance','native-package-audit','native-ai-source','native-build-source',
        'native-test-source','pvz-rouge-add-plant','pvz-rouge-add-zombie','pvz-rouge-add-boss','pvz-rouge-add-mode']
FILES=['README.md','INDEX.md','MIGRATION.md','GAPS.md','VALIDATION.md','THIRD_PARTY_NOTICES.txt',
       'compatibility.json','migration-matrix.json','launch.cmd','sdk/protocol.md','sdk/request.schema.json',
       'tools/pvz_tools.py','tools/build_extension.py','tools/relay/relay_server.py','tools/relay/health.py',
       'tools/relay/config.example.json','provenance/developer-extra-files.json',
       'provenance/related-archives.json','provenance/legacy-skill-provenance.json','provenance/source-checkout-comparison.json',
       'examples/capabilities-request.json','examples/quickstart.ps1','validation/results.json']
FILES += ['skills/'+name+'/SKILL.md' for name in SKILLS]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def build(output):
    if output.exists() or output.with_suffix(output.suffix+'.sha256').exists():
        raise RuntimeError('Refusing to overwrite an existing delivery')
    files=sorted(FILES+['allowlist.json'])
    metadata=['manifest.json','SHA256SUMS.txt']
    (BASE/'allowlist.json').write_text(json.dumps({'files':files+metadata,'policy':'Exact explicit paths; no recursive project archive'},indent=2)+'\n',encoding='utf8')
    manifest={'toolkit_version':'1.0.0','files':[],'metadata_files':metadata}
    for name in files:
        p=BASE/name
        if not p.is_file() or p.is_symlink():raise RuntimeError('Missing/unsafe allowlisted file: '+name)
        manifest['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha(p)})
    (BASE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (BASE/'SHA256SUMS.txt').write_text(''.join(sha(BASE/n)+'  '+n+'\n' for n in sorted(files+['manifest.json'])),encoding='utf8')
    actual={p.relative_to(BASE).as_posix() for p in BASE.rglob('*') if p.is_file()}
    if actual!=set(files+metadata):raise RuntimeError('Unexpected/missing extension files: '+repr(sorted(actual^set(files+metadata))))
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(files+metadata):
            info=zipfile.ZipInfo('developer-tools/'+name,date_time=(2026,11,4,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(BASE/name).read_bytes())
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC failure')
        expected={'developer-tools/'+name for name in files+metadata}
        if set(z.namelist())!=expected or len(z.namelist())!=len(expected):raise RuntimeError('ZIP allowlist mismatch')
        for name in files+metadata:
            if hashlib.sha256(z.read('developer-tools/'+name)).hexdigest()!=sha(BASE/name):raise RuntimeError('ZIP readback mismatch')
    digest=sha(output)
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='utf8')
    print(json.dumps({'zip':str(output),'bytes':output.stat().st_size,'sha256':digest,'files':len(expected)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    build(p.parse_args().output.resolve())
