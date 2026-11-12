"""Content target ordering and real sweet-potato persistent taunt fields."""
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_seat_paths as seats
shared=seats.shared
hero=seats.hero
shooting=seats.shooting
CONTENT=shared.LOCAL/'native_content.py'
PVP64=shared.PVP/'pvp64_content.py'


def reference():
    ref=seats.reference()
    env=dict(math=math,__package__=shared.PACKAGE)
    shooting.projectiles.functions(seats.res.seat.SIM,['wrap_delta'],env)
    env['SWEET_POTATO']=hero.constant(shared.PVP/'pvp64_catalog.py','SWEET_POTATO')
    for key in ('FLYERS','TAUNT_KEYS'):env[key]=hero.constant(PVP64,key)
    hero.selected_class(PVP64,['potatoes','potato_point','update_taunts','taunting_potato',
                              'apply_taunt','restore_taunt','taunt_target'],'Taunts',env)
    hero.selected_class(CONTENT,['enemies','nearest','nearest_dynamic','route_target','route_target_dynamic'],'Queries',env)
    hero.selected_class(shared.SEPTEMBER,['targetable'],'September',env)
    ref['content_queries']=env
    return ref


class ContentQueriesExtension(seats.SeatPathExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.content_seen=False
        env=ref['content_queries']
        self.taunt=env['Taunts']()
        self.taunt.b=self.b
        self.taunt.g=self.g
        self.content.pvp64=self.taunt
        self.content.september=env['September']()
        for key,value in env['Queries'].__dict__.items():
            if callable(value):setattr(self.content,key,types.MethodType(value,self.content))

    def content_target(self,target):
        return self.all_plants[target['plant']] if isinstance(target,dict) else self.target(target)

    def content_label(self,target):
        if target is None:return None
        if '植物' in target:return {'plant':next(i for i,p in enumerate(self.all_plants) if p is target)}
        return self.label(target)

    def operation(self,op):
        name=op['op'];t=self.taunt
        if name=='content_queries_setup':
            self.content_seen=True
            t.sweet_radius=3. if op['resist'] else 6.
            t.potatoes_dirty=True;t.potato_list=[];t.potato_points=[]
            t.taunt_fields={};t.taunt_baseline=None;t.saved_tracking=None;t.hidden_cells=[]
        elif name in ('content_unit_fields','content_plant_fields'):
            record=self.units[op['unit']] if name=='content_unit_fields' else self.all_plants[op['plant']]
            record.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):record.pop(key,None)
        elif name=='content_enemies':return [self.content_label(p) for p in self.content.enemies(self.content_target(op['source']))]
        elif name=='content_nearest':return self.content_label(self.content.nearest(self.content_target(op['source'])))
        elif name=='content_route':
            source=self.content_target(op['source'])
            goal=self.content_target(op['goal']) if op['goal'] is not None else None
            return self.content_label(self.content.route_target(source,goal,[self.content_target(p) for p in op['candidates']]))
        elif name=='taunt_update':t.update_taunts(self.b.avatars['zombie'])
        elif name=='taunt_dirty':t.potatoes_dirty=True
        elif name=='taunt_find':return self.content_label(t.taunting_potato(self.content_target(op['source'])))
        elif name=='taunt_apply':t.apply_taunt(self.units[op['unit']])
        elif name=='taunt_restore':t.restore_taunt()
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.content_seen:return
        t=self.taunt;g=self.g;identities={}
        def identity(value):
            key=id(value)
            if key not in identities:identities[key]=len(identities)
            return identities[key]
        def chase(state):
            return dict(fields=state['洪水'],goal=state['目标位置'],target=state['目标植物'],
                        running=state['paoku'],output=state['输出植物数'],aliases=[identity(x) for x in state['洪水']])
        def snapshot(state):
            if state is None:return None
            return dict(fields=[[state[p+'洪水cd'],state[p+'洪水覆盖'],state[p+'洪水'],state[p+'洪水圈']] for p in ('人','植')],
                        chase=chase(state),hold=state['先别追植'],hero=[state['wjy'],state['wjx']],
                        aliases=[identity(state[p+suffix]) for p in ('人','植') for suffix in ('洪水','洪水圈')])
        row['content_queries']=dict(current=snapshot(g),
            fields=[[uid,snapshot(t.taunt_fields[uid])] for uid in sorted(t.taunt_fields,key=lambda uid:(uid is not None,uid))],
            baseline=snapshot(t.taunt_baseline),saved=chase(t.saved_tracking) if t.saved_tracking is not None else None,
            cached=[self.content_label(p) for p in t.potato_list],hidden=len(t.hidden_cells),
            units=[{key:u[key] for key in ('_pvp_taunted_by','_pvp_content','_pvp_no_hero_attack') if key in u} for u in self.units])


def cases():
    output=[];prototype=seats.phase.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=985000+i
        ops=case['operations']=case['operations'][:1]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops.append(dict(op='path_setup',point=[264.,412.8],targets=['向日葵','豌豆射手'],producers=['向日葵'],hold=7.,output=1.,running=2.))
        ops.append(dict(op='content_queries_setup',resist=i%2==0))
        for j in range(4):
            ops.append(dict(op='content_unit_fields',unit=j,fields={'位置':[120.+j*96.,432.,0.,0.],
                '血量':100.,'_pvp_owner':('zombie','plant','zombie','plant')[j]},erase=['魅惑','_pvp_content']))
        return case,ops
    def potato(ops,index,cell,uid,hp=100.,owner='plant'):
        ops.append(dict(op='plant_original',name='坚果',cell=list(cell)))
        ops.append(dict(op='content_plant_fields',plant=index,fields={
            '_pvp_content':'甜薯','_pvp_id':uid,'植物血':hp,'_pvp_owner':owner}))
    for i in range(128):
        case,ops=setup(i)
        for j in range(3):
            potato(ops,j,(8,(i+j*5)%20),'p'+str(j),0. if j==2 and i%5==0 else 100.)
        ops.append(dict(op='content_plant_fields',plant=1,fields={'_pvp_content':('幽灵辣椒','甜薯','抓人草触手','')[i%4]}))
        if i%4==2:ops.append(dict(op='plant_write',plant=1,values={'_pvp_head_point':[960.1,400.]}))
        ops.append(dict(op='content_unit_fields',unit=0,fields={'位置':[(-.1,959.9,1920.1,264.)[i%4],432.,0.,0.],
            '_pvp_content':('普通僵尸','海盗鹦鹉','乌鸦','抓人草触手')[i//4%4],
            '_pvp_head_point':[24.,400.],'_pvp_no_hero_attack':i//8%2==0}))
        if i%3==0:ops.append(dict(op='content_unit_fields',unit=0,fields={'魅惑':0.}))
        ops.append(dict(op='roster_replace',targets=[0,1,2,3,1,'plant','zombie']))
        for source in (0,1,{'plant':0},'plant','zombie'):
            ops.extend([dict(op='content_enemies',source=source),dict(op='content_nearest',source=source)])
        ops.extend([dict(op='taunt_update'),dict(op='content_nearest',source=0)])
        output.append(('content-nearest-order-proxies-and-owner-'+str(i),case))
    for i in range(64):
        case,ops=setup(200+i)
        origin=(.1,959.9,480.,-960.1)[i%4]
        for j in range(4):
            ops.append(dict(op='content_unit_fields',unit=j,fields={'位置':[origin+(0.,100.,50.,50.)[j],
                432.+(0.,0.,31.2,31.20000001)[j]*(1. if i%2 else -1.),0.,0.]}))
        for candidates in ([2,3,2,1],[3,2,1],[1,0,2],[]):
            ops.append(dict(op='content_route',source=0,goal=1 if i%7 else None,candidates=candidates))
        output.append(('content-route-projection-radius-and-first-tie-'+str(i),case))
    for i in range(96):
        case,ops=setup(400+i)
        potato(ops,0,(8,0),'b')
        potato(ops,1,(8,19),'a')
        potato(ops,2,(7,1),'c',owner='zombie' if i%3==0 else 'plant')
        for j in range(4):
            x=(-.1,0.,24.,288.,312.,959.9,960.1,1920.)[(i+j)%8]
            ops.append(dict(op='content_unit_fields',unit=j,fields={'位置':[x,456.,0.,0.],
                '_pvp_owner':'zombie','_pvp_content':('普通僵尸','海盗鹦鹉','乌鸦','某海盗鹦鹉变体')[j],
                '_pvp_grave':j==3 and i%2==0}))
        if i%5==0:ops.append(dict(op='content_plant_fields',plant=0,fields={'睡觉':0.}))
        ops.append(dict(op='taunt_update'))
        ops.append(dict(op='batch',body=[dict(op='taunt_update') for unused in range(20)]))
        for j in (0,1,2,3,0):
            ops.extend([dict(op='taunt_find',source=j),dict(op='taunt_apply',unit=j),
                        dict(op='banks_native_write',hold=13.,running=7.,target=j,cooldown=4,field=0,cell=[7,2,-9]),
                        dict(op='taunt_restore')])
        ops.append(dict(op='content_plant_fields',plant=0,fields={'死':0.}))
        ops.extend([dict(op='taunt_find',source=0),dict(op='taunt_update')])
        potato(ops,3,(8,5),'new')
        ops.extend([dict(op='taunt_find',source=0),dict(op='taunt_dirty'),dict(op='taunt_find',source=0),dict(op='taunt_update')])
        ops.append(dict(op='plant_roster_replace',plants=[]))
        ops.extend([dict(op='taunt_find',source=0),dict(op='taunt_update'),dict(op='taunt_find',source=0)])
        output.append(('sweet-taunt-persistent-banks-and-death-'+str(i),case))
    for i in range(32):
        case,ops=setup(600+i)
        potato(ops,0,(8,5),'same')
        potato(ops,1,(8,6),'same' if i%2 else None)
        ops.append(dict(op='content_unit_fields',unit=0,fields={'位置':[264.,432.,0.,0.]}))
        for x in range(3,8):
            ops.append(dict(op='tile_replace',cell=[7,x],value={'方块':'空','植物':False if i%2 else True}))
        ops.extend([dict(op='hold_tile',cell=[7,4]),dict(op='taunt_update'),dict(op='taunt_apply',unit=0),
                    dict(op='tile_replace',cell=[7,4],value={'方块':'石'}),dict(op='taunt_apply',unit=0),
                    dict(op='taunt_restore'),dict(op='taunt_restore')])
        output.append(('sweet-taunt-hidden-marker-alias-and-duplicate-id-'+str(i),case))
    for i in range(16):
        case=copy.deepcopy(output[192+i][1])
        first_update=next(index for index,op in enumerate(case['operations']) if op['op']=='taunt_update')
        ops=case['operations']=case['operations'][:first_update+1]
        ops.append(dict(op='content_unit_fields',unit=0,fields={'位置':[24.,432.,0.,0.]}))
        for target,running in ((3,7.),(-1,11.),(1,2.)):
            # Team/rally switching can replace these scalars before each body.
            # Taunt restoration must use update_taunts' tick baseline.
            ops.extend([dict(op='banks_native_write',hold=17.,running=running,target=target,cooldown=3,
                             field=i%2,cell=[7,2,-8]),
                        dict(op='taunt_apply',unit=0),dict(op='taunt_restore')])
        ops.extend([dict(op='taunt_update'),dict(op='taunt_apply',unit=0),dict(op='taunt_restore')])
        output.append(('sweet-taunt-baseline-across-native-bank-writes-'+str(i),case))
    return output


def paths():
    files=[Path(__file__).resolve(),Path(seats.__file__),Path(seats.paths.__file__),Path(seats.res.__file__),
           Path(seats.res.hp.__file__),Path(seats.phase.__file__),Path(shared.__file__),seats.res.seat.SIM,
           shared.BATTLE,shared.SEPTEMBER,PVP64,shared.PVP/'pvp64_catalog.py',CONTENT,hero.PHYSICS,
           shared.PVP/'native_flood.py',shared.PVP/'native_bytecode.py',
           shared.ROOT/'src/sim/pvp/hand/targeting72.cpp']
    files += [shared.ROOT/'tools/typed72'/name for name in (
        'seat_paths_probe.cpp','resources_probe.cpp','world_rules_probe.cpp',
        'content_queries_probe.cpp','zombie_motion_fixture.inc')]
    files += [shared.ROOT/('extract/live/physics_'+name+'.marshal') for name in (
        'tracking_initialize','tracking_bind','tracking_coordinates','tracking_player','tracking_targets','tracking_plants')]
    return files


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,ContentQueriesExtension,'typed72-content-queries-and-taunts',probe_timeout=600))
