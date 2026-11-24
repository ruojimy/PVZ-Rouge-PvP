"""PvP75 r3 second night (2026-11-22 21:xx -> 2026-11-23 09:00), unattended: plant drafter distillation.

  collect   until 06:30: plant seat drafts with the value searcher (fresh seeds, draft ids >= 100000); every searched
            decision is stored, the drafted matchup is played once (r22 vs r22) and appended to the value corpus
  refit     value ensemble refit on the grown corpus, card prior refreshed; previous distill kept as distill-1122-0506.pt
  distill   fast drafter refit on all searched decisions (both seats)
  eval-1c   distill arm only, on the eval-1 seeds (same as eval-1b, new weights) - direct comparison with 11-22 morning
  eval-2    fresh seeds 49,700,000+, 72 cases, arms uniform / prior / distill / search, opponent value-prior .04
Stop early: <RUN>/STOP_NIGHT2.  Status: <RUN>/night2-status.json, events: <RUN>/night2.jsonl (phase field per event).
"""
import os,sys,json,time,shutil,tempfile,threading,traceback,datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

H=Path(__file__).resolve().parent
RUN=H.parents[1]/'test_results/ai-nn-home-options-20261118/deck-value-pvp75-20261121'
os.environ['DV_RUN']=str(RUN)
os.environ['PVZ_RANKED_PROFILE']=str(RUN/'profile.json')
import torch
torch.set_num_threads(2)
import deckvalue_night75 as nt
import deckvalue_model as dm
import deckvalue_search as ds
import deckvalue_distill as dd
from ranked_draft import Room,SIDES,read,write
assert dm.RUN==RUN and ds.RUN==RUN and dd.RUN==RUN

def at(day,hour,minute=0):
    return datetime.datetime(2026,11,day,hour,minute,tzinfo=datetime.timezone(datetime.timedelta(hours=8))).timestamp()
END=at(23,9);COLLECT_END=at(23,6,30)
COLLECT_LANES=6;EVAL_LANES=4      # thermal: 11-21 blackouts at 16 lanes; 8 lanes ran clean 11-21/22
START=100000;EVAL2=49700000
STOP=RUN/'STOP_NIGHT2'

def log(**k):
    with (RUN/'night2.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'),**k),ensure_ascii=False)+'\n')

def plant_drafts():
    import sqlite3,zlib
    db=sqlite3.connect(RUN/'distill.sqlite',timeout=60)
    n=db.execute('select count(*) from drafts where id>=?',(START,)).fetchone()[0];db.close();return n

def patch_catalog():
    import ranked_draft_train as rdt          # legacy combat catalog lacks the PvP75 cards (11-22 05:10 KeyError)
    for k,c in dm.catalog()['cards'].items():rdt.COMBAT_CATALOG.setdefault(k,c)
    return rdt

def eval_1c(value,prior,fast):
    rdt=patch_catalog();src=RUN/'eval-1';out=RUN/'eval-1c';out.mkdir(exist_ok=True)
    write(out/'setup.json',dict(note='eval-1 seeds; only the distill arm re-drafted with the night-2 fast drafter (prior top-24)',
          distill_report=read(RUN/'models/distill-report.json')))
    def case(j):
        path=out/f'{j:04d}.json'
        if path.exists():return read(path)
        rec=read(src/f'{j:04d}.json');seat=rec['seat'];foe=SIDES[1-SIDES.index(seat)]
        room=Room()
        try:sc,_=ds.run_draft(room,rec['seed'],{seat:('distill',fast),foe:('prior',prior,.04)})
        finally:room.close()
        rec['decks']['distill']=sc['decks'];rec['predicted']['distill']=float(value([sc['decks']])[0])
        key=json.dumps(sc['decks'],sort_keys=True,ensure_ascii=False)
        same=[a for a in ('uniform','prior','search') if json.dumps(rec['decks'][a],sort_keys=True,ensure_ascii=False)==key]
        if same:rec['arms']['distill']=rec['arms'][same[0]]
        else:
            with tempfile.TemporaryDirectory(prefix='c',dir=RUN/'scratch') as tmp:
                r=rdt.fight(sc,j,Path(tmp)/'d',('r22','r22'))
                rec['arms']['distill']={k:r[k] for k in ('winner','timeout','seconds','hp','extension') if k in r}|{'actions':r['actions']}
        write(path,rec);return rec
    with ThreadPoolExecutor(EVAL_LANES) as pool:recs=list(pool.map(case,range(nt.EVAL_N)))
    write(out/'summary.json',nt.summarize(recs))

def eval_2(value,prior,fast):
    patch_catalog();out=RUN/'eval-2';out.mkdir(exist_ok=True)
    nt.EVAL0=EVAL2                               # eval_case reads the module-level seed base
    write(out/'setup.json',dict(n=nt.EVAL_N,seed_base=EVAL2,arms=nt.ARMS,opponent='value-prior drafter, noise .04',
          distill='prior-restricted top-24 (FastDrafter(prior=...))',value_report=read(sorted((RUN/'models').glob('report-*.json'))[-1]),
          distill_report=read(RUN/'models/distill-report.json')))
    recs=[]
    with ThreadPoolExecutor(EVAL_LANES) as pool:
        for r in pool.map(lambda j:nt.eval_case(j,value,prior,fast,out),range(nt.EVAL_N)):
            recs.append(r)
            if len(recs)%12==0:write(out/'summary.json',dict(partial=len(recs),**nt.summarize(recs)))
            if STOP.exists() or time.time()>END:break
    write(out/'summary.json',nt.summarize(recs) if len(recs)==nt.EVAL_N else dict(partial=len(recs),**nt.summarize(recs)))

def main():
    sp=RUN/'night2-state.json'
    st=read(sp) if sp.exists() else dict(collected=False,refit=False,distilled=False,eval1c=False,eval2=False)
    def save():write(sp,st)
    for f in ('STOP_DISTILL',):(RUN/f).unlink(missing_ok=True)
    (RUN/'scratch').mkdir(exist_ok=True)
    collector=None
    try:
        if not st['collected'] and time.time()<COLLECT_END:
            def run():
                try:dd.collect(COLLECT_LANES,COLLECT_END,side='plant',start=START)
                except Exception:log(phase='collect',event='crash',trace=traceback.format_exc())
            collector=threading.Thread(target=run,daemon=True);collector.start();log(phase='collect',event='start',lanes=COLLECT_LANES)
            while collector.is_alive():
                write(RUN/'night2-status.json',dict(updated=time.strftime('%Y-%m-%dT%H:%M:%S'),phase='collect',plant_drafts=plant_drafts(),**st))
                if STOP.exists():(RUN/'STOP_DISTILL').write_text('night2 stop','utf8')
                collector.join(60)
        st['collected']=True;save();log(phase='collect',event='end',plant_drafts=plant_drafts())
        if STOP.exists():return
        if not st['refit']:
            keep=RUN/'models/distill-1122-0506.pt'
            if not keep.exists():shutil.copy2(RUN/'models/distill-latest.pt',keep);shutil.copy2(RUN/'models/distill-report.json',RUN/'models/distill-report-1122-0506.json')
            dm.fit(5,60);ds.save_prior();st['refit']=True;save()
            log(phase='refit',event='end',report=read(sorted((RUN/'models').glob('report-*.json'))[-1]))
        if not st['distilled']:
            dd.fit();st['distilled']=True;save();log(phase='distill',event='end',report=read(RUN/'models/distill-report.json'))
        value=ds.Value();prior=ds.corpus_prior(value);fast=dd.FastDrafter(prior=prior)
        if not st['eval1c'] and time.time()<END and not STOP.exists():
            write(RUN/'night2-status.json',dict(updated=time.strftime('%Y-%m-%dT%H:%M:%S'),phase='eval-1c',**st))
            eval_1c(value,prior,fast);st['eval1c']=True;save();log(phase='eval-1c',event='end')
        if not st['eval2'] and time.time()<END and not STOP.exists():
            write(RUN/'night2-status.json',dict(updated=time.strftime('%Y-%m-%dT%H:%M:%S'),phase='eval-2',**st))
            eval_2(value,prior,fast);st['eval2']=True;save();log(phase='eval-2',event='end')
    except Exception:
        log(phase='main',event='crash',trace=traceback.format_exc());raise
    finally:
        (RUN/'STOP_DISTILL').write_text('night2 finished','utf8')
        write(RUN/'night2-status.json',dict(updated=time.strftime('%Y-%m-%dT%H:%M:%S'),phase='finished',plant_drafts=plant_drafts(),**st))
        log(phase='main',event='finished')

if __name__=='__main__':
    if sys.argv[1:2]==['eval']:                 # 11-23: machine slept 01:01-09:34; evaluations re-run on request
        END=time.time()+3*3600;log(phase='main',event='eval-rerun')
    import msvcrt
    with (RUN/'night2.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:sys.exit('night2 run already active')
        main()
