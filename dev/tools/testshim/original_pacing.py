"""250 Hz original simulation with 60 Hz presentation and measured overload."""
import time
from pvp.adaptive_pacing import AdaptivePacing
from pvp import perf_hooks

class OriginalPacing:
    def __init__(self,game,clock=time.perf_counter,sleep=time.sleep):
        self.g=game;self.clock=clock;self.sleep=sleep;self.pace=AdaptivePacing()
        self.last=None;self.next_tick=None;self.next_present=0.;self.work=0.

    def finish(self):
        g=self.g;now=self.clock()
        runtime=g.get('__pvp_runtime')
        if not runtime or not runtime.battle or runtime.active or g.get('暂停'):
            self.last=self.next_tick=None;self.pace=AdaptivePacing();self.work=0.
            return g['__pvp_original_flow']()
        if self.last is None:
            self.last=now;self.next_tick=now
        else:
            self.pace.sample(max(0.,now-self.last),.004)
            self.work+=max(0.,now-self.last)
        # Catch-up ticks do not submit the same screen to Android's vsync.
        if not g.get('补帧'):
            g['渐亮']();g['pygame'].display.update()
            # PvP71: report the ticks' work since the last present (ADPF hint,
            # diagnostics); while slowed the provider halves presentation.
            perf_hooks.frame(None,self.work+max(0.,self.clock()-now),self.pace.snapshot());self.work=0.
            self.next_present=self.clock()+1./perf_hooks.frame_rate(60)
        self.next_tick+=.004/self.pace.scale
        now=self.clock()
        if self.next_tick<now-.1:self.next_tick=now
        if self.next_tick>now:self.sleep(self.next_tick-now)
        self.last=self.clock()
        g['补帧']=0 if self.last>=self.next_present else 1
        g['保底画面']=0;g['job']=int(max(0.,self.last-self.next_tick)/.004)
        g['_pvp_original_pacing']=self.pace.snapshot()

def arm(game):
    if '__pvp_original_flow' in game or not callable(game.get('走流程')):return
    game['__pvp_original_flow']=game['走流程']
    controller=OriginalPacing(game);game['走流程']=controller.finish
    game['__pvp_original_pacer']=controller
