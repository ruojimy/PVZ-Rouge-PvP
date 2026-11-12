"""Installed PvP plant death region, nuclear/supplement gates and zombie rewards."""
import copy
import marshal
import math
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import verify_grave_clock as graves
economy=graves.economy
res=graves.res
shared=graves.shared
hero=graves.hero
shooting=graves.shooting
CONTENT64=shared.PVP/'pvp64_content.py'
CATALOG64=shared.PVP/'pvp64_catalog.py'
RAW=shared.ROOT/'extract/live/plant_maintenance.marshal'


def reference():
    ref=graves.reference()
    env=dict(math=math)
    shooting.projectiles.functions(res.seat.SIM,['wrap_delta'],env)
    env['PLANT_ZOMBIES']=hero.constant(hero.ZSECRETS,'PLANT_ZOMBIES')
    env['BRAIN_PER_KILL']=hero.constant(hero.ZSECRETS,'BRAIN_PER_KILL')
    env['PRIMAL_MINE']=hero.constant(CATALOG64,'PRIMAL_MINE')
    env['PRIMAL_RADIUS']=hero.constant(CATALOG64,'PRIMAL_RADIUS')
    hero.selected_class(hero.ZSECRETS,['on_plant_killed','_queue_conversion','has','holders','pay'],'Killed',env)
    hero.selected_class(shared.SEPTEMBER,['supplement_death'],'Supplement',env)
    hero.selected_class(economy.SECRETS66,['doom','note_death_sun'],'PlantSecrets',env)
    hero.selected_class(CONTENT64,['_mine_plant','_mine_x','_mine_y'],'Mine',env)
    env['region']=marshal.loads(RAW.read_bytes())
    ref['maintenance']=env
    return ref


class MaintenanceExtension(graves.GraveClockExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.death_seen=False
        self.death_ref=ref['maintenance']
        b=self.b;g=self.g;env=self.death_ref
        b.zsecrets.converts=[]
        for name,fn in env['Killed'].__dict__.items():
            if callable(fn):setattr(b.zsecrets,name,types.MethodType(fn,b.zsecrets))
        b.zsecrets._cards=lambda:self.admitted_forms
        for name,fn in env['PlantSecrets'].__dict__.items():
            if callable(fn):setattr(b.secrets66,name,types.MethodType(fn,b.secrets66))
        b.secrets66.g=g;b.secrets66.secrets=set()
        b.content.september.b=b
        b.content.september.supplement_death=types.MethodType(env['Supplement'].supplement_death,b.content.september)
        mine=env['Mine']();mine.b=b;mine.g=g
        g.update(_pvp64_mine_x=mine._mine_x,_pvp64_mine_y=mine._mine_y,
                 _pvp66_doom=b.secrets66.doom,_pvp_supplement_death=b.content.september.supplement_death)

    def operation(self,op):
        b=self.b;g=self.g;name=op['op']
        if name=='death_policy_setup':
            self.death_seen=True
            b.zsecrets.enabled=op['enabled']
            b.zsecrets.by_seat={seat:set() for seat in b.players if seat.startswith('zombie')}
            for seat in op['brain_holders']:b.zsecrets.by_seat[seat].add('脑光')
            for seat in op['conversion_holders']:b.zsecrets.by_seat[seat].add('植物僵尸')
            b.zsecrets.team=set().union(*b.zsecrets.by_seat.values())
            b.secrets66.secrets={'secret:核平'} if op['nuclear'] else set()
            self.admitted_forms={'zombie:'+name for name in op['forms'].values()}
        elif name=='death_plant_fields':
            plant=self.all_plants[op['plant']]
            plant.update(copy.deepcopy(op['fields']))
            for key in op.get('erase',[]):plant.pop(key,None)
        elif name=='plant_killed':b.zsecrets.on_plant_killed(self.all_plants[op['plant']])
        elif name=='death_supplement':
            g['l']=op['index']
            return b.content.september.supplement_death()
        elif name=='death_doom':
            g['z']=op['index']
            return b.secrets66.doom()
        elif name=='maintenance_run':
            with self.c.context(target='zombie',owner='plant',phase='plants'):
                exec(self.death_ref['region'],g)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.death_seen:
            row['plant_deaths']=dict(conversions=[list(item) for item in self.b.zsecrets.converts],
                points=[list(point) for point in self.b.secrets66.death_points],suns=self.g['阳光球'])


def cases():
    prototype=res.phase.cases()[0][1]
    forms=hero.constant(hero.ZSECRETS,'PLANT_ZOMBIES')
    output=[]
    def setup(index):
        case=copy.deepcopy(prototype);case['seed']=832000+index
        ops=case['operations']=case['operations'][:1]
        ops[0]['mode']='duo'
        case['globals']['秘籍']=['补光'] if index%2 else []
        # The real PvP context selects normal mode even with a campaign frame
        # outside it. This is exercised along with the ordinary outer frame.
        case['globals']['模式']='我是僵尸' if index%3==0 else '正常模式'
        ops += [dict(op='resources_setup',accounts={seat:[100.,0.] for seat in case['players']}),
                dict(op='death_policy_setup',enabled=index%5!=0,nuclear=index%2==0,
                     brain_holders=['zombie','zombie2'] if index%3 else ['zombie2'],
                     conversion_holders=['zombie','zombie2'] if index%4 else [],forms=forms)]
        for i in range(4):
            ops.append(dict(op='grave_idle_fields',unit=i,fields={'_pvp_owner':'zombie','_pvp_content':'',
                '血量':1000.,'位置':[240.+i*24.,408.,0.,0.]},erase=['灰烬','魅惑']))
        ops.append(dict(op='write',target='zombie',values={'玩家位置':[264.,408.,0.,0.],'玩家血量':40.}))
        return case,ops
    def plant(ops,name,cell,fields=None):
        index=sum(op['op']=='plant_original' for op in ops)
        ops.append(dict(op='plant_original',name=name,cell=cell))
        ops.append(dict(op='plant_write',plant=index,values={'_pvp_id':'plant-'+str(index),'_pvp_owner':'plant'}))
        if fields:ops.append(dict(op='death_plant_fields',plant=index,fields=fields))
        return index

    kinds=('向日葵','毁灭菇','樱桃炸弹','火爆辣椒','缠绕海草','土豆地雷','花盆','睡莲')
    for i in range(160):
        case,ops=setup(i);kind=kinds[i%len(kinds)]
        fields={'死':(0,False,True,1)[i//8%4]}
        if i//16%3==1:fields['睡觉']=0.
        if i//16%3==2:fields['铲死']=False
        if kind=='土豆地雷':fields['埋藏']=0. if i%3 else 1.
        first=plant(ops,kind,[8,5],fields)
        if kind=='睡莲':plant(ops,'向日葵',[7,5])
        if kind=='缠绕海草' and i%2:ops.append(dict(op='death_plant_fields',plant=first,fields={'黑白':False}))
        for col in (3,4,6,7):
            ops.append(dict(op='tile_replace',cell=[8,col],value={'方块':('空','梯子块','雪','石')[i//8%4]}))
        if i%4==0:ops.append(dict(op='roster_replace',targets=[0,'zombie',1,2,3]))
        if i%7==0:ops.append(dict(op='grave_idle_fields',unit=1,fields={'魅惑':None}))
        ops += [dict(op='maintenance_run'),dict(op='maintenance_run'),dict(op='world_important')]
        output.append(('installed-plant-death-and-cleanup-'+str(i),case))

    for i in range(96):
        case,ops=setup(200+i)
        kind=('豌豆射手','向日葵','樱桃炸弹','毁灭菇','土豆地雷','倭瓜')[i%6]
        plant(ops,kind,[8,5],{'_pvp_temporary':i%5==0,'_pvp_zs_killed':i%7==0,
                            '_pvp_transform_succeeded':i%3==0,'方向':(-1.,0.,1.)[i%3]})
        if i%4==0:ops.append(dict(op='plant_write',plant=0,values={'魅惑':None}))
        ops += [dict(op='plant_killed',plant=0),dict(op='plant_killed',plant=0),
                dict(op='death_supplement',index=0),dict(op='death_supplement',index=0)]
        ops.append(dict(op='death_plant_fields',plant=0,fields={'死':0,'睡觉':0.}))
        ops.append(dict(op='maintenance_run'))
        output.append(('death-reward-deduplication-and-conversion-'+str(i),case))

    for i in range(96):
        case,ops=setup(400+i)
        col=(0,19,5)[i%3];x=col*48.+24.
        plant(ops,'土豆地雷',[8,col],{'死':0,'埋藏':0.})
        ops.append(dict(op='plant_write',plant=0,values={'_pvp_content':'原始土豆地雷' if i%2 else ''}))
        dx=(115.2-1e-8,115.2,115.2+1e-8,24.,48.,0.)[i//2%6]
        for unit in range(4):
            y=(408.,480.,528.,528.000001)[unit]
            ops.append(dict(op='grave_idle_fields',unit=unit,fields={'位置':[x+dx+(960. if unit%2 else 0.),y,0.,0.]}))
        ops.append(dict(op='maintenance_run'))
        output.append(('primal-mine-body-circle-and-periodic-boundary-'+str(i),case))

    for i in range(64):
        case,ops=setup(600+i)
        for j in range(4):plant(ops,kinds[(i+j)%len(kinds)],[8,3+j],{'死':0,'埋藏':0.})
        if i%4==0:ops.append(dict(op='plant_roster_replace',plants=[0,1,0,3]))
        ops += [dict(op='maintenance_run'),dict(op='maintenance_run'),dict(op='plant_killed',plant=0)]
        output.append(('reverse-death-roster-and-retained-records-'+str(i),case))

    for i in range(48):
        case,ops=setup(800+i)
        plant(ops,'毁灭菇',[8,5])
        ops += [dict(op='grave_idle_fields',unit=1,fields={'魅惑':None}),
                dict(op='roster_replace',targets=[0,1,'zombie',2,3]),
                dict(op='context',target='zombie',owner='plant',phase='plants',body=[
                    dict(op='death_doom',index=index) for index in (-1,0,1,2,3,4,5)]),
                dict(op='death_plant_fields',plant=0,fields={'死':0},erase=['睡觉']),
                dict(op='maintenance_run')]
        output.append(('nuclear-gate-heroes-allies-and-range-'+str(i),case))
    return output


if __name__=='__main__':
    paths=[Path(__file__).resolve(),Path(graves.__file__),Path(economy.__file__),Path(res.__file__),Path(res.hp.__file__),
           Path(res.phase.__file__),Path(shared.__file__),shared.BATTLE,shared.SEPTEMBER,hero.ZSECRETS,
           economy.SECRETS66,CONTENT64,CATALOG64,RAW,graves.GRAVES,graves.CONTENT,graves.CATALOG,
           shared.ROOT/'tools/typed72/maintenance_probe.cpp',shared.ROOT/'tools/typed72/resources_probe.cpp',
           shared.ROOT/'tools/typed72/world_rules_probe.cpp',shared.ROOT/'tools/typed72/zombie_motion_fixture.inc']
    sys.exit(shooting.main(paths,reference,cases,MaintenanceExtension,'typed72-installed-plant-maintenance'))
