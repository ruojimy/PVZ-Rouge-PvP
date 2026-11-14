"""Verified plain copy for a Windows build without full zlib. Originals remain intact."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

source, dest = map(Path, sys.argv[1:3])
if dest.exists():
    raise SystemExit("destination already exists")
index = json.loads((source / 'index.json').read_text('utf-8'))
dest.mkdir(parents=True)
copied = {}

def copy(name, expected):
    if name in copied:
        return copied[name]
    raw = (gzip.open(source / name, 'rb').read() if name.endswith('.gz') else (source / name).read_bytes())
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('corpus hash mismatch: ' + name)
    new = name[:-3] if name.endswith('.gz') else name
    target = dest / new
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    copied[name] = new
    return new

index['atlas'] = copy(index['atlas'], index['atlas_sha256'])
if 'recipes' in index:
    index['recipes'] = copy(index['recipes'], index['recipes_sha256'])
for e in index['entries']:
    for kind in ('cold', 'draw'):
        e[kind] = copy(e[kind], e[kind + '_sha256'])
(dest / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), 'utf-8')
print(json.dumps(dict(entries=len(index['entries']), files=len(copied), verified=True)))
