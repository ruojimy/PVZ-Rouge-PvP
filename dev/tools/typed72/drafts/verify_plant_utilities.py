"""Installed sea-shroom bridge and owner umbrella passes, including native plant execution."""
import copy
import marshal
import sys
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_plant_region as plants
shared=plants.shared
shooting=plants.shooting
hero=plants.hero
SEA=shared.PVP/'pvp59_sea.py'


def reference():
    ref=plants.reference()
    env={}
    shooting.projectiles.functions(shooting.projectiles.SIMULATION,['wrap_delta'],env)
    env['BUBBLE_DAMAGE']=hero.constant(SEA,'BUBBLE_DAMAGE')
    hero.selected_class(SEA,['__init__','restore','_water_graves','gate','bubbles'],'SeaShroom',env)
    hero.selected_class(shared.BATTLE,['_own_umbrella_effects','_own_umbrella_pass'],'Umbrella',env)
    env['regions']={name:marshal.loads((shared.ROOT/('extract/live/'+name+'.marshal')).read_bytes())
                    for name in ('umbrella_player_trigger','umbrella_player_bounce')}
    ref['plant_utilities']=env
    return ref


class PlantUtilitiesExtension(plants.PlantRegionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.utilities_seen=False
        env=ref['plant_utilities']
        self.sea=env['SeaShroom'](self.content)
        for name in ('_own_umbrella_effects','_own_umbrella_pass'):
            setattr(self.b,name,types.MethodType(getattr(env['Umbrella'],name),self.b))
        self.b.engine.regions.update(env['regions'])

    def operation(self,op):
        name=op['op']
        if name=='plant_utilities_setup':
            self.utilities_seen=True
            self.base_rows=self.g['同横尸']
            for row,water in zip(self.b.map['tiles'],op['water']):
                for cell,value in zip(row,water):cell['water']=bool(value)
        elif name=='sea_gate':self.sea.gate(self.all_plants[op['plant']])
        elif name=='sea_restore':self.sea.restore()
        elif name=='sea_bubbles':self.sea.bubbles()
        elif name=='sea_region':
            original=self.g['_pvp_plant_gate']
            def gate():
                original()
                self.sea.gate(self.g['植物'][self.g['l']])
            self.g['_pvp_plant_gate']=gate
            try:
                with self.c.context('zombie','plant','plants'):
                    exec(self.plant_ref['region'],self.g)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
            finally:
                self.g['_pvp_plant_gate']=original
                self.sea.restore()
        elif name=='owner_umbrella':
            try:self.b._own_umbrella_effects(op['after'])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.utilities_seen:row['plant_utilities']=[self.sea._base is not None,self.g['同横尸'] is self.base_rows]


def cases():
    prototype=plants.cases()[0][1]
    output=[]
    def setup(index):
        case=copy.deepcopy(prototype)
        case['seed']=950000+index
        ops=case['operations']=case['operations'][:2]
        ops[0].update(mode=('duel','duo','coop','pve')[index%4],rows=[[8,[]],[3,[1,9]]],cols=[])
        water=[[0]*20 for _ in case['plant_world']['grid']]
        water[8]=[1]*20
        ops.append(dict(op='plant_utilities_setup',water=water))
        for unit in range(4):
            ops.append(dict(op='plant_unit',unit=unit,fields={'血量':100.,'位置':[264.+unit*48.,384.,0.,0.],
                '防具':'','防具血量':0.,'手持':'','手持血量':0.,'_pvp_owner':'zombie','大小':2.},erase=['魅惑']))
            ops.append(dict(op='rules_grave',unit=unit,grave=True))
        return case,ops
    def plant(ops,kind='海蘑菇',cell=(8,5),fields=None):
        index=sum(op['op']=='plant_original' for op in ops)
        ops.extend([dict(op='plant_original',cell=list(cell),name=kind,facing=1.),
                    dict(op='plant_fields',plant=index,fields=dict({'_pvp_owner':'plant'},**(fields or {})),erase=['睡觉'])])
        return index
    for i in range(96):
        case,ops=setup(i)
        plant(ops,fields={'植物血':(100.,0.)[i//48]})
        plant(ops,'缠绕水草')
        plant(ops,cell=(7,5))
        if i%6==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        for unit in range(4):
            fields={'位置':[(264.,-1.,960.,48.)[unit],(384.,384.001,383.999,432.)[i//4%4],0.,0.],
                    '_pvp_owner':('zombie','plant',None,'zombie2')[unit]}
            if i%4==1:fields['灰烬']=0.
            if i%4==2:fields['魅惑']=None
            if i%4==3:fields['血量']=0.
            ops.append(dict(op='plant_unit',unit=unit,fields=fields))
        for index in (0,1,0,2,0):ops.append(dict(op='sea_gate',plant=index))
        ops.extend([dict(op='sea_restore'),dict(op='sea_restore'),dict(op='sea_region')])
        output.append(('sea-row-allegiance-and-restoration-'+str(i),case))
    for i in range(128):
        case,ops=setup(200+i)
        x=(264.,959.9,0.,-960.)[i%4]
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[x,384.,0.,0.],
                    '血量':(5.,100.)[i//4%2],'手持':'钢门' if i%7==0 else '',
                    '手持血量':100. if i%7==0 else 0.}))
        ops.append(dict(op='roster_replace',targets=[0,0,1,'zombie']))
        dx=(24.,24.0000001,-24.,-24.0000001)[i//4%4]
        dy=(-40.8,-40.7999999,33.6,33.6000001,0.,24.,-24.,0.)[i//16%8]
        for j in range(3):
            ops.append(dict(op='service_entity',name='海泡泡' if j<2 else '泡泡',position=[x+dx+(960. if j==1 else 0.),384.+dy,0.,0.]))
            values={'_pvp_owner':'plant','消亡':(0.,None,1.,-1.)[i//32]}
            if j==1 and i%3==0:values['_pvp_owner']='zombie'
            ops.append(dict(op='region_fields',entity=j,values=values))
        ops.extend([dict(op='squash_roster',entities=[2,0,0,1]),dict(op='sea_bubbles'),dict(op='sea_bubbles')])
        output.append(('sea-bubble-boundaries-armor-and-identity-'+str(i),case))
    for i in range(128):
        case,ops=setup(400+i)
        plant(ops,'萝卜伞',fields={'射':(0.,1.,19.,20.)[i//4%4],'射cd':(-1.,0.,1.,1200.)[i//16%4]})
        plant(ops,'萝卜伞',(8,6),{'射':20.,'射cd':0.})
        dx=(0.,48.,96.,96.000001)[i//4%4]
        for seat in ('plant','plant2'):
            case['heroes'][seat]['玩家位置']=[264.+dx,408.,0.,(.96,.96000001)[i//64]]
            case['players'][seat]['hp']=0. if seat=='plant' and i%9==0 else 40.
        if i%7==0:ops.append(dict(op='plant_fields',plant=0,fields={'睡觉':0.}))
        if i%11==0:ops.append(dict(op='plant_fields',plant=1,fields={'植物血':0.}))
        ops.extend([dict(op='owner_umbrella',after=False),dict(op='owner_umbrella',after=True),
                    dict(op='plant_region_run'),dict(op='owner_umbrella',after=True)])
        output.append(('owner-umbrella-mode-seat-and-thresholds-'+str(i),case))
    for i in range(24):
        case,ops=setup(600+i)
        plant(ops,'萝卜伞',fields={'射':0.,'射cd':0.})
        ops.append(dict(op='plant_fields',plant=0,fields={},erase=['射cd']))
        case['heroes']['plant']['玩家位置']=[264.,408.,0.,1.]
        case['heroes']['plant2']['玩家位置']=[264.,408.,0.,1.]
        ops.extend([dict(op='owner_umbrella',after=bool(i%2),catch=True),dict(op='owner')])
        output.append(('owner-umbrella-missing-clock-unwind-'+str(i),case))
    return output


def paths():
    return plants.paths()+[Path(__file__).resolve(),Path(plants.__file__),SEA,
        shared.ROOT/'tools/typed72/plant_utilities_probe.cpp']+[
        shared.ROOT/('extract/live/'+name+'.marshal') for name in ('umbrella_player_trigger','umbrella_player_bounce')]


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,PlantUtilitiesExtension,'typed72-plant-utilities',probe_timeout=600))
