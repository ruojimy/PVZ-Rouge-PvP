"""Freeze actual working sources/inputs; never infer binary correspondence from a version label."""
import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / 'CMakeLists.txt', ROOT / 'README.md']
    for directory in ('src', 'tools', 'extract/original', 'extract/schema', 'docs', 'android'):
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and not any(x in p.parts for x in ('__pycache__', '.gradle', 'build', '.cxx'))
                     and p.suffix not in ('.apk', '.so', '.a', '.pdb', '.exe'))
    paths.extend((ROOT / 'extract/data').glob('*.json'))
    paths.append(ROOT / 'dist/PVP72-20261104-release-manifest.json')
    files = {}
    with zipfile.ZipFile(str(out / 'sources.zip'), 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in sorted(set(paths)):
            rel = p.relative_to(ROOT).as_posix()
            digest = sha(p)
            z.write(str(p), rel)
            if sha(p) != digest:
                raise RuntimeError('Source changed while freezing: ' + rel)
            files[rel] = {'sha256': digest, 'bytes': p.stat().st_size}
    binaries = {}
    dest = out / 'binaries'
    dest.mkdir()
    for p in (ROOT / 'build/Release').iterdir():
        if p.is_file() and (p.name in ('run_battle.exe', 'PvZPvPNative.exe') or p.suffix == '.dll'):
            shutil.copy2(str(p), str(dest / p.name))
            binaries[p.name] = {'sha256': sha(dest / p.name), 'bytes': p.stat().st_size}
    manifest = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'source_root': str(ROOT), 'files': files, 'binaries': binaries,
                'sources_zip_sha256': sha(out / 'sources.zip'),
                'binary_source_correspondence': 'not established; rebuild required',
                'reference_policy': 'Python71 is read-only. No player data is included or changed.'}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'out': str(out), 'files': len(files), 'binaries': len(binaries)}))


if __name__ == '__main__':
    main()
