"""Unattended deck-value loop: refit the value ensemble as the corpus grows, run paired blind tests at fixed sizes.
Stop with <RUN>/STOP_LOOP.  Each blind uses its own fresh seed block, fixed before any result is seen."""
import json,time,sys,traceback
from pathlib import Path
H=Path(__file__).resolve().parent
RUN=H.parents[1]/'test_results/ai-nn-home-options-20261118/deck-value-20261120'
FITS=[1500,3000,6000,10000,15000,22000,30000]
BLINDS={3000:('blind-1',49000000),10000:('blind-2',49100000)}
CROSS={15000:('cross-1',49300000),30000:('cross-2',49400000)}    # opponent = fast prior drafter

def games():
    try:return json.loads((RUN/'corpus-status.json').read_text('utf8'))['games']
    except Exception:return 0

def log(**k):
    with (RUN/'loop.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S'),**k),ensure_ascii=False)+'\n')

def main():
    import deckvalue_model as dm
    state_p=RUN/'loop-state.json'
    state=json.loads(state_p.read_text('utf8')) if state_p.exists() else dict(fits=[],blinds=[])
    while not (RUN/'STOP_LOOP').exists():
        n=games()
        todo=[f for f in FITS if f<=n and f not in state['fits']]
        if todo:
            dm.fit(5,60);state['fits'].extend(todo);log(event='fit',games=n)
            import deckvalue_search as ds
            ds.save_prior();log(event='prior',games=n)
            state_p.write_text(json.dumps(state),'utf8')
            for size,(tag,base) in BLINDS.items():
                if size<=n and tag not in state['blinds']:
                    import deckvalue_search as ds
                    log(event='blind-start',tag=tag,games=n)
                    ds.blind(96,6,tag,base=base);state['blinds'].append(tag);log(event='blind-done',tag=tag)
                    state_p.write_text(json.dumps(state),'utf8')
            for size,(tag,base) in CROSS.items():
                if size<=n and tag not in state['blinds'] and not (RUN/tag/'summary.json').exists():
                    import deckvalue_search as ds
                    log(event='cross-start',tag=tag,games=n)
                    ds.cross(96,6,tag,base);state['blinds'].append(tag);log(event='cross-done',tag=tag)
                    state_p.write_text(json.dumps(state),'utf8')
        time.sleep(60)

if __name__=='__main__':
    try:main()
    except Exception:log(event='crash',trace=traceback.format_exc());raise
