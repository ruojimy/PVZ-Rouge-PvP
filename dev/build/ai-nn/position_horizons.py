"""Extend every observed matched loss-to-timeout substitution by a frozen selected head."""
from collections import defaultdict
from pathlib import Path
import hashlib
from position_train import OUT,BASE,HOME,TRANSFER,MODELS,read,write,sha,score,group
from overnight_eval import footer


def run():
    robust=OUT/'robust'
    model_paths={sha(p):p for p in list((OUT/'models').glob('*.json'))+list(filter(None,MODELS.values()))}
    model_paths[None]=None
    zheads={read(f/'zombie-frozen.json')['sha256'] for f in [OUT,robust]}
    pheads={read(f/'plant-frozen.json')['sha256'] for f in [OUT,robust]}
    corpora={sha(p/'index.json'):p for p in [HOME,TRANSFER,robust/'plain',robust/'diverse/plain']}
    short={};long={}
    labels=defaultdict(list)
    def key(p,uid):return(p['corpus'],uid,p['plant'],p['zombie'],p['tactical'])
    for folder in (OUT/'games').iterdir():
        if not (folder/'parameters.json').exists() or not (folder/'summary.json').exists():continue
        params=read(folder/'parameters.json')
        if params['binary']!=read(OUT/'build.json')['binary']:continue
        dest=short if params['limit']==600 else long if params['limit']==1200 else None
        if dest is None:continue
        for uid,result in read(folder/'summary.json')['matches'].items():
            k=key(params,uid)
            if k in dest:assert dest[k][0]['log_sha256']==result['log_sha256']
            dest[k]=(result,folder/'matches'/(uid+'.jsonl'))
            if dest is short:labels[k].append(folder.name)
    cases=[]
    for k,(candidate,trace) in short.items():
        corpus,uid,plant,zombie,tactical=k
        if not candidate['timeout']:continue
        ref={}
        if plant in pheads and tactical in (zheads|{None}):ref['plant']=(corpus,uid,sha(BASE),zombie,tactical)
        if tactical in zheads and zombie==sha(BASE):ref['zombie']=(corpus,uid,plant,zombie,None)
        for side,parent in ref.items():
            if parent not in short or score(short[parent][0],side)!=-1:continue
            if k not in long:
                token=hashlib.sha256(repr(k).encode()).hexdigest()[:12]
                extended=group('horizon-selected-'+token,[uid],model_paths[plant],model_paths[zombie],model_paths[tactical],1200,corpora[corpus])[uid]
                long[k]=(extended['match'],Path(extended['trace']))
            result,path=long[k];a,b=footer(trace),footer(path)
            for field,time_key in [('activity','time'),('spatial_actions','t'),('accepted_commands','time')]:
                assert [e for e in a[field] if e[time_key]<600]==[e for e in b[field] if e[time_key]<600]
            cases.append(dict(side=side,opening=uid,seed=candidate['seed'],map=candidate['map'],
                         parent_time=short[parent][0]['time'],winner=result['winner'],timeout=result['timeout'],extended_time=result['time'],
                         compared_groups=labels[parent],candidate_groups=labels[k],extended=str(path)))
    write(OUT/'selected-loss-timeouts.json',dict(cases=cases,scope='All completed 600s ordinary games for the frozen selected heads with an exact same-corpus/seed/opposing-head historical baseline already played. Existing 1200s records reused.'))

if __name__=='__main__':run()

