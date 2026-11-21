"""Read-only evidence checks, followed by one combined overnight receipt."""
import gzip
import json
import zipfile
from overnight_common import *

plans = [(B/'plan.json', True), (B/'prepared.json', False),
         (B/'supplement/plan.json', False), (B/'residual/plan.json', False),
         (B/'residual/native-prepared.json', False), (B/'polish/plan.json', False),
         (B/'polish/parents.json', False)]
verified = {}
for path, relative in plans:
    if not path.exists(): continue
    doc = read(path)
    for field in ['source_sha256', 'binary_sha256', 'data_sha256']:
        for name, expected in doc.get(field, {}).items():
            source = R/name if relative and field == 'source_sha256' else Path(name)
            assert sha(source) == expected, str(source)
            verified[str(source)] = expected
assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe') == read(B/'plan.json')['release_sha256']
for manifest in [B/'research-sources.json', B/'additional-research-sources.json', B/'polish-research-sources.json']:
    if not manifest.exists(): continue
    doc = read(manifest)
    assert sha(Path(doc['archive'])) == doc['archive_sha256']
    with zipfile.ZipFile(doc['archive']) as archive:
        for name, expected in doc['files'].items():
            assert hashlib.sha256(archive.read(Path(name).relative_to(R).as_posix())).hexdigest() == expected

archives = []
for path in sorted((B/'eval').glob('*/archives.json')):
    for original, record in read(path).items():
        archive = Path(record['archive'])
        assert sha(archive) == record['archive_sha256']
        with gzip.open(archive, 'rb') as handle:
            assert hashlib.file_digest(handle, 'sha256').hexdigest() == record['raw_sha256']
        assert not Path(original).exists()
        archives.append(str(archive))

evaluations = []; unfinished = []
for folder in sorted((B/'eval').iterdir()):
    if not folder.is_dir(): continue
    if not (folder/'summary.json').exists():
        unfinished.append(dict(name=folder.name, files=len(list((folder/'matches').glob('*.jsonl')))))
        continue
    summary = read(folder/'summary.json')
    assert set(summary['ids']) == set(summary['matches']), str(folder)
    for uid, row in summary['matches'].items():
        assert sha(folder/'matches'/f'{uid}.jsonl') == row['file_sha256'], str(folder/uid)
    study = 'supplement' if folder.name.startswith('supp-') else 'residual' if folder.name.startswith('resid-') else 'polish' if folder.name.startswith('polish-') else 'main'
    fixture = folder.name == 'telemetry-regression' or folder.name.startswith(('resid-neutral-', 'resid-legacy-check-'))
    evaluations.append(dict(name=folder.name, study=study, games=len(summary['matches']), fixture=fixture,
        crashes=summary['crashed'], ai_errors=[uid for uid,r in summary['matches'].items() if r['ai_error']]))
main = [r for r in evaluations if r['study']=='main']
assert sum(r['games'] for r in main) == read(B/'completion.json')['all_completed_eval_games']

states = {}; tests = {}; selections = {}; contracts = []
for name, base in [('main', B), ('supplement', B/'supplement'), ('residual', B/'residual'), ('polish', B/'polish')]:
    if not (base/'state.json').exists(): continue
    states[name] = read(base/'state.json')
    if (base/'test-results.json').exists(): tests[name] = read(base/'test-results.json')
    if (base/'selection.json').exists():
        selection=read(base/'selection.json'); selections[name]=selection
        assert selection['test_not_opened']
        for side, selected in selection['best'].items():
            assert sha(Path(selected['model'])) == selected['model_sha256']
    for report in (base/'checks').glob('*/report.json'):
        result = read(report)
        assert result['passed'], str(report)
        contracts.append(str(report))

supp_models=[]
for report in (B/'supplement/models').glob('*/report.json'):
    doc=read(report);supp_models.append(dict(name=report.parent.name, epochs=len(doc['history']), selected_epoch=doc['selected_epoch']))
if (B/'supplement/candidates.json').exists():
    for candidate in read(B/'supplement/candidates.json'):
        assert sha(Path(candidate['model'])) == candidate['model_sha256']
residual_trials=[]
for study in ['residual','polish']:
    for path in (B/study/'train-trials').glob('*.json'):
        actor=read(path);assert sha(Path(actor['model']))==actor['model_sha256']
        residual_trials.append(dict(name=actor['name'],study=study,side=actor['side'],rank=actor['rank'],model_sha256=actor['model_sha256']))
if (B/'polish/calibration.npz').exists():
    assert sha(B/'polish/calibration.npz') == sha(B/'residual/calibration.npz')

disk = [read(p) for p in B.glob('disk-*.json')]; used, free = usage()
primary = read(B/'completion.json')
per_side_eligible = {}
for study, sides in tests.items():
    per_side_eligible[study] = {}
    for side, assessment in sides.items():
        candidate = selections[study]['best'][side]
        passed = bool(candidate['rank'][0] and all(a['passed'] for a in assessment.values()))
        if study in ['residual','polish']:
            gate = assessment['vs_r22']['outcome']
            passed = bool(passed and candidate['changed_validation_ids'] and
                (gate['candidate_wins']>gate['reference_wins'] or gate['candidate_timeouts']<gate['reference_timeouts'] or gate['capped_mean_duration_ratio']<.97))
        per_side_eligible[study][side] = passed
totals = {s:dict(regular_games=sum(r['games'] for r in evaluations if r['study']==s and not r['fixture']),
                 fixture_games=sum(r['games'] for r in evaluations if r['study']==s and r['fixture']))
          for s in states}
receipt = dict(audited_at=datetime.datetime.now(TZ).isoformat(), states=states, tests=tests, selections=selections,
    all_studies_completed=all(s['completed'] for s in states.values()),auditor_sha256=sha(Path(__file__)),
    per_side_eligible_before_dual_diagnostic=per_side_eligible,
    source_binary_and_data_hashes_verified=len(verified), formal_exe_sha256=read(B/'plan.json')['release_sha256'],
    formal_promoted=False, raw_archives_verified=len(archives), forward_checks_verified=len(contracts),
    totals_by_study=totals, evaluated_games=sum(r['games'] for r in evaluations if not r['fixture']),
    fixture_games=sum(r['games'] for r in evaluations if r['fixture']),
    all_completed_eval_games=sum(r['games'] for r in evaluations), evaluations=evaluations, unfinished_eval_groups=unfinished,
    completed_supervised_fits=primary['completed_training_runs']+len(supp_models),
    completed_supervised_epochs=primary['completed_epochs']+sum(r['epochs'] for r in supp_models),
    supplemental_models=supp_models, completed_outcome_search_trials=len(residual_trials), outcome_search_trials=residual_trials,
    completed_outcome_search_trials_by_study={s:sum(r['study']==s for r in residual_trials) for s in ['residual','polish']},
    new_bytes=used, sampled_peak_bytes=max([used,*[r['new_bytes_peak'] for r in disk]]), free_bytes=free,
    sampled_minimum_free_bytes=min([free,*[r['minimum_free_bytes'] for r in disk]]), cap_bytes=LIMIT,free_floor_bytes=FREE_FLOOR,
    note='Completed native evaluation groups only; structural fixtures separate. Interrupted starts and original failures preserved. Outcome-search trials are not supervised epochs. No formal release, default model, launcher or user save replaced.')
write(B/'all-completion.json',receipt)
used, free = usage()
receipt.update(new_bytes=used, sampled_peak_bytes=max(used,receipt['sampled_peak_bytes']),free_bytes=free,
               sampled_minimum_free_bytes=min(free,receipt['sampled_minimum_free_bytes']))
write(B/'all-completion.json',receipt)
print(json.dumps({k:receipt[k] for k in ['totals_by_study','evaluated_games','fixture_games','completed_supervised_fits','completed_supervised_epochs','completed_outcome_search_trials','new_bytes','sampled_peak_bytes','free_bytes']},ensure_ascii=False))
