"""Host-only fixed step battle simulation, independent of native game globals."""
import math
import random
from copy import deepcopy
from . import cppcore as _cppcore
deepcopy = _cppcore.fast_deepcopy(deepcopy)
from .catalog import CARDS, RULES, actual_card, apply_secret_effects, allowed, validate_deck, starting_resource
from .audit_log import AuditLog
from .balance import deathmatch_blocked, hero_hp
from .teams import DUEL, DUO, normalize_mode, seats_for, scripted, team_of, team_mode
from .zombie_secret_catalog import SUBSIDY_START_BRAINS

# Handing economy to a teammate: one packet at a time, on a short cooldown, so
# a teammate can be supported without turning the match into a resource pump.
GIFT_AMOUNT = 50
GIFT_MAX = 100
GIFT_COOLDOWN = 12.


def wrap_delta(a, b, width):
    return (b-a+width/2.) % width-width/2.


_wrap_delta_py = wrap_delta
from . import cppcore as _cppcore
if _cppcore.native_for(("wrap_delta", _wrap_delta_py.__code__)) is not None:
    # Same float operations in the same order (pvpnative.cpp); see tests.
    wrap_delta = _cppcore.native().wrap_delta


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


class Battle:
    def __init__(self, terrain, decks, rules=None, seed=1, bans=(), mode=DUEL):
        self.rules=deepcopy(rules or RULES)
        # PvP66 modes. In the duel every seat is its own team and nothing
        # below differs from PvP65.
        self.mode=normalize_mode(mode)
        self.scripted=scripted(self.mode);self.team_mode=team_mode(self.mode)
        self.seats=seats_for(self.mode)
        # The "zombie" seat always exists as a faction anchor; in PvE it is a
        # dormant record that never moves, draws or takes damage.
        self.present=frozenset(self.seats)
        self.surrender_requests={};self.surrender_serial=0
        self.map=deepcopy(terrain.to_dict() if hasattr(terrain,"to_dict") else terrain)
        self.width=self.map["width"];self.height=self.map["height"];self.tile=self.map.get("tile_size",48)
        self.rng=random.Random(seed);self.tick=0;self.time=0.;self.deathmatch=False;self.result=None
        self.ids=0;self.units={};self.projectiles={};self.resources={};self.events=[];self.log=AuditLog()
        self.bans=list(bans);self.command="follow";self.rally_point=None;self.players={};self.damage_groups={}
        if self.mode == DUO:
            self.commands = {seat: "follow" for seat in ("zombie", "zombie2")}
            self.rally_points = {seat: None for seat in self.commands}
        self.sky_progress=0.;self.terrain_revision=0;self.dt=1./self.rules["tick_rate"]
        self.use_spatial_index=True;self._spatial=None;self._spatial_locations={}
        self._actor_cache=None;self._max_actor_radius=50.;self._bucket_size=self.tile*2
        self._interceptors=None;self._interceptor_range=150.
        for seat in ("plant","zombie")+tuple(s for s in self.seats if s not in ("plant","zombie")):
            side=team_of(seat)
            deck=decks.get(seat,decks[side])
            if not (self.scripted and side=="zombie"):
                error=validate_deck(side,deck,bans,self.rules[side+"_slots"],starter_budget=self.rules["zombie_start"])
                if error:raise ValueError(error)
            spawns=self.map["spawns"]
            spawn=spawns.get(seat) or spawns[side]
            x,y=(spawn["x"],spawn["y"]) if isinstance(spawn,dict) else spawn
            start_resource = starting_resource(side, self.rules, self.map)
            if side == "zombie" and "zsecret:补贴" in deck:
                start_resource += SUBSIDY_START_BRAINS     # PvP68 68003 补贴
            self.players[seat]=dict(id=seat,side=side,owner=side,current_owner=side,
                original_owner=side,native_side=side,source_entity=side,root_source=side,
                root_original_owner=side,parent_entity=None,parent_attack=None,
                x=float(x),y=float(y),vx=0.,vy=0.,
                # Native Dave is a 2-tile square canvas (36px source, alpha
                # bounds 16x35). Keep the solid body close to its visible size.
                w=self.tile*.8,h=self.tile*1.9,facing=1 if side=="plant" else -1,grounded=False,
                hp=hero_hp(self.rules,side,deck),max_hp=hero_hp(self.rules,side,deck),
                resource=start_resource,deck=list(deck),
                secrets=[c for c in deck if CARDS[c]["category"]=="secret"],
                cooldowns={},input={"move":0},seq=-1,last_input_tick=0,control_until=0.,
               immune_until=0.,marked_until=0.,tail_cd=0.,jump_held=False,
                knock_until=0.,knock_vx=0.,
                stats=dict(spent=0,earned=0,hero_damage=0,producer_lost=0))
            if seat!=side:self.players[seat].update(seat=seat)
            if seat not in self.present:self.players[seat].update(absent=True,resource=0)
        # Team-wide secret effects (native ones especially) follow every
        # teammate's secrets; a card's own form follows its holder's.
        self.team_secrets={team:sorted({k for s,p in self.players.items() if team_of(s)==team and s in self.present
                                        for k in p["secrets"]} | set(self.players[team]["secrets"]))
                           for team in ("plant","zombie")}
        self._emit("battle_start",map=self.map.get("map_id"),seed=seed)

    def _id(self,prefix):
        self.ids+=1;return prefix+str(self.ids)

    @property
    def audit_error(self):return self.log.error

    @staticmethod
    def command_seat(owner):
        """Spawned children keep their paying seat, even through a shared grave."""
        if isinstance(owner, dict):
            return owner.get('_pvp_seat', owner.get('seat', 'zombie'))
        return owner or 'zombie'

    def command_for(self, owner='zombie'):
        return self.commands.get(self.command_seat(owner), 'follow') if self.mode == DUO else self.command

    def rally_for(self, owner='zombie'):
        return self.rally_points.get(self.command_seat(owner)) if self.mode == DUO else self.rally_point

    def set_rally(self, seat, point):
        if self.mode == DUO:self.rally_points[seat] = point
        if seat == 'zombie' or self.mode != DUO:self.rally_point = point

    def close(self):self.log.close()

    @staticmethod
    def _actor_order(obj):
        return -2 if obj["id"]=="plant" else -1 if obj["id"]=="zombie" else (
            -4 if obj["id"]=="plant2" else -3 if obj["id"]=="zombie2" else int(obj["id"][1:]))

    def team_seats(self,team,alive=False):
        """Present seats of one team, optionally only those still standing."""
        return [s for s in self.seats if team_of(s)==team and
                (not alive or self.players[s]["hp"]>0)]

    def _index_actor(self,obj):
        if self._spatial is None:return
        point=(int((obj["x"]%self.width)//self._bucket_size),
               int(math.floor((obj["y"]-obj.get("h",0)/2.)/self._bucket_size)))
        old=self._spatial_locations.get(obj["id"])
        if old==point:return
        if old is not None:
            bucket=self._spatial.get(old,{})
            bucket.pop(obj["id"],None)
            if not bucket:self._spatial.pop(old,None)
        self._spatial.setdefault(point,{})[obj["id"]]=obj
        self._spatial_locations[obj["id"]]=point

    def _build_index(self):
        self._actor_cache=tuple(self.players.values())+tuple(self.units.values())
        self._max_actor_radius=max((max(a.get("w",0),a.get("h",0))/2.+6 for a in self._actor_cache),default=50.)
        self._spatial={} if self.use_spatial_index else None
        self._spatial_locations={}
        self._interceptors=tuple(u for u in self.units.values() if u["hp"]>0 and
                                 (u["behavior"]=="torch" or u["behavior"]=="umbrella" and not u["mobile"]))
        self._interceptor_range=max((u["card"]["range"] if u["behavior"]=="umbrella" else u["h"] for u in self._interceptors),default=0.)
        if self._spatial is not None:
            for obj in self._actor_cache:self._index_actor(obj)

    def _nearby(self,center,radius):
        if self._spatial is None:
            return self._actor_cache if self._actor_cache is not None else tuple(self.players.values())+tuple(self.units.values())
        span=self._bucket_size;cols=int(math.ceil(self.width/span))
        x=center["x"]%self.width;y=center["y"]-center.get("h",0)/2.
        if radius*2>=self.width:columns=range(cols)
        else:
            left=(x-radius)%self.width;right=(x+radius)%self.width
            start=int(left//span);end=int(right//span)
            columns=range(start,end+1) if left<=right else list(range(start,cols))+list(range(0,end+1))
        result=[]
        for col in columns:
            for row in range(int(math.floor((y-radius)/span)),int(math.floor((y+radius)/span))+1):
                result.extend(self._spatial.get((col,row),{}).values())
        # Preserve original insertion ordering for exact-distance ties, stacked
        # collision resolution, and simultaneous projectile contacts.
        return sorted(result,key=self._actor_order)

    def _emit(self,event,**data):
        e=dict(event=event,tick=self.tick,time=round(self.time,4));e.update(data)
        self.events.append(e);self.log.append(e)
        if len(self.events)>128:self.events=self.events[-128:]

    @staticmethod
    def _provenance(origin=None,side=None):
        """Detached audit fields; current allegiance never overwrites origin.

        An entity's original_owner is its allegiance at creation. Summoned
        children retain their creator and root lineage separately, including
        when a charmed creator now belongs to the opposing player.
        """
        obj=origin if isinstance(origin,dict) else {}
        source_entity=obj.get("source_entity",obj.get("id"))
        original_owner=obj.get("original_owner",obj.get("side",side))
        return dict(source_entity=source_entity,original_owner=original_owner,
                    current_owner=side if side is not None else obj.get("side",obj.get("owner")),
                    native_side=obj.get("native_side",obj.get("card",{}).get("side")),
                    root_source=obj.get("root_source",source_entity),
                    root_original_owner=obj.get("root_original_owner",original_owner),
                    parent_entity=obj.get("parent_entity"),parent_attack=obj.get("parent_attack"),
                    reflected_by=obj.get("reflected_by"),reflection_chain=list(obj.get("reflections",())))

    def cell(self,x,y):
        row=int(math.floor(y/self.tile));col=int(math.floor((x%self.width)/self.tile))
        if row<0:return {"solid":False,"water":False,"kind":"空"}
        if row>=len(self.map["tiles"]):return {"solid":True,"water":False,"kind":"石"}
        return self.map["tiles"][row][col%len(self.map["tiles"][row])]

    def _solid(self,x,y):
        return self.cell(x,y).get("solid",False)

    def distance(self,a,b):
        return math.hypot(wrap_delta(a["x"],b["x"],self.width), (a["y"]-a.get("h",0)/2)-(b["y"]-b.get("h",0)/2))

    def line_of_sight(self,a,b):
        dx=wrap_delta(a["x"],b["x"],self.width);dy=(b["y"]-b.get("h",0)/2)-(a["y"]-a.get("h",0)/2)
        n=max(1,int(math.hypot(dx,dy)/12.))
        return not any(self._solid(a["x"]+dx*i/n,a["y"]-a.get("h",0)/2+dy*i/n) for i in range(1,n))

    def _overlaps(self,a,b):
        return abs(wrap_delta(a["x"],b["x"],self.width))<(a["w"]+b["w"])/2.-1 and a["y"]>b["y"]-b["h"]+1 and b["y"]>a["y"]-a["h"]+1

    def _container(self,target):
        shell=self.units.get(target.get("container_id"))
        if (shell and shell["hp"]>0 and shell["side"]==target["side"]
                and abs(wrap_delta(shell["x"],target["x"],self.width))<self.tile*.55
                and abs(shell["y"]-target["y"])<6):return shell
        return None

    def _contained_ids(self,shell):
        return [u["id"] for u in self.units.values() if u.get("container_id")==shell["id"]]

    def _blocked(self,obj,x,y):
        w,h=obj.get("w",28),obj.get("h",48)
        # Only exclude the contact boundary. A two-pixel inset previously let
        # standing producers sink and heroes clip into walls at the seam.
        rows=max(1,int(h/(self.tile*.5)))
        for i in range(rows+1):
            yy=y-h+.001+(h-.002)*i/rows
            for xx in (x-w/2+.001,x+w/2-.001):
                if self._solid(xx,yy):return True
        return False

    def _water_support(self,obj):
        card=obj.get("card",{})
        if card.get("aquatic") or obj.get("behavior")=="lily":return True
        if obj.get("mobile") or obj["id"] in self.players:return False
        if not self.cell(obj["x"],obj["y"]+.1).get("water"):return False
        return any(u is not obj and u["hp"]>0 and u["side"]==obj["side"]
                   and u["behavior"]=="lily"
                   and abs(wrap_delta(u["x"],obj["x"],self.width))<self.tile*.45
                   and abs(u["y"]-obj["y"])<4 for u in self.units.values())

    def _move(self,obj,dt,flying=False):
        if (not flying and obj.get("grounded") and abs(obj.get("vx",0))<.0001
                and abs(obj.get("vy",0))<.0001 and not self._blocked(obj,obj["x"],obj["y"])
                and any(self._solid(obj["x"]+offset,obj["y"]+.002)
                        for offset in (-obj.get("w",28)/2.+.001,obj.get("w",28)/2.-.001))):
            self._index_actor(obj);return
        steps=max(1,int(max(abs(obj.get("vx",0)),abs(obj.get("vy",0)))*dt/8)+1)
        obj["grounded"]=False
        for unused in range(steps):
            dd=dt/steps;old_y=obj["y"]
            nx=(obj["x"]+obj.get("vx",0)*dd)%self.width
            if not self._blocked(obj,nx,obj["y"]):obj["x"]=nx
            elif not flying:
                # Low lips and supported steps, never pass through a full wall.
                for step in (6,12):
                    if not self._blocked(obj,nx,obj["y"]-step) and self._solid(nx,obj["y"]+3):
                        obj["x"]=nx;obj["y"]-=step;break
            if not flying:obj["vy"]=min(720.,obj.get("vy",0)+1400.*dd)
            ny=obj["y"]+obj.get("vy",0)*dd
            if self._blocked(obj,obj["x"],ny):
                if obj.get("vy",0)>0:obj["grounded"]=True
                if not self._blocked(obj,obj["x"],obj["y"]):
                    # Find the actual contacted floor/ceiling, independent of
                    # velocity or tick rate; keep stable feet coordinates.
                    clear,blocked=obj["y"],ny
                    for index in range(18):
                        middle=(clear+blocked)/2.
                        if self._blocked(obj,obj["x"],middle):blocked=middle
                        else:clear=middle
                    obj["y"]=clear
                obj["vy"]=0.
            else:obj["y"]=ny
            if obj.get("vy",0)>=0 and not flying:
                if self._water_support(obj):
                    start=max(0,int(math.floor((old_y-.01)/self.tile)))
                    end=int(math.floor(obj["y"]/self.tile))
                    for row in range(start,end+1):
                        top=row*self.tile
                        if old_y<=top+.01 and obj["y"]>=top and self.cell(obj["x"],top+.01).get("water"):
                            obj["y"]=float(top);obj["vy"]=0.;obj["grounded"]=True;break
                for unit in self._nearby(obj,self._max_actor_radius+obj.get("h",48)/2.+16):
                    if unit["id"] in self.players:continue
                    if unit is obj or unit["hp"]<=0 or unit.get("flying") or unit.get("burrowed"):continue
                    if unit["behavior"] in ("spike","lily","pot","mine"):continue
                    top=unit["y"]-unit["h"]
                    if old_y<=top+8 and obj["y"]>=top and abs(wrap_delta(obj["x"],unit["x"],self.width))<(obj["w"]+unit["w"])/2-3:
                        obj["y"]=top;obj["vy"]=0.;obj["grounded"]=True;break
        obj["x"]%=self.width
        if obj["y"]>self.height+150:
            spawn=self.map["spawns"][obj["side"]]
            obj["x"],obj["y"]=(spawn["x"],spawn["y"]) if isinstance(spawn,dict) else spawn
            obj["vy"]=0.
        self._index_actor(obj)

    def _card(self,side,key):return actual_card(key,self.players[side]["secrets"],self.map.get("environment",{}).get("night",False))

    def surface_y(self,x,y):
        colx=(math.floor((x%self.width)/self.tile)+.5)*self.tile
        start=max(0,int(y/self.tile)-1)
        for row in range(start,min(start+4,len(self.map["tiles"]))):
            tile=self.cell(colx,row*self.tile+1)
            if tile.get("solid") or tile.get("water"):
                return colx,float(row*self.tile),bool(tile.get("water"))
        return None

    def _soldier_exit(self,c,side,x,y):
        """Stack new ground troops on allies; never materialize inside foes."""
        probe=dict(id="preview",side=side,x=x%self.width,y=y,w=34.,h=float(c.get("height",44)))
        if c.get("flying"):probe["y"]-=100.
        for level in range(len(self.units)+1):
            if self._blocked(probe,probe["x"],probe["y"]):return None
            overlaps=[u for u in self.units.values() if u["hp"]>0 and self._overlaps(probe,u)]
            if any(u["side"]!=side and u["behavior"] not in ("spike","mine","pot","lily") for u in overlaps):return None
            allies=[u for u in overlaps if u["side"]==side and u["mobile"] and not u["flying"] and not u["burrowed"]]
            if c.get("flying") or not allies:return probe["x"],probe["y"]+(100. if c.get("flying") else 0.)
            probe["y"]=min(u["y"]-u["h"] for u in allies)
        return None

    def _grave_soldier_exit(self,c,side,grave,facing):
        # A neighbouring step must not disable an otherwise usable grave.
        # Spawn at the grave itself if its forward exit is obstructed; native
        # movement then handles the step/plant. Both positions retain checks.
        return (self._soldier_exit(c,side,grave["x"]+facing*42,grave["y"])
                or self._soldier_exit(c,side,grave["x"],grave["y"]))

    def _grave_surface_y(self,x,y):
        colx=(math.floor((x%self.width)/self.tile)+.5)*self.tile
        start=max(0,int(math.floor(y/self.tile)))
        if self.cell(colx,start*self.tile+1).get("water"):
            while start>0 and self.cell(colx,(start-1)*self.tile+1).get("water"):start-=1
        # Search from the hovered cell, never from an overhanging ceiling.
        for row in range(start,min(start+4,len(self.map["tiles"]))):
            tile=self.cell(colx,row*self.tile+1)
            if tile.get("solid") or tile.get("water"):
                return colx,float(row*self.tile),bool(tile.get("water"))
        return None

    def _aquatic_exit(self,c,side,grave,facing):
        """Find a nearby water landing reachable from this grave's shore.

        A feet-level water test misses a shore above its waterline. Permit a
        short horizontal exit and a clear fall, but never pass through a
        deck, wall or foe. Enclosed water under a boat hull remains unusable.
        """
        probe=dict(w=34.,h=float(c.get("height",44)))
        for distance in (42.,42.+self.tile):
            spot=self.surface_y(grave["x"]+facing*distance,grave["y"])
            if spot is None or not spot[2]:continue
            x,y,unused=spot;drop=y-grave["y"]
            if drop<-.01 or drop>self.tile*2+.01:continue
            dx=wrap_delta(grave["x"],x,self.width)
            if dx*facing<=0 or abs(dx)>self.tile*2+.01:continue
            points=[]
            count=max(1,int(abs(dx)/8)+1)
            points.extend(((grave["x"]+dx*i/count)%self.width,grave["y"]) for i in range(count+1))
            count=max(1,int(drop/8)+1)
            points.extend((x,grave["y"]+drop*i/count) for i in range(1,count+1))
            blocked=False
            for xx,yy in points:
                if self._blocked(probe,xx,yy):blocked=True;break
                footprint=dict(probe,x=xx,y=yy)
                if any(t["hp"]>0 and t["side"]!=side and
                       t["behavior"] not in ("spike","mine","pot","lily") and self._overlaps(footprint,t)
                       for t in self.units.values()):blocked=True;break
            if not blocked:
                result=self._soldier_exit(c,side,x,y)
                if result is not None:return result
        return None

    def _terrain_ladder(self,u):
        """Attach a climbable ladder outside a solid wall, preserving solids."""
        if not u["card"].get("ladder") or self.time<u["control_until"]:return
        wall_x=(u["x"]+u["facing"]*(u["w"]/2.+7))%self.width
        bottom=int(math.floor((u["y"]-2)/self.tile))
        if bottom<0 or not self.cell(wall_x,bottom*self.tile+1).get("solid"):return
        wall_col=int(wall_x/self.tile)%len(self.map["tiles"][0])
        own_col=int(u["x"]/self.tile)%len(self.map["tiles"][0])
        if wall_col==own_col:own_col=(wall_col-u["facing"])%len(self.map["tiles"][0])
        top=bottom
        while top>=0 and self.map["tiles"][top][wall_col].get("solid"):top-=1
        changed=[]
        for row in range(max(0,top-1),min(bottom+1,len(self.map["tiles"]))):
            cell=self.map["tiles"][row][own_col]
            if cell.get("solid"):continue
            if not cell.get("ladder"):
                cell["ladder"]=True;cell["ladder_owner"]=u["side"];changed.append([own_col,row])
        if changed:
            self.terrain_revision+=1;u["ladder_placed"]=True
            self._emit("terrain_ladder",source=u["id"],side=u["side"],cells=changed)

    def _stack_mobile(self,u):
        if not u["grounded"] or u["flying"] or u["burrowed"] or not u["vx"]:return
        probe=dict(u,x=(u["x"]+u["facing"]*26)%self.width)
        for ally in self._nearby(probe,self._max_actor_radius+u["h"]/2.+32):
            if ally["id"] in self.players or ally is u or ally["side"]!=u["side"] or ally["hp"]<=0:continue
            if not ally["mobile"] or ally["flying"] or ally["burrowed"] or not ally["grounded"]:continue
            dx=wrap_delta(u["x"],ally["x"],self.width)
            if dx*u["facing"]<-.001 or (abs(dx)<.001 and self._actor_order(u)<self._actor_order(ally)):continue
            if not self._overlaps(probe,ally):continue
            top=ally["y"]-ally["h"]
            x=(ally["x"]-u["facing"]*((u["w"]+ally["w"])/2.-4))%self.width
            if self._blocked(u,x,top):continue
            standing=dict(u,x=x,y=top)
            if any(t["side"]!=u["side"] and t["hp"]>0 and self._overlaps(standing,t)
                   for t in self._nearby(standing,self._max_actor_radius+u["h"]/2.) if t["id"] not in self.players):continue
            u["x"]=x;u["y"]=top;u["vy"]=0.;self._index_actor(u);return

    def placement(self,side,key,x,y,grave_id=None,copy_id=None):
        if side not in self.players:return "未知玩家",None
        p=self.players[side]
        if self.result:return "对局已结束",None
        if not finite(x) or not finite(y):return "坐标无效",None
        if key not in p["deck"] or not allowed(key,self.bans):return "未携带此卡",None
        c=self._card(side,key)
        if c["category"]=="secret":return "秘籍为常驻效果",None
        if p["cooldowns"].get(key,0)>self.time:return "正在冷却",None
        charge=c["cost"]
        if c["behavior"]=="copy":
            if copy_id not in p["deck"] or copy_id==key or not allowed(copy_id,self.bans):return "请选择已携带的合法复制目标",None
            source=self._card(side,copy_id)
            if source["category"] in ("secret","tool"):return "不能复制工具或秘籍",None
            c=source;charge+=c["cost"]
        if self.deathmatch and deathmatch_blocked(c):return "死斗禁止新增生产者",None
        team=team_of(side)
        if p["resource"]<charge:return "阳光不足" if team=="plant" else "脑光不足",None
        if len(self.units)>=700:return "战场单位达到上限",None
        if team=="zombie" and c["behavior"]!="grave":
            if not isinstance(grave_id,str):return "请选择存活的己方脑光墓碑",None
            grave=self.units.get(grave_id)
            if not grave or grave["side"]!=team or grave["behavior"]!="grave" or grave["hp"]<=0:return "请选择存活的己方脑光墓碑",None
            x=grave["x"]+p["facing"]*42;y=grave["y"]
            if c.get("aquatic"):
                exit_position=self._aquatic_exit(c,team,grave,p["facing"])
                if exit_position is None:return "水生僵尸需要墓碑前方两格内可达的水面出兵口",None
            else:exit_position=self._grave_soldier_exit(c,team,grave,p["facing"])
            if exit_position is None:return "墓碑出兵口被地形或敌方单位阻挡",None
            x,y=exit_position
            return "",dict(card=c,charge=charge,x=x%self.width,y=y,slot=key,temporary=bool(copy_id))
        if c["behavior"] in ("coffee",):
            targets=[u for u in self.units.values() if u["hp"]>0 and u["side"]==team and u["card"].get("mushroom") and abs(wrap_delta(x,u["x"],self.width))<40 and abs(y-u["y"]+20)<60]
            if not targets:return "请选择己方蘑菇",None
            return "",dict(card=c,charge=charge,target=targets[0]["id"],slot=key)
        if c["behavior"]=="stone":
            xx=(math.floor(x/self.tile)+.5)*self.tile%self.width;yy=(math.floor(y/self.tile)+.5)*self.tile
            if yy<0 or yy>=self.height:return "不能在地图外修地形",None
            if self.cell(xx,yy).get("solid"):return "此处已有实体地形",None
            probe=dict(x=xx,y=yy+self.tile/2,w=self.tile,h=self.tile)
            if any(self._overlaps(probe,u) for u in list(self.units.values())+list(self.players.values())):return "修复位置被占用",None
            return "",dict(card=c,charge=charge,x=xx,y=yy,slot=key)
        spot=self._grave_surface_y(x,y) if c["behavior"]=="grave" else self.surface_y(x,y)
        if not spot:return "需要可放置的地面",None
        x,y,water=spot
        if c['behavior']=='grave' and self.cell(x,y-1).get('water'):
            return '不能在水下地面布置墓碑，请选择水面或陆地',None
        vines=[]
        if c['behavior']=='grave':
            # A petrified vine is a shell: it may wrap one own grave, and a
            # grave may be set into it - on water too, where it floats the
            # grave like a lily pad does a plant.
            footprint=dict(x=x,y=y,w=32,h=40)
            stacked=[u for u in self.units.values() if u["hp"]>0 and u["side"]==team
                     and u["behavior"]=="grave" and self._overlaps(footprint,u)]
            vines=[u for u in stacked if u["card"].get("shell")]
            if c.get('shell') and vines:return '此处已有石化藤蔓',None
            if c.get('grave_surface')=='land' and water and not vines:return '地面墓碑不能放在水面，请选择水上墓碑',None
            if c.get('grave_surface')=='water' and not water:return '水上墓碑只能放在水面',None
        support=[u for u in self.units.values() if abs(wrap_delta(x,u["x"],self.width))<self.tile*.65 and abs(y-u["y"])<self.tile*1.2 and u["hp"]>0]
        bases=[u for u in support if u["side"]==team and u["behavior"] in ("pot","lily")]
        occupants=[u for u in support if u["behavior"] not in ("pot","lily") and not u.get("mobile")]
        if c["behavior"]=="grave":
            footprint=dict(x=x,y=y,w=32,h=40)
            occupants=[u for u in self.units.values() if u["hp"]>0 and not u.get("mobile")
                       and self._overlaps(footprint,u)]
            if c.get('shell'):
                occupants=[u for u in occupants if not (u["side"]==team and u["behavior"]=="grave")]
            elif vines and not [u for u in occupants if u not in vines and u["side"]==team and u["behavior"]=="grave"]:
                occupants=[u for u in occupants if u not in vines]
        shells=[u for u in occupants if u["card_id"]=="plant:南瓜头" and u["side"]==team]
        if c["id"]=="plant:南瓜头":
            if shells:return "已有南瓜头保护容器",None
            if any(u["side"]!=team for u in occupants):return "位置已有敌方单位",None
            occupants=[]
        else:occupants=[u for u in occupants if u not in shells]
        if c["behavior"]=="lily" and not water:return "睡莲需要水面",None
        if c.get("aquatic") and not water:return "水生植物需要水面",None
        if team=="plant" and water and not c.get("aquatic") and c["behavior"]!="lily" and not any(u["behavior"]=="lily" for u in bases):return "水面需要睡莲",None
        if c["behavior"] in ("pot","lily"):
            if bases:return "已有承载植物",None
        elif occupants:return "位置已有单位",None
        # Native hard material needs a flowerpot unless the chosen secret supplies soil.
        kind=self.cell(x,y+2).get("kind","")
        natural=kind in ("土","草","沙","沙土","沙草","雪","空","水")
        if team=="plant" and not water and not natural and c["behavior"] not in ("pot","gravebuster") and not bases and "secret:无土栽培" not in p["secrets"]:return "坚实地面需要花盆或无土栽培",None
        if self._blocked(dict(w=32,h=40),x,y):return "地面上方空间不足",None
        return "",dict(card=c,charge=charge,x=x,y=y,slot=key,temporary=bool(copy_id))

    def deploy(self,side,key,x,y,grave_id=None,copy_id=None,facing=None):
        error,plan=self.placement(side,key,x,y,grave_id,copy_id)
        if error:return error
        p=self.players[side];c=plan["card"];entity=None;target=None
        direction=p["facing"] if facing is None else facing
        if c["behavior"]=="stone":
            row=int(plan["y"]/self.tile);col=int(plan["x"]/self.tile)
            self.map["tiles"][row][col]=dict(kind="石",solid=True,water=False,ladder=False,background="")
            self.terrain_revision+=1
        elif c["behavior"]=="coffee":
            target=self.units[plan["target"]];target["coffee_until"]=self.time+20.;target["awake"]=True
        else:
            entity=self.spawn(c,side,plan["x"],plan["y"],direction,temporary=plan.get("temporary",False))
            if entity is None:return "无法创建此单位"
        p["resource"]-=plan["charge"];p["stats"]["spent"]+=plan["charge"]
        p["cooldowns"][key]=self.time+self._card(side,key)["cooldown"]
        self._emit("deploy",side=side,card=key,charge=plan["charge"],
                   entity=entity["id"] if entity else None,actual_card=c["id"],
                   target=target["id"] if target else None,
                   x=plan.get("x",target["x"] if target else None),
                   y=plan.get("y",target["y"] if target else None),
                   grave=grave_id if side=="zombie" and c["behavior"]!="grave" else None,
                   copy=copy_id if CARDS[key]["behavior"]=="copy" else None,
                   facing=direction,source_entity=side)
        return ""

    def spawn(self,card,side,x,y,facing=1,temporary=False,parent=None,parent_attack=None):
        c=apply_secret_effects(CARDS[card] if isinstance(card,str) else card,self.players[side]["secrets"])
        if not allowed(c["id"],self.bans,for_spawn=True):return None
        if self.deathmatch and deathmatch_blocked(c):return None
        if len(self.units)>=700:return None
        hp=float(c["hp"])
        uid=self._id("u")
        lineage=self._provenance(parent)
        u=dict(id=uid,card=c,card_id=c["id"],side=side,owner=side,current_owner=side,
               original_owner=side,native_side=c["side"],source_entity=uid,
               parent_entity=parent.get("id") if isinstance(parent,dict) else None,
               root_source=lineage["root_source"] or uid,
               root_original_owner=lineage["root_original_owner"] or side,parent_attack=parent_attack,
               x=float(x)%self.width,y=float(y),
               w=34.,h=float(c.get("height",44)),vx=0.,vy=0.,hp=hp,max_hp=hp,
               facing=facing,behavior=c["behavior"],born=self.time,attack_at=self.time+.4,
               progress=0.,grounded=False,slow_until=0.,control_until=0.,coffee_until=0.,
               awake=True,temporary=temporary,mobile=c.get("speed",0)>0,flying=c.get("flying",False),
               burrowed=c.get("burrow",False),vaulted=False,death_done=False,killer=None,
               ladder_placed=False,imp_thrown=False,marked_until=0.,air_until=0.,air_vx=0.,
               knock_until=0.,knock_vx=0.,ability_at=self.time+.4,
               armor_hp=float(c.get("armor",0)),armor_max=float(c.get("armor",0)))
        if u["flying"]:u["y"]-=100
        if c["id"]=="plant:南瓜头":u["w"]=46.
        self.units[uid]=u;self._actor_cache=None
        if not u["mobile"] and c["behavior"] not in ("pot","lily"):
            if c["id"]=="plant:南瓜头":
                for child in self.units.values():
                    if (child is not u and child["side"]==side and not child["mobile"] and child["hp"]>0
                            and child["behavior"] not in ("pot","lily") and child["card_id"]!="plant:南瓜头"
                            and abs(wrap_delta(child["x"],u["x"],self.width))<self.tile*.45
                            and abs(child["y"]-u["y"])<6):child["container_id"]=uid
            else:
                shell=next((other for other in self.units.values() if other["side"]==side and other["hp"]>0
                            and other["card_id"]=="plant:南瓜头"
                            and abs(wrap_delta(other["x"],u["x"],self.width))<self.tile*.45
                            and abs(other["y"]-u["y"])<6),None)
                if shell:u["container_id"]=shell["id"]
        if c["behavior"] in ("torch","umbrella"):
            self._interceptors=None
            self._interceptor_range=max(self._interceptor_range,c["range"] if c["behavior"]=="umbrella" else u["h"])
        self._max_actor_radius=max(self._max_actor_radius,u["h"]/2.+6)
        self._index_actor(u)
        self._emit("spawn",entity=uid,card=c["id"],side=side,temporary=temporary,x=u["x"],y=u["y"],**self._provenance(u))
        return u

    def command_input(self,side,payload):
        if self.audit_error:return self.audit_error
        error=self._command_input(side,payload)
        if error:return error
        kind=payload["type"];fields={}
        if kind=="move":fields=dict(move=self.players[side]["input"]["move"],jump=self.players[side]["jump_held"])
        elif kind=="deploy":
            fields=dict(card=payload["card"],x=payload["x"],y=payload["y"])
            if "facing" in payload:fields["facing"]=payload["facing"]
            if side=="zombie" and CARDS[payload["card"]]["behavior"]!="grave":fields["grave"]=payload.get("grave")
            if CARDS[payload["card"]]["behavior"]=="copy":fields["copy"]=payload.get("copy")
        elif kind=="command":fields["mode"]=self.command_for(side)
        elif kind=="rally":fields["point"]=deepcopy(self.rally_for(side))
        elif kind=="collect":fields["resource"]=payload["resource"]
        elif kind=="mark":fields["target"]="zombie"
        elif kind=="cannon":fields=dict(x=payload.get("x"),y=payload.get("y"))
        elif kind=="shovel":fields=dict(x=payload['x'],y=payload['y'],right=payload.get('right',False))
        elif kind=="teleport":fields=dict(target=payload['target'])
        elif kind=="wake":fields=dict(grave=payload['grave'])
        elif kind=="select_grave":fields=dict(grave=payload['grave'])
        elif kind=="detonate":fields=dict(target=payload['target'])
        elif kind=="turn":fields=dict(target=payload['target'],facing=payload['facing'])
        elif kind in ('surrender','surrender_accept','surrender_decline','surrender_cancel'):
            if self.result:fields['winner']=self.result['winner']
            if 'request' in payload:fields['request']=payload['request']
        # Only accepted, semantically validated fields enter the audit log.
        # This deliberately bypasses the bounded UI event queue: frequent
        # movement input must not evict death, damage or match-result events.
        self.log.append(dict(event="input",tick=self.tick,time=round(self.time,4),
                             side=side,seq=payload["seq"],kind=kind,accepted=True,**fields))
        return ""

    def _command_input(self,side,payload):
        if side not in self.players or not isinstance(payload,dict):return "输入格式错误"
        p=self.players[side];seq=payload.get("seq")
        if not isinstance(seq,int) or isinstance(seq,bool) or seq<0 or seq>2**53:return "序号错误"
        if seq<=p["seq"]:return "旧输入"
        p["seq"]=seq;p["last_input_tick"]=self.tick
        kind=payload.get("type")
        if self.result:return "对局已结束"
        if kind=="turn":
            handler=getattr(self,'turn_plant',None)
            return handler(side,payload.get('target'),payload.get('facing')) if handler else "当前引擎不支持转向"
        if kind=="detonate":
            handler=getattr(self,'detonate_clown',None)
            return handler(side,payload.get('target')) if handler else "当前引擎不支持手动引爆"
        if kind=="select_grave":
            handler=getattr(self,'select_grave',None)
            return handler(side,payload.get('grave')) if handler else "当前引擎不支持选择墓碑"
        if kind=="wake":
            handler=getattr(self,'wake_grave',None)
            return handler(side,payload.get('grave')) if handler else "当前引擎不支持唤醒墓碑"
        if kind=="teleport":
            handler=getattr(self,'teleport_hero',None)
            return handler(side,payload.get('target')) if handler else "当前引擎不支持传送"
        if kind=="move":
            move=payload.get("move",0)
            if isinstance(move,bool) or not isinstance(move,int) or move not in (-1,0,1):return "方向无效"
            if not isinstance(payload.get("jump",False),bool):return "跳跃状态无效"
            p["input"]["move"]=move
            jump=bool(payload.get("jump",False))
            if jump and not p["jump_held"] and p["grounded"] and self.time>=p["control_until"]:
                p["vy"]=-self.rules["hero_jump"];p["grounded"]=False
            p["jump_held"]=jump;return ""
        if kind=="deploy":
            if "facing" in payload:
                facing=payload["facing"]
                if isinstance(facing,bool) or not isinstance(facing,int) or facing not in (-1,1):return "部署方向无效"
                return self.deploy(side,payload.get("card"),payload.get("x"),payload.get("y"),payload.get("grave"),payload.get("copy"),facing=facing)
            return self.deploy(side,payload.get("card"),payload.get("x"),payload.get("y"),payload.get("grave"),payload.get("copy"))
        if kind=="rally":
            if team_of(side)!="zombie":return "只有僵尸方可召集"
            if payload.get("clear") is True:
                self.set_rally(side, None)
            else:
                x,y=payload.get("x"),payload.get("y")
                if not finite(x) or not finite(y) or not 0<=x<self.width or not 0<=y<self.height:return "召集点坐标无效"
                self.set_rally(side, dict(x=(int(x//self.tile)+.5)*self.tile,y=(int(y//self.tile)+.5)*self.tile))
            self._emit("rally",side=side,point=deepcopy(self.rally_for(side)));return ""
        if kind=="command":
            if team_of(side)!="zombie":return "只有僵尸方可指挥"
            if self.mode != DUO and self.rally_point is not None:
                self.rally_point=None
                self._emit("rally",side=side,point=None);return ""
            mode="attack" if self.command_for(side)=="follow" else "follow"
            if self.mode == DUO:self.commands[side]=mode
            if side == "zombie" or self.mode != DUO:self.command=mode
            self._emit("command",mode=mode,side=side,seq=seq);return ""
        if kind=="collect":
            if team_of(side)!="plant":return "脑光由系统自动收集"
            rid=payload.get("resource")
            if not isinstance(rid,str):return "资源编号无效"
            r=self.resources.get(rid)
            shared=bool(r and r.get("shared") and team_of(r["side"])=="plant")
            if not r or (r["side"]!=side and not shared):return "资源已收集或不存在"
            if self.team_mode and p["hp"]<=0:return "戴夫已阵亡，等待队友复活"
            if self.time<p.get("collect_locked_until",0.):
                return "黄金蓓蕾放置后%.1f秒内只能由戴夫肉身拾取阳光"%(p["collect_locked_until"]-self.time)
            if shared:self._collect(rid,side);return ""
            self._collect(rid);return ""
        if kind=="mark":
            if team_of(side)!="plant":return "只有植物方可标记"
            target=self.players["zombie"]
            if self.distance(p,target)>self.rules["hero_lock_range"] or not self.line_of_sight(p,target):return "目标超出标记范围或被地形遮挡"
            target["marked_until"]=self.time+self.rules["mark_seconds"];return ""
        if kind in ("cannon","cannon_cancel") and hasattr(self,"native_cannon"):
            return self.native_cannon(side,payload.get("x"),payload.get("y"),kind=="cannon_cancel")
        if kind=='shovel' and hasattr(self,'native_shovel'):
            return self.native_shovel(side,payload.get('x'),payload.get('y'),payload.get('right',False))
        if kind in ('surrender','surrender_accept','surrender_decline','surrender_cancel'):
            if side not in self.present:return '观众不能投降'
            team=team_of(side)
            mates=[s for s in self.seats if team_of(s)==team and s!=side]
            if mates:
                request=self.surrender_requests.get(team)
                if request and self.time>=request['expires']:
                    self.surrender_requests.pop(team,None);request=None
                if kind=='surrender':
                    if request:return '已有投降请求，请队友选择同意或拒绝'
                    self.surrender_serial+=1
                    self.surrender_requests[team]=dict(id=self.surrender_serial,seat=side,expires=self.time+20.)
                    self._emit('surrender_requested',side=side,request=self.surrender_serial)
                    return ''
                if not request or payload.get('request')!=request['id']:return '投降请求已失效'
                if kind=='surrender_cancel':
                    if request['seat']!=side:return '只有发起人可以撤回'
                elif request['seat']==side:return '请等待队友确认'
                self.surrender_requests.pop(team,None)
                self._emit('surrender_vote',side=side,request=request['id'],accepted=kind=='surrender_accept')
                if kind!='surrender_accept':return ''
            elif kind!='surrender':return '当前没有队友投降请求'
            self.result=dict(winner="zombie" if team_of(side)=="plant" else "plant",reason="surrender",tick=self.tick)
            self._emit("result",**self.result);return ""
        if kind=="gift":
            # Co-op / 2v2: a player may hand part of their own economy to a
            # teammate (user request 10-14).  Own resource only, teammate only.
            mates=[s for s in self.seats if team_of(s)==team_of(side) and s!=side]
            if not mates:return "没有可资助的队友"
            amount=payload.get("amount")
            if isinstance(amount,bool) or not isinstance(amount,int) or amount<=0:return "资助数量无效"
            if amount>GIFT_MAX:return "单次最多资助 %d" % GIFT_MAX
            if self.mode==DUO and self.time<p.get("gift_ready_at",0.):return "资助冷却中"
            if p["resource"]<amount:return "资源不足"
            mate=min(mates,key=lambda seat:abs(self.players[seat]["x"]-p["x"]))
            p["resource"]-=amount;p["stats"]["spent"]=p["stats"].get("spent",0)
            self.players[mate]["resource"]+=amount
            self.players[mate]["stats"]["earned"]=self.players[mate]["stats"].get("earned",0)+amount
            p["gift_ready_at"]=self.time+(GIFT_COOLDOWN if self.mode==DUO else 0.)
            self._emit("gift",side=side,to=mate,amount=amount)
            return ""
        return "未知战斗命令"

    def clear_input(self,side):
        self.players[side]["input"]={"move":0};self.players[side]["jump_held"]=False

    def _collect(self,rid):
        r=self.resources.pop(rid,None)
        if not r:return
        p=self.players[r["side"]];p["resource"]+=r["amount"];p["stats"]["earned"]+=r["amount"]
        self._emit("income",side=r["side"],amount=r["amount"],source=r["source"],resource_id=rid)

    def resource(self,side,amount,x,y,source):
        rid=self._id("r");self.resources[rid]=dict(id=rid,side=side,amount=amount,x=x%self.width,y=y,born=self.time,source=source)
        if team_of(side)=="zombie":self._collect(rid)
        return rid

    def targets(self,side,center=None,radius=None):
        enemy="zombie" if side=="plant" else "plant"
        source=self._nearby(center,radius) if center is not None and radius is not None else (self._actor_cache if self._actor_cache is not None else tuple(self.players.values())+tuple(self.units.values()))
        # Freeze recipients before applying the first hit. Otherwise killing a
        # shell can expose its child halfway through the same area explosion,
        # depending on which was planted first.
        visible=[target for target in source if target["side"]==enemy and target["hp"]>0
                 and not target.get("burrowed") and self._container(target) is None]
        yield from visible

    def hero_lock(self,attacker,hero):
        return hero.get("marked_until",0)>self.time and self.distance(attacker,hero)<=self.rules["hero_lock_range"] and self.line_of_sight(attacker,hero)

    def _target(self,u):
        c=u["card"];candidates=[]
        if c.get("spread"):
            return next((target for unused,target in self._tripea_targets(u) if target is not None),None)
        for t in self.targets(u["side"],u,c["range"]):
            dx=wrap_delta(u["x"],t["x"],self.width)
            dy=(u["y"]-u.get("h",0)/2.)-(t["y"]-t.get("h",0)/2.)
            distance_squared=dx*dx+dy*dy
            if distance_squared>c["range"]*c["range"]:continue
            if c.get("homing") and t["id"] in self.players:
                if t.get("marked_until",0)<=self.time or distance_squared>self.rules["hero_lock_range"]**2:continue
            if t.get("flying") and not (c.get("anti_air") or c.get("lob") or c.get("homing")):continue
            if not (c.get("radial") or c.get("homing") or c.get("star") or c.get("rear_burst") or u["mobile"]) and dx*u["facing"]<0:continue
            if c["behavior"]=="gravebuster" and t.get("behavior")!="grave":continue
            if c["behavior"]=="charm" and t["id"] not in self.players and not t.get("mobile"):continue
            if c["behavior"] in ("bite","chomp","gravebuster","squash","mine","spike") and abs(u["y"]-t["y"])>70:continue
            candidates.append((distance_squared,t))
        # Visibility of distant candidates cannot change a nearer valid
        # target. Check nearest first instead of raycasting the entire army.
        for unused,t in sorted(candidates,key=lambda pair:pair[0]):
            if (c.get("lob") and not c.get("homing")) or self.line_of_sight(u,t):return t
        return None

    def damage(self,target,amount,side,attack_id,kind="normal",control=0.,slow=0.,knock=0,origin=None):
        if not target or target["hp"]<=0 or target["side"]==side:return 0.
        target=self._container(target) or target
        if side not in self.players or not finite(amount):return 0.
        amount=max(0.,float(amount));hero=target["id"] in self.players
        can_control=not hero or self.time>=target["immune_until"]
        if hero and kind in ("ash","chomp","crush"):
            group=(target["id"],attack_id);used=self.damage_groups.get(group,(0.,self.time))[0]
            amount=min(amount,max(0.,target["max_hp"]*self.rules["hero_ash_cap"]-used))
            self.damage_groups[group]=(used+amount,self.time)
        applied=min(target["hp"],amount);target["hp"]-=applied
        if hero:
            self.players[side]["stats"]["hero_damage"]+=applied
            if side=="plant" and applied:target["marked_until"]=self.time+self.rules["mark_seconds"]
            if control and can_control:
                target["control_until"]=self.time+min(control,self.rules["hero_control_max"])
                target["immune_until"]=target["control_until"]+self.rules["hero_control_immunity"]
        else:
            if target.get("armor_hp",0)>0:
                target["armor_hp"]=max(0.,target["armor_hp"]-applied)
                if target["armor_hp"]<=0:
                    target["max_hp"]=max(target["hp"],target["max_hp"]-target.get("armor_max",0))
                    target["armor_max"]=0.;target["card"]["armor"]=0
            if control:target["control_until"]=max(target.get("control_until",0),self.time+control)
            if slow:target["slow_until"]=max(target.get("slow_until",0),self.time+slow)
        if knock and can_control:
            # A bounded impulse survives the next input update; immunity to a
            # second control event also covers its accompanying knockback.
            target["knock_vx"]=knock;target["knock_until"]=self.time+.25
            target["vx"]=knock;target["vy"]=-100.
            if hero and not control:target["immune_until"]=self.time+.25+self.rules["hero_control_immunity"]
        if target["hp"]<=0:
            target["killer"]=side;target["death_kind"]=kind
            target["death_overkill"]=amount-applied
            target["fatal_attack"]=attack_id;target["fatal_source"]=self._provenance(origin,side)
        if applied:self._emit("damage",target=target["id"],source=side,attack=attack_id,amount=round(applied,2),kind=kind,**self._provenance(origin,side))
        return applied

    def explode(self,u,attack_id=None):
        if u.get("death_done"):return
        u["death_done"]=True;c=u["card"];aid=attack_id or self._id("a")
        origin=dict(u,parent_attack=u.get("fatal_attack",u.get("parent_attack")))
        radius=c["range"]
        chili=c["behavior"]=="chili" or "辣椒" in c["name"]
        for t in self.targets(u["side"],u,radius):
            hit=abs(wrap_delta(u["x"],t["x"],self.width))<=radius and abs(u["y"]-t["y"])<65 if chili else self.distance(u,t)<=radius
            if hit:self.damage(t,c["damage"],u["side"],aid,"ash",origin=origin)
        if c["behavior"]=="doom" or "毁灭菇" in c["name"]:
            # Local crater only, shared by preview, simulation and snapshots.
            for dy in (0,1):
                row=int(u["y"]/self.tile)+dy
                if 0<=row<len(self.map["tiles"])-1:
                    for dx in (-1,0,1):
                        col=(int(u["x"]/self.tile)+dx)%len(self.map["tiles"][row])
                        self.map["tiles"][row][col]=dict(kind="空",solid=False,water=False,ladder=False,background="")
            self.terrain_revision+=1
        self._emit("explosion",x=u["x"],y=u["y"],radius=radius,side=u["side"],attack=aid,**self._provenance(origin))

    def _projectile(self,u,target,aid,angle=None,damage=None):
        if len(self.projectiles)>=1400:return
        c=u["card"];x=u["x"];y=u["y"]-u["h"]*.6
        dx=wrap_delta(x,target["x"],self.width);dy=target["y"]-target.get("h",44)*.55-y
        speed=390.;duration=max(.22,min(2.,math.hypot(dx,dy)/speed))
        vx=dx/duration;vy=dy/duration;gravity=0.
        if c.get("lob") or c["behavior"] in ("lob","cannon"):
            gravity=500.;duration=max(.65,min(2.,abs(dx)/300.));vx=dx/duration;vy=(dy-.5*gravity*duration*duration)/duration
        if angle is not None:vx=math.cos(angle)*speed;vy=math.sin(angle)*speed
        pid=self._id("p")
        self.projectiles[pid]=dict(id=pid,x=x,y=y,vx=vx,vy=vy,gravity=gravity,
            side=u["side"],owner=u["owner"],source=u["id"],attack=aid,damage=c["damage"] if damage is None else damage,
            lock_origin=dict(x=u["x"],y=u["y"],h=u["h"]),
            born=self.time,lifetime=4.,target=target["id"] if c.get("homing") else None,
            homing=bool(c.get("homing")),splash=c.get("splash",0),pierce=c.get("pierce",False),
            slow=c.get("slow",0),control=0.,hits=[],torch=[],hero_cap=c.get("hero_cap",False),
            kind="ash" if c["behavior"]=="cannon" else "normal",asset="冰豆" if c.get("slow") else ("卷心菜" if c.get("lob") else "豌豆"))
        self.projectiles[pid].update(self._provenance(u))
        self.projectiles[pid].pop("reflection_chain",None)
        if c.get("projectile_asset"):self.projectiles[pid]["asset"]=c["projectile_asset"]
        if c.get("butter") and self.rng.random()<(.5 if "secret:黄油" in self.players[u["side"]]["secrets"] else .25):
            self.projectiles[pid].update(control=2.,damage=40.,asset="黄油")
        return self.projectiles[pid]

    def _tripea_targets(self,u):
        """Native three-head offsets and independent forward target ranking."""
        fractions=((.36,.16),(.55,.38),(.73,.60))
        used=set();result=[];c=u["card"]
        for fx,fy in fractions:
            if u["facing"]<0:fx=1.-fx
            head=dict(x=(u["x"]+(fx-.5)*self.tile)%self.width,y=u["y"]+(fy-1.)*self.tile,h=0)
            ranked=[]
            for target in self.targets(u["side"],head,c["range"]):
                dx=wrap_delta(head["x"],target["x"],self.width)
                if dx*u["facing"]< -1.:continue
                distance=self.distance(head,target)
                if distance<=c["range"]:ranked.append((distance,target))
            ranked.sort(key=lambda pair:pair[0]);valid=[]
            for unused,target in ranked:
                if self.line_of_sight(head,target):valid.append(target)
            chosen=next((target for target in valid if target["id"] not in used),valid[0] if valid else None)
            if chosen:used.add(chosen["id"])
            result.append((head,chosen))
        return result

    def _attack(self,u,t):
        c=u["card"];b=u["behavior"];aid=self._id("a")
        if c.get("rear_burst"):
            self._split_attack(u);return
        if b in ("bite","gravebuster","chomp","spike"):
            kind="chomp" if b=="chomp" else ("crush" if c.get("heavy") else "normal")
            self.damage(t,c["damage"],u["side"],aid,kind,origin=u)
            if t.get("behavior")=="garlic":
                u["facing"]*=-1;u["retreat_until"]=self.time+(3. if "secret:体香" in self.players[t["side"]]["secrets"] else 1.)
            return
        if c.get("spread"):
            targets=self._tripea_targets(u)
            u["head_targets"]=[];u["head_angles"]=[]
            for index,(head,target) in enumerate(targets):
                u["head_targets"].append(target["id"] if target else None)
                if target is None:u["head_angles"].append(None);continue
                fake=dict(u,x=head["x"],y=head["y"],h=0)
                shot=self._projectile(fake,target,aid)
                if shot:
                    shot["head_index"]=index;shot["intended_target"]=target["id"]
                    u["head_angles"].append(math.atan2(shot["vy"],shot["vx"]))
            return
        if c.get("radial"):
            for other in self.targets(u["side"],u,c["range"]):
                if self.distance(u,other)<=c["range"] and self.line_of_sight(u,other):self.damage(other,c["damage"],u["side"],aid,slow=c.get("slow",0),origin=u)
            return
        if c.get("chain"):
            candidates=sorted((t for t in self.targets(u["side"],u,c["range"]) if self.line_of_sight(u,t)),key=lambda other:self.distance(u,other))
            for other in candidates[:c["chain"]]:
                if self.distance(u,other)<=c["range"]:self.damage(other,c["damage"],u["side"],aid,origin=u)
            return
        if c.get("star"):
            angles=[-math.pi*.75,-math.pi*.25,0.,math.pi*.25,math.pi*.75]
            if "secret:大帝" in self.players[u["side"]]["secrets"]:angles.extend([a+.15 for a in list(angles)])
            for a in angles:self._projectile(u,t,aid,a if u["facing"]>0 else math.pi-a)
            return
        count=c.get("burst",1)
        if c.get("rear_burst") and wrap_delta(u["x"],t["x"],self.width)*u["facing"]<0:count=c["rear_burst"]
        for i in range(count):
            self._projectile(u,t,aid)
            if count>1:
                p=self.projectiles.get("p"+str(self.ids))
                if p:p["x"]=(p["x"]-i*12*u["facing"])%self.width

    def _split_attack(self,u):
        if self.time<u["control_until"] or not u.get("awake",True):return
        c=u["card"]
        for rear in (False,True):
            timer="rear_attack_at" if rear else "attack_at"
            if self.time<u.get(timer,u["born"]+.4):continue
            head_card=dict(c);head_card.pop("rear_burst",None)
            if rear:head_card["range"]=c.get("rear_range",c["range"])
            head=dict(u,card=head_card,facing=-u["facing"] if rear else u["facing"])
            target=self._target(head)
            if target is None:continue
            aid=self._id("a")
            for index in range(c["rear_burst"] if rear else 1):
                shot=self._projectile(head,target,aid)
                if shot:
                    shot["x"]=(shot["x"]-index*12*head["facing"])%self.width
                    shot["head_index"]=1 if rear else 0;shot["intended_target"]=target["id"]
            u[timer]=self.time+c["interval"]/(1.25 if u["coffee_until"]>self.time else 1.)

    def _remove_metal(self,u,side,aid,origin=None):
        armor=u.get("armor_hp",0.)
        if armor:self.damage(u,armor,side,aid,origin=origin)
        u["disarmed"]=True;u["card"]["metal"]=False
        u["card"]["pogo"]=False;u["card"]["ladder"]=False

    def _service_ability(self,u):
        """Service plant-zombies retain the current patch's ability families.

        Numbers come from the independent PvP card definition. The native
        lantern heals (it has no laser); the gold magnet gives a bucket, or
        removes enemy metal after charm. Neither creates economy.
        """
        c=u["card"];b=u["behavior"]
        if b not in ("blover","lantern_zombie","gold_magnet","umbrella"):return False
        if self.time<u["ability_at"] or self.time<u["control_until"]:return True
        aid=self._id("a");affected=[]
        if b=="lantern_zombie":
            for target in self.units.values():
                if target["side"]!=u["side"] or target["hp"]<=0 or self.distance(u,target)>c["range"] or not self.line_of_sight(u,target):continue
                heal=min(c.get("heal_amount",40),target["max_hp"]-target["hp"])
                if heal>0:target["hp"]+=heal;affected.append(target["id"])
        elif b=="gold_magnet":
            if u["side"]=="zombie":
                choices=[t for t in self.units.values() if t is not u and t["side"]==u["side"]
                         and t["hp"]>0 and t["mobile"] and t.get("armor_hp",0)<=0
                         and self.distance(u,t)<=c["range"] and self.line_of_sight(u,t)]
                if choices:
                    target=min(choices,key=lambda t:self.distance(u,t));armor=c.get("armor_grant",300)
                    target["armor_hp"]=target["armor_max"]=float(armor)
                    target["hp"]+=armor;target["max_hp"]+=armor
                    target["card"].update(armor=armor,metal=True);target["disarmed"]=False
                    affected.append(target["id"])
            else:
                choices=[t for t in self.targets(u["side"]) if t.get("card",{}).get("metal")
                         and not t.get("disarmed") and self.distance(u,t)<=c["range"] and self.line_of_sight(u,t)]
                if choices:
                    target=min(choices,key=lambda t:self.distance(u,t));self._remove_metal(target,u["side"],aid,origin=u);affected.append(target["id"])
        else:
            for p in list(self.projectiles.values()):
                point=dict(x=p["x"],y=p["y"],h=0)
                if p["side"]==u["side"] or self.distance(u,point)>c["range"] or not self.line_of_sight(u,point):continue
                if b=="blover":
                    if wrap_delta(u["x"],p["x"],self.width)*u["facing"]<-.25*self.tile:continue
                    p["vx"]=u["facing"]*max(260.,abs(p["vx"])+80.)
                else:
                    if not p["gravity"] or u["id"] in p.get("reflections",[]):continue
                    p.setdefault("reflections",[]).append(u["id"])
                    p["vx"]=-p["vx"] if abs(p["vx"])>.01 else u["facing"]*260.
                    p["side"]=u["side"];p["owner"]=u["side"];p["source"]=u["id"]
                    p["current_owner"]=u["side"];p["reflected_by"]=u["id"]
                    p["hits"]=[];p["lock_origin"]=dict(x=u["x"],y=u["y"],h=u["h"])
                    self._emit("projectile_reflect",projectile=p["id"],attack=p["attack"],side=p["side"],**self._provenance(p))
                p["target"]=None;p["homing"]=False;affected.append(p["id"])
            for target in self.targets(u["side"]):
                if target["id"] not in self.players and not target.get("mobile"):continue
                if self.distance(u,target)>c["range"] or not self.line_of_sight(u,target):continue
                dx=wrap_delta(u["x"],target["x"],self.width)
                if b=="blover" and dx*u["facing"]<0:continue
                direction=u["facing"] if b=="blover" else (1 if dx>=0 else -1)
                self.damage(target,0,u["side"],aid,control=.25,knock=direction*180.,origin=u)
                affected.append(target["id"])
        if affected:
            u["ability_at"]=self.time+c["interval"]
            self._emit("ability",source=u["id"],side=u["side"],ability=b,targets=affected,attack=aid,**self._provenance(u))
        else:u["ability_at"]=self.time+.15
        return True

    def _update_unit(self,u,dt):
        c=u["card"];age=self.time-u["born"];b=u["behavior"]
        if c.get("lifetime") and age>=c["lifetime"]:u["hp"]=0;return
        if not u["mobile"]:
            # Supports may be destroyed or terrain repaired; plants retain gravity.
            self._move(u,dt)
        if not u.get("awake",True):return
        if c.get("producer"):
            u["progress"]+=dt*(self.rules["production_multiplier"] if self.deathmatch else 1.)/c["period"]
            while u["progress"]>=1.-1e-10:
                amount=c.get("mature_yield",c["yield_amount"]) if age>=c.get("mature_at",1e30) else c["yield_amount"]
                self.resource(u["side"],amount,u["x"],u["y"]-50,u["id"]);u["progress"]=max(0.,u["progress"]-1.)
            return
        if b in ("pot","lily","wall","garlic","torch","grave"):return
        if b in ("ash","doom","chili","freeze","wind") and age>=c.get("fuse",1.):
            if b=="freeze":
                aid=self._id("a")
                for t in self.targets(u["side"]):
                    if self.distance(u,t)<=c["range"]:self.damage(t,20,u["side"],aid,control=3.,slow=5.,origin=u)
            elif b=="wind":
                aid=self._id("a")
                for t in self.targets(u["side"]):
                    if t.get("flying") and self.distance(u,t)<=c["range"]:self.damage(t,1800,u["side"],aid,"ash",origin=u)
            else:self.explode(u)
            u["hp"]=0;return
        if b=="suicide" and age>=c.get("fuse",12.):self.explode(u);u["hp"]=0;return
        if u["mobile"]:
            hero=self.players[u["side"]] if self.command_for(u)=="follow" and u["side"]=="zombie" else self.players["zombie" if u["side"]=="plant" else "plant"]
            dx=wrap_delta(u["x"],hero["x"],self.width)
            if abs(dx)>45 and self.time>=u.get("retreat_until",0):u["facing"]=1 if dx>0 else -1
            target=self._target(u)
            stop=bool(target and (not c.get("burrow") or not u["burrowed"]))
            service=b in ("blover","lantern_zombie","gold_magnet","umbrella")
            if service or self.time<u.get("retreat_until",0):stop=False
            if stop and u["behavior"] in ("bite","thief","squash") and self.distance(u,target)>c["range"]:stop=False
            speed=c.get("speed",0)*(1.7 if c.get("rage") and u["hp"]<u["max_hp"]*.5 else 1.)
            if u["slow_until"]>self.time:speed*=.5
            if self.time<u["control_until"]:speed=0.
            if self.command_for(u)=="follow" and u["side"]=="zombie" and abs(dx)<65 and not target:speed=0.
            u["vx"]=0. if stop else speed*u["facing"]
            front=dict(x=(u["x"]+u["facing"]*26)%self.width,y=u["y"],w=32,h=u["h"])
            blocker=next((p for p in self._nearby(front,self._max_actor_radius+u["h"]/2.+32) if p["id"] not in self.players and p is not u and p["hp"]>0 and p["side"]!=u["side"] and self._overlaps(front,p) and p["behavior"] not in ("spike","mine","pot","lily")),None)
            if blocker:
                if c.get("vault") and not u["vaulted"] and blocker["h"]<80 and u["grounded"]:
                    u["vy"]=-410.;u["air_vx"]=145*u["facing"];u["air_until"]=self.time+.7;u["vaulted"]=True
                elif c.get("pogo") and u["grounded"]:
                    u["vy"]=-420.;u["air_vx"]=85*u["facing"];u["air_until"]=self.time+.7
                elif c.get("ladder") or blocker.get("ladder"):
                    if c.get("ladder"):blocker["ladder"]=True;u["ladder_placed"]=True
                    u["x"]=(blocker["x"]-u["facing"]*((u["w"]+blocker["w"])/2.+1))%self.width
                    u["vy"]=-160.;u["vx"]=0.
                else:
                    u["vx"]=0.
                    if self.time>=u["attack_at"] and self.time>=u["control_until"] and b not in ("suicide","squash"):
                        if b in ("summon","thief") or service:
                            self.damage(blocker,c.get("bite_damage",35) if service else c["damage"],u["side"],self._id("a"),"chomp" if b=="thief" else "normal",origin=u)
                        else:self._attack(u,blocker)
                        u["attack_at"]=self.time+c["interval"]
            if self.time<u["air_until"] and self.time>=u["control_until"]:u["vx"]=u["air_vx"]
            if self.time<u["knock_until"]:u["vx"]+=u["knock_vx"]
            if u["flying"] and self.time>=u["control_until"]:
                flight_target=hero
                if b=="thief":
                    choices=[t for t in self.targets(u["side"]) if t["id"] not in self.players]
                    if choices:flight_target=min(choices,key=lambda t:self.distance(u,t))
                    fx=wrap_delta(u["x"],flight_target["x"],self.width)
                    if abs(fx)>30:u["vx"]=(1 if fx>0 else -1)*speed
                    else:u["vx"]=0.
                nearby=abs(wrap_delta(u["x"],flight_target["x"],self.width))<120
                descending=nearby and (self.command_for(u)=="attack" or u["side"]=="plant" or b=="thief")
                desired_y=flight_target["y"] if descending else hero["y"]-100.
                u["vy"]=max(-100.,min(100.,(desired_y-u["y"])*3.))
            self._terrain_ladder(u)
            self._stack_mobile(u)
            cell=self.cell(u["x"],u["y"]-20)
            if cell.get("ladder") and self.time>=u["control_until"]:
                if hero["y"]<u["y"]-.001:u["vy"]=-180.
                elif hero["y"]>u["y"]+20:u["vy"]=100.
            if u["burrowed"] and abs(dx)<100:u["burrowed"]=False;u["facing"]*=-1
            if u["burrowed"]:u["x"]=(u["x"]+speed*u["facing"]*dt)%self.width;self._index_actor(u)
            else:self._move(u,dt,u["flying"])
            if c.get("throw_imp") and not u["imp_thrown"] and u["hp"]<u["max_hp"]*.5:
                imp=self.spawn("zombie:小鬼僵尸",u["side"],u["x"],u["y"]-55,u["facing"],True,parent=u,parent_attack=self._id("a"))
                if imp:imp["air_vx"]=200*u["facing"];imp["air_until"]=self.time+.65;imp["vx"]=imp["air_vx"];imp["vy"]=-300.
                u["imp_thrown"]=True
        if self._service_ability(u):return
        if b=="summon" and self.time>=u["attack_at"]:
            aid=self._id("a")
            for offset in (-45,45):self.spawn(c["summon"],u["side"],u["x"]+offset,u["y"],u["facing"],True,parent=u,parent_attack=aid)
            u["attack_at"]=self.time+c["interval"];return
        if b=="lantern":
            enemy=self.players["zombie" if u["side"]=="plant" else "plant"]
            if self.distance(u,enemy)<c["range"] and self.line_of_sight(u,enemy):enemy["marked_until"]=self.time+.5
            if "secret:光疗" in self.players[u["side"]]["secrets"] and self.time>=u["attack_at"]:
                for t in self.units.values():
                    if t["side"]==u["side"] and self.distance(u,t)<c["range"]:t["hp"]=min(t["max_hp"],t["hp"]+10)
                u["attack_at"]=self.time+2.
            return
        if b=="umbrella":return
        if c.get("rear_burst"):
            self._split_attack(u);return
        if self.time<u["attack_at"] or self.time<u["control_until"]:return
        t=self._target(u)
        if not t:return
        if c.get("timid") and self.distance(u,t)<100 and "secret:胆大" not in self.players[u["side"]]["secrets"]:return
        if b=="mine" and age<c.get("arm_time",8.):return
        if b in ("mine","squash"):
            self.explode(u);u["hp"]=0;return
        if b=="charm":
            if t["id"] not in self.players and not t["card"].get("heavy"):
                previous_side=t["side"]
                t["side"]=u["side"];t["owner"]=u["side"];t["facing"]*=-1
                t["current_owner"]=u["side"]
                if "secret:魅惑" in self.players[u["side"]]["secrets"]:t["hp"]+=(t["max_hp"]-t["hp"])*.5
                self._emit("charm",target=t["id"],side=u["side"],previous_side=previous_side,
                           target_original_owner=t["original_owner"],**self._provenance(u));u["hp"]=0
            else:self.damage(t,80,u["side"],self._id("a"),control=.4,origin=u)
        elif b=="magnet":
            metals=[t for t in self.targets(u["side"]) if t.get("card",{}).get("metal") and not t.get("disarmed") and self.distance(u,t)<c["range"]]
            if metals:
                t=min(metals,key=lambda t:self.distance(u,t));self._remove_metal(t,u["side"],self._id("a"),origin=u)
        elif b=="thief":
            self.damage(t,150,u["side"],self._id("a"),"chomp",origin=u)
        elif b not in ("suicide","freeze","wind"):
            self._attack(u,t)
        u["attack_at"]=self.time+c["interval"]/(1.25 if u["coffee_until"]>self.time else 1.)

    def _update_projectile(self,p,dt):
        if self.time-p["born"]>p["lifetime"]:
            self._splash(p,dict(x=p["x"],y=p["y"],h=0));return False
        if p["homing"] and p.get("target"):
            t=self.players.get(p["target"]) or self.units.get(p["target"])
            a=self.players.get(p["source"]) or self.units.get(p["source"]) or p.get("lock_origin",dict(x=p["x"],y=p["y"],h=0))
            legal=t and t["hp"]>0 and not t.get("burrowed") and t["side"]!=p["side"] and (t["id"] not in self.players or self.hero_lock(a,t))
            if legal:
                dx=wrap_delta(p["x"],t["x"],self.width);dy=t["y"]-t.get("h",44)/2-p["y"];norm=max(1.,math.hypot(dx,dy))
                p["vx"]=dx/norm*390.;p["vy"]=dy/norm*390.
            else:p["target"]=None;p["homing"]=False
        n=max(1,int(math.hypot(p["vx"],p["vy"])*dt/10)+1)
        for unused in range(n):
            p["vy"]+=p["gravity"]*dt/n;p["x"]=(p["x"]+p["vx"]*dt/n)%self.width;p["y"]+=p["vy"]*dt/n
            if self._solid(p["x"],p["y"]):
                self._splash(p,dict(x=p["x"],y=p["y"],h=0));return False
            point=dict(x=p["x"],y=p["y"],h=0)
            interceptors=self._interceptors
            if interceptors is None:
                interceptors=tuple(u for u in self.units.values() if u["behavior"]=="torch" or u["behavior"]=="umbrella" and not u["mobile"])
            if len(interceptors)>8:interceptors=self._nearby(point,max(self._max_actor_radius,self._interceptor_range))
            for u in interceptors:
                if u["id"] in self.players or u["hp"]<=0:continue
                if u["behavior"]=="torch" and u["side"]==p["side"] and u["id"] not in p["torch"] and abs(wrap_delta(u["x"],p["x"],self.width))<24 and u["y"]-u["h"]<p["y"]<u["y"] and p["asset"]=="豌豆":
                    p["damage"]*=3. if "secret:蓝火" in self.players[u["side"]]["secrets"] else u["card"].get("fire_multiplier",2.)
                    p["torch"].append(u["id"]);p["asset"]="火豆"
                if u["hp"]>0 and u["behavior"]=="umbrella" and not u["mobile"] and u["side"]!=p["side"] and p["gravity"] and self.distance(dict(x=p["x"],y=p["y"],h=0),u)<u["card"]["range"]:return False
            for t in self.targets(p["side"],point,self._max_actor_radius):
                if t["id"] in p["hits"]:continue
                if abs(wrap_delta(p["x"],t["x"],self.width))<t["w"]/2+5 and t["y"]-t["h"]-4<p["y"]<t["y"]+4:
                    covered=self._contained_ids(t) if t.get("card_id")=="plant:南瓜头" else []
                    self.damage(t,p["damage"],p["side"],p["attack"],p["kind"],p["control"],p["slow"],origin=p)
                    p["hits"].extend([t["id"]]+covered)
                    self._splash(p,t)
                    if not p["pierce"]:return False
        return -200<p["y"]<self.height+100

    def _splash(self,p,center):
        if not p.get("splash") or p.get("splash_done"):return
        p["splash_done"]=True
        recipients=list(self.targets(p["side"],center,p["splash"]))
        for target in recipients:
            if target["id"] in p["hits"] or self.distance(center,target)>=p["splash"]:continue
            covered=self._contained_ids(target) if target.get("card_id")=="plant:南瓜头" else []
            self.damage(target,p["damage"]*.5,p["side"],p["attack"],p["kind"],slow=p["slow"],origin=p)
            p["hits"].extend([target["id"]]+covered)
        self._emit("projectile_blast",x=p["x"],y=p["y"],radius=p["splash"],attack=p["attack"],side=p["side"],**self._provenance(p))

    def _death_spawn(self,u):
        key=u["card"].get("death_spawn")
        if not key or u.get("death_spawn_done"):return
        u["death_spawn_done"]=True
        if u.get("death_kind") in ("ash","chomp") or u.get("death_overkill",0)>=1000:return
        if u["side"]=="plant":key="plant:墓碑吞噬者"
        # Bans apply to derived playable plants too; neither copies nor charm
        # may smuggle a banned family back into a deck's battle.
        if not allowed(key,self.bans,for_spawn=True):return
        spot=self.surface_y(u["x"],u["y"])
        if spot is None or spot[2]:return
        x,y,unused=spot
        if self._blocked(dict(w=34.,h=44.),x,y):return
        # The native tile replacement erases occupants. The PvP entity instead
        # requires a free footprint and never deletes plants or allied units.
        if any(t["hp"]>0 and not t["mobile"] and self._overlaps(dict(x=x,y=y,w=34.,h=44.),t)
               for t in self.units.values()):return
        child=self.spawn(key,u["side"],x,y,u["facing"],temporary=True,parent=u,parent_attack=u.get("fatal_attack"))
        if child:self._emit("death_spawn",source=u["id"],entity=child["id"],card=key,side=u["side"],**self._provenance(child))

    def step(self,steps=1):
        for unused in range(steps):
            if self.audit_error:return
            if self.result:return
            dt=self.dt;self.tick+=1;self.time=self.tick*dt
            if not self.deathmatch and self.time>=self.rules["deathmatch_seconds"]:
                self.deathmatch=True;self._emit("deathmatch",multiplier=self.rules["production_multiplier"])
            self._build_index()
            for side,p in self.players.items():
                if self.tick-p["last_input_tick"]>self.rules["tick_rate"]*2:self.clear_input(side)
                move=p["input"].get("move",0)
                if move:p["facing"]=move
                sprint=1.25 if (side=="plant" and "secret:疾行" in p["secrets"]) else 1.
                p["vx"]=move*self.rules["hero_speed"]*sprint if self.time>=p["control_until"] else 0.
                if self.time<p["knock_until"]:p["vx"]+=p["knock_vx"]
                if p["jump_held"] and self.time>=p["control_until"] and self.cell(p["x"],p["y"]-20).get("ladder"):
                    p["vy"]=-180.
                self._move(p,dt)
                if "secret:猫尾" in p["secrets"] and self.time>=p["tail_cd"]:
                    fake=dict(p,card=dict(CARDS["plant:香蒲"],damage=12,range=500),owner=side,mobile=False)
                    t=self._target(fake)
                    if t:self._projectile(fake,t,self._id("a"));p["tail_cd"]=self.time+1.2
            for u in list(self.units.values()):
                if u["hp"]>0:self._update_unit(u,dt)
            for pid,p in list(self.projectiles.items()):
                if not self._update_projectile(p,dt):self.projectiles.pop(pid,None)
            # A death explosion can kill a unit already visited in insertion
            # order. Resolve the complete chain before deciding either winner.
            while True:
                deaths=[u for u in self.units.values() if u["hp"]<=0]
                if not deaths:break
                for u in deaths:
                    if u["card"].get("death_explosion") and not u["death_done"]:self.explode(u)
                    if u["card"].get("producer"):self.players[u["side"]]["stats"]["producer_lost"]+=1
                    if u["side"]=="plant" and u["card"]["side"]=="plant" and u.get("killer")=="zombie" and not u["temporary"] and "secret:补光" in self.team_secrets["plant"]:
                        self.resource("plant",15,u["x"],u["y"]-30,u["id"])
                    self._emit("death",entity=u["id"],side=u["side"],card=u["card_id"],
                               killer=u.get("killer"),fatal_attack=u.get("fatal_attack"),
                               fatal_source=deepcopy(u.get("fatal_source")),**self._provenance(u));self.units.pop(u["id"],None)
                    self._death_spawn(u)
            self.sky_progress+=dt
            if self.sky_progress>=self.rules["sky_interval"]:
                self.sky_progress-=self.rules["sky_interval"]
                x=self.rng.uniform(0,self.width)
                self.resource("plant",self.rules["sky_amount"],x,self.players["plant"]["y"]-80,"sky")
            for rid,r in list(self.resources.items()):
                if math.hypot(wrap_delta(r["x"],self.players["plant"]["x"],self.width),r["y"]-(self.players["plant"]["y"]-30))<60:self._collect(rid)
                elif self.time-r["born"]>self.rules["sun_lifetime"]:self.resources.pop(rid,None)
            dead=[s for s,p in self.players.items() if p["hp"]<=0]
            if dead:
                self.result=dict(winner="draw" if len(dead)==2 else ("zombie" if dead[0]=="plant" else "plant"),reason="hero_death",tick=self.tick)
                self._emit("result",winner=self.result["winner"],reason=self.result["reason"])
            if self.tick%300==0:
                self.damage_groups={k:v for k,v in self.damage_groups.items() if self.time-v[1]<15.}
            self._spatial=None;self._spatial_locations={};self._actor_cache=None;self._interceptors=None

    def snapshot(self,include_map=False,copy_state=True):
        """Detached state by default; cheap local render views are opt-in.

        With copy_state=False, actor dictionaries are shallow copies, while
        their nested card/list data is shared and must be treated as read-only.
        Player/private dictionaries and results always remain deeply detached
        so room privacy masking cannot mutate authoritative player state.
        """
        copy_entities=(lambda values:deepcopy(list(values))) if copy_state else (lambda values:[dict(v) for v in values])
        value=dict(tick=self.tick,time=self.time,deathmatch=self.deathmatch,result=deepcopy(self.result),audit_error=self.audit_error,
                   players=deepcopy(self.players),units=copy_entities(self.units.values()),
                   projectiles=copy_entities(self.projectiles.values()),resources=copy_entities(self.resources.values()),
                   command=self.command,events=deepcopy(self.events[-30:]),terrain_revision=self.terrain_revision)
        if self.rally_point is not None:value["rally_point"]=deepcopy(self.rally_point)
        if self.team_mode:
            value['surrender_requests']=deepcopy({team:r for team,r in self.surrender_requests.items() if r['expires']>self.time})
        if include_map:value["map"]=deepcopy(self.map)
        return value
