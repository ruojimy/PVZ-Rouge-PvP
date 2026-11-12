"""Freeze the pre-72 sources, inputs and benchmark executable without modifying 71."""
import hashlib, json, shutil, zipfile
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'test_results' / ('pvp72-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
out.mkdir()
files = [root / 'CMakeLists.txt']
for name in ('src', 'tools', 'android', 'extract/data', 'extract/schema', 'docs/coverage'):
    files += [p for p in (root / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
manifest = {}
with zipfile.ZipFile(str(out / 'baseline71-source.zip'), 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
    for p in sorted(set(files)):
        rel = p.relative_to(root).as_posix()
        manifest[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        archive.write(str(p), rel)
baseline = out / 'baseline71'
baseline.mkdir()
for p in (root / 'build/Release').iterdir():
    if p.is_file() and (p.name in ('run_battle.exe', 'app_run.exe', 'PvZPvPNative.exe') or p.suffix == '.dll'):
        shutil.copy2(str(p), str(baseline / p.name))
        manifest['build/Release/' + p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(str(root / 'extract/data'), str(baseline / 'extract/data'))
for p in sorted((root / 'dist').glob('*workerfix-r2*')):
    if p.is_file():
        manifest[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
manifest['next_pvp71_policy'] = 'Read-only reference; no regeneration or output into next-pvp71.'
(out / 'baseline71-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'build/pvp72-workdir.txt').write_text(str(out), encoding='utf-8')
print(str(out))
