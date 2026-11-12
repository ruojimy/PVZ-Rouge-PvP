"""Flying plant scheduling, hidden projectile phases and installed damage/wind chains."""
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_plant_region as plants
shared=plants.shared
shooting=plants.shooting
hero=plants.hero
FLYING=plants.FLYING
CATALOG=plants.FLYING_CATALOG
CONTENT=plants.CONTENT
SCALE=shooting.projectiles.SCALE


def reference():
    ref=plants.reference()
    env=dict(math=math)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    shooting.projectiles.functions(SCALE,['factor','unit_root'],env)
    for key in ('PLANTS','TURNIP_HERO_DAMAGE'):env[key]=hero.constant(CATALOG,key)
    hero.selected_class(FLYING,['configure','nearby','clear_line','turnip_target','plant_tick','fire',
                               'before_tick','wall_contact','target_contact','contact_reach','projectiles'],'Flying',env)
    hero.selected_class(CONTENT,['enemies'],'Queries',env)
    ref['flying_plants']=env
    return ref


class FlyingPlantsExtension(plants.PlantRegionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['flying_plants'];b=self.b
        env['FACTOR']=copy.deepcopy(case['world_rules']['scale'])
        self.flight=self.shoot_flying
        self.flight.c=self.content;self.flight.b=b;self.flight.g=self.g
        for key,value in env['Flying'].__dict__.items():
            if callable(value):setattr(self.flight,key,types.MethodType(value,self.flight))
        self.content.flying=self.flight
        self.content.enemies=types.MethodType(env['Queries'].enemies,self.content)
        self.flying_seen=False;self.flying_events=[];self.flying_draws=[];self.flight_records=[]
        emit=b._emit
        def routed(event_type,**fields):
            if event_type=='asparagus_sweep':
                self.flying_events.append([event_type,fields]);self.before('flying_event');self.after('flying_event')
            else:emit(event_type,**fields)
        b._emit=routed
        def draw(entity):
            self.flying_draws.append([entity['_pvp_id'],list(entity['位置'])])
            self.before('flying_draw');self.after('flying_draw')
        self.flight.draw_shot=draw
        def observe_damage(original):
            def damage(*args):
                self.before('content_damage');result=original(*args);self.after('content_damage');return result
            return damage
        for key in ('伤害僵尸','表面伤害僵尸'):self.g[key]=observe_damage(self.g[key])

    def content_target(self,target):
        return self.all_plants[target['plant']] if isinstance(target,dict) else self.target(target)

    def content_label(self,target):
        if target is None:return None
        if '植物' in target:return {'plant':next(i for i,p in enumerate(self.all_plants) if p is target)}
        return self.label(target)

    def operation(self,op):
        name=op['op'];f=self.flight;g=self.g
        if name=='flying_setup':self.flying_seen=True;self.b.height=op['height']
        elif name=='flying_configure':return f.configure(self.all_plants[op['plant']],dict(content=op['name']))
        elif name=='flying_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='flying_shot_fields':self.flight_records[op['shot']].update(copy.deepcopy(op['fields']))
        elif name=='flying_published':self.b.map['tiles']=[[dict(solid=bool(v)) for v in row] for row in op['solid']]
        elif name=='flying_roster':g['实体']=[self.flight_records[i] for i in op['shots']]
        elif name=='flying_clear':return f.clear_line(*op['start'],*op['end'])
        elif name=='flying_wall':return f.wall_contact(*op['start'],*op['delta'])
        elif name=='flying_nearby':return [self.content_label(t) for t in f.nearby(self.all_plants[op['plant']],op['radius'])]
        elif name=='flying_target':return self.content_label(f.turnip_target(self.all_plants[op['plant']]))
        elif name=='flying_reach':
            target=self.content_target(op['target']);return f.contact_reach(target,self.content.point(target))
        elif name=='flying_before':f.before_tick()
        elif name=='flying_wind':self.ns[shooting.P+'apply_blover_zombie_wind'](g,self.units[op['unit']],op['strength'])
        elif name in ('flying_tick','flying_fire','flying_projectiles'):
            plant=self.all_plants[op['plant']] if 'plant' in op else None
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants',source=plant):
                    if name=='flying_tick':f.plant_tick(plant)
                    elif name=='flying_fire':f.fire(plant,op['angle'])
                    else:f.projectiles()
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='flying_region':
            original=g['_pvp_plant_gate']
            def gate():original();f.plant_tick(g['植物'][g['l']])
            g['_pvp_plant_gate']=gate
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants'):
                    exec(self.plant_ref['region'],g)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
            finally:g['_pvp_plant_gate']=original
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.flying_seen:return
        for entity in self.g['实体']+self.flight.shots:
            if '_pvp_hits' in entity and not any(entity is old for old in self.flight_records):self.flight_records.append(entity)
        row['flying']=dict(events=self.flying_events,draws=self.flying_draws,
            hidden=[self.fire_state(entity) for entity in self.flight.shots],
            records=[self.fire_state(entity) for entity in self.flight_records])


def cases():
    output=[];prototype=plants.cases()[0][1]
    def setup(i,name='旋转芜菁'):
        case=copy.deepcopy(prototype);case['seed']=990000+i
        ops=case['operations']=case['operations'][:2]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops[0]['solid']=[[0]*20 for unused in case['plant_world']['grid']]
        ops.extend([dict(op='flying_setup',height=len(case['plant_world']['grid'])*48.),
                    dict(op='plant_original',name='杨桃',cell=[8,5],facing=(-1.,1.)[i%2]),
                    dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉']),
                    dict(op='flying_configure',plant=0,name=name)])
        if i%5:ops.append(dict(op='plant_write',plant=0,values={'_pvp_id':'flight-plant'}))
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_owner':'zombie','血量':0.,
                '位置':[600.+unit*48.,100.,0.,0.],'手持':'','手持血量':0.,'防具':'','防具血量':0.,'大小':2.},erase=['魅惑']))
        for seat in ('zombie','zombie2'):case['heroes'][seat]['玩家位置']=[840.,80.,0.,0.]
        return case,ops
    for i in range(96):
        case,ops=setup(i)
        dx=(0.,120.,-120.,600.,-600.,960.)[i%6]
        dy=(0.,120.,-120.,.1)[i//6%4]
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':1000.,'位置':[264.+dx,405.6+dy+33.6,0.,0.]}))
        ops.append(dict(op='flying_fields',plant=0,fields={'_pvp_flying_clock':(0.,248.,249.,250.)[i//24],
            '_pvp_aura_factor':(.01,.5,1.,2.)[i%4]}))
        if i%17==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        ops.extend([dict(op='flying_target',plant=0),dict(op='flying_nearby',plant=0,radius=16.),
                    dict(op='flying_tick',plant=0),dict(op='flying_region'),dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('turnip-periodic-rays-aura-and-native-gate-'+str(i),case))
    for i in range(96):
        case,ops=setup(200+i,'芦笋战机')
        for unit in range(2):ops.append(dict(op='plant_unit',unit=unit,fields={'血量':1000.,
            '位置':[264.+(120. if unit==0 else -120.),405.6+48.+(-120.,0.,120.)[i%3],0.,0.]}))
        ops.append(dict(op='flying_fields',plant=0,fields={'_pvp_aura_factor':(.01,.5,1.,2.)[i%4],
            '_pvp_flying_rest':(0.,0.,.5,1.)[i//4%4]}))
        if i//16%3==1:
            solid=copy.deepcopy(ops[0]['solid'])
            for row in range(len(solid)):solid[row][6]=1
            ops.append(dict(op='flying_published',solid=solid))
        if i//16%3==2:ops.append(dict(op='flying_fields',plant=0,fields={'_pvp_flying_mode':'sweep',
            '_pvp_sweep_age':(748.,749.,750.)[i%3],'_pvp_sweep_angle':(-39.92,39.92,0.)[i%3],
            '_pvp_sweep_facing':(-1.,1.)[i%2],'_pvp_flying_clock':(61.5,62.49999999,62.5)[i%3]}))
        ops.extend([dict(op='flying_tick',plant=0) for unused in range(4)])
        ops.extend([dict(op='flying_region'),dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('asparagus-sweep-aim-wall-rest-and-boundary-'+str(i),case))
    for i in range(96):
        case,ops=setup(400+i,'芦笋战机' if i%2 else '旋转芜菁')
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'血量':100.,'位置':[264.+(3-unit)*24.,453.6,0.,0.]}))
        if i//8%3==1:ops.append(dict(op='plant_unit',unit=2,fields={'手持':'铁门','手持血量':110.}))
        if i//8%3==2:
            case['heroes']['zombie']['玩家位置']=[280.,453.6,0.,0.]
            case['heroes']['zombie2']['玩家位置']=[300.,453.6,0.,0.]
        for shot in range(2):
            ops.extend([dict(op='flying_fire',plant=0,angle=0.),dict(op='flying_shot_fields',shot=shot,fields={
                '位置':[264.,405.6,(12.,48.,120.,-48.)[i//2%4],0.],
                '_pvp_distance':(0.,32.*48.-48.,64.*48.-48.,64.*48.)[i//24],
                '_pvp_hits':[]})])
        ops.append(dict(op='flying_before'))
        if i%12==0:ops.append(dict(op='lifecycle_hook',name='content_damage',body=[dict(op='plant_unit',unit=3,fields={'血量':0.})]))
        if i%12==1:ops.append(dict(op='flying_roster',shots=[1,1]))
        ops.extend([dict(op='flying_projectiles'),dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('flight-contact-order-piercing-heroes-and-distance-'+str(i),case))
    for i in range(64):
        case,ops=setup(600+i,'芦笋战机' if i%2 else '旋转芜菁')
        solid=copy.deepcopy(ops[0]['solid']);solid[8][6]=1;solid[7][0]=1
        ops.append(dict(op='flying_published',solid=solid))
        start=[(264.,287.999999,288.,959.9)[i%4],(405.6,384.,383.9999,-.1)[i//4%4]]
        delta=[(24.,48.,120.,-120.)[i//16],(-12.,0.,12.,48.)[i%4]]
        ops.extend([dict(op='flying_wall',start=start,delta=delta),
                    dict(op='flying_clear',start=start,end=[start[0]+delta[0],start[1]+delta[1]]),
                    dict(op='flying_fire',plant=0,angle=0.),
                    dict(op='flying_shot_fields',shot=0,fields={'位置':start+delta}),
                    dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('flight-wall-sweep-endpoints-and-seams-'+str(i),case))
    for i in range(32):
        case,ops=setup(700+i,'芦笋战机' if i%2 else '旋转芜菁')
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':100.,'位置':[280.,453.6,0.,0.],
            '方向':(-1.,1.)[i%2]}))
        ops.append(dict(op='service_unit',unit=0,values={'植物僵尸':True,'植物僵尸名':'大喷菇僵尸',
            '植物僵尸鸭子':bool(i%3),'植物僵尸发射动画':i%24}))
        ops.extend([dict(op='flying_reach',target=0),dict(op='flying_fire',plant=0,angle=(0.,90.,180.,270.)[i%4]),
                    dict(op='flying_before'),dict(op='flying_wind',unit=0,strength=(.5,1.,2.,0.)[i//4%4]),
                    dict(op='flying_projectiles')])
        output.append(('flight-extended-head-and-hidden-wind-'+str(i),case))
    for i in range(32):
        case,ops=setup(760+i)
        height=7000.
        ops.append(dict(op='flying_setup',height=height))
        ops.append(dict(op='flying_published',solid=[[0]*20 for unused in range(146)]))
        dx=(240.,-240.,0.,480.)[i%4]
        dy=(1200.,2160.,3072./math.sqrt(2.),3072./math.sqrt(2.)+80.)[i//4%4]
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':1000.,'位置':[264.+dx,405.6+dy+33.6,0.,0.]}))
        ops.extend([dict(op='flying_target',plant=0),
                    dict(op='flying_fields',plant=0,fields={'_pvp_flying_clock':250.}),dict(op='flying_tick',plant=0)])
        output.append(('turnip-distant-periodic-image-and-ray-length-'+str(i),case))
    for i in range(24):
        case,ops=setup(800+i,'芦笋战机')
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':1000.,'位置':[400.,453.6,0.,0.]}))
        hook='flying_event' if i%2 else 'flying_draw'
        ops.append(dict(op='lifecycle_hook',name=hook,fail_before=i//2%3==0,fail_after=i//2%3==1,
                        body=[dict(op='plant_roster_replace',plants=[] if i%3==0 else [0,0])]))
        ops.extend([dict(op='flying_tick',plant=0,catch=True),dict(op='flying_before'),dict(op='flying_projectiles',catch=True),
                    dict(op='flying_projectiles',catch=True),dict(op='flying_region',catch=True)])
        output.append(('flight-callback-mutation-and-unwind-'+str(i),case))
    for i in range(24):
        case,ops=setup(850+i,'芦笋战机')
        for angle in (0.,180.):ops.append(dict(op='flying_fire',plant=0,angle=angle))
        ops.append(dict(op='flying_before'))
        body=[dict(op='flying_roster',shots=[1,1] if i%2 else [])]
        if i%3==0:body.append(dict(op='flying_fire',plant=0,angle=90.))
        ops.append(dict(op='lifecycle_hook',name='flying_draw',body=body,fail_after=i//3%2==0))
        ops.extend([dict(op='flying_projectiles',catch=True),dict(op='flying_projectiles',catch=True),
                    dict(op='flying_before'),dict(op='phase_run'),dict(op='flying_projectiles')])
        output.append(('flight-captured-hidden-and-replaced-live-rosters-'+str(i),case))
    for i in range(16):
        case,ops=setup(880+i,'芦笋战机' if i%2 else '旋转芜菁')
        for plant,kind in enumerate(('魅惑菇','坚果'),1):
            ops.extend([dict(op='plant_original',name=kind,cell=[8,5+plant]),
                dict(op='plant_fields',plant=plant,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉'])])
        ops.extend([dict(op='flying_fire',plant=0,angle=0.),
                    dict(op='plant_fields',plant=0,fields={'植物血':0.}),
                    dict(op='flying_shot_fields',shot=0,fields={'_pvp_owner':'zombie',
                        '位置':[264.,405.6,(48.,100.)[i//2%2],0.]}),
                    dict(op='flying_before'),dict(op='flying_projectiles'),
                    dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('flight-plant-contact-charm-and-live-allegiance-'+str(i),case))
    for i in range(8):
        case,ops=setup(910+i,'芦笋战机' if i%2 else '旋转芜菁')
        ops.extend([dict(op='flying_fire',plant=0,angle=0.),
                    dict(op='flying_shot_fields',shot=0,fields={'_pvp_flight_distance':100000.,'_pvp_distance':i*10.}),
                    dict(op='flying_before'),dict(op='flying_projectiles'),
                    dict(op='flying_before'),dict(op='flying_projectiles')])
        output.append(('flight-independent-native-and-custom-distance-'+str(i),case))
    for i in range(24):
        case,ops=setup(920+i,'芦笋战机' if i%2 else '旋转芜菁')
        ops.extend([dict(op='plant_unit',unit=0,fields={'血量':10000.,'位置':[400.,453.6,0.,0.]}),
                    dict(op='flying_fields',plant=0,fields={'_pvp_aura_factor':(.25,1.,2.)[i%3]})])
        body=[]
        for tick in range(800):body.extend([dict(op='clock',tick=tick,time=tick/250.),dict(op='flying_before'),
            dict(op='flying_tick',plant=0),dict(op='flying_projectiles')])
        ops.append(dict(op='batch',body=body))
        output.append(('flight-continuous-schedule-and-piercing-ledger-'+str(i),case))
    return output


def paths():
    return plants.paths()+[Path(__file__).resolve(),Path(plants.__file__),FLYING,CATALOG,CONTENT,SCALE,
                           shared.ROOT/'tools/typed72/flying_plants_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,FlyingPlantsExtension,'typed72-flying-plants',probe_timeout=600))
