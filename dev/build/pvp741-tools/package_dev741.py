"""PvP74.1 developer package: C++ sources, typed kernel stage + composition driver, Python PvP sources,
decompiled original-game Python, tools, data, docs and SDL dev libraries, in the project's own layout.

    python package_dev74.py <id>   ->  dist/PvZ-PvP-Native-<id>-Developer-Package.zip
Top folder inside the ZIP: PvZ-PvP-Native-PvP74.1-src/. SHA256SUMS.txt lists every file."""
import fnmatch, hashlib, sys, zipfile
from pathlib import Path
ROOT = Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
ID = sys.argv[1]
TOP = 'PvZ-PvP-Native-PvP74.1-src'
OUT = ROOT / 'dist' / ('PvZ-PvP-Native-%s-Developer-Package.zip' % ID)
assert not OUT.exists(), OUT

# (directory or file, recursive) relative to ROOT
INCLUDE = ['CMakeLists.txt', 'README.md', 'AGENTS.md', '更新说明-PvP74.1.md', 'PvP74.1_进度.md', '待办.md', '工作汇总.md', '启动PvP.cmd',
           'src', 'tools', 'android', 'docs', 'developer-tools', 'fonts',
           'extract/original', 'extract/live', 'extract/data', 'extract/schema', 'extract/assets', 'extract/golden',
           'third_party/SDL2-2.30.9', 'third_party/SDL2_image-2.8.2', 'third_party/SDL2_mixer-2.8.0',
           'third_party/SDL2_ttf-2.22.0', 'third_party/nlohmann', 'third_party/zlib-1.3.2-compress',
           'build/typed72-integrated-v44/source',
           'build/typed72-match-v1', 'build/pvp73-tools', 'build/pvp74-tools', 'build/pvp741-tools', 'build/ai-nn']
# build/ driver folders: sources only, not their own build trees or logs
EXCLUDE_DIRS = {'__pycache__', '.git', 'Release', 'Debug', 'x64'}
EXCLUDE_UNDER = ['build/typed72-match-v1/build', 'build/pvp741-tools/build']
EXCLUDE_FILES = ['提示词_*', '*.bak', '*.bak-*', '*.bak*', '*.log', '*.obj', '*.pdb', '*.ilk', '*.exe', '*.lib.tmp', '*.pyc', '*.orig']
EXCLUDE_JSON_UNDER = ['build/typed72-match-v1']   # recorded traces there are large evidence, not inputs
KEEP_JSON_UNDER = ['build/typed72-match-v1/scenarios', 'build/typed72-match-v1/probes']

def wanted(rel):
    parts = rel.split('/')
    if any(p in EXCLUDE_DIRS for p in parts[:-1]): return False
    if any(rel.startswith(u + '/') for u in EXCLUDE_UNDER): return False
    name = parts[-1]
    if any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_FILES): return False
    if name.endswith(('.json', '.jsonl', '.bin')) and any(rel.startswith(u + '/') for u in EXCLUDE_JSON_UNDER) \
            and not any(rel.startswith(k + '/') for k in KEEP_JSON_UNDER): return False
    return True

files = []
for item in INCLUDE:
    p = ROOT / item
    if p.is_file(): files.append(item)
    else:
        assert p.is_dir(), item
        files += [q.relative_to(ROOT).as_posix() for q in p.rglob('*') if q.is_file()]
files = sorted(f for f in set(files) if wanted(f))

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

guide = (ROOT / 'build/pvp741-tools/开发者包说明-PvP74.1.md').read_text('utf-8')
sums = []
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr(TOP + '/开发者包说明-PvP74.1.md', guide.encode('utf-8'))
    sums.append('%s *开发者包说明-PvP74.1.md' % hashlib.sha256(guide.encode('utf-8')).hexdigest())
    for f in files:
        z.write(ROOT / f, TOP + '/' + f)
        sums.append('%s *%s' % (sha(ROOT / f), f))
    z.writestr(TOP + '/SHA256SUMS.txt', '\n'.join(sums) + '\n')
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    n = len(z.namelist())
digest = sha(OUT)
OUT.with_suffix('.zip.sha256').write_text('%s *%s\n' % (digest, OUT.name), encoding='utf-8')
print(OUT, n, 'entries', OUT.stat().st_size, 'bytes', digest)
