"""Match-clock protection at numeric native damage writes, before death checks.

The native engine also has nonnumeric removal operations (swallowing, crushing,
plant incineration, shovelling and spent one-shot plants). Those retain their native
meaning. No HP ledger, death reversal or change to maximum HP is involved.
"""
import ast
import dis
from functools import lru_cache

from .catalog import CARDS
from .native_bytecode import instruction_window
from .native_gate import NativeGateError
from .native_physics import _instruction, NATIVE_HZ


@lru_cache(maxsize=16)
def replace_damage_write(code, start, end, name, expected):
    """Replace a checked complete HP-write statement, retaining all branches."""
    actual = tuple((i.opname, i.argval) for i in instruction_window(code, start, end)
                   if i.opname != 'EXTENDED_ARG')
    if actual != expected or any(start < p < end for p in dis.findlabels(code.co_code)):
        raise NativeGateError('Native damage write changed: ' + name)
    names = code.co_names + (name,)
    call = (_instruction('LOAD_NAME', len(names)-1) +
            _instruction('CALL_FUNCTION', 0) + _instruction('POP_TOP'))
    if len(call) > end-start:
        raise NativeGateError('Native damage write window too small: ' + name)
    data = bytearray(code.co_code)
    data[start:end] = call + _instruction('NOP') * ((end-start-len(call))//2)
    return code.replace(co_code=bytes(data), co_names=names)


def plant_write_expected(amount):
    return (('LOAD_NAME', '植物'), ('LOAD_NAME', 'z'), ('BINARY_SUBSCR', None),
            ('LOAD_CONST', '植物血'), ('DUP_TOP_TWO', None), ('BINARY_SUBSCR', None),
            ('LOAD_CONST', amount), ('INPLACE_SUBTRACT', None),
            ('ROT_THREE', None), ('STORE_SUBSCR', None))


@lru_cache(maxsize=2)
def _patch_damage_code(source):
    # Compile only the verified damage expressions into the match's existing
    # namespace. Keep native target selection, hit effects and death checks.
    specs = {
        '__pvz_sb_damage_plant_from_fumeshroom': ('hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - __pvz_sb_float(damage, 0.0)'),
        '__pvz_sb_zombie_pea_hit': ('new_hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - __pvz_sb_PLANT_ZOMBIE_PEA_DAMAGE * __pvz_sb_zombie_pea_fire_mult(g, pea)'),
        '__pvz_sb_zombie_pea_fire_splash': ('new_hp',
            '__pvz_sb_float(plant.get(__pvz_sb_K_PLANT_HP, 0.0), 0.0) - splash'),
        '__pvz_sb_update_gravebuster_zombie_plant_damage': ('desired',
            '__pvz_sb_float(__pvz_sb_GRAVEBUSTER_ZOMBIE_PLANT_DAMAGE, 6.0)'),
    }
    functions = []
    for function in ast.parse(source).body:
        if not isinstance(function, ast.FunctionDef) or function.name not in specs:
            continue
        name, expression = specs[function.name]
        expected = ast.dump(ast.parse(expression, mode='eval').body)
        matches = [node for node in ast.walk(function) if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == name and ast.dump(node.value) == expected]
        if len(matches) != 1 or function.decorator_list:
            raise NativeGateError('Patch damage expression changed: ' + function.name)
        node = matches[0]
        # The supplemental bite ledger compares the already-reduced native
        # bite with its desired total, so scale that total rather than extra.
        value = node.value if name == 'desired' else node.value.right
        call = ast.Call(func=ast.Name(id='_pvp_damage_amount', ctx=ast.Load()),
                        args=[ast.Name(id='plant', ctx=ast.Load()), value], keywords=[])
        if name == 'desired':
            node.value = ast.copy_location(call, value)
        else:
            node.value.right = ast.copy_location(call, value)
        functions.append(function)
    if len(functions) != len(specs):
        raise NativeGateError('Missing native patch damage functions')
    return compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                   '<pvp-producer-protection>', 'exec')


SELECTED_GRAVE_FACTOR = .25


class NativeProtection:
    def __init__(self, battle, source):
        self.b = battle
        self.until = round(float(battle.rules['producer_protection_seconds']) * NATIVE_HZ)
        self.factor = float(battle.rules['producer_protection_multiplier'])
        battle.g['_pvp_damage_amount'] = self.amount
        battle.patch.ns['_pvp_damage_amount'] = self.amount
        rebuilt = {}
        exec(_patch_damage_code(source), rebuilt)
        for name, replacement in rebuilt.items():
            if not name.startswith('__pvz_sb_'):
                continue
            # NativeCombatPatch has already installed allegiance wrappers.
            # Retain that chain and replace only its match-local raw body.
            original = battle.patch.ns[name]
            while hasattr(original, '__wrapped__'):
                original = original.__wrapped__
            original.__code__ = replacement.__code__

    def multiplier(self, target):
        if self.b.engine.native_tick < target.get('_pvp_anchor_until',0):return 0.
        zs = getattr(self.b, 'zsecrets', None)
        if (zs is not None and zs.enabled and target.get('_pvp_grave') and zs.has('解除封印')
                and zs.selected_grave(target)):
            # 解除封印: the selected grave takes 25%. The same effect as the
            # opening producer protection, so the two never stack.
            return SELECTED_GRAVE_FACTOR
        if not 0 <= self.b.engine.native_tick < self.until:
            return 1.
        # Resolved imitater copies are registered with their actual card.
        # Temporary production units use the same catalog contract.
        card = CARDS.get(target.get('_pvp_card'), {})
        return self.factor if card.get('producer') else 1.

    def amount(self, target, amount):
        if amount <= 0:
            return amount
        zs = getattr(self.b, 'zsecrets', None)
        if zs is not None and zs.enabled:
            amount = zs.adjust(target, amount)
        amount *= self.multiplier(target)
        if amount > 0 and target.get('_pvp_content') == '死神僵尸':
            target['_pvp_reaper_hurt'] = self.b.engine.native_tick
        return amount

    def install_basketball(self):
        b = self.b
        def hit():
            plant = b.g['植物'][b.g['z']]
            plant['植物血'] -= self.amount(plant, 2.)
        name = '_pvp_basketball_plant_damage'
        b.g[name] = hit
        regions = dict(b.engine.regions)
        def enemy_plant():
            g=b.g
            return (b.targets.owner(g['实体'][g['l']])!='plant'
                    and '植物' in g['ditu'][g['y']][g['x']])
        b.g['_pvp_basket_enemy_plant']=enemy_plant
        from .native_gate import replace_predicate
        regions['entities']=replace_predicate(regions['entities'],100728,100746,
            '_pvp_basket_enemy_plant', [('LOAD_CONST','植物'),('LOAD_NAME','ditu'),
            ('LOAD_NAME','y'),('BINARY_SUBSCR',None),('LOAD_NAME','x'),('BINARY_SUBSCR',None),
            ('COMPARE_OP','in')])
        regions['entities'] = replace_damage_write(regions['entities'], 100800, 100826,
                                                   name, plant_write_expected(2))
        b.engine.regions = regions
