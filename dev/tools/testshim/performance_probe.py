"""Explicit diagnostic scenes in the actual Application loop, PC or APK.

Only the adb/CLI test entry imports this module. It never opens public rooms.
The native engine, render, scaling, present and normal replay recording run.
"""
import json
import os
import time
from pathlib import Path


class Driver:
    def __init__(self,config):
        self.config=config;self.started=None;self.measuring=False;self.finished=False
        self.output=Path(config['output']);self.output.parent.mkdir(parents=True,exist_ok=True)
        from pvp.performance import FLAGS
        for name in FLAGS:
            # The reference is the delivered PvP51, with its four features on.
            default=True if name in FLAGS[:4] else config.get('optimized',True)
            os.environ['PVP_'+name]=str(int(config.get('flags',{}).get(name,default)))
        if 'scaled' in config:
            # Display backend A/B switch (PVP_SCALED); absent keeps the process value.
            os.environ['PVP_SCALED']=str(int(bool(config['scaled'])))

    def setup(self,app):
        setup_start=time.perf_counter()
        from pvp.maps import MapSnapshot,_cell
        from pvp.performance import runtime_info
        app.create(True);room=app.room
        # The probe runs on a temporary userdata folder, so the player's
        # settings.json is never read; display A/B comes from the config.
        from pvp.display_pipeline import load_settings as load_display_settings
        load_display_settings(app.state,self.config)
        tiles=[[_cell(dict(方块='土' if row>=20 else '空',里方块='空'),('空','水','花盆块','梯子块','坟墓')) for col in range(72)] for row in range(24)]
        room.map=MapSnapshot('性能固定场景',301,'performance51',tiles,
            spawns={'plant':(2200.,960.),'zombie':(2460.,960.)},source='performance51')
        room.seed=301
        room.decks={'plant':['plant:豌豆射手','plant:机枪射手','plant:杨桃','plant:香蒲','plant:花盆','plant:向日葵'],
                    'zombie':['zombie:脑光墓碑','zombie:普通僵尸','zombie:机枪僵尸','zombie:豌豆僵尸','zombie:铁桶僵尸']}
        room._start_battle();room.phase='battle';room.loaded={'plant':True,'zombie':True};room.match_number=1
        b=room.battle
        for side,avatar in b.avatars.items():
            # Diagnostic-only enlarged pool prevents an incidental hero death
            # ending a long run. Damage, movement and all unit AI stay native.
            avatar['玩家血量']=avatar['_pvp_max_hp']=avatar['_pvp_previous_hp']=1000000.
            b.players[side]['hp']=b.players[side]['max_hp']=1000000.
        scenario=self.config.get('scenario','ordinary');size=int(self.config.get('units',20))
        requested=[]
        for i in range(size):
            plant=scenario in ('mixed','barrage') and i%2==0
            if plant:
                name=('机枪射手','杨桃','香蒲')[i//2%3] if scenario=='barrage' else '豌豆射手'
                x=((37+i//2)%70+.5)*48
                key='plant:'+name;side='plant'
            else:
                name=('机枪僵尸','豌豆僵尸')[i%2] if scenario=='special' else '普通僵尸'
                x=2300.+(i%25)*8;key='zombie:'+name;side='zombie'
                if scenario=='offscreen':x=300.+(i%25)*8
            obj=b.spawn(key,side,x,960.,facing=1 if plant else -1)
            if not obj:raise AssertionError('Diagnostic spawn failed: '+key)
            if scenario=='status':
                obj.update(冰冻=6000 if i%3==0 else 600,眩晕=6000 if i%3==1 else 0,受伤=1)
                if i%3==2:b.status.apply(obj,1,duration=20.)
            requested.append(key)
        b._sync_public();app.last_map_key=None;app.refresh()
        # Human-input heartbeats are scheduled by wall time in the real App.
        # A fixed-input performance fixture must not give differently paced
        # runs different seq/last_input_tick values (part of replay hashes).
        # Submit the same neutral input once at tick zero in this diagnostic
        # entry, then let the normal native input timeout run deterministically.
        for side in ('plant','zombie'):
            error=b.command_input(side,dict(type='move',seq=1,move=0,jump=False))
            if error:raise AssertionError(error)
        app.move_inputs=lambda dt:None
        app.state.update(screen='room',active_side='plant',zoom=1.,ui_scale=1.1,sound=False)
        app.apply_scale()
        self.fixture=dict(scenario=scenario,requested_units=size,composition=requested,seed=301,
            hero_hp=1000000,network='local',camera='plant',replay=bool(room.recording),
            note='Scripted native scene; no replenishment or AI suppression. Compare actual surviving populations.')
        self.fixture['input']='Neutral move seq=1 at native tick 0 for each side; diagnostic wall-clock heartbeats disabled.'
        self.started=time.monotonic()
        self.setup_seconds=time.perf_counter()-setup_start
        self.warm_ticks=int(self.config.get('warmup_room_ticks',0))
        self.measure_ticks=int(self.config.get('measure_room_ticks',0))
        if self.measure_ticks:
            self.tick_limit=self.warm_ticks or self.measure_ticks
            original_step=b.step;original_update=room.update
            # Diagnostic boundary only: preserve the unprocessed accumulator
            # while stopping at an exact logical tick for comparable evidence.
            def limited_step(count=1):
                actual=min(count,max(0,self.tick_limit-b.tick))
                self.unused_steps+=count-actual
                return original_step(actual)
            def limited_update(dt):
                self.unused_steps=0
                try:return original_update(dt)
                finally:room.accumulator+=self.unused_steps*b.dt
            b.step=limited_step;room.update=limited_update

    def __call__(self,app,frame):
        if self.finished:return
        if self.started is None:self.setup(app)
        elapsed=time.monotonic()-self.started
        warm=float(self.config.get('warmup_seconds',5))
        ready=app.room.battle.tick>=self.warm_ticks if self.measure_ticks else elapsed>=warm
        if not self.measuring and ready:
            if self.measure_ticks:self.tick_limit=self.warm_ticks+self.measure_ticks
            from pvp.performance import AppProfiler
            app.profiler=AppProfiler(app,detail=bool(self.config.get('detail')),path=self.output.with_suffix('.live.json'))
            self.measuring=True;self.measure_start=time.monotonic()
        done=app.room.battle.tick>=self.tick_limit if self.measure_ticks else self.measuring and time.monotonic()-self.measure_start>=float(self.config.get('seconds',15))
        if self.measuring and done:
            report=app.profiler.report();report.update(fixture=self.fixture,config=self.config,completed=True,
                scene_setup_seconds=self.setup_seconds)
            report['native_result']=app.room.battle.result
            from pvp.replay import state_hash
            import hashlib
            report['final_state_sha256']=state_hash(app.room.battle)
            report['final_state']=app.room.battle.snapshot(include_map=True)
            report['final_rng_sha256']=hashlib.sha256(repr(app.room.battle.engine.rng.getstate()).encode()).hexdigest()
            report['final_canvas_sha256']=hashlib.sha256(app.pg.image.tobytes(app.renderer.screen,'RGBA')).hexdigest()
            self.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            if self.config.get('export_download'):
                from modkit.android.platform_android import export_performance
                report['downloads_export']=export_performance(self.output)
                self.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            app.pg.image.save(app.renderer.screen,str(self.output.with_suffix('.png')))
            app.profiler.unbind();app.profiler=None;app.running=False;self.finished=True


def run(config):
    import tempfile
    from pvp.app import run as run_app
    old=os.environ.get('PVP_USERDATA')
    with tempfile.TemporaryDirectory(prefix='pvp-perf-') as folder:
        os.environ['PVP_USERDATA']=folder
        try:return run_app(auto_test=Driver(config))
        finally:
            if old is None:os.environ.pop('PVP_USERDATA',None)
            else:os.environ['PVP_USERDATA']=old


if __name__=='__main__':
    import sys
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'modkit'));os.chdir(str(root))
    run(json.loads(Path(sys.argv[1]).read_text(encoding='utf8')))
