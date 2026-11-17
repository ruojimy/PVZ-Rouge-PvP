"""External ADB driver. No source/APK changes, no install, isolated native diagnostics."""
import argparse, base64, hashlib, json, re, subprocess, time, os
from datetime import datetime, timezone
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--build', required=True)
    p.add_argument('--installed-name', required=True)
    p.add_argument('--code', required=True, type=int)
    a = p.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    plan = json.loads(Path(a.plan).read_text('utf-8-sig'))
    package = 'org.pvzrouge.pvzpvpnative'
    remote = '/sdcard/Android/data/' + package + '/files/reports'

    def raw(*words, check=True, timeout=12):
        serial = a.serial
        try:
            r = subprocess.run([a.adb, '-s', serial] + list(words), capture_output=True, timeout=timeout, env={**{k:v for k,v in os.environ.items() if k.lower() not in ("http_proxy","https_proxy","all_proxy")}, "NO_PROXY":"*", "no_proxy":"*"})
        except subprocess.TimeoutExpired:
            with (out / 'adb-timeouts.txt').open('a', encoding='utf8') as f:
                f.write(datetime.now(timezone.utc).isoformat() + ' ' + str(words) + '\n')
            if check:
                raise
            return b''
        if r.stderr:
            with (out / 'adb-stderr.txt').open('ab') as f:
                f.write((datetime.now(timezone.utc).isoformat() + ' ' + str(words) + '\n').encode('utf8'))
                f.write(r.stderr + b'\n')
        if check and r.returncode:
            raise RuntimeError((r.stdout + r.stderr).decode('utf8', 'replace'))
        return r.stdout

    def command(*words, **kwargs):
        return raw(*words, **kwargs).decode('utf8', 'replace').strip()

    def save(case, name, *words):
        (case / name).write_bytes(raw(*words, check=False))

    pkg = command('shell', 'dumpsys', 'package', package)
    (out / 'package-before.txt').write_text(pkg, 'utf8')
    if not re.search(r'^\s*versionName=' + re.escape(a.installed_name) + r'\s*$', pkg, re.M):
        raise RuntimeError('Incorrect installed versionName')
    codes = re.findall(r'^\s*versionCode=(\d+)\b', pkg, re.M)
    if not codes or any(int(c) != a.code for c in codes):
        raise RuntimeError('Incorrect installed versionCode')
    results = []
    for order, item in enumerate(plan):
        case = out / item['name']
        case.mkdir()
        cfg = dict(scenario=item['scenario'], units=item['units'], durable_units=True,
                   unit_hp=1e8, warmup_seconds=5, seconds=item['seconds'],
                   world_quality='native', display_filter='pixel', display_budget=False,
                   optimized=True, detail=False, prime_tentacles=item['scenario'] == 'grabber',
                   function_profile=item.get('function_profile', False))
        if item.get('audit_userdata'): cfg['audit_userdata'] = True
        if item.get('interactive_input'): cfg['interactive_input'] = True
        if 'engine_options' in item:
            cfg['engine_options'] = item['engine_options']
        (case / 'config.json').write_text(json.dumps(cfg, indent=2), 'utf8')
        command('shell', 'am', 'force-stop', package)
        previous = set(command('shell', 'ls', '-1', remote, check=False).splitlines())
        save(case, 'battery-before.txt', 'shell', 'dumpsys', 'battery')
        save(case, 'thermal-before.txt', 'shell', 'dumpsys', 'thermalservice')
        temp = re.search(r'^\s*temperature:\s*(\d+)', (case / 'battery-before.txt').read_text('utf8'), re.M)
        if temp and int(temp.group(1)) >= 400:
            raise RuntimeError('Battery temperature >=40C; pause before next scene')
        encoded = base64.b64encode(json.dumps(cfg).encode()).decode()
        started_utc = datetime.now(timezone.utc).isoformat()
        save(case, 'launch.txt', 'shell', 'am', 'start', '-W', '-n',
             package + '/org.pvzrouge.pvzpvpnative.PvPActivity',
             '--es', 'pvp72_diagnostic_b64', encoded)
        started = time.monotonic()
        report = None
        pid = None
        captured = False
        while time.monotonic() - started < item['seconds'] + 240:
            if not captured and time.monotonic() - started >= 20:
                pid = command('shell', 'pidof', package, check=False)
                save(case, 'device-screen.png', 'exec-out', 'screencap', '-p')
                save(case, 'meminfo-during.txt', 'shell', 'dumpsys', 'meminfo', package)
                activity = command('shell', 'dumpsys', 'activity', 'activities', check=False)
                (case / 'resumed-during.txt').write_text('\n'.join(
                    line for line in activity.splitlines() if 'topResumedActivity=' in line), 'utf8')
                captured = True
            fresh = [n for n in command('shell', 'ls', '-1', remote, check=False).splitlines()
                     if n not in previous and n.endswith('.json') and not n.endswith('.live.json')]
            for name in fresh:
                try:
                    d = json.loads(command('shell', 'cat', remote + '/' + name, check=False))
                except ValueError:
                    continue
                if not d.get('completed') or 'native72' not in d:
                    continue
                if d['native72']['build'] != a.build:
                    raise RuntimeError('Report build mismatch')
                command('pull', remote + '/' + name, str(case / 'report.json'))
                command('pull', remote + '/' + name[:-5] + '.png', str(case / 'frame.png'), check=False)
                report = json.loads((case / 'report.json').read_text('utf8'))
                break
            if report is not None:
                break
            time.sleep(2)
        save(case, 'battery-after.txt', 'shell', 'dumpsys', 'battery')
        save(case, 'thermal-after.txt', 'shell', 'dumpsys', 'thermalservice')
        events = command('logcat', '-b', 'events', '-d', '-v', 'time', check=False)
        (case / 'lifecycle-events.txt').write_text('\n'.join(
            line for line in events.splitlines() if package in line and
            any(tag in line for tag in ('wm_on_pause_called', 'wm_on_resume_called',
                'wm_on_top_resumed_lost_called', 'wm_on_top_resumed_gained_called',
                'wm_activity_launch_time', 'wm_destroy_activity'))), 'utf8')
        if pid and pid.isdigit():
            save(case, 'logcat.txt', 'logcat', '-d', '--pid=' + pid, '-t', '1500')
        if report is None:
            save(case, 'failure-meminfo.txt', 'shell', 'dumpsys', 'meminfo', package)
            raise RuntimeError('No completed report for ' + item['name'])
        backend = report['backend_audit']
        neutral_audit = None
        if item.get('strict_neutral'):
            players = report['final_state']['players']
            neutral_audit = dict(attempts=backend.get('typed_commands'),
                players={s:{k:v.get(k) for k in ('seq','last_input_tick','input','jump_held')} for s,v in players.items()})
            initial_tick = 2 if cfg['prime_tentacles'] else 0
            # CommandInput increments sequence before accepting any new action;
            # typed_commands also counts rejected stale sequence attempts.
            valid = backend.get('typed_commands') in (2,4) and all(
                v.get('seq')==1 and v.get('last_input_tick')==initial_tick and
                v.get('input',{}).get('move')==0 and v.get('jump_held') is False
                for v in players.values())
            neutral_audit['passed'] = valid
            if not valid:
                raise RuntimeError('Neutral comparison received new input; keep this case as interaction evidence')
        if cfg.get('audit_userdata') and not report.get('userdata_audit',{}).get('unchanged'):
            raise RuntimeError('Original userdata changed during isolated diagnostic')
        for switch,counter in [('PVP744_METADATA_VIEW','metadata_view'),('PVP744_STATE_VIEW','state_view')]:
            if cfg.get('engine_options',{}).get(switch) and backend.get(counter,{}).get('builds',0)<=0:
                raise RuntimeError('Requested presentation path was not exercised: '+switch)
        if backend.get('backend') != 'typed72' or not backend.get('session'):
            raise RuntimeError('Not actual typed native Session')
        # 74.1 predates frame_descriptions; retain its projection counters verbatim.
        if 'frame_descriptions' in backend and backend['frame_descriptions'] <= 0:
            raise RuntimeError('Native frame route was not used')
        for counter in backend['dynamic_v_work'].values():
            if counter['boxes'] != 0 or counter['calls'] != 0:
                raise RuntimeError('Dynamic boxed work in native step')
        row = {k: report.get(k) for k in ('completed', 'wall_seconds', 'simulated_seconds',
               'simulation_wall_ratio', 'frames', 'presentation', 'frame_phases_ms',
               'frame_phases_cpu_ms', 'native72', 'population_samples', 'backend_audit', 'fixture', 'userdata_audit', 'config')}
        row.update(name=item['name'], order=order, config=cfg, started_utc=started_utc,
                   finished_utc=datetime.now(timezone.utc).isoformat(),
                   neutral_input_audit=neutral_audit,
                   report_sha256=hashlib.sha256((case / 'report.json').read_bytes()).hexdigest())
        results.append(row)
        (out / 'summary.json').write_text(json.dumps(dict(completed=len(results) == len(plan),
            build=a.build, version_code=a.code, results=results), ensure_ascii=False, indent=2), 'utf8')
        print(item['name'], report['presentation']['frames_per_second'], 'FPS',
              report.get('simulation_wall_ratio'), 'simulation/wall', flush=True)
    save(out, 'package-after.txt', 'shell', 'dumpsys', 'package', package)
    command('shell', 'am', 'force-stop', package)


if __name__ == '__main__':
    main()


