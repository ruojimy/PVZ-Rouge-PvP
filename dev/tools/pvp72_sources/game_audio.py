"""Original roguelike music and effects for local, network and replay views."""
import math
import time
from pathlib import Path


def music_track(view,state):
    screen=state.get('screen','home');phase=view.get('phase')
    if screen in ('room','replay') and phase=='result':return None
    if screen in ('room','replay') and phase=='battle':
        if (view.get('battle') or {}).get('deathmatch'):return '死斗-虽华'
        terrain=view.get('map') or (view.get('battle') or {}).get('map') or {}
        env=terrain.get('environment',{})
        if env.get('weather')=='rain':return '雨夜' if env.get('night') else '泳池'
        if env.get('night'):return '黑天'
        if any(c.get('water') for row in terrain.get('tiles',[]) for c in row):return '泳池'
        return '白天'
    if screen=='pve_shop':return '商店'          # the original shop plays 音乐/商店.mp3
    if screen=='pve':return '选卡'
    return '选卡' if screen=='room' else '主界面'


class GameAudio:
    def __init__(self,pygame,asset_root):
        self.pg=pygame;self.root=Path(asset_root);self.sounds={};self.missing=set()
        self.files={p.stem:p for p in (self.root/'音效').glob('*') if p.suffix.lower() in ('.ogg','.wav')}
        self.music_files={p.stem:p for p in (self.root/'音乐').glob('*') if p.suffix.lower() in ('.mp3','.ogg','.wav')}
        self.channels=[];self.playing={};self.cursor=0;self.tick=None;self.session=None;self.track=None;self.music_paused=False
        self.retry_at=0.;self.last_error=''
        self._ensure_ready()

    def _ensure_ready(self):
        if not self.pg.mixer.get_init():
            # A transient device failure must not leave this instance without
            # channels forever. Retry in the foreground, with bounded frequency.
            self.channels=[];self.playing.clear();self.sounds.clear();self.track=None
            now=time.monotonic()
            if now<self.retry_at:return False
            self.retry_at=now+2.
            try:self.pg.mixer.init()
            except self.pg.error as exc:self.last_error=str(exc);return False
        if not self.channels:
            self.pg.mixer.set_num_channels(max(24,self.pg.mixer.get_num_channels()))
            self.pg.mixer.set_reserved(16)
            self.channels=[self.pg.mixer.Channel(i) for i in range(16)]
        self.last_error='';self.retry_at=0.
        return True

    def stop_effects(self):
        for channel in self.channels:channel.stop()
        self.playing.clear()

    def reset(self):
        self.stop_effects();self.cursor=0;self.tick=None;self.session=None

    def _music(self,view,state):
        name=music_track(view,state) if state.get('music',True) else None
        if name!=self.track:
            self.pg.mixer.music.stop();self.track=None;self.music_paused=False
            if name in self.music_files:
                try:
                    self.pg.mixer.music.load(str(self.music_files[name]));self.pg.mixer.music.play(-1);self.track=name
                except self.pg.error:self.missing.add('音乐:'+name)
        self.pg.mixer.music.set_volume(max(0.,min(1.,float(state.get('music_volume',.25)))))
        paused=bool(view.get('paused') or state.get('focused') is False)
        if paused!=self.music_paused:
            (self.pg.mixer.music.pause if paused else self.pg.mixer.music.unpause)();self.music_paused=paused

    def play(self,name,volume=1.,pan=0.):
        if not self._ensure_ready():return False
        if name not in self.files:self.missing.add(name);return False
        sound=self.sounds.get(name)
        if sound is None:
            try:sound=self.sounds[name]=self.pg.mixer.Sound(str(self.files[name]))
            except self.pg.error:self.missing.add(name);return False
        channel=next((c for c in self.channels if not c.get_busy()),None)
        if channel is None:return False
        channel.set_volume(volume*(1.-max(0.,pan)*.65),volume*(1.+min(0.,pan)*.65))
        channel.play(sound);self.playing.setdefault(name,[]).append(channel)
        return True

    def update(self,view,state):
        if not self.pg.mixer.get_init() and state.get('focused') is False:return
        if not self._ensure_ready():return
        self._music(view,state)
        battle=view.get('battle') or {};data=battle.get('audio') or {};events=data.get('events') or []
        sequence=data.get('sequence',0);tick=battle.get('native_tick',0)
        session=(state.get('screen'),view.get('match_id'),view.get('terrain_hash'),view.get('match_number'))
        if session!=self.session or self.tick is None or tick<self.tick:
            self.stop_effects();self.cursor=sequence;self.session=session
        self.tick=tick
        active=(state.get('screen') in ('room','replay') and view.get('phase')=='battle'
                and not view.get('paused') and state.get('focused') is not False and state.get('sound',True))
        if not active:self.stop_effects();self.cursor=sequence;return
        terrain=view.get('map') or battle.get('map') or {};width=terrain.get('width',0)
        tile=terrain.get('tile_size',48);width=width or len((terrain.get('tiles') or [[]])[0])*tile
        side=state.get('active_side') or state.get('local_side') or next(iter(view.get('local_sides') or []),'plant')
        hero=battle.get('players',{}).get(side,{})
        listener=state.get('replay_camera') if state.get('screen')=='replay' else None
        if view.get('spectating'):
            mode=state.get('spectator_mode')
            if mode in ('plant','zombie'):
                hero=battle.get('players',{}).get(mode,{})
            else:listener=state.get('spectator_camera')
        if not isinstance(listener,(tuple,list)) or len(listener)<2:listener=[hero.get('x',0),hero.get('y',0)]
        volume=max(0.,min(1.,float(state.get('volume',.35))))
        for event in events:
            if event.get('id',0)<=self.cursor or tick-event.get('tick',0)>250:continue
            name=event.get('name','')
            if event.get('stop'):
                for channel in self.playing.pop(name,[]):
                    if channel.get_sound() is self.sounds.get(name):channel.stop()
                continue
            gain=volume;pan=0.;pos=event.get('position')
            if isinstance(pos,list) and len(pos)>=2:
                dx=pos[0]-listener[0]
                if width:dx=(dx+width*.5)%width-width*.5
                distance=math.hypot(dx,pos[1]-listener[1]);gain*=max(0.,1.-distance/(tile*36.))
                pan=max(-1.,min(1.,dx/(tile*8.)))
            if name.startswith('吃'):gain*=.5
            if gain>.005:self.play(name,gain,pan)
        self.cursor=max(self.cursor,sequence)
        self.playing={name:[c for c in channels if c.get_busy() and c.get_sound() is self.sounds.get(name)]
                      for name,channels in self.playing.items()}

    def close(self):
        if self.pg.mixer.get_init():
            self.stop_effects();self.pg.mixer.music.stop()
            self.pg.mixer.set_reserved(0)
