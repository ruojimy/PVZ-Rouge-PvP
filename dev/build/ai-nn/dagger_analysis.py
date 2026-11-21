"""Audit a completed frozen DAgger study; never select a model on test outcomes."""
import bisect
import collections
import hashlib
import json
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parents[2]
B = R / 'test_results/ai-nn-dagger-20261117'
BIN = R / 'build/ai-nn/windows-pvp744-20261117/Release'
read = lambda p: json.loads(p.read_text('utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def lines(path):
    with path.open(encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def measure(rows, events, seat, until):
    plans = [r for r in rows if r['type'] == 'plan' and r['seat'] == seat and r['input']['time'] < until]
    deploy = [r for r in events if r['event'] == 'deploy' and r['side'] == seat and r['time'] <= until]
    times = sorted(r['time'] for r in deploy)
    resource = siege = rich_idle = 0.
    for i, row in enumerate(plans):
        now = row['input']['time']
        end = min(until, plans[i+1]['input']['time'] if i+1 < len(plans) else until)
        dt = end - now
        assert dt >= 0
        resource += row['input']['me']['resource'] * dt
        siege += (row['plan'].get('mode') == 'siege') * dt
        last = bisect.bisect_right(times, now) - 1
        inp = row['input']
        if now - (times[last] if last >= 0 else 0) >= 30 and inp['me']['resource'] >= 700 and not inp['recovering'] and inp['me']['hp'] > 0:
            rich_idle += dt
    boundaries = [0., *times, until]
    return dict(window_game_seconds=until, successful_deploys=len(deploy),
                spent_on_deploys=sum(r['charge'] for r in deploy),
                mean_resource_sampled=resource/until, siege_fraction_sampled=siege/until,
                longest_no_deploy_seconds=max(y-x for x,y in zip(boundaries,boundaries[1:])),
                rich_idle_seconds_sampled=rich_idle,
                deploy_cards=dict(collections.Counter(r['card'] for r in deploy)))


def flags(a, b):
    result = []
    if b['rich_idle_seconds_sampled'] - a['rich_idle_seconds_sampled'] > 30:
        result.append('added_rich_idle_over_30_seconds')
    if a['successful_deploys'] >= 10 and b['successful_deploys'] < .75*a['successful_deploys'] and b['mean_resource_sampled'] > 1.5*a['mean_resource_sampled']:
        result.append('less_deployment_more_resources')
    return result


def main():
    state = read(B/'run.json')
    assert state['completed'] and state['source_binary_data_hashes_verified']
    assert not (B/'analysis.json').exists()
    assert all(sha(Path(p)) == h for p,h in state['frozen'].items())
    plan = read(B/'plan.json')
    selection = read(B/'selection.json')
    assert sha(B/'training-1/selected/model.json') == selection['final_candidate_sha256']
    assert all(sha(R/p) == h for p,h in plan['source_sha256'].items())
    summaries = {p.parent.name: read(p) for p in B.glob('*/summary.json')}
    assert set(summaries) == {'development-r22','student-plant','student-zombie','test-r22',
                            *[f'{part}-{kind}-{seat}' for part in ['validation','test'] for kind in ['old','new'] for seat in ['plant','zombie']]}
    games = sum(len(s['matches']) for s in summaries.values())
    assert games == 288
    assert all(not s['crashed'] and set(s['ids']) == set(s['matches']) and all(not m['ai_error'] for m in s['matches'].values()) for s in summaries.values())
    outcomes = {}
    for part in ['validation','test']:
        ids = [r['id'] for r in plan['entries'] if r['part'] == part]
        for arm in ['r22','old-plant','new-plant','old-zombie','new-zombie']:
            name = ('development-r22' if part == 'validation' else 'test-r22') if arm == 'r22' else part+'-'+arm
            rows = [summaries[name]['matches'][i] for i in ids]
            outcomes[part+'-'+arm] = dict(matches=len(rows), plant_wins=sum(r['winner']=='plant' and not r['timeout'] for r in rows),
                zombie_wins=sum(r['winner']=='zombie' and not r['timeout'] for r in rows),
                timeouts=sum(r['timeout'] for r in rows), capped_mean_seconds=sum(r['time'] for r in rows)/len(rows),
                timeout_ids=[i for i in ids if summaries[name]['matches'][i]['timeout']])
    goal_overflow = {}
    for part in ['validation','test']:
        baseline = 'development-r22' if part == 'validation' else 'test-r22'
        counts = {}
        for entry in plan['entries']:
            if entry['part'] != part:continue
            rows = lines(B/baseline/'matches'/f"{entry['id']}.jsonl")
            count = sum(r['type']=='plan' and r['seat']=='plant' and r['plan']['econ_goal']>10 for r in rows)
            if count:counts[entry['id']] = count
        goal_overflow[part] = counts
    comparisons = {}
    flagged = {}
    for part in ['validation','test']:
        ids = [r['id'] for r in plan['entries'] if r['part'] == part]
        baseline = 'development-r22' if part == 'validation' else 'test-r22'
        for seat in ['plant','zombie']:
            new = part+'-new-'+seat
            for reference in [baseline,part+'-old-'+seat]:
                key = new+'-vs-'+reference
                comparisons[key] = {}
                for uid in ids:
                    until = min(summaries[new]['matches'][uid]['time'],summaries[reference]['matches'][uid]['time'])
                    a = measure(lines(B/reference/'matches'/f'{uid}.jsonl'),lines(B/reference/'logs'/f'{uid}.jsonl'),seat,until)
                    b = measure(lines(B/new/'matches'/f'{uid}.jsonl'),lines(B/new/'logs'/f'{uid}.jsonl'),seat,until)
                    found = flags(a,b)
                    comparisons[key][uid] = dict(reference=a,candidate=b,flags=found)
                    if found: flagged[key+'/'+uid] = found

    # Test teacher features are encoded only after the frozen test games finish.
    ids = [r['id'] for r in plan['entries'] if r['part']=='test']
    subprocess.run([str(BIN/'neural_dataset.exe'),str(B/'test-features.jsonl'),'-','--feature-version','2','--stride','4',
                    *[str(B/'test-r22/matches'/f'{i}.jsonl') for i in ids]],check=True)
    import torch
    from dagger_train import Network, from_old, score
    from train import read_data
    torch.set_num_threads(2)
    header, rows = read_data(B/'test-features.jsonl')
    scores = {'warm-old':score(from_old(read(B/'warm/old.json'),header),rows),
              'warm-compact':score(from_old(read(B/'warm/compact.json'),header),rows)}
    for stage in [0,1]:
        model = Network(16+len(header['behaviors']))
        model.load_state_dict(torch.load(B/f'training-{stage}/selected/selected.pt',weights_only=True)['state_dict'])
        scores['stage-'+str(stage)] = score(model,rows)
    strength = read(B/'strength.json')
    report = dict(completed_games=games,crashes=0,ai_errors=0,outcomes=outcomes,
        final_model_sha256=selection['final_candidate_sha256'],heldout_teacher_scores=scores,
        teacher_econ_goal_over_10_plan_counts=goal_overflow,
        activity_flag_count=len(flagged),activity_flags=flagged,common_window=comparisons,
        outcome_gate_passed=strength['gate_passed'],
        eligible_for_dual_nn_diagnostic=strength['gate_passed'] and not flagged,
        limitations=['Test openings use new seeds on known maps; only 24 games per evaluated seat.',
            'Historical states were re-labelled by current r22, but retain their original simulation distribution.',
            'Resource and rich-idle measures are sampled at replans; flags do not prove a legal purchase was available.',
            'No test-driven checkpoint changes, online rewards, or self-play reinforcement learning in this study.',
            'Teacher accuracy includes only three active heads; action-goal representation still clips absolute goals to 10.'])
    (B/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['common_window','activity_flags']},ensure_ascii=False))


if __name__ == '__main__':main()
