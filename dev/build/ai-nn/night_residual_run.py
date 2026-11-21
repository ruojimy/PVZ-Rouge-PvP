"""Conditional outcome search: bounded neural corrections, fixed r22 opponents."""
import sys,subprocess
import numpy as np
import torch
import overnight_eval as ev
from overnight_common import *
from night_residual_model import D,NBIN,PARENTS,prepare_calibration,calibration,save_actor
ev.BIN=NBIN
state=dict(completed=False,phase='preparing',train_trials=[],validation_trials=[],best={},test_opened=False)
def phase(name):
    state.update(phase=name,updated_at=datetime.datetime.now(TZ).isoformat());write(D/'state.json',state);print(name,flush=True)
def rank(a):
    pairs=list(a.values());bad=sum(len(p['outcome']['failures'])+len(p['activity_flags']) for p in pairs);g=pairs[0]['outcome']
    return (int(all(p['passed'] for p in pairs)),-bad,min(p['outcome']['candidate_wins']-p['outcome']['reference_wins'] for p in pairs),g['candidate_wins'],-g['candidate_timeouts'],-g['capped_mean_duration_ratio'])
def frozen():
    p=read(D/'plan.json');q=read(B/'prepared.json');n=read(D/'native-prepared.json')
    expected={**p['source_sha256'],**p['data_sha256'],**q['source_sha256'],**q['binary_sha256'],**n['source_sha256'],**n['binary_sha256']}
    assert all(sha(Path(k))==v for k,v in expected.items())
    assert all(sha(R/k)==v for k,v in read(B/'plan.json')['source_sha256'].items())
    assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==read(B/'plan.json')['release_sha256']
def verify(actor):
    name=actor['name'];model=Path(actor['model']);assert sha(model)==actor['model_sha256']
    command('resid-contract-'+name,[NBIN/'neural_contract.exe',model],stop=FIT_END)
    command('resid-forward-'+name,[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',NBIN/'neural_dataset.exe','--model',model,
        '--checkpoint',model.parent/'selected.pt','--out',D/'checks'/name,OLD/'development-r22/matches/010.jsonl'],stop=FIT_END)
def compare_pair(folder,side,prefix):
    return dict(vs_r22=ev.screen(B/('eval/'+prefix+'-r22'),folder,side),vs_old=ev.screen(B/('eval/'+prefix+'-old-'+side),folder,side))
def changed(reference,candidate):
    a=read(reference/'summary.json');b=read(candidate/'summary.json')
    return [i for i in b['ids'] if a['matches'][i]['log_sha256']!=b['matches'][i]['log_sha256']]
def strict_gain(a):
    g=a['vs_r22']['outcome']
    return g['candidate_wins']>g['reference_wins'] or g['candidate_timeouts']<g['reference_timeouts'] or g['capped_mean_duration_ratio']<.97

assert (D/'native-prepared.json').exists() and not (D/'plan.json').exists()
oldplan=read(OLD/'plan.json');train_entries=[r for r in oldplan['entries'] if r['part']=='train'];maps=list(dict.fromkeys(r['map'] for r in train_entries))
train_ids=[next(r['id'] for r in train_entries if r['map']==m and bool(r['night'])==bool(i%2)) for i,m in enumerate(maps)]
assert len(train_ids)==12
val_ids=[r['id'] for r in read(B/'plan.json')['entries'] if r['part']=='validation']
sources=[H/'night_residual_run.py',H/'night_residual_model.py',H/'night_bounded_build.py',H/'night_bounded_contract.cpp']
data=[B/'data/train.npz',B/'data/validation.npz',*PARENTS.values(),OLD/'warm/old.json',OLD/'plan.json',B/'plan.json',B/'selection.json',B/'supplement/plan.json']
write(D/'plan.json',dict(created_at=datetime.datetime.now(TZ).isoformat(),source_sha256={str(p):sha(p) for p in sources},data_sha256={str(p):sha(p) for p in data},
    trigger='Run only if the supplemental study completes without an eligible model, and before the start cutoff. Otherwise skip games.',
    start_cutoff=DEADLINE-130*60,deadline=DEADLINE,fit_end=FIT_END,training_ids=train_ids,validation_ids=val_ids,
    search=dict(seed=181120,generations=3,population_per_side=6,stop_after_stale_generations=2,validation_top_per_side=3,
        calibration='8192 unique canonical training states per side, validation feature hashes excluded',
        mutable='Two conditional action readouts, 130 parameters per side; trained encoder frozen. Actions are -1/0/+1. Mode, save and strategy memory remain r22.',
        objective='Paired real battles versus r22 and the old model: all tempo/activity gates, fewer failures, minimum win gain, wins, fewer timeouts, shorter capped mean. No self-play or policy-gradient claim.'),
    test='Fresh 24 openings, seed base 202000, draft seed 181120; frozen selection first. Test outcomes never feed search.',
    promotion='Both references must pass validation and test, actual validation behavior must differ from neutral, and test must improve r22 wins, timeouts, or capped duration by at least 3% without fewer wins. Then run dual-model tempo diagnostic.',
    storage='Original shared 4 GiB budget and 100 GiB free-space floor. New build is inside the monitored run directory. At most four games, after the supplemental games end.'))
try:
    frozen();phase('calibration');prepare_calibration();torch.set_num_threads(1)
    neutrals={s:save_actor('neutral-'+s,s) for s in ['plant','zombie']}
    for s,a in neutrals.items():
        phase('neutral-contract-'+s);verify(a)
        result=subprocess.run([str(BIN/'neural_dataset.exe'),str(D/('old-runtime-rejected-'+s+'.jsonl')),a['model'],str(OLD/'development-r22/matches/010.jsonl')],capture_output=True)
        assert result.returncode!=0
        write(D/('old-runtime-rejection-'+s+'.json'),dict(returncode=result.returncode,message=result.stderr.decode('utf-8','replace')))
    phase('waiting-for-supplement')
    while not read(B/'supplement/state.json')['completed']:
        guard()
        if read(B/'supplement/state.json')['phase']=='stopped':raise RuntimeError('SUPPLEMENT_STOPPED')
        time.sleep(5)
    trigger=read(B/'supplement/state.json');state['trigger_state_sha256']=sha(B/'supplement/state.json')
    if trigger.get('eligible') or time.time()>DEADLINE-130*60:
        state.update(completed=True,skipped=True,reason='supplement_passed' if trigger.get('eligible') else 'insufficient_time');phase('skipped');sys.exit(0)
    psutil.Process().cpu_affinity(list(range(psutil.cpu_count())));frozen();state['search_started_at']=datetime.datetime.now(TZ).isoformat()
    phase('training-baselines');ev.evaluate('resid-train-r22',train_ids,corpus=OLD/'corpus-plain',stop=FIT_END)
    old_reference=read(OLD/'development-r22/summary.json');new_reference=read(B/'eval/resid-train-r22/summary.json')
    assert all(old_reference['matches'][i]['log_sha256']==new_reference['matches'][i]['log_sha256'] for i in train_ids)
    parity=dict(r22_training_openings=len(train_ids),legacy_neural_checks={},neutral_checks={})
    for side in ['plant','zombie']:
        ev.evaluate('resid-train-old-'+side,train_ids,OLD/'warm/old.json',side,corpus=OLD/'corpus-plain',stop=FIT_END)
        folder,_=ev.evaluate('resid-legacy-check-'+side,[val_ids[0]],OLD/'warm/old.json',side,stop=FIT_END)
        assert not changed(B/('eval/validation-old-'+side),folder);parity['legacy_neural_checks'][side]=1
        folder,_=ev.evaluate('resid-neutral-'+side,train_ids,Path(neutrals[side]['model']),side,corpus=OLD/'corpus-plain',stop=FIT_END)
        assert not changed(B/'eval/resid-train-r22',folder);parity['neutral_checks'][side]=len(train_ids)
        neutrals[side].update(assessment=compare_pair(folder,side,'resid-train'),folder=str(folder))
        neutrals[side]['rank']=rank(neutrals[side]['assessment'])
    write(D/'runtime-parity.json',dict(passed=True,**parity))
    for side in ['plant','zombie']:
        rng=np.random.default_rng(181120+(side=='zombie'));_,_,contrast,_=calibration(side);incumbent=neutrals[side];stale=0;seen={}
        for generation in range(3):
            before=tuple(incumbent['rank'])
            for index in range(6):
                phase(f'train-{side}-g{generation}-i{index}')
                if generation==0 and index==0:genes=np.stack([contrast,-contrast]);rates=[.1,0.]
                elif generation==0 and index==1:genes=np.stack([-contrast,contrast]);rates=[0.,.05]
                else:
                    parent=np.asarray(incumbent['genes']) if incumbent['genes'] is not None else np.stack([contrast,-contrast])
                    genes=parent+rng.normal(size=parent.shape)*(.2 if index<3 else .6)
                    rates=[[.05,.05],[.1,0.],[0.,.1],[.1,.1],[.2,0.],[.1,.05]][index]
                name=f'{side}-g{generation}-i{index}'
                actor=save_actor(name,side,genes,rates);digest=actor['policy_digest']
                if digest in seen:
                    write(D/'duplicates'/f'{name}.json',dict(name=name,same_parameters_as=seen[digest]));continue
                seen[digest]=name;verify(actor)
                folder,_=ev.evaluate('resid-train-'+name,train_ids,Path(actor['model']),side,corpus=OLD/'corpus-plain',stop=FIT_END)
                a=compare_pair(folder,side,'resid-train');actor.update(assessment=a,rank=rank(a),folder=str(folder),changed_training_ids=changed(B/'eval/resid-train-r22',folder))
                write(D/'train-trials'/f'{name}.json',actor);state['train_trials'].append(dict(name=name,side=side,rank=actor['rank']))
                if tuple(actor['rank'])>tuple(incumbent['rank']):incumbent=actor
                write(D/'state.json',state)
            improved=tuple(incumbent['rank'])>before;stale=0 if improved else stale+1
            state.setdefault('generations',[]).append(dict(side=side,generation=generation,improved=improved,stale=stale,incumbent=incumbent['name']));write(D/'state.json',state)
            if stale>=2:break
    frozen();pool={s:[] for s in ['plant','zombie']}
    for p in (D/'train-trials').glob('*.json'):
        a=read(p);pool[a['side']].append(a)
    for side in ['plant','zombie']:
        selected=sorted(pool[side],key=lambda r:tuple(r['rank']),reverse=True)[:3];assert selected
        for actor in selected:
            name=actor['name'];phase('validation-'+name)
            folder,_=ev.evaluate('resid-val-'+name,val_ids,Path(actor['model']),side,stop=FIT_END)
            a=dict(vs_r22=ev.screen(B/'eval/validation-r22',folder,side),vs_old=ev.screen(B/('eval/validation-old-'+side),folder,side))
            candidate=dict(name=name,side=side,model=actor['model'],model_sha256=actor['model_sha256'],rank=rank(a),assessment=a,
                changed_validation_ids=changed(B/'eval/validation-r22',folder))
            write(D/'validation-trials'/f'{name}.json',candidate);state['validation_trials'].append(dict(name=name,side=side,rank=candidate['rank']))
            if side not in state['best'] or tuple(candidate['rank'])>tuple(state['best'][side]['rank']):state['best'][side]=candidate
            write(D/'state.json',state)
    frozen();write(D/'selection.json',dict(best=state['best'],test_not_opened=True,frozen_at=datetime.datetime.now(TZ).isoformat()));selection_sha=sha(D/'selection.json')
    phase('export-fresh-test');exporters=R/'build/pvp73-tools/ai-20261117/Release'
    command('resid-draft',[exporters/'deck73_corpus.exe',D/'draft.json','1','2','202000','181120'])
    pool=read(D/'draft.json');maps=list(dict.fromkeys(r['map'] for r in pool))
    chosen=[r for r in pool if (r['seed']%500)//17==(maps.index(r['map'])+int(r['night']))%2]
    assert len(chosen)==24 and all(not r.get('invalid') and not r.get('error') for r in chosen);write(D/'scenarios.json',chosen)
    command('resid-export',[sys.executable,'-X','utf8',H/'export_corpus.py',D/'scenarios.json',D/'corpus','4',exporters/'cold73_export.exe'])
    command('resid-materialize',[sys.executable,'-X','utf8',H/'materialize_corpus.py',D/'corpus',D/'corpus-plain'])
    ids=[f'{i:03d}' for i in range(24)];corpus=D/'corpus-plain';state['test_opened']=True;phase('sealed-test-r22')
    ev.evaluate('resid-test-r22',ids,corpus=corpus);tests={}
    for side in ['plant','zombie']:
        phase('sealed-test-old-'+side);ev.evaluate('resid-test-old-'+side,ids,OLD/'warm/old.json',side,corpus=corpus)
        phase('sealed-test-new-'+side);actor=state['best'][side];assert sha(Path(actor['model']))==actor['model_sha256']
        folder,_=ev.evaluate('resid-test-new-'+side,ids,Path(actor['model']),side,corpus=corpus)
        tests[side]=dict(vs_r22=ev.screen(B/'eval/resid-test-r22',folder,side),vs_old=ev.screen(B/('eval/resid-test-old-'+side),folder,side));write(D/'test-results.json',tests)
    eligible=all(state['best'][s]['rank'][0] and state['best'][s]['changed_validation_ids'] and all(v['passed'] for v in tests[s].values()) and strict_gain(tests[s]) for s in ['plant','zombie'])
    if eligible:
        phase('dual-network-interaction');folder,_=ev.evaluate('resid-test-dual',ids,Path(state['best']['plant']['model']),'both',corpus=corpus,zombie_model=Path(state['best']['zombie']['model']))
        dual={s:ev.screen(B/'eval/resid-test-r22',folder,s) for s in ['plant','zombie']};relevant={'crashes','missing_games','ai_errors','more_timeouts','new_timeout_openings','longer_capped_mean_duration'}
        eligible=all(not(set(v['outcome']['failures'])&relevant) and not v['activity_flags'] for v in dual.values());write(D/'dual-diagnostic.json',dict(sides=dual,passed=eligible))
    assert sha(D/'selection.json')==selection_sha;frozen();guard();state.update(completed=True,eligible=bool(eligible),formal_promoted=False);phase('completed')
except SystemExit:raise
except BaseException as e:
    state['error']=str(e);phase('stopped');raise
