"""Prespecified second stratum of ranked draft fixtures using archived playable deck families."""
from ranked_special_setup import OUT, HOME, SIDES, Room, DraftNet, draft, read, write, sha
from ranked_corpus import create
from league_data import NEW,OLD_CORPUS

SUPPORT=OUT/'playable'

def prepare():
    if (OUT/'playable.json').exists():return
    refs=[e for p in (NEW,OLD_CORPUS) for e in read(p/'index.json')['entries'] if e['map']==HOME]
    room=Room()
    try:
        model=DraftNet(room.catalog);scenarios=[];rejects=[]
        for i in range(160):
            n=len(scenarios);night=bool(n%2);templates=[e for e in refs if bool(e['night'])==night]
            # Draw both archetypes independently so their original matchup cannot leak into this opening.
            p=templates[(i*7+3)%len(templates)];z=templates[(i*13+5)%len(templates)]
            template={s:e['decks'][s] for s,e in zip(SIDES,(p,z))}
            sc,_=draft(room,dict.fromkeys(SIDES,model),8400000+i,HOME,night,width=256,combat_template=template)
            if sc['battle_error']:rejects.append(sc);continue
            sc['template_overlap']={s:len(set(sc['decks'][s])&set(template[s])) for s in SIDES}
            scenarios.append(sc)
            if len(scenarios)==48:break
        assert len(scenarios)==48
    finally:room.close()
    entries=create(SUPPORT,scenarios,3)
    ids=['playable/'+e['id'] for e in entries]
    write(OUT/'playable.json',dict(train=ids[:16],validation=ids[16:24],blind=ids[24:],
          index_sha=sha(SUPPORT/'index.json'),unstartable=len(rejects),blind_seeds=[e['seed'] for e in entries[24:]]))

if __name__=='__main__':prepare()
