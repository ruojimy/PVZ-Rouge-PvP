"""Whole NativeBattle economy method, with native clocks and independent room RNG."""
import ast
import copy
import math
import random
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_resources as res
shared=res.shared
hero=res.hero
shooting=res.shooting
SECRETS66=shared.LOCAL/'pvp66_secrets.py'


def reference():
    ref=res.reference();env=dict(copy=copy,math=math)
    shooting.projectiles.functions(res.seat.SIM,['wrap_delta'],env)
    env['sun_scale']=ref['resources']['sun_scale']
    env['team_of']=ref['resources']['team_of']
    env['battle']=hero.selected_class(shared.BATTLE,['_economy','_sun_owner'],'Economy',env)
    env['zombies']=hero.selected_class(hero.ZSECRETS,['day_income_count','_zombie','_own'],'DayIncome',env)
    env['SUPPLEMENT_SUN']=hero.constant(SECRETS66,'SUPPLEMENT_SUN')
    env['death']=hero.selected_class(SECRETS66,['death_sun_amount'],'DeathSun',env)
    shooting.projectiles.functions(res.seat.BALANCE,['rest_factor'],env)
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='obj'
           and any(isinstance(v,ast.Constant) and v.value=='_pvp_sun_due' for v in ast.walk(n))]
    loop,=loops
    env['production']=compile(ast.Module(body=[loop],type_ignores=[]),str(shared.BATTLE),'exec')
    ref['economy']=env
    return ref


class EconomyExtension(res.ResourceExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;env=ref['economy'];self.economy_ref=env;self.economy_seen=False;self.sun_records=[];self.cards={}
        b.rng=random.Random(case['seed']);b._native_sun_seats={};b._native_objects={};b._grave_progress={}
        b.zsecrets.g=self.g
        b.content.september.bloom_sun_amounts={}
        b.secrets66=env['death']();b.secrets66.b=b;b.secrets66.death_points=[]
        for cls,target in ((env['battle'],b),(env['zombies'],b.zsecrets)):
            for name,fn in cls.__dict__.items():
                if callable(fn):setattr(target,name,types.MethodType(fn,target))
        # The component receives resolved, typed producer policies at the cold
        # boundary. Catalog resolution has its own integration work remaining.
        b._card=lambda side,key:self.cards[key]
    def operation(self,op):
        b=self.b;g=self.g;name=op['op']
        if name=='economy_setup':
            self.economy_seen=True;b.present=frozenset(op['present']);b.height=op['height']
            g['产光植物']=list(op['producers']);b._day_brain_native_tick=op['previous_tick']
            b.sky_progress=op['progress'];b.sky_interval=op['interval'];b.zsecrets.subsidy_phase=op['subsidy_phase']
            b.rules.update(day_brain_interval=op['day_interval'],day_brain_amount=op['day_amount'],sky_amount=op['sky_amount'],sun_lifetime=op['lifetime'])
            b.map['environment']={'night':op['night']}
            if op['subsidy']:b.zsecrets.team.add('补贴')
            else:b.zsecrets.team.discard('补贴')
        elif name=='economy_state':
            if 'night' in op:b.map['environment']['night']=op['night']
            if 'subsidy' in op:
                if op['subsidy']:b.zsecrets.team.add('补贴')
                else:b.zsecrets.team.discard('补贴')
        elif name=='producer_card':self.cards[op['id']]=copy.deepcopy(op['fields'])
        elif name=='producer_fields':self.all_plants[op['plant']].update(copy.deepcopy(op['fields']))
        elif name=='production_step':
            b.rules.update(producer_rest_seconds=op['quiet'],producer_rest_ramp_seconds=op['ramp'],producer_rest_bonus=op['bonus'],production_multiplier=op['multiplier'])
            b.deathmatch=op['deathmatch'];exec(self.economy_ref['production'],dict(self.economy_ref,self=b))
        elif name=='grave_economy':self.units[op['unit']].update(copy.deepcopy(op['fields']))
        elif name=='economy_native':
            if 'unit' in op:b._native_objects[op['id']]=self.units[op['unit']]
            else:b._native_objects.pop(op['id'],None)
        elif name=='producer_seat':self.all_plants[op['plant']]['_pvp_seat']=op['side']
        elif name=='grave_progress':b._grave_progress[op['id']]=op['value']
        elif name=='sun_add':
            sun=copy.deepcopy(op['value']);self.sun_records.append(sun);g['阳光球'].append(sun)
            if 'seat' in op:b._native_sun_seats[id(sun)]=op['seat']
            if 'bloom' in op:b.content.september.bloom_sun_amounts[id(sun)]=op['bloom']
        elif name=='sun_alias':g['阳光球'].append(self.sun_records[op['index']])
        elif name=='death_point':b.secrets66.death_points.append(tuple(op['point']))
        elif name=='economy_step':b.dt=op['elapsed'];b._economy()
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if not self.economy_seen:return
        b=self.b
        row['economy']=dict(previous_tick=b._day_brain_native_tick,sky_progress=b.sky_progress,subsidy_phase=b.zsecrets.subsidy_phase,
            death_points=[list(p) for p in b.secrets66.death_points],loose_suns=self.g['阳光球'],
            sun_metadata=[[b._native_sun_seats.get(id(s)),b.content.september.bloom_sun_amounts.get(id(s))] for s in self.sun_records],
            grave_progress=b._grave_progress,grave_fields=[{k:u[k] for k in ('_pvp_max_hp','_pvp_born','_pvp_mature','_pvp_produced') if k in u} for u in self.units],
            rng=list(b.rng.getstate()[1]))


def cases():
    source=res.phase.cases()[0][1];out=[]
    def base(i):
        c=copy.deepcopy(source);c['seed']=725000+i;ops=c['operations']=c['operations'][:1]
        mode=('duel','duo','coop','pve')[i%4];ops[0]['mode']=mode
        seats={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'coop':['plant','plant2'],'pve':['plant']}[mode]
        for n,row in enumerate(ops[0]['solid']):
            if n>6:row[:]=[1]*len(row)
        for s in c['players']:c['players'][s]['secrets']=['secret:阳光'] if i%7==0 else []
        ops += [dict(op='resources_setup',accounts={s:[100.,10.] for s in c['players']}),
            dict(op='economy_setup',present=seats,producers=['向日葵','双子向日葵','阳光菇'],height=576.,
                 previous_tick=(0,249,500)[i%3],progress=(0.,.4999999995,2.)[i//3%3],interval=.5,
                 subsidy=i%2==0,subsidy_phase=(0.,100.,249.)[i//4%3],night=i%5==0,
                 day_interval=5.,day_amount=15.,sky_amount=25.,lifetime=30.)]
        return c,ops
    for i in range(80):
        c,ops=base(i)
        for j in range(3):
            ops += [dict(op='plant_original',name='向日葵',cell=[8,(3,5,19)[j]]),
                    dict(op='plant_write',plant=j,values={'_pvp_id':('z','a','b')[j]}),
                    dict(op='producer_seat',plant=j,side=('plant','plant2','plant')[j])]
        for j in range(5):
            sun=[j,[(216.,959.9,-.1,960.1,264.)[j],408.,j*.1,-.1],j*2,(i+j)%2]
            ops.append(dict(op='sun_add',value=sun))
            if j==1:ops[-1]['seat']=('plant2','zombie2')[i%2]
            if j==2:ops[-1]['bloom']=(0.,15.,50.)[i%3]
            if j==3:ops.append(dict(op='death_point',point=[959.,408.+(72.,72.00001)[i%2]]))
        if i%3==0:ops.append(dict(op='sun_alias',index=2))
        ops += [dict(op='clock',tick=500,time=2.),dict(op='economy_step',elapsed=.04),dict(op='economy_step',elapsed=0.),
                dict(op='sun_advance'),dict(op='clock',tick=510,time=2.04),dict(op='economy_step',elapsed=.04)]
        out.append(('native-sun-attribution-and-amounts-'+str(i),c))
    for i in range(96):
        c,ops=base(200+i)
        ops[2]['day_interval']=(.002,.006,1.,5.)[i//4%4]
        for j in range(4):
            ops += [dict(op='grave_economy',unit=j,fields={'_pvp_grave':(i+j)%4==0,'_pvp_orphan_barrel':(i+j)%4==1,'血量':0. if i%6==0 else 40.}),
                    dict(op='track_unit',unit=j,owner='plant' if i%3 else 'zombie')]
        if i%3==1:ops.append(dict(op='roster_replace',targets=[]))
        for j in range(5):
            ticks=(0,1,2,4,4) if ops[2]['day_interval']<.01 else (0,249,250,500,500)
            ops += [dict(op='clock',tick=ticks[j],time=j*.04),dict(op='economy_step',elapsed=(0.,.04,.5,2.)[(i+j)%4])]
            if j==2:ops.append(dict(op='economy_state',night=i%2==0))
            if j==3:ops.append(dict(op='economy_state',night=False,subsidy=i%2==1))
        out.append(('native-day-clock-subsidy-and-sky-'+str(i),c))
    for i in range(96):
        c,ops=base(400+i)
        for j in range(3):
            fields=dict(producer=j<2,period=(12.,14.,16.)[j],yield_amount=(25.,20.,50.)[j])
            if j==1:fields.update(mature_at=90.,mature_hp=800.,mature_yield=40.)
            key='grave'+str(j)
            ops += [dict(op='producer_card',id=key,fields=fields),
                    dict(op='grave_economy',unit=j,fields={'_pvp_grave':True,'_pvp_card':key,'_pvp_max_hp':400.,'_pvp_born':0.,
                         '_pvp_seat':'zombie2' if j%2 else 'zombie','_pvp_produced':i%2==0,'_pvp_mature':i%3==0,'血量':(0.,100.,399.)[(i+j)%3]}),
                    dict(op='economy_native',id=key,unit=j),dict(op='grave_progress',id=key,value=(5.9999999995,6.,13.9999999995,30.)[(i+j)%4])]
        if i%3==0:ops.append(dict(op='economy_native',id='alias',unit=1))
        for j in range(4):
            time=(89.999,90.,90.001,95.)[j]
            ops += [dict(op='clock',tick=round(time*250),time=time),dict(op='economy_step',elapsed=.04)]
        ops += [dict(op='economy_native',id='grave0'),dict(op='economy_native',id='grave0',unit=1),dict(op='economy_step',elapsed=0.)]
        out.append(('native-grave-growth-and-payment-'+str(i),c))
    for i in range(96):
        c,ops=base(600+i)
        for j,kind in enumerate(('向日葵','阳光菇','豌豆射手')):
            ops += [dict(op='plant_original',name=kind,cell=[8,3+j*3]),
                    dict(op='producer_card',id='plant:'+kind,fields=dict(producer=j<2,period=18.+j)),
                    dict(op='producer_fields',plant=j,fields={'植物血':(0.,50.,100.,150.)[(i+j)%4],
                        '爆了':(0.,1.,124.,125.)[(i+j)%4],'_pvp_sun_due':(1500.,125.,1.0000001,1.,0.)[(i+j)%5],
                        '_pvp_rest_hp':(None,100.)[(i+j)%2],'_pvp_rest_since':0.,'_pvp_aura_factor':(.5,1.,2.)[i%3]})]
            if i%8==0:ops.append(dict(op='plant_write',plant=j,values={'睡觉':0.}))
        for j in range(5):
            tick=(0,249,250,2000,10000)[j]
            ops += [dict(op='clock',tick=tick,time=tick/250.),dict(op='production_step',quiet=(0.,1.,5.)[i%3],
                        ramp=(0.,1.,5.)[i//3%3],bonus=(0.,.5,1.)[i//9%3],multiplier=3.,deathmatch=i%2==0)]
            if j==2:ops.append(dict(op='producer_fields',plant=0,fields={'植物血':49.}))
        out.append(('native-producer-rest-and-animation-'+str(i),c))
    return out


if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(res.__file__),Path(res.hp.__file__),Path(res.phase.__file__),Path(shared.__file__),
           res.seat.SIM,res.seat.BALANCE,shared.BATTLE,hero.ZSECRETS,hero.PHYSICS,res.VIEW,SECRETS66,
           shared.ROOT/'tools/typed72/resources_probe.cpp',shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    sys.exit(shooting.main(paths,reference,cases,EconomyExtension,'typed72-native-whole-economy'))
