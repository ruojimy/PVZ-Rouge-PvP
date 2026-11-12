"""Native-texture world and map previews, isolated from solo global state."""
import math

from .native_style import NativeArt, SKY_COLORS


def _values(items):
    return items.values() if isinstance(items, dict) else items or ()


# Sun art size in tiles. The 15-sun keeps its size; a full 25-sun (and any
# larger drop) is drawn - and picked up, see sun_pick_radius - noticeably bigger.
SMALL_SUN_TILES, LARGE_SUN_TILES = 2/3, .9


# PvP64: adjacent suns merge into one worth their sum. Its art (and pick
# radius) grows with the square root of the value - area follows value -
# up to this factor, so a big merged sun still reads as one sun.
MERGED_SUN_GROWTH_CAP = 2.4


def sun_scale(amount):
    return 1. if amount <= 25 else min(MERGED_SUN_GROWTH_CAP, math.sqrt(amount/25.))


def sun_size(amount):
    return (LARGE_SUN_TILES if amount >= 25 else SMALL_SUN_TILES)*sun_scale(amount)


def sun_pick_radius(amount, base):
    return (base*LARGE_SUN_TILES/SMALL_SUN_TILES*1.15 if amount >= 25 else base)*sun_scale(amount)


class WorldView:
    def __init__(self, pygame, bridge=None, asset_dir=None):
        self.pg, self.bridge = pygame, bridge
        self.art = NativeArt(pygame, bridge, asset_dir)
        self.camera = None
        self._preview_cache, self._distant = {}, {}
        self._background_tiles = {}
        self._tinted_tiles = {}
        self.last_visuals = {}
        self.native_error = ""
        self._native_replay = None
        self._native_graphics = None
        self._native_runtime = None
        self._native_tile = None
        self._native_dynamic_loads = 0
        self._native_error_font = None
        self._native_load_error = ""

    def reset_native_replay(self):
        """Release a room's private atlas and allow retry after a local repair."""
        self._native_replay=self._native_graphics=self._native_runtime=None
        self._native_tile=None
        self._native_load_error=self.native_error=""
        if hasattr(self,'_world_layer'): self._world_layer.clear()

    def _ensure_native_replay(self, terrain, tile):
        """Build the same original atlas locally; no atlas crosses each frame."""
        from .native_animation import NamespaceGraphics, DrawReplay, NativeGraphicsError
        from .native_assets import load_original_assets
        from .native_bridge import NativeBridgeError
        from .native_runtime import NativeRuntime, load_patch
        if self._native_replay is not None and self._native_tile == tile:
            return self._native_replay
        if self._native_load_error:
            raise NativeGraphicsError(self._native_load_error)
        if self.bridge is None or not callable(getattr(self.bridge,"combat_payload",None)):
            raise NativeGraphicsError("原战斗绘制缺少本机权威源与资产")
        try:
            root, source, assets = self.bridge.combat_payload()
        except (NativeBridgeError, OSError) as exc:
            self._native_load_error=str(exc)[:200]
            raise NativeGraphicsError(self._native_load_error)
        try:
            runtime = NativeRuntime(root, terrain, seed=0, pygame=self.pg)
            patch = load_patch(source)
            load_original_assets(runtime.g, root, assets, tile, patch)
            from .native_scale import install as install_native_scale
            from .expansion_assets import install as install_expansion_assets
            install_expansion_assets(runtime.g, self.pg)
            from .content_assets import install as install_content_assets
            install_content_assets(runtime.g,self.pg)
            install_native_scale(runtime.g,self.pg)
            graphics = NamespaceGraphics(self.pg, tile)
            graphics.install(runtime.g, root)
        except Exception as exc:
            self._native_load_error=str(exc)[:200]
            raise NativeGraphicsError(self._native_load_error)
        self._native_runtime, self._native_graphics = runtime, graphics
        self._native_tile, self._native_dynamic_loads = tile, 0
        self._native_replay = DrawReplay(self.pg, asset_resolver=self._native_asset)
        return self._native_replay

    def _native_asset(self, key):
        """Resolve original lazy image-load recipes through the same loader.

        Names come from authoritative draw data, but are still bounded and kept
        inside the trusted flat asset directory by the original-assets adapter.
        Unknown synthetic atlas keys are errors, never substituted sprites.
        """
        from .native_animation import NativeGraphicsError
        source = self._native_graphics.sources.get(key)
        if source is not None:return source
        if not isinstance(key,str) or not key.startswith("world:@load/"):
            raise NativeGraphicsError("缺少原始动画资产："+str(key)[:160])
        name, separator, size = key[len("world:@load/"):].rpartition("/")
        normalized=name.replace("\\","/")
        parts=normalized.split("/")
        if (not separator or not name or len(name)>160 or ":" in name or
                any(p in ("", ".", "..") for p in parts) or
                len(parts)>2 or (len(parts)==2 and parts[0]!="图片")):
            raise NativeGraphicsError("非法原始资产名称")
        try:w,h=(int(value) for value in size.split("x"))
        except (TypeError,ValueError):raise NativeGraphicsError("非法原始资产尺寸")
        if not 0<w<=8192 or not 0<h<=8192 or w*h>4096*4096:
            raise NativeGraphicsError("非法原始资产尺寸")
        if self._native_dynamic_loads>=256:
            raise NativeGraphicsError("原始动态资产数量超过限制")
        self._native_runtime.g["加载图"](name,w,h)
        source=self._native_graphics.sources.get(key)
        if source is None:raise NativeGraphicsError("原始资产加载标识不一致："+key[:160])
        self._native_dynamic_loads+=1
        return source

    def _replay_native(self, screen, battle, terrain, rect, scale, layer=None):
        from .native_animation import NativeGraphicsError
        frame=battle.get("native_frame")
        if frame is None:return False
        hidden=getattr(self,'_outro_hide',None)
        if hidden and isinstance(frame,dict):
            # PvP64 outro: this hero is drawn separately, toppling over.
            frame=dict(frame,commands=[c for c in frame.get("commands",()) if c.get('entity')!=hidden])
        try:
            if not isinstance(frame,dict) or frame.get("tile")!=terrain.get("tile_size",48):
                raise NativeGraphicsError("原始绘制帧比例不一致")
            replay=self._ensure_native_replay(terrain,frame["tile"])
            replay.render(screen,frame,point=self.point,scale=scale,clip=rect,layer=layer,
                          offsets=battle.get('_visual_offsets'),local_pixels=getattr(self,'local_pixels',None))
        except (NativeGraphicsError,OSError,ValueError,KeyError,TypeError,self.pg.error) as exc:
            if not self.native_error:self.native_error="原动画回放失败："+str(exc)[:200]
        return True

    def draw_fallen_hero(self, screen, battle, entity, angle):
        """Replay only one hero's native body commands, rotated about the feet."""
        frame=battle.get("native_frame")
        players=battle.get("players") or {}
        hero=players.get(entity.split(':',1)[-1])
        if not isinstance(frame,dict) or not hero or self.camera is None:return False
        commands=[c for c in frame.get("commands",()) if c.get('entity')==entity]
        if not commands:return False
        terrain=battle.get('map') or {}
        scale=self.camera[2]
        fx,fy=self.point(hero['x'],hero['y'])
        size=int(max(8,(terrain.get('tile_size',48)*scale)*5))
        canvas=self.pg.Surface((size,size),self.pg.SRCALPHA)
        offset_x,offset_y=size/2-fx,size/2-fy
        point=lambda x,y:(self.point(x,y)[0]+offset_x,self.point(x,y)[1]+offset_y)
        try:
            replay=self._ensure_native_replay(terrain,frame["tile"])
            replay.render(canvas,dict(frame,commands=commands),point=point,scale=scale)
        except Exception as exc:
            self.native_error="原动画回放失败："+str(exc)[:200]
            return False
        rotated=self.pg.transform.rotate(canvas,angle)
        screen.blit(rotated,(round(fx-rotated.get_width()/2),round(fy-rotated.get_height()/2)))
        return True

    def _show_native_error(self, screen, rect):
        if not self.native_error:return
        if self._native_error_font is None:
            try:
                from .rendering import Renderer
                self._native_error_font=Renderer(self.pg,screen,self.bridge,self.asset_dir).font(16)
            except Exception:
                self._native_error_font=self.pg.font.Font(None,16)
        text=self._native_error_font.render(self.native_error,True,(255,240,220))
        panel=self.pg.Rect(rect.x+8,rect.y+8,min(rect.w-16,text.get_width()+16),text.get_height()+12)
        self.pg.draw.rect(screen,(122,25,20),panel)
        screen.blit(text,(panel.x+8,panel.y+6))

    def draw_background(self, screen, rect, terrain=None, sky="白天"):
        """Exact original 24-band sky formula (生成近景 lines 570–588)."""
        rect = self.pg.Rect(rect)
        environment=(terrain or {}).get("environment",{})
        if environment.get("weather")=="rain":sky="阴天"
        if environment.get("night"):sky="黑天"
        if environment.get("background","自动")!="自动":sky=environment["background"]
        base = SKY_COLORS.get(sky, SKY_COLORS["白天"])
        for row in range(24):
            color = tuple(max(0, min(255, channel + row-12)) for channel in base)
            top, bottom = rect.y + row*rect.h//24, rect.y + (row+1)*rect.h//24
            self.pg.draw.rect(screen, color, (rect.x, top, rect.w, bottom-top))

    @staticmethod
    def _fence_asset(before, after):
        # Original main draw 63948..64068: endpoints select native caps;
        # an isolated segment uses the middle PNG. No generic 栅栏.png exists.
        left = before.get("background") == "栅栏"
        right = after.get("background") == "栅栏"
        return "左栅栏" if right and not left else "右栅栏" if left and not right else "中间栅栏"

    def _tile(self, screen, cell, rect, seconds=0, background_asset=None, phase=None):
        rect = self.pg.Rect(rect)
        native = cell.get("native") or {}
        background = cell.get("background")
        if phase!='foreground' and background and background != "空":
            asset = background_asset or ("中间栅栏" if background == "栅栏" else background)
            fence = background in ("栅栏", "铁栅栏")
            key = (asset, rect.size, fence)
            texture = self._background_tiles.get(key)
            if texture is None:
                texture = self.art.image(asset, rect.size)
                if texture is not None:
                    # Keep the old opaque-wall tone, but tint RGB on a COPY:
                    # painting a full black rectangle darkened transparent air.
                    # Original fences are drawn directly without wall shading.
                    texture = texture.copy()
                    if not fence:
                        texture.fill((180, 180, 180), special_flags=self.pg.BLEND_RGB_MULT)
                    if len(self._background_tiles) > 128:
                        self._background_tiles.clear()
                    self._background_tiles[key] = texture
            if texture is not None:
                texture = self._tint_tile(texture, native.get("_pvp_wall_color"), ("wall", key))
                screen.blit(texture, rect)
        if phase=='background':return
        kind = cell.get("kind", "空")
        if kind != "空" and not cell.get("water"):
            texture = self.art.image(kind, rect.size)
            if texture is not None:
                texture = self._tint_tile(texture, native.get("_pvp_block_color"), ("block", kind, rect.size))
                screen.blit(texture, rect)
        if cell.get("ladder"):
            # PvP64: a conveyor-belt zombie's ladder block is a belt.
            tile_name = "传送带块" if native.get("_pvp_belt") else "梯子块"
            texture = self.art.image(tile_name, rect.size)
            if texture is not None:
                texture = self._tint_tile(texture, native.get("_pvp_block_color"), ("block", tile_name, rect.size))
                screen.blit(texture, rect)
        grave = native.get("坟墓")
        if grave:
            self.art.blit(screen, "坟墓"+str(grave), rect.topleft, rect.size)
        if cell.get("water"):
            frame = int(seconds*12)%32
            texture = self.art.image("水", rect.size, frame=frame, alpha=150)
            if texture is not None:
                texture = self._tint_tile(texture, native.get("_pvp_block_color"), ("water", frame, rect.size))
                screen.blit(texture, rect)

    def _tint_tile(self, texture, color, key):
        """Tint only a private PNG copy; retain native texture, alpha and shape."""
        if color is None:return texture
        if (not isinstance(color, (list, tuple)) or len(color) != 3 or
                any(type(c) is not int or not 0 <= c <= 255 for c in color)):
            return texture
        key = (key, tuple(color))
        result = self._tinted_tiles.get(key)
        if result is None:
            result = texture.copy()
            result.fill(tuple(color), special_flags=self.pg.BLEND_RGB_MULT)
            if len(self._tinted_tiles) >= 1024:self._tinted_tiles.clear()
            self._tinted_tiles[key] = result
        return result

    def _terrain(self, screen, terrain, camera, seconds=0, phase=None):
        left, top, scale, rect, width = camera
        rect = self.pg.Rect(rect)
        tile = terrain.get("tile_size", 48)
        tiles = terrain["tiles"]
        cols = terrain.get("cols", len(tiles[0]))
        start_y = max(0, int(top//tile))
        end_y = min(len(tiles), int((top+rect.h/scale)//tile)+2)
        for row in range(start_y, end_y):
            for col in range(int(left//tile)-1, int((left+rect.w/scale)//tile)+2):
                cell = tiles[row][col%cols]
                x1, x2 = round(rect.x+(col*tile-left)*scale), round(rect.x+((col+1)*tile-left)*scale)
                y1, y2 = round(rect.y+(row*tile-top)*scale), round(rect.y+((row+1)*tile-top)*scale)
                before, after = tiles[row][(col-1)%cols], tiles[row][(col+1)%cols]
                fence = self._fence_asset(before, after) if cell.get("background") == "栅栏" else None
                self._tile(screen, cell, (x1, y1, x2-x1, y2-y1), seconds, fence, phase)
                # Original terrain contours: black only on air-facing surfaces.
                if phase!='background' and cell.get("solid"):
                    thickness = max(1, round(tile*scale/24))
                    above = tiles[row-1][col%cols] if row else {}
                    if not above.get("solid"):
                        self.pg.draw.line(screen, (0, 0, 0), (x1,y1), (x2,y1), thickness)
                    if not before.get("solid"):
                        self.pg.draw.line(screen, (0, 0, 0), (x1,y1), (x1,y2), thickness)
                    if not after.get("solid"):
                        self.pg.draw.line(screen, (0, 0, 0), (x2-1,y1), (x2-1,y2), thickness)

    def preview(self, screen, terrain, rect, players=None):
        """Render real native tile textures at 16px, then fit without distortion."""
        rect = self.pg.Rect(rect)
        self.draw_background(screen, rect, terrain)
        if not terrain or not terrain.get("tiles"):
            return rect
        cols = terrain.get("cols", len(terrain["tiles"][0]))
        rows = terrain.get("rows", len(terrain["tiles"]))
        key = (terrain.get("terrain_hash"), terrain.get("terrain_revision", 0), id(terrain["tiles"]))
        image = self._preview_cache.get(key)
        if image is None:
            image = self.pg.Surface((cols*16, rows*16))
            self.draw_background(image, image.get_rect(), terrain)
            tile = terrain.get("tile_size", 48)
            self._terrain(image, terrain, (0,0,16/tile,image.get_rect(),cols*tile))
            if len(self._preview_cache) > 16:
                self._preview_cache.clear()
            self._preview_cache[key] = image
        factor = min(rect.w/image.get_width(), rect.h/image.get_height())
        size = (max(1,round(image.get_width()*factor)), max(1,round(image.get_height()*factor)))
        fitted = self.pg.Rect(0,0,*size)
        fitted.center = rect.center
        screen.blit(self.pg.transform.scale(image, size), fitted)
        for side, entity in (players or terrain.get("spawns", {})).items():
            if not isinstance(entity, dict) or entity.get("absent") or "x" not in entity:
                continue
            px = fitted.x+entity["x"]/terrain["width"]*fitted.w
            py = fitted.y+entity["y"]/terrain["height"]*fitted.h
            self.pg.draw.line(screen, (235,250,128) if side.startswith("plant") else (248,166,235), (px,py-8), (px,py), 2)
        return fitted

    def point(self, x, y):
        if not self.camera:
            return None
        left, top, scale, rect, width = self.camera
        center = left+rect.w/scale/2
        dx = (x-center+width/2)%width-width/2
        return (rect.centerx+dx*scale, rect.y+(y-top)*scale)

    def world_point(self, pos):
        if not self.camera:
            return None
        left, top, scale, rect, width = self.camera
        if not rect.collidepoint(pos):
            return None
        return ((left+(pos[0]-rect.x)/scale)%width, top+(pos[1]-rect.y)/scale)

    def flag(self, screen, x, y, size, seat='zombie'):
        from .teams import RALLY_COLORS
        size=max(12,round(size))
        self.pg.draw.line(screen,(65,43,29),(x,y),(x,y-size),max(2,size//14))
        self.pg.draw.polygon(screen,RALLY_COLORS.get(seat,RALLY_COLORS['zombie']),[(x,y-size),(x+size*.65,y-size*.85),(x,y-size*.52)])
        # One or two light stitches also distinguish flags without color alone.
        for i in range(2 if seat=='zombie2' else 1):
            px=x+size*(.13+i*.16)
            self.pg.draw.line(screen,(255,245,212),(px,y-size*.88),(px,y-size*.68),max(1,size//24))
        self.pg.draw.circle(screen,(255,227,119),(round(x),round(y-size)),2)

    def minimap_flags(self, screen, battle, terrain, fitted):
        from .teams import rally_flags
        if not terrain or not fitted:return
        for seat,point in rally_flags(battle):
            px=fitted.x+point['x']/terrain['width']*fitted.w
            py=fitted.y+point['y']/terrain['height']*fitted.h
            self.flag(screen,px,py,12,seat)

    def rain(self, screen, rect, terrain, seconds=0, low=False):
        if terrain.get('environment',{}).get('weather')!='rain':return
        # Original vertical quarter-tile streak, speed plk*600 at 250 Hz.
        # Pure presentation clock: never consume combat RNG or add entities.
        rect=self.pg.Rect(rect);tile=max(16,screen.get_width()//20)
        color=(153,169,197) if terrain.get('environment',{}).get('night') else (93,124,164)
        for i in range(28 if low else 72):
            x=rect.x+(i*137+terrain.get('seed',0)*17)%max(1,rect.w)
            y=rect.y+(i*79+seconds*tile*15)%(rect.h+tile)-tile
            self.pg.draw.line(screen,color,(x,y),(x,y+tile/4),1)

    def render(self, screen, battle, rect, side="plant", settings=None, terrain=None, replay=False):
        settings=settings or {}
        if settings.get('world_quality','native')!='native':
            from .display_pipeline import WorldLayer
            if not hasattr(self,'_world_layer'): self._world_layer=WorldLayer(self.pg)
            return self._world_layer.render(self,screen,battle,rect,side,settings,terrain,replay)
        if hasattr(self,'_world_layer'): self._world_layer.clear()
        return self._render_full(screen,battle,rect,side,settings,terrain,replay)

    def camera_for(self, screen, battle, rect, side, settings, terrain, replay=False):
        if not terrain or not battle.get('players'):return None
        rect=self.pg.Rect(rect)
        players=battle['players']; hero=players.get(side,players.get('plant'))
        if battle.get('team') and hero.get('hp',1)<=0:
            mate=players.get(side+'2' if side in ('plant','zombie') else side[:-1])
            if mate and mate.get('hp',0)>0:hero=mate
        tile=terrain.get('tile_size',48)
        scale=max(16,round((screen.get_width()//20)*settings.get('zoom',1.0)))/tile
        left=hero['x']-rect.w/scale/2
        max_top=max(0,terrain['height']-rect.h/scale)
        top=max(0,min(max_top,hero['y']-rect.h/scale*.60))
        if replay and settings.get('replay_camera_mode')=='overview':
            scale=min(rect.w/terrain['width'],rect.h/terrain['height'])
            left=(terrain['width']-rect.w/scale)/2;top=(terrain['height']-rect.h/scale)/2
        elif replay and settings.get('replay_camera') is not None:
            cx,cy=settings['replay_camera'];left=cx-rect.w/scale/2;top=cy-rect.h/scale/2
        elif settings.get('outro_camera') is not None:
            cx,cy=settings['outro_camera'];left=cx-rect.w/scale/2;top=max(0,min(max_top,cy-rect.h/scale*.55))
        return left,top,scale,rect,terrain['width']

    def _render_full(self, screen, battle, rect, side="plant", settings=None, terrain=None, replay=False):
        # Clear once per frame, not after each successful (possibly empty) layer.
        self.native_error=""
        settings = settings or {}
        terrain = battle.get("map") or terrain
        rect = self.pg.Rect(rect)
        self.draw_background(screen, rect, terrain)
        if not terrain or not battle.get("players"):
            self.camera = None
            return None
        players = battle["players"]
        hero = players.get(side, players.get('plant'))
        if battle.get('team') and hero.get('hp',1)<=0:
            mate=players.get(side+'2' if side in ('plant','zombie') else side[:-1])
            if mate and mate.get('hp',0)>0:hero=mate
        tile = terrain.get("tile_size", 48)
        self._outro_hide=settings.get('outro_hide')
        self.camera = settings.get('_render_camera') or self.camera_for(screen,battle,rect,side,settings,terrain,replay)
        left,top,scale,rect,width = self.camera
        # Overview can replace the normal zoom scale. All world-space overlays
        # must use that final camera scale, including graves and loose resources.
        pixel_tile = tile * scale
        previous_clip = screen.get_clip()
        screen.set_clip(rect)
        self._terrain(screen, terrain, self.camera, battle.get("time", 0),phase='background')
        self._replay_native(screen,battle,terrain,rect,scale,layer='below_ground')
        self._terrain(screen, terrain, self.camera, battle.get("time", 0),phase='foreground')
        native_frame = self._replay_native(screen,battle,terrain,rect,scale,layer='foreground')
        if not native_frame:self.native_error=""
        self.last_visuals = {}
        entities = list(_values(battle.get("units"))) + [p for p in players.values() if not p.get("absent")]
        pots = {(e.get("side"), round(e["x"]/tile), round(e["y"]/tile))
                for e in entities if e.get("hp",1)>0 and e.get("card",{}).get("name")=="花盆"}
        # The real pot rim occludes the inserted root; pumpkins enclose both.
        def layer(entity):
            name = entity.get("card",{}).get("name")
            return (name=="石化藤蔓", entity.get("y",0),
                    2 if name=="南瓜头" else 1 if name=="花盆" else 0)
        entities.sort(key=layer)
        shielded = {p.get("selected_grave") for p in players.values() if p.get("selected_grave")}
        for entity in entities:
            if entity.get("hp", 1) <= 0:
                if entity.get('id') in players and battle.get('team'):
                    # Recoverable bodies stay visible to the teammate in
                    # play, replay and spectator views, including in water.
                    px,py=self.point(entity['x'],entity['y'])
                    asset='僵尸戴夫' if entity.get('side','plant').startswith('zombie') else '疯狂戴夫'
                    self.art.blit(screen,asset,(px-pixel_tile,py-pixel_tile*.9),2*pixel_tile,
                                  entity.get('facing',1)<0,angle=90)
                continue
            px, py = self.point(entity["x"], entity["y"])
            if px < rect.left-3*pixel_tile or px > rect.right+3*pixel_tile or py < rect.top or py > rect.bottom+3*pixel_tile:
                continue
            card = entity.get("card",{})
            potted = (entity.get("side"),round(entity["x"]/tile),round(entity["y"]/tile)) in pots
            native = entity.get("native") or (native_frame and entity.get("native_pose") is not None)
            if potted and card.get("category")=="plant" and not entity.get("mobile") and not native:
                # Small visual seating offset only: simulation and projectile
                # coordinates remain authoritative. Native solo uses a full
                # terrain block instead of PvP's independently damageable base.
                py -= pixel_tile*.1
            if native:
                # The original draw stream already contains this body, roots,
                # head poses, equipment and hit flashes. Only custom graves use
                # the separate PvP grave artwork; HUD bounds are not sprites.
                if entity.get("behavior",card.get("behavior"))=="grave":
                    visual=self.art.grave(screen,card.get("name","脑光墓碑"),px,py,pixel_tile,floating=entity.get("floating",False),seconds=battle.get("time",0),
                                          lit=not entity.get("drowsy"),blue=entity.get('torch_blue',False))
                    if entity.get("frozen") or entity.get("slowed"):
                        shade=self.pg.Surface(visual.size,self.pg.SRCALPHA)
                        shade.fill((89,185,255,110 if entity.get("frozen") else 55))
                        screen.blit(shade,visual.topleft)
                        self.pg.draw.rect(screen,(174,235,255),visual,2)
                        for n in range(3):
                            sx=visual.left+(n+1)*visual.w//4
                            sy=visual.top+int((battle.get("time",0)*8+n*7)%max(1,visual.h))
                            self.pg.draw.line(screen,(219,248,255),(sx-2,sy),(sx+2,sy),1)
                    if entity.get("drowsy"):
                        # Idle producing grave: dimmed, with drifting sleep marks.
                        # A sweep or the zombie Dave's touch wakes it. The
                        # shade deepens with the dozing level; fully asleep
                        # graves are drawn clearly darker.
                        level=max(0.,min(1.,float(entity.get("drowsy_level",1.))))
                        shade=self.pg.Surface(visual.size,self.pg.SRCALPHA)
                        shade.fill((24,14,54,70+round(80*level)) if level<1. else (10,4,26,190))
                        screen.blit(shade,visual.topleft)
                        now=battle.get("time",0)
                        border=max(2,round(pixel_tile*.055))
                        pulse=round(18*(1+math.sin(now*3)))
                        self.pg.draw.rect(screen,(172+pulse,135+pulse,239),
                                          visual.inflate(border*2,border*2),border)
                        for n in range(3):
                            phase=(now*.8+n/3.)%1.
                            size=pixel_tile*(.34+.13*n)
                            self.art.blit(screen,"睡觉",(visual.right-pixel_tile*.45+phase*pixel_tile*.3,
                                          visual.top-pixel_tile*(.08+.5*phase)-size),size)
                    if entity.get("buttered"):
                        self.art.blit(screen,"黄油",(px-pixel_tile*.2,visual.top-pixel_tile*.12),pixel_tile*.4)
                    if entity.get('poison_level'):
                        from .native_status import COLORS
                        shade=self.pg.Surface(visual.size,self.pg.SRCALPHA)
                        shade.fill(COLORS[entity['poison_level']]+(85,))
                        screen.blit(shade,visual.topleft)
                    if entity.get('stunned'):
                        for n in range(3):
                            angle=battle.get('time',0)*5+n*2.094
                            self.pg.draw.circle(screen,(255,229,80),
                                (round(px+math.cos(angle)*pixel_tile*.35),round(visual.top-pixel_tile*.12+math.sin(angle)*pixel_tile*.08)),max(2,round(pixel_tile*.05)))
                else:
                    w,h=entity.get("w",tile)*scale,entity.get("h",tile)*scale
                    visual=self.pg.Rect(round(px-w/2),round(py-h),max(1,round(w)),max(1,round(h)))
            else:
                visual = self.art.entity(screen, entity, px, py, pixel_tile, battle.get("time",0), settings.get("low_effects",False))
            if entity.get("mature") and visual is not None and "成长" in card.get("name",""):
                # Fully grown growth grave: double yield, shown by a gold frame.
                # Units carry the flag, so play, spectating and replay agree.
                width=max(2,round(pixel_tile/16))
                self.pg.draw.rect(screen,(120,78,6),visual.inflate(width*2+2,width*2+2),1)
                self.pg.draw.rect(screen,(255,206,48),visual.inflate(width*2,width*2),width)
            self.last_visuals[entity.get("id")] = visual
            if entity.get('first_soldier_ready') and visual is not None:
                # A golden first-soldier pennant disappears after this grave's
                # first deployment. Authoritative snapshot flag also serves
                # guests, spectators and replay without reading native state.
                radius=max(5,round(pixel_tile*.13))
                cx,cy=visual.left+radius,visual.top-radius
                points=[(round(cx+math.sin(n*math.pi/5)*radius*(1 if n%2==0 else .45)),
                         round(cy-math.cos(n*math.pi/5)*radius*(1 if n%2==0 else .45))) for n in range(10)]
                self.pg.draw.polygon(screen,(255,217,70),points)
                self.pg.draw.polygon(screen,(64,43,12),points,1)
            if '玉米卷' in entity.get('secret_speed_bonuses',{}):
                self.art.blit(screen,'玉米卷',(px-pixel_tile*.2,py-pixel_tile*1.95),pixel_tile*.4)
                if not settings.get('low_effects'):
                    self.pg.draw.lines(screen,(255,218,70),False,
                                       [(px-pixel_tile*.28,py-pixel_tile*.25),(px,py-pixel_tile*.45),(px+pixel_tile*.28,py-pixel_tile*.25)],2)
            if settings.get("show_health", True) and "card" in entity and entity.get("hp",0)<entity.get("max_hp",1):
                w = max(18, pixel_tile*.6)
                health_y = visual.top-5 if visual is not None else py-pixel_tile-5
                self.pg.draw.rect(screen,(24,18,12),(px-w/2,health_y,w,4))
                fraction=max(0,min(1,entity["hp"]/max(1,entity.get("max_hp",1))))
                self.pg.draw.rect(screen,(113,224,70) if entity.get("side")=="plant" else (194,132,225),(px-w/2,health_y,w*fraction,4))
            if entity.get("id") == settings.get("grave"):
                self.pg.draw.ellipse(screen,(255,228,40),(px-pixel_tile*.6,py-pixel_tile*.12,pixel_tile*1.2,pixel_tile*.25),2)
            if entity.get("behavior")=="grave" and entity.get("id") in shielded:
                # 解除封印: this grave is a player's selected grave (75% damage reduction).
                self.pg.draw.ellipse(screen,(120,200,255),(px-pixel_tile*.7,py-pixel_tile*.2,pixel_tile*1.4,pixel_tile*.4),2)
                if not hasattr(self,"_shield_font"):self._shield_font=self.pg.font.Font(None,max(12,int(pixel_tile*.38)))
                label=self._shield_font.render("-75%",True,(150,215,255))
                screen.blit(label,(px-label.get_width()/2,py-pixel_tile*1.6))
        # Shell vines are rendered after their hosts, independent of planting
        # order. The same draw stream is used for local play and replay.
        self._replay_native(screen,battle,terrain,rect,scale,layer='vine_foreground')
        for resource in _values(battle.get("resources")):
            px,py=self.point(resource["x"],resource["y"])
            coin=resource.get("coin")
            if coin:
                # PvE coins and money bags, with the original coin art.
                name="钱袋" if coin=="bag" else "金币"
                size=pixel_tile*(.75 if coin=="bag" else .62 if coin=="gold" else .48)
                self.art.blit(screen,name,(px-size/2,py-size/2),size)
                continue
            name="阳光球" if str(resource.get("side","plant")).startswith("plant") else "脑子"
            size=pixel_tile*(sun_size(resource.get("amount",25)) if name=="阳光球" else .5)
            self.art.blit(screen,name,(px-size/2,py-size/2),size)
        for item in (battle.get("zsecrets") or {}).get("pickups", ()):
            # 二手: a dropped half-life piece waiting for a zombie to pick it up.
            px,py=self.point(item["x"],item["y"])
            size=pixel_tile*.7
            if self.art.blit(screen,item.get("asset") or item["name"],(px-size/2,py-size*.8),size) is None:
                self.pg.draw.rect(screen,(150,150,150),(px-size/3,py-size/2,size*2/3,size/3))
        for effect in (battle.get('zsecrets') or {}).get('effects',()):
            if effect.get('kind')!='taco':continue
            from .simulation import wrap_delta
            world_width=terrain['width']
            duration=max(.001,effect.get('until',effect['born']+.8)-effect['born'])
            fraction=max(0.,min(1.,(battle.get('time',0)-effect['born'])/duration))
            x=(effect['x']+wrap_delta(effect['x'],effect['tx'],world_width)*fraction)%world_width
            y=effect['y']+(effect['ty']-effect['y'])*fraction-math.sin(fraction*math.pi)*tile*1.5
            # A short throwing-arm gesture makes the origin readable before
            # the spinning taco arcs toward its recipient. Presentation only:
            # no extra entity, damage, random draw or speed-buff delay.
            if fraction<.25:
                sx,sy=self.point(effect['x'],effect['y'])
                direction=1 if wrap_delta(effect['x'],effect['tx'],world_width)>=0 else -1
                hand=(sx+direction*pixel_tile*(.25+fraction),sy+pixel_tile*(.5-fraction))
                self.pg.draw.line(screen,(65,82,53),(sx,sy+pixel_tile*.65),hand,max(2,round(pixel_tile*.12)))
                self.pg.draw.circle(screen,(181,193,148),(round(hand[0]),round(hand[1])),max(2,round(pixel_tile*.12)))
            px,py=self.point(x,y);size=pixel_tile*.8
            self.art.blit(screen,'玉米卷',(px-size/2,py-size/2),size,angle=fraction*360)
        for projectile in _values(battle.get("projectiles")):
            if projectile.get("native"):continue
            px,py=self.point(projectile["x"],projectile["y"])
            name=projectile.get("asset") or "豌豆"
            size=pixel_tile if projectile.get("lob") else pixel_tile*.6
            visual=self.art.blit(screen,name,(px-size/2,py-size/2),size)
            if visual is None:
                self.art.blit(screen,"豌豆",(px-size/2,py-size/2),size)
        preview=settings.get("placement_preview")
        if preview:
            px,py=self.point(preview["x"],preview["y"])
            key=settings.get("selected_card")
            if key:
                from .catalog import actual_card
                card=actual_card(key,hero.get("secrets",()))
                self.art.entity(screen,{"card":card,"side":side,"facing":hero.get("facing",1),"floating":preview.get("floating",False)},px,py,pixel_tile,alpha=120)
            color=(218,37,28) if preview.get("error") else (241,232,79)
            self.pg.draw.rect(screen,color,(px-pixel_tile/2,py-pixel_tile,pixel_tile,pixel_tile),2)
            self.pg.draw.line(screen,color,(px,py-pixel_tile*.4),(px+hero.get("facing",1)*pixel_tile*.7,py-pixel_tile*.4),2)
        self.rain(screen,rect,terrain,battle.get('time',0),settings.get('low_effects',False))
        from .teams import rally_flags, own_rally_seat
        for seat,rally in rally_flags(battle):
            px,py=self.point(rally['x'],rally['y'])
            self.flag(screen,px,py,pixel_tile*.85,seat)
        if settings.get('rally') and (not settings.get('touch_mode') or settings.get('rally_drag') is not None):
            # Logical pointer, the same coordinates place_rally submits. The raw
            # window position drifts from it whenever the window is scaled.
            pos=settings.get('rally_drag') or settings.get('pointer_pos') or self.pg.mouse.get_pos()
            point=self.world_point(pos)
            if point is not None:
                cx,cy=self.point((int(point[0]//tile)+.5)*tile,(int(point[1]//tile)+.5)*tile)
                self.pg.draw.rect(screen,(255,220,97),(cx-pixel_tile/2,cy-pixel_tile/2,pixel_tile,pixel_tile),2)
                # The placed flag stands on the exact clicked point; so does this.
                px,py=self.point(*point)
                self.flag(screen,px,py,pixel_tile*.85,own_rally_seat(battle))
        self._show_native_error(screen,rect)
        screen.set_clip(previous_clip)
        return self.camera
