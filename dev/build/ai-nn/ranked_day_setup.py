"""Build disjoint daytime home-map ranked-seven pools for both populations."""
import os
from pathlib import Path
from ranked_night_native import OUT as STAGING, ROOT, read, write, sha

RUN=ROOT/'ranked-day-league-20261120'

def prepare():
    RUN.mkdir(exist_ok=True)
    cfg={**read(STAGING/'profile.json'),'output':str(RUN),'day_league':True,'native_dir':str(STAGING/'native'),
         'weights_dir':str(STAGING/'battle/weights'),'seed_offset':18500000,'weather':'clear','night':False}
    path=RUN/'profile.json'
    if path.exists():assert cfg==read(path)
    else:write(path,cfg)
    os.environ['PVZ_RANKED_PROFILE']=str(path)
    from ranked_draft import BATTLE,Room,DraftNet,HOME,SIDES,RULES,check_game,draft
    from ranked_corpus import create
    from league_data import OLD_CORPUS,NEW
    if (RUN/'ready.json').exists():return
    BATTLE.mkdir(exist_ok=True)
    build=read(STAGING/'native-build.json')
    for n,v in build['binaries'].items():assert sha(Path(cfg['native_dir'])/(n+'.exe'))==v
    meta=read(STAGING/'battle/opponents.json')
    frozen=read(ROOT/'league-20261119/frozen.json')['sides']
    for side,n in [('plant','plant-away'),('zombie','historical-zombie')]:
        assert frozen[side]['champ_sha']==meta['transfer'][n]['source_sha']
    write(BATTLE/'opponents.json',meta)
    refs=[e for c in [NEW,OLD_CORPUS] for e in read(c/'index.json')['entries'] if e['map']==HOME and not e['night']]
    previous=[e for root in [STAGING,ROOT/'ranked-seven-20261119'] for name in ['plain','playable']
              for e in read(root/'battle'/name/'index.json')['entries']]
    known={s:{tuple(sorted(e['decks'][s])) for e in previous} for s in SIDES}
    seen={e['seed'] for e in previous}
    room=Room()
    try:
        net=DraftNet(room.catalog).load(Path(cfg['draft_parent']))
        assert sha(Path(cfg['draft_parent']))==cfg['draft_sha']
        cases={};pools={k:[] for k in ('train','validation','blind')};strata={}
        for name,start in [('free',30400000),('template',30600000)]:
            selected=[];rejects=0
            for i in range(640):
                seed=start+i
                templ={s:refs[(i*k+b)%len(refs)]['decks'][s] for s,k,b in zip(SIDES,(11,17),(3,9))} if name=='template' else None
                sc,_=draft(room,dict.fromkeys(SIDES,net),seed,HOME,False,weather='clear',width=256,combat_template=templ)
                decks={s:tuple(sorted(sc['decks'][s])) for s in SIDES}
                if sc['battle_error'] or seed in seen or any(decks[s] in known[s] for s in SIDES):
                    rejects+=1;continue
                for s in SIDES:known[s].add(decks[s])
                seen.add(seed);selected.append(sc)
                if len(selected)==48:break
            assert len(selected)==48
            root=BATTLE/name
            entries=create(root,selected,3)
            cases[name]=dict(path=str(root),sha=sha(root/'index.json'),rejected=rejects)
            for i,e in enumerate(entries):
                check_game(e);uid=name+'/'+e['id'];strata[uid]=name
                pools['train' if i<16 else 'validation' if i<24 else 'blind'].append(uid)
        assert len(set(sum(pools.values(),[])))==96
        write(BATTLE/'fixtures.json',dict(**pools,sources=cases,strata=strata,mode=RULES,map=HOME,night=False,weather='clear'))
    finally:room.close()
    st=dict(round=0,completed_rounds=0,sides={})
    for s,champ,explorer in [('plant',meta['pool']['away'],meta['pool']['explorer']),('zombie',meta['champion'],meta['start_zombie'])]:
        st['sides'][s]=dict(champ=champ,explorer=explorer,hall=[champ],defenses=0,temp=1.,promotions=0,last_suites=[])
    write(BATTLE/'state.json',st)
    write(RUN/'ready.json',dict(build=build['version'],rule=RULES,map=HOME,night=False,weather='clear',train=32,validation=16,
          blind=48,previous_champions={s:v['champ_sha'] for s,v in frozen.items()},draft_parent=cfg['draft_sha'],
          fixture_sha=sha(BATTLE/'fixtures.json'),mutants_per_seat=4,stable_defenses_per_cooling=3))

if __name__=='__main__':prepare()
