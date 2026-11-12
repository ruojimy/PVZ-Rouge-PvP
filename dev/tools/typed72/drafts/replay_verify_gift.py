"""Versioned gift recording over the actual source command and battle loop.

Replay-1 retains its historical omitted amount and expected playback error.
Replay-2 adds exactly amount to the Recording input field set. Command,
resource transfer, cooldown and Playback code remain the actual source.
Every playback update executes at most one real room tick, and checkpoints
include balances and gift cooldowns for all seats.
"""
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replay_verify_lifecycle as base
LegacyExtension=base.ReplayExtension
original_paths=base.paths
original_cases=base.cases
class GiftExtension(LegacyExtension):
    def operation(self,op):
        if op['op']=='record_generated':op=dict(op,op='record_input')
        result=super().operation(op)
        if op['op']=='record_setup' and op.get('format')=='pvz-pvp-replay-2':
            self.replay_env['INPUT_FIELDS']=self.replay_env['INPUT_FIELDS']+('amount',)
            self.replay_env['FORMAT']='pvz-pvp-replay-2'
        return result
def cases():
    out=[]
    originals=original_cases()
    duo=next(c for _,c in originals if next(op for op in c['operations'] if op['op']=='track_setup')['mode']=='duo')
    for i in range(16):
        c=copy.deepcopy(duo);c['snapshot_resources']=True;rate=30 if i%4<2 else 60;start=rate*5-1;format='pvz-pvp-replay-1' if i%2==0 else 'pvz-pvp-replay-2'
        end=next(j for j,op in enumerate(c['operations']) if op['op']=='record_setup');c['operations']=c['operations'][:end]
        for op in c['operations']:
            if op['op']=='track_setup':op['mode']='duo'
            elif op['op']=='native_tick_setup':op.update(present=['plant','zombie','plant2','zombie2'],team_mode=True,multi_target=True,multi_plant=True,scripted=False)
            elif op['op']=='room_setup':op.update(rate=rate,tick=start,phase=(start*250)%rate)
            elif op['op']=='clock':op.update(tick=(start*250)//rate,time=start/rate)
            elif op['op']=='economy_setup':op['present']=['plant','zombie','plant2','zombie2']
        ops=c['operations'];amount=(1,25,50,100)[i//2%4]
        # The legacy format fails on its first gift. Advance one real tick
        # before that input so Playback.update exposes its documented error
        # state, instead of construction correctly rejecting the session.
        ops.extend([dict(op='record_setup',format=format),dict(op='record_step'),dict(op='record_input',side='plant',payload=dict(type='gift',amount=amount,seq=1)),dict(op='record_step'),dict(op='record_generated',side='plant2',payload=dict(type='gift',amount=100,seq=1)),dict(op='record_step'),dict(op='record_input',side='plant',payload=dict(type='gift',amount=50,seq=2)),dict(op='record_step'),dict(op='record_input',side='zombie',payload=dict(type='gift',amount=25,seq=1))])
        ops.extend(dict(op='record_step') for _ in range(5));ops.append(dict(op='record_play'))
        for j in range(10):ops.append(dict(op='play_update',playing=j==0,dt=.5 if j==0 else 0.,max_steps=1,budget=.1) if j==0 else dict(op='play_update',dt=0.,max_steps=1,budget=.1))
        ops.extend([dict(op='play_seek',tick=start+1),dict(op='play_update',max_steps=1,budget=.1),dict(op='play_seek',tick=start+9)])
        ops.extend(dict(op='play_update',max_steps=1,budget=.1) for _ in range(8));ops.append(dict(op='record_close'));out.append((format+'-gift-every-tick-'+str(i),c))
    return out
def paths():return original_paths()+[Path(__file__).resolve()]
if __name__=='__main__':
    base.cases=cases;base.ReplayExtension=GiftExtension;base.paths=paths
    raise SystemExit(base.main())
