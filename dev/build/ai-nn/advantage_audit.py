"""Verify locked assets, held-out novelty and native receipts for the matched continuation study."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import numpy as np
from advantage_study import OUT,ROOT,R,H,CORPUS,PROGRAM,FORK,PARENT,STRONG,PLANTS,deck,inputs_ok,read,write,sha
from option_audit import verify_games
from option_study import size,BUILD
from option_games import Game,trace
from advantage_fit import training_scans

def route_execution(rows):
    summary=Counter()
    forward=Counter()
    for row in rows:
        original=Game(row['uid'],PLANTS[row['opponent']],corpus=Path(row['corpus']),storage=OUT,
                      policy=PARENT,binary=FORK,after=row['time'],forced=0)
        immediate=replace(original,forced=1)
        advance=replace(original,forced=2)
        assert [original.key(),immediate.key(),advance.key()]==row['keys'][:3]
        front=next(e for e in trace(advance)['options'] if e.get('forked'))
        forward[front['status']]+=1
        if front.get('built') and not front.get('spawn'):
            forward['built_without_followup_spawn']+=1
        before,after=trace(original),trace(immediate)
        event=next(e for e in after['options'] if e.get('forked'))
        spawn=event.get('spawn')
        if not spawn:
            summary['failed']+=1
            continue
        summary['executed']+=1
        same=any(c['kind']=='deploy' and c['accepted'] and c['tick']==round(spawn['time']*30)
                 and c['card']==spawn['card'] and c.get('grave')==spawn['source'] for c in before['accepted_commands'])
        summary['same_native_command']+=same
        summary['same_battle_log']+=before['log_sha256']==after['log_sha256']
        if not same:
            summary['different_command_changed_result']+=row['outcomes'][0]!=row['outcomes'][1]
    return {'immediate':dict(summary),'advance':dict(forward)}

def audit():
    inputs_ok()
    design=read(OUT/'design.json');build=read(OUT/'build.json')
    assert sha(FORK)==build['binary'] and sha(PROGRAM)==design['native']
    assert sha(PARENT)==design['parent'] and sha(STRONG)==design['plant']
    for name,digest in build['sources'].items():assert sha(OUT/'native-src'/name)==digest
    for name,digest in build['libraries'].items():assert sha(BUILD/'Release'/name)==digest
    for name in ('zombie','plant'):
        locked=read(OUT/(name+'.json'));assert sha(Path(locked['path']))==locked['model']
    split=read(OUT/'splits.json');assert split['corpus']==sha(CORPUS/'index.json')
    entries={r['id']:r for r in read(CORPUS/'index.json')['entries']}
    historic=[r for p in [*(R/x for x in read(ROOT/'splits.json')['past_indexes']),ROOT/'plain/index.json',ROOT/'confirm/plain/index.json'] for r in read(p)['entries'] if r.get('map')=='家院' and 'decks' in r]
    dev=[entries[i] for i in split['train']+split['validation']]
    held=[entries[i] for i in split['a']+split['b']]
    assert len(held)==len({r['seed'] for r in held})==24
    assert not {r['seed'] for r in dev+historic}&{r['seed'] for r in held}
    for j in range(2):
        unique={deck(r)[j] for r in held};assert len(unique)==24 and not unique&{deck(r)[j] for r in dev+historic}
    for key in ('a','b'):assert sum(bool(entries[i]['night']) for i in split[key])==6
    idx,limits=verify_games(OUT,expected_map='家院')
    stages={s:read(OUT/(s+'.json'))['extensions'] for s in ('training','zombie','plant','test','ranking-test','continuation')}
    unique={}
    for scope,rows in stages.items():
        for row in rows:
            base=idx[row['base']];new=idx[row['candidate']];long=idx[row['extended']]
            assert base['winner'] in ('plant','zombie') and base['winner']!=row['side'] and new['timeout']
            assert {**new['parameters'],'limit':1200}==long['parameters']
            assert (long['winner'],long['time'],long['timeout'])==(row['winner'],row['end'],row['timeout'])
            k=row['extended'],row['side']
            v=unique.setdefault(k,dict(key=k[0],side=k[1],winner=long['winner'],timeout=long['timeout'],time=long['time'],stages=[]))
            if scope not in v['stages']:v['stages'].append(scope)
    training=read(OUT/'training.json')['rows']
    scans={(i,o):trace(g) for source,i,o,g in training_scans() if source=='new'}
    distinct={}
    for a,b in [('r','p'),('r','o'),('p','o')]:
        changed=0
        for i in split['train']:
            x,y=scans[i,a],scans[i,b];end=min(180,x['time'],y['time'])
            def deployments(tr):
                return [(e['card'],round(e['time']*30)) for e in tr['activity'] if e['time']<=end and e['kind']=='deploy' and e['side']=='plant']
            changed+=deployments(x)!=deployments(y)
        distinct[a+'-'+b]=changed
    extra_training={v for r in training for v in r['extended'] if v}-{k for k,_ in unique}
    followup=read(OUT/'blind-timeouts.json')
    assert followup['test']==sha(OUT/'test.json')
    for case in followup['rows']:
        short,long=idx[case['timed']],idx[case['long']]
        assert short['timeout'] and long['parameters']=={**short['parameters'],'limit':1200}
        assert (long['winner'],long['time'],long['timeout'])==(case['winner'],case['end'],case['timeout'])
    extra_blind={case['long'] for case in followup['rows']}-{k for k,_ in unique}
    longer=extra_training|extra_blind|{k for k,_ in unique}
    assert longer=={k for k,r in idx.items() if r['parameters']['limit']==1200}
    def differences(rows):
        return {str(a):dict(Counter(str(int(np.sign(r['outcomes'][a]-r['outcomes'][0]))) for r in rows)) for a in (1,2,3)}
    prior={r['prefix']:r for f in ('branches','branches-extra','branches-timed') for r in read(ROOT/(f+'.json'))['groups']}
    cv={}
    predictions=read(OUT/'zombie.json')['cv']
    disagreement={tag:dict(roots=0,informative=0) for tag in ('same','different')}
    for a,b in zip(predictions['mean'],predictions['rank'],strict=True):
        assert all(a[k]==b[k] for k in ('opening','incumbent','informative'))
        group=disagreement['same' if a['picked']==b['picked']==a['incumbent'] else 'different']
        group['roots']+=1
        group['informative']+=a['informative']
    for method,rows in predictions.items():
        keys={r['opening'] for r in rows}
        cv[method]=dict(measured=len(rows),informative=sum(r['informative'] for r in rows),changed=sum(r['picked']!=r['incumbent'] for r in rows),
            improved=sum(r['gain']>0 for r in rows),worse=sum(r['gain']<0 for r in rows),
            by_opening_mean_gain=float(np.mean([np.mean([r['gain'] for r in rows if r['opening']==k]) for k in keys])))
    test=read(OUT/'test.json');summaries={}
    for side,group in test['results'].items():
        summaries[side]={}
        for label in ('a','b','all'):
            r=group[label];rows=r['rows'];assert len(rows)==(72 if label=='all' else 36)
            ids=split['a']+split['b'] if label=='all' else split[label]
            assert {(x['id'],x['opponent']) for x in rows}=={(i,o) for i in ids for o in ('r','h','b')}
            switch='plant' if side=='plant' else 'policy'
            parent=sha(STRONG if side=='plant' else PARENT)
            for x in rows:
                old,new=idx[x['baseline']]['parameters'],idx[x['candidate']]['parameters']
                assert old['opening']==x['id'] and old['corpus']==split['corpus'] and old['limit']==600
                assert old['binary']==design['native'] and old[switch]==parent
                assert {**old,switch:test[side]}==new
            summaries[side][label]=dict(before=[sum(x['old']==j for x in rows) for j in (1,0,-1)],
                after=[sum(x['new']==j for x in rows) for j in (1,0,-1)],net=r['net'],ci=r['paired_mean95'],
                per_opponent={o:v['net'] for o,v in r['per_opponent'].items()},stall=sum(x['stall'] for x in rows))
    disk=read(ROOT/'disk.json');total=disk['prior']+size(ROOT)
    assert total<disk['cap'] and disk['combined_sampled_peak']<disk['cap']
    write(OUT/'audited.json',dict(games=len(idx),by_horizon=dict(limits),loss_timeout_unique=list(unique.values()),
        extra_training_long_games=len(extra_training),extra_blind_long_games=len(extra_blind),
        train_roots=len(training),train_unique_prefixes=len({r['prefix'] for r in training}),
        historic_action_differences=differences(prior.values()),training_action_differences=differences(training),
        plant_sequence_differences_in_12_starts=distinct,route_execution=route_execution(training),
        cv=cv,cross_fold_vote_disagreement=disagreement,results=summaries,
        disk=dict(own_bytes=size(OUT),combined_bytes=total,sampled_peak=disk['combined_sampled_peak'],limit=disk['cap']),
        source_hashes={s:sha(H/s) for s in ('advantage_study.py','advantage_fit.py','advantage_audit.py','option_games.py','option_study.py','option_audit.py')},
        test_sha256=sha(OUT/'test.json'),rank_sha256=sha(OUT/'ranking-test.json'),continuation_sha256=sha(OUT/'continuation.json')))

if __name__=='__main__':audit()
