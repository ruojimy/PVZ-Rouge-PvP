"""Independent pygame presentation for the PvP room and authoritative battle."""
import math
from pathlib import Path

from .catalog import CARDS, RULES, describe, actual_card, map_card_error
from .ui_data import endpoint_note
from .bounded_cache import BudgetCache, surface_cache


COLORS = dict(bg=(19, 22, 25), panel=(76, 37, 15), raised=(88, 88, 116),
              text=(255, 239, 199), muted=(198, 181, 145), line=(124, 86, 52),
              plant=(167, 218, 97), zombie=(199, 173, 229), gold=(255, 218, 106),
              bad=(255, 120, 97), blue=(181, 211, 168))


def card_art_name(card):
    """Display artwork overrides do not change the battle catalog identity."""
    if card['behavior'] == 'grave' or card.get('id') == 'secret:密植':
        return card['name']
    return card['asset']


def layout(width, height):
    """All hit boxes derive from the rendered frame, never old animation targets."""
    margin = 14
    middle = max(168, int(width * .15))
    side = (width - 4 * margin - middle) // 2
    return {"plant": (margin, 182, side, height - 224),
            "center": (side + 2 * margin, 182, middle, height - 224),
            "zombie": (side + middle + 3 * margin, 182, side, height - 224)}


class Renderer:
    def __init__(self, pygame, surface, bridge=None, asset_dir=None):
        self.pg = pygame
        self.screen = surface
        self.bridge = bridge
        self.asset_dir = Path(asset_dir) if asset_dir else None
        self.fonts = {}
        # Font.render / Font.size results by (font, text[, color]): pure
        # functions of their inputs, so a frame that draws the same labels as
        # the last one reuses them.  Rendered surfaces are only blitted.
        self._text_images = surface_cache(2048,16*1024*1024)
        self._text_sizes = surface_cache(8192,2*1024*1024,lambda value:128)
        self.images = {}
        self.scaled = surface_cache(2048,16*1024*1024)
        self.controls = []
        self.camera = None
        self.mouse_world = None
        self.native_frames = surface_cache(300,12*1024*1024)
        self._seed_bank_sources = {}
        self.native_seed_banks = surface_cache(32,8*1024*1024)
        self.text_scale = 1.

    def font(self, size):
        size = max(14,round(size*self.text_scale)) if self.text_scale>1 else int(size)
        if size not in self.fonts:
            self.fonts[size] = self._load_font(size)
        return self.fonts[size]

    def clear_transient_caches(self):
        for cache in (self._text_images,self._text_sizes,self.scaled,self.native_frames,self.native_seed_banks):
            cache.clear()

    def _load_font(self, size):
        import os
        candidates = []
        # Android: the app bundles fonts/cjk.ttf, and every device ships a CJK
        # fallback under /system/fonts. Windows fonts come after these.
        env_font = os.environ.get("PVP_FONT")
        if env_font:
            candidates.append(Path(env_font))
        candidates.append(Path.cwd() / "fonts" / "cjk.ttf")
        for name in ("NotoSansCJK-Regular.ttc", "DroidSansFallbackFull.ttf",
                     "DroidSansFallback.ttf", "DroidSansFallback.ttf"):
            candidates.append(Path("/system/fonts") / name)
        candidates.append(Path("C:/Windows/Fonts/simhei.ttf"))
        candidates.append(Path("C:/Windows/Fonts/msyh.ttc"))
        for candidate in candidates:
            try:
                if candidate.is_file():
                    return self.pg.font.Font(str(candidate), size)
            except (OSError, self.pg.error):
                continue
        try:
            return self.pg.font.SysFont("microsoftyahei,simhei,arial", size)
        except Exception:
            return self.pg.font.Font(None, size)

    def text_size(self, font, value):
        key = (font, value)
        size = self._text_sizes.get(key)
        if size is None:
            size = font.size(value)
            if not isinstance(self._text_sizes,BudgetCache) and len(self._text_sizes)>=8192:self._text_sizes.clear()
            self._text_sizes[key] = size
        return size

    def rendered(self, font, value, color):
        key = (font, value, tuple(color))
        image = self._text_images.get(key)
        if image is None:
            image = font.render(value, True, color)
            if not isinstance(self._text_images,BudgetCache) and len(self._text_images)>=2048:self._text_images.clear()
            self._text_images[key] = image
        return image

    def text(self, value, pos, color=None, size=18, max_width=None):
        value = str(value)
        font = self.font(size)
        if max_width:
            while value and self.text_size(font, value)[0] > max_width:
                value = value[:-2] + "…" if len(value) > 2 else ""
        if value:
            self.screen.blit(self.rendered(font, value, color or COLORS["text"]), pos)

    def wrapped(self, value, rect, size=16, color=None, line_height=None):
        x, y, width, height = rect
        font = self.font(size)
        line_height = max(line_height or 0,font.get_height()+5,size+7)
        line = ""
        for char in str(value) + "\n":
            if char == "\n" or self.text_size(font, line + char)[0] > width:
                self.text(line, (x, y), color, size)
                y += line_height
                if y + line_height > rect[1] + height:
                    return y
                line = "" if char == "\n" else char
            else:
                line += char
        return y

    def native_frame(self, name, rect, edge=5):
        """Stretch the original frame's interior, keeping pixel corners intact."""
        rect=self.pg.Rect(rect)
        source=self.artwork(name)
        if source is None or rect.w<2 or rect.h<2:return False
        bounds=source.get_bounding_rect()
        if bounds.w and bounds.h:source=source.subsurface(bounds)
        key=(name,rect.w,rect.h,edge)
        out=self.native_frames.get(key)
        if out is None:
            sw,sh=source.get_size();cut=max(1,min(edge,sw//3,sh//3))
            out=self.pg.Surface(rect.size,self.pg.SRCALPHA)
            target=min(cut*2,rect.w//3,rect.h//3)
            xs=(0,cut,sw-cut,sw);ys=(0,cut,sh-cut,sh)
            dx=(0,target,rect.w-target,rect.w);dy=(0,target,rect.h-target,rect.h)
            for iy in range(3):
                for ix in range(3):
                    part=source.subsurface((xs[ix],ys[iy],xs[ix+1]-xs[ix],ys[iy+1]-ys[iy]))
                    size=(dx[ix+1]-dx[ix],dy[iy+1]-dy[iy])
                    if min(size)>0:out.blit(self.pg.transform.scale(part,size),(dx[ix],dy[iy]))
            if len(self.native_frames)>300:self.native_frames.clear()
            self.native_frames[key]=out
        self.screen.blit(out,rect)
        if name=="作战卡" and rect.w>100 and rect.h>45:
            self.pg.draw.rect(self.screen,(33,33,53),rect.inflate(-16,-16))
        return True

    def native_seed_bank(self, rect, count):
        """Blit the original overlapping bank, then scale its complete canvas.

        Raw main-loop offsets 47494..47616: a (2.5+n)u by 1.5u canvas,
        the complete sun panel at zero, and complete 1.5u slot images at
        x=(1.5+i)u. The 1u step covers intermediate right caps. Transparent
        atlas padding belongs to this overlap and must never be trimmed.
        """
        rect = self.pg.Rect(rect)
        count = int(count)
        if count < 0 or rect.w < 1 or rect.h < 1:
            return False
        if count not in self._seed_bank_sources:
            sun, slot = self.artwork("阳光板"), self.artwork("卡槽")
            if sun is None or (count and slot is None):
                return False
            # Fixed original-art coordinates make fractional destination
            # sizes one whole-image scale rather than separately rounded tiles.
            unit = 40
            source = self.pg.Surface(((count * 2 + 5) * unit // 2, 3 * unit // 2), self.pg.SRCALPHA)
            source.blit(self.pg.transform.scale(sun, (60, 60)), (0, 0))
            if count:
                tile = self.pg.transform.scale(slot, (60, 60))
                for index in range(count):
                    source.blit(tile, (60 + index * unit, 0))
            self._seed_bank_sources[count] = source
        key = (count, rect.w, rect.h)
        image=self.native_seed_banks.get(key)
        if image is None:
            if not isinstance(self.native_seed_banks,BudgetCache) and len(self.native_seed_banks)>=32:
                self.native_seed_banks.clear()
            image=self.pg.transform.scale(self._seed_bank_sources[count], rect.size)
            self.native_seed_banks[key]=image
        self.screen.blit(image,rect.topleft)
        return True

    def box(self, rect, color=None, border=None, radius=0):
        if color is None or color==COLORS["panel"]:
            if not self.native_frame("选卡板",rect,8):self.pg.draw.rect(self.screen,COLORS["panel"],rect)
        else:self.pg.draw.rect(self.screen,color,rect)
        if border:self.pg.draw.rect(self.screen,border,rect,width=2)

    def button(self, label, rect, action, active=True, selected=False, accent=None, size=17):
        accent = accent or COLORS["blue"]
        if not self.native_frame("按钮",rect,2):self.pg.draw.rect(self.screen,COLORS["raised"],rect)
        if not active:
            shade=self.pg.Surface(self.pg.Rect(rect).size,self.pg.SRCALPHA);shade.fill((0,0,0,115));self.screen.blit(shade,rect[:2])
        if selected:self.pg.draw.rect(self.screen,accent,rect,2)
        while size>9 and (self.text_size(self.font(size),str(label))[0]>rect[2]-10 or self.font(size).get_height()>rect[3]-6):size-=1
        image = self.rendered(self.font(size), str(label), COLORS["text"] if active else COLORS["muted"])
        self.screen.blit(image, (rect[0] + (rect[2] - image.get_width()) // 2,
                                 rect[1] + (rect[3] - image.get_height()) // 2))
        if active:
            self.controls.append((self.pg.Rect(rect), action))

    def seed_packet(self, key, rect, selected=False, banned=False, picked=False, disabled=False, label=True, cost=None, display_card=None):
        """Use the shipped seed envelope and parchment, never a dashboard tile."""
        card=CARDS[key] if display_card is None else display_card
        x,y,w,h=rect;secret=card["category"]=="secret"
        base="秘籍" if secret else "高级植物卡" if card["side"]=="zombie" else "植物卡"
        source=self.artwork(base)
        if source is not None:
            source=source.subsurface(source.get_bounding_rect())
            self.screen.blit(self.pg.transform.scale(source,(int(w),int(h))),(x,y))
        else:self.box(rect)
        ink=(49,39,26);paper=(210,174,97) if secret else (218,209,236) if card["side"]=="zombie" else (221,238,187)
        # Replace the original envelope's sample illustration with this card.
        self.pg.draw.rect(self.screen,paper,(x+w*.12,y+h*.22,w*.76,h*.53))
        self.icon(card_art_name(card),(x+w*.14,y+h*.24,w*.72,h*.49))
        if label:
            title=card["name"];fs=max(10,min(14,int(w/4.3)))
            self.text(title,(x+3,y+3),ink,fs,w-6)
        value="秘籍" if secret else str(card["cost"] if cost is None else cost)
        self.pg.draw.rect(self.screen,paper if secret else (233,232,193),(x+w*.07,y+h*.77,w*.75,h*.20))
        fs=max(12,min(21,int(h*.23)))
        font=self.font(fs);font.set_bold(True)
        self.text(value,(x+w*.1,y+h*.775),ink,fs,w*.8)
        font.set_bold(False)
        if disabled or picked:
            shade=self.pg.Surface((int(w),int(h)),self.pg.SRCALPHA);shade.fill((0,0,0,100 if disabled else 65));self.screen.blit(shade,(x,y))
        if banned:
            strokes=(((x+12,y+16),(x+w-12,y+h-12)),((x+w-12,y+16),(x+12,y+h-12)))
            for color,thickness in (((25,17,15),9),((229,29,20),5)):
                for start,end in strokes:self.pg.draw.line(self.screen,color,start,end,thickness)
        elif picked:self.text("已选",(x+4,y+h*.43),COLORS["gold"],max(12,int(w*.23)),w-8)
        if selected:
            for a,b,c in (((x-2,y+9),(x-2,y-2),(x+9,y-2)),((x+w-9,y-2),(x+w+2,y-2),(x+w+2,y+9)),((x-2,y+h-9),(x-2,y+h+2),(x+9,y+h+2)),((x+w-9,y+h+2),(x+w+2,y+h+2),(x+w+2,y+h-9))):
                self.pg.draw.lines(self.screen,COLORS["gold"],False,(a,b,c),3)

    def hit(self, pos):
        for rect, action in reversed(self.controls):
            if rect.collidepoint(pos):
                return action
        return None

    def artwork(self, name):
        if name in self.images:
            return self.images[name]
        if name in ("石化火炬", "水上石化火炬", "石化火炬-蓝火"):
            # These cards are world compositions rather than atlas entries.
            # Use the same stone stump / flame rendering as the placed grave.
            from .native_style import NativeArt
            image = self.pg.Surface((128, 128), self.pg.SRCALPHA)
            NativeArt(self.pg, self.bridge, self.asset_dir).grave(
                image, name, 64, 120, 80,
                floating=name.startswith("水上"), blue=name.endswith("-蓝火"))
            self.images[name] = image
            return image
        from .pvp66_icons import artwork as secret_artwork
        image = secret_artwork(self.pg, name, self.artwork)
        if image is not None:
            self.images[name] = image
            return image
        # The embedded PvP content atlas answers its own names first, in the same
        # order NativeArt.raw resolves them for the world. Most of those units
        # have no 图片/*.png at all - their art exists only in the atlas - so
        # without this the card icon silently fell back to a coloured circle
        # while the deployed unit drew correctly.
        from .content_assets import artwork as content_artwork
        image = content_artwork(self.pg, name)
        if image is not None:
            self.images[name] = image
            return image
        from .expansion_assets import artwork as expansion_artwork
        image = expansion_artwork(self.pg,name,[self.asset_dir] if self.asset_dir else ())
        if image is not None:
            self.images[name]=image
            return image
        # Raw shipped pixels are independent of the old window's scaled atlas.
        if self.asset_dir and "/" not in name and "\\" not in name:
            for filename in (name+".png",name+"-首.png"):
                path=self.asset_dir/filename
                if path.is_file():
                    try:image=self.pg.image.load(str(path)).convert_alpha()
                    except self.pg.error:pass
                    break
        if image is None and self.bridge:
            for ui in (True, False):
                for key in (name, name + "-首", name + "右", name + "-右"):
                    image = self.bridge.surface(key, ui)
                    if image is not None:
                        break
                if image is not None:
                    break
        if image is None and self.asset_dir and "/" not in name and "\\" not in name:
            for filename in (name + ".png", name + "-首.png"):
                path = self.asset_dir / filename
                if path.is_file():
                    try:
                        image = self.pg.image.load(str(path)).convert_alpha()
                    except Exception:
                        pass
                    break
        self.images[name] = image
        return image

    def icon(self, name, rect, flip=False):
        image=self.artwork(name)
        if "脑光墓碑" in name or "残骸墓碑" in name or name=="墓碑":
            if not hasattr(self,"_grave_icons"):self._grave_icons={}
            if name not in self._grave_icons:
                from .native_style import NativeArt
                canvas=self.pg.Surface((128,128),self.pg.SRCALPHA)
                NativeArt(self.pg,self.bridge,self.asset_dir).grave(canvas,name,64,120,80,floating=name.startswith('水上'))
                self._grave_icons[name]=canvas
            image=self._grave_icons[name]
        if image is None:
            body,head=self.artwork(name+"-身"),self.artwork(name+"-首")
            if body is not None and head is not None:
                image=self.pg.Surface((max(body.get_width(),head.get_width()),max(body.get_height(),head.get_height())),self.pg.SRCALPHA)
                image.blit(body,(0,0));image.blit(head,(0,0));self.images[name]=image
        if image is None:
            color = COLORS["zombie"] if "僵尸" in name or "墓碑" in name else COLORS["plant"]
            self.pg.draw.circle(self.screen, color, (int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)), max(3, int(min(rect[2], rect[3]) * .33)))
            return
        bounds=image.get_bounding_rect()
        if bounds.w and bounds.h:image=image.subsurface(bounds)
        key = (name, int(rect[2]), int(rect[3]), bool(flip))
        cached=self.scaled.get(key)
        if cached is None:
            scale = min(rect[2] / max(1, image.get_width()), rect[3] / max(1, image.get_height()))
            scaled = self.pg.transform.scale(image, (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale))))
            cached=self.pg.transform.flip(scaled,True,False) if flip else scaled
            self.scaled[key]=cached
        image=cached
        self.screen.blit(image, (rect[0] + (rect[2] - image.get_width()) / 2,
                                 rect[1] + rect[3] - image.get_height()))

    def start(self, title, subtitle=""):
        from .world_view import WorldView
        self.controls = []
        self.native_hover = ()
        if not hasattr(self,"world"):self.world=WorldView(self.pg,self.bridge,self.asset_dir)
        self.world.draw_background(self.screen,self.screen.get_rect())
        if title:self.box((8,7,self.screen.get_width()-16,76))
        self.text(title, (24, 17), size=27)
        self.text(subtitle, (25, 57), COLORS["muted"], 15, self.screen.get_width() - 50)

    def home(self, state):
        from .menu_view import draw_home
        return draw_home(self,state)

    def join_form(self, state):
        if state.get("network_mode") == "relay":
            return self.relay_form(state, joining=True)
        width, height = self.screen.get_size()
        self.start("加入房间", "输入主机分享的地址和房间口令；IPv6 地址使用 [地址]:端口")
        x = width // 2 - 330
        self.box((x-24,126,708,350))
        for label, key, y in (("地址", "address", 165), ("房间口令", "token", 270)):
            self.text(label, (x, y), COLORS["muted"])
            self.box((x, y + 33, 660, 48), border=COLORS["blue"] if state.get("focus") == key else COLORS["line"])
            value = state.get(key, "")
            self.text(value or ("[IPv6]:24561 或 192.168.1.2:24561" if key == "address" else "与主机一致的口令"), (x + 12, y + 44), size=18, max_width=630)
            self.controls.append((self.pg.Rect(x, y + 33, 660, 48), ("focus", key)))
        self.button("连接", (x, 400, 320, 48), ("menu", "join"))
        self.button("返回", (x + 340, 400, 320, 48), ("menu", "home"))
        self.button("切换云端中继", (x, 490, 240, 40), ("network_mode", "relay"))
        self.button('观战（已满也可）',(x+340,490,320,40),('spectate',))
        self.footer(state)

    def host_form(self, state):
        if state.get("network_mode") == "relay":
            return self.relay_form(state, joining=False)
        width, height = self.screen.get_size()
        self.start("创建联机房间", "IPv6 / IPv4 双栈监听；连接前双方校验构建、规则、卡池和地图版本")
        x = width // 2 - 300
        self.box((x-24,126,648,361))
        self.text("监听端口（默认 24561）", (x, 166), size=21)
        self.box((x, 211, 600, 48), border=COLORS["blue"] if state.get("focus") == "port" else COLORS["line"])
        self.text(state.get("port", "24561"), (x + 15, 222), size=20)
        self.controls.append((self.pg.Rect(x, 211, 600, 48), ("focus", "port")))
        self.wrapped("房间开启后会生成口令，并显示本机地址候选。可以轮换并复制地址；这些候选不会自动证明公网可达。" +
                     ("手机联机请让双方连接同一 Wi-Fi，或由一方开启个人热点后分享本机地址。" if state.get("android") else ""),
                     (x, 295, 600, 90), 18, COLORS["muted"])
        self.button("开启房间", (x, 416, 288, 46), ("menu", "create_host"))
        self.button("取消", (x + 312, 416, 288, 46), ("menu", "home"))
        self.button("切换云端中继", (x, 500, 240, 40), ("network_mode", "relay"))
        self.button('允许观战：'+('开' if state.get('allow_spectators',True) else '关'),(x+312,500,288,40),('allow_spectators',))
        self.button('对战人数：'+('2v2 · 四人' if state.get('room_size')=='duo' else '1v1 · 双人'),(x,552,600,40),('room_size',))
        self.footer(state)

    def relay_form(self, state, joining):
        width, height = self.screen.get_size()
        self.start("加入云端房间" if joining else "创建云端房间", "公开大厅可直接加入；私有房间使用房间码。无需公网 IP 或端口映射")
        x = width // 2 - 330
        self.box((x-24, 108, 708, 440))
        self.button("云端中继", (x, 121, 320, 36), ("network_mode", "relay"))
        self.button("高级：IP / 端口直连", (x+340, 121, 320, 36), ("network_mode", "direct"))
        key = "token" if joining else "room_name"
        self.text("朋友分享的 10 位房间码" if joining else "房间名称", (x, 175), size=19)
        self.box((x, 204, 660, 44), border=COLORS["blue"] if state.get("focus") == key else COLORS["line"])
        self.text(state.get(key) or ("例如：0123ABCDXY" if joining else "来一局植物大战僵尸"), (x+12, 215), size=19, max_width=630)
        self.controls.append((self.pg.Rect(x, 204, 660, 44), ("focus", key)))
        self.text("中继地址（通常无需更改）", (x, 262), COLORS["muted"], 15)
        self.box((x, 287, 660, 39), border=COLORS["blue"] if state.get("focus") == "relay_endpoint" else COLORS["line"])
        self.text(state.get("relay_endpoint") or "请填写服务器地址:24562", (x+12, 297), size=17, max_width=630)
        self.controls.append((self.pg.Rect(x, 287, 660, 39), ("focus", "relay_endpoint")))
        if joining:
            self.button("浏览公开大厅", (x, 342, 660, 40), ("relay_lobby",))
        else:
            self.button("公开房间 · 大厅可见" if state.get("room_public", True) else "私有房间 · 仅凭码加入", (x, 342, 660, 40), ("relay_visibility",))
        self.button("凭码加入" if joining else "创建房间", (x, 400, 320, 48), ("menu", "join" if joining else "create_host"))
        self.button("返回", (x+340, 400, 320, 48), ("menu", "home"))
        if joining:self.button('凭码观战（已满也可）',(x,468,320,40),('spectate',))
        else:
            self.button('允许观战：'+('开' if state.get('allow_spectators',True) else '关'),(x,468,320,40),('allow_spectators',))
            self.button('对战人数：'+('2v2 · 四人' if state.get('room_size')=='duo' else '1v1 · 双人'),(x+340,468,320,40),('room_size',))
        if joining:self.text('需相同版本',(x+354,480),COLORS['muted'],17)
        self.footer(state)

    def relay_lobby(self, state):
        width, height = self.screen.get_size()
        self.start("公开联机大厅", "等待中的房间可加入；房主允许时，已满房间也可观战")
        x = 30
        self.button("刷新", (x, 101, 140, 38), ("relay_refresh",))
        self.button("创建公开房间", (x+155, 101, 210, 38), ("menu", "host"))
        self.button("房间码加入 / 返回", (width-285, 101, 255, 38), ("menu", "join_form"))
        rooms = state.get("public_rooms", [])
        page = state.get("lobby_page", 0)
        # The fixed room heads every page. It exists only in this client (nothing
        # is published to the relay) and is drawn exactly like any public room.
        from .lobby_room import AI_ROOM_NAME, AI_DUO_ROOM_NAME
        for index, (name, duo) in enumerate(((AI_ROOM_NAME, False), (AI_DUO_ROOM_NAME, True))):
            y = 157 + index*65
            self.box((x, y, width-60, 57))
            self.text(name, (x+12, y+8), size=19, max_width=width-340)
            self.text(RULES["build"] + " · 等待加入", (x+12, y+34), COLORS["muted"], 13)
            self.button("加入", (width-305, y+8, 115, 40), ("ai_room", "duo") if duo else ("ai_room",))
            self.button('观战 0/4', (width-180, y+8, 130, 40), ("ai_room", "watch_duo" if duo else "watch"))
        for index, room in enumerate(rooms[page*3:page*3+3]):
            y = 157 + (index+2)*65
            self.box((x, y, width-60, 57))
            self.text(room.get("name", "公开房间"), (x+12, y+8), size=19, max_width=width-340)
            self.text(room.get("build", "") + " · " + ("等待加入" if room.get("joinable") else "点击加入检查空位"), (x+12, y+34), COLORS["muted"], 13)
            # Older byte relays report only their first guest's occupancy.
            # The authoritative host admits four 2v2 seats via spare lanes.
            self.button("加入", (width-305, y+8, 115, 40), ("relay_join", room["code"]))
            self.button('观战 %d/4'%room.get('spectator_count',0),(width-180,y+8,130,40),('spectate',room['code']),active=bool(room.get('allow_spectators')) and room.get('spectator_count',0)<4)
        if not rooms:
            self.text("正在读取大厅……" if state.get("lobby_loading") else "暂无其它公开房间，可以先创建一个。", (x+12, 260), size=21)
        self.button("上一页", (x, 502, 130, 36), ("relay_page", -1), active=page>0)
        self.button("下一页", (x+145, 502, 130, 36), ("relay_page", 1), active=(page+1)*3<len(rooms))
        self.footer(state)

    def help(self, state):
        width, height = self.screen.get_size()
        self.start("对战规则与操作", "菜单支持 Tab / 方向键 + Enter，手柄十字 + A / B；引导可跳过并随时重看。")
        groups = (
            (("1 保护你的戴夫", "双方戴夫各40血；8秒未受伤后每2秒恢复1血。普通戴夫阵亡则僵尸胜，僵尸戴夫阵亡则植物胜。双方二段跳，落地重置；联机双方均用A/D移动、W或空格跳跃。"),
             ("2 经济与出兵", "白天12秒起每12秒补25脑光，夜无。双方生产者本局前80秒数值减伤75%，不分昼夜天气；处决例外见图鉴。阳光点按/秘籍收集，脑光自动入账。墓碑出兵；脑光/双生/成长分陆水卡，其余自动浮水。"),
             ("3 双方确认地图与交替禁选", "双方各禁两张，僵尸先手交替各选四张，再各禁两张，交替补满七槽（房主开启额外卡槽时为八槽，禁选时机不变）。每轮禁选：植物方先禁一个僵尸单位（含墓碑）和一个僵尸秘籍，僵尸方再禁一个植物单位（含工具）和一个植物秘籍，重复两次；2v2 每轮四人轮流各禁一组（秘籍禁用可跳过）；咖啡豆、花盆、睡莲和梯子僵尸不可禁。双方秘籍都占一槽并常驻。")),
            (("4 死斗与脱困传送", "7:00起禁止新增生产者（坚固脑光墓碑、石化火炬除外），已有生产提速。水面与水体内双方英雄每秒失去1生命，不触发击倒。点传送进入选目标状态，再点可取消；植物方点己方植物、僵尸方点己方墓碑。独立20秒冷却，开局可用，无安全落点不耗冷却。"),
             ("5 指挥、翻面与部署", "数字1–7对应当前卡槽；滚轮向下/向上选下一张/上一张，可跨页循环并跳过常驻秘籍。秘籍统一排在末尾并常驻。电脑版左/右键朝左/右种植，C取消；V换模仿目标，本地H换阵营。僵尸点墓碑出兵，点召集后再点战场放旗，也可拖旗；倒地前已插旗时，僵尸戴夫倒地第4秒若旗仍在立即起身（否则8秒）；有旗时传送冷却减半。F或再次点召集清除旗；无旗时F切换跟随/追击。按键可在设置修改。"),
             ("6 标记、保护与联机", "猫尾秘籍开局前120秒不生效，香蒲植物不受此限制。猫尾类技能需近距离视线标记才能锁定敌方英雄；英雄有短时控制保护、灰烬与吞咽单轮伤害上限。联机以主机裁定，断线等待重连；设置/帮助不会单方暂停对局。")),
            (("7 手机触控与布局", "虚拟键移动/跳跃；空手点战场也跳跃并保留植物标记，阳光、炮身和墓碑优先交互。种植默认跟随戴夫，自动/左/右切换朝向。传送点按进入并亮起，再点取消；召集先点按钮再点落点。设置中每个动作键可独立移动、缩放。"),
             ("8 触控细节与秘籍", "自动／左／右切换种植与铲子操作；自动跟随戴夫朝向。水盆左键铲除，右键变全新花盆，长按也可执行右键并跳过保护壳。自动瞄准时点目标开炮，点取消或长按取消；长按卡牌看详情。闪现后恢复4生命，可超过上限；魅惑秘籍缩短魅惑菇75%冷却，可叠加速植。"),
             ("9 房主观战与入座", "选图阶段可转为观战，观众可点击空位入座。房主观战时仍管理地图和房间，由两名入座玩家对战；观众不操作英雄。结算后可入空位。禁选和战斗进行中保持当前席位，房主退出会关闭房间。")),
        )
        page = min(len(groups)-1, max(0, state.get("help_page", 0)))
        block_h = max(112, (height - 260) // 3)
        for index, (title, body) in enumerate(groups[page]):
            y = 114 + index * block_h
            self.box((32, y, width - 64, block_h - 10))
            self.text(title, (52, y + 12), COLORS["gold"], 22)
            self.wrapped(body, (52, y + 49, width - 104, block_h - 58), 17, COLORS["text"], 22)
        self.button("上一页", (32, height - 91, 150, 40), ("help_page", -1), active=page > 0)
        self.text("%d / %d" % (page + 1,len(groups)), (205, height - 81), COLORS["muted"])
        self.button("下一页", (285, height - 91, 150, 40), ("help_page", 1), active=page < len(groups)-1)
        self.button("跳过 / 返回" if page == 0 else "我已了解 / 返回", (width - 265, height - 91, 233, 40), ("help_done",))
        self.footer(state)

    def settings(self, state):
        width, height = self.screen.get_size()
        self.start("对战设置与操作", "对战设置独立保存，不读取或覆盖旧模式存档；已打开 %d 个菜单手柄。" % state.get("controller_count", 0))
        self.box((22,100,width-44,height-197))
        x = 40
        labels = (("植物左移", "plant_left"), ("植物右移", "plant_right"), ("植物跳跃", "plant_jump"),
                  ("僵尸左移/墓碑←", "zombie_left"), ("僵尸右移/墓碑→", "zombie_right"), ("僵尸跳跃/墓碑↑", "zombie_jump"),
                  ("墓碑↓（解除封印）", "grave_down"),
                  ("僵尸指挥", "command"), ("卡槽翻面", "page"), ("取消操作", "cancel"), ("模仿目标", "copy"))
        for index, (label, key) in enumerate(labels):
            col, row = index % 2, index // 2
            bx, by = x + col * 292, 120 + row * 36
            self.text(label, (bx, by + 8), size=14 if len(label) > 5 else 17)
            self.button(self.pg.key.name(state["bindings"][key]), (bx + 132, by, 135, 33), ("bind", key), selected=state.get("bind_pending") == key, size=15)
        for row, (label, key) in enumerate((("界面尺度", "ui_scale"), ("战场视距", "zoom"))):
            by = 340 + row * 52
            self.text(label + " %.2f" % state[key], (x, by + 10), size=18)
            self.button("-", (x + 190, by, 75, 40), ("setting", key, -.1))
            self.button("+", (x + 275, by, 75, 40), ("setting", key, .1))
        self.button("数字冷却：" + ("开" if state.get("numeric_cd", True) else "关"), (x, 444, 170, 40), ("numeric_cd",))
        if state.get("android"):
            # Touch controls are the only input path on Android; the toggle
            # stays visible but cannot be switched off there.
            self.button("触摸按键：开（触屏必选）", (x + 180, 444, 190, 40), ("touch_mode",),
                        active=False, selected=True)
        else:
            self.button("触摸按键：" + ("开" if state.get("touch_mode") else "关"), (x + 180, 444, 190, 40), ("touch_mode",),
                        selected=bool(state.get("touch_mode")))
        self.button("布局：" + ("左手" if state.get("touch_mirror") else "右手"), (x + 380, 444, 170, 40), ("touch_mirror",))
        self.text("按键大小", (x, 500), size=17)
        size = state.get("touch_size", 1)
        if not isinstance(size, int) or isinstance(size, bool):
            size = 1
        self.button("-", (x + 112, 492, 56, 38), ("touch_size", -1), active=size > 0)
        self.button(("小", "中", "大")[min(2, max(0, size))], (x + 176, 492, 76, 38), ("touch_size", 0), active=False)
        self.button("+", (x + 260, 492, 56, 38), ("touch_size", 1), active=size < 2)
        if state.get("touch_mode"):
            self.button("自定义按键布局…", (x + 380, 492, 224, 38), ("menu", "touch_layout"))
        rx, rw = 650, width - 690
        self.text("画面", (rx, 124), COLORS["gold"], 22)
        if not state.get("android"):
            self.button("全屏：" + ("开" if state.get("fullscreen") else "关"), (rx, 169, rw, 40), ("fullscreen",))
        self.button("低特效：" + ("开" if state.get("low_effects") else "关"), (rx, 222, (rw-8)/2, 40), ("low_effects",),size=16)
        self.button("性能记录", (rx+(rw+8)/2, 222, (rw-8)/2, 40), ("menu","performance"),size=16)
        self.text("声音", (rx, 268), COLORS["gold"], 22)
        self.button("游戏音效：" + ("开" if state.get("sound") else "关"), (rx, 302, rw, 34), ("sound",),size=16)
        self.text("音量 %d%%" % round(state.get("volume", .35) * 100), (rx, 350), size=16)
        self.button("-", (rx+rw-112, 342, 50, 34), ("volume", -.1))
        self.button("+", (rx+rw-50, 342, 50, 34), ("volume", .1))
        self.button("背景音乐："+('开' if state.get('music',True) else '关'),(rx,390,rw,34),('music',),size=16)
        self.text('音量 %d%%'%round(state.get('music_volume',.25)*100),(rx,442),size=16)
        self.button('-',(rx+rw-112,434,50,34),('music_volume',-.1))
        self.button('+',(rx+rw-50,434,50,34),('music_volume',.1))
        self.button("自动保存回放：" + ("开" if state.get("save_replays") else "关"), (rx, 500, rw, 40), ("save_replays",))
        if state.get("can_surrender"):
            # Only offered while a battle is live: this ends the match in the
            # opponent's favour, so it never appears in the home-screen menus.
            self.button("确认投降？再点一次" if state.get("confirm_surrender") else "投降认输",
                        (rx, height - 90, rw, 40), ("surrender",),
                        selected=bool(state.get("confirm_surrender")))
        self.button("返回", (40, height - 90, 180, 42), ("menu", "back"))
        self.button("恢复默认设置", (235, height - 90, 220, 42), ("reset_settings",))
        self.button("卡槽按键", (470, height - 90, 155, 42), ("menu", "slot_keys"), size=16)
        self.button("动作快捷键",(x+380,392,220,40),('menu','action_keys'),size=17)
        self.footer(state)

    def action_keys(self,state):
        self.start('动作快捷键','点击按键重新绑定；传送、召集、铲子再次按下可取消。')
        labels=(('传送选目标','teleport'),('召集点','rally'),('铲子','shovel'),('暂停投票','pause'),
                ('跟随 / 追击','command'),('取消操作','cancel'),('模仿目标','copy'),('卡槽翻页','page'))
        width,height=self.screen.get_size();pitch=(width-90)//2
        self.box((22,104,width-44,height-206))
        for index,(label,key) in enumerate(labels):
            x=45+index%2*pitch;y=128+index//2*84
            self.text(label,(x,y+12),size=19)
            self.button(self.pg.key.name(state['bindings'][key]).upper(),(x+160,y,pitch-190,46),('bind',key),selected=state.get('bind_pending')==key,size=20)
        self.button('返回设置',(45,height-90,200,42),('menu','back'))
        self.footer(state)

    def profile(self,state):
        from .player_profile import stats_text
        width,height=self.screen.get_size()
        self.start('玩家名称与战绩','本机累计战绩公开显示在房间；对局结算自动记录，独立于回放保存。')
        self.box((22,104,width-44,height-206))
        self.text('玩家名称（最多 16 字）',(45,132),size=22)
        rect=(45,178,min(540,width-90),52)
        self.box(rect,border=COLORS['gold'] if state.get('focus')=='player_name' else COLORS['line'])
        self.text(state.get('player_name','玩家'),(60,191),size=23)
        self.controls.append((self.pg.Rect(rect),('focus','player_name')))
        self.button('保存名称',(45,250,220,44),('profile_save',),size=20)
        stats=state.get('player_stats') or {}
        self.text('总计：'+stats_text(stats),(45,320),COLORS['gold'],24,width-90)
        for i,side in enumerate(('plant','zombie')):
            self.text(('植物：' if side=='plant' else '僵尸：')+stats_text(stats.get('by_side',{}).get(side)),(45,360+i*37),COLORS[side],22,width-90)
        self.wrapped('胜率 = 胜场 ÷ 总场次（含平局），按参赛阵营分别累计。观战、回放、本地演练和未判胜负的中止局不计入；结算只记一次。',(45,452,min(560,width-90),82),17)
        # PvP62 saves: name, record and custom maps belong to one save.
        px=min(640,width-330);pw=width-px-45
        if pw>=260:
            self.text('存档（名称、战绩、地图各自独立）',(px,132),COLORS['gold'],18,pw)
            rows=state.get('profiles') or []
            for i,row in enumerate(rows[:8]):
                stats=row.get('stats') or {}
                total=stats.get('wins',0)+stats.get('losses',0)+stats.get('draws',0)
                rate=('%.0f%%'%(100.*stats.get('wins',0)/total)) if total else '—'
                label='%d. %s · 胜率 %s'%(row.get('number',i+1),row.get('name','玩家'),rate)
                self.button(label,(px,164+i*44,pw,38),('profile_switch',row['id']),
                            selected=bool(row.get('current')),size=16)
            y=164+min(8,len(rows))*44+6
            self.button('新建存档',(px,y,(pw-10)//2,40),('profile_new',),size=17)
            current=next((r for r in rows if r.get('current')),None)
            if current and current.get('id')!='default':
                pending=state.get('profile_delete_pending')==current.get('id')
                self.button('确认删除' if pending else '删除存档',(px+(pw-10)//2+10,y,(pw-10)//2,40),
                            ('profile_delete',current['id']),selected=pending,size=17)
        self.button('返回',(45,height-90,200,42),('menu','back'))
        self.footer(state)

    def draft_reference(self,view,state):
        width,height=self.screen.get_size();side=state.get('advice_side','plant');advice=state.get('draft_advice',{})
        seat=state.get('advice_seat',side)
        labels={'plant':'植物一席','plant2':'植物二席','zombie':'僵尸一席','zombie2':'僵尸二席'} if view.get('mode')=='duo' else {'plant':'植物','zombie':'僵尸'}
        self.start('参考阵容 · '+labels.get(seat,seat),advice.get('summary','依据本局地图与禁用推荐；点击卡牌预览后确认选取。'))
        for i,(key,label) in enumerate(labels.items()):
            self.button(label,(30+i*105,98,100,36),('draft_reference',key),selected=seat==key,size=16)
        self.button('载入已存阵容',(width-390,98,170,36),('load_deck',),size=16)
        self.button('保存当前阵容',(width-210,98,180,36),('save_deck',),size=16)
        deck=advice.get('deck',[]);row_h=min(105,(height-248)//4);col_w=(width-75)//2
        for i,key in enumerate(deck):
            if key not in CARDS:continue
            x=30+(i%2)*(col_w+15);y=148+(i//2)*row_h;chosen=key in view.get('decks',{}).get(seat,[])
            self.box((x,y,col_w,row_h-7),border=COLORS[side] if chosen else COLORS['line'])
            self.seed_packet(key,(x+7,y+5,48,row_h-17),label=False)
            self.text(CARDS[key]['name']+(' · 已锁定' if chosen else ''),(x+67,y+7),COLORS['gold'],18,col_w-78)
            self.wrapped(advice.get('reasons',{}).get(key,'适合当前地图与阵容'),(x+67,y+35,col_w-78,row_h-46),14)
            if not chosen:self.controls.append((self.pg.Rect(x,y,col_w,row_h-7),('advice_card',key)))
        self.button('返回选卡',(30,height-90,200,42),('menu','back'),size=18)
        self.footer(state)

    def slot_keys(self, state):
        self.start("卡槽快捷键", "默认 1–8 对应当前页卡槽（第 8 槽用于开启额外卡槽的对局）；点击按键可修改，Esc 取消改键。")
        for i in range(1,9):
            x=45+((i-1)%2)*430;y=130+((i-1)//2)*76
            self.text("卡槽 %d"%i,(x,y+12),size=21)
            key='slot_%d'%i
            self.button(self.pg.key.name(state['bindings'][key]).upper(),(x+140,y,220,48),
                        ('bind',key),selected=state.get('bind_pending')==key,size=22)
        self.button("返回设置",(45,self.screen.get_height()-90,200,42),('menu','back'))
        self.footer(state)

    def performance(self,state):
        width,height=self.screen.get_size()
        self.start('性能记录','记录本机实际耗时，帮助定位卡顿；保存于游戏数据目录的 performance 文件夹。')
        self.text('状态：'+state.get('performance_recording','未开始'),(45,135),size=23)
        for i,(label,action) in enumerate((('开始基础记录',('perf_start',False)),('开始详细记录',('perf_start',True)),('导出当前记录',('perf_export',)),('停止并保存',('perf_stop',)))):
            self.button(label,(45+i*220,200,208,48),action,size=19)
        top=285
        from .perf_hooks import boost_available,boost_enabled
        if boost_available():
            # PvP71 Android: switch the performance requests for an A/B check and
            # export the core/frequency/thermal diagnostics in one tap.
            self.button('性能申请：'+('开' if boost_enabled() else '关'),(45,262,208,44),('perf_boost',),size=18)
            self.button('导出性能诊断',(265,262,208,44),('perf_diag_export',),size=18)
            top=322
        from .display_pipeline import QUALITY_LABELS
        self.button('战场画质：'+QUALITY_LABELS.get(state.get('world_quality'),'原画'),(45,top,208,40),('world_quality',),size=18)
        self.button('画面缩放：'+('像素' if state.get('display_filter')=='pixel' else '平滑'),(265,top,208,40),('display_filter',),size=18)
        self.button('自动画帧：'+('开' if state.get('display_budget',True) else '关'),(485,top,208,40),('display_budget',),size=18)
        self.wrapped('战场画质独立于文字和按键大小。自动画帧会在绘制较慢时减少显示帧，输入、联机和战斗判定继续处理。详细记录有额外计时开销，请与基础记录分开比较。',(45,top+52,width-90,95),18)
        self.wrapped(state.get('performance_path',''),(45,top+150,width-90,65),15)
        self.button('返回设置',(45,height-90,200,42),('menu','back'))
        self.footer(state)

    def almanac(self, state):
        width, height = self.screen.get_size()
        self.start("对战图鉴", "可切换 PvP 数值与旧模式基础表；旧表仅作参考，不代表所有动态秘籍加成。")
        left_width = int(width * .49)
        self.box((20, 107, left_width - 20, height - 163))
        categories = (("植物", "plant"), ("工具", "tool"), ("植物秘籍", "secret"), ("僵尸", "zombie"), ("墓碑", "economy"), ("僵尸秘籍", "zsecret"))
        for index, (label, key) in enumerate(categories):
            bw = (left_width - 60) // len(categories)
            self.button(label, (32 + index * (bw + 3), 119, bw, 32), ("almanac_tab", key), selected=state["almanac_category"] == key, size=13)
        self.box((32, 164, left_width - 48, 34), border=COLORS["blue"] if state.get("focus") == "search" else COLORS["line"])
        self.text("搜索：" + state.get("search", ""), (42, 171), COLORS["muted"], 15, left_width - 68)
        self.controls.append((self.pg.Rect(32, 164, left_width - 48, 34), ("focus", "search")))
        category = state['almanac_category']
        cards = [c for c in CARDS.values() if c['category'] == ('secret' if category == 'zsecret' else category)
                 and (c['category'] != 'secret' or c['side'] == ('zombie' if category == 'zsecret' else 'plant'))
                 and state.get("search", "") in c["name"]]
        rows = max(3, min(7, (height - 308) // 51));page_size = rows * 2
        page = min(state["almanac_page"], max(0, (len(cards) - 1) // page_size));state["almanac_page"] = page
        bw = (left_width - 57) // 2
        for index, card in enumerate(cards[page * page_size:(page + 1) * page_size]):
            x, y = 32 + index % 2 * (bw + 9), 211 + index // 2 * 51
            self.box((x, y, bw, 44), COLORS["raised"], COLORS["gold"] if state.get("detail") == card["id"] else COLORS["line"], 5)
            self.icon(card_art_name(card), (x + 3, y + 3, 38, 36))
            self.text(card["name"], (x + 47, y + 13), size=15, max_width=bw - 55)
            self.controls.append((self.pg.Rect(x, y, bw, 44), ("almanac_card", card["id"])))
        self.button("上一页", (32, height - 106, 112, 34), ("almanac_page", -1), size=15)
        self.text("%d / %d" % (page + 1, max(1, math.ceil(len(cards) / page_size))), (160, height - 99), COLORS["muted"], 16)
        self.button("下一页", (left_width - 128, height - 106, 112, 34), ("almanac_page", 1), size=15)
        x, w = left_width + 18, width - left_width - 39
        self.box((x, 107, w, height - 163))
        context = state.get("reference_context", "pvp")
        self.button("PvP", (x + 16, 171, 88, 32), ("reference_context", "pvp"), selected=context == "pvp", size=15)
        self.button("旧模式参考", (x + 115, 171, 145, 32), ("reference_context", "legacy"), selected=context == "legacy", size=15)
        card = CARDS.get(state.get("detail"))
        if card:
            self.text(card["name"], (x + 18, 128), COLORS["gold"], 24)
            self.icon(card_art_name(card), (x + w - 115, 119, 84, 84))
            if context == "legacy":
                from .reference import describe_reference
                value = describe_reference(self.bridge, card["id"])
            else:
                value = describe(card["id"],state.get("reference_decks",{}).get(card["side"],[]),state.get("reference_night",False),
                                 detailed=state.get('almanac_detailed',False))
            lines, line = [], ""
            font = self.font(19)
            for char in value + "\n":
                if char == "\n" or self.text_size(font, line + char)[0] > w - 42:
                    lines.append(line);line = "" if char == "\n" else char
                else:
                    line += char
            count = max(1, (height - 345) // 28)
            scroll = min(state["almanac_scroll"], max(0, len(lines) - count));state["almanac_scroll"] = scroll
            for index, line in enumerate(lines[scroll:scroll + count]):
                self.text(line, (x + 18, 222 + index * 28), size=19)
            self.button("上滚", (x + 18, height - 106, 100, 34), ("almanac_scroll", -3), size=15)
            self.button("下滚", (x + 128, height - 106, 100, 34), ("almanac_scroll", 3), size=15)
            if context!='legacy':
                self.button('查看精简版' if state.get('almanac_detailed',False) else '查看详细版',
                            (x+w-138,height-106,120,34),('almanac_detail',),size=15)
        else:
            self.text("从左侧选择卡牌", (x + 22, 150), COLORS["muted"], 20)
        self.button("返回", (width - 150, 20, 120, 40), ("menu", "back"))
        self.footer(state)

    def mini_map(self, terrain, rect, players=None):
        from .world_view import WorldView
        if not hasattr(self,"world"):self.world=WorldView(self.pg,self.bridge,self.asset_dir)
        return self.world.preview(self.screen,terrain,rect,players)

    def footer(self, state):
        width, height = self.screen.get_size()
        message=" · ".join(x for x in (state.get("message",""),state.get("cooperation_hint","")) if x)
        self.text(message, (24, height - 35), (43,29,18), 16, width - 48)
        if state.get("link_notice"):
            self.text(state["link_notice"], (24, height - 57), COLORS["bad"], 16, width - 48)

    def pointer_feedback(self,position,pressed=None,flashed=None):
        hit=self.hit(position)
        for rect,action in self.controls:
            if action in (("hud_block",),):continue
            down=action==pressed;flash=action==flashed;hover=action==hit and rect.collidepoint(position)
            # Original-style pages (PvE select / shop) show hover in the art itself.
            if hover and not (down or flash) and action[0] in getattr(self,'native_hover',()):continue
            if not (down or flash or hover):continue
            if down or flash:
                overlay=self.pg.Surface(rect.size,self.pg.SRCALPHA)
                overlay.fill((25,13,5,75) if down else (255,231,155,65))
                self.screen.blit(overlay,rect.topleft)
            self.pg.draw.rect(self.screen,(255,224,125),rect,3 if down or flash else 2)

    def map_select(self, view, state):
        from .menu_view import draw_map_select
        return draw_map_select(self,view,state)

    def room_info(self, view, state):
        width,height=self.screen.get_size()
        self.start("房间规则与连接详情", "本页展示当前房间的权威规则、双方身份和版本校验信息。")
        rules=view.get("rules",RULES);info=state.get("connection_details",{})
        x,w=28,int(width*.46)
        self.box((x,111,w,height-204))
        self.text("固定规则",(x+18,129),COLORS["gold"],23)
        value=("植物 %d 槽；僵尸 %d 槽\n双方各禁对方单位 %d 个、对方秘籍 %d 个（秘籍禁用可跳过）\n每轮禁选：植物方禁僵尸单位+秘籍→僵尸方禁植物单位+秘籍，重复两次\n秘籍占一槽、战斗常驻并排在末尾\n咖啡豆、花盆、睡莲和梯子僵尸不可禁\n第 %d 秒死斗：禁新增生产单位\n现有生产速度 × %g\n死斗水面与水体内双方英雄每秒失去1生命，不触发击倒\n基础墓碑分地面与水上卡，无水地图不提供水上卡\nBoss 不入僵尸卡池\n地图左右连通；戴夫阵亡判负\n环境：晴天；水生卡按真实出兵条件筛选" % (rules["plant_slots"],rules["zombie_slots"],rules["unit_bans"],rules["secret_bans"],rules["deathmatch_seconds"],rules["production_multiplier"]))
        value+='\n白天不强制携带生产植物；带前体秘籍仍需前体\n夜晚带前体秘籍须保留生产植物\n玩家名称与本机战绩可在首页设置'
        self.wrapped(value,(x+18,174,w-36,height-290),17,COLORS["text"],28)
        rx=x+w+16;rw=width-rx-28
        self.box((rx,111,rw,height-204))
        self.text("身份与连接",(rx+18,129),COLORS["gold"],23)
        members=[]
        from .player_profile import stats_text
        for peer,side in view.get("members",{}).items():
            label=("本地玩家1" if peer=="host" else "本地玩家2") if info.get("mode")=="local" else ("本机" if peer==info.get("peer_id") else "对方")
            profile=view.get('player_profiles',{}).get(peer)
            if profile:label=profile['name']+' · '+label
            seat_name={"plant":"植物","zombie":"僵尸","plant2":"植物2","zombie2":"僵尸2"}.get(side,side)
            members.append(seat_name+" · "+label+" · "+("在线" if view.get("connected",{}).get(peer) else "已断开")+" · "+peer)
            if profile:
                for faction,title in (('plant','植物'),('zombie','僵尸')):
                    members.append('  '+title+'战绩：'+stats_text(profile.get('by_side',{}).get(faction)))
        seat_count=len(view.get('seats') or ("plant","zombie"))
        if len(view.get('members',{}))<seat_count:members.append("空座位：等待加入（%d/%d）"%(len(view.get('members',{})),seat_count) if seat_count>2 else "另一阵营：等待加入")
        identity=info.get("identity",{})
        lines=members+["方式："+{"local":"本地双人演练","host":"TCP主机","guest":"TCP客机"}.get(info.get("mode"),"尚未连接"),
                       "连接状态："+str(info.get("transport_state","")),
                       "地址："+(info.get("address") or "本机候选见地图页"),
                       "快照接收：%d · 主机快照10Hz" % info.get("snapshots",0),
                       "构建："+str(identity.get("build","")),
                       "规则校验："+str(identity.get("rules_hash","")),
                       "卡池校验："+str(identity.get("catalog_hash","")),
                       "地图适配："+str(identity.get("map_adapter",""))]
        wrapped=[];line="";font=self.font(14)
        for char in "\n".join(lines)+"\n":
            if char=="\n" or self.text_size(font,line+char)[0]>rw-36:
                wrapped.append(line);line="" if char=="\n" else char
            else:line+=char
        count=max(1,(height-310)//22)
        scroll=min(state.get("room_info_scroll",0),max(0,len(wrapped)-count));state["room_info_scroll"]=scroll
        for index,line in enumerate(wrapped[scroll:scroll+count]):
            self.text(line,(rx+18,174+index*22),COLORS["muted"],14)
        self.button("上滚",(rx+18,height-130,100,29),("room_info_scroll",-3),size=14)
        self.button("下滚",(rx+129,height-130,100,29),("room_info_scroll",3),size=14)
        self.button("返回房间",(width-242,height-81,210,38),("menu","back"))
        if view.get('can_kick') or view.get('can_request_config'):
            self.button(('请求切换观战：' if view.get('can_request_config') else '允许观战：')+('开' if view.get('allow_spectators',True) else '关')+' · %d人'%view.get('spectator_count',0),
                        (32,height-81,290,38),('allow_spectators',),active=bool(view.get('can_kick')) or view.get('phase')=='config')
        self.footer(state)

    def _card_grid(self, side, rect, view, state):
        from .draft_view import card_grid
        return card_grid(self,side,rect,view,state)

    def bp(self, view, state):
        from .draft_view import draw
        return draw(self,view,state)

    def ban_summary(self, view, state):
        width, height = self.screen.get_size()
        self.start("本局禁选清单", "植物、僵尸单位及两方秘籍分别列示。咖啡豆、花盆、睡莲和梯子僵尸不可禁。")
        for index, (title, side) in enumerate((("植物单位", "plant"), ("僵尸单位", "zombie"), ("植物秘籍", "secret"), ("僵尸秘籍", "zsecret"))):
            w = (width - 84) // 4;x = 24 + index * (w + 12)
            self.box((x, 122, w, height - 235))
            self.text(title, (x + 15, 140), COLORS["gold"], 20)
            names = [CARDS[key]['name'] for key in view.get('bans', [])
                     if (('zsecret' if CARDS[key]['side'] == 'zombie' else 'secret')
                         if CARDS[key]['category'] == 'secret' else CARDS[key]['side']) == side]
            self.wrapped("\n\n".join(names) or "无", (x + 15, 201, w - 30, height - 329), 18)
        self.button("返回 BP", (width - 240, height - 87, 210, 42), ("menu", "back"))
        self.footer(state)

    def world_point(self, pos):
        if not self.camera:
            return None
        left, top, scale, rect, width = self.camera
        if not self.pg.Rect(rect).collidepoint(pos):
            return None
        return ((left + (pos[0] - rect[0]) / scale) % width,
                top + (pos[1] - rect[1]) / scale)

    def battle(self, view, state):
        from .battle_view import draw
        return draw(self,view,state)

    def result(self, view, state):
        width, height = self.screen.get_size()
        battle = view.get("battle") or {}
        result = battle.get("result") or view.get("result") or {}
        winner = result.get("winner") if isinstance(result, dict) else result
        title = "植物方获胜" if winner == "plant" else "僵尸方获胜" if winner == "zombie" else "平局" if winner == "draw" else "对局结束"
        reasons = {"hero_death": "同一判定帧双方英雄阵亡" if winner == "draw" else "英雄阵亡",
                   "surrender": "僵尸方认输" if winner == "plant" else "植物方认输",
                   "disconnect": "断线重连超时，对局中止", "load_timeout": "双方载入确认超时，对局中止",
                   "leave": "对方离开房间，对局中止", "kick": "房主请出对方，对局中止",
                   "host_closed": "观战房主关闭房间，对局结束"}
        if isinstance(result, dict) and result.get("forfeit") in ("plant", "zombie"):
            loser = "植物方" if result["forfeit"] == "plant" else "僵尸方"
            reasons["leave"] = loser + "退出对局，判负"
            reasons["disconnect"] = loser + "断线未重连，判负"
        reason = reasons.get(result.get("reason"), str(result.get("reason", ""))) if isinstance(result, dict) else ""
        self.start(title, "结束原因：" + reason + " · 结果由主机统一裁定")
        if view.get('can_change_role') and view.get('local_sides'):
            self.button("转为观战",(width-202,94,170,36),("spectator_role","spectator"),size=16)
        x = width // 2 - 350
        duo = (view.get("mode") or "duel") == "duo"
        members = view.get('match_members', view.get('members', {}))
        local = battle.get("local_seat")
        for side, col in (("plant", 0), ("zombie", 1)):
            self.box((x + col * 365, 150, 335, 270), border=COLORS[side])
            if duo:
                # 2v2: both seats of the team, each on its own line.
                self.text("植物方" if side == "plant" else "僵尸方", (x + col * 365 + 20, 166), COLORS[side], 23, 295)
                for row, seat in enumerate((side, side + "2")):
                    # A second-seat client sees its own seat under the faction key.
                    key = seat
                    if local and local.startswith(side):
                        key = side if seat == local else local if seat == side else seat
                    p = battle.get("players", {}).get(key, {})
                    stats = p.get("stats", {})
                    member = next((peer for peer, s in members.items() if s == seat), None)
                    name = view.get('player_profiles', {}).get(member, {}).get('name') or ("玩家 %d" % (row + 1))
                    self.text(name, (x + col * 365 + 20, 206 + row * 104), COLORS["text"], 19, 295)
                    self.wrapped("生命 %d · 收入 %d · 消费 %d\n英雄伤害 %d · 损失生产者 %d" % (
                        max(0, p.get("hp", 0)), stats.get("earned", 0), stats.get("spent", 0),
                        stats.get("hero_damage", 0), stats.get("producer_lost", 0)),
                        (x + col * 365 + 20, 234 + row * 104, 295, 70), 16)
                continue
            member=next((peer for peer,team in view.get('match_members',view.get('members',{})).items() if team==side),None)
            name=view.get('player_profiles',{}).get(member,{}).get('name')
            self.text(("植物方" if side == "plant" else "僵尸方")+(' · '+name if name else ''), (x + col * 365 + 20, 174), COLORS[side], 23,295)
            p = battle.get("players", {}).get(side, {})
            stats = p.get("stats", {})
            self.wrapped("剩余生命：%d\n经济收入：%d\n部署消费：%d\n英雄伤害：%d\n损失生产者：%d" % (max(0, p.get("hp", 0)), stats.get("earned", 0), stats.get("spent", 0), stats.get("hero_damage", 0), stats.get("producer_lost", 0)), (x + col * 365 + 20, 220, 295, 185), 19)
        has_opponent = len(view.get("members", {})) >= 2
        if has_opponent:
            self.button("同卡组复赛", (x, 445, 700, 40), ("rematch", 'same_deck'))
            self.button("原阵营 · 重新禁选", (x, 495, 335, 40), ("rematch", False),size=18)
            self.button("交换阵营 · 重新禁选", (x + 365, 495, 335, 40), ("rematch", True),size=18)
        elif view.get("can_kick"):
            self.button("回到房间（等待新玩家）", (x, 460, 335, 48), ("room_reopen",))
        else:
            self.button("原阵营复赛", (x, 460, 335, 48), ("rematch", False), active=False)
            self.button("交换阵营复赛", (x + 365, 460, 335, 48), ("rematch", True), active=False)
        self.button("保存回放日志", (x, 546, 335, 38), ("export_log",))
        self.button("返回首页", (x + 365, 546, 335, 38), ("leave",))
        self.footer(state)

    def confirm_leave(self):
        width, height = self.screen.get_size()
        overlay = self.pg.Surface((width, height), self.pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180));self.screen.blit(overlay, (0, 0))
        rect = (width // 2 - 240, height // 2 - 100, 480, 200)
        self.box(rect, border=COLORS["line"])
        self.text("离开本局？", (rect[0] + 24, rect[1] + 22), size=24)
        self.text("进行中的联机对局会通知另一方。", (rect[0] + 24, rect[1] + 68), COLORS["muted"], 17)
        self.controls = []
        self.button("继续对战", (rect[0] + 24, rect[1] + 125, 207, 43), ("cancel_leave",))
        self.button("确定离开", (rect[0] + 249, rect[1] + 125, 207, 43), ("confirm_leave",))

    def audit_error(self):
        width,height=self.screen.get_size()
        overlay=self.pg.Surface((width,height),self.pg.SRCALPHA)
        overlay.fill((0,0,0,180));self.screen.blit(overlay,(0,0))
        rect=(width//2-300,height//2-110,600,220)
        self.box(rect,border=COLORS["bad"])
        self.text("对局因日志写入失败已暂停",(rect[0]+24,rect[1]+23),COLORS["bad"],23)
        self.wrapped("可以导出已有记录或退出。本次暂停不代表任何阵营获胜；暂停期间不继续执行战斗操作。",(rect[0]+24,rect[1]+72,552,65),17)
        self.controls=[]
        self.button("导出已有记录",(rect[0]+24,rect[1]+155,264,42),("export_log",))
        self.button("退出房间",(rect[0]+312,rect[1]+155,264,42),("leave",))
