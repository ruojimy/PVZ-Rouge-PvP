"""Local performance switches; never part of game rules or network payloads."""
import os
import json
import platform
import sys
import time
from pathlib import Path
from .native_multiworker import PhaseProfiler,distribution,native_kernel_status
FLAGS=('COPY_RECIPE','LOCAL_PIXELS','DAVE_NODRAW','SCALE_REUSE',
       'IMAGE_COW','LAZY_PIXELS','CAPTURE_DEMAND','TARGET_KEYS','GEOMETRY_CACHE','FLOOD_GEOMETRY','DART_BROADPHASE','UI_CACHE_BUDGET')


def enabled(name):
    return os.environ.get('PVP_'+name,'1').lower() not in ('0','false','off','no')


def maybe_record_crowd(app):
    """Start coarse evidence once for an overloaded host battle, without hooks."""
    if app.profiler is not None or not app.room or app.room.phase != 'battle':
        return
    battle = app.room.battle
    if (battle is None or battle.mode not in ('pve', 'coop', 'duo') or
            getattr(app, '_crowd_profile_battle', None) is battle or
            (battle.native_cost_ratio or 0.) < .9 or len(battle.g['僵尸']) < 48):
        return
    app._crowd_profile_battle = battle
    app.profiler = AppProfiler(app, detail=False)
    app.state['performance_recording'] = '拥挤场景基础计时'


def crowd_sample(b):
    """Bounded routing/status evidence; no matrices, pixels or game mutation."""
    def fields(state):
        return dict(target=state.get('目标位置'), plant=state.get('目标植物'),
                    player_frontier=len(state.get('人洪水圈', ())),
                    plant_frontier=len(state.get('植洪水圈', ())),
                    player_cd=state.get('人洪水cd'), plant_cd=state.get('植洪水cd'))
    avatars=getattr(b,'hero_states',b.avatars)
    present=getattr(b,'present',tuple(avatars))
    tracking=getattr(b,'_seat_tracking',{})
    content=getattr(b,'content',None)
    paths=getattr(getattr(content,'september',None),'paths',{})
    audit=getattr(b,'backend_audit',None)
    typed=callable(audit) and audit().get('backend')=='typed72'
    if typed:tracking={};paths={}
    return dict(native_tick=b.engine.native_tick, map=b.map.get('name', b.map.get('map_id')),
        terrain_revision=b.terrain_revision,
        heroes={seat:list(a['玩家位置'][:2]) for seat,a in avatars.items() if seat in present},
        seat_fields={seat:fields(state) for seat,state in tracking.items()},
        hunt_fields={str(key):fields(state) for key,state in list(paths.items())[-8:]},
        routing_scope='typed routing counters not published' if typed else 'native routing dictionaries',
        units=[dict(id=z.get('_pvp_id'),card=z.get('_pvp_card', z.get('僵尸')),
                    position=list(z['位置']),hp=z.get('血量'),split=z.get('分兵'),
                    ice=z.get('冰冻',0),butter=z.get('黄油',0),stun=z.get('眩晕',0),
                    biting=z.get('啃咬',0),taunt=z.get('_pvp_taunted_by'))
               for z in b.g['僵尸'][:128] if '位置' in z])


class FramePixels:
    """One immutable, process-local frame. Surface references never enter JSON."""
    LIMIT=24*1024*1024

    def __init__(self):
        self.frame=None;self.images={};self.bytes=0;self._pixels=set()

    def add(self,description,image):
        if image.graphics.lazy_pixels or image.graphics.defer_capture:
            size=image.retained_bytes()
            if self.bytes+size>self.LIMIT:return
            self.images[id(description)]=(description,image.frozen())
            self.bytes+=size
            return
        pixels=image.pixels;identity=id(pixels)
        size=pixels.get_pitch()*pixels.get_height() if identity not in self._pixels else 0
        if self.bytes+size>self.LIMIT:return
        image._shared=True
        self.images[id(description)]=(description,pixels)
        self._pixels.add(identity);self.bytes+=size

    def get(self,frame,description):
        if frame is not self.frame:return None
        entry=self.images.get(id(description))
        if entry is None or entry[0] is not description:return None
        value=entry[1]
        from .native_animation import NativeImage
        return value.pixels if isinstance(value,NativeImage) else value


def runtime_info(app):
    pg=app.pg
    battle=app.room.battle if app.room else None
    # python-for-android can expose an application directory as sys.executable.
    # platform.platform() then tries opening it as an ELF file in libc_ver().
    try:platform_name=platform.platform();platform_error=None
    except (OSError,ValueError) as exc:
        platform_name=' '.join((platform.system(),platform.release(),platform.machine()))
        platform_error=type(exc).__name__+': '+str(exc)
    info=dict(python=sys.version,pygame=pg.version.ver,sdl=pg.get_sdl_version(),
              platform=platform_name,platform_probe_error=platform_error,
              machine=platform.machine(),processor=platform.processor(),
              android=app.android,logical_canvas=list(app.renderer.screen.get_size()),
              physical_canvas=list(app.display_backend.physical_size(app.surface)),
              display_backend=app.display_backend.describe(),
              smoothscale_backend=pg.transform.get_smoothscale_backend(),
              native_kernels=native_kernel_status(),build=app.identity,
              mode=app.mode,flags={k:enabled(k) for k in FLAGS})
    from .performance_window import process_memory
    from .cppcore import status
    info['process_memory_bytes']=process_memory()
    info['cpp_core']=status()
    from .display_pipeline import world_size
    info['presentation_settings']={k:app.state.get(k) for k in ('world_quality','display_filter','display_budget')}
    info['world_canvas']=list(world_size(app.renderer.screen.get_size(),app.state.get('world_quality')))
    if battle:
        info.update(workers=battle.sim_workers,installed_scans=[s.name for s in battle.candidate_scans],
                    map_id=battle.map.get('id'),seed=app.room.seed)
    try:
        import resource
        info['max_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:pass
    status=Path('/proc/self/status')
    if status.is_file():
        info['process_memory']={s.split(':',1)[0]:s.split(':',1)[1].strip() for s in status.read_text().splitlines() if s.startswith(('VmRSS:','VmHWM:','VmSize:'))}
    return info


class AppProfiler:
    """Bounded rolling samples in the actual game process, exported in batches.

    Frame phases do not overlap. Nested native detail is a separate section.
    Coarse and instrumented runs must be compared only to their own mode.
    """
    SCANS=('bonus_scan','chili_fire_scan','update_chili_row_hints','plant_zombie_head_hit_scan',
           'starfruit_target','star_damage_scan','update_plant_zombie_deaths',
           'update_plant_zombie_shooting','update_zombie_peas','patch_tripea_shooting',
           'update_gravebuster_zombie_plant_damage')

    def __init__(self,app,detail=False,path=None):
        self.app=app;self.detail=detail
        self.phases=PhaseProfiler(limit=6000,rolling=True)
        self.cpu_phases=PhaseProfiler(limit=6000,rolling=True)
        self.seat_phases=PhaseProfiler(limit=6000,rolling=True) if detail else None
        from .performance_window import BattleWindow, InputObservations
        self.active_window=BattleWindow()
        from collections import deque
        self.window_history=deque(maxlen=8)
        self.inputs=InputObservations(self.phases)
        self.native=PhaseProfiler(limit=6000,rolling=True) if detail else None
        self.scans=PhaseProfiler(limit=3000,rolling=True)
        from collections import deque
        for generation in range(3):self.scans.samples['gc_generation_'+str(generation)]=deque(maxlen=3000)
        self.started=time.perf_counter();self.last_export=self.started
        self.frame_start=self.started;self.last=self.started
        # A button can create us during input handling, before this frame renders.
        # Only begin() opens a measurable frame; never time a partial startup frame.
        self.frame_open=False
        self.battle=None;self.original_profiler=None;self.wrapped=[]
        self.native_ticks=0;self.frame_count=0;self.population=[]
        self.last_present=None;self.present_count=0
        self.crowd_samples=deque(maxlen=12)
        self.room_ticks=0;self.gc_started=None;self._gc_hook=None
        self.path=Path(path) if path else app.settings_path.parent/'performance'/('perf-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())+('-detail' if detail else '-coarse')+'.json')
        self.error=None
        import hashlib
        self.source_hashes={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                            for p in Path(__file__).parent.glob('*.py')}

    def bind(self):
        battle=self.app.room.battle if self.app.room else None
        if battle is self.battle:return
        if self.battle is not None:
            self.window_history.append(dict(mode=self.battle.mode,measurement=self.active_window.report()))
        self.active_window=type(self.active_window)()
        self.unbind();self.battle=battle;self.inputs.clear()
        if not battle:return
        self.original_profiler=battle.profiler
        battle.graphics.profile_detail=self.detail
        import gc
        self._gc_hook=self._gc_event
        gc.callbacks.append(self._gc_hook)
        if self.native is not None:
            battle.profiler=self.native
            self.original_seat_profiler=getattr(battle,'seat_profiler',None)
            battle.seat_profiler=self.seat_phases
            patch=getattr(battle,'patch',None)
            if patch is None:return  # typed backend has no legacy patch namespace
            for name in self.SCANS:
                key='__pvz_sb_'+name;fn=patch.ns.get(key)
                if not callable(fn):continue
                def timed(*a,_fn=fn,_name=name,**kw):
                    start=time.perf_counter()
                    try:return _fn(*a,**kw)
                    finally:self.scans.record(_name,(time.perf_counter()-start)*1000.)
                self.wrapped.append((patch.ns,key,fn,timed));patch.ns[key]=timed

    def unbind(self):
        import gc
        hook=self._gc_hook
        self._gc_hook=None  # Bound callbacks otherwise keep this native instance alive.
        if hook is not None and hook in gc.callbacks:gc.callbacks.remove(hook)
        for ns,key,fn,timed in self.wrapped:
            if ns.get(key) is timed:ns[key]=fn
        self.wrapped=[]
        if self.battle and self.battle.profiler is self.native:self.battle.profiler=self.original_profiler
        if self.battle and self.seat_phases is not None:
            self.battle.seat_profiler=getattr(self,'original_seat_profiler',None)
        if self.battle:self.battle.graphics.profile_detail=False

    def begin(self,dt):
        self.frame_open=False
        self.bind();self.tick_before=self.battle.engine.native_tick if self.battle else 0
        self.room_before=self.battle.tick if self.battle else 0
        now=time.perf_counter()
        self.cpu_start=self.cpu_last=time.process_time()
        self.render_before=self.app.frames
        self.active_window.begin(now,self.active_scope())
        # Untruncated wall interval between frame starts; frame_interval keeps
        # the loop's dt (capped at 250 ms) and must not be used for FPS.
        if self.frame_count or self.phases.samples.get('frame_interval'):
            self.phases.record('frame_interval_actual',(now-self.frame_start)*1000.)
        self.frame_start=self.last=now
        replay=getattr(getattr(self.app.renderer,'world',None),'_native_replay',None)
        if replay is not None:replay.profile_detail=self.detail
        self.phases.record('frame_interval',dt*1000.)
        self.frame_open=True

    def _gc_event(self,phase,info):
        if phase=='start':self.gc_started=time.perf_counter()
        elif self.gc_started is not None:
            self.scans.record('gc_generation_'+str(info.get('generation')),1000*(time.perf_counter()-self.gc_started))
            self.gc_started=None

    def mark(self,name):
        if not self.frame_open:return
        now=time.perf_counter();self.phases.record(name,(now-self.last)*1000.);self.last=now
        cpu=time.process_time();self.cpu_phases.record(name,(cpu-self.cpu_last)*1000.);self.cpu_last=cpu

    def active_scope(self):
        if self.app.mode=='guest':
            view=self.app.view or {}
            transport=self.app.transport
            if (transport is not None and transport.state=='connected' and view.get('phase')=='battle'
                    and view.get('disconnect_remaining') is None and not view.get('paused')
                    and not view.get('result') and not view.get('audit_error')):
                return ('guest-presentation',view.get('match_id'),view.get('match_number'))
            return None
        room=self.app.room
        if (room is None or room.phase!='battle' or room.paused or room.audit_error
                or room.disconnect_deadline is not None or room.battle is None or room.battle.result
                or len(room.members)<len(room.seat_list()) or not all(room.connected.values())):
            return None
        return (id(room.battle),room.match_id)

    def input_sent(self,seat,sequence,started=None):
        self.inputs.sent(self.input_scope(),seat,sequence,started)

    def input_scope(self):
        view=self.app.view or {}
        return (view.get('match_id'),view.get('match_number'),view.get('mode'))

    def end(self):
        if not self.frame_open:return
        self.frame_open=False
        now=time.perf_counter();self.phases.record('frame_work',(now-self.frame_start)*1000.)
        self.frame_count+=1
        if self.app.frames>self.render_before:
            if self.last_present is not None:
                self.phases.record('presentation_interval_actual',(now-self.last_present)*1000.)
            self.last_present=now;self.present_count+=self.app.frames-self.render_before
        ticks=max(0,self.battle.engine.native_tick-self.tick_before) if self.battle else 0
        self.active_window.end(self.active_scope(),ticks,self.app.frames-self.render_before,time.process_time()-self.cpu_start)
        self.inputs.expire(now)
        if self.battle:
            self.native_ticks+=max(0,self.battle.engine.native_tick-self.tick_before)
            self.room_ticks+=max(0,self.battle.tick-self.room_before)
            if self.frame_count%30==0:
                b=self.battle
                self.population.append(dict(elapsed=now-self.started,native_tick=b.engine.native_tick,
                    zombies=sum(z.get('血量',0)>0 for z in b.g['僵尸']),plants=sum(p.get('植物血',0)>0 for p in b.g['植物']),
                    projectiles=len(b.g['实体']),backlog_seconds=self.app.room.accumulator))
                if len(self.population)>1200:self.population.pop(0)
                if len(b.g['僵尸'])>=48:self.crowd_samples.append(crowd_sample(b))
        if now-self.last_export>=5.:
            self.export();self.last_export=time.perf_counter()

    def report(self):
        wall=time.perf_counter()-self.started
        frames=self.phases.samples.get('frame_work',())
        report=dict(format='pvp-app-performance-2',runtime=runtime_info(self.app),detail=self.detail,source_hashes=self.source_hashes,
            wall_seconds=wall,frames=self.frame_count,native_ticks=self.native_ticks,native_ticks_per_second=self.native_ticks/max(.001,wall),
            room_ticks=self.room_ticks,room_ticks_per_second=self.room_ticks/max(.001,wall),
            simulated_seconds=self.native_ticks/250.,simulation_wall_ratio=self.native_ticks/250./max(.001,wall),
            sample_window='last 6000 frames / last 6000 native ticks',frame_phases_ms=self.phases.summary(),
            over_budget_pct={str(ms):100.*sum(v>ms for v in frames)/max(1,len(frames)) for ms in (16.7,33.3,50.)},
            population=self.population,crowd_samples=list(self.crowd_samples),
            native_phases_ms=self.native.summary() if self.native else {},
            nested_patch_scans_ms=self.scans.summary())
        report['active_battle']=self.active_window.report()
        report['presentation']=dict(frames=self.present_count,frames_per_second=self.present_count/max(.001,wall),
            service_iterations=self.frame_count,interval_scope='presentation_interval_actual: completed displays; frame_interval_actual: service loop')
        budget=getattr(self.app,'presentation_budget',None)
        if budget is not None:report['presentation']['budget']=budget.report()
        from .perf_hooks import report as platform_report
        android_perf=platform_report()
        if android_perf is not None:report['android_perf']=android_perf
        report['active_battle_history']=list(self.window_history)
        report['active_battle']['role']='guest-presentation' if self.app.mode=='guest' else 'local-authority'
        if self.app.mode=='guest':
            for key in ('native_ticks_per_second','simulation_wall_ratio','target_native_ticks_per_second'):
                report['active_battle'][key]=None
        report['frame_phases_cpu_ms']=self.cpu_phases.summary()
        report['nested_seat_physics_ms']=self.seat_phases.summary() if self.seat_phases else {}
        report['clock_info']={name:dict(resolution=time.get_clock_info(name).resolution,monotonic=time.get_clock_info(name).monotonic) for name in ('perf_counter','process_time')}
        report['legacy_rate_scope']='The lifetime native_ticks_per_second includes waiting; use active_battle for active authoritative speed.'
        report['input_observations']=dict(pending=len(self.inputs.pending),limit=self.inputs.limit,expired=self.inputs.expired,overflow=self.inputs.overflow,
            scope='Local send to observed authority acknowledgement and present return; not physical touch-to-photon latency.')
        from .bounded_cache import BudgetCache
        report['ui_caches']={name:cache.stats() for name,cache in vars(self.app.renderer).items() if isinstance(cache,BudgetCache)}
        transport=self.app.transport
        report['transport']=transport.statistics() if transport is not None and hasattr(transport,'statistics') else dict(available=False)
        room=self.app.room
        report['scheduling']=dict(native_hz=250,room_hz=room.battle.rules['tick_rate'] if room and room.battle else None,
            max_room_steps_per_update=12,backlog_seconds=room.accumulator if room else None,
            snapshot_period_seconds=self.app.snapshot_interval(),simulation_time_dropped=False,
            note='Existing independent logic/presentation/snapshot/heartbeat schedules retained; twelve room steps is a count bound, not a frame-time guarantee.')
        b=self.battle
        if b:
            g=b.graphics;t=g.pygame.transform;p=g.recorder.latest_pixels
            report['graphics']=dict(transform_hits=t.hits,transform_misses=t.misses,transform_evictions=t.evictions,
                transform_cache_bytes=t.cache_bytes,surface_copies=g.copies,copied_bytes=g.copy_bytes,
                frame_pixels_bytes=p.bytes if p else 0)
            report['graphics'].update(shared_copies=g.shared_copies,actual_transforms=t.executions,
                transform_output_pixels=t.output_pixels,deferred_transforms=t.deferred,
                capture_frames=b.capture_frames,deferred_capture_frames=b.capture_deferred,
                commands=len(b._frame.get('commands',[])))
            report['graphics'].update(total_commands=g.recorder.total_commands,
                image_commands_ms=g.recorder.command_ms,actual_pixel_transforms_ms=t.pixel_ms,
                counter_scope='match lifetime; timings only while detailed profiler is attached')
            report['current_population']=dict(native_tick=b.engine.native_tick,
                zombies=sum(z.get('血量',0)>0 for z in b.g['僵尸']),
                plants=sum(p.get('植物血',0)>0 for p in b.g['植物']),projectiles=len(b.g['实体']),
                backlog_seconds=self.app.room.accumulator)
        r=getattr(getattr(self.app.renderer,'world',None),'_native_replay',None)
        if r:
            report['reconstruction']=dict(recipe_hits=r.hits,recipe_misses=r.misses,local_pixel_hits=r.local_hits,
                recipe_cache_bytes=r.cache_bytes,local_scaled_bytes=r.local_bytes,key_serializations=r.key_serializations)
            report['reconstruction'].update(local_scale_hits=r.local_scale_hits,local_scale_misses=r.local_scale_misses)
            report['reconstruction'].update(recipe_rebuild_ms=r.rebuild_ms,recipe_evictions=r.evictions,local_scale_evictions=r.local_evictions)
        worker=getattr(self.app,'pack_worker',None)
        if worker is not None:
            report['network_pack']=dict(worker.telemetry)
            report['snapshot_pack_phases_ms']=worker.profile_phases.summary()
            report['snapshot_pack_timing_scope']='Detailed-profile tasks only; child/worker CPU, exact task counts; excludes GUI marshal freeze (network_pack.freeze_ms).'
        return report

    def export(self):
        started=time.perf_counter()
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.report(),ensure_ascii=False,indent=2),encoding='utf8')
            tmp.replace(self.path);self.error=None
        except (OSError,ValueError,TypeError) as exc:self.error=str(exc)
        self.phases.record('profiler_export',(time.perf_counter()-started)*1000.)
        return self.path

    def close(self):
        self.frame_open=False
        try:self.export()
        finally:self.unbind()
