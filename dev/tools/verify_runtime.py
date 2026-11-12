"""Independent operation traces from CPython deque and the unchanged original profiler."""
import argparse,collections,hashlib,importlib.util,itertools,json,os,random,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3] if Path(__file__).resolve().parent.name=='runtime29' else Path(__file__).resolve().parents[1]
REFERENCE=Path(r'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(REFERENCE/'modkit'))
    from pvp.native_multiworker import PhaseProfiler
    from pvp.rendering import Renderer
    sets=[list(x for x in range(3) if mask&(1<<x)) for mask in range(8)]
    # Reverse insertion order on half the pairs; set relations cannot depend on it.
    set_cases=[[left[::-1],right] for left in sets for right in sets]
    rng=random.Random(83029);deques=[]
    for maximum in (None,0,1,4,-1,2.5):
        actions=[['append',99],['extendleft',[7,8]],['rotate',-2],['copy_append',500]]
        for _ in range(80):
            op=rng.choice(['append','appendleft','extend','extendleft','pop','popleft','clear','reverse','rotate','count','remove','getitem','setitem','delitem','contains','copy_append'])
            if op in ('extend','extendleft'):args=[rng.sample(range(8),3)]
            elif op in ('clear','reverse','pop','popleft'):args=[]
            elif op=='setitem':args=[rng.randrange(-5,6),rng.randrange(8)]
            else:args=[rng.randrange(-5,6) if op in ('rotate','getitem','delitem') else rng.randrange(8)]
            actions.append([op]+args)
        actions += [['rotate',1.5],['getitem',1.5],['remove',999],['clear'],['pop'],['popleft']]
        deques.append(dict(initial=[0,1,2],maxlen=maximum,actions=actions))
    profiles=[dict(limit=limit,rolling=rolling,values=[['work',float(i%11)] for i in range(7002)]+[['present',2.5],['present',8.5]]) for limit,rolling in itertools.product((0,3,6000),(False,True))]
    spec=dict(sets=set_cases,deques=deques,profiles=profiles)
    expected=dict(sets=[],deques=[],profiles=[],vars={})
    fixture=ROOT/'tools/testshim/argument_fixture.py'
    definition=importlib.util.spec_from_file_location('argument_reference',fixture)
    reference=importlib.util.module_from_spec(definition);definition.loader.exec_module(reference)
    expected['arguments']=[reference.run_order(),reference.run_duplicate(),reference.run_bad_mapping()]
    for a,b in set_cases:
        a,b=set(a),set(b);expected['sets'].append([a<b,a<=b,a==b,a>=b,a>b])
    for row in deques:
        try:d=collections.deque(row['initial'],maxlen=row['maxlen'])
        except Exception as error:expected['deques'].append(dict(error=type(error).__name__));continue
        states=[]
        for action in row['actions']:
            op,*args=action;state={}
            try:
                result=None
                if op=='getitem':result=d[args[0]]
                elif op=='setitem':d[args[0]]=args[1]
                elif op=='delitem':del d[args[0]]
                elif op=='contains':result=args[0] in d
                elif op=='copy_append':copy=d.copy();copy.append(args[0]);result=list(copy)
                else:result=getattr(d,op)(*args)
                state['result']=result
            except Exception as error:state['error']=type(error).__name__
            state.update(values=list(d),maxlen=d.maxlen);states.append(state)
        expected['deques'].append(states)
    for row in profiles:
        p=PhaseProfiler(limit=row['limit'],rolling=row['rolling'])
        for phase,value in row['values']:p.record(phase,value)
        expected['profiles'].append(p.summary())
    renderer=Renderer.__new__(Renderer);renderer.text_scale=2;renderer.custom_probe=7
    view=vars(renderer);expected['vars']['initial']=view.copy()
    view['text_scale']=3;renderer.custom_probe=8;expected['vars']['live']=view.copy()
    del view['text_scale'];expected['vars']['deleted']=view.copy()
    (out/'inputs.json').write_text(json.dumps(spec),encoding='utf-8');(out/'python.json').write_text(json.dumps(expected),encoding='utf-8')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    exe=ROOT/'build/Release/cpp_tests.exe';digest=sha(exe)
    env=os.environ.copy();env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PVP_USERDATA=str(out/'native-userdata'))
    with (out/'native.log').open('w',encoding='utf-8') as log:
        run=subprocess.run([str(exe),'--runtime-report',str(out/'inputs.json'),str(out/'native.json')],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:raise RuntimeError('Native report failed')
    actual=json.loads((out/'native.json').read_text(encoding='utf-8'));differences=[]
    def walk(a,b,path=''):
        if isinstance(a,dict) and isinstance(b,dict):
            if set(a)!=set(b):differences.append(dict(path=path,python_keys=sorted(a),native_keys=sorted(b)));return
            for key in a:walk(a[key],b[key],path+'/'+key)
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):differences.append(dict(path=path,python_len=len(a),native_len=len(b)));return
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
        elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
            if abs(a-b)>1e-9:differences.append(dict(path=path,python=a,native=b))
        elif type(a)!=type(b) or a!=b:differences.append(dict(path=path,python=a,native=b))
    walk(expected,actual)
    (out/'differences.json').write_text(json.dumps(differences,indent=2),encoding='utf-8')
    summary=dict(set_pairs=len(set_cases),deque_constructors=len(deques),deque_steps=sum(len(x) for x in expected['deques'] if isinstance(x,list)),profile_cases=len(profiles),profile_records=sum(len(x['values']) for x in profiles),differences=len(differences),exe_sha256=digest,exe_unchanged=digest==sha(exe),reference_sources={str(REFERENCE/'modkit/pvp'/name):sha(REFERENCE/'modkit/pvp'/name) for name in ('native_multiworker.py','rendering.py')})
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    return int(bool(differences) or not summary['exe_unchanged'])
if __name__=='__main__':raise SystemExit(main())
