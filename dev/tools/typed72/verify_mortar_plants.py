"""Literal PvP64 mortar/whip controllers and the installed umbrella wrapper."""
import ast
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_flying_plants as flying
shared=flying.shared
shooting=flying.shooting
hero=flying.hero
SOURCE=shared.PVP/'pvp64_content.py'
CATALOG=shared.PVP/'pvp64_catalog.py'


def reference():
    ref=flying.reference()
    env=dict(math=math,types=types)
    constants,_=shooting.patch.patch_reference();env.update(constants)
    shooting.projectiles.functions(shooting.patch.PATCH,[shooting.P+'solve_intercept'],env)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    shooting.projectiles.functions(SOURCE,['_held'],env)
    for key in ('PRIMAL_MINE','SWEET_POTATO','PEA_MORTAR','SPRING_GRASS','REDEYE','SLIME','SLIME_MEDIUM','SLIME_SMALL','CONVEYOR','GRENADIER',
                'MORTAR_INTERVAL','MORTAR_SHOTS','MORTAR_RANGE_COLUMNS','MORTAR_RETRY_SECONDS',
                'SPRING_RANGE','SPRING_HALF_ANGLE','SPRING_INTERVAL','SPRING_DAMAGE','SPRING_HERO_DAMAGE'):
        env[key]=hero.constant(CATALOG,key)
    slimes,=[node for node in ast.parse(CATALOG.read_text(encoding='utf8')).body if isinstance(node,ast.Assign)
             and any(isinstance(target,ast.Name) and target.id=='SLIMES' for target in node.targets)]
    exec(compile(ast.Module(body=[slimes],type_ignores=[]),str(CATALOG),'exec'),env)
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    constants=[node for node in tree.body if isinstance(node,ast.Assign)
               and any(isinstance(target,ast.Name) and target.id in ('CUSTOM_PLANTS','FLYERS') for target in node.targets)]
    assert len(constants)==2
    exec(compile(ast.Module(body=constants,type_ignores=[]),str(SOURCE),'exec'),env)
    hero.selected_class(SOURCE,['configure','plant_tick','enemies','muzzle','mortar_targets','aim','lead','mortar',
                               'split_pea_blue','red_pea','before_entities','projectile_damage','spring'],'Mortars',env)
    high,=[node for node in ast.walk(tree) if isinstance(node,ast.Assign)
           and any(isinstance(target,ast.Attribute) and target.attr=='high_solver' for target in node.targets)]
    reflect,=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='umbrella_reflect'
              and node.args.args[0].arg=='game']
    visible,=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='entity_visible']
    env['high_install']=compile(ast.Module(body=[high],type_ignores=[]),str(SOURCE),'exec')
    env['reflect_install']=compile(ast.Module(body=[reflect],type_ignores=[]),str(SOURCE),'exec')
    env['visible_install']=compile(ast.Module(body=[visible],type_ignores=[]),str(SOURCE),'exec')
    ref['mortar_plants']=env
    return ref


class MortarPlantsExtension(flying.FlyingPlantsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['mortar_plants'];r=self.mortars=env['Mortars']()
        r.c=self.content;r.b=self.b;r.g=self.g;r.gravity=4*self.g['plk'];r.mortar_speed=800*self.g['plk'];r.swipes=[]
        local=dict(env,self=r,solver=env[shooting.P+'solve_intercept'])
        exec(env['high_install'],local)
        local=dict(env,self=r,reflect=self.ns[shooting.P+'umbrella_reflect_projectiles'],inside=self.ns[shooting.P+'point_in_square_radius'])
        exec(env['reflect_install'],local);self.ns[shooting.P+'umbrella_reflect_projectiles']=local['umbrella_reflect']
        local=dict(env,g=self.g,visible=self.g['_pvp_entity_visible'])
        exec(env['visible_install'],local);self.g['_pvp_entity_visible']=local['entity_visible']
        self.mortar_seen=False;self.mortar_events=[]
        original=self.b._emit
        def emit(event_type,**fields):
            if event_type in ('mortar_volley','spring_whip'):
                self.mortar_events.append([event_type,fields]);self.before('mortar_event');self.after('mortar_event')
            else:original(event_type,**fields)
        self.b._emit=emit

    def operation(self,op):
        name=op['op'];r=self.mortars;g=self.g
        if name=='mortar_setup':
            self.mortar_seen=True;g['秘籍']=['三向蓝火'] if op['blue'] else []
        elif name=='mortar_configure':return r.configure(self.all_plants[op['plant']],dict(content=op['name']))
        elif name=='mortar_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='mortar_shot_fields':self.births[op['entity']].update(copy.deepcopy(op['fields']))
        elif name=='mortar_muzzle':
            point,direction=r.muzzle(self.all_plants[op['plant']]);return [list(point),direction]
        elif name=='mortar_targets':return [self.content_label(t) for t in r.mortar_targets(self.all_plants[op['plant']])]
        elif name=='mortar_lead':return list(r.lead(self.content_target(op['target'])))
        elif name=='mortar_aim':
            start,solution=r.aim(self.all_plants[op['plant']],self.content_target(op['target']))
            return [list(start),list(solution) if solution is not None else None]
        elif name=='mortar_damage':
            try:return r.projectile_damage(self.births[op['entity']],self.content_target(op['target']),op['amount'])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='mortar_red':r.red_pea(self.births[op['entity']])
        elif name=='mortar_split':r.split_pea_blue(self.births[op['entity']])
        elif name=='mortar_before':r.before_entities()
        elif name in ('mortar_tick','mortar_fire','spring_fire'):
            plant=self.all_plants[op['plant']]
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants',source=plant):
                    if name=='mortar_tick':r.plant_tick(plant)
                    elif name=='mortar_fire':return r.mortar(plant)
                    else:return r.spring(plant)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='mortar_region':
            original=g['_pvp_plant_gate']
            def gate():original();r.plant_tick(g['植物'][g['l']])
            g['_pvp_plant_gate']=gate
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants'):exec(self.plant_ref['region'],g)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
            finally:g['_pvp_plant_gate']=original
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.mortar_seen:row['mortars']=dict(events=self.mortar_events,swipes=[list(s) for s in self.mortars.swipes],
            units=[{key:u[key] for key in ('_pvp_blown',) if key in u} for u in self.units])


def cases():
    output=[];prototype=flying.plants.cases()[0][1]
    def setup(i,name='豌豆迫击炮'):
        case=copy.deepcopy(prototype);case['seed']=997000+i
        ops=case['operations']=case['operations'][:2]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops.extend([dict(op='flying_setup',height=len(case['plant_world']['grid'])*48.),
                    dict(op='mortar_setup',blue=bool(i%2)),dict(op='plant_original',name='杨桃',cell=[8,5],facing=1.),
                    dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉']),
                    dict(op='mortar_configure',plant=0,name=name)])
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_owner':'zombie','血量':100.,'大小':2.,
                '位置':[320.+unit*24.,453.6,0.,0.],'手持':'','手持血量':0.,'防具':'','防具血量':0.},erase=['魅惑']))
            ops.append(dict(op='source_write',unit_source=unit,values={'_pvp_id':'mortar-'+str(3-unit)}))
        for seat in ('zombie','zombie2'):case['heroes'][seat]['玩家位置']=[840.,80.,0.,0.]
        return case,ops
    for i in range(80):
        case,ops=setup(i)
        if i>=40:case['world_rules']['width']=3840.
        if i%2:ops.append(dict(op='plant_fields',plant=0,fields={'方向':-1.}))
        x=(264.+13.44 if i%2==0 else 264.-13.44)+(1. if i%2==0 else -1.)*(0.,-24.,-24.000001,48.,479.999,480.,-480.,768.,769.,960.)[i%10]
        y=396.+(0.,480.,480.00001,-480.)[i//10%4]+48.
        for unit in (0,1):ops.append(dict(op='plant_unit',unit=unit,fields={'位置':[x,y,(0.,.5,3.,100.)[i//20],0.]}))
        if i%4:ops.append(dict(op='plant_unit',unit=0,fields={('冰冻','黄油','眩晕')[i%4-1]:(1000.,1001.,1.)[i%3]}))
        ops.extend([dict(op='mortar_muzzle',plant=0),dict(op='mortar_targets',plant=0),dict(op='mortar_lead',target=0),
                    dict(op='mortar_aim',plant=0,target=0),dict(op='mortar_fire',plant=0)])
        output.append(('mortar-high-arcs-leading-held-and-range-'+str(i),case))
    for i in range(64):
        case,ops=setup(100+i)
        for unit in range(4):ops.append(dict(op='plant_unit',unit=unit,fields={'位置':[300.+unit*48.,450.,(0.,.2,1.,20.)[unit],0.]}))
        case['heroes']['zombie']['玩家位置']=[300.,450.,0.,0.]
        case['heroes']['zombie2']['玩家位置']=[320.,450.,0.,0.]
        if i%4==0:ops.append(dict(op='roster_replace',targets=[0,1,2,3,0]))
        ops.extend([dict(op='mortar_fire',plant=0),dict(op='mortar_before'),dict(op='mortar_before')])
        if i%4!=3:ops.extend([dict(op='mortar_damage',entity=0,target=0,amount=10.),dict(op='mortar_damage',entity=0,target=1,amount=10.)])
        else:ops.extend([dict(op='mortar_damage',entity=0,target='zombie',amount=10.),dict(op='mortar_damage',entity=0,target=0,amount=10.)])
        output.append(('mortar-volley-native-births-gravity-and-bonus-'+str(i),case))
    for i in range(48):
        case,ops=setup(200+i)
        ops.append(dict(op='service_entity',name=('豌豆','火豆','卷心菜')[i%3],position=[(240.,264.,288.)[i%3],400.,(0.,.001,.001001,5.)[i//3%4],4.]))
        fields={'_pvp_mortar':i%5!=0,'三向蓝火弹':True,'_pvp_mortar_speed':(0.,3.,None,8.)[i//12]}
        if i%7==0:fields['_pvp_umbrella_reflected']=None
        ops.append(dict(op='mortar_shot_fields',entity=0,fields=fields))
        ops.extend([dict(op='mortar_damage',entity=0,target=0,amount=10.,catch=True),
                    dict(op='mortar_split',entity=0),dict(op='mortar_red',entity=0),
                    dict(op='service_reflect',unit=0,center=[264.,400.],radius=.5),
                    dict(op='service_reflect',unit=0,center=[264.,400.],radius=.5)])
        output.append(('mortar-red-reflection-and-bonus-once-'+str(i),case))
    for i in range(80):
        case,ops=setup(300+i,'弹簧草')
        for unit in range(4):
            angle=(0.,30.,-30.,30.0000001)[unit]+(-20.,0.,20.,180.)[i%4]
            radius=(0.,1e-6,115.2,115.200001,80.)[i//4%5]
            point=[264.+math.cos(math.radians(angle))*radius,405.6+math.sin(math.radians(angle))*radius+48.,0.,0.]
            ops.append(dict(op='plant_unit',unit=unit,fields={'位置':point}))
            if i//20%2:ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_content':('海盗鹦鹉','乌鸦','普通僵尸','')[unit]}))
        if i%4==3:ops.append(dict(op='plant_fields',plant=0,fields={'方向':-1.}))
        case['heroes']['zombie']['玩家位置']=[300.,453.6,0.,0.]
        ops.extend([dict(op='spring_fire',plant=0),dict(op='mortar_region')])
        output.append(('spring-fan-boundaries-damage-and-flyer-blow-'+str(i),case))
    for i in range(32):
        case,ops=setup(400+i,'弹簧草' if i%2 else '豌豆迫击炮')
        hook=('add','content_damage','mortar_event','pea_knockback')[i%4]
        body=[dict(op='roster_replace',targets=[3,2,1] if i%3 else []),dict(op='plant_fields',plant=0,fields={'方向':-1.})]
        ops.append(dict(op='lifecycle_hook',name=hook,fail_before=i//4%4==0,fail_after=i//4%4==1,body=body))
        ops.extend([dict(op='mortar_fields',plant=0,fields={'_pvp_attack_clock':499. if i%2==0 else 299.}),
                    dict(op='mortar_tick',plant=0,catch=True),dict(op='mortar_region',catch=True)])
        output.append(('mortar-spring-callback-order-and-unwind-'+str(i),case))
    for i in range(24):
        case,ops=setup(500+i,'弹簧草' if i%2 else '豌豆迫击炮')
        ops.append(dict(op='mortar_fields',plant=0,fields={'_pvp_aura_factor':(.5,1.,2.)[i//2%3]}))
        if i//6==1:
            for unit in range(4):ops.append(dict(op='plant_unit',unit=unit,fields={'血量':0.}))
            ops.append(dict(op='roster_replace',targets=[]))
        if i//6==2:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        body=[]
        for tick in range(1050):body.extend([dict(op='clock',tick=tick,time=tick/250.),dict(op='mortar_tick',plant=0)])
        ops.append(dict(op='batch',body=body))
        output.append(('mortar-spring-continuous-clock-retry-and-sleep-'+str(i),case))
    for i in range(24):
        case,ops=setup(600+i)
        ops.append(dict(op='service_entity',name='豌豆',position=[264.,396.,.5,-1.]))
        ops.append(dict(op='lifecycle_hook',name='add',body=[dict(op='effect_roster_replace',births=([0,0],[],[0])[i%3])],
                        fail_before=i//3%4==0,fail_after=i//3%4==1))
        ops.extend([dict(op='mortar_fire',plant=0,catch=True),dict(op='mortar_before')])
        output.append(('mortar-constructor-replaces-live-tail-'+str(i),case))
    for i in range(16):
        case,ops=setup(700+i)
        ops.append(dict(op='source_write',unit_source=0,values={'_pvp_id':None if i%2 else 'umbrella'}))
        ops.append(dict(op='service_entity',name='豌豆',position=[264.,400.,.001,4.]))
        ops.append(dict(op='mortar_shot_fields',entity=0,fields={'_pvp_mortar':True,
            '_pvp_umbrella_reflected':(None,'umbrella','other','')[i//4]}))
        ops.extend([dict(op='service_reflect',unit=0,center=[264.,400.],radius=.5),
                    dict(op='service_reflect',unit=0,center=[264.,400.],radius=.5)])
        output.append(('mortar-umbrella-null-and-source-id-marks-'+str(i),case))
    for i in range(16):
        case,ops=setup(800+i)
        ops.append(dict(op='roster_replace',targets=[]))
        ops.append(dict(op='service_entity',name='火豆' if i%2 else '豌豆',position=[720.,200.,.1,-.1]))
        if i%2:ops.append(dict(op='mortar_red',entity=0))
        ops.append(dict(op='mortar_shot_fields',entity=0,fields={'_pvp_mortar':True}))
        ops.extend([dict(op='mortar_before'),dict(op='phase_run'),dict(op='mortar_before'),dict(op='phase_run')])
        output.append(('mortar-native-movement-and-visibility-'+str(i),case))
    return output


def paths():
    return flying.paths()+[Path(__file__).resolve(),Path(flying.__file__),SOURCE,CATALOG,
                            shared.ROOT/'tools/typed72/mortar_plants_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,MortarPlantsExtension,'typed72-mortar-plants',probe_timeout=600))
