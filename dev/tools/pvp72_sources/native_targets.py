"""PvP allegiance/hero overlay over the shipped native combat functions.

The original projectile and plant regions perform their own collisions against
ordinary original zombie dictionaries. A temporary HeroProxy is added ONLY to
those target lists by the caller, never to native zombie AI/death/reward loops.
Its shape comes from the actual ``新增僵尸`` constructor (大小=2), not a second
collider. Damage uses original points without an extra PvP divisor.

Ordinary damage callbacks retain native hit semantics. Chili direct/ground-fire
ash is deduplicated only within one explosion. Hero damage calls original
``掉血``, retaining native hurt/knockdown flags, with friendly-damage rejection
and a per-attack 40% maximum for ash/instant swallowing.
"""
import dis
import math
import types
from contextlib import contextmanager
from .native_physics import NativePhysics
from .pvp64_catalog import PRIMAL_MINE, PRIMAL_ASH_DAMAGE
from .balance68006 import hero_amount


HERO_DAMAGE_SCALE = 1.
HERO_MAX_HP = 40.
INSTANT_CAP = .4
_MISSING = object()
# Flat hero damage for named plant projectile/melee sources (PvP balance).
# Native gravity/velocity bonuses never reach a hero; see the patch source's
# bonus-damage skip for _pvp_hero targets.
HERO_PROJECTILE_DAMAGE = {"卷心菜": 12., "火豆": 12., "蓝火豆": 16., "星星": 30.,
                          "西瓜": 16., "冰瓜": 16., "窝瓜x": 16.}
HERO_MELON_SPLASH_DAMAGE = 2.
# PvP59: each gloom-shroom pulse (about every 0.2 s) hits the zombie Dave for 4.
HERO_GLOOM_DAMAGE = 4.
# Zombie bites on a Dave hero. Native bites are 掉血(1); only that bite amount
# is remapped, so explosions and patch plant-zombie attacks keep their values.
HERO_BLACK_BITE_DAMAGE = 3.
HERO_BITE_DAMAGE = {"墓碑吞噬者僵尸": 6.}


def gravebuster_bite(source):
    """PvP73: 墓碑吞噬者僵尸 bites for 3 above half health and 6 at or below half
    (plants and Dave; zombie-to-zombie bites are this x10)."""
    return 6. if source.get('血量',0)<=source.get('_pvp_max_hp',300.)*.5 else 3.
BLACK_BITE_VARIANTS = frozenset(("黑普通僵尸", "黑路障僵尸", "黑铁桶僵尸",
                                 "黑旗帜僵尸", "黑撑杆僵尸", "黑橄榄僵尸"))
_HERO_KEYS = tuple(set(NativePhysics.state_keys).union((
    "玩家恢复", "玩家受伤", "玩家皮肤", "玩家倒地", "玩家血量", "玩家位置")))
_HERO_KEY_SET=frozenset(_HERO_KEYS)
_CONVERSIONS = frozenset(("魅惑", "灰烬", "死亡", "消亡", "出土", "僵尸", "大小",
                          "防具", "防具血量", "手持", "手持血量"))
_COMBAT_HERO_KEYS = ("玩家位置", "玩家血量", "玩家恢复", "玩家受伤", "玩家倒地",
                     "辣飞天", "__pvz_sb_chili_launch_lock_until")
# context() setdefaults that are also combat keys (玩家皮肤 is restored, not written back).
_CONTEXT_DEFAULTS = {"玩家恢复": 0, "玩家受伤": 0}


class NativeTargetError(RuntimeError):
    pass


class HeroProxy(dict):
    """Native target record; intercept native direct instant-kill writes too."""
    def __init__(self, template, controller, side):
        dict.__init__(self, template)
        self.controller = controller
        self.side = side
        team = "plant" if side.startswith("plant") else "zombie"
        dict.update(self, _pvp_hero=side, _pvp_owner=team, _pvp_id="hero:" + side,
                    出场=500, 防具="", 防具血量=0, 手持="", 手持血量=0)
        self.sync()

    def sync(self):
        avatar = self.controller.heroes[self.side]
        for key,state_key in (("冰冻","_pvp_ice"),("黄油","_pvp_butter"),("眩晕","_pvp_stun")):
            dict.__setitem__(self,key,avatar.get(state_key,0))
        dict.__setitem__(self, "血量", max(0., avatar["玩家血量"]) * HERO_DAMAGE_SCALE)
        dict.__setitem__(self, "位置", avatar["玩家位置"])
        dict.__setitem__(self, "方向", avatar.get("玩家方向", 1))

    def __setitem__(self, key, value):
        if key in ("冰冻","黄油","眩晕"):
            if self.controller.owner()!=self.side:
                self.controller.heroes[self.side][{"冰冻":"_pvp_ice","黄油":"_pvp_butter","眩晕":"_pvp_stun"}[key]]=max(0,value)
                dict.__setitem__(self,key,max(0,value))
            return
        if key == "血量":
            old = dict.__getitem__(self, key)
            if value < old:
                # The original 大嘴花/龙蒺藜 writes -1024 directly at 134072.
                kind = "swallow" if value <= -1024 else self.controller.damage_kind
                self.controller.damage_hero(self.side, (old - value) / HERO_DAMAGE_SCALE, kind)
                self.sync()
            return
        if key == "灰烬":
            self.controller.damage_hero(self.side, HERO_MAX_HP, "ash")
            self.sync()
            return
        if key in _CONVERSIONS:
            return
        dict.__setitem__(self, key, value)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value


class NativeTargets:
    """Install into ONE isolated native match dictionary.

    ``context(target, owner, phase, source=None)`` selects the actual hero globals
    and captures native direct HP/velocity writes on exit. For mixed entities,
    execute each owner batch with its enemy hero, never all entities against Z.
    ``source`` may be explicit or the current native ``l`` in a unit phase.
    ``hero_lock(source, side)`` must validate mark/range/LOS; absent means no
    tracking lock on a hero. Physical untracked collisions remain possible.
    """
    def __init__(self, namespace, heroes, hero_lock=None, on_damage=None):
        from .performance import enabled
        self.context_keys=_HERO_KEY_SET if enabled('TARGET_KEYS') else _HERO_KEYS
        self.g, self.heroes = namespace, heroes
        self.hero_lock = hero_lock or (lambda source, side: False)
        self.on_damage = on_damage
        self.originals = {}
        self.proxies = {}
        # A hero collider is a private native record, not a selectable summon.
        # Retain the constructor before match card-ban admission wraps it.
        self.proxy_factory = namespace.get("新增僵尸")
        self.active = None
        self.damage_kind = "normal"
        self.sequence = 0
        self._damage_packets = set()
        self.budgets = {}
        self.unshielded = None
        self.armor_break = None
        native = _NATIVE_CONTEXT
        if native is not None:
            # C++ HeroContext: the same enter/exit steps as context() below.
            import functools
            self.context = functools.partial(native.HeroContext, self)
        self.install()

    def install(self):
        names = ("掉血", "伤害僵尸", "表面伤害僵尸", "灰烬僵尸", "新增实体")
        missing = [name for name in names if not callable(self.g.get(name))]
        if missing:
            raise NativeTargetError("Missing native target callbacks: " + ",".join(missing))
        if self.g.get("_pvp_native_targets") not in (None, self):
            raise NativeTargetError("Native target overlay is already installed")
        if self.originals:
            return
        self.originals = {name: self.g[name] for name in names}
        hurt = self.originals["掉血"]
        if hurt.__code__.co_firstlineno != 197 or len(hurt.__code__.co_code) != 96:
            raise NativeTargetError("Unexpected native Dave damage function")
        # Original bytecode 8:92 is exactly the damage body, without the I-Z
        # mode immunity guard. No damage equation or animation is rewritten.
        hurt_bytes = bytearray(hurt.__code__.co_code)
        hurt_bytes[:2] = bytes((dis.opmap["JUMP_ABSOLUTE"], 8))
        self.native_hurt = types.FunctionType(hurt.__code__.replace(co_code=bytes(hurt_bytes)), self.g, "native_pvp_hurt")
        self.g["掉血"] = self._player_damage
        self.g["伤害僵尸"] = self._zombie_damage
        self.g["表面伤害僵尸"] = self._surface_damage
        self.g["灰烬僵尸"] = self._ash_damage
        self.g["新增实体"] = self._new_entity
        self._tag_bypassed_add_entity()
        self.g["_pvp_native_targets"] = self

    def _tag_bypassed_add_entity(self):
        """Tag projectiles created through the stored pre-patch add-entity.

        The 三向射手 branch calls the pre-patch original on purpose, so the
        patch's own per-projectile tweaks do not re-apply to a shot it already
        configured.  That also skips ``g['新增实体']``, which is where every
        projectile picks up its allegiance; without this the three peas reach
        the target lists ownerless and a barrel contact raises inside
        ``NativeTargetError``.  Only the stored reference is re-pointed, the
        patch's own wrapper and its closure keep calling the true original.
        """
        stored = self.g.get("__pvz_sb_add_entity_original")
        if not callable(stored) or getattr(stored, "__pvp_tagged_add__", False):
            return

        def tagged(name, fx, weizhi, _original=stored):
            return self._tag_added(_original, (name, fx, weizhi))

        tagged.__name__ = getattr(stored, "__name__", "新增实体")
        tagged.__pvp_tagged_add__ = True
        self.g["__pvz_sb_add_entity_original"] = tagged

    def hero_proxy(self, side="zombie"):
        if side not in self.heroes:
            raise NativeTargetError("Unknown hero")
        if side not in self.proxies:
            # Keep constructor random consumption out of the actual world RNG.
            rng = self.g.get("random")
            rng_state = rng.getstate() if hasattr(rng, "getstate") else None
            old_units, old_mode = self.g["僵尸"], self.g["模式"]
            try:
                self.g["僵尸"] = []
                self.g["模式"] = "正常模式"
                self.proxy_factory("普通僵尸", list(self.heroes[side]["玩家位置"]), 1)
                template = self.g["僵尸"][-1]
            finally:
                self.g["僵尸"], self.g["模式"] = old_units, old_mode
                if rng_state is not None:
                    rng.setstate(rng_state)
            self.proxies[side] = HeroProxy(template, self, side)
        self.proxies[side].sync()
        return self.proxies[side]

    def source(self):
        if not self.active:
            return None
        if self.active["source"] is not None:
            return self.active["source"]
        key = {"plants": "植物", "zombies": "僵尸", "entities": "实体"}.get(self.active["phase"])
        index = self.g.get("l")
        values = self.g.get(key, ())
        return values[index] if isinstance(index, int) and 0 <= index < len(values) else None

    def owner(self, source=None):
        source = self.source() if source is None else source
        if isinstance(source, dict):
            if "魅惑" in source:
                return "plant"
            if source.get("_pvp_owner") in self.heroes:
                return source["_pvp_owner"]
        return self.active["owner"] if self.active else None

    def source_id(self, source):
        if not isinstance(source, dict):
            return "hero:" + (self.active["owner"] if self.active else "unknown")
        if not source.get("_pvp_id"):
            self.sequence += 1
            source["_pvp_id"] = "native:%d" % self.sequence
        return source["_pvp_id"]

    def tag_entity(self, entity, owner=None, source=None):
        source = self.source() if source is None else source
        owner = owner or self.owner(source)
        if owner not in self.heroes:
            raise NativeTargetError("Native entity has no explicit source allegiance")
        self.source_id(entity)
        entity.setdefault("_pvp_owner", owner)
        entity.setdefault("_pvp_original_owner", (source or {}).get("_pvp_original_owner",
                          (source or {}).get("_pvp_owner", owner)))
        entity.setdefault("_pvp_source_entity", self.source_id(source))
        entity.setdefault("_pvp_root_source", (source or {}).get("_pvp_root_source", self.source_id(source)))
        if entity.get('名')=='尖刺' and isinstance(source,dict):
            entity['_pvp_cattail']=source.get('植物')=='香蒲' or str(source.get('_pvp_id','')).startswith('hero:plant')
        from .native_projectiles import begin_flight
        begin_flight(entity, source)
        # All fragments of one original explosion share its hero damage cap,
        # including the direct plant hit and the persistent ground flames.
        entity.setdefault("_pvp_instant_attack", (source or {}).get("_pvp_instant_attack",
                          (self.source_id(source if isinstance(source,dict) else entity),
                           int(self.g.get("_pvp_native_tick", 0)))))
        return entity

    def _tag_added(self, add, args, kwargs=None):
        """Run one add-entity call and give its new entities an allegiance."""
        before = len(self.g["实体"])
        source, owner = self.source(), self.owner()
        result = add(*args, **(kwargs or {}))
        if self.active:
            for entity in self.g["实体"][before:]:
                self.tag_entity(entity, owner, source)
        return result

    def _new_entity(self, *args, **kwargs):
        return self._tag_added(self.originals["新增实体"], args, kwargs)

    @contextmanager
    def full_targets(self):
        """Expose stationary targets only during a synchronous damage callback.

        Mobile native AI must never iterate Dave proxies or economy graves.
        Its death callbacks can still explode immediately, before the normal
        plant phase appends those targets. The battle supplies its omitted
        targets here; remove only what this context inserted and retain all
        native deletions, replacements and newly spawned ordinary units.
        """
        provider = self.g.get("_pvp_target_extras")
        if not callable(provider):
            yield self
            return
        original = self.g["僵尸"]
        present = {id(obj) for obj in original}
        inserted = set()
        for obj in provider():
            if isinstance(obj, dict) and id(obj) not in present:
                original.append(obj)
                present.add(id(obj))
                inserted.add(id(obj))
        try:
            yield self
        finally:
            current = self.g["僵尸"]
            original[:] = [obj for obj in current if id(obj) not in inserted]
            self.g["僵尸"] = original

    @contextmanager
    def context(self, target, owner, phase, source=None, attack_id=None):
        if target not in self.heroes or owner not in self.heroes:
            raise NativeTargetError("Unknown combat allegiance")
        previous = self.active
        if previous:
            # A source hook can nest inside the original bonus scan. Capture
            # direct original HP writes before changing which hero is global.
            previous_avatar = self.heroes[previous["target"]]
            for key in _COMBAT_HERO_KEYS:
                if key in self.g:
                    previous_avatar[key] = self.g[key]
        saved = {key: self.g.get(key, _MISSING) for key in _HERO_KEYS}
        self.active = dict(target=target, owner=owner, phase=phase, source=source, attack_id=attack_id)
        avatar = self.heroes[target]
        self.g.update({key: value for key, value in avatar.items() if key in self.context_keys and key != "秘籍"})
        # Both target contexts use original normal combat. A Z proxy supplies
        # plant collision, so I-Z immunity is neither needed nor relied upon.
        self.g["模式"] = "正常模式"
        self.g.setdefault("玩家恢复", 0)
        self.g.setdefault("玩家受伤", 0)
        self.g.setdefault("玩家皮肤", "普通戴夫")
        try:
            yield self
        finally:
            if phase=="plants" and self.g.get("冻水",0)>saved.get("冻水",0):
                self.g["_pvp_water_ice"]=max(self.g.get("_pvp_water_ice",0),self.g["冻水"])
            for key in _COMBAT_HERO_KEYS:
                if key in self.g:
                    avatar[key] = self.g[key]
            for key, value in saved.items():
                if value is _MISSING:
                    self.g.pop(key, None)
                else:
                    self.g[key] = value
            self.active = previous
            if previous:
                # Restore the enclosing hero's latest HP, not its pre-hit
                # snapshot. Otherwise nested charmed-source attacks heal Z
                # when the outer bonus context subsequently exits.
                current = self.heroes[previous["target"]]
                for key in _COMBAT_HERO_KEYS:
                    if key in current:
                        self.g[key] = current[key]
            for proxy in self.proxies.values():
                proxy.sync()

    def context_effects(self, target, owner, phase):
        """Exact net effect of ``with self.context(target, owner, phase, source):``
        around a body that touches no hero global, ``模式``, avatar, proxy or
        targets state (the caller proves that for its body).

        Mirrors ``context`` step by step: capture into the enclosing hero,
        g <- target hero, write-back target hero <- g, restore g, re-apply the
        enclosing hero's combat keys, proxy sync. Net: only the three avatar /
        g writes below survive; everything else is restored by ``context``.
        """
        heroes = self.heroes
        if target not in heroes or owner not in heroes:
            raise NativeTargetError("Unknown combat allegiance")
        if phase == "plants":
            raise NativeTargetError("plants-phase context has a water-ice side effect; use context()")
        g = self.g
        previous = self.active
        if previous:
            enclosing = heroes[previous["target"]]
            for key in _COMBAT_HERO_KEYS:
                if key in g:
                    enclosing[key] = g[key]
        avatar = heroes[target]
        for key in _COMBAT_HERO_KEYS:
            if key in avatar:
                continue  # g[key] = avatar[key] on entry, avatar[key] = g[key] on exit
            if key in g:
                avatar[key] = g[key]
            elif key in _CONTEXT_DEFAULTS:
                avatar[key] = _CONTEXT_DEFAULTS[key]
        if previous:
            current = heroes[previous["target"]]
            for key in _COMBAT_HERO_KEYS:
                if key in current:
                    g[key] = current[key]
        for proxy in self.proxies.values():
            proxy.sync()

    def _attack_key(self, side, kind):
        source = self.source()
        tick = int(self.g.get("_pvp_native_tick", 0))
        attack = self.active.get("attack_id") if self.active else None
        if attack is None and isinstance(source, dict):
            attack = source.get("_pvp_instant_attack")
        if attack is None:
            # A projectile is one attack across its whole native lifetime;
            # synchronous plant ash-secret double calls share this native tick.
            attack = (self.source_id(source), None if isinstance(source, dict) and "名" in source else tick)
        return (side, kind, str(attack)), tick

    def damage_hero(self, side, amount, kind="normal"):
        if not self.active or amount <= 0 or self.owner() == ("plant" if side.startswith("plant") else "zombie"):
            return 0.
        source = self.source()
        if isinstance(source,dict) and source.get('_pvp_no_hero_attack'):
            return 0.
        avatar = self.heroes[side]
        if avatar["玩家血量"] <= 0:
            return 0.
        amount = float(amount)
        if kind in ("ash", "swallow"):
            key, tick = self._attack_key(side, kind)
            used = self.budgets.get(key, (tick, 0.))[1]
            maximum=avatar.get("_pvp_max_hp",20.)
            cap=maximum*INSTANT_CAP
            if isinstance(source,dict) and (source.get('植物')=='火爆辣椒' or source.get('僵尸')=='辣椒僵尸' or source.get('名')=='火'):
                cap=min(cap,16.)
            amount = min(amount, max(0., cap - used))
            self.budgets[key] = (tick, used + amount)
            if len(self.budgets) > 1024:
                self.budgets = {k: v for k, v in self.budgets.items() if v[0] >= tick - 2500}
                if len(self.budgets) > 2048:
                    self.budgets = dict(sorted(self.budgets.items(), key=lambda kv: kv[1][0])[-1024:])
        factor = getattr(self, "damage_factor", None)
        if factor is not None:
            amount *= factor(side)
        last_stand = getattr(self, "last_stand", None)
        if last_stand is not None:
            amount = last_stand(side, avatar, amount)
        amount = min(amount, avatar["玩家血量"])
        if amount <= 0:
            return 0.
        # A proxy may be hit while the native global player is the other hero.
        # Select only for this original callback, then restore that context.
        saved = {key: self.g.get(key, _MISSING) for key in _HERO_KEYS}
        original_particles = self.g.get("增粒子")
        try:
            self.g.update({key: value for key, value in avatar.items() if key in _HERO_KEYS})
            self.g.setdefault("玩家皮肤", "普通戴夫")
            if callable(original_particles):
                # Original Dave always received integer damage, so its blood
                # count goes straight to range(). Secret modifiers can
                # yield fractional HP. Coerce only this presentation count;
                # preserve the fractional damage and the real particle code.
                def blood_particles(name, position, count, *args, **kwargs):
                    return original_particles(name, position, int(math.ceil(count)), *args, **kwargs)
                self.g["增粒子"] = blood_particles
            self.native_hurt(amount)
            for key in ("玩家血量", "玩家恢复", "玩家受伤", "玩家倒地"):
                avatar[key] = self.g[key]
        finally:
            if original_particles is not None:
                self.g["增粒子"] = original_particles
            for key, value in saved.items():
                if value is _MISSING:
                    self.g.pop(key, None)
                else:
                    self.g[key] = value
        if self.active["target"] == side:
            self.g.update({key: avatar[key] for key in ("玩家血量", "玩家恢复", "玩家受伤", "玩家倒地")})
        if self.on_damage:
            self.on_damage(side, amount, kind, self.source())
        for proxy in self.proxies.values():
            proxy.sync()
        return amount

    def _player_damage(self, amount):
        if not self.active:
            return self.originals["掉血"](amount)
        if amount == 1:
            source = self.source()
            if isinstance(source, dict) and "僵尸" in source:
                if source.get("_pvp_variant") in BLACK_BITE_VARIANTS:
                    amount = HERO_BLACK_BITE_DAMAGE
                else:
                    amount = HERO_BITE_DAMAGE.get(source["僵尸"], amount)
                    if source["僵尸"] == "墓碑吞噬者僵尸":amount = gravebuster_bite(source)
        override=hero_amount(self.source(),self.active["target"],self.g.get("秘籍",()))
        if (isinstance(self.source(),dict) and self.source().get('_pvp_cattail')
                and str(self.active['target']).startswith('zombie')):override=2.
        if override is not None:amount=override
        return self.damage_hero(self.active["target"], amount, self.damage_kind)

    def _proxy(self, index):
        values = self.g["僵尸"]
        return values[index] if isinstance(values[index], HeroProxy) else None

    def hero_source_amount(self, amount, side=None):
        """Flat PvP hero damage for named projectile entities; None keeps native."""
        source = self.source()
        override=hero_amount(source,side,self.g.get("秘籍",()))
        if override is not None:return override
        if str(side).startswith('zombie') and isinstance(source, dict) and source.get("植物") == "忧郁蘑菇":
            return HERO_GLOOM_DAMAGE
        if not isinstance(source, dict) or "名" not in source:
            return None
        # These two card overrides are Zombie Dave balance only. Ordinary
        # zombies, their plant heads and reflected shots at Plant Dave retain
        # their existing damage paths and values.
        if str(side).startswith('zombie'):
            if source.get('_pvp_plant_kind') == '小喷菇' and source.get('_pvp_content') != '忧郁藤蔓':return 2.5
            if source.get('_pvp_plant_kind') == '海蘑菇':return 2.5
            if source['名']=='星星':return 6.
            if source['名']=='尖刺' and source.get('_pvp_cattail'):return 2.
            content=source.get('_pvp_content')
            if content=='甜椒投手':
                return 5. if source.get('_pvp_melon_splash') else 15.
            if content=='原始豌豆射手':
                if not source.get('_pvp_melon_splash'):return 15.
                blue=source['名']=='蓝火豆' or source['名']=='火豆' and '蓝火' in self.g.get('秘籍',())
                return 6. if blue else 3.
        if source.get("_pvp_melon_splash"):
            return HERO_MELON_SPLASH_DAMAGE
        name = source["名"]
        # Native fire peas stay 名=火豆 and take the 蓝火 secret boost at hit
        # time; mirror that switch with the flat blue-fire hero value.
        if name == "火豆" and "蓝火" in self.g.get("秘籍", ()):
            return HERO_PROJECTILE_DAMAGE["蓝火豆"]
        return HERO_PROJECTILE_DAMAGE.get(name)

    def _zombie_damage(self, index, facing, amount):
        self._record_melon_hit(index)
        source = self.source()
        if id(self.g['僵尸'][index]) not in self._damage_packets and isinstance(source, dict) and source.get("名") == "星星":
            amount = 30.
        proxy = self._proxy(index)
        if proxy is None:
            return self._unit_damage('伤害僵尸',index,facing,amount)
        override = self.hero_source_amount(amount, proxy.side)
        if override is not None:
            amount = override * HERO_DAMAGE_SCALE
        return self.damage_hero(proxy.side, amount / HERO_DAMAGE_SCALE, self.damage_kind)

    def _surface_damage(self, index, facing, amount):
        self._record_melon_hit(index)
        source = self.source()
        if id(self.g['僵尸'][index]) not in self._damage_packets and isinstance(source, dict) and source.get("名") == "星星":
            amount = 30.
        if self._proxy(index) is None:
            return self._unit_damage('表面伤害僵尸',index,facing,amount)
        self._zombie_damage(index, facing, amount)
        return False  # original armorless result; preserve native hit effects.

    def _unit_damage(self, callback, index, facing, amount):
        target = self.g['僵尸'][index]
        token = id(target)
        if token in self._damage_packets:
            return self.originals[callback](index,facing,amount)
        adjust = self.g.get('_pvp_damage_amount')
        if adjust is not None:
            amount = adjust(target,amount)
        # Native surface damage can delegate to ordinary damage. Both armor
        # and body consume the same already-scaled incoming packet.
        self._damage_packets.add(token)
        watch = self.armor_break
        if watch is not None:
            worn = (target.get('防具'), target.get('防具血量', 0), target.get('手持'), target.get('手持血量', 0))
        try:
            if watch is not None:
                try:
                    return self._shielded_damage(callback, target, index, facing, amount)
                finally:
                    if worn[0] and worn[1] > 0 and target.get('防具血量', 0) <= 0:
                        watch(target, '防具', worn[0], target.get('_pvp_armor_max') or worn[1])
                    if worn[2] and worn[3] > 0 and target.get('手持血量', 0) <= 0:
                        watch(target, '手持', worn[2], target.get('_pvp_zs_hand_max') or worn[3])
            return self._shielded_damage(callback, target, index, facing, amount)
        finally:
            self._damage_packets.remove(token)

    def _shielded_damage(self, callback, target, index, facing, amount):
        unshielded = self.unshielded
        if callback == '伤害僵尸' and unshielded is not None and unshielded(target):
            # PvP66 僵王出品: a type-II shield cannot be bypassed.
            self.originals['表面伤害僵尸'](index,facing,amount)
            return None
        return self.originals[callback](index,facing,amount)

    def _record_melon_hit(self, index):
        source = self.source()
        # Direct hits are recorded so the impact-time splash skips them.
        # Fire/blue peas count too: their splash is one third of direct.
        if isinstance(source, dict) and source.get('名') in ('西瓜','冰瓜','火豆','蓝火豆'):
            hits = source.setdefault('_pvp_melon_hits', [])
            uid = self.source_id(self.g['僵尸'][index])
            if uid not in hits:hits.append(uid)

    def _ash_damage(self, index):
        proxy = self._proxy(index)
        if proxy is None:
            source = self.source()
            if isinstance(source, dict) and (source.get("植物") == "火爆辣椒" or
                    source.get("僵尸") == "辣椒僵尸" or source.get("名") == "火"):
                # Native chili's direct hit and its persistent fire invoke ash
                # separately. A giant must receive only one native ash hit per
                # originating explosion, not acquire delayed ash death at 500 HP.
                attack = source.get("_pvp_instant_attack",
                    (self.source_id(source), int(self.g.get("_pvp_native_tick", 0))))
                key = (self.owner(), tuple(attack) if isinstance(attack, list) else attack)
                seen = self.g["僵尸"][index].setdefault("_pvp_chili_ash_hits", set())
                if key in seen:
                    return None
                seen.add(key)
            target = self.g['僵尸'][index]
            adjust = self.g.get('_pvp_damage_amount')
            source = self.source()
            if isinstance(source, dict) and (source.get('_pvp_content') == PRIMAL_MINE
                    or source.get('植物')=='火爆辣椒' or source.get('僵尸')=='辣椒僵尸' or source.get('名')=='火'):
                # The primal mine's blast is the native ash function with a
                # 750-point packet: above it the packet is subtracted,
                # otherwise the zombie is marked for the ash death.
                scaled = adjust(target, PRIMAL_ASH_DAMAGE) if adjust is not None else PRIMAL_ASH_DAMAGE
                if '灰烬' not in target and target['血量'] + target.get('防具血量', 0) > scaled:
                    return self._unit_damage('伤害僵尸', index, 1, PRIMAL_ASH_DAMAGE)
                target['灰烬'] = 0
                return None
            # Native ash is a 500-point hit: above 500 combined body/first
            # armor HP it subtracts 500, otherwise it marks the ash death.
            # Apply the same finite packet before choosing its death branch.
            # Secondary armor is bypassed, as in the original ash function.
            scaled = adjust(target,500.) if adjust is not None else 500.
            if scaled < 500. and '灰烬' not in target:
                if target['血量'] + target.get('防具血量',0) > scaled:
                    return self._unit_damage('伤害僵尸',index,1,500.)
            return self.originals["灰烬僵尸"](index)
        source=self.source()
        chili=isinstance(source,dict) and (source.get('植物')=='火爆辣椒' or source.get('僵尸')=='辣椒僵尸' or source.get('名')=='火')
        return self.damage_hero(proxy.side, 16. if chili else HERO_MAX_HP, "ash")

    def target_index(self, code, source=None):
        """Run the ORIGINAL nearest-target region with gated hero eligibility.

        出场 is an existing original eligibility check at byte 98552. Temporarily
        hide an unmarked/obstructed/out-of-range hero from tracking only; the same
        proxy remains in physical projectile collision and ordinary plant fire.
        """
        hidden = []
        try:
            for proxy in self.proxies.values():
                if not self.hero_lock(source, proxy.side):
                    hidden.append((proxy, proxy["出场"]))
                    dict.__setitem__(proxy, "出场", 0)
            exec(code, self.g)
            # Cattails choose distance from the shooter, including vertical
            # distance and the ring seam. The native index measures from Dave.
            if isinstance(source,dict) and (source.get('植物')=='香蒲' or source.get('_pvp_cattail')
                    or str(source.get('_pvp_id','')).startswith('hero:plant')):
                tile=self.g['比'];width=len(self.g['ditu'][0])*tile
                if '坐标' in source:
                    row,col=source['坐标'];sx,sy=(col+.5)*tile,(row+.5)*tile
                else:
                    pos=source.get('位置',source.get('玩家位置',self.g['玩家位置']))
                    sx,sy=pos[0],pos[1]-tile
                candidates=[]
                for index,target in enumerate(self.g['僵尸']):
                    if (target.get('血量',0)<=0 or target.get('出场')!=500 or '灰烬' in target
                            or '出土' in target or self.owner(target)==self.owner(source)):
                        continue
                    tx,ty=target['位置'][:2]
                    dx=(tx-sx+width/2.)%width-width/2.
                    candidates.append((dx*dx+(ty-tile-sy)**2,self.source_id(target),index))
                self.g['离玩家最近']=min(candidates)[2] if candidates else -1
        finally:
            for proxy, old in hidden:
                dict.__setitem__(proxy, "出场", old)


_NATIVE_CONTEXT = None


def _install_native():
    """C++ bodies for the hottest methods (pvpnative_targets.cpp), same steps."""
    global _NATIVE_CONTEXT
    from . import cppcore
    _NATIVE_CONTEXT = cppcore.native_for(("hero_context", NativeTargets.context.__wrapped__.__code__))
    native = cppcore.native_for(("targets_source", NativeTargets.source.__code__),
                                ("targets_owner", NativeTargets.owner.__code__),
                                ("targets_context_effects", NativeTargets.context_effects.__code__),
                                ("proxy_sync", HeroProxy.sync.__code__))
    if native is None and _NATIVE_CONTEXT is None:
        return
    native = native or _NATIVE_CONTEXT
    config = dict(HERO_KEYS=_HERO_KEYS, COMBAT_HERO_KEYS=_COMBAT_HERO_KEYS, MISSING=_MISSING,
                  NativeTargetError=NativeTargetError, CONTEXT_DEFAULTS=_CONTEXT_DEFAULTS,
                  PHASE_KEYS={"plants": "植物", "zombies": "僵尸", "entities": "实体"},
                  TARGETS_GLOBALS=globals())
    # Constants the C++ bodies use, owned by this module's own classes.
    NativeTargets._pvp_native_config = config
    HeroProxy._pvp_native_config = config
    if cppcore.native_for(("proxy_sync", HeroProxy.sync.__code__)) is not None:
        HeroProxy.sync = native.method(native.proxy_sync)
        NativeTargets.source = native.method(native.targets_source)
        NativeTargets.owner = native.method(native.targets_owner)
        NativeTargets.context_effects = native.method(native.targets_context_effects)


_install_native()
