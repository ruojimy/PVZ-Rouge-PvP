"""Bounded isolated allocator A/B through real dynamic guest draw ownership."""
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
    p.add_argument('--frames', type=int, default=64)
    p.add_argument('--units', type=int, default=120)
    p.add_argument('--cap-mib', type=int, choices=[256, 512], default=256)
    p.add_argument('--scenes', nargs='+', choices=['mixed', 'grabber', 'dense'],
                   default=['mixed', 'grabber', 'dense'])
    args = p.parse_args()
    if not 64 <= args.frames <= 256 or not 20 <= args.units <= 240:
        p.error('bounded limits: 64..256 frames, 20..240 units')
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, comparisons = [], []
    for scene in args.scenes:
        pair = []
        for allocator in (0, 1):
            report = out / (scene + '-allocator-' + str(allocator) + '.json')
            env = dict(os.environ, PVP742_ALLOCATOR=str(allocator),
                       SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                       PVP741_PROFILE='1', PVP_CAPTURE_CPP_TRACE='1', PVP742_SURFACE_MEMORY='1')
            command = [str(args.exe.resolve()), str(report), scene,
                       str(args.frames), str(args.units), str(args.cap_mib)]
            try:
                result = subprocess.run(command, cwd=str(root), env=env,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, timeout=240)
                report.with_suffix('.stdout.log').write_bytes(result.stdout)
                report.with_suffix('.stderr.log').write_bytes(result.stderr)
                data = json.loads(report.read_text('utf8')) if report.exists() else {
                    'passed': False, 'error': 'child wrote no JSON'}
                data['exit_code'] = result.returncode
            except subprocess.TimeoutExpired as error:
                report.with_suffix('.stdout.log').write_bytes(error.stdout or b'')
                report.with_suffix('.stderr.log').write_bytes(error.stderr or b'')
                data = {'passed': False, 'error': '240-second child deadline',
                        'exit_code': None}
            data.update(allocator=allocator, scene=scene, report=str(report))
            pair.append(data)
            rows.append({k: data.get(k) for k in
                         ('allocator', 'scene', 'passed', 'report', 'exit_code',
                          'completed_frames', 'stopped_at_memory_cap', 'phase', 'error')})
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        same_frames = pair[0].get('completed_frames') == pair[1].get('completed_frames')
        compare = {'scene': scene, 'same_completed_frames': same_frames}
        for field in ('host_state_sha256', 'native_frame_sha256',
                      'guest_view_sha256', 'rendered_pixels_sha256'):
            compare[field + '_equal'] = (same_frames and pair[0].get(field) is not None
                                        and pair[0].get(field) == pair[1].get(field))
        for index, data in enumerate(pair):
            samples = data.get('samples', [])
            first, late, last = (samples[0], samples[len(samples)//2], samples[-1]) if samples else ({}, {}, {})
            compare[str(index)] = {
                'completed_frames': data.get('completed_frames'),
                'stopped_at_memory_cap': data.get('stopped_at_memory_cap'),
                'cold_to_last_private_growth': last.get('private_bytes', 0) - data.get('baseline_private_bytes', 0),
                'first_to_last_private_growth': last.get('private_bytes', 0) - first.get('private_bytes', 0),
                'late_private_growth': last.get('private_bytes', 0) - late.get('private_bytes', 0),
                'first_to_last_requested_live_growth': last.get('requested_live_bytes', 0) - first.get('requested_live_bytes', 0),
                'late_requested_live_growth': last.get('requested_live_bytes', 0) - late.get('requested_live_bytes', 0),
                'first_to_last_slab_growth': last.get('slab_bytes', 0) - first.get('slab_bytes', 0),
                'requested_peak_bytes_max': max((s['requested_peak_bytes'] for s in samples), default=0),
                'draw_before': data.get('draw_before'),
                'draw_after': data.get('draw_after'),
                'final_units': last.get('units'),
                'final_draw_commands': last.get('draw_commands')}
        comparisons.append(compare)
    completed = all(row['passed'] and row['exit_code'] == 0 for row in rows)
    equivalent = all(row[key + '_equal'] for row in comparisons
                     for key in ('host_state_sha256', 'native_frame_sha256', 'guest_view_sha256'))
    uncapped = all(row['stopped_at_memory_cap'] is False for row in rows)
    summary = {'passed': completed and equivalent and uncapped,
               'children_completed_without_exception': completed,
               'simulation_and_guest_state_equal': equivalent,
               'all_requested_frames_completed_without_memory_cap': uncapped,
               'private_growth_cap_mib': args.cap_mib, 'comparisons': comparisons, 'runs': rows,
               'scope': 'Each process owns one evolving real host and guest, one overwriting wire slot, actual background outer decoder and UI unpack/merge/render. First-render resources are included in the explicitly reported cap. Raw test processes also retain a test host; absolute memory is not standalone guest usage. A bounded passing run is not long-duration stability proof.'}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({'passed': summary['passed'], 'summary': str(out / 'summary.json')}, ensure_ascii=False), flush=True)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
