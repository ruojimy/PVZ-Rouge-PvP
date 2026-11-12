"""Literal grenadier wind-up, priced targets, lobs, deflection and executions."""
import copy
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_mortar_plants as mortars
shared=mortars.shared
shooting=mortars.shooting
hero=mortars.hero
SOURCE=mortars.SOURCE
CATALOG=mortars.CATALOG
FIELDS=('_pvp_grenade','_pvp_grenade_clock','_pvp_seen_hp','_pvp_hold_x','_pvp_content_position_before')


def reference():
    ref=mortars.reference();env=ref['mortar_plants']
    for key in ('GRENADE_SECONDS','GRENADE_RADIUS','GRENADE_DAMAGE','GRENADE_HERO_DAMAGE'):env[key]=hero.constant(CATALOG,key)
    shooting.projectiles.functions(SOURCE,['_factor'],env)
    shooting.projectiles.functions(shared.PVP/'teams.py',['team_of'],env)
    hero.selected_class(SOURCE,['grenadier_step','grenade_target','throw_grenade','update_grenades','umbrella_reflect','explode','zombie_vs_zombie'],
        'Grenadiers',env)
    return ref


class GrenadierExtension(mortars.MortarPlantsExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        env=ref['mortar_plants'];r=self.grenadiers=env['Grenadiers']()
        r.c=self.content;r.b=self.b;r.g=self.g;r.gravity=4.*self.g['plk'];r.high_solver=self.mortars.high_solver
        r.grenades=[];r.blasts=[]
        self.b._native_objects={}
        self.grenade_seen=False;self.grenade_events=[];self.grenade_costs={};self.grenade_cost_calls=[]
        original=self.b._emit
        def emit(name,**payload):
            if name.startswith('grenade_'):
                self.grenade_events.append([name,payload]);self.before('grenade_event');self.after('grenade_event')
            else:original(name,**payload)
        self.b._emit=emit
        def card(owner,key):
            self.grenade_cost_calls.append([owner,key]);self.before('grenade_cost')
            value=self.grenade_costs[key]
            self.after('grenade_cost')
            if value is None:raise ValueError('fixture missing card')
            return dict(cost=value)
        self.b._unit_card=card
        protection=ref['plant_region']['Protection70']();protection.b=self.b;self.content.pvp70=protection

    def operation(self,op):
        name=op['op'];r=self.grenadiers
        if name=='grenade_setup':
            self.grenade_seen=True;self.b.height=op['height'];self.grenade_costs=copy.deepcopy(op['costs'])
            self.b.map['rows']=len(self.g['ditu']);self.b.map['cols']=len(self.g['ditu'][0])
            for seat in ('plant','plant2','zombie','zombie2'):
                if seat in self.b.players:self.b.players[seat]['secrets']=list(op.get('secrets',{}).get(seat,[]))
        elif name=='grenadier_fields':self.units[op['unit']].update(copy.deepcopy(op['fields']))
        elif name in ('grenade_add','grenade_fields'):
            fields=copy.deepcopy(op['fields'])
            if 'cell' in fields:fields['cell']=tuple(fields['cell'])
            if name=='grenade_add':r.grenades.append(fields)
            else:r.grenades[op['grenade']].update(fields)
        elif name=='grenade_roster':r.grenades=[r.grenades[i] for i in op['indices']]
        elif name=='grenade_clear':r.grenades=[]
        elif name=='grenade_registry':self.b._native_objects[op['id']]=self.units[op['unit']]
        elif name=='grenade_zombie_scale':return r.zombie_vs_zombie(self.content_target(op['target']))
        elif name in ('grenadier_step','grenade_target','grenade_throw','grenade_update','grenade_reflect','grenade_explode'):
            try:
                if name=='grenadier_step':r.grenadier_step(self.units[op['unit']],op['alive'])
                elif name=='grenade_target':
                    target=r.grenade_target(self.units[op['unit']])
                    return self.content_label(target) if target is not None else None
                elif name=='grenade_throw':r.throw_grenade(self.units[op['unit']])
                elif name=='grenade_update':r.update_grenades()
                elif name=='grenade_reflect':return r.umbrella_reflect(r.grenades[op['grenade']])
                else:r.explode(r.grenades[op['grenade']],*op['cell'])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.grenade_seen:return
        grenades=[]
        for grenade in self.grenadiers.grenades:
            record=dict(grenade);record['cell']=list(record['cell']);grenades.append(record)
        row['grenadiers']=dict(events=self.grenade_events,cost_calls=self.grenade_cost_calls,grenades=grenades,
            blasts=[list(blast) for blast in self.grenadiers.blasts],
            units=[{key:unit[key] for key in FIELDS if key in unit} for unit in self.units])


def paths():
    return mortars.paths()+[Path(__file__).resolve(),Path(mortars.__file__),shared.PVP/'teams.py',
        shared.ROOT/'tools/typed72/grenadiers_probe.cpp']


def cases():
    output=[];prototype=mortars.flying.plants.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1061000+i
        ops=case['operations']=case['operations'][:2];ops[0]['mode']=('duel','duo','pve','coop')[i%4]
        ops.extend([dict(op='flying_setup',height=len(case['plant_world']['grid'])*48.),
            dict(op='grenade_setup',height=len(case['plant_world']['grid'])*48.,
                 costs={'plant:a':50.,'plant:b':100.,'plant:c':100.,'zombie:a':150.,'zombie:b':None},
                 secrets={s:['zsecret:手雷'] if i%2 else [] for s in ('plant','plant2','zombie','zombie2')})])
        for index,col in enumerate((5,6,8)):
            ops.extend([dict(op='plant_original',name='杨桃',cell=[8,col]),dict(op='plant_write',plant=index,
                values={'_pvp_id':'plant-'+str(2-index),'_pvp_owner':'plant','_pvp_card':'plant:'+('a','b','c')[index],'植物血':100.}),
                dict(op='plant_fields',plant=index,fields={},erase=['睡觉'])])
        for index in range(4):
            ops.extend([dict(op='plant_unit',unit=index,fields={'_pvp_owner':'zombie','血量':1000.,'大小':2.,'手持':'','手持血量':0.,
                '防具':'','防具血量':0.,'位置':[264.+index*30.,432.,0.,0.]},erase=['魅惑']),
                dict(op='source_write',unit_source=index,values={'_pvp_id':'grenadier-'+str(index)})])
        ops.append(dict(op='grenadier_fields',unit=0,fields={'_pvp_grenade':'ready','_pvp_grenade_clock':0.,'_pvp_seen_hp':1000.}))
        for seat in ('plant','plant2','zombie','zombie2'):case['heroes'][seat]['玩家位置']=[264.,432.,0.,0.]
        return case,ops
    def shot(i,**extra):
        result=dict(x=264.,y=400.,vx=1.,vy=2.,owner=('plant','zombie')[i%2],source=None if i%7==0 else 'grenadier-0',target='plant-0',
            cell=[8,5],defused=False,age=0)
        if i%3:result['instant']=bool(i%2)
        if i%4:result['seat']=(None,'plant2','zombie2','plant')[i//4%4]
        if i%11==0:result['instant']=None
        if i%5:result['direction']=(-1.,0.,1.)[i%3]
        result.update(extra);return result
    for i in range(64):
        case,ops=setup(i)
        state=('ready','wind','thrown','cancelled')[i%4]
        fields={'_pvp_grenade':state,'血量':(1000.,999.9999999995,999.,0.)[i//4%4],
                '_pvp_grenade_clock':(0.,249.,249.5,250.)[i//16]}
        if i%8<4:fields['_pvp_content_position_before']=[250.,430.,7.,8.]
        if i%8==4:fields['冰冻']=1000.
        if i%8==5:fields['冰冻']=1001.
        if i%8==6:fields['黄油']=1.
        if i%8==7:fields['眩晕']=1.
        ops.extend([dict(op='grenadier_fields',unit=0,fields=fields),dict(op='grenadier_step',unit=0,alive=i%7!=0),
                    dict(op='grenadier_step',unit=0,alive=True)])
        output.append(('grenadier-windup-held-cancelled-and-hurt-'+str(i),case))
    for i in range(64):
        case,ops=setup(100+i)
        if i%2:ops.append(dict(op='plant_unit',unit=0,fields={'魅惑':0.}))
        for unit in (1,2):ops.append(dict(op='plant_unit',unit=unit,fields={'_pvp_card':('zombie:a','zombie:b')[unit-1]}))
        if i%4==0:
            for plant in range(3):ops.append(dict(op='plant_fields',plant=plant,fields={'植物血':0.}))
        x=(264.,-24.,840.,960.)[i//4%4]
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[x,432.,0.,0.]}))
        if i//16%4==1:ops.append(dict(op='plant_write',plant=1,values={'_pvp_card':'missing'}))
        if i//16%4==2:ops.append(dict(op='lifecycle_hook',name='grenade_cost',fail_before=True))
        if i//16%4==3:ops.append(dict(op='lifecycle_hook',name='grenade_cost',body=[dict(op='plant_fields',plant=2,fields={'植物血':0.})]))
        ops.extend([dict(op='grenade_target',unit=0),dict(op='grenade_throw',unit=0)])
        output.append(('grenadier-priced-targets-allegiance-and-ties-'+str(i),case))
    for i in range(48):
        case,ops=setup(200+i)
        case['world_rules']['width']=3840.
        y=(432.,-100.,2000.)[i//4%3]
        ops.extend([dict(op='plant_unit',unit=0,fields={'位置':[264.,y,0.,0.],'方向':(-1.,0.,1.)[i%3]}),
            dict(op='grenadier_fields',unit=0,fields={'_pvp_seat':('plant2','zombie2')[i%2]}),
            dict(op='grenade_throw',unit=0)])
        output.append(('grenadier-lob-secrets-seat-and-no-target-'+str(i),case))
    for i in range(64):
        case,ops=setup(300+i)
        ops.extend([dict(op='plant_original',name='萝卜伞',cell=[8,5]),
            dict(op='plant_write',plant=3,values={'_pvp_owner':('plant','zombie')[i%2],'_pvp_id':'umbrella'}),
            dict(op='plant_fields',plant=3,fields={'射':(0.,1.)[i//2%2],'射cd':(-1.,0.,1.)[i//4%3]},erase=['睡觉'])])
        if i//16%4==1:ops.append(dict(op='plant_fields',plant=3,fields={'睡觉':0.}))
        if i//16%4==2:ops.append(dict(op='plant_fields',plant=3,fields={'植物血':0.}))
        if i//16%4==3:ops.append(dict(op='plant_fields',plant=3,fields={'死':0.}))
        ops.append(dict(op='grenade_add',fields=shot(i+1,x=(192.,191.999999,336.,336.000001)[i%4],y=408.,vy=(-5.,0.,5.)[i%3])))
        ops.extend([dict(op='grenade_reflect',grenade=0),dict(op='grenade_update')])
        output.append(('grenadier-umbrella-open-square-and-defuse-'+str(i),case))
    for i in range(64):
        case,ops=setup(400+i)
        ops.extend([dict(op='grenade_add',fields=shot(i,instant=bool(i//4%2))),
                    dict(op='plant_write',plant=1,values={'_pvp_anchor_until':(0.,1.,100.)[i%3]})])
        if i%4==1:ops.append(dict(op='plant_unit',unit=1,fields={'_pvp_anchor_until':100.}))
        if i%4==2:ops.append(dict(op='grenadier_fields',unit=1,fields={'_pvp_grave':True}))
        if i%4==3:ops.append(dict(op='grenadier_fields',unit=1,fields={'_pvp_orphan_barrel':True}))
        if i//8%4==1:ops.append(dict(op='plant_original',name='魅惑菇',cell=[8,5]))
        if i//8%4==2:ops.append(dict(op='roster_replace',targets=[0,1,1,2,3]))
        if i//8%4==3:ops.append(dict(op='plant_unit',unit=2,fields={'灰烬':0.}))
        ops.extend([dict(op='grenade_zombie_scale',target=1),dict(op='grenade_explode',grenade=0,cell=[8,(5,0,19,6)[i%4]])])
        output.append(('grenadier-explosion-execution-protection-and-heroes-'+str(i),case))
    for i in range(32):
        case,ops=setup(500+i)
        ops.append(dict(op='flying_published',solid=[[0]*20 for _ in case['plant_world']['grid']]))
        ops.append(dict(op='grenade_add',fields=shot(i,defused=i%2==1,age=(898,899,1999,2000)[i//2%4],
            x=(-1.,0.,959.,960.)[i%4],y=(100.,575.,624.,625.)[i//8],vx=2.,vy=.1,cell=[-2,3])))
        ops.extend([dict(op='grenade_update'),dict(op='grenade_update')])
        output.append(('grenadier-projectile-age-floor-wrap-and-expiry-'+str(i),case))
    for i in range(24):
        case,ops=setup(600+i)
        body=[dict(op='grenade_clear')] if i%3==0 else [dict(op='grenade_roster',indices=[])] if i%3==1 else []
        ops.append(dict(op='grenade_add',fields=shot(i,instant=False)))
        ops.append(dict(op='lifecycle_hook',name=('grenade_event','content_damage')[i%2],body=body,fail_before=i//3%4==0,fail_after=i//3%4==1))
        ops.extend([dict(op='grenade_explode',grenade=0,cell=[8,5],catch=True),dict(op='grenade_throw',unit=0,catch=True),dict(op='grenade_update',catch=True)])
        output.append(('grenadier-callback-roster-and-exception-order-'+str(i),case))
    for i in range(24):
        case,ops=setup(700+i)
        ops.append(dict(op='flying_published',solid=[[0]*20 for _ in case['plant_world']['grid']]))
        ops.append(dict(op='grenade_add',fields=shot(i,x=264.,y=400.,vx=0.,vy=(-.016,-.015,0.)[i%3],cell=[8,5])))
        if i//3%4==1:
            ops.append(dict(op='lifecycle_hook',name='grenade_event',body=[dict(op='grenade_clear')]))
        if i//3%4==2:
            ops.append(dict(op='lifecycle_hook',name='grenade_event',body=[dict(op='grenade_roster',indices=[0,0])]))
        if i//3%4==3:
            ops.append(dict(op='lifecycle_hook',name='grenade_event',body=[dict(op='grenade_add',
                fields=shot(i,defused=True,x=100.,y=100.,vy=0.,cell=[-2,3]))]))
        ops.append(dict(op='grenade_update'))
        output.append(('grenadier-target-cell-descent-and-retained-iteration-'+str(i),case))
    for i in range(32):
        case,ops=setup(800+i)
        owner=('plant','zombie')[i//4%2]
        fields=shot(i,owner=owner,instant=bool(i//8%2),source='grenadier-0')
        fields.pop('seat',None);fields.pop('direction',None)
        ops.extend([dict(op='grenade_registry',id='grenadier-0',unit=0),
            dict(op='grenadier_fields',unit=0,fields={'_pvp_seat':('plant2','zombie2')[i//16],
                '_pvp_owner':('zombie','plant')[i//4%2]}),
            dict(op='plant_unit',unit=0,fields={'方向':-1.}),
            dict(op='grenade_add',fields=fields),dict(op='grenade_explode',grenade=0,cell=[8,5])])
        output.append(('grenadier-frozen-allegiance-legacy-origin-and-four-seats-'+str(i),case))
    return output


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,GrenadierExtension,'typed72-grenadiers',probe_timeout=600))
