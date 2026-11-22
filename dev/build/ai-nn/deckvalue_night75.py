"""PvP75 r3 overnight run (2026-11-21 22:xx -> 2026-11-22 09:00), unattended.

  corpus     separate process, r22 vs r22 regular-time games (uniform / template / value-prior drafts)
  fits       value ensemble refit at 1500/3000/6000/10000/15000 games, card prior refreshed after each fit
  collect    from the 3000-game fit until 05:00: searcher drafts one seat, every searched decision is stored
  distill    05:00: final value fit, distilled fast drafter fit
  evaluate   fresh seeds, opponent = value-prior drafter; tested seat drafts with uniform / prior / distilled / search;
             every matchup is played r22 vs r22 with the 1200 s continuation on timeout
Stop early: <RUN>/STOP_NIGHT.
"""
import os,sys,json,time,threading,traceback,subprocess,tempfile,datetime
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

H=Path(__file__).resolve().parent
RUN=H.parents[1]/'test_results/ai-nn-home-options-20261118/deck-value-pvp75-20261121'
os.environ['DV_RUN']=str(RUN)
os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
import numpy as np
import deckvalue_model as dm
import deckvalue_search as ds
import deckvalue_distill as dd
from ranked_draft import Room,SIDES,read,write
assert dm.RUN==RUN and ds.RUN==RUN and dd.RUN==RUN

def at(day,hour):
    return datetime.datetime(2026,11,day,hour,0,tzinfo=datetime.timezone(datetime.timedelta(hours=8))).timestamp()
END=at(22,9);COLLECT_END=at(22,5)
FITS=[1500,3000,6000,10000,15000,22000]
CORPUS_LANES=5;SEARCH_LANES=3      # 11-21 22:23 second thermal blackout: keep total load low
EVAL0=49600000;EVAL_N=72

def log(**k):
    with (RUN/'night.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'),**k),ensure_ascii=False)+'\n')

def games():
    try:return json.loads((RUN/'corpus-status.json').read_text('utf8'))['games']
    except Exception:return 0

def start_corpus():
    env={**os.environ,'DV_RUN':str(RUN),'PYTHONUTF8':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    out=open(RUN/'corpus.log','ab')
    return subprocess.Popen([sys.executable,'-X','utf8','-u',str(H/'deckvalue_corpus.py'),'run',str(CORPUS_LANES)],cwd=H,env=env,
                            stdout=out,stderr=out,stdin=subprocess.DEVNULL,creationflags=0x08000000|0x00004000)

# ---------------- evaluation ----------------
def label(r,side):
    if r['timeout']:
        e=r.get('extension') or {}
        return 'T' if e.get('timeout') or e.get('winner') in (None,'draw') else ('t' if e['winner']==side else 'l')
    return 'W' if r['winner']==side else 'L' if r['winner'] not in (None,'draw') else 'T'

ARMS=('uniform','prior','distill','search')

def eval_case(j,value,prior,fast,out):
    from ranked_draft_train import fight
    path=out/f'{j:04d}.json'
    if path.exists():return read(path)
    seat=SIDES[j%2];foe=SIDES[1-j%2];seed=EVAL0+j
    room=Room();searcher=ds.Searcher(value,prior)
    try:
        pol={'uniform':('prior',{},1.),'prior':('prior',prior,.04),'distill':('distill',fast),'search':('search',searcher)}
        drafts={};t0=time.time();secs={}
        for a in ARMS:
            t=time.time();sc,_=ds.run_draft(room,seed,{seat:pol[a],foe:('prior',prior,.04)});secs[a]=time.time()-t
            drafts[a]=sc
    finally:room.close();searcher.close()
    rec=dict(j=j,seat=seat,seed=seed,decks={a:drafts[a]['decks'] for a in ARMS},draft_seconds=secs,
             predicted={a:float(value([drafts[a]['decks']])[0]) for a in ARMS},errors={a:drafts[a]['battle_error'] for a in ARMS})
    arms={};seen={}
    (RUN/'scratch').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='e',dir=RUN/'scratch') as tmp:
        for n,a in enumerate(ARMS):
            if drafts[a]['battle_error']:continue
            key=json.dumps(drafts[a]['decks'],sort_keys=True,ensure_ascii=False)
            if key not in seen:
                r=fight(drafts[a],j,Path(tmp)/f'a{n}',('r22','r22'))
                seen[key]={k:r[k] for k in ('winner','timeout','seconds','hp','extension') if k in r}|{'actions':r['actions']}
            arms[a]=seen[key]
    rec['arms']=arms
    write(path,rec);return rec

def summarize(recs):
    out={}
    for side in SIDES:
        rs=[r for r in recs if r['seat']==side and all(a in r['arms'] for a in ARMS)]
        s=dict(cases=len(rs))
        for a in ARMS:
            labs=Counter(label(r['arms'][a],side) for r in rs)
            s[a]=dict(outcomes=dict(labs),true_wins=labs['W'],mean_seconds=float(np.mean([r['arms'][a]['seconds'] for r in rs])) if rs else 0,
                      distinct_decks=len({tuple(sorted(r['decks'][a][side])) for r in rs}),
                      mean_predicted_plant_score=float(np.mean([r['predicted'][a] for r in rs])) if rs else 0)
        for x,y in (('prior','search'),('prior','distill'),('distill','search'),('uniform','search')):
            s[x+'>'+y]=dict(Counter(label(r['arms'][x],side)+'>'+label(r['arms'][y],side) for r in rs))
        # Deployments per minute over each case's common window (shortest arm), both seats.
        tempo={a:[0,0] for a in ARMS};window=0
        for r in rs:
            t=min(r['arms'][a]['seconds'] for a in ARMS);window+=t
            for a in ARMS:
                for k,side2 in enumerate(SIDES):tempo[a][k]+=sum(x<=t for x in r['arms'][a]['actions'][side2])
        s['deploys_per_minute_plant_zombie']={a:[round(v*60/max(1,window),2) for v in tempo[a]] for a in ARMS}
        out[side]=s
    return out

def evaluate():
    import ranked_draft_train as rdt          # legacy combat catalog lacks the PvP75 cards (11-22 05:10 KeyError)
    for k,c in dm.catalog()['cards'].items():rdt.COMBAT_CATALOG.setdefault(k,c)
    out=RUN/'eval-1';out.mkdir(exist_ok=True)
    value=ds.Value();prior=ds.corpus_prior(value);fast=dd.FastDrafter()
    write(out/'setup.json',dict(n=EVAL_N,seed_base=EVAL0,arms=ARMS,opponent='value-prior drafter, noise .04',
          value=dm.RUN.joinpath('models/value-latest.pt').as_posix(),value_report=read(sorted((RUN/'models').glob('report-*.json'))[-1]),
          distill_report=read(RUN/'models/distill-report.json')))
    recs=[]
    with ThreadPoolExecutor(SEARCH_LANES) as pool:
        for r in pool.map(lambda j:eval_case(j,value,prior,fast,out),range(EVAL_N)):
            recs.append(r)
            if len(recs)%12==0:write(out/'summary.json',dict(partial=len(recs),**summarize(recs)))
    write(out/'summary.json',summarize(recs))

# ---------------- main ----------------
def main():
    state_p=RUN/'night-state.json'
    state=read(state_p) if state_p.exists() else dict(fits=[],collect_done=False,distilled=False,evaluated=False)
    def save():write(state_p,state)
    corpus=start_corpus();log(event='corpus-start',pid=corpus.pid)
    collector=None
    try:
        while time.time()<END and not (RUN/'STOP_NIGHT').exists():
            if corpus.poll() is not None and not (RUN/'STOP').exists():
                corpus=start_corpus();log(event='corpus-restart',pid=corpus.pid)
            n=games()
            todo=[f for f in FITS if f<=n and f not in state['fits']]
            if todo and not state['distilled']:
                dm.fit(5,60);ds.save_prior();state['fits']+=todo;state['last_fit_games']=n;save();log(event='fit',games=n)
            if (collector is None and not state['collect_done'] and 3000 in state['fits'] and time.time()<COLLECT_END):
                collector=threading.Thread(target=lambda:dd.collect(SEARCH_LANES,COLLECT_END),daemon=True);collector.start()
                log(event='collect-start')
            if time.time()>=COLLECT_END and not state['distilled']:
                if collector is not None:collector.join();state['collect_done']=True;save()
                if 3000 not in state['fits']:
                    log(event='skip-distill',reason='corpus below 3000 games at 06:00');state['distilled']=True;state['evaluated']=True;save();continue
                if games()-state.get('last_fit_games',0)>=1000:
                    dm.fit(5,60);ds.save_prior();state['last_fit_games']=games();log(event='fit',games=games())
                dd.fit();state['distilled']=True;save();log(event='distilled',report=read(RUN/'models/distill-report.json'))
            if state['distilled'] and not state['evaluated']:
                log(event='eval-start');evaluate();state['evaluated']=True;save();log(event='eval-done')
            write(RUN/'night-status.json',dict(updated=time.strftime('%Y-%m-%dT%H:%M:%S'),games=n,**state,
                  collecting=collector is not None and collector.is_alive()))
            time.sleep(60)
    except Exception:
        log(event='crash',trace=traceback.format_exc());raise
    finally:
        (RUN/'STOP').write_text('night run finished','utf8')
        (RUN/'STOP_DISTILL').write_text('night run finished','utf8')
        try:corpus.wait(900)
        except Exception:corpus.kill()
        log(event='finished',games=games())

if __name__=='__main__' and sys.argv[1:2]==['eval']:
    log(event='eval-start',mode='standalone');evaluate();log(event='eval-done')
elif __name__=='__main__':
    import msvcrt
    with (RUN/'night.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:sys.exit('night run already active')
        main()
