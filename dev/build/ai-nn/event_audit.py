"""Recheck game receipts, activated states, distinct commands and preservation of old wins."""
from collections import Counter
from pathlib import Path
from math import tanh

from event_study import OUT,ROOT,R,H,BUILD,LAST,CORPUS,PROGRAM,PARENT,STRONG,PROBE,NATIVE,LIVE,inputs_ok,sha,read,deck
from event_fit import locks,MODELS,historical,scans,g,trace
from option_audit import verify_games
from option_study import size,write

def coverage(rows):
    return dict(encounters=len(rows),openings=len({r['opening'] for r in rows}),real_event_games=sum(r['events']>0 for r in rows),
        multiple_choices=sum(r['multiple_command_samples']>0 for r in rows),
        deploy_or_move=sum(any(r['actions'].get(str(k),0)>0 for k in (1,2,3)) for r in rows),
        reasons={str(k):sum(r['reasons'][str(k)] for r in rows) for k in (1,2,4,8)},
        action_counts={str(k):sum(r['actions'].get(str(k),0) for r in rows) for k in range(4)},
        multiple_grave_samples=sum(r['multiple_grave_samples'] for r in rows),
        multiple_card_samples=sum(r['multiple_card_samples'] for r in rows),
        transitions=dict(Counter(str((r['old'],r['new'])) for r in rows)),
        strength={tag:[sum(r[tag]==v for r in rows if tag in r) for v in (1,0,-1)]
                  for tag in ('old','start','new') if any(tag in r for r in rows)})

def audit():
    inputs_ok();z,p=locks()
    gate=read(OUT/'gate-test.json');assert gate['assertions']==11 and gate['header']==sha(OUT/'native-src/event_policy.inc')
    assert gate['test']==sha(H/'event_gate_test.cpp')
    price=read(OUT/'price-test.json');assert price['assertions']==16 and price['header']==sha(OUT/'live-src/event_policy.inc')
    assert price['test']==sha(OUT/'live-gate-src/event_price_test.cpp')
    parity=read(OUT/'live-parity.json');assert len(parity['pairs'])==2 and parity['binary']==sha(LIVE)
    for file,exe,src in [('build.json',NATIVE,'native-src'),('probe-build.json',PROBE,'probe-src'),('live-build.json',LIVE,'live-src')]:
        b=read(OUT/file)
        assert b['binary']==sha(exe) and all(sha(OUT/src/n)==v for n,v in b['sources'].items())
        assert all(sha(BUILD/'Release'/n)==v for n,v in b['libraries'].items())
    split=read(OUT/'splits.json');assert sha(CORPUS/'index.json')==split['corpus']
    data={e['id']:e for e in read(CORPUS/'index.json')['entries']}
    past=[r for path in split['historical_indexes'] for r in read(R/path)['entries'] if r.get('map')=='家院' and 'decks' in r]
    test_ids=split['a']+split['b'];held=[data[i] for i in test_ids]
    dev=[data[i] for i in split['train']+split['val']]
    assert len(held)==len({e['seed'] for e in held})==24 and not {e['seed'] for e in held}&{e['seed'] for e in past+dev}
    for k in ('a','b'):assert sum(bool(data[i]['night']) for i in split[k])==6
    for j in range(2):
        decks={deck(e)[j] for e in held};assert len(decks)==24 and not decks&{deck(e)[j] for e in past+dev}
    idx,limits=verify_games(OUT,expected_map='家院')
    def lookup(key):
        if key in idx:return idx[key]
        path=LAST/'games'/(key+'.jsonl.gz');m=read(path.with_suffix('.receipt.json'))
        assert sha(path)==m['sha256'];return m
    stages=['preflight','routes','supplement','zombie','live-routes','zombie-live','plant','plant-selected','test','regression','fine-test']
    long={}
    for stage in stages:
        for e in read(OUT/(stage+'.json'))['extensions']:
            a,b,c=[lookup(e[key]) for key in ('base','candidate','extended')]
            assert a['winner'] and a['winner']!=e['side'] and b['timeout']
            assert c['parameters']=={**b['parameters'],'limit':1200}
            assert (c['winner'],c['timeout'],c['time'])==(e['winner'],e['timeout'],e['end'])
            key=e['extended']
            if key not in long:long[key]=dict(side=e['side'],winner=e['winner'],timeout=e['timeout'],end=e['end'],scopes=[])
            assert long[key]['side']==e['side']
            if stage not in long[key]['scopes']:long[key]['scopes'].append(stage)
    extra=set()
    horizon=read(OUT/'horizons.json');assert horizon['test']==sha(OUT/'test.json')
    for r in horizon['rows']:
        a,b=idx[r['timed']],idx[r['long']]
        assert a['timeout'] and {**a['parameters'],'limit':1200}==b['parameters']
        assert (b['winner'],b['time'],b['timeout'])==(r['winner'],r['end'],r['timeout'])
        if r['long'] not in long:extra.add(r['long'])
    assert set(long)|extra=={k for k,v in idx.items() if v['parameters']['limit']==1200}
    train=[r for stage in ['routes','supplement','live-routes'] for r in read(OUT/(stage+'.json'))['rows']]
    from event_fit import detail_pairs
    train_summary=dict(roots=len(train),unique_prefixes=len({r['prefix'] for r in train}),openings=len({r['opening'] for r in train}),
        choices=sum(len(r['keys']) for r in train),actual_distinct=sum(len(r['keep']) for r in train),
        informative=sum(len({r['outcomes'][i] for i in r['keep']})>1 for r in train),
        coverage={str(k):sum(bool(r['mask']&k) for r in train) for k in (1,2,4,8)},
        kind=dict(Counter(p['act'][0] for r in train for j,p in enumerate(r['pool']) if j in r['keep'])),
        card_swaps=sum(bool(detail_pairs([r['pool'][j] for j in r['keep']],1)) for r in train),
        grave_swaps=sum(bool(detail_pairs([r['pool'][j] for j in r['keep']],2)) for r in train))
    test=read(OUT/'test.json');stats={}
    assert test['zombie']==sha(z) and test['plant']==sha(p)
    old_binary,price_binary=map(sha,(PROGRAM,LIVE))
    z16,plant1p=sha(PARENT),sha(STRONG)
    rivals={o:sha(MODELS[o]) if MODELS[o] else None for o in 'rhb'}
    for side,group in test['results'].items():
        by={}
        for k in ('a','b','all'):
            ids=test_ids if k=='all' else split[k];rs=group[k]['rows']
            assert len(rs)==len(ids)*3 and {(r['id'],r['opponent']) for r in rs}=={(i,o) for i in ids for o in 'rhb'}
            for r in rs:
                a=idx[r['baseline']]['parameters'];b=idx[r['candidate']]['parameters']
                assert a['opening']==r['id'] and a['corpus']==split['corpus'] and a['limit']==600
                if side=='zombie':
                    assert a['binary']==old_binary and a['policy']==z16 and b=={**a,'binary':price_binary,'policy':test['zombie']}
                    assert a['plant']==rivals[r['opponent']]
                else:
                    assert a['binary']==price_binary and a['plant']==plant1p and b=={**a,'plant':test['plant']}
                    assert a['zombie']==rivals[r['opponent']] and a['position'] is None
            by[k]=dict(before=[sum(r['old']==v for r in rs) for v in (1,0,-1)],after=[sum(r['new']==v for r in rs) for v in (1,0,-1)],
                win_held=sum(r['old']==1 and r['new']==1 for r in rs),new_wins=sum(r['old']!=1 and r['new']==1 for r in rs),
                net=group[k]['net'],adjusted_net=group[k]['adjusted_net'],ci=group[k]['paired_mean95'],stall=sum(r['stall'] for r in rs),
                opponents={o:v['net'] for o,v in group[k]['per_opponent'].items()})
        stats[side]=by
    reg=read(OUT/'regression.json')['rows']
    geometry=Counter()
    for r in test['coverage']:
        candidate=g(r['opening'],MODELS[r['opponent']],policy=z,binary=LIVE)
        assert candidate.key()==r['after']
        for e in trace(candidate)['options']:
            if not e['mask']&15:continue
            geometry['decisions']+=1
            geometry['chose_approach']+=e['action'][0]==3
            pool=e.get('pool',[])
            geometry['offered_approach']+=any(q['act'][0]==3 for q in pool)
            if pool and e['action'][0]==0:
                geometry['sampled_waits']+=1
                geometry['sampled_waits_with_other_command']+=any(q['act'][0]!=0 for q in pool)
            if pool and e['action'][0]==1:
                geometry['measured_builds']+=1
                geometry['built_forward_one_tile']+=pool[0]['x'][11]>=tanh(1/6)-1.e-9
    def seeds_of(group):
        result=set()
        for _,i,_,g in group:
            result.add(next(r['seed'] for r in read(g.corpus/'index.json')['entries'] if r['id']==i))
        return result
    assert not seeds_of(scans())&seeds_of(historical()[1])
    guard=read(ROOT/'disk.json');total=guard['prior']+size(ROOT)
    assert total<guard['cap'] and guard['combined_sampled_peak']<guard['cap']
    write(OUT/'audited.json',dict(games=len(idx),limits=dict(limits),extensions=long,other_blind_extensions=len(extra),training=train_summary,
        blind_results=stats,blind_geometry=dict(geometry),prior_zero=coverage(reg),blind_zero=coverage([r for r in test['coverage'] if r['old_triggers']==0]),
        blind_active=coverage([r for r in test['coverage'] if r['old_triggers']]),disk=dict(own=size(OUT),combined=total,peak=guard['combined_sampled_peak'],cap=guard['cap']),
        hashes={f:sha(OUT/f) for f in ('routes.json','supplement.json','live-routes.json','test.json','regression.json','fine-test.json','zombie-selected.json','plant-selected.json')},
        sources={f:sha(H/f) for f in ('event_study.py','event_fit.py','event_policy.inc','event_gate_test.cpp','event_audit.py','option_games.py','option_study.py')}))

if __name__=='__main__':audit()
