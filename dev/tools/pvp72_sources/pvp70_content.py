"""PvP70 native units, attackable tentacles, water supports and projectiles.

All simulation clocks advance at 250 Hz; drawing never advances a clock.
Shots retain firing allegiance. Dynamic state lives in native unit dictionaries
and the battle snapshot's recorded draw commands, including independent guests.
"""
import math
from .simulation import wrap_delta
from .teams import team_of
from .pvp70_catalog import (HOOK, REAPER, BASIN, GRABBER, HEAD, LETTUCE,
                            ANCHOR_SECRET, TENTACLE_SECRET, AIRDROP_SECRET)


def alive(obj):
    return obj.get('植物血',obj.get('血量',0))>0 and '死' not in obj and '灰烬' not in obj



def factor(obj):
    return 0. if obj.get('冰冻',0)>1000 or obj.get('黄油',0)>0 or obj.get('眩晕',0)>0 else .5 if obj.get('冰冻',0)>0 else 1.


class PvP70Content:
    def __init__(self,content):
        self.c=content;self.b=content.b;self.g=content.g
        self.shots=[];self.flashes=[];self.basins={};self.head_cells=set()
        self._install()

    def _install(self):
        g=self.g;b=self.b
        support=g['_pvp_needs_plant_support']
        def needs_support():
            p=g['植物'][g['l']]
            # A water basin is its own support; a tentacle head floats.
            if p.get('_pvp_content') in (BASIN,HEAD):return False
            return support()
        g['_pvp_needs_plant_support']=needs_support
        show=g['显示植物']
        def show_plant(index,*args,**kwargs):
            p=g['植物'][index]
            if p.get('_pvp_content') in (BASIN,GRABBER,LETTUCE):return self.draw_plant(p)
            if p.get('_pvp_content')==HEAD:return self.draw_head(p)
            return show(index,*args,**kwargs)
        g['显示植物']=show_plant
        # Invulnerability is checked inside the existing damage adapters and
        # numeric protection boundary. Extra wrappers here would hide the
        # original caller frame used by reciprocal bites and projectile hits.
        ns=b.patch.ns;wind=ns['__pvz_sb_apply_blover_zombie_wind']
        def zombie_wind(game,zombie,strength=1.):
            result=wind(game,zombie,strength)
            center=ns['__pvz_sb_plant_zombie_head_center'](game,zombie)
            if center:
                for shot in self.shots+self.c.pvp64.grenades:
                    if shot.get('kind')=='hook':continue
                    dx=wrap_delta(center[0],shot['x'],b.width)
                    if (math.hypot(dx,shot['y']-center[1])<=8*b.tile and
                            ns['__pvz_sb_blover_side_match'](center[0],center[0]+dx,zombie.get('方向',1),b.tile)):
                        shot['vx']+=zombie.get('方向',1)*1.5*self.g['plk']*strength
            return result
        ns['__pvz_sb_apply_blover_zombie_wind']=zombie_wind
        umbrella=ns['__pvz_sb_update_umbrella_zombie']
        def update_umbrella(game,zombie,cfg):
            if zombie.get('_pvp_umbrella_secret'):
                cfg=dict(cfg,cooldown=max(1,int(cfg.get('cooldown',100)*.25)))
                if not zombie.get('_pvp_umbrella_initialized'):
                    zombie['_pvp_umbrella_initialized']=True
                    key=ns['__pvz_sb_K_UMBRELLA_ZOMBIE_CD']
                    current=zombie.get(key)
                    if current is None:
                        current=ns['__pvz_sb_randint'](game,0,ns['__pvz_sb_PLANT_ZOMBIE_INITIAL_COOLDOWN_MAX'])
                    zombie[key]=max(0,int(current*.25))
            return umbrella(game,zombie,cfg)
        ns['__pvz_sb_update_umbrella_zombie']=update_umbrella

    def invulnerable(self,obj):
        return self.b.engine.native_tick<obj.get('_pvp_anchor_until',0)

    def configure(self,obj,card):
        name=card.get('content')
        if name not in (HOOK,REAPER,BASIN,GRABBER,LETTUCE):return False
        obj['_pvp_content']=name
        obj['_pvp70_clock']=0.
        if name in (HOOK,REAPER):
            obj.update(血量=120.,_pvp_max_hp=120.)
            if name==REAPER:obj['_pvp_reaper_hurt']=self.b.engine.native_tick
        else:
            hp=float(card['hp'])
            obj.update(植物=name,植物血=hp,植物血上限=hp,_pvp_max_hp=hp,射cd=10**9)
            obj.pop('睡觉',None);obj.pop('_pvp_one_shot',None)
            if name==BASIN:
                row,col=obj['坐标'];cell=self.g['ditu'][row][col]
                obj['_pvp_basin_terrain']={k:v for k,v in cell.items() if k!='植物'}
                self.basins[obj['_pvp_id']]=obj
                cell.update(方块='水',_pvp_basin=obj['_pvp_id'])
                self.b._sync_terrain()
            elif name==GRABBER:
                obj['_pvp_heads']=[];self.spawn_head(obj)
            else:
                obj['_pvp_one_shot']=True
                self.try_lettuce(obj)
        return True

    def seat_has(self,obj,key):
        seat=obj.get('_pvp_seat',obj.get('_pvp_owner','zombie'))
        return key in self.b.players[seat]['secrets']

    def plant_rate(self,p):
        if '睡觉' in p or not alive(p):return 0.
        return 1./max(.01,float(p.get('_pvp_aura_factor',1.)))

    def plant_tick(self,p):
        name=p.get('_pvp_content')
        if name==LETTUCE:
            if alive(p) and '睡觉' not in p:self.try_lettuce(p)
        elif name==GRABBER and alive(p):
            heads=self.heads(p)
            # Sleep travels along the vine both ways: a sleeping head puts the
            # root to sleep, so coffee on the root (the only coffee target, as
            # heads occupy no cell) wakes the whole plant.
            if '睡觉' in p:
                for head in heads:head.setdefault('睡觉',0)
            elif p.get('_pvp_was_asleep'):
                for head in heads:head.pop('睡觉',None)       # the root was just woken
            elif any('睡觉' in head for head in heads):
                p['睡觉']=0
                for head in heads:head.setdefault('睡觉',0)
            p['_pvp_was_asleep']='睡觉' in p
            limit=3 if self.seat_has(p,TENTACLE_SECRET) else 1
            if len(heads)<limit:
                p['_pvp70_clock']+=self.plant_rate(p)
                if p['_pvp70_clock']>=10000:
                    if self.spawn_head(p):p['_pvp70_clock']-=10000
            else:p['_pvp70_clock']=0.
            self.update_heads(p,heads)

    def heads(self,p):
        return [h for h in self.g['植物'] if h.get('_pvp_parent')==p.get('_pvp_id') and alive(h)]

    @staticmethod
    def is_head(obj):
        return isinstance(obj,dict) and obj.get('_pvp_content')==HEAD

    def spawn_head(self,p):
        """A tentacle head is a moving plant part: a native plant record that
        follows its point, so native bites, crushes, sleep and statuses apply
        in plant terms. It occupies no cell (placement ignores it)."""
        if len(self.b._native_objects)>=700:return None
        x,y=self.c.point(p);row,col=p['坐标']
        cell=self.g['ditu'][row][col];had='植物' in cell
        created=self.b.engine.spawn_plant('坚果',row,col,p.get('方向',1),factory=self.b._plant_native_factory)
        if not had:cell.pop('植物',None)
        if not created:return None
        head=created[0]
        used={h.get('_pvp_head_color',0) for h in self.heads(p)}
        color=next((i for i in range(3) if i not in used),0)
        from .catalog import actual_card
        card=actual_card('plant:'+HEAD)
        self.b._register(head,card,'plant',True,parent=dict(id=p['_pvp_id']))
        head.update(植物=HEAD,植物血=54.,植物血上限=54.,_pvp_max_hp=54.,射cd=10**9,
                    _pvp_content=HEAD,_pvp_parent=p['_pvp_id'],
                    _pvp_head_clock=0.,_pvp_head_phase='idle',
                    _pvp_head_age=0.,_pvp_head_hits=[],_pvp_head_point=(x,y),_pvp_head_color=color,
                    _pvp_head_aim=(p.get('方向',1),0.))
        head.pop('睡觉',None)
        if '_pvp_seat' in p:head['_pvp_seat']=p['_pvp_seat']
        self.anchor_head(head)
        self.b._emit('tentacle_spawn',source=p['_pvp_id'],entity=head['_pvp_id'])
        return head

    def head_targets(self,p):
        x,y=self.c.point(p);direction=p.get('方向',1);found=[]
        for target in self.c.enemies(p):
            if not alive(target):continue
            tx,ty=self.c.point(target);dx=wrap_delta(x,tx,self.b.width);dy=ty-y
            distance=math.hypot(dx,dy)
            if distance>16*self.b.tile or distance and dx*direction/distance<math.cos(math.radians(80)):continue
            hp=target.get('血量',0)*(10 if target.get('_pvp_hero') else 1)
            found.append((-hp,self.b.targets.source_id(target),target))
        found.sort(key=lambda item:item[:2]);return [t[2] for t in found]

    def update_heads(self,p,heads):
        targets=self.head_targets(p)
        used={h.get('_pvp_head_target') for h in heads if h['_pvp_head_phase']!='idle'}
        base=self.c.point(p);rate=self.plant_rate(p)
        for head in sorted(heads,key=lambda h:h['_pvp_id']):
            rate_head=0. if '睡觉' in head else rate*factor(head)
            head['_pvp_head_clock']=min(500.,head['_pvp_head_clock']+rate_head)
            if head['_pvp_head_phase']=='idle':
                choice=next((t for t in targets if self.b.targets.source_id(t) not in used),targets[0] if targets else None)
                if choice is not None:
                    uid=self.b.targets.source_id(choice);used.add(uid);head['_pvp_head_target']=uid
                    tx,ty=self.c.point(choice)
                    ax,ay=wrap_delta(base[0],tx,self.b.width),ty-base[1]
                    length=math.hypot(ax,ay)
                    if length:head['_pvp_head_aim']=(ax/length,ay/length)
                if choice is not None and head['_pvp_head_clock']>=500:
                    tx,ty=self.c.point(choice)
                    head.update(_pvp_head_phase='retract',_pvp_head_age=0.,_pvp_head_hits=[],
                                _pvp_head_goal=(base[0]+wrap_delta(base[0],tx,self.b.width),ty),
                                _pvp_head_start=tuple(head['_pvp_head_point']))
                    head['_pvp_head_clock']-=500.
            phase=head['_pvp_head_phase'];head['_pvp_head_age']+=rate_head
            old=head['_pvp_head_point'];age=head['_pvp_head_age']
            if phase=='idle':
                rest=self.head_rest(p,head)
                f=min(1.,rate_head/40.)
                point=(old[0]+wrap_delta(old[0],rest[0],self.b.width)*f,old[1]+(rest[1]-old[1])*f)
            elif phase=='retract':
                f=min(1.,age/50.);sx,sy=head['_pvp_head_start']
                rx,ry=self.head_rest(p,head)
                point=(sx+wrap_delta(sx,rx,self.b.width)*f,sy+(ry-sy)*f)
                if f>=1:
                    tx,ty=head['_pvp_head_goal'];ax,ay=wrap_delta(point[0],tx,self.b.width),ty-point[1]
                    length=math.hypot(ax,ay)
                    if length:head['_pvp_head_aim']=(ax/length,ay/length)
                    head.update(_pvp_head_phase='dash',_pvp_head_age=0.,_pvp_head_start=point)
            elif phase=='dash':
                f=min(1.,age/50.);tx,ty=head['_pvp_head_goal']
                sx,sy=head['_pvp_head_start']
                point=(sx+wrap_delta(sx,tx,self.b.width)*f,sy+(ty-sy)*f)
                if rate_head:self.head_hit(p,head,old,point)
                if f>=1:head.update(_pvp_head_phase='return',_pvp_head_age=0.,_pvp_head_start=point)
            else:
                f=min(1.,age/100.);sx,sy=head['_pvp_head_start']
                rx,ry=self.head_rest(p,head)
                point=(sx+wrap_delta(sx,rx,self.b.width)*f,sy+(ry-sy)*f)
                if f>=1:head.update(_pvp_head_phase='idle',_pvp_head_age=0.)
            head['_pvp_head_point']=(point[0]%self.b.width,point[1])
            head['方向']=p.get('方向',1)
            self.anchor_head(head)

    def head_rest(self,p,head):
        """Pause between root and target, 65% of the way towards the target."""
        bx,by=self.c.point(p);tile=self.b.tile
        target=self.b._native_objects.get(head.get('_pvp_head_target'))
        if target is None:
            target=next((t for t in self.c.enemies(p)
                         if self.b.targets.source_id(t)==head.get('_pvp_head_target')),None)
        if target is not None and alive(target):
            tx,ty=self.c.point(target)
            dx=wrap_delta(bx,tx,self.b.width);dy=ty-by
            distance=math.hypot(dx,dy)
            if distance>16*tile:
                scale=16*tile/distance;dx*=scale;dy*=scale
            return (bx+dx*.65,by+dy*.65)
        lane=head.get('_pvp_head_color',0)-1
        return (bx+p.get('方向',1)*tile*(1.7+.15*abs(lane)),by-tile*(.35+.3*lane))

    def segment_hit(self,target,start,end):
        dx=wrap_delta(start[0],end[0],self.b.width);dy=end[1]-start[1]
        # Shared body/head capsule geometry handles giants, heroes and flyers.
        return self.c.flying.target_contact(None,target,start[0],start[1],dx,dy)

    def head_hit(self,p,head,start,end):
        for target in self.c.enemies(p):
            uid=self.b.targets.source_id(target)
            if uid in head['_pvp_head_hits'] or not alive(target) or not self.segment_hit(target,start,end):continue
            head['_pvp_head_hits'].append(uid)
            self.c.damage_target(p,target,4. if target.get('_pvp_hero') else 16.,surface=True,hero_kind='tentacle')
            direction=1 if wrap_delta(start[0],end[0],self.b.width)>=0 else -1
            if target.get('_pvp_hero'):
                target['位置'][2]+=direction*self.g['plk']*400
            else:
                index=next((i for i,z in enumerate(self.g['僵尸']) if z is target),None)
                if index is not None:self.g['击退僵尸'](index,direction*self.g['plk']*400)
            self.b._emit('tentacle_hit',source=p['_pvp_id'],head=head['_pvp_id'],target=uid)

    def anchor_head(self,head):
        """Native plant contact is per cell: keep the record in its point's cell."""
        x,y=head['_pvp_head_point'];tile=self.b.tile
        rows=self.g['ditu']
        cell=[min(len(rows)-2,max(0,int(y//tile))),int(x//tile)%self.b.map['cols']]
        old=head.get('坐标')
        # Native zombies stop for a plant through the cell mark: carry it with
        # the head, never clearing a cell another plant (or head) still holds.
        if old!=cell:
            if old and not self.plant_in(old,head):rows[old[0]][old[1]].pop('植物',None)
            head['坐标']=cell
        rows[cell[0]][cell[1]]['植物']=True
        self.head_cells.add(tuple(cell))

    def head_only_cells(self):
        """Cells whose plant mark exists only for a tentacle head."""
        found=set()
        for p in self.g['植物']:
            if self.is_head(p) and alive(p):
                cell=tuple(p['坐标'])
                if not any(alive(q) and not self.is_head(q) and q.get('坐标')==list(cell) for q in self.g['植物']):
                    found.add(cell)
        return found

    def plant_in(self,cell,but=None):
        return any(p is not but and alive(p) and p.get('坐标')==list(cell) for p in self.g['植物'])

    def restore_marks(self):
        """A head's native removal clears its cell mark even where a real
        plant still stands (the root, a carried plant): put those back."""
        rows=self.g['ditu']
        for row,col in self.head_cells:
            if '植物' not in rows[row][col] and self.plant_in((row,col)):rows[row][col]['植物']=True
        self.head_cells=set()

    def before_tick(self):
        for uid,p in list(self.basins.items()):
            if not alive(p) or not any(item is p for item in self.g['植物']):
                self.remove_basin(p);self.basins.pop(uid,None)
        if self.head_cells:self.restore_marks()
        for head in self.g['植物']:
            if head.get('_pvp_content')!=HEAD:continue
            parent=self.b._native_objects.get(head.get('_pvp_parent'))
            if (not parent or not alive(parent)) and not head.get('_pvp_head_gone'):
                head['_pvp_head_gone']=True
                if alive(head):
                    head['植物血']=0.;head['死']=0
                    # A crushed root (NativeContent's 扁死 wrapper) flattens its heads.
                    if parent and parent.get('_pvp_crushed'):head['_pvp_head_crushed']=self.b.engine.native_tick
            elif alive(head):self.anchor_head(head)

    def remove_basin(self,p):
        if p.get('_pvp_basin_removed'):return
        p['_pvp_basin_removed']=True
        row,col=p['坐标'];cell=self.g['ditu'][row][col]
        if cell.get('_pvp_basin')!=p['_pvp_id']:return
        # The water is gone: water-only plants in the pot die with it (a plant
        # standing on a lily then loses its support natively).
        from .catalog import CARDS
        for other in self.g['植物']:
            if other is p or not alive(other) or self.is_head(other) or other.get('坐标')!=[row,col]:continue
            card=CARDS.get(other.get('_pvp_card'),{})
            if card.get('aquatic') or other.get('植物')=='睡莲':other['植物血']=0.
        occupied=any(other is not p and alive(other) and not self.is_head(other)
                     and other.get('坐标')==[row,col] for other in self.g['植物'])
        cell.clear();cell.update(p['_pvp_basin_terrain'])
        if occupied:cell['植物']=True
        self.b._sync_terrain()

    def water_component(self,row,col):
        rows=self.g['ditu'];cols=len(rows[0]);seen=set();todo=[(row,col%cols)]
        while todo:
            r,c=todo.pop()
            if (r,c) in seen or not 0<=r<len(rows) or rows[r][c].get('方块')!='水':continue
            seen.add((r,c));todo.extend(((r-1,c),(r+1,c),(r,(c-1)%cols),(r,(c+1)%cols)))
        return seen

    def target_in_water(self,target,water):
        pos=target['位置'];x,y=pos[:2];tile=self.b.tile
        # Feet can stand exactly at a tile boundary; include the wetted body.
        col=int(x//tile)%self.b.map['cols']
        top=y-tile*(2. if target.get('_pvp_hero') else float(target.get('大小',2)))
        return any((r,col) in water for r in range(max(0,int(top//tile)),min(len(self.g['ditu']),int((y-.001)//tile)+1)))

    def freeze(self,p,target):
        with self.b.targets.context('zombie','plant','status',p):
            target['冰冻']=max(target.get('冰冻',0),2250)

    def try_lettuce(self,p):
        if p.get('_pvp_effect_done') or not alive(p):return
        row,col=p['坐标'];water=self.water_component(row,col)
        enemies=[t for t in self.c.enemies(p) if '植物' not in t and alive(t)]
        if water:
            hits=[t for t in enemies if self.target_in_water(t,water)]
            for seat in self.b.team_seats('plant'):
                avatar=self.b.hero_states[seat]
                proxy=self.b.targets.hero_proxy(seat)
                if avatar.get('玩家血量',0)>0 and self.target_in_water(proxy,water):
                    # Native physics reads 感冒 as a presence/timer state.
                    avatar['_pvp_cold_until']=max(avatar.get('_pvp_cold_until',0),self.b.engine.native_tick+1500)
        else:
            x,y=self.c.point(p)
            hits=[t for t in enemies if abs(wrap_delta(x,self.c.point(t)[0],self.b.width))<self.b.tile*.6
                  and abs(y-self.c.point(t)[1])<self.b.tile*1.4]
            if not hits:return
            hits=hits[:1]
        for target in hits:self.freeze(p,target)
        p.update(植物血=0.,死=0,_pvp_effect_done=True)
        self.flashes.append((self.b.engine.native_tick,tuple(water),self.c.point(p)))
        self.b._emit('lettuce_freeze',source=p['_pvp_id'],water=sorted(water),targets=[self.b.targets.source_id(t) for t in hits])

    def zombie_gate(self,z):
        if z.get('僵尸')=='飞贼僵尸':self.airdrop(z)
        name=z.get('_pvp_content')
        if name not in (HOOK,REAPER):return
        # Both ship native body/head layers: the original code animates them.
        for part in ('-身','-首'):
            self.b.expansion.alias_art(z['僵尸']+part,name+part)
        if not alive(z) or z.get('出场',500)<400:return
        if name==REAPER:
            idle=self.b.engine.native_tick-z['_pvp_reaper_hurt']>=5000
            if idle!=z.get('_pvp_reaper_idle',False):
                z['_pvp_reaper_idle']=idle
                self.b._emit('reaper_idle' if idle else 'reaper_resumed',source=z['_pvp_id'])
            if idle:return
        z['_pvp70_clock']+=factor(z)
        if z['_pvp70_clock']>=1500:
            fired=self.hook(z) if name==HOOK else self.throw_bone(z)
            if fired:z['_pvp70_clock']-=1500
            else:z['_pvp70_clock']=1450.

    def airdrop(self,z):
        """Native bungee reaches its landing position at 出场=500, before
        the following steal/departure branch. It grants one independent child."""
        if (not alive(z) or z.get('出场',0)<500 or '离开' in z
                or z.get('_pvp_airdrop_used') or not self.seat_has(z,AIRDROP_SECRET)):return
        z['_pvp_airdrop_used']=True
        from .scripted_spawn_budget import source_snapshot
        source=source_snapshot(z)
        if not self.b.scripted_spawn_budget.can_spawn(source=source):
            self.b.scripted_spawn_budget.defer(source,'airdrop',0,lambda:self.airdrop_child(source))
            return
        self.airdrop_child(source)

    def airdrop_child(self,source):
        b=self.b;x,y=source['位置'][:2];owner=b.targets.owner(source)
        if len(b._native_objects)>=700:return False
        with b.targets.context('zombie' if owner=='plant' else 'plant',owner,'summon',source),b._ban_free_spawn():
            unit=b.spawn('zombie:路障僵尸','zombie',x,y,source.get('方向',-1),True,parent=source)
        if unit is None:return False
        child=b._native_objects[unit['id']];child['出场']=500
        if owner=='plant':child['魅惑']=200
        b._emit('airdrop_summon',source=source['_pvp_id'],entity=unit['id'],owner=owner)
        return True

    def hook_target(self,z):
        charmed=self.b.targets.owner(z)=='plant';x,y=self.c.point(z);found=[]
        for t in self.c.enemies(z):
            if t.get('_pvp_hero') or not alive(t):continue
            if charmed and ('僵尸' not in t or t.get('_pvp_grave')):continue
            if not charmed and ('植物' not in t or self.is_head(t)):continue
            tx,ty=self.c.point(t);distance=math.hypot(wrap_delta(x,tx,self.b.width),ty-y)
            if distance<=12*self.b.tile:found.append((-distance,self.b.targets.source_id(t),t))
        if not found:return None
        found.sort(key=lambda item:item[:2]);target=found[0][2]
        return target if charmed else self.c.pvp64.taunt_target(z,target)

    def snapshot(self,z):
        owner=self.b.targets.owner(z);seat=z.get('_pvp_seat',owner)
        if team_of(seat)!=owner:seat=owner
        return dict(_pvp_owner=owner,_pvp_id=z['_pvp_id'],_pvp_seat=seat,方向=z.get('方向',1))

    def hook(self,z):
        target=self.hook_target(z)
        if target is None:return False
        start=self.c.point(z);end=self.c.point(target);source=self.snapshot(z)
        anchor=self.seat_has(z,ANCHOR_SECRET)
        if anchor:
            for t in self.c.enemies(source):
                if alive(t) and (t is target or self.segment_hit(t,start,end)):
                    self.c.damage_target(source,t,30. if '僵尸' in t and not t.get('_pvp_hero') else 3.,hero_kind='anchor')
        self.shots.append(dict(kind='hook',x=start[0],y=start[1],vx=0.,vy=0.,age=0,
                               owner=source['_pvp_owner'],source=z['_pvp_id'],seat=source['_pvp_seat'],
                               direction=z.get('方向',1),target=self.b.targets.source_id(target),
                               anchor=anchor,defused=False))
        self.b._emit('hook_fired',source=z['_pvp_id'],target=self.b.targets.source_id(target))
        return True

    def graves(self):
        """(row, col) -> living grave, from the authoritative native roster.

        The mobile-zombie region lifts graves out of 僵尸 while it runs, and
        the reaper throws from inside that region; the roster still holds them.
        """
        tile=self.b.tile;cols=self.b.map['cols'];found={}
        for g in self.b._native_objects.values():
            if g.get('_pvp_grave') and alive(g):
                found[(int(round(g['位置'][1]/tile))-1,int(g['位置'][0]//tile)%cols)]=g
        return found

    def grave_at(self,row,col,index=None):
        return (self.graves() if index is None else index).get((row,col))

    def grave_cell(self,row,col,index=None):
        rows=self.g['ditu'];col%=len(rows[0])
        if not 0<=row<len(rows)-1:return False
        cell=rows[row][col]
        return (cell.get('方块') in self.g['kong'] and cell.get('方块')!='水'
                and '植物' not in cell and not self.grave_at(row,col,index)
                and not any(alive(p) and not self.is_head(p) and p.get('坐标')==[row,col] for p in self.g['植物'])
                and rows[row+1][col].get('方块') not in self.g['kong'])

    def bone_cell(self,z):
        x,y=self.c.point(z);tile=self.b.tile;owner=self.b.targets.owner(z);choices=[]
        plants=[self.c.point(p) for p in self.g['植物'] if alive(p) and not self.is_head(p)
                and self.c.september.targetable(p)]
        index=self.graves()
        for row,line in enumerate(self.g['ditu']):
            for col,cell in enumerate(line):
                cx,cy=(col+.5)*tile,(row+.5)*tile
                distance=math.hypot(wrap_delta(x,cx,self.b.width),cy-y)
                if distance>12*tile:continue
                if owner=='zombie' and not self.grave_cell(row,col,index):continue
                grave=self.grave_at(row,col,index)
                if owner=='plant':score=1000 if grave and self.b.targets.owner(grave)=='zombie' else 0
                else:score=sum(max(0.,4.-math.hypot(wrap_delta(cx,px,self.b.width),py-cy)/tile) for px,py in plants)
                choices.append((-score,distance,row,col))
        if not choices:return None
        choices.sort();return choices[0][2:]

    def throw_bone(self,z):
        cell=self.bone_cell(z)
        if cell is None:return False
        row,col=cell;tile=self.b.tile;x,y=self.c.point(z);tx,ty=(col+.5)*tile,(row+.8)*tile
        flight=max(100.,min(300.,math.hypot(wrap_delta(x,tx,self.b.width),ty-y)/(tile*.035)))
        gravity=self.c.pvp64.gravity
        vx=wrap_delta(x,tx,self.b.width)/flight;vy=(ty-y-.5*gravity*flight*(flight+1))/flight
        source=self.snapshot(z)
        self.shots.append(dict(kind='bone',x=x,y=y,vx=vx,vy=vy,age=0,owner=source['_pvp_owner'],
                               source=z['_pvp_id'],seat=source['_pvp_seat'],direction=z.get('方向',1),
                               cell=cell,defused=False))
        self.b._emit('bone_thrown',source=z['_pvp_id'],row=row,col=col)
        return True

    def drop_bone(self,z):
        """PvP73: a 墓碑吞噬者僵尸 that dies normally releases one bone where it
        stands. It falls straight down and lands like a 死神僵尸 bone: a legal
        grave cell becomes a bone grave, anything else (water, a plant, no
        ground below) leaves nothing."""
        x,y=self.c.point(z);source=self.snapshot(z)
        self.shots.append(dict(kind='bone',x=x,y=y,vx=0.,vy=0.,age=0,owner=source['_pvp_owner'],
                               source=z['_pvp_id'],seat=source['_pvp_seat'],direction=z.get('方向',1),
                               cell=None,defused=False))
        self.b._emit('bone_released',source=z['_pvp_id'])
        return True

    def reflect(self,shot):
        if shot.get('defused'):return False
        b=self.b;tile=b.tile
        if self.c.pvp64.umbrella_reflect(shot):return True
        if shot['owner']!='plant':return False
        ns=b.patch.ns
        for z in self.g['僵尸']:
            if not alive(z) or b.targets.owner(z)==shot['owner'] or factor(z)==0:continue
            if z.get('僵尸')!='萝卜伞僵尸':continue
            center=ns['__pvz_sb_plant_zombie_head_center'](self.g,z)
            if center and abs(wrap_delta(center[0],shot['x'],b.width))<=1.5*tile and abs(center[1]-shot['y'])<=1.5*tile:
                shot.update(defused=True,vx=-shot['vx'],vy=min(shot['vy'],-500*self.g['plk']),age=0)
                z['射']=1;b._emit('projectile_reflected',kind=shot.get('kind','grenade'),source=shot['source'],umbrella=z.get('_pvp_id'))
                return True
        return False

    def wind(self,shot):
        if shot.get('kind')=='hook':return
        b=self.b;tile=b.tile
        for p in self.c.wind._clovers():
            # Native plants region 141114..141142: one plk of horizontal
            # velocity every active tick, independently of the clover sound.
            px,py=self.c.point(p);direction=p.get('方向',1)
            if wrap_delta(px,shot['x'],b.width)*direction>=0:
                shot['vx']+=direction*self.g['plk']
                if shot['vx']*direction>0:shot['direction']=direction

    def impact_bone(self,shot,row,col):
        b=self.b;tile=b.tile
        source=b._native_objects.get(shot['source']) or dict(_pvp_id=shot['source'],方向=shot['direction'])
        if shot['owner']=='zombie':
            if self.grave_cell(row,col):
                native=b.spawn_remnant((col+.5)*tile,(row+1)*tile,source)
                if native is not None:
                    # In co-op a bone grave serves its nearest spawn point like
                    # every other grave (coop_cycle.groups / rotate).
                    native['_pvp_seat']=shot['seat'];native['_pvp_bone_grave']=True
                    b._emit('bone_grave',source=shot['source'],entity=native['_pvp_id'])
        else:
            grave=self.grave_at(row,col)
            if grave is None or b.targets.owner(grave)!='zombie':return
            if any(alive(p) and not self.is_head(p) and p.get('坐标')==[row,col] for p in self.g['植物']):return
            created=b.engine.spawn_plant('墓碑吞噬者',row,col,shot['direction'],factory=b._plant_native_factory)
            if not created:return
            from .catalog import actual_card
            p=created[0];b._register(p,actual_card('plant:墓碑吞噬者'),'plant',True,parent=dict(id=shot['source']))
            p['_pvp_seat']=shot['seat'];b.gravebusters.attach(p,grave['_pvp_id'])
            b._emit('bone_gravebuster',source=shot['source'],entity=p['_pvp_id'],grave=grave['_pvp_id'])

    def projectiles(self):
        b=self.b;tile=b.tile;kept=[];index=None
        for shot in self.shots:
            shot['age']+=1
            if shot['age']>2000:continue
            if shot.get('defused'):
                shot['vy']+=self.c.pvp64.gravity
                shot['x']=(shot['x']+shot['vx'])%b.width;shot['y']+=shot['vy']
                if shot['age']<125 and 0<shot['y']<b.height:kept.append(shot)
                continue
            if shot['kind']=='hook':
                target=b._native_objects.get(shot['target']);source=b._native_objects.get(shot['source'])
                if not target or not source or not alive(target) or not alive(source) or b.targets.owner(target)==shot['owner']:continue
                tx,ty=self.c.point(target);dx=wrap_delta(shot['x'],tx,b.width);dy=ty-shot['y'];distance=math.hypot(dx,dy)
                step=tile*.16
                if distance>step:
                    shot['x']=(shot['x']+dx/distance*step)%b.width;shot['y']+=dy/distance*step
                else:shot['x'],shot['y']=tx,ty
                if self.reflect(shot):kept.append(shot);continue
                if distance<=step:
                    packet=dict(_pvp_owner=shot['owner'],_pvp_id=shot['source'],方向=shot['direction'])
                    self.c.damage_target(packet,target,30. if '僵尸' in target else 3.,hero_kind='hook')
                    # Reaching the plant/zombie is the skill's successful effect.
                    source['_pvp_hook_pull']=(tx,(target['坐标'][0]+1)*tile if '植物' in target else target['位置'][1])
                    if shot['anchor']:source['_pvp_anchor_until']=b.engine.native_tick+750
                    b._emit('hook_hit',source=shot['source'],target=shot['target']);continue
            else:
                self.wind(shot);shot['vy']+=self.c.pvp64.gravity
                shot['x']=(shot['x']+shot['vx'])%b.width;shot['y']+=shot['vy']
                if self.reflect(shot):kept.append(shot);continue
                row,col=int(shot['y']//tile),int(shot['x']//tile)%b.map['cols']
                if not 0<=row<len(self.g['ditu']):continue
                if shot['owner']=='plant':
                    if index is None:index=self.graves()
                    if self.grave_at(row,col,index):
                        self.impact_bone(shot,row,col);index=None;continue
                if b.cell(shot['x'],shot['y']).get('solid'):
                    self.impact_bone(shot,row-1,col);continue
            kept.append(shot)
        self.shots=kept
        for z in self.g['僵尸']:
            if z.get('_pvp_hook_pull') and alive(z):
                tx,ty=z['_pvp_hook_pull'];x,y=z['位置'][:2];dx=wrap_delta(x,tx,b.width);dy=ty-y
                distance=math.hypot(dx,dy);step=tile*.2*factor(z)
                if distance<=max(step,1e-6):z['位置'][:]=[tx,ty,0.,0.];z.pop('_pvp_hook_pull',None)
                elif step:z['位置'][:]=[(x+dx/distance*step)%b.width,y+dy/distance*step,0.,0.]
        self.draw_effects()

    def draw_plant(self,p):
        name=p['_pvp_content'];x,y=self.c.point(p)
        if name==BASIN:
            row,col=p['坐标'];tile=self.b.tile;pg=self.g['pygame']
            image=pg.transform.scale(self.g['图集']['水'],(tile,tile)).copy()
            # A water surface stays open; only the two sides and bottom have a rim.
            pg.draw.lines(image,(91,48,24),False,[(0,0),(0,tile-2),(tile-2,tile-2),(tile-2,0)],max(2,round(tile*.09)))
            pg.draw.lines(image,(162,99,48),False,[(2,0),(2,tile-4),(tile-4,tile-4),(tile-4,0)],max(1,round(tile*.035)))
            # Actual water occupies this square; its border shares its bounds.
            if p.get('受伤',0)>0:pg.draw.lines(image,(220,171,99),False,[(0,0),(0,tile-2),(tile-2,tile-2),(tile-2,0)],2)
            self.g['摄像显示'](image,(col*tile,row*tile))
            return
        key=name+'-帧'+str((self.b.engine.native_tick//60)%4) if name in (GRABBER,LETTUCE) else name
        self.c.draw_custom_plant(p,key,x,(p['坐标'][0]+1)*self.b.tile,bottom=True)
        if name==LETTUCE and alive(p) and not p.get('_pvp_effect_done'):
            ground=(p['坐标'][0]+1)*self.b.tile
            self.frost(x,ground-self.b.tile*.55,11,self.b.tile*.7,seed=p['坐标'][1],ground=ground)

    def draw_zombie(self,z):
        # Hook and reaper are drawn by the original zombie code from their
        # native body/head layers (see zombie_gate).
        return False

    def head_pose(self,z,parent):
        """Drawn mouth direction (ux,uy) and the neck point the vine joins."""
        x,y=z['_pvp_head_point'];tile=self.b.tile
        ux,uy=z.get('_pvp_head_aim',(parent.get('方向',1),0.))
        if '睡觉' in z:
            # Same drooping, breathing sleep as native plants (draw_custom_plant).
            # The mouth turns about its centre, so its neck turns with it.
            droop=-z.get('方向',1)*(20+math.sin(self.b.engine.native_tick/85.)*3)
            turn=math.atan2(uy,ux)-math.radians(droop)
            ux,uy=math.cos(turn),math.sin(turn)
        # The reference mouth's stem is behind its centre. Join the tether
        # there, using the same authoritative vector as the actual dash.
        return ux,uy,(x-ux*tile*.44,y-uy*tile*.44)

    def draw_head(self,z):
        """Tentacle head (a plant record): vine to the root, then the mouth."""
        if self.g.get('补帧'):return True
        tile=self.b.tile;pg=self.g['pygame'];now=self.b.engine.native_tick
        color=z.get('_pvp_head_color',0)
        if not alive(z):
            # Plant exit: flattened like a crushed plant, otherwise wilting.
            x,y=z['_pvp_head_point']
            image=self.g['图集'][HEAD+'-色'+str(color%3)+'-帧0']
            crushed=z.get('_pvp_head_crushed')
            age=max(0,now-(crushed if crushed is not None else z.setdefault('_pvp_head_died',now)))
            if crushed is not None:
                f=min(1.,age/30.)
                w=round(image.get_width()*(1+.25*f));h=max(1,round(image.get_height()*(1-.7*f)))
                image=pg.transform.scale(image,(w,h))
            else:
                k=max(.2,1-age/250.);image=pg.transform.rotozoom(image,z.get('方向',1)*-age*.3,k)
            image=image.copy();image.set_alpha(max(0,255-int(max(0,age-150)*255/250)))
            self.g['摄像显示'](image,(x-image.get_width()/2,y+tile*.45-image.get_height() if crushed is not None
                                       else y-image.get_height()/2))
            return True
        parent=self.b._native_objects.get(z.get('_pvp_parent'))
        if not parent or not alive(parent):return True
        x,y=z['_pvp_head_point'];bx,by=self.c.point(parent)
        # The stalk's visible root knot is at pixel (24,41) on a 48px tile.
        # Start the tether inside that knot, not at the plant hit-box centre.
        by=(parent['坐标'][0]+41./48.)*self.b.tile
        tile=self.b.tile;pg=self.b.pg
        ux,uy,(neck_x,neck_y)=self.head_pose(z,parent)
        sleeping='睡觉' in z
        dx=wrap_delta(bx,neck_x,self.b.width)
        width=max(1,round(abs(dx)+tile));height=max(1,round(abs(neck_y-by)+tile))
        if width>32*tile or height>24*tile:return True
        pg=self.g['pygame'];canvas=pg.Surface((width,height),pg.SRCALPHA)
        # An imitater's grabber is grey; its heads follow the root (71002).
        grey='黑白' in parent
        tone=(lambda c:(round(.299*c[0]+.587*c[1]+.114*c[2]),)*3) if grey else (lambda c:c)
        ox=min(bx,bx+dx)-tile/2;oy=min(by,neck_y)-tile/2
        points=[]
        for i in range(33):
            f=i/32.;points.append((bx+dx*f-ox,by+(neck_y-by)*f+math.sin(f*math.pi)*tile*.2-oy))
        pg.draw.lines(canvas,tone((48,24,30)),False,points,max(3,round(tile*.15)))
        color=z.get('_pvp_head_color',0)
        mid=tone(((155,64,61),(165,72,82),(130,77,60))[color%3])
        light=tone(((216,115,94),(222,119,129),(186,130,93))[color%3])
        pg.draw.lines(canvas,mid,False,points,max(2,round(tile*.10)))
        pg.draw.lines(canvas,light,False,[(a,b-tile*.025) for a,b in points],max(1,round(tile*.025)))
        # Closely spaced collars and alternating small thorns follow the local
        # tangent, so the vine remains coherent even on a steep upward strike.
        length=math.hypot(dx,neck_y-by)
        joints=max(2,min(48,int(length/(tile*.55))))
        for i in range(1,joints):
            f=i/float(joints)
            a=bx+dx*f-ox;b=by+(neck_y-by)*f+math.sin(f*math.pi)*tile*.2-oy
            tx=dx;ty=neck_y-by+math.cos(f*math.pi)*math.pi*tile*.2
            norm=math.hypot(tx,ty) or 1.;tx/=norm;ty/=norm
            nx,ny=-ty,tx
            pg.draw.line(canvas,tone((85,39,41)),(a-nx*tile*.05,b-ny*tile*.05),(a+nx*tile*.05,b+ny*tile*.05),max(1,round(tile*.035)))
            side=1 if i%2 else -1
            tip=(a+nx*tile*.14*side-tx*tile*.025,b+ny*tile*.14*side-ty*tile*.025)
            base1=(a-tx*tile*.055,b-ty*tile*.055)
            base2=(a+tx*tile*.065,b+ty*tile*.065)
            pg.draw.polygon(canvas,tone((67,33,33)),[base1,tip,base2])
            pg.draw.line(canvas,light,(a,b),(a+(tip[0]-a)*.62,b+(tip[1]-b)*.62),max(1,round(tile*.02)))
        self.g['摄像显示'](canvas,(ox,oy))
        frame=0 if sleeping else (now//45)%4
        key=HEAD+'-色'+str(color%3)+'-帧'+str(frame)
        suffix='-受伤' if z.get('受伤',0)>0 else '-冰冻' if z.get('冰冻',0)>0 else '-黑白' if grey else ''
        image=self.g['图集'][key+suffix]
        if z.get('_pvp_poison'):
            from .native_status import tint_poison
            image=tint_poison(image,z['_pvp_poison']['level'],self.g['pygame'])
        angle=-math.degrees(math.atan2(uy,ux))   # already includes the droop
        if sleeping:
            image=image.copy();image.fill((180,190,210),special_flags=pg.BLEND_RGB_MULT)
        if angle:image=self.g['pygame'].transform.rotate(image,angle)
        self.g['摄像显示'](image,(x-image.get_width()/2,y-image.get_height()/2))
        if sleeping:
            mark=pg.transform.scale(self.g['图集']['睡觉'],(round(tile*.4),round(tile*.4)))
            lift=(now%200)/200.*tile*.3
            self.g['摄像显示'](mark,(x+tile*.22,y-image.get_height()/2-tile*.2-lift))
        if z.get('黄油',0)>0:
            butter=self.g['图集']['黄油砸']
            self.g['摄像显示'](butter,(x-butter.get_width()/2,y-image.get_height()/2-butter.get_height()/2))
        return True

    def draw_effects(self):
        if self.g.get('补帧'):return
        tile=self.b.tile
        for shot in self.shots:
            key='死神骨头' if shot['kind']=='bone' else '钩索钩头'
            if shot['kind']=='hook' and not shot.get('defused'):
                source=self.b._native_objects.get(shot['source'])
                if source:
                    sx,sy=self.c.point(source);dx=wrap_delta(sx,shot['x'],self.b.width);dy=shot['y']-sy
                    for i in range(max(1,int(math.hypot(dx,dy)/(tile*.15)))):
                        f=i/max(1,int(math.hypot(dx,dy)/(tile*.15)))
                        image=self.g['pygame'].Surface((3,3),self.g['pygame'].SRCALPHA);image.fill((151,153,150))
                        self.g['摄像显示'](image,(sx+dx*f,sy+dy*f))
            image=self.g['图集'][key]
            if shot.get('defused'):
                image=image.copy();image.set_alpha(max(20,255-shot['age']*2))
            self.c.draw_center(image,shot['x'],shot['y'],shot['age']*5 if shot['kind']=='bone' else 0)
        self.flashes=[f for f in self.flashes if self.b.engine.native_tick-f[0]<100]
        for born,cells,point in self.flashes:
            image=self.g['pygame'].Surface((tile,tile),self.g['pygame'].SRCALPHA)
            image.fill((120,220,255,max(0,120-int((self.b.engine.native_tick-born)*1.2))))
            for row,col in cells:self.g['摄像显示'](image,(col*tile,row*tile))
            # Burst of cold air from the lettuce that froze.
            self.frost(point[0],point[1],16,tile*1.6,seed=born%7,age=self.b.engine.native_tick-born)

    def frost(self,x,y,count,radius,seed=0,age=None,ground=None):
        """Cold-air motes: an idle sinking mist, or a burst `age` ticks old.

        Positions are a pure function of the native tick, so every client
        draws the same motes without any random state.
        """
        pg=self.g['pygame'];tile=self.b.tile;now=self.b.engine.native_tick
        for i in range(count):
            k=i*2.399+seed
            if age is None:
                # Cold air sinks off the leaves and spreads along the ground.
                p=((now+i*53+seed*17)%150)/150.
                px=x+math.cos(k)*radius*(.25+.75*p)
                py=y+math.sin(k)*tile*.12+p*tile*.4
                if ground is not None:py=min(py,ground-tile*.08)
            else:
                p=min(1.,age/100.)
                r=radius*(.2+.8*p)*(.6+.1*(i*7%5))
                px=x+math.cos(k)*r;py=y+math.sin(k)*r*.6+p*tile*.2
            alpha=int(210*(1-p*p))
            if alpha<=0:continue
            size=max(2,round(tile*(.07+.09*p)))
            # Opaque pixel squares faded by surface alpha (per-pixel alpha in a
            # fill does not survive the recorded replay and turns dark).
            mote=pg.Surface((size,size))
            mote.fill((205,240,255))
            if i%4==0 and p<.5:
                # A few glints read as ice crystals rather than smoke.
                mote.fill((255,255,255),(0,size//3,size,max(1,size//3)))
            mote.set_alpha(alpha)
            self.g['摄像显示'](mote,(px-size/2,py-size/2))
