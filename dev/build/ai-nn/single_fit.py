"""Paired one-decision rollouts, fitting, and held-out evaluation."""
from collections import Counter,defaultdict
from itertools import combinations
from dataclasses import replace
import numpy as np
from switch_fit import commands,fit
from option_fit import paired_result
from overnight_eval import measure
from single_study import *
option_games.batch=batch

def base_cfg():return read(ACTIVE)['switch']
def make(name,**updates):return policy(name,{**base_cfg(),**updates})
def probe(g):return next(e for e in trace(g)['switches'] if e['phase']=='probe')
def val(g,side='zombie'):return outcome(trace(g),side)
def extend_groups(groups,side='zombie'):
    pairs={(a,b,side) for gs in groups for a in gs for b in gs if a!=b and val(a,side)<0 and trace(b)['timeout']}
    return extend(sorted(pairs,key=lambda x:(x[0].key(),x[1].key())))
def utility(a,b,tails,side='zombie'):
    def score(g,other):
        w=val(g,side)
        if w:return float(w)
        e=tails.get((other.key(),g.key()))
        if e:
            if e['winner']==side and not e['joint_idle']:return .45
            return -1.
        return -.55
    x,y=trace(a),trace(b);t=min(x['time'],y['time'])
    teams=[(measure(x['activity'],s,t)['deploys'],measure(y['activity'],s,t)['deploys']) for s in (side,'plant' if side=='zombie' else 'zombie')]
    lower=max(0.,(teams[0][0]-teams[0][1])/max(5,teams[0][0]))
    return score(b,a)-score(a,b)-.22*min(1.,lower)-.15*int(all(v<u for u,v in teams))
def tails(ext):return {(r['base'],r['candidate']):r for r in ext}
def review():
    rows=read(OUT/'disagreements.json')['rows'];groups=[]
    old=policy('old-review',dict(start='old',single_mode='review',full_inputs=True))
    new=make('active-review',single_mode='review',full_inputs=True)
    for r,(_,oa,ob) in zip(rows,scans()):
        t=r['tick']/30;gs=[game(r['id'],MODELS[r['opponent']],p,PREVIOUS_CORPUS,forced=j,after=t) for j,p in enumerate((old,new,new))]
        groups.append((r,oa,ob,gs))
    batch('first actual disagreement: z16 / one move / persistent',[a for *_,gs in groups for a in gs])
    ext=extend_groups([gs for *_,gs in groups]);ex=tails(ext);result=[]
    for r,oa,ob,gs in groups:
        stamps=[probe(g) for g in gs];tick=r['tick']
        assert len({s['prefix'] for s in stamps})==1 and all(round(s['t']*30)==tick for s in stamps),(r,stamps)
        assert trace(gs[0])['log_sha256']==trace(oa)['log_sha256'] and trace(gs[2])['log_sha256']==trace(ob)['log_sha256']
        ca,cb,cc=[commands(g) for g in gs]
        assert ca[tick]==r['commands'][0] and cb[tick]==cc[tick]==r['commands'][1]
        assert [[(t,c) for t,c in v.items() if t<tick] for v in (ca,cb,cc)].count([(t,c) for t,c in ca.items() if t<tick])==3
        ret=[e for e in trace(gs[1])['switches'] if e['phase']=='return_z16']
        assert len(ret)==1 or trace(gs[1])['time']<=gs[1].after+.08
        result.append(dict(**{k:r[k] for k in ('id','opponent','tick','commands')},prefix=stamps[0]['prefix'],keys=[g.key() for g in gs],
            x=stamps[0]['x'],results=[val(g) for g in gs],end=[trace(g)['time'] for g in gs],release=ret[0]['t'] if ret else None,
            target=utility(gs[0],gs[1],ex),effect=trace(gs[0])['log_sha256']!=trace(gs[1])['log_sha256']))
    fixed(OUT/'review.json',dict(rows=result,extensions=ext))
def arrivals():
    cfg=make('arrival-pairs',single_mode='arrival_pair');groups=[]
    for i in read(LAST/'splits.json')['a']+read(LAST/'splits.json')['b']:
        for o in 'rhb':
            ref=Game(i,MODELS[o],policy=ACTIVE,corpus=PREVIOUS_CORPUS,storage=LAST,binary=PREVIOUS_NATIVE)
            for e in trace(ref)['switches']:
                if e['phase']!='arrival_vote':continue
                gs=[game(i,MODELS[o],cfg,PREVIOUS_CORPUS,forced=j,after=e['t']) for j in (0,1)]
                groups.append((i,o,ref,e,gs))
    assert len(groups)==23
    batch('23 reached sites, defer vs build at the exact arrival',[a for *_,gs in groups for a in gs]);ext=extend_groups([gs for *_,gs in groups]);ex=tails(ext);rows=[]
    for i,o,ref,e,gs in groups:
        marks=[probe(v) for v in gs];assert marks[0]['prefix']==marks[1]['prefix']
        votes=[next(s for s in trace(g)['switches'] if s['phase']=='arrival_vote' and round(s['t']*30)==round(e['t']*30)) for g in gs]
        assert votes[0]['x']==votes[1]['x'] and [v['place'] for v in votes]==[False,True] and votes[0]['target']==votes[1]['target']==e['target']
        assert trace(gs[int(e['place'])])['log_sha256']==trace(ref)['log_sha256']
        for j,g in enumerate(gs):
            at=[c for c in trace(g)['accepted_commands'] if c['tick']==round(e['t']*30) and c['kind']=='deploy' and c['accepted']]
            assert bool(at)==bool(j)
        rows.append(dict(id=i,opponent=o,t=e['t'],prefix=marks[0]['prefix'],x=votes[0]['x'],site=e['target'],keys=[g.key() for g in gs],
                         results=[val(g) for g in gs],target=utility(gs[0],gs[1],ex)))
    fixed(OUT/'arrivals.json',dict(rows=rows,extensions=ext))
def collect_cfg():
    return make('collect',single_mode='lease',sample=True)
def fresh():
    if not (OUT/'splits.json').exists():
        import psutil
        def drafting():
            for proc in psutil.process_iter(['cmdline']):
                line=proc.info.get('cmdline') or []
                if line[-2:]==['worker','prepare'] and any('single_study.py' in v for v in line):return True
            return False
        while not (OUT/'splits.json').exists() and drafting():time.sleep(3)
        if not (OUT/'splits.json').exists():prepare()
    ids=read(OUT/'splits.json')['train'];policy0=collect_cfg()
    scans0=[(i,o,game(i,p,policy0)) for i in ids for o,p in TEACHERS.items()]
    batch('development scans with three frozen plant snapshots',[g for _,_,g in scans0])
    groups=[]
    for j,(i,o,g) in enumerate(scans0):
        opts=[e for e in trace(g)['switches'] if e['phase']=='lease' and 'x' in e];seen=set()
        for request,want in [(0,(0,12,24)[j%3]),(1,(18,65,125)[(j+j//3)%3])]:
            pool=[e for e in opts if round(e['t']*30) not in seen]
            if not pool:continue
            e=min(pool,key=lambda e:((request==1 and not e['offered']),not bool(e['mask']&15) if want>0 else False,abs(e['t']-want)))
            seen.add(round(e['t']*30));gs=[replace(g,forced=k,after=e['t']) for k in range(3 if e['offered'] else 2)]
            groups.append((i,o,g,e,gs))
    batch('one-decision alternatives on fresh frozen-plant states',[a for *_,gs in groups for a in gs])
    ext=extend_groups([gs for *_,gs in groups]);ex=tails(ext);rows=[]
    for i,o,ref,e,gs in groups:
        stamps=[probe(a) for a in gs]
        assert all(s['x']==e['x'] and s['prefix']==stamps[0]['prefix'] and round(s['t']*30)==round(e['t']*30) for s in stamps)
        assert trace(gs[0])['log_sha256']==trace(ref)['log_sha256']
        rows.append(dict(id=i,opponent=o,t=e['t'],prefix=stamps[0]['prefix'],mask=e['mask'],x=e['x'],keys=[a.key() for a in gs],results=[val(g) for g in gs],
                         targets=[utility(gs[0],g,ex) for g in gs],distinct=len({trace(g)['log_sha256'] for g in gs})))
    fixed(OUT/'fresh.json',dict(rows=rows,extensions=ext))
def run(stage):
    if stage=='review':review()
    elif stage=='arrivals':arrivals()
    elif stage=='fresh':fresh()
    elif stage=='zombie':train_zombie()
    elif stage=='plant':train_plant()
    elif stage=='test':test()
    elif stage=='audit':audit()
    else:raise ValueError(stage)
LIVE=OUT/'live/Release/position_match.exe'
def live_game(i,plant,policy,corpus=CORPUS,**kw):return game(i,plant,policy,corpus,binary=LIVE,**kw)
def training_rows(refined=False):
    events=[];trips=[];arrivals=[]
    for r in read(OUT/'review.json')['rows']:
        events.append(('historic'+r['id'],r['prefix'],r['x'],r['target']))
    for stage in ['fresh']+(['visited'] if refined else []):
        for r in read(OUT/(stage+'.json'))['rows']:
            key=r.get('set','fresh')+r['id']
            events.append((key,r['prefix'],r['x'],r['targets'][1]))
            if len(r['targets'])>2:trips.append((key,r['prefix'],r['x'],r['targets'][2]))
    for stage in ['arrivals','earlier-arrivals']+(['visited-arrivals'] if refined else []):
        for r in read(OUT/(stage+'.json'))['rows']:
            arrivals.append((r.get('set','historic')+r['id'],r['prefix'],r['x'],r['target']))
    return [fit(rs) for rs in (events,trips,arrivals)]
def candidate(tag,heads,margins,sample=False):
    (one,_),(trip,_),(arrival,_)=heads
    return make(tag,single_mode='lease',one_head=one,trip_head=trip,arrival_live=arrival,
                one_margin=margins[0],trip_margin=margins[1],arrival_margin=margins[2],sample=sample)
def dev_encounters(subset='train',history=False):
    output=[('fresh',i,o,CORPUS,p) for i in read(OUT/'splits.json')[subset] for o,p in TEACHERS.items()]
    if history:
        output+=[('history',r['id'],r['opponent'],PREVIOUS_CORPUS,MODELS[r['opponent']]) for r in read(OUT/'review.json')['rows']]
    return output
def arrival_checks(name,encounters,p,limit):
    # Spread the selected roots across openings before taking a second one.
    cases=[]
    for tag,i,o,g in encounters:
        for ev in trace(g)['switches']:
            if ev['phase']=='arrival_vote':cases.append((tag,i,o,g,ev))
    chosen=[];counts=Counter()
    while cases and len(chosen)<limit:
        j=min(range(len(cases)),key=lambda j:(counts[cases[j][0]+cases[j][1]],abs(cases[j][4]['t']-75),cases[j][2],cases[j][4]['t']))
        item=cases.pop(j);chosen.append(item);counts[item[0]+item[1]]+=1
    probe_policy=policy(name+'-probe',{**read(p)['switch'],'arrival_probe':True})
    groups=[(tag,i,o,g,e,[replace(g,binary=LIVE,policy=probe_policy,forced=k,after=e['t']) for k in (0,1)]) for tag,i,o,g,e in chosen]
    batch(name+' immediate build vs one wait under the recurrent head',[a for *_,gs in groups for a in gs])
    ext=extend_groups([gs for *_,gs in groups]);ex=tails(ext);rows=[]
    for tag,i,o,g,e,gs in groups:
        marks=[probe(a) for a in gs]
        votes=[next(s for s in trace(a)['switches'] if s['phase']=='arrival_vote' and round(30*s['t'])==round(30*e['t'])) for a in gs]
        assert votes[0]['x']==votes[1]['x']==e['x'] and [v['place'] for v in votes]==[False,True]
        assert marks[0]['prefix']==marks[1]['prefix'] and trace(gs[int(e['place'])])['log_sha256']==trace(g)['log_sha256']
        tick=round(e['t']*30)
        for j,a in enumerate(gs):
            builds=[c for c in trace(a)['accepted_commands'] if c['tick']==tick and c['kind']=='deploy' and c['accepted'] and (c['card'],c['x'],c['y'])==(e['target'][1],e['target'][3],e['target'][4])]
            assert len(builds)==j
        rows.append(dict(set=tag,id=i,opponent=o,t=e['t'],prefix=marks[0]['prefix'],x=e['x'],site=e['target'],choice=int(e['place']),keys=[a.key() for a in gs],
                         results=[val(a) for a in gs],target=utility(gs[0],gs[1],ex)))
    fixed(OUT/(name+'.json'),dict(eligible=len(cases)+len(chosen),rows=rows,extensions=ext))
def visited(heads):
    provisional=candidate('provisional',heads,(-.035,.045,.02),True)
    enc=[(s,i,o,live_game(i,p,provisional,c)) for s,i,o,c,p in dev_encounters(history=True)]
    batch('roll out provisional one-action gate against fixed plants',[g for *_,g in enc])
    groups=[]
    for j,(tag,i,o,g) in enumerate(enc):
        opts=[e for e in trace(g)['switches'] if e['phase']=='lease' and 'x' in e]
        if not opts:continue
        # Keep both sides of the return decision. Include sites with and without
        # an available forward option and do not filter on terminal outcomes.
        goal=(15.,55.,125.,220.)[j%4]
        e=min(opts,key=lambda e:(e['from']!=1,not bool(e['mask']&15),int(e['choice']!=0)!=(j%2),abs(e['t']-goal)))
        gs=[replace(g,forced=k,after=e['t']) for k in range(3 if e['offered'] and j%2==0 or e['choice']==2 else 2)]
        groups.append((tag,i,o,g,e,gs))
    batch('at visited decisions, return to z16 or renew the alternative for one move',[a for *_,gs in groups for a in gs])
    ext=extend_groups([gs for *_,gs in groups]);ex=tails(ext);rows=[]
    for tag,i,o,ref,e,gs in groups:
        marks=[probe(a) for a in gs];assert all(m['prefix']==marks[0]['prefix'] and m['x']==e['x'] for m in marks)
        assert trace(gs[e['choice']])['log_sha256']==trace(ref)['log_sha256']
        rows.append(dict(set='historic' if tag=='history' else tag,id=i,opponent=o,t=e['t'],prefix=marks[0]['prefix'],x=e['x'],mask=e['mask'],prior=e['from'],choice=e['choice'],
                         results=[val(g) for g in gs],keys=[g.key() for g in gs],targets=[utility(gs[0],g,ex) for g in gs]))
    fixed(OUT/'visited.json',dict(rows=rows,model=sha(provisional),extensions=ext))
    arrival_checks('visited-arrivals',enc,provisional,18)
def pair_report(gr,side):
    return paired_result(gr,side,[a.uid for a,_ in next(iter(gr.values()))])
def flatten(gr):return [g for rows in gr.values() for pair in rows for g in pair]
def winscore(report):
    rows=report['rows']
    return dict(kept=sum(r['old']==r['new']==1 for r in rows),old_wins=sum(r['old']==1 for r in rows),
        lost=sum(r['old']==1 and r['new']!=1 for r in rows),true_gain=sum(r['old']==-1 and r['new']==1 for r in rows),
        win_delta=sum(int(r['new']==1)-int(r['old']==1) for r in rows),stalls=sum(r['stall'] for r in rows))
def score(report,side):
    w=winscore(report);a,b=[report['tempo'][k] for k in ('parent','candidate')]
    x,y=[m['common_window_deploys_per_min'][side] for m in (a,b)]
    penalty=max(0.,1-y/max(x,.01))*max(1,w['old_wins'])*1.5
    return w['win_delta']-.65*w['lost']-w['stalls']-penalty
def train_zombie():
    if not (OUT/'earlier-arrivals.json').exists():supplement_arrivals()
    heads=training_rows()
    if not (OUT/'visited-arrivals.json').exists():visited(heads)
    heads=training_rows(True)
    paths={k:candidate('single-'+k,heads,v) for k,v in [('open',(-.04,.03,0.)),('middle',(.08,.13,.08)),('selective',(.25,.29,.16))]}
    ids=read(OUT/'splits.json')['val'];history=read(OUT/'review.json')['rows'];reports={};replays={};diffs={};comp=[]
    groups={k:{o:[(live_game(i,p,PARENT),live_game(i,p,w)) for i in ids] for o,p in TEACHERS.items()} for k,w in paths.items()}
    historic={k:[(r,live_game(r['id'],MODELS[r['opponent']],PARENT,PREVIOUS_CORPUS),live_game(r['id'],MODELS[r['opponent']],w,PREVIOUS_CORPUS)) for r in history] for k,w in paths.items()}
    batch('validate trained margins, including all 18 historical regressions',[g for gr in groups.values() for g in flatten(gr)]+[g for rs in historic.values() for _,a,b in rs for g in (a,b)])
    def hist_score(rows):
        # Repeated opponents on the same opening share weight.
        unique=defaultdict(list)
        for r in rows:unique[r['id']].append(int(r['new']==1)-int(r['old']==1)-.65*int(r['old']==1 and r['new']!=1))
        return float(np.mean([np.mean(x) for x in unique.values()]))
    for k in paths:
        gr=groups[k];reports[k]=pair_report(gr,'zombie');diffs[k]=sum(trace(a)['log_sha256']!=trace(b)['log_sha256'] for rs in gr.values() for a,b in rs)
        replays[k]=[dict(id=r['id'],opponent=r['opponent'],old=val(a),previous=r['results'][2],single=r['results'][1],new=val(b),key=b.key()) for r,a,b in historic[k]]
        comp.extend((a,b,'zombie') for rs in gr.values() for a,b in rs)
        comp.extend((a,b,'zombie') for _,a,b in historic[k])
    selected=max(paths,key=lambda k:(bool(diffs[k]),score(reports[k],'zombie')+4*hist_score(replays[k]),winscore(reports[k])['true_gain']))
    alternate=max(paths,key=lambda k:(winscore(reports[k])['true_gain']+sum(r['old']==-1 and r['new']==1 for r in replays[k]),score(reports[k],'zombie'),hist_score(replays[k])))
    if diffs[alternate]==0:alternate=selected
    fixed(OUT/'zombie.json',dict(alternate=str(paths[alternate]),alternate_sha=sha(paths[alternate]),path=str(paths[selected]),sha256=sha(paths[selected]),selected=selected,validation=reports,
         regressions=replays,distinct=diffs,training=[info for _,info in heads],extensions=extend(comp)))
def train_plant():
    z=read(OUT/'zombie.json');frozen=Path(z['path']);assert sha(frozen)==z['sha256']
    parent=read(PLANT);w=np.array(parent['heads']['weight'])[:12,-28:]
    direction=w-np.array(read(STRONG)['heads']['weight'])[:12,-28:]
    rng=np.random.default_rng(654131);cross=rng.normal(size=w.shape)
    cross-=np.sum(cross*direction)/np.sum(direction**2)*direction;cross*=np.linalg.norm(direction)/np.linalg.norm(cross)
    paths={}
    for nm,d in [('along',direction),('cross',cross)]:
        for tag,sign in [('p',1),('m',-1)]:
            m=read(PLANT)
            for j,row in enumerate(w+sign*.65*d):m['heads']['weight'][j][-28:]=row.tolist()
            m['training_source']=dict(parent=sha(PLANT),frozen_zombie=sha(frozen),method='paired return and common-window deployments')
            p=OUT/'models'/('plant-'+nm+tag+'.json');fixed(p,m);paths[nm+tag]=p
    splits=read(OUT/'splits.json')
    def pairs(p,ids):
        return {'single':[(live_game(i,PLANT,frozen),live_game(i,p,frozen)) for i in ids],
            'persistent':[(live_game(i,PLANT,ACTIVE),live_game(i,p,ACTIVE)) for i in ids],
            'r22':[(live_game(i,PLANT,None,zombie=None,position=None),live_game(i,p,None,zombie=None,position=None)) for i in ids]}
    gr={k:pairs(p,splits['train']) for k,p in paths.items()};batch('reverse sides: plant search with fixed opponents',[g for x in gr.values() for g in flatten(x)])
    reports={k:pair_report(x,'plant') for k,x in gr.items()};best=sorted(paths,key=lambda k:score(reports[k],'plant'),reverse=True)[:2]
    vs={k:pairs(paths[k],splits['val']) for k in best};batch('plant paired validation',[g for x in vs.values() for g in flatten(x)])
    vr={k:pair_report(x,'plant') for k,x in vs.items()};win=max(best,key=lambda k:score(vr[k],'plant'))
    ext=extend((a,b,'plant') for table in (gr,vs) for x in table.values() for rs in x.values() for a,b in rs)
    fixed(OUT/'plant.json',dict(path=str(paths[win]),sha256=sha(paths[win]),selected=win,zombie=sha(frozen),prior=sha(PLANT),
                               validation=vr,training=reports,extensions=ext))
def supplement_arrivals():
    prior=read(LAST/'walk.json')['rows'];front={r['prefix']:r for r in read(LAST/'front.json')['rows']}
    # These older paired interventions share the same trip until the native
    # placement succeeds or is omitted. Recollect the public arrival features.
    groups=[]
    for j,r in enumerate(prior):
        if not r['arrival']:continue
        row=front[r['prefix']]
        old_receipt=read(LAST/'games'/(r['keys'][1]+'.jsonl.receipt.json'))
        params=old_receipt['parameters'];gs=[]
        for k in (0,1):
            constant=dict(linear=[0.]*32,hb=[],head=[],hidden=[],bias=float(2*k-1))
            cfg=dict(start='event',target=r['target'],arrival=constant,arrival_margin=0.,full_inputs=True)
            w=policy(f'arrival-legacy-{j}-{k}',cfg)
            from switch_study import OLD_CORPUS
            gs.append(game(r['id'],MODELS[r['opponent']],w,OLD_CORPUS,forced=2,after=params['after']))
        groups.append((r,gs))
    batch('recollect live state on earlier matched arrival choices',[g for _,gs in groups for g in gs])
    ext=extend_groups([gs for _,gs in groups]);ex=tails(ext);rows=[]
    for r,gs in groups:
        es=[next(v for v in trace(g)['switches'] if v['phase']=='arrival_vote') for g in gs];t=round(es[0]['t']*30)
        assert es[0]['x']==es[1]['x'] and [e['place'] for e in es]==[False,True] and t==round(30*r['arrival']['t'])
        assert [trace(g)['log_sha256'] for g in gs]==[read(LAST/'games'/(r['keys'][j]+'.jsonl.receipt.json'))['battle'] for j in (3,1)]
        c,d=[commands(g) for g in gs];assert {k:v for k,v in c.items() if k<t}=={k:v for k,v in d.items() if k<t}
        rows.append(dict(set='earlier',id=r['id'],opponent=r['opponent'],site=r['target'],t=es[0]['t'],prefix=r['prefix'],x=es[0]['x'],
                   keys=[g.key() for g in gs],results=[val(g) for g in gs],target=utility(gs[0],gs[1],ex)))
    fixed(OUT/'earlier-arrivals.json',dict(rows=rows,extensions=ext))
def stats(rows):
    return dict(kept=sum(r['old']==r['new']==1 for r in rows),gain=sum(r['old']==-1 and r['new']==1 for r in rows),
                lost=sum(r['old']==1 and r['new']!=1 for r in rows),
                old=[sum(r['old']==v for r in rows) for v in (1,0,-1)],new=[sum(r['new']==v for r in rows) for v in (1,0,-1)])
def troop_tempo(groups,side,catalog):
    totals=defaultdict(lambda:dict(pairs=0,seconds=0.,troops=[0,0],graves=[0,0]))
    for pairs in groups.values():
        for a,b in pairs:
            traces=[trace(a),trace(b)]
            window=min(r['time'] for r in traces)
            outcomes=[outcome(r,side) for r in traces]
            keys=['all']
            if outcomes==[-1,1]:keys.append('old_loss_to_win')
            for key in keys:
                tally=totals[key]
                tally['pairs']+=1;tally['seconds']+=window
                for j,r in enumerate(traces):
                    for e in r['activity']:
                        if e['kind']!='deploy' or e['side']!='zombie' or e['time']>window:continue
                        if not e['card'].startswith('zombie:'):continue
                        grave=catalog[e['card']]['behavior']=='grave'
                        tally['graves' if grave else 'troops'][j]+=1
    for tally in totals.values():
        tally['troops_per_min']=[n*60/tally['seconds'] for n in tally['troops']]
    return totals
def diagnostics(enc,p):
    candidate=[]
    for tag,i,o,g in enc:
        for e in trace(g)['switches']:
            if e['phase']=='lease' and e['mask']&15 and e['from']==1 and e['choice'] in (0,1):
                candidate.append((i,o,g,e))
    chosen=[];used=set()
    for want in (0,1):
        for opponent in 'rhb':
            opts=[it for it in candidate if it[0] not in used and it[1]==opponent and it[3]['choice']==want]
            if not opts:continue
            it=min(opts,key=lambda it:(abs(it[3]['t']-80),it[0],it[3]['t']));used.add(it[0]);chosen.append(it)
    groups=[(i,o,g,e,[replace(g,forced=k,after=e['t']) for k in (0,1)]) for i,o,g,e in chosen]
    batch('sealed same-state return to z16 vs renewal for one action',[a for *_,gs in groups for a in gs])
    rows=[]
    for i,o,g,e,gs in groups:
        marks=[probe(a) for a in gs]
        assert marks[0]['prefix']==marks[1]['prefix'] and marks[0]['x']==marks[1]['x']
        assert trace(gs[e['choice']])['log_sha256']==trace(g)['log_sha256']
        rows.append(dict(id=i,opponent=o,time=e['t'],choice=e['choice'],prefix=marks[0]['prefix'],keys=[a.key() for a in gs],results=[val(a) for a in gs],
                         distinct=trace(gs[0])['log_sha256']!=trace(gs[1])['log_sha256']))
    fixed(OUT/'sealed-choices.json',dict(eligible=len(candidate),rows=rows,extensions=extend_groups([gs for *_,gs in groups])))
    arrival_checks('sealed-arrivals',enc,p,9)
def test():
    split=read(OUT/'splits.json');ids=split['a']+split['b']
    zl,pl=[read(OUT/(k+'.json')) for k in ('zombie','plant')];z,p=Path(zl['path']),Path(pl['path'])
    assert sha(z)==zl['sha256']==pl['zombie'] and sha(p)==pl['sha256']
    fixed(OUT/'sealed-design.json',dict(zombie=sha(z),plant=sha(p),cases=ids,
        troop_metric='Separate actual zombie unit card deployments from grave construction using the release card catalog. Compare both arms within the shorter matched duration.',
        diagnostics='After natural sealed games choose up to one observed return and one renewal per opponent at a genuine public event, unique openings, nearest 80 seconds. At most nine reached arrival choices, balance openings first, nearest 75 seconds. No terminal-result filter or fitting.'))
    alt=Path(zl['alternate']);assert sha(alt)==zl['alternate_sha']
    matrix={k:{} for k in ('z16','persistent','plant')};enc=[]
    if alt!=z:matrix['alternate']={}
    for o in 'rhb':
        opp=MODELS[o]
        matrix['z16'][o]=[(live_game(i,opp,PARENT),live_game(i,opp,z)) for i in ids]
        if alt!=z:matrix['alternate'][o]=[(live_game(i,opp,PARENT),live_game(i,opp,alt)) for i in ids]
        matrix['persistent'][o]=[(live_game(i,opp,ACTIVE),live_game(i,opp,z)) for i in ids]
        matrix['plant'][o]=[(live_game(i,PLANT,None,zombie=opp,position=None),live_game(i,p,None,zombie=opp,position=None)) for i in ids]
        enc.extend(('blind',b.uid,o,b) for _,b in matrix['z16'][o])
    batch('paired blind cohorts on 24 new home openings, both seats vs r22/H/B',[g for gr in matrix.values() for g in flatten(gr)])
    card_file=Path(read(R/'dist/latest-native-release.json')['target']).parent/'extract/data/_resolved_cards.json'
    cards=read(card_file)
    assert all(row['behavior']==cards['night'][k]['behavior'] for k,row in cards['day'].items() if k.startswith('zombie:'))
    reports={};timed=[]
    for label,gr in matrix.items():
        side='plant' if label=='plant' else 'zombie';rep={}
        for k,sub in [('a',split['a']),('b',split['b']),('all',ids)]:
            rep[k]=pair_report({o:[(a,b) for a,b in rs if a.uid in sub] for o,rs in gr.items()},side)
            rows=rep[k]['rows'];rep[k]['counts']=stats(rows)
            by_open=np.array([np.mean([int(r['new']==1)-int(r['old']==1) for r in rows if r['id']==i]) for i in sub])
            rng=np.random.default_rng(652809)
            rep[k]['true_win_delta95']=np.quantile(by_open[rng.integers(0,len(by_open),(20000,len(by_open)))].mean(axis=1),[.025,.975]).tolist()
        rp=rep['all'];both=rp['tempo'];a,b=[both[k] for k in ('parent','candidate')]
        own_a,own_b=[v['common_window_deploys_per_min'][side] for v in (a,b)]
        rep['stable']=bool(rp['counts']['lost']==0 and all(rep[k]['counts']['new'][0]>rep[k]['counts']['old'][0] for k in ('a','b'))
            and rp['true_win_delta95'][0]>0 and own_b>=own_a and not any(r['stall'] for r in rp['rows']))
        rep['native_draws']=[sum(val(pair[j],side)==0 and not trace(pair[j])['timeout'] for rs in gr.values() for pair in rs) for j in (0,1)]
        rep['troop_tempo']=troop_tempo(gr,side,cards['day'])
        if side=='zombie':
            old_rate,new_rate=rep['troop_tempo']['all']['troops_per_min']
            rep['stable']=rep['stable'] and new_rate>=old_rate
        for o,rs in gr.items():
            for a,b in rs:
                if trace(b)['timeout'] and val(a,side):
                    loser='plant' if trace(a)['result']['winner']=='zombie' else 'zombie'
                    timed.append((label,o,side,a,b,loser))
        reports[label]=rep
    extra=extend((a,b,loser) for label,o,side,a,b,loser in timed)
    assert len(timed)==len(extra)
    horizon=[dict(comparison=label,opponent=o,view=side,old=val(a,side),late=val(replace(b,limit=1200),side),**e) for (label,o,side,a,b,_),e in zip(timed,extra)]
    dynamics=[]
    for _,i,o,g in enc:
        tr=trace(g);es=[e for e in tr['switches'] if e['phase']=='lease'];votes=[e for e in tr['switches'] if e['phase']=='arrival_vote']
        dynamics.append(dict(id=i,opponent=o,actions=len(es),new=sum(e['choice']!=0 for e in es),
             returns=sum(e['from']==1 and e['choice']==0 for e in es),public_returns=sum(e['from']==1 and e['choice']==0 and bool(e['mask']&15) for e in es),
             enter=sum(e['from']==0 and e['choice']!=0 for e in es),public=sum(bool(e['mask']&15) for e in es),arrivals=len(votes),defer=sum(not e['place'] for e in votes),
             changed=tr['log_sha256']!=trace(live_game(i,MODELS[o],PARENT))['log_sha256']))
    fixed(OUT/'test.json',dict(zombie=sha(z),plant=sha(p),results=reports,dynamics=dynamics,extensions=horizon))
    diagnostics(enc,z)
def audit():
    check_readouts()
    from option_audit import verify_games
    from switch_fit import allocated
    idx,limits=verify_games(OUT,expected_map='家院')
    for label,src,exe in [('build','native-src',NATIVE),('probe-build','probe-src',OUT/'probe/Release/position_match.exe'),('live-build','live-src',LIVE)]:
        record=read(OUT/(label+'.json'));assert sha(exe)==record['binary']
        for f,h in record['sources'].items():assert sha(OUT/src/f)==h
        for f,h in record['libraries'].items():assert sha(BUILD/'Release'/f)==h
    release=read(R/'dist/latest-native-release.json');assert sha(Path(release['target']))==release['exe_sha256']
    sealed=read(OUT/'sealed-design.json')
    tested=read(OUT/'test.json')
    for seat in ('plant','zombie'):
        frozen=read(OUT/(seat+'.json'))
        assert sha(Path(frozen['path']))==frozen['sha256']==sealed[seat]==tested[seat]
    assert read(OUT/'plant.json')['zombie']==sealed['zombie']
    extensions={};coverage={}
    for label in ('review','arrivals','earlier-arrivals','fresh','visited','visited-arrivals','zombie','plant','test','sealed-choices','sealed-arrivals'):
        rs=read(OUT/(label+'.json'))['extensions']
        coverage[label]=len({r['extended'] for r in rs})
        for e in rs:
            base,a,b=[idx[e[k]] for k in ('base','candidate','extended')]
            assert a['timeout'] and base['winner'] in ('plant','zombie') and base['winner']!=e['side']
            assert {**a['parameters'],'limit':1200}==b['parameters'] and b['winner']==e['winner'] and b['timeout']==e['timeout']
            if e['extended'] not in extensions:
                import gzip,json
                pair=[]
                for k in ('candidate','extended'):
                    with gzip.open(OUT/'games'/(e[k]+'.jsonl.gz'),'rt',encoding='utf8') as f:f.readline();pair.append(json.loads(f.readline()))
                assert [v for v in pair[0]['switches'] if v['t']<600]==[v for v in pair[1]['switches'] if v['t']<600]
                extensions[e['extended']]=e
    assert len(extensions)==limits[1200]
    split=read(OUT/'splits.json');entries=read(CORPUS/'index.json')['entries'];seeds=set();decks=[set(),set()]
    assert sha(CORPUS/'index.json')==split['corpus'] and len(entries)==40
    assert sealed['cases']==split['a']+split['b']
    expected={(i,o) for i in sealed['cases'] for o in 'rhb'}
    live_hash=sha(LIVE)
    for label,summary in tested['results'].items():
        rows=summary['all']['rows']
        assert len(rows)==72 and {(r['id'],r['opponent']) for r in rows}==expected
        assert summary['troop_tempo']['all']['pairs']==len(rows)
        timed={(r['baseline'],r['candidate']) for r in rows if r['old']!=0 and idx[r['candidate']]['timeout']}
        extended={(e['base'],e['candidate']) for e in tested['extensions'] if e['comparison']==label}
        assert timed==extended
        for r in rows:
            for g in ('baseline','candidate'):
                params=idx[r[g]]['parameters']
                assert params['binary']==live_hash and params['corpus']==split['corpus']
    for path in split['indexes']:
        for r in read(R/path)['entries']:
            if r.get('map')=='家院' and 'decks' in r:
                seeds.add(r['seed'])
                for s,d in zip(decks,deck(r)):s.add(d)
    assert not seeds&{r['seed'] for r in entries} and len({r['seed'] for r in entries})==40
    for j in range(2):
        assert len({deck(r)[j] for r in entries})==40 and not {deck(r)[j] for r in entries if r['id'] in split['a']+split['b']}&decks[j]
    assert all(sum(r['night'] for r in entries if r['id'] in split[k])==6 for k in ('a','b'))
    styles={}
    for i in split['train']:
        events={}
        for o,p in TEACHERS.items():
            g=game(i,p,collect_cfg());events[o]=[(v['card'],v['time']) for v in trace(g)['activity'] if v['kind']=='deploy' and v['side']=='plant']
        for a,b in combinations(events,2):styles[a+b]=styles.get(a+b,0)+int(events[a]!=events[b])
    roots=(ROOT,PREV,NIGHT,BUILD,PRIOR_HOME,PRIOR)
    before=allocated(roots);assert before<CAP
    cleaned=0
    for variant in ('native','live','probe'):
        folder=(OUT/variant/'position_match.dir'/'Release').resolve();assert folder.is_relative_to(OUT.resolve())
        for name in ('position_match.obj','tactical_session.obj'):
            path=folder/name
            if path.exists():cleaned+=path.stat().st_size;path.unlink()
    physical=allocated(roots);assert physical<CAP and not list((OUT/'temp').glob('*.jsonl'))
    fixed(OUT/'audit.json',dict(games=len(idx),limits={str(k):v for k,v in limits.items()},extensions=coverage,distinct_extended=len(extensions),
        prior_indexes=len(split['indexes']),differing_plant_deployment_traces=styles,official=release['version'],sha256=release['exe_sha256'],
        allocated_before_cleanup=before,allocated_after_cleanup=physical,removed_objects=cleaned,cap=CAP,run_bytes=size(OUT)))
def check_readouts():
    zl=read(OUT/'zombie.json');p=Path(zl['path']);config=read(p)['switch'];splits=read(OUT/'splits.json')
    instrument=policy('final-score-probes',{**config,'sample':True});cases=[]
    for i,o in ((splits['a'][0],'r'),(splits['b'][1],'b')):
        source=live_game(i,MODELS[o],p)
        cases.append((source,replace(source,policy=instrument)))
        for baseline in (PARENT,ACTIVE):
            g=replace(source,policy=baseline);cases.append((g,replace(g,binary=PREVIOUS_NATIVE)))
    batch('full-log parity and native neural score reproduction',[b for _,b in cases])
    for a,b in cases:assert trace(a)['log_sha256']==trace(b)['log_sha256']
    count=Counter()
    def scalar(x,head):
        x=np.asarray(x)
        return float(head['bias']+x@np.asarray(head['linear'])+np.dot(np.tanh(np.asarray(head['hidden'])@x+head['hb']),head['head']))
    for a,b in cases:
        if b.policy!=instrument:continue
        for e in trace(b)['switches']:
            if e['phase']=='lease' and 'x' in e:
                q=scalar(e['x'],config['one_head']);assert abs(q-e['v'])<1e-8
                f=scalar(e['x'],config['trip_head']) if e['offered'] else -100.
                assert abs(f-e['trip'])<1e-8
                choice=int(q>config['one_margin'])
                if e['offered'] and f>config['trip_margin'] and f>q:choice=2
                assert choice==e['choice'];count['leases']+=1
    for i in splits['a']+splits['b']:
        for o in 'rhb':
            g=live_game(i,MODELS[o],p)
            for e in trace(g)['switches']:
                if e['phase']=='arrival_vote':
                    q=scalar(e['x'],config['arrival_live'])
                    assert abs(q-e['gain'])<1e-8 and e['place']==(q>=-config['arrival_margin'])
                    count['arrivals']+=1
    fixed(OUT/'readout-parity.json',dict(pairs=[[a.key(),b.key()] for a,b in cases],predictions=dict(count)))
