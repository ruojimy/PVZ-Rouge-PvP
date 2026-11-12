"""Golden bloom and ghost pepper through their installed native plant source gate."""
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
SEPTEMBER=shared.SEPTEMBER
CONTENT=shared.LOCAL/'native_content.py'


def reference():
    ref=plants.reference()
    env=dict(math=math)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    for key in ('PLANTS','ZOMBIES'):env[key]=hero.constant(SEPTEMBER,key)
    hero.selected_class(SEPTEMBER,['configure','targetable','living_enemies','inside','attack','plant_tick'],'September',env)
    hero.selected_class(CONTENT,['enemies'],'Queries',env)
    ref['september_plants']=env
    return ref


class SeptemberPlantsExtension(plants.PlantRegionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['september_plants'];b=self.b
        self.september=env['September']()
        self.september.c=self.content;self.september.b=b;self.september.g=self.g
        self.september.effects=[];self.september.bloom_sun_amounts={}
        self.content.september=self.september
        self.content.enemies=types.MethodType(env['Queries'].enemies,self.content)
        self.september_seen=False;self.september_events=[]
        emit=b._emit
        def routed(event_type,**fields):
            if event_type in ('gold_bloom','ghost_activated','ghost_exploded'):
                self.september_events.append([event_type,fields])
                self.before('september_event');self.after('september_event')
            else:emit(event_type,**fields)
        b._emit=routed

    def operation(self,op):
        name=op['op'];s=self.september;g=self.g
        if name=='september_setup':self.september_seen=True
        elif name=='september_configure':return s.configure(self.all_plants[op['plant']],dict(content=op['name']))
        elif name=='september_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='september_inside':
            target=self.all_plants[op['target']['plant']] if isinstance(op['target'],dict) else self.target(op['target'])
            return s.inside(self.all_plants[op['plant']],target,op['horizontal'],op['vertical'])
        elif name in ('september_tick','september_attack'):
            plant=self.all_plants[op['plant']]
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants',source=plant):
                    if name=='september_tick':s.plant_tick(plant)
                    else:s.attack(plant,op['amount'],op['horizontal'],op['vertical'],op['hero_amount'],op.get('kind','content'))
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='september_region':
            original=g['_pvp_plant_gate']
            def gate():
                original();s.plant_tick(g['植物'][g['l']])
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
        if self.september_seen:
            row['september']=dict(events=self.september_events,
                effects=[[tick,list(point)] for tick,point in self.september.effects],
                sun_amounts=[self.september.bloom_sun_amounts.get(id(sun)) for sun in self.g['阳光球']])


def cases():
    output=[];prototype=plants.cases()[0][1]
    def setup(i,name):
        case=copy.deepcopy(prototype);case['seed']=988000+i
        ops=case['operations']=case['operations'][:2]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops.append(dict(op='september_setup'))
        ops.extend([dict(op='plant_original',name='向日葵',cell=[8,5],facing=(-1.,1.)[i%2]),
                    dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉']),
                    dict(op='september_configure',plant=0,name=name)])
        if i%5:ops.append(dict(op='plant_write',plant=0,values={'_pvp_id':'flower-0'}))
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_owner':'zombie','血量':0.,
                '位置':[312.+unit*48.,453.6,0.,0.]},erase=['魅惑']))
        for seat in ('zombie','zombie2'):
            case['heroes'][seat]['玩家位置']=[840.,80.,0.,0.]
        return case,ops
    for i in range(96):
        case,ops=setup(i,'黄金蓓蕾')
        tick=(0,29999,30000,30001)[i%4]
        ops.extend([dict(op='clock',tick=tick,time=tick/250.),
                    dict(op='september_fields',plant=0,fields={'_pvp_content_age':(0.,123.,124.,125.)[i//4%4]})])
        if i%13==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        if i%17==0:ops.append(dict(op='plant_fields',plant=0,fields={'植物血':0.}))
        if i%19==0:ops.append(dict(op='september_fields',plant=0,fields={'_pvp_effect_done':True}))
        ops.extend([dict(op='september_tick',plant=0) for unused in range(3)])
        ops.append(dict(op='september_region'))
        output.append(('gold-bloom-clock-income-and-one-shot-'+str(i),case))
    for i in range(96):
        case,ops=setup(200+i,'幽灵辣椒')
        dx=(240.,240.0000001,-240.,-240.0000001,0.,960.)[i%6]
        dy=(40.8,40.8000001,-40.8,-40.8000001)[i//6%4]
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':1000.,'位置':[264.+dx,405.6+dy+48.,0.,0.]}))
        if i//24%4==1:ops.append(dict(op='rules_grave',unit=0,grave=True))
        if i//24%4==2:ops.append(dict(op='plant_unit',unit=0,fields={'魅惑':0.}))
        if i//24%4==3:
            case['heroes']['zombie']['玩家位置']=[264.,453.6,0.,0.]
            ops.append(dict(op='plant_unit',unit=0,fields={'血量':0.}))
        ops.extend([dict(op='september_inside',plant=0,target=0,horizontal=5.,vertical=.85),
                    dict(op='september_tick',plant=0),dict(op='september_tick',plant=0),dict(op='september_region')])
        output.append(('ghost-activation-bounds-graves-and-heroes-'+str(i),case))
    for i in range(80):
        case,ops=setup(400+i,'幽灵辣椒')
        now=(2499,2500,2501,9000)[i%4]
        ops.extend([dict(op='clock',tick=now,time=now/250.),dict(op='september_fields',plant=0,fields={
            '_pvp_ghost_started':0.,'_pvp_ghost_clock':(0.,249.,249.99999999,500.)[i//4%4],
            '_pvp_aura_factor':(0.,.01,.5,1.,2.)[i//16]})])
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'血量':1000.,'位置':[264.+unit*60.,453.6,0.,0.]}))
        case['heroes']['zombie']['玩家位置']=[264.,453.6,0.,0.]
        case['heroes']['zombie2']['玩家位置']=[280.,453.6,0.,0.]
        ops.extend([dict(op='september_tick',plant=0),dict(op='september_tick',plant=0),dict(op='september_region')])
        output.append(('ghost-pulse-aura-final-blast-and-budget-'+str(i),case))
    for i in range(24):
        case,ops=setup(600+i,'幽灵辣椒')
        ops.append(dict(op='september_fields',plant=0,fields={'_pvp_ghost_started':0.,'_pvp_ghost_clock':0.,
                                                          '_pvp_aura_factor':(.5,1.,2.)[i%3]}))
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':2000.,'位置':[264.,453.6,0.,0.]}))
        body=[]
        for tick in range(2250,2502):body.extend([dict(op='clock',tick=tick,time=tick/250.),dict(op='september_tick',plant=0)])
        ops.append(dict(op='batch',body=body))
        output.append(('ghost-continuous-pulses-and-expiry-'+str(i),case))
    for i in range(24):
        case,ops=setup(700+i,'黄金蓓蕾' if i%2 else '幽灵辣椒')
        ops.append(dict(op='september_fields',plant=0,fields={'_pvp_content_age':124.}))
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':1000.,'位置':[264.,453.6,0.,0.]}))
        ops.append(dict(op='lifecycle_hook',name='september_event',fail_before=i//2%3==0,fail_after=i//2%3==1,
                        body=[dict(op='plant_roster_replace',plants=[] if i%3==0 else [0,0])]))
        ops.extend([dict(op='september_tick',plant=0,catch=True),dict(op='september_region',catch=True)])
        output.append(('september-event-callback-mutation-and-unwind-'+str(i),case))
    return output


def paths():
    return plants.paths()+[Path(__file__).resolve(),Path(plants.__file__),SEPTEMBER,CONTENT,
                           shared.ROOT/'tools/typed72/september_plants_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,SeptemberPlantsExtension,'typed72-september-plants',probe_timeout=600))
