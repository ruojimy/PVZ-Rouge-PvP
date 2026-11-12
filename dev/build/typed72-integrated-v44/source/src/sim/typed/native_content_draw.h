#pragma once
// pvp native_content draw_zombie (content zombies with their own frame art), draw_center and
// native_barrels.draw. Source: tools/pvp72_sources/native_content.py:957,1251; native_barrels.py:130.
#include "sim/typed/native_canvas.h"
#include "sim/typed/targets.h"
#include "sim/typed/cart_lifecycle.h"
#include "sim/typed/native_content_phase.h"
#include <functional>
#include <map>
#include <optional>
namespace pvz::typed72 {
class NativeContentDraw {
public:
    NativeContentDraw(TypedBattleState& world,NativeCanvas& canvas):world_(world),canvas_(canvas){}
    std::vector<std::string> content_zombies;  // content_catalog.ZOMBIES
    std::function<void(const std::string&)> unsupported;
    // native_barrels.draw(z) for a barrel zombie that still carries its barrel.
    std::function<void(const ZombieRef&)> carried_barrel;
    int64_t native_tick=0;
    void draw_zombie(const ZombieRef&);
    // pvp64 draw_zombie (slimes, grenadier) and pvp61 draw_zombie (scarecrow, crow).
    void draw_zombie64(const ZombieRef&);
    void draw_zombie61(const ZombieRef&);
    // native_barrels.draw: the unaliased 滚桶 art turned by travel, centred above the feet.
    void draw_barrel(Point feet,double angle);
    void draw_center(const NativeArt&,double x,double y,double angle);
    // native_content.draw_custom_plant: content plant art with status flags.
    void draw_custom_plant(const CombatPlant&,std::string key,double x,double y,bool bottom=false,double angle=0.);
    // Content plants with their own drawer (pvp64/pvp61/september/vines/pvp70): true if drawn here.
    bool draw_plant(const CombatPlant&);
    std::map<std::string,double> pvp64_sinks;  // pvp64 plant_sink (cold)
    // pvp70_content.frost: idle mist (no age) or a burst `age` ticks old.
    void frost(double x,double y,int count,double radius,double seed,std::optional<double> age,std::optional<double> ground);
    // pvp70_content.draw_head: a 抓人草触手 head record.
    void draw_head(const CombatPlant&);
    // native_carts CartLifecycle::draw (小鬼炮) over this canvas.
    std::function<void(const ZombieRef&,CartDrawing&)> draw_cart;
    // Content effects (NativeContentPhases::draw_effects / draw_zombie70_effects callers):
    // september ghost blast ring, pvp61 reed bolt, pvp64 spring swipe, grenade blast and
    // grenade, pvp70 hook rope dot, bone/hook projectile and lettuce freeze flash.
    void ghost_effect(const GhostBlast&);
    void reed_effect(const ReedBolt&);
    void spring_effect(const SpringSwipe&);
    void grenade_effect(const GrenadeBlast&);
    void grenade_projectile(const GrenadeRef&,double angle,double alpha);
    void hook_rope(Point);
    void zombie_projectile(const ContentProjectileRef&,std::string_view sprite,double angle,double alpha);
    void lettuce_flash(const LettuceFlash&);
private:
    TypedBattleState& world_;
    NativeCanvas& canvas_;
    // pvp70 draw_head z.setdefault('_pvp_head_died', now): presentation-only, by head id.
    std::map<std::string,double> head_died_;
    void missing(const std::string& what){if(unsupported)unsupported(what);}
};
} // namespace pvz::typed72
