"""Latest-game supervised learning with one on-policy teacher-query iteration."""
import hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
B=R/'test_results/ai-nn-dagger-20261117';BIN=H/'windows-pvp744-20261117/Release'
read=lambda p:json.loads(p.read_text('utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(B/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
state=dict(completed=False,steps=[])
def command(name,args):
    state['current_step']=name;write('run.json',state);print(json.dumps(dict(step=name,status='running')),flush=True)
    start=time.perf_counter()
    with (B/(name+'.log')).open('wb') as log:subprocess.run([str(a) for a in args],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=R)
    state['steps'].append(dict(step=name,wall_seconds=time.perf_counter()-start));write('run.json',state)
    print(json.dumps(dict(step=name,status='completed')),flush=True)
def evaluate(name,ids,model=None,seat=None):
    out=B/name;assert not out.exists();(out/'logs').mkdir(parents=True)
    args=[sys.executable,'-X','utf8',H/'eval.py','--bin',BIN/'headless_match.exe','--corpus',B/'corpus-plain',
          '--out-dir',out,'--ids',','.join(ids),'--jobs','4','--limit-seconds','600']
    if model:args+=['--planner','nn']
    args+=['--','--log',out/'logs/{id}.jsonl']
    if model:args+=['--model',model,'--nn-seat',seat]
    command(name,args);return read(out/'summary.json')
def encode(name,paths,stride=4,augment=0):
    command(name,[BIN/'neural_dataset.exe',B/(name+'.jsonl'),'-','--feature-version','2','--stride',str(stride),
                  '--augment',str(augment),'--seed','171117',*paths])
    return B/(name+'.jsonl')
def merge(target,sources):
    total=0
    with (B/target).open('w',encoding='utf-8',newline='\n') as out:
        out.write(json.dumps(header,ensure_ascii=False)+'\n')
        for path,prefix,weight in sources:
            with path.open(encoding='utf-8') as src:
                h=json.loads(next(src));assert all(h[k]==header[k] for k in header)
                for line in src:
                    row=json.loads(line);row['id']=prefix+row['id'];row['sample_weight']=.25 if row.get('aug') else weight
                    out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n');total+=1
    return total
def relabel(group,paths):
    folder=B/'relabelled'/group;folder.mkdir(parents=True);result=[];manifest={}
    for i,p in enumerate(paths):
        target=folder/f'{i:03d}.jsonl'
        subprocess.run([str(BIN/'teacher_trace.exe'),str(p),str(target)],check=True,stdout=subprocess.DEVNULL)
        # Namespace observed trajectories before encoding; retain source provenance.
        lines=target.read_text('utf-8').splitlines();h=json.loads(lines[0]);h['id']=group+'-'+f'{i:03d}'
        target.write_text(json.dumps(h,ensure_ascii=False)+'\n'+'\n'.join(lines[1:])+'\n','utf-8')
        manifest[str(p)]=dict(source_sha256=sha(p),relabelled=str(target),sha256=sha(target));result.append(target)
    write('relabel-'+group+'.json',manifest);return result

assert not (B/'run.json').exists()
plan=read(B/'plan.json')
assert all(sha(R/p)==h for p,h in plan['source_sha256'].items())
compiled=re.search(r'"([a-f0-9]{64})"',(BIN.parent/'ai_nn_build.h').read_text())[1]
fp=hashlib.sha256(''.join(f'{p}:{plan["source_sha256"][p]}\n' for p in sorted(plan['source_sha256'])).encode()).hexdigest()
assert fp==compiled
for dll in (R/'dist/PvZ-PvP-Native-20261117-pvp744-r3').glob('*.dll'):shutil.copy2(dll,BIN/dll.name)
frozen={str(p):sha(p) for p in [Path(__file__),H/'dagger_train.py',H/'dagger_setup.py',H/'tempo_gate.py',H/'verify_model.py',
        H/'src/neural_planner.h',H/'src/neural_dataset.cpp',H/'src/teacher_trace.cpp',H/'CMakeLists.txt',
        BIN/'headless_match.exe',BIN/'neural_dataset.exe',BIN/'neural_contract.exe',BIN/'teacher_trace.exe',B/'plan.json',B/'corpus-plain/index.json']}
state.update(frozen=frozen,sim_fingerprint=compiled,started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
write('acceptance-protocol.json',dict(frozen_before_fitting=True,activity_flags='Per matched common window: rich >=700 and >=30s since last successful deploy, '
      'candidate adds >30s rich idle; OR candidate deploy count <75% of r22 with at least10 r22 deploys and mean resources >150% of r22. '
      'Any flag blocks automatic research-default replacement; legal action availability still needs manual causal review.'))
ids={p:[r['id'] for r in plan['entries'] if r['part']==p] for p in ['train','validation','test']}
dev=evaluate('development-r22',ids['train']+ids['validation'])
fresh=encode('fresh-train',[B/'development-r22/matches'/f'{i}.jsonl' for i in ids['train']],4,1)
valid=encode('fresh-validation',[B/'development-r22/matches'/f'{i}.jsonl' for i in ids['validation']],4)
header=json.loads(valid.open(encoding='utf-8').readline())
assert header['feature_version']==2
merge('validation-data.jsonl',[(valid,'validation-',1.)])

# Current teacher labels for all historical states; these are supplements, not new-game trajectories.
hist=[]
for d in ['test_results/ai-nn-local-20261114/training-rollouts/matches',
          'test_results/ai-nn-strength-20261116/development-r22/matches',
          'test_results/ai-nn-strength-20261116/test-r22/matches']:
    hist.extend(sorted((R/d).glob('*.jsonl')))
history=encode('historical-teacher',relabel('history',hist),8,1)
oldstudent=[]
for p in sorted((R/'test_results/ai-nn-r4-tempo-20261116/teacher-relabelled').glob('compact-*.jsonl')):
    with p.open(encoding='utf-8') as f:oldstudent.append(Path(json.loads(next(f))['source_file']))
# Query the original student observations again, preserving their actual executed plans.
students=encode('historical-student',relabel('oldstudent',oldstudent),1)
rows=merge('train-0.jsonl',[(history,'historical-',.5),(students,'student-',2.),(fresh,'fresh-',1.)])
write('dataset-sources.json',dict(train_rows=rows,sources={str(p):sha(p) for p in [history,students,fresh,valid]},
    historical_state_warning='Re-labelled under current teacher, but generated by previous simulation versions. Fresh current-game data are separate.'))

warm=B/'warm';warm.mkdir();warm_manifest={}
sources={'old':R/'test_results/ai-nn-r4-tempo-20261116/models/old.json',
         'compact':R/'test_results/ai-nn-r4-tempo-20261116/models/compact.json'}
for name,path in sources.items():
    doc=read(path);assert doc['embedding']==8 and doc['hidden']==64
    weights=doc['unit']['weight'];old_behaviors=doc['behaviors']
    doc['unit']['weight']=[row[:16]+[row[16+old_behaviors.index(x)] if x in old_behaviors else 0. for x in header['behaviors']] for row in weights]
    for k in ['catalog_hash','rules_hash','behaviors','sim_fingerprint']:doc[k]=header[k]
    doc.pop('compatibility_registration',None)
    doc['transfer_initialization']=dict(source_sha256=sha(path),note='Transferred for current-game evaluation, not a source-equivalence claim. New behaviors have zero input columns.')
    target=warm/(name+'.json');target.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),'utf-8')
    warm_manifest[name]=dict(source=str(path),source_sha256=sha(path),current_path=str(target),current_sha256=sha(target))
    command('contract-warm-'+name,[BIN/'neural_contract.exe',target])
write('warm-starts.json',warm_manifest)
command('train-stage0',[sys.executable,'-X','utf8','-u',H/'dagger_train.py','--study',B,'--stage','0'])
model0=B/'training-0/selected/model.json'
command('contract-stage0',[BIN/'neural_contract.exe',model0])
verify_records=[B/'development-r22/matches'/f'{i}.jsonl' for i in [ids['train'][0],ids['train'][12],ids['validation'][-1]]]
command('forward-stage0',[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe',
        '--model',model0,'--checkpoint',model0.with_name('selected.pt'),'--out',B/'forward-stage0',*verify_records])
roll_ids=[ids['train'][2*i+(i//2)%2] for i in range(12)]
student_paths=[]
for seat in ['plant','zombie']:
    evaluate('student-'+seat,roll_ids,model0,seat)
    student_paths.extend(B/('student-'+seat)/'matches'/f'{i}.jsonl' for i in roll_ids)
currentstudent=encode('current-student',relabel('currentstudent',student_paths),2)
merge('train-1.jsonl',[(history,'historical-',.5),(students,'student-',2.),(fresh,'fresh-',1.),(currentstudent,'currentstudent-',2.)])
command('train-stage1',[sys.executable,'-X','utf8','-u',H/'dagger_train.py','--study',B,'--stage','1'])
model1=B/'training-1/selected/model.json'
command('contract-stage1',[BIN/'neural_contract.exe',model1])
command('forward-stage1',[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe',
        '--model',model1,'--checkpoint',model1.with_name('selected.pt'),'--out',B/'forward-stage1',*verify_records])
from tempo_gate import assess
from compare import compare
def subset(s,keys):return dict(s,ids=keys,matches={i:s['matches'][i] for i in keys},crashed=[i for i in s['crashed'] if i in keys])
validation={};vb=subset(dev,ids['validation'])
for seat in ['plant','zombie']:
    old=evaluate('validation-old-'+seat,ids['validation'],warm/'old.json',seat)
    new=evaluate('validation-new-'+seat,ids['validation'],model1,seat)
    validation[seat]=dict(vs_r22=assess(vb,new,seat),vs_old=assess(old,new,seat),strength=compare(vb,new,seat))
write('selection.json',dict(final_candidate_sha256=sha(model1),validation=validation,
    eligible_on_validation=all(v['vs_r22']['passed'] and v['vs_old']['passed'] for v in validation.values()),
    test_not_opened=True,rule='No model changes after this file; test the sole final candidate for research even when it fails validation.'))
selection_sha=sha(B/'selection.json')
tb=evaluate('test-r22',ids['test']);tests={}
for seat in ['plant','zombie']:
    old=evaluate('test-old-'+seat,ids['test'],warm/'old.json',seat)
    new=evaluate('test-new-'+seat,ids['test'],model1,seat)
    tests[seat]=dict(vs_r22=assess(tb,new,seat),vs_old=assess(old,new,seat),strength=compare(tb,new,seat),vs_old_strength=compare(old,new,seat))
write('strength.json',dict(validation=validation,test=tests,selection_sha256=selection_sha,
                         gate_passed=all(v[k]['passed'] for s in [validation,tests] for v in s.values() for k in ['vs_r22','vs_old'])))
assert sha(B/'selection.json')==selection_sha
assert all(sha(Path(p))==h for p,h in frozen.items())
assert all(sha(R/p)==h for p,h in plan['source_sha256'].items())
assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==plan['release_sha256']
state.update(completed=True,current_step='complete',source_binary_data_hashes_verified=True)
write('run.json',state);print(json.dumps(dict(completed=True)),flush=True)
