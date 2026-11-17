"""Conservative promotion screen: winning, finishing, and time must pass together.

Passing is a screen, not statistical evidence of strength or a proof of active play.
Use the same openings/time cap and inspect productive-action traces separately.
"""
import argparse
import json
from pathlib import Path


def assess(reference, candidate, seat, max_mean_duration_ratio=1.05):
    if any(reference[k]!=candidate[k] for k in ('limit_seconds','control_hz')):
        raise ValueError('Tempo gate requires the same time cap and control rate')
    if max_mean_duration_ratio<1:
        raise ValueError('Duration allowance must be at least 1')
    if set(reference['ids']) != set(candidate['ids']):
        raise ValueError('Tempo gate requires identical opening IDs')
    ids=reference['ids'];a=reference['matches'];b=candidate['matches']
    if len(ids)!=len(set(ids)) or len(candidate['ids'])!=len(set(candidate['ids'])):
        raise ValueError('Duplicate opening IDs')
    if set(a)!=set(ids) or not set(b)<=set(ids):
        raise ValueError('Summary match records disagree with opening IDs')
    failures=[]
    if candidate['crashed']:failures.append('crashes')
    missing=[i for i in ids if i not in b]
    if missing:failures.append('missing_games')
    for i in ids:
        if i in b and any(a[i][k]!=b[i][k] for k in ('map','night','seed')):
            raise ValueError('Unpaired opening '+i)
    wins=lambda r:sum(v['winner']==seat and not v['timeout'] and not v['ai_error'] for v in r.values())
    aw,bw=wins(a),wins(b)
    at=sum(v['timeout'] for v in a.values());bt=sum(v['timeout'] for v in b.values())
    new_timeouts=[i for i in ids if i in b and b[i]['timeout'] and not a[i]['timeout']]
    errors=[i for i,v in b.items() if v['ai_error']]
    if errors:failures.append('ai_errors')
    if bw<aw:failures.append('fewer_wins')
    if bt>at:failures.append('more_timeouts')
    if new_timeouts:failures.append('new_timeout_openings')
    duration_ratio=sum(v['time'] for v in b.values())/sum(v['time'] for v in a.values()) if not missing else None
    if duration_ratio is None or duration_ratio>max_mean_duration_ratio:failures.append('longer_capped_mean_duration')
    return dict(passed=not failures,failures=failures,seat=seat,matches=len(ids),
        reference_wins=aw,candidate_wins=bw,reference_timeouts=at,candidate_timeouts=bt,
        new_timeout_ids=new_timeouts,capped_mean_duration_ratio=duration_ratio,
        max_mean_duration_ratio=max_mean_duration_ratio,
        productive_action_review_required=True,
        scope='Promotion screen only. No new timeouts or fewer wins; at most 5% capped mean time growth by default. '
              'A shorter loss is not a successful tempo improvement. Inspect common-window productive actions.')


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--reference',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--seat',choices=['plant','zombie'],required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-mean-duration-ratio',type=float,default=1.05)
    args=ap.parse_args()
    if args.out.exists():raise SystemExit('Use a new report path')
    result=assess(json.loads(args.reference.read_text('utf-8')),json.loads(args.candidate.read_text('utf-8')),
                  args.seat,args.max_mean_duration_ratio)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
