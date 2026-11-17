"""Local replay library and camera controls, isolated from live match input."""
import json
from pathlib import Path
from .replay import Playback, read_recording, SPEEDS
from .replay_transfer import ReplayTransfer


def timestamp(seconds):
    seconds=max(0,int(seconds));return '%02d:%02d'%(seconds//60,seconds%60)


class ReplayUI(ReplayTransfer):
    def init_replays(self):
        self.init_replay_transfer()
        self.playback=None;self.replay_drag=None
        self.state.update(save_replays=False, replay_camera_mode='free', replay_zoom=1., replay_page=0)

    @property
    def replay_folder(self):return self.settings_path.parent/'replays'

    def save_recording(self, room, manual=False):
        recording=getattr(room,'recording',None)
        if recording is None:
            if manual:self.message('本局尚未开始，暂无可回放记录')
            return
        if not manual and not self.state.get('save_replays'):return
        key=(recording.battle.tick,len(recording.log),json.dumps(room.result,sort_keys=True))
        if not manual and key==recording.last_saved:return
        try:
            stamp=recording.created.replace(':','-').replace(' ','_')
            path=recording.export(self.replay_folder/(stamp+'-'+recording.id[:12]+'.pvp-replay.json'),room.result)
            recording.last_saved=key
            self.state['replay_saved']=str(path)
            self.message('回放已保存：'+path.name)
        except (OSError, ValueError, RuntimeError) as exc:self.message('回放保存失败：'+str(exc))

    def replay_library(self):
        if self.room or self.transport:
            self.message('请先离开当前房间，再打开回放');return
        self.close_playback()
        files=sorted(self.replay_folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True) if self.replay_folder.exists() else []
        self.state.update(screen='replays',focus=None,replay_files=files,replay_page=0,message='')
        self.state.pop('replay_delete',None)

    def close_playback(self):
        if self.playback:self.playback.close();self.playback=None
        if getattr(self,'game_audio',None):self.game_audio.reset()
        self.replay_drag=None
        self.state.pop('replay_preview_tick',None)

    def replay_action(self, action):
        kind=action[0]
        if not kind.startswith('replay_') and kind!='save_replays':return False
        try:
            if kind=='save_replays':
                self.state['save_replays']=not self.state['save_replays'];self.save_settings()
                if self.room and self.room.phase=='result':self.save_recording(self.room)
                self.auto_save_guest_replay()
            elif kind=='replay_delete_cancel':self.state.pop('replay_delete',None)
            elif kind in ('replay_delete','replay_delete_confirm'):
                if self.state.get('screen')!='replays':return True
                path=next((p for p in self.state.get('replay_files',[]) if str(p)==action[1]),None)
                if path is None or path.parent!=self.replay_folder or path.suffix!='.json':
                    self.message('只能删除回放列表中的文件');return True
                if kind=='replay_delete':
                    self.state['replay_delete']=str(path)
                    self.message('再次点击“确认删除”删除此回放，或取消')
                elif self.state.get('replay_delete')==str(path):
                    page=self.state.get('replay_page',0)
                    path.unlink()
                    self.replay_library()
                    self.state['replay_page']=page
                    self.message('已删除回放：'+path.name)
            elif kind=='replay_library':self.replay_library()
            elif kind=='replay_page':self.state['replay_page']=max(0,self.state['replay_page']+action[1])
            elif kind=='replay_home':self.close_playback();self.state.update(screen='home',message='')
            elif kind=='replay_open':
                data=read_recording(action[1]);self.close_playback()
                self.playback=Playback(data,self.bridge,self.pg)
                hero=self.playback.battle.players['plant']
                self.state.update(screen='replay',message='',replay_camera_mode='free',
                                  replay_camera=[hero['x'],hero['y']],replay_zoom=1.)
                self.held_keys.clear();self.pointer_capture=None
            elif self.playback:
                p=self.playback
                if kind=='replay_play':
                    if p.battle.tick>=p.data['ticks']:p.seek(0)
                    p.playing=not p.playing
                    if not p.playing:p.credit=0.
                elif kind=='replay_speed':p.speed=SPEEDS[max(0,min(len(SPEEDS)-1,SPEEDS.index(p.speed)+action[1]))]
                elif kind=='replay_seek':
                    if getattr(self,'game_audio',None):self.game_audio.reset()
                    p.seek((p.target if p.target is not None else p.battle.tick)+round(action[1]/p.battle.dt))
                elif kind=='replay_tick':
                    if getattr(self,'game_audio',None):self.game_audio.reset()
                    p.playing=False;p.seek((p.target if p.target is not None else p.battle.tick)+action[1])
                elif kind=='replay_camera':self.state['replay_camera_mode']=action[1]
                elif kind=='replay_follow':
                    hero=p.battle.players[action[1]]
                    self.state.update(replay_camera=[hero['x'],hero['y']],replay_camera_mode=action[1])
                elif kind=='replay_zoom':self.state['replay_zoom']=max(.2,min(3.,self.state['replay_zoom']*action[1]))
        except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:self.message('无法读取回放：'+str(exc))
        return True

    def replay_pointer(self, phase, pos, button=1):
        if self.state['screen']!='replay':return False
        p=self.playback
        if phase=='down':
            if button != 1:return False
            hit=self.renderer.hit(pos)
            if hit and hit[0]=='replay_timeline':
                self.replay_drag=('time',pos)
                self.state['replay_resume_after_seek']=p.playing
                p.playing=False
            elif hit is None and self.renderer.camera and self.renderer.camera[3].collidepoint(pos):
                self.replay_drag=('camera',pos);self.state['replay_camera_mode']='free'
            else:return False
        elif not self.replay_drag:return False
        mode,previous=self.replay_drag
        if mode=='time':
            rect=self.state['replay_timeline_rect']
            fraction=max(0.,min(1.,(pos[0]-rect[0])/rect[2]))
            self.state['replay_preview_tick']=round(fraction*p.data['ticks'])
            if phase=='up':
                if getattr(self,'game_audio',None):self.game_audio.reset()
                p.seek(self.state.pop('replay_preview_tick'))
                p.playing=self.state.pop('replay_resume_after_seek',False)
        elif phase=='motion':
            scale=self.renderer.camera[2];camera=self.state['replay_camera']
            camera[0]=(camera[0]-(pos[0]-previous[0])/scale)%p.battle.width
            camera[1]=max(0,min(p.battle.height,camera[1]-(pos[1]-previous[1])/scale))
        self.replay_drag=None if phase=='up' else (mode,pos)
        return True

    def replay_key(self, key):
        if self.state['screen']!='replay':return False
        pg=self.pg
        actions={pg.K_ESCAPE:('replay_library',),pg.K_SPACE:('replay_play',),
                 pg.K_LEFT:('replay_seek',-5),pg.K_RIGHT:('replay_seek',5),
                 pg.K_UP:('replay_speed',1),pg.K_DOWN:('replay_speed',-1),
                 pg.K_COMMA:('replay_tick',-1),pg.K_PERIOD:('replay_tick',1),
                 pg.K_TAB:('replay_camera','free' if self.state['replay_camera_mode']=='overview' else 'overview')}
        if key in actions:self.replay_action(actions[key])
        return True

    def update_replay(self, dt):
        if self.state['screen']!='replay' or not self.playback:return
        self.playback.update(dt)
        pg=self.pg;held=self.held_keys
        if self.state['replay_camera_mode']=='free':
            camera=self.state['replay_camera'];speed=600*min(.1,dt)/self.state['replay_zoom']
            camera[0]=(camera[0]+((pg.K_d in held)-(pg.K_a in held))*speed)%self.playback.battle.width
            camera[1]=max(0,min(self.playback.battle.height,camera[1]+((pg.K_s in held)-(pg.K_w in held))*speed))

    def render_replays(self):
        r=self.renderer;state=self.state;screen=state['screen'];w,h=r.screen.get_size()
        if screen=='replays':
            r.start('对局回放','选择已保存日志 · 同版本原生引擎模拟 · 联机双方均可在结算页保存')
            r.button('自动保存：'+('开' if state['save_replays'] else '关'),(30,106,230,42),('save_replays',))
            r.text('关闭自动保存仍可在结算页手动保存；每次复赛独立记录。',(282,117),(221,214,184),17)
            files=state.get('replay_files',[]);count=max(1,(h-280)//58)
            pages=max(1,(len(files)+count-1)//count);page=min(state['replay_page'],pages-1);state['replay_page']=page
            for i,path in enumerate(files[page*count:(page+1)*count]):
                pending=state.get('replay_delete')==str(path)
                r.button(path.stem,(30,165+i*58,w-280,48),('replay_open',str(path)),size=17)
                r.button('确认删除' if pending else '删除',(w-238,165+i*58,104,48),('replay_delete_confirm' if pending else 'replay_delete',str(path)),size=16)
                if pending:r.button('取消',(w-124,165+i*58,94,48),('replay_delete_cancel',),size=16)
            if not files:r.text('暂无回放。对局结束后点“保存回放”，或把收到的回放 JSON 放入下方目录。',(40,190),(238,220,161),20,w-80)
            r.button('上一页',(30,h-102,135,40),('replay_page',-1),active=page>0)
            r.button('下一页',(175,h-102,135,40),('replay_page',1),active=page+1<pages)
            r.button('刷新',(325,h-102,135,40),('replay_library',))
            r.button('返回首页',(w-200,h-102,170,40),('replay_home',))
            r.text(str(self.replay_folder),(30,h-52),(190,187,172),12,w-60);r.footer(state)
            return True
        if screen!='replay' or not self.playback:return False
        from .world_view import WorldView
        p=self.playback;b=p.battle;r.controls=[]
        r.screen.fill((26,30,30))
        if not hasattr(r,'world'):r.world=WorldView(r.pg,r.bridge,r.asset_dir)
        if state['replay_camera_mode'] in ('plant','zombie'):
            hero=b.players[state['replay_camera_mode']];state['replay_camera']=[hero['x'],hero['y']]
        settings=dict(show_health=state.get('show_health',True),zoom=state['replay_zoom'],
                      replay_camera=state['replay_camera'],replay_camera_mode=state['replay_camera_mode'])
        touch=bool(state.get('touch_mode'));bottom=220 if touch else 178
        game=b.snapshot(include_map=True)
        r.camera=r.world.render(r.screen,game,(0,64,w,h-64-bottom),'plant',settings,replay=True)
        from .deathmatch_presentation import draw_notice
        draw_notice(r,dict(phase='result' if b.result else 'battle',battle=game,rules=b.rules))
        r.button('返回列表',(12,10,120,42),('replay_library',),size=16)
        r.button('自由视角',(145,10,120,42),('replay_camera','free'),selected=state['replay_camera_mode']=='free',size=16)
        r.button('一览全图',(278,10,120,42),('replay_camera','overview'),selected=state['replay_camera_mode']=='overview',size=16)
        r.button('跟随植物',(411,10,120,42),('replay_follow','plant'),selected=state['replay_camera_mode']=='plant',size=16)
        r.button('跟随僵尸',(544,10,120,42),('replay_follow','zombie'),selected=state['replay_camera_mode']=='zombie',size=16)
        r.button('缩小',(w-200,10,86,42),('replay_zoom',.8),size=16)
        r.button('放大',(w-102,10,86,42),('replay_zoom',1.25),size=16)
        y=h-bottom+12;gap=8;bw=(w-40-gap*6)//7;bh=48 if touch else 40
        r.button('暂停' if p.playing else '播放',(20,y,bw,bh),('replay_play',),active=not bool(p.error),size=16)
        for i,(label,act) in enumerate([('前5秒',('replay_seek',-5)),('后5秒',('replay_seek',5)),('前一刻',('replay_tick',-1)),('后一刻',('replay_tick',1)),('减速',('replay_speed',-1)),('加速',('replay_speed',1))],1):
            r.button(label,(20+i*(bw+gap),y,bw,bh),act,size=16)
        backlog=p.credit*b.dt if p.target is None else 0
        status='%g×   %s / %s   刻 %d / %d'%(p.speed,timestamp(b.time),timestamp(p.duration),b.tick,p.data['ticks'])
        if p.playing and backlog>.5:status+=' · 设备正在追赶 %.1fs'%backlog
        r.text(status,(25,y+bh+10),(250,220,134),17,w-50)
        rect=(25,h-94,w-50,40 if touch else 30);state['replay_timeline_rect']=rect
        r.pg.draw.rect(r.screen,(62,73,75),rect)
        shown=b.tick
        x=rect[0]+round(rect[2]*shown/max(1,p.data['ticks']))
        r.pg.draw.rect(r.screen,(213,181,80),(rect[0],rect[1],max(1,x-rect[0]),rect[3]))
        r.pg.draw.circle(r.screen,(255,236,170),(x,rect[1]+rect[3]//2),9)
        preview=state.get('replay_preview_tick',p.target)
        if preview is not None:
            target_x=rect[0]+round(rect[2]*preview/max(1,p.data['ticks']))
            r.pg.draw.line(r.screen,(158,224,255),(target_x,rect[1]),(target_x,rect[1]+rect[3]),3)
        r.controls.append((r.pg.Rect(rect).inflate(0,12 if touch else 0),('replay_timeline',)))
        winner=(p.data.get('result') or {}).get('winner')
        end='终点状态校验通过'+({'plant':' · 植物获胜','zombie':' · 僵尸获胜','draw':' · 平局'}.get(winner,' · 记录结束'))
        note=p.error or ('跳转中：%s → %s'%(timestamp(b.time),timestamp(p.target*b.dt)) if p.target is not None else
                         end if p.verified else ('拖动画面 · 点上方按钮缩放 · 拖动时间轴 · 高倍速受设备性能限制' if touch else '拖动画面 / WASD 移动 · 滚轮缩放 · 拖动时间轴 · 高倍速受设备性能限制'))
        r.text(state.get('message') or note,(25,h-43),(250,210,125),15,w-50)
        return True
