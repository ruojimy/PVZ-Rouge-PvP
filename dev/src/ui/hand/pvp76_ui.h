#pragma once
// PvP76 battle-screen fixes, hooked into the translated Application by
// tools/pvp76_ui_hooks.py (re-applied after UI regeneration; --check is a build gate).
#include "sim/pvp/pvprt.h"
namespace pvz::pvp76_ui {
// Placement preview for cards summoned at the pointer without a grave (克苏鲁之仆,
// test-mode Terraria Bosses). The V preview validator only knows grave exits and
// used to snap these to the selected grave although the kernel places them at the
// pointer. Returns true when it wrote state["placement_preview"].
bool free_summon_preview(const V& app,const V& card,const V& x,const V& y);
}
namespace pvz::pvp76_perf {
// Typed battles answer battle.g / avatars with a whole-world native projection and, once
// handed out, re-project after every command. Performance evidence must not do that:
// these read the published counters / the app's snapshot view instead.
bool typed(const V& battle);
// Live mobile zombies (typed) or the native list length (reference battle).
double zombie_count(const V& battle);
// {native_tick, zombies, plants, projectiles, backlog_seconds} from the view for typed battles.
V population(const V& app,const V& battle);
}
