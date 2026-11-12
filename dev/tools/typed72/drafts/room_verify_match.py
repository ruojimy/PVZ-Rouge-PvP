"""Actual outer Room lifecycle over the real typed room/native driver.

Map/deck admission and campaign persistence are explicit cold fixtures. No
second battle simulation is used: input and updates execute the same verified
RoomCommands/RoomScheduler composition as live recording.
"""
import ast,copy,sys,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replay_verify_lifecycle as base
room=base.room
original_paths=base.paths
def match_reference():
    env=dict(deepcopy=copy.deepcopy,DUEL='duel',MODES=('duel','duo','pve','coop'),scripted=lambda m:m in ('pve','coop'),team_of=lambda s:'plant' if s.startswith('plant') else 'zombie',seats_for=lambda m:{'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'pve':['plant'],'coop':['plant','plant2']}[m])
    tree=ast.parse((base.ROOT/'tools/pvp72_sources/room.py').read_text(encoding='utf8'));cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Room')
    names={'audit_error','_halt_for_audit','_record','side_for','peer_connected','snapshot_peers','role_change_error','change_role','connect_spectator','connect','_forget_prepared_seat','_release_peer','disconnect','leave','kick','reopen','_forfeit','host_quit','_capture_battle_result','_reset_selection','command','_command','seat_list','duo','deck_keys','players_sides','update'}
    cls=ast.ClassDef(name='Room',bases=[],keywords=[],body=[copy.deepcopy(n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'actual_room_lifecycle','exec'),env)
    exec(compile((base.SOURCE/'adaptive_pacing.py').read_text(encoding='utf8'),'actual_adaptive_pacing','exec'),env)
    return env
class MatchExtension(room.RoomExtension):
    def __init__(self,ctx,case,pref,ref):
        super().__init__(ctx,case,pref,ref);self.match=None;self.match_env=match_reference();self.records=[];self.saves=self.closes=self.progress_syncs=self.progress_finishes=self.draft_timeouts=0;self.dropped=[];self.clock=0.
        def monotonic():now=self.clock;self.clock+=.001;return now
        self.match_env['time']=types.SimpleNamespace(perf_counter=monotonic)
        self.match_env['AuditLogError']=RuntimeError
    def increment(self,key):setattr(self,key,getattr(self,key)+1)
    def operation(self,op):
        name=op['op'];peer=op.get('peer','guest')
        if name=='match_setup':
            original_input=self.b.command_input;original_clear=self.b.clear_input
            def traced_input(side,payload):
                error=original_input(side,payload);self.input_events.append(['attempt',self.b.tick,side,error]);return error
            def traced_clear(side):
                result=original_clear(side);self.input_events.append(['clear',self.b.tick,side]);return result
            self.b.command_input=traced_input;self.b.clear_input=traced_clear
            r=self.match=self.match_env['Room']();r.mode=op.get('mode','duel');seats=r.seat_list();r.members=dict(op.get('members',[['host','plant']]));r.connected={p:True for p in r.members};r.spectators={};r.revision=1;r.phase='config';r.clock=0.;r.ready={s:False for s in seats};r.confirmed=dict(r.ready);r.loaded=dict(r.ready);r.deadline=0.;r.result=None;r.accumulator=0.;r.status='等待对方加入并确认地图';r.pacing=self.match_env['AdaptivePacing']();r._paced_battle=None;r.disconnect_deadline=None;r.rematch_votes={};r.pause_votes=set();r.paused=False;r.pause_epoch=0;r.restart_votes=set();r.match_number=0;r.loading_id=None;r._audit_error='';r.log=types.SimpleNamespace(error='',append=self.records.append);r.allow_spectators=op.get('allow',True);r.max_spectators=op.get('max_spectators',2);r.ai_peers=set(op.get('ai',[]));r.subsidy_peers=set(r.ai_peers);r.config_requests={};r.same_deck_rematch=False;r.pve=dict(day=3,decks={}) if r.mode in ('pve','coop') else None;r.on_pve_result=None;r.map=types.SimpleNamespace(terrain_hash='fixture-terrain');r.decks={s:[] for s in r.deck_keys()};r.bans=[];r.rules=self.b.rules
            r.coop_progress=types.SimpleNamespace(sync=lambda _:self.increment('progress_syncs'),drop=self.dropped.append,finish=lambda *_:self.increment('progress_finishes'));r._save_replay=lambda:self.increment('saves');self.b.close=lambda:self.increment('closes');r.battle=self.b if op.get('bind',True) else None
        elif name=='match_phase':
            r=self.match;r.phase=op['phase']
            if 'deadline' in op:r.deadline=op['deadline']
            if 'loading_id' in op:r.loading_id=op['loading_id']
            if op.get('bind'):r.battle=self.b
        elif name=='match_connect':return self.match.connect(peer,op.get('spectator',False),op.get('seat'))
        elif name=='match_role':return self.match.change_role(peer,'spectator' if op.get('spectator') else 'player',op.get('seat'))
        elif name in ('match_disconnect','match_leave','match_kick'):getattr(self.match,name[6:])(peer)
        elif name=='match_host_quit':self.match.host_quit()
        elif name=='match_reopen':return self.match.reopen()
        elif name=='match_update':self.match.update(op['dt'])
        elif name in ('match_pause','match_loaded'):
            payload={k:v for k,v in op.items() if k not in ('op','peer')};payload['type']=name[6:];return self.match.command(peer,payload)
        elif name=='match_input':return self.match.command(peer,dict(type='input',input=op['payload']))
        elif name=='match_capture':self.match._capture_battle_result()
        elif name=='match_result':self.b.result=dict(winner=op.get('winner','plant'),reason='hero_death',tick=self.b.tick)
        elif name=='match_audit':self.match.log.error=op['error']
        else:return super().operation(op)
    def snapshot(self,row):
        super().snapshot(row)
        if self.match is None:return
        r=self.match;keys=['phase','members','connected','spectators','ready','confirmed','loaded','clock','deadline','accumulator','revision','pause_epoch','paused','disconnect_deadline','result','status','audit_error','loading_id','match_number'];value={k:copy.deepcopy(getattr(r,k)) for k in keys};value.update(pause_votes=sorted(r.pause_votes),restart_votes=sorted(r.restart_votes),snapshot_peers=r.snapshot_peers(),records=copy.deepcopy(self.records),saves=self.saves,closes=self.closes,progress_syncs=self.progress_syncs,progress_finishes=self.progress_finishes,dropped_progress=list(self.dropped),draft_timeouts=self.draft_timeouts);row['match']=value
def cases():
    out=[];originals=base.room.cases()[:4]
    for i in range(24):
        _,c=originals[i%4];c=copy.deepcopy(c);end=next(j for j,op in enumerate(c['operations']) if op['op']=='room_setup');c['operations']=c['operations'][:end+1];mode=next(op['mode'] for op in c['operations'] if op['op']=='track_setup');seats={'duel':['plant','zombie'],'duo':['plant','zombie','plant2','zombie2'],'pve':['plant'],'coop':['plant','plant2']}[mode];members=[['host','plant']]+[['guest' if j==1 else 'peer'+str(j),s] for j,s in enumerate(seats) if j];ops=c['operations'];ops.append(dict(op='match_setup',mode=mode,members=members,bind=False,ai=['peer2']));kind=i//4
        if kind==0:
            ops.extend([dict(op='match_connect',peer='watch',spectator=True),dict(op='match_role',peer='host',spectator=True),dict(op='match_role',peer='host',spectator=False),dict(op='match_disconnect'),dict(op='match_connect'),dict(op='match_leave'),dict(op='match_connect',peer='new')])
        elif kind==1:
            ops.extend([dict(op='match_phase',phase='loading',loading_id='current',deadline=60.,bind=True),dict(op='match_loaded',peer='host',loading_id='old',terrain_hash='fixture-terrain'),dict(op='match_loaded',peer='host',loading_id='current',terrain_hash='wrong')]);ops.extend(dict(op='match_loaded',peer=p,loading_id='current',terrain_hash='fixture-terrain') for p,s in members);ops.append(dict(op='match_update',dt=.11));ops.extend(dict(op='match_pause',peer=p,paused=True) for p,s in members);ops.extend([dict(op='match_update',dt=.1),dict(op='match_pause',peer='host',paused=False,pause_epoch=0),dict(op='match_pause',peer='host',paused=True,pause_epoch=0),dict(op='match_update',dt=.04)])
        elif kind==2:
            ops.extend([dict(op='match_phase',phase='battle',bind=True),dict(op='match_disconnect',peer='guest' if len(seats)>1 else 'host')]);ops.extend(dict(op='match_update',dt=2.) for _ in range(11));ops.extend([dict(op='match_reopen'),dict(op='match_connect',peer='new')])
        elif kind==3:
            ops.extend([dict(op='match_phase',phase='battle',bind=True),dict(op='match_result'),dict(op='match_disconnect',peer='guest' if len(seats)>1 else 'host'),dict(op='match_host_quit'),dict(op='match_reopen')])
        elif kind==4:
            ops.extend([dict(op='match_phase',phase='battle',bind=True),dict(op='match_input',peer='host',payload=dict(type='move',move=1,seq=2)),dict(op='match_pause',peer='host',paused=1),dict(op='match_update',dt=.1),dict(op='match_audit',error='fixture I/O error'),dict(op='match_update',dt=.1),dict(op='match_input',peer='host',payload=dict(type='move',move=0,seq=3))])
        else:
            ops.extend([dict(op='match_phase',phase='loading',bind=True,deadline=1.),dict(op='match_update',dt=1.2),dict(op='match_kick'),dict(op='match_reopen'),dict(op='match_connect',peer='next'),dict(op='match_connect',peer='watch1',spectator=True),dict(op='match_connect',peer='watch2',spectator=True),dict(op='match_connect',peer='watch3',spectator=True),dict(op='match_disconnect',peer='watch1')])
        out.append(('actual-room-lifecycle-'+str(i),c))
    return out
def paths():return original_paths()+[Path(__file__).resolve(),base.ROOT/'tools/pvp72_sources/room.py',base.SOURCE/'adaptive_pacing.py']
if __name__=='__main__':
    base.cases=cases;base.ReplayExtension=MatchExtension;base.paths=paths
    raise SystemExit(base.main())
