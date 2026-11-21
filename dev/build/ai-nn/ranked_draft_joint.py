"""Complete the two-by-two frozen draft comparison on the same 24 prespecified seeds."""
from ranked_draft_train import *

def main():
    out=DRAFT/'joint.json'
    if out.exists():return
    frozen=DRAFT/'frozen.npz';room=Room()
    try:net=DraftNet(room.catalog).load(frozen)
    finally:room.close()
    with sqlite3.connect((DRAFT/'draft.sqlite').as_uri()+'?mode=ro',uri=True) as db:checks=rows(db,'blind')
    groups={}
    for d in checks:groups.setdefault(d['setup']['seed'],{})[d['seat']]=d
    def run(group):
        a,b=[group[s] for s in SIDES];room=Room()
        try:sc,_=draft(room,dict.fromkeys(SIDES,net),**a['setup'],greedy=True,width=256)
        finally:room.close()
        item=dict(seed=sc['seed'],setup=a['setup'],controllers=a['controllers'],decks=sc['decks'])
        if sc['battle_error'] or 'arms' not in a or 'arms' not in b:return dict(**item,unstartable=True)
        assert a['controllers']==b['controllers'] and a['arms'][0]['log']==b['arms'][0]['log']
        result=None
        for existing in (a,b):
            for sc0,r in zip(existing['drafts'],existing['arms']):
                if sc0['decks']==sc['decks'] and sc0['bans']==sc['bans']:result=r
        if result is None:
            with tempfile.TemporaryDirectory(prefix='joint',dir=DRAFT/'scratch') as temp:
                result=fight(sc,a['i'],Path(temp)/'a')
        return dict(**item,initial=a['arms'][0],plant_only=a['arms'][1],zombie_only=b['arms'][1],both=result)
    with ThreadPoolExecutor(3) as pool:data=list(pool.map(run,groups.values()))
    summary={}
    for label in ('initial','plant_only','zombie_only','both'):
        results=[d[label] for d in data if label in d]
        summary[label]=dict(games=len(results),outcomes=dict(Counter('timeout' if r['timeout'] else r['winner'] for r in results)),
                            mean_seconds=np.mean([r['seconds'] for r in results]))
    write(out,dict(frozen=sha(frozen),summary=summary,results=data))

if __name__=='__main__':main()
