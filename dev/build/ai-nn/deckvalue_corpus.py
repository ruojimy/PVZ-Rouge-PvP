"""Deck-value corpus (2026-11-20 pivot): many native ranked-seven drafts, each played once r22 vs r22.

Only the final decks, bans, draft history and the game outcome are kept; the battle controller is the production
AI on both seats, so the label is "how good is this matchup when r22 plays it".  Decks come from a mixture of
draft policies chosen independently per seat (near-uniform legal play, the v2 draft head sampled warm/cold, and
later the value-search drafter), so the value net sees both stress decks and decks a competent drafter makes.

Usage:  python deckvalue_corpus.py setup            (once: profile + head snapshot)
        python deckvalue_corpus.py run [lanes]      (until <RUN>/STOP; resumable)
        python deckvalue_corpus.py smoke            (two games, prints timing)
"""
import os,sys,json,time,zlib,sqlite3,shutil,tempfile,random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED

H=Path(__file__).resolve().parent
R=H.parents[1]
ROOT=R/'test_results/ai-nn-home-options-20261118'
LEGACY=ROOT/'deck-value-20261120'
RUN=Path(os.environ['DV_RUN']) if os.environ.get('DV_RUN') else LEGACY   # PvP75 run: deck-value-pvp75-20261121
V2=ROOT/'ranked-v2-20261120'
SEED0=41000000

def setup():
    sys.path.insert(0,str(H))
    from overnight_common import read,write
    RUN.mkdir(exist_ok=True)
    base=read(V2/'profile.json')
    cfg={k:v for k,v in base.items() if k not in ('strata','v2','draft_lanes','battle_lanes','run_limit_bytes','deadline')}
    cfg.update(output=str(RUN),seed_offset=SEED0,draft_v2=True,deadline=None,purpose='deck-value corpus, r22 vs r22')
    if not (RUN/'profile.json').exists():write(RUN/'profile.json',cfg)
    head=RUN/'draft-head.npz'
    if not head.exists():shutil.copyfile(V2/'draft/current.npz',head)

def setup75():
    """PvP75 r3 run: tools relinked by ranked_pvp75_native.py, game data snapshotted into the run (the release folder
    is replaced on every release).  There is no PvP75 draft head yet, so head policies are not used."""
    sys.path.insert(0,str(H))
    from overnight_common import read,write
    run=ROOT/'deck-value-pvp75-20261121';run.mkdir(exist_ok=True)
    nb=read(ROOT/'ranked-pvp75-20261121/native-build.json');rel=read(R/'dist/latest-native-release.json')
    assert rel['revision']=='pvp75-r3' and nb['version']==rel['version']
    data=run/'data'
    if not (data/'extract').exists():shutil.copytree(Path(rel['release'])/'extract',data/'extract')
    base=read(LEGACY/'profile.json')
    cfg={**base,'version':nb['version'],'output':str(run),'data_root':str(data),'native_dir':str(ROOT/'ranked-pvp75-20261121/native'),
         'seed_offset':SEED0,'purpose':'deck-value corpus, PvP75 r3, r22 vs r22','native_build':nb['fingerprint']}
    cfg.pop('draft_parent',None);cfg.pop('draft_sha',None)
    if not (run/'profile.json').exists():write(run/'profile.json',cfg)
    print(run)

if sys.argv[1:2]==['setup']:setup();sys.exit()
if sys.argv[1:2]==['setup75']:setup75();sys.exit()
os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
from ranked_draft import Room,DraftNet,draft,SIDES,HOME,PROFILE,read,write
from ranked_draft_train import fight
from league_data import local
assert Path(PROFILE['output'])==RUN

# (plant weight, zombie weight, noise scale).  'template' biases picks toward a historical playable home deck of
# that seat (the native mask still decides legality) - random drafts almost never give the plant seat a win.
POLICIES={'uniform':(.20,.35,50.),'head-warm':(.20,.30,.55),'head-cold':(.15,.20,.25),'template':(.45,.15,.55)}
FIRST_TEMPLATE_ID=200     # ids below this were generated before the template policy existed
FIRST_PRIOR_ID=15400      # from here (2026-11-21 09:40) seats may also draft with the value-derived card prior
PRIOR_POLICIES={'uniform':(.10,.25),'head-warm':(.10,.20),'head-cold':(.10,.15),'template':(.35,.10),'prior':(.35,.30)}

P75_BASE={'uniform':(.45,.60),'template':(.55,.40)}
P75_PRIOR={'uniform':(.20,.35),'template':(.40,.25),'prior':(.40,.40)}

def policy_for(i):
    rng=random.Random(SEED0+i*7+3)
    if RUN!=LEGACY:
        table=P75_PRIOR if (RUN/'prior.json').exists() else P75_BASE
        names=list(table)
        return {s:rng.choices(names,[table[n][j] for n in names])[0] for j,s in enumerate(SIDES)}
    names=list(POLICIES)
    if i<FIRST_TEMPLATE_ID:
        old={'uniform':.4,'head-warm':.35,'head-cold':.25}
        return {s:rng.choices(list(old),list(old.values()))[0] for s in SIDES}
    if i>=FIRST_PRIOR_ID and (RUN/'prior.json').exists():
        names=list(PRIOR_POLICIES)
        return {s:rng.choices(names,[PRIOR_POLICIES[n][j] for n in names])[0] for j,s in enumerate(SIDES)}
    return {s:rng.choices(names,[POLICIES[n][j] for n in names])[0] for j,s in enumerate(SIDES)}

_refs=None
def references():
    global _refs
    if _refs is None:
        from league_data import OLD_CORPUS,NEW
        _refs=[e['decks'] for c in [NEW,OLD_CORPUS] for e in read(c/'index.json')['entries'] if e['map']==HOME and not e['night']]
    return _refs

def fight_once(sc,folder):
    """One regular-length r22 vs r22 game, no 1200 s continuation (the value target is the regular-time true win)."""
    from ranked_corpus import create
    from ranked_day_league import combat_game
    from option_games import play,trace
    case=folder/'c';create(case,[sc]);(folder/'temp').mkdir()
    g=combat_game(case,'000','r22','r22',folder)
    play(g);t=trace(g)
    actions={s:[a['time'] for a in t['activity'] if a['kind']=='deploy' and a['side']==s] for s in SIDES}
    return dict(winner=(t['result'] or {}).get('winner'),timeout=t['timeout'],seconds=t['time'],hp=t['hp'],actions=actions,troops=[])

def outcome(r):
    """Regular-time result: 'plant' / 'zombie' true win, else 'timeout' (draws included)."""
    if r['timeout'] or r['winner'] in (None,'draw'):return 'timeout'
    return r['winner']

def label(r):
    """Plant-side value target: win 1, loss 0, unresolved .5; a timeout uses its 1200 s continuation."""
    end=r['extension'] if r['timeout'] and r.get('extension') else r
    if end['timeout'] or end['winner'] in (None,'draw'):return .5
    return 1. if end['winner']=='plant' else 0.

def one(i,head_path):
    room=Room()
    try:
        pol=policy_for(i);seed=SEED0+i
        head=DraftNet(room.catalog).load(head_path) if head_path.exists() else None;template=None
        if 'prior' in pol.values():
            import deckvalue_search as ds
            pr=read(RUN/'prior.json')['prior'];mapping={'prior':('prior',pr,.1),'uniform':('prior',{},1.),
                 'head-warm':('head',head,False),'head-cold':('head',head,False),'template':('prior',pr,.1)}
            sc,_=ds.run_draft(room,seed,{s:mapping[pol[s]] for s in SIDES})
            template=None
        else:sc=None
        uni=DraftNet(room.catalog)
        # draft() takes one noise scale per call; mix seats by giving the uniform seat a zeroed scorer.
        for k in ('w','head','bias'):getattr(uni,k)[...]=0
        nets={s:(uni if pol[s]=='uniform' or head is None else head) for s in SIDES}
        scales={POLICIES[pol[s]][2] for s in SIDES if pol[s] in POLICIES and pol[s]!='uniform'}
        scale=min(scales) if scales else 1.
        if sc is not None:pass
        elif 'template' in pol.values():
            refs=references();rng=random.Random(seed)
            template={s:(refs[rng.randrange(len(refs))][s] if pol[s]=='template' else []) for s in SIDES}
        if sc is None:sc,_=draft(room,nets,seed,HOME,False,weather='clear',width=256,noise_scale=scale,combat_template=template)
    finally:room.close()
    row=dict(i=i,seed=seed,policy=pol,template=template,decks=sc['decks'],bans=sc['bans'],
             history=[[h['side'],h['kind'],h['card']] for h in sc['draft_history']],terrain=sc['terrain_hash'])
    if sc['battle_error']:
        row['unstartable']=sc['battle_error'];return row
    (RUN/'scratch').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='g',dir=RUN/'scratch') as tmp:
        r=fight_once(sc,Path(tmp)/'a')
    row['result']={k:r[k] for k in ('winner','timeout','seconds','hp','extension') if k in r}
    row['deploys']={s:len(r['actions'][s]) for s in SIDES};row['troops']=len(r['troops'])
    row['y']=label(r);row['outcome']=outcome(r)
    return row

def open_db():
    db=sqlite3.connect(RUN/'corpus.sqlite',timeout=60)
    db.execute('pragma journal_mode=wal')
    db.execute('create table if not exists games(id integer primary key,data blob not null)')
    db.commit();return db

def load_rows(path=None):
    db=sqlite3.connect(path or RUN/'corpus.sqlite',timeout=60)
    try:return [json.loads(zlib.decompress(b)) for (b,) in db.execute('select data from games order by id')]
    finally:db.close()

def run(lanes):
    db=open_db();head=RUN/'draft-head.npz'
    done={r[0] for r in db.execute('select id from games')}
    nxt=0;pending={};t0=time.time();made=0;streak=0
    def status(phase):
        n=db.execute('select count(*) from games').fetchone()[0]
        write(RUN/'corpus-status.json',dict(phase=phase,games=n,new=made,lanes=lanes,updated=local(time.time()),
              rate_per_hour=made*3600/max(1,time.time()-t0)))
    with ThreadPoolExecutor(lanes) as pool:
        while not (RUN/'STOP').exists():
            if shutil.disk_usage(RUN).free<24*2**30:status('磁盘保护已停止');break
            while len(pending)<lanes:
                while nxt in done:nxt+=1
                pending[pool.submit(one,nxt,head)]=nxt;nxt+=1
            fin,_=wait(pending,timeout=30,return_when=FIRST_COMPLETED)
            for f in fin:
                i=pending.pop(f)
                try:row=f.result();streak=0
                except Exception as e:
                    row=dict(i=i,error=repr(e)[:400]);streak+=1
                if streak>=40:
                    # A broken environment (missing data root, bad binary) must not flood the corpus with error rows.
                    status('连续出错已停止');(RUN/'STOP').write_text(row['error'],'utf8');return
                with db:db.execute('insert or replace into games values(?,?)',(i,zlib.compress(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode(),6)))
                made+=1
            status('生成中')
        for f in pending:f.cancel()
    status('已停止')

if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'run'
    if cmd=='smoke':
        t=time.time()
        for i in (900000000-SEED0+1,900000000-SEED0+2):
            row=one(i,RUN/'draft-head.npz');print(json.dumps({k:row.get(k) for k in ('policy','decks','y','result','unstartable')},ensure_ascii=False)[:900])
            print('elapsed',round(time.time()-t,1));t=time.time()
    else:
        import msvcrt
        with (RUN/'corpus.lock').open('a+b') as lock:
            if not lock.tell():lock.write(b'x');lock.flush()
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:sys.exit('corpus generator already running')
            run(int(sys.argv[2]) if len(sys.argv)>2 else 12)
