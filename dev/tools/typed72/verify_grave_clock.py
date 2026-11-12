"""Compare grave tending, wake input and the complete native grave clock loop."""
import ast
import copy
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_economy as economy
res=economy.res
shared=res.shared
hero=res.hero
shooting=res.shooting
GRAVES=shared.PVP/'pvp59_graves.py'
CONTENT=shared.PVP/'pvp61_content.py'
CATALOG=shared.PVP/'pvp61_catalog.py'
FIELDS=('_pvp_producer','_pvp_idle','_pvp_zs_awake','_pvp_production_rate')


def reference():
    ref=economy.reference()
    env=dict(math=math)
    for name in ('GRAVE_IDLE_SECONDS','GRAVE_DOZE_SECONDS','DROWSY_RATE','SCARECROW_RADIUS'):
        env[name]=hero.constant(GRAVES,name)
    env['SCARECROW']=hero.constant(CATALOG,'SCARECROW')
    shooting.projectiles.functions(GRAVES,['drowsy_level','drowsy','sleep_rate'],env)
    hero.selected_class(GRAVES,['__init__','advance','_guarded','_touched','wake','wake_input'],'GraveIdle',env)
    hero.selected_class(CONTENT,['scarecrows'],'Scarecrows',env)
    hero.selected_class(hero.ZSECRETS,['team_last_stand'],'LastStand',env)
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    loops=[node for node in ast.walk(tree) if isinstance(node,ast.For) and isinstance(node.target,ast.Name)
           and node.target.id=='grave' and isinstance(node.iter,ast.Name) and node.iter.id=='graves'
           and any(isinstance(item,ast.Constant) and item.value=='_pvp_production_rate' for item in ast.walk(node))]
    loop,=loops
    env['clock']=compile(ast.Module(body=[loop],type_ignores=[]),str(shared.BATTLE),'exec')
    ref['grave_clock']=env
    return ref


class GraveClockExtension(economy.EconomyExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.grave_seen=False
        self.grave_ref=ref['grave_clock']
        b=self.b
        b.grave_idle=self.grave_ref['GraveIdle'](b)
        b.content.pvp61=self.grave_ref['Scarecrows']()
        b.content.pvp61.g=self.g
        b.zsecrets.team_last_stand=types.MethodType(self.grave_ref['LastStand'].team_last_stand,b.zsecrets)

    def operation(self,op):
        b=self.b
        name=op['op']
        if name=='grave_clock_setup':
            self.grave_seen=True
            b.present=frozenset(op['present'])
        elif name=='grave_clock_state':
            if 'deathmatch' in op:b.deathmatch=op['deathmatch']
            if 'last_stand' in op:b.zsecrets.last_stand=dict(op['last_stand'])
        elif name=='grave_idle_fields':
            unit=self.units[op['unit']]
            unit.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):unit.pop(key,None)
        elif name=='grave_clock_step':
            b.rules['production_multiplier']=op['multiplier']
            exec(self.grave_ref['clock'],dict(self.grave_ref,self=b,graves=[self.units[i] for i in op['graves']]))
        elif name=='grave_idle_step':return b.grave_idle.advance(self.units[op['unit']],op['factor'])
        elif name=='grave_wake':b.grave_idle.wake(self.units[op['unit']],op['cause'])
        elif name=='grave_wake_input':return b.grave_idle.wake_input(op['side'],op['id'])
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.grave_seen:
            row['grave_idle']=dict(units=[[{key:u[key] for key in FIELDS if key in u},
                self.grave_ref['drowsy_level'](u),self.grave_ref['drowsy'](u)] for u in self.units],
                progress=self.b._grave_progress)


def cases():
    prototype=res.phase.cases()[0][1]
    output=[]
    def setup(index):
        case=copy.deepcopy(prototype)
        case['seed']=821000+index
        ops=case['operations']=case['operations'][:1]
        ops[0]['mode']='duo'
        ops += [dict(op='grave_clock_setup',present=['plant','zombie','plant2','zombie2']),
                dict(op='resources_setup',accounts={seat:[0.,0.] for seat in case['players']})]
        for seat in ('zombie','zombie2'):
            ops.append(dict(op='write',target=seat,values={'玩家位置':[700.,100.,0.,0.],'玩家血量':40.}))
        for unit in range(4):
            ops.append(dict(op='grave_idle_fields',unit=unit,fields={'_pvp_content':'','_pvp_owner':'zombie',
                '_pvp_id':'grave-'+str(unit),'_pvp_producer':unit<2,'_pvp_grave':unit<3,'位置':[24.+unit*48.,432.,0.,0.]},erase=['灰烬','魅惑']))
            ops.append(dict(op='economy_native',unit=unit,id='grave-'+str(unit)))
        return case,ops
    def fields(ops,unit,**values):ops.append(dict(op='grave_idle_fields',unit=unit,fields=values))
    def step(ops,multiplier=2.):ops.append(dict(op='grave_clock_step',graves=[0,1,2],multiplier=multiplier))

    for i in range(144):
        case,ops=setup(i)
        fields(ops,0,_pvp_idle=(0.,19.995999999,19.996,20.,39.996,40.,100.)[i%7],
               冰冻=(0.,.5,1.,1000.,1001.)[i//7%5],黄油=(0.,1.,2.)[i//35%3],眩晕=1. if i%11==0 else 0.)
        fields(ops,1,_pvp_idle=(20.,30.,40.)[i%3],冰冻=2.,_pvp_zs_awake=i%4==0)
        fields(ops,2,_pvp_idle=60.,冰冻=1.,黄油=2.,眩晕=1.)
        ops.append(dict(op='grave_clock_state',deathmatch=i%9==0,last_stand={'zombie2':50.} if i%10==0 else {}))
        for j in range(6):step(ops,(0.,.5,2.,4.)[i%4])
        ops.append(dict(op='grave_clock_state',deathmatch=False,last_stand={}))
        step(ops)
        ops += [dict(op='grave_idle_step',unit=0,factor=.5),dict(op='grave_wake',unit=1,cause='sweep')]
        output.append(('native-grave-status-and-clock-'+str(i),case))

    for i in range(96):
        case,ops=setup(200+i)
        x=(0.,959.9,960.,-.1)[i%4]
        fields(ops,0,位置=[x,432.,0.,0.],_pvp_idle=30.)
        dx=(43.2,43.2000001,-43.2,-43.2000001)[i//4%4]
        y=(384.,384.000001,432.,527.999999,528.,550.)[i//16%6]
        seat=('zombie','zombie2')[i%2]
        ops.append(dict(op='write',target=seat,values={'玩家位置':[x+dx,y,0.,0.],'玩家血量':0. if i%13==0 else 40.}))
        step(ops)
        fields(ops,0,_pvp_idle=20.-1e-10)
        ops.append(dict(op='grave_idle_step',unit=0,factor=0.))
        output.append(('grave-hero-touch-seams-and-open-edges-'+str(i),case))

    for i in range(96):
        case,ops=setup(400+i)
        fields(ops,0,_pvp_idle=30.,_pvp_owner=('zombie','plant')[i%2])
        dx=(287.999999,288.,288.000001,-288.,-288.000001)[i%5]
        fields(ops,3,_pvp_content='稻草人',位置=[24.+dx+(960. if i%3==0 else 0.),432.,0.,0.],
               血量=0. if i%7==0 else 300.)
        if i%4<2:fields(ops,3,魅惑=None)
        if i%11==0:fields(ops,3,灰烬=0.)
        step(ops)
        fields(ops,0,_pvp_idle=20.)
        ops.append(dict(op='roster_replace',targets=[0,1,2]))
        step(ops)
        output.append(('grave-scarecrow-radius-and-allegiance-'+str(i),case))

    for i in range(64):
        case,ops=setup(600+i)
        fields(ops,0,_pvp_idle=(19.999999998,19.999999999,20.,40.)[i%4])
        fields(ops,1,_pvp_owner=('zombie','zombie2','plant',None)[i%4])
        fields(ops,2,血量=(300.,0.,-1.)[i%3])
        if i%8==0:ops.append(dict(op='grave_idle_fields',unit=1,fields={},erase=['_pvp_owner']))
        for uid in (None,123,[],{},'', 'missing','grave-0','grave-1','grave-2','grave-3'):
            ops.append(dict(op='grave_wake_input',side=('plant','plant2','zombie','zombie2')[i//4%4],id=uid))
        ops += [dict(op='grave_wake',unit=0,cause='hero'),dict(op='grave_wake',unit=0,cause='hero')]
        output.append(('grave-wake-input-and-idempotence-'+str(i),case))
    return output


if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(economy.__file__),Path(res.__file__),Path(res.hp.__file__),Path(res.phase.__file__),
           Path(shared.__file__),shared.BATTLE,GRAVES,CONTENT,CATALOG,hero.ZSECRETS,
           shared.ROOT/'tools/typed72/maintenance_probe.cpp',shared.ROOT/'tools/typed72/resources_probe.cpp',
           shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    sys.exit(shooting.main(paths,reference,cases,GraveClockExtension,'typed72-grave-idle-and-clock'))
