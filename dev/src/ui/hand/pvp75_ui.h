#pragma once
// PvP75 激光豆 controls on the battle screen. Hooked into the translated
// Application / battle_view by tools/pvp75_ui_hooks.py (re-applied after UI regeneration).
#include "sim/pvp/pvprt.h"
namespace pvz::pvp75_ui {
// The active local plant seat has selected a 激光豆 and is choosing a point.
bool laser_aiming(const V& app);
// An own live 激光豆 unit row under the world point, or None.
V laser_at(const V& app,const V& x,const V& y);
// True when the click belonged to a 激光豆 (aim / fire / stop / cancel).
bool world_click(const V& app,const V& pos,const V& right);
void cancel(const V& app);
// A touch press on a 激光豆 or while aiming is a world click, never a jump.
bool blocks_jump(const V& app,const V& pos);
// Range hint while aiming, both ±80° sectors around the facing: red up to 8 cells (too close), green 8 to 20 cells.
// Diagnostic scene "laser" (performance probe): config["lasers"] durable 激光豆 firing through the zombies.
void diagnostic_lasers(const V& app,const V& battle,const V& config);
void draw_laser_ring(const V& r,const V& view,const V& state,const V& game,const V& terrain,const V& players,const V& side);
}
