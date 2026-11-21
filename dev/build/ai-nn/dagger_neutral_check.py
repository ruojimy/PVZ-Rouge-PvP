"""Current-game regression of a trainable neutral seed; no strength claim."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]
B=R/'test_results/ai-nn-dagger-20261117'
BIN=R/'build/ai-nn/windows-pvp744-20261117/Release'
read=lambda p:json.loads(p.read_text('utf-8'))
assert read(B/'run.json')['completed']
out=B/'aux/residual-neutral-match'
ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
if not args.verify_only:
    assert not out.exists()
    (out/'logs').mkdir(parents=True)
    with (B/'residual-native-contract.log').open('wb') as f:
        subprocess.run([str(BIN/'neural_contract.exe'),str(B/'residual-neutral/model.json')],check=True,stdout=f)
    subprocess.run([sys.executable,'-X','utf8',str(R/'build/ai-nn/eval.py'),
        '--bin',str(BIN/'headless_match.exe'),'--corpus',str(B/'corpus-plain'),'--out-dir',str(out),
        '--ids','000,010','--jobs','2','--limit-seconds','600','--planner','nn','--',
        '--model',str(B/'residual-neutral/model.json'),'--nn-seat','both','--log',str(out/'logs/{id}.jsonl')],check=True)
a=read(B/'development-r22/summary.json');b=read(out/'summary.json')
assert not b['crashed']
fields=['winner','timeout','tick','time','hp','ai_error','log_sha256','ai']
rows={};plans=0;goal11=0
for uid in b['ids']:
    assert all(a['matches'][uid][k]==b['matches'][uid][k] for k in fields)
    left=(B/'development-r22/matches'/f'{uid}.jsonl').read_bytes().splitlines()
    right=(out/'matches'/f'{uid}.jsonl').read_bytes().splitlines()
    assert len(left)==len(right)
    # The recorder intentionally labels its caller as r22 versus nn.
    for x,y in zip(left[1:],right[1:]):
        x,y=json.loads(x),json.loads(y)
        if x['type']=='plan':
            assert x.pop('planner')=='r22' and y.pop('planner')=='nn'
        assert x==y, 'Planning or result fields differ: '+uid
    assert (B/'development-r22/logs'/f'{uid}.jsonl').read_bytes()==(out/'logs'/f'{uid}.jsonl').read_bytes()
    rows[uid]=len(left)-1
    for line in left[1:]:
        r=json.loads(line)
        if r['type']=='plan':
            plans+=1
            goal11+=r['seat']=='plant' and r['plan']['econ_goal']==11
assert goal11>0
report=dict(passed=True,matches=2,ids=b['ids'],limit_seconds=600,compared_result_fields=fields,
    equal_planning_and_result_rows=rows,excluded_metadata=['header','plan.planner'],battle_logs_byte_equal=True,
    planning_states=plans,econ_goal_11_plans=goal11,
    initial_checker_failure='Raw record comparison included the expected r22/nn planner tag; original failure log retained. All remaining plan and result fields compared.',
    gradient_probe=read(B/'residual-neutral/initialization-contract.json'),
    scope='Two current-game regression openings including a real goal-11 trajectory. Neutral residual equals r22; no reward training or strength gain.')
(B/'residual-neutral-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False))
