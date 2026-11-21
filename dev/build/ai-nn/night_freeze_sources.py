"""Archive the exact research sources used by the active overnight study."""
import zipfile
from overnight_common import B, H, R, BUILD, guard, read, sha, write

guard()
prepared = read(B / 'prepared.json')
paths = {str(p): h for p, h in prepared['source_sha256'].items()}
extras = [H / 'CMakeLists.txt', BUILD / 'ai_nn_build.h', *sorted((H / 'src').glob('*'))]
for path in extras:
    if path.is_file():
        paths[str(path)] = sha(path)
target = B / 'research-sources.zip'
assert not target.exists()
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, expected in paths.items():
        from pathlib import Path
        path = Path(name)
        assert sha(path) == expected, name
        archive.write(path, path.relative_to(R).as_posix())
with zipfile.ZipFile(target) as archive:
    import hashlib
    for name, expected in paths.items():
        assert hashlib.sha256(archive.read(Path(name).relative_to(R).as_posix())).hexdigest() == expected
write(B / 'research-sources.json', dict(
    archive=str(target), archive_sha256=sha(target), bytes=target.stat().st_size,
    files=paths, scope='Research sources only; production source hashes remain in plan.json and the earlier frozen core is preserved.'))
guard()
print(dict(files=len(paths), bytes=target.stat().st_size, verified=True))
