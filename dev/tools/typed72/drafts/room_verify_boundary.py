import argparse,ast,copy,hashlib,json,math,random,struct,subprocess,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def selected(path,names,env):
    tree=ast.parse(path.read_text(encoding='utf8'));body=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),env);return env
def cases():
    rng=random.Random(720519);out=[]
    for index in range(24):
        rows=8+index%6;cols=12+index%12;tiles=[[dict(solid=rng.random()<.2,water=rng.random()<.15) for _ in range(cols)] for _ in range(rows)]
        queries=[dict(zone=z,x=x,y=y,limit=limit) for z,x,y,limit in [(rng.randrange(-1,7),rng.uniform(-200,cols*48+200),rng.choice([0,200,400,800]),rng.choice([-4,-1,0,1,8,100])) for _ in range(24)]]
        queries.extend(dict(zones=True,x=x) for x in [0,48,cols*24,cols*48-1]);out.append(dict(kind='field',tiles=tiles,width=cols*48,height=rows*48,queries=queries))
    for index in range(16):
        messages=[dict(type='room_snapshot',tick=i,text='中文🥔',state=[True,None,i]) for i in range(4)]
        raw=b''.join(struct.pack('!I',len(dump(v).encode('utf8')))+dump(v).encode('utf8') for v in messages)
        steps=[dict(encode=v) for v in messages];pos=0
        while pos<len(raw):end=min(len(raw),pos+rng.randint(1,31));steps.append(dict(feed=raw[pos:end].hex()));pos=end
        out.append(dict(kind='wire',steps=steps))
    for raw in [b'\x00\x00\x00\x00',b'\xff\xff\xff\xff',b'\x00\x00\x00\x02[]',b'\x00\x00\x00\x07{"a":}',b'\x00\x00\x00\x08{"a":\xff}',b'\x00\x00\x00\x0a{"a":1e99}']:
        out.append(dict(kind='wire',maximum=64,steps=[dict(feed=raw.hex())]))
    for index in range(8):
        steps=[]
        for i in range(20):
            p=dict(type='latency_probe' if i%2 else 'latency_echo',nonce='0123456789abcdef')
            if i%5==0:p['extra']=1
            if i%7==0:p['nonce']='0123456789abcdeF'
            steps.append(dict(time=(i//4)*.25 if index%2 else i*.1,payload=p))
        out.append(dict(kind='latency',steps=steps))
    pairs=[]
    for old_map in [None,False,True,0,1,'',[],{}]:
        for stream in [None,0,1,'x','']:
            old=dict(type='message',peer_id='peer',payload=dict(type='room_snapshot',map_included=old_map,snapshot_stream=stream))
            for changed in [False,True]:
                new=copy.deepcopy(old)
                if changed:new['peer_id']='other'
                pairs.append([new,old])
    out.append(dict(kind='supersedes',pairs=pairs))
    deck=['pea','sun','secret:no'];plans=[{},None,[],dict(priority=[]),dict(priority=['pea','pea','sun']),dict(priority=['secret:no']),dict(priority=[False]),dict(priority=['missing'])]
    for key in ['reserve','target_x','distance','deploy_ahead','economy_offset','jump_every','teleport_hp']:
        for value in [True,None,'',-1,0,1.25]:plans.append(dict(priority=['pea'],**{key:value}))
    for q in [None,[],{'pea':False},{'pea':1.0},{'pea':-1},{'pea':701},{'pea':700},{'unknown':1}]:plans.append(dict(priority=['pea'],quotas=q))
    for s in ['hold','advance','hunt','kite','retreat','bad',None]:plans.append(dict(priority=['pea'],stance=s))
    for value in [None,False,0,'',[],{},'pea','sun']:
        plans.append(dict(priority=['pea'],save_for=value,mark=value,evade=value,command=value))
    out.append(dict(kind='plan',deck=deck,plans=plans))
    payloads=[dict(type='gift',seq=1,amount=100,unknown=42),None,[],{},dict(type='move',move=1,jump=True,edge=3,right=False,request=1,seq=2)]
    out.append(dict(kind='replay_fields',payloads=payloads))
    steps=[]
    for build in ['1.6.0.72-native.20261104','other']:
        for entity in ['unit','',False,{},['x']]:
            for kwargs in [{},[],None,{'width':2}]:
                snap=dict(native_frame=dict(tile=48,commands=[dict(op='primitive',primitive='line',args=[[50,50,50],[1,2],[3,4],2],entity=entity,kwargs=kwargs)]))
                steps.append(dict(snapshot=snap,format='pvz-pvp-replay-1',build=build))
    out.append(dict(kind='rope',steps=steps))
    out.append(dict(kind='digest',payloads=[{},None,[],True,dict(z=-0.,a=1.,数字='中文\n\t\u0001',arr=[1e16,1e-7,.1,1.2345678901234567]),dict(a=9007199254740993,b=1e20),dict(emoji='🥔',line='x\r\ny')]))
    return out

def references():
    network=selected(SOURCE/'network.py',{'ProtocolError','_reject_constant','_finite_float','_decode','encode_frame','FrameDecoder','supersedes_snapshot','valid_latency_payload','allow_latency_payload'},dict(json=json,math=math,struct=struct,MAX_FRAME_BYTES=1024*1024,_HEADER=struct.Struct('!I'),LATENCY_KINDS=('latency_probe','latency_echo')))
    obs=selected(SOURCE/'rv_observation.py',{'wrap_delta'},{});field=selected(SOURCE/'rv_field.py',{'Field'},dict(obs,VIEW_ABOVE=384,VIEW_BELOW=256,VIEW_HALF_WIDTH=480,ZONES=6))
    controls=selected(SOURCE/'rv_realtime_controls.py',{'validate_plan'},dict(math=math))
    replay=selected(ROOT/'tools/pvp72_sources/replay.py',{'matches_state_hash'},dict(copy=copy,FORMAT='pvz-pvp-replay-1'))
    tree=ast.parse((ROOT/'tools/pvp72_sources/replay.py').read_text(encoding='utf8'));fields=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='INPUT_FIELDS' for t in n.targets))
    return network,field,controls,replay,fields

def native_number(v):
    d=float(v)
    if d==math.floor(d) and abs(d)<1e16:return str(int(d))
    for precision in range(1,18):
        result=format(d,'.'+str(precision)+'g')
        if float(result)==d:break
    return result if any(c in result for c in '.eEn') else result+'.0'
def canonical(v):
    if v is None:return 'null'
    if isinstance(v,bool):return 'true' if v else 'false'
    if isinstance(v,(int,float)):return native_number(v)
    if isinstance(v,str):return dump(v)
    if isinstance(v,list):return '['+','.join(canonical(x) for x in v)+']'
    return '{'+','.join(dump(k)+':'+canonical(v[k]) for k in sorted(v))+'}'
def reference(c,refs):
    n,field,controls,replay,fields=refs;kind=c['kind'];out=[]
    if kind=='field':
        f=field['Field'](dict(width=c['width'],height=c['height'],tile_size=c.get('tile',48),tiles=c['tiles']))
        for q in c['queries']:out.append(f.zones_in_view(q['x']) if q.get('zones') else f.candidates(q['zone'],q['x'],q.get('y'),q.get('limit',8)))
    elif kind=='wire':
        decoder=n['FrameDecoder'](c.get('maximum',1024*1024))
        for step in c['steps']:
            if 'encode' in step:
                try:out.append(dict(encoded=n['encode_frame'](step['encode'],c.get('maximum',1024*1024)).hex()))
                except Exception:out.append(dict(error=True))
            if 'feed' in step:
                try:out.append(dict(decoded=decoder.feed(bytes.fromhex(step['feed'])),retained=len(decoder.buffer)))
                except Exception:out.append(dict(error=True,retained=len(decoder.buffer)))
    elif kind=='latency':
        conn=types.SimpleNamespace()
        for s in c['steps']:out.append([n['allow_latency_payload'](conn,s['payload'],s['time']),getattr(conn,'latency_tokens',4.),getattr(conn,'latency_rate_at',None)])
    elif kind=='supersedes':out=[n['supersedes_snapshot'](*pair) for pair in c['pairs']]
    elif kind=='plan':
        for raw in c['plans']:
            try:
                p=controls['validate_plan'](raw,c['deck']);command=p.get('command','attack');save=p.get('save_for')
                out.append(dict(priority=p['priority'],quotas=p.get('quotas',{}),stance=['hold','advance','hunt','kite','retreat'].index(p.get('stance','hold')),target_x=p.get('target_x'),reserve=p.get('reserve',0),distance=p.get('distance',350),ahead=p.get('deploy_ahead',120),economy=p.get('economy_offset',100),jump=p.get('jump_every',0),teleport=p.get('teleport_hp',0),save=save if save else None,flags=[bool(p.get(k,d)) for k,d in [('evade',False),('jump_on_block',True),('dodge_jump',True),('mark',True)]],command=command if command in ('follow','attack') else None))
            except Exception as e:out.append(dict(error=str(e)))
    elif kind=='replay_fields':out=[{k:v for k,v in p.items() if k in fields} if isinstance(p,dict) else p for p in c['payloads']]
    elif kind=='rope':
        for s in c['steps']:
            snapshots=[]
            def digest(snapshot):snapshots.append(copy.deepcopy(snapshot));return 'second' if len(snapshots)==2 else 'first'
            replay['digest']=digest;b=types.SimpleNamespace(snapshot=lambda include_map:copy.deepcopy(s['snapshot']))
            changed=replay['matches_state_hash'](b,'second',s)
            out.append(dict(changed=changed,snapshot=snapshots[-1] if changed else s['snapshot']))
    elif kind=='digest':out=[dict(canonical=canonical(v),sha256=hashlib.sha256(canonical(v).encode('utf8')).hexdigest()) for v in c['payloads']]
    return json.loads(dump(out))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',required=True,type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__).resolve(),args.exe.resolve(),SOURCE/'network.py',SOURCE/'rv_observation.py',SOURCE/'rv_field.py',SOURCE/'rv_realtime_controls.py',ROOT/'tools/pvp72_sources/replay.py',ROOT/'src/ui/stdlib.cpp',ROOT/'src/sim/pvp/pvprt.cpp']
    stage=ROOT/'build/typed72-room-stage';paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());paths.append(stage/'build-inputs.json');pins={str(p):sha(p) for p in paths};(args.out/'pins.json').write_text(dump(pins),encoding='utf8')
    inputs=cases();refs=references();expected=[reference(c,refs) for c in inputs]
    for name,values in [('inputs',inputs),('expected',expected)]: (args.out/(name+'.jsonl')).write_text('\n'.join(dump(v) for v in values)+'\n',encoding='utf8')
    run=subprocess.run([str(args.exe.resolve()),str((args.out/'inputs.jsonl').resolve()),str((args.out/'actual.jsonl').resolve())],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8');(args.out/'probe.log').write_text(run.stdout,encoding='utf8');actual=[json.loads(s) for s in (args.out/'actual.jsonl').read_text(encoding='utf8').splitlines()]
    failures=[dict(case=i,kind=inputs[i]['kind'],expected=expected[i],actual=actual[i] if i<len(actual) else None) for i in range(len(inputs)) if i>=len(actual) or expected[i]!=actual[i]]
    summary=dict(cases=len(inputs),pass_cases=len(inputs)-len(failures),returncode=run.returncode,changed_inputs=[str(p) for p in paths if sha(p)!=pins[str(p)]],failures=failures,digest_scope='native numeric text contract re-expressed with Python formatting; direct old-native digest probe remains pending',wire_scope='source byte equality for integral JSON; decoder compatibility for received JSON')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}));return 1 if failures or summary['changed_inputs'] or run.returncode else 0
if __name__=='__main__':raise SystemExit(main())
