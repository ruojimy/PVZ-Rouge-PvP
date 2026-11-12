import argparse,ast,copy,hashlib,json,math,random,subprocess,types
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def select(path,names,env):
    tree=ast.parse(path.read_text(encoding='utf8'));nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names];exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env);return env
def cases():
    rng=random.Random(721922);out=[]
    def tiles():
        values=[[dict(solid=row==20,water=False) for col in range(72)] for row in range(24)]
        for row in range(20):
            for col in (10,20,35):values[row][col].update(ladder=True,kind='梯子块')
        return values
    def hero(x=504,y=960):return dict(x=x,y=y,hp=40,max_hp=40,resource=200)
    for i in range(48):
        ops=[]
        for j in range(28):
            me=hero(x=(i%8)*48+(.5*48 if j<18 else (j-18)*12))
            ops.append(dict(op='drive',time=j*[.1,.35,.5][i%3],me=me,target=me['x']+[-1200,-50,0,10,25,100,1200][i%7],jump_wish=j%5==0,tolerance=[20,6.72,0][i%3]))
        out.append(dict(kind='tactical',side='plant' if i%2 else 'zombie',tiles=tiles(),operations=ops))
    for i in range(16):
        ops=[]
        for j,t in enumerate([0.,.1,1.,3.,3.1,7.]):
            ops.append(dict(op='deploy',time=t,me=hero(),card='plant:豌豆射手',x=-2.1+i*7.9,y=940,grave=None if i%2 else 'grave',facing=-1 if i%3 else 1,placement_error='坚实地面需要花盆或无土栽培' if j==0 and i%4==0 else '',placement=not(j==0 and i%4==1),send_error='rejected' if j in (0,1) and i%4==2 else ''))
        out.append(dict(kind='tactical',side='plant',tiles=tiles(),operations=ops))
    for i in range(24):
        ops=[]
        for j in range(12):
            x=[400,504,516,960][i%4];y=900-j*18 if i<12 else 500+j*18
            me=hero(x,y);op=dict(op='ladder',time=j*.35,me=me,post=700,goal_y=400 if i<12 else 900,mode=['duo','coop','pve','duel'][i%4])
            if i%8==0 and j in (3,4):op['goal_y']=y
            if i%8==1 and j>3:op['me']['y']=900
            if i%8==2 and j==5:op['deathmatch']=True
            if i%8==3 and j==5:op['recovering']=True
            if i%8==4 and j==5:op['reason']='local_danger'
            if i%8==5 and j==5:op['threats']=[dict(source='projectile',eta_ms=349)]
            if i%8==6 and j==5:op['me']['hp']=15
            if i%8==7 and j==5:op['hold_until']=3.
            if j==6:op['recovering']=False;op['hold_until']=None
            ops.append(op)
        out.append(dict(kind='tactical',side='plant' if i%2 else 'zombie',tiles=tiles(),operations=ops))
    for i in range(16):
        ops=[]
        units=[dict(id='u'+str(k),side='plant',hp=50,max_hp=50,x=24+k*48,y=960,behavior=['shoot','pot','lily'][k%3],mobile=k%5==0,card_id='plant:pea',card={}) for k in range(16)]
        for free in [False,True]:ops.append(dict(op='spots',time=0,me=hero(i*48),units=units,free=free))
        for t in [0,1,2]:
            for reserve in [0,100,101]:ops.append(dict(op='ready',time=t,me=hero(),card='plant:pea',reserve=reserve,deathmatch=i%2==0))
        out.append(dict(kind='tactical',side='plant',tiles=tiles(),cards={'plant:pea':dict(cost=100,cooldown=1,producer=i%3==0)},operations=ops))
    tree=ast.parse((SOURCE/'rv_human70.py').read_text(encoding='utf8'));values=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RESIDUAL' for t in n.targets));keys=list(values)
    out.append(dict(kind='human_prior',decks=[rng.choices(keys,k=7) for _ in range(60)]+[['missing'],[],keys]))
    return out

def reference(case):
    wrap=lambda a,b,width:((b-a)%width-width if (b-a)%width>width/2 else (b-a)%width)
    env=dict(math=math,Counter=Counter,wrap_delta=wrap,VIEW_HALF_WIDTH=480.,VIEW_ABOVE=384.,VIEW_BELOW=256.,TILE=48.)
    if case['kind']=='human_prior':
        exec(compile((SOURCE/'rv_human70.py').read_text(encoding='utf8'),str(SOURCE/'rv_human70.py'),'exec'),env);return [env['human_feature']('plant',deck) for deck in case['decks']]
    env.update(ZONES=6);select(SOURCE/'rv_field.py',{'Field'},env);select(SOURCE/'rv_tactics_v6.py',{'in_view','sgn','Ctx','Controller'},env);select(SOURCE/'rv_tactics19.py',{'TeamSupportMixin'},env)
    controller=env['Controller']();controller.ladder_drive=types.MethodType(env['TeamSupportMixin'].ladder_drive,controller);sent=[];metrics={'previews':0,'resets':0};operation={};cards=case.get('cards',{})
    def send(side,kind,**fields):sent.append(dict(side=case.get('owner',side),type=kind,**fields));return operation.get('send_error','')
    controller.send=send
    class Preview:
        @staticmethod
        def from_snapshot(snap,bridge):return Preview()
        def placement(self,*args):metrics['previews']+=1;return operation.get('placement_error',''),operation.get('placement',True)
    env['PreviewBattle']=Preview;env['resolve_card']=lambda key,secrets,bans,night:cards[key]
    terrain=dict(width=case.get('width',3456),height=len(case['tiles'])*case.get('tile',48),tile_size=case.get('tile',48),tiles=case['tiles'],environment={});field=env['Field'](terrain);out=[];side=case['side'];other='plant' if side=='zombie' else 'zombie'
    for operation in case['operations']:
        me=copy.deepcopy(operation['me']);me['cooldowns']={k:v.get('cooldown',0) for k,v in cards.items()}
        snap=dict(map=terrain,bans=[],battle=dict(time=operation.get('time',0),players={side:me,other:operation.get('foe',{})},units=operation.get('units',[]),deathmatch=operation.get('deathmatch',False),mode=operation.get('mode','duo')))
        context=env['Ctx'](side,snap,dict(threats=operation.get('threats',[])),field,None)
        if 'recovering' in operation:controller.recovering=operation['recovering']
        if 'hold_until' in operation:controller.hold_refuge=(0,0,operation['hold_until']) if operation['hold_until'] is not None else None
        controller.support_decision=dict(reason=operation.get('reason'))
        kind=operation['op']
        if kind=='drive':value=controller.drive(context,operation['target'],operation.get('jump_wish',False),operation.get('tolerance',20))
        elif kind=='ladder':value=controller.ladder_drive(context,operation['post'],operation['goal_y'])
        elif kind=='spots':value=context.spots(operation.get('free',True))
        elif kind=='ready':value=context.ready(operation['card'],operation.get('reserve',0))
        else:
            before=len(sent);value=controller.try_deploy(context,operation['card'],operation['x'],operation['y'],operation.get('grave'),operation.get('facing',1))
            if not value and len(sent)>before:metrics['resets']+=1
        state=dict(jump_down=controller.jump_down,blocked=controller.blocked,next_jump=controller.next_jump,last_pos=controller.last_pos,stuck_since=getattr(controller,'stuck_since',None),detour_until=getattr(controller,'detour_until',0),failed=controller.failed,log=controller.log,ladder_route=getattr(controller,'ladder_route',None),ladder_backoff_until=getattr(controller,'ladder_backoff_until',0),sent=sent,**metrics)
        out.append(copy.deepcopy(dict(result=value,state=state)))
    return json.loads(dump(out))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    paths=[args.exe.resolve(),Path(__file__).resolve()]+[SOURCE/n for n in ['rv_tactics_v6.py','rv_tactics19.py','rv_human70.py','rv_field.py','rv_observation.py']];stage=ROOT/'build/typed72-room-stage';paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());paths.append(stage/'build-inputs.json');pins={str(p):sha(p) for p in paths};(args.out/'pins.json').write_text(dump(pins),encoding='utf8')
    inputs=cases();expected=[reference(c) for c in inputs]
    for name,values in [('inputs',inputs),('expected',expected)]: (args.out/(name+'.jsonl')).write_text('\n'.join(dump(v) for v in values)+'\n',encoding='utf8')
    with (args.out/'probe.log').open('wb') as log:run=subprocess.run([str(args.exe.resolve()),str((args.out/'inputs.jsonl').resolve()),str((args.out/'actual.jsonl').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=120)
    actual=[json.loads(line) for line in (args.out/'actual.jsonl').read_text(encoding='utf8').splitlines()];failures=[]
    for i,want in enumerate(expected):
        if i>=len(actual):failures.append(dict(case=i,error='missing output'));continue
        if want!=actual[i]:
            for j,(a,b) in enumerate(zip(want,actual[i])):
                if a!=b:failures.append(dict(case=i,step=j,expected=a,actual=b));break
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]];summary=dict(cases=len(inputs),pass_cases=len(inputs)-len(failures),states=sum(len(v) for v in expected),returncode=run.returncode,changed_inputs=changed,failures=failures,scope='actual Controller v6 drive/deploy, Ctx ready/spots, r19 ladder_drive and r22 human70 prior; full tactical/draft chain remains pending')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}));return 1 if failures or changed or run.returncode else 0
if __name__=='__main__':raise SystemExit(main())
