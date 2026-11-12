"""PvP73 typed-vs-V batch: the fixed 58 scenarios + supplementary + PvP73 scenarios, simulation records
(compare73.py) and native draw frames (frames73.py), both against a V reference recorded from the
CURRENT sources. One summary JSON; serial by default (memory).

    python batch73.py <tag> [jobs] [--frames] [names,comma,separated]
"""
import concurrent.futures, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(r'C:\Users\xiech\Downloads\PVZ_rougePvP_native')
HERE = Path(__file__).resolve().parent
FIXED = sorted({p.name.split('.')[0] for p in (ROOT / 'test_results/typed72-20261108/frames-f7').glob('*.cmp.json')})
SUPP = ['supp_actions', 'supp_ranked', 'supp_ranked_accept', 'supp_ranked_gold_lock', 'supp_ranked_gold_lock2']
PVP73 = ['coop_night7', 'pvp73_gravebuster_death', 'pvp73_gravebuster_charm', 'pvp73_imitate', 'pvp73_barrel_drop',
         'coop_rail8_w6', 'coop_rail8_w6_real']
args = [a for a in sys.argv[1:] if not a.startswith('--')]
tag = args[0]; jobs = int(args[1]) if len(args) > 1 else 1
names = args[2].split(',') if len(args) > 2 else FIXED + SUPP + PVP73
frames = '--frames' in sys.argv
OUT = ROOT / 'test_results/pvp73' / ('batch-' + tag); OUT.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONIOENCODING='utf-8')

def one(name):
    row = dict(scenario=name)
    d = OUT / name
    p = subprocess.run([sys.executable, str(HERE / 'compare73.py'), name, str(d.relative_to(ROOT))], cwd=str(ROOT), env=env, capture_output=True, timeout=7200)
    c = d / 'comparison.json'
    if c.exists():
        s = json.loads(c.read_text(encoding='utf8')); f = s.get('first_difference')
        row.update(identical=s.get('identical'), typed_rc=s.get('typed_rc'), lines=[s.get('reference_lines'), s.get('typed_lines')],
                   gaps=list(s.get('field_gaps', {}))[:6], log_equal=(s.get('final') or {}).get('log_equal'),
                   first=None if not f else dict(t=f['t'], head=[x[:4] for x in f['differences'][:4]]))
    else:
        row['error'] = (p.stdout + p.stderr).decode('utf8', 'replace')[-600:]
    for key in ('reference.jsonl', 'typed.jsonl', 'atlas.bin'):
        try: (d / key).unlink()
        except OSError: pass
    if frames:
        q = subprocess.run([sys.executable, str(HERE / 'frames73.py'), name, str((OUT / ('frames-' + name)).relative_to(ROOT))], cwd=str(ROOT), env=env, capture_output=True, timeout=7200)
        cmp = OUT / ('frames-' + name) / 'cmp.json'
        fr = json.loads(cmp.read_text(encoding='utf8')) if cmp.exists() else None
        row['frames'] = (fr['identical'] == fr['reference_frames'] == fr['typed_frames'] and not fr['absent']) if fr else ('error', q.stdout.decode('utf8', 'replace')[-300:] + q.stderr.decode('utf8', 'replace')[-300:])
    print(json.dumps(row, ensure_ascii=False)[:600], flush=True)
    return row

with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
    rows = list(pool.map(one, names))
ok = [r['scenario'] for r in rows if r.get('identical') and (not frames or r.get('frames') is True)]
(OUT / 'batch.json').write_text(json.dumps(dict(total=len(rows), identical=len(ok), rows=rows), ensure_ascii=False, indent=1), encoding='utf8')
print('IDENTICAL', len(ok), 'of', len(rows))
