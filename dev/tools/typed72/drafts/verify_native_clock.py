"""Deferred constructors observe the preceding published attack tick."""
import copy
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_tick_clock_reference',HERE/'verify_native_tick.py')
driver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
shooting=driver.shooting


class NativeClockExtension(driver.NativeTickExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.clock_seen=False;self.clock_events=[]

    def operation(self,op):
        name=op['op']
        if name=='clock_setup':
            self.clock_seen=True;self.b.engine.native_tick=op['engine'];self.g['_pvp_native_tick']=op['published']
            self.budget.enabled=True
        elif name=='clock_defer':
            unit=self.units[op['unit']];behavior=op['behavior'];attempts=[0]
            def create():
                with self.b.targets.context('plant','zombie','summon',unit):
                    key,tick=self.b.targets._attack_key('plant','ash')
                    amount=self.b.targets.damage_hero('plant',10.,'ash')
                    self.clock_events.append([self.b.engine.native_tick,tick,key[2],amount])
                    attempts[0]+=1
                    if attempts[0]==1 and behavior=='throw_once':raise RuntimeError('clock constructor retry')
                    return attempts[0]!=1 or behavior!='false_once'
            return self.budget.defer(unit,'clock_probe',op['slot'],create)
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.clock_seen:row['clock_bridge']=dict(events=self.clock_events,pending=self.budget.pending_count(),draining=self.budget.draining)


def paths():
    return driver.paths()+[Path(__file__).resolve(),driver.shared.ROOT/'tools/typed72/native_clock_probe.cpp']


def cases():
    result=[];baselines=driver.cases()[:16]
    for index in range(64):
        case=copy.deepcopy(baselines[index%16][1]);case['seed']=1300000+index
        ops=case['operations']=case['operations'][:-4]
        engine=(0,249,250,2500)[index//4%4]
        ops += [dict(op='roster_replace',targets=[]),dict(op='clock_setup',engine=engine,published=engine-index%3),
                dict(op='clock_defer',unit=0,slot=0.,behavior=('true','false_once','throw_once','true')[index%4])]
        if index%4==3:ops.append(dict(op='clock_defer',unit=0,slot=1.,behavior='true'))
        for tick in range(3):ops.append(dict(op='native_tick',draw=False,catch=True))
        result.append(('native-clock-deferred-constructor-'+str(index),case))
    return result


if __name__=='__main__':
    raise SystemExit(shooting.main(paths(),driver.reference,cases,NativeClockExtension,'typed72-native-clock-bridge'))
