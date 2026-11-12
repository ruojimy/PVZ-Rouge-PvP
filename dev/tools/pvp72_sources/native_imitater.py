"""Keep the selected PvP card through the original imitater transformation."""
import sys

from .catalog import resolve_card


class NativeImitater:
    def __init__(self, battle):
        self.b = battle
        self.original = battle.g["种植植物"]
        battle.g["种植植物"] = self.plant

    def plant(self, row, col, name, facing):
        b = self.b
        source = b.targets.source()
        # Only the native transformation callback may consume this identity.
        # The native template name is deliberately retained for its animation.
        copying = (sys._getframe(1).f_code is b.engine.regions["plants"]
                   and isinstance(source, dict)
                   and source.get("植物") == "模仿者"
                   and source.get("坐标") == [row, col]
                   and source.get("模仿") == name
                   and source.get("_pvp_copy_card"))
        if not copying:
            return self.original(row, col, name, facing)
        try:
            card = resolve_card(source["_pvp_copy_card"],
                                b.team_secrets["plant"], b.bans,
                                b.map.get("environment", {}).get("night", False))
        except ValueError:
            b._emit("spawn_blocked", card=source["_pvp_copy_card"],
                    reason="copy_target_unavailable")
            return None
        if b.deathmatch and card.get("producer"):
            b._emit("spawn_blocked", card=card["id"], reason="deathmatch_producer")
            return None
        roster = b.g["植物"]
        before = len(roster)
        # Admission concerns the copied card. Its implementation template may
        # be independently banned (primal pea still uses ordinary pea code).
        result = b._plant_native_factory(row, col, card["native_input_name"], facing)
        for native in roster[before:]:
            b._configure_plant(native, card)
            b._register(native, card, "plant", True,
                        parent={"id": source.get("_pvp_id")})
            b.content.configure(native, card)
            # Native marks the copy grey with 植物[-1]['黑白']=0 after this call.
            # Content that appends its own records (抓人草's tentacle heads)
            # would take that mark instead, leaving the copy in colour (71002).
            native['黑白'] = 0
            # The shell was replaced successfully, not killed. Its copied
            # plant owns the single eventual 补光 death reward.
            source['_pvp_transform_succeeded'] = True
        return result
