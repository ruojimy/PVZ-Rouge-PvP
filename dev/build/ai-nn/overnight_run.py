"""Adaptive supervised study, bounded by storage and the user's 09:00 deadline."""
import sys
from overnight_common import *
from overnight_eval import evaluate,screen,archive_full

state=dict(completed=False,phase='waiting_for_preparation',trials=[],best={},rounds=[],test_opened=False)
def save():write(B/'state.json',state)
def phase(name):
    state.update(phase=name,phase_started_at=datetime.datetime.now(TZ).isoformat());save();print(json.dumps(dict(phase=name)),flush=True)
def rank(assessment):
    pairs=list(assessment.values());bad=sum(len(p['outcome']['failures'])+len(p['activity_flags']) for p in pairs)
    g=pairs[0]['outcome'];gain=min(p['outcome']['candidate_wins']-p['outcome']['reference_wins'] for p in pairs)
    return (int(all(p['passed'] for p in pairs)),-bad,gain,g['candidate_wins'],-g['candidate_timeouts'],-g['capped_mean_duration_ratio'])
def check_frozen():
    prepared=read(B/'prepared.json')
    assert all(sha(Path(p))==h for p,h in prepared['source_sha256'].items())
    assert all(sha(Path(p))==h for p,h in prepared['binary_sha256'].items())
    assert all(sha(R/p)==h for p,h in read(B/'plan.json')['source_sha256'].items())
def assess_trial(name,model,kind,config,seats=('plant','zombie')):
    result=dict(name=name,model=str(model),model_sha256=sha(model),kind=kind,config=config,seats={})
    for seat in seats:
        phase('validation-'+name+'-'+seat)
        folder,_=evaluate('validation-'+name+'-'+seat,val_ids,model,seat,stop=FIT_END)
        a=dict(vs_r22=screen(B/'eval/validation-r22',folder,seat),vs_old=screen(B/('eval/validation-old-'+seat),folder,seat))
        result['seats'][seat]=dict(rank=rank(a),assessment=a)
        old=state['best'].get(seat)
        if old is None or tuple(result['seats'][seat]['rank'])>tuple(old['rank']):
            state['best'][seat]=dict(name=name,model=str(model),model_sha256=sha(model),rank=result['seats'][seat]['rank'])
        write(B/'trials'/(name+'.json'),result);save()
    state['trials'].append(dict(name=name,model=str(model),kind=kind,model_sha256=sha(model),rank={s:v['rank'] for s,v in result['seats'].items()}));save()
    return result
def fit(name,initial,caches,width,transition,weight,epochs,lr,seed):
    guard(FIT_END);phase('fit-'+name);out=B/'models'/name
    args=[sys.executable,'-X','utf8','-u',H/'overnight_train.py','--data',*caches,'--validation',B/'data/validation.npz',
          '--initial',initial,'--out',out,'--mode-hidden',str(width),'--transition-weight',str(weight),'--epochs',str(epochs),'--lr',str(lr),'--seed',str(seed)]
    if transition:args+=['--transition']
    command('fit-'+name,args,stop=FIT_END)
    assert (out/'report.json').exists()
    command('contract-'+name,[BIN/'neural_contract.exe',out/'model.json'],stop=FIT_END)
    command('forward-'+name,[sys.executable,'-X','utf8',H/'verify_model.py','--encoder',BIN/'neural_dataset.exe','--model',out/'model.json',
        '--checkpoint',out/'selected.pt','--out',B/'checks'/name,OLD/'development-r22/matches/010.jsonl'],stop=FIT_END)
    return assess_trial(name,out/'model.json','trained',dict(initial=str(initial),mode_hidden=width,transition=transition,transition_weight=weight,epochs=epochs,lr=lr,seed=seed))

assert not (B/'state.json').exists();save()
try:
    while not (B/'prepared.json').exists():guard(FIT_END);time.sleep(5)
    check_frozen();plan=read(B/'plan.json');val_ids=[r['id'] for r in plan['entries'] if r['part']=='validation']
    test_ids=[r['id'] for r in plan['entries'] if r['part']=='test']
    grid=[dict(width=width,transition=transition,weight=weight) for weight in [6.,18.] for width,transition in [(0,False),(0,True),(32,False),(32,True)]]
    write(B/'design.json',dict(grid=grid,initial_epochs=80,initial_lr=.0003,
        adaptive_rounds='Use validation-ranked best per side, collect 12 earlier training openings per side; current r22 labels, compressed cache, keep two newest aggregation caches. Two fine-tunes per distinct parent, 60 epochs, lr .0002 or .0001, transition weight 18 or 6. Stop after three rounds without battle-rank improvement.',
        plant_ablation='After the initial grid, evaluate the best plant model with mode-only and economy-only masks. No all-heads-disabled candidate is treated as an improvement.',
        selection='Lexicographic: both references pass all outcome/activity gates; fewer violation flags; minimum win gain; wins; fewer timeouts; lower capped duration. Test remains sealed until final selection.',
        data=str(B/'data/train.npz'),validation=str(B/'data/validation.npz'),deadline=DEADLINE,fit_end=FIT_END))
    stopped_for_time=False
    try:
        for i,c in enumerate(grid):
            fit(f'initial-{i:02d}',OLD/'training-1/selected/model.json',[B/'data/train.npz'],c['width'],c['transition'],c['weight'],80,.0003,181118)
        parent=read(Path(state['best']['plant']['model']));parent_sha=state['best']['plant']['model_sha256']
        for label,mask in [('econ-only',[True,False,True,False]),('mode-only',[False,True,True,False])]:
            name='ablation-'+label;doc=dict(parent);doc['enabled_heads']=mask
            doc['ablation']=dict(parent_sha256=parent_sha,mask=mask)
            path=B/'models'/name/'model.json';write(path,doc);assess_trial(name,path,'head_ablation',dict(mask=mask),seats=['plant'])
        stale=0;extra=[];round_id=0;oldplan=read(OLD/'plan.json');train_ids=[r['id'] for r in oldplan['entries'] if r['part']=='train']
        while time.time()<FIT_END-1800 and stale<3:
            round_id+=1;before={s:tuple(v['rank']) for s,v in state['best'].items()};sources=[];folders=[]
            for side in ['plant','zombie']:
                rotation=(round_id*5+(0 if side=='plant' else 12))%24
                ids=(train_ids[rotation:]+train_ids[:rotation])[:12]
                name=f'collect-r{round_id}-{side}';phase(name)
                folder,_=evaluate(name,ids,Path(state['best'][side]['model']),side,corpus=OLD/'corpus-plain',full=True,stop=FIT_END)
                sources.extend(str(p) for p in sorted((folder/'matches').glob('*.jsonl')));folders.append((folder,name))
            manifest=B/f'collection-r{round_id}-sources.json';write(manifest,sources);cache=B/f'data/collection-r{round_id}.npz'
            command(f'collection-cache-r{round_id}',[sys.executable,'-X','utf8',H/'overnight_data.py','--sources',manifest,'--out',cache,
                '--stride','2','--augment','1','--limit','18000'],stop=FIT_END)
            for folder,name in folders:archive_full(folder,name)
            extra.append(cache);extra=extra[-2:]
            parents={v['model'] for v in state['best'].values()}
            for index,p in enumerate(sorted(parents)):
                doc=read(Path(p))
                for variant,(lr,weight) in enumerate([(.0002,18.),(.0001,6.)]):
                    fit(f'r{round_id}-p{index}-v{variant}',Path(p),[B/'data/train.npz',*extra],doc.get('mode_hidden',0),bool(doc.get('mode_transition')),weight,60,lr,181118+round_id)
            improved=any(tuple(state['best'][s]['rank'])>before[s] for s in before);stale=0 if improved else stale+1
            state['rounds'].append(dict(round=round_id,improved=improved,stale_rounds=stale,best=json.loads(json.dumps(state['best']))));save()
        state['training_stop_reason']='battle_rank_plateau' if stale>=3 else 'reserve_time_for_test'
    except RuntimeError as e:
        if str(e)=='TIME_LIMIT' and time.time()<DEADLINE-1200 and state['best']:
            stopped_for_time=True;state['training_stop_reason']='fit_time_limit';save()
        else:raise
    check_frozen();assert set(state['best'])=={'plant','zombie'}
    selection=dict(best=state['best'],test_not_opened=True,frozen_at=datetime.datetime.now(TZ).isoformat(),training_stop_reason=state['training_stop_reason'])
    write(B/'selection.json',selection);selection_hash=sha(B/'selection.json')
    state['test_opened']=True;save();phase('sealed-test-r22');evaluate('test-r22',test_ids)
    tests={}
    for side in ['plant','zombie']:
        phase('sealed-test-old-'+side);evaluate('test-old-'+side,test_ids,OLD/'warm/old.json',side)
        model=Path(state['best'][side]['model']);assert sha(model)==state['best'][side]['model_sha256']
        phase('sealed-test-new-'+side);folder,_=evaluate('test-new-'+side,test_ids,model,side)
        tests[side]=dict(vs_r22=screen(B/'eval/test-r22',folder,side),vs_old=screen(B/('eval/test-old-'+side),folder,side))
        write(B/'test-results.json',tests)
    eligible=all(state['best'][s]['rank'][0] and all(v['passed'] for v in tests[s].values()) for s in ['plant','zombie'])
    if eligible:
        phase('dual-network-interaction');folder,_=evaluate('test-dual-network',test_ids,Path(state['best']['plant']['model']),'both',zombie_model=Path(state['best']['zombie']['model']))
        dual={side:screen(B/'eval/test-r22',folder,side) for side in ['plant','zombie']}
        # Shared-game wins compete, so only completion, duration, errors and activity screen this diagnostic.
        relevant={'crashes','missing_games','ai_errors','more_timeouts','new_timeout_openings','longer_capped_mean_duration'}
        eligible=all(not (set(v['outcome']['failures'])&relevant) and not v['activity_flags'] for v in dual.values())
        write(B/'dual-diagnostic.json',dict(sides=dual,passed=eligible))
    assert sha(B/'selection.json')==selection_hash;check_frozen();guard()
    state.update(completed=True,phase='completed',eligible=eligible,formal_promoted=False,finished_at=datetime.datetime.now(TZ).isoformat())
    save();print(json.dumps(dict(completed=True,eligible=eligible,best=state['best'])),flush=True)
except BaseException as e:
    state.update(phase='stopped',stop_error=str(e),stopped_at=datetime.datetime.now(TZ).isoformat());save();raise
