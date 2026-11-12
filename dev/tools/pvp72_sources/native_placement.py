"""Read-only original planting rules, shared by authority and local preview.

Only the trusted local marshal's planting query region and its three query
functions execute. Peer snapshots supply data, never code, functions or paths.
No native combat initialization, random number, tick, spawn or save is used.
"""
import builtins
import math
import types
from .catalog import resolve_card
from .native_runtime import PeriodicRow, original_regions, load_patch
from .simulation import finite
from .maps import _cell
from .pvp56_plants_catalog import AIR_PLANTS
from .pvp58_catalog import DENSE_PLANT_LIMIT

UNTARGETABLE_PLANTS = ('幽灵辣椒',)


_PATCHES = {}


def validate_thief_placement(battle, side, key, x, y):
    """The native bungee descends onto a chosen living plant, without a grave."""
    player = battle.players.get(side)
    if not side.startswith("zombie") or player is None or key not in player["deck"]:
        return "卡牌不在本方卡槽", None
    if battle.result:return "对局已结束", None
    if not finite(x) or not finite(y) or not 0 <= x < battle.width or not 0 <= y < battle.height:
        return "放置坐标无效", None
    try:card = resolve_card(key, player["secrets"], battle.bans)
    except ValueError as exc:return str(exc), None
    if player["cooldowns"].get(key,0) > battle.time:return "卡牌冷却中", None
    if player["resource"] < card["cost"]:return "脑光不足", None
    if len(battle.units) >= 700:return "战场单位达到上限", None
    col, row = int(x // battle.tile), int(y // battle.tile)
    # This validator also runs in PreviewBattle, which has only the public
    # snapshot. Keep ghost targetability in that shared representation.
    # Flying plants in the air are valid prey. Only the haunting pepper stays
    # out: zombies can never target it, wherever it floats.
    targets = [unit for unit in battle.units.values() if unit["side"] == "plant" and unit["hp"] > 0
        and (unit.get('card_id') or '')[6:] not in UNTARGETABLE_PLANTS
        and (unit.get('copy_card_id') or '')[6:] not in UNTARGETABLE_PLANTS
        and unit.get('card_id') != 'plant:抓人草触手'     # PvP70: a floating head is not prey
        and int(unit["x"] // battle.tile) == col and int(round(unit["y"] / battle.tile))-1 == row]
    if not targets:return "请选择存活的敌方植物", None
    target = sorted(targets,key=lambda unit:unit["id"])[0]
    return "", dict(card=card,charge=card["cost"],x=target["x"],y=target["y"],slot=key,thief_target=target["id"])


def placement_patch(source):
    """Cache a private, definition-only patch namespace for its stone query."""
    if source not in _PATCHES:
        if len(_PATCHES) >= 2:
            _PATCHES.clear()
        _PATCHES[source] = load_patch(source)
    return _PATCHES[source]


def make_native_placement_state(g):
    """Minimal serializable native state; terrain is already in the snapshot.

    Preserve plant order because original pumpkin/non-pumpkin queries use it.
    Sleep is a presence flag in the original coffee test, not a timer test.
    """
    from .pvp58_vines import is_shell, is_airborne
    plants = []
    for plant in g["植物"]:
        if plant.get("_pvp_content") == "抓人草触手":
            continue    # PvP70: a floating tentacle head occupies no cell
        # The original query knows exactly one shell, the pumpkin. A vine
        # takes the same layer, so the query sees it under that name.
        item = {"植物": "南瓜头" if is_shell(plant) else plant["植物"], "坐标": list(plant["坐标"])}
        if plant.get('_pvp_content')=='水盆':item['basin']=True
        if "睡觉" in plant:
            item["睡觉"] = True
        if plant.get("_pvp_content") in ("阳光藤蔓", "忧郁藤蔓", "抓人草"):
            item["vine"] = True
        if is_airborne(plant):
            item["air"] = True
        plants.append(item)
    return dict(version=1, plants=plants, secrets=list(g["秘籍"]),
                empty_blocks=list(g["kong"]), spike_cost=g.get("地刺阳光", 100))


class NativePlacementRules:
    def __init__(self, root, terrain, state, patch=None):
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError("等待原版放置状态")
        self.region = original_regions(root)["placement"]
        self.patch = patch
        # These are read-only references: the original query writes only its
        # own scratch globals. Fresh rows provide the same periodic indexing.
        rows = [PeriodicRow(cell.get("native", {"方块": cell["kind"]})
                            for cell in row) for row in terrain["tiles"]]
        # The imported extended railway has a permanent bottom rail. The old
        # query unconditionally rejects every plant above 铁路, even a potted
        # one, leaving this lane without a defence. In this map's read-only
        # planting query only, treat its lowest rail as soil. Physics, textures,
        # all other railways and every remaining native legality rule stay native.
        if terrain.get('source') == 'custom:ea660000000000000000000000000009':
            rails = [r for r, line in enumerate(rows)
                     if any(cell.get('方块') == '铁路' for cell in line)]
            if rails:
                bottom = rails[-1]
                rows[bottom] = PeriodicRow(dict(cell, 方块='土') if cell.get('方块') == '铁路' else cell
                                           for cell in rows[bottom])
        self.g = dict(__builtins__=builtins.__dict__, ditu=rows,
                      植物=state["plants"], 秘籍=state["secrets"],
                      kong=state["empty_blocks"], 模式="正常模式")
        codes = {code.co_name: code for code in root.co_consts
                 if isinstance(code, types.CodeType)}
        for name in ("哪个植物", "哪个无南瓜植物", "出界"):
            self.g[name] = types.FunctionType(codes[name], self.g)
        original = self.g["出界"]
        self.g["出界"] = lambda row, col: original(row, 0)
        self.spike_cost = state.get("spike_cost", 100)

    @property
    def dense(self):
        return "密植" in self.g["秘籍"]

    def _water(self, row, col):
        tiles = self.g["ditu"]
        return 0 <= row < len(tiles) and str(tiles[row][col % len(tiles[0])].get("方块")) == "水"

    def plants_at(self, row, col):
        return [p for p in self.g["植物"] if p.get("坐标") == [row, col]]

    def dense_error(self, native_name, row, col):
        """Three plant bodies and one shared shell; coffee is independent.

        This snapshot query serves both the host and the guest's preview.
        Pots/lilies are terrain supports, not plant bodies in the stack.
        """
        if not self.dense or native_name in ('咖啡豆', '花盆', '睡莲', '石块'):
            return ''
        here = self.plants_at(row, col % len(self.g['ditu'][0]))
        if native_name == '南瓜头':
            return '每格最多额外种一个南瓜头或藤蔓' if any(p['植物'] == '南瓜头' for p in here) else ''
        bodies = [p for p in here if p['植物'] not in ('南瓜头', '咖啡豆', '花盆', '睡莲','水盆')]
        return '密植每格最多种三个主体植物' if len(bodies) >= DENSE_PLANT_LIMIT else ''

    def accepts(self, native_name, row, col):
        if not 0 <= row < len(self.g["ditu"]):
            return False
        col %= len(self.g["ditu"][0])
        if self.dense_error(native_name, row, col):
            return False
        if native_name == "石块":
            if self.patch is None:
                raise ValueError("等待原版石块放置规则")
            return bool(self.patch["__pvz_sb_valid_stone_cell"](self.g, row, col))
        if self.dense and native_name == "咖啡豆":
            # 密植: one coffee bean wakes the whole stack, so any sleeper in
            # the cell is a valid target, whatever lies on top of it.
            return any(p.get("睡觉") for p in self.plants_at(row, col))
        if native_name == "咖啡豆" and any(p.get("vine") and p.get("睡觉") for p in self.plants_at(row, col)):
            # A sleeping shell (忧郁藤蔓, 抓人草 and its heads) sits on the
            # pumpkin layer the original coffee query skips.
            return True
        plants = self.g["植物"]
        basin_here=[p for p in plants if p.get('坐标')==[row,col]]
        basin_only=bool(basin_here) and all(p.get('basin') for p in basin_here)
        # A vine on the water surface carries plants the way a lily pad does:
        # present a lily in the water cell below it to the original query.
        visible = [p for p in plants if not p.get('basin') and (not self.dense or p.get('坐标') != [row,col])]
        visible += [{"植物": "睡莲", "坐标": [p["坐标"][0]+1, p["坐标"][1]]} for p in plants
                    if p.get("vine") and self._water(p["坐标"][0]+1, p["坐标"][1])]
        self.g["植物"] = visible
        rows = self.g["ditu"]
        marked = rows[row][col]
        if (self.dense or basin_only) and "植物" in marked:
            # Occupancy is waived: the query sees the cell's terrain only.
            rows[row][col] = {k: v for k, v in marked.items() if k != "植物"}
        try:
            self.g.update(拿中=native_name, sbx=col, sby=row, 种植="")
            exec(self.region, self.g)
        finally:
            self.g["植物"] = plants
            rows[row][col] = marked
        return self.g["种植"] == "适宜种植"

    def shell_cell(self, row, col, vine):
        """Where a pumpkin or vine may go: onto a plant, the ground, or (a
        vine) straight onto the water surface. One shell per cell."""
        if not 0 <= row < len(self.g["ditu"]):
            return False
        col %= len(self.g["ditu"][0])
        here = self.plants_at(row, col)
        if any(p["植物"] == "南瓜头" for p in here):
            return False
        if any(p.get("air") for p in here):
            return True
        tile = _cell(self.g["ditu"][row][col], self.g["kong"])
        if vine and not here and not tile["solid"] and not tile["water"] and self._water(row+1, col):
            return True
        return self.accepts("南瓜头", row, col)

    def idle_cell(self, row, col):
        """A new floating plant still respects terrain and plant occupancy."""
        tiles = self.g['ditu']
        if not 0 <= row < len(tiles):return False
        col %= len(tiles[0])
        tile = _cell(tiles[row][col], self.g['kong'])
        if self.dense:
            return not tile['solid'] and not self.dense_error('飞行植物', row, col)
        return (not tile['solid'] and '植物' not in tiles[row][col]
                and not any(p.get('坐标') == [row, col] for p in self.g['植物']))

    def grass_cell(self, row, col):
        if not self.idle_cell(row, col):return False
        tiles = self.g['ditu']; col %= len(tiles[0])
        return any(_cell(tiles[rr][col+dx], self.g['kong'])['solid']
                   for rr in range(max(0, row-1), min(len(tiles), row+2))
                   for dx in (-1, 0, 1) if (rr, dx) != (row, 0))


def validate_native_placement(battle, native, side, key, x, y,
                              grave_id=None, copy_id=None):
    """Plant-side protocol checks plus exact original terrain/occupancy rules.

    ``native`` is a NativePlacementRules made from current authority state or
    its public snapshot. The returned plan is data and does not mutate battle.
    Copies keep the native imitater entity and its 300-frame transformation;
    the caller sets native global 模仿 from plan.copy_card before creating it.
    """
    player = battle.players.get(side)
    if not side.startswith("plant") or player is None:
        return "未知植物玩家", None
    if battle.result:
        return "对局已结束", None
    if not finite(x) or not finite(y):
        return "放置坐标无效", None
    if not isinstance(key, str) or key not in player["deck"]:
        return "卡牌不在本方卡槽", None
    try:
        card = resolve_card(key, player["secrets"], battle.bans,
                            battle.map.get("environment",{}).get("night",False))
    except ValueError as exc:
        return str(exc), None
    if player["cooldowns"].get(key, 0) > battle.time:
        return "卡牌冷却中", None
    copied = None
    if card["behavior"] == "copy":
        if copy_id is None:copy_id=player.get("last_copy_card")
        if not isinstance(copy_id, str) or copy_id == key or copy_id not in player["deck"]:
            return "请先种下一株可复制植物，或通过模仿目标按键选择复制目标（默认 V）", None
        try:
            copied = resolve_card(copy_id, player["secrets"], battle.bans,
                                  battle.map.get("environment",{}).get("night",False))
        except ValueError as exc:
            return str(exc), None
        if copied["category"] in ("secret", "tool") or copied["behavior"] == "gravebuster":
            return "不能复制工具、秘籍或墓碑吞噬者", None
    elif copy_id is not None:
        return "仅模仿者可以指定复制目标", None
    if battle.deathmatch and (card.get("producer") or (copied and copied.get("producer"))):
        return "死斗期间不能新增生产单位", None
    charge = card["cost"]
    if copied and 'secret:肆意模仿' in player['secrets']:
        charge=copied['cost']-100
    if card["native_input_name"] == "地刺":
        charge = native.spike_cost
    if not finite(player.get("resource")):
        return "等待本方资源状态", None
    if player["resource"] < charge:
        return "阳光不足", None
    if len(battle.units) >= 700:
        return "战场单位达到上限", None
    row = int(math.floor(y / battle.tile))
    col = int(math.floor((x % battle.width) / battle.tile))
    if not 0 <= row < len(native.g["ditu"]):
        return "放置位置超出地图", None
    placed = copied or card
    special=placed.get('content')
    special_legal=False
    if special=='水盆':
        if native.plants_at(row,col) or not native.accepts('花盆',row,col):return '水盆需要符合花盆放置要求的空格',None
        special_legal=True
    elif special=='冰冻生菜':
        here=[p for p in native.plants_at(row,col) if not p.get('basin')]
        # 密植 shares the water cell (its three-body limit still applies below).
        if native._water(row,col) and (not here or native.dense):special_legal=True
    shell = placed.get('behavior')=='vine' or not copied and card.get('native_input_name')=='南瓜头'
    limit_error = native.dense_error('南瓜头' if shell else placed['native_input_name'], row, col)
    if limit_error:
        return limit_error, None
    if card["behavior"] == "gravebuster":
        # A PvP grave is an attackable entity, never an old untargetable tile.
        # The native 600-frame consumption bridge receives this stable ID.
        # Stacked graves (a petrified vine with a grave) are eaten top first.
        stack = [unit for unit in battle.units.values()
                 if unit.get("behavior") == "grave" and unit.get("side") == "zombie"
                 and unit.get("hp", 0) > 0
                 and int(math.floor((unit["x"] % battle.width) / battle.tile)) == col
                 and int(math.floor((unit["y"] - .001) / battle.tile)) == row]
        target = stack[-1] if stack else None
        if target is None:
            return "请选择存活的敌方实体墓碑", None
        if "植物" in native.g["ditu"][row][col]:
            return "墓碑位置已有植物", None
        return "", dict(card=card, charge=charge, x=(col + .5) * battle.tile,
                         y=(row + 1) * battle.tile, row=row, col=col, slot=key,
                         grave_target=target["id"], copy_card=None, copy_id=None,
                         temporary=False)
    if card['behavior'] == 'grass':
        if not native.grass_cell(row, col):return '草坪需要闲置格，周围八格至少一格实体方块', None
        probe = dict(x=(col+.5)*battle.tile, y=(row+1)*battle.tile, w=battle.tile, h=battle.tile)
        if any(battle._overlaps(probe,u) for u in list(battle.units.values())+list(battle.players.values())
               if u.get('hp',1)>0):return '草坪位置被单位占用', None
    elif placed.get('allow_air'):
        if not native.idle_cell(row, col):return '此处不是闲置空格', None
        if not native.dense and any(u.get('hp',0)>0 and not u.get('mobile') and
               int(u['x']//battle.tile)==col and int((u['y']-.001)//battle.tile)==row
               for u in battle.units.values()):return '位置已有单位', None
    elif shell:
        if not native.shell_cell(row, col, placed.get('behavior') == 'vine'):
            return '此处不能放置南瓜头或藤蔓（每格限一个保护壳）', None
    elif copied and not special_legal and not native.accepts(copied["native_input_name"], row, col):
        return "此处不符合复制目标的原版种植条件", None
    shell = placed.get('behavior')=='vine' or not copied and card.get('native_input_name')=='南瓜头'
    # An imitater copying an aquatic plant goes where that plant goes: the
    # water. Its own land-only rule would refuse every such cell.
    aquatic_copy = bool(copied and copied.get('aquatic'))
    if (not special_legal and card['behavior'] != 'grass' and not placed.get('allow_air') and not shell and not aquatic_copy
            and not native.accepts(card["native_input_name"], row, col)):
        return "此处不符合原版种植条件", None
    return "", dict(card=card, charge=charge, x=(col + .5) * battle.tile,
                     y=(row + 1) * battle.tile, row=row, col=col, slot=key,
                     copy_card=copied, copy_id=copy_id, temporary=bool(copied))
