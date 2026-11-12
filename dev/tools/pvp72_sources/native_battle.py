"""PvP room/economy adapter around the actual original combat engine.

The inherited methods are protocol validation, audit records and PvP economy
utilities only. No synthetic unit update, projectile update or body integrator
is called. Original dictionaries are private authoritative state; public unit
objects are projections for HUD, selection and network snapshots.
"""
import copy
from . import cppcore as _cppcore
copy = _cppcore.copy_module()
import math
import sys
import time as _time
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

_perf_counter = _time.perf_counter
# Exponential smoothing for the measured native cost, and the share of one core
# above which the wave director paces (never drops) pending spawns.
NATIVE_COST_SMOOTHING = .08
# 68004 co-op: an AI plant seat is paid 25 sun every 8 s; the payment doubles
# every 40 s of battle time, up to 200 per payment.
AI_SUBSIDY_INTERVAL = 8.
AI_SUBSIDY_SUN = 25
AI_SUBSIDY_DOUBLING = 40.
AI_SUBSIDY_MAX = 200


def ai_subsidy_amount(seconds):
    return min(AI_SUBSIDY_MAX, AI_SUBSIDY_SUN * 2 ** int(seconds // AI_SUBSIDY_DOUBLING))


from .simulation import Battle as RoomContract, finite, wrap_delta
from .catalog import CARDS, RULES, actual_card, resolve_card, native_secret_names
from .native_runtime import NativeRuntime, load_patch
from .native_animation import NamespaceGraphics, draw_dave
from .native_assets import load_original_assets
from .native_patch import NativeCombatPatch
from .native_targets import NativeTargets, _COMBAT_HERO_KEYS
from .native_gate import inject_iteration_gate, replace_predicate
from .native_gravebuster import NativeGravebuster
from .native_periodic_targets import NativePeriodicTargets
from .expansion_catalog import (PETRIFIED_TORCH, PETRIFIED_TORCH_RANGE, PETRIFIED_TORCH_REWARD,
                                PETRIFIED_TORCH_BRAIN_CAP, PETRIFIED_TORCH_SLEEP_SECONDS,
                                PETRIFIED_TORCH_DEATHMATCH_SLEEP_SECONDS)
from .native_expansion import (CARRIER_BODY_MARK, IMP_ARMOR, IMP_ARMOR_HP,
                               IMP_BLACK_ARMOR, armor_logic, black_armor_variant,
                               carried_imp_armored, strip_carried_imp_armor)
from .pvp56_plants_catalog import AIR_PLANTS
from .pvp58_catalog import (MASOCHIST_SECRET, MASOCHIST_COOLDOWN, MASOCHIST_EARLY_SECONDS,
                            MASOCHIST_EARLY_SUN, MASOCHIST_LATE_SUN,
                            MASOCHIST_RISE_FRAMES, NATIVE_RISE_FRAMES)
from .native_placement import NativePlacementRules, make_native_placement_state, validate_native_placement, validate_thief_placement
from .maps import _cell
from .world_view import sun_scale
from .pvp64_catalog import SLIMES as _PVP64_SLIMES, GRENADIER as _PVP64_GRENADIER
NO_BUCKET = _PVP64_SLIMES + (_PVP64_GRENADIER,)
from .pvp64_catalog import PRIMAL_ARM_SECONDS, STURDY_SECRET, STURDY_REDUCTION, STURDY_COOLDOWN_CUT
from .balance import (MINE_EMERGENCE_SECONDS, SPIKE_SECRET_STEP, rest_factor, deathmatch_blocked,
                      hero_hp, balloon_hp,
                      SPIKE_SECRET_MIN_COST, GOLD_MAGNET_BUCKET_HP, initial_cooldown,
                      HARDENING_MIN_BASE_HP, HARDENING_HP_FACTOR, HEALTH,
                      deathmatch_factor, deployment_cooldown)

_GATES = {}
BEDROCK = "基岩"
PETRIFIED_TORCH_KEY = "zombie:" + PETRIFIED_TORCH


def tick_asleep(torch, tick):
    """True while a petrified torch is in its brain-cap sleep."""
    return tick < torch.get("_pvp_torch_sleep_until", 0)


def _native_match_secrets(secrets):
    """Exclude legacy hardening; PvP applies its explicit percentage rule."""
    return [name for name in native_secret_names(secrets) if name != "硬化"]


def _gated_regions(engine):
    identity = id(engine.root)
    if identity not in _GATES:
        regions = dict(engine.regions)
        regions['plants']=replace_predicate(regions['plants'],128448,128456,'_pvp_star_target',
            [('LOAD_NAME','y'),('LOAD_NAME','同横尸'),('COMPARE_OP','in')])
        regions['entities']=replace_predicate(regions['entities'],106532,106546,'_pvp_entity_visible',
            [('LOAD_CONST','穿墙'),('LOAD_NAME','实体'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),('COMPARE_OP','not in')])
        regions['entities']=inject_iteration_gate(regions['entities'],107096,'_pvp_projectile_impact')
        from .native_bytecode import instruction_window
        deletion=[(i.opname,i.argval) for i in instruction_window(regions['entities'],108794,108802) if i.opname!='EXTENDED_ARG']
        if deletion!=[('LOAD_NAME','实体'),('LOAD_NAME','l'),('DELETE_SUBSCR',None)]:raise ValueError('Native projectile deletion boundary changed')
        # After native movement, before target collisions: silently expire an
        # over-range shot through the original reverse-loop deletion boundary.
        regions['entities']=inject_iteration_gate(regions['entities'],99030,'_pvp_flight_expired',108794)
        regions['zombies']=replace_predicate(regions['zombies'],77072,77090,'_pvp_rally_speed',[
            ('LOAD_NAME','c'),('LOAD_NAME','僵尸'),('LOAD_NAME','l'),('BINARY_SUBSCR',None),
            ('LOAD_CONST','移速'),('BINARY_SUBSCR',None),('CALL_FUNCTION',1)])
        # Keep the original blocked-unit support trigger, but enqueue the
        # trusted ladder through the director after native unit iteration.
        # Restore only the skipped condition's first operand for the gate's
        # validated trampoline; its callback always skips the campaign spawn.
        data=bytearray(regions['zombies'].co_code)
        data[76374:76380]=engine.root.co_code[76374:76380]
        regions['zombies']=inject_iteration_gate(regions['zombies'].replace(co_code=bytes(data)),
            76374,'_pvp_ladder_support_request',76786)
        for region,entry,callback in (("plants",121112,"_pvp_plant_gate"),
                                      ("zombies",68444,"_pvp_zombie_gate"),
                                      ("entities",98650,"_pvp_entity_gate")):
            regions[region] = inject_iteration_gate(regions[region],entry,callback)
        _GATES[identity] = (engine.root,regions)
    return _GATES[identity][1]


# Engine-only animation state stored in a terrain cell (flower pot roots).
TERRAIN_ANIMATION_KEY = "根动画"
from .pvp59_graves import drowsy as grave_drowsy, drowsy_level as grave_drowsy_level
from .pvp61_ranked import ranked as ranked_rules, ring_error, BLOOM, BLOOM_COLLECT_LOCK
from .pvp64_content import BELT_STRIDE
from .teams import DUEL, DUO, team_of, REVIVE_SECONDS, REVIVE_HP_FRACTION, TOUCH_RANGE_X, TOUCH_RANGE_Y


_HERO_MISSING = object()


class NativeBattle(RoomContract):
    def __init__(self, terrain, decks, rules=None, seed=1, bans=(), bridge=None, pygame=None, mode=DUEL, director=None):
        if bridge is None:raise ValueError("Original combat source is required")
        super().__init__(terrain, decks, rules, seed, bans, mode)
        if pygame is None:
            from .app import _pygame
            pygame, self._dll_handles = _pygame()
        self.pg = pygame
        # Optional PhaseProfiler (native_multiworker); None costs one branch.
        self.profiler = None
        # Share of one core the original regions need (None until measured).
        self.native_cost_ratio = None
        if not pygame.font.get_init():pygame.font.init()
        if pygame.display.get_surface() is None:
            pygame.display.init()
            pygame.display.set_mode((1,1),pygame.HIDDEN)
        root, source, assets = bridge.combat_payload()
        self.native_secrets = _native_match_secrets(self.team_secrets["plant"])
        self.engine = NativeRuntime(root, self.map, seed, self.native_secrets, pygame)
        self.g = self.engine.g
        self.g['_pvp_rally_speed']=self._rally_speed
        self.g["地刺阳光"]=CARDS["plant:地刺"]["cost"]
        self.patch_namespace = load_patch(source)
        load_original_assets(self.g, root, assets, self.tile, self.patch_namespace)
        from .expansion_assets import install as install_expansion_assets
        install_expansion_assets(self.g,pygame)
        from .content_assets import install as install_content_assets
        install_content_assets(self.g,pygame)
        # Last, so every atlas - original, expansion and content - is already in
        # place: the units this rescales do not all come from the same pack, and
        # a pass that ran before the content atlas landed would silently skip the
        # ones it builds.
        from .native_scale import install as install_native_scale
        install_native_scale(self.g, pygame)
        self.graphics = NamespaceGraphics(pygame, self.tile)
        from .performance import enabled
        self.capture_demand=enabled('CAPTURE_DEMAND')
        self.capture_frames=self.capture_deferred=0
        self.recorder = self.graphics.install(self.g, root)
        self.patch = NativeCombatPatch(self.g, self.patch_namespace)
        # This namespace belongs only to this PvP match.  The shared source
        # remains at its original value for every non-PvP mode.
        self.patch.ns["__pvz_sb_GOLD_MAGNET_BUCKET_HP"] = GOLD_MAGNET_BUCKET_HP
        self.avatars = {}
        self._jump_presses = {side: 0 for side in self.players}
        self._press_reported = {side: False for side in self.players}
        self._native_phase = 0
        self._day_brain_native_tick = 0
        self._native_objects = {}
        self._grave_progress = {}
        self._sun_motion = {}
        self._frame = self.recorder.snapshot()
        for side, player in self.players.items():
            # PvP health changes the pool, never the original damage units.
            player["hp"] = player["max_hp"] = hero_hp(self.rules, side, player["deck"])
            team = team_of(side)
            self.avatars[side] = self.engine.physics.make_state(player["x"], player["y"],
                "我是僵尸" if team == "zombie" else "正常模式", player["hp"],
                _native_match_secrets(player["secrets"]))
            self.avatars[side].update(玩家皮肤="僵尸戴夫" if team=="zombie" else "疯狂戴夫",
                                      玩家受伤=0,玩家恢复=0,xx=0,yy=0,
                                      _pvp_owner=team,_pvp_id="hero:"+side,
                                      _pvp_max_hp=player["max_hp"],_pvp_last_damage=0.,
                                      _pvp_previous_hp=player["hp"],_pvp_regen_progress=0.,
                                      _pvp_balloon_hp=balloon_hp(team, player["deck"]))
            if self.mode != DUEL:self.avatars[side]["_pvp_seat"] = side
        # Seat -> its own avatar, unaffected by the temporary team aliasing
        # that lets the original single-player regions serve a second Dave.
        self.hero_states = dict(self.avatars)
        # Zombie secrets first: protection, content and the spawn path read it.
        from .zombie_secrets import ZombieSecrets
        self.zsecrets=ZombieSecrets(self)
        from .native_protection import NativeProtection
        self.protection = NativeProtection(self, source)
        self.targets = NativeTargets(self.g,self.avatars,self._hero_lock,self._hero_damaged)
        from .native_audio import NativeAudio
        self.audio=NativeAudio(self)
        self.recorder.entity_source = self.targets.source
        self.patch.bind_targets(self.targets)
        self._install_star_damage()
        self.targets.hero_proxy("zombie")
        self.g["_pvp_target_extras"] = lambda: [obj for obj in self._native_objects.values()
            if (obj.get("_pvp_grave") or obj.get('_pvp_orphan_barrel')) and obj.get("血量",0)>0]+self.zombie_hero_proxies()
        self.engine.regions = _gated_regions(self.engine)
        self.g["_pvp_plant_gate"] = self.g["_pvp_entity_gate"] = self._tracking_gate
        self.periodic_targets = NativePeriodicTargets(self)
        self.g['_pvp_star_target']=self._star_target
        from .native_projectiles import NativeProjectiles
        self.projectile_rules = NativeProjectiles(self)
        self.g['_pvp_projectile_impact'] = self.projectile_rules.impact
        self.g['_pvp_entity_visible']=self._engine_draws_entity
        # Every native block removal - explosions, crushing, fire - goes
        # through this one function. Bedrock simply never leaves.
        destroy_block=self.g["摧毁方块"]
        def keep_bedrock(y,x,_destroy=destroy_block):
            rows=self.g["ditu"]
            if 0<=y<len(rows) and rows[y][x%len(rows[y])].get("方块")==BEDROCK:return None
            return _destroy(y,x)
        self.g["摧毁方块"]=keep_bedrock
        self.gravebusters = NativeGravebuster(self.g,self._native_objects.get,on_event=self._emit)
        # Zero unless the match itself is handing out a unit as part of another
        # card's effect, which is the one kind of spawn a ban must not touch.
        self._spawn_ban_exempt = 0
        from .scripted_spawn_budget import ScriptedSpawnBudget
        self.scripted_spawn_budget = ScriptedSpawnBudget(self)
        self._install_admission()
        self._install_grave_deaths()
        self._install_petrified_torch()
        from .native_expansion import NativeExpansion
        self.expansion=NativeExpansion(self)
        self.g['_pvp_zombie_gate']=self.expansion.zombie_gate
        self._install_imp_armor_hooks()
        from .native_status import NativeStatus
        from .native_content import NativeContent
        self.status=NativeStatus(self)
        self.content=NativeContent(self)
        self._native_sun_seats = {}
        self._sun_source_start = None
        if len(self.team_seats('plant')) > 1:
            plant_gate = self.g['_pvp_plant_gate']
            def owned_plant_gate():
                self._finish_sun_source()
                start = len(self.g['阳光球'])
                plant_gate()
                source = self.targets.source()
                seat = source.get('_pvp_seat', 'plant') if isinstance(source, dict) else 'plant'
                self._sun_source_start = (start, seat)
            self.g['_pvp_plant_gate'] = owned_plant_gate
        from .pvp59_graves import GraveIdle
        self.grave_idle=GraveIdle(self)
        self.protection.install_basketball()
        self._native_zombie_gate=self.g['_pvp_zombie_gate']
        _install_native_zgate(self)
        self.g['_pvp_zombie_gate']=self._rally_zombie_gate
        # PvP64 sweet potato: undo the previous zombie's taunt (path swap and
        # hidden plant markers) before the rally gate selects this zombie's.
        # The restore is a no-op unless a taunt is actually up; skipping the
        # call also skips its fresh `hidden_cells = []` allocation, 30 times a
        # tick in a full wave.
        rally_gate=self.g['_pvp_zombie_gate']
        pvp64=self.content.pvp64
        def taunt_gate(_rally=rally_gate,_p64=pvp64,_restore=pvp64.restore_taunt):
            if _p64.saved_tracking is not None or _p64.hidden_cells:_restore()
            _rally()
        self.g['_pvp_zombie_gate']=taunt_gate
        self.g['_pvp_ladder_support_request']=self._ladder_support_request
        from .native_imitater import NativeImitater
        self.imitater=NativeImitater(self)
        from .native_plant_zombies import NativePlantZombies
        self.plant_zombies=NativePlantZombies(self)
        from .pvp66_secrets import PlantSecrets66
        self.secrets66=PlantSecrets66(self)
        self.zsecrets.install_late()
        self.scripted_spawn_budget.install_native_guards()
        self.cpp_region_policy=_cppcore.configure_final_regions(self.engine.regions)
        # Multi-worker coordinator. PVP_SIM_FASTPATH (default on) installs the
        # exact candidate scans (native_candidates); PVP_SIM_WORKERS>=2 lets
        # their broad-phase run on the job system's workers. FASTPATH=0 with
        # workers=0 keeps every original scan as is. The world, RNG and
        # every mutation stay on this thread.
        from .native_multiworker import JobSystem, configured_workers, fastpath_enabled
        self.sim_workers = configured_workers()
        self.sim_fastpath = fastpath_enabled()
        self.jobs = JobSystem(self.sim_workers)
        self.candidate_scans = []
        if self.sim_fastpath or self.sim_workers >= 1:
            from . import native_candidates
            self.candidate_scans = native_candidates.install(self, self.jobs)
        for side, player in self.players.items():
            player["cooldowns"] = {key: initial_cooldown(self._card(side,key)["cooldown"])
                for key in player["deck"] if CARDS[key]["category"] != "secret"}
            # Full length of the cooldown now running, for the card mask.
            player["cooldown_spans"] = dict(player["cooldowns"])
        self.targets.damage_factor = self._hero_damage_factor
        if self.zsecrets.has("最后攻势"):
            self.targets.last_stand = self.zsecrets.hero_amount
        if self.zsecrets.has("僵王出品"):
            self.targets.unshielded = self.zsecrets.shield_first
        if self.zsecrets.has("二手"):
            self.targets.armor_break = self.zsecrets.on_armor_break
        self._acting_seat = None
        self._team_init(director)
        self._sync_public()
        self._install_native_rotation()
        # PvP62: sky sun frequency follows the map size; the first sun falls
        # after half an interval.
        from .balance import sky_interval
        tiles = self.map["tiles"]
        self.sky_interval = sky_interval(self.rules, len(tiles[0]) if tiles else 0, len(tiles))
        from .pvp66_secrets import SECRET_NOON
        if any(SECRET_NOON in self.players[seat]["secrets"] for seat in self.team_seats("plant")):
            self.sky_interval /= 2.     # 正午: halved, the first drop included
        self.sky_progress = self.sky_interval / 2.
        # Loading is done: freeze its survivors out of full GC passes.
        from . import gc_policy
        gc_policy.apply(id(self))
        # Test runs only (PVP_HERO_GUARD): one Dave's state never reaches another.
        from . import hero_guard
        hero_guard.install(self)

    def _install_native_rotation(self):
        """C++ twin of the 1.5.0.1 rotated-camera-display armour wrapper."""
        from . import cppcore
        wrapper = self.g.get("旋转摄像显示")
        predicate = self.patch.ns.get("__pvz_sb_should_skip_native_plant_zombie_armor_draw")
        code = getattr(wrapper, "__code__", None)
        if code is None or predicate is None or getattr(wrapper, "__closure__", None) is None:
            return
        native = cppcore.native_for(("rot_camera_wrapper", code),
                                    ("armor_skip_predicate", predicate.__code__))
        if native is not None and hasattr(native, "RotCameraDisplay"):
            self.g["旋转摄像显示"] = native.RotCameraDisplay(wrapper)

    def _install_grave_deaths(self):
        ns = self.patch.ns
        def remnant(game, source):
            # PvP73: no more native remnant grave. The zombie releases a bone on
            # the spot (the 死神僵尸 bone path); a legal landing cell becomes a
            # bone grave, day or night.
            if source.get("僵尸")!="墓碑吞噬者僵尸":return False
            if not self.content.pvp70.drop_bone(source):return False
            ns["__pvz_sb_gravebuster_zombie_grave_count"] += 1
            return True
        def charmed_plant(game, source):
            row,col,cell = ns["__pvz_sb_gravebuster_zombie_cell"](game,source)
            if cell is None or "植物" in cell:return False
            target = next((obj for obj in self._native_objects.values() if obj.get("_pvp_grave") and
                obj["血量"]>0 and obj.get("_pvp_owner")=="zombie" and
                int(obj["位置"][0]//self.tile)==col and int(round(obj["位置"][1]/self.tile))-1==row),None)
            if target is None:return False
            created = self.engine.spawn_plant("墓碑吞噬者",row,col,source.get("方向",1))
            if not created:return False
            self._register(created[0],self._card("plant","plant:墓碑吞噬者"),"plant",True,
                           parent=dict(id=source.get("_pvp_id")))
            self.gravebusters.attach(created[0],target["_pvp_id"])
            ns["__pvz_sb_gravebuster_zombie_plant_count"] += 1
            return True
        ns["__pvz_sb_place_grave_from_gravebuster_zombie"] = remnant
        ns["__pvz_sb_spawn_gravebuster_plant_from_zombie"] = charmed_plant

    def spawn_remnant(self, x, y, source=None):
        """Shared native remnant for gravebuster deaths and co-op nights."""
        card = self._card('zombie','zombie:残骸墓碑（非生产）')
        created = self.engine.spawn_zombie('普通僵尸',x,y,(source or {}).get('方向',1),
                                           factory=self._grave_native_factory)
        if not created:return None
        native = created[0]
        native.update(出场=500,血量=card['hp'],位置=[x,y,0.,0.],_pvp_grave=True)
        self._register(native,card,'zombie',True,parent=dict(id=source.get('_pvp_id')) if source else None)
        return native

    def _install_petrified_torch(self):
        """石化火炬 ignites peas the way the original torchwood does.

        A zombie pea already runs through the patch's own torch check, so extend
        that one function instead of duplicating its 蓝火 and ignite semantics.
        The plant-pea half is a pre-pass in _step_original, sitting right before
        the entity update so a pea converted on entry already lands its fire hit
        on the same 250 Hz tick.
        """
        ns = self.patch.ns
        self._petrified_fire_key = ns["__pvz_sb_K_ZOMBIE_PEA_FIRE"]
        self._petrified_pea_xy = ns["__pvz_sb_zombie_pea_xy"]
        from .torch_rules import TorchRules
        self.torches=TorchRules(self)

    def _petrified_torch_points(self):
        """World point of every living, awake 石化火炬 grave."""
        return [(x, y) for x, y, unused in self._petrified_torches()]

    def _petrified_torches(self):
        """(x, y, grave) of every living, awake 石化火炬 grave.

        Read from the authoritative native roster rather than the tracked
        objects: graves are held in that list even while the mobile-zombie
        region has them lifted out, and a dead one must stop igniting. A
        sleeping torch (it paid its brain cap) neither ignites nor pays.
        """
        points = []
        tick = self.engine.native_tick
        for obj in self.g["僵尸"]:
            if not isinstance(obj, dict) or not obj.get("_pvp_grave"):
                continue
            if obj.get("血量", 0) <= 0 or obj.get("_pvp_card") != PETRIFIED_TORCH_KEY:
                continue
            if tick < obj.get("_pvp_torch_sleep_until", 0):
                continue
            position = obj.get("位置")
            if isinstance(position, list) and len(position) >= 2:
                points.append((position[0], position[1], obj))
        return points

    def _petrified_torch_covers(self, point):
        """The first awake petrified torch whose 2.5-tile box holds the point."""
        if not point:
            return None
        px, py = point
        reach = PETRIFIED_TORCH_RANGE * self.tile * self.zsecrets.torch_range_scale()
        for tx, ty, torch in self._petrified_torches():
            if abs(wrap_delta(px, tx, self.width)) <= reach and abs(py - ty) <= reach:
                return torch
        return None

    def _petrified_torch_ignite_plant_peas(self):
        """Shared per-stump thaw/ignition before native projectile collisions."""
        self.torches.tick()

    def _petrified_torch_reward(self, point, torch):
        """One conversion is one activation: pay the torch's owner at once.

        Each torch counts the brain it paid; at the cap it sleeps for 36 s
        (24 s in deathmatch) and starts counting again when it wakes.
        """
        x, y = point if point else (self.players["zombie"]["x"], self.players["zombie"]["y"])
        self.resource("zombie", PETRIFIED_TORCH_REWARD, x, y, "petrified_torch")
        paid = torch.get("_pvp_torch_brain", 0) + PETRIFIED_TORCH_REWARD
        if paid >= PETRIFIED_TORCH_BRAIN_CAP:
            seconds = PETRIFIED_TORCH_DEATHMATCH_SLEEP_SECONDS if self.deathmatch else PETRIFIED_TORCH_SLEEP_SECONDS
            seconds *= self.zsecrets.torch_sleep_scale()     # 暴怒
            torch["_pvp_torch_sleep_until"] = self.engine.native_tick + int(round(seconds * 250))
            paid = 0
        torch["_pvp_torch_brain"] = paid

    def _install_admission(self):
        plant_factory,zombie_factory = self.g["种植植物"],self.g["新增僵尸"]
        # Graves use the native record shape, not the ordinary zombie card.
        # Keep the original factory before card-ban admission is installed.
        self._grave_native_factory = zombie_factory
        self._plant_native_factory = plant_factory
        def plant(row,col,name,facing):
            key = "plant:"+name
            if key in CARDS:
                try:card = resolve_card(key,self.team_secrets["plant"],self.bans)
                except ValueError:return None
                if self.deathmatch and deathmatch_blocked(card):
                    self._emit("spawn_blocked",card=key,reason="deathmatch_producer")
                    return None
            return plant_factory(row,col,name,facing)
        def zombie(name,position,facing):
            key = "zombie:"+name
            roster=self.g['僵尸'];index=self.g.get('l')
            native_call=sys._getframe(1).f_code is self.engine.regions['zombies']
            source=(self.targets.source() if native_call or
                    self.targets.active and self.targets.active.get('phase')=='summon' else None)
            native_throw=(name=='小鬼僵尸' and native_call
                and isinstance(index,int) and 0<=index<len(roster)
                and roster[index].get('僵尸')=='巨人僵尸')
            # Only the original giant's actual throw bypasses card admission.
            # A direct call with a stale giant index must remain banned.
            if key in CARDS and not (self._spawn_ban_exempt or native_throw):
                try:resolve_card(key,self.players["zombie"]["secrets"],self.bans)
                except ValueError:return None
            if not self.scripted_spawn_budget.can_spawn(source=source):
                # Native call sites are guarded before their constructor and
                # post-construction [-1] writes; this is the external factory
                # admission boundary, including NativeRuntime.spawn_zombie.
                if native_call:raise RuntimeError('Unguarded native campaign spawn')
                return None
            roster=self.g["僵尸"]
            before=len(roster)
            created=zombie_factory(name,position,facing)
            if native_throw and len(roster)>before:
                imp=roster[-1];carrier=roster[index]
                self._inherit_carried_imp_armor(imp)
                # Registration is part of the internal hand-out too. Waiting
                # for public adoption would run banned-card admission again.
                self._register(imp,self._unit_card('zombie',key),'zombie',True,
                               parent={'id':carrier.get('_pvp_id')})
            elif native_call and isinstance(source,dict) and len(roster)>before:
                child=roster[-1]
                self._register(child,self._unit_card('zombie',key),'zombie',True,
                               parent={'id':source.get('_pvp_id')})
            if len(roster)>before and isinstance(source,dict):
                self.scripted_spawn_budget.inherit(roster[-1],source)
            return created
        self.g["种植植物"],self.g["新增僵尸"] = plant,zombie

    def _inherit_carried_imp_armor(self,imp):
        """Give a thrown imp the headgear the imp on the back was wearing.

        The original spawns the imp bare, so the headgear a magnet fitted to the
        imp riding the giant would vanish the moment it is thrown.  Only the imps
        own slot is handed over - the giants own headgear stays on the giant -
        and a magnet that already stripped it leaves nothing to inherit, so the
        imp then lands unarmoured, as intended.
        """
        roster=self.g["僵尸"]
        index=self.g.get("l")
        if not isinstance(index,int) or not 0<=index<len(roster):return False
        carrier=roster[index]
        if not isinstance(carrier,dict) or carrier is imp:return False
        if "巨人" not in str(carrier.get("僵尸","")):return False
        if not carried_imp_armored(carrier):return False
        armor=carrier.get(IMP_ARMOR)
        # The slot holds the name the engine knows (铁桶) and the art carries the
        # black alias, which is the split the black regiment itself uses: it is
        # what keeps the piece metal, so a magnet and the thunder stun both still
        # see it once the imp is on its own.
        imp["防具"]=armor_logic(armor)
        imp["防具血量"]=carrier.get(IMP_ARMOR_HP,0)
        variant=black_armor_variant(armor)
        if variant:imp[IMP_BLACK_ARMOR]=variant
        else:imp.pop(IMP_BLACK_ARMOR,None)
        # The imp leaves with its helmet, so the carrier no longer has one to
        # show - a giant that threw its imp is not still carrying an armoured one.
        if carrier.get('_pvp_zs_secondhand', {}).get(IMP_ARMOR):
            imp.setdefault('_pvp_zs_secondhand', {})['防具'] = True
        strip_carried_imp_armor(carrier)
        return True

    def _riding_imp_candidate(self,center,radius_tiles,armed):
        """Nearest carrier whose riding imp is (un)armoured, with its point.

        The patch's own pickers only look at a zombie's head and handheld slots,
        so the imp on the back is invisible to them; this finds it so one
        activation can dress or strip exactly one of the two.
        """
        ns=self.patch.ns
        point_of=ns.get("__pvz_sb_gold_magnet_target_point")
        within=ns.get("__pvz_sb_point_in_square_radius")
        live=ns.get("__pvz_sb_live_zombie")
        if not callable(point_of) or not callable(within):return None
        best=best_dist=None
        for target in list(self.g.get(ns.get("__pvz_sb_K_ZOMBIES","僵尸"),[])):
            if not isinstance(target,dict):continue
            if CARRIER_BODY_MARK not in str(target.get("僵尸","")):continue
            if callable(live) and not live(target):continue
            if carried_imp_armored(target)!=armed:continue
            point=point_of(self.g,target)
            if point is None or not within(self.g,center,point,radius_tiles):continue
            dist=(point[0]-center[0])**2+(point[1]-center[1])**2
            if best_dist is None or dist<best_dist:best,best_dist=(target,point),dist
        return best

    def _install_imp_armor_hooks(self):
        """Treat a giant and the imp riding it as two independent recipients.

        One magnet activation therefore handles one piece of metal: the patch
        picks first among ordinary heads, and only once every head is settled
        does the imp on a back become a candidate - and the other way round when
        absorbing.  The patch's gift and absorb calls are reused verbatim so the
        armour value, HP scaling, magnet effect and sound all stay its own.
        """
        ns=self.patch.ns
        bucket=IMP_ARMOR
        gift=ns.get("__pvz_sb_gift_bucket_to_zombie")
        pick_gift=ns.get("__pvz_sb_pick_gold_magnet_bucket_target")
        if callable(gift) and callable(pick_gift):
            def pick_bucket(g,source,center,radius_tiles):
                roster=g['僵尸']
                try:
                    # PvP64 slimes and the grenadier have drawn bodies with no
                    # head slot to show a bucket on; they never receive one.
                    g['僵尸']=[z for z in roster if not z.get('_pvp_grave') and not z.get('_pvp_hero')
                              and z.get('_pvp_content') not in NO_BUCKET]
                    found=pick_gift(g,source,center,radius_tiles)
                finally:g['僵尸']=roster
                if found is not None:return found
                sitting=self._riding_imp_candidate(center,radius_tiles,False)
                if sitting is None or not sitting[0].get("防具"):return None
                return sitting
            def gift_bucket(g,source,target,center,point):
                if target.get('_pvp_grave') or target.get('_pvp_hero'):return False
                before=(target.get("防具"),target.get("防具血量",0))
                fired=gift(g,source,target,center,point)
                if fired and before[0] and before[1]:
                    # That head was already armed, so this gift was for the imp.
                    target[bucket]=target.get("防具")
                    target[IMP_ARMOR_HP]=target.get("防具血量",0)
                    target["防具"],target["防具血量"]=before
                elif fired:
                    # A replacement ordinary bucket is a new piece, not the
                    # black piece previously stripped from this thrown imp.
                    target[IMP_BLACK_ARMOR]=None
                    target.pop('_pvp_armor_triggered',None)
                return fired
            ns["__pvz_sb_pick_gold_magnet_bucket_target"]=pick_bucket
            ns["__pvz_sb_gift_bucket_to_zombie"]=gift_bucket
        absorb=ns.get("__pvz_sb_absorb_metal_from_zombie")
        pick_absorb=ns.get("__pvz_sb_pick_gold_magnet_absorb_target")
        metal=ns.get("__pvz_sb_METAL_ITEMS",())
        if callable(absorb) and callable(pick_absorb):
            effect=ns.get("__pvz_sb_spawn_magnet_attract_effect")
            sound=ns.get("__pvz_sb_play_named_sound")
            sound_key=ns.get("__pvz_sb_K_MAGNET_SOUND")
            hurt=ns.get("__pvz_sb_K_HURT","受伤")
            def pick_metal(g,source,center,radius_tiles):
                found=pick_absorb(g,source,center,radius_tiles)
                if found is not None:return found
                sitting=self._riding_imp_candidate(center,radius_tiles,True)
                if sitting is None or armor_logic(sitting[0].get(bucket)) not in metal:return None
                return (sitting[0],sitting[1],"imp")
            def absorb_metal(g,source,target,point,center,slot):
                if slot!="imp":return absorb(g,source,target,point,center,slot)
                item=target.get(bucket)
                if armor_logic(item) not in metal or not carried_imp_armored(target):return False
                # A magnet takes the piece off whole: nothing broke, so nothing
                # blasts.  The black drop belongs to the armour falling off the
                # imp that was thrown off the back, which the engine's own damage
                # path reports through armor_drop.
                strip_carried_imp_armor(target)
                target[hurt]=1
                if callable(effect):effect(g,item,point,center)
                if callable(sound) and sound_key:sound(g,sound_key,center)
                return True
            ns["__pvz_sb_pick_gold_magnet_absorb_target"]=pick_metal
            ns["__pvz_sb_absorb_metal_from_zombie"]=absorb_metal
        has_metal=ns.get("__pvz_sb_zombie_has_active_metal")
        if callable(has_metal):
            def active_metal(zombie):
                if has_metal(zombie):return True
                # The imp on the back wears its own armour, and metal there is
                # metal: the thunder stun has to see it as well, or a giant
                # stripped of its own helmet would stop being a metal target
                # while still carrying a black bucket.
                return (isinstance(zombie,dict) and carried_imp_armored(zombie)
                        and armor_logic(zombie.get(bucket)) in metal)
            ns["__pvz_sb_zombie_has_active_metal"]=active_metal

    def _block_pending_producer_transforms(self):
        for obj in list(self.g["植物"]):
            target = obj.get("模仿")
            if obj.get("植物") == "模仿者" and target:
                key = obj.get("_pvp_copy_card", "plant:"+target)
                try:card = resolve_card(key,self.team_secrets["plant"],self.bans)
                except ValueError:card = None
                if card is None or card.get("producer"):
                    obj["植物血"] = 0
                    self._emit("spawn_blocked",card=key,reason="deathmatch_pending_copy")

    def _hero_lock(self, source, side):
        if team_of(side) != "zombie":return False
        target = self.players[side]
        origin = self.players["plant"]
        if isinstance(source,dict):
            if source.get("_pvp_owner") == "zombie":return False
            if "坐标" in source:
                row,col = source["坐标"]
                origin = dict(x=(col+.5)*self.tile,y=(row+1)*self.tile,h=self.tile)
            elif "位置" in source or "玩家位置" in source:
                x,y = source.get("位置",source.get("玩家位置"))[:2]
                origin = dict(x=x,y=y,h=self.tile)
        marked = self.time < target["marked_until"]
        if not marked:
            for obj in self.g["植物"]:
                if obj.get("植物") != "路灯花" or obj.get("植物血",0)<=0:continue
                row,col = obj["坐标"]
                lantern = dict(x=(col+.5)*self.tile,y=(row+1)*self.tile,h=self.tile)
                if self.distance(lantern,target) <= 220 and self.line_of_sight(lantern,target):
                    marked = True
                    break
        if not marked:
            # 71002: a standing plant Dave marks the zombie Dave like a lantern.
            for seat in self.team_seats("plant"):
                dave = self.players[seat]
                if (self.hero_states[seat].get("玩家倒地") or dave.get("hp",0) <= 0
                        or self.distance(dave,target) > 220 or not self.line_of_sight(dave,target)):
                    continue
                marked = True
                break
        return (marked and
                self.distance(origin,target) <= self.rules["hero_lock_range"] and self.line_of_sight(origin,target))

    def _star_target(self):
        plant=self.g['植物'][self.g['l']]
        row,col=plant['坐标']
        query=self.patch.ns['__pvz_sb_starfruit_target']
        args=((col+.5)*self.tile,(row+.5)*self.tile,plant['方向'])
        if query(self.g,*args) is not None:return True
        # Original ray selection samples the torso, while projectile collisions
        # include the hero's upper body. Query that extra point without moving
        # the authoritative hero or changing ordinary zombie/multi-hit logic.
        heads=[]
        for target in self.g['僵尸']:
            if target.get('_pvp_hero'):
                head=dict(target);head['位置']=list(target['位置'])
                head['位置'][1]-=self.tile*.7
                heads.append(head)
        return bool(heads) and query(dict(self.g,僵尸=heads),*args) is not None

    def _tracking_gate(self):
        self.expansion.source_gate(None)
        self.periodic_targets.restore()
        source = self.targets.source()
        self.periodic_targets.begin(source)
        self.expansion.source_gate(source)
        if not isinstance(source,dict) or (source.get("植物") != "香蒲" and "追踪" not in source):return
        self._tracking_index(source)

    def _tracking_index(self, source):
        """Original tracking target index for a cattail/tracking source."""
        # The original target index uses these shared top-level scratch names.
        # Restore them before resuming the original unit's loop body.
        missing = object()
        saved = {key:self.g.get(key,missing) for key in ("l","x","y","juli")}
        try:self.targets.target_index(self.engine.regions["unit_target_index"],source)
        finally:
            for key,value in saved.items():
                if value is missing:self.g.pop(key,None)
                else:self.g[key] = value

    def _engine_draws_entity(self):
        """Whether the peeled entity region should draw the entity it is on.

        The original predicate only lets an entity through when it is not a
        wall-crosser, plus the two the PvP rules want drawn anyway.  Zombie
        peas are withheld on top of that: the patch paints them itself, because
        it alone knows whether a pea has been ignited through a torchwood, and
        an engine draw on top of that shows a second pea a few pixels away.
        """
        entity=self.g['实体'][self.g['l']]
        is_pea=self.patch.ns.get('__pvz_sb_is_zombie_pea') if hasattr(self,'patch') else None
        if callable(is_pea) and is_pea(entity):
            return False
        return '穿墙' not in entity or entity.get('名') in ('星星','尖刺')

    # 「疾行」 arms the plant hero with a third airborne jump.  The cap itself
    # stays native: the same original KEYDOWN region with only its
    # ``玩家跳跃 < 2`` operand widened, so gravity, launch speed and the 二段跳
    # lean are untouched.  Only the plant side ever asks for it.
    SECRET_TRIPLE_JUMP = "secret:疾行"
    TRIPLE_JUMP_CAP = 3

    def _jump_cap(self, side):
        """Native jump cap for one avatar; None keeps the original two jumps."""
        if team_of(side) == "plant" and self.SECRET_TRIPLE_JUMP in self.players[side]["secrets"]:
            return self.TRIPLE_JUMP_CAP
        if team_of(side) == "zombie":
            return self.zsecrets.jump_cap(side)     # 豌豆: one jump only
        return None

    def _hero_damaged(self, side, amount, kind, source):
        # Under team aliasing the faction key may hold the second seat's Dave.
        side = self.avatars[side].get("_pvp_seat", side)
        if amount>0:
            self.avatars[side]["_pvp_last_damage"]=self.engine.native_tick/250.
            self.avatars[side]["_pvp_regen_progress"]=0.
        if (team_of(side) == "zombie" and amount>0 and
                not (isinstance(source,dict) and source.get('_pvp_cattail'))):
            self.players[side]["marked_until"] = self.time+self.rules["mark_seconds"]
        owner = self.targets.owner(source)
        if isinstance(source, dict) and source.get("_pvp_seat") in self.players:owner = source["_pvp_seat"]
        if owner in self.players and team_of(owner) != team_of(side):self.players[owner]["stats"]["hero_damage"] += amount
        self._emit("damage",target=side,amount=amount,kind=kind,
                   source_entity=(source or {}).get("_pvp_id"),native=True)

    def _step_original(self, draw=True):
        """Advance exactly one 0.004-second native frame, in original order."""
        prof = self.profiler
        if prof:prof.begin(draw)
        self.engine.native_tick += 1
        # Already established finite child requests precede new director
        # admissions. No hidden live unit is constructed while the cap is full.
        self.scripted_spawn_budget.drain()
        if self.scripted and self.g['梯子cd']>0:self.g['梯子cd']-=1
        now = self.engine.native_tick / 250.
        self.g["_pvp_native_tick"] = self.engine.native_tick
        self.status.tick()
        self.content.before_tick()
        self.recorder.begin_frame(self.engine.native_tick)
        self.recorder.enabled=draw
        self.g["补帧"] = 0 if draw else 1
        self.g["同横尸"], self.g["同竖尸"] = {}, {}
        if prof:prof.mark("pre_tick")
        for side, avatar in self.avatars.items():
            if side not in self.present:continue
            seat_prof=getattr(self,'seat_profiler',None)
            if seat_prof:seat_started=seat_prof.clock()
            player = self.players[side]
            team = team_of(side)
            avatar["冻水"]=max(self.g.get("_pvp_water_ice",0),avatar.get('_pvp_cold_until',0)-self.engine.native_tick)
            before_entities = len(self.g["实体"])
            ice=avatar.get("_pvp_ice",0);butter=avatar.get("_pvp_butter",0)
            stun=avatar.get('_pvp_stun',0)
            held=butter>0 or ice>1000 or stun>0 or avatar["玩家血量"]<=0 and self.team_mode
            move=0 if held else player["input"]["move"]
            start_x=avatar["玩家位置"][0]
            pressed = self._jump_presses[side] > 0
            if (team == "plant" and avatar.get("玩家倒地", 0) > 0 and
                    MASOCHIST_RISE_FRAMES <= avatar.get("玩家恢复", 0) < NATIVE_RISE_FRAMES and
                    MASOCHIST_SECRET in player["secrets"]):
                # 抖M: the original stands Dave up once 玩家恢复 passes 2000
                # frames (8 s); PvP72 reaches that point after 4 s.
                avatar["玩家恢复"] = NATIVE_RISE_FRAMES
            elif team == "zombie":
                self._rally_rise(avatar)
            floating_body = self.team_mode and avatar['玩家血量'] <= 0 and self._float_body(avatar)
            if not floating_body:self.engine.physics.step(avatar, move, player["jump_held"] and not held,
                                     pressed and not held,
                                     max_jumps=self._jump_cap(side),
                                     balloon_hp=avatar.get("_pvp_balloon_hp"))
            if held:
                avatar["玩家位置"][0]=start_x;avatar["玩家位置"][2]=0.
            elif ice>0:
                avatar["玩家位置"][0]=(start_x+wrap_delta(start_x,avatar["玩家位置"][0],self.width)*.5)%self.width
            avatar["_pvp_ice"]=max(0,ice-1);avatar["_pvp_butter"]=max(0,butter-1)
            avatar['_pvp_stun']=max(0,stun-1)
            for entity in self.g["实体"][before_entities:]:
                self.targets.tag_entity(entity, team, avatar)
                if side != team:entity["_pvp_seat"] = side
                if entity.get("名")=="火" and avatar.get("_pvp_launch_attack"):
                    entity["_pvp_instant_attack"] = avatar["_pvp_launch_attack"]
                if team == "zombie" and entity.get("名") == "火":
                    ns = self.patch.ns
                    entity.update({ns["__pvz_sb_K_CHILI_ZOMBIE_FIRE"]:True,
                        ns["__pvz_sb_K_CHILI_FIRE_DAMAGE_MODE"]:"enemy",
                        ns["__pvz_sb_K_CHILI_ZOMBIE_EXPLOSION_ID"]:"launch:%s" % avatar["__pvz_sb_chili_launch_lock_until"],
                        # Launch tail flames burn enemy units only; the enemy
                        # hero already took the one-per-explosion judgement.
                        ns["__pvz_sb_K_CHILI_FIRE_NO_HERO"]:True,
                        ns["__pvz_sb_K_CHILI_FIRE_TARGET_ROWS"]:[int(entity["位置"][1]//self.tile)]})
            if pressed:
                # One reported press per native tick.  A counter rather than a
                # flag, so two taps landing inside one 30 Hz frame start two
                # jumps instead of collapsing into a single one.
                self._jump_presses[side] -= 1
            if seat_prof:seat_prof.record('hero_physics:'+side,(seat_prof.clock()-seat_started)*1000.)
        if prof:prof.mark("hero_physics")
        self._advance_suns()
        if prof:prof.mark("sun_motion")
        source = "zombie" if self.command == "follow" else "plant"
        if self._multi_target or self.mode == 'pve':source = self._team_tracking()
        else:
            self.engine.physics.update_tracking(self.avatars[source],
                "我是僵尸" if self.command == "follow" else "正常模式")
        self._update_rally_tracking(self.avatars[source])
        self.content.pvp64.update_taunts(self.avatars[source])
        self._select_hero("plant")
        if prof:prof.mark("tracking")
        self.engine.execute("water_animation")
        self.engine.execute("important_blocks")
        if prof:prof.mark("world_blocks")
        self.patch.before_native_tick(now)
        if prof:prof.mark("patch_before")
        # Graves skip the mobile-zombie region, which is also where native ash
        # deaths complete. Treat an ash-marked grave as dead here, or it keeps
        # its HP and burns forever. One pass builds the two suspended lists and
        # the mobile roster: three passes over every zombie ran 250 times a
        # second, and the profiler showed this driver as the biggest self time.
        graves = []
        barrels = []
        mobiles = []
        for obj in self.g["僵尸"]:
            grave = obj.get("_pvp_grave")
            barrel = obj.get('_pvp_orphan_barrel')
            if barrel and obj["血量"]>0:barrels.append(obj)
            if grave:
                if obj["血量"]>0 and "灰烬" not in obj:graves.append(obj)
            elif not barrel:
                mobiles.append(obj)
        self.g["僵尸"] = mobiles
        # A summon can synchronise the public roster inside this region. These
        # stationary targets are still alive while absent from mobile AI.
        self._suspended_graves = graves+barrels
        try:
            if self._multi_plant:
                with self._plant_switching("zombies"), \
                        self.targets.context(target="plant",owner="zombie",phase="zombies"), self.content.september.hide_ghost_cells():
                    try:
                        self.engine.execute("zombies")
                        if prof:prof.mark("zombies_engine")
                        self.content.finish_zombie()
                        self.expansion.finish_zombie()
                    finally:self._switch_back()
            else:
                with self.targets.context(target="plant",owner="zombie",phase="zombies"), self.content.september.hide_ghost_cells():
                    self.engine.execute("zombies")
                    if prof:prof.mark("zombies_engine")
                    # Restore the final car's temporary AI destination before the
                    # context commits hero state; it is not a Dave teleport.
                    self.content.finish_zombie()
                    self.expansion.finish_zombie()
        finally:
            self.content.pvp64.restore_taunt()
            self._restore_rally_tracking()
            self.g["僵尸"].extend(graves+barrels)
            self._suspended_graves = []
        self.content.wind.after_zombies()
        # Native bites can leave a plant at exactly zero HP without setting
        # its death marker. Resolve that boundary before plant actions run.
        for plant in self.g["植物"]:
            if plant.get("植物血", 1) <= 0 and "死" not in plant:
                plant["死"] = 0
        if prof:prof.mark("zombies")
        for grave in graves:
            ice=grave.get("冰冻",0);butter=grave.get("黄油",0)
            factor=0. if butter>0 or ice>1000 or grave.get('眩晕',0)>0 else .5 if ice>0 else 1.
            factor=self.grave_idle.advance(grave,factor)
            grave["_pvp_production_rate"]=factor
            for effect in ("冰冻","黄油","眩晕"):
                if grave.get(effect,0)>0:grave[effect]=max(0,grave[effect]-1)
            # A non-producing grave has no production clock at all. Accruing one
            # would leave a phantom >= period reading that any later relaxation
            # of the economy's producer gate would pay out immediately.
            if not grave.get("_pvp_producer"):continue
            uid=grave["_pvp_id"]
            self._grave_progress[uid]=self._grave_progress.get(uid,0.)+factor/250.*(self.rules["production_multiplier"] if self.deathmatch or self.zsecrets.team_last_stand() else 1.)
        self.g["僵尸"].extend(self.zombie_hero_proxies())
        if prof:prof.mark("grave_clock")
        # These targets deliberately skip mobile zombie AI. They still need
        # the original body's row/column registration so chomping and other
        # row-activated plants can see their head as well as their feet.
        for index,obj in enumerate(self.g["僵尸"]):
            if (obj.get("_pvp_grave") or obj.get("_pvp_hero") or obj.get('_pvp_orphan_barrel')) and obj["血量"]>0:
                self.g["l"] = index
                self.engine.execute("zombie_coordinates")
                self.engine.execute("zombie_body_index")
        if prof:prof.mark("target_registration")
        for side, avatar in self.avatars.items():
            if side not in self.present:continue
            with self.targets.context(target=side,owner=team_of(side),phase="player",source=avatar):
                self.targets.target_index(self.engine.regions["unit_target_index"],avatar)
                self.engine.physics.advance_hero_effects(avatar,
                    tail_enabled=now >= self.rules['tail_activation_seconds'])
        if prof:prof.mark("hero_target_index")
        if draw:self.engine.draw_plants()
        if prof:prof.mark("plant_draw")
        self.targets.target_index(self.engine.regions["unit_target_index"])
        if prof:prof.mark("unit_target_index")
        self._petrified_torch_ignite_plant_peas()
        self.plant_zombies.ignite_charmed_peas()
        if prof:prof.mark("petrified_torch")
        entities = self.g["实体"]
        completed = []
        for owner in ("plant","zombie"):
            self.g["实体"] = [entity for entity in entities if entity.get("_pvp_owner","plant")==owner]
            switching = self._multi_plant and owner=="zombie"
            with (self._plant_switching("entities") if switching else nullcontext()), \
                    self.targets.context(target="zombie" if owner=="plant" else "plant",owner=owner,phase="entities"), (
                    self.content.september.hide_ghost_cells() if owner=="zombie" else nullcontext()):
                try:self.engine.execute("entities")
                finally:
                    if switching:self._switch_back()
                    self.expansion.source_gate(None)
                    self.periodic_targets.restore()
            self.expansion.restore_art()
            completed.extend(self.g["实体"])
            if prof:prof.mark("entities_"+owner)
        self.g["实体"] = completed
        self.content.projectiles()
        self.projectile_rules.cull_flight()
        if prof:prof.mark("projectile_patch")
        self.engine.execute("particles")
        if prof:prof.mark("particles")
        self.gravebusters.before_native_tick()
        with self.targets.context(target="zombie",owner="plant",phase="plants"):
            self.engine.execute("plant_maintenance")
        self.expansion.before_plants()
        if prof:prof.mark("plant_maintenance")
        for obj in self.g["植物"]:
            if obj.get("植物") not in self.g["产光植物"] or "睡觉" in obj:continue
            card=self._card("plant","plant:"+obj["植物"])
            rest=rest_factor(obj,self.engine.native_tick,self.rules)
            due=obj.get("_pvp_sun_due",1500.)-(self.rules["production_multiplier"] if self.deathmatch else 1.)*rest/obj.get('_pvp_aura_factor',1.)
            obj["阳光"]=1000000  # only the PvP scheduler starts the original burst
            if due<=125 and not obj.get("爆了"):obj["爆了"]=1
            if due<=1e-7:
                obj["爆了"]=124  # original next tick emits at animation frame 125
                due+=card["period"]*250.
            elif obj.get("爆了")==124:obj["爆了"]=123
            obj["_pvp_sun_due"]=due
        if prof:prof.mark("production_clock")
        self._own_umbrella_effects(False)
        self.content.wind.before_plants()
        with self.targets.context(target="zombie",owner="plant",phase="plants"), self.gravebusters.plants():
            try:self.engine.execute("plants")
            finally:
                self._finish_sun_source()
                self.expansion.source_gate(None)
                self.periodic_targets.restore()
        self.content.sea.restore()
        self._own_umbrella_effects(True)
        self.content.wind.after_plants()
        self.expansion.source_gate(None)
        if prof:prof.mark("plants")
        self.patch.after_native_tick(now)
        if prof:prof.mark("patch_after")
        self.expansion.after_plants()
        self.content.after_plants()
        if prof:prof.mark("content_after")
        self.g["冻水"]=self.g.get("_pvp_water_ice",0)
        self.engine.execute("water_ice_clock")
        self.g["_pvp_water_ice"]=self.g["冻水"]
        if draw:self.patch.draw(now)
        if prof:prof.mark("patch_draw")
        self.g["僵尸"] = [obj for obj in self.g["僵尸"] if not obj.get("_pvp_hero")]
        for obj in self.g["僵尸"]:
            if obj.get("_pvp_grave") and obj.get("_pvp_anchor"):
                obj["位置"][:]=list(obj["_pvp_anchor"])+[0.,0.]
        for side, avatar in self.avatars.items():
            if side not in self.present:continue
            self.recorder.entity_override=avatar
            draw_dave(self.g,self.engine.root,avatar,materialize=draw or not self.graphics.skip_dave_pixels)
        self.recorder.entity_override=None
        self.content.barrels.reconcile()
        for obj in self.g['僵尸']:
            if obj.get('_pvp_orphan_barrel'):
                self.recorder.entity_override=obj
                self.content.barrels.draw(obj)
        self.recorder.entity_override=None
        for obj in self.g["僵尸"] + self.g["实体"]:
            if "位置" in obj:obj["位置"][0] %= self.width
        if prof:prof.mark("post_draw")
        if draw:self._frame = self.recorder.snapshot()
        if prof:
            prof.mark("frame_record")
            prof.end()

    def _own_umbrella_effects(self, after):
        if self._multi_plant:
            try:
                for seat in self.team_seats("plant", alive=True):
                    self._set_alias(seat)
                    self._own_umbrella_pass(after)
            finally:self._set_alias("plant")
            return
        self._own_umbrella_pass(after)

    def _own_umbrella_pass(self, after):
        # The plant loop targets Z Dave. Its original player-only utility
        # branch must also remain available to the owner's ordinary Dave.
        for index,plant in enumerate(self.g["植物"]):
            if plant.get("植物")!="萝卜伞" or plant.get("植物血",0)<=0 or "睡觉" in plant:continue
            if after and plant.get("射")!=20:continue
            if not after and (plant.get("射",0)!=0 or plant.get("射cd",0)>0):continue
            saved={k:self.g.get(k) for k in ("l","xx","yy","射")}
            row,col=plant["坐标"]
            with self.targets.context("plant","plant","plants",plant):
                self.g.update(l=index,xx=(col+.5)*self.tile,yy=(row+.5)*self.tile,射=False)
                self.engine.execute("umbrella_player_bounce" if after else "umbrella_player_trigger")
            self.g.update(saved)

    def step(self, steps=1):
        for unused in range(steps):
            if self.result or self.audit_error:return
            # Preserve native draw branches and their RNG/state changes. Only
            # the pixel transforms of intermediate captures may be deferred.
            self.graphics.defer_capture=self.capture_demand and (unused<steps-1 or getattr(self,'_capture_intermediate',False))
            self.capture_frames+=1
            self.capture_deferred+=int(self.graphics.defer_capture)
            self.tick += 1
            self.time = self.tick*self.dt
            if self.director and getattr(self.director,'cycle',None):
                self.director.cycle.step()
            if not self.deathmatch and self.time >= self.rules["deathmatch_seconds"]:
                self.deathmatch = True
                for side, player in self.players.items():
                    spans = player.setdefault("cooldown_spans", {})
                    for key, ready_at in player["cooldowns"].items():
                        factor = deathmatch_factor(self._card(side,key)["cooldown"])
                        player["cooldowns"][key] = self.time + max(0.,ready_at-self.time) * factor
                        if key in spans:spans[key] *= factor
                self._block_pending_producer_transforms()
                self._emit("deathmatch", multiplier=self.rules["production_multiplier"])
            for side, player in self.players.items():
                if self.tick-player["last_input_tick"] > self.rules["tick_rate"]*2:self.clear_input(side)
            # Integer accumulator: 30 network updates advance 250 original
            # ticks exactly. Display FPS and latency never change unit speed.
            self._native_phase += 250
            count, self._native_phase = divmod(self._native_phase, self.rules["tick_rate"])
            prof = self.profiler
            if prof:started = prof.clock()
            clock = _perf_counter
            native_started = clock()
            for index in range(count):self._step_original(draw=index==count-1)
            if count:
                # Recent share of one core the original regions need for the game
                # time they advance. The wave director reads it to pace late
                # waves instead of piling more units onto a saturated engine.
                spent = clock() - native_started
                ratio = spent / (count / 250.)
                self.native_cost_ratio = ratio if self.native_cost_ratio is None else (
                    self.native_cost_ratio * (1. - NATIVE_COST_SMOOTHING) + ratio * NATIVE_COST_SMOOTHING)
            if prof:native_done = prof.clock()
            self._deathmatch_water(count/250.)
            self._masochist()
            self._sturdy()
            self._recover_heroes(count/250.)
            self._sync_public()
            if prof:public_done = prof.clock()
            self._economy()
            if self.ai_subsidy_seats:self._ai_subsidy()
            if self.zsecrets.enabled:self.zsecrets.step(count/250.)
            if self.mode != DUEL:
                self._team_step(count/250.)
            else:
                dead = [side for side, player in self.players.items() if player["hp"] <= 0]
                if dead:
                    self.result = dict(winner="draw" if len(dead)==2 else ("zombie" if dead[0]=="plant" else "plant"),
                                       reason="hero_death",tick=self.tick)
                    self._emit("result", **self.result)
            if prof:
                done = prof.clock()
                prof.record("room_native_ticks", (native_done-started)*1000.)
                prof.record("room_sync_public", (public_done-native_done)*1000.)
                prof.record("room_economy_result", (done-public_done)*1000.)
                prof.record("room_step", (done-started)*1000.)
        self.graphics.defer_capture=False

    SUN_MERGE_TILES = .6
    SUN_MERGE_SPEED = .05

    def _merge_suns(self):
        """PvP64: suns that overlap and move together become one.

        The value is the sum and the later of the two expiry times is kept, so
        no sun is lost or shortened; only the number of loose suns (each one a
        native motion region every 250 Hz tick, and a sprite) goes down.
        Pairs are taken in id order, so every peer reaches the same result.
        """
        suns = [r for r in self.resources.values() if team_of(r["side"]) == "plant" and r["id"] in self._sun_motion]
        if len(suns) < 2:
            return
        def order(r):
            return (int(r["id"][1:]) if r["id"][1:].isdigit() else 0, r["id"])
        suns.sort(key=order)
        reach = self.SUN_MERGE_TILES * self.tile
        cols = max(1, int(math.ceil(self.width / reach)))
        changed = True
        while changed:
            changed = False
            grid = {}
            for r in suns:
                grid.setdefault((int(r["x"] // reach) % cols, int(r["y"] // reach)), []).append(r)
            gone = set()
            for r in suns:
                if r["id"] in gone:
                    continue
                gx, gy = int(r["x"] // reach) % cols, int(r["y"] // reach)
                motion = self._sun_motion[r["id"]][1]
                neighbours = sorted((other for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                     for other in grid.get(((gx + dx) % cols, gy + dy), ())
                                     if other is not r and other["id"] not in gone), key=order)
                for other in neighbours:
                    if other["id"] in gone:
                        continue
                    if math.hypot(wrap_delta(r["x"], other["x"], self.width), other["y"] - r["y"]) > reach:
                        continue
                    if other["side"] != r["side"] or other.get("shared") != r.get("shared") or other.get("coin") != r.get("coin"):
                        continue
                    other_motion = self._sun_motion[other["id"]][1]
                    if abs(motion[2] - other_motion[2]) + abs(motion[3] - other_motion[3]) > self.SUN_MERGE_SPEED:
                        continue
                    # The larger sun absorbs the smaller; on a tie, the older one.
                    keep, drop = (r, other) if r["amount"] >= other["amount"] else (other, r)
                    keep["amount"] += drop["amount"]
                    keep["born"] = max(keep["born"], drop["born"])
                    self.resources.pop(drop["id"], None)
                    self._sun_motion.pop(drop["id"], None)
                    gone.add(drop["id"])
                    changed = True
                    if drop is r:
                        break
            suns = [r for r in suns if r["id"] not in gone]

    def _economy(self):
        self._merge_suns()
        for sun in self.g["阳光球"]:
            # Original loose suns use numeric size: 0 small, 1 full size.
            amount=self.content.september.bloom_sun_amounts.pop(id(sun),None)
            if amount is None:amount=self.secrets66.death_sun_amount(sun)
            rid=self.resource(self._sun_owner(sun) if self._multi_plant else "plant",amount if amount is not None else
                              (15 if sun[-1]==0 else 25),sun[1][0],sun[1][1],"native_producer")
            self._sun_motion[rid]=copy.deepcopy(sun)
        self.g["阳光球"].clear()
        night=self.map.get("environment",{}).get("night",False)
        # Settle against the same 250Hz clock as native production. Room pauses
        # and replay pauses do not advance it; repeat snapshots cannot pay twice.
        previous=self._day_brain_native_tick
        now=self.engine.native_tick
        self._day_brain_native_tick=now
        if not night:
            interval=max(1,round(self.rules["day_brain_interval"]*250))
            payments=self.zsecrets.day_income_count(previous,now,interval)
            if payments is None:payments=max(0,now//interval-previous//interval)
            for unused in range(payments):
                for seat in self.team_seats("zombie"):
                    hero=self.players[seat]
                    self.resource(seat,self.rules["day_brain_amount"],hero["x"],hero["y"],"day_income")
        self.sky_progress = 0. if night else self.sky_progress+self.dt
        if not night and self.sky_progress+1e-9 >= self.sky_interval:
            self.sky_progress = max(0.,self.sky_progress-self.sky_interval)
            x=self.rng.uniform(0,self.width)
            floor=next((row*self.tile for row in range(len(self.map["tiles"])) if self.cell(x,row*self.tile+1).get("solid")),self.height)
            rid=self.resource("plant", self.rules["sky_amount"], x,
                          max(0.,min(self.players["plant"]["y"]-80,floor-self.tile)), "sky")
            # PvP66: sky sun is common to the plant team; whoever reaches it
            # first takes it. Each Dave's own production stays his own.
            if self._multi_plant:self.resources[rid]["shared"]=True
        for uid, obj in self._native_objects.items():
            if not obj.get("_pvp_grave") or obj["血量"] <= 0:continue
            card = self._card("zombie",obj["_pvp_card"])
            if not card.get("producer"):continue
            mature=self.time-obj.get("_pvp_born",0)>=card.get("mature_at",float("inf"))
            if mature and card.get("mature_hp") and not obj.get("_pvp_mature"):
                obj["血量"]*=2;obj["_pvp_max_hp"]=card["mature_hp"];obj["_pvp_mature"]=True
            amount = self._grave_progress.get(uid,0.)
            period=card["period"] if obj.get("_pvp_produced") else 6.
            if amount+1e-9 >= period:
                amount = max(0.,amount-period);obj["_pvp_produced"]=True
                reward = card.get("mature_yield",card["yield_amount"]) if self.time-obj.get("_pvp_born",0)>=card.get("mature_at",float("inf")) else card["yield_amount"]
                self.resource(obj.get("_pvp_seat","zombie"),reward,obj["位置"][0],obj["位置"][1],uid)
            self._grave_progress[uid] = amount
        for rid, resource in list(self.resources.items()):
            if resource.get("shared"):
                if self._auto_shared_sky(rid):continue
                collector = self._shared_collector(resource)
                if collector:self._collect(rid, collector)
                elif self.time-resource["born"] > self.rules["sun_lifetime"]:self.resources.pop(rid,None)
                continue
            player = self.players[resource["side"]]
            if self.team_mode and player["hp"] <= 0:
                if self.mode=='coop' and team_of(resource['side'])=='plant':
                    collector=self._shared_collector(resource)
                    if collector:
                        self._collect(rid,collector)
                        continue
                if self.time-resource["born"] > self.rules["sun_lifetime"]:self.resources.pop(rid,None)
                continue
            if ((team_of(resource['side'])=='plant' and 'secret:阳光' in player['secrets']) or
                math.hypot(wrap_delta(resource["x"],player["x"],self.width),resource["y"]-player["y"]+30)<60*sun_scale(resource["amount"])):self._collect(rid)
            elif self.time-resource["born"] > self.rules["sun_lifetime"]:self.resources.pop(rid,None)

    def _masochist(self):
        for seat in self.team_seats("plant"):
            self._masochist_seat(seat)

    def _masochist_seat(self, seat):
        """抖M: any loss of the plant hero's life pays sun, at most every 3 s.

        Compared once per network frame against the life the previous frame
        ended with, so every damage source counts - bites, shots, fire, water -
        while healing never does.
        """
        avatar = self.avatars[seat]
        hp = avatar["玩家血量"]
        # _recover_heroes records the life each frame ends with; it runs after.
        before = avatar.get("_pvp_previous_hp", hp)
        if MASOCHIST_SECRET not in self.players[seat]["secrets"] or hp >= before or (self.team_mode and hp <= 0):
            return
        if self.time < avatar.get("_pvp_masochist_ready", 0.):
            return
        avatar["_pvp_masochist_ready"] = self.time + MASOCHIST_COOLDOWN
        amount = MASOCHIST_EARLY_SUN if self.time < MASOCHIST_EARLY_SECONDS else MASOCHIST_LATE_SUN
        player = self.players[seat]
        rid = self.resource(seat, amount, player["x"], player["y"], "masochist")
        self._sun_motion.pop(rid, None)
        self._collect(rid)

    def select_grave(self, seat, grave_id):
        """解除封印: the chosen grave (75% damage reduction, zombie_secrets)."""
        if team_of(seat) != "zombie" or not self.zsecrets.seat_has(seat, "解除封印"):
            return "需要携带解除封印秘籍"
        grave = self.units.get(grave_id) if isinstance(grave_id, str) else None
        if (not grave or grave.get("behavior") != "grave" or grave.get("hp", 0) <= 0
                or team_of(grave.get("side", "")) != "zombie"):
            return "请选择己方存活的墓碑"
        if self.players[seat].get("selected_grave") != grave_id:
            self.players[seat]["selected_grave"] = grave_id
            self._emit("zsecret_select_grave", side=seat, grave=grave_id)
        return ""

    def _rally_rise(self, avatar):
        """PvP66 rally-flag rise (user rule 10-13).

        Only a flag that already stood on the last tick before the zombie Dave
        fell earns the early rise; a flag planted while he is down does not.
        An eligible Dave is checked once, 4 s after falling: a flag standing
        then lifts him at once, otherwise he waits for the native 8 s.
        Per-avatar state, so every 2v2 seat keeps its own.
        """
        down = avatar.get("玩家倒地", 0) > 0
        if not down:
            avatar.pop("_pvp_rally_eligible", None)
            avatar.pop("_pvp_rally_checked", None)
            # Kept only while a flag stands: a flagless game gains no state.
            if self.rally_for(avatar) is not None:
                avatar["_pvp_rally_before"] = True
            else:
                avatar.pop("_pvp_rally_before", None)
            return
        if "_pvp_rally_eligible" not in avatar:
            if not avatar.pop("_pvp_rally_before", False):
                return        # no flag before the fall: the native 8 s, nothing recorded
            avatar["_pvp_rally_eligible"] = True
        if avatar.get("_pvp_rally_checked") or avatar.get("玩家恢复", 0) < NATIVE_RISE_FRAMES // 2:
            return
        avatar["_pvp_rally_checked"] = True
        early = self.rally_for(avatar) is not None and avatar.get("玩家恢复", 0) < NATIVE_RISE_FRAMES
        if early:
            avatar["玩家恢复"] = NATIVE_RISE_FRAMES
        self._emit("rally_rise_check", side=avatar.get("_pvp_seat", "zombie"), eligible=True, early=early)

    def _hero_damage_factor(self, side):
        """强健: the knocked-down plant hero takes half damage."""
        side = self.avatars[side].get("_pvp_seat", side) if side in self.avatars else side
        if (team_of(side) == "plant" and STURDY_SECRET in self.players[side]["secrets"]
                and self.hero_states[side].get("玩家倒地", 0) > 0):
            return 1. - STURDY_REDUCTION
        if (team_of(side)=='zombie' and self.zsecrets.seat_has(side,'石更！')
                and self.hero_states[side].get('玩家倒地',0)>0):
            return .75
        return 1.

    def _sturdy(self):
        for seat in self.team_seats("plant"):
            self._sturdy_seat(seat)

    def _sturdy_seat(self, seat):
        """强健: each knockdown halves what is left of every running cooldown."""
        avatar = self.avatars[seat]
        player = self.players[seat]
        down = avatar.get("玩家倒地", 0) > 0 and avatar.get("玩家血量", 0) > 0
        if not down:
            avatar.pop("_pvp_sturdy_down", None)
            return
        if STURDY_SECRET not in player["secrets"] or avatar.get("_pvp_sturdy_down"):
            return
        avatar["_pvp_sturdy_down"] = True
        cut = []
        for key, ready_at in player["cooldowns"].items():
            remaining = ready_at - self.time
            if remaining > 0:
                player["cooldowns"][key] = self.time + remaining * (1. - STURDY_COOLDOWN_CUT)
                cut.append(key)
        self._emit("sturdy", side=seat, cards=sorted(cut))

    def _deathmatch_water(self, elapsed):
        """Environmental HP loss bypasses hit impulses and native knockdown."""
        for side, avatar in self.avatars.items():
            if side not in self.present:continue
            x, y = avatar['玩家位置'][:2]
            wet = self.deathmatch and any(self.cell(x+dx,y+dy).get('water')
                for dx in (-self.tile*.2,0,self.tile*.2)
                for dy in (.1,-self.tile*.5,-self.tile*1.2))
            progress = avatar.get('_pvp_water_damage_clock',0.) + elapsed if wet else 0.
            if wet and avatar['玩家血量']>0 and progress+1e-9>=1.:
                amount = int(progress+1e-9); progress -= amount
                avatar['玩家血量'] = max(0.,avatar['玩家血量']-amount)
                self._emit('damage', target=side, amount=amount, kind='deathmatch_water')
            avatar['_pvp_water_damage_clock'] = progress

    def resource(self,side,amount,x,y,source):
        if hasattr(self,'audio') and source not in ('sky','day_income','petrified_torch','masochist'):self.audio.emit('阳光菇',[x,y])
        rid=super().resource(side,amount,x,y,source)
        if team_of(side)=="plant":self._sun_motion[rid]=[0,[float(x),float(y),0.,0.],0,1]
        return rid

    def _advance_suns(self):
        saved=self.g["阳光球"];old_index=self.g.get("l",0)
        try:
            for rid,motion in list(self._sun_motion.items()):
                if rid not in self.resources:
                    del self._sun_motion[rid];continue
                self.g["阳光球"]=[motion];self.g["l"]=0
                self.engine.execute("sun_motion")
                motion[1][0]%=self.width
                self.resources[rid].update(x=motion[1][0],y=motion[1][1])
        finally:self.g["阳光球"]=saved;self.g["l"]=old_index

    def _recover_heroes(self,elapsed):
        now=self.engine.native_tick/250.
        for side,avatar in self.avatars.items():
            hp=avatar["玩家血量"];maximum=avatar["_pvp_max_hp"]
            if hp<avatar["_pvp_previous_hp"]:
                avatar["_pvp_last_damage"]=now;avatar["_pvp_regen_progress"]=0.
            if 0<hp<maximum and now-avatar["_pvp_last_damage"]>=self.rules["hero_regen_delay"]:
                eligible=max(0.,min(elapsed,now-avatar["_pvp_last_damage"]-self.rules["hero_regen_delay"]))
                avatar["_pvp_regen_progress"]+=eligible
                interval=self.rules["hero_regen_interval"]
                if avatar["_pvp_regen_progress"]+1e-9>=interval:
                    count=int((avatar["_pvp_regen_progress"]+1e-9)/interval)
                    avatar["_pvp_regen_progress"]-=count*interval
                    healed=min(maximum-hp,count*self.rules["hero_regen_amount"])
                    avatar["玩家血量"]+=healed
                    self._emit("heal",target=side,amount=healed,kind="out_of_combat")
            else:avatar["_pvp_regen_progress"]=0.
            avatar["_pvp_previous_hp"]=avatar["玩家血量"]
        for proxy in self.targets.proxies.values():proxy.sync()

    @contextmanager
    def _summon_hero(self, side):
        """Lend the global player to ``side``'s Dave for one spawn.

        Original spawn code reads the faction's global player, but a summon
        can run inside another hero's combat context (a bungee's airdrop
        lands while the plant Dave is global). Borrow it the way a nested
        targets.context does: capture the enclosing hero's direct writes,
        make the active target the Dave that is now global (a context the
        spawned unit opens captures into that Dave, not the enclosing one),
        then put every replaced global back and re-apply the enclosing hero's
        latest combat values. Otherwise the zombie Dave's position list, HP
        and downed state land on the plant Dave (replay cc456a4cd961a0e57fd1).
        """
        g, targets = self.g, self.targets
        active = targets.active
        if active:
            outer = targets.heroes[active["target"]]
            for key in _COMBAT_HERO_KEYS:
                if key in g:outer[key] = g[key]
        saved = [(key, g.get(key, _HERO_MISSING)) for key in (*self.avatars[side], "模式", "秘籍")]
        lent = self.avatars[side]
        self._select_hero(side)
        if active:targets.active = dict(active, target=side)
        try:
            yield
        finally:
            for key in _COMBAT_HERO_KEYS:
                if key in g:lent[key] = g[key]
            for key, value in saved:
                if value is _HERO_MISSING:g.pop(key, None)
                else:g[key] = value
            targets.active = active
            if active:
                outer = targets.heroes[active["target"]]
                for key in _COMBAT_HERO_KEYS:
                    if key in outer:g[key] = outer[key]

    def _select_hero(self, side, mode=None):
        self.g.update(self.avatars[side])
        self.g["模式"] = mode or ("我是僵尸" if team_of(side) == "zombie" else "正常模式")
        self.g["秘籍"] = self.native_secrets

    def rally_destination(self, owner='zombie'):
        """Nearest open cell to the flag; solid tiles never become colliders or heroes."""
        point=self.rally_for(owner)
        if point is None:return None
        key=(point['x'],point['y'],self.terrain_revision)
        if self.mode == DUO:
            seat=self.command_seat(owner)
            cache=getattr(self,'_rally_destinations',{})
            if seat in cache and cache[seat][0]==key:return list(cache[seat][1])
        if getattr(self,'_rally_destination_key',None)!=key:
            x,y=key[:2];col=int(x//self.tile);row=int(y//self.tile)
            candidates=[(abs(ry-row)+min(abs(cx-col),self.map['cols']-abs(cx-col)),ry,cx)
                for ry,line in enumerate(self.map['tiles']) for cx,cell in enumerate(line) if not cell['solid']]
            _,ry,cx=min(candidates,default=(0,row,col))
            self._rally_destination=[(cx+.5)*self.tile,(ry+1.)*self.tile]
            self._rally_destination_key=key
        if self.mode == DUO:
            cache[seat]=(key,list(self._rally_destination))
            self._rally_destinations=cache
        return list(self._rally_destination)

    def _update_rally_tracking(self, avatar):
        from .native_physics import TRACKING_KEYS
        self._rally_tracking_base=None
        if self.mode == DUO:
            # Separate persistent path fields: mixed follow/attack and two flags
            # can coexist without the previous zombie leaking its destination.
            baseline={key:self.g[key] for key in TRACKING_KEYS if key in self.g}
            fields=getattr(self,'_rally_trackings',{})
            active={}
            for seat in self.team_seats('zombie'):
                if self.rally_for(seat) is None:continue
                state=fields.get(seat) or copy.deepcopy(baseline)
                goal=self.rally_destination(seat)
                if state.get('_pvp_goal')!=goal:
                    state.update(人洪水圈=[],人洪水cd=0,_pvp_goal=goal)
                self.g.update(state)
                try:
                    self.engine.physics.update_tracking(dict(self.hero_states[seat],玩家位置=goal+[0.,0.]),'我是僵尸')
                    active[seat]={key:self.g[key] for key in TRACKING_KEYS if key in self.g}
                    active[seat]['_pvp_goal']=goal
                finally:self.g.update(baseline)
            self._rally_trackings=active
            self._rally_tracking_base={key:baseline[key] for key in
                ('洪水','目标植物','目标位置','paoku','输出植物数') if key in baseline}
            return
        if self.rally_point is None:
            self._rally_tracking=None
            return
        # Keep the ordinary field alive for charmed units. A rally is a second
        # path field, never a command to units that have changed allegiance.
        baseline={key:self.g[key] for key in TRACKING_KEYS if key in self.g}
        if getattr(self,'_rally_tracking',None) is None:
            self._rally_tracking=copy.deepcopy(baseline)
            self._rally_tracking_goal=None
        goal=self.rally_destination()
        if getattr(self,'_rally_tracking_goal',None)!=goal:
            self._rally_tracking.update(人洪水圈=[],人洪水cd=0)
            self._rally_tracking_goal=goal
        self.g.update(self._rally_tracking)
        try:
            self.engine.physics.update_tracking(dict(avatar,玩家位置=goal+[0.,0.]),'我是僵尸')
            self._rally_tracking={key:self.g[key] for key in TRACKING_KEYS if key in self.g}
        finally:self.g.update(baseline)
        self._rally_tracking_base={key:baseline[key] for key in
            ('洪水','目标植物','目标位置','paoku','输出植物数') if key in baseline}

    def _restore_rally_tracking(self):
        if getattr(self,'_rally_tracking_base',None):self.g.update(self._rally_tracking_base)

    def _rally_zombie_gate(self):
        self._restore_rally_tracking()
        z=self.g['僵尸'][self.g['l']]
        tracking=self.rally_tracking_for(z)
        if tracking is not None:
            self.g.update({key:tracking[key] for key in self._rally_tracking_base})
        self._native_zombie_gate()

    def rally_tracking_for(self, z):
        if '魅惑' in z or self.rally_for(z) is None:return None
        if self.mode == DUO:return getattr(self,'_rally_trackings',{}).get(self.command_seat(z))
        return self._rally_tracking

    def _rally_speed(self):
        z=self.g['僵尸'][self.g['l']]
        speed=z['移速']
        if self.rally_for(z) is not None and '魅惑' not in z and not z.get('_pvp_grave'):
            x,y=self.rally_destination(z)
            if abs(wrap_delta(z['位置'][0],x,self.width))<self.tile*.4 and abs(z['位置'][1]-y)<self.tile:
                speed=0.
        return speed

    def _command_input(self, side, payload):
        if isinstance(payload, dict) and payload.get("type") == "move" and side in self.players:
            player = self.players[side]
            before = player["jump_held"]
            grounded = player["grounded"]
            # The protocol parent may validate a jump, but may not apply its
            # former one-jump velocity formula. Native KEYDOWN owns jumping.
            player["grounded"] = False
            result = super()._command_input(side, payload)
            player["grounded"] = grounded
            if not result:
                if payload.get("edge"):
                    # The client reports the press itself, so it no longer has
                    # to survive a 40 ms key sample or share a frame with the
                    # next tap. From here on this side's presses come this way.
                    self._press_reported[side] = True
                    self._jump_presses[side] = min(3, self._jump_presses[side] + 1)
                elif player["jump_held"] and not before and not self._press_reported[side]:
                    # Legacy held-state rising edge, kept so a side that only
                    # samples still jumps - and skipped once real presses
                    # arrive, or one tap would be counted twice.
                    self._jump_presses[side] = min(3, self._jump_presses[side] + 1)
            return result
        return super()._command_input(side, payload)

    def clear_input(self, side):
        super().clear_input(side)
        if side in self._jump_presses:
            self._jump_presses[side] = 0

    def _card(self, side, key):
        card = resolve_card(key, self.players[side]["secrets"], self.bans, self.map.get("environment",{}).get("night",False))
        target=self.players[side].get('last_copy_card')
        if key=='plant:模仿者' and 'secret:肆意模仿' in self.players[side]['secrets'] and target:
            copied=resolve_card(target,self.players[side]['secrets'],self.bans,self.map.get('environment',{}).get('night',False))
            card['cost']=copied['cost']-100
        return card

    def turn_plant(self, side, target_id, facing):
        if team_of(side)!='plant' or 'secret:转向' not in self.players[side]['secrets']:
            return '需要植物方携带转向秘籍'
        if isinstance(facing,bool) or not isinstance(facing,int) or facing not in (-1,1):
            return '转向方向无效'
        target=self._native_objects.get(target_id) if isinstance(target_id,str) else None
        if (target is None or target.get('_pvp_owner')!='plant' or
                '植物' not in target or target.get('植物血',0)<=0 or '死' in target):
            return '请选择己方存活植物'
        cell=target.get('坐标')
        members=[p for p in self.g['植物'] if p.get('_pvp_owner')=='plant'
                 and p.get('植物血',0)>0 and '死' not in p and p.get('坐标')==cell]
        if cell is None:members=[target]
        for plant in members:
            plant['方向']=facing
            # An ongoing asparagus sweep stores its launch orientation separately.
            if plant.get('_pvp_flying_mode')=='sweep':plant['_pvp_sweep_facing']=facing
        self._emit('plant_turned',side=side,entity=target_id,
                   entities=[p['_pvp_id'] for p in members],facing=facing)
        self._sync_public()
        return ''

    def teleport_hero(self, side, target_id):
        player=self.players[side]
        if self.avatars[side]['玩家血量']<=0:return '戴夫已阵亡'
        avatar=self.avatars[side]
        if avatar.get('_pvp_ice',0)>1000 or avatar.get('_pvp_butter',0)>0 or avatar.get('_pvp_stun',0)>0:
            return '冰冻、黄油或眩晕期间无法传送'
        remaining=player.get('teleport_ready_at',0)-self.time
        if remaining>0:return '传送冷却中：%.1f秒'%remaining
        target=self.units.get(target_id) if isinstance(target_id,str) else None
        team=team_of(side)
        if not target or target.get('hp',0)<=0 or target.get('side')!=team:
            return '请选择己方存活的植物或墓碑'
        if (team=='plant' and (target.get('card',{}).get('side')!='plant' or target.get('behavior')=='tentacle')) or (team=='zombie' and target.get('behavior')!='grave'):
            return '植物方只能传送至植物，僵尸方只能传送至墓碑'
        # 70005: plants in or on a flower pot or water basin are ordinary targets.
        tile=self.tile;spot=air_spot=None
        airborne=bool(target.get('card',{}).get('allow_air')) or (target.get('copy_card_id') or '')[6:] in AIR_PLANTS
        # Test the entire native Dave body (0.6 tiles wide, 1.5 high),
        # not just his feet. Nearby alternatives allow a low ceiling or step;
        # a plant raised on a flower pot has its ground one or two tiles lower.
        for up in (0,1,2,3,-1,-2):
            for dx in (0,-1,1,-2,2):
                x=(target['x']+dx*tile)%self.width;y=target['y']-up*tile
                if y<1.5*tile or y>=self.height:continue
                cols=range(int(math.floor((x-.3*tile)/tile)),int(math.floor((x+.3*tile)/tile))+1)
                rows=range(int(math.floor((y-1.5*tile)/tile)),int(math.floor((y-.01)/tile))+1)
                if any(self.cell((col+.5)*tile,(row+.5)*tile).get('solid') for col in cols for row in rows):continue
                if not any(self.cell(x+offset,y+1).get('solid') or self.cell(x+offset,y+1).get('water') for offset in (-.2*tile,0,.2*tile)):
                    # A plant in the air has nothing under it. Dave may still
                    # arrive beside it, clear of walls, and falls from there.
                    if airborne and air_spot is None:air_spot=(x,y)
                    continue
                spot=(x,y);break
            if spot:break
        if spot is None:spot=air_spot
        if spot is None:return '目标附近没有安全落点，未消耗传送冷却'
        avatar=self.avatars[side];avatar['玩家位置'][:]=[spot[0],spot[1],0.,0.]
        if team=='zombie':self.zsecrets.on_teleport(side)
        cooldown=self.rules.get('teleport_cooldown',20.)
        if team=='plant' and 'secret:闪现' in player['secrets']:
            cooldown*=.5
            avatar['玩家血量']+=4.
            self._emit('heal',target=side,amount=4.,kind='blink')
        if team=='zombie' and self.rally_for(side) is not None:
            # PvP65: a standing rally flag halves zombie Dave's teleport cooldown.
            cooldown*=.5
        player['teleport_ready_at']=self.time+cooldown
        self._emit('teleport',side=side,target=target_id,x=spot[0],y=spot[1])
        self._sync_public()
        return ''

    def native_shovel(self,side,x,y,right=False):
        if team_of(side)!='plant':return '只有植物方可使用铲子'
        if not finite(x) or not finite(y) or not 0<=x<self.width or not 0<=y<self.height or not isinstance(right,bool):
            return '铲除坐标无效'
        row,col=int(y//self.tile),int(x//self.tile)
        index=self.g['哪个无南瓜植物' if right else '哪个植物'](row,col)
        if index<0 or '死' in self.g['植物'][index]:return '这里没有可铲除的植物'
        obj=self.g['植物'][index]
        if obj.get('_pvp_owner','plant')!='plant':return '只能铲除己方植物'
        basin=obj.get('_pvp_content')=='水盆'
        if basin:
            # The native shovel contains template-specific conversions; a
            # basin instead restores its underlying cell exactly once.
            obj.update(植物血=0.,死=0)
            self.content.pvp70.remove_basin(obj)
            if right:
                # Fresh native construction, with no inherited HP/status or
                # placement cost/cooldown. Existing upper layers stay put.
                with self._ban_free_spawn():
                    pot=self.spawn('plant:花盆','plant',(col+.5)*self.tile,(row+1)*self.tile,
                                   obj.get('方向',1),parent={'id':obj.get('_pvp_id')})
                if pot is None:raise RuntimeError('水盆转换花盆失败')
                self._emit('basin_to_pot',source=obj.get('_pvp_id'),entity=pot['id'])
            self.native_cannon(side,cancel=True)
            self._emit('shovel',target=obj.get('_pvp_id'),side=side,right=right)
            self._sync_public()
            return ''
        saved={key:self.g.get(key) for key in ('event','sby','sbx')}
        try:
            self.g.update(event=SimpleNamespace(button=3 if right else 1),sby=row,sbx=col)
            with self.targets.context('zombie','plant','plants',obj):self.engine.execute('shovel')
        finally:self.g.update(saved)
        self.native_cannon(side,cancel=True)
        self._emit('shovel',target=obj.get('_pvp_id'),side=side,right=right)
        return ''

    def native_cannon(self, side, x=None, y=None, cancel=False):
        if team_of(side) != "plant":return "只有植物方可操作玉米炮"
        if cancel:
            self.g["拿中玉米炮"] = []
            self.players[side]["cannon_aim"] = None
            return ""
        if not finite(x) or not finite(y) or not 0<=x<self.width or not 0<=y<self.height:
            return "炮击坐标无效"
        self._select_hero(side)
        self.g.update(sbx=int(x//self.tile),sby=int(y//self.tile))
        selected = self.g["拿中玉米炮"]
        if selected:
            cannon = next((obj for obj in self.g["植物"] if obj["坐标"]==selected and
                           obj["植物"]=="玉米加农炮" and obj["植物血"]>0),None)
            if cannon is None or cannon["发射cd"] or cannon["发射动画"]:
                self.g["拿中玉米炮"] = []
                self.players[side]["cannon_aim"] = None
                return "玉米炮已失效或未装填完成"
            self.g["开炮"] = True
            self.engine.execute("cannon_fire")
            self._emit("cannon_fire",side=side,entity=cannon["_pvp_id"],x=x,y=y)
        else:
            self.engine.execute("cannon_select")
            if not self.g["拿中玉米炮"]:return "此处没有装填完成的玉米炮"
        self.players[side]["cannon_aim"] = list(self.g["拿中玉米炮"]) or None
        return ""

    def detonate_clown(self, side, uid):
        """PvP61: the owner clicks a live jack-in-the-box zombie to set it off.

        The native death branch explodes a clown still holding its box when
        its death counter reaches -300; jump straight to the frame before it so
        the original blast, knock-back and block damage run unchanged.
        """
        if not isinstance(uid, str):
            return "目标编号无效"
        z = self._native_objects.get(uid)
        if (z is not None and z.get("僵尸") != "小丑僵尸" and team_of(side) == "zombie"
                and self.zsecrets.seat_has(side, "自爆")):
            return self.zsecrets.self_destruct(side, uid)
        if z is None or z.get("僵尸") != "小丑僵尸" or z.get("血量", 0) <= 0 or "灰烬" in z:
            return "只能引爆存活的小丑僵尸"
        if self.targets.owner(z) != team_of(side):
            return "只能引爆己方小丑僵尸"
        if z.get("手持") != "玩偶匣":
            return "这只小丑僵尸已没有玩偶匣"
        z["血量"] = -299
        self._emit("clown_detonate", side=side, entity=uid)
        self._sync_public()
        return ""

    def placement(self, side, key, x, y, grave_id=None, copy_id=None):
        if team_of(side)=='zombie' and self.zsecrets.team_last_stand():
            from .balance import deathmatch_blocked
            if key in self.players[side]['deck'] and deathmatch_blocked(self._card(side,key)):
                return '最后攻势期间不能新增生产单位',None
        error, plan = self._placement_unranked(side, key, x, y, grave_id, copy_id)
        if not error and plan and key == "zombie:乌鸦":
            surcharge = self.zsecrets.crow_surcharge(side)
            if surcharge:
                plan = dict(plan, charge=plan["charge"] + surcharge)
                if self.players[side]["resource"] < plan["charge"]:
                    return "脑光不足（鸦群：每只稻草人 +%d）" % 50, None
        if error or not ranked_rules(self.rules) or not plan:
            return error, plan
        card = plan.get("card") or {}
        if card.get("category") == "secret":
            return error, plan
        if (team_of(side) == "zombie" and card.get("behavior") != "grave"
                and self.zsecrets.seat_has(side, "解除封印")):
            return error, plan
        hero = self.avatars[side]["玩家位置"]
        error = ring_error(card, hero, x, y, self.tile, self.width)
        return (error, None) if error else ("", plan)

    def _placement_unranked(self, side, key, x, y, grave_id=None, copy_id=None):
        if team_of(side) == "zombie" and key == "zombie:飞贼僵尸":
            return validate_thief_placement(self,side,key,x,y)
        if team_of(side) != "plant":return super().placement(side, key, x, y, grave_id, copy_id)
        native = NativePlacementRules(self.engine.root,self.map,make_native_placement_state(self.g),self.patch_namespace)
        return validate_native_placement(self,native,side,key,x,y,grave_id,copy_id)

    def deploy(self, side, key, x, y, grave_id=None, copy_id=None, facing=None):
        if side != team_of(side) or self.mode != DUEL:
            if self.team_mode and side in self.players and self.players[side]["hp"] <= 0:
                return "戴夫已阵亡，等待队友复活"
            self._acting_seat = side
            try:return self._deploy(side, key, x, y, grave_id, copy_id, facing)
            finally:self._acting_seat = None
        return self._deploy(side, key, x, y, grave_id, copy_id, facing)

    def _deploy(self, seat, key, x, y, grave_id=None, copy_id=None, facing=None):
        if self.mode in ('coop', 'pve'):
            from .pve import campaign_card_allowed, disabled_message
            coop = self.mode == 'coop'
            if isinstance(key, str) and key in CARDS and (
                    not campaign_card_allowed(key, coop) or
                    key == 'plant:模仿者' and isinstance(copy_id, str) and copy_id in CARDS
                    and not campaign_card_allowed(copy_id, coop)):
                return disabled_message(coop)
        error, plan = self.placement(seat, key, x, y, grave_id, copy_id)
        if error:return error
        side = team_of(seat)
        player, card = self.players[seat], plan["card"]
        direction = player["facing"] if facing is None else facing
        self._select_hero(seat)
        if plan.get("copy_card"):self.g["模仿"] = plan["copy_card"]["native_input_name"]
        entity = None
        if side == 'plant' and card['behavior'] == 'grass':
            cell = self.g['ditu'][plan['row']][plan['col']]
            cell['方块'] = card['terrain_kind']
            self._sync_terrain()
            self._emit('terrain_grass',row=plan['row'],col=plan['col'])
        elif side == "plant" and card["behavior"] == "coffee":
            self.g.update(sby=plan["row"], sbx=plan["col"], fx=direction)
            # One bean wakes every sleeper in its cell: the original query only
            # sees the non-pumpkin body, but PvP shells (忧郁藤蔓, 抓人草) sleep
            # too, and 密植 stacks several bodies.
            target = self.content.vines.coffee_target(plan["row"], plan["col"])
            if target < 0:
                self.engine.execute("coffee")
            else:
                lookup = self.g["哪个无南瓜植物"]
                self.g["哪个无南瓜植物"] = lambda row, col: target
                try:self.engine.execute("coffee")
                finally:self.g["哪个无南瓜植物"] = lookup
        else:
            entity = self.spawn(card, side, plan["x"], plan["y"], direction,
                                temporary=plan.get("temporary", False))
            if side == "zombie" and entity is None:
                return "未能生成该单位，未扣除脑光或冷却"
            if side == 'plant' and card.get('content') and entity is None:
                return "未能生成该植物，未扣除阳光或冷却"
            if entity and plan.get("grave_target"):
                self.gravebusters.attach(self._native_objects[entity["id"]],plan["grave_target"])
            if entity and plan.get("copy_card"):
                self._native_objects[entity["id"]]["_pvp_copy_card"] = plan["copy_card"]["id"]
        player["resource"] -= plan["charge"]
        player["stats"]["spent"] += plan["charge"]
        if side=="plant" and entity and card["category"] not in ("tool","secret") and card["behavior"] not in ("gravebuster","copy"):
            player["last_copy_card"]=key
        if (side == "plant" and entity and card["base_id"] == "plant:地刺" and
                "地刺" in card.get("native_secret_names", ())):
            self.g["地刺阳光"] = max(SPIKE_SECRET_MIN_COST,
                                   self.g.get("地刺阳光", plan["charge"]) - SPIKE_SECRET_STEP)
        player["cooldowns"][key] = self.time + deployment_cooldown(self._card(seat, key), self.deathmatch or side=='zombie' and self.zsecrets.team_last_stand())
        player.setdefault("cooldown_spans", {})[key] = player["cooldowns"][key] - self.time
        self._emit("deploy", side=seat, card=key, charge=plan["charge"],
                   entity=entity["id"] if entity else None, x=plan["x"], y=plan["y"],
                   grave=grave_id, facing=direction)
        if key in ("zombie:旗帜僵尸","zombie:黑旗帜僵尸") and entity:
            self._flag_reinforcements(entity)
        if key == BLOOM and entity and ranked_rules(self.rules):
            player["collect_locked_until"] = max(player.get("collect_locked_until", 0.), self.time + BLOOM_COLLECT_LOCK)
        if side == "zombie" and entity:
            self.zsecrets.on_deployed(entity, grave_id)
            if grave_id and self.zsecrets.seat_has(seat, "解除封印"):
                self.select_grave(seat, grave_id)     # deploying through a grave selects it
        if key == "zombie:乌鸦" and entity:
            if self.zsecrets.seat_has(seat, "鸦群"):self.zsecrets.crow_flock(entity, seat)
            else:self.content.pvp61.crow_echo(entity)
        self._sync_public()
        return ""

    def _flag_reinforcements(self, flag):
        # The summoned unit is not a card either side can withhold: the flag has
        # been paid for, and its whole value is the summon, so this resolves the
        # designation directly instead of through the ban-gated card lookup.
        key = "zombie:黑普通僵尸" if flag['card_id']=='zombie:黑旗帜僵尸' else "zombie:普通僵尸"
        key = self.zsecrets.flag_summon(flag) or key
        card = actual_card(key, self.players["zombie"]["secrets"],
                           self.map.get("environment",{}).get("night",False))
        graves = sorted((unit for unit in self.units.values() if unit["side"]=="zombie"
            and unit["behavior"]=="grave" and unit["hp"]>0),key=lambda unit:unit["id"])
        for grave in graves:
            facing = self.players["zombie"]["facing"]
            exit_position = self._grave_soldier_exit(card,"zombie",grave,facing)
            if exit_position is None or len(self.units)>=700:
                self._emit("flag_reinforcement_blocked",grave=grave["id"],reason="blocked_or_full")
                continue
            with self._ban_free_spawn():
                child = self.spawn(card,"zombie",*exit_position,facing=facing,temporary=True,parent=flag)
            if child is None:
                continue
            self._emit("flag_reinforcement",grave=grave["id"],source=flag["id"],entity=child["id"])

    @contextmanager
    def _ban_free_spawn(self):
        """A spawn the match grants through another card's own effect.

        A ban takes a card out of a player's reach - it empties the deck slot and
        blocks a direct deployment.  It cannot take away a unit the match hands
        out as part of a card that has already been paid for, because that would
        sell the flag zombie as a 175-brain no-op whenever its summoned unit was
        banned.  Only the match's own hand-outs run inside this.
        """
        self._spawn_ban_exempt += 1
        try:
            yield
        finally:
            self._spawn_ban_exempt -= 1

    def _unit_card(self, side, key):
        """The card of a unit that is already on the field, ban or no ban.

        Once such a unit exists the projection has to describe it, so this never
        raises: a banned card resolves to its own definition rather than
        aborting the whole per-tick projection.
        """
        if getattr(self, "sim_fastpath", False):
            # Fast path: resolution depends only on these inputs; every caller
            # still receives its own independent copy, as before.
            from .native_runtime import plain_clone, alias_free_plain
            memo = self.__dict__.setdefault("_unit_card_memo", {})
            night = self.map.get("environment",{}).get("night",False)
            memo_key = (side, key, tuple(self.players[side]["secrets"]), tuple(self.bans), night)
            entry = memo.get(memo_key)
            if entry is None:
                card = self._unit_card_resolved(side, key)
                entry = memo[memo_key] = (card, alias_free_plain(card))
                return plain_clone(card) if entry[1] else copy.deepcopy(card)
            return plain_clone(entry[0]) if entry[1] else copy.deepcopy(entry[0])
        return self._unit_card_resolved(side, key)

    def _unit_card_resolved(self, side, key):
        try:
            return self._card(side, key)
        except ValueError:
            return actual_card(key, self.players[side]["secrets"],
                               self.map.get("environment",{}).get("night",False))

    def spawn(self, card, side, x, y, facing=1, temporary=False, parent=None, parent_attack=None):
        key = card if isinstance(card, str) else card["id"]
        if key=='plant:抓人草触手':
            raise ValueError('抓人草触手只能由存活本体生成')
        card = self._unit_card(side, key) if self._spawn_ban_exempt else self._card(side, key)
        if card.get('behavior') == 'grass':
            raise ValueError('草坪是地形工具，必须通过合法放置建立原生方块')
        if self.deathmatch and deathmatch_blocked(card):return None
        parent_native = ((self._native_objects.get(parent.get('id')) or parent)
                         if isinstance(parent,dict) else None)
        if (side == 'zombie' and card['behavior'] != 'grave'
                and not self.scripted_spawn_budget.can_spawn(source=parent_native)):
            return None
        if key=="zombie:残骸墓碑（非生产）" and (not parent or parent.get("card_id")!="zombie:墓碑吞噬者僵尸"):
            raise ValueError("残骸墓碑只能由墓碑吞噬者僵尸死亡产生")
        with self._summon_hero(side):
            if card["behavior"] == "grave":
                created = self.engine.spawn_zombie("普通僵尸", x, y, facing,
                                                  factory=self._grave_native_factory)
                if not created:return None
                native = created[0]
                # A grave set into a petrified vine rests on the vine, not on a
                # duck ring; the vine itself lies flat on the water surface.
                on_vine = any(u["side"]=="zombie" and u["card"].get("shell") and u["hp"]>0
                              and abs(wrap_delta(u["x"],x,self.width))<self.tile*.5 and abs(u["y"]-y)<self.tile*.5
                              for u in self.units.values())
                floating = (self.cell(x,y+1).get("water",False) and not card.get("shell")
                            and (card.get("grave_surface")=="water" or not on_vine))
                native.update(出场=500, 血量=card["hp"], 位置=[x,y,0.,0.], _pvp_grave=True,
                              _pvp_floating=floating)
            elif side == "plant":
                row, col = int(round(y/self.tile))-1, int(x/self.tile)
                # Admission already checked this actual card. Its native template
                # may be banned independently (e.g. primal pea versus ordinary pea).
                created = self.engine.spawn_plant(card["native_input_name"], row, col, facing,
                    factory=self._plant_native_factory if card.get('content') or card.get('expansion') else None)
                if not created:
                    self._sync_terrain()
                    return None
                native = created[0]
                self._configure_plant(native,card)
            else:
                created = self.engine.spawn_zombie(card["native_input_name"], x, y, facing,
                    # Public/card/content summons are not the native giant throw
                    # call site. A stale loop index must not steal a riding helmet.
                    factory=self._grave_native_factory if card.get('expansion') or card['native_input_name']=='小鬼僵尸' else None)
                if not created:return None
                native = created[0]
                if card["native_input_name"] != "飞贼僵尸":native["出场"] = 400
                self.expansion.configure(native,card)
            self._register(native, card, side, temporary, parent, parent_attack)
            if key == "zombie:投篮车僵尸":
                native["篮球"] = 20
            self.content.configure(native,card)
            if side == "zombie" and getattr(self, "zsecrets", None) is not None:
                self.zsecrets.on_spawn(native, card, parent)
            self._sync_public()
            return self.units[native["_pvp_id"]]

    def _configure_plant(self, native, card):
        """Direct planting and native copies receive the same PvP values."""
        self._apply_pvp_health(native)
        self._apply_pvp_hardening(native)
        if card['base_id']=='plant:原始土豆地雷':
            native['植物血']=card['hp'];native['植物血上限']=card['hp']
        if card["base_id"] in ("plant:土豆地雷", "plant:原始土豆地雷"):
            emergence = (PRIMAL_ARM_SECONDS if card["base_id"] == "plant:原始土豆地雷"
                         else MINE_EMERGENCE_SECONDS) * 250
            if "地雷" in card.get("native_secret_names",[]):
                emergence /= 2
            native["埋藏"] = emergence

    def _register(self, native, card, side, temporary=False, parent=None, parent_attack=None):
        if card['base_id']=='zombie:墓碑吞噬者僵尸' and not native.get('_pvp72_health'):
            native['血量']=300.;native['_pvp72_health']=True
            observed=self.patch.ns.get('__pvz_sb_K_ZOMBIE_OBSERVED_MAX_HP')
            if observed:native[observed]=300.
        if side == "zombie" and card["base_id"] == "zombie:伴舞僵尸":
            native["移速"] = 60.
        # A child can fire in one of the remaining native substeps before its
        # first network projection. Preserve the ID already assigned by the
        # source hook so those projectiles remain traceable to the same unit.
        uid = native.get("_pvp_id") or self._id("u")
        if native.get("_pvp_grave"):
            native["_pvp_anchor"]=tuple(native["位置"][:2])
            # Recorded once: a non-producing grave must never accrue a clock.
            native["_pvp_producer"]=bool(card.get("producer"))
        native.update(_pvp_id=uid, _pvp_card=card["id"], _pvp_owner=side,
                      _pvp_temporary=temporary, _pvp_max_hp=native.get("植物血", native.get("血量", 0)),
                      _pvp_armor_max=native.get("防具血量", 0), _pvp_born=self.time)
        if self.mode != DUEL:
            seat = self._acting_seat if team_of(self._acting_seat) == side else None
            if seat is None and parent:
                parent_native = self._native_objects.get(parent.get("id")) or parent
                seat = parent_native.get("_pvp_seat")
            native["_pvp_seat"] = seat or side
        if parent:
            parent_native = self._native_objects.get(parent.get('id')) or parent
            self.scripted_spawn_budget.inherit(native,parent_native)
        elif self.scripted_spawn_budget.enabled and hasattr(self,'_scripted_spawn_wave'):
            native['_pvp_wave_index']=self._scripted_spawn_wave
        self._native_objects[uid] = native
        self._emit("spawn", entity=uid, card=card["id"], side=side,
                   source_entity=uid, parent_entity=parent.get("id") if parent else None,
                   parent_attack=parent_attack, native=True)

    def _install_star_damage(self):
        """Give the patch's original star collision scan its projectile source.

        That scan calls the damage callback after the native entity phase, when
        no PvP target context is active. Preserve its geometry, pierce list and
        iteration order; establish source ownership only for each actual hit.
        The wrapper lives only inside the star scan. Other native damage calls
        retain their original stack and callback.
        """
        scan=self.patch.ns['__pvz_sb_star_damage_scan']
        scan_code=scan.__code__
        def impact(star,index,facing,amount,damage):
            with self.targets.context('zombie','plant','entities',source=star):
                return damage(index,facing,amount)
        def pvp_scan(game):
            damage=game['伤害僵尸']
            def star_hit(index,facing,amount):
                frame=sys._getframe(1)
                star=frame.f_locals.get('entity') if frame.f_code is scan_code else None
                if isinstance(star,dict) and star.get('名')=='星星':
                    return impact(star,index,facing,amount,damage)
                return damage(index,facing,amount)
            game['伤害僵尸']=star_hit
            try:
                return scan(game)
            finally:
                game['伤害僵尸']=damage
        self.patch.ns['__pvz_sb_star_damage_scan']=pvp_scan
        self.g['_pvp_star_damage']=impact

    def _apply_pvp_health(self, native):
        """Level a deployed plant to the PvP health override.

        The engine's template health stays captured verbatim in
        `NATIVE_CARD_EVIDENCE` (a parity test re-executes the engine's creation
        functions against it), so a PvP health change cannot live in that table -
        it is applied to the deployed native object here instead. Hardening is
        folded in, because it scales whatever base health the plant ended up
        with.
        """
        name = native.get("植物") if isinstance(native, dict) else None
        base = HEALTH.get("plant:" + name) if name else None
        if base is None or native.get("_pvp_health_form") == name:
            return
        if "secret:硬化" in self.team_secrets["plant"]:
            base = base * HARDENING_HP_FACTOR if base > HARDENING_MIN_BASE_HP else base + 3
        if name == "路灯花" and "secret:光疗" in self.team_secrets["plant"]:
            base *= 2
        native["植物血上限"] = base
        native["植物血"] = base
        native["_pvp_health_form"] = name

    def _apply_pvp_hardening(self, native):
        """Apply hardening once per native plant form: base-6 plants gain a flat
        +3, anything above gains the 25% factor; never the old-mode blanket +3.

        Plants carrying a PvP health override already folded hardening into
        `_apply_pvp_health`, so they are skipped here to avoid overwriting the
        override with the engine's base number.  Both health fields are written:
        the engine's own `种植植物` sets `植物血上限` from the post-hardening
        `植物血`, and the health bar draws from `植物血上限`, so writing only
        `植物血` left hardened plants above 100% on the bar.
        """
        if "secret:硬化" not in self.team_secrets["plant"]:
            return
        name = native.get("植物") if isinstance(native, dict) else None
        if not name or native.get("_pvp_hardening_form") == name:
            return
        if "plant:" + name in HEALTH:
            return
        base_hp = CARDS.get("plant:" + name, {}).get("native_hp")
        if base_hp is None:
            native["_pvp_hardening_form"] = name
            return
        if base_hp > HARDENING_MIN_BASE_HP:
            base_hp *= HARDENING_HP_FACTOR
        elif base_hp == HARDENING_MIN_BASE_HP:
            base_hp += 3
        else:
            base_hp = None
        if base_hp is not None:
            native["植物血上限"] = base_hp
            native["植物血"] = base_hp
        native["_pvp_hardening_form"] = name

    def wake_grave(self, side, uid):
        return self.grave_idle.wake_input(side, uid)

    def _sync_terrain(self):
        """Publish real terrain changes only.

        A planted flower pot keeps the native root-animation counter 根动画 in
        its terrain cell and advances it every frame. Nothing outside the
        engine reads it, yet publishing it bumped the terrain revision on
        every tick, which resent the whole map in every snapshot.
        """
        changed = False
        belts = set()
        content = getattr(self, 'content', None)
        head_only = content.pvp70.head_only_cells() if content is not None and hasattr(content, 'pvp70') else ()
        for y, row in enumerate(self.g["ditu"]):
            for x, cell in enumerate(row):
                if cell.get('_pvp_belt'):belts.add(y*BELT_STRIDE+x)
                if TERRAIN_ANIMATION_KEY in cell:
                    cell = {k: v for k, v in cell.items() if k != TERRAIN_ANIMATION_KEY}
                if (y, x) in head_only:
                    # PvP70: the mark a floating tentacle head carries for
                    # native zombie contact is not terrain occupancy.
                    cell = {k: v for k, v in cell.items() if k != "植物"}
                old = self.map["tiles"][y][x]
                if old.get("native") != cell:
                    self.map["tiles"][y][x] = _cell(cell, self.g["kong"])
                    changed = True
        if changed:self.terrain_revision += 1
        content = getattr(self, 'content', None)
        if content is not None:content.pvp64.set_belts(belts)

    def _sync_public(self, terrain=True):
        for obj in self.g["植物"]:
            self._apply_pvp_hardening(obj)
        for side, native in self.avatars.items():
            player = self.players[side]
            x,y,vx,vy = native["玩家位置"]
            player.update(x=x,y=y,vx=vx*250,vy=vy*250,hp=native["玩家血量"],
                          poison_level=native.get('_pvp_poison',{}).get('level',0),
                          frozen=native.get("_pvp_ice",0)>1000,slowed=0<native.get("_pvp_ice",0)<=1000 or native.get('_pvp_cold_until',0)>self.engine.native_tick,buttered=native.get("_pvp_butter",0)>0,
                          grounded=bool(native.get("landing_result")),facing=native["玩家方向"],
                          jumps=native["玩家跳跃"],jump_cap=self._jump_cap(side) or 2,native_pose=copy.deepcopy(native))
        for obj in self.g["植物"] + self.g["僵尸"]:
            if obj.get("_pvp_id") in self._native_objects or obj.get("_pvp_hero"):continue
            side = "plant" if "植物" in obj else "zombie"
            key = side+":"+obj.get("植物",obj.get("僵尸"))
            if key in CARDS:
                try:card = self._card(side,key)
                except ValueError:continue
                self._register(obj,card,side,True)
        live = {id(obj) for obj in self.g["植物"] + self.g["僵尸"] + getattr(self,"_suspended_graves",[])}
        units = {}
        for uid, obj in list(self._native_objects.items()):
            if id(obj) not in live:
                self._emit("death", entity=uid, side=obj["_pvp_owner"], card=obj["_pvp_card"])
                if self.zsecrets.enabled:self.zsecrets.on_unit_gone(obj)
                consumed_bloom=obj.get('_pvp_content')=='黄金蓓蕾' and obj.get('_pvp_effect_done',False)
                if CARDS[obj["_pvp_card"]].get("producer") and not consumed_bloom:
                    self.players[obj.get("_pvp_seat",obj["_pvp_owner"])]["stats"]["producer_lost"] += 1
                del self._native_objects[uid]
                continue
            side = "plant" if "魅惑" in obj else obj["_pvp_owner"]
            card = self._unit_card(obj["_pvp_owner"], obj["_pvp_card"])
            if "坐标" in obj:
                row, col = obj["坐标"]
                x,y,vx,vy = (col+.5)*self.tile,(row+1)*self.tile,0.,0.
            else:x,y,vx,vy = obj["位置"]
            hp = obj.get("植物血",obj.get("血量",0))
            units[uid] = dict(id=uid,card=card,card_id=card["id"],side=side,owner=side,
                original_owner=obj["_pvp_owner"],current_owner=side,source_entity=uid,
                native_side=obj["_pvp_owner"],x=x,y=y,vx=vx*250,vy=vy*250,w=self.tile*.6,
                h=self.tile*(1.5 if "僵尸" in obj and not obj.get("_pvp_grave") and card.get('behavior')!='tentacle' else 1),
                hp=hp,max_hp=obj["_pvp_max_hp"],facing=obj.get("方向",1),
                armor_hp=obj.get("防具血量",0),armor_max=obj["_pvp_armor_max"],
                behavior=card["behavior"],mobile="僵尸" in obj and not obj.get("_pvp_grave") and not obj.get('_pvp_orphan_barrel'),
                flying=bool(card.get("flying")),burrowed="出土" in obj,temporary=obj["_pvp_temporary"],
                awake="睡觉" not in obj,grounded=False,born=0,progress=0,native=True,floating=bool(obj.get("_pvp_floating")),
                frozen=obj.get("冰冻",0)>1000,slowed=0<obj.get("冰冻",0)<=1000,
                buttered=obj.get("黄油",0)>0,stunned=obj.get('眩晕',0)>0,production_rate=obj.get("_pvp_production_rate",1.),mature=obj.get("_pvp_mature",False),
                torch_blue=bool(obj.get("_pvp_card")==PETRIFIED_TORCH_KEY and (self.zsecrets.has("暴怒") or "蓝火" in self.g["秘籍"])),
                drowsy=grave_drowsy(obj) or tick_asleep(obj,self.engine.native_tick) or bool(obj.get('_pvp_coop_dormant')),
                drowsy_level=1. if tick_asleep(obj,self.engine.native_tick) or obj.get('_pvp_coop_dormant') else round(grave_drowsy_level(obj),3))
            if obj.get('_pvp_copy_card'):
                units[uid]['copy_card_id'] = obj['_pvp_copy_card']
            if '_pvp_seat' in obj:units[uid]['seat'] = obj['_pvp_seat']
            if obj.get('_pvp_grave'):
                units[uid]['first_soldier_ready'] = bool(self.zsecrets.has('头兵') and not obj.get('_pvp_zs_first_used'))
            if obj.get('_pvp_zs_speed'):
                units[uid]['secret_speed_bonuses']=dict(obj['_pvp_zs_speed'])
            units[uid]['poison_level']=obj.get('_pvp_poison',{}).get('level',0)
            if obj.get('_pvp_orphan_barrel'):
                units[uid].update(card=dict(card,name='滚桶',asset='滚桶'),w=self.tile*1.2,h=self.tile*1.2,
                                  orphan_barrel=True,armor_hp=0.,armor_max=0.)
        self.units = units
        if terrain:self._sync_terrain()


    # ------------------------------------------------------------ PvP66 teams
    def _team_init(self, director):
        """Seat bookkeeping for team/PvE modes; a no-op for the duel."""
        self._multi_plant = len(self.team_seats("plant")) > 1
        self.coins = 0
        self.fallen_count = 0
        self._multi_target = self.mode != DUEL and (self._multi_plant or len(self.team_seats("zombie")) > 1)
        self._alias_seat = "plant"
        self._switch_state = None
        self._seat_tracking = {}
        self.revive = {seat: 0. for seat in self.seats}
        self.down_since = {}
        # Co-op AI seats set by the room after construction (see _ai_subsidy).
        self.ai_subsidy_seats = ()
        self._ai_subsidy_paid = 0
        self.director = None
        if director is not None:
            self.command = "attack"
            self.director = director
            director.bind(self)

    def _ai_subsidy(self):
        """Co-op AI sun subsidy on the battle clock (paid at 8 s, 16 s, ...)."""
        due = int(self.time // AI_SUBSIDY_INTERVAL)
        while self._ai_subsidy_paid < due:
            self._ai_subsidy_paid += 1
            amount = 25 if self.mode=='duo' else ai_subsidy_amount(self._ai_subsidy_paid * AI_SUBSIDY_INTERVAL)
            for seat in self.ai_subsidy_seats:
                player = self.players.get(seat)
                if player is None:
                    continue
                player["resource"] += amount
                player["stats"]["earned"] += amount
                self._emit("ai_subsidy", side=seat, amount=amount)

    def zombie_hero_proxies(self):
        """Target records of the zombie Daves taking part in this match."""
        if not self.scripted and not self.team_mode:
            return [self.targets.hero_proxy("zombie")]
        return [self.targets.hero_proxy(seat) for seat in self.team_seats("zombie")]

    def _set_alias(self, seat):
        """Let the faction key "plant" address another plant seat's Dave.

        The original zombie and projectile regions know one global player.
        Swapping the two plant entries (a bijection, so every Dave is still
        reachable under exactly one key) lets them serve a second Dave without
        touching their code; each avatar carries its true seat in _pvp_seat.
        """
        if seat == self._alias_seat:
            return
        states = self.hero_states
        for key in self.team_seats("plant"):
            self.avatars[key] = states[key]
        if seat != "plant":
            self.avatars["plant"], self.avatars[seat] = states[seat], states["plant"]
        self._alias_seat = seat

    def _nearest_plant_seat(self, x, y):
        best = None
        for seat in self.team_seats("plant", alive=True):
            hx, hy = self.hero_states[seat]["玩家位置"][:2]
            key = (math.hypot(wrap_delta(x, hx, self.width), y - hy), seat)
            if best is None or key < best:
                best = key
        return best[1] if best else "plant"

    @contextmanager
    def _plant_switching(self, phase):
        """Per-unit choice of the plant Dave inside one original region."""
        from .native_physics import TRACKING_KEYS
        entry = self._nearest_plant_seat(*self.hero_states["plant"]["玩家位置"][:2])
        self._set_alias(entry)
        gate_key = "_pvp_zombie_gate" if phase == "zombies" else "_pvp_entity_gate"
        roster_key = "僵尸" if phase == "zombies" else "实体"
        previous = self.g[gate_key]
        baseline = {key: self.g[key] for key in TRACKING_KEYS if key in self.g}
        self._switch_state = dict(entry=entry, track=None)

        def team_gate(_previous=previous):
            obj = self.g[roster_key][self.g["l"]]
            position = obj.get("位置")
            if position is not None:
                self._switch_plant(self._nearest_plant_seat(position[0], position[1]-self.tile*.5))
            if phase == "zombies":
                self._switch_tracking(obj)
            _previous()
        self.g[gate_key] = team_gate
        try:
            yield
        finally:
            self.g[gate_key] = previous
            self._switch_state = None
            if phase == "zombies":
                self.g.update(baseline)
            self._set_alias("plant")

    def _switch_plant(self, seat):
        """Move the global player of an active context to another plant Dave."""
        if seat == self._alias_seat:
            return
        # The slot still holds the previous body's temporary chase destination
        # until its own gate finishes, which happens after this switch. Commit
        # that here and one Dave's goal becomes the other's position - the
        # co-op pair ends on one spot, sunk and bobbing (report 2026-10-15).
        self.content.release_pending_destination()
        from .native_targets import _COMBAT_HERO_KEYS
        g = self.g
        current = self.avatars["plant"]
        for key in _COMBAT_HERO_KEYS:
            if key in g:
                current[key] = g[key]
        self._set_alias(seat)
        keys = self.targets.context_keys
        g.update({key: value for key, value in self.avatars["plant"].items() if key in keys and key != "秘籍"})

    def _switch_tracking(self, z):
        """Chase field of the Dave this zombie follows or hunts."""
        if '魅惑' in z or not self._seat_tracking:
            return
        if self.command_for(z) == "follow":
            seat = z.get("_pvp_seat") if z.get("_pvp_seat") in self.present else "zombie"
        else:
            seat = self.avatars["plant"].get("_pvp_seat", "plant")
        state = self._switch_state
        if seat == state["track"] or seat not in self._seat_tracking:
            return
        self._restore_rally_tracking()
        if state["track"] is not None:
            saved = self._seat_tracking[state["track"]]
            for key in saved:
                if key in self.g:
                    saved[key] = self.g[key]
        tracking = self._seat_tracking[seat]
        self.g.update(tracking)
        if getattr(self, "_rally_tracking_base", None):
            self._rally_tracking_base = {key: tracking[key] for key in self._rally_tracking_base if key in tracking}
        state["track"] = seat

    def _switch_back(self):
        """Return to the region's entry Dave before its context commits."""
        if self._switch_state is not None:
            self._switch_plant(self._switch_state["entry"])

    def _team_tracking(self):
        """Persistent chase fields per Dave; returns the seat left in globals."""
        from .native_physics import TRACKING_KEYS
        if self.mode == DUO:
            seats=list(self.team_seats('zombie')) + list(self.team_seats('plant',alive=True) or self.team_seats('plant'))
            mode=None
        elif self.command == "follow":
            seats = self.team_seats("zombie", alive=True) or self.team_seats("zombie")
            mode = "我是僵尸"
        else:
            seats = self.team_seats("plant", alive=True) or self.team_seats("plant")
            # A wave has no zombie player ordering a plant raid. Normal PvP
            # target selection lets an unexpired split chase a producer left
            # at the old spawn even after both Daves have moved away.
            mode = "我是僵尸" if self.scripted else "正常模式"
        if not seats:
            seats = ["zombie" if self.command == "follow" else "plant"]
        self._seat_tracking = {seat: state for seat, state in self._seat_tracking.items() if seat in seats}
        # All these fields read one unchanged terrain. Share only this read
        # batch; native world blocks and unit actions run after the scope ends.
        shared = self.engine.physics.flood_geometry_shared
        previous = self.g.get('_pvp_flood_geometry')
        if shared:self.g['_pvp_flood_geometry'] = {}
        try:
            for seat in reversed(seats):
                state = self._seat_tracking.get(seat)
                if state:
                    self.g.update(state)
                else:
                    self.engine.physics.initialize_tracking(self.hero_states[seat])
                if self.scripted and team_of(seat) == "plant":
                    # Suppressing plant selection alone retains 目标位置.
                    # Aim the second native field at this Dave's actual feet
                    # too; neither native split branch may lead back to spawn.
                    # Keep the persistent per-seat queues and C++ flood path:
                    # no extra flood, per-zombie goal or borrowed avatar slot.
                    x, y = self.hero_states[seat]["玩家位置"][:2]
                    self.g["目标位置"] = [int((y-.5*self.tile)//self.tile), int(x//self.tile)]
                self.engine.physics.update_tracking(self.hero_states[seat], mode or ('我是僵尸' if team_of(seat)=='zombie' else '正常模式'))
                self._seat_tracking[seat] = {key: self.g[key] for key in TRACKING_KEYS if key in self.g}
        finally:
            if shared:
                if previous is None:self.g.pop('_pvp_flood_geometry',None)
                else:self.g['_pvp_flood_geometry']=previous
        return seats[0]

    def _ladder_support_request(self):
        """Original ti/metal/charm/cooldown conditions; no routing changes."""
        if self.scripted and self.director is not None and self.g['梯子尸数']>0 and self.g['梯子cd']==0:
            z=self.g['僵尸'][self.g['l']]
            if z.get('僵尸')!='梯子僵尸' and self.g.get('ti') and '魅惑' not in z:
                self.director.request_ladder(self,z)
        return True

    def _finish_sun_source(self):
        pending = self._sun_source_start
        if pending is not None:
            start, seat = pending
            for sun in self.g['阳光球'][start:]:
                self._native_sun_seats[id(sun)] = seat
            self._sun_source_start = None

    def _sun_owner(self, sun):
        """The plant seat whose producer dropped this native sun."""
        seat = self._native_sun_seats.pop(id(sun), None)
        if seat in self.present:
            return seat
        x, y = sun[1][0], sun[1][1]
        best = None
        for plant in self.g["植物"]:
            if plant.get("植物") not in self.g["产光植物"] or "坐标" not in plant:
                continue
            row, col = plant["坐标"]
            px, py = (col+.5)*self.tile, (row+.5)*self.tile
            key = (math.hypot(wrap_delta(x, px, self.width), y-py), plant.get("_pvp_id", ""))
            if best is None or key < best[0]:
                best = (key, plant)
        seat = best[1].get("_pvp_seat") if best else None
        return seat if seat in self.present else "plant"

    def _shared_collector(self, resource):
        """First standing plant Dave touching a shared (sky) sun."""
        for seat in self.team_seats("plant", alive=True):
            player = self.players[seat]
            if ('secret:阳光' in player['secrets'] or
                    math.hypot(wrap_delta(resource["x"], player["x"], self.width),
                               resource["y"]-player["y"]+30) < 60*sun_scale(resource["amount"])):
                return seat
        return None

    def _auto_shared_sky(self, rid):
        """Full-auto sky sun pays both plant seats once; producer sun stays personal."""
        resource=self.resources.get(rid)
        seats=self.team_seats('plant')
        if (not resource or resource.get('source')!='sky' or len(seats)!=2
                or not any('secret:阳光' in self.players[s]['secrets'] for s in seats)):
            return False
        self.resources.pop(rid)
        self._sun_motion.pop(rid,None)
        for seat in seats:
            player=self.players[seat]
            player['resource']+=15
            player['stats']['earned']+=15
            self._emit('income',side=seat,amount=15,source='sky',resource_id=rid,shared_auto=True)
        return True

    def _float_body(self, avatar):
        """A teammate's recoverable body rises to the connected water surface."""
        position=avatar['玩家位置'];x,y=position[:2]
        if not self.cell(x,y).get('water') and not self.cell(x,y-self.tile*.4).get('water'):
            avatar.pop('_pvp_floating_body',None)
            return False
        row=max(0,min(len(self.map['tiles'])-1,int(y//self.tile)))
        if not self.cell(x,row*self.tile+1).get('water'):row=max(0,row-1)
        while row>0 and self.cell(x,(row-1)*self.tile+1).get('water'):row-=1
        surface=(row+.45)*self.tile
        position[1]=max(surface,y-self.tile*2/250.) if y>surface else min(surface,y+self.tile/250.)
        position[2:]=[0.,0.]
        avatar['_pvp_floating_body']=True
        return True

    def _collect(self, rid, collector=None):
        resource = self.resources.get(rid)
        if resource and resource.get("coin"):
            # PvE coins: one team purse, never sun.
            self.resources.pop(rid, None)
            self._sun_motion.pop(rid, None)
            self.coins += resource["amount"]
            seat = collector or resource["side"]
            if seat in self.players:
                self.players[seat]["stats"]["coins"] = self.players[seat]["stats"].get("coins", 0) + resource["amount"]
            self._emit("coin", side=seat, amount=resource["amount"], resource_id=rid)
            return None
        if collector is None:
            return super()._collect(rid)
        if resource:
            resource["side"] = collector
        return super()._collect(rid)

    def drop_coin(self, amount, x, y, kind="coin"):
        """A PvE coin or money bag that falls like a sun; either Dave picks it up."""
        rid = self.resource("plant", amount, x, y, "coin")
        self.resources[rid].update(shared=True, coin=kind)
        return rid

    def _touching(self, a, b):
        ax, ay = a["玩家位置"][:2]
        bx, by = b["玩家位置"][:2]
        return (abs(wrap_delta(ax, bx, self.width)) <= self.tile*TOUCH_RANGE_X
                and abs(ay-by) <= self.tile*TOUCH_RANGE_Y)

    def _team_step(self, elapsed):
        """Help-up, revive and the team/PvE result, once per room step."""
        if self.team_mode:
            for seat in self.seats:
                avatar = self.hero_states[seat]
                helpers = [mate for mate in self.team_seats(team_of(seat), alive=True)
                           if mate != seat and self.hero_states[mate].get("玩家倒地", 0) <= 0
                           and self._touching(avatar, self.hero_states[mate])]
                if avatar["玩家血量"] <= 0:
                    if seat not in self.down_since:
                        self.down_since[seat] = self.time
                        self.fallen_count += 1
                        self._emit("hero_fallen", side=seat)
                    self.revive[seat] = self.revive[seat]+elapsed if helpers else 0.
                    if self.revive[seat]+1e-9 >= REVIVE_SECONDS:
                        self._revive(seat, helpers[0])
                else:
                    self.revive[seat] = 0.
                    if helpers and avatar.get("玩家倒地", 0) > 0 and avatar.get("玩家恢复", 0) < NATIVE_RISE_FRAMES:
                        # A teammate's touch stands a knocked-down Dave up at once.
                        avatar["玩家恢复"] = NATIVE_RISE_FRAMES
                        self._emit("hero_helped", side=seat, helper=helpers[0])
            self._sync_public(terrain=False)
        if self.director is not None:
            self.director.step(self)
        if self.result:
            return
        standing = {team: [seat for seat in self.team_seats(team) if self.players[seat]["hp"] > 0]
                    for team in ("plant", "zombie")}
        if self.scripted:
            if not standing["plant"]:
                self.result = dict(winner="zombie", reason="hero_death", tick=self.tick)
            elif self.director is not None and self.director.cleared():
                self.result = dict(winner="plant", reason="waves_cleared", tick=self.tick)
        else:
            fallen = [team for team in ("plant", "zombie") if not standing[team]]
            if fallen:
                self.result = dict(winner="draw" if len(fallen) == 2 else ("zombie" if fallen[0] == "plant" else "plant"),
                                   reason="hero_death", tick=self.tick)
        if self.result:
            if self.scripted:
                self.result["coins"] = self.coins
                self.result["fallen"] = self.fallen_count
            self._emit("result", **self.result)

    def _revive(self, seat, helper):
        avatar = self.hero_states[seat]
        hp = round(avatar["_pvp_max_hp"]*REVIVE_HP_FRACTION, 1)
        avatar.update(玩家血量=hp, 玩家倒地=0, 玩家恢复=0, 玩家受伤=0, _pvp_previous_hp=hp,
                      _pvp_last_damage=self.engine.native_tick/250.)
        position = self.hero_states[helper]["玩家位置"]
        avatar["玩家位置"][:] = [position[0], position[1], 0., 0.]
        self.revive[seat] = 0.
        self.down_since.pop(seat, None)
        self.players[seat]["immune_until"] = self.time+2.
        self._emit("hero_revived", side=seat, helper=helper, hp=hp)
        self._sync_public()

    def team_snapshot(self):
        value = dict(revive={seat: round(progress/REVIVE_SECONDS, 3) for seat, progress in self.revive.items() if progress > 0},
                     fallen=sorted(self.down_since), coins=self.coins)
        if self.director is not None:
            value["waves"] = self.director.snapshot()
            if getattr(self.director,'cycle',None):value['daylight']=self.director.cycle.snapshot()
        return value

    # Teammates share one draft; graves of either zombie seat serve both.

    def snapshot(self, include_map=False, copy_state=True):
        value = super().snapshot(include_map, copy_state)
        if self.mode != DUEL:
            value.update(mode=self.mode,seats=list(self.seats),team=self.team_snapshot())
        if self.mode == DUO:
            value.update(commands=dict(self.commands),rally_points=copy.deepcopy(self.rally_points))
        if self.zsecrets.enabled:
            value["zsecrets"] = dict(pickups=self.zsecrets.public_pickups(),
                                     effects=[dict(e) for e in self.zsecrets.effects if e['until']>self.time],
                                     last_stand={seat: max(0., until-self.time) for seat, until in self.zsecrets.last_stand.items()})
        value.update(engine="original-native-250hz",native_tick=self.engine.native_tick,
                     # Recorder frames are immutable once finished (copy-once).
                     native_frame=self._frame,
                     native_placement_state=make_native_placement_state(self.g),audio=self.audio.snapshot())
        value['pvp70']=dict(projectiles=copy.deepcopy(self.content.pvp70.shots),
                           tentacles=[dict(id=z['_pvp_id'],parent=z['_pvp_parent'],phase=z['_pvp_head_phase'],
                                           clock=z['_pvp_head_clock'],target=z.get('_pvp_head_target'))
                                      for z in self.g['植物'] if z.get('_pvp_content')=='抓人草触手' and z.get('植物血',0)>0 and '死' not in z])
        return value

    def _emit(self,event,**data):
        super()._emit(event,**data)
        if hasattr(self,'audio'):self.audio.event(event,data)

    def close(self):
        from . import gc_policy
        gc_policy.release(id(self))
        if hasattr(self,'scripted_spawn_budget'):self.scripted_spawn_budget.pending.clear()
        if hasattr(self,"jobs"):self.jobs.close()
        if hasattr(self,"gravebusters"):self.gravebusters.close()
        if hasattr(self,"patch"):self.patch.close()
        super().close()


def _install_native():
    """C++ _tracking_gate (pvpnative_gates.cpp); same calls in the same order."""
    from . import cppcore
    native = cppcore.native_for(("battle_tracking_gate", NativeBattle._tracking_gate.__code__))
    if native is None or not hasattr(native, "battle_tracking_gate"):
        return
    NativeBattle._tracking_gate = native.method(native.battle_tracking_gate)


_install_native()


def _install_native_zgate(battle):
    """C++ _rally_zombie_gate with the ordinary-zombie gate chain
    (pvpnative_zgate.cpp). Installed once per class, on its first battle,
    when every Python body of the chain still matches its reference."""
    cls = NativeBattle
    if "_pvp_zgate_checked" in cls.__dict__:
        return
    cls._pvp_zgate_checked = True
    from . import cppcore, native_expansion
    from .native_content import NativeContent
    from .native_september_content import SeptemberContent
    from .pvp56_zombies import PvP56Zombies
    from .pvp64_content import PvP64Content as P
    import types
    wrapper = battle._native_zombie_gate
    if not isinstance(wrapper, types.FunctionType):
        return
    E, C, S, Z = native_expansion.NativeExpansion, NativeContent, SeptemberContent, PvP56Zombies
    refs = [("zgate_rally", cls.__dict__["_rally_zombie_gate"].__code__),
            ("zgate_restore", cls._restore_rally_tracking.__code__),
            ("zgate_wrapper", wrapper.__code__),
            ("zgate_c_finish", C.finish_zombie.__code__), ("zgate_c_gate", C.zombie_gate.__code__),
            ("zgate_c_draw", C.draw_zombie.__code__),
            ("zgate_e_finish", E.finish_zombie.__code__), ("zgate_e_gate", E.zombie_gate.__code__),
            ("zgate_e_armor_gate", E.armor_gate.__code__), ("zgate_e_armor_clear", E.armor_clear.__code__),
            ("zgate_carried_imp", native_expansion.carried_imp_armored.__code__),
            ("zgate_s_gate", S.zombie_gate.__code__), ("zgate_s_finish", S.finish_zombie.__code__),
            ("zgate_s_wave", S.wave_chase.__code__),
            ("zgate_z_gate", Z.zombie_gate.__code__), ("zgate_z_finish", Z.finish_zombie.__code__),
            ("zgate_p64_gate", P.zombie_gate.__code__), ("zgate_p64_finish", P.finish_zombie.__code__),
            ("zgate_p64_apply_taunt", P.apply_taunt.__code__), ("zgate_p64_taunting", P.taunting_potato.__code__),
            ("zgate_p64_on_belt", P.on_belt.__code__)]
    restore = E.__dict__["restore_art"]
    if hasattr(restore, "__code__"):  # Python body: its C++ port was not enabled
        refs.append(("expansion_restore_art", restore.__code__))
    native = cppcore.native_for(*refs)
    if native is None or not hasattr(native, "battle_rally_zombie_gate"):
        return
    if None in native_expansion.BLACK_ARMOR_DROP.values():
        return
    cls._pvp_native_config = dict(getattr(cls, "_pvp_native_config", {}),
        ZG_py=cls.__dict__["_rally_zombie_gate"], ZG_restore=cls.__dict__["_restore_rally_tracking"],
        ZG_wrapper_code=wrapper.__code__,
        C_finish=C.__dict__["finish_zombie"], C_gate=C.__dict__["zombie_gate"], C_draw=C.__dict__["draw_zombie"],
        E_finish=E.__dict__["finish_zombie"], E_gate=E.__dict__["zombie_gate"],
        E_armor_gate=E.__dict__["armor_gate"], E_armor_clear=E.__dict__["armor_clear"], E_restore_art=restore,
        S_gate=S.__dict__["zombie_gate"], S_finish=S.__dict__["finish_zombie"], S_wave=S.__dict__["wave_chase"],
        Z_gate=Z.__dict__["zombie_gate"], Z_finish=Z.__dict__["finish_zombie"],
        P64_gate=P.__dict__["zombie_gate"], P64_finish=P.__dict__["finish_zombie"],
        IMP_ARMOR=native_expansion.IMP_ARMOR, IMP_ARMOR_HP=native_expansion.IMP_ARMOR_HP, IMP_BLACK_ARMOR=native_expansion.IMP_BLACK_ARMOR,
        CARRIER_BODY_MARK=native_expansion.CARRIER_BODY_MARK, IMP_BODY_MARK=native_expansion.IMP_BODY_MARK)
    cls._rally_zombie_gate = native.method(native.battle_rally_zombie_gate)
