"""Verify all retained files and compute per-opponent acceptance and paired changes."""
import gzip
import hashlib
import json
import datetime
from pathlib import Path
from collections import Counter
from coverage_study import OUT, inputs_ok, SIDES, OLD_MODEL, H
from coverage_guard import size, PREVIOUS, BUILD
from overnight_common import read, write, sha

def rates(root,ref,new,seat):
    a=read(root/ref/'summary.json')['matches'];b=read(root/new/'summary.json')['matches']
    result=Counter()
    for uid,left in a.items():
        right=b[uid]
        assert left['seed']==right['seed'] and left['night']==right['night'] and left['map']==right['map']
        wins=lambda m:int(not m['timeout'] and m['winner']==seat)
        result['gained_wins']+=wins(right)>wins(left)
        result['lost_wins']+=wins(right)<wins(left)
        result['new_timeouts']+=right['timeout'] and not left['timeout']
        result['resolved_timeouts']+=left['timeout'] and not right['timeout']
        result['different_battle_logs']+=right['log_sha256']!=left['log_sha256']
    return dict(result)
def main():
    inputs_ok()
    assert read(OUT/'phase.json')['stage']=='completed'
    frozen=read(OUT/'frozen.json')
    assert sha(OUT/'model/model.json')==frozen['model_sha256'] and frozen['validation_outcomes_unopened'] and frozen['test_outcomes_unopened']
    archives=0; game_counts={}; forwards=0
    for split in ['train','validation','test']:
        total=0
        for folder in (OUT/split).iterdir():
            receipt=read(folder/'ready.json');assert receipt['summary_sha256']==sha(folder/'summary.json')
            summary=read(folder/'summary.json');assert not summary['crashed'] and summary['control_hz']==15 and summary['limit_seconds']==600
            for uid,match in summary['matches'].items():
                assert not match['ai_error']
                raw=folder/'matches'/(uid+'.jsonl')
                if split=='train':
                    record=read(folder/'receipts'/(uid+'.json'));archive=folder/'archives'/(uid+'.jsonl.gz')
                    assert sha(raw)==record['compact_sha256'] and sha(archive)==record['archive_sha256']
                    assert sha(folder/'cache'/(uid+'.npz'))==record['cache_sha256']
                    with gzip.open(archive,'rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==record['raw_sha256']==match['file_sha256']
                    archives+=1
                else: assert sha(raw)==match['file_sha256']
                total+=1
        game_counts[split]=total
    for path in [OUT/'model',*(OUT/'controls').iterdir()]:
        assert read(path/'verify/report.json')['passed'];forwards+=1
    assert game_counts==dict(train=384,validation=288,test=192)
    table=[];eligible={}
    for side in SIDES:
        passed=True;gain={ref:0 for ref in 'ro'};saved={ref:0 for ref in 'ro'}
        for split in ['validation','test']:
            results=read(OUT/(split+'-results.json'))
            for opp in 'ro':
                arm=lambda policy: policy+opp if side=='plant' else opp+policy
                for ref in 'ro':
                    result=results[side+'-opp'+opp+'-ref'+ref];gate=result['outcome']
                    tally=rates(OUT/split,arm(ref),arm('n'),side)
                    failures=list(gate['failures'])
                    if gate['capped_mean_duration_ratio']>1 and 'longer_capped_mean_duration' not in failures:failures.append('time_exceeds_reference')
                    if result['activity_flags'] or result['other_side_activity_flags']:failures.append('common_window_activity')
                    assert (not failures)==result['passed']
                    passed &= result['passed']
                    if split=='test':
                        gain[ref]+=gate['candidate_wins']-gate['reference_wins'];saved[ref]+=gate['reference_timeouts']-gate['candidate_timeouts']
                    table.append(dict(split=split,side=side,opponent=opp,reference=ref,wins=gate['candidate_wins'],timeouts=gate['candidate_timeouts'],ref_wins=gate['reference_wins'],ref_timeouts=gate['reference_timeouts'],duration_ratio=gate['capped_mean_duration_ratio'],passed=result['passed'],failures=failures,**tally))
        eligible[side]=bool(passed and all(gain[r]>0 or saved[r]>0 for r in 'ro'))
    verified_source={p:sha(OUT/'source-snapshot'/p) for p in frozen['source_sha256']}
    assert verified_source==frozen['source_sha256']
    amended=read(OUT/'zero-control-amendment.json')
    assert all(sha(H/p)==digest for p,digest in amended['live_source_sha256'].items())
    assert sha(OUT/'zero-control/model.json')==amended['corrected_model_sha256']
    for seat in SIDES:
        corrected=read(OUT/'neutral-parity'/seat/'summary.json')['matches']
        prior=read(OUT/'validation'/('or' if seat=='plant' else 'ro')/'summary.json')['matches']
        assert all(prior[k]['log_sha256']==m['log_sha256'] for k,m in corrected.items())
    disk=read(OUT/'disk.json')
    write(OUT/'completion.json',dict(completed_at=datetime.datetime.now().astimezone().isoformat(),game_counts=game_counts,archives_verified=archives,forward_checks=forwards,formal_promoted=False,eligible=eligible,table=table,coverage=read(OUT/'coverage.json'),sampled_peak=disk['new_peak'],source_and_binary_verification=True))
if __name__=='__main__':
    main()
