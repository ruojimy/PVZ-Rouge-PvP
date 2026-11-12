"""Actual Recording/Playback over the verified room/native-clock composition.

The checkpoint view deliberately contains selected typed battle facts, not a
claim that the unfinished production full snapshot/native_pose is complete.
"""
import argparse,ast,copy,hashlib,importlib.util,json,subprocess,sys,traceback,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PRIVATE=ROOT/'test_results/typed72-20261105/room-work/reference'
sys.path.insert(0,str(PRIVATE));import verify_room as room
sys.path.insert(0,str(Path(__file__).resolve().parent));import room_verify_boundary as boundary
sys.path.insert(0,str(ROOT/'tools/typed72'));import evidence_store,evidence_archive;sys.path.pop(0)
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'
def digest(value):return hashlib.sha256(boundary.canonical(value).encode('utf8')).hexdigest()
def map_dimensions(b):
    b.map.setdefault('cols',len(b.map['tiles'][0]) if b.map['tiles'] else 0)
    b.map.setdefault('rows',len(b.map['tiles']))
def snapshot(b):
    def rounded(value):
        x=value*1000000.;f=int(x);fraction=x-f
        if fraction>.5 or fraction==.5 and f%2:f+=1
        if fraction<-.5 or fraction==-.5 and f%2:f-=1
        return f/1000000.
    heroes={s:dict(hp=rounded(h['玩家血量']),motion=[rounded(v) for v in h['玩家位置']],seq=b.players[s]['seq'],move=b.players[s]['input']['move']) for s,h in b.hero_states.items()}
    if getattr(b,'_fixture_snapshot_resources',False):
        for s,row in heroes.items():row.update(resource=rounded(b.players[s]['resource']),gift_ready=rounded(b.players[s]['gift_ready_at']))
    return dict(tick=b.tick,native_tick=b.engine.native_tick,time=rounded(b.time),heroes=heroes,result=b.result)
def references():
    ref=room.reference();spec=importlib.util.spec_from_file_location('lifecycle_audit_log',SOURCE/'audit_log.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit);ref['replay_audit']=audit
    tree=ast.parse((SOURCE/'replay.py').read_text(encoding='utf8'));names={'Recording','Playback','state_hash'};body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('FORMAT','INPUT_FIELDS') for t in n.targets)];ref['replay_ast']=ast.Module(body=body,type_ignores=[]);return ref
class ReplayExtension(room.RoomExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.case=case;self.pref=pref;self.refs=ref;self.recording=None;self.playback=None;self.replay_clock=0.;self.b._fixture_snapshot_resources=case.get('snapshot_resources',False)
        initial=copy.deepcopy(case);initial['operations']=[]
        for op in case['operations']:
            if op['op']=='record_setup':break
            initial['operations'].append(op)
        self.initial=initial
        def native_battle(*args,**kwargs):
            captured=[]
            def extension(ctx):
                ext=room.RoomExtension(ctx,initial,pref,ref);captured.append(ext);return ext
            room.hero.oracle(initial,ref['hero_reference'],extension)
            battle=captured[0].b;battle._fixture_snapshot_resources=initial.get('snapshot_resources',False);map_dimensions(battle);battle.close=lambda:None;battle.snapshot=lambda **kwargs:snapshot(battle);return battle
        def clock():value=self.replay_clock;self.replay_clock+=.001;return value
        self.replay_env=dict(copy=copy,uuid=types.SimpleNamespace(uuid4=lambda:types.SimpleNamespace(hex='fixture-id')),time=types.SimpleNamespace(strftime=lambda *a:'fixture-time',perf_counter=clock),AuditLog=ref['replay_audit'].AuditLog,digest=digest,NativeBattle=native_battle)
        exec(compile(ref['replay_ast'],str(SOURCE/'replay.py'),'exec'),self.replay_env)
    def operation(self,op):
        name=op['op'];b=self.b
        if name=='record_setup':
            map_dimensions(b);b.close=lambda:None;b.snapshot=lambda **kwargs:snapshot(b);self.recording=self.replay_env['Recording'](b,1,{},[])
        elif name=='record_input':return super().operation(dict(op='room_input',side=op['side'],payload=op['payload']))
        elif name=='record_clear':return super().operation(dict(op='room_clear',side=op['side']))
        elif name=='record_step':b.step(op.get('count',1))
        elif name=='record_play':
            data=dict(initial=copy.deepcopy(self.recording.initial),ticks=b.tick,final_hash='incorrect' if op.get('bad_hash') else digest(snapshot(b)),operations=list(self.recording.log));self.playback=self.replay_env['Playback'](data,None)
        elif name=='play_update':
            if 'playing' in op:self.playback.playing=op['playing']
            if 'speed' in op:self.playback.speed=op['speed']
            self.playback.update(op.get('dt',0.),op.get('max_steps'),op.get('budget'))
        elif name=='play_seek':self.playback.seek(op['tick'])
        elif name=='record_close':self.recording.log.close()
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if self.recording:row['recording']=dict(events=[] if self.recording.log.closed else list(self.recording.log),error=self.recording.error,closed=self.recording.log.closed,snapshot=snapshot(self.b))
        if self.playback:
            p=self.playback;row['playback']=dict(tick=p.battle.tick,cursor=p.cursor,error=p.error,verified=p.verified,playing=p.playing,credit=p.credit,target=p.target,snapshot=snapshot(p.battle))
def cases():
    out=[]
    for i,(label,c) in enumerate(room.cases()[:16]):
        c=copy.deepcopy(c);end=next(j for j,op in enumerate(c['operations']) if op['op']=='room_setup');c['operations']=c['operations'][:end+1];ops=c['operations'];ops[-1].update(rate=30,capture=True,deathmatch=9999.)
        # Start immediately before a real five-second checkpoint; every room
        # step still executes all corresponding native ticks.
        tick=149;ops[-1].update(tick=tick,phase=(tick*250)%30);native_index=next(j for j,op in enumerate(ops) if op['op']=='native_tick_setup');ops.insert(native_index,dict(op='clock',tick=(tick*250)//30,time=tick/30))
        ops.extend([dict(op='record_setup'),dict(op='record_input',side='plant',payload=dict(seq=1,type='move',move=1,jump=True,ignored='filtered')),dict(op='record_input',side='plant',payload=dict(seq=1,type='move',move=-1)),dict(op='record_input',side='plant',payload=dict(seq=2,type='move',move=True)),dict(op='record_step',count=3),dict(op='record_clear',side='plant'),dict(op='record_input',side='zombie',payload=dict(seq=3,type='rally',x=170.,y=400.)),dict(op='record_step',count=4),dict(op='record_play',bad_hash=i%4==0),dict(op='play_update',playing=True,dt=1.,max_steps=2,budget=.1),dict(op='play_update',dt=0.,max_steps=20,budget=.1),dict(op='play_seek',tick=151),dict(op='play_update',max_steps=20,budget=.1),dict(op='play_seek',tick=156),dict(op='play_update',max_steps=20,budget=.1),dict(op='record_close')]);out.append(('recording-playback-native-composition-'+str(i),c))
    return out
def paths():return room.paths()+[Path(__file__).resolve(),Path(boundary.__file__).resolve(),SOURCE/'replay.py',SOURCE/'audit_log.py',Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()]
def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    files=[a.exe.resolve()]+paths()+list(PRIVATE.glob('*.py'));files=list(dict.fromkeys(p.resolve() for p in files if p.exists()));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pins={str(p):sha(p) for p in files};(a.out/'pinned.json').write_text(json.dumps(pins,indent=2),encoding='utf8')
    evidence_store.freeze_closure(files,a.out/'frozen',ROOT,pins)
    fixtures=cases();fixtures=fixtures[:a.limit] if a.limit is not None else fixtures;hero_ref=room.hero.load_reference();pref=room.shooting.plants.protection.reference();ref=references();ref['hero_reference']=hero_ref
    with (a.out/'inputs.jsonl').open('w',encoding='utf8') as stream:
        for label,c in fixtures:stream.write(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n')
    with (a.out/'probe.log').open('wb') as log:run=subprocess.run([str(a.exe.resolve()),str((a.out/'inputs.jsonl').resolve()),str((a.out/'actual.jsonl').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=240)
    with (a.out/'actual.jsonl').open(encoding='utf8') as actual_stream:actual=[json.loads(line) for line in actual_stream if line.strip()]
    results=[]
    with (a.out/'expected.jsonl').open('w',encoding='utf8') as stream:
        for i,(label,c) in enumerate(fixtures):
            row=dict(case=i,label=label,passed=False)
            try:
                want=room.hero.oracle(c,hero_ref,lambda ctx:ReplayExtension(ctx,c,pref,ref));stream.write(json.dumps(want,ensure_ascii=False,separators=(',',':'))+'\n');difference=room.shooting.difference(want,actual[i]);row.update(passed=difference is None,steps=len(want),first_difference=difference)
            except Exception as e:row['error']=repr(e);row['traceback']=traceback.format_exc()
            results.append(row)
    changed=[str(p) for p in files if sha(p)!=pins[str(p)]];summary=dict(cases=len(fixtures),pass_cases=sum(r['passed'] for r in results),states=sum(r.get('steps',0) for r in results),returncode=run.returncode,changed_inputs=changed,results=results,scope='actual Recording and Playback against concrete typed RoomScheduler/NativeTick/RoomCommands; selected checkpoint snapshot and cold admission remain explicit fixtures, full snapshot/native_pose pending')
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
    try:
        proof=evidence_archive.completion_proof(a.out,producer=run,closed_streams=(actual_stream,stream));archived=evidence_archive.archive_completed_run(proof)
        archive=dict(passed=not archived.errors,manifest=str(archived.manifest_path),removed=list(archived.removed),retained=list(archived.retained),errors=list(archived.errors),original_bytes=archived.original_bytes)
    except Exception as e:archive=dict(passed=False,error=repr(e))
    (a.out/'archive-status.json').write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding='utf8')
    return 2 if not archive['passed'] else 1 if not all(r['passed'] for r in results) or changed or run.returncode or len(actual)!=len(fixtures) else 0
if __name__=='__main__':raise SystemExit(main())
