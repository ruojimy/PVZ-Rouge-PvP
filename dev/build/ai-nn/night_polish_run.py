"""Precommitted local refinement around training elites; no test-driven tuning."""
import sys
import numpy as np
import overnight_eval as ev
import night_residual_model as actor
from overnight_common import *

D=B/'residual';P=B/'polish';P.mkdir(exist_ok=True);NBIN=D/'native-build/Release';ev.BIN=NBIN
state=dict(completed=False,phase='preparing',train_trials=[],validation_trials=[],best={},test_opened=False)
def phase(name):
    state.update(phase=name,updated_at=datetime.datetime.now(TZ).isoformat());write(P/'state.json',state);print(name,flush=True)
def rank(a):
    pairs=list(a.values());bad=sum(len(p['outcome']['failures'])+len(p['activity_flags']) for p in pairs);g=pairs[0]['outcome']
    return (int(all(p['passed'] for p in pairs)),-bad,min(p['outcome']['candidate_wins']-p['outcome']['reference_wins'] for p in pairs),g['candidate_wins'],-g['candidate_timeouts'],-g['capped_mean_duration_ratio'])
def frozen():
    for path in [B/'prepared.json',D/'plan.json',D/'native-prepared.json',P/'plan.json',P/'parents.json']:
        q=read(path)
        for field in ['source_sha256','binary_sha256','data_sha256']:
            assert all(sha(Path(k))==v for k,v in q.get(field,{}).items()),str(path)
    assert all(sha(R/k)==v for k,v in read(B/'plan.json')['source_sha256'].items())
    assert sha(R/'PVZ_rougePvP_native/PvZPvPNative.exe')==read(B/'plan.json')['release_sha256']
def changed(reference,folder):
    a=read(reference/'summary.json');b=read(folder/'summary.json')
    return [i for i in b['ids'] if a['matches'][i]['log_sha256']!=b['matches'][i]['log_sha256']]
def screen(folder,side,group):
    return dict(vs_r22=ev.screen(B/('eval/'+group+'-r22'),folder,side),vs_old=ev.screen(B/('eval/'+group+'-old-'+side),folder,side))
def verify(item):
    name=item['name'];model=Path(item['model']);assert sha(model)==item['model_sha256']
    command('polish-contract-'+name,[NBIN/'neural_contract.exe',model],stop=FIT_END)
    command('polish-forward-'+name,[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',NBIN/'neural_dataset.exe','--model',model,
        '--checkpoint',model.parent/'selected.pt','--out',P/'checks'/name,OLD/'development-r22/matches/010.jsonl'],stop=FIT_END)
def strict_gain(a):
    g=a['vs_r22']['outcome']
    return g['candidate_wins']>g['reference_wins'] or g['candidate_timeouts']<g['reference_timeouts'] or g['capped_mean_duration_ratio']<.97

assert not (P/'plan.json').exists() and not read(D/'state.json')['test_opened']
write(P/'plan.json',dict(created_at=datetime.datetime.now(TZ).isoformat(),prior_test_not_opened=True,
    source_sha256={str(p):sha(p) for p in [H/'night_polish_run.py',H/'night_residual_model.py']},
    data_sha256={str(p):sha(p) for p in [D/'plan.json',D/'calibration.npz',B/'selection.json']},
    trigger='Run only after the residual study completes without a jointly eligible model, and before 07:25. No simultaneous game studies.',
    parents='Best nonneutral candidates by training rank only, frozen as soon as the residual search ends and before its test is opened.',
    proposals=[dict(relative_noise=n,rate_multiplier=r) for n,r in [(0.025,1),(0.075,1),(0.15,1),(0,0.8),(0,1.2),(0.05,1.1)]],
    seed=181121,selection='Six proposals per side on the same 12 training openings. Stop if neither side improves its training elite. Otherwise evaluate top two per side on 24 validation openings.',
    testing='Only validation-eligible sides enter a NEW sealed 24-opening test. Seed base 212000; draft seed 181121. Frozen selection first. Original training elites are not counted as new fitted candidates.',
    promotion='Validation and test must pass both references, behavior must change, and test must improve wins, timeouts or capped duration by at least 3% with no fewer wins. Only jointly eligible sides enter the dual-model diagnostic.',
    fit_end=FIT_END,deadline=DEADLINE,start_cutoff=DEADLINE-95*60,storage='Shared 4 GiB/100 GiB guards; four game workers maximum.'))
try:
    phase('waiting-for-training-elites')
    while True:
        q=read(D/'state.json');guard()
        if q['phase']=='stopped':raise RuntimeError('RESIDUAL_STOPPED')
        if q['test_opened']:raise RuntimeError('TOO_LATE_TO_FREEZE_PARENTS')
        if q['phase'].startswith('validation-'):break
        time.sleep(5)
    parents={};paths=[]
    for side in ['plant','zombie']:
        options=[(read(p),p) for p in (D/'train-trials').glob(side+'-*.json')]
        item,path=max(options,key=lambda pair:tuple(pair[0]['rank']));parents[side]=item;paths+=[path,Path(item['model'])]
    write(P/'parents.json',dict(frozen_at=datetime.datetime.now(TZ).isoformat(),residual_test_not_opened=True,parents=parents,data_sha256={str(p):sha(p) for p in paths}))
    phase('waiting-for-residual-study')
    while not read(D/'state.json')['completed']:
        guard()
        if read(D/'state.json')['phase']=='stopped':raise RuntimeError('RESIDUAL_STOPPED')
        time.sleep(5)
    trigger=read(D/'state.json');state['trigger_state_sha256']=sha(D/'state.json')
    if trigger.get('eligible') or time.time()>DEADLINE-95*60:
        state.update(completed=True,skipped=True,reason='residual_passed' if trigger.get('eligible') else 'insufficient_time');phase('skipped');sys.exit(0)
    frozen();psutil.Process().cpu_affinity(list(range(psutil.cpu_count())));actor.D=P
    shutil.copy2(D/'calibration.npz',P/'calibration.npz');assert sha(P/'calibration.npz')==sha(D/'calibration.npz')
    train_ids=read(D/'plan.json')['training_ids'];val_ids=read(D/'plan.json')['validation_ids'];pools={s:[] for s in parents};improved={};seen={}
    for side,parent in parents.items():
        rng=np.random.default_rng(181121+(side=='zombie'));base=np.asarray(parent['genes']);rates=np.asarray(parent['rates']);best=tuple(parent['rank'])
        for index,proposal in enumerate(read(P/'plan.json')['proposals']):
            phase(f'train-{side}-{index}');sigma=proposal['relative_noise']
            noise=rng.normal(size=base.shape)*np.linalg.norm(base,axis=1,keepdims=True)/np.sqrt(base.shape[1])*sigma
            candidate=actor.save_actor(f'polish-{side}-{index}',side,base+noise,(rates*proposal['rate_multiplier']).tolist())
            if candidate['policy_digest'] in seen:
                state.setdefault('duplicates',[]).append(dict(name=candidate['name'],same_parameters_as=seen[candidate['policy_digest']]));write(P/'state.json',state);continue
            seen[candidate['policy_digest']]=candidate['name'];verify(candidate)
            folder,_=ev.evaluate('polish-train-'+side+'-'+str(index),train_ids,Path(candidate['model']),side,corpus=OLD/'corpus-plain',stop=FIT_END)
            a=screen(folder,side,'resid-train');candidate.update(assessment=a,rank=rank(a),folder=str(folder),changed_training_ids=changed(B/'eval/resid-train-r22',folder))
            pools[side].append(candidate);write(P/'train-trials'/(candidate['name']+'.json'),candidate);state['train_trials'].append(dict(name=candidate['name'],side=side,rank=candidate['rank']));write(P/'state.json',state)
        improved[side]=max(tuple(c['rank']) for c in pools[side])>best
    state['training_improved']=improved
    if not any(improved.values()):
        state.update(completed=True,eligible=False,reason='no_training_gain',formal_promoted=False);frozen();phase('completed');sys.exit(0)
    for side,pool in pools.items():
        for candidate in sorted(pool,key=lambda c:tuple(c['rank']),reverse=True)[:2]:
            phase('validation-'+candidate['name']);folder,_=ev.evaluate('polish-val-'+candidate['name'],val_ids,Path(candidate['model']),side,stop=FIT_END)
            a=screen(folder,side,'validation');item=dict(name=candidate['name'],side=side,model=candidate['model'],model_sha256=candidate['model_sha256'],rank=rank(a),assessment=a,changed_validation_ids=changed(B/'eval/validation-r22',folder))
            write(P/'validation-trials'/(item['name']+'.json'),item);state['validation_trials'].append(dict(name=item['name'],side=side,rank=item['rank']))
            if side not in state['best'] or tuple(item['rank'])>tuple(state['best'][side]['rank']):state['best'][side]=item
            write(P/'state.json',state)
    frozen();write(P/'selection.json',dict(best=state['best'],test_not_opened=True,frozen_at=datetime.datetime.now(TZ).isoformat()));selection_sha=sha(P/'selection.json')
    eligible_sides=[s for s,v in state['best'].items() if v['rank'][0] and v['changed_validation_ids']]
    state['validation_eligible_sides']=eligible_sides
    if not eligible_sides:
        state.update(completed=True,eligible=False,reason='no_validation_candidate',formal_promoted=False);phase('completed');sys.exit(0)
    phase('export-fresh-test');exporters=R/'build/pvp73-tools/ai-20261117/Release'
    command('polish-draft',[exporters/'deck73_corpus.exe',P/'draft.json','1','2','212000','181121'])
    pool=read(P/'draft.json');maps=list(dict.fromkeys(r['map'] for r in pool));chosen=[r for r in pool if (r['seed']%500)//17==(maps.index(r['map'])+int(r['night']))%2]
    assert len(chosen)==24 and all(not r.get('invalid') and not r.get('error') for r in chosen);write(P/'scenarios.json',chosen)
    command('polish-export',[sys.executable,'-X','utf8',H/'export_corpus.py',P/'scenarios.json',P/'corpus','4',exporters/'cold73_export.exe'])
    command('polish-materialize',[sys.executable,'-X','utf8',H/'materialize_corpus.py',P/'corpus',P/'corpus-plain'])
    ids=[f'{i:03d}' for i in range(24)];corpus=P/'corpus-plain';state['test_opened']=True;phase('sealed-test-r22');ev.evaluate('polish-test-r22',ids,corpus=corpus);tests={}
    for side in eligible_sides:
        phase('sealed-test-old-'+side);ev.evaluate('polish-test-old-'+side,ids,OLD/'warm/old.json',side,corpus=corpus)
        phase('sealed-test-new-'+side);item=state['best'][side];assert sha(Path(item['model']))==item['model_sha256']
        folder,_=ev.evaluate('polish-test-new-'+side,ids,Path(item['model']),side,corpus=corpus);tests[side]=screen(folder,side,'polish-test');write(P/'test-results.json',tests)
    state['eligible_sides']=[s for s,a in tests.items() if all(v['passed'] for v in a.values()) and strict_gain(a)]
    eligible=len(state['eligible_sides'])==2
    if eligible:
        phase('dual-network-interaction');folder,_=ev.evaluate('polish-test-dual',ids,Path(state['best']['plant']['model']),'both',corpus=corpus,zombie_model=Path(state['best']['zombie']['model']))
        dual={s:ev.screen(B/'eval/polish-test-r22',folder,s) for s in ['plant','zombie']};relevant={'crashes','missing_games','ai_errors','more_timeouts','new_timeout_openings','longer_capped_mean_duration'}
        eligible=all(not(set(v['outcome']['failures'])&relevant) and not v['activity_flags'] for v in dual.values());write(P/'dual-diagnostic.json',dict(sides=dual,passed=eligible))
    assert sha(P/'selection.json')==selection_sha;frozen();guard();state.update(completed=True,eligible=eligible,formal_promoted=False);phase('completed')
except SystemExit:raise
except BaseException as e:
    state['error']=str(e);phase('stopped');raise
