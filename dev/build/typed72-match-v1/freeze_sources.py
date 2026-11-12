"""Source-freeze fingerprint: SHA-256 of every file that feeds the typed kernel stage, the match
driver, the app composition/adapter, the UI/sim sources, tests and the release scripts; plus the
built binaries. Usage: freeze_sources.py <out.json> [--check <earlier.json>]"""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SETS={
 'stage_v44':ROOT/'build/typed72-integrated-v44/source/src/sim/typed',
 'typed_drafts':ROOT/'tools/typed72/drafts',
 'match_driver':ROOT/'build/typed72-match-v1',
 'app_src':ROOT/'src',
 'android':ROOT/'android',
}
SKIP_DIRS={'build','__pycache__','scenarios'}
SUFFIX={'.cpp','.h','.inc','.py','.ps1','.sh','.txt','.json','.cmake'}
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
out={'sets':{},'binaries':{},'extra':{}}
for name,base in SETS.items():
    files={}
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.suffix not in SUFFIX:continue
        rel=p.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]) and name=='match_driver':continue
        if name=='match_driver' and rel.suffix=='.json' and rel.parent!=Path('.'):continue
        files[str(rel).replace('\\','/')]=sha(p)
    out['sets'][name]={'files':len(files),'digest':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'hashes':files}
for f in ('CMakeLists.txt','tools/package.sh','tools/run_cpp_suite.py','build/typed72-integrated-v44/integration-manifest.json'):
    out['extra'][f]=sha(ROOT/f)
for f in ('build/app-typed72-v2/Release/PvZPvPNative.exe','build/app-typed72-v2/Release/typed72_battle_audit.exe','build/app-typed72-v2/Release/cpp_tests.exe',
          'build/typed72-match-v1/build/Release/match72.exe','build/typed72-match-v1/build/Release/cold72_export.exe'):
    p=ROOT/f;out['binaries'][f]=sha(p) if p.exists() else None
dest=Path(sys.argv[1]);dest.write_text(json.dumps(out,indent=1),encoding='utf-8')
summary={k:(v['files'],v['digest'][:16]) for k,v in out['sets'].items()}
print(json.dumps(summary,indent=1))
if len(sys.argv)>3 and sys.argv[2]=='--check':
    old=json.loads(Path(sys.argv[3]).read_text('utf-8'))
    changed=[k for k in out['sets'] if out['sets'][k]['digest']!=old['sets'][k]['digest']]
    changed+=[k for k in out['extra'] if out['extra'][k]!=old['extra'].get(k)]
    changed+=[k for k in out['binaries'] if out['binaries'][k]!=old['binaries'].get(k)]
    print('CHANGED since freeze:',changed or 'none')
