#pragma once
// patch1501 __pvz_sb_draw_bonus_overlays (NativeCombatPatch.draw): zombie peas, fume bubbles,
// plant-zombie heads (+ armor, umbrella leaf), sunflower dancer boss heads, pumpkin armors,
// boss bar. Source: src/sim/pvp/gen/pm_patch1501.cpp (draw_* helpers, lines 10364-11461).
#include "sim/typed/native_canvas.h"
#include "sim/typed/targets.h"
#include <functional>
namespace pvz::typed72 {
class NativePatchDraw {
public:
    NativePatchDraw(TypedBattleState& world,NativeCanvas& canvas):world_(world),canvas_(canvas){}
    std::function<void(const std::string&)> unsupported;
    // __pvz_sb_fumeshroom_zombie_is_thunder (FumeEffects::thunder) and
    // __pvz_sb_update_fumeshroom_bubbles(g, now) (FumeEffects::update_bubbles), which the
    // original calls from the draw itself.
    std::function<bool(const ZombieRef&)> thunder;
    std::function<void(double)> update_bubbles;
    double now=0.;
    void draw_overlays();
    void zombie_peas();
    void fume_bubbles();
    void plant_zombie_heads();
private:
    NativeArt bubble_surface(const std::string& name);
    TypedBattleState& world_;
    NativeCanvas& canvas_;
    NativeArt flip_cached(const NativeArt& source,const std::string& key);
    NativeArt smoothscaled(const NativeArt& surface,double factor);
    void missing(const std::string& what){if(unsupported)unsupported(what);}
};
} // namespace pvz::typed72
