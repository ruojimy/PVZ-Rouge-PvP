"""New ranked r4 openings, exact old-win replays, and verified parameter transfer."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import os
from pathlib import Path
from ranked_night_native import OUT,PREVIOUS,RELEASE,R,ROOT,read,write,sha
from league_data import TZ,OLD_Z,BASE

profile_path=OUT/'profile.json'

def profile():
    parent=PREVIOUS/'draft/frozen.npz'
    assert sha(parent)==read(PREVIOUS/'draft/results.json')['frozen']
    deadline=datetime.datetime(2026,11,20,9,tzinfo=TZ).timestamp()
    cfg=dict(version=RELEASE['version'],output=str(OUT),data_root=RELEASE['release'],deadline=deadline,
             draft_parent=str(parent),draft_sha=sha(parent),seed_offset=12000000,home='家院',reference='r22')
    if profile_path.exists():assert cfg==read(profile_path)
    else:write(profile_path,cfg)
    os.environ['PVZ_RANKED_PROFILE']=str(profile_path)
    return cfg

def prepare():
    cfg=profile()
    from ranked_draft import Room,DraftNet,draft,HOME,RULES,SIDES,check_game,BATTLE
    from ranked_corpus import create,verify
    from option_games import Game,play,trace
    from league_data import NEW,OLD_CORPUS
    import gzip,json
    if (OUT/'ready.json').exists():return
    build=read(OUT/'native-build.json')
    assert all(sha(OUT/'native'/(n+'.exe'))==v for n,v in build['binaries'].items())
    assert sha(Path(cfg['data_root'])/'extract/data/_resolved_cards.json')==build['shipped_catalog']
    stage=BATTLE/'weights';stage.mkdir(exist_ok=True,parents=True)
    old=read(PREVIOUS/'battle/opponents.json')
    saved=read(PREVIOUS/'battle/sealed.json')
    parent=Path(saved['models']['研究候选'])
    assert sha(parent)==saved['hashes']['研究候选']
    pos=stage/'position.json';links={}
    def move(source,name):
        source=Path(source);new=stage/(name+'.json');body=read(source);orig=body['sim_fingerprint']
        def visit(node):
            if not isinstance(node,dict):return
            if 'sim_fingerprint' in node:
                assert node['sim_fingerprint']==orig;node['sim_fingerprint']=build['fingerprint']
            if 'position_parent' in node:
                assert node['position_parent']==sha(OLD_Z);node['position_parent']=sha(pos)
            for v in node.values():visit(v)
        visit(body);write(new,body)
        links[name]=dict(source=str(source),source_sha=sha(source),old_fingerprint=orig,transferred=sha(new))
        return str(new)
    move(OLD_Z,'position');move(BASE,'macro')
    pool={n:move(path,'plant-'+n) if path!='r22' else 'r22' for n,path in old['pool'].items()}
    past=move(old['champion'],'historical-zombie');start=move(parent,'previous-specialist')
    write(BATTLE/'opponents.json',dict(pool=pool,selected=old['selected'],plant_sha={n:sha(Path(v)) for n,v in pool.items() if v!='r22'},
           champion=past,champion_sha=sha(Path(past)),start_zombie=start,transfer=links))
    write(BATTLE/'build.json',dict(binary=build['binaries']['position_match'],release=build['release'],fingerprint=build['fingerprint']))
    legacy={tag:read(PREVIOUS/'battle'/name/'index.json')['entries'] for tag,name in [('fresh','plain'),('playable','playable')]}
    room=Room()
    try:
        model=DraftNet(room.catalog).load(Path(cfg['draft_parent']));nets=dict.fromkeys(SIDES,model)
        old_rows=read(PREVIOUS/'battle/assessment.json')['研究候选']
        lost=[r for r in old_rows['r22']['rows'] if r['old']==1 and r['new']!=1]
        assert len(lost)==10
        useful=[r for r in old_rows['night']['rows'] if r['old']==-1 and r['new']==1]
        pairs=[];cases={};scenarios=[];old_to_new={v:pool[n] for n,v in old['pool'].items()}
        for r in [*lost,*useful]:
            code=r['case']
            if code not in cases:
                tag,uid=code.split('/');e=next(v for v in legacy[tag] if v['id']==uid)
                state=room.request(op='start',seed=e['seed'],map=e['map'],night=e['night'],weather=e['weather'])
                terrain=state['terrain']['terrain_hash']
                for h in e['draft_history']:
                    assert all(state['action'][k]==h[k] for k in ('stage','kind','side'))
                    state=room.request(op='act',key=h['card'])
                assert not state.get('battle_error') and state['decks']==e['decks'] and state['bans']==e['bans']
                sc=check_game(dict(seed=e['seed'],map=e['map'],night=e['night'],weather=e['weather'],rules=state['rules'],
                                   decks=state['decks'],bans=state['bans'],draft_history=state['history'],terrain_hash=terrain))
                cases[code]=f'replay/{len(scenarios):03d}';scenarios.append(sc)
            pairs.append(dict(case=cases[code],plant=old_to_new[r['opp']],previous_case=code,
                              reason='lost-r22-win' if r in lost else 'recovered-historical-loss'))
        proof=verify(scenarios[0]);write(BATTLE/'export-proof.json',proof)
        create(BATTLE/'replay',scenarios,3)
        write(BATTLE/'replay.json',dict(pairs=pairs,index_sha=sha(BATTLE/'replay/index.json')))
        bench=OUT/'smoke';(bench/'temp').mkdir(parents=True,exist_ok=True)
        for name,macro,position,policy in [('r22',None,None,None),('prior',None,pos,Path(start)),('historical',stage/'macro.json',pos,Path(past))]:
            game=Game('000',Path(pool['away']),zombie=macro,position=position,policy=policy,corpus=BATTLE/'replay',
                      binary=OUT/'native/position_match.exe',storage=bench,limit=24)
            play(game)
            with gzip.open(game.path(),'rt',encoding='utf8') as f:header=json.loads(f.readline())
            assert header['source_fingerprint']==build['fingerprint'] and header['ranked_rules']['build']==cfg['version']
            assert not trace(game)['ai_error']
        write(OUT/'smoke.json',dict(version=cfg['version'],models=['r22','previous-specialist','historical-zombie'],
              rules=RULES,replayed_previous_losses=len(lost),eligible_past_gains=len(useful),native=proof))
        refs=[e for path in (OLD_CORPUS,NEW) for e in read(path/'index.json')['entries'] if e['map']==HOME]
        known={s:{tuple(sorted(e['decks'][s])) for group in legacy.values() for e in group} for s in SIDES}
        for tag,name,seed_base in [('fresh','plain',22000000),('playable','playable',22100000)]:
            scenarios=[];rejects=[]
            for i in range(500):
                n=len(scenarios);night=bool(n%2)
                choices=[v for v in refs if v['night']==night]
                template={s:choices[(i*k+b)%len(choices)]['decks'][s] for s,k,b in zip(SIDES,(11,17),(3,9))} if tag=='playable' else None
                sc,_=draft(room,nets,seed_base+i,HOME,night,width=256,weather='rain' if (n+n//4)%5==1 else 'clear',combat_template=template)
                if sc['battle_error']:rejects.append(dict(seed=sc['seed'],error=sc['battle_error']));continue
                decks={s:tuple(sorted(sc['decks'][s])) for s in SIDES}
                if any(decks[s] in known[s] for s in SIDES):continue
                for s in SIDES:known[s].add(decks[s])
                scenarios.append(sc)
                if len(scenarios)==48:break
            assert len(scenarios)==48
            entries=create(BATTLE/name,scenarios,3);ids=[tag+'/'+e['id'] for e in entries]
            plan=dict(train=ids[:16],validation=ids[16:24],blind=ids[24:],blind_seeds=[e['seed'] for e in entries[24:]],
                      index_sha=sha(BATTLE/name/'index.json'),rules=RULES,room=proof['room'],unstartable=rejects)
            write(BATTLE/('fixtures.json' if tag=='fresh' else 'playable.json'),plan)
    finally:room.close()
    write(OUT/'ready.json',dict(native=sha(OUT/'native-build.json'),draft_parent=cfg['draft_sha'],battle_parent=sha(parent),
           replay_pairs=len(pairs),training_openings=32,validation_openings=16,sealed_openings=48))

if __name__=='__main__':prepare()
