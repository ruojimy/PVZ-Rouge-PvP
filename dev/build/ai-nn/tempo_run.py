"""r4 compatibility checks and retrospective head ablations; no model fitting."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
B=ROOT/'test_results/ai-nn-r4-tempo-20261116'
OLD=ROOT/'test_results/ai-nn-strength-20261116'
BIN=HERE/'windows-r4-20261116/Release'
read=lambda p:json.loads(p.read_text('utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj): (B/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
def command(name,args):
    print(json.dumps(dict(step=name,status='running')),flush=True)
    with (B/(name+'.log')).open('wb') as log:
        subprocess.run([str(a) for a in args],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
    print(json.dumps(dict(step=name,status='completed')),flush=True)
def evaluate(name,ids,model=None,seat=None):
    folder=B/name
    assert not folder.exists()
    folder.mkdir();(folder/'logs').mkdir()
    cmd=[sys.executable,'-X','utf8',HERE/'eval.py','--bin',BIN/'headless_match.exe',
         '--corpus',OLD/'corpus-plain','--out-dir',folder,'--ids',','.join(ids),
         '--jobs','4','--limit-seconds','600']
    if model:cmd += ['--planner','nn']
    cmd += ['--','--log',folder/'logs/{id}.jsonl']
    if model:cmd += ['--model',model,'--nn-seat',seat]
    command(name,cmd)
    return read(folder/'summary.json')

assert not (B/'protocol.json').exists()
source=read(B/'source-before.json')
assert all(sha(ROOT/p)==h for p,h in source['source_sha256'].items())
dependencies={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src/sim/typed72_app').glob('*.h')}
write('additional-app-headers.json',dependencies)
shutil.copy2(HERE/'windows-20261116/Release/SDL2.dll',BIN/'SDL2.dll')
ids=(OLD/'test-ids.txt').read_text().split()
plant_ids=['015','047','071','083']
zombie_ids=['015','047','063']
protocol=dict(kind='retrospective diagnosis, NOT new heldout strength evidence',
    baseline_ids=ids,plant_added_timeouts=plant_ids,zombie_added_timeouts=zombie_ids,
    arms=['r22','old-plant','compact-plant','econ-only-plant','mode-only-plant','compact-zombie'],
    model_fitting=False,new_model_promotion=False,limit_game_seconds=600,concurrent_games=4,
    driver_sha256=sha(Path(__file__)),binary_sha256=sha(BIN/'headless_match.exe'))
write('protocol.json',protocol)
baseline=evaluate('r22',ids)
equiv={i:sha(B/'r22/matches'/f'{i}.jsonl')==sha(OLD/'test-r22/matches'/f'{i}.jsonl') for i in ids}
write('baseline-equivalence.json',dict(passed=all(equiv.values()),byte_identical=equiv))
assert all(equiv.values()),'r4 baseline differs; do not register old neural weights'

# Verify the full 19,824-row augmented development corpus using the new encoder/teacher.
records=[OLD/'development-r22/matches'/f'{i}.jsonl' for i in (OLD/'development-ids.txt').read_text().split()]
command('features',[BIN/'neural_dataset.exe',B/'features-r4.jsonl','-','--stride','4','--augment','1','--seed','161116',*records])
new_lines=(B/'features-r4.jsonl').read_bytes().splitlines();old_lines=(OLD/'fresh-dataset.jsonl').read_bytes().splitlines()
nh,oh=json.loads(new_lines[0]),json.loads(old_lines[0])
nf,of=nh.pop('sim_fingerprint'),oh.pop('sim_fingerprint')
assert nh==oh and new_lines[1:]==old_lines[1:]
write('feature-equivalence.json',dict(passed=True,samples=len(new_lines)-1,old_fingerprint=of,
    new_fingerprint=nf,old_sha256=sha(OLD/'fresh-dataset.jsonl'),new_sha256=sha(B/'features-r4.jsonl')))

models=B/'models';models.mkdir()
registered={}
for name,path in [('old',Path(read(OLD/'plan.json')['original_model'])),('compact',OLD/'training/compact/model.json')]:
    doc=read(path);assert doc['sim_fingerprint']==of
    doc['sim_fingerprint']=nf
    doc['compatibility_registration']=dict(source_sha256=sha(path),
        evidence=str(B/'feature-equivalence.json'),baseline_evidence=str(B/'baseline-equivalence.json'),
        weights_changed=False,scope='r4 fixed-build compatibility; not retraining')
    target=models/(name+'.json');target.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),'utf-8')
    assert all(doc[k]==read(path)[k] for k in ('unit','body','heads','embedding','hidden','enabled_heads'))
    registered[name]=dict(path=str(target),sha256=sha(target),source=str(path),source_sha256=sha(path))
    command('contract-'+name,[BIN/'neural_contract.exe',target])
for name,mask in [('econ-only',[True,False,False,False]),('mode-only',[False,True,False,False])]:
    doc=read(models/'compact.json');doc['enabled_heads']=mask
    doc['ablation']='Retrospective diagnostic; other heads controlled by r22'
    target=models/(name+'.json');target.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),'utf-8')
    registered[name]=dict(path=str(target),sha256=sha(target),head_mask=mask)
write('models.json',registered)
for name in ['old','compact','econ-only','mode-only']:
    evaluate(name+'-plant',plant_ids,models/(name+'.json'),'plant')
evaluate('compact-zombie',zombie_ids,models/'compact.json','zombie')
reproduced={}
for arm,oldarm,keys in [('old-plant','test-original-plant',plant_ids),('compact-plant','test-selected-plant',plant_ids),('compact-zombie','test-challenger-zombie',zombie_ids)]:
    got=read(B/arm/'summary.json')['matches'];prior=read(OLD/oldarm/'summary.json')['matches']
    reproduced[arm]={i:all(got[i][k]==prior[i][k] for k in ('winner','timeout','tick','time','hp','ai_error','log_sha256','ai')) for i in keys}
assert all(all(v.values()) for v in reproduced.values())
assert all(sha(ROOT/p)==h for p,h in source['source_sha256'].items())
assert all(sha(ROOT/p)==h for p,h in dependencies.items())
assert sha(BIN/'headless_match.exe')==protocol['binary_sha256']
assert sha(Path(__file__))==protocol['driver_sha256']
write('run.json',dict(completed=True,matches=43,baseline_equivalence=True,feature_rows_equivalent=len(new_lines)-1,
                     reproduced=reproduced,models=registered,source_unchanged=True))
print(json.dumps(dict(completed=True,matches=43)),flush=True)
