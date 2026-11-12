"""Literal PvP61 reed targeting, chained packets, direct stun and native gates."""
import ast
import copy
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_flying_plants as flying
shared=flying.shared
shooting=flying.shooting
hero=flying.hero
SOURCE=shared.PVP/'pvp61_content.py'
CATALOG=shared.PVP/'pvp61_catalog.py'


def reference():
    ref=flying.reference()
    env=dict(math=math)
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    for key in ('LIGHTNING_REED','OVERLOAD_REED','SCARECROW','CROW','ELECTRO_SECRET','ELECTRO_STUN_SECONDS','REED_RANGE','REED_HALF_ANGLE',
                'REED_INTERVAL','LIGHTNING_DAMAGE','LIGHTNING_HERO_DAMAGE','LIGHTNING_JUMPS','LIGHTNING_JUMP_RADIUS',
                'OVERLOAD_DAMAGE','OVERLOAD_CONTACT_DAMAGE','OVERLOAD_HERO_CONTACT','OVERLOAD_HERO_DIRECT'):
        env[key]=hero.constant(CATALOG,key)
    reeds,=[node for node in ast.parse(CATALOG.read_text(encoding='utf8')).body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='REEDS' for target in node.targets)]
    exec(compile(ast.Module(body=[reeds],type_ignores=[]),str(CATALOG),'exec'),env)
    constants=[node for node in ast.parse(SOURCE.read_text(encoding='utf8')).body if isinstance(node,ast.Assign)
               and any(isinstance(target,ast.Name) and target.id in ('ZOMBIES','STUN_TICKS') for target in node.targets)]
    assert len(constants)==2
    exec(compile(ast.Module(body=constants,type_ignores=[]),str(SOURCE),'exec'),env)
    hero.selected_class(SOURCE,['configure','enemies','in_cone','reed_target','plant_tick','strike','lightning',
                                'contacts','overload','add_bolt'],'Reeds',env)
    ref['reed_plants']=env
    return ref


class ReedPlantsExtension(flying.FlyingPlantsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.reeds=ref['reed_plants']['Reeds']()
        self.reeds.c=self.content;self.reeds.b=self.b;self.reeds.g=self.g;self.reeds.bolts=[]
        self.reed_seen=False;self.reed_events=[]
        original=self.b._emit
        def emit(event_type,**fields):
            if event_type=='lightning':
                self.reed_events.append([event_type,fields]);self.before('reed_event');self.after('reed_event')
            else:original(event_type,**fields)
        self.b._emit=emit

    def operation(self,op):
        name=op['op'];r=self.reeds;g=self.g
        if name=='reed_setup':self.reed_seen=True;self.b.team_secrets={'plant':{'secret:电疗'} if op['electro'] else set()}
        elif name=='reed_configure':return r.configure(self.all_plants[op['plant']],dict(content=op['name']))
        elif name=='reed_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='reed_cone':return r.in_cone(self.all_plants[op['plant']],self.content_target(op['target']))
        elif name=='reed_target':return self.content_label(r.reed_target(self.all_plants[op['plant']]))
        elif name=='reed_contacts':return [self.content_label(t) for t in r.contacts(self.all_plants[op['plant']],self.content_target(op['target']))]
        elif name in ('reed_tick','reed_lightning','reed_overload'):
            plant=self.all_plants[op['plant']]
            try:
                with self.c.context(target='zombie',owner='plant',phase='plants',source=plant):
                    if name=='reed_tick':r.plant_tick(plant)
                    elif name=='reed_lightning':r.lightning(plant,self.content_target(op['target']))
                    else:r.overload(plant,self.content_target(op['target']))
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='reed_region':
            original=g['_pvp_plant_gate']
            def gate():original();r.plant_tick(g['植物'][g['l']])
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
        if self.reed_seen:row['reeds']=dict(events=self.reed_events,
            bolts=[[tick,name,[list(point) for point in points]] for tick,name,points in self.reeds.bolts])


def cases():
    output=[];prototype=flying.plants.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=994000+i
        ops=case['operations']=case['operations'][:2]
        ops[0]['mode']=('duel','duo','coop','pve')[i%4]
        ops.extend([dict(op='flying_setup',height=len(case['plant_world']['grid'])*48.),
                    dict(op='reed_setup',electro=i%3!=0),dict(op='plant_original',name='杨桃',cell=[8,5],facing=1.),
                    dict(op='plant_fields',plant=0,fields={'_pvp_owner':'plant','植物血':300.},erase=['睡觉']),
                    dict(op='reed_configure',plant=0,name='闪电芦苇' if i%2==0 else '超载芦苇')])
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_owner':'zombie','血量':100.,'大小':2.,
                '位置':[320.+unit*24.,453.6,0.,0.],'手持':'','手持血量':0.,'防具':'','防具血量':0.},erase=['魅惑']))
            ops.append(dict(op='source_write',unit_source=unit,values={'_pvp_id':'reed-'+str(3-unit)}))
        for seat in ('zombie','zombie2'):case['heroes'][seat]['玩家位置']=[840.,80.,0.,0.]
        return case,ops
    for i in range(64):
        case,ops=setup(i)
        angle=(-40.,40.,-40.00000001,40.00000001,0.,180.,179.,-179.)[i%8]
        distance=(0.,576.,576.000001,1e-6)[i//8%4]
        x=264.+math.cos(math.radians(angle))*distance
        y=405.6+math.sin(math.radians(angle))*distance+48.
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[x,y,0.,0.]}))
        ops.append(dict(op='plant_unit',unit=1,fields={'位置':[x,y,0.,0.]}))
        if i>=32:ops.append(dict(op='plant_fields',plant=0,fields={'方向':-1.}))
        ops.extend([dict(op='reed_cone',plant=0,target=0),dict(op='reed_target',plant=0),
                    dict(op='reed_fields',plant=0,fields={'_pvp_reed_clock':374.}),dict(op='reed_tick',plant=0)])
        output.append(('reed-cone-closed-edges-and-id-ties-'+str(i),case))
    for i in range(64):
        case,ops=setup(100+i)
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'位置':[280.+unit*(48.,48.000001,48.000002,24.)[i%4],453.6,0.,0.]}))
        case['heroes']['zombie']['玩家位置']=[280.+4*24.,453.6,0.,0.]
        case['heroes']['zombie2']['玩家位置']=[280.+5*24.,453.6,0.,0.]
        if i//4%4==1:ops.append(dict(op='source_write',unit_source=1,values={'_pvp_id':'reed-3'}))
        if i//4%4==2:ops.append(dict(op='plant_unit',unit=2,fields={'魅惑':0.}))
        if i//4%4==3:ops.append(dict(op='plant_unit',unit=2,fields={'血量':7.5}))
        ops.extend([dict(op='reed_lightning',plant=0,target=0),dict(op='reed_region')])
        output.append(('reed-chain-jumps-seen-ids-stun-and-heroes-'+str(i),case))
    for i in range(64):
        case,ops=setup(200+i)
        case['heroes']['zombie']['玩家位置']=[300.,453.6,0.,0.]
        case['heroes']['zombie2']['玩家位置']=[360.,453.6,0.,0.]
        ops.append(dict(op='plant_unit',unit=0,fields={'血量':(5.,6.,7.,18.)[i%4],
            '防具':('','路障')[i//4%2],'防具血量':(0.,5.)[i//4%2]}))
        target=0 if i//8%2==0 else 'zombie'
        ops.extend([dict(op='reed_contacts',plant=0,target=target),dict(op='reed_overload',plant=0,target=target)])
        output.append(('reed-overload-direct-contact-armor-and-death-'+str(i),case))
    for i in range(32):
        case,ops=setup(300+i)
        hook='content_damage' if i%2 else 'reed_event'
        body=[dict(op='roster_replace',targets=[3,2,1] if i%3 else []),
              dict(op='plant_fields',plant=0,fields={'方向':-1.})]
        ops.append(dict(op='lifecycle_hook',name=hook,fail_before=i//2%4==0,fail_after=i//2%4==1,body=body))
        ops.extend([dict(op='reed_fields',plant=0,fields={'_pvp_reed_clock':374.}),
                    dict(op='reed_tick',plant=0,catch=True),dict(op='reed_region',catch=True)])
        output.append(('reed-damage-event-mutation-and-unwind-'+str(i),case))
    for i in range(24):
        case,ops=setup(400+i)
        ops.append(dict(op='reed_fields',plant=0,fields={'_pvp_aura_factor':(0.,.5,1.,2.)[i%4],
                                                      '_pvp_reed_clock':(0.,374.,374.99999999)[i//4%3]}))
        if i%7==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        body=[]
        for tick in range(780):body.extend([dict(op='clock',tick=tick,time=tick/250.),dict(op='reed_tick',plant=0)])
        ops.append(dict(op='batch',body=body))
        output.append(('reed-continuous-clock-aura-and-sleep-'+str(i),case))
    return output


def paths():
    return flying.paths()+[Path(__file__).resolve(),Path(flying.__file__),SOURCE,CATALOG,
                            shared.ROOT/'tools/typed72/reed_plants_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,ReedPlantsExtension,'typed72-reed-plants',probe_timeout=600))
