"""Follow up the two improved frozen-opponent zombie timeouts and test both heads together."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sys

from home_pool import BIN, CURRENT, H, OLD_MODEL, OUT, arm_game, cmd, footer, inputs_ok, read, score, sha, write
from home_analysis import deployment_rates
from coverage_guard import size


def followup():
    inputs_ok()
    disk = read(OUT / 'disk.json')
    assert disk['prior'] + size(OUT) + 256 * 2**20 < 4 * 2**30
    assert shutil.disk_usage(OUT).free > 100 * 2**30 + 256 * 2**20
    model = OUT / 'snapshot-only' / 'model.json'
    assert sha(model) == read(model.parent / 'frozen.json')['model_sha256']
    improvements = []
    for opponent, plant_model in [('r', None), ('o', OLD_MODEL), ('n', CURRENT)]:
        before = read(OUT / 'test' / (opponent + 'n') / 'ready.json')['rows']
        after = read(OUT / 'test' / (opponent + 'b') / 'ready.json')['rows']
        for uid, row in after.items():
            if row['match']['timeout'] and score(before[uid]['match'], 'zombie') == -1:
                improvements.append((opponent, plant_model, uid, before[uid], row))

    def probe(pair):
        opponent, plant_model, uid, before, after = pair
        folder = OUT / 'followup' / (opponent + 'b-' + uid)
        flags = ['--model', plant_model or model, '--nn-seat', 'both' if plant_model else 'zombie']
        if plant_model:
            flags += ['--zombie-model', model]
        if not (folder / 'summary.json').exists():
            cmd(sys.executable, H/'eval.py', '--bin', BIN/'headless_match.exe', '--corpus', OUT/'plain',
                '--out-dir', folder, '--ids', uid, '--jobs', 1, '--limit-seconds', 1200, '--planner',
                'nn', '--', *flags, '--telemetry', '--no-records')
        summary = read(folder / 'summary.json')
        result = summary['matches'][uid]
        assert not result['ai_error'] and not summary['crashed']
        full = footer(folder / 'matches' / (uid + '.jsonl'))
        original = footer(Path(after['trace']))
        assert [e for e in full['activity'] if e['time'] < 600] == [e for e in original['activity'] if e['time'] < 600]
        return {'opponent': opponent, 'opening': uid, 'before': before['match'], 'short': after['match'], 'extended': result}

    with ThreadPoolExecutor(max_workers=2) as pool:
        probes = list(pool.map(probe, improvements))
    arm_game('test', 'bb')
    independent = read(OUT / 'test' / 'bb' / 'ready.json')
    assert independent['new'] == 12
    for row in independent['rows'].values():
        assert sha(Path(row['trace'])) == row['match']['file_sha256']
    write(OUT / 'followup.json', dict(home_timeout_probes=probes, selfplay_deploys_per_min=deployment_rates('bb'),
          selfplay_rows={i: row['match'] for i, row in independent['rows'].items()},
          purpose='Post-selection diagnostics on the same held-out openings, no weight update or new independent test.'))


if __name__ == '__main__':
    followup()
