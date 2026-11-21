"""Independent second home cohort with both challengers locked before drafting."""
import sys
from pathlib import Path
from option_study import ROOT,R,H,EXPORT,OLD_P,inputs_ok,read,write,sha,cmd
from option_games import Game,MODELS,batch,extend
from option_fit import paired_result

CONFIRM=ROOT/'confirm'

def prepare():
    inputs_ok();CONFIRM.mkdir(exist_ok=True)
    z=read(ROOT/'zombie-frozen.json');p=read(ROOT/'plant-trial-frozen.json')
    plan=dict(zombie=z['sha256'],plant=p['sha256'],n=18,opponents=['r','h','b'],
              samples='18 additional day/night balanced openings, each complete deck unseen for its own seat in historical material, primary training, validation and first test. New drafting seeds. No model or threshold changes.',
              comparison='Separately report paired returns vs immediate parents for each cohort. Repeat same predeclared stability criteria; never select by the second cohort.')
    target=CONFIRM/'plan.json'
    if target.exists():assert read(target)==plan
    else:write(target,plan)
    if (CONFIRM/'ready.json').exists():
        assert read(CONFIRM/'ready.json')['corpus']==sha(CONFIRM/'plain/index.json')
        return
    known=[set(),set()];past_seeds=set()
    def pair(row):return tuple(tuple(sorted(row['decks'][s])) for s in ('plant','zombie'))
    s=read(ROOT/'splits.json')
    for path in [R/f for f in s['past_indexes']]+[ROOT/'plain/index.json']:
        for row in read(path)['entries']:
            if row.get('map')!='家院' or 'decks' not in row:continue
            past_seeds.add(row['seed'])
            for d,seen in zip(pair(row),known):seen.add(d)
    pool=[]
    for b in range(8):
        draft=CONFIRM/f'draft-{b}.json'
        if not draft.exists():cmd(EXPORT/'deck73_corpus.exe',draft,3,16,1570000+b*10000,71533+b*777)
        pool.extend(row for row in read(draft) if row['map']=='家院' and not row.get('invalid') and not row.get('error') and row['seed'] not in past_seeds)
        chosen=[];used=[set(v) for v in known]
        for dark in [False,True]*9:
            opts=[row for row in pool if row['night']==dark and all(d not in seen for d,seen in zip(pair(row),used))]
            if not opts:break
            x=min(opts,key=lambda row:row['seed']);chosen.append(x)
            for d,seen in zip(pair(x),used):seen.add(d)
        if len(chosen)==18:break
    assert len(chosen)==len({x['seed'] for x in chosen})==18
    assert all(len({pair(x)[j] for x in chosen})==18 for j in (0,1))
    write(CONFIRM/'scenarios.json',chosen)
    if not (CONFIRM/'corpus/index.json').exists():cmd(sys.executable,H/'export_corpus.py',CONFIRM/'scenarios.json',CONFIRM/'corpus',3,EXPORT/'cold73_export.exe')
    if not (CONFIRM/'plain/index.json').exists():cmd(sys.executable,H/'materialize_corpus.py',CONFIRM/'corpus',CONFIRM/'plain')
    entries=read(CONFIRM/'plain/index.json')['entries']
    assert [pair(e) for e in entries]==[pair(x) for x in chosen]
    write(CONFIRM/'ready.json',dict(ids=[e['id'] for e in entries],corpus=sha(CONFIRM/'plain/index.json'),
         excluded_home_decks_each_side=list(map(len,known)),fresh_plant_decks=18,fresh_zombie_decks=18))

def test():
    inputs_ok();ids=read(CONFIRM/'ready.json')['ids'];z=Path(read(ROOT/'zombie-frozen.json')['model'])
    p=Path(read(ROOT/'plant-trial-frozen.json')['model']);plan=read(CONFIRM/'plan.json')
    assert (sha(z),sha(p))==(plan['zombie'],plan['plant'])
    assert sha(CONFIRM/'plain/index.json')==read(CONFIRM/'ready.json')['corpus']
    corpus=CONFIRM/'plain';groups={'zombie':{},'plant':{}}
    for o in plan['opponents']:
        rival=MODELS[o]
        groups['zombie'][o]=[(Game(i,rival,corpus=corpus),Game(i,rival,policy=z,corpus=corpus)) for i in ids]
        groups['plant'][o]=[(Game(i,OLD_P,rival,None,corpus=corpus),Game(i,p,rival,None,corpus=corpus)) for i in ids]
    batch('independent confirmation on 18 further home openings',[g for s in groups.values() for ab in s.values() for pair in ab for g in pair])
    report={}
    for side,gs in groups.items():
        r=paired_result(gs,side,ids)
        r['extensions']=extend((a,b,side) for rows in gs.values() for a,b in rows)
        report[side]=r
    write(CONFIRM/'results.json',dict(frozen=plan,comparisons=report))
