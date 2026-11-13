"""Playable pygame PvP client: local room, network host and network guest."""
import math
import base64
import json
import os
import secrets
import sys
import time
import zlib
from pathlib import Path

from .catalog import CARDS, RULES, allowed, catalog_hash, rules_hash, map_card_error
from .native_bridge import NativeBridge
from .network import ServerTransport, ClientTransport, DEFAULT_PORT
from .latency import LatencyTracker
from .relay import RelayHostTransport, RelayClientTransport, LobbyQuery, configured_endpoint, normalize_code
from .room import Room
from .rendering import Renderer
from .ui_data import local_endpoints, load_decks, save_decks, network_error, copy_text, read_clipboard
from .preview import PreviewBattle
from .audit_log import AuditLogError
from .controllers import MenuControllers
from .maps import ADAPTER_REVISION, MapSnapshot, map_registry
from .hud import input_block_text, opponent_idle_text, battle_deck, bank_page_size
from .map_editor_actions import MapEditing
from .replay_ui import ReplayUI
from .spectator_ui import SpectatorUI
from .pve_ui import PveUI, is_scripted
from .teams import SEATS, scripted, team_of, local_perspective


MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


def input_block_reason(state, view):
    """Why the local client is not sending input right now, or None if it is.

    Every branch used to be a bare early return inside ``move_inputs``, so a
    guest whose window lost focus, or who opened the almanac mid-battle, went
    silent with no trace on either screen: the opponent only saw a hero that
    stopped moving. Keeping the answer in one place lets the HUD say it.
    """
    if view.get("phase") != "battle":
        return "not_battle"
    if view.get('spectating'):return 'spectating'
    if view.get("audit_error"):
        return "audit"
    if state.get("screen") != "room":
        return "viewing"
    if state.get("focus"):
        return "textbox"
    if state.get("confirm_leave") or state.get("leave_pending"):
        return "leaving"
    if not state.get("focused", True):
        return "unfocused"
    return None


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid number")
    return number


# Unsent bytes toward one peer above which the host skips a battle snapshot.
SNAPSHOT_BACKLOG_BYTES = 96 * 1024


def pack_snapshot(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("权威快照超出大小限制")
    return {"type": "room_snapshot", "encoding": "zlib-json",
            "data": base64.b64encode(zlib.compress(raw, 4)).decode("ascii")}


def unpack_snapshot(payload):
    if payload.get("encoding") != "zlib-json" or not isinstance(payload.get("data"), str):
        raise ValueError("快照编码无效")
    compressed = base64.b64decode(payload["data"].encode("ascii"), validate=True)
    inflater = zlib.decompressobj()
    raw = inflater.decompress(compressed, MAX_SNAPSHOT_BYTES + 1)
    if len(raw) > MAX_SNAPSHOT_BYTES or inflater.unconsumed_tail or not inflater.eof or inflater.unused_data:
        raise ValueError("快照损坏或超出大小限制")
    value = json.loads(raw.decode("utf-8"), parse_float=_finite_float,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid number")))
    if not isinstance(value, dict):
        raise ValueError("快照不是房间对象")
    return value


def _exe_dir():
    """Directory of the host executable, or None where sys.executable is unset.

    python-for-android can leave ``sys.executable`` None/empty; ``Path(None)``
    would raise before any fallback ran.
    """
    executable = getattr(sys, "executable", None)
    if not executable:
        return None
    try:
        return Path(executable).resolve().parent
    except (OSError, TypeError, ValueError):
        return None


def host_tick_rate(android=False):
    """Room tick rate this host runs battles at.

    A 30 Hz room advances 8-9 original ticks every other 60 fps frame, so a
    dense late game alternates long and short frames.  With the C++ core the
    host steps at 60 Hz instead: 4-5 original ticks per frame, the same game
    (unit speed and timers count original ticks), half the work per frame.
    Without it (Android, PVP_CPP=0) the per-step overhead would dominate, so
    those hosts keep 30 Hz.  PVP_TICK_RATE=30/60 overrides.
    """
    from .catalog import ROOM_TICK_RATES
    forced = os.environ.get("PVP_TICK_RATE", "")
    if forced.isdigit() and int(forced) in ROOM_TICK_RATES:
        return int(forced)
    if android:
        return RULES["tick_rate"]
    from . import cppcore
    return 60 if cppcore.status().get("active") else RULES["tick_rate"]


def _is_android():
    if os.environ.get("PVP_ANDROID"):
        return True
    return hasattr(sys, "getandroidapilevel") or "ANDROID_PRIVATE" in os.environ


def _workspace():
    candidates = [Path.cwd()]
    exe = _exe_dir()
    if exe is not None:
        candidates.append(exe)
    try:
        candidates += list(Path(__file__).resolve().parents)
    except NameError:
        pass
    for candidate in candidates:
        if (candidate / "reverse_engineered/raw/pvzrouge.pyc").is_file():
            return candidate
    return Path.cwd()


def _pygame():
    handles = []
    runtime = _workspace() / "modkit/tools/pvp-runtime"
    if runtime.is_dir() and hasattr(os, "add_dll_directory"):
        handles.append(os.add_dll_directory(str(runtime)))
        handles.append(os.add_dll_directory(str(runtime / "pygame")))
        # SDL_image uses legacy LoadLibrary internally; explicitly preloading
        # its image codecs also supports the original Chinese asset paths.
        import ctypes
        for name in ("zlib1.dll", "libpng16-16.dll", "libjpeg-62.dll", "libwebp-7.dll"):
            path = runtime / name
            if path.is_file():
                handles.append(ctypes.WinDLL(str(path)))
    try:
        import pygame
    except ImportError:
        if not runtime.is_dir():
            raise RuntimeError("未找到游戏自带 pygame 运行库")
        sys.path.insert(0, str(runtime))
        import pygame
    return pygame, handles


def recommended_deck(side, bans, terrain=None):
    from .draft_advisor import recommend
    return recommend(dict(bans=bans,map=terrain,decks={}),side)['deck']


# One gift packet, and the cooldown the simulation enforces between packets.
from .simulation import GIFT_AMOUNT


class Application(MapEditing, ReplayUI, SpectatorUI, PveUI):
    def __init__(self, pygame, surface, bridge, raw_api=None, asset_dir=None):
        self.pg = pygame
        self.surface = surface
        self.windowed_size = surface.get_size()
        self.ui_sound = None
        self.bridge = bridge
        raw_api = raw_api or {}
        self.events = raw_api.get("event_get", pygame.event.get)
        self.mouse_pos = raw_api.get("mouse_get_pos", pygame.mouse.get_pos)
        self.keys = raw_api.get("key_get_pressed", pygame.key.get_pressed)
        self.held_keys = set()
        self.present = raw_api.get("display_flip", raw_api.get("display_update", pygame.display.flip))
        self.renderer = Renderer(pygame, surface, bridge, asset_dir)
        from .scaled_display import ScaledDisplay
        self.display_backend = ScaledDisplay(self)   # PVP_SCALED; inert unless requested
        from .result_animation import ResultAnimation
        self.result_animation=ResultAnimation(pygame,asset_dir,bridge)
        from .result_outro import ResultOutro
        self.result_outro=ResultOutro()
        self.state = dict(screen="home", message="", focus=None, search="", address="", token="",
                          tabs={"plant": "plant", "zombie": "zombie"}, pages={"plant": 0, "zombie": 0},
                          active_side="plant", battle_page=0, selected_card=None, detail=None, grave=None,
                          copy=None, zoom=1., ui_scale=1., numeric_cd=True, confirm_leave=False, placement_preview=None,
                          confirm_surrender=False, can_surrender=False,
                          bindings={"plant_left": pygame.K_a, "plant_right": pygame.K_d, "plant_jump": pygame.K_w,
                                    "zombie_left": pygame.K_LEFT, "zombie_right": pygame.K_RIGHT, "zombie_jump": pygame.K_UP,
                                    "command": pygame.K_f, "page": pygame.K_TAB,
                                    "cancel": pygame.K_c, "copy": pygame.K_v,
                                    "teleport":pygame.K_t,"rally":pygame.K_r,
                                    "shovel":pygame.K_e,"pause":pygame.K_p,"grave_down":pygame.K_DOWN,
                                    "gift":pygame.K_q}, bind_pending=None)
        self.state['bindings'].update({'slot_%d'%i: pygame.K_1+i-1 for i in range(1,9)})
        self.scale_x = self.scale_y = 1.
        self.default_bindings = dict(self.state["bindings"])
        self.state.update(almanac_category="plant", almanac_page=0, almanac_scroll=0,
                          fullscreen=False, low_effects=False, sound=True, volume=.35,music=True,music_volume=.25,
                          tutorial_seen=False, help_page=0, return_screen="home",
                          port=str(DEFAULT_PORT), endpoint_index=0, map_page=0,
                          reference_context="pvp", room_info_scroll=0, keyboard_focus=None)
        self.state["focused"] = True
        self.state.update(network_mode="direct", relay_endpoint=configured_endpoint())
        self.state.update(room_public=True, room_name="", public_rooms=[], lobby_page=0, lobby_loading=False)
        self.lobby_query = None
        # Android gets touch controls by default; desktop players can enable the
        # same layout from settings (touchscreens, Steam Deck, playtesting).
        self.android = _is_android()
        self.state.update(android=self.android, touch_mode=self.android, touch_mirror=False,
                          touch_size=1, touch_facing=-1, touch_quick_plant=True, touch_layout={})
        from .display_pipeline import defaults, PresentationBudget
        self.state.update(defaults(self.android))
        self.presentation_budget=PresentationBudget()
        if self.android:
            width,height=self.surface.get_size()
            self.state['ui_scale']=min(1.6,max(1.,min(width/1280.,height/720.)))
        self.pointer_capture = None
        self.loaded_ack = None
        from .userdata import resolve as resolve_userdata
        folder, self.userdata_migration = resolve_userdata(_workspace(), _exe_dir(), self.android)
        self.settings_path = folder / "settings.json"
        from .player_profile import PlayerProfile
        from .profiles import ProfileBook
        # PvP62: several saves; each owns its name, match record and maps.
        self.profiles=ProfileBook(self.settings_path.parent)
        self.player_profile=PlayerProfile(self.profiles.player_path())
        self.state.update(player_name=self.player_profile.name,player_stats=self.player_profile.public())
        self._profile_sent=None
        self.init_map_editor()
        self.init_pve()
        self.snapshot_backlog_skips = 0
        self.init_replays()
        self.init_spectators()
        self._text_input_active = False
        self.load_settings()
        if self.android:
            self.apply_display()
        from .game_audio import GameAudio
        self.game_audio=GameAudio(pygame,bridge.combat_payload()[2].parent)
        self.room = None
        self.transport = None
        self.ai_room = None
        self.tutorial = None
        self.mode = None
        self.peer_id = "host"
        self.network_latency = LatencyTracker()
        self.state.update(self.network_latency.display(None))
        self.view = {}
        from .presentation import GuestPresentation
        self.presentation = GuestPresentation()
        self.state["cooperation_hint"]=""
        self.state.update(link_notice="", input_block=None, input_block_seconds=0.)
        self.running = True
        self.sequence = {seat: 0 for seat in SEATS}
        self.send_timer = 0.
        self.move_timer = 0.
        self.last_move = {}
        self.last_input_states = {}
        self.released_keys = set()
        self.sent_map = {}
        # Optional secondary worker for json/zlib/base64 of host snapshots.
        self.pack_worker = None
        self.snapshot_deliveries = {}
        self.last_map_key = None
        self.result_seen_peers = set()
        self.result_ack = None
        self.identity = {"protocol": 1, "build": RULES["build"], "rules_hash": rules_hash(),
                         "catalog_hash": catalog_hash(), "generator": bridge.generator_revision,
                         "map_adapter": ADAPTER_REVISION}
        self.received_snapshots = 0
        self.coalesced_snapshots = 0
        self.frames = 0
        self.profiler=None
        self._scaled_frame=None;self._scaled_signature=None
        from .performance import enabled
        self.scale_reuse=enabled('SCALE_REUSE')
        self.controllers = MenuControllers(pygame)
        self.state["controller_count"] = len(self.controllers.devices)
        from .touch import TouchControls
        self.touch = TouchControls(self)

    def load_settings(self):
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if value.get("format") == "pvp-settings-1":
                for key in self.state["bindings"]:
                    number = value.get("bindings", {}).get(key)
                    if isinstance(number, int) and not isinstance(number, bool) and 0 <= number < 2 ** 31:
                        self.state["bindings"][key] = number
                # Older settings may already use V for another action.
                for key, choices in (('cancel', (self.pg.K_c, self.pg.K_x, self.pg.K_b)),
                                     ('copy', (self.pg.K_v, self.pg.K_x, self.pg.K_b, self.pg.K_n)),
                                     ('teleport',(self.pg.K_t,)),('rally',(self.pg.K_r,)),
                                     ('shovel',(self.pg.K_e,)),('pause',(self.pg.K_p,))):
                    if key not in value.get('bindings', {}):
                        used = {v for k, v in self.state['bindings'].items() if k != key}
                        choices += tuple(self.pg.key.key_code(letter) for letter in 'bcdefgijklmnopqrstuvxyz')
                        self.state['bindings'][key] = next((v for v in choices if v not in used), self.state['bindings'][key])
                self.state["zoom"] = min(1.5, max(.65, float(value.get("zoom", 1.))))
                self.state["ui_scale"] = min(1.6 if self.state.get("touch_mode") else 1.15,
                                             max(.8, float(value.get("ui_scale", 1.))))
                self.state["numeric_cd"] = bool(value.get("numeric_cd", True))
                for key in ("fullscreen", "low_effects", "sound", "music", "tutorial_seen", "save_replays"):
                    self.state[key] = bool(value.get(key, self.state[key]))
                self.state["volume"] = min(1., max(0., _finite_float(value.get("volume", .35))))
                self.state['music_volume']=min(1.,max(0.,_finite_float(value.get('music_volume',.25))))
                from .display_pipeline import load_settings as load_display_settings
                load_display_settings(self.state,value)
                for key in ("touch_mode", "touch_mirror", "touch_quick_plant"):
                    if key in value:
                        self.state[key] = bool(value[key])
                if self.android:
                    # No mouse fallback on Android: SDL touch->mouse synthesis is
                    # disabled, so turning touch controls off bricks all input.
                    self.state["touch_mode"] = True
                self.state["touch_size"] = min(2, max(0, int(value.get("touch_size", 1))))
                from .touch import layout_overrides
                self.state["touch_layout"] = layout_overrides(value.get("touch_layout"))
        except (OSError, ValueError, TypeError):
            pass
        self.apply_scale()

    def apply_scale(self):
        self._ime_rect_focus = None      # re-place the IME candidates after a resize / fullscreen switch
        display = self.display_backend
        width, height = display.physical_size(self.surface)
        factor = min(self.state["ui_scale"], width / 960., height / 640.)
        target = (max(960, int(width / factor)), max(640, int(height / factor)))
        if self.renderer.screen.get_size()!=target:self.renderer.clear_transient_caches()
        if display.wants(target, (width, height)):
            scaled = display.ensure(target) and display.rebuild(target)
            surface = self.pg.display.get_surface()
            if surface is not None:
                self.surface = surface
            if scaled:
                # PVP_SCALED: the display Surface is the logical canvas; SDL
                # scales it and maps pointer/finger input back (scale 1).
                self.renderer.screen = self.surface
                self.scale_x = self.scale_y = 1.
                return
            width, height = self.surface.get_size()
        if target == (width, height):
            self.renderer.screen = self.surface
        elif self.renderer.screen is not self.surface and self.renderer.screen.get_size() == target:
            # PvP73: keep the existing logical canvas (and every cache keyed to it). Android
            # re-applies the display on each foreground/focus change; a fresh canvas there
            # made the first seconds after returning from the background stutter.
            pass
        else:
            self.renderer.screen = self.pg.Surface(target)
        self.scale_x, self.scale_y = target[0] / width, target[1] / height

    def save_settings(self):
        value = {"format": "pvp-settings-1", "bindings": self.state["bindings"],
                 "ui_scale": self.state["ui_scale"], "zoom": self.state["zoom"], "numeric_cd": self.state["numeric_cd"],
                 "touch_mode": self.state["touch_mode"], "touch_mirror": self.state["touch_mirror"],
                 "touch_quick_plant": self.state["touch_quick_plant"],
                 "touch_size": self.state["touch_size"],
                 "touch_layout": self.state.get("touch_layout") or {}}
        for key in ("fullscreen", "low_effects", "sound", "volume", "music", "music_volume", "tutorial_seen", "save_replays"):
            value[key] = self.state[key]
        for key in ('world_quality','display_filter','display_budget'):
            value[key]=self.state[key]
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply_display(self):
        if self.android:
            # Keep SDL's existing window/context; Android updates its size after
            # system bars are hidden. Resize events then rebuild only UI scale.
            from modkit.android.platform_android import set_fullscreen
            set_fullscreen()
            self.state["fullscreen"] = True
            surface = self.pg.display.get_surface()
            if surface is not None:
                self.surface = surface
            self.apply_scale()
            return
        try:
            flags = self.pg.FULLSCREEN if self.state["fullscreen"] else 0
            self.display_backend.external_mode_change()
            self.surface = self.pg.display.set_mode((0, 0) if flags else self.windowed_size, flags)
            self.apply_scale()
        except self.pg.error:
            self.state["fullscreen"] = False
            self.message("当前显示驱动不支持全屏，已保留窗口模式。")

    def play_ui_sound(self):
        if not self.state.get("sound") or not self.pg.mixer.get_init():
            return
        try:
            if self.ui_sound is None:
                from array import array
                rate, fmt, channels = self.pg.mixer.get_init()
                if fmt != -16:
                    return
                count = int(rate * .035)
                samples = array("h", [int(1800 * math.sin(i * 2 * math.pi * 640 / rate) * (1-i/count))
                                      for i in range(count) for _ in range(channels)])
                self.ui_sound = self.pg.mixer.Sound(buffer=samples.tobytes())
            self.ui_sound.set_volume(self.state["volume"])
            self.ui_sound.play()
        except self.pg.error:
            pass

    def logical_pos(self, position):
        return (position[0] * self.scale_x, position[1] * self.scale_y)

    def message(self, value):
        self.state["message"] = str(value)

    def binding_name(self, key):
        return self.pg.key.name(self.state['bindings'][key]).upper()

    def profile_action(self,kind,key=None):
        """Switch, create or delete a save. Not inside a room: the room
        already carries this player's name and record."""
        if self.room or self.transport:
            self.message('请先离开房间再切换或管理存档');return
        book=self.profiles
        if kind=='profile_delete':
            key=key or book.current
            if self.state.get('profile_delete_pending')!=key:
                self.state['profile_delete_pending']=key
                self.message('再点一次“确认删除”：该存档的名称、战绩与地图将被删除');return
        self.state['profile_delete_pending']=None
        try:
            if kind=='profile_new':
                book.create();self.message('已新建存档，可在左侧修改玩家名称')
            elif kind=='profile_switch':
                book.switch(key);self.message('已切换到存档 %d'%(book.ids.index(key)+1))
            else:
                book.delete(key);self.message('存档已删除')
        except (ValueError,OSError) as exc:
            self.message(str(exc));return
        self.load_profile()

    def load_profile(self):
        from .player_profile import PlayerProfile
        from .custom_maps import MapStore
        self.player_profile=PlayerProfile(self.profiles.player_path())
        self.map_store=MapStore(self.profiles.maps_dir())
        self.state.update(player_name=self.player_profile.name,player_stats=self.player_profile.public(),
                          profiles=self.profiles.summaries(),focus=None)

    def sync_player_profile(self):
        if not hasattr(self,'player_profile'):return
        profile=self.player_profile.public()
        if self.mode in ('host','local') and self.room:
            self.room.set_player_profile('host',profile)
        elif self.mode=='guest' and self.transport:
            if self.view.get('spectating'):
                self._profile_sent=None;return
            key=(id(self.transport),self.peer_id,json.dumps(profile,sort_keys=True))
            if key!=self._profile_sent:
                self.transport.send(dict(type='player_profile',profile=profile))
                self._profile_sent=key

    def draft_advice(self,side,seat=None):
        from .draft_advisor import recommend
        from .draft_advisor import recommend_ai
        seat=seat or self.local_seat(side) or side
        side=team_of(seat)
        plan=self.state.get("draft_plan",{})
        return recommend_ai(self.view,side,preferred=plan.get(seat,plan.get(side)),seat=seat)

    def copy_hint(self):
        if self.state.get("selected_card")!="plant:模仿者":return
        player=(self.view.get("battle") or {}).get("players",{}).get("plant",{})
        key=self.state.get("copy") or player.get("last_copy_card")
        if self.state.get("touch_mode"):
            self.message("模仿目标："+CARDS[key]["name"]+"（再点“模仿”切换）" if key in CARDS
                         else "模仿者：请先种下一株可复制植物，或点“模仿”选择目标")
        else:
            button = self.binding_name('copy')
            self.message("模仿目标："+CARDS[key]["name"]+"（按 %s 切换）" % button if key in CARDS
                         else "模仿者：请先种下一株可复制植物，或按 %s 选择目标" % button)

    def close_room(self, graceful=False):
        self._coop_campaign = None
        self._coop_campaign_scope = None
        self._coop_campaign_remote = None
        self._coop_observer_campaign = None
        self._coop_observer_scope = None
        if getattr(self, 'ai_room', None) is not None:
            owner, self.ai_room = self.ai_room, None
            owner.close()
        self.tutorial = None
        if graceful and hasattr(self,'player_profile') and self.mode=='guest' and self.view.get('phase')=='battle' and not self.view.get('result'):
            side=self.view.get('match_members',{}).get(self.peer_id)
            if side in ('plant','zombie'):
                result=dict(self.view,result=dict(winner='zombie' if side=='plant' else 'plant',reason='leave'))
                try:
                    self.player_profile.record(result,self.peer_id,self.mode)
                    self.state['player_stats']=self.player_profile.public()
                except OSError:pass
        self.renderer.local_pixels=None
        self.renderer.clear_transient_caches()
        world=getattr(self.renderer,'world',None)
        if world is not None:
            world.local_pixels=None
            layer=getattr(world,'_world_layer',None)
            if layer is not None:layer.clear()
            replay=getattr(world,'_native_replay',None)
            if replay is not None:
                replay._local_frame=None;replay._local_scaled.clear();replay.local_bytes=0
        self.invalidate_snapshots()
        self.presentation.clear()
        self.result_animation.skip();self.result_outro.skip()
        self.state.pop('result_animation_pending',None)
        self.close_spectators()
        self.clear_replay_transfer()
        self.replay_auto_match = None
        if self.transport:
            if graceful and self.mode == "guest":
                # Best-effort: tell the host to free our slot immediately
                # instead of waiting out the reconnect window.
                try:
                    self.transport.send({"type": "leave"})
                    time.sleep(.15)  # let the network thread flush the buffer
                except Exception:
                    pass
            self.transport.close()
        close = getattr(self.room, "close", None)
        if close:
            close()
        if self.pack_worker is not None:
            self.pack_worker.close()
            self.pack_worker = None
        self.transport = None
        self.room = None
        self.mode = None
        self.network_latency.clear()
        self.state.update(self.network_latency.display(None))
        self.view = {}
        self.last_map_key = None
        self.sent_map = {}
        self.loaded_ack = None
        self.state.update(screen="home", confirm_leave=False, selected_card=None, grave=None, focus=None, endpoints=[],cooperation_hint="",
                          link_notice="", input_block=None, input_block_seconds=0.,
                          leave_pending=False, map_sync_error=False)
        self.result_seen_peers = set();self.result_ack = None

    def quit_live_battle(self):
        """Closing the game mid-battle forfeits it (the quitter loses).

        Host: forfeit its own side and push that result to the guest before the
        socket closes. Guest: the graceful ``leave`` makes the host rule it lost.
        Returns True when the guest should close gracefully.
        """
        if not self.transport or self.mode not in ("host", "guest"):
            return False
        if self.mode == "guest":
            return True
        room = self.room
        if room is None or room.phase != "battle" or room.result is not None:
            return False
        try:
            self.invalidate_snapshots()
            room.host_quit()
            if hasattr(self,'player_profile'):
                self.player_profile.record(room.snapshot('host',include_map=False),'host','host')
                self.state['player_stats']=self.player_profile.public()
            for peer in [p for p in room.members if p != "host" and room.connected.get(p)]:
                self.transport.send(peer, pack_snapshot(room.snapshot(peer, include_map=False)))
            time.sleep(.15)  # let the network thread flush the result
        except Exception:
            pass
        return False

    def close(self):
        if getattr(self,'game_audio',None):self.game_audio.close()
        if self.profiler is not None:
            self.profiler.close();self.profiler=None
        self.close_playback()
        if self.lobby_query:
            self.lobby_query.close()
        try:
            graceful = False
            try:
                graceful = self.quit_live_battle()
            except Exception:
                graceful = False
            self.close_room(graceful=graceful)
        finally:
            self.controllers.close()

    def release_inputs(self):
        self.state['rally']=False;self.state.pop('rally_drag',None)
        self.held_keys.clear()
        self.last_move.clear()
        self.last_input_states.clear()
        self.replay_drag=None;self.spectator_drag=None
        self.state.pop('replay_preview_tick',None)
        if getattr(self, "touch", None) is not None:
            self.touch.clear()
        if self.view.get("phase") == "battle":
            for side in self.local_sides():
                self.input(side, "move", move=0, jump=False)

    def leave_modal(self, value=True):
        if value:
            self.release_inputs()
        self.state["confirm_leave"] = bool(value)
        self.state["keyboard_focus"] = 0 if value else None

    def relay_room_in_use(self):
        """True while the cloud room is played, even with no remote socket.

        A co-op match whose teammate is an AI seat keeps no guest connection, so
        the relay sees only a host waiting for a friend and reclaims the room
        after its waiting timeout. Report the local match and its occupied seats
        as "in use" so that reclaim can never end the game (report 10-16).
        """
        room = getattr(self, 'room', None)
        if room is None:
            return False
        if getattr(room, 'phase', '') in ('loading', 'battle', 'result'):
            return True
        return bool(getattr(room, 'members', None))

    def create(self, local=False):
        if local:
            self.state.update(network_mode="direct", token="")
        cloud = not local and self.state.get("network_mode") == "relay"
        try:
            port = DEFAULT_PORT if local or cloud else int(self.state.get("port", DEFAULT_PORT))
            if not 1 <= port <= 65535:
                raise ValueError()
        except (TypeError, ValueError):
            self.message("端口必须是 1–65535 的整数。")
            self.state["screen"] = "host"
            return
        self.close_room()
        self.room = Room(self.bridge)
        self.room.rules["tick_rate"] = host_tick_rate(self.android)
        self.room.set_player_profile('host',self.player_profile.public())
        self.room.allow_spectators=self.state.get('allow_spectators',True)
        self.room.replay_enabled=True
        self.room.on_replay=self.save_recording
        duo = not local and self.state.get("room_size") == "duo"
        if duo:
            self.room.set_mode("duo")
            if not self.pending_custom_map:
                # 2v2 is played on the extended maps by default.
                from .team_maps import DEFAULT_DUO_MAP, map_command
                self.room.command("host", map_command(DEFAULT_DUO_MAP, self.room.revision))
        if self.pending_custom_map:
            doc = self.pending_custom_map
            error = self.room.command("host", dict(type="map", revision=self.room.revision,
                map_id="custom:"+doc["id"], seed=doc["seed"], custom_map=doc, night=doc["night"]))
            if error:
                self.close_room();self.message(error);return
            self.pending_custom_map = None
        self.peer_id = "host"
        self.mode = "local" if local else "host"
        self.sequence = {seat: 0 for seat in SEATS}
        if local:
            self.room.connect("guest")
            self.message("本地双人规则演练：双方使用各自移动键；鼠标可切换操作阵营。")
        elif cloud:
            self.state["token"] = ""
            try:
                name = self.state.get("room_name", "")
                if duo:name = ("[2v2] " + name)[:40]
                elif self.state.pop("room_kind", None) == "coop":name = ("[合作] " + name)[:40]
                self.transport = RelayHostTransport(self.state.get("relay_endpoint", ""), identity=self.identity,
                                                    public=self.state.get("room_public", True), name=name,
                                                    allow_spectators=self.room.allow_spectators,max_peers=3 if duo else 2,
                                                    in_use=self.relay_room_in_use)
            except (ValueError, OSError) as exc:
                self.close_room()
                self.state.update(screen="host", focus="relay_endpoint")
                self.message("请设置可用的云端中继地址：" + str(exc))
                return
            self.message("正在创建云端房间，请稍候……")
        else:
            self.state["token"] = "%06d" % secrets.randbelow(1000000)
            self.transport = ServerTransport("::", port, identity=self.identity, room_code=self.state["token"],allow_spectators=self.room.allow_spectators,max_peers=3 if duo else 2)
            self.state["endpoints"] = local_endpoints(port)
            self.state["endpoint_index"] = 0
            self.message("正在监听端口 %d；房间口令：%s。" % (port, self.state["token"]))
        self.state["screen"] = "room"
        self.refresh()

    def create_offline_host(self):
        """Host room without any transport: only local AI peers can take the other seats."""
        self.close_room()
        self.state.update(network_mode="direct", token="", endpoints=[])
        self.room = Room(self.bridge)
        self.room.rules["tick_rate"] = host_tick_rate(self.android)
        self.room.set_player_profile('host', self.player_profile.public())
        self.room.allow_spectators = True
        self.room.replay_enabled = True
        self.room.on_replay = self.save_recording
        self.peer_id = "host"
        self.mode = "host"
        self.sequence = {seat: 0 for seat in SEATS}
        self.state["screen"] = "room"

    def join(self, spectator=False):
        address, token = self.state["address"].strip(), self.state["token"].strip()
        self.close_room()
        self.state.update(address=address, token=token, screen="room",spectating=bool(spectator),
                          spectator_camera=None,spectator_mode='free')
        self.mode = "guest"
        self.peer_id = "pending"
        try:
            if self.state.get("network_mode") == "relay":
                self.state["token"] = normalize_code(token)
                self.transport = RelayClientTransport(self.state.get("relay_endpoint", ""), identity=self.identity, room_code=token,spectator=spectator)
            else:
                self.transport = ClientTransport(address, identity=self.identity, room_code=token,spectator=spectator)
            self.message("正在连接；版本、卡池、规则和地图生成器会共同校验。")
        except (ValueError, OSError) as exc:
            self.message(exc)
            self.state["screen"] = "join"

    def opponent_quit_battle(self):
        """Guest view: the host vanished mid-battle, or already ruled that it forfeited."""
        if self.view.get('host_spectating'):return False
        sides = self.local_sides()
        battle = self.view.get("battle") or {}
        result = battle.get("result") or self.view.get("result")
        if self.view.get("phase") == "battle" and not result:
            return bool(sides)
        return (isinstance(result, dict) and result.get("forfeit") in ("plant", "zombie")
                and bool(sides) and result.get("forfeit") not in sides)

    def local_seats(self):
        if self.mode == "local":
            return ["plant", "zombie"]
        members = self.view.get("members", {})
        side = members.get(self.peer_id)
        return [side] if side else []

    def local_sides(self):
        """Factions this client plays; its seat may be the second of a team."""
        return [team_of(seat) for seat in self.local_seats()]

    def local_seat(self, side):
        return next((seat for seat in self.local_seats() if seat == side or team_of(seat) == side), None)

    def peer_for(self, side):
        return next((key for key, value in self.view.get("members", {}).items() if value == side), None)

    def command(self, payload, side=None):
        kind=payload.get('type')
        if self.mode=='guest' and kind in ('map','swap','allow_spectators','room_options'):
            payload=dict(type='request_config',proposal=dict(payload));kind='request_config'
        host_control=self.mode=='host' and kind in ('map','swap','allow_spectators','reopen','resolve_config_request','room_options')
        if self.state.get('spectating') and kind!='role_change' and not host_control:return '观众不能操作对局'
        if self.state.get("map_sync_error") and payload.get("type") in ("confirm_map", "loaded"):
            self.message("地形校验失败，等待完整地图重新同步。")
            return "map_sync_error"
        payload = dict(payload, revision=self.view.get("revision"))
        if self.mode == "local":
            side = side or self.view.get("current_side") or self.state["active_side"]
            peer = self.peer_for(side)
        else:
            peer = self.peer_id
        if self.room:
            old_policy=self.room.allow_spectators;old_spectators=list(self.room.spectators)
            error = self.spectator_role_change(peer, payload) if kind=='role_change' else self.room.command(peer, payload)
            if not error and self.room.allow_spectators!=old_policy and self.transport:
                if not self.room.allow_spectators:
                    for watcher in old_spectators:
                        if watcher!='host':
                            self.transport.send_spectator(watcher,dict(type='error',message='房主已关闭观战',terminal=True))
                            self.transport.release_peer(watcher)
                self.transport.set_allow_spectators(self.room.allow_spectators)
            self.refresh()
            if error:
                self.message(error)
            return error
        if self.transport:
            if not self.transport.send({"type": "role_change" if kind=='role_change' else "room_command", "payload": payload}):
                self.message("连接尚未就绪或发送队列已满")
                return "not_connected"
            if kind=='request_config':self.message('设置请求已发送，等待房主同意；可在“房间请求”查看或撤回')
        return ""

    def input(self, side, kind, **data):
        if self.view.get("audit_error"):
            return "日志写入失败，对局已暂停"
        if side not in self.local_sides():
            return "not_local"
        seat = self.local_seat(side)
        self.sequence[seat] += 1
        payload = dict(type=kind, seq=self.sequence[seat], **data)
        observed_start=time.perf_counter() if self.profiler else None
        error = self.command({"type": "input", "input": payload}, seat)
        if self.profiler and not error:
            self.profiler.input_sent(seat,self.sequence[seat],observed_start)
            if self.room:
                self.profiler.inputs.acknowledged(self.profiler.input_scope(),(self.view.get('battle') or {}).get('players') or {})
        if self.tutorial is not None:
            self.tutorial.on_input(side, kind, error)
        return error

    def gift_teammate(self, amount=None):
        """Hand part of this player's economy to their teammate (co-op / 2v2)."""
        from .simulation import GIFT_AMOUNT, GIFT_COOLDOWN, GIFT_MAX
        sides = self.local_sides()
        side = self.state.get("active_side") if self.state.get("active_side") in sides else (sides[0] if sides else None)
        if not side:
            self.message("连接未就绪，无法资助队友。")
            return
        view = self.view or {}
        if view.get("phase") != "battle" or view.get("result"):
            self.message("当前不在对局中。")
            return
        if view.get("mode") not in ("duo", "coop"):
            self.message("只有合作模式与 2v2 可以资助队友。")
            return
        amount = max(1, min(int(GIFT_MAX), int(GIFT_AMOUNT if amount is None else amount)))
        error = self.input(side, "gift", amount=amount)
        self.message(error or (("已资助队友 %d（无冷却）"%amount) if view.get('mode')=='coop' else
                               ("已资助队友 %d（冷却 %.0f 秒）" % (amount, GIFT_COOLDOWN))))

    def refresh(self):
        self.bind_coop_progress()
        if not self.room:
            return
        terrain_revision = self.room.battle.terrain_revision if self.room.battle else -1
        key = (self.room.map.terrain_hash, terrain_revision)
        include_map = key != self.last_map_key or not self.view.get("map")
        value = self.room.snapshot(None if self.mode == "local" else "host", include_map=include_map, copy_state=False)
        self.merge_view(value)
        self.last_map_key = key

    def merge_view(self, value):
        if self.mode == "guest":
            if "map" in value:
                try:
                    verified = MapSnapshot.from_dict(value["map"])
                    if verified.terrain_hash != value.get("terrain_hash"):
                        raise ValueError("room terrain hash mismatch")
                except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
                    self.state["map_sync_error"] = True
                    self.message("地形校验失败，已保留上个有效状态；正在请求完整地图。")
                    if self.transport:
                        self.transport.send({"type": "request_full_snapshot"})
                    return False
                self.state["map_sync_error"] = False
            elif self.state.get("map_sync_error"):
                return False
        old = self.view
        if self.state.get('screen')=='room_requests' and value.get('phase')!='config':
            self.state.update(screen='room',return_screen='room')
        pending=value.get('config_requests') or []
        old_ids={r['id'] for r in old.get('config_requests',[])}
        if self.mode=='host' and value.get('phase')=='config' and any(r['id'] not in old_ids for r in pending):
            if self.state.get('screen') in ('room','room_requests'):
                self.state.update(screen='room_requests',return_screen='room',focus=None)
        if self.mode=='guest' and value.get('phase')=='config':
            outcome=value.get('request_outcome')
            if outcome and outcome!=old.get('request_outcome') and outcome.get('peer')==self.peer_id:
                self.message(('房主已同意：' if outcome['accepted'] else '房主已拒绝：')+outcome['label'])
            elif any(r['peer']==self.peer_id for r in old.get('config_requests',[])) and not any(r['peer']==self.peer_id for r in pending):
                self.message('请求已撤回或因房间配置变化失效')
        if (old.get("draft_progress") or {}).get("step") != (value.get("draft_progress") or {}).get("step"):
            self.state.update(pending_card=None,pending_ban=None,keyboard_focus=None)
        if old.get("phase") != value.get("phase"):
            self.state['rally']=False;self.state.pop('rally_drag',None)
            self.state.update(message="", detail=None, pending_card=None, pending_ban=None, placement_preview=None, keyboard_focus=None)
            if value.get("phase") == "battle":
                self.state.update(selected_card=None, battle_page=0, grave=None,focus=None,bind_pending=None,shovel=False,copy=None,teleport=False)
                self.pointer_capture=None
                self.move_timer=.04
            if value.get("phase") == "loading":
                self.loaded_ack = None
                self.result_seen_peers.clear();self.result_ack = None
            if value.get('phase')=='result':self.state['result_animation_pending']=True
            else:
                self.result_animation.skip();self.result_outro.skip();self.state.pop('result_animation_pending',None)
                self.state.pop('result_outro_ran',None);self.state.pop('result_curtain_pending',None)
        if "map" not in value and "map" in old:
            value["map"] = old["map"]
        if value.get("battle") and "map" not in value["battle"]:
            value["battle"]["map"] = (old.get("battle") or {}).get("map", value.get("map"))
        if self.profiler:
            # Acknowledgements use authority seats. The local HUD swaps plant2
            # with plant below; its remapped player keys cannot acknowledge
            # the actual plant2 input sequence.
            scope=(value.get('match_id'),value.get('match_number'),value.get('mode'))
            self.profiler.inputs.acknowledged(scope,(value.get('battle') or {}).get('players') or {})
        if self.mode != "local" and value.get("battle"):
            seat = (value.get("members") or {}).get(self.peer_id)
            if seat and seat != team_of(seat):
                value["battle"] = local_perspective(value["battle"], seat)
        self.view = value
        # Co-op: the guest advances its own campaign from the broadcast result,
        # so both Daves keep their own coins, unlocks and reward picks.
        if hasattr(self, "pve_apply_guest_result"):
            self.pve_apply_guest_result(value)
        if hasattr(self,'player_profile'):
            try:
                self.player_profile.record(value,self.peer_id,self.mode)
                self.state['player_stats']=self.player_profile.public()
            except OSError:self.message('战绩保存失败，请检查游戏数据目录权限')
            self.sync_player_profile()
        if self.mode in ('guest','host'):
            was_spectating=self.state.get('spectating',False)
            self.state['spectating']=bool(value.get('spectating'))
            if was_spectating != self.state['spectating']:
                self.release_inputs()
                self.cancel_battle_action()
                self.state.update(spectator_camera=None,spectator_mode='free')
        if self.mode=='host':self.state['allow_spectators']=value.get('allow_spectators',True)
        if self.mode == "guest" or self.state.get('pressure_interpolation'):
            self.presentation.accept(value)
        from .hud import cooperation_hint
        self.state["cooperation_hint"]=cooperation_hint(value)
        self.view["maps"] = list(self.bridge.map_names)
        self.view["map_registry"] = map_registry(self.bridge, value.get("seed", 1))
        if value.get("mode") == "duo":
            from .team_maps import registry_entries
            self.view["map_registry"] = registry_entries() + self.view["map_registry"]
        self.view['can_request_config']=self.mode=='guest' and bool(self.local_sides()) and value.get('phase')=='config'
        self.view["can_select_map"] = self.mode in ("local", "host") or self.view['can_request_config']
        self.view['local_peer_id']=self.peer_id
        self.view["can_kick"] = self.mode == "host"
        self.view['can_fill_ai'] = self.mode == 'host' and value.get('phase') in ('config','result') and (
            self.ai_room is None or not self.ai_room.autofill)
        self.view["local_sides"] = self.local_sides()
        self.view["local_seats"] = self.local_seats()
        self.view["aquatic_zombie_error"] = map_card_error("zombie:潜水僵尸", self.view.get("map"))
        sides = self.local_sides()
        if sides and self.state["active_side"] not in sides:
            self.state["active_side"] = sides[0]
        if value.get("current_action") in ("secret", "zsecret"):
            owner = "plant" if value["current_action"] == "secret" else "zombie"
            self.state["tabs"][owner] = "secret"
            if old.get("current_action")!=value["current_action"]:
                self.state["pages"][owner]=0
                self.state["search"]=""
        elif value.get("phase")=="banning" and value.get("current_action")!=old.get("current_action"):
            target=value.get("current_action")
            if target in ("plant","zombie"):
                self.state["tabs"][target]=target
                self.state["pages"][target]=0
                self.state["search"]=""
        if value.get("phase") == "banning":
            actor = "植物方" if value["current_side"] == "plant" else "僵尸方"
            action = {"secret": "禁植物秘籍", "zsecret": "禁僵尸秘籍"}.get(value["current_action"], "禁对方单位")
            progress=value.get('ban_progress')
            if progress:action+='（本轮第 %d / %d 个）'%(progress['index'],progress['total'])
            self.view["status"] = "%s：%s · 剩余阶段 %d · %.0f 秒" % (actor, action, value["remaining"], value["deadline"])
        elif value.get("phase") == "picking":
            self.view["status"] = "阵容锁定，请双方准备" if value.get("draft_stage")=="complete" else ("僵尸" if value.get("current_side")=="zombie" else "植物")+"回合：选择一张卡后切换"
        if value.get("audit_error"):
            self.message("对局因日志写入失败已暂停，可导出已有记录或退出。")
        return True

    def poll_network(self, dt, publish=True):
        self.update_replay_transfer()
        if self.lobby_query:
            result = self.lobby_query.poll()
            if result is not None:
                self.lobby_query = None
                self.state["lobby_loading"] = False
                if "error" in result:
                    self.message(network_error(result["error"]))
                else:
                    self.state.update(public_rooms=result["rooms"], lobby_page=0)
                    self.message("大厅已刷新 · %d 个公开房间" % (len(result["rooms"]) + 1))
        if not self.transport:
            self.state.update(self.network_latency.display(None))
            return
        # Watching is an active read-only session. Keep an application-level
        # round trip even when the viewer never moves a camera or sends input.
        if self.mode=='guest' and self.state.get('spectating'):
            elapsed=self.state.get('_spectator_keepalive',0.)+max(0.,dt)
            if elapsed>=2.:
                self.transport.send(dict(type='spectator_watch'))
                elapsed=elapsed%2.
            self.state['_spectator_keepalive']=elapsed
        else:self.state['_spectator_keepalive']=0.
        events = self.transport.poll()
        if self.mode == 'guest':
            from .snapshot_delivery import coalesce_snapshot_events
            fresh = coalesce_snapshot_events(events)
            self.coalesced_snapshots += len(events) - len(fresh)
            events = fresh
        for event in events:
            kind = event["type"]
            if kind in ("connected", "reconnected"):
                if self.mode == "host":
                    self.invalidate_snapshots(event["peer_id"])
                    requested_player=bool(event.get('request_player') and event.get('spectator'))
                    error = self.room.connect(event["peer_id"],spectator=bool(event.get('spectator',False) and not requested_player))
                    if not error and requested_player:
                        error=self.transport.set_peer_role(event['peer_id'],False)
                    if error:
                        if requested_player and event['peer_id'] in self.room.members:self.room.leave(event['peer_id'])
                        self.transport.reject_peer(event['peer_id'],error)
                        continue
                    self.sent_map.pop(event["peer_id"], None)
                    self.refresh()
                else:
                    self.presentation.clear()
                    self.peer_id = event.get("assigned_peer_id", self.transport.peer_id)
                self.network_latency.connected(event['peer_id'])
                if not (self.mode=='host' and event.get('spectator')):
                    self.message("连接成功，正在同步权威状态" if kind == "connected" else "重连成功，正在恢复战场")
            elif kind == "message":
                payload = event.get("payload", {})
                if isinstance(payload,dict) and payload.get('type') in ('spectator_watch','spectator_watch_ack'):
                    if (payload.get('type')=='spectator_watch' and self.mode=='host'
                            and event.get('peer_id') in self.room.spectators):
                        self.transport.send(event['peer_id'],dict(type='spectator_watch_ack'))
                    continue
                if self.network_latency.receive(event.get('peer_id'), payload, self.send_latency):
                    continue
                if self.mode=='host' and isinstance(payload,dict) and payload.get('type')=='player_profile':
                    if self.room.set_player_profile(event.get('peer_id'),payload.get('profile')):self.refresh()
                    continue
                if self.spectator_network(event.get('peer_id'),payload):continue
                if self.replay_network(event.get('peer_id'),payload):continue
                if self.mode == "host" and payload.get("type") == "room_command":
                    request=payload.get('payload')
                    if isinstance(request,dict) and request.get('type')=='role_change':
                        error=self.spectator_role_change(event['peer_id'],request)
                    else:error = self.room.command(event["peer_id"], request)
                    if error:
                        self.transport.send(event["peer_id"], {"type": "error", "message": error})
                    self.refresh()
                elif self.mode == "host" and payload.get("type") == "request_full_snapshot":
                    self.invalidate_snapshots(event["peer_id"])
                    self.sent_map.pop(event["peer_id"], None)
                elif self.mode == "host" and payload.get("type") == "result_received":
                    if self.room.phase == "result" and payload.get("match_number") == self.room.match_number:
                        self.result_seen_peers.add(event["peer_id"])
                elif self.mode == "host" and payload.get("type") == "leave":
                    self.network_latency.remove(event['peer_id'])
                    self.room.leave(event["peer_id"]);self.refresh()
                    if event['peer_id'] not in self.room.members:
                        self.transport.release_peer(event['peer_id'])
                elif self.mode == "guest" and payload.get("type") == "room_snapshot":
                    try:
                        value = unpack_snapshot(payload)
                    except (ValueError, TypeError, zlib.error) as exc:
                        self.message("拒绝损坏的快照：" + str(exc))
                        continue
                    if isinstance(value, dict) and isinstance(value.get("revision"), int):
                        if not self.merge_view(value):
                            continue
                        if value.get("phase") == "result" and self.result_ack != value.get("match_number"):
                            self.transport.send({"type": "result_received", "match_number": value.get("match_number")})
                            self.result_ack = value.get("match_number")
                        self.received_snapshots += 1
                        if not self.state.get('spectating'):self.auto_save_guest_replay()
                        # Inputs resume from the authoritative acknowledgement after reconnect.
                        for side in self.local_sides():
                            acknowledged = (value.get("battle") or {}).get("players", {}).get(side, {}).get("seq", -1)
                            self.sequence[side] = max(self.sequence[side], acknowledged)
                elif payload.get("type") == "error":
                    self.pve_guest_command_error(payload)
                    if self.mode == "guest" and payload.get("terminal"):
                        self.close_room();self.state.update(screen="join", focus="address")
                        self.message(payload.get("message", "请求被主机拒绝"));return
                    self.message(payload.get("message", "请求被主机拒绝"))
            elif kind == "disconnected":
                self.network_latency.disconnected(event.get('peer_id'))
                if self.mode == 'guest':
                    self.presentation.clear()
                if self.mode == "host":
                    self.invalidate_snapshots(event.get("peer_id"))
                    spectator=event.get('spectator') or event.get('peer_id') in self.room.spectators
                    self.room.disconnect(event.get("peer_id"))
                    if not spectator:self.refresh()
                    if event.get('peer_id') not in self.room.members:
                        self.transport.release_peer(event.get('peer_id'))
                    if spectator:continue
                self.message("连接中断，正在等待重连；移动输入已清除。")
            elif kind in ("error", "closed"):
                code = event.get("code", kind)
                if self.mode == "guest" or (self.mode == "host" and (code == "listen_failed" or event.get("relay_terminal"))):
                    destination = "join" if self.mode == "guest" else "host"
                    won = self.mode == "guest" and self.opponent_quit_battle()
                    self.close_room()
                    self.state.update(screen=destination, focus="address" if destination == "join" else "port")
                    self.message("对方已退出游戏，本局判你获胜。" if won else network_error(code))
                    return
                self.message(network_error(code))
            elif kind == "listening":
                self.message("房间已开启 · 端口 %d · 口令 %s · 等待另一位玩家" % (self.transport.port, self.state["token"]))
            elif kind == "relay_ready":
                self.state["token"] = event["room_code"]
                self.message("云端房间已开启 · 房间码 %s · 发给朋友即可加入" % event["room_code"])
            elif kind == "relay_reclaimed":
                # The reservation was reclaimed while a local match keeps
                # running (co-op with an AI seat looks idle to the relay).
                # Never a terminal error: a fresh room code follows shortly.
                self.state["token"] = ""
                self.message("云端房间码已失效，正在自动重建（本局继续进行）。")
        if self.mode == 'host' and self.room is not None:
            remaining = set(self.room.members) | set(self.room.spectators)
            for peer in list(self.network_latency.peers):
                if peer not in remaining:
                    self.network_latency.remove(peer)
        self.network_latency.update(self.send_latency)
        self.state.update(self.network_latency.display(self.mode))
        if publish:
            self.publish_network(dt)

    def send_latency(self, peer, payload):
        """Probe through the same direct/relay route as authoritative game data."""
        if self.transport is None:
            return False
        return self.transport.send(payload) if self.mode == 'guest' else self.transport.send(peer, payload)

    def invalidate_snapshots(self, peer=None):
        tickets = getattr(self, 'snapshot_deliveries', {})
        for name in list(tickets) if peer is None else [peer]:
            ticket = tickets.pop(name, None)
            if ticket is not None:
                ticket.cancel()
            if self.pack_worker is not None:
                self.pack_worker.forget(name)

    def publish_network(self, dt):
        if self.mode != 'host' or not self.room or not self.transport:
            return
        self.send_timer += dt
        self.send_spectator_snapshots(dt)
        worker = self._snapshot_pack_worker() if self.mode == "host" else None
        key = (self.room.map.terrain_hash, self.room.battle.terrain_revision if self.room.battle else -1)
        stamp = (key, self.room.phase, self.room.match_number, self.room.loading_id)
        for peer, ticket in list(self.snapshot_deliveries.items()):
            if ticket.stamp != stamp or not self.room.connected.get(peer):
                self.invalidate_snapshots(peer)
        if worker is not None:
            for peer, sent_key, payload in worker.completed():
                ticket = self.snapshot_deliveries.pop(peer, None)
                if ticket is not None and ticket.accepted():
                    self.sent_map[peer] = sent_key
        if self.mode == "host" and self.send_timer + 1e-9 >= self.snapshot_interval():
            interval = self.snapshot_interval()
            self.send_timer = max(0., self.send_timer - int((self.send_timer + 1e-9) / interval) * interval)
            key = (self.room.map.terrain_hash, self.room.battle.terrain_revision if self.room.battle else -1)
            pending = getattr(self.transport, "pending_bytes", None)
            for peer in self.room.members:
                if peer == "host" or peer in getattr(self.room,'ai_peers',()) or not self.room.connected.get(peer):
                    continue
                # PvP66: snapshots supersede each other. While the link to this
                # peer still holds unsent ones, skip instead of piling up until
                # the 4 MB send buffer drops the connection (and the room
                # pauses for the reconnect) on a slow downlink or relay.
                if pending is not None and pending(peer) > SNAPSHOT_BACKLOG_BYTES:
                    self.snapshot_backlog_skips += 1
                    continue
                include = self.sent_map.get(peer) != key
                if worker is not None:
                    if worker.busy(peer):
                        continue
                    # marshal inside submit is the detached copy of this tick's
                    # state, so the room need not deep-copy it first.
                    from .snapshot_delivery import SnapshotDelivery
                    ticket = SnapshotDelivery(self.transport, peer, stamp, include)
                    self.snapshot_deliveries[peer] = ticket
                    if worker.submit(peer, key, self.room.snapshot(peer, include_map=include, copy_state=False), delivery=ticket):
                        continue
                    self.snapshot_deliveries.pop(peer, None)
                from .snapshot_delivery import annotate_snapshot
                payload = annotate_snapshot(pack_snapshot(self.room.snapshot(peer, include_map=include)), stamp, include)
                if self.transport.send(peer, payload):
                    self.sent_map[peer] = key

    def action(self, action, right=False):
        if not action:
            return
        if self.state.get("leave_pending"):
            return
        kind = action[0]
        if kind=='perf_start':
            from .performance import AppProfiler
            if self.profiler is not None:self.profiler.close()
            self.profiler=AppProfiler(self,detail=bool(action[1]))
            self.state['performance_recording']='详细计时' if action[1] else '基础计时'
            self.message('性能记录已开始，返回对局即可采样。')
            return
        if kind in ('perf_stop','perf_export'):
            if self.profiler is not None:
                path=self.profiler.export()
                if kind=='perf_export' and self.android and not self.profiler.error:
                    try:
                        from modkit.android.platform_android import export_performance
                        path=export_performance(path)
                    except Exception as exc:self.message('已保存游戏内记录，导出下载目录失败：'+str(exc));return
                self.message('性能记录保存失败：'+self.profiler.error if self.profiler.error else '性能记录：'+str(path))
                self.state['performance_path']=str(path)
                if kind=='perf_stop':
                    self._crowd_profile_battle=self.room.battle if self.room else None
                    self.profiler.unbind();self.profiler=None;self.state['performance_recording']='已停止'
            return
        if kind=='perf_boost':
            from . import perf_hooks
            perf_hooks.set_boost(not perf_hooks.boost_enabled())
            self.message('性能申请已'+('开启' if perf_hooks.boost_enabled() else '关闭')+'，可在同一局里对照慢放倍率。')
            return
        if kind in ('world_quality','display_filter','display_budget'):
            from .display_pipeline import QUALITIES, FILTERS
            if kind=='display_budget':self.state[kind]=not self.state.get(kind,True)
            else:
                choices=QUALITIES if kind=='world_quality' else FILTERS
                old=self.state.get(kind,choices[0]);self.state[kind]=choices[(choices.index(old)+1)%len(choices)]
            self.save_settings()
            return
        if kind=='perf_diag_export':
            from . import perf_hooks
            data=perf_hooks.report()
            if data is None:
                self.message('本机没有性能诊断数据。');return
            try:
                folder=self.settings_path.parent/'performance';folder.mkdir(parents=True,exist_ok=True)
                path=folder/('android-perf-%s.json'%time.strftime('%Y%m%d-%H%M%S'))
                path.write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding='utf8')
                if self.android:
                    from modkit.android.platform_android import export_performance
                    path=export_performance(path)
            except Exception as exc:
                self.message('性能诊断导出失败：'+str(exc));return
            self.state['performance_path']=str(path);self.message('性能诊断：'+str(path))
            return
        if kind=='skip_result_animation':
            self.result_animation.skip();self.result_outro.skip();self.state.pop('result_animation_pending',None)
            self.state.pop('result_outro_ran',None);self.state.pop('result_curtain_pending',None);return
        if self.spectator_action(action):return
        if self.replay_action(action):
            return
        if self.map_editor_action(action):
            return
        if self.pve_action(action):
            return
        if kind == "relay_visibility":
            self.state["room_public"] = not self.state.get("room_public", True)
            return
        if kind == "room_size":
            self.state["room_size"] = "duel" if self.state.get("room_size") == "duo" else "duo"
            return
        if kind == "tutorial":
            from .tutorial import action as tutorial_action
            tutorial_action(self, action)
            return
        if kind == "ai_room":
            from .lobby_room import create as create_ai_room
            option = action[1] if len(action) > 1 else "play"
            create_ai_room(self, watch=option in ("watch", "watch_duo"), duo=option in ("duo", "watch_duo"),
                           coop=option == "coop")
            if option == "coop":
                self.state.update(screen="room", focus=None)
            return
        if kind in ("relay_lobby", "relay_refresh"):
            self.state.update(screen="relay_lobby", focus=None)
            if self.lobby_query:
                return
            try:
                self.lobby_query = LobbyQuery(self.state.get("relay_endpoint", ""))
                self.state["lobby_loading"] = True
            except (ValueError, OSError) as exc:
                self.message(str(exc))
            return
        if kind == "relay_page":
            self.state["lobby_page"] = max(0, min((len(self.state.get("public_rooms", []))-1)//3, self.state.get("lobby_page", 0)+action[1]))
            return
        if kind == "relay_join":
            self.state.update(network_mode="relay", token=action[1])
            self.join()
            return
        if kind == "network_mode":
            self.state["network_mode"] = action[1]
            self.state.update(focus=None, message="", token="")
            return
        if kind == "copy_relay_code":
            try:
                copy_text(self.pg, self.state.get("token", ""))
                self.message("房间码已复制，发给朋友即可。")
            except Exception:
                self.message("剪贴板不可用，请手动分享房间码：" + self.state.get("token", ""))
            return
        if kind == "fill_ai":
            if self.mode != 'host' or not self.room:return
            if self.room.phase not in ('config','result'):
                self.message('请在准备界面邀请 AI');return
            if self.ai_room is None:
                from .lobby_room import AIRoom
                self.ai_room = AIRoom(self, autofill=False)
            error = self.ai_room.invite(action[1] if len(action)>1 else None)
            if error:self.message(error)
            self.refresh()
            return
        if kind == "kick":
            if self.mode == "host" and self.room:
                peer = action[1] if len(action)>1 else next((p for p in self.room.members if p != "host"), None)
                if peer=='host' or peer not in self.room.members:return
                if peer is not None:
                    if self.transport:
                        try:self.transport.send(peer, {"type": "error", "message": "你已被房主请出房间。", "terminal": True})
                        except Exception:pass
                    self.room.kick(peer)
                    if self.ai_room is not None:self.ai_room.seats.pop(peer, None)
                    self.refresh()
            return
        if kind == "room_reopen":
            if self.mode == "host" and self.room:
                error = self.room.reopen()
                if error:self.message(error)
                self.refresh()
            return
        self.state["button_feedback"]=(action,time.monotonic()+.18)
        self.play_ui_sound()
        if kind == "menu":
            target = action[1]
            if target=='profile':
                self.release_inputs()
                self.state.update(return_screen=self.state.get('screen','home'),screen='profile',focus=None,
                                  profiles=self.profiles.summaries(),profile_delete_pending=None)
                return
            if target=='action_keys':
                self.state.update(screen=target,editor_return_screen=self.state.get('return_screen','home'),return_screen='settings',focus=None)
                return
            if target in ("settings", "almanac", "help", "home", "bans", "room_info", "room_requests", "touch_layout"):
                self.release_inputs()
                self.state["confirm_surrender"] = False
            if target in ("settings", "help", "almanac", "bans", "room_info", "room_requests") and self.state["screen"] not in ("settings", "help", "almanac", "bans", "room_info", "room_requests"):
                self.state["return_screen"] = "room" if self.state["screen"] == "room" else "home"
            if target == "almanac":
                self.state["almanac_scroll"] = 0
            if target == "room_info":
                self.state["connection_details"] = {"mode": self.mode, "peer_id": self.peer_id,
                    "transport_state": self.transport.state if self.transport else ("connected" if self.ai_room is not None else "本地演练"),
                    "address": self.state.get("address", ""), "identity": dict(self.identity),
                    "snapshots": self.received_snapshots}
            if target == "exit":
                self.running = False
            elif target == "local":
                self.create(True)
            elif target == "host":
                self.state.update(screen="host", network_mode="relay", room_public=True, focus=None, message="")
            elif target == "create_host":
                self.create(False)
            elif target == "back":
                leaving_editor = self.state["screen"] in ("touch_layout", "slot_keys", "performance", "action_keys")
                self.state.update(screen=self.state.get("return_screen", "home"), focus=None)
                if self.state['screen']=='draft_reference':self.state['return_screen']='room'
                if leaving_editor:
                    self.state["return_screen"] = self.state.pop("editor_return_screen", "home")
            elif target == "join":
                self.join()
            elif target == "join_form":
                self.state.update(screen="join", network_mode="relay", focus="token", token="")
            elif target in ("touch_layout", "slot_keys", "performance"):
                # The editor's 完成 goes back to settings; keep the outer
                # return target aside so settings' own 返回 still works after.
                self.state.update(screen=target,
                                  editor_return_screen=self.state.get("return_screen", "home"),
                                  return_screen="settings", focus=None)
            else:
                self.state.update(screen=target, focus=None, message="")
            return
        if kind in ('profile_switch','profile_new','profile_delete'):
            self.profile_action(kind,action[1] if len(action)>1 else None)
            return
        if kind=='profile_save':
            from .player_profile import player_name
            self.player_profile.name=player_name(self.state.get('player_name'))
            try:
                self.player_profile.save();self.state['player_name']=self.player_profile.name
                self.state['player_name_saved']=True
                self.sync_player_profile();self.state['focus']=None;self.message('玩家名称已保存')
            except OSError:self.message('名称保存失败，请检查游戏数据目录权限')
            return
        if kind=='draft_reference':
            seat=action[1] if len(action)>1 else self.view.get('current_seat') or self.local_seat(self.view.get('current_side')) or self.view.get('current_side') or self.state.get('active_side','plant')
            side=team_of(seat)
            self.state.update(screen='draft_reference',return_screen='room',advice_side=side,advice_seat=seat,draft_advice=self.draft_advice(side,seat),advice_revision=self.view.get('revision'),focus=None)
            return
        if kind=='advice_card':
            key=action[1]
            seat=self.view.get('current_seat') or self.view.get('current_side')
            if self.view.get('phase')=='picking' and CARDS[key]['side']==self.view.get('current_side') and seat in self.local_seats() and self.state.get('advice_seat',seat)==seat:
                self.state['screen']='room';self.action(('card',key))
            else:
                self.state.update(screen='almanac',return_screen='draft_reference',detail=key,almanac_scroll=0)
            return
        if kind == "help_done":
            self.state["tutorial_seen"] = True
            self.save_settings()
            self.state.update(screen=self.state.get("return_screen", "home"), focus=None)
            return
        if kind == "help_page":
            self.state["help_page"] = max(0, min(2, self.state["help_page"] + action[1]));return
        if kind in ("fullscreen", "low_effects", "sound", "music"):
            if kind == "fullscreen" and self.android:
                self.release_inputs()
                self.apply_display()
                self.message("已启用安卓全屏显示。")
                return
            self.state[kind] = not self.state[kind]
            if kind == "fullscreen":
                self.release_inputs();self.apply_display()
            self.save_settings();return
        if kind in ("volume","music_volume"):
            self.state[kind] = round(max(0., min(1., self.state[kind] + action[1])), 2)
            self.save_settings();return
        if kind == "focus":
            self.state["focus"] = action[1]
            return
        if kind == "reference_context":
            self.state.update(reference_context=action[1], almanac_scroll=0);return
        if kind == "room_info_scroll":
            self.state["room_info_scroll"] = max(0, self.state["room_info_scroll"] + action[1]);return
        if kind=='resolve_config_request':
            self.command(dict(type=kind,request_id=action[1],accept=action[2]));return
        if kind=='cancel_config_request':
            self.command(dict(type=kind));return
        if kind == "map_page":
            self.state["map_page"] = max(0, self.state["map_page"] + action[1]);return
        if kind == "map_info":
            self.state["map_info_id"] = action[1]
            entry = next((entry for entry in self.view.get("map_registry", []) if entry["id"] == action[1]), {})
            self.message("此地图不可选：" + entry.get("reason", "地图验证未通过"));return
        if kind == "random_map":
            candidates = [entry["id"] for entry in self.view.get("map_registry", []) if entry["supported"]]
            if candidates and self.view.get("can_select_map"):
                selected = secrets.choice(candidates)
                self.action(("map", selected))
                self.state["map_page"] = next(i for i, entry in enumerate(self.view["map_registry"]) if entry["id"] == selected) // self.state.get("map_page_size", 9)
            return
        if kind == "setting":
            key, delta = action[1], action[2]
            low, high = (.8, 1.6 if self.state.get("touch_mode") else 1.15) if key == "ui_scale" else (.65, 1.5)
            self.state[key] = round(min(high, max(low, self.state[key] + delta)), 2)
            self.apply_scale();self.save_settings();return
        if kind == "touch_mode":
            if self.android and self.state["touch_mode"]:
                self.message("安卓触屏设备必须开启触摸按键。")
                return
            self.state["touch_mode"] = not self.state["touch_mode"]
            if not self.state["touch_mode"]:
                self.release_inputs()
            if self.state["ui_scale"] > (1.15 if not self.state["touch_mode"] else 1.6):
                self.state["ui_scale"] = 1.15
            self.apply_scale();self.save_settings();return
        if kind == "touch_mirror":
            self.state["touch_mirror"] = not self.state["touch_mirror"]
            self.save_settings();return
        if kind == "touch_size":
            self.state["touch_size"] = min(2, max(0, self.state.get("touch_size", 1) + action[1]))
            self.save_settings();return
        if kind == "layout_scale":
            self.touch.editor_scale_selected(action[1] * .1);return
        if kind == "layout_reset":
            self.state["touch_layout"] = {}
            self.touch.editor_selected = None
            self.save_settings();self.message("已恢复默认按键布局");return
        if kind == "facing":
            self.state['touch_quick_plant'] = len(action)>1 and action[1]==0
            if self.state['touch_quick_plant']:
                self.save_settings();self.message('自动：种植与铲子操作跟随戴夫朝向（向左=左键，向右=右键）');return
            self.state["touch_facing"] = action[1] if len(action) > 1 else -self.state.get("touch_facing", -1)
            self.save_settings()
            self.message("种植与铲子方向：" + ("向右（右键）" if self.state["touch_facing"] > 0 else "向左（左键）"))
            return
        if kind == "bind":
            self.state["bind_pending"] = action[1]
            self.message("请按新的按键；Esc 取消。")
            return
        if kind == "numeric_cd":
            self.state["numeric_cd"] = not self.state.get("numeric_cd", True)
            self.save_settings();return
        if kind == "reset_settings":
            old_fullscreen = self.state["fullscreen"]
            self.state.update(bindings=dict(self.default_bindings), zoom=1., ui_scale=1., numeric_cd=True, bind_pending=None,
                              fullscreen=False, low_effects=False, sound=True, volume=.35,music=True,music_volume=.25, touch_layout={}, save_replays=False)
            if old_fullscreen:
                self.apply_display()
            self.apply_scale();self.save_settings();self.message("已恢复对战默认设置");return
        if kind == "endpoint":
            count = len(self.state.get("endpoints", []))
            if count:
                self.state["endpoint_index"] = (self.state["endpoint_index"] + action[1]) % count
            return
        if kind == "copy_address":
            endpoints = self.state.get("endpoints", [])
            if not endpoints:
                self.message("未发现可分享的本机地址。")
                return
            text = endpoints[self.state["endpoint_index"] % len(endpoints)] + "\n房间口令：" + self.state.get("token", "")
            try:
                copy_text(self.pg, text)
                self.message("已复制所选地址和口令；本机候选地址不代表公网可达。")
            except Exception:
                self.message("系统剪贴板不可用，请手动复制屏幕上的地址和口令。")
            return
        if kind == "almanac_tab":
            self.state.update(almanac_category=action[1], almanac_page=0, almanac_scroll=0)
            return
        if kind == "almanac_page":
            self.state["almanac_page"] = max(0, self.state["almanac_page"] + action[1]);return
        if kind == "almanac_card":
            self.state.update(detail=action[1], almanac_scroll=0);return
        if kind == 'almanac_detail':
            self.state.update(almanac_detailed=not self.state.get('almanac_detailed',False),almanac_scroll=0);return
        if kind == "almanac_scroll":
            self.state["almanac_scroll"] = max(0, self.state["almanac_scroll"] + action[1]);return
        self.state["focus"] = None
        if kind == "map":
            self.state["map_info_id"] = None
            from .team_maps import bundled_id, map_command
            if bundled_id(action[1]):
                self.command(map_command(bundled_id(action[1]), self.view.get("revision")), self.room.side_for("host") if self.mode == "local" else None)
                return
            self.command({"type": "map", "map_id": action[1], "seed": self.view.get("seed", 1)}, self.room.side_for("host") if self.mode == "local" else None)
        elif kind == "weather":
            from .maps import next_weather
            self.command(dict(type="map",map_id=self.view["map_id"],seed=self.view.get("seed",1),
                **next_weather(self.view.get("map",{}).get("environment",{}))),
                self.room.side_for("host") if self.mode=="local" else None)
        elif kind == "night":
            self.command({"type":"map","map_id":self.view["map_id"],"seed":self.view.get("seed",1),
                "night":not self.view.get("map",{}).get("environment",{}).get("night",False)},
                self.room.side_for("host") if self.mode=="local" else None)
        elif kind == "seed":
            self.command({"type": "map", "map_id": self.view["map_id"], "seed": (self.view.get("seed", 1) + 1) % (2 ** 31)}, self.room.side_for("host") if self.mode == "local" else None)
        elif kind == "swap":
            self.command({"type": "swap"}, self.room.side_for("host") if self.mode == "local" else None)
        elif kind == "room_options":
            rules = self.view.get("rules") or {}
            values = dict(ranked=bool(rules.get("ranked")), extra_slot=bool(rules.get("extra_slot")))
            values[action[1]] = not values[action[1]]
            self.command(dict(type="room_options", **values), self.room.side_for("host") if self.mode == "local" and self.room else None)
        elif kind == "confirm_map":
            # Confirmations are per seat: a 2v2 player whose teammate (same
            # faction) already confirmed must still send their own.
            for seat in self.local_seats():
                if not self.view.get("confirmed", {}).get(seat):
                    self.command({"type": "confirm_map", "terrain_hash": self.view.get("terrain_hash")}, seat)
        elif kind == "tab":
            self.state["tabs"][action[1]] = action[2];self.state["pages"][action[1]] = 0
        elif kind == "page":
            side = action[1]
            self.state["pages"][side] = max(0, self.state["pages"][side] + action[2])
        elif kind in ("card", "picked_card"):
            key = action[-1]
            self.state["detail"] = key
            if right:
                self.state.update(screen="almanac",return_screen="room",almanac_scroll=0)
                return
            self.state.update(pending_ban=None,pending_card=None)
            phase = self.view.get("phase")
            actor=self.view.get("current_side")
            if kind=="picked_card":
                self.message("此卡已锁定，不能撤回；右键查看详情。")
                return
            if actor not in self.local_sides():
                self.message("等待对方完成当前回合。")
                return
            if phase == "banning":
                if CARDS[key].get("ban_protected"):
                    self.message("咖啡豆、花盆、睡莲和梯子僵尸不可禁选。")
                elif ((CARDS[key]["category"]=="secret") != (self.view.get("current_action") in ("secret","zsecret"))
                      or CARDS[key]["side"] != {"secret":"plant","zsecret":"zombie"}.get(self.view.get("current_action"),self.view.get("current_action"))):
                    self.message("请在本回合高亮的卡池中禁用；秘籍在各自的“秘籍”分页。")
                else:
                    self.state["pending_ban"] = key
                    self.message("已预览 %s；点击“确认禁用”提交。" % CARDS[key]["name"])
            elif phase == "picking":
                if CARDS[key]["side"]!=actor:
                    self.message("当前只能选择己方卡牌。")
                elif key in self.view.get("decks",{}).get(self.view.get("current_seat") or actor,[]):
                    self.message("此卡已在阵容中。")
                else:
                    self.state["pending_card"]=key
                    self.message("已预览 %s；确认选取后锁定并切换回合。"%CARDS[key]["name"])
        elif kind == "advance":
            if self.view.get("draft_stage") == "complete":
                for seat in self.local_seats():
                    self.command({"type": "ready", "ready": not self.view.get("ready", {}).get(seat, False)}, team_of(seat))
            elif self.view.get("phase")=="picking" and self.state.get("pending_card"):
                key=self.state["pending_card"]
                error=self.command({"type":"pick","card":key},self.view.get("current_side"))
                if not error:
                    self.state["pending_card"]=None
                    self.message("已锁定 "+CARDS[key]["name"]+"，按回合提示继续。")
            elif self.view.get("phase") == "banning" and self.state.get("pending_ban"):
                error = self.command({"type": "ban", "card": self.state["pending_ban"]}, self.view.get("current_side"))
                if not error:
                    self.state["pending_ban"] = None
                    self.message("禁选已确认，按回合提示继续。")
            else:
                self.message("请先预览当前回合的卡牌，再确认。")
        elif kind=="skip_ban":
            self.command({"type":"ban","card":None},self.view.get("current_side"))
        elif kind == "recommended":
            if self.view.get("phase") != "picking":
                self.message("推荐只用于当前选卡回合。")
            else:
                side=self.view.get("current_side")
                if side in self.local_sides():
                    own=self.view.get("decks",{}).get(self.view.get("current_seat") or side,[])
                    legal=lambda k:k in CARDS and k not in own and allowed(k,self.view.get("bans",[])) and CARDS[k]["side"]==side
                    # A loaded deck plan is the player's stated intent: propose its
                    # next legal card before any fresh AI advice overrides it.
                    planned=next((k for k in self.state.get("draft_plan",{}).get(side,[]) if legal(k)),None)
                    advice={} if planned else self.draft_advice(side)
                    key=planned or next((k for k in advice.get('deck',()) if legal(k)),None)
                    if key:
                        self.state["tabs"][side]=CARDS[key]["category"]
                        self.action(("card",key))
                        reason='载入的卡组计划' if planned else advice.get('reasons',{}).get(key,'适合当前阵容')
                        self.message('推荐 '+CARDS[key]['name']+'：'+reason+'；确认后选取')
        elif kind == "save_deck":
            try:
                decks = {seat: self.view.get("decks", {}).get(seat, []) for seat in self.local_seats()}
                save_decks(self.settings_path.parent / "decks.json", decks, self.view.get('rules'))
                self.message("当前对战卡组已保存，附带卡池和规则版本。")
            except (OSError, ValueError) as exc:
                self.message(exc)
        elif kind == "load_deck":
            try:
                decks = load_decks(self.settings_path.parent / "decks.json", self.view.get("bans", []))
                self.state["draft_plan"]={side:decks.get(self.local_seat(side),decks.get(side,[])) for side in self.local_sides()}
                self.action(('draft_reference',self.state.get('advice_seat') or self.view.get('current_seat') or self.state.get('advice_side') or self.view.get('current_side') or 'plant'))
                self.message("已载入本地阵容，并按本局地图与禁用补全。")
            except (OSError, ValueError) as exc:
                self.message(exc)
        elif kind == "active_side":
            if action[1] in self.local_sides():
                self.state.update(active_side=action[1], selected_card=None, battle_page=0,shovel=False,teleport=False,rally=False)
                self.state.pop('rally_drag',None)
        elif kind == 'shovel':
            self.state['rally']=False
            self.state['teleport']=False
            if self.state['active_side']=='plant' and 'plant' in self.local_sides():
                self.state.update(shovel=not self.state.get('shovel',False),selected_card=None)
                self.message(('铲子：左键铲除，右键跳过保护壳；水盆右键变花盆。触屏自动／左／右切换，长按右键；%s取消' % self.binding_name('cancel')) if self.state['shovel'] else '')
        elif kind == 'cancel_action':
            self.cancel_battle_action()
        elif kind == "select_card":
            self.state['rally']=False
            self.state['teleport']=False
            self.state['shovel']=False
            self.state["selected_card"] = action[1]
            self.copy_hint()
        elif kind == 'teleport':
            self.state['rally']=False
            self.state.pop('rally_drag',None)
            if self.state['active_side'] in self.local_sides():
                self.state.update(teleport=not self.state.get('teleport',False),selected_card=None,shovel=False)
                self.message('传送：点击己方植物或墓碑；再次点击传送取消' if self.state['teleport'] else '')
        elif kind == "hud_toggle":
            # Local HUD switches (enemy overview, folded teammate bank).
            if action[1] in ("enemy_overview", "mate_collapsed"):
                self.state[action[1]] = not self.state.get(action[1], False)
        elif kind == "gift":
            self.gift_teammate()
        elif kind == "battle_page":
            self.state["battle_page"] += 1;self.state["selected_card"] = None
        elif kind == "rally":
            self.begin_rally(None)
        elif kind == "command":
            held_rally=self.state.get('rally')
            self.state['rally']=False;self.state.pop('rally_drag',None)
            if not held_rally or (self.view.get('battle') or {}).get('rally_point') is not None:
                self.input("zombie", "command")
        elif kind == "pause":
            paused=bool(self.view.get('paused'))
            seat=self.local_seat(self.state['active_side'])
            self.command({'type':'pause','paused':not paused,'pause_epoch':self.view.get('pause_epoch',0),
                          'cancel':not paused and seat in self.view.get('pause_votes',[])},self.state['active_side'])
        elif kind == "rematch":
            for side in self.local_sides():
                value=action[1] if len(action)>1 else False
                self.command({"type": "rematch", "swap": value is True,'same_deck':value=='same_deck'}, side)
            self.state.update(selected_card=None, grave=None)
        elif kind == "restart":
            # Mirrors the rematch vote: one ballot per local side, so a hot-seat
            # match restarts outright while a networked match waits for the peer.
            sides = self.local_sides()
            if not sides:
                self.message("连接未就绪，无法请求重开。")
            else:
                for side in sides:
                    self.command({"type": "restart"}, side)
        elif kind == "surrender":
            sides = self.local_sides()
            side = self.state.get("active_side") if self.state.get("active_side") in sides else (sides[0] if sides else None)
            if not side:
                self.message("连接未就绪，无法投降。")
            elif (self.view or {}).get("phase") != "battle" or (self.view or {}).get("result"):
                self.state["confirm_surrender"] = False
                self.message("当前不在对局中，无需投降。")
            elif not self.state.get("confirm_surrender"):
                self.state["confirm_surrender"] = True
                self.message("再点一次向队友发起投降请求。" if self.view.get('mode') in ('duo','coop') else "再点一次确认投降，即认输本局。")
            else:
                self.state["confirm_surrender"] = False
                error = self.input(side, "surrender")
                self.message(error or ("已发起投降请求，等待队友确认。" if self.view.get('mode') in ('duo','coop') else "已投降认输，本局判负。"))
        elif kind == 'surrender_vote':
            side=self.state.get('active_side')
            self.input(side,'surrender_'+action[1],request=action[2])
        elif kind == "export_log":
            if self.mode == 'guest':
                self.request_replay()
                return
            if self.room and getattr(self.room,'recording',None) is not None and not self.room.audit_error:
                self.save_recording(self.room,manual=True)
                return
            path = self.settings_path.parent / ("audit-%d.json" % int(time.time()))
            if self.room:
                try:
                    self.room.export_log(path)
                except (OSError, AuditLogError, ValueError) as exc:
                    self.message("导出失败，房间与已有记录已保留；释放磁盘空间后可重试：" + str(exc))
                else:
                    self.message("对局记录已导出：" + str(path))
            else:
                self.message("完整权威日志保存在主机，请由主机导出。")
        elif kind == "leave":
            self.leave_modal()
        elif kind == "cancel_leave":
            self.state["confirm_leave"] = False
        elif kind == "confirm_leave":
            if self.state.get('spectating'):
                self.close_room(graceful=True)
            elif self.view.get("phase") == "battle" and not self.view.get("audit_error"):
                self.release_inputs()
                self.state.update(leave_pending=True, leave_elapsed=0., leave_settled_elapsed=0., confirm_leave=False)
                sides = self.local_sides()
                error = self.input(sides[0], "surrender") if sides else "not_connected"
                self.send_timer = .1
                if error:
                    self.close_room();self.message("连接未就绪，已离开；对方按房间断线规则处理。")
                else:
                    self.message("正在确认认输结果并离开…")
            else:
                self.close_room(graceful=True)

    def cannon_aiming(self):
        """本方是否正处在玉米加农炮的瞄准态（此时左键=发射、右键=取消）。"""
        if "plant" not in self.local_sides():
            return False
        battle = self.view.get("battle") or {}
        return bool((battle.get("players") or {}).get("plant", {}).get("cannon_aim"))

    def cannon_at(self, x, y):
        """己方存活玉米炮的命中框；点击、进瞄准与开炮共用同一个框。"""
        battle = self.view.get("battle") or {}
        width = (battle.get("map") or self.view["map"])["width"]
        units = battle.get("units", [])
        units = list(units.values()) if isinstance(units, dict) else units
        return any(u["side"] == "plant" and u["card_id"] == "plant:玉米加农炮" and u["hp"] > 0 and
                   abs((u["x"] - x + width / 2) % width - width / 2) < 30 and
                   abs(u["y"] - y - 20) < 50 for u in units)

    def cancel_battle_action(self):
        if self.cannon_aiming():self.input('plant','cannon_cancel')
        self.state.update(selected_card=None,shovel=False,teleport=False,grave=None,rally=False,
                          copy=None,placement_preview=None,message='')
        self.state.pop('rally_drag',None)
        self.pointer_capture=None

    def resource_at(self, x, y):
        battle=self.view.get('battle') or {}
        width=(battle.get('map') or self.view.get('map') or {}).get('width',3456)
        resources=battle.get('resources',[])
        if isinstance(resources,dict):resources=resources.values()
        scale=self.renderer.camera[2] if self.renderer.camera else 1.
        from .world_view import sun_pick_radius
        base=max(30.,18./scale)
        candidates=[r for r in resources if r.get('side','plant')=='plant'
                    and abs((r['x']-x+width/2)%width-width/2)<sun_pick_radius(r.get('amount',25),base)
                    and abs(r['y']-y)<sun_pick_radius(r.get('amount',25),base)]
        return min(candidates,key=lambda r:abs((r['x']-x+width/2)%width-width/2)+abs(r['y']-y)) if candidates else None

    def world_touch_can_jump(self, pos):
        if (self.state.get('screen')!='room' or self.view.get('phase')!='battle'
                or self.state['active_side'] not in self.local_sides()
                or self.view.get('audit_error') or self.state.get('confirm_leave')
                or self.state.get('leave_pending') or self.state.get('selected_card')
                or self.state.get('rally') or self.state.get('shovel') or self.state.get('teleport') or self.cannon_aiming()):return False
        point=self.renderer.world_point(pos)
        if not point:return False
        if self.state['active_side']=='plant':
            return not self.resource_at(*point) and not self.cannon_at(*point) and not self.turn_plant_at(*point)
        battle=self.view.get("battle") or {}
        width=(battle.get("map") or self.view.get("map") or {}).get("width")
        if width and self.detonate_target_at(self.state['active_side'],point[0],point[1],width):
            # Tapping an own unit that this press would detonate must reach the
            # world click, not the world jump (player report 10-15: 安卓点不出自爆).
            return False
        return not self.graves_at(*point)

    def holds_secret(self, side, key):
        battle = self.view.get("battle") or {}
        return key in ((battle.get("players") or {}).get(side) or {}).get("secrets", ())

    def clown_at(self, side, x, y, width):
        """An own, live jack-in-the-box zombie under the pointer (PvP61).

        PvP66 自爆: with that zombie secret every own walking zombie counts."""
        battle = self.view.get("battle") or {}
        tile = (battle.get("map") or self.view.get("map") or {}).get("tile_size", 48)
        units = battle.get("units", [])
        units = list(units.values()) if isinstance(units, dict) else units
        blast = side == "zombie" and self.holds_secret(side, "zsecret:自爆")
        hits = [u for u in units if u.get("side") == side and u.get("hp", 0) > 0
                and (u.get("card", {}).get("name") == "小丑僵尸" or blast and u.get("mobile"))
                and abs((u["x"]-x+width/2) % width-width/2) < tile*.6
                and u["y"]-tile*2 <= y <= u["y"]+tile*.2]
        return min(hits, key=lambda u: abs(u["x"]-x), default=None)

    def detonate_target_at(self, side, x, y, width):
        """The own unit a plain press detonates: PvP61 小丑僵尸 or PvP66 自爆.

        Shared by the world click and by the touch jump guard, which must leave
        the press to the world click instead of treating it as a jump."""
        clown = self.clown_at(side, x, y, width)
        if clown and (clown.get("card", {}).get("name") == "小丑僵尸" or not self.graves_at(x, y)):
            return clown
        return None

    def world_click(self, pos, right=False):
        if self.state.get("screen") != "room":
            # Only the battle screen may commit world actions; overlay screens
            # (settings, layout editor) must never leak a deploy through.
            return
        if self.view.get("phase") != "battle" or self.view.get("audit_error"):
            return
        if self.state.get('rally'):
            if right and not self.state.get('touch_mode'):self.cancel_battle_action()
            else:self.place_rally(pos)
            return
        turn_right = right
        if right and self.state.get('touch_mode'):
            # The touch selector chooses an operation side, not desktop's
            # general cancel gesture. Teleport/collect/select remain usable.
            if self.state.get('teleport') or (not self.state.get('selected_card')
                    and not self.state.get('shovel') and not self.cannon_aiming()):
                right = False
        if self.state.get('teleport'):
            if right:self.state['teleport']=False;self.message('');return
            point=self.renderer.world_point(pos)
            if not point:return
            side=self.state['active_side'];battle=self.view.get('battle') or {};width=(battle.get('map') or self.view['map'])['width']
            units=battle.get('units',[]);units=list(units.values()) if isinstance(units,dict) else units
            candidates=[u for u in units if u.get('side')==side and u.get('hp',0)>0
                and (u.get('card',{}).get('side')=='plant' if side=='plant' else u.get('behavior')=='grave')
                and abs((u['x']-point[0]+width/2)%width-width/2)<35 and abs(u['y']-point[1]-24)<55]
            if not candidates:self.message('请选择己方存活的植物或墓碑');return
            target=min(candidates,key=lambda u:abs(u['y']-point[1]-24))
            error=self.input(side,'teleport',target=target['id'])
            if not error:self.state['teleport']=False;self.message('已提交传送，落点与冷却由主机确认')
            return
        if right and self.cannon_aiming():
            # 瞄准期间右键属于瞄准流程，优先于"取消选卡 / 收铲子"。
            self.input("plant", "cannon_cancel")
            self.state.update(selected_card=None, shovel=False, teleport=False, grave=None, copy=None)
            self.message("已取消玉米炮瞄准")
            return
        if right and not self.state.get("selected_card") and not self.state.get('shovel'):
            if not self.turn_plant_at(*(self.renderer.world_point(pos) or (-1,-1))):
                if self.state["active_side"] == "plant":self.input("plant","cannon_cancel")
                return
        point = self.renderer.world_point(pos)
        if not point:
            return
        x, y = point
        side = self.state["active_side"]
        if self.state.get('shovel') and side=='plant':
            error=self.input(side,'shovel',x=x,y=y,right=right)
            if not error:self.state['shovel']=False;self.message('已铲除植物')
            return
        battle = self.view.get("battle") or {}
        width = (battle.get("map") or self.view["map"])["width"]
        if side=='plant' and not right and not self.cannon_aiming():
            resource=self.resource_at(x,y)
            if resource:
                self.input(side,'collect',resource=resource['id']);return
        if not right and not self.state.get("selected_card"):
            clown = self.detonate_target_at(side, x, y, width)
            if clown:
                error = self.input(side, "detonate", target=clown["id"])
                if not error:self.message("已引爆小丑僵尸" if clown.get("card", {}).get("name") == "小丑僵尸" else "已引导僵尸自爆")
                return
        graves = self.graves_at(x,y)
        if side == "zombie" and graves:
            self.state["grave"] = graves[0]["id"]
            self.sync_selected_grave()
            if not self.state.get("selected_card"):
                self.message("已选择出兵墓碑")
                return
        card = self.state.get("selected_card")
        if card and side == "plant" and (self.cannon_aiming() or self.cannon_at(x, y)):
            # 玉米加农炮：手里拿着卡点己方炮身，要先进瞄准，而不是把卡丢出去。
            # 顺手放下卡 / 铲子 / 传送 —— 瞄准期间左键是发射、右键是取消，这两个
            # 键不能再被它们占着，否则右键会先去取消选卡、取消不掉瞄准。
            self.state.update(selected_card=None, shovel=False, teleport=False, grave=None, copy=None)
            error = self.input(side, "cannon", x=x, y=y)
            if error:
                self.message(error)
            else:
                self.message("玉米炮：左键点目标位置发射，右键取消瞄准。")
            return
        if card:
            if self.state.get('touch_mode') and self.state.get('touch_quick_plant',True):
                facing=battle.get('players',{}).get(side,{}).get('facing',-1)
            elif right:
                facing = 1
            elif self.state.get("touch_mode"):
                facing = self.state.get("touch_facing", -1)
            else:
                facing = -1
            options = dict(facing=facing)
            error=self.input(side, "deploy", card=card, x=x, y=y, grave=self.state.get("grave"), copy=self.state.get("copy") if CARDS[card]["behavior"] == "copy" else None, **options)
            if not error:self.message("")
        elif side == "plant":
            if self.cannon_aiming() or self.cannon_at(x, y):
                error = self.input(side, "cannon", x=x, y=y)
                if error:
                    self.message(error)
                else:
                    self.message("玉米炮：左键点目标位置发射，右键取消瞄准。")
            else:
                target = self.turn_plant_at(x,y)
                if target:
                    if self.state.get('touch_mode'):
                        facing = (battle.get('players',{}).get(side,{}).get('facing',-1)
                                  if self.state.get('touch_quick_plant',True) else self.state.get('touch_facing',-1))
                    else:facing = 1 if turn_right else -1
                    self.input(side,'turn',target=target['id'],facing=facing)
                else:self.input(side, "mark")

    def turn_plant_at(self,x,y):
        battle=self.view.get('battle') or {}
        player=battle.get('players',{}).get('plant',{})
        if self.state.get('active_side')!='plant' or 'secret:转向' not in player.get('secrets',()):return None
        if self.cannon_at(x,y):return None
        width=(battle.get('map') or self.view.get('map') or {}).get('width',3456)
        units=battle.get('units',[])
        if isinstance(units,dict):units=list(units.values())
        # The most recently planted body/shell is the visible top layer.
        return next((u for u in reversed(units) if u.get('side')=='plant' and u.get('hp',0)>0
                     and u.get('card',{}).get('side')=='plant'
                     and abs((u['x']-x+width/2)%width-width/2)<35 and abs(u['y']-y-24)<55),None)

    def graves_at(self,x,y):
        battle=self.view.get("battle") or {}
        width=(battle.get("map") or self.view["map"])["width"]
        units=battle.get("units",[])
        units=list(units.values()) if isinstance(units,dict) else units
        return [u for u in units if u["side"]=="zombie" and u["behavior"]=="grave" and u["hp"]>0
                and abs((u["x"]-x+width/2)%width-width/2)<35 and abs(u["y"]-y-20)<50]

    def keyboard(self, event):
        if (self.result_animation.active or self.result_outro.active) and event.key in (self.pg.K_ESCAPE,self.pg.K_SPACE,self.pg.K_RETURN):
            self.action(('skip_result_animation',));return
        if self.spectator_key(event.key):return
        if self.replay_key(event.key):return
        pg = self.pg
        if self.state.get("bind_pending"):
            key = self.state.pop("bind_pending")
            if event.key != pg.K_ESCAPE:
                conflict = next((name for name, value in self.state["bindings"].items() if value == event.key and name != key), None)
                if conflict or event.key in (pg.K_ESCAPE, pg.K_h, pg.K_SPACE):
                    self.message("该按键已用于其他操作，请选择另一个按键。")
                else:
                    self.state["bindings"][key] = event.key
                    self.save_settings();self.message("按键已保存")
            return
        if self.state.get("confirm_leave"):
            self.renderer.confirm_leave()
            if event.key == pg.K_ESCAPE:
                self.action(("cancel_leave",))
            else:
                self.navigate_controls(event.key, getattr(event, "mod", 0))
            return
        if self.view.get("audit_error") and self.state["screen"] == "room":
            self.renderer.audit_error()
            if event.key == pg.K_ESCAPE:
                self.leave_modal()
            else:
                self.navigate_controls(event.key, getattr(event, "mod", 0))
            return
        focus = self.state.get("focus")
        if event.key == pg.K_ESCAPE:
            if self.state["screen"] == "map_editor" and not focus:
                self.action(("mapedit_cancel",) if self.state.get("map_discard") else ("mapedit_back",));return
            if self.state["screen"] in ("maps", "map_launch") and not focus:
                self.action(("maps_back",));return
            if focus:
                self.state["focus"] = None
            elif self.state["screen"] == "help":
                self.action(("help_done",))
            elif self.state["screen"] in ("settings", "almanac", "bans", "room_info", "room_requests", "touch_layout", "slot_keys", "performance", "action_keys", "profile", "draft_reference"):
                self.action(("menu", "back"))
            elif self.state["screen"] == "pve_shop":
                self.action(("pve_shop_back",))       # Esc is 走啦, as in the original shop
            elif self.state["screen"] == "pve":
                self.action(("pve_back",))
            elif self.room or self.transport:
                self.leave_modal(not self.state["confirm_leave"])
            else:
                self.state["screen"] = "home"
            return
        if focus:
            if event.key == pg.K_TAB:
                self.state["focus"] = None
                self.navigate_controls(event.key, getattr(event, "mod", 0))
            elif self.state.get("ime_text"):
                pass                      # the IME owns keys while it composes
            elif event.key == pg.K_BACKSPACE:
                self.state[focus] = self.state.get(focus, "")[:-1]
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER) and focus == "chat":
                self.action(("chat_send",))
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                self.state["focus"] = None
            elif event.key == pg.K_v and getattr(event, "mod", 0) & pg.KMOD_CTRL:
                try:
                    value = read_clipboard(pg).replace("\x00", "").strip()
                    self.state[focus] = (self.state.get(focus, "") + value)[:200 if focus == "address" else 64]
                except Exception:
                    self.message("剪贴板不可用，请直接输入")
            return
        if (event.key in (pg.K_RETURN, pg.K_KP_ENTER) and self.state.get("screen") == "room"
                and (self.view or {}).get('mode') in ('duo','coop')):
            from .team_chat import chat_available, open_chat
            if chat_available(self.view, self.state):
                open_chat(self.state)       # Enter opens team chat in 2v2 / co-op battles
                self.release_inputs()
                return
        if (self.state.get("screen") == "room" and (self.view or {}).get("phase") in ("banning", "picking")
                and event.key == pg.K_r):
            # Draft-phase restart key.  During BP every other key is navigation,
            # so R is free here; it is not a rebindable battle binding because
            # the touch layout reaches the same vote through the 重开 button.
            self.action(("restart",))
            return
        if self.state.get("screen") != "room" or self.view.get("phase") != "battle":
            self.navigate_controls(event.key, getattr(event, "mod", 0))
            return
        if self.view.get("phase") != "battle" or self.view.get("audit_error") or self.state.get("screen") != "room" or self.state.get("confirm_leave") or self.state.get("leave_pending") or not self.state.get("focused", True):
            return
        if event.key == self.state["bindings"]["cancel"]:
            self.cancel_battle_action()
        elif event.key == self.state["bindings"]["page"]:
            self.action(("battle_page",))
        elif event.key == self.state["bindings"]["command"]:
            self.action(("command",))
        elif event.key in [self.state['bindings'].get(k) for k in ('teleport','rally','shovel','pause','gift')]:
            key=next(k for k in ('teleport','rally','shovel','pause','gift') if self.state['bindings'].get(k)==event.key)
            if not getattr(event,'repeat',False):self.action((key,))
        elif self.grave_nav_key(event.key):
            pass
        elif event.key == pg.K_h and self.mode == "local":
            self.action(("active_side", "zombie" if self.state["active_side"] == "plant" else "plant"))
        elif event.key == self.state["bindings"]["copy"]:
            player = (self.view.get("battle") or {}).get("players", {}).get(self.state["active_side"], {})
            choices = [key for key in player.get("deck", []) if CARDS[key]["side"]=="plant" and CARDS[key]["category"] not in ("tool", "secret") and CARDS[key]["behavior"]!="gravebuster"]
            if choices:
                old = self.state.get("copy")
                self.state["copy"] = choices[(choices.index(old) + 1) % len(choices)] if old in choices else choices[0]
                # PvP73: publish the pick so every card bar (the opponent's too) prices 肆意模仿 from it.
                if self.mode in ("host", "guest") and self.view.get("phase") == "battle":
                    self.command(dict(type="copy_target", card=self.state["copy"]), side=self.state["active_side"])
                self.message("模仿目标："+CARDS[self.state["copy"]]["name"]+
                             ("（再点“模仿”切换）" if self.state.get("touch_mode") else "（按 %s 切换）" % self.binding_name('copy')))
        elif event.key in [self.state['bindings']['slot_%d'%i] for i in range(1,9)]:
            player = (self.view.get("battle") or {}).get("players", {}).get(self.state["active_side"], {})
            choices = battle_deck(player)
            page_size = bank_page_size(self.view.get("rules") or RULES, self.state["active_side"], len(choices),
                                       scripted(self.view.get("mode")))
            pages = max(1, math.ceil(len(choices) / page_size))
            slot = next(i for i in range(8) if self.state['bindings']['slot_%d'%(i+1)] == event.key)
            index = (self.state["battle_page"] % pages) * page_size + slot
            if slot >= page_size:index = len(choices)
            if index < len(choices):
                self.state['rally']=False
                self.state['teleport']=False
                if CARDS[choices[index]]["category"]=="secret":
                    self.state["selected_card"]=None;self.message("此槽为常驻秘籍，无需部署。")
                else:
                    self.state["selected_card"] = choices[index];self.state['shovel']=False
                    self.copy_hint()

    def sync_selected_grave(self):
        """解除封印: tell the authority which grave is chosen (it gets 75% protection)."""
        grave = self.state.get("grave")
        if grave and self.holds_secret("zombie", "zsecret:解除封印") and "zombie" in self.local_sides():
            self.input("zombie", "select_grave", grave=grave)

    def grave_nav_key(self, key):
        """解除封印: arrow-style keys step the chosen grave across the map.

        Uses the zombie movement bindings (free online, where both factions
        walk with the plant keys) plus 墓碑↓; the mouse still picks graves."""
        if self.mode not in ("host", "guest") or self.state.get("active_side") != "zombie":
            return False
        binds = self.state["bindings"]
        moves = {binds.get("zombie_left"): (-1, 0), binds.get("zombie_right"): (1, 0),
                 binds.get("zombie_jump"): (0, -1), binds.get("grave_down"): (0, 1)}
        if key not in moves or not self.holds_secret("zombie", "zsecret:解除封印"):
            return False
        battle = self.view.get("battle") or {}
        units = battle.get("units", [])
        units = list(units.values()) if isinstance(units, dict) else units
        graves = [u for u in units if u.get("side") == "zombie" and u.get("behavior") == "grave" and u.get("hp", 0) > 0]
        if not graves:
            self.message("没有可选择的己方墓碑")
            return True
        width = (battle.get("map") or self.view.get("map") or {}).get("width", 1)
        current = next((u for u in graves if u["id"] == self.state.get("grave")), None)
        if current is None:
            hero = (battle.get("players") or {}).get("zombie") or {}
            origin = (hero.get("x", 0), hero.get("y", 0))
        else:
            origin = (current["x"], current["y"])
        dx, dy = moves[key]
        def offset(u):
            return ((u["x"]-origin[0]+width/2) % width-width/2, u["y"]-origin[1])
        ahead = [u for u in graves if u is not current and (offset(u)[0]*dx > 1 if dx else offset(u)[1]*dy > 1)]
        pool = ahead or [u for u in graves if u is not current] or graves
        choice = min(pool, key=lambda u: (abs(offset(u)[0])+abs(offset(u)[1])*2 if dx else abs(offset(u)[1])+abs(offset(u)[0])*.5, u["id"]))
        self.state["grave"] = choice["id"]
        self.sync_selected_grave()
        self.message("已选择墓碑：%s（小地图已标出）" % choice.get("card", {}).get("name", "墓碑"))
        return True

    def navigate_controls(self, key, modifiers=0):
        """Navigate the current topmost renderer control list, never gameplay."""
        pg = self.pg
        controls = self.renderer.controls
        if not controls or self.state.get("leave_pending"):
            return
        index = self.state.get("keyboard_focus")
        index = min(index, len(controls)-1) if isinstance(index, int) else None
        if key in (pg.K_TAB, pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN):
            step = -1 if key in (pg.K_LEFT, pg.K_UP) or key == pg.K_TAB and modifiers & pg.KMOD_SHIFT else 1
            self.state["keyboard_focus"] = (index+step) % len(controls) if index is not None else (0 if step > 0 else len(controls)-1)
        elif key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            index = 0 if index is None else index
            self.action(controls[index][1])
            self.state["keyboard_focus"] = None

    def begin_rally(self, position):
        if (self.state.get('active_side')!='zombie' or 'zombie' not in self.local_sides()
                or self.view.get('spectating') or self.view.get('phase')!='battle'
                or self.state.get('screen')!='room' or self.state.get('confirm_leave')):return False
        if (self.view.get('battle') or {}).get('rally_point') is not None or self.state.get('rally'):
            self.input('zombie','rally',clear=True)
            self.cancel_battle_action()
            self.message('已清除召集点')
            return False
        self.cancel_battle_action()
        self.state['rally']=True
        if position is not None:self.state['rally_drag']=position
        self.message('点击战场放置自己的召集旗；再次点击召集清除，%s 切换本人跟随/追击（旗优先）'%self.binding_name('command')
                     if self.view.get('mode')=='duo' else
                     '点击战场放置召集旗，也可拖动小旗；再次点击召集或按 %s 清除'%self.binding_name('command'))
        return True

    def place_rally(self, position):
        if (not self.state.get('rally') or self.state.get('active_side')!='zombie'
                or self.state.get('screen')!='room' or self.view.get('phase')!='battle'
                or not self.state.get('focused',True)
                or self.view.get('spectating') or self.view.get('paused')
                or self.state.get('confirm_leave') or self.renderer.hit(position) is not None):return
        point=self.renderer.world_point(position)
        if point is None:return
        error=self.input('zombie','rally',x=point[0],y=point[1])
        if not error:
            self.state['rally']=False
            self.message('自己的召集点已提交；再次点击召集清除，%s 只切换本人跟随/追击'%self.binding_name('command')
                         if self.view.get('mode')=='duo' else
                         '召集点已提交；按 %s 或再次点击召集清除'%self.binding_name('command'))

    def end_rally(self, position):
        self.state.pop('rally_drag',None)
        self.place_rally(position)

    def pointer_motion(self, position):
        if self.state.get('rally_drag') is not None:
            self.state['rally_drag']=position;return
        if self.spectator_pointer('motion',position):return
        if self.replay_pointer('motion',position):return
        if self.map_paint is not None:
            self.map_brush(position, self.map_paint == 3)
            return
        captured = self.pointer_capture
        if captured is None:
            return
        if ((captured[3] is not None and not captured[3].collidepoint(position)) or
            (captured[3] is None and abs(position[0]-captured[2][0])+abs(position[1]-captured[2][1]) >= 12)):
            self.pointer_capture = None

    def chat_guard(self, position):
        """While team chat is typed, a press outside the chat box / send button
        only closes the box (draft kept): it never plants, deploys or confirms."""
        if self.state.get("focus") != "chat":
            return False
        if self.renderer.hit(position) in (("focus", "chat"), ("chat_send",)):
            return False
        self.state.update(focus=None, ime_text="")
        return True

    def pointer_down(self, position, button):
        """Shared mouse/touch press; position is logical, button 1=left 3=right."""
        if self.chat_guard(position):
            self.pointer_capture = None
            return
        if self.spectator_pointer('down',position,button):return
        if self.replay_pointer('down',position,button):return
        if self.map_brush(position, button == 3):
            self.map_paint = button
            self.pointer_capture = None
            return
        self.state["keyboard_focus"] = None
        action = self.renderer.hit(position)
        if action == ('rally',) and button==1:
            self.begin_rally(position);self.pointer_capture=None;return
        if (action is None and self.view.get("phase") == "battle" and
                (self.state.get("selected_card") or
                 (self.state.get('shovel') and not self.state.get("touch_mode"))) and
                not self.state["confirm_leave"]):
            # Original planting commits on press, independent of hand
            # movement or network updates before the button is released.
            # Touch shovel instead commits on release, so a long press still
            # reaches the right-button (skip-pumpkin) path.
            self.pointer_capture = None
            self.world_click(position, button == 3)
            return
        rect = next((rect.copy() for rect, candidate in reversed(self.renderer.controls)
                     if candidate == action and rect.collidepoint(position)), None)
        self.pointer_capture = (button, action, position, rect,
                                self.view.get("revision"), self.state.get("screen"))

    def pointer_up(self, position, button):
        if self.state.get('rally_drag') is not None:
            self.end_rally(position);return
        if self.spectator_pointer('up',position,button):return
        if self.replay_pointer('up',position,button):return
        if self.map_paint is not None:
            self.map_paint = None
            return
        captured = self.pointer_capture
        self.pointer_capture = None
        if not captured or captured[0] != button:
            return
        if captured[4] != self.view.get("revision") or captured[5] != self.state.get("screen"):
            return
        current = self.renderer.hit(position)
        if captured[1] is not None and captured[1] == current and captured[3].collidepoint(position):
            self.action(current, button == 3)
        elif captured[1] is None and current is None and not self.state["confirm_leave"]:
            # A dragged selection cannot become an accidental deploy.
            if abs(position[0] - captured[2][0]) + abs(position[1] - captured[2][1]) < 12:
                self.world_click(position, button == 3)

    def handle_events(self):
        pg = self.pg
        self.released_keys.clear()
        events = list(self.events())
        # SDL can emit both forms for the same physical notch. Prefer modern
        # wheel events for this batch while retaining legacy-only devices.
        modern_wheel = any(e.type == getattr(pg, 'MOUSEWHEEL', -96) for e in events)
        for event in events:
            if event.type == pg.QUIT:
                self.running = False
            elif event.type in (getattr(pg, 'WINDOWSIZECHANGED', -131),
                                getattr(pg, 'WINDOWRESIZED', -132)):
                surface=pg.display.get_surface()
                if surface is not None and self.display_backend.echo(surface):
                    continue    # PVP_SCALED's own set_mode; window and canvas unchanged
                if surface is not None:
                    self.surface=surface
                    self.pointer_capture=None
                    self.release_inputs()
                    self.apply_scale()
            elif event.type in (getattr(pg, 'RENDER_DEVICE_RESET', 0x2001),
                                getattr(pg, 'RENDER_TARGETS_RESET', 0x2000)):
                # Only a PVP_SCALED renderer reacts; the software path ignores these.
                device = event.type == getattr(pg, 'RENDER_DEVICE_RESET', 0x2001)
                self.display_backend.device_reset('device_reset' if device else 'targets_reset')
                if device and self.display_backend.active:
                    self.apply_scale()
            elif event.type == pg.KEYDOWN:
                key = event.key
                if key == getattr(pg, "K_AC_BACK", -1000):
                    # The Android back gesture has its own keycode; the whole
                    # cancel/back tree already hangs off Escape.
                    key = pg.K_ESCAPE
                    event = pg.event.Event(pg.KEYDOWN, key=key, mod=getattr(event, "mod", 0))
                first_press = key not in self.held_keys
                self.held_keys.add(key)
                self.released_keys.discard(key)
                self.keyboard(event)
                if first_press:
                    self.jump_press(key)
                self.move_inputs(0.)
            elif event.type == pg.KEYUP:
                key = event.key
                if key == getattr(pg, "K_AC_BACK", -1000):
                    key = pg.K_ESCAPE
                self.held_keys.discard(key)
                self.released_keys.add(key)
                self.move_inputs(0.)
            elif event.type == getattr(pg, "JOYDEVICEADDED", -93):
                self.controllers.add(getattr(event, "device_index", -1))
                self.state["controller_count"] = len(self.controllers.devices)
            elif event.type == getattr(pg, "JOYDEVICEREMOVED", -92):
                self.controllers.remove(getattr(event, "instance_id", None))
                self.state["controller_count"] = len(self.controllers.devices)
            elif event.type == getattr(pg, "JOYHATMOTION", -95):
                if self.state.get("confirm_leave") or self.view.get("audit_error") or self.state["screen"] != "room" or self.view.get("phase") != "battle":
                    dx, dy = event.value
                    if dx or dy:
                        self.navigate_controls(pg.K_RIGHT if dx > 0 else pg.K_LEFT if dx < 0 else pg.K_UP if dy > 0 else pg.K_DOWN)
            elif event.type == getattr(pg, "JOYBUTTONUP", -94):
                if self.state.get("confirm_leave") or self.view.get("audit_error") or self.state["screen"] != "room" or self.view.get("phase") != "battle":
                    if event.button in (0, 1):
                        self.keyboard(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN if event.button == 0 else pg.K_ESCAPE, mod=0))
            elif event.type == getattr(pg, "TEXTEDITING", -100):
                # The IME's in-progress composition (drawn by the chat box).
                self.state["ime_text"] = getattr(event, "text", "") if self.state.get("focus") else ""
            elif event.type == getattr(pg, "TEXTINPUT", -99):
                focus = self.state.get("focus")
                self.state["ime_text"] = ""
                if focus:
                    limit = 200 if focus == "address" else 64
                    self.state[focus] = (self.state.get(focus, "") + event.text)[:limit]
                    if focus == "search":
                        self.state["pages"] = {"plant": 0, "zombie": 0}
            elif event.type == getattr(pg, "MOUSEWHEEL", -96):
                self.wheel(-event.y if getattr(event, 'flipped', False) else event.y)
            elif event.type == pg.MOUSEBUTTONDOWN and event.button in (4, 5):
                if not modern_wheel:
                    self.wheel(1 if event.button == 4 else -1)
            elif event.type == getattr(pg, "FINGERDOWN", -111):
                if self.touch.active:
                    self.touch.finger(event, "down")
            elif event.type == getattr(pg, "FINGERMOTION", -112):
                if self.touch.active:
                    self.touch.finger(event, "motion")
            elif event.type == getattr(pg, "FINGERUP", -113):
                if self.touch.active:
                    self.touch.finger(event, "up")
            elif event.type in (getattr(pg, "APP_WILLENTERBACKGROUND", -121),
                                getattr(pg, "APP_DIDENTERBACKGROUND", -122)):
                self.app_background()
            elif event.type in (getattr(pg, "APP_WILLENTERFOREGROUND", -123),
                                getattr(pg, "APP_DIDENTERFOREGROUND", -124)):
                self.app_foreground()
            elif event.type == pg.MOUSEMOTION:
                position = self.logical_pos(event.pos)
                if self.touch.active:
                    self.touch.mouse_motion(position)
                elif self.pointer_capture or self.map_paint is not None or self.replay_drag is not None or getattr(self,'spectator_drag',None) is not None:
                    self.pointer_motion(position)
            elif event.type == pg.MOUSEBUTTONDOWN and event.button in (1, 3):
                position = self.logical_pos(event.pos)
                if self.touch.active:
                    self.touch.mouse_down(position, event.button)
                else:
                    self.pointer_down(position, event.button)
            elif event.type == pg.MOUSEBUTTONUP and event.button in (1, 3):
                position = self.logical_pos(event.pos)
                if self.touch.active:
                    self.touch.mouse_up(position, event.button)
                else:
                    self.pointer_up(position, event.button)
            elif event.type == getattr(pg, "WINDOWFOCUSLOST", -98):
                self.state["focused"] = False
                self.pointer_capture = None
                self.map_paint = None
                self.release_inputs()
            elif event.type == getattr(pg, "WINDOWFOCUSGAINED", -97):
                self.state["focused"] = True
                if self.android:
                    self.apply_display()

    def app_background(self):
        """Mobile lifecycle: the process may be frozen any moment after this."""
        if self.ai_room is not None:
            self.ai_room.background()
        self.state["focused"] = False
        self.pointer_capture = None
        self.map_paint = None
        self.release_inputs()
        self.touch.clear()
        if (self.view.get("phase") == "battle" and not self.view.get("paused")
                and not self.view.get("audit_error")):
            sides = self.local_sides()
            if sides:
                # A pause vote is the only safe thing a frozen client can still
                # say; the opponent keeps playing unless they agree.
                self.command({"type": "pause"}, sides[0])
                if self.mode == "local":
                    for side in sides[1:]:
                        self.command({"type": "pause"}, side)
                if self.mode != "local":
                    self.message("已切到后台：已投出暂停票；超过重连时限按断线处理。")

    def app_foreground(self):
        self.state["focused"] = True
        self.touch.clear()
        self.display_backend.foreground()       # PVP_SCALED: re-validate the renderer
        if self.android:
            self.apply_display()
        if self.ai_room is not None:
            self.ai_room.foreground()

    def wheel(self, amount, pos=None):
        if self.state.get("screen") in ("pve_shop", "pve"):
            key = "pve_detail_scroll" if self.state["screen"] == "pve_shop" else "pve_reward_scroll"
            self.state[key] = max(0, int(self.state.get(key, 0) or 0) - int(amount) * 2)
            return
        if self.state.get('spectating') and self.state.get('screen')=='room':
            self.spectator_action(('spectator_zoom',1.15 if amount>0 else 1/1.15));return
        if self.state['screen']=='replay':
            self.replay_action(('replay_zoom',1.15 if amount>0 else 1/1.15));return
        if not amount or self.state.get("confirm_leave") or self.state.get("leave_pending"):
            return
        direction = -1 if amount > 0 else 1
        screen = self.state["screen"]
        x, y = pos if pos is not None else self.logical_pos(self.mouse_pos())
        width = self.renderer.screen.get_width()
        if screen == "almanac":
            self.action(("almanac_scroll", direction*3) if x > width*.49 else ("almanac_page", direction))
        elif screen == "room_info":
            self.action(("room_info_scroll", direction*3))
        elif screen == "help":
            self.action(("help_page", direction))
        elif screen == "room" and self.view.get("phase") == "config":
            if x < width*.43:
                self.action(("map_page", direction))
        elif screen == "room" and self.view.get("phase") in ("banning", "picking"):
            if x < width*.39:
                self.action(("page", "plant", direction))
            elif x > width*.61:
                self.action(("page", "zombie", direction))
        elif screen == "room" and self.view.get("phase") == "battle":
            if input_block_reason(self.state, self.view) is not None:
                return
            side = self.state['active_side']
            if side not in self.local_sides():
                return
            player = (self.view.get('battle') or {}).get('players', {}).get(side, {})
            deck = battle_deck(player)
            choices = [key for key in deck if CARDS[key]['category'] != 'secret']
            if not choices:
                return
            selected = self.state.get('selected_card')
            # First notch selects the nearest end; subsequent notches wrap the
            # whole personal bank, including cards on another page.
            steps = int(abs(amount))
            if not steps:
                return
            start = choices.index(selected) if selected in choices else (-1 if direction > 0 else 0)
            key = choices[(start + direction * steps) % len(choices)]
            page_size = bank_page_size(self.view.get('rules') or RULES, side, len(deck),
                                       scripted(self.view.get('mode')))
            self.state['battle_page'] = deck.index(key) // page_size
            self.state.pop('rally_drag', None)
            self.action(('select_card', key))

    def update_link_notice(self, dt):
        """Say out loud when this client stops sending, or when the other stops.

        Neither state has a network cause, so neither may look like one.
        """
        reason = input_block_reason(self.state, self.view)
        if reason in ("audit", "viewing", "textbox", "leaving", "unfocused"):
            self.state["input_block_seconds"] = (self.state["input_block_seconds"] + dt
                                                 if self.state["input_block"] == reason else dt)
            self.state["input_block"] = reason
        else:
            self.state["input_block"], self.state["input_block_seconds"] = None, 0.
        pieces = []
        if self.state["input_block"] and self.state["input_block_seconds"] >= .5:
            pieces.append(input_block_text(self.state["input_block"]))
        idle = opponent_idle_text(self.view, self.local_sides())
        if idle:
            pieces.append(idle)
        self.state["link_notice"] = " · ".join(pieces)

    def move_inputs(self, dt):
        if input_block_reason(self.state, self.view) is not None:
            return
        self.move_timer += dt
        due = self.move_timer >= .04 - 1e-9
        if due:
            self.move_timer = max(0., self.move_timer - int((self.move_timer + 1e-9) / .04) * .04)
        keys = self.keys()
        def pressed(key):
            if key in self.held_keys:
                return True
            if key in self.released_keys:
                return False
            try:
                return bool(keys[key])
            except (IndexError, KeyError, TypeError):
                # Some embedded input providers return a short list rather
                # than pygame's keycode-aware ScancodeWrapper. Arrow keycodes
                # must never be used as unchecked list offsets.
                return False
        pg = self.pg
        binds = self.state["bindings"]
        for side in self.local_sides():
            if side == "plant" or self.mode in ("host","guest"):
                move = int(pressed(binds["plant_right"])) - int(pressed(binds["plant_left"]))
                jump = pressed(binds["plant_jump"]) or pressed(pg.K_SPACE)
            else:
                move = int(pressed(binds["zombie_right"])) - int(pressed(binds["zombie_left"]))
                jump = pressed(binds["zombie_jump"])
            state = (move, jump)
            if due or self.last_input_states.get(side) != state:
                if not self.input(side, "move", move=move, jump=jump):
                    self.last_move[side] = move
                    self.last_input_states[side] = state

    def _snapshot_pack_worker(self):
        """The host's pack worker, created on first use when enabled.

        PVP_NET_PACK_WORKER=process|thread|off; unset means process (a worker
        interpreter in development, the game EXE's hidden worker mode when
        packaged, threads where neither exists). It is not a simulation worker:
        it never reads live state, and its bytes are identical to inline packing.
        """
        if self.pack_worker is None and self.room is not None:
            from .native_multiworker import SnapshotPackWorker
            mode = os.environ.get("PVP_NET_PACK_WORKER", "").strip().lower() or "process"
            if mode in ("0", "off", "inline", "none"):
                return None
            self.pack_worker = SnapshotPackWorker(mode, MAX_SNAPSHOT_BYTES)
        if self.pack_worker is not None:
            self.pack_worker.profile_detail=bool(self.profiler and self.profiler.detail)
        return self.pack_worker

    def snapshot_interval(self):
        """How often the host pushes a snapshot to its peers.

        A client only ever sees its own hero one snapshot old, and the third
        jump is won or lost inside a 0.40 s window, so a battle runs at 20 Hz.
        Lobby traffic has no such deadline and stays at 10 Hz.
        """
        return .05 if self.view.get("phase") == "battle" else .10

    def jump_press(self, key):
        """Report a jump key press the moment it arrives.

        Held state changes are sent immediately, with a 40 ms keepalive.
        Explicit edges also preserve two taps within a single rendered frame;
        the third jump is locked behind a native 0.40 s window. ``edge`` tells
        the authority this is a fresh press, not a held state.
        """
        if self.mode is None or input_block_reason(self.state, self.view) is not None:
            return
        binds = self.state["bindings"]
        space = getattr(self.pg, "K_SPACE", None)
        for side in self.local_sides():
            if side == "plant" or self.mode in ("host", "guest"):
                keys = (binds.get("plant_jump"), space)
            else:
                keys = (binds.get("zombie_jump"),)
            if key in keys:
                move = self.last_move.get(side, 0)
                if not self.input(side, "move", move=move, jump=True, edge=True):
                    self.last_input_states[side] = (move, True)

    def hover_collect(self, hover):
        """Sweeping the pointer (or a finger) over a sun collects it, no click."""
        if (hover is None or self.state.get('screen')!='room' or self.view.get('phase')!='battle'
                or self.view.get('spectating') or self.view.get('paused') or self.view.get('audit_error')
                or self.state.get('active_side')!='plant' or 'plant' not in self.local_sides()
                or not self.state.get('focused',True) or self.renderer.hit(hover) is not None):
            return
        point=self.renderer.world_point(hover)
        if not point:return
        resource=self.resource_at(*point)
        if resource is None:return
        sent=self.__dict__.setdefault('_hover_collected',{})
        now=time.perf_counter()
        # One request per sun while the host confirms; retry after a moment.
        if now-sent.get(resource['id'],-1.)<.5:return
        if len(sent)>256:sent.clear()
        sent[resource['id']]=now
        self.input('plant','collect',resource=resource['id'])

    def hover_wake(self, hover):
        """A pointer/finger sweep tends a producing grave, even while awake."""
        if (hover is None or self.state.get('screen')!='room' or self.view.get('phase')!='battle'
                or self.view.get('spectating') or self.view.get('paused') or self.view.get('audit_error')
                or self.state.get('active_side')!='zombie' or 'zombie' not in self.local_sides()
                or not self.state.get('focused',True) or self.renderer.hit(hover) is not None):
            return
        point=self.renderer.world_point(hover)
        if not point:return
        graves=[g for g in self.graves_at(*point) if g.get('card',{}).get('producer')]
        if not graves:return
        sent=self.__dict__.setdefault('_hover_woken',{})
        now=time.perf_counter()
        if len(sent)>256:sent.clear()
        # Tend every producer at the pointer (a vine may share a grave's cell).
        # Throttle each stable ID while the host confirms, including awake ones.
        for grave in graves:
            if now-sent.get(grave['id'],-1.)<.5:continue
            sent[grave['id']]=now
            self.input('zombie','wake',grave=grave['id'])

    def preview(self):
        self.state["placement_preview"] = None
        hover = self.touch.hover_pos() if self.touch.active else self.logical_pos(self.mouse_pos())
        # The world view draws hover markers (rally flag) at this logical point.
        self.state["pointer_pos"] = hover
        self.hover_collect(hover)
        self.hover_wake(hover)
        card = self.state.get("selected_card")
        if not card or self.view.get("phase") != "battle":
            return
        if hover is None:
            return
        point = self.renderer.world_point(hover)
        if not point:
            return
        side = self.state["active_side"]
        x, y = point
        error = "";plan=None
        try:
            validator = PreviewBattle.from_snapshot(self.view,bridge=self.bridge)
            graves=self.graves_at(x,y) if side=="zombie" else []
            grave=graves[0]["id"] if graves else self.state.get("grave")
            error, plan = validator.placement(side, card, x, y, grave, self.state.get("copy") if CARDS[card]["behavior"] == "copy" else None)
            if plan:
                x, y = plan.get("x", x), plan.get("y", y)
        except (KeyError, ValueError, TypeError) as exc:
            error = "等待完整部署校验状态"
        self.state["placement_preview"] = dict(x=x, y=y, error=error)
        if plan and CARDS[card]["behavior"]=="grave":
            self.state["placement_preview"].update(x=plan["x"],y=plan["y"],floating=validator.cell(plan["x"],plan["y"]+1).get("water",False) and not CARDS[card].get("shell"))
        # The preview owns transient hover errors. Do not leave an old error
        # in the persistent click-feedback message after hovering a valid cell.

    def render(self):
        prof=self.profiler
        if prof:prof.last=time.perf_counter()
        if self.display_backend.validate_pending:
            self.apply_scale()      # PVP_SCALED resume/reset check before drawing (never set when off)
        battle=self.room.battle if self.room else None
        self.renderer.local_pixels=battle.recorder.latest_pixels if battle is not None else None
        self.renderer.text_scale=1.18 if self.state.get('touch_mode') else 1.
        screen = self.state["screen"]
        result_phase=screen=='room' and self.view.get('phase')=='result'
        if result_phase and self.state.pop('result_animation_pending',False):
            # PvP64: the frozen field first - pan to the loser, who topples -
            # then the original curtains over that picture.
            local=[team_of(s) for s in self.local_sides()]
            if not self.result_outro.start(self.view,local[0] if len(local)==1 else None):
                self.state['result_curtain_pending']=True
        outro_drawn=result_phase and self.result_outro.active and self.result_outro.draw(self.renderer,self.state,self.view)
        if result_phase and not outro_drawn and (self.state.pop('result_curtain_pending',False) or self.state.pop('result_outro_ran',False)):
            result=(self.view.get('battle') or {}).get('result') or self.view.get('result')
            local=[team_of(s) for s in self.local_sides()]
            self.result_animation.start(self.renderer.screen,result,local[0] if len(local)==1 else None,
                                        sound=self.state.get('sound',True),volume=self.state.get('volume',.35))
        if outro_drawn:
            self.state['result_outro_ran']=True
            self.renderer.controls=[]
            width,height=self.renderer.screen.get_size()
            self.renderer.button('跳过动画',(width-180,height-64,155,40),('skip_result_animation',),size=17)
        elif result_phase and self.result_animation.draw(self.renderer.screen):
            self.renderer.controls=[];self.renderer.camera=None
            width,height=self.renderer.screen.get_size()
            self.renderer.button('跳过动画',(width-180,height-64,155,40),('skip_result_animation',),size=17)
        elif self.render_spectator():
            pass
        elif self.render_replays():
            pass
        elif self.render_map_screen():
            pass
        elif screen == "home":
            self.renderer.home(self.state)
        elif screen == "pve":
            self.draw_pve(self.renderer)
        elif screen == "pve_shop":
            self.draw_pve_shop(self.renderer)
        elif screen == "coop_entry":
            self.draw_coop_entry(self.renderer)
        elif screen in ("newbie", "tutorial_menu", "tutorial_rules"):
            from . import tutorial
            {"newbie": tutorial.draw_newbie, "tutorial_menu": tutorial.draw_menu,
             "tutorial_rules": tutorial.draw_rules}[screen](self.renderer, self.state)
        elif screen == "join":
            self.renderer.join_form(self.state)
        elif screen == "host":
            self.renderer.host_form(self.state)
        elif screen == "relay_lobby":
            self.renderer.relay_lobby(self.state)
        elif screen == "help":
            self.renderer.help(self.state)
        elif screen == "bans":
            self.renderer.ban_summary(self.view, self.state)
        elif screen == "room_info":
            self.renderer.room_info(self.view, self.state)
        elif screen == 'room_requests':
            from .menu_view import draw_room_requests
            draw_room_requests(self.renderer,self.view,self.state)
        elif screen == "settings":
            live = self.view or {}
            self.state["can_surrender"] = bool(self.local_sides()) and live.get("phase") == "battle" and not live.get("result")
            self.renderer.settings(self.state)
        elif screen == "slot_keys":
            self.renderer.slot_keys(self.state)
        elif screen == 'action_keys':
            self.renderer.action_keys(self.state)
        elif screen == 'profile':
            self.renderer.profile(self.state)
        elif screen == 'draft_reference':
            if self.state.get('advice_revision')!=self.view.get('revision'):
                self.state.update(draft_advice=self.draft_advice(self.state.get('advice_side','plant'),self.state.get('advice_seat')),advice_revision=self.view.get('revision'))
            self.renderer.draft_reference(self.view,self.state)
        elif screen == "performance":
            self.renderer.performance(self.state)
        elif screen == "touch_layout":
            self.renderer.start("按键布局", "拖动调整位置，点选后调整大小；改动自动保存并立即生效")
            self.touch.draw_editor()
            self.renderer.footer(self.state)
        elif screen == "almanac":
            self.state["reference_night"]=(self.view or {}).get("map",{}).get("environment",{}).get("night",False)
            self.state["reference_decks"]=(self.view or {}).get("decks",{})
            self.renderer.almanac(self.state)
        elif not self.view:
            self.renderer.start("联机房间", "连接与版本校验中")
            self.renderer.button("取消连接", (30, 130, 200, 44), ("leave",))
            self.renderer.footer(self.state)
        elif self.view.get("phase") == "config" and is_scripted(self.view):
            self.draw_coop_room(self.renderer, self.view)
        elif self.view.get("phase") == "config":
            self.renderer.map_select(self.view, self.state)
        elif self.view.get("phase") in ("banning", "picking"):
            self.renderer.bp(self.view, self.state)
        elif self.view.get("phase") == "result" and is_scripted(self.view):
            self.draw_pve_result(self.renderer, self.view)
        elif self.view.get("phase") == "result":
            self.renderer.result(self.view, self.state)
        else:
            self.renderer.battle(self.presentation.sample(self.view) if self.mode == "guest" or self.state.get('pressure_interpolation') else self.view, self.state)
            if self.tutorial is not None and screen == "room":
                self.tutorial.draw(self.renderer)
            if self.view.get("phase") == "loading":
                self.renderer.text("正在同步双方战场 · 准备完成后开始计时", (28, 60), (250, 210, 89), 16)
        if self.view and not outro_drawn and self.renderer.controls is not None:
            from .team_chat import chat_available, draw as draw_team_chat
            if chat_available(self.view, self.state) and not self.view.get("audit_error"):
                draw_team_chat(self.renderer, self.view, self.state)
        if self.view.get("audit_error") and screen == "room":
            self.renderer.audit_error()
        if self.state.get("confirm_leave"):
            self.renderer.confirm_leave()
        focus = self.state.get("keyboard_focus")
        if isinstance(focus, int) and 0 <= focus < len(self.renderer.controls):
            rect = self.renderer.controls[focus][0]
            self.pg.draw.rect(self.renderer.screen, (250, 210, 89), rect.inflate(4, 4), 2, border_radius=7)
        capture=self.pointer_capture
        flash=self.state.get("button_feedback")
        if self.touch.active:
            hover = self.touch.hover_pos()
            feedback_pos = hover if hover is not None else (-1., -1.)
        else:
            feedback_pos = self.logical_pos(self.mouse_pos())
        self.renderer.pointer_feedback(feedback_pos,
            pressed=capture[1] if capture else None,
            flashed=flash[0] if flash and time.monotonic()<flash[1] else None)
        if self.touch.active:
            self.touch.draw()
        if prof:prof.mark('render')
        if self.renderer.screen is not self.surface:
            from .display_pipeline import scale_frame
            scale_frame(self)
        if prof:prof.mark('screen_scale_blit')
        self.present()
        if prof:prof.inputs.presented()
        if prof:prof.mark('present')
        self.frames += 1
        if hasattr(self, "smoke"):
            self.smoke.setdefault("rendered_phases", [])
            if self.view.get("phase") not in self.smoke["rendered_phases"]:
                self.smoke["rendered_phases"].append(self.view.get("phase"))
        if self.view.get("phase") == "loading" and self.view.get("map") and self.view.get("battle") and not self.state.get("map_sync_error"):
            key = (self.view.get("loading_id"), self.view.get("terrain_hash"))
            if self.loaded_ack != key:
                self.loaded_ack = key
                # Acknowledge only after assets/map rendered and display flipped.
                for side in self.local_sides():
                    self.command({"type": "loaded", "terrain_hash": self.view.get("terrain_hash"),
                                  "loading_id": self.view.get("loading_id")}, side)

    def _sync_text_input(self):
        """Android shows the soft keyboard only while a text box has focus.
        On the desktop the IME's candidate window is placed at the box."""
        if not self.android:
            focus = self.state.get("focus")
            if focus and focus != getattr(self, "_ime_rect_focus", None):
                rect = next((rect for rect, act in self.renderer.controls if act == ("focus", focus)), None)
                if rect is not None and self.scale_x and self.scale_y:
                    try:
                        self.pg.key.set_text_input_rect(self.pg.Rect(
                            rect.x / self.scale_x, rect.y / self.scale_y,
                            rect.w / self.scale_x, rect.h / self.scale_y))
                        self._ime_rect_focus = focus
                    except (self.pg.error, AttributeError):
                        pass
            elif not focus:
                self._ime_rect_focus = None
            return
        want = bool(self.state.get("focus"))
        if want == self._text_input_active:
            return
        self._text_input_active = want
        try:
            if want:
                rect = next((rect for rect, act in self.renderer.controls
                             if act == ("focus", self.state["focus"])), None)
                if rect is not None and self.scale_x and self.scale_y:
                    self.pg.key.set_text_input_rect(self.pg.Rect(
                        rect.x / self.scale_x, rect.y / self.scale_y,
                        rect.w / self.scale_x, rect.h / self.scale_y))
                self.pg.key.start_text_input()
            else:
                self.pg.key.stop_text_input()
        except (self.pg.error, AttributeError):
            pass

    def step(self, dt, present=True):
        from .performance import maybe_record_crowd
        maybe_record_crowd(self)
        prof=self.profiler
        if prof:prof.begin(dt)
        if getattr(self, "native_entry", None) and self.state.get("screen") == "home":
            # Opened from the original mode list: leaving returns there.
            self.running = False
        self.handle_events()
        self.update_replay(dt)
        self.update_spectator_camera(dt)
        self.poll_network(dt, publish=False)
        self.touch.update(dt)
        self._sync_text_input()
        self.move_inputs(dt)
        if prof:prof.mark('input_network')
        if self.room:
            if self.ai_room is not None:
                self.ai_room.tick(min(1., dt))
            if self.tutorial is not None:
                self.tutorial.tick(min(1., dt))
            if prof:prof.mark('ai_policy_tutorial')
            previous_members = set(self.room.members)
            self.room.update(min(1., dt))
            if prof:prof.mark('room_update')
            self.refresh()
            if prof:prof.mark('refresh')
            if self.mode == 'host' and self.transport:
                for peer in previous_members - set(self.room.members):
                    self.transport.release_peer(peer)
        self.publish_network(dt)
        if getattr(self,'game_audio',None):
            audio_view=self.view
            if self.state.get('screen')=='replay' and self.playback:
                p=self.playback
                audio_view=dict(phase='battle',battle=p.battle.snapshot(),map=p.battle.map,
                                paused=not p.playing or p.target is not None,
                                match_id='replay:'+str(id(p)))
                seeking=p.target is not None
                if seeking!=getattr(self,'_audio_seeking',False):self.game_audio.reset()
                self._audio_seeking=seeking
            self.game_audio.update(audio_view,self.state)
        if prof:prof.mark('network_publish')
        if self.state.get("leave_pending"):
            self.state["leave_elapsed"] += dt
            settled = self.view.get("phase") == "result"
            if self.mode == "host" and self.room:
                peers = {peer for peer in self.room.members if peer != "host" and self.room.connected.get(peer)}
                settled = settled and peers <= self.result_seen_peers
            if settled:
                self.state["leave_settled_elapsed"] += dt
            if self.state["leave_settled_elapsed"] >= .25 or self.state["leave_elapsed"] >= 4.:
                confirmed = settled
                self.close_room(graceful=True)
                self.message("已确认终局并离开房间。" if confirmed else "未收到完整结算确认，已离开；对方按最后权威状态处理。")
        if prof:prof.mark('other')
        self.preview()
        self.update_link_notice(dt)
        if prof:prof.mark('preview')
        if present is None:present=self.presentation_budget.due(self)
        if present:
            render_started=time.perf_counter()
            self.render()
            self.presentation_budget.observe(time.perf_counter()-render_started)
        if prof:
            prof.mark('after_present');prof.end()


def _smoke_driver(app, frame, evidence=None):
    """Explicit native-engine EXE smoke; production gameplay never calls it."""
    from .smoke import driver
    return driver(app, frame, evidence)


def run(g=None, auto_test=None, raw_api=None, entry=None):
    """Run a modal independent scene and return to the caller's native menu.

    auto_test is only an explicit test harness: integer frame budget or a
    callable receiving (application, frame). It never enables gameplay cheats.
    """
    if isinstance(auto_test, dict) and "event_get" in auto_test and raw_api is None:
        raw_api, auto_test = auto_test, None
    pg, dll_handles = _pygame()
    was_initialized = pg.get_init()
    if not was_initialized:
        pg.init()
    if not pg.font.get_init():
        pg.font.init()
    old_caption = pg.display.get_caption()
    screen = pg.display.get_surface()
    if screen is None:
        # On Android the SDL window is always the device screen; (0, 0) asks
        # SDL for that size instead of a desktop window it cannot provide.
        screen = pg.display.set_mode((0, 0) if _is_android() else (1280, 800))
    old_display_size, old_display_flags = screen.get_size(), screen.get_flags()
    android_guard = None
    android_display_switched = False
    if _is_android():
        from modkit.android import original_game, touch_hotfix
        android_guard = touch_hotfix.GUARD['on']
        touch_hotfix.install(pg)
        full_surface = original_game.pvp_display(pg)
        if full_surface is not None:
            screen = full_surface
            android_display_switched = True
    bridge = NativeBridge(g) if g and callable(g.get("生成地图")) else NativeBridge.from_marshaled(_workspace() / "reverse_engineered/raw/pvzrouge.pyc")
    # Use the same verified resource root as combat and audio. Android's host
    # executable lives in /system/bin, not beside the extracted APK assets.
    folder = bridge.combat_payload()[2]
    app = Application(pg, screen, bridge, raw_api, folder)
    pg.display.set_caption("植物大战僵尸 · 横版对战 · " + RULES["build"])
    from .team_chat import enable_ime_ui
    enable_ime_ui()
    if app.state["fullscreen"] and not auto_test:
        app.apply_display()
    # PvP65: the newcomer guide opens at every launch until the player renames
    # themselves; saving a name other than the default ends it for good.
    from .tutorial import needs_newbie
    if entry:
        app.enter_native(entry)
    elif needs_newbie(app) and not auto_test:
        app.state.update(screen="newbie", return_screen="home", help_page=0)
    clock = pg.time.Clock()
    frame = 0
    auto_evidence = auto_test if isinstance(auto_test, str) and auto_test not in ("1", "smoke") else None
    try:
        if not app.android:
            # On Android a global text-input session pops the soft keyboard at
            # launch; _sync_text_input toggles it with text box focus instead.
            pg.key.start_text_input()
        from . import perf_hooks
        while app.running:
            # PvP71: a platform provider (Android) may present at 30 fps while slowed.
            dt = min(.25, clock.tick(perf_hooks.frame_rate(60)) / 1000.)
            if isinstance(auto_test, str):
                # The scripted smoke checks states a set number of frames after
                # each input. On a slow device (arm64 under translation) a 0.25 s
                # frame let the Dave land between two jump presses, so the third
                # press began a new first jump. The smoke advances fixed 1/30 s
                # steps instead; real play keeps the wall-clock step.
                dt = min(dt, 1. / 30.)
                _smoke_driver(app, frame, auto_evidence)
            elif callable(auto_test):
                auto_test(app, frame)
            elif isinstance(auto_test, int) and frame >= auto_test:
                break
            work_started = time.perf_counter()
            app.step(dt,present=None)
            perf_hooks.frame(app, time.perf_counter() - work_started)
            frame += 1
        report = {"frames": app.frames, "phase": app.view.get("phase"),
                  "received_snapshots": app.received_snapshots, "mode": app.mode,
                  "smoke": getattr(app, "smoke", None), "native_generator": bridge.generator_revision}
        if isinstance(auto_test, str):
            required = {"home", "config", "banning", "picking", "battle", "result"}
            if not required <= set(app.smoke["phases"]):
                raise AssertionError("Native smoke did not visit every required screen")
            if not (app.smoke.get("rematched") and app.smoke.get("deployed")):
                raise AssertionError("Native smoke did not deploy and rematch")
            if len(app.smoke.get("draft_history",[]))!=30:     # PvP66 ban order: 8+8 bans, 14 picks
                raise AssertionError("Native smoke did not complete the 30-step draft")
            if not all(len(deck)==7 for deck in app.smoke["final_decks"].values()):
                raise AssertionError("Native smoke did not fill both seven-slot decks")
            if "secret:疾行" not in app.smoke["final_decks"]["plant"]:
                raise AssertionError("Native smoke did not select its required secret")
            if not {"opening_ban","opening_pick","second_ban","final_pick","complete"} <= set(app.smoke["draft_stages"]):
                raise AssertionError("Native smoke did not visit every draft stage")
            report["passed"] = True
        if auto_evidence:
            Path(auto_evidence).parent.mkdir(parents=True, exist_ok=True)
            Path(auto_evidence).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    except Exception:
        import traceback
        try:
            path = app.settings_path.parent / ("crash-%d.txt" % time.time())
            path.write_text("build=%s mode=%s screen=%s phase=%s\n%s" % (
                RULES["build"], app.mode, app.state.get("screen"),
                app.view.get("phase"), traceback.format_exc()), encoding="utf-8")
        except OSError:
            pass
        raise
    finally:
        app.close()
        pg.key.stop_text_input()
        if not was_initialized:
            pg.quit()
        else:
            try:
                current = pg.display.get_surface()
                if current and (android_display_switched or current.get_size() != old_display_size or bool(current.get_flags() & pg.FULLSCREEN) != bool(old_display_flags & pg.FULLSCREEN)):
                    pg.display.set_mode(old_display_size, old_display_flags & (pg.FULLSCREEN | pg.NOFRAME | pg.RESIZABLE))
                pg.display.set_caption(*old_caption)
            except Exception:
                pass
        if android_guard is not None:
            touch_hotfix.GUARD['on'] = android_guard
        # Keep DLL directory handles alive for the entire scene.
        for handle in dll_handles:
            close = getattr(handle, "close", None)
            if close:
                close()


if __name__ == "__main__":
    run()
