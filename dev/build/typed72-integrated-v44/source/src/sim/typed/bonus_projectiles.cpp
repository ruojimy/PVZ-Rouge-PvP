#include "sim/typed/bonus_projectiles.h"
#include "sim/typed/spatial_mode.h"
#include "core/function_profile.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
double number(const Field<double>& field, double fallback = 0.) {
    return field.present() && !field.is_null() ? field.get() : fallback;
}
bool yes(const Field<bool>& field) {
    return field.present() && !field.is_null() && field.get();
}
bool smart(const Field<SmartProjectile>& field) {
    if (!field.present() || field.is_null()) return false;
    const auto& value = field.get();
    return value.target_index.present() || value.target_id.present() || value.initial_speed.present() ||
           value.gravity.present() || value.hit_time.present() || value.lead_scale.present() || value.created.present();
}
double length(double x, double y) { return std::sqrt(x * x + y * y); }
}

bool BonusProjectiles::live(const ZombieRecordFields& body) {
    return !body.dead.present() && !body.ash.present() && body.hp > 0.;
}
bool BonusProjectiles::has_live_zombies() const {
    return std::any_of(world_.targets->begin(), world_.targets->end(), [&](const CombatTarget& target) {
        return live(ballistics_.body(target));
    });
}
bool BonusProjectiles::i_zombie() const {
    const auto& mode = world_.heroes.globals.mode;
    return mode.present() && !mode.is_null() && mode.get() == "我是僵尸";
}
bool BonusProjectiles::zombie_placed() {
    if (!i_zombie()) {
        placed_ = false;
        board_zombies_.reset();
        board_plants_.reset();
        return false;
    }
    if (board_zombies_.lock() != world_.targets || board_plants_.lock() != world_.plant_roster) {
        board_zombies_ = world_.targets;
        board_plants_ = world_.plant_roster;
        placed_ = false;
    }
    if (has_live_zombies()) placed_ = true;
    return placed_;
}
bool BonusProjectiles::thrown(std::string_view name) {
    return name == "卷心菜" || name == "西瓜" || name == "冰瓜" || name == "玉米粒" || name == "黄油";
}
double BonusProjectiles::base_damage(const EntityRef& entity) {
    // NativeContent's dictionary override reads the current entity even when
    // its name is absent from the base-damage table.
    const auto& content = entity->source.content;
    if (content.present() && !content.is_null() && content.get() == "甜椒投手") return 60.;
    if (entity->kind == "玉米粒") return 5.;
    if (entity->kind == "卷心菜") return 30.;
    if (entity->kind == "黄油") return 10.;
    if (entity->kind == "西瓜" || entity->kind == "冰瓜") return 150.;
    return 0.;
}
void BonusProjectiles::patch(const EntityRef& entity) {
    try {
        if (!thrown(entity->kind) || smart(entity->service.smart) || yes(entity->service.smart_skip)) return;
        if (i_zombie() && !zombie_placed()) {
            entity->service.smart_skip.set(true);
            return;
        }
        ++seen_throwers;
        auto& position = entity->motion.get();
        const double speed = length(position.vx, position.vy);
        if (speed <= .01) {
            entity->service.smart_skip.set(true);
            return;
        }
        const auto aim = ballistics_.pick(entity);
        if (!aim.target) {
            entity->service.smart_skip.set(true);
            return;
        }
        const auto [solution, gravity] = ballistics_.compute(entity, *aim.target, aim.velocity, speed);
        if (!solution) {
            entity->service.smart_skip.set(true);
            return;
        }
        position.vx = solution->vx;
        position.vy = solution->vy;
        SmartProjectile value;
        value.target_index.set(aim.target->index);
        value.target_id.set(aim.target->identity);
        value.initial_speed.set(speed);
        value.gravity.set(gravity);
        value.hit_time.set(solution->time);
        value.lead_scale.set(.35);
        value.created.set(world_.native_time);
        entity->service.smart.set(std::move(value));
        ++patches;
    } catch (const std::exception&) {}
}
void BonusProjectiles::reaim(const EntityRef& entity) {
    if(!ballistics_.allows_reaim(entity))return;
    try {
        if (!smart(entity->service.smart) || yes(entity->bonus.damage_done)) return;
        const double now = world_.native_time;
        if (now - number(entity->bonus.last_guide) < .08) return;
        auto& lock = entity->service.smart.get();
        const auto index = lock.target_index.or_missing(-1);
        const auto aim = ballistics_.current(entity, index);
        if (!aim.target) return;
        auto& position = entity->motion.get();
        const double initial = std::max(.01, number(lock.initial_speed));
        const double current = length(position.vx, position.vy);
        const double speed = std::max(initial, current);
        const auto [solution, gravity] = ballistics_.compute(entity, *aim.target, aim.velocity, speed);
        if (!solution) return;
        double vx = position.vx * (1. - .26) + solution->vx * .26;
        double vy = position.vy * (1. - .26) + solution->vy * .26;
        const double next_speed = length(vx, vy);
        if (next_speed > .001) {
            vx = vx / next_speed * speed;
            vy = vy / next_speed * speed;
        }
        position.vx = vx;
        position.vy = vy;
        entity->bonus.last_guide.set(now);
        const auto count = int64_t(number(entity->bonus.guide_count)) + 1;
        entity->bonus.guide_count.set(double(count));
        lock.gravity.set(gravity);
        if (count == 1 || count == 6 || count == 12 || count % 24 == 0) ++guide_logs;
    } catch (const std::exception&) {}
}
void BonusProjectiles::guide() {
    const auto entities = *world_.runtime.entities.list();
    for (const auto& entity : entities) if (thrown(entity->kind) && smart(entity->service.smart)) reaim(entity);
}
void BonusProjectiles::velocity_damage(const std::shared_ptr<EntityRoster>& entities,
                                      const std::shared_ptr<TargetRoster>& zombies) {
    const auto captured = *entities;
    for (const auto& entity : captured) try {
        if (!smart(entity->service.smart) || yes(entity->bonus.damage_done)) continue;
        const double base = base_damage(entity);
        const auto index = entity->service.smart.get().target_index.or_missing(-1);
        if (base <= 0. || index < 0 || uint64_t(index) >= zombies->size()) continue;
        const auto target = zombies->at(size_t(index));
        const auto& position = entity->motion.get();
        const auto& target_position = ballistics_.motion(target);
        if (std::abs(position.x - target_position.x) > world_.runtime.tile * .55 ||
            std::abs(position.y - target_position.y) > world_.runtime.tile * 1.2) continue;
        if (target.is_hero() || target.unit->protection.hero) {
            entity->bonus.damage_done.set(true);
            continue;
        }
        const double impact = length(position.vx, position.vy);
        const double initial = std::max(1., number(entity->service.smart.get().initial_speed, impact));
        const double extra = base * .45 * std::max(0., impact / initial - 1.);
        entity->bonus.damage_done.set(true);
        if (extra > .5) {
            services_.bonus_damage(size_t(index), entity->facing, extra);
            ++bonus_hits;
        }
    } catch (const std::exception&) {}
}
void BonusProjectiles::prepare_cannon(const EntityRef& entity) {
    if (entity->kind != "玉米炮") return;
    const auto& position = entity->motion.get();
    if (!entity->cannon_lock.present()) entity->cannon_lock.set(0.);
    if (!entity->cannon_column.present()) entity->cannon_column.set(std::trunc(position.x / std::max(1., world_.runtime.tile)));
    if (!entity->gravity.present()) entity->gravity.set(0.);
}
void BonusProjectiles::fix_cannons() {
    const auto entities = *world_.runtime.entities.list();
    for (const auto& entity : entities) prepare_cannon(entity);
}
void BonusProjectiles::mark_reloading(const EntityRef& entity) {
    const auto& position = entity->motion.get();
    const auto plants = *world_.plant_roster;
    PlantRef best;
    double best_distance = 0.;
    for (const auto& plant : plants) {
        if (plant->kind != "玉米加农炮") continue;
        const double dx = (plant->cell.x + .5) * world_.runtime.tile - position.x;
        const double dy = (plant->cell.y + .5) * world_.runtime.tile - position.y;
        const double distance = std::abs(dx) + std::abs(dy);
        if (!best || distance < best_distance) { best = plant; best_distance = distance; }
    }
    if (!best) return;
    best->bonus.cannon_reloading.set(true);
    if (number(best->cannon_cd) > 7200.) best->cannon_cd.set(7200.);
}
void BonusProjectiles::patch_cannons() {
    const auto plants = *world_.plant_roster;
    for (const auto& plant : plants) {
        if (plant->kind != "玉米加农炮") continue;
        plant->monochrome.erase();
        double cooldown = number(plant->cannon_cd);
        if (cooldown > 7200.) {
            plant->cannon_cd.set(7200.);
            cooldown = 7200.;
            ++cannon_patches;
        }
        if (!yes(plant->bonus.cannon_reloading) || plant->shovel_dead.present()) continue;
        if (plant->dead.present() && cooldown > 0.) plant->dead.erase();
        if (cooldown <= 0. && number(plant->cannon_animation) <= 0.) plant->bonus.cannon_reloading.erase();
    }
}
double BonusProjectiles::head_damage(const EntityRef& entity) const {
    const auto& name = entity->kind;
    if (thrown(name)) return base_damage(entity);
    if (name == "豌豆" || name == "星星" || name == "尖刺" || name == "大泡泡" || name == "蓝泡泡") return 20.;
    if (name == "火豆") return 40.;
    if (name == "蓝火豆") return 30.;
    if (name == "泡泡" || name == "海泡泡") return 5.;
    return std::find(rules_.damaging.begin(), rules_.damaging.end(), name) != rules_.damaging.end() ? 20. : 0.;
}
bool BonusProjectiles::pierces(const EntityRef& entity) {
    const auto& name = entity->kind;
    return name == "星星" || name == "尖刺" || name == "大泡泡" || name == "蓝泡泡" ||
           yes(entity->bonus.star_patched) || number(entity->through_wall) != 0.;
}
bool BonusProjectiles::surface(const EntityRef& entity, const CombatZombie& unit, const Ellipse& head) {
    if (unit.body.hand != "钢门" || unit.body.hand_hp <= 0.) return true;
    if (entity->kind == "火豆" || entity->kind == "蓝火豆" || thrown(entity->kind)) return false;
    const double facing = unit.body.facing < 0. ? -1. : 1.;
    if ((entity->facing < 0. ? -1. : 1.) == facing) return false;
    const auto& position = entity->motion.get();
    if ((position.x - head.center.x) * facing < -std::max(1., head.rx) * .20) return false;
    return !(position.y - head.center.y < -std::max(1., head.ry) * .45 && std::abs(position.vy) > std::abs(position.vx) * .35);
}
void BonusProjectiles::head_hits() {
    PVP_PROFILE_SCOPE("BonusProjectiles::head_hits");
    const auto zombies = world_.targets;
    const auto entities = world_.runtime.entities.list();
    if (!std::any_of(zombies->begin(), zombies->end(), [](const CombatTarget& target) {
        return target.unit && yes(target.unit->patch.plant_zombie) && live(target.unit->body);
    })) return;
    if (!std::any_of(entities->begin(), entities->end(), [&](const EntityRef& entity) {
        return !entity->expires.is_true() && head_damage(entity) > 0.;
    })) return;
    const auto head_of=[&](const CombatZombie& unit){
        const auto& name=unit.patch.plant_name;
        const auto found=name.present()&&!name.is_null()?collision_.plant_heads.find(name.get()):collision_.plant_heads.end();
        const double scale=found==collision_.plant_heads.end()?.68:found->second.head_scale;
        return Ellipse{native_plant_zombie_head_center(unit,world_.runtime.tile,collision_),
            std::max(world_.runtime.tile*.20,world_.runtime.tile*scale*.46),
            std::max(world_.runtime.tile*.20,world_.runtime.tile*scale*.50)};
    };
    bool dirty=true;
    const auto captured_entities = *entities;
    for (const auto& entity : captured_entities) try {
        if (entity->expires.is_true()) continue;
        const bool piercing = pierces(entity);
        if (!piercing && yes(entity->bonus.head_hit)) continue;
        if (piercing && (!entity->bonus.head_hits.present() || entity->bonus.head_hits.is_null())) entity->bonus.head_hits.set({});
        const double amount = head_damage(entity);
        if (amount <= 0.) continue;
        const Point point{entity->motion.get().x, entity->motion.get().y};
        ++head_queries;head_full_scan+=zombies->size();
        if(spatial741_enabled()&&dirty){
            head_grid_.reset(world_.runtime.tile,world_.world_width.get(),world_.terrain.rows(),zombies->size());
            for(size_t i=0;i<zombies->size();++i)if(const auto u=zombies->at(i).unit;u&&yes(u->patch.plant_zombie)){
                const auto h=head_of(*u);head_grid_.cover(i,{h.center.x-h.rx,h.center.y-h.ry,h.center.x+h.rx,h.center.y+h.ry});
            }
            head_grid_.finish();dirty=false;
        }
        // Piercing impacts can synchronously transform or move other units.
        // Retain that legacy shallow snapshot only for piercing projectiles;
        // after an actual hit, inspect its remaining original entries live.
        const auto captured_zombies=piercing||!spatial741_enabled()?*zombies:TargetRoster{};
        auto selected=spatial741_enabled()?SpatialSelection<CombatTarget>::local(*zombies,head_grid_.point(point)):
            SpatialSelection<CombatTarget>::legacy(captured_zombies);
        size_t at=0;bool resumed=false;
        while(at<selected.values.size()) {
            const size_t index=selected.ordinal(at);const auto unit=selected.values[at++].unit;
            ++head_candidates;
            if (!unit || !yes(unit->patch.plant_zombie) || unit->source.charmed.present() || unit->body.hp <= 0.) continue;
            if (entity->native_source_zombie.present() && !entity->native_source_zombie.is_null() && entity->native_source_zombie.get() == unit->identity) continue;
            auto& hits = entity->bonus.head_hits;
            if (piercing && std::find(hits.get().begin(), hits.get().end(), unit->identity) != hits.get().end()) continue;
            const auto head=head_of(*unit);++head_exact_tests;
            const double dx = point.x - head.center.x, dy = point.y - head.center.y;
            if (dx * dx / std::max(1., head.rx * head.rx) + dy * dy / std::max(1., head.ry * head.ry) > 1.) continue;
            if (piercing) hits.get().push_back(unit->identity);
            else { entity->bonus.head_hit.set(true); entity->expires.set(true); }
            services_.head_damage(entity, index, entity->facing, amount, surface(entity, *unit, head));
            dirty=true;
            if (!piercing) break;
            if(spatial741_enabled()&&!resumed){
                resumed=true;selected=SpatialSelection<CombatTarget>::legacy(captured_zombies);at=index+1;
            }
        }
    } catch (const std::exception&) {}
}
} // namespace pvz::typed72
