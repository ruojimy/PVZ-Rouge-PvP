"""Original poison clocks installed at the native driver's status boundary."""
import copy
import importlib.util
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_tick_status_reference',HERE/'verify_native_tick.py')
driver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
shared=driver.shared
shooting=driver.shooting
hero=driver.hero
SOURCE=shared.PVP/'native_status.py'


def reference():
    ref=driver.reference()
    env={'COLORS':hero.constant(SOURCE,'COLORS')}
    hero.selected_class(SOURCE,['layers','summarize','apply','tick'],'Status',env)
    ref['native_status']=env
    return ref


class NativeStatusExtension(driver.NativeTickExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.poison=ref['native_status']['Status']();self.poison.b=self.b
        self.poison_seen=False;self.poison_events=[]
        self.b.g=self.g
        def tick():
            self.record('status');self.poison.tick()
        self.b.status=types.SimpleNamespace(tick=tick,apply=self.poison.apply)
        emit=self.b._emit
        def event(name,**fields):
            if name=='poison_damage':
                self.poison_events.append(['damage',fields.get('entity'),fields['amount'],fields['level']])
                self.before('poison_damage');self.after('poison_damage')
            else:emit(name,**fields)
        self.b._emit=event
        def body(name,unit):
            self.poison_events.append([name,self.label(unit)])
            self.before('poison_'+name);self.after('poison_'+name)
        self.b.content.break_barrel=lambda unit:body('break',unit)
        self.b.content.barrels.detach=lambda unit:body('detach',unit)

    def operation(self,op):
        name=op['op']
        if name=='poison_setup':self.poison_seen=True
        elif name=='poison_apply':
            target=self.b.targets.hero_proxy(op['side']) if 'side' in op else self.units[op['unit']]
            self.poison.apply(target,op['level'],op.get('duration',4.),op.get('owner','plant'))
        elif name=='poison_fields':
            target=self.b.avatars[op['side']] if 'side' in op else self.units[op['unit']]
            if op.get('erase'):target.pop('_pvp_poison',None)
            else:
                state=copy.deepcopy(op['state'])
                if state is not None and state.get('layers') is not None:state['layers']=dict(state['layers'])
                target['_pvp_poison']=state
        elif name=='poison_tick':
            self.b.engine.native_tick=op['tick'];self.poison.tick()
        elif name=='poison_clock':self.b.engine.native_tick=op['tick']
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.poison_seen:return
        def state(obj):
            if '_pvp_poison' not in obj:return {'present':False}
            value=copy.deepcopy(obj['_pvp_poison'])
            if value is not None and value.get('layers') is not None:value['layers']=[[k,v] for k,v in value['layers'].items()]
            return value
        units=[]
        for unit in self.units:
            item={'poison':state(unit)}
            for key in ('_pvp_poison_killed','_pvp_armor_triggered','_pvp_imp_armor','_pvp_imp_armor_hp'):
                if key in unit:item[key]=unit[key]
            units.append(item)
        row['poison']=dict(units=units,heroes={seat:state(avatar) for seat,avatar in self.b.avatars.items()},events=self.poison_events)
        # JSON object keys are strings. The explicit poison channel above
        # retains numeric layer identities and their original insertion order.
        for avatar in row['heroes'].values():
            poison=avatar.get('_pvp_poison')
            if poison and isinstance(poison.get('layers'),dict):
                poison['layers']={str(level):layer for level,layer in poison['layers'].items()}


def paths():
    return driver.paths()+[Path(__file__).resolve(),SOURCE,shared.ROOT/'tools/typed72/native_status_probe.cpp']


def cases():
    baselines=driver.cases()[:16]
    result=[]
    def setup(index):
        case=copy.deepcopy(baselines[index%16][1]);case['seed']=1200000+index
        ops=case['operations']=case['operations'][:-4]
        ops.append(dict(op='poison_setup'))
        return case,ops
    for i in range(96):
        case,ops=setup(i)
        ops += [dict(op='tick_unit',unit=0,fields={'血量':(3.,8.,20.,100.)[i%4],'防具':'铁桶','防具血量':50.,
                    '手持':'钢门','手持血量':80.,'_pvp_orphan_barrel':i%3==0,'_pvp_owner':'zombie','_pvp_id':'poison-target'}),
                dict(op='roster_replace',targets=[0,0] if i%7==0 else [0]),dict(op='poison_clock',tick=0)]
        first=(1,2)[i%2];second=3-first
        ops += [dict(op='poison_apply',unit=0,level=first,duration=(1.,1.998,2.,4.)[i//2%4]),
                dict(op='poison_clock',tick=(0,100,249,250)[i//8%4]),
                dict(op='poison_apply',unit=0,level=second,duration=(.1,1.,2.,4.)[i//4%4])]
        if i%3==0:ops.append(dict(op='poison_apply',unit=0,level=first,duration=3.))
        if i%8==4:ops.append(dict(op='tick_unit',unit=0,fields={'魅惑':0.}))
        for tick in (249,250,251,500,750,1000):ops.append(dict(op='poison_tick',tick=tick))
        result.append(('poison-independent-clocks-and-death-'+str(i),case))
    for i in range(48):
        case,ops=setup(100+i)
        level=(1,2)[i%2]
        state=dict(level=level,until=(250.,500.,1000.)[i%3],next=250.,owner=('plant','zombie')[i//2%2])
        if i%3==1:state['layers']=None
        elif i%3==2:state['layers']=[[level,dict(until=500.,next=250.,owner='plant')],
                                    [3-level,dict(until=750.,next=500.,owner='plant')]]
        ops += [dict(op='tick_unit',unit=0,fields={'血量':100.,'_pvp_owner':'zombie'}),
                dict(op='roster_replace',targets=[0]),dict(op='poison_fields',unit=0,state=state),
                dict(op='poison_tick',tick=500),dict(op='poison_clock',tick=500),
                dict(op='poison_apply',unit=0,level=level,duration=1.),dict(op='poison_tick',tick=750),
                dict(op='poison_tick',tick=1000)]
        result.append(('poison-legacy-normalization-and-expiry-'+str(i),case))
    for i in range(32):
        case,ops=setup(200+i)
        present=next(op['present'] for op in ops if op['op']=='native_tick_setup')
        ops += [dict(op='roster_replace',targets=[]),dict(op='poison_clock',tick=0)]
        for seat in present:
            owner='zombie' if seat.startswith('plant') else 'plant'
            ops += [dict(op='poison_apply',side=seat,level=1,duration=4.,owner=owner),
                    dict(op='poison_apply',side=seat,level=2,duration=2.,owner=owner)]
        for tick in (250,500,750,1000):ops.append(dict(op='poison_tick',tick=tick))
        result.append(('poison-hero-routing-'+str(i),case))
    for i in range(16):
        case,ops=setup(300+i)
        ops += [dict(op='tick_unit',unit=0,fields={'血量':100.,'_pvp_grave':True,'_pvp_owner':'zombie'}),
                dict(op='roster_replace',targets=[0]),dict(op='poison_clock',tick=248),
                dict(op='poison_fields',unit=0,state=dict(level=2,until=500.,next=250.,owner='plant'))]
        for tick in range(6):ops.append(dict(op='native_tick',draw=tick%2==0))
        result.append(('poison-continuous-native-driver-'+str(i),case))
    return result


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),reference,cases,NativeStatusExtension,'typed72-native-status-driver'))
