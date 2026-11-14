"""Validate finished teacher rollouts and call the one canonical C++ encoder."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--records', type=Path, required=True)
ap.add_argument('--ids', type=Path, required=True)
ap.add_argument('--encoder', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--stride', type=int, default=4)
args = ap.parse_args()
if args.out.exists():
    raise SystemExit('Dataset exists; use a new path')
ids = args.ids.read_text('utf-8').split()
assert len(ids) == len(set(ids)) and args.stride > 0
paths, manifest = [], []
for key in ids:
    path = args.records / (key + '.jsonl')
    raw = path.read_bytes()
    lines = raw.splitlines()
    header, footer = json.loads(lines[0]), json.loads(lines[-1])
    if footer.get('type') != 'result' or footer['ai_error'] or not header['records']:
        raise ValueError('Incomplete or invalid teacher rollout: ' + key)
    paths.append(str(path))
    manifest.append(dict(id=key, sha256=hashlib.sha256(raw).hexdigest(), map=header['map'],
                         seed=header['seed'], limit_seconds=header['limit_seconds'],
                         timeout=footer['timeout'], time=footer['time']))
subprocess.run([str(args.encoder), str(args.out), '-', '--stride', str(args.stride), *paths], check=True)
meta = dict(format='pvz-neural-dataset-provenance-1', stride_per_seat=args.stride, matches=manifest,
            encoder_sha256=hashlib.sha256(args.encoder.read_bytes()).hexdigest(),
            dataset_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest())
args.out.with_suffix('.provenance.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), 'utf-8')
