"""Supplemental study; one fit core, games serialized after the first study."""
import sys
from overnight_common import *
from overnight_eval import evaluate,screen
S=B/'supplement';S.mkdir(exist_ok=True)
state=dict(completed=False,phase='starting',trials=[],best={},test_opened=False)
def phase(name):
    state.update(phase=name,updated_at=datetime.datetime.now(TZ).isoformat());write(S/'state.json',state);print(name,flush=True)
def rank(a):
    pairs=list(a.values());bad=sum(len(p['outcome']['failures'])+len(p['activity_flags']) for p in pairs);g=pairs[0]['outcome']
    return (int(all(p['passed'] for p in pairs)),-bad,min(p['outcome']['candidate_wins']-p['outcome']['reference_wins'] for p in pairs),g['candidate_wins'],-g['candidate_timeouts'],-g['capped_mean_duration_ratio'])
def policy_hash(model):
    d=read(model);d.pop('training_source',None)
    return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def frozen():
    p=read(S/'plan.json');q=read(B/'prepared.json')
    expected={**p['source_sha256'],**p['data_sha256'],**q['source_sha256'],**q['binary_sha256']}
    assert all(sha(Path(k))==v for k,v in expected.items())
    assert all(sha(R/k)==v for k,v in read(B/'plan.json')['source_sha256'].items())
assert not (S/'plan.json').exists()
configs=[dict(name='shared-uniform',mode_hidden=0,summary_only=False),dict(name='mode-branch-uniform',mode_hidden=32,summary_only=False),dict(name='summary-uniform',mode_hidden=0,summary_only=True)]
write(S/'plan.json',dict(created_at=datetime.datetime.now(TZ).isoformat(),main_test_opened=read(B/'state.json')['test_opened'],
    configs=configs,epochs=60,checkpoints=[20,60,'minimum validation loss'],transition_weight=1.,
    source_sha256={str(p):sha(p) for p in [H/'night_supplement_run.py',H/'night_supplement_train.py']},
    data_sha256={str(p):sha(p) for p in [B/'data/train.npz',B/'data/collection-r1.npz',B/'data/validation.npz',OLD/'training-1/selected/model.json']},
    protocol='Fresh fixed grid based on validation false-switch audit, not on main sealed test. Reuse validation only; separate unseen test seed group 193000. No neural self-play. Deduplicate identical parameters before battles.',
    storage='Shared original 4 GiB/100 GiB guards; one extra logical fit core; game evaluation only after main study completes.',
    game_start_cutoff=DEADLINE-100*60,deadline=DEADLINE))
try:
    assert not read(S/'plan.json')['main_test_opened'];frozen()
    for c in configs:
        phase('fit-'+c['name']);args=[sys.executable,'-X','utf8',H/'night_supplement_train.py','--name',c['name'],'--mode-hidden',c['mode_hidden']]
        if c['summary_only']:args+=['--summary-only']
        command('supp-fit-'+c['name'],args,stop=FIT_END)
    phase('waiting-for-main-study')
    while not read(B/'state.json')['completed']:
        guard()
        if read(B/'state.json')['phase']=='stopped':raise RuntimeError('MAIN_STUDY_STOPPED')
        time.sleep(5)
    if time.time()>DEADLINE-100*60:raise RuntimeError('INSUFFICIENT_TIME_FOR_COMPLETE_SUPPLEMENT')
    # The main study's four game workers have ended. This study may now use four cores.
    psutil.Process().cpu_affinity([0,1,2,3]);frozen()
    val_ids=[r['id'] for r in read(B/'plan.json')['entries'] if r['part']=='validation'];seen={};candidates=[]
    for c in configs:
        for checkpoint in ['epoch-20','selected','epoch-60']:
            model=S/'models'/c['name']/checkpoint/'model.json';digest=policy_hash(model);name=c['name']+'-'+checkpoint
            if digest in seen:
                state.setdefault('duplicates',[]).append(dict(name=name,same_parameters_as=seen[digest]));continue
            seen[digest]=name;candidates.append((name,model))
    write(S/'candidates.json',[dict(name=n,model=str(p),model_sha256=sha(p),policy_digest=policy_hash(p)) for n,p in candidates])
    for name,model in candidates:
        phase('contract-'+name);command('supp-contract-'+name,[BIN/'neural_contract.exe',model],stop=FIT_END)
        command('supp-forward-'+name,[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',model,
            '--checkpoint',model.parent/'selected.pt','--out',S/'checks'/name,OLD/'development-r22/matches/010.jsonl'],stop=FIT_END)
        trial=dict(name=name,model=str(model),model_sha256=sha(model),seats={})
        for side in ['plant','zombie']:
            phase('validation-'+name+'-'+side);folder,_=evaluate('supp-val-'+name+'-'+side,val_ids,model,side,stop=FIT_END)
            a=dict(vs_r22=screen(B/'eval/validation-r22',folder,side),vs_old=screen(B/('eval/validation-old-'+side),folder,side));score=rank(a)
            trial['seats'][side]=dict(rank=score,assessment=a)
            if side not in state['best'] or score>tuple(state['best'][side]['rank']):state['best'][side]=dict(name=name,model=str(model),model_sha256=sha(model),rank=score)
            write(S/'trials'/(name+'.json'),trial);write(S/'state.json',state)
        state['trials'].append(dict(name=name,model=str(model),rank={s:v['rank'] for s,v in trial['seats'].items()}));write(S/'state.json',state)
    frozen();write(S/'selection.json',dict(best=state['best'],test_not_opened=True,frozen_at=datetime.datetime.now(TZ).isoformat()));selection_sha=sha(S/'selection.json')
    phase('export-new-sealed-test');exporters=R/'build/pvp73-tools/ai-20261117/Release'
    command('supp-draft',[exporters/'deck73_corpus.exe',S/'draft.json','1','2','192000','181119'])
    pool=read(S/'draft.json');maps=list(dict.fromkeys(r['map'] for r in pool));chosen=[]
    for r in pool:
        variant=(r['seed']%500)//17
        if variant!=(maps.index(r['map'])+int(r['night']))%2:continue
        assert not r.get('invalid') and not r.get('error');chosen.append(r)
    assert len(chosen)==24;write(S/'scenarios.json',chosen)
    command('supp-export',[sys.executable,'-X','utf8',H/'export_corpus.py',S/'scenarios.json',S/'corpus','4',exporters/'cold73_export.exe'])
    command('supp-materialize',[sys.executable,'-X','utf8',H/'materialize_corpus.py',S/'corpus',S/'corpus-plain'])
    ids=[f'{i:03d}' for i in range(24)];corpus=S/'corpus-plain';state['test_opened']=True;phase('sealed-test-r22')
    evaluate('supp-test-r22',ids,corpus=corpus);tests={}
    for side in ['plant','zombie']:
        phase('sealed-test-old-'+side);evaluate('supp-test-old-'+side,ids,OLD/'warm/old.json',side,corpus=corpus)
        phase('sealed-test-new-'+side);best=state['best'][side];assert sha(Path(best['model']))==best['model_sha256']
        folder,_=evaluate('supp-test-new-'+side,ids,Path(best['model']),side,corpus=corpus)
        tests[side]=dict(vs_r22=screen(B/'eval/supp-test-r22',folder,side),vs_old=screen(B/('eval/supp-test-old-'+side),folder,side));write(S/'test-results.json',tests)
    eligible=all(state['best'][s]['rank'][0] and all(v['passed'] for v in tests[s].values()) for s in ['plant','zombie'])
    if eligible:
        phase('dual-network-interaction');folder,_=evaluate('supp-test-dual',ids,Path(state['best']['plant']['model']),'both',corpus=corpus,zombie_model=Path(state['best']['zombie']['model']))
        dual={s:screen(B/'eval/supp-test-r22',folder,s) for s in ['plant','zombie']};relevant={'crashes','missing_games','ai_errors','more_timeouts','new_timeout_openings','longer_capped_mean_duration'}
        eligible=all(not(set(v['outcome']['failures'])&relevant) and not v['activity_flags'] for v in dual.values());write(S/'dual-diagnostic.json',dict(sides=dual,passed=eligible))
    assert sha(S/'selection.json')==selection_sha;frozen();guard()
    state.update(completed=True,eligible=eligible,formal_promoted=False);phase('completed')
except BaseException as e:
    state['error']=str(e);phase('stopped');raise
