"""Isolated allocator A/B for the real guest receive/merge ownership chain."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('exe', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--iterations', type=int, default=128)
    p.add_argument('--units', type=int, default=200)
    args = p.parse_args()
    if not 64 <= args.iterations <= 200 or not 10 <= args.units <= 300:
        p.error('bounded limits: 64..200 messages, 10..300 units')
    exe = args.exe.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    modes = ['same_wire', 'cross_wire']
    runs = []
    for alloc in (0, 1):
        for mode in modes:
            folder = out / ('allocator-' + str(alloc))
            folder.mkdir(exist_ok=True)
            report = folder / (mode + '.json')
            env = dict(os.environ, PVP742_ALLOCATOR=str(alloc),
                       SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                       PVP741_PROFILE='0')
            command = [str(exe), str(report), mode, str(args.iterations), str(args.units)]
            try:
                result = subprocess.run(command, cwd=str(root), env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=180)
                (folder / (mode + '.stdout.log')).write_bytes(result.stdout)
                (folder / (mode + '.stderr.log')).write_bytes(result.stderr)
                data = json.loads(report.read_text('utf8')) if report.exists() else {'passed': False, 'error': 'child wrote no JSON'}
                data['exit_code'] = result.returncode
            except subprocess.TimeoutExpired as error:
                data = {'passed': False, 'error': '180-second child deadline', 'exit_code': None}
                (folder / (mode + '.stdout.log')).write_bytes(error.stdout or b'')
                (folder / (mode + '.stderr.log')).write_bytes(error.stderr or b'')
            data['mode'] = mode
            data['allocator'] = alloc
            data['report'] = str(report)
            runs.append(data)
            print(json.dumps({k: data.get(k) for k in
                              ('allocator', 'mode', 'passed', 'completed_messages',
                               'stopped_at_memory_cap', 'slab_bytes_added',
                               'requested_final_live_bytes', 'error')}, ensure_ascii=False), flush=True)
    hashes = {run.get('final_view_sha256') for run in runs if run.get('passed')}
    snapshots_equal = len(hashes) == 1 and None not in hashes and len(hashes) > 0
    comparisons = []
    for mode in modes:
        pair = [next(run for run in runs if run['allocator'] == a and run['mode'] == mode) for a in (0, 1)]
        row = {'mode': mode, 'production_thread_placement': mode == 'cross_wire'}
        for alloc, run in enumerate(pair):
            samples = [s for s in run.get('samples', []) if s['phase'] == 'message']
            row[str(alloc)] = {'completed': run.get('completed_messages'),
                               'slab_bytes_added': run.get('slab_bytes_added'),
                               'requested_final_live_bytes': run.get('requested_final_live_bytes'),
                               'requested_held_view_bytes': run.get('requested_held_view_bytes'),
                               'private_bytes_added_during_messages':
                                   samples[-1]['private_bytes'] - run['private_bytes_before'] if samples else None,
                               'late_requested_live_growth':
                                   samples[-1]['requested_live_bytes'] - samples[len(samples)//2]['requested_live_bytes'] if samples else None,
                               'stopped_at_memory_cap': run.get('stopped_at_memory_cap')}
        comparisons.append(row)
    passed = all(run.get('passed') and run.get('exit_code') == 0 for run in runs) and snapshots_equal
    summary = {'passed': passed, 'snapshot_hashes_equal_across_all_children': snapshots_equal,
               'iterations': args.iterations, 'units': args.units, 'comparisons': comparisons,
               'runs': [{k: run.get(k) for k in ('allocator', 'mode', 'passed', 'report', 'error')} for run in runs],
               'scope': 'Each child is isolated. cross_wire preserves production decoding threads; same_wire is its same-thread control. Large inner snapshot trees stay on the UI thread. Requested bytes exclude slabs/foreign malloc; Windows PrivateBytes is commit. Each message is consumed before the next, and growth is stopped at 256 MiB above warm baseline.'}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({'passed': passed, 'snapshot_hashes_equal': snapshots_equal, 'summary': str(out / 'summary.json')}, ensure_ascii=False), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
