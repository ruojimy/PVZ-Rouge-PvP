import argparse, copy, hashlib, importlib.util, json, math, random, shutil, subprocess, sys, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def cases():
    rng=random.Random(7219105)
    catalog={
        'plant:pea':dict(name='豌豆',behavior='shoot',cost=100,damage=20,category='plant'),
        'plant:sun':dict(name='太阳花',behavior='produce',cost=50,producer=True,category='plant'),
        'plant:pot':dict(name='花盆',behavior='pot',cost=25,category='plant'),
        'plant:lily':dict(name='荷叶',behavior='lily',cost=25,category='plant'),
        'plant:mushroom':dict(name='蘑菇',behavior='shoot',cost=75,mushroom=True,range=288,category='plant'),
        'plant:玉米加农炮':dict(name='玉米加农炮',behavior='cannon',cost=500,category='plant'),
        'secret:test':dict(name='秘笈',behavior='secret',cost=0,category='secret'),
        'zombie:basic':dict(name='僵尸',behavior='walk',cost=50,damage=12,category='zombie'),
        'zombie:grave':dict(name='墓碑',behavior='grave',cost=50,producer=True,category='zombie'),
    }
    def hero(x,y=800): return dict(x=x,y=y,w=38,h=91,hp=40,max_hp=40,resource=300,deck=list(catalog),cooldowns={},facing=1,grounded=True)
    def unit(i,side,x,y,card,hp=50):
        c=catalog[card]
        return dict(id='u'+str(i),side=side,card_id=card,x=x,y=y,hp=hp,max_hp=100,mobile=side=='zombie' and c['behavior']!='grave',behavior=c['behavior'],card=copy.deepcopy(c),awake=True,vx=0)
    result=[]
    for index in range(96):
        side='plant' if index%2==0 else 'zombie';width=960 if index%3==0 else 3456
        me=hero(rng.choice([0,48,479.9,width-1,width/2]));enemy=hero((me['x']+width/2)%width)
        me.update(hp=rng.choice([0,1,9,20,39,40,60]),vx=-3.9,vy=1.1,jump_cap=3,jumps=index%5,poison_level=index%4,teleport_ready_at=4.25,cannon_aim='u1')
        units=[]
        for i in range(45):
            s=rng.choice(['plant','zombie']);key=rng.choice(list(catalog));u=unit(i,s,rng.uniform(-width,width*2),rng.uniform(300,1300),key,rng.choice([-1,0,1,50,100,150]))
            u.update(awake=rng.choice([True,False]),mobile=rng.choice([True,False]),vx=rng.choice([-80,0,40]))
            if i%7==0:u.pop('behavior')
            units.append(u)
        units.extend([unit(100,'plant',me['x'],me['y'],'plant:pot'),unit(101,'plant',me['x']+23.9,me['y']-48,'plant:pea'),unit(102,'plant',me['x']-72,me['y'],'plant:pot')])
        shots=[]
        for i in range(18):
            shots.append(dict(id='s'+str(i),side='zombie' if i%3 else 'plant',x=me['x']+rng.choice([-300,-48,0,48,300]),y=me['y']-rng.choice([0,46,200]),vx=rng.choice([-1000,0,1000]),vy=rng.choice([-100,0,100]),gravity=rng.choice([-900,0,900]),damage=rng.choice([0,1,10,100]),slow=i%4==0,control=i%5==0,splash=40 if i%2 else 0,asset='冰豆'))
        resources=[dict(id='r'+str(i),side='plant' if i%4 else 'zombie',x=me['x']+rng.choice([-480.1,-480,-20.2,20.8,480,480.1]),y=me['y']+rng.choice([-384.1,-384,0,256,256.1]),amount=25.5,source='sun') for i in range(20)]
        players={side:me,('zombie' if side=='plant' else 'plant'):enemy}
        frames=[]
        for sample in range(4):
            battle=dict(players=copy.deepcopy(players),units=copy.deepcopy(units),projectiles=shots,resources=resources,time=sample*.125,tick=sample,deathmatch=index%4==0,map={'environment':{'night':index%5==0}})
            battle['players'][side]['resource']+=sample*13 if sample<3 else -20
            battle['players'][side]['cooldowns']={'plant:pea':.25,'plant:sun':100}
            frames.append(dict(battle=battle,plan_id=3,match_id=7,observation_id=sample))
        if index%24==0:frames.append({'battle':{'players':{}}})
        if index%24==1:
            invalid=copy.deepcopy(frames[0]);invalid['battle']['players']['zombie' if side=='plant' else 'plant']['input']={'move':0};frames.append(invalid)
        result.append(dict(kind='observation',side=side,width=width,catalog=catalog,frames=frames))
    for index in range(48):
        side='plant' if index%2==0 else 'zombie';enemy_side='zombie' if side=='plant' else 'plant'
        me=hero(500);mate=hero(1300);me['resource']=1000;me['deck']=['plant:pea','plant:pot','secret:test'];mate['hp']=15
        players={side:me,side+'2':mate,enemy_side:dict(hero(2500),absent=True)}
        units=[unit(1,side,500,800,'plant:pea',100),unit(2,side,520,800,'plant:sun',100),unit(3,enemy_side,1400,800,'zombie:basic',100),unit(4,enemy_side,1401,800,'zombie:basic',100)]
        frames=[]
        for time in [0,1,5,12,13,21,22]:
            b=dict(players=copy.deepcopy(players),units=copy.deepcopy(units),time=time,mode='duo',team={'fallen':[]},deathmatch=False,local_seat=side+'2' if index%3==0 else side)
            for u in b['units']:
                if u['side']==side:u['seat']=b['local_seat']
            threats=[]
            branch=index//2%24
            if branch==1:b['players'].pop(side+'2')
            elif branch==2:b['players'][side+'2']['hp']=0
            elif branch==3:b['players'][side]['hp']=20
            elif branch==4:b['units'][2]['x']=501
            elif branch==5:b['units'][2]['x']=700
            elif branch==6:threats=[dict(source='projectile',eta_ms=699)]
            elif branch==7:b['players'][enemy_side].update(x=600,absent=False)
            elif branch==8:b['players'][side]['ready']={'plant:pea':False}
            elif branch==9:b['players'][side]['resource']=100
            elif branch==10:b['units'][0]['hp']=1
            elif branch==11:b['units'].pop(1)
            elif branch==12:b['players'][side+'2']['x']=1600
            elif branch==13:b['players'][side+'2']['y']=1200
            elif branch==14:b['units']=b['units'][:2]
            elif branch==15:
                for u in b['units'][2:]:u['card']['cost']=5000
            elif branch in (16,17):
                b['team']['fallen']=[side if b['local_seat']==side+'2' else side+'2'];b['players'][side+'2']['hp']=0
                if branch==17:b['units']=b['units'][:2]
            elif branch==18:b['units'][2]['x']=1000
            elif branch==19:b['mode']='duel'
            elif branch==20:
                if time>=5:b['units']=b['units'][:2]
            elif branch==21:
                if time>=5:b['players'][side]['hp']=22
            elif branch==22:b['deathmatch']=True;b['units'].pop(1)
            elif branch==23:b['players'][side+'2']['absent']=True
            frames.append(dict(battle=b,home=[500,800],threats=threats))
        result.append(dict(kind='team_support',side=side,width=3456,catalog=catalog,frames=frames))
    return result

def load_sources(directory):
    pvp=types.ModuleType('pvp');pvp.__path__=[];sys.modules['pvp']=pvp
    catalog=types.ModuleType('pvp.catalog');catalog.CARDS={};catalog.actual_card=lambda key,secrets,night:catalog.CARDS[key];sys.modules['pvp.catalog']=catalog
    def load(name,filename):
        spec=importlib.util.spec_from_file_location(name,str(directory/filename));module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
    observation=load('pvp.rv_observation','rv_observation.py');support=load('pvp.rv_team_support66','rv_team_support66.py')
    return catalog,observation,support

def reference(case,modules,native=True):
    catalog,obs,support=modules;catalog.CARDS.clear();catalog.CARDS.update(copy.deepcopy(case['catalog']))
    obs._round=(lambda value,digits=2:round(float(value)*10.**digits)/10.**digits) if native else (lambda value,digits=2:round(float(value),digits))
    out=[];side=case['side']
    if case['kind']=='observation':
        builder=obs.ObservationBuilder(side,case.get('width',3456),case.get('height',1152),case.get('tile',48),case.get('night',False))
        for frame in case['frames']:
            try:out.append(builder.build(frame,frame.get('plan_id',0),frame.get('match_id',0),frame.get('observation_id',0)))
            except obs.ObservationError as e:out.append({'error':str(e)})
    else:
        brain=support.TeamSupport()
        for frame in case['frames']:
            b=copy.deepcopy(frame['battle']);me=b['players'][side]
            c=types.SimpleNamespace(b=b,me=me,side=side,t=b.get('time',0),width=case.get('width',3456),tile=case.get('tile',48),deathmatch=b.get('deathmatch',False),obs={'threats':frame.get('threats',[])})
            c.own=[u for u in b['units'] if u['side']==side];c.enemy=[u for u in b['units'] if u['side']!=side]
            c.card=lambda k:catalog.CARDS[k];c.ready=lambda k:me.get('ready',{}).get(k,True)
            decision=brain.decide(c,frame['home'])
            out.append(copy.deepcopy(dict(decision=decision,active=brain.active,until=brain.until,cooldown_until=brain.cooldown_until,quiet_since=brain.quiet_since,last=brain.last)))
    return out

def differences(a,b,path='$'):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return [(path+'.keys',sorted(a),sorted(b))]
        return [d for k in a for d in differences(a[k],b[k],path+'.'+k)]
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return [(path+'.len',len(a),len(b))]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'['+str(i)+']')]
    if a==b:return []
    return [(path,a,b)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    frozen=args.out/'reference';frozen.mkdir()
    for name in ['rv_observation.py','rv_team_support66.py']:shutil.copy2(str(SOURCE/name),str(frozen/name))
    paths=[args.exe.resolve(),Path(__file__).resolve(),SOURCE/'rv_observation.py',SOURCE/'rv_team_support66.py',ROOT/'src/core/pymath.h']
    stage=ROOT/'build/typed72-room-stage';paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());paths.append(stage/'build-inputs.json')
    pins={str(p):sha(p) for p in paths};(args.out/'pins.json').write_text(dump(pins),encoding='utf8')
    inputs=cases();expected=[];cpython=[];modules=load_sources(frozen)
    for case in inputs:expected.append(reference(case,modules));cpython.append(reference(case,modules,False))
    for name,values in [('inputs',inputs),('expected',expected),('cpython',cpython)]: (args.out/(name+'.jsonl')).write_text('\n'.join(dump(v) for v in values)+'\n',encoding='utf8')
    run=subprocess.run([str(args.exe.resolve()),str((args.out/'inputs.jsonl').resolve()),str((args.out/'actual.jsonl').resolve())],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8')
    (args.out/'probe.log').write_text(run.stdout,encoding='utf8');actual=[json.loads(line) for line in (args.out/'actual.jsonl').read_text(encoding='utf8').splitlines()]
    failures=[]
    for i in range(max(len(expected),len(actual))):
        diff=differences(expected[i],actual[i]) if i<min(len(expected),len(actual)) else [('$','missing line',i)]
        if diff:failures.append(dict(case=i,kind=inputs[i]['kind'],differences=diff[:30]))
    native_round_diffs=[dict(case=i,differences=differences(cpython[i],expected[i])[:30]) for i in range(len(expected)) if cpython[i]!=expected[i]]
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]]
    summary=dict(cases=len(inputs),states=sum(len(c['frames']) for c in inputs),pass_cases=len(inputs)-len(failures),failures=failures,returncode=run.returncode,changed_inputs=changed,native_round_contract='effective src/core/pymath.h py::roundn scaled ties-even; CPython differences separately recorded',cpython_round_differences=native_round_diffs)
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k not in ('failures','cpython_round_differences')}));print('failures',len(failures),'CPython round cases',len(native_round_diffs));return 1 if failures or changed or run.returncode else 0
if __name__=='__main__':raise SystemExit(main())
