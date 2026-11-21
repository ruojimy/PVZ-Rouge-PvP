"""Audit completed overnight evidence without changing any model or selection."""
import datetime
import gzip
import hashlib
import json
import zipfile
from pathlib import Path
from overnight_common import B, R, TZ, read, sha, usage, write

state = read(B / 'state.json')
assert state['completed'], 'The study is still running or stopped incompletely.'
prepared = read(B / 'prepared.json')
plan = read(B / 'plan.json')
expected = {**prepared['source_sha256'], **prepared['binary_sha256']}
expected.update({str(R / name): value for name, value in plan['source_sha256'].items()})
changed = [name for name, value in expected.items() if sha(Path(name)) != value]
assert not changed, changed
frozen = read(B / 'research-sources.json')
assert sha(Path(frozen['archive'])) == frozen['archive_sha256']
with zipfile.ZipFile(frozen['archive']) as archive:
    for name, expected_hash in frozen['files'].items():
        assert hashlib.sha256(archive.read(Path(name).relative_to(R).as_posix())).hexdigest() == expected_hash

archives = []
for manifest_path in sorted((B / 'eval').glob('*/archives.json')):
    for original, record in read(manifest_path).items():
        path = Path(record['archive'])
        assert sha(path) == record['archive_sha256'], str(path)
        with gzip.open(path, 'rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == record['raw_sha256'], str(path)
        assert not Path(original).exists(), original
        archives.append(dict(path=str(path), bytes=path.stat().st_size))

evaluations = []
for path in sorted((B / 'eval').glob('*/summary.json')):
    if path.parent.name.startswith('supp-'):
        continue
    summary = read(path)
    assert set(summary['ids']) == set(summary['matches']), str(path)
    for uid, match in summary['matches'].items():
        data = path.parent / 'matches' / (uid + '.jsonl')
        assert sha(data) == match['file_sha256'], str(data)
    evaluations.append(dict(name=path.parent.name, games=len(summary['matches']),
                            crashes=summary['crashed'], ai_errors=[uid for uid, m in summary['matches'].items() if m['ai_error']]))
models = []
policy_groups = {}
for path in sorted((B / 'models').glob('*/report.json')):
    report = read(path)
    model = read(path.parent / 'model.json')
    policy = {k: v for k, v in model.items() if k not in {'training_source', 'ablation'}}
    digest = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    policy_groups.setdefault(digest, []).append(path.parent.name)
    models.append(dict(name=path.parent.name, epochs=len(report['history']),
                       selected_epoch=report['selected_epoch'], rows=report['train_rows'],
                       model_sha256=sha(path.parent / 'model.json'), policy_digest=digest, test_used=report['test_used']))
disk_rows = [read(p) for p in B.glob('disk-*.json')]
size, free = usage()
fixtures = [r for r in evaluations if r['name'] == 'telemetry-regression']
regular = [r for r in evaluations if r['name'] != 'telemetry-regression']
receipt = dict(completed=True, audited_at=datetime.datetime.now(TZ).isoformat(),
    state=state, game_revision=plan['game_revision'], release_sha256=plan['release_sha256'],
    source_and_binary_hashes_verified=len(expected), source_archive_verified=True,
    raw_archives_verified=len(archives), archive_bytes=sum(r['bytes'] for r in archives),
    evaluated_games=sum(r['games'] for r in regular), evaluation_groups=regular,
    fixture_games=sum(r['games'] for r in fixtures), fixture_groups=fixtures,
    all_completed_eval_games=sum(r['games'] for r in evaluations),
    completed_training_runs=len(models), completed_epochs=sum(r['epochs'] for r in models), models=models,
    unique_selected_parameter_sets=len(policy_groups), identical_parameter_groups=[v for v in policy_groups.values() if len(v)>1],
    new_bytes=size, sampled_peak_bytes=max([size, *[d['new_bytes_peak'] for d in disk_rows]]),
    free_bytes=free, sampled_minimum_free_bytes=min([free, *[d['minimum_free_bytes'] for d in disk_rows]]),
    interrupted_attempts_preserved=[str(p) for p in B.glob('interrupted*')],
    note='Counts cover completed eval groups only. Structural/telemetry fixtures and interrupted fits are separate. No formal release or user save was replaced.')
write(B / 'completion.json', receipt)
print(json.dumps({k: receipt[k] for k in ['evaluated_games', 'completed_training_runs', 'completed_epochs',
    'raw_archives_verified', 'new_bytes', 'sampled_peak_bytes', 'free_bytes']}))
