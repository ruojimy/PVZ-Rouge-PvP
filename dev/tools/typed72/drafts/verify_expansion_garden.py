"""NativeExpansion timer/aura methods and ZombieSecrets pressure in real ticks."""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import sys
import types
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('garden_bonus_reference',HERE/'verify_bonus.py')
bonus=importlib.util.module_from_spec(spec);spec.loader.exec_module(bonus)
shared=bonus.shared;shooting=bonus.shooting;hero=bonus.hero
import verify_scarecrow as scarecrow
SOURCE=shared.PVP/'native_expansion.py'
ZSECRETS=shared.PVP/'zombie_secrets.py'
TIMERS=('射cd','射','吃','发射cd','发射动画','埋藏','滚蛋','吸','爆了','路灯')

def reference():
    ref=bonus.reference();ref['scarecrows']=scarecrow.reference()['scarecrows']
    env=dict(math=math,__package__=shooting.wind.proxy_reference.PACKAGE)
    for key in ('TIMERS','CHECKPOINTS'):env[key]=hero.constant(SOURCE,key)
    for key in ('ABSORB_TICKS','ENGINE_ABSORB_TICKS'):env[key]=hero.constant(shared.PVP/'balance.py',key)
    assignments=[node for node in ast.parse(ZSECRETS.read_text(encoding='utf8')).body if isinstance(node,ast.Assign)
                 and any(isinstance(target,ast.Name) and target.id in ('PRESSURE_RADIUS','PRESSURE_FACTOR') for target in node.targets)]
    assert len(assignments)==2
    exec(compile(ast.Module(body=assignments,type_ignores=[]),str(ZSECRETS),'exec'),env)
    hero.selected_class(SOURCE,['aura','absorb_clock_cap','before_plants','after_plants'],'Garden',env)
    hero.selected_class(ZSECRETS,['has','holders','_hero','_distance','pressure'],'Pressure',env)
    ref['garden']=env
    return ref

class GardenExtension(bonus.BonusExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.garden_seen=False;self.garden_installed=False
        r=self.garden=ref['garden']['Garden']();r.b=self.b;r.g=self.g
        r.aura_cells={};r.aura_centers=[];r.slow_cells=set();r.timer_before={}
        self.scarecrows=ref['scarecrows']['Scarecrows']()
        self.scarecrows.b=self.b;self.scarecrows.g=self.g;self.scarecrows.c=self.content
        self.b.content.pvp61=self.scarecrows
        p=self.pressure=self.b.zsecrets;p.b=self.b;p.g=self.g
        # Keep the real secret controller's jump/movement/damage methods used
        # by the native driver; install only the six selected pressure methods.
        for name in ('has','holders','_hero','_distance','pressure'):
            setattr(p,name,types.MethodType(getattr(ref['garden']['Pressure'],name),p))
        p.enabled=False;p.team=set();p.by_seat={};p._pressure=(None,())
        old_before,old_after=self.b.expansion.before_plants,self.b.expansion.after_plants
        def before():
            old_before()
            if self.garden_installed:r.before_plants()
        def after():
            old_after()
            if self.garden_installed:r.after_plants()
        self.b.expansion.before_plants=before;self.b.expansion.after_plants=after

    def operation(self,op):
        name=op['op'];b=self.b;r=self.garden
        if name=='garden_setup':
            self.garden_seen=True;self.garden_installed=op.get('installed',False)
            for seat,player in b.players.items():player['secrets']=list(op.get('secrets',{}).get(seat,[]))
            b.team_secrets={'plant':set(secret for seat in b.team_seats('plant') for secret in b.players[seat]['secrets'])}
            p=self.pressure;p.by_seat={seat:set(s.split(':',1)[-1] for s in b.players[seat]['secrets']) for seat in b.team_seats('zombie')}
            p.team=set().union(*p.by_seat.values()) if p.by_seat else set();p.enabled=bool(p.team);p._pressure=(None,())
        elif name=='garden_plant':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='garden_avatar':
            avatar=b.hero_states[op['seat']];avatar['玩家血量']=op['hp'];avatar['玩家位置'][:2]=op['point']
        elif name=='garden_tick':b.engine.native_tick=op['tick']
        elif name=='garden_scarecrow':
            u=self.units[op['unit']];self.scarecrows.configure(u,dict(content='稻草人',hp=op.get('hp',100.)))
            u['_pvp_owner']=op.get('owner','zombie')
            if op.get('ash'):u['灰烬']=0.
        elif name=='garden_call':
            action=op['action']
            if action=='before':r.before_plants()
            elif action=='after':r.after_plants()
            elif action=='absorb':r.absorb_clock_cap()
            elif action=='aura':return r.aura(self.all_plants[op['plant']])
            elif action=='pressure':return self.pressure.pressure(self.all_plants[op['plant']])
            else:raise ValueError(action)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.garden_seen:return
        r=self.garden;p=self.pressure
        row['garden']=dict(centers=[list(c) for c in r.aura_centers],cells=[[a,b,n] for (a,b),n in sorted(r.aura_cells.items())],
            slow=[list(c) for c in sorted(r.slow_cells)],pressure_tick=p._pressure[0],spots=[list(c) for c in p._pressure[1]],
            before=[[i,copy.deepcopy(r.timer_before[id(plant)])] for i,plant in enumerate(self.all_plants) if id(plant) in r.timer_before])

def cases():
    prototypes=bonus.driver.cases();output=[]
    def setup(i,duo=False,installed=False):
        case=copy.deepcopy(prototypes[1 if duo else 0][1]);case['seed']=1400000+i
        ops=case['operations']=case['operations'][:-4]
        ops += [dict(op='garden_setup',installed=installed),dict(op='roster_replace',targets=[0,1,2,3])]
        return case,ops
    def plant(ops,name='豌豆射手',point=(8,5),fields=None):
        index=sum(o['op']=='plant_original' for o in ops)
        ops += [dict(op='plant_original',name=name,cell=list(point)),
                dict(op='plant_fields',plant=index,fields=dict({'_pvp_owner':'plant'},**(fields or {})),erase=['睡觉'])]
        return index
    def clock(ops,p,**fields):ops.append(dict(op='garden_plant',plant=p,fields=fields))
    def call(action,**args):return dict(op='garden_call',action=action,**args)
    for i in range(40):
        case,ops=setup(i)
        for j in range(1+i%5):plant(ops,'金盏花',(8,3+j))
        p=plant(ops,'仙人掌' if i%2 else '豌豆射手')
        if i%2:ops.append(dict(op='garden_setup',secrets={'plant':['secret:尖刺']}))
        val=(1.,19.,20.,24.9,25.,49.,50.,124.,1200.,1250.)[i%10]
        ops.append(dict(op='plant_fields',plant=p,fields={key:val for key in TIMERS}))
        delta=(-2.,-1.,1.,2.)[i//10]
        clock(ops,p,_pvp_clock_delta={key:delta for key in TIMERS},_pvp_clock_credit={key:.75 for key in TIMERS})
        for j in range(3):
            ops += [call('before'),dict(op='plant_fields',plant=p,fields={key:val+delta+j for key in TIMERS}),call('after')]
        output.append(('garden-acceleration-terminal-checkpoints-'+str(i),case))
    for i in range(24):
        case,ops=setup(50+i);p=plant(ops)
        ops += [dict(op='plant_unit',unit=0,fields={'位置':[264.,432.,0.,0.],'血量':100.},erase=['魅惑']),
                dict(op='garden_scarecrow',unit=0,owner='plant' if i%6==0 else 'zombie',ash=i%6==1)]
        val=(.5,1.,19.,20.,21.,25.)[i%6];delta=(-2.,-1.,1.,2.)[i//6]
        ops.append(dict(op='plant_fields',plant=p,fields={key:val for key in TIMERS}))
        clock(ops,p,_pvp_clock_delta={key:delta for key in TIMERS},_pvp_clock_debt={key:.95 for key in TIMERS})
        ops += [call('before'),call('before'),call('after'),call('aura',plant=p)]
        output.append(('garden-scarecrow-debt-checkpoint-and-owner-'+str(i),case))
    for i in range(12):
        case,ops=setup(90+i)
        kind=('磁力菇','吸金磁','豌豆射手')[i%3]
        p=plant(ops,kind,fields={'吸':(13000.,9000.,12999.,6000.)[i//3]})
        if i%2:ops.append(dict(op='plant_fields',plant=p,fields={'睡觉':0.,'植物血':0.}))
        ops += [call('absorb'),call('before'),call('after')]
        output.append(('garden-exact-magnet-rearm-cap-'+str(i),case))
    for i in range(16):
        case,ops=setup(120+i,duo=True);p=plant(ops,'仙人掌',fields={'_pvp_owner':('plant','zombie')[i%2]})
        ops.append(dict(op='garden_setup',secrets={'plant2':['secret:尖刺'],'zombie':['zsecret:威压'],'zombie2':['zsecret:威压']}))
        ops += [dict(op='garden_avatar',seat='zombie',hp=(0.,100.)[i%2],point=[264.,456.]),
                dict(op='garden_avatar',seat='zombie2',hp=100.,point=[264.+(287.999,288.,288.001,700.)[i//4],456.]),
                call('pressure',plant=p),dict(op='garden_avatar',seat='zombie2',hp=0.,point=[900.,800.]),
                call('pressure',plant=p),dict(op='garden_tick',tick=100+i),call('pressure',plant=p),call('before'),call('aura',plant=p)]
        output.append(('garden-pressure-fixed-native-avatars-and-tick-cache-'+str(i),case))
    for i in range(12):
        case,ops=setup(150+i);flower=plant(ops,'金盏花',(8,19))
        p=plant(ops,'向日葵' if i%2 else '豌豆射手',(8,0),{'射cd':7.,'爆了':6.,'射':None})
        if i%3:ops.append(dict(op='plant_fields',plant=flower,fields={'死':False} if i%3==1 else {'睡觉':0.}))
        clock(ops,p,_pvp_clock_delta={'射cd':-1.,'爆了':-1.})
        ops += [call('before'),dict(op='plant_fields',plant=p,fields={'射cd':6.},erase=['爆了']),call('after')]
        if i%4==0:ops += [dict(op='plant_roster_replace',plants=[flower]),call('after')]
        ops += [call('before'),call('after')]
        output.append(('garden-presence-producer-skip-and-roster-replacement-'+str(i),case))
    for i in range(8):
        case,ops=setup(180+i,installed=True)
        # The inherited fixture admits only mobile 0. Give every additional
        # mobile the same complete original native field schema before its
        # first full tick; target-only records are insufficient for movement.
        admitted=next(o for o in ops if o['op']=='motion_unit' and o['unit']==0)
        for unit in (1,2,3):
            complete=copy.deepcopy(admitted);complete['unit']=unit;ops.append(complete)
        plant(ops,'金盏花',(8,4));p=plant(ops,'向日葵' if i%2 else '豌豆射手')
        ops += [dict(op='producer_card',id='plant:向日葵',fields={'producer':True,'period':18.}),
                dict(op='plant_fields',plant=p,fields={'射cd':50.,'爆了':0.}),
                dict(op='garden_scarecrow',unit=0)]
        clock(ops,p,_pvp_clock_delta={'射cd':-1.,'爆了':1.})
        for j in range(5):ops.append(dict(op='native_tick',draw=(i+j)%2==0))
        output.append(('garden-installed-native-tick-and-producer-'+str(i),case))
    return output

def paths():
    return bonus.paths()+scarecrow.paths()+[Path(__file__).resolve(),SOURCE,ZSECRETS,shared.PVP/'balance.py',
                         shared.ROOT/'tools/typed72/expansion_garden_probe.cpp']

if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,GardenExtension,'typed72-native-expansion-garden',probe_timeout=600))
