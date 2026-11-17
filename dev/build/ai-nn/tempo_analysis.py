"""Common-window deployment, resources, mode and teacher divergence diagnostics."""
import bisect
import collections
import json
import subprocess
from pathlib import Path
from tempo_gate import assess

ROOT=Path(__file__).resolve().parents[2]
B=ROOT/'test_results/ai-nn-r4-tempo-20261116'
OLD=ROOT/'test_results/ai-nn-strength-20261116'
BIN=Path(__file__).resolve().parent/'windows-r4-20261116/Release'
read=lambda p:json.loads(p.read_text('utf-8'))
assert read(B/'run.json')['completed']
assert not (B/'analysis.json').exists()

def records(path):
    with path.open(encoding='utf-8') as f:return [json.loads(line) for line in f]

def measure(arm,uid,seat,until):
    rows=records(B/arm/'matches'/f'{uid}.jsonl')
    events=records(B/arm/'logs'/f'{uid}.jsonl')
    plans=[r for r in rows if r['type']=='plan' and r['seat']==seat and r['input']['time']<until]
    deploy=[r for r in events if r['event']=='deploy' and r['side']==seat and r['time']<=until]
    times=[r['time'] for r in deploy]
    moves=[r for r in events if r['event']=='input' and r['side']==seat and r['kind']=='move' and r['time']<=until]
    resource=siege=rich_idle=0.;flips=0
    for i,r in enumerate(plans):
        now=r['input']['time'];end=min(until,plans[i+1]['input']['time'] if i+1<len(plans) else until)
        dt=end-now
        resource+=r['input']['me']['resource']*dt
        if r['plan'].get('mode')=='siege':siege+=dt
        if i and r['plan'].get('mode')!=plans[i-1]['plan'].get('mode'):flips+=1
        last=bisect.bisect_right(times,now)-1
        # Conservative sample-based flag, not a claim that a legal purchase existed.
        if now-(times[last] if last>=0 else 0)>=30 and r['input']['me']['resource']>=700 and not r['input']['recovering'] and r['input']['me']['hp']>0:
            rich_idle+=dt
    boundaries=[0.,*times,until]
    return dict(window_game_seconds=until,successful_deploys=len(deploy),deploys_per_minute=len(deploy)*60/until,
        spent_on_deploys=sum(r['charge'] for r in deploy),mean_resource_sampled=resource/until,
        siege_fraction_sampled=siege/until,mode_switches=flips,
        longest_no_deploy_seconds=max(y-x for x,y in zip(boundaries,boundaries[1:])),
        rich_30s_no_deploy_seconds_sampled=rich_idle,
        movement_commands=len(moves),nonzero_movement_command_fraction=sum(r['move']!=0 for r in moves)/max(1,len(moves)),
        deploy_cards=dict(collections.Counter(r['card'] for r in deploy)))

summary={name:read(B/name/'summary.json') for name in ('r22','old-plant','compact-plant','econ-only-plant','mode-only-plant','compact-zombie')}
outcomes={arm:{i:{k:v[k] for k in ('winner','timeout','time','hp')} for i,v in s['matches'].items()} for arm,s in summary.items()}
metrics={}
for arm,s in summary.items():
    if arm=='r22':continue
    seat=arm.rsplit('-',1)[1];metrics[arm]={}
    for uid,v in s['matches'].items():
        limit=min(summary['r22']['matches'][uid]['time'],v['time'])
        metrics[arm][uid]=dict(candidate=measure(arm,uid,seat,limit),reference=measure('r22',uid,seat,limit),
            opponent_candidate=measure(arm,uid,'zombie' if seat=='plant' else 'plant',limit),
            opponent_reference=measure('r22',uid,'zombie' if seat=='plant' else 'plant',limit))

rel=B/'teacher-relabelled';rel.mkdir(exist_ok=True)
teacher={}
for arm in ('r22','compact-plant','econ-only-plant','mode-only-plant','compact-zombie'):
    teacher[arm]={}
    subset=['015'] if arm=='r22' else summary[arm]['ids']
    for uid in subset:
        target=rel/(arm+'-'+uid+'.jsonl')
        if not target.exists():
            subprocess.run([str(BIN/'teacher_trace.exe'),str(B/arm/'matches'/f'{uid}.jsonl'),str(target)],check=True,stdout=subprocess.DEVNULL)
        stat=collections.Counter();examples=[]
        for row in records(target):
            if row['type']!='plan':continue
            p,t=row['executed_plan'],row['plan']
            if arm=='r22':
                assert p==t
                stat['teacher_plans_verified']+=1
                continue
            seat=arm.rsplit('-',1)[1]
            if row['seat']!=seat:continue
            stat['plans']+=1
            heads=['econ_goal','mode'] if seat=='plant' else ['grave_start']
            for h in heads:
                if p[h]!=t[h]:
                    stat[h+'_mismatch']+=1
                    if len(examples)<8:examples.append(dict(time=row['input']['time'],head=h,executed=p[h],teacher=t[h],resource=row['input']['me']['resource']))
            if seat=='plant' and p['mode']=='defend' and t['mode']=='siege':stat['missed_siege']+=1
            if seat=='plant' and p['mode']=='siege' and t['mode']=='defend':stat['early_siege']+=1
        teacher[arm][uid]=dict(counts=dict(stat),examples=examples)

gates={}
for seat,folder in [('plant','test-selected-plant'),('zombie','test-challenger-zombie')]:
    for reference in ['test-r22','test-original-'+seat]:
        gates[seat+'-vs-'+reference]=assess(read(OLD/reference/'summary.json'),read(OLD/folder/'summary.json'),seat)
assert assess(read(OLD/'test-r22/summary.json'),read(OLD/'test-r22/summary.json'),'plant')['passed']
assert all(not r['passed'] for r in gates.values())
report=dict(outcomes=outcomes,common_window_metrics=metrics,teacher_counterfactual=teacher,promotion_gates=gates,
    limitations=['Retrospective targeted scenarios; no independent strength claim.',
        'Successful deploy events exclude unsuccessful clicks and movement spam.',
        'Resource/mode/idle times are sampled at replans, roughly every 1.5 seconds.',
        'Rich and idle is a diagnostic flag, not proof of an available legal purchase.',
        'Counterfactual r22 recommendations use student-visited input and memory, not a different r22 trajectory.',
        'Ablations show head contributions on these fixed openings; not universal causal conclusions.'])
(B/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(dict(outcomes=outcomes,gates={k:v['failures'] for k,v in gates.items()}),ensure_ascii=False))
