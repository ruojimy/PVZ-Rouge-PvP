"""Same barrage diagnostic, same fixed tick count, typed package vs V package (Python 3.8+).
Runs each package from a private copy (never the release directory) with dummy video,
warmup 150 room ticks + 900 measured room ticks, then compares final_state_sha256,
final_rng_sha256 and the zombie Dave's final position/velocity.
Usage: pc_barrage_equivalence.py <out-dir> <typed-pkg> <v-pkg>"""
import json, os, shutil, subprocess, sys
from pathlib import Path

out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=False)
rows = {}
for label, src in (('typed', sys.argv[2]), ('v', sys.argv[3])):
    pkg = out / ('pkg-' + label); shutil.copytree(Path(src).resolve(), pkg)
    run = out / label; run.mkdir()
    cfg = dict(scenario='barrage', units=120, warmup_room_ticks=150, measure_room_ticks=900, warmup_seconds=5, seconds=30,
               world_quality='native', display_filter='pixel', optimized=True, detail=False)
    (run / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    env = dict(os.environ); env['PVP_USERDATA'] = str(run / 'userdata'); env['SDL_VIDEODRIVER'] = 'dummy'; env['SDL_AUDIODRIVER'] = 'dummy'
    with open(run / 'stdout.txt', 'wb') as so, open(run / 'stderr.txt', 'wb') as se:
        rc = subprocess.run([str(pkg / 'PvZPvPNative.exe'), '--diagnostic', str(run / 'config.json')], cwd=str(pkg), env=env,
                            stdout=so, stderr=se, timeout=900).returncode
    text = (run / 'stdout.txt').read_text('utf-8', errors='replace') + (run / 'stderr.txt').read_text('utf-8', errors='replace')
    report = None
    for line in text.splitlines():
        if 'PVP72_DIAGNOSTIC_COMPLETE' in line: report = Path(line.split('PVP72_DIAGNOSTIC_COMPLETE', 1)[1].strip())
    r = json.loads(report.read_text(encoding='utf-8'))
    shutil.copy2(report, run / 'report.json')
    z = r['final_state']['players']['zombie']
    rows[label] = dict(exit=rc, room_ticks=r.get('room_ticks'), native_tick=r['final_state'].get('native_tick'),
                       final_state_sha256=r['final_state_sha256'], final_rng_sha256=r['final_rng_sha256'],
                       zombie_dave=dict(x=z['x'], y=z['y'], vx=z.get('vx'), vy=z.get('vy'), hp=z['hp'], knock_vx=z.get('knock_vx'), knock_until=z.get('knock_until')),
                       typed_session='[typed72] battle session started' in text)
    print(label, json.dumps(rows[label], ensure_ascii=False), flush=True)
same = {k: rows['typed'][k] == rows['v'][k] for k in ('room_ticks', 'native_tick', 'final_state_sha256', 'final_rng_sha256', 'zombie_dave')}
result = dict(rows=rows, identical=same, passed=all(same.values()))
(out / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(same), 'IDENTICAL' if result['passed'] else 'DIFFERENT')
