"""Run all eight interaction audits serially and fail closed (Python 3.8+)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ('mouse', 'touch', 'sdl-mouse', 'sdl-touch')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate(report, backend):
    if not isinstance(report, dict):
        raise ValueError('Audit report must be an object')
    planned, checks = report['planned_checks'], report['checks']
    if not planned or len(planned) != len(set(planned)):
        raise ValueError('Empty or duplicate planned checks')
    ids = [c['id'] for c in checks]
    if len(ids) != len(set(ids)) or set(ids) != set(planned):
        raise ValueError('Missing, extra or duplicate completed checks')
    n = len(planned)
    if not (report['complete'] is True and report['passed'] is True
            and report['completed_checks'] == report['pass_count'] == n
            and report['fail_count'] == report['unrun_count'] == 0
            and not report.get('fatal_error')
            and all(c['passed'] is True for c in checks)):
        raise ValueError('Incomplete or failed interaction audit')
    if backend == 'typed':
        proof = report['backend_audit']
        if not (proof['backend'] == 'typed72' and proof['session'] is True
                and all(proof[k] > 0 for k in ('typed_steps', 'typed_commands', 'typed_tick'))
                and proof['v_tick_now'] == proof['v_tick_at_start']
                and proof['v_native_tick_now'] == proof['v_native_tick_at_start']):
            raise ValueError('Typed backend proof missing or V clocks advanced')
        scalar = report['scalar_observation']
        if ('typed_scalar_observation' not in ids
                or scalar['projections_before'] != scalar['projections_after']):
            raise ValueError('Scalar reads caused full-world projection')
    return n


def save(path, data):
    temp = path.with_suffix('.pending')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(str(temp), str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--typed-exe', default='build/app-typed72-v2/Release/typed72_battle_audit.exe')
    parser.add_argument('--baseline-exe', default='build/Release/battle_interaction_audit.exe')
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    executables = {'typed': Path(args.typed_exe).resolve(), 'v-baseline': Path(args.baseline_exe).resolve()}
    fingerprints = {name: {'path': str(path), 'sha256': digest(path)} for name, path in executables.items()}
    out.mkdir(parents=True, exist_ok=False)
    summary = {'schema': 1, 'passed': False, 'executables': fingerprints, 'rows': []}
    save(out / 'summary.json', summary)
    for backend, exe in executables.items():
        for variant in VARIANTS:
            case = out / (backend + '-' + variant)
            case.mkdir()
            env = {k.upper(): v for k, v in os.environ.items() if not k.upper().startswith(('MATCH_', 'REF_'))}
            env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PVP_USERDATA=str(case / 'userdata'))
            row = {'backend': backend, 'variant': variant, 'passed': False}
            started = time.monotonic()
            try:
                with (case / 'stdout.txt').open('wb') as so, (case / 'stderr.txt').open('wb') as se:
                    result = subprocess.run([str(exe), str(case), variant], cwd=str(ROOT), env=env,
                                            stdout=so, stderr=se, timeout=args.timeout)
                row['exit'] = result.returncode
                if result.returncode != 0:
                    raise ValueError('Audit process exited %d' % result.returncode)
                report_path = case / 'report.json'
                report = json.loads(report_path.read_text(encoding='utf-8-sig'))
                row['checks'] = validate(report, backend)
                row['report_sha256'] = digest(report_path)
                if digest(exe) != fingerprints[backend]['sha256']:
                    raise ValueError('Executable changed while audit ran')
                row['passed'] = True
            except Exception as error:
                row['error'] = '%s: %s' % (type(error).__name__, error)
            row['seconds'] = round(time.monotonic() - started, 3)
            summary['rows'].append(row)
            save(out / 'summary.json', summary)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    summary['passed'] = len(summary['rows']) == 8 and all(row['passed'] for row in summary['rows'])
    save(out / 'summary.json', summary)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
