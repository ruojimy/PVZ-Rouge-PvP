"""Audit game counts, frozen models, matched horizons, unseen decks, and native commands in round two."""
from collections import Counter
from pathlib import Path
import shutil
import numpy as np

from position_robust import ROOT,OUT,BASE,read,sha,write,score
from position_audit import tactical,aggregate,matchset
from position_study import inputs_ok, H, BIN, cmd
from overnight_eval import footer,measure
from coverage_guard import size


def retest():
    inputs_ok()
    output=read(ROOT/'complete.json')
    assert sha(Path(read(ROOT/'zombie-frozen.json')['model']))==output['zombie']
    assert sha(Path(read(ROOT/'plant-frozen.json')['model']))==output['plant']
    meta=read(ROOT/'prepared.json')
    corpus=ROOT/'plain';rows=read(ROOT/'scenarios.json')
    original=read(OUT/'scenarios.json')
    assert not set(x['seed'] for x in rows).intersection(x['seed'] for x in original)
    assert len({rows[int(i)]['seed'] for i in meta['test']})==18
    assert all(rows[int(i)]['map']=='家院' for i in meta['test'])
    keys=lambda x:tuple(tuple(sorted(x['decks'][s])) for s in ('plant','zombie'))
    diverse=read(ROOT/'diverse/scenarios.json')
    assert not {x['seed'] for x in diverse}.intersection(x['seed'] for x in rows)
    dev={keys(x) for x in original[:18]+diverse}
    devcards={s:{c for x in original[:12]+diverse for c in x['decks'][s]} for s in ['plant','zombie']}
    rng=np.random.default_rng(991114)
    summary={};extended=[];decisions={};tempo={}
    for arena,ids,opps in [('house',meta['test'],'rhb'),('transfer',meta['transfer'],'rh')]:
        for side in ('zombie','plant'):
            all_pairs=[];independent=[];first_pairs=[]
            for o in opps:
                label=side+'-'+o
                record=output['results'][arena][label]
                base_name=record['parent_group']
                trial_name='r2-'+arena+'-'+label+'-candidate'
                a=matchset(base_name);b=matchset(trial_name);pair=(a,b)
                all_pairs.append(pair)
                if o=='h':independent.append(pair)
                if arena=='house' and o in 'rh':
                    earlier=OUT/'games'/('r2-house-'+label+'-first')/'summary.json'
                    first_pairs.append((read(earlier)['matches'] if earlier.exists() else b,b))
                if side=='zombie':
                    decisions[arena+'-'+o]=tactical(OUT/'games'/trial_name,corpus)
                seconds=[0.,0.]; deploys=[Counter(),Counter()];idle=[Counter(),Counter()]
                sends=[Counter(),Counter()];rejected=[Counter(),Counter()]
                for j,name in enumerate([base_name,trial_name]):
                    for uid in ids:
                        t=footer(OUT/'games'/name/'matches'/(uid+'.jsonl'))
                        seconds[j]+=t['time']
                        for s in ('plant','zombie'):
                            activity=measure(t['activity'],s,t['time'])
                            deploys[j][s]+=activity['deploys'];idle[j][s]+=activity['rich_idle']
                            sends[j][s]+=t['ai'][s]['sends'];rejected[j][s]+=t['ai'][s]['send_errors']
                tempo[arena+'/'+label]=[dict(mean_time=seconds[j]/len(ids),deploys_per_min={s:60*n/seconds[j] for s,n in deploys[j].items()},
                     rich_idle_fraction={s:n/seconds[j] for s,n in idle[j].items()},sends=dict(sends[j]),rejections=dict(rejected[j])) for j in range(2)]
                checks=[('r2-'+arena,record)]
                if 'vs_first' in record:checks.append(('r2-first',record['vs_first']))
                for prefix,entry in checks:
                    for uid,res in entry['horizons'].items():
                        short=footer(OUT/'games'/trial_name/'matches'/(uid+'.jsonl'))
                        long=footer(OUT/'games'/(prefix+'-1200-'+label)/'matches'/(uid+'.jsonl'))
                        for field,key in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')]:
                            assert [e for e in short[field] if e[key]<600]==[e for e in long[field] if e[key]<600]
                        extended.append(dict(domain=prefix,opponent=o,side=side,opening=uid,long_result=score(res,side),time=res['time']))
            key=side+'/'+arena
            seeds=[rows[int(i)]['seed'] for i in ids]
            summary[key]=aggregate(all_pairs,ids,side,rng,seeds)
            summary[key+'/heldout_H']=aggregate(independent,ids,side,rng,seeds)
            if arena=='house':
                summary[key+'/vs_first_rh']=aggregate(first_pairs,ids,side,rng)
                for sub,condition in [('unseen_decks',lambda v:keys(v) not in dev),
                         ('new_zombie_cards',lambda v:bool(set(v['decks']['zombie'])-devcards['zombie'])),
                         ('night',lambda v:v['night']),('day',lambda v:not v['night'])]:
                    subids=[i for i in ids if condition(rows[int(i)])]
                    if subids:summary[key+'/'+sub]=aggregate(all_pairs,subids,side,rng)
            else:
                for region in ('山地','铁道'):
                    subids=[i for i in ids if rows[int(i)]['map']==region]
                    summary[key+'/'+region]=aggregate(all_pairs,subids,side,rng)
    all_games={p.parent.name:len(read(p)['matches']) for p in (OUT/'games').glob('*/summary.json')}
    extra={'example_replays':len(read(OUT/'action-fit.json')['pairs']),'one_action_forks':len(read(OUT/'counterfactuals.json')['results']),
           'preflight_completed':sum(1 for p in (OUT/'preflight-games').glob('*/matches/*.jsonl') if p.stat().st_size>0 and p.read_bytes().rstrip().endswith(b'}') and b'"type":"result"' in p.read_bytes().splitlines()[-1])}
    write(ROOT/'audit.json',dict(paired=summary,horizons=extended,action_audit=decisions,tempo=tempo,groups=all_games,extra=extra,
          prior_full_deck_pairs_check=len(dev),new_house_heldout=meta['test'],official_promoted=False))
    d=read(OUT/'disk.json');d.update(current=size(OUT),free=shutil.disk_usage(OUT).free)
    d['peak']=max(d['peak'],d['current']);write(OUT/'disk.json',d)

if __name__=='__main__':retest()

