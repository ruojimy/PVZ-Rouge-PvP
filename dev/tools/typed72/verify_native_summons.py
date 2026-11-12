"""Generic content summons, fractional death slots and live versus deferred producers."""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_content_zombies64 as zombies
shared=zombies.shared
shooting=zombies.shooting
hero=zombies.hero
SOURCE=shared.LOCAL/'native_content.py'


def reference():
    ref=zombies.reference();env=dict(__package__=shared.PACKAGE)
    hero.selected_class(SOURCE,['summon'],'Summons',env)
    ref['native_summons']=env
    return ref


class NativeSummonsExtension(zombies.ContentZombie64Extension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.summons=ref['native_summons']['Summons']();self.summons.b=self.b;self.summons.g=self.g
        self.b.g=self.g;self.summon_events=[];self.summon_seen=False
        original=self.b._emit
        def emit(name,**payload):
            if name=='content_summon':
                self.summon_events.append([name,payload]);self.before('content_summon_event');self.after('content_summon_event')
            else:original(name,**payload)
        self.b._emit=emit

    def operation(self,op):
        name=op['op']
        if name=='content_summon_setup':self.summon_seen=True
        elif name=='content_summon_fields':self.units[op['unit']].update(copy.deepcopy(op['fields']))
        elif name=='content_summon_clear':self.budget.pending.clear()
        elif name=='content_summon':
            try:return self.summons.summon(self.units[op['unit']],op['name'],op.get('thrown',False),op.get('offset',0.),op.get('defer',True))
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.summon_seen:row['native_summons']=dict(events=self.summon_events,
            units=[{key:unit[key] for key in ('旋转','_pvp_barrel_position') if key in unit} for unit in self.units])


def paths():
    return zombies.paths()+[Path(__file__).resolve(),Path(zombies.__file__),SOURCE,shared.ROOT/'tools/typed72/native_summons_probe.cpp']


def cases():
    result=[];prototype=zombies.cases()[0][1]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1081000+i
        ops=case['operations']=case['operations'][:-3]
        mode=('duel','duo','pve','coop')[i%4];ops[0]['mode']=mode
        next(op for op in ops if op['op']=='zombie64_setup')['mode']=mode
        ops.append(dict(op='content_summon_setup'))
        return case,ops
    def summon(**fields):
        op=dict(op='content_summon',unit=0,name='小鬼僵尸');op.update(fields);return op
    for i in range(64):
        case,ops=setup(i)
        ops.append(dict(op='content_summon_fields',unit=0,fields={'方向':(-1.,0.,1.,-1.)[i//4%4],
            '_pvp_content':('滚桶僵尸','海盗船长','小鬼炮','普通僵尸')[i//16],
            '_pvp_barrel_position':[950.,400.,2.,3.],'_pvp_seat':'zombie2','_pvp_wave_index':7}))
        if i%5==0:ops.append(dict(op='content_summon_fields',unit=0,fields={'魅惑':0.}))
        ops.extend([summon(thrown=bool(i%2),offset=(-.2,0.,.2,1.)[i//4%4]),
                    summon(name='海盗鹦鹉',thrown=True,offset=.2)])
        result.append(('native-summon-immediate-origin-charm-and-barrel-launch-'+str(i),case))
    for i in range(64):
        case,ops=setup(100+i)
        ops.extend([dict(op='zombie64_limit',value=1),dict(op='content_summon_fields',unit=0,
            fields={'_pvp_id':None if i%5==0 else 'producer','_pvp_content':'滚桶僵尸',
                    '_pvp_barrel_position':[950.,400.,2.,3.],'_pvp_wave_index':7,'_pvp_seat':'zombie2'}),
            summon(thrown=True,offset=0.),summon(thrown=True,offset=.2),summon(thrown=True,offset=.2),
            summon(name='海盗鹦鹉',defer=False),
            dict(op='content_summon_fields',unit=0,fields={'位置':[100.,200.,0.,0.],'方向':-1.,
                '_pvp_barrel_position':[100.,250.,0.,0.],'_pvp_wave_index':19,'_pvp_seat':'plant2','魅惑':0.}),
            dict(op='zombie64_spawn_mode',value=('ok','none','throw_before','throw_after')[i//4%4]),
            dict(op='zombie64_limit',value=200),dict(op='zombie64_drain',catch=True),
            dict(op='zombie64_spawn_mode',value='ok'),dict(op='zombie64_drain',catch=True)])
        result.append(('native-summon-deferred-fractional-slots-and-frozen-source-'+str(i),case))
    for i in range(48):
        case,ops=setup(200+i)
        ops.extend([dict(op='content_summon_fields',unit=0,fields={'_pvp_content':'滚桶僵尸','_pvp_barrel_position':[950.,400.,2.,3.]}),
            dict(op='lifecycle_hook',name=('zombie64_spawn','content_summon_event')[i%2],fail_before=i//2%4==0,fail_after=i//2%4==1,
                body=[dict(op='content_summon_fields',unit=0,fields={'方向':-1.,'位置':[100.,200.,0.,0.],
                    '_pvp_content':('普通僵尸','滚桶僵尸')[i//8%2],'_pvp_barrel_position':[120.,220.,0.,0.],
                    '_pvp_owner':'plant','_pvp_id':'callback-id'})]),
            summon(thrown=True,offset=.2,catch=True)])
        result.append(('native-summon-live-source-constructor-mutation-and-scopes-'+str(i),case))
    return result


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,NativeSummonsExtension,'typed72-native-summons',probe_timeout=600))
