"""Close the 216-case denominator and compare two identical Linux executables
and the Windows real-SDL build. This is a headless AI gate, not product acceptance.
"""
import argparse
import hashlib
import json
import statistics
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('evidence', type=Path)
args = ap.parse_args()
root = args.evidence
names = ('r22-run1', 'r22-run2', 'windows-r22')
summaries = {n: json.loads((root / n / 'summary.json').read_text('utf-8')) for n in names}
for name, s in summaries.items():
    if len(s['ids']) != 216 or s['overall']['matches'] != 216 or s['crashed'] or s['overall']['ai_errors']:
        raise SystemExit('Incomplete/failed baseline: ' + name)

def footer(path):
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - 16384))
        return json.loads(f.read().splitlines()[-1])

byte_equal = (root / names[0] / 'summary.json').read_bytes() == (root / names[1] / 'summary.json').read_bytes()
same_linux, windows_diffs, retention = [], [], {}
probe_names = ('aliases64', 'draws64', 'events64', 'spawns64', 'cost_calls', 'grenade_events', 'poison_events')
for key in summaries[names[0]]['ids']:
    a, b, c = [footer(root / n / 'matches' / (key + '.jsonl')) for n in names]
    if summaries[names[0]]['matches'][key]['file_sha256'] != summaries[names[1]]['matches'][key]['file_sha256']:
        same_linux.append(key)
    diff = [k for k in a if k != 'plan_records' and a[k] != c[k]]
    if diff:
        windows_diffs.append(dict(id=key, keys=diff))
    for n in probe_names:
        retention[n] = max(retention.get(n, 0), a['fixture_retention'][n])
timing = json.loads((root / names[0] / 'timing.json').read_text('utf-8'))
rss = [t['resources']['max_rss_kib'] / 1024 for t in timing['per_match'].values()]
result = dict(scope='headless-ai-216-current-corpus', planned_per_run=216, completed_runs=3,
              linux_summary_byte_equal=byte_equal, linux_file_differences=same_linux,
              windows_footer_differences=windows_diffs, max_probe_retention=retention,
              outcomes=summaries[names[0]]['overall'],
              linux_peak_rss_mib=dict(min=min(rss), median=statistics.median(rss), max=max(rss)),
              summaries_sha256={n: hashlib.sha256((root/n/'summary.json').read_bytes()).hexdigest() for n in names},
              passed=byte_equal and not same_linux and not windows_diffs and not any(retention.values()))
(root / 'baseline-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result['passed'] else 1)
