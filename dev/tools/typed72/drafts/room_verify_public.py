import argparse,ast,copy,hashlib,json,random,subprocess,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/typed72'));import evidence_store,evidence_archive;sys.path.pop(0)
SOURCE=ROOT.parent/'PVZ-Rouge-v1.4.8/next-pvp71/modkit/pvp'
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def select(path,names,env):
    tree=ast.parse(path.read_text(encoding='utf8'));body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names];exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),env);return env
def cases():
    rng=random.Random(722148);out=[]
    cards={}
    for side,name,behavior,producer in [('plant','豌豆','shoot',False),('plant','向日葵','produce',True),('plant','黄金蓓蕾','gold_bloom',True),('zombie','普通僵尸','walk',False),('zombie','墓碑','grave',True),('zombie','石化火炬','torch',False)]:
        key=side+':'+name;cards[key]=dict(id=key,name=name,asset=name,behavior=behavior,producer=producer,cost=50,hp=100)
    def hero(i):return {'玩家位置':[100+i*100,240,.125,-.25],'玩家血量':40-i*3,'玩家方向':-1 if i%2 else 1,'玩家跳跃':i,'landing_result':i%2,'_pvp_ice':(0,1000,1001,-1)[i],'_pvp_butter':i,'_pvp_cold_until':100,'_pvp_poison':{'level':i}}
    def obj(i):
        side='plant' if i<3 else 'zombie';name=['豌豆','向日葵','黄金蓓蕾','普通僵尸','墓碑','石化火炬'][i]
        value={'_pvp_id':'u'+str(i),'_pvp_card':side+':'+name,'_pvp_owner':side,'_pvp_max_hp':100.,'_pvp_armor_max':0.,'_pvp_temporary':i%2==1,'方向':-1 if i%2 else 1}
        if side=='plant':value.update({'植物':name,'坐标':[3,i+1],'植物血':50.25,'植物血上限':100})
        else:value.update({'僵尸':name,'位置':[240+i*48,240,.2,-.1],'血量':50.,'防具血量':30.5,'_pvp_armor_max':60.,'冰冻':1001.,'黄油':2.,'眩晕':3.,'_pvp_poison':{'level':2}})
        if i==4:value.update(_pvp_grave=True,_pvp_producer=True,_pvp_idle=30.,_pvp_floating=True)
        if i==5:value['_pvp_torch_sleep_until']=80.
        return value
    for i in range(48):
        objects=[obj(j) for j in range(6)];registered=list(range(6))
        if i%3==0:registered.remove(0);objects[0].pop('_pvp_id')
        if i%4==0:objects[2].update(_pvp_content='黄金蓓蕾',_pvp_effect_done=True)
        if i%5==0:objects[3]['魅惑']=None
        if i%6==0:objects[3]['_pvp_orphan_barrel']=True
        if i%7==0:objects[1]['睡觉']=0
        if i%8==0:objects[0]['_pvp_copy_card']='plant:向日葵'
        if i%2:objects[4]['_pvp_zs_speed']={'flag':1.2,'secret':1.5};objects[4]['_pvp_coop_dormant']=True
        for j in range(6):objects[j]['_pvp_seat']=('plant2' if j<3 else 'zombie2') if i%2 else ('plant' if j<3 else 'zombie')
        tiles=[[{'方块':'空'} for _ in range(10)] for _ in range(6)];tiles[5]=[{'方块':'石头'} for _ in range(10)];tiles[3][1]={'方块':'空','植物':True,'根动画':2.};tiles[5][2]={'方块':'海水','里方块':'背景'};tiles[2][3]={'方块':'梯子块'}
        ops=[dict(tick=0),dict(tick=100,cell=[3,1],fields={'方块':'空','植物':True,'根动画':999.}),dict(heads=[[3,1]],cell=[1,1],fields={'方块':'石头','_pvp_belt':True}),dict(unit=3,set={'魅惑':0,'血量':23.5,'冰冻':1000.,'出土':False}),dict(live=[0,1,2,3,5],suspended=[4]),dict(live=[0,3,5],suspended=[]),dict(live=[0,3,5],terrain=False),dict(cell=[1,1],fields={'方块':'池水','_pvp_belt':False}),dict(heads=[])]
        if i%3==1:ops.insert(4,dict(hero='plant',fields=dict(hero(0),**{'玩家位置':[300,200,-.2,.4],'玩家血量':33.,'_pvp_ice':1001.})))
        out.append(dict(cards=cards,objects=objects,registered=registered,live=list(range(6)),suspended=[],tiles=tiles,heroes={s:hero(j) for j,s in enumerate(['plant','zombie','plant2','zombie2'])},operations=ops,zsecrets=i%2==0,first=i%3==0,rage=i%4==0,secrets=['蓝火'] if i%5==0 else []))
    return out

def reference(case):
    env=dict(copy=copy,CARDS=case['cards'],TERRAIN_ANIMATION_KEY='根动画',BELT_STRIDE=1<<16,PETRIFIED_TORCH_KEY='zombie:石化火炬')
    select(SOURCE/'maps.py',{'_cell'},env);select(SOURCE/'pvp59_graves.py',{'drowsy','drowsy_level'},env);env.update(GRAVE_IDLE_SECONDS=20.,GRAVE_DOZE_SECONDS=20.,grave_drowsy=env['drowsy'],grave_drowsy_level=env['drowsy_level'])
    tree=ast.parse((ROOT/'tools/pvp72_sources/native_battle.py').read_text(encoding='utf8'));native=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeBattle');methods=[copy.deepcopy(n) for n in native.body if isinstance(n,ast.FunctionDef) and n.name in ('_sync_public','_sync_terrain')];cls=ast.ClassDef(name='Battle',bases=[],keywords=[],body=methods,decorator_list=[]);module=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]));exec(compile(module,'native_battle.public','exec'),env)
    select(ROOT/'tools/pvp72_sources/native_battle.py',{'tick_asleep'},env)
    b=env['Battle']();objects=copy.deepcopy(case['objects']);ids={id(o):i for i,o in enumerate(objects)};trace=[];heads=[];belts=set();counter=[0]
    b.tile=case.get('tile',48);b.engine=types.SimpleNamespace(native_tick=0);b.g={'植物':[],'僵尸':[],'ditu':copy.deepcopy(case['tiles']),'kong':case.get('empty',['空']),'秘籍':case.get('secrets',[])}
    b.avatars=copy.deepcopy(case['heroes']);b.players={s:dict(stats={'producer_lost':0},resource=100.+j*25.,teleport_ready=10.+j,cannon_aimed=j%2!=0,absent=j==3) for j,s in enumerate(b.avatars)};b._native_objects={objects[i]['_pvp_id']:objects[i] for i in case['registered']};b._suspended_graves=[];b.terrain_revision=0;b.map={'tiles':[[env['_cell'](raw,b.g['kong']) for raw in row] for row in case['tiles']]}
    b._apply_pvp_hardening=lambda obj:trace.append(['harden',ids[id(obj)]])
    order={'plant':0,'zombie':1,'plant2':2,'zombie2':3};b._jump_cap=lambda side:3 if order[side]%2 else 0
    def card(side,key):
        if key in case.get('banned',[]):raise ValueError('banned')
        return copy.deepcopy(case['cards'][key])
    b._card=card;b._unit_card=lambda side,key:copy.deepcopy(case['cards'][key])
    def register(obj,card,side,temporary):
        uid=obj.get('_pvp_id')
        if not uid:counter[0]+=1;uid='auto'+str(counter[0])
        obj.update(_pvp_id=uid,_pvp_card=card['id'],_pvp_owner=side,_pvp_temporary=temporary,_pvp_max_hp=obj.get('植物血',obj.get('血量',0)),_pvp_armor_max=obj.get('防具血量',0));b._native_objects[uid]=obj;trace.append(['register',ids[id(obj)],card['id'],side,temporary])
    b._register=register;b._emit=lambda event,**data:trace.append([event,data['entity'],data['card'],data['side']]);b.zsecrets=types.SimpleNamespace(enabled=case.get('zsecrets',False),on_unit_gone=lambda obj:trace.append(['gone',obj['_pvp_id']]),has=lambda key:case.get('rage',False) if key=='暴怒' else case.get('first',False) if key=='头兵' else False)
    def set_belts(value):belts.clear();belts.update(value);trace.append(['belts',sorted(value)])
    b.content=types.SimpleNamespace(pvp70=types.SimpleNamespace(head_only_cells=lambda:heads),pvp64=types.SimpleNamespace(set_belts=set_belts))
    def rosters(op):
        if 'live' in op:b.g['植物']=[objects[i] for i in op['live'] if '植物' in objects[i]];b.g['僵尸']=[objects[i] for i in op['live'] if '植物' not in objects[i]]
        if 'suspended' in op:b._suspended_graves=[objects[i] for i in op['suspended']]
    rosters(case);out=[];fields=['x','y','vx','vy','hp','frozen','slowed','buttered','grounded','facing','jumps','jump_cap','poison_level','resource','teleport_ready','cannon_aimed','absent']
    if case.get('include_native_pose'):fields.append('native_pose')
    def native_token(raw):
        if isinstance(raw,dict) and set(raw)=={'tuple'}:return tuple(native_token(x) for x in raw['tuple'])
        if isinstance(raw,list):return [native_token(x) for x in raw]
        return raw
    def decode_pose(h):
        if '_pvp_launch_attack' in h:h['_pvp_launch_attack']=native_token(h['_pvp_launch_attack'])
        return h
    for h in b.avatars.values():decode_pose(h)
    for op in case['operations']:
        rosters(op)
        if 'tick' in op:b.engine.native_tick=op['tick']
        if 'heads' in op:heads[:]=[tuple(xy) for xy in op['heads']]
        if 'unit' in op:
            objects[op['unit']].update(copy.deepcopy(op.get('set',{})))
            for key in op.get('erase',[]):objects[op['unit']].pop(key,None)
        if 'hero' in op:b.avatars[op['hero']]=decode_pose(copy.deepcopy(op['fields']))
        if 'cell' in op:y,x=op['cell'];b.g['ditu'][y][x]=copy.deepcopy(op['fields'])
        if 'hero_mutate' in op:
            h=b.avatars[op['hero_mutate']];h['玩家位置'][0]+=7.;h['秘籍'].append('mutation');h['_pvp_id']='changed'
            if h.get('_pvp_poison',{}).get('layers'):
                h['_pvp_poison']['level']=9;next(iter(h['_pvp_poison']['layers'].values()))['until']+=13.
            h['_pvp_launch_attack']='changed'
        if op.get('publish',True):b._sync_public(op.get('terrain',True))
        out.append(copy.deepcopy(dict(players={s:{k:p[k] for k in fields} for s,p in b.players.items()},units=list(b.units.values()),tiles=b.map['tiles'],revision=b.terrain_revision,belts=sorted(belts),registry=list(b._native_objects),trace=trace,producer_lost=[b.players[s]['stats']['producer_lost'] for s in ['plant','zombie','plant2','zombie2']])))
    return json.loads(dump(out))

def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    paths=list(globals().get('extra_paths',[]))+[a.exe.resolve(),Path(__file__).resolve(),ROOT/'tools/pvp72_sources/native_battle.py',SOURCE/'maps.py',SOURCE/'pvp59_graves.py',Path(evidence_store.__file__).resolve(),Path(evidence_archive.__file__).resolve()];stage=ROOT/'build/typed72-room-stage';paths.extend(p for p in (stage/'source').rglob('*') if p.is_file());paths.append(stage/'build-inputs.json');pins={str(p):sha(p) for p in paths};(a.out/'pinned.json').write_text(dump(pins),encoding='utf8');evidence_store.freeze_closure(paths,a.out/'frozen',ROOT,pins)
    inputs=cases();expected=[reference(c) for c in inputs]
    for name,values in [('inputs',inputs),('expected',expected)]:
        with (a.out/(name+'.jsonl')).open('w',encoding='utf8') as output_stream:
            for value in values:output_stream.write(dump(value)+'\n')
        if name=='expected':expected_stream=output_stream
    with (a.out/'probe.log').open('wb') as log:run=subprocess.run([str(a.exe.resolve()),str((a.out/'inputs.jsonl').resolve()),str((a.out/'actual.jsonl').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=120)
    with (a.out/'actual.jsonl').open(encoding='utf8') as actual_stream:actual=[json.loads(line) for line in actual_stream if line.strip()]
    failures=[]
    for i,want in enumerate(expected):
        if i>=len(actual):failures.append(dict(case=i,error='missing output'));continue
        if len(want)!=len(actual[i]):failures.append(dict(case=i,error='state count mismatch',expected=len(want),actual=len(actual[i])));continue
        if want!=actual[i]:
            for j,(x,y) in enumerate(zip(want,actual[i])):
                if x!=y:failures.append(dict(case=i,step=j,expected=x,actual=y));break
    if len(actual)!=len(expected):failures.append(dict(error='case count mismatch',expected=len(expected),actual=len(actual)))
    changed=[str(p) for p in paths if sha(p)!=pins[str(p)]];summary=dict(cases=len(inputs),pass_cases=len(inputs)-len({v['case'] for v in failures if 'case' in v}),states=sum(len(v) for v in expected),returncode=run.returncode,changed_inputs=changed,failures=failures,scope=globals().get('test_scope','real NativeBattle _sync_public/_sync_terrain with explicit catalog/register/hardening fixtures; full native_pose when requested; full room snapshot codec remains pending'))
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(dump({k:v for k,v in summary.items() if k!='failures'}))
    try:
        proof=evidence_archive.completion_proof(a.out,producer=run,closed_streams=(actual_stream,expected_stream));archived=evidence_archive.archive_completed_run(proof)
        archive=dict(passed=not archived.errors,manifest=str(archived.manifest_path),removed=list(archived.removed),retained=list(archived.retained),errors=list(archived.errors),original_bytes=archived.original_bytes)
    except Exception as e:archive=dict(passed=False,error=repr(e))
    (a.out/'archive-status.json').write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding='utf8')
    return 2 if not archive['passed'] else 1 if failures or changed or run.returncode else 0
if __name__=='__main__':raise SystemExit(main())
