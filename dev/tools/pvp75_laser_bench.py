"""PvP75 激光豆 rendering cost: the "laser" diagnostic scene with 0..N firing beans.

Same 20 durable zombies in every case; only the number of firing beans changes. Runs the
exe's own --diagnostic (production performance flags as engine options).
    python tools/pvp75_laser_bench.py pc  --exe <PvZPvPNative.exe> --out <dir> [--lasers 0,5,10,20,40] [--reps 2]
    python tools/pvp75_laser_bench.py summary --out <dir>
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
from pathlib import Path

FLAGS = {'PVP744_PACING': True, 'PVP744_VIEW_REUSE': True, 'PVP744_LOCAL_FRAME': True,
         'PVP744_STATE_VIEW': True, 'PVP744_METADATA_VIEW': True, 'PVP744_STEP_BUDGET_MS': 8}


def config(lasers, tiles=True, warmup=5, seconds=20):
    return dict(scenario='laser', units=20, lasers=lasers, durable_units=True, unit_hp=1e8,
                warmup_seconds=warmup, seconds=seconds, world_quality='native', display_filter='pixel',
                display_budget=False, optimized=True, detail=False, engine_options={**FLAGS, 'PVP75_LASER_TILES': tiles})


def metrics(report):
    ph = report['frame_phases_ms']
    return dict(fps=report['presentation']['frames_per_second'], render_ms=ph['render']['mean'], render_p95=ph['render']['p95'],
                frame_work_ms=ph['frame_work']['mean'], interval_p95=ph['frame_interval_actual']['p95'],
                sim_ratio=report['simulation_wall_ratio'], peak_rss_mib=report['native72']['memory'].get('peak_rss_bytes', 0) / 2**20,
                rss_mib=report['native72']['memory'].get('rss_bytes', 0) / 2**20)


def pc(a):
    exe = Path(a.exe).resolve(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    reports = exe.parent / 'reports'
    rows = []
    for rep in range(a.reps):
      for tiles in [{'old': False, 'tiles': True}[m] for m in a.modes.split(',')]:
        for n in [int(x) for x in a.lasers.split(',')]:
            case = out / f'{"tiles" if tiles else "old"}-lasers{n:02d}-r{rep + 1}'; case.mkdir()
            (case / 'config.json').write_text(json.dumps(config(n, tiles)), 'utf8')
            before = set(reports.glob('*.json')) if reports.exists() else set()
            env = dict({k: v for k, v in os.environ.items() if not k.startswith('PVP744_')},
                       PVP_USERDATA=str(case / 'userdata'), SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PVP741_PROFILE='0')
            with (case / 'stdout.log').open('wb') as log:
                r = subprocess.run([str(exe), '--diagnostic', str(case / 'config.json')], cwd=exe.parent, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, timeout=300, creationflags=0x08000000)
            fresh = [p for p in reports.glob('*.json') if p not in before and not p.name.endswith('.live.json')]
            assert r.returncode == 0 and len(fresh) == 1, (n, r.returncode, fresh)
            shutil.move(str(fresh[0]), case / 'report.json')
            png = fresh[0].with_suffix('.png')
            if png.exists(): shutil.move(str(png), case / 'frame.png')
            for live in reports.glob('*.live.json'): live.unlink()
            m = metrics(json.loads((case / 'report.json').read_text('utf8')))
            rows.append(dict(mode='tiles' if tiles else 'old', lasers=n, rep=rep + 1, **m)); print('tiles' if tiles else 'old', n, rep + 1, {k: round(v, 2) for k, v in m.items()}, flush=True)
    (out / 'samples.json').write_text(json.dumps(rows, indent=1), 'utf8')
    summary(out)


def summary(out):
    out = Path(out); rows = json.loads((out / 'samples.json').read_text('utf8'))
    table = {}
    for mode, n in sorted({(r.get('mode', 'old'), r['lasers']) for r in rows}):
        group = [r for r in rows if r.get('mode', 'old') == mode and r['lasers'] == n]
        table[f'{mode}-{n}'] = {k: statistics.median(r[k] for r in group) for k in group[0] if k not in ('mode', 'lasers', 'rep')}
    (out / 'summary.json').write_text(json.dumps(table, indent=1), 'utf8')
    for n, m in table.items(): print(n, {k: round(v, 2) for k, v in m.items()})


PACKAGE = 'org.pvzrouge.pvzpvpnative'
ADB = shutil.which('adb') or str(Path.home() / 'android-sdk/platform-tools/adb.exe')


def android(a):
    """Same scene on the phone: the installed APK's diagnostic entry (intent extra), reports pulled back."""
    import base64, re, time
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy')}
    def adb(*words, check=True, timeout=30):
        r = subprocess.run([ADB, '-s', a.serial] + list(words), capture_output=True, timeout=timeout, env=env)
        if check and r.returncode: raise RuntimeError((r.stdout + r.stderr).decode('utf8', 'replace'))
        return r.stdout.decode('utf8', 'replace')
    remote = '/sdcard/Android/data/' + PACKAGE + '/files/reports'
    pkg = adb('shell', 'dumpsys', 'package', PACKAGE); (out / 'package.txt').write_text(pkg, 'utf8')
    if a.code and not re.search(r'versionCode=' + str(a.code) + r'\b', pkg): raise RuntimeError('unexpected installed versionCode')
    rows = []
    for rep in range(a.reps):
      for tiles in [{'old': False, 'tiles': True}[m] for m in a.modes.split(',')]:
        for n in [int(x) for x in a.lasers.split(',')]:
            case = out / f'{"tiles" if tiles else "old"}-lasers{n:02d}-r{rep + 1}'; case.mkdir()
            cfg = config(n, tiles, warmup=5, seconds=a.seconds); cfg.update(json.loads(a.extra)); (case / 'config.json').write_text(json.dumps(cfg), 'utf8')
            for _ in range(60):  # let the phone cool below 40 C between scenes
                temp = int(re.search(r'temperature:\s*(\d+)', adb('shell', 'dumpsys', 'battery')).group(1))
                if temp < 400: break
                time.sleep(10)
            adb('shell', 'am', 'force-stop', PACKAGE)
            before = set(adb('shell', 'ls', '-1', remote, check=False).split())
            adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/org.pvzrouge.pvzpvpnative.PvPActivity',
                '--es', 'pvp72_diagnostic_b64', base64.b64encode(json.dumps(cfg).encode()).decode(), timeout=60)
            started = time.monotonic(); report = None
            while time.monotonic() - started < a.seconds + 180 and report is None:
                time.sleep(3)
                for name in adb('shell', 'ls', '-1', remote, check=False).split():
                    if name in before or not name.endswith('.json') or name.endswith('.live.json'): continue
                    try: d = json.loads(adb('shell', 'cat', remote + '/' + name, check=False))
                    except ValueError: continue
                    if d.get('completed') and 'native72' in d:
                        (case / 'report.json').write_text(json.dumps(d), 'utf8'); report = d
                        subprocess.run([ADB, '-s', a.serial, 'pull', remote + '/' + name[:-5] + '.png', str(case / 'frame.png')], capture_output=True, env=env)
                        break
            adb('shell', 'am', 'force-stop', PACKAGE)
            if report is None: raise RuntimeError('no completed report for ' + case.name)
            m = metrics(report); m['battery_c'] = temp / 10
            rows.append(dict(mode='tiles' if tiles else 'old', lasers=n, rep=rep + 1, **m)); print(case.name, {k: round(v, 2) for k, v in m.items()}, flush=True)
            (out / 'samples.json').write_text(json.dumps(rows, indent=1), 'utf8')
    summary(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['pc', 'android', 'summary'])
    ap.add_argument('--exe'); ap.add_argument('--out', required=True); ap.add_argument('--lasers', default='0,5,10,20,40'); ap.add_argument('--reps', type=int, default=2); ap.add_argument('--modes', default='old,tiles')
    ap.add_argument('--serial'); ap.add_argument('--code', type=int); ap.add_argument('--seconds', type=float, default=20); ap.add_argument('--extra', default='{}')
    a = ap.parse_args()
    {'pc': pc, 'android': android, 'summary': lambda a: summary(a.out)}[a.mode](a)
