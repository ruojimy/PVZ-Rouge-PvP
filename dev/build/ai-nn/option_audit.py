"""Verify every compact match receipt and consolidate extended timeout outcomes."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from option_study import ROOT,PROGRAM,inputs_ok,read,write,sha

def verify_games(root,expected_map=None):
    index={};limits=Counter()
    for receipt in (root/'games').glob('*.receipt.json'):
        r=read(receipt);p=receipt.with_suffix('').with_suffix('.gz')
        assert p.exists() and sha(p)==r['sha256']
        with gzip.open(p,'rt',encoding='utf8') as f:
            header=json.loads(f.readline());footer=json.loads(f.readline());assert not f.readline()
        cfg=r['parameters']
        key=p.name.split('.')[0]
        assert key==hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()[:24]
        assert header['control_hz']==15 and header['limit_seconds']==cfg['limit']
        if expected_map is not None:assert header['map']==expected_map
        assert header['id']==footer['id']==cfg['opening'] and footer['type']=='result' and not footer['ai_error']
        assert r['battle']==footer['log_sha256'] and r['time']==footer['time']
        assert r['winner']==(footer['result'] or {}).get('winner')
        assert r['timeout']==footer['timeout'] and (footer['finished'] or abs(r['time']-cfg['limit'])<1e-6)
        if cfg['plant'] or cfg['zombie']:
            assert header['model_sha256']==(cfg['plant'] or cfg['zombie'])
        if cfg['plant'] and cfg['zombie']:assert header['zombie_model_sha256']==cfg['zombie']
        for seat in ('plant','zombie'):
            assert header['planners'][seat]==('nn' if cfg[seat] else 'r22')
        if cfg['position']:assert header['zombie_position_sha256']==cfg['position']
        if cfg['policy']:assert header['option_sha256']==cfg['policy']
        index[key]=r;limits[cfg['limit']]+=1
    assert len(index)==len(list((root/'games').glob('*.gz')))
    return index,limits

def audit():
    inputs_ok()
    release=read(ROOT/'build.json');assert sha(PROGRAM)==release['binary']
    for name,digest in release['sources'].items():assert sha(ROOT/'native-src'/name)==digest
    for path in ('zombie-frozen','plant-frozen','plant-trial-frozen'):
        frozen=read(ROOT/(path+'.json'));assert sha(Path(frozen['model']))==frozen['sha256']
    index,limits=verify_games(ROOT)
    scope={}
    for file,field in [('branch-horizons','cases'),('zombie-frozen','extensions'),('plant-frozen','extensions'),
                       ('route-test','extensions'),('plant-trial','results'),('changed-home-branches','extensions')]:
        rows=read(ROOT/(file+'.json'))[field]
        scope[file]=rows['extensions'] if field=='results' else rows
    for k,v in read(ROOT/'complete.json')['comparisons'].items():scope[k]=v['extensions']
    confirmation=read(ROOT/'confirm/results.json')
    for k,v in confirmation['comparisons'].items():scope['confirm-'+k]=v['extensions']
    extensions={}
    for name,rows in scope.items():
        for e in rows:
            kid=e['extended'];old=index[e['base']];new=index[e['candidate']];long=index[kid]
            assert old['winner'] in ('plant','zombie') and old['winner']!=e['side'] and new['timeout']
            assert long['time']==e['end'] and long['timeout']==e['timeout'] and long['winner']==e['winner']
            assert {**new['parameters'],'limit':1200}==long['parameters']
            key=(kid,e['side'])
            entry=extensions.setdefault(key,dict(side=e['side'],id=e['id'],extended=kid,winner=e['winner'],
                timeout=e['timeout'],time=e['end'],scopes=[]))
            if name not in entry['scopes']:entry['scopes'].append(name)
    assert {k for k,r in index.items() if r['parameters']['limit']==1200}=={k for k,_ in extensions}
    for row in read(ROOT/'changed-home-branches.json')['cases']:assert row['exact_original_log']
    result=read(ROOT/'complete.json');trial=read(ROOT/'plant-trial.json')['results']
    assert all(len(group['rows'])==54 for group in [*result['comparisons'].values(),trial])
    combined={}
    for side,first in [('plant',trial),('zombie',result['comparisons']['zombie_parent'])]:
        rng=np.random.default_rng(749973);boot=[];signs=[];games=[]
        for group in [first,confirmation['comparisons'][side]]:
            rows=group['rows'];ids=sorted({row['id'] for row in rows})
            delta=np.array([sum(r['new']-r['old']-int(r['stall']) for r in rows if r['id']==i)/3 for i in ids])
            assert len(ids)==18 and len(rows)==54
            boot.append(delta[rng.integers(0,len(ids),(30000,len(ids)))].mean(axis=1))
            signs.append(dict(improved=int((delta>0).sum()),same=int((delta==0).sum()),worse=int((delta<0).sum())))
            games.extend(rows)
        combined[side]=dict(before=[sum(r['old']==v for r in games) for v in (1,0,-1)],
            after=[sum(r['new']==v for r in games) for v in (1,0,-1)],net=sum(r['new']-r['old'] for r in games),
            by_opening=signs,descriptive_stratified95=np.quantile((boot[0]+boot[1])/2,[.025,.975]).tolist())
    write(ROOT/'audited.json',dict(verified_match_files=len(index),by_horizon=dict(limits),
        extended_unique=list(extensions.values()),extension_comparisons={k:len(v) for k,v in scope.items()},
        primary=sha(ROOT/'complete.json'),plant_trial=sha(ROOT/'plant-trial.json'),route_ranking=sha(ROOT/'route-test.json'),
        postselected_routes=sha(ROOT/'changed-home-branches.json'),confirmation=sha(ROOT/'confirm/results.json'),
        pooled_descriptive=combined,kernel_verified=True))

if __name__=='__main__':audit()
