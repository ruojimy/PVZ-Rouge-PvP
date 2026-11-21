"""Audit matched game returns, independence, native commands, and placement behavior."""
from collections import Counter
import math
from pathlib import Path
from functools import lru_cache
import numpy as np
from position_study import OUT, read, write, sha, score
from overnight_eval import footer, measure


def matchset(group):
    folder=OUT/'games'/group
    return read(folder/'summary.json')['matches']


def result_view(domain,side,ids,opp):
    return [(matchset('home-joint-parent' if domain=='home' and o=='b' else f'{domain}-{side}-{o}-parent'),
             matchset(f'{domain}-{side}-{o}-candidate')) for o in opp]


def aggregate(pairs,ids,side,rng,cluster_keys=None):
    def wtl(vals):
        return dict(win=int(np.sum(vals==1)),timeout=int(np.sum(vals==0)),loss=int(np.sum(vals==-1)))
    a=np.array([[score(first[i],side) for first,_ in pairs] for i in ids]);b=np.array([[score(last[i],side) for _,last in pairs] for i in ids])
    delta=(b-a).mean(1)
    keys=cluster_keys or ids
    blocks=[np.flatnonzero(np.array(keys)==key) for key in dict.fromkeys(keys)]
    samples=rng.integers(0,len(blocks),(20000,len(blocks)))
    sums=np.array([delta[block].sum() for block in blocks])
    lengths=np.array([len(block) for block in blocks])
    interval=np.quantile(sums[samples].sum(1)/lengths[samples].sum(1),[.025,.975]).tolist()
    natural_draws={label:sum(not pair[j][i]['timeout'] and pair[j][i]['winner']=='draw' for pair in pairs for i in ids)
                   for j,label in enumerate(['before','after'])}
    return dict(openings=len(ids),matches=a.size,before=wtl(a),after=wtl(b),natural_draws=natural_draws,net=int((b-a).sum()),
                worst_delta_by_opponent=int((b-a).sum(axis=0).min()),mean_delta=float(delta.mean()),paired95=interval,clusters=len(blocks))


@lru_cache(maxsize=None)
def geometry(corpus,uid):
    entry=next(e for e in read(corpus/'index.json')['entries'] if e['id']==uid)
    board=read(corpus/entry['cold'])['battle']
    return board['width'],board['tile']


def tactical(rows_dir,corpus=None):
    counters=Counter()
    examples={}
    for path in (rows_dir/'matches').glob('*.jsonl'):
        trace=footer(path)
        decisions=trace.get('spatial_actions',[])
        commands=trace['accepted_commands']
        native=[r for r in commands if r['kind']=='deploy']
        chosen=[e for e in decisions if e['kind'] in ('spawn','build')]
        geometry_root=corpus or (OUT/'transfer/plain' if rows_dir.name.startswith('away-') else OUT/'plain')
        width,tile=geometry(geometry_root,path.stem)
        distance=lambda a,b:abs((a-b+width/2)%width-width/2)
        assert len(chosen)==len(native),(path,len(native),len(chosen))
        for e,c in zip(chosen,native):
            assert e['card']==c['card'] and abs(c['time']-e['t'])<.001 and c['accepted'] and abs(e['x']-c['x'])<1e-6 and abs(e['y']-c['y'])<1e-6,(path,e,c)
            if e['kind']=='spawn':assert c.get('grave')==e['source']
        chose_flags=[e for e in decisions if e['kind'] in ('flag','release')]
        actual_flags=[c for c in commands if c['kind']=='rally']
        assert len(chose_flags)==len(actual_flags)
        for e,c in zip(chose_flags,actual_flags):
            assert abs(e['t']-c['time'])<.001 and ((e['kind']=='release')==(c['point'] is None))
            if e['kind']=='flag':
                assert all(abs(c['point'][key]-(math.floor(e[key]/tile)+.5)*tile)<1e-6 for key in ['x','y'])
        counters['games']+=1
        counters['games_timeout']+=int(trace['timeout'])
        for kind in ['spawn','build','approach','flag','release','order','wait']:
            n=sum(e['kind']==kind for e in decisions)
            counters[kind]+=n
            counters['games_with_'+kind]+=int(n>0)
        for e in chosen:
            if e['kind']=='spawn' and e['preview_legal_exits']>=2:
                counters['spawn_2plus']+=1
                if e['native_card']==e['card'] and e['native_source'] and e['native_source']!=e['source']:
                    counters['different_source_same_card']+=1
                    examples.setdefault('different_source',dict(game=path.stem,event=e))
            if e['native_card'] and e['card']!=e['native_card']:counters['different_card']+=1
            if not e['native_card']:counters['without_card_hint']+=1
        for e in decisions:
            if e['kind']=='approach':
                examples.setdefault('approach',dict(game=path.stem,event=e))
        # A requested waypoint alone does not prove arrival or forward construction.
        confirmed=0
        for b in (e for e in chosen if e['kind']=='build'):
            matching=[a for a in decisions if a['kind']=='approach' and a['card']==b['card']
                      and 0<b['t']-a['t']<=15 and distance(a['x'],b['x'])<=tile
                      and abs(a['y']-b['y'])<=tile]
            for a in matching:
                closer=distance(a['hero'][0],a['foe'][0])-distance(b['hero'][0],a['foe'][0])
                arrived=distance(a['hero'][0],a['x'])-distance(b['hero'][0],a['x'])
                if closer>=tile and arrived>=tile:
                    confirmed+=1
                    examples.setdefault('confirmed_forward_build',dict(game=path.stem,approach=a,build=b,progress_tiles=closer/tile))
                    break
        counters['confirmed_forward_builds']+=confirmed
        counters['games_with_confirmed_forward_builds']+=int(confirmed>0)
        counters['send_errors']+=trace['ai']['zombie']['send_errors']
    return dict(counts=dict(counters),examples=examples)


def audit():
    complete=read(OUT/'complete.json');plan=read(OUT/'plan.json')
    disclosure=read(OUT/'generalization-plan.json')['per_opening']
    rng=np.random.default_rng(970811)
    groups={}
    for side in ['plant','zombie']:
        for domain,ids,opps in [('home',plan['test'],'rohb'),('away',[f'{i:03}' for i in range(8)],'rh')]:
            data=result_view(domain,side,ids,opps)
            seed_keys=None if domain=='home' else [e['seed'] for e in read(OUT/'transfer/plain/index.json')['entries']]
            groups[f'{side}/{domain}/all']=aggregate(data,ids,side,rng,seed_keys)
            if domain=='away':
                for arena in ['山地','铁道']:
                    sub=[r['id'] for r in read(OUT/'transfer/plain/index.json')['entries'] if r['map']==arena]
                    groups[f'{side}/away/{arena}']=aggregate(data,sub,side,rng)
            if domain=='home':
                groups[f'{side}/home/excluded_opponents']=aggregate(result_view(domain,side,ids,'rh'),ids,side,rng)
                subsets={'unseen_decks':[i for i in ids if disclosure[i]['unseen_deck_pair']],
                         'unseen_decks_excluded_opponents':[i for i in ids if disclosure[i]['unseen_deck_pair']],
                         'day':[i for i in ids if not disclosure[i]['night']], 'night':[i for i in ids if disclosure[i]['night']],
                         'novel_zombie_cards':[i for i in ids if disclosure[i]['new_cards']['zombie']]}
                for k,subset in subsets.items():
                    which=result_view(domain,side,ids,'rh') if k=='unseen_decks_excluded_opponents' else data
                    groups[f'{side}/home/{k}']=aggregate(which,subset,side,rng)
    actions={d:tactical(OUT/'games'/d) for d in ['home-zombie-'+o+'-candidate' for o in 'rohb']+['home-joint-candidate']+['away-zombie-'+o+'-candidate' for o in 'rh']}
    by_seat={}
    for variant in ['parent','candidate']:
        folder=OUT/'games'/('home-joint-'+variant)
        time_sum=0.;deploys=Counter()
        for uid in plan['test']:
            tr=footer(folder/'matches'/(uid+'.jsonl'));time_sum+=tr['time']
            for s in ['plant','zombie']:deploys[s]+=measure(tr['activity'],s,tr['time'])['deploys']
        by_seat[variant]=dict(average_seconds=time_sum/len(plan['test']),deployments_per_game_minute={s:60*n/time_sum for s,n in deploys.items()})
    receipts=list((OUT/'games').glob('*/summary.json'))
    counts={p.parent.name:len(read(p)['matches']) for p in receipts}
    extended=[]
    for short_path in (OUT/'games').glob('*-1200-*/summary.json'):
        label=short_path.parent.name
        domain,kind=label.split('-1200-')
        if domain not in ('home','away'):
            continue
        base_group=domain+'-joint-candidate' if kind.startswith('joint-') else domain+'-'+kind+'-candidate'
        side=kind.split('-')[-1] if kind.startswith('joint-') else kind.split('-')[0]
        for uid,row in read(short_path)['matches'].items():
            a=footer(OUT/'games'/base_group/'matches'/(uid+'.jsonl'))
            b=footer(short_path.parent/'matches'/(uid+'.jsonl'))
            for field,key in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')]:
                assert [e for e in a[field] if e[key]<600]==[e for e in b[field] if e[key]<600],(label,uid,field)
            extended.append(dict(domain=domain,arm=kind,side=side,opening=uid,long_score=score(row,side),seconds=row['time']))
    write(OUT/'audit.json',dict(returns=groups,action_audit=actions,joint_tempo=by_seat,game_counts=counts,
          extended=extended,
          treatment='Result confidence intervals are descriptive paired bootstrap estimates over openings. Multiple opponents on one opening remain together.'))

if __name__=='__main__':audit()

