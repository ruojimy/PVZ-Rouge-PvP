#include "sim/typed/bonus_scan.h"
#include <cmath>

namespace pvz::typed72 {
void BonusScan::before(double time) {
    if (closed) throw std::logic_error("Native combat patch is closed");
    if (!std::isfinite(time) || time < now) throw std::invalid_argument("Combat time must be finite and monotonic");
    now = time;
    world_.native_time = time;
}
void BonusScan::after(double time, std::span<const Seat> hero_order) {
    before(time);
    auto& heroes = world_.heroes;
    for (const Seat seat : hero_order) {
        HeroContext context(heroes, {seat, team_of(seat), CombatPhase::player, heroes.hero(seat).avatar_source, {}});
        systems_.deaths.chili.launch_guard(now);
    }
    {
        HeroContext context(heroes, {Seat::zombie, Seat::plant, CombatPhase::player, heroes.hero(Seat::plant).avatar_source, {}});
        scan();
    }
    ++tick_calls;
}
void BonusScan::track_max_hp() {
    const auto zombies = *world_.targets;
    for (const auto& target : zombies) try {
        if (target.unit) DamagePatch::remember_max_hp(*target.unit);
        else {
            auto& proxy = world_.heroes.cached_proxy(target.hero);
            if (proxy.hp <= 0.) continue;
            auto& maximum = proxy.observed_max_hp;
            const double old = maximum.present() && !maximum.is_null() ? maximum.get() : proxy.hp;
            if (proxy.hp > old || !maximum.present()) maximum.set(proxy.hp);
        }
    } catch (const std::exception&) {}
}
void BonusScan::death_effects() {
    if (!std::any_of(world_.targets->begin(), world_.targets->end(), [](const CombatTarget& target) {
        return target.unit && target.unit->patch.plant_zombie.present() &&
               !target.unit->patch.plant_zombie.is_null() && target.unit->patch.plant_zombie.get();
    })) return;
    const auto zombies = *world_.targets;
    for (const auto& target : zombies) try {
        if (target.unit) {
            systems_.deaths.auto_explode(target.unit, now);
            systems_.deaths.plant_zombie_deaths(target.unit);
        } else {
            const auto source = world_.heroes.proxy_source(target.hero);
            const auto owner = SourcedContext::source_owner(*source);
            const auto enemy = owner == Seat::plant ? Seat::zombie : Seat::plant;
            world_.heroes.context_effects(enemy, owner, CombatPhase::zombies);
            world_.heroes.context_effects(enemy, owner, CombatPhase::zombies);
        }
    } catch (const std::exception&) {}
}
void BonusScan::scan() {
    const auto zombies = world_.targets;
    const auto plants = world_.plant_roster;
    const auto entities = world_.runtime.entities.list();
    const bool live = systems_.projectiles.has_live_zombies();
    const bool placed = systems_.projectiles.zombie_placed();
    const bool pending_squash = systems_.squash.pending();
    const auto& mode = world_.heroes.globals.mode;
    const bool empty = mode.present() && !mode.is_null() && mode.get() == "我是僵尸" &&
        world_.zombie_peas.legacy->empty() && world_.fume.bubbles.empty() && !placed && !live && !pending_squash;
    bool active = !world_.zombie_peas.legacy->empty() || !world_.fume.bubbles.empty() || !zombies->empty();
    if (empty) active = false;
    else active = active || !plants->empty() || !entities->empty();
    if (now - last_scan < (active ? .02 : .10)) return;
    last_scan = now;
    systems_.deaths.chili.launch_guard(now);
    const double maintenance_interval = active ? .25 : (empty ? 1. : .5);
    if (now - last_maintenance >= maintenance_interval) {
        last_maintenance = now;
        systems_.plants.cleanup_stones();
        if (!empty) {
            systems_.projectiles.fix_cannons();
            systems_.projectiles.patch_cannons();
        }
    }
    if (empty) return;
    systems_.plants.finalize_stars();
    systems_.plants.starfruit();
    systems_.plants.tripea();
    track_max_hp();
    systems_.shooting.step();
    systems_.plants.grave_damage();
    systems_.lantern.native_charmed_healing();
    systems_.peas.update_all();
    systems_.fume.update_bubbles(now);
    systems_.projectiles.guide();
    systems_.squash.finish_entities();
    systems_.squash.update_entities();
    systems_.plants.star_damage();
    death_effects();
    systems_.deaths.chili.scan();
    systems_.projectiles.velocity_damage(entities, zombies);
    systems_.projectiles.head_hits();
}
} // namespace pvz::typed72
