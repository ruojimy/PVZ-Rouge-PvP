"""Close the fixed-build study, checking every game and the concurrent timing-only edit.

This does NOT update model fingerprints or authorize loading them into new builds.
The normal audit_study.py intentionally continues to reject source drift.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
read = lambda p: json.loads(p.read_text('utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ap = argparse.ArgumentParser()
ap.add_argument('--study', type=Path, required=True)
args = ap.parse_args()
base = args.study.resolve()
assert not (base/'completion.json').exists()
run = read(base/'run.json')
assert run['completed'] and run['final_hashes_verified']
assert all(sha(Path(p)) == h for p,h in run['frozen'].items())
assert (base/'final-analysis.json').exists()
before = read(base/'source-corpus-audit-before.json')
current = {p:sha(ROOT/p) for p in before['source_sha256']}
changed = [p for p in current if current[p] != before['source_sha256'][p]]
timing_file = 'build/typed72-integrated-v44/source/src/sim/typed/native_tick.cpp'
assert changed == [timing_file], changed
data = (ROOT/timing_file).read_bytes()
pattern = rb'\s*(?:function_profile::Phases (?:setup_profile|effects_profile);|(?:setup_profile|effects_profile)\.mark\("NativeTick::(?:setup|effects)::[a-z_]+"\);)\s*'
kept = [line for line in data.splitlines(keepends=True) if not re.fullmatch(pattern, line)]
normalized = b''.join(kept)
assert hashlib.sha256(normalized).hexdigest() == before['source_sha256'][timing_file]
frozen = base/'frozen-source'
frozen.mkdir()
(frozen/'native_tick.cpp').write_bytes(normalized)
fingerprint = hashlib.sha256(''.join(f'{p}:{current[p]}\n' for p in sorted(current)).encode()).hexdigest()
compiled = re.search(r'"([a-f0-9]{64})"', (ROOT/'build/ai-nn/windows-20261116/ai_nn_build.h').read_text())[1]
assert compiled == before['sim_fingerprint']

index = read(base/'corpus-plain/index.json')
for entry in index['entries']:
    for key in ('cold','draw'):
        assert sha(base/'corpus-plain'/entry[key]) == entry[key+'_sha256']
for key in ('atlas','recipes'):
    assert sha(base/'corpus-plain'/index[key]) == index[key+'_sha256']
release_paths = [ROOT/'PVZ_rougePvP_native/PvZPvPNative.exe',
                 ROOT/'dist/PvZ-PvP-Native-20261116-pvp743-r3/PvZPvPNative.exe']
assert all(sha(p) == before['game_release_sha256'] for p in release_paths)
selection = read(base/'selection.json')
assert sha(base/'selection.json') == read(base/'strength.json')['selection_sha256']
assert all(sha(Path(m['path'])) == m['sha256'] for m in selection['models'].values())
challenger = read(base/'challenger-selection.json')
assert challenger['selection_sha256'] == sha(base/'selection.json')
assert challenger['protocol_sha256'] == sha(base/'challenger-protocol.json')
assert read(base/'challenger-protocol.json')['script_sha256'] == sha(ROOT/'build/ai-nn/study_challenger.py')
plan = read(base/'plan.json')
parts = {p:{r['id'] for r in plan['entries'] if r['part']==p} for p in ('train','validation','test')}
rows = {r['id']:r for r in plan['entries']}
summaries = {}
for path in sorted(base.glob('*/summary.json')):
    name = path.parent.name
    summary = read(path)
    expected = parts['train']|parts['validation'] if name=='development-r22' else parts['test'] if name.startswith('test-') else parts['validation']
    assert set(summary['ids']) == expected
    assert not summary['crashed'] and not summary['overall']['ai_errors']
    if name in ('development-r22','test-r22'):
        model_hash = None
        planners = {'plant':'r22','zombie':'r22'}
    elif name=='identity-validation':
        model_hash = sha(base/'identity.json')
        planners = {'plant':'nn','zombie':'nn'}
    else:
        seat = name.rsplit('-',1)[1]
        if name.startswith('validation-'):
            model = name[len('validation-'):-(len(seat)+1)]
        elif name.startswith('test-original-'):
            model = 'original'
        elif name.startswith('test-selected-'):
            model = selection['selected'][seat]['name']
        else:
            assert name.startswith('test-challenger-')
            model = challenger['chosen'][seat]['name']
        model_hash = selection['models'][model]['sha256']
        planners = {s:'nn' if s==seat else 'r22' for s in ('plant','zombie')}
    for uid in expected:
        with (path.parent/'matches'/f'{uid}.jsonl').open(encoding='utf-8') as f:
            header = json.loads(next(f))
            result = json.loads(list(f)[-1])
        assert header['control_hz']==15 and header['plan_every']==1.5 and header['limit_seconds']==600
        assert header['planners']==planners
        assert header.get('model_sha256')==model_hash
        assert all(header[k]==rows[uid][k] for k in ('id','map','night','seed'))
        assert (result['result'] or {}).get('winner')==summary['matches'][uid]['winner']
        assert all(result[k]==summary['matches'][uid][k] for k in ('timeout','tick','time','hp','ai_error','log_sha256','ai'))
    summaries[name] = summary['overall']
assert len(summaries)==15 and sum(s['matches'] for s in summaries.values())==408
assert read(base/'identity-comparison.json')['passed']
assert read(base/'trainable-residual-seed/match-equivalence.json') == dict(plans=406,count_equal=True,plans_equal=True,full_result_equal=True)
assert all(v['record_bytes_identical'] for v in read(base/'profile/assessment.json')['matches'].values())
audit = dict(frozen_experiment_valid=True,current_source_byte_identical=False,
    strict_source_audit_passed=False,sim_fingerprint=compiled,current_source_fingerprint=fingerprint,
    source_changes=changed,changed_file_only_adds_timing=True,
    removed_timer_lines=len(data.splitlines())-len(kept),current_source_sha256=current,
    corpus_sha256_verified=True,release_sha256=before['game_release_sha256'],release_unchanged=True,
    warning='Fresh builds will have a different fingerprint. Do not relabel these models or rebuild the frozen experiment directory.')
(base/'source-corpus-audit-after.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf-8')
receipt = dict(completed=True,completed_at=datetime.now().astimezone().isoformat(),
    formal_release='PvP74.3 r3',simulation_fingerprint=compiled,
    matched_study_games=408,diagnostic_profile_games=2,diagnostic_residual_seed_games=1,
    completed_games_total=411,ai_errors=0,crashes=0,
    timeouts=sum(s['timeouts'] for s in summaries.values()),timeouts_scope='408 main/challenger games',
    interrupted_attempts_excluded=True,interrupted_evidence='concurrency-amendment',
    all_headers_results_and_model_hashes_verified=True,summaries=summaries,
    source_audit=audit,production_ai_changed=False,research_default_changed=False,
    training_kind='supervised r22 imitation; fixed residual diagnostic; trainable neutral residual seed, no reward training')
(base/'completion.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('summaries','source_audit')},ensure_ascii=False))
