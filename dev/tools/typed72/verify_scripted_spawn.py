"""Scripted admission, retained summon requests and installed native guards."""
import contextlib
import copy
import sys
import types
from collections import OrderedDict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent if Path(__file__).parent.name=='drafts' else Path(__file__).resolve().parent))
import verify_zombie_actions as actions
shared=actions.shared
shooting=actions.shooting
hero=actions.hero
SOURCE=shared.PVP/'scripted_spawn_budget.py'
FIELDS=('_pvp_id','_pvp_owner','_pvp_seat','_pvp_wave_index','_pvp_content','魅惑')


def reference():
    ref=actions.reference()
    env=dict(__package__=shared.PACKAGE,OrderedDict=OrderedDict,DEFAULT_LIMIT=40,MAX_LIMIT=200,MAX_PENDING=3200)
    shooting.projectiles.functions(SOURCE,['live_enemy','source_snapshot'],env)
    hero.selected_class(SOURCE,['__init__','limit','count','available','can_spawn','pending_count','pending_for_source',
        'defer','drain','inherit','install_native_guards','_source','_hold_dance','_defer_dancer','_hold_sled','_hold_giant'],
        'ScriptedSpawnBudget',env)
    ref['scripted_budget']=env
    return ref


class ScriptedSpawnExtension(actions.ActionExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        self.budget_env=ref['scripted_budget'];self.budget=None;self.budget_events=[];self.budget_calls=[]
        self.budget_origins=[];self.budget_spawn_mode='ok';self.budget_spawned=0
        b=self.b;g=self.g;b._ban_free_spawn_count=0
        original=b._emit
        def emit(name,**payload):
            if name=='scripted_summon_deferred':
                self.budget_events.append([name,payload]);self.before('budget_event');self.after('budget_event')
            else:original(name,**payload)
        b._emit=emit
        @contextlib.contextmanager
        def exemption():
            b._ban_free_spawn_count+=1
            try:yield
            finally:b._ban_free_spawn_count-=1
        b._ban_free_spawn=exemption
        def spawn(card,owner,x,y,direction,free,parent):
            assert (card,owner,free)==('zombie:伴舞僵尸','zombie',True)
            self.budget_calls.append([x,y,direction,copy.deepcopy(parent),b._ban_free_spawn_count,
                self.c.active['owner'] if self.c.active else None,self.c.active['phase'] if self.c.active else None])
            if self.budget_spawn_mode=='none':return None
            if self.budget_spawn_mode=='throw_before':raise RuntimeError('spawn fixture before')
            g['新增僵尸']('伴舞僵尸',[x,y,0.,0.],direction)
            unit=g['僵尸'][-1];self.budget_spawned+=1;uid='dancer:'+str(self.budget_spawned)
            unit['_pvp_id']=uid;b._native_objects[uid]=unit
            if self.budget_spawn_mode=='throw_after':raise RuntimeError('spawn fixture after')
            return {'id':uid}
        b.spawn=spawn

    def operation(self,op):
        name=op['op'];b=self.b;g=self.g;r=self.budget
        if name=='budget_setup':
            b.mode=op['mode'];b._ban_free_spawn_count=op.get('exempt',0)
            b.rules={};b.director=types.SimpleNamespace();b.targets=self.c;b._native_objects={}
            self.budget=self.budget_env['ScriptedSpawnBudget'](b);self.budget.install_native_guards()
        elif name=='budget_limits':
            if op.get('clear_director') and hasattr(b.director,'max_zombies'):del b.director.max_zombies
            if op.get('clear_rule'):b.rules.pop('pve_max_zombies',None)
            if 'director' in op:b.director.max_zombies=op['director']
            if 'rule' in op:b.rules['pve_max_zombies']=op['rule']
        elif name=='budget_fields':
            unit=self.units[op['unit']];unit.update(copy.deepcopy(op['fields']))
            if op.get('erase_wave'):unit.pop('_pvp_wave_index',None)
            if op.get('erase_seat'):unit.pop('_pvp_seat',None)
        elif name=='budget_can':return r.can_spawn(op.get('count',1),self.units[op['unit']] if 'unit' in op else None)
        elif name=='budget_pending':return r.pending_count(op.get('wave'))
        elif name=='budget_for_source':return r.pending_for_source(self.units[op['unit']],op.get('kind'))
        elif name=='budget_clear':r.pending.clear()
        elif name=='budget_spawn_mode':self.budget_spawn_mode=op['mode']
        elif name=='budget_snapshot':self.budget_origins.append(self.budget_env['source_snapshot'](self.units[op['unit']]))
        elif name=='budget_inherit':
            parent=self.budget_origins[op['origin']] if 'origin' in op else self.units[op['parent']] if 'parent' in op else None
            r.inherit(self.units[op['unit']],parent)
        elif name in ('budget_defer','budget_drain','budget_native_dancer','budget_hold'):
            try:
                if name=='budget_drain':r.drain()
                elif name=='budget_hold':return r._hold_dance() if op.get('dance') else r._hold_sled()
                elif name=='budget_native_dancer':
                    g['zx']=op['point'][0]/b.tile-.5;g['zy']=op['point'][1]/b.tile-.9;g['lzx']=op['slot']
                    source=r._source()
                    if source is not None:source['方向']=op['facing']
                    return r._defer_dancer()
                else:
                    callback=copy.deepcopy(op['callback'])
                    def create():
                        if 'body' in callback:self.operations(callback['body'],False)
                        if callback.get('throw'):raise RuntimeError('deferred callback fixture')
                        return callback.get('result',True)
                    return r.defer(self.units[op['unit']],op['kind'],op['slot'],create)
            except Exception:
                if not op.get('catch'):raise
                return {'caught':True}
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if self.budget is None:return
        r=self.budget
        row['budget']=dict(enabled=r.enabled,draining=r.draining,limit=r.limit,count=r.count(),available=r.available(),
            admitted=r.admitted,deferred=r.deferred,peak=r.peak_pending,pending=[[list(key),item['wave']] for key,item in r.pending.items()],
            units=[{key:unit[key] for key in FIELDS if key in unit} for unit in self.units],
            origins=self.budget_origins,events=self.budget_events,calls=self.budget_calls,exempt=self.b._ban_free_spawn_count)


def cases():
    native=actions.cases();prototype=native[0][1];output=[]
    def setup(i):
        case=copy.deepcopy(prototype);case['seed']=1031000+i
        ops=case['operations']=case['operations'][:-1]
        ops[2]['values'].update(血量=100.,手持='',防具='')
        for key in ('灰烬','魅惑','冰冻','狂暴','眩晕'):ops[2]['values'].pop(key,None)
        ops.append(dict(op='budget_setup',mode=('duel','duo','pve','coop')[i%4],exempt=i%3))
        return case,ops
    def request(unit=0,kind='test',slot=0,callback=None,**extra):
        return dict(op='budget_defer',unit=unit,kind=kind,slot=slot,callback=callback or {'result':True},**extra)
    for i in range(64):
        case,ops=setup(i)
        ops.extend([dict(op='budget_limits',rule=(-1,0,1,4,40,200,201,None)[i//8]),
                    dict(op='budget_limits',director=(1,3,None,200)[i//4%4]),
                    dict(op='roster_replace',targets=([0],[0,0,1],[0,1,2,3],[])[i%4])])
        if i%8<4:ops.append(dict(op='budget_fields',unit=0,fields={('_pvp_grave','_pvp_orphan_barrel')[i%2]:True}))
        if i%8 in (4,5):ops.append(dict(op='motion_unit',unit=0,values={('灰烬','魅惑')[i%2]:0.}))
        if i%8==6:ops.append(dict(op='motion_unit',unit=0,values={'血量':0.}))
        for count in (-1,0,1,4,200,201):ops.append(dict(op='budget_can',count=count,unit=0))
        ops.extend([dict(op='budget_can'),dict(op='budget_limits',clear_director=True),dict(op='budget_can')])
        output.append(('scripted-live-admission-and-limit-'+str(i),case))
    for i in range(16):
        case,ops=setup(80+i)
        ops.extend([dict(op='budget_limits',director=1),dict(op='roster_replace',targets=[0,0,1]),
                    dict(op='motion_unit',unit=0,values={'魅惑':(None,0.,1.,-1.)[i//4]}),
                    dict(op='budget_can',count=201,unit=0),dict(op='budget_can',count=201),
                    dict(op='budget_can',unit=0),dict(op='budget_can',unit=1)])
        output.append(('scripted-live-charmed-source-exemption-'+str(i),case))
    for i in range(96):
        case,ops=setup(100+i)
        ops.append(dict(op='budget_fields',unit=0,fields={'_pvp_wave_index':(None,0,1,7)[i%4]}))
        ops.append(dict(op='source_write',unit_source=0,values={'_pvp_id':(None,'','producer','producer2')[i//4%4]}))
        callback={'result':i%5!=0}
        if i%5==1:callback.update(throw=True)
        if i%5==2:callback['body']=[dict(op='budget_drain')]
        if i%5==3:callback['body']=[request(kind='nested')]
        if i%5==4:callback['body']=[dict(op='budget_clear')]
        ops.extend([request(callback=callback),request(),request(slot=1),dict(op='budget_pending'),
                    dict(op='budget_pending',wave=1),dict(op='budget_for_source',unit=0),dict(op='budget_for_source',unit=0,kind='other'),
                    dict(op='budget_limits',director=200),dict(op='budget_drain',catch=True),dict(op='budget_clear'),dict(op='budget_drain')])
        output.append(('scripted-retained-requests-reentrancy-and-unwind-'+str(i),case))
    for i in range(32):
        case,ops=setup(300+i)
        ops.extend([dict(op='budget_fields',unit=0,fields={'_pvp_wave_index':(None,0,1,19)[i%4],
            '_pvp_seat':('plant2','zombie2')[i%2],'_pvp_barrel_position':[1.,2.,3.,4.]}),dict(op='budget_snapshot',unit=0),
            dict(op='motion_unit',unit=0,values={'位置':[960.,80.,3.,9.]}),
            dict(op='budget_fields',unit=0,fields={'_pvp_wave_index':77},erase_seat=True),
            dict(op='budget_inherit',unit=1,origin=0),dict(op='budget_inherit',unit=2,parent=0),dict(op='budget_inherit',unit=3)])
        output.append(('scripted-provenance-copy-and-inherit-'+str(i),case))
    for i in range(48):
        case,ops=setup(400+i)
        ops[-1]['mode']='coop'
        ops.extend([dict(op='budget_limits',director=1),dict(op='budget_fields',unit=0,fields={'_pvp_wave_index':i%4,'_pvp_seat':'zombie2'}),
                    dict(op='source_write',unit_source=0,values={'_pvp_id':None if i%2 else 'king'}),
                    dict(op='budget_spawn_mode',mode=('ok','none','throw_before','throw_after')[i//4%4]),
                    dict(op='context',target='plant',owner='zombie',phase='zombies',unit_source=0,body=[
                        dict(op='budget_hold',dance=True),dict(op='budget_native_dancer',point=[264.,427.2],facing=-1.,slot=i%4),
                        dict(op='budget_hold',dance=True)]),
                    dict(op='budget_fields',unit=0,fields={},erase_wave=True,erase_seat=True),
                    dict(op='source_write',unit_source=0,values={'_pvp_id':'mutated'}),
                    dict(op='budget_limits',director=200),dict(op='budget_drain',catch=True),
                    dict(op='budget_spawn_mode',mode='ok'),dict(op='budget_drain',catch=True)])
        output.append(('scripted-deferred-dancer-provenance-and-scopes-'+str(i),case))
    selected=[case for label,case in native if label.startswith(('dance-summon-order-','vehicles-armor-and-ammo-','giant-hammer-wake-and-imp-'))]
    for i,original in enumerate(selected):
        case=copy.deepcopy(original);case['seed']=1032000+i;ops=case['operations']
        ops[-1:-1]=[dict(op='budget_setup',mode=('coop','pve','duel','duo')[i%4]),dict(op='budget_limits',director=(1,2,3,4,200)[i%5])]
        ops.extend([dict(op='budget_limits',director=200),dict(op='budget_drain')])
        output.append(('scripted-installed-native-summon-guards-'+str(i),case))
    for i in range(4):
        case,ops=setup(700+i)
        ops.append(dict(op='batch',body=[request(slot=slot) for slot in range(3200)]))
        ops.extend([request(slot=0),request(slot=3200,catch=True),dict(op='budget_clear'),request(slot=3200),dict(op='budget_drain')])
        output.append(('scripted-hard-ceiling-and-recovery-'+str(i),case))
    for i in range(32):
        case,ops=setup(800+i)
        ops.extend([dict(op='budget_limits',director=200),
                    request(slot=0.),request(slot=.2),request(slot=.4),request(slot=1),request(slot=1.),
                    request(slot=-.2),request(slot=.2 if i%2 else .20000000000000004),
                    dict(op='budget_pending'),dict(op='budget_drain'),dict(op='budget_pending')])
        output.append(('scripted-fractional-child-offsets-and-numeric-key-equality-'+str(i),case))
    return output


def paths():
    return [Path(__file__).resolve(),Path(actions.__file__),Path(actions.motion.__file__),Path(actions.phase.__file__),Path(shared.__file__),
        SOURCE,shared.ROOT/'tools/typed72/scripted_spawn_probe.cpp',shared.ROOT/'tools/typed72/world_rules_probe.cpp',
        shared.ROOT/'tools/typed72/zombie_motion_fixture.inc',actions.motion.RAW,actions.motion.BITES,actions.motion.BLACK,
        actions.motion.CACTUS,actions.MINER,shared.BATTLE,actions.motion.CONTENT,shared.SEPTEMBER,shared.PLANT_ZOMBIES,
        actions.phase.PERIODIC,actions.phase.EXPANSION,shared.ROOT/'extract/live/zombie_coordinates.marshal',
        shared.ROOT/'extract/live/zombie_body_index.marshal']


if __name__=='__main__':
    sys.exit(shooting.main(paths(),reference,cases,ScriptedSpawnExtension,'typed72-scripted-spawn',probe_timeout=600))
