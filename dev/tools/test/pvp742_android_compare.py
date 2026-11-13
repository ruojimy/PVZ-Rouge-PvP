"""Run the four sustained-load scenes on an explicit, already installed phone.

The production diagnostic isolates userdata. This script neither installs an
APK nor changes routes, pairing, saves, or game settings. Each case keeps raw
reports, phase timings, population, battery temperature and package identity.
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--expected-build', default='1.6.0.74.2-typed.20261113')
    parser.add_argument('--expected-code', type=int, default=1114071)
    parser.add_argument('--package', default='org.pvzrouge.pvzpvpnative')
    parser.add_argument('--render-stats', action='store_true')
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.]+', args.package):
        raise ValueError('Invalid package name')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    adb = [args.adb, '-s', args.serial]

    def command(*words, check=True):
        result = subprocess.run(adb + list(words), capture_output=True, timeout=60)
        content = (result.stdout + result.stderr).decode('utf8', errors='replace').strip()
        if check and result.returncode:
            raise RuntimeError(content)
        return content

    command('get-state')
    package = command('shell', 'dumpsys', 'package', args.package)
    (out / 'package-before.txt').write_text(package, encoding='utf8')
    (out / 'device.txt').write_text(command('shell', 'getprop'), encoding='utf8')
    if 'versionName=' + args.expected_build not in package:
        raise RuntimeError('Installed package is not the expected build')
    codes = re.findall(r'^\s*versionCode=(\d+)\b', package, re.MULTILINE)
    if not codes or any(int(code) != args.expected_code for code in codes):
        raise RuntimeError('Installed package versionCode differs from candidate')
    remote_folder = '/sdcard/Android/data/' + args.package + '/files/reports'
    results = []
    for scene, units, seconds in [('ordinary', 20, 30), ('mixed', 120, 30),
                                   ('barrage', 240, 60), ('grabber', 120, 60)]:
        case = out / (scene + str(units))
        case.mkdir()
        config = dict(scenario=scene, units=units, durable_units=True, unit_hp=1e8,
                      warmup_seconds=5, seconds=seconds, world_quality='native',
                      display_filter='pixel', display_budget=False, optimized=True,
                      detail=False, prime_tentacles=scene == 'grabber',
                      function_profile=args.profile)
        (case / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf8')
        (case / 'battery-before.txt').write_text(command('shell', 'dumpsys', 'battery'), encoding='utf8')
        command('shell', 'am', 'force-stop', args.package)
        previous = set(command('shell', 'ls', '-1', remote_folder, check=False).splitlines())
        encoded = base64.b64encode(json.dumps(config).encode()).decode()
        launch = ['shell', 'am', 'start', '-W', '-n',
                  args.package + '/org.pvzrouge.pvzpvpnative.PvPActivity',
                  '--es', 'pvp72_diagnostic_b64', encoded]
        if args.render_stats:
            launch += ['--ez', 'pvp72_render_stats', 'true']
        (case / 'launch.txt').write_text(command(*launch), encoding='utf8')
        started = time.monotonic()
        report = None
        while time.monotonic() - started < seconds + 240:
            paths = command('shell', 'ls', '-1', remote_folder, check=False).splitlines()
            fresh = [p for p in paths if p not in previous and p.endswith('.json') and not p.endswith('.live.json')]
            for name in fresh:
                try:
                    value = json.loads(command('shell', 'cat', remote_folder + '/' + name, check=False))
                except ValueError:
                    continue
                if not value.get('completed') or 'native72' not in value:
                    continue
                if value['native72']['build'] != args.expected_build:
                    raise RuntimeError('Report build does not match installed candidate')
                command('pull', remote_folder + '/' + name, str(case / 'report.json'))
                command('pull', remote_folder + '/' + name[:-5] + '.png', str(case / 'frame.png'), check=False)
                report = json.loads((case / 'report.json').read_text('utf8'))
                break
            if report is not None:
                break
            time.sleep(2)
        (case / 'battery-after.txt').write_text(command('shell', 'dumpsys', 'battery'), encoding='utf8')
        (case / 'logcat.txt').write_text(command('logcat', '-d', '-t', '1200'), encoding='utf8')
        if report is None:
            raise RuntimeError('No completed report for ' + scene)
        assert report['backend_audit']['frame_descriptions'] > 0
        for counter in report['backend_audit']['dynamic_v_work'].values():
            assert counter['boxes'] == counter['calls'] == 0
        result = {k: report.get(k) for k in ('completed', 'wall_seconds', 'simulated_seconds',
                  'simulation_wall_ratio', 'frames', 'presentation', 'frame_phases_ms',
                  'frame_phases_cpu_ms', 'native72', 'population_samples', 'backend_audit')}
        result.update(scene=scene, units=units,
                      report_sha256=hashlib.sha256((case / 'report.json').read_bytes()).hexdigest())
        results.append(result)
        (out / 'summary.json').write_text(json.dumps(dict(completed=len(results) == 4,
            serial=args.serial, build=args.expected_build, version_code=args.expected_code, render_stats=args.render_stats,
            function_profile=args.profile, results=results), ensure_ascii=False, indent=2), encoding='utf8')
        print(scene, report['presentation']['frames_per_second'], 'FPS', flush=True)
    (out / 'package-after.txt').write_text(command('shell', 'dumpsys', 'package', args.package), encoding='utf8')
    command('shell', 'am', 'force-stop', args.package)


if __name__ == '__main__':
    main()
