"""Original Grave Buster lifecycle and its attackable PvP grave binding."""
import contextlib
import copy
import functools
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_plant_region as plants
shared=plants.shared
shooting=plants.shooting
hero=plants.hero
BRIDGE=shared.PVP/'native_gravebuster.py'


def reference():
    ref=plants.reference()
    env=dict(math=math,copy=copy,contextmanager=contextlib.contextmanager,wraps=functools.wraps)
    hero.selected_class(BRIDGE,['__init__','_current','_target_cell','_valid','attach','_event','_cancel',
                               '_remove_completion_coin','before_native_tick','plants','close'],'NativeGravebuster',env)
    ref['grave_binding']=env
    return ref


class GraveBindingExtension(plants.PlantRegionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.binding_seen=False
        self.binding_events=[]
        self.g['摧毁方块']=self.destroy_pvp
        self.g['显示植物']=lambda index:None
        self.bridge=ref['grave_binding']['NativeGravebuster'](self.g,self.native._native_objects.get,
                            on_consume=self.consume,on_event=self.event)

    def consume(self,target,plant):
        self.calls.append(['grave_consume',self.label(target),self.label(plant)['plant']])
        self.before('grave_consume');self.after('grave_consume')

    def event(self,kind,**fields):
        self.binding_events.append([kind,fields])
        self.before('grave_event');self.after('grave_event')

    def operation(self,op):
        name=op['op']
        if name=='binding_setup':self.binding_seen=True
        elif name=='binding_attach':
            try:self.bridge.attach(self.all_plants[op['plant']],op['target'])
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        elif name=='binding_before':self.bridge.before_native_tick()
        elif name=='binding_close':self.bridge.close()
        elif name=='binding_destroy':
            self.g['l']=op.get('index',-1)
            self.g['摧毁方块'](*op['cell'])
        elif name=='binding_coin':
            self.g['钱币'].append([op.get('age',0.),copy.deepcopy(op['point']),op.get('cooldown',0.),op['kind']])
        elif name=='binding_draw_target':
            index=op['index'];roster=self.g['植物']
            plant=roster[index] if 0<=index<len(roster) else None
            link=self.bridge.links.get(id(plant))
            if link is not None and self.bridge._valid(link):return list(link['cell'])+[link['target_id']]
        elif name in ('binding_region','binding_scope'):
            try:
                with self.c.context('zombie','plant','plants'),self.bridge.plants():
                    if name=='binding_region':exec(self.plant_ref['region'],self.g)
                    else:self.operations(op['body'],False)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.binding_seen:
            row['grave_binding']=dict(links=[[self.label(link['plant'])['plant'],self.label(link['target']),link['target_id'],list(link['cell'])]
                                            for link in self.bridge.links.values()],
                cancelled=sorted(self.label(plant)['plant'] for plant in self.bridge._cancelled.values()),
                events=self.binding_events,depth=self.bridge._depth,closed=self.bridge._closed)


def cases():
    prototype=plants.cases()[0][1]
    output=[]
    def setup(index):
        case=copy.deepcopy(prototype);case['seed']=960000+index
        ops=case['operations']=case['operations'][:2]
        ops.append(dict(op='binding_setup'))
        for j in range(4):
            ops.extend([dict(op='plant_unit',unit=j,fields={'血量':100.,'位置':[264.+j*48.,432.,0.,0.],
                        '_pvp_owner':'zombie'},erase=['魅惑']),
                        dict(op='registry_flags',unit=j,grave=True),dict(op='registry_set',key='grave-'+str(j),target=j)])
        return case,ops
    def plant(ops,cell=(8,5),kind='墓碑吞噬者',fields=None):
        i=sum(op['op']=='plant_original' for op in ops)
        ops.extend([dict(op='plant_original',cell=list(cell),name=kind,facing=1.),
                    dict(op='plant_fields',plant=i,fields=fields or {},erase=['睡觉']),
                    dict(op='plant_write',plant=i,values={'_pvp_id':'buster-'+str(i)})])
        return i
    for i in range(96):
        case,ops=setup(i)
        plant(ops,fields={'滚蛋':(0.,99.,998.,999.)[i%4]})
        plant(ops)
        x=(264.,-696.,1224.,239.999999,240.,287.999999,288.,264.)[i//4%8]
        y=(432.,432.001,431.999)[i//32]
        ops.append(dict(op='plant_unit',unit=0,fields={'位置':[x,y,0.,0.]}))
        ops.extend([dict(op='binding_attach',plant=0,target='grave-0',catch=True),
                    dict(op='binding_attach',plant=0,target='grave-0',catch=True),
                    dict(op='binding_attach',plant=1,target='grave-0',catch=True),
                    dict(op='binding_draw_target',index=0),dict(op='binding_region'),dict(op='binding_region'),
                    dict(op='binding_before'),dict(op='binding_close'),dict(op='binding_close')])
        output.append(('grave-binding-cell-identity-and-native-completion-'+str(i),case))
    for i in range(96):
        case,ops=setup(200+i)
        plant(ops,fields={'滚蛋':999.})
        ops.append(dict(op='binding_attach',plant=0,target='grave-0'))
        change=[dict(op='registry_erase',key='grave-0'),dict(op='registry_set',key='grave-0',target=1),
                dict(op='plant_unit',unit=0,fields={'血量':0.}),dict(op='native_write_unit',unit=0,values={'死':0.}),
                dict(op='plant_unit',unit=0,fields={'_pvp_owner':'plant'}),dict(op='plant_unit',unit=0,fields={'魅惑':None}),
                dict(op='plant_unit',unit=0,fields={'位置':[312.,432.,0.,0.]}),dict(op='plant_roster_replace',plants=[]),
                dict(op='plant_fields',plant=0,fields={'植物血':0.}),dict(op='plant_fields',plant=0,fields={'死':0.}),
                dict(op='plant_unit',unit=0,fields={'灰烬':0.}),dict(op='plant_unit',unit=0,fields={'_pvp_owner':None})][i%12]
        if i//12%2:
            ops.append(dict(op='lifecycle_hook',name='plant_gate',body=[change]))
        else:ops.append(change)
        ops.extend([dict(op='binding_region',catch=True),dict(op='binding_before'),dict(op='binding_draw_target',index=0),
                    dict(op='binding_region',catch=True),dict(op='plant_roster_replace',plants=[]),dict(op='binding_before')])
        output.append(('grave-binding-cancellation-and-same-loop-invalidity-'+str(i),case))
    for i in range(48):
        case,ops=setup(400+i)
        plant(ops,fields={'滚蛋':1000.})
        ops.append(dict(op='binding_attach',plant=0,target='grave-0'))
        body=[dict(op='plant_unit',unit=0,fields={'血量':0.}),
              dict(op='binding_coin',kind=('银币','金币')[i%2],point=[264.+(1. if i%3==0 else 0.),408.,0.,-1.]),
              dict(op='binding_destroy',index=0,cell=[8,5]),dict(op='binding_destroy',index=0,cell=[8,5])]
        if i//6%2:body.insert(1,dict(op='binding_before'))
        nested=dict(op='binding_scope',body=body)
        ops.append(dict(op='binding_scope',body=[nested]) if i//12%2 else nested)
        ops.extend([dict(op='binding_destroy',index=0,cell=[8,5]),dict(op='binding_close'),
                    dict(op='binding_attach',plant=0,target='grave-0',catch=True),dict(op='binding_scope',body=[],catch=True)])
        output.append(('grave-binding-nested-scope-and-reward-suppression-'+str(i),case))
    for i in range(32):
        case,ops=setup(500+i)
        plant(ops,fields={'滚蛋':999.})
        ops.append(dict(op='binding_attach',plant=0,target='grave-0'))
        ops.append(dict(op='lifecycle_hook',name='grave_consume',fail_before=i%2==0,fail_after=i%2==1,
                        body=[dict(op='registry_erase',key='grave-0')]))
        ops.extend([dict(op='binding_region',catch=True),dict(op='binding_before'),dict(op='binding_region'),dict(op='binding_close')])
        output.append(('grave-binding-consume-callback-unwind-'+str(i),case))
    for i in range(24):
        case,ops=setup(600+i)
        plant(ops,kind=('豌豆射手','墓碑吞噬者')[i%2],fields={'植物血':(0.,100.)[i//2%2]})
        for target in (None,1,{},[],True,'missing','grave-0'):
            ops.append(dict(op='binding_attach',plant=0,target=target,catch=True))
        ops.extend([dict(op='binding_before'),dict(op='binding_close')])
        output.append(('grave-binding-admission-validation-'+str(i),case))
    return output


def paths():
    return plants.paths()+[Path(__file__).resolve(),Path(plants.__file__),BRIDGE,shared.ROOT/'tools/typed72/grave_binding_probe.cpp']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,GraveBindingExtension,'typed72-grave-binding',probe_timeout=600))
