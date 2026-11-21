"""Learn both ranked-seven pick/ban policies from paired native game continuations."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from dataclasses import replace
import gzip
import json
import shutil
import sqlite3
import sys
import tempfile
import time
import zlib

from ranked_corpus import create
from ranked_draft import *
from ranked_special_setup import EXE
from league_data import ROOTS,TOTAL_LIMIT, OLD_Z,BASE,CARDS,local,sha
from league_run import physical
from option_games import Game,play,trace

V2=bool(PROFILE.get('draft_v2'))
LANES=int(PROFILE.get('draft_lanes',3))
HOLDOUT=48 if V2 else 24
HERO_HP=40.
META=lambda:read(BATTLE/'opponents.json')
COMBAT_CATALOG=read(CARDS)['day']
if PROFILE:
    weight_dir=Path(PROFILE.get('weights_dir',BATTLE/'weights'))
    BASE=weight_dir/'macro.json';OLD_Z=weight_dir/'position.json'

def setting(i,room,holdout):
    group=i//2
    maps=[m for m in room.catalog['maps'] if m!=HOME]
    return dict(seed=(PROFILE.get('seed_offset',0))+(9700000 if holdout else 9200000)+(group if holdout else i),
                map_name=HOME if PROFILE.get('day_league') or group%4!=3 else maps[(group//4)%len(maps)],
                night=False if PROFILE.get('day_league') else bool((group//4+group)%2),
                weather='clear' if PROFILE.get('day_league') else ('rain' if (group+group//4)%5==1 else 'clear'))

def controllers(i):
    m=META()
    return [('r22','r22'),(m['pool']['away'],'r22'),(m['pool']['H'],m['champion'])][(i//2)%3]

def fight(sc,i,folder,combat=None):
    case=folder/'c';entries=create(case,[sc])
    plant,z=combat or controllers(i)
    (folder/'temp').mkdir()
    g=Game('000',None if plant=='r22' else Path(plant),zombie=None if z=='r22' else BASE,
           position=None if z=='r22' else OLD_Z,policy=None if z=='r22' else Path(z),binary=EXE,corpus=case,storage=folder)
    if PROFILE.get('day_league'):
        from ranked_day_league import combat_game
        g=combat_game(case,'000',plant,z,folder)
    def run(game):
        play(game);t=trace(game)
        actions={s:[a['time'] for a in t['activity'] if a['kind']=='deploy' and a['side']==s] for s in SIDES}
        troops=[a['time'] for a in t['activity'] if a['side']=='zombie' and a['kind']=='deploy'
                and a['card'].startswith('zombie:') and COMBAT_CATALOG[a['card']]['behavior']!='grave']
        return dict(winner=(t['result'] or {}).get('winner'),timeout=t['timeout'],seconds=t['time'],log=t['log_sha256'],
                    actions=actions,troops=troops,**({'hp':t['hp']} if V2 else {})),t
    r,t=run(g)
    if r['timeout']:
        lg=replace(g,limit=1200)
        e,t2=run(lg)
        for k,field in [('activity','time'),('accepted_commands','time')]:
            assert [a for a in t[k] if a[field]<600]==[a for a in t2[k] if a[field]<600]
        r['extension']={k:e[k] for k in ('winner','timeout','seconds','log',*(('hp',) if V2 else ()))}
    return r

def reward(r,side):
    if r['timeout']:
        late=r['extension']
        return 0 if late['timeout'] or late['winner']=='draw' else (.65 if late['winner']==side else -.65)
    return 0 if r['winner']=='draw' else (1 if r['winner']==side else -1)

def utility(r,side):
    """draft_v2: outcome first; final hero damage breaks ties among equal outcomes (|shaping|<=.3).
    Damage dealt to the enemy hero is offensive progress, so this never rewards merely surviving longer."""
    base=reward(r,side)
    if not V2:return base
    end=r['extension'] if r['timeout'] and r.get('extension') else r
    hp=end.get('hp')
    if not hp:return base
    foe=SIDES[1-SIDES.index(side)]
    frac=lambda s:min(1.,max(0.,hp[s]/HERO_HP))
    # Decided games: the winner prefers finishing sooner, the loser prefers holding out longer (zero-sum,
    # so it never rewards both seats for a slow game; slow-and-longer branches are vetoed separately).
    sign=0 if end['timeout'] or end['winner'] in (None,'draw') else (1 if end['winner']==foe else -1)
    return base+.3*((1-frac(foe))-(1-frac(side)))+.15*sign*min(1.,end['seconds']/1200)

def reduced(sc):
    d={k:v for k,v in sc.items() if k!='rules'}
    if PROFILE:d['rules']={k:sc['rules'][k] for k in (*RULES,'build')}
    return d

def pair(i,net,holdout=False):
    room=Room()
    try:
        arg=setting(i,room,holdout)
        base=DraftNet(room.catalog) if holdout else net
        if PROFILE and holdout:base.load(DRAFT/'initial.npz')
        who=SIDES[i%2]
        start={s:base for s in SIDES}
        fixed=bool(PROFILE and not holdout and (i//2)%2==0)
        if fixed:start[SIDES[1-SIDES.index(who)]]=DraftNet(room.catalog).load(DRAFT/'initial.npz')
        combat=controllers(i)
        if PROFILE.get('day_league') and not holdout and (i//2)%4==3:
            champions=read(BATTLE/'state.json')['sides']
            combat=tuple(champions[s]['champ'] for s in SIDES)
        detail=dict(i=i,phase='blind' if holdout else 'train',seat=who,setup=arg,controllers=combat,fixed_draft_opponent=fixed)
        if holdout and V2:
            # Tested seat greedy, opposing seat samples the initial head: 48 distinct matchups instead of one.
            a,dec=draft(room,start,**arg,greedy_sides={who},width=256)
        else:a,dec=draft(room,start,**arg,greedy=holdout,width=256)
        pref=None
        if holdout:
            b,_=draft(room,{**start,who:net},**arg,greedy=not V2,greedy_sides={who} if V2 else None,width=256)
        else:
            eligible=[j for j,(s,f,p,q,_) in enumerate(dec) if s==who and p!=q]
            if not eligible:raise RuntimeError('no legal fork')
            # Cycle pick / unit-ban / secret-ban and early / late stages without selecting any designated cards.
            groups={}
            for j in eligible:
                h=a['draft_history'][j]
                groups.setdefault((h['stage'],h['kind'],h['category']),[]).append(j)
            options=list(groups.values());group=options[(i//2)%len(options)]
            j=group[(i//(len(options)*2))%len(group)]
            _,f,p,q,offers=dec[j]
            method='second sampled action'
            if PROFILE and a['draft_history'][j]['kind']=='pick' and (i//2)%3==0:
                def role(k):
                    c=net.cards[k]
                    return c['category'],bool(net.parents[k]),bool(c.get('producer')),c.get('economy')
                different=[n for n,k in enumerate(offers) if role(k)!=role(offers[p])]
                if different:
                    scores=net.predict(f);q=max(different,key=lambda n:scores[n]);method='different legal card role'
            if a['draft_history'][j]['kind']=='ban' and (i//2)%4!=0:
                # Search allocation only. Replay a legal ban that could deny a later voluntary pick.
                # The network at inference sees only the original public prefix and the full legal set.
                foe=SIDES[1-SIDES.index(who)]
                suffix={h['card'] for h in a['draft_history'][j+1:] if h['side']==foe and h['kind']=='pick'}
                candidates=[n for n,k in enumerate(offers) if k in suffix and n!=p]
                if candidates:
                    value=net.predict(f);q=max(candidates,key=lambda n:value[n]);method='denial counterfactual'
            b,_=draft(room,start,**arg,fork=(j,offers[p],offers[q]),width=256)
            assert a['draft_history'][:j]==b['draft_history'][:j]
            detail.update(step=j+1,stage=a['draft_history'][j]['stage'],kind=a['draft_history'][j]['kind'],
                          category=a['draft_history'][j]['category'],alternatives=[offers[p],offers[q]],legal=len(offers),fork_method=method)
            pref=(f,p,q)
        detail['drafts']=[reduced(a),reduced(b)]
        if a['battle_error'] or b['battle_error']:
            detail['unstartable']=[a['battle_error'],b['battle_error']]
            return detail,None,[]
        def signature(sc):return [sc['decks'],sc['bans']]
        same=signature(a)==signature(b)
        with tempfile.TemporaryDirectory(prefix='p',dir=DRAFT/'scratch') as tmp:
            path=Path(tmp)
            x=fight(a,i,path/'a',combat)
            y=x if same else fight(b,i,path/'b',combat)
        detail.update(same_setup=same,games=1 if same else 2,arms=[x,y],utility=[reward(r,who) for r in (x,y)])
        if V2:detail['dense']=[utility(r,who) for r in (x,y)]
        weak=[] if holdout or reward(x,'plant')==0 else [(s,f,p) for s,f,p,_,_ in dec if not fixed or s==who]
        if V2 and pref:return v2_preference(detail,pref,x,y,who,weak)
        if PROFILE and pref:
            t=min(x['seconds'],y['seconds'])
            def activity(r):
                return sum(n<=t for n in (r['troops'] if who=='zombie' else r['actions']['plant']))
            slower=[activity(a)+1<=.85*activity(b) and a['seconds']>1.15*b['seconds'] for a,b in ((x,y),(y,x))]
            if slower[0]:weak=[row for row in weak if row[0]!=who]
            detail['slow_and_longer']=slower
            if detail['utility']==[1,1] and any(slower):
                f,p,q=pref;detail['preference_reason']='true wins with different deployment tempo'
                return detail,(f,q if slower[0] else p,p if slower[0] else q,.25),weak
        # An unresolved timeout caused by slower deployment on both seats provides no preference.
        def idle_timeout():
            if 0 not in detail['utility']:return False
            t=min(x['seconds'],y['seconds'])
            def count(r,s):return sum(k<=t for k in r['actions'][s])
            positive,negative=(x,y) if detail['utility'][0]>detail['utility'][1] else (y,x)
            return positive['timeout'] and all(count(positive,s)<count(negative,s) for s in SIDES)
        if not holdout and pref and detail['utility'][0]!=detail['utility'][1] and not idle_timeout():
            better=detail['utility'][0]>detail['utility'][1]
            f,p,q=pref
            if PROFILE and slower[0 if better else 1] and detail['utility'][0 if better else 1]<=0:
                return detail,None,weak
            detail['preference_reason']='outcome'
            return detail,(f,p if better else q,q if better else p,abs(detail['utility'][0]-detail['utility'][1])/2),weak
        return detail,None,weak
    finally:room.close()

def v2_preference(detail,pref,x,y,who,weak):
    t=min(x['seconds'],y['seconds'])
    def own(r):return sum(n<=t for n in (r['troops'] if who=='zombie' else r['actions']['plant']))
    def both(r):return sum(n<=t for s in SIDES for n in r['actions'][s])
    # Slow-and-longer: own deployments in the common window drop by 15%+ and the game runs 15%+ longer.
    slower=[own(a)+1<=.85*own(b) and a['seconds']>1.15*b['seconds'] for a,b in ((x,y),(y,x))]
    idle=[both(a)+1<=.85*both(b) and a['seconds']>1.15*b['seconds'] for a,b in ((x,y),(y,x))]
    detail['slow_and_longer']=slower;detail['both_idle']=idle
    if slower[0]:weak=[row for row in weak if row[0]!=who]
    u=detail['dense'];base=detail['utility'];f,p,q=pref
    diff=u[0]-u[1];better=0 if diff>0 else 1
    if abs(diff)>=.1:
        # A slower branch may only win the preference with a true regular-time win over a non-win.
        if (slower[better] or idle[better]) and not (base[better]==1 and base[1-better]<1):
            detail['preference_reason']='rejected: better branch slower and longer';return detail,None,weak
        detail['preference_reason']='outcome' if base[0]!=base[1] else 'hero damage tie-break'
        w=abs(base[0]-base[1])/2 if base[0]!=base[1] else min(.15,abs(diff)/2)
        return detail,(f,p if better==0 else q,q if better==0 else p,w),weak
    if slower[0]!=slower[1]:
        detail['preference_reason']='equal outcome, faster deployment'
        return detail,(f,q if slower[0] else p,p if slower[0] else q,.15),weak
    return detail,None,weak

def counts(db,phase):
    return db.execute('select count(*) from trials where phase=?',(phase,)).fetchone()[0]

def rows(db,phase):
    return [json.loads(zlib.decompress(r[0])) for r in db.execute('select data from trials where phase=? order by id',(phase,))]

def insert(db,d):
    db.execute('insert into trials values(?,?,?)',(d['phase'],d['i'],zlib.compress(json.dumps(d,ensure_ascii=False,separators=(',',':')).encode(),5)))

def summarize(data):
    stats={}
    for side in SIDES:
        trials=[d for d in data if d['seat']==side and 'arms' in d]
        changes=Counter();late=Counter();tempo=[0,0];troops=[0,0];window=0;times=[0,0];strong=Counter()
        for d in trials:
            x,y=d['arms']
            def label(r):return 'T' if r['timeout'] or r['winner']=='draw' else 'W' if r['winner']==side else 'L'
            k=label(x)+label(y);changes[k]+=1
            if k=='LT':
                e=y['extension'];late['T' if e['timeout'] or e['winner']=='draw' else 'W' if e['winner']==side else 'L']+=1
            t=min(x['seconds'],y['seconds']);window+=t
            for j,r in enumerate((x,y)):
                tempo[j]+=sum(a<=t for a in r['actions'][side]);times[j]+=r['seconds']
                troops[j]+=sum(a<=t for a in r['troops'])
            strong[(d['controllers'][0]=='r22',k)]+=1
        stats[side]=dict(pairs=len(trials),transitions=dict(changes),loss_to_timeout_extended=dict(late),
                         deployments_per_minute=[n*60/max(1,window) for n in tempo],seconds=[n/max(1,len(trials)) for n in times],
                         troops_per_minute=[n*60/max(1,window) for n in troops],
                         by_controller={'r22_mirror' if k else 'historical':{r:n for (flag,r),n in strong.items() if flag==k}
                                        for k in (True,False)})
    return stats

def main():
    DRAFT.mkdir(parents=True,exist_ok=True);(DRAFT/'scratch').mkdir(exist_ok=True)
    db=sqlite3.connect(DRAFT/'draft.sqlite')
    db.execute('create table if not exists trials(phase text,id integer,data blob not null, primary key(phase,id))')
    db.execute('create table if not exists checkpoints(id integer primary key,weights blob not null)')
    db.commit()
    room=Room()
    try:net=DraftNet(room.catalog)
    finally:room.close()
    first=DRAFT/'initial.npz';live=DRAFT/'current.npz'
    if not first.exists():
        if PROFILE:net.load(Path(PROFILE['draft_parent']))
        net.save(first)
    else:net.load(first)
    last=db.execute('select weights from checkpoints order by id desc limit 1').fetchone()
    if last:live.write_bytes(last[0]);net.load(live)
    if not (DRAFT/'clock.json').exists():
        now=time.time()
        write(DRAFT/'clock.json',dict(started=now,train_until=PROFILE.get('deadline',now+7200),lanes=LANES,heldout_per_seat=HOLDOUT,
              initial=sha(first),mode=RULES,room=sha(ROOM),controllers=[controllers(2*i) for i in range(3)]))
    clock=read(DRAFT/'clock.json');epoch=counts(db,'train');updates=Counter();baseline=Counter();observed=Counter();policy_steps=Counter()
    for d in rows(db,'train'):
        if d.get('update'):updates[d['seat']]+=1
        if d.get('arms'):
            k=tuple(d['controllers']);baseline[k]+=utility(d['arms'][0],'plant');observed[k]+=1
        policy_steps.update(d.get('policy_steps',{}))
    last_gauge=0
    def guard():
        nonlocal last_gauge
        if shutil.disk_usage(DRAFT).free<24*2**30:raise RuntimeError('disk floor reached')
        if not PROFILE and time.monotonic()-last_gauge>240:
            used=physical(ROOTS);last_gauge=time.monotonic()
            if used>TOTAL_LIMIT-128*2**20:raise RuntimeError('total training disk budget reached')
        if sum(p.stat().st_size for p in DRAFT.glob('*') if p.is_file())>256*2**20:raise RuntimeError('draft storage budget reached')
    completed={r[0] for r in db.execute("select id from trials where phase='train'")}
    next_trial=0;pending={}
    with ThreadPoolExecutor(LANES) as pool:
        while time.time()<clock['train_until'] and not (DRAFT/'frozen.npz').exists():
            guard()
            while len(pending)<LANES:
                while next_trial in completed:next_trial+=1
                f=pool.submit(pair,next_trial,deepcopy(net))
                pending[f]=epoch;next_trial+=1
            done,_=wait(pending,timeout=min(20,max(0,clock['train_until']-time.time())),return_when=FIRST_COMPLETED)
            for f in done:
                if time.time()>=clock['train_until']:break
                source=pending.pop(f)
                detail,update,trajectory=f.result()
                with db:
                    detail['source_epoch']=source
                    detail['catalog_inputs']='dependencies, declared targets and public descriptions'
                    detail['update']=bool(update)
                    if 'arms' in detail:
                        key=tuple(detail['controllers']);payoff=utility(detail['arms'][0],'plant')
                        advantage=payoff-baseline[key]/(4+observed[key]);step_counts=Counter()
                        # The matched preference remains interpretable under its saved policies.
                        # Use unsupervised trajectory credit only for near-current policy draws.
                        if epoch-source<=3:
                            for s,features,p in trajectory:
                                net.reinforce(features,p,advantage if s=='plant' else -advantage)
                                step_counts[s]+=int(len(features[2])>1)
                        detail['policy_steps']=dict(step_counts);policy_steps.update(step_counts)
                        baseline[key]+=payoff;observed[key]+=1
                    if update:net.prefer(*update);updates[detail['seat']]+=1
                    insert(db,detail)
                    epoch+=1;net.save(live)
                    db.execute('delete from checkpoints');db.execute('insert into checkpoints values(?,?)',(epoch,live.read_bytes()))
                write(DRAFT/'status.json',dict(phase='training',pairs_attempted=epoch,direct_preferences=dict(updates),policy_steps=dict(policy_steps),
                      updated=local(time.time()),stop=local(clock['train_until']),weights=sha(live)))
        frozen=DRAFT/'frozen.npz'
        if not frozen.exists():net.save(frozen)
        if not (DRAFT/'freeze.json').exists():
            write(DRAFT/'freeze.json',dict(actual=local(time.time()),epoch=epoch,sha256=sha(frozen)))
        for f in pending:f.cancel()
        net.load(frozen);finished=counts(db,'blind')
        for i in range(finished,HOLDOUT*2,LANES):
            guard()
            with db:
                for d,_,_ in pool.map(lambda n:pair(n,net,True),range(i,min(i+LANES,HOLDOUT*2))):insert(db,d)
            write(DRAFT/'status.json',dict(phase='blind',trials=epoch,blind_attempted=counts(db,'blind'),updated=local(time.time())))
    test=rows(db,'blind');training=rows(db,'train')
    write(DRAFT/'results.json',dict(mode=RULES,started=local(clock['started']),freeze=local(clock['train_until']),frozen=sha(frozen),
        updates=dict(updates),policy_steps=dict(policy_steps),attempts=len(training),unstartable=sum('unstartable' in d for d in training),blind_attempts=len(test),
        blind_unstartable=sum('unstartable' in d for d in test),training_games=sum(d.get('games',0) for d in training),
        blind_games=sum(d.get('games',0) for d in test),blind=summarize(test),
        examined={s:dict(Counter(d['stage'] for d in training if d['seat']==s and d.get('update'))) for s in SIDES}))
    write(DRAFT/'status.json',dict(phase='complete',updated=local(time.time()),weights=sha(frozen)))
    db.close()

if __name__=='__main__':
    import msvcrt
    DRAFT.mkdir(parents=True,exist_ok=True)
    with (DRAFT/'run.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'x');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:sys.exit('another ranked draft trainer is running')
        main()
