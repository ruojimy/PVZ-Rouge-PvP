"""2026-11-20 v2 run: daytime home, ranked seven slots, three deck strata for deck generalisation.

Strata (all drafted by the native Room under its own ban/pick schedule):
  free     - both seats sample the parent draft heads with the old .55 Gumbel noise (stress decks)
  drafted  - both seats sample the merged v2 draft heads at .25 noise (decks a competent drafter produces)
  template - the historical playable decks bias the draft (as in the day league)
Each stratum: 16 train, 8 validation, 16 blind. Deck sets never repeat earlier pools.
"""
import os,sys
from pathlib import Path
import numpy as np

H=Path(__file__).resolve().parent
R=H.parents[1]
ROOT=R/'test_results/ai-nn-home-options-20261118'
DAY=ROOT/'ranked-day-league-20261120'
RUN=ROOT/'ranked-v2-20261120'
STRATA=('free','drafted','template')
SPLIT=dict(train=16,validation=8,blind=16)

def merged_parent():
    """Plant draft head restarts from the pre-regression parent; zombie keeps its day-league frozen head."""
    from overnight_common import read
    day=read(DAY/'profile.json');out=RUN/'draft-parent.npz'
    if out.exists():return out
    plant=np.load(day['draft_parent']);zombie=np.load(DAY/'draft/frozen.npz')
    assert str(plant['keys'])==str(zombie['keys'])
    arrays={k:zombie[k].copy() for k in ('embed','w','head','bias')}
    for k in arrays:arrays[k][0]=plant[k][0]          # index 0 == plant seat (SIDES order)
    tmp=out.with_suffix('.partial')
    with tmp.open('wb') as f:np.savez_compressed(f,**arrays,keys=str(zombie['keys']))
    os.replace(tmp,out);return out

def profile(deadline):
    from overnight_common import read,write
    from league_data import sha
    assert 'ranked_draft' not in sys.modules,'ranked_draft must be imported only after the v2 profile exists'
    RUN.mkdir(exist_ok=True)
    base=read(DAY/'profile.json')
    parent=merged_parent()
    cfg={**base,'output':str(RUN),'seed_offset':21500000,'deadline':deadline,'draft_parent':str(parent),
         'draft_sha':sha(parent),'draft_v2':True,'draft_lanes':4,'strata':list(STRATA),'v2':True}
    path=RUN/'profile.json'
    if path.exists():
        old=read(path);assert {k:v for k,v in old.items() if k!='deadline'}=={k:v for k,v in cfg.items() if k!='deadline'}
    else:write(path,cfg)
    return path

def prepare():
    os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
    from ranked_draft import BATTLE,ROOM,Room,DraftNet,HOME,SIDES,RULES,check_game,draft,read,write
    assert BATTLE==RUN/'battle' and ROOM.parent==Path(read(RUN/'profile.json')['native_dir']),(BATTLE,ROOM)
    from ranked_corpus import create
    from league_data import OLD_CORPUS,NEW,sha
    if (RUN/'ready.json').exists():return
    cfg=read(RUN/'profile.json');BATTLE.mkdir(parents=True,exist_ok=True)
    meta=read(DAY/'battle/opponents.json');write(BATTLE/'opponents.json',meta)
    refs=[e for c in [NEW,OLD_CORPUS] for e in read(c/'index.json')['entries'] if e['map']==HOME and not e['night']]
    previous=[e for root in [ROOT/'ranked-seven-20261120',ROOT/'ranked-seven-20261119'] for name in ['plain','playable']
              if (root/'battle'/name/'index.json').exists() for e in read(root/'battle'/name/'index.json')['entries']]
    previous+=[e for name in ('free','template') for e in read(DAY/'battle'/name/'index.json')['entries']]
    known={s:{tuple(sorted(e['decks'][s])) for e in previous} for s in SIDES}
    seen={e['seed'] for e in previous}
    need=sum(SPLIT.values())
    room=Room()
    try:
        old=DraftNet(room.catalog).load(Path(read(DAY/'profile.json')['draft_parent']))
        new=DraftNet(room.catalog).load(Path(cfg['draft_parent']))
        cases={};pools={k:[] for k in SPLIT};strata={}
        for name,start in [('free',33400000),('drafted',33500000),('template',33600000)]:
            selected=[];rejects=0;net=new if name=='drafted' else old
            for i in range(800):
                seed=start+i
                templ={s:refs[(i*k+b)%len(refs)]['decks'][s] for s,k,b in zip(SIDES,(11,17),(3,9))} if name=='template' else None
                sc,_=draft(room,dict.fromkeys(SIDES,net),seed,HOME,False,weather='clear',width=256,combat_template=templ,
                           noise_scale=.25 if name=='drafted' else .55)
                decks={s:tuple(sorted(sc['decks'][s])) for s in SIDES}
                if sc['battle_error'] or seed in seen or any(decks[s] in known[s] for s in SIDES):
                    rejects+=1;continue
                for s in SIDES:known[s].add(decks[s])
                seen.add(seed);selected.append(sc)
                if len(selected)==need:break
            assert len(selected)==need,(name,len(selected))
            root=BATTLE/name
            entries=create(root,selected,3)
            cases[name]=dict(path=str(root),sha=sha(root/'index.json'),rejected=rejects)
            for i,e in enumerate(entries):
                check_game(e);uid=name+'/'+e['id'];strata[uid]=name
                split='train' if i<SPLIT['train'] else 'validation' if i<SPLIT['train']+SPLIT['validation'] else 'blind'
                pools[split].append(uid)
        write(BATTLE/'fixtures.json',dict(**pools,sources=cases,strata=strata,mode=RULES,map=HOME,night=False,weather='clear'))
    finally:room.close()
    write(RUN/'ready.json',dict(build=cfg['version'],rule=RULES,map=HOME,night=False,weather='clear',split=SPLIT,strata=STRATA,
          fixture_sha=sha(BATTLE/'fixtures.json'),draft_parent=cfg['draft_sha']))

if __name__=='__main__':
    profile(float(sys.argv[1]));prepare()
