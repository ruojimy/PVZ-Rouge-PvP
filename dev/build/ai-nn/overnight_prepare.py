"""Build contracts, source compatibility, compact telemetry, and compressed data."""
import sys
import torch
from overnight_common import *
from overnight_eval import evaluate,footer,archive_full
from overnight_train import initialize,export
assert not (B/'prepared.json').exists();plan=read(B/'plan.json')
assert all(sha(R/p)==h for p,h in plan['source_sha256'].items())
oldmodel=OLD/'training-1/selected/model.json';doc=read(oldmodel)
header={k:doc[k] for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint']};header.update(feature_version=2,policy_version=2)
assert header['sim_fingerprint'] in (BIN.parent/'ai_nn_build.h').read_text()
torch.set_num_threads(2)
for width,transition in [(0,False),(0,True),(32,False),(32,True)]:
    torch.manual_seed(181118);model=initialize(doc,width,transition);d=B/'fixtures'/f'{width}-{int(transition)}'
    export(model,header,d,transition,dict(initialization_only=True))
    command('contract-'+d.name,[BIN/'neural_contract.exe',d/'model.json'])
    command('forward-'+d.name,[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',d/'model.json',
        '--checkpoint',d/'selected.pt','--out',B/'checks'/d.name,OLD/'development-r22/matches/010.jsonl'])
legacy=OLD/'warm/old.json';command('legacy-contract',[BIN/'neural_contract.exe',legacy])
out,s=evaluate('telemetry-regression',['000'],corpus=OLD/'corpus-plain')
base=read(OLD/'development-r22/summary.json')['matches']['000'];actual=s['matches']['000']
fields=['winner','timeout','tick','time','hp','ai_error','log_sha256','ai'];assert all(base[k]==actual[k] for k in fields)
events=footer(out/'matches/000.jsonl')['activity']
with (OLD/'development-r22/matches/000.jsonl').open(encoding='utf-8') as f:rows=[json.loads(x) for x in f]
expected=[dict(kind='plan',time=r['input']['time'],side=r['seat'],resource=r['input']['me']['resource'],hp=r['input']['me']['hp'],recovering=r['input']['recovering'],mode=r['plan']['mode']) for r in rows if r['type']=='plan']
assert [r for r in events if r['kind']=='plan']==expected
with (OLD/'development-r22/logs/000.jsonl').open(encoding='utf-8') as f:logs=[json.loads(x) for x in f]
expected=[dict(kind='deploy',**{k:r[k] for k in ['time','side','charge','card']}) for r in logs if r['event']=='deploy']
assert [r for r in events if r['kind']=='deploy']==expected
write(B/'telemetry-contract.json',dict(passed=True,gameplay_fields=fields,plans=sum(r['kind']=='plan' for r in events),deploys=len(expected),
    match_bytes=(out/'matches/000.jsonl').stat().st_size,old_record_bytes=(OLD/'development-r22/matches/000.jsonl').stat().st_size))
ids=[r['id'] for r in plan['entries'] if r['part']=='validation']
val,s=evaluate('validation-r22',ids,full=True)
write(B/'validation-sources.json',[str(p) for p in sorted((val/'matches').glob('*.jsonl'))])
command('validation-cache',[sys.executable,'-X','utf8',H/'overnight_data.py','--sources',B/'validation-sources.json','--out',B/'data/validation.npz','--stride','2','--augment','0','--limit','20000'])
archive_full(val,'validation-r22')
sources=[]
for folder in ['development-r22','student-plant','student-zombie','validation-old-plant','validation-new-plant','validation-old-zombie','validation-new-zombie',
               'test-r22','test-old-plant','test-new-plant','test-old-zombie','test-new-zombie']:
    sources.extend(str(p) for p in sorted((OLD/folder/'matches').glob('*.jsonl')))
write(B/'training-sources.json',sources)
command('training-cache',[sys.executable,'-X','utf8',H/'overnight_data.py','--sources',B/'training-sources.json','--out',B/'data/train.npz','--stride','4','--augment','2','--limit','90000'])
for seat in ['plant','zombie']:evaluate('validation-old-'+seat,ids,legacy,seat)
files=[p for p in H.glob('overnight_*.py')]+[H/'src'/n for n in ['neural_planner.h','neural_dataset.cpp','neural_contract.cpp','headless_match.cpp']]
files+=[H/n for n in ['train.py','eval.py','tempo_gate.py','verify_model.py']]
write(B/'prepared.json',dict(completed=True,core_source_verified=True,initial_model_sha256=sha(oldmodel),old_baseline_sha256=sha(legacy),
    source_sha256={str(p):sha(p) for p in files},binary_sha256={str(p):sha(p) for p in BIN.glob('*.exe')}))
guard();print('Preparation completed')
