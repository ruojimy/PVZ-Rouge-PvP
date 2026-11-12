"""PvP58 shell vines on native plant records, plus the dense-planting lookup.

A vine shares its cell with another plant exactly like the original pumpkin:
the original ``哪个植物`` returns the pumpkin before anything else and
``哪个无南瓜植物`` skips it. Both queries are re-expressed here with vines in
the same shell layer, so zombie bites, the shovel's left/right buttons and
every other native caller keep one rule. The haunting pepper's untargetable
cell, previously its own wrapper, is folded into the same lookup.
"""
from .pvp58_catalog import (PLANT_VINES, PUFF_VINE, SUN_VINE, VINE_FIRST,
                            VINE_PERIOD, VINE_YIELD, DENSE_SECRET)
from .pvp56_plants_catalog import PLANTS as FLYING_PLANTS
from .balance import HARDENING_MIN_BASE_HP, rest_factor

VINE_HP = 6.


def is_shell(plant):
    return (plant.get('植物') == '南瓜头' or plant.get('_pvp_content') in PLANT_VINES
            or plant.get('植物')=='模仿者' and plant.get('_pvp_copy_card')=='plant:抓人草')


def is_airborne(plant):
    """A flying plant (or its pending copy) that holds itself up in the air."""
    if plant.get('_pvp_content') in FLYING_PLANTS:
        return True
    return plant.get('植物') == '模仿者' and plant.get('_pvp_copy_card', '')[6:] in FLYING_PLANTS


class Vines:
    def __init__(self, content):
        self.c = content
        self.b = content.b
        self.g = content.g
        september = content.september
        for name, skip in (('哪个植物', False), ('哪个无南瓜植物', True)):
            self.g[name] = (lambda row, col, _skip=skip: self.lookup(row, col, _skip))
        self._support = self.g['_pvp_needs_plant_support']
        self.g['_pvp_needs_plant_support'] = self.needs_support
        self._targetable = september.targetable
        if self.dense():
            self._shell_first_peas()

    def dense(self):
        return DENSE_SECRET in self.b.team_secrets['plant']

    def lookup(self, row, col, skip_shell=False):
        """Original pumpkin-first order; with 密植 the latest plant is on top.

        Without the secret this is the original loop: the first shell in the
        cell wins, otherwise the last plant listed there. With 密植 the latest
        plant is on top for the shovel and every other plant-side caller, but
        attacking zombies (PvP62) go for the shell first: the topmost pumpkin
        or vine, else the topmost plant. Zombie-owned combat phases never see
        the untargetable haunting pepper.
        """
        active = self.b.targets.active
        hide = bool(active) and active['owner'] == 'zombie' and active['phase'] in ('zombies', 'entities')
        dense = self.dense()
        found = shell = -1
        for index, plant in enumerate(self.g['植物']):
            cell = plant.get('坐标')
            if not cell or cell[0] != row or cell[1] != col:
                continue
            # A shell remains the cell's contact layer until maintenance
            # removes it. Repeated crush queries must not consume the body
            # immediately after killing the shell in the same native tick.
            if hide and not self._targetable(plant) and not is_shell(plant):
                continue
            if is_shell(plant):
                if skip_shell:
                    continue
                if not dense and shell < 0:
                    shell = index
                elif dense and hide:
                    shell = index
            found = index
        return shell if shell >= 0 else found

    def _shell_first_peas(self):
        """密植: a zombie pea crossing a stacked cell hits its shell.

        The native pea test damages the first plant in list order whose point
        it crosses, which in a stack is the oldest plant. While that test runs,
        the other plants of a cell that has a living pumpkin or vine report no
        world point, so the pea lands on the shell. Nothing is reordered.
        """
        ns = self.b.patch.ns
        hit_name, point_name = '__pvz_sb_zombie_pea_hit', '__pvz_sb_plant_world_point'
        hit, point = ns.get(hit_name), ns.get(point_name)
        if not callable(hit) or not callable(point):
            return
        shells = []

        def shell_cells():
            return {tuple(p['坐标']) for p in self.g['植物']
                    if is_shell(p) and p.get('坐标') and p.get('植物血', 0) > 0 and '死' not in p}

        def pea_hit(g, pea, *args, **kwargs):
            shells.append(shell_cells())
            try:
                return hit(g, pea, *args, **kwargs)
            finally:
                shells.pop()

        def world_point(g, plant, *args, **kwargs):
            if shells and not is_shell(plant) and tuple(plant.get('坐标') or ()) in shells[-1]:
                return None
            return point(g, plant, *args, **kwargs)

        pea_hit.__wrapped__, world_point.__wrapped__ = hit, point
        ns[hit_name] = pea_hit
        ns[point_name] = world_point

    def needs_support(self):
        """A shell around a flying plant floats with it; nothing else changes."""
        plant = self.g['植物'][self.g['l']]
        if is_shell(plant) and any(
                other is not plant and other.get('坐标') == plant.get('坐标') and
                other.get('植物血', 0) > 0 and '死' not in other and is_airborne(other)
                for other in self.g['植物']):
            return False
        return self._support()

    def configure(self, plant, card):
        name = card.get('content')
        if name not in PLANT_VINES:
            return False
        plant['_pvp_content'] = name
        # A vine is no mushroom: never asleep by day, and the puff secret's
        # opening burst belongs to real puff-shrooms only.
        plant.pop('睡觉', None)
        plant.pop('小喷', None)
        if name == SUN_VINE:
            plant['植物'] = SUN_VINE
            hp = VINE_HP
            if 'secret:硬化' in self.b.team_secrets['plant']:
                hp = hp + 3 if hp == HARDENING_MIN_BASE_HP else hp
            plant.update(植物血=hp, 植物血上限=hp, _pvp_hardening_form=SUN_VINE,
                         _pvp_vine_clock=0., _pvp_vine_produced=False)
            plant['_pvp_max_hp'] = hp
        self.wake_cell(plant)
        return True

    def coffee_target(self, row, col):
        """Coffee: the native bean wakes its target and every other sleeper
        sharing the cell (密植 bodies, sleeping shells) wakes with it. Returns
        the index the native coffee region should treat as its target, or -1
        for no sleeper. Tentacle heads follow their root, not the cell."""
        sleepers = [index for index, plant in enumerate(self.g['植物'])
                    if plant.get('坐标') == [row, col] and '睡觉' in plant
                    and plant.get('植物血', 0) > 0 and '死' not in plant
                    and plant.get('_pvp_content') != '抓人草触手']
        for index in sleepers[:-1]:
            self.g['植物'][index].pop('睡觉', None)
        return sleepers[-1] if sleepers else -1

    def wake_cell(self, vine):
        if vine.get('_pvp_content') != PUFF_VINE or vine.get('植物血', 0) <= 0 or '死' in vine:
            return
        for plant in self.g['植物']:
            if plant is not vine and plant.get('坐标') == vine.get('坐标'):
                plant['_pvp_awake_forever'] = True
                plant.pop('睡觉', None)

    def tick(self):
        b = self.b
        rate = (b.rules['production_multiplier'] if b.deathmatch else 1.)
        for plant in self.g['植物']:
            if plant.get('_pvp_awake_forever'):
                plant.pop('睡觉', None)
            name = plant.get('_pvp_content')
            if name == PUFF_VINE:
                self.wake_cell(plant)
            if name != SUN_VINE or plant.get('植物血', 0) <= 0 or '死' in plant or '睡觉' in plant:
                continue
            # The marigold shortens production, first delivery included.
            rest = rest_factor(plant, b.engine.native_tick, b.rules)
            plant['_pvp_vine_clock'] += rate*rest/max(.01, float(plant.get('_pvp_aura_factor', 1.)))/250.
            period = VINE_PERIOD if plant['_pvp_vine_produced'] else VINE_FIRST
            if plant['_pvp_vine_clock']+1e-9 >= period:
                plant['_pvp_vine_clock'] -= period
                plant['_pvp_vine_produced'] = True
                row, col = plant['坐标']
                # A faction is not a seat: player 2's vine income stays personal
                # before resource merging and both manual/automatic collection.
                b.resource(plant.get('_pvp_seat', 'plant'), VINE_YIELD, (col+.5)*b.tile, (row+.5)*b.tile,
                           plant.get('_pvp_id', 'vine'))

    def draw_plant(self, plant):
        if self.g.get('补帧'):
            return
        name = plant['_pvp_content']
        row, col = plant['坐标']
        tile = self.b.tile
        x, y = (col+.5)*tile, (row+1)*tile
        # The low puff-vine silhouette sits on the soil; its leaf tips should
        # not hover above the host's roots. Keep the shell foreground layer.
        if name == PUFF_VINE:
            y += tile*.10
        if name in (SUN_VINE, PUFF_VINE) and '睡觉' not in plant:
            # Idle cycle on the native clock; a sleeping vine holds frame 0.
            name += '-帧' + str((self.b.engine.native_tick//60) % 4)
        self.c.draw_custom_plant(plant,name,x,y,bottom=True)
