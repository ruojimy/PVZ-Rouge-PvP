from ranked_draft import BATTLE as OUT, HOME, SIDES, DraftNet, Room, draft
import ranked_corpus
import zombie_special_setup as old
from zombie_special_setup import EXE, NIGHT, REVIEW, R, ROOT, read, write, sha
from ranked_draft import PROFILE,RUN,NATIVE

if PROFILE:EXE=NATIVE/'position_match.exe'

FRESH=OUT/'plain'

def prepare():
    OUT.mkdir(exist_ok=True,parents=True)
    if (OUT/'fixtures.json').exists():return
    prior=read(old.OUT/'opponents.json')
    for key in ('regression','wins','distance'):prior.pop(key,None)
    prior['preselection']='Frozen plants from the earlier study. Strength and distinct activity are measured again on ranked openings.'
    write(OUT/'opponents.json',prior)
    assert sha(EXE)==read(old.OUT/'build.json')['binary']
    write(OUT/'build.json',read(old.OUT/'build.json'))
    room=Room()
    try:
        net=DraftNet(room.catalog)
        scenarios=[];rejected=[]
        for i in range(192):
            sc=draft(room,dict.fromkeys(SIDES,net),8100000+i,HOME,bool(len(scenarios)%2))[0]
            if sc['battle_error']:rejected.append(sc)
            else:scenarios.append(sc)
            if len(scenarios)==48:break
        assert len(scenarios)==48
        write(OUT/'unstartable-drafts.json',rejected)
    finally:room.close()
    for s in SIDES:assert len({tuple(sorted(sc['decks'][s])) for sc in scenarios})==len(scenarios)
    proof=ranked_corpus.verify(scenarios[0]);write(OUT/'export-proof.json',proof)
    entries=ranked_corpus.create(FRESH,scenarios,3)
    ids=['fresh/'+e['id'] for e in entries]
    write(OUT/'fixtures.json',dict(train=ids[:16],validation=ids[16:24],blind=ids[24:],index_sha=sha(FRESH/'index.json'),
          blind_seeds=[e['seed'] for e in entries[24:]],rules=ranked_corpus.RULES,room=proof['room']))

if __name__=='__main__':prepare()
