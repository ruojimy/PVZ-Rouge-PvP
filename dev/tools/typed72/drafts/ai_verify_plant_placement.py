"""Real five-layer shipped plant placement chain, including firing legality."""
import ast,collections,copy,sys,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import room_verify_public as runner
import ai_verify_firing as firing
SOURCE=firing.SOURCE
FILES=['rv_tactics_v6.py','rv_tactics65.py','rv_tactics11.py','rv_tactics18.py','rv_tactics19.py','rv_firing66.py','rv_observation.py']
def classes():
    module,_=firing.modules();package=module.__package__;observation=sys.modules[package+'.rv_observation'];env=dict(__package__=package,Counter=collections.Counter,wrap_delta=observation.wrap_delta,NATIVE_REFUSED='此处不符合原版种植条件',TILE=48)
    tree=ast.parse((SOURCE/'rv_tactics_v6.py').read_text(encoding='utf8'));ctx=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Ctx');exec(compile(ast.Module(body=[ctx],type_ignores=[]),'actual Ctx','exec'),env)
    sequence=[('rv_tactics_v6.py','Controller','Controller',[],['__init__','try_deploy']),('rv_tactics_v6.py','PlantTactics','Plant6',['Controller'],['ground','place_at']),('rv_tactics65.py','PlantTactics','Plant65',['Plant6'],['place_at']),('rv_tactics11.py','PlantTactics','Plant11',['Plant65'],['place_at']),('rv_tactics18.py','PlantTactics','Plant18',['Plant11'],['place_at']),('rv_tactics19.py','PlantTactics','Plant19',['Plant18'],['place_at','try_deploy','lane_direction'])]
    for file,original,name,bases,names in sequence:
        tree=ast.parse((SOURCE/file).read_text(encoding='utf8'));old=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==original);body=[copy.deepcopy(n) for n in old.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEAD_FOR' for t in n.targets)];cls=ast.ClassDef(name=name,bases=[ast.Name(id=b,ctx=ast.Load()) for b in bases],keywords=[],body=body,decorator_list=[]);exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(SOURCE/file),'exec'),env)
    return env
ENV=None
def reference(case):
    global ENV
    if ENV is None:ENV=classes()
    env=ENV;controller=env['Plant19']();sent=[];previewed=[];resets=[0];operation={};cards=case['cards']
    def send(side,kind,**fields):
        sent.append(dict(side=case.get('owner',side),type=kind,**fields));error=operation.get('send_errors',{}).get(fields['card'],'')
        if not error:resets[0]+=1
        return error
    controller.send=send
    class Preview:
        @staticmethod
        def from_snapshot(*args):return Preview()
        def placement(self,side,key,x,y,grave):previewed.append([case.get('owner',side),key,x,y,grave]);return operation.get('preview_errors',{}).get(key,''),operation.get('placement',True)
    env['PreviewBattle']=Preview;env['resolve_card']=lambda key,*args:cards[key];out=[]
    for operation in case['operations']:
        me=copy.deepcopy(operation['me']);me['cooldowns']={k:v.get('cooldown',0.) for k,v in cards.items()};terrain=dict(width=operation.get('width',960.),tile_size=operation.get('tile',48.),tiles=operation['tiles'],environment={});snap=dict(map=terrain,bans=[],battle=dict(time=operation.get('time',0.),players=dict(plant=me,zombie=dict(hp=0)),units=operation.get('units',[]),deathmatch=operation.get('deathmatch',False)));context=env['Ctx']('plant',snap,dict(empty_supports=operation.get('empty_supports',[])),None,None)
        value=controller.place_at(context,operation['card'],operation['x'],operation['y'],operation.get('facing',1));dead=[[x,y,t] for (x,y),t in sorted(getattr(controller,'dead_spots',{}).items())];bad=[[a,b,lift] for (a,b),lift in getattr(controller,'bad_pot_ground',{}).items()]
        out.append(copy.deepcopy(dict(result=value,sent=sent,previewed=previewed,resets=resets[0],failed=controller.failed,log=dict(controller.log),dead_spots=dead,bad_ground=bad,lane_count=len(getattr(controller,'lane_failures',{})),lane_blocked=getattr(controller,'lane_blocked',False),last_blocked_card=getattr(controller,'last_blocked_card',''))))
    return out
def cases():
    out=[];cards={}
    for key,name,behavior,traits in [('plant:shoot','豌豆射手','shoot',{}),('plant:aquatic','海藻','reed',dict(aquatic=True)),('plant:spike','地刺','spike',{}),('plant:produce','向日葵','produce',dict(producer=True)),('plant:花盆','花盆','pot',{}),('plant:睡莲','睡莲','lily',{}),('plant:水盆','水盆','basin',{}),('plant:lob','卷心菜投手','shoot',dict(lob=True))]:cards[key]=dict(id=key,name=name,behavior=behavior,cost=25.,**traits)
    for i in range(80):
        key=['plant:shoot','plant:aquatic','plant:spike','plant:produce','plant:lob'][i%5];deck=[key]+(['plant:花盆'] if i%2 else [])+(['plant:睡莲'] if i%3 else [])+(['plant:水盆'] if i%4 else []);tiles=[[dict(kind='空',solid=False,water=False) for _ in range(20)] for _ in range(10)];kind=['土','石头','水','雪','铁轨'][i//5%5]
        for cell in tiles[7]:cell.update(kind=kind,solid=kind!='水',water=kind=='水')
        if i%7==0:
            for row in range(2,8):tiles[row][8]=dict(kind='石头',solid=True,water=False)
        if kind=='铁轨':tiles[6][6]=dict(kind='车厢',solid=True,water=False)
        supports=[dict(x=300.,y=360.,plant_y=312.)] if i%3==0 else []
        units=[dict(id='foe',side='zombie',x=650.,y=384.,h=72.,hp=100.,mobile=True)]
        if i%6==0:units.append(dict(id='basin',card_id='plant:水盆',side='plant',x=300.,y=360.,hp=10.,mobile=False,behavior='basin'))
        ops=[]
        for j,t in enumerate([0.,.1,2.9,3.1,119.,120.1,121.,130.]):
            op=dict(card=key,x=300.,y=360.,facing=-1 if i%2 else 1,time=t,tiles=copy.deepcopy(tiles),me=dict(x=290.,y=360.,hp=40.,max_hp=40.,resource=10. if i%11==0 else 250.,deck=deck,secrets=['secret:无土栽培'] if i%13==0 else []),units=copy.deepcopy(units),empty_supports=copy.deepcopy(supports),deathmatch=i%17==0)
            if i%4==0 and j<4:op['preview_errors']={key:'此处不符合原版种植条件'}
            if i%9==0 and j<4:op['send_errors']={'plant:水盆':'盆位被占',key:'此处不符合原版种植条件'}
            if j==6:op['empty_supports']=[]
            if j==7:op['x']=348.;op['empty_supports']=[]
            ops.append(op)
        out.append(dict(cards=copy.deepcopy(cards),owner='plant2' if i%2 else 'plant',operations=ops))
    return out
if __name__=='__main__':
    runner.cases=cases;runner.reference=reference;runner.extra_paths=[Path(__file__).resolve(),Path(firing.__file__).resolve()]+[SOURCE/f for f in FILES];runner.test_scope='actual shipped r19/r18/r11/PvP65/v6 plant place_at, firing lane, support setup, native rejection memo, typed preview/input services'
    raise SystemExit(runner.main())
