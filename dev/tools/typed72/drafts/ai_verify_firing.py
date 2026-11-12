import argparse,ast,collections,copy,hashlib,json,math,random,subprocess,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cases():
    rng=random.Random(726619);out=[]
    cards=[dict(id='plant:'+str(i),name=name,behavior=behavior,lob=lob) for i,(name,behavior,lob) in enumerate([('豌豆射手','shoot',False),('三向射手','shoot',False),('裂荚射手','shoot',False),('卷心菜投手','shoot',True),('甜椒投手','shoot',True),('玉米加农炮','mortar',True),('猫尾草','shoot',False),('向日葵','produce',False)])]
    for n in range(96):
        card=copy.deepcopy(cards[n%len(cards)]);card['range']=(None,3.,31.,32.,600.,3000.)[n%6]
        solid=[[0]*20 for _ in range(12)];solid[-1]=[1]*20
        if n%4:
            for row in range(3+(n%6),11):solid[row][10]=1
        targets=[] if n%5==0 else [dict(x=x,y=528.,h=height) for x,height in [(600.,72.),(120.,86.4),(rng.uniform(1,959),0.)]]
        ops=[]
        for t in [0.,.1,.49,.5,.51,1.,2.,3.,4.,5.]:
            op=dict(card=card,solid=copy.deepcopy(solid),targets=copy.deepcopy(targets),x=408.+(n%3)*48,y=504.,time=t,facing=-1 if n%2 else 1,segment=[rng.uniform(-200,1100),rng.uniform(-100,600),rng.uniform(-200,1100),rng.uniform(-100,600)])
            if t>=3 and op['targets']:op['targets'][0]['x']-=96.
            if t>=4:op['solid'][7][10]=0
            ops.append(op)
        out.append(dict(operations=ops))
    # Failure eviction: source preserves insertion order on an update and
    # stably evicts the earliest expiry, then insertion order, in groups of 32.
    ops=[]
    for i in range(180):
        solid=[[0]*180 for _ in range(6)];solid[3]=[1]*180
        ops.append(dict(card=cards[0],solid=solid,targets=[dict(x=48.*i+80,y=180,h=80)],x=i*48.+24,y=168.,time=0.,width=8640.))
    out.append(dict(operations=ops));return out
def modules():
    name='typed72_firing_reference';package=types.ModuleType(name);package.__path__=[];sys.modules[name]=package
    observation=types.ModuleType(name+'.rv_observation');tree=ast.parse((SOURCE/'rv_observation.py').read_text(encoding='utf8'));body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='wrap_delta'];exec(compile(ast.Module(body=body,type_ignores=[]),str(SOURCE/'rv_observation.py'),'exec'),observation.__dict__);sys.modules[observation.__name__]=observation
    module=types.ModuleType(name+'.rv_firing66');module.__package__=name;exec(compile((SOURCE/'rv_firing66.py').read_text(encoding='utf8'),str(SOURCE/'rv_firing66.py'),'exec'),module.__dict__);sys.modules[module.__name__]=module
    tree=ast.parse((SOURCE/'rv_tactics19.py').read_text(encoding='utf8'));plant=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PlantTactics');method=next(n for n in plant.body if isinstance(n,ast.FunctionDef) and n.name=='lane_direction');cls=ast.ClassDef(name='Controller',bases=[],keywords=[],body=[method],decorator_list=[]);env={'__package__':name};exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'native r19 lane_direction','exec'),env);return module,env['Controller']
def reference(case,module,controller):
    state=controller();state.log=collections.defaultdict(int);out=[]
    for op in case['operations']:
        card=copy.deepcopy(op['card']);tiles=[[dict(solid=bool(v)) for v in row] for row in op['solid']];context=types.SimpleNamespace(width=op.get('width',960.),tile=op.get('tile',48.),snap=dict(map=dict(tiles=tiles)),enemy=op['targets'],b={},foe={},card=lambda key:card,t=op['time'])
        assessment=module.firing_assessment(context,card['id'],op['x'],op['y'],op.get('facing',1));direction=module.firing_direction(context,card['id'],op['x'],op['y'],op.get('facing',1));remembered=state.lane_direction(context,card['id'],op['x'],op['y'],op.get('facing',1));row=dict(assessment=assessment,direction=direction,remembered=remembered,memo_count=len(getattr(state,'lane_failures',{})),blocked=getattr(state,'lane_blocked',False),last_card=getattr(state,'last_blocked_card',''),blocked_count=state.log['skip:blocked_firing_lane'],turn_count=state.log['route_replan:turn'])
        if 'segment' in op:row['segment']=module.clear_segment(context,tiles,*op['segment'])
        out.append(row)
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    stage=ROOT/'build/typed72-room-stage';paths=[a.exe.resolve(),Path(__file__).resolve(),SOURCE/'rv_firing66.py',SOURCE/'rv_tactics19.py',SOURCE/'rv_observation.py',stage/'build-inputs.json'];paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());pins={str(p):sha(p) for p in paths};(a.out/'pins.json').write_text(dump(pins),encoding='utf8')
    module,controller=modules();inputs=cases();expected=[reference(c,module,controller) for c in inputs]
    for name,values in [('inputs',inputs),('expected',expected)]:(a.out/(name+'.jsonl')).write_text('\n'.join(dump(v) for v in values)+'\n',encoding='utf8')
    with (a.out/'probe.log').open('wb') as log:run=subprocess.run([str(a.exe.resolve()),str((a.out/'inputs.jsonl').resolve()),str((a.out/'actual.jsonl').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=120)
    actual=[json.loads(line) for line in (a.out/'actual.jsonl').read_text(encoding='utf8').splitlines()];failures=[]
    for i,want in enumerate(expected):
        if i>=len(actual) or len(actual[i])!=len(want):failures.append(dict(case=i,error='missing or extra states'));continue
        for j,(x,y) in enumerate(zip(want,actual[i])):
            if x!=y:failures.append(dict(case=i,step=j,expected=x,actual=y));break
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]];summary=dict(cases=len(inputs),pass_cases=len(inputs)-len(failures),states=sum(map(len,expected)),returncode=run.returncode,changed_inputs=changed,failures=failures,scope='actual rv_firing66 and r19 lane_direction with explicit public target/card fixtures; binary64 arc boundary differs if effective V math differs from CPython')
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}));return 1 if failures or changed or run.returncode or len(actual)!=len(expected) else 0
if __name__=='__main__':raise SystemExit(main())
