"""Compare C++ inference with exported PyTorch weights; test metadata rejection."""
import argparse
import json
import subprocess
from pathlib import Path

import torch
from train import DeepSet, collate, OFFSETS

ap = argparse.ArgumentParser()
ap.add_argument('--encoder', type=Path, required=True)
ap.add_argument('--model', type=Path, required=True)
ap.add_argument('--checkpoint', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('records', type=Path, nargs='+')
args = ap.parse_args()
if args.out.exists():
    raise SystemExit('Use a new verification output directory')
args.out.mkdir(parents=True)
cpp_file = args.out / 'cpp-forward.jsonl'
subprocess.run([str(args.encoder), str(cpp_file), str(args.model), '--stride', '4',
                *map(str, args.records)], check=True)
torch.set_num_threads(4)
checkpoint = torch.load(args.checkpoint, weights_only=True, map_location='cpu')
meta = json.loads(args.model.read_text('utf-8'))
model = DeepSet(16 + len(meta['behaviors']), meta['embedding'], meta['hidden']).double()
model.load_state_dict(checkpoint['state_dict']);model.eval()
rows = []
with cpp_file.open(encoding='utf-8') as f:
    next(f)
    for line in f:
        r = json.loads(line)
        r['g'] = torch.tensor(r['x']['global'], dtype=torch.float64)
        r['y'] = torch.tensor(r['y'], dtype=torch.long)
        r['plant'] = r['seat'] == 'plant'
        for k in ('own', 'enemy'):
            a = r['x'][k]
            r[k + '_count'] = len(a)
            r[k] = torch.tensor(a or [[0.] * (16 + len(meta['behaviors']))], dtype=torch.float64)
        rows.append(r)
maximum = 0.;mismatches = 0
with torch.no_grad():
    for start in range(0, len(rows), 64):
        part = rows[start:start + 64]
        x, _, _ = collate(part)
        logits = model(*x)
        expected = torch.tensor([r['logits'] for r in part], dtype=torch.float64)
        maximum = max(maximum, float((logits - expected).abs().max()))
        for h in range(4):
            classes = logits[:, OFFSETS[h]:OFFSETS[h+1]].argmax(1)
            mismatches += int((classes != torch.tensor([r['classes'][h] for r in part])).sum())
negative = []
for field, value in (('sim_fingerprint', 'wrong-source'), ('catalog_hash', 'wrong-catalog'),
                     ('enabled_heads', [True]), ('format', 'unsupported-format')):
    bad = dict(meta);bad[field] = value
    path = args.out / ('invalid-' + field + '.json')
    path.write_text(json.dumps(bad), 'utf-8')
    run = subprocess.run([str(args.encoder), str(args.out / ('rejected-' + field + '.jsonl')),
                          str(path), str(args.records[0])], capture_output=True)
    negative.append(dict(field=field, rejected=run.returncode != 0, returncode=run.returncode,
                         message=run.stderr.decode('utf-8', 'replace').strip()))
result = dict(samples=len(rows), classes_checked=4 * len(rows), class_mismatches=mismatches,
              max_absolute_logit_error=maximum, negative=negative,
              passed=maximum < 1e-9 and mismatches == 0 and all(r['rejected'] for r in negative))
(args.out / 'report.json').write_text(json.dumps(result, indent=2), 'utf-8')
print(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
