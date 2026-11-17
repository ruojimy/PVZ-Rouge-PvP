"""Auditable sequential research pipeline. New outputs only, two workers maximum.

Run after study_setup and materialize_corpus. Test matches are only started after
selection.json is written. Candidate failures stay in the denominator and stop
promotion, rather than silently dropping games.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from compare import compare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text('utf-8'))


def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--study', type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--resume-development', action='store_true',
                    help='Audited resume before training, after a user-requested worker-count change')
    args = ap.parse_args()
    base = args.study.resolve()
    plan = read(base / 'plan.json')
    bin_dir = HERE / 'windows-20261116/Release'
    binary, encoder = bin_dir / 'headless_match.exe', bin_dir / 'neural_dataset.exe'
    corpus = base / 'corpus-plain'
    started = time.perf_counter()
    receipt = base / 'run.json'
    if receipt.exists() and not args.resume_development:
        raise SystemExit('Use a new run; implicit cache reuse is not allowed')
    paths = [binary, encoder, bin_dir / 'neural_contract.exe', base / 'plan.json',
             corpus / 'index.json', Path(plan['original_model'])]
    paths += list(HERE.glob('study_*.py')) + [HERE / 'train.py', HERE / 'eval.py', HERE / 'src/neural_planner.h']
    frozen = {str(p): sha(p) for p in paths}
    if args.resume_development:
        state = read(receipt)
        assert state['current_step']=='development-r22' and not (base / 'training').exists()
        previous = state['frozen']
        driver = str(HERE / 'study_run.py')
        assert sha(base / 'concurrency-amendment/study_run_original.py') == previous[driver]
        assert all(sha(p)==digest for p,digest in previous.items() if p!=driver)
        amendment = dict(reason='User requested moderate concurrent games', old_jobs=2, new_jobs=args.jobs,
                         old_driver_sha256=previous[driver], new_driver_sha256=sha(Path(driver)),
                         game_binary_changed=False, simulation_settings_changed=False,
                         amended_before_training_and_model_selection=True)
        write(base / 'concurrency-amendment/protocol.json', amendment)
        state.update(frozen=frozen, concurrency_amendment=amendment)
    else:
        state = dict(started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), frozen=frozen, steps=[], completed=False)
    state['effective_jobs'] = args.jobs
    write(receipt, state)

    def command(name, cmd):
        if args.resume_development and any(r['step']==name and r['returncode']==0 for r in state['steps']):
            print(json.dumps(dict(step=name, status='reused_verified_complete')), flush=True)
            return
        print(json.dumps(dict(step=name, status='running'), ensure_ascii=False), flush=True)
        state['current_step'] = name
        write(receipt, state)
        before = time.perf_counter()
        with (base / (name + '.log')).open('wb') as log:
            process = subprocess.run([str(x) for x in cmd], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        result = dict(step=name, returncode=process.returncode, wall_seconds=time.perf_counter()-before)
        state['steps'].append(result)
        write(receipt, state)
        if process.returncode:
            raise RuntimeError(f'{name} failed; inspect its preserved log')
        print(json.dumps(result, ensure_ascii=False), flush=True)

    def evaluate(name, ids, model=None, seat=None):
        cmd = [sys.executable, '-X', 'utf8', HERE / 'eval.py', '--bin', binary, '--corpus', corpus,
               '--out-dir', base / name, '--ids', ','.join(ids), '--jobs', str(args.jobs), '--limit-seconds', '600']
        if args.resume_development and name=='development-r22':
            cmd += ['--resume']
        if model:
            cmd += ['--planner', 'nn', '--', '--model', model, '--nn-seat', seat, '--no-records']
        command(name, cmd)
        return read(base / name / 'summary.json')

    def subset(summary, ids):
        return dict(summary, ids=ids, matches={i: summary['matches'][i] for i in ids},
                    crashed=[i for i in summary['crashed'] if i in ids])

    ids = {p: [r['id'] for r in plan['entries'] if r['part'] == p] for p in ('train', 'validation', 'test')}
    development = ids['train'] + ids['validation']
    (base / 'development-ids.txt').write_text('\n'.join(development)+'\n', 'utf-8')
    write(base / 'training-design.json', dict(
        frozen_before_candidate_fitting=True, optimizer='AdamW', weight_decay=0.0001,
        warm_start=dict(architecture='compact', seeds=plan['training_seeds'], learning_rate=0.0003,
                        source_sha256=plan['original_model_sha256'], method='Exact float32 weights imported from validated JSON'),
        augmentation_weight=0.25, disabled_head='zombie_save',
        outcome_candidates=['original', 'compact', 'wide', 'residual-minus1'],
        residual_note='Predeclared constant -1 correction, not a learned reinforcement policy; zero correction separately checked.',
        note='Do not train a one-class save override; no test outcomes or test labels used for selection.'))
    command('contract', [bin_dir / 'neural_contract.exe', plan['original_model']])
    baseline = evaluate('development-r22', development)
    command('identity-model', [sys.executable, '-X', 'utf8', HERE / 'identity_model.py',
                              '--like', plan['original_model'], '--out', base / 'identity.json'])
    neutral = evaluate('identity-validation', ids['validation'], base / 'identity.json', 'both')
    identity_equal = all(all(baseline['matches'][i][k] == neutral['matches'][i][k]
        for k in ('winner', 'timeout', 'tick', 'time', 'hp', 'ai_error', 'log_sha256', 'ai')) for i in ids['validation'])
    write(base / 'identity-comparison.json', dict(passed=identity_equal, matches=len(ids['validation']),
        limit_seconds=600, fields=['winner', 'timeout', 'tick', 'time', 'hp', 'ai_error', 'log_sha256', 'ai']))
    assert identity_equal, 'Zero residual does not reproduce baseline'
    residual = read(base / 'identity.json')
    residual['heads']['bias'][5] = residual['heads']['bias'][18] = 0.0
    residual['heads']['bias'][4] = residual['heads']['bias'][17] = 1.0
    residual['enabled_heads'] = [True, False, True, False]
    residual['heads_note'] = 'Predeclared constant -1 economy/grave correction; not reward-trained'
    write(base / 'residual-minus1.json', residual)
    command('encode-development', [sys.executable, '-X', 'utf8', HERE / 'prepare_training.py',
        '--records', base / 'development-r22/matches', '--ids', base / 'development-ids.txt',
        '--encoder', encoder, '--out', base / 'fresh-dataset.jsonl', '--stride', '4', '--augment', '1', '--seed', '161116'])
    old = ROOT / 'test_results/ai-nn-followup-20261115/dataset.jsonl'
    sources = [old, base / 'fresh-dataset.jsonl']
    header = None
    counts = {}
    with (base / 'dataset.jsonl').open('w', encoding='utf-8', newline='\n') as output:
        for path in sources:
            count = 0
            with path.open(encoding='utf-8') as source:
                got = json.loads(next(source))
                if header is None:
                    header = got
                    output.write(json.dumps(header, ensure_ascii=False, separators=(',', ':'))+'\n')
                else:
                    for key in ('sim_fingerprint', 'behaviors', 'catalog_hash', 'rules_hash'):
                        assert got[key] == header[key], key
                for line in source:
                    row = json.loads(line)
                    if path == old:
                        row['id'] = 'old-' + row['id']
                    output.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n')
                    count += 1
            counts[str(path)] = dict(samples=count, sha256=sha(path))
    write(base / 'dataset.provenance.json', dict(sources=counts, dataset_sha256=sha(base / 'dataset.jsonl'),
        old_data_policy='Previously observed old data are all train; fresh validation/test IDs are disjoint seed groups.'))
    command('training', [sys.executable, '-X', 'utf8', HERE / 'study_train.py', '--study', base, '--threads', '2'])
    training = read(base / 'training/report.json')
    candidates = {'original': Path(plan['original_model']),
                  **{name: base / 'training' / name / 'model.json' for name in training['selected']},
                  'residual-minus1': base / 'residual-minus1.json'}
    sample_ids = [ids['train'][0], ids['train'][len(ids['train'])//2], ids['validation'][-1]]
    for name in training['selected']:
        command('forward-' + name, [sys.executable, '-X', 'utf8', HERE / 'verify_model.py',
            '--encoder', encoder, '--model', candidates[name], '--checkpoint', base / 'training' / name / 'selected.pt',
            '--out', base / ('forward-' + name),
            *[base / 'development-r22/matches' / (key+'.jsonl') for key in sample_ids]])
    validation = {}
    for name, model in candidates.items():
        validation[name] = {}
        for seat in ('plant', 'zombie'):
            got = evaluate('validation-' + name + '-' + seat, ids['validation'], model, seat)
            validation[name][seat] = compare(baseline, got, seat)
    selections = {}
    complexity = {'r22': 0, 'original': 1, 'compact': 2, 'residual-minus1': 3, 'wide': 4}
    for seat in ('plant', 'zombie'):
        base_wins = sum(baseline['matches'][i]['winner']==seat and not baseline['matches'][i]['timeout']
                        for i in ids['validation'])
        options = [('r22', base_wins, 0)] + [(name, rows[seat]['candidate_wins'], rows[seat]['losses'])
                    for name, rows in validation.items() if not rows[seat]['crashed'] and not rows[seat]['ai_errors']]
        best = max(options, key=lambda v: (v[1], -v[2], -complexity[v[0]]))
        selections[seat] = dict(name=best[0], model=str(candidates[best[0]]) if best[0]!='r22' else None)
    selection = dict(validation=validation, selected=selections,
                     models={k: dict(path=str(p), sha256=sha(p)) for k,p in candidates.items()},
                     frozen_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), test_started=False)
    write(base / 'selection.json', selection)
    selection_sha = sha(base / 'selection.json')
    # This is the first point at which final held-out games are run.
    test_base = evaluate('test-r22', ids['test'])
    comparisons = {}
    for seat in ('plant', 'zombie'):
        got = evaluate('test-original-' + seat, ids['test'], candidates['original'], seat)
        comparisons['original-'+seat] = compare(test_base, got, seat)
        selected = selections[seat]
        if selected['name'] == 'r22':
            selected_summary = test_base
        elif selected['name'] == 'original':
            selected_summary = got
        else:
            selected_summary = evaluate('test-selected-' + seat, ids['test'], selected['model'], seat)
        comparisons['selected-'+seat] = compare(test_base, selected_summary, seat)
        comparisons['selected-vs-original-'+seat] = compare(got, selected_summary, seat)
    assert sha(base / 'selection.json') == selection_sha
    assert all(sha(p)==digest for p,digest in frozen.items()), 'Study source/binary/data drift'
    write(base / 'strength.json', dict(comparisons=comparisons, selected=selections,
        selection_sha256=selection_sha, limitation='24 paired test openings share maps and some seed groups; '
        'exact McNemar p-values are descriptive and do not remove map/seed clustering or multiple endpoints. '
        'No automatic production promotion.'))
    state.update(completed=True, wall_seconds=time.perf_counter()-started,
                 final_hashes_verified=True, current_step='complete')
    write(receipt, state)
    print(json.dumps(dict(completed=True, wall_seconds=state['wall_seconds'])), flush=True)


if __name__ == '__main__':
    main()
