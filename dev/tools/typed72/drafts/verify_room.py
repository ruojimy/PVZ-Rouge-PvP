"""Real PvP72 room/input methods over the typed native-driver fixture.

Outer public registration, director and resolved-card boundaries are observed
fixtures. This is component/composition evidence, not production acceptance.
"""
import ast
import copy
import math
import sys
import types
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(1,str(HERE.parent if HERE.name=='drafts' else HERE))
import verify_native_tick as native
import verify_hero_recovery as recovery
shared=native.shared;hero=native.hero;shooting=native.shooting
SIM=shared.LOCAL/'simulation.py'

def reference():
    ref=native.reference();ref.update({k:v for k,v in recovery.reference().items() if k not in ref})
    env=dict(ref['native_tick']);env.update(ref['recovery']);env.update(math=math,deepcopy=copy.deepcopy,copy=copy)
    env.update(DUEL='duel',DUO='duo',GIFT_MAX=100,GIFT_COOLDOWN=12.,AI_SUBSIDY_INTERVAL=8.,AI_SUBSIDY_SUN=25,
               AI_SUBSIDY_DOUBLING=40.,AI_SUBSIDY_MAX=200,REVIVE_SECONDS=4.,REVIVE_HP_FRACTION=.5,
               TOUCH_RANGE_X=.9,TOUCH_RANGE_Y=1.6,NATIVE_COST_SMOOTHING=.08,NATIVE_RISE_FRAMES=2000)
    shooting.projectiles.functions(SIM,['finite','wrap_delta'],env)
    shooting.projectiles.functions(shared.LOCAL/'balance.py',['deathmatch_factor'],env)
    shooting.projectiles.functions(shared.BATTLE,['ai_subsidy_amount'],env)
    base_names=['command_input','_command_input','clear_input','command_for','command_seat','rally_for','set_rally','distance']
    hero.selected_class(SIM,base_names,'RoomBase',env)
    names=['_command_input','clear_input','step','_ai_subsidy','_team_step','_touching','_revive','_block_pending_producer_transforms']
    tree=ast.parse(shared.BATTLE.read_text(encoding='utf8'))
    nodes=[n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name in names]
    cls=ast.ClassDef(name='RoomNative',bases=[ast.Name(id='RoomBase',ctx=ast.Load())],keywords=[],body=nodes,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(shared.BATTLE),'exec'),env)
    ref['room']=env
    return ref

class RoomExtension(native.NativeTickExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref)
        b=self.b;env=self.room_ref=ref['room'];self.room_seen=False
        self.room_events=[];self.boundary_events=[];self.input_events=[];self.measured=0.;self.cooldowns={};self.cleared=False;self.sight_clear=True
        self.adapter=env['RoomNative']();self.adapter.__dict__=b.__dict__
        for name in ('command_input','_command_input','clear_input','command_for','rally_for','set_rally','distance','step','_ai_subsidy','_team_step','_touching','_revive','_block_pending_producer_transforms'):
            setattr(b,name,types.MethodType(getattr(env['RoomNative'],name),self.adapter))
        b.command_seat=env['RoomNative'].command_seat
        for name,fn in ref['recovery']['battle'].__dict__.items():
            if callable(fn):setattr(b,name,types.MethodType(fn,b))
        def clock():
            value=self.measured;self.measured+=.001;return value
        env['_perf_counter']=clock
        original_emit=b._emit
        room_names={'deathmatch','ai_subsidy','hero_fallen','hero_helped','hero_revived','spawn_blocked','rally','command','gift','surrender_requested','surrender_vote','result'}
        def emit(event,**fields):
            if event in room_names:self.room_events.append(dict(event=event,data=copy.deepcopy(fields)) if event=='result' else dict(event=event,**copy.deepcopy(fields)))
            else:original_emit(event,**fields)
        b._emit=emit
        b.log=types.SimpleNamespace(append=lambda value:self.input_events.append(['accepted',value['tick'],value['time'],value['side']]))
        b.line_of_sight=lambda a,t:self.sight_clear
        for i,name in enumerate(('turn_plant','detonate_clown','select_grave','wake_grave','teleport_hero','deploy','native_cannon','cannon_cancel','native_shovel')):
            if name=='cannon_cancel':continue
            setattr(b,name,lambda *a,_i=i,**k:'fixture-native-'+str(7 if _i==6 and len(a)>3 and a[3] else _i))
        parent=self
        class Graphics:
            def __init__(self,previous):self.__dict__.update(previous.__dict__);self._defer=False
            @property
            def defer_capture(self):return self._defer
            @defer_capture.setter
            def defer_capture(self,value):self._defer=value;parent.boundary_events.append(['capture',value])
        b.graphics=Graphics(b.graphics)
        def sync(terrain=True):
            for seat,h in b.hero_states.items():b.players[seat].update(x=h['玩家位置'][0],y=h['玩家位置'][1],hp=h['玩家血量'])
            self.boundary_events.append(['public',terrain])
        b._sync_public=sync
        b._card=lambda seat,key:dict(self.cards.get(key,{}),cooldown=self.cooldowns[key])
        env['resolve_card']=lambda key,*a:self.cards[key] if key in self.cards else (_ for _ in ()).throw(ValueError(key))

    def operation(self,op):
        b=self.b;name=op['op']
        if name=='room_setup':
            self.room_seen=True;b.tick=op.get('tick',0);b.dt=1./op.get('rate',30);b.time=b.tick*b.dt;b.result=None;b.audit_error=''
            b.rules.update(tick_rate=op.get('rate',30),deathmatch_seconds=op.get('deathmatch',180.),production_multiplier=2.,
                           hero_regen_delay=10.,hero_regen_interval=1.,hero_regen_amount=1.,hero_lock_range=360.,mark_seconds=6.)
            b._native_phase=op.get('phase',0);b.native_cost_ratio=None;b.capture_demand=op.get('capture',False);b._capture_intermediate=False
            b.capture_frames=b.capture_deferred=0;b.deathmatch=False;b.fallen_count=0;b.revive={s:0. for s in b.players};b.down_since={}
            b._press_reported={s:False for s in b.players};b.surrender_requests={};b.surrender_serial=0
            b.ai_subsidy_seats=op.get('subsidy',[]);b._ai_subsidy_paid=op.get('paid',0)
            b.director=types.SimpleNamespace(cycle=types.SimpleNamespace(step=lambda:self.boundary_events.append(['cycle'])) if op.get('cycle') else None,
                step=lambda battle:self.boundary_events.append(['director']),cleared=lambda:self.cleared) if op.get('director') else None
            b.zsecrets.enabled=op.get('secrets',False);b.zsecrets.step=lambda elapsed:self.boundary_events.append(['secrets',elapsed])
            for s,h in b.hero_states.items():
                h.update(_pvp_previous_hp=h['玩家血量'],_pvp_last_damage=0.,_pvp_regen_progress=0.)
                b.players[s].update(seq=-1,last_input_tick=b.tick,immune_until=0.,gift_ready_at=0.,cooldowns={},cooldown_spans={},input={'move':0},jump_held=False,grounded=False,h=b.tile*1.9)
                b._jump_presses.setdefault(s,0)
        elif name=='room_input':
            error=b.command_input(op['side'],copy.deepcopy(op['payload']));self.input_events.append(['attempt',b.tick,op['side'],error]);return error
        elif name=='room_clear':b.clear_input(op['side']);self.input_events.append(['clear',b.tick,op['side']])
        elif name=='room_step':b.step(op.get('count',1))
        elif name=='room_player':
            s=op['side'];p=b.players[s];h=b.hero_states[s]
            for key,target in (('seq','seq'),('last','last_input_tick'),('lock','collect_locked_until')):
                if key in op:p[target]=op[key]
            if 'hp' in op:p['hp']=h['玩家血量']=op['hp']
            if 'presses' in op:b._jump_presses[s]=op['presses']
            if 'revive' in op:b.revive[s]=op['revive']
            if 'cooldowns' in op:p['cooldowns']=dict(op['cooldowns'])
            if 'spans' in op:p['cooldown_spans']=dict(op['spans'])
            if 'native' in op:h.update(copy.deepcopy(op['native']))
            if 'position' in op:p['x'],p['y']=op['position'];h['玩家位置'][:2]=op['position']
        elif name=='room_card':self.cooldowns[op['id']]=op['cooldown']
        elif name=='room_state':
            if 'audit' in op:b.audit_error=op['audit']
            if 'cleared' in op:self.cleared=op['cleared']
            if 'sight' in op:self.sight_clear=op['sight']
            if 'intermediate' in op:b._capture_intermediate=op['intermediate']
        else:return super().operation(op)

    def snapshot(self,row):
        super().snapshot(row)
        if not self.room_seen:return
        b=self.b;players={}
        for s,p in b.players.items():players[s]=dict(seq=p['seq'],last=p['last_input_tick'],move=p['input']['move'],held=p['jump_held'],presses=b._jump_presses[s],
            reported=b._press_reported[s],immune=p['immune_until'],gift_ready=p['gift_ready_at'],cooldowns=list(map(list,p['cooldowns'].items())),
            spans=list(map(list,p.get('cooldown_spans',{}).items())),revive=b.revive[s],down=b.down_since.get(s))
        row['room']=dict(tick=b.tick,time=b.time,phase=b._native_phase,deathmatch=b.deathmatch,defer=b.graphics.defer_capture,
            frames=b.capture_frames,deferred=b.capture_deferred,cost=b.native_cost_ratio,result=b.result,players=players,paid=b._ai_subsidy_paid,fallen=b.fallen_count,
            events=self.room_events,boundaries=self.boundary_events,inputs=self.input_events,requests=[b.surrender_requests.get(s) for s in ('plant','zombie')])

def cases():
    bases=native.cases()[:16];out=[]
    def base(i):
        c=copy.deepcopy(bases[i%len(bases)][1]);c['seed']=1140000+i;c['operations']=c['operations'][:-4];ops=c['operations']
        seats=next(op['present'] for op in ops if op['op']=='native_tick_setup')
        ops += [dict(op='resources_setup',accounts={s:[300.,10.] for s in c['players']}),
            dict(op='economy_setup',present=seats,producers=[],height=576.,previous_tick=0,progress=0.,interval=10.,subsidy=False,subsidy_phase=0.,night=False,day_interval=5.,day_amount=15.,sky_amount=25.,lifetime=30.),
            dict(op='room_setup')]
        return c,ops
    invalid=[None,[],{}, {'seq':True},{'seq':-1},{'seq':2**53+1}, {'seq':1,'type':'move','move':True},
        {'seq':1,'type':'move','move':1.0},{'seq':1,'type':'move','move':2},{'seq':1,'type':'move','jump':1}]
    for i in range(32):
        c,ops=base(i)
        for payload in invalid:ops.append(dict(op='room_input',side='plant',payload=copy.deepcopy(payload)))
        for seq,payload in enumerate([dict(type='move',move=1,jump=True),dict(type='move',move=-1,jump=False),dict(type='move',jump=True),dict(type='move',edge=True),dict(type='move',edge=True),dict(type='move',jump=False),dict(type='move',jump=True)],10):
            ops.append(dict(op='room_input',side='plant',payload=dict(payload,seq=seq)))
        ops += [dict(op='room_clear',side='plant'),dict(op='room_input',side='plant',payload=dict(type='move',jump=True,seq=30))]
        out.append(('room-input-order-and-jump-'+str(i),c))
    for i in range(32):
        c,ops=base(100+i)
        for seq,(side,payload) in enumerate([('plant',dict(type='rally',x=0.,y=0.)),('zombie',dict(type='rally',x=-1.,y=10.)),('zombie',dict(type='rally',x=959.9,y=575.9)),('zombie',dict(type='command')),('zombie',dict(type='command')),('zombie2',dict(type='rally',x=11.,y=32.)),('plant',dict(type='gift',amount=True)),('plant',dict(type='gift',amount=101)),('plant',dict(type='gift',amount=50)),('plant',dict(type='gift',amount=50)),('plant',dict(type='mark'))],1):
            ops.append(dict(op='room_input',side=side,payload=dict(payload,seq=seq)))
        out.append(('room-rally-mark-gift-'+str(i),c))
    for i in range(24):
        c,ops=base(200+i)
        for seq,(side,kind,request) in enumerate([('plant','surrender',None),('plant','surrender_accept',1),('plant2','surrender_cancel',1),('plant2','surrender_decline',True),('plant','surrender',None),('plant2','surrender_accept',2),('zombie','move',None)],1):
            ops.append(dict(op='room_input',side=side,payload=dict(type=kind,seq=seq,request=request)))
        out.append(('room-surrender-votes-'+str(i),c))
    for i in range(24):
        c,ops=base(300+i);ops[-1].update(rate=(25,30,50)[i%3],capture=i%2==0,director=i%4>1,cycle=True,secrets=True)
        for j in range(2):ops.append(dict(op='room_step',count=(1,2,3)[i%3]))
        out.append(('room-native-scheduler-'+str(i),c))
    for i in range(12):
        c,ops=base(400+i);rate=(30,60)[i%2];tick=rate*420-1
        ops[-1].update(rate=rate,tick=tick,phase=(tick*250)%rate,deathmatch=420.,capture=True)
        # Set the engine clock before NativeTick setup publishes its clock.
        # The generic clock fixture updates the engine counter only on C++;
        # setting it after setup would compare an impossible split fixture.
        setup_index=next(j for j,op in enumerate(ops) if op['op']=='native_tick_setup')
        ops.insert(setup_index,dict(op='clock',tick=(tick*250)//rate,time=tick/rate))
        for k,cooldown in enumerate((0.,12.,12.001,48.,48.001,80.)):
            ops.append(dict(op='room_card',id='card-'+str(k),cooldown=cooldown))
        for seat in c['players']:
            ops.append(dict(op='room_player',side=seat,cooldowns=[['card-'+str(k),420.+offset] for k,offset in enumerate((-1.,0.,.1,12.,40.,80.))],spans=[['card-'+str(k),60.] for k in range(6)]))
        ops += [dict(op='room_step'),dict(op='room_step')]
        out.append(('room-deathmatch-cooldown-boundaries-'+str(i),c))
    for i in range(8):
        c,ops=base(501+4*i)
        ops += [dict(op='roster_replace',targets=[]),dict(op='room_player',side='plant',hp=0.,position=[264.,432.],revive=4.-.032),
            dict(op='room_player',side='plant2',position=[264.,432.]),dict(op='room_step'),dict(op='room_step')]
        out.append(('room-team-revive-and-result-'+str(i),c))
    for i in range(8):
        c,ops=base(600+i);rate=(30,60)[i%2];ops[-1].update(rate=rate,capture=True)
        ops += [dict(op='roster_replace',targets=[]),dict(op='room_player',side='plant',last=-(rate*2)),
            dict(op='room_input',side='plant',payload=dict(type='move',move=1,jump=True,seq=1)),
            dict(op='room_player',side='plant',last=-(rate*2)),dict(op='room_step',count=3),
            dict(op='room_state',audit='fixture-audit-stop'),dict(op='room_step',count=2)]
        out.append(('room-input-timeout-and-audit-stop-'+str(i),c))
    return out

def paths():
    stage=shared.ROOT/'build/typed72-room-stage'
    requested=native.paths()+[Path(__file__).resolve(),SIM,shared.LOCAL/'balance.py',stage/'source/tools/typed72/room_probe.cpp']
    requested=[p if p.exists() else stage/'source/tools/typed72'/p.name for p in requested]
    return requested+list(HERE.glob('verify_*.py'))+list((stage/'source').rglob('*.h'))+list((stage/'source').rglob('*.cpp'))+[stage/'build-inputs.json']

if __name__=='__main__':raise SystemExit(shooting.main(paths(),reference,cases,RoomExtension,'typed72-room-native-input'))
