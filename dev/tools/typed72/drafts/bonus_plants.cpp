#include "sim/typed/bonus_plants.h"
#include "sim/typed/plant_zombie_shooting.h"
#include "core/pymath.h"
#include <cmath>

namespace pvz::typed72 {
namespace {
constexpr double pi = 0x1.921fb54442d18p+1;
double number(const Field<double>& value, double fallback = 0.) {
    return value.present() && !value.is_null() ? value.get() : fallback;
}
bool yes(const Field<bool>& value) { return value.present() && !value.is_null() && value.get(); }
double direction(double value) { return value < 0. ? -1. : 1.; }
Point vector(double angle, double speed) { return {std::cos(angle) * speed, -std::sin(angle) * speed}; }
double clamp_angle(double angle, double facing) {
    const double base = facing > 0. ? 0. : 180.;
    const double difference = std::clamp(py::mod(angle - base + 180., 360.) - 180., -90., 90.);
    return py::mod(base + difference, 360.);
}
class StarQueryScope {
public:
    StarQueryScope(NativeTracking& chart, Point point) : chart_(chart), restore_(!chart.active()) {
        if (!restore_) return;
        auto source = std::make_shared<AttackSource>();
        source->projectile.set("star-target");
        source->owner.set("plant");
        chart_.begin({source, {}, point});
    }
    ~StarQueryScope() { if (restore_) chart_.restore(); }
private:
    NativeTracking& chart_;
    bool restore_;
};
}

std::array<double, 5> BonusPlants::star_angles(double facing) {
    const double base = direction(facing) < 0. ? 0. : pi, step = 2. * pi / 5.;
    return {base, base - step, base + step, base - 2. * step, base + 2. * step};
}
void BonusPlants::apply_star(const EntityRef& entity, Point origin, Point velocity) {
    entity->motion.get() = {origin.x, origin.y, velocity.x, velocity.y};
    entity->facing = velocity.x >= 0. ? 1. : -1.;
    entity->through_wall.set(0.);
    entity->expires.set(-1000.);
    entity->bonus.star_patched.set(true);
    entity->bonus.star_hits.set({});
    entity->gravity.erase();
}
void BonusPlants::record_star(const EntityRef& entity, double facing) {
    if (entity->kind != "星星" || yes(entity->bonus.star_patched)) return;
    const auto& position = entity->motion.get();
    const double now = world_.native_time;
    const double speed = std::max(1., std::sqrt(position.vx * position.vx + position.vy * position.vy));
    for (const auto& group : pending_stars) {
        if (group->done || now - group->created > .12) continue;
        if (std::abs(group->origin.x - position.x) < 6. && std::abs(group->origin.y - position.y) < 6.) {
            group->stars.push_back(entity);
            group->speed = std::max(group->speed, speed);
            return;
        }
    }
    pending_stars.push_back(std::make_shared<StarBurst>(StarBurst{now, {position.x, position.y}, speed, direction(facing), {entity}, false}));
}
void BonusPlants::finalize_stars() {
    if (pending_stars.empty()) return;
    const auto entities = world_.runtime.entities.list();
    const double now = world_.native_time;
    const auto captured = pending_stars;
    std::vector<std::shared_ptr<StarBurst>> keep;
    for (const auto& group : captured) try {
        if (group->done) continue;
        if (now - group->created < .03) { keep.push_back(group); continue; }
        std::vector<EntityRef> stars;
        for (const auto& entity : group->stars) {
            // Admitted PvP entities carry distinct _pvp_id values. Their
            // dictionary membership therefore resolves to record identity.
            if (entity->kind == "星星" && std::find(entities->begin(), entities->end(), entity) != entities->end()) stars.push_back(entity);
        }
        if (stars.empty()) continue;
        const auto angles = star_angles(group->direction);
        for (size_t index = 0; index < angles.size(); ++index) {
            const auto velocity = vector(angles[index], std::max(1., group->speed));
            EntityRef entity;
            if (index < stars.size()) entity = stars[index];
            else {
                assets_.stored_add_entity("星星", velocity.x >= 0. ? 1. : -1.,
                    {group->origin.x, group->origin.y, velocity.x, velocity.y});
                if (!entities->empty()) entity = entities->back();
            }
            if (entity) apply_star(entity, group->origin, velocity);
        }
        for (size_t index = 5; index < stars.size(); ++index) stars[index]->expires.set(1024.);
        group->done = true;
        ++star_patches;
    } catch (const std::exception&) {}
    std::erase_if(keep, [now](const auto& group) { return now - group->created >= .5 || group->done; });
    pending_stars = std::move(keep);
}
size_t BonusPlants::spawn_stars(Point origin, double speed, double facing) {
    const auto entities = world_.runtime.entities.list();
    assets_.prepare_star_atlas();
    size_t patched = 0;
    for (const double angle : star_angles(facing)) try {
        const auto velocity = vector(angle, speed);
        const auto before = entities->size();
        assets_.stored_add_entity("星星", velocity.x >= 0. ? 1. : -1., {origin.x, origin.y, velocity.x, velocity.y});
        if (entities->size() > before) { apply_star(entities->back(), origin, velocity); ++patched; }
    } catch (const std::exception&) {}
    return patched;
}
bool BonusPlants::star_target(Point origin, double facing) {
    StarQueryScope scope(chart_, origin);
    const double tile = world_.runtime.tile;
    const auto rays = star_angles(facing);
    const auto zombies = *world_.targets;
    for (const auto& target : zombies) try {
        const auto& body = ballistics_.body(target);
        if (body.hp <= 0.) continue;
        const auto& position = ballistics_.motion(target);
        const double size = number(body.size, 2.);
        const double dx = position.x - origin.x, dy = position.y - tile * .35 * size - origin.y;
        if (std::sqrt(dx * dx + dy * dy) < tile * .45) continue;
        for (const double angle : rays) {
            const auto ray = vector(angle, 1.);
            if (dx * ray.x + dy * ray.y <= tile * .25) continue;
            const double perpendicular = std::abs(dx * ray.y - dy * ray.x);
            if (perpendicular <= std::max(18., tile * .42) + tile * std::max(.22, .18 * size)) return true;
        }
    } catch (const std::exception&) {}
    return false;
}
void BonusPlants::starfruit() {
    if (world_.targets->empty()) return;
    const auto plants = *world_.plant_roster;
    const double tile = world_.runtime.tile;
    const double speed = std::max(1., (200. + world_.targets->size() * 10.) * world_.runtime.plk);
    for (const auto& plant : plants) try {
        if (plant->kind != "杨桃" || number(plant->shoot_cd) > 1. || number(plant->shooting) > 0.) continue;
        const Point origin{plant->cell.x * tile + tile * .5, plant->cell.y * tile + tile * .5};
        const double facing = direction(plant->facing);
        if (!star_target(origin, facing)) continue;
        if (spawn_stars(origin, speed, facing)) {
            plant->shoot_cd.set(500.);
            if (number(plant->shooting) < 0.) plant->shooting.set(0.);
            ++star_shots;
        }
    } catch (const std::exception&) {}
}
void BonusPlants::star_damage() {
    const auto zombies = world_.targets;
    const auto entities = *world_.runtime.entities.list();
    const double tile = world_.runtime.tile;
    for (const auto& entity : entities) try {
        if (entity->kind != "星星" || !yes(entity->bonus.star_patched)) continue;
        if (!entity->bonus.star_hits.present()) entity->bonus.star_hits.set({});
        auto& hits = entity->bonus.star_hits.get();
        const auto& position = entity->motion.get();
        const Point point{position.x, position.y};
        const auto captured_zombies = *zombies;
        for (size_t index = 0; index < captured_zombies.size(); ++index) {
            const auto target = captured_zombies[index];
            const auto id = ballistics_.identity(target);
            if (std::find(hits.begin(), hits.end(), id) != hits.end()) continue;
            const auto& body = ballistics_.body(target);
            if (body.hp <= 0.) continue;
            const auto& target_position = ballistics_.motion(target);
            const double size = number(body.size, 2.);
            if (std::abs(point.x - target_position.x) > tile * .28 * size ||
                point.y < target_position.y - tile * .95 * size || point.y > target_position.y + tile * .12) continue;
            {
                HeroContext context(world_.heroes, {Seat::zombie, Seat::plant, CombatPhase::entities, source_ref(entity), {}});
                impacts_.bonus_damage(index, entity->facing, 10.);
            }
            hits.push_back(id);
        }
    } catch (const std::exception&) {}
}
std::array<Point, 3> BonusPlants::centers(const PlantRef& plant) const {
    const double scale = world_.runtime.tile;
    const double sway = std::sin(number(plant->root_animation) / 28.) * scale * .018;
    const double x = plant->cell.x * scale, y = plant->cell.y * scale;
    if (plant->facing < 0.) return {{{x + scale * .64 - sway, y + scale * .16},
        {x + scale * .45 + sway, y + scale * .38}, {x + scale * .27 - sway, y + scale * .60}}};
    return {{{x + scale * .36 + sway, y + scale * .16}, {x + scale * .55 - sway, y + scale * .38},
        {x + scale * .73 + sway, y + scale * .60}}};
}
std::vector<double> BonusPlants::angles(const PlantRef& plant, std::span<const Point> centers,
                                      std::span<const std::optional<PlantAimTarget>> targets) {
    const double facing = direction(plant->facing);
    const std::array<double, 3> fallback = facing > 0. ? std::array<double, 3>{-15., 0., 15.} : std::array<double, 3>{195., 180., 165.};
    const auto& previous = plant->bonus.tripea_angles;
    const bool valid = previous.present() && !previous.is_null() && previous.get().size() == 3;
    std::vector<Field<double>> next;
    std::vector<Field<RecordId>> identities;
    std::vector<double> result;
    for (size_t index = 0; index < centers.size(); ++index) {
        const auto target = index < targets.size() ? targets[index] : std::nullopt;
        double desired = fallback[index];
        Field<RecordId> id;
        id.set_null();
        if (target) {
            desired = py::mod(std::atan2(target->point.y - centers[index].y, target->point.x - centers[index].x) * (180. / pi) + 360., 360.);
            desired = clamp_angle(desired, facing);
            id.set(ballistics_.identity(target->target));
        }
        const double current = clamp_angle(valid ? number(previous.get()[index], fallback[index]) : fallback[index], facing);
        const double delta = py::mod(desired - current + 180., 360.) - 180.;
        const double value = clamp_angle(py::mod(current + delta * .30, 360.), facing);
        next.emplace_back(value);
        identities.push_back(id);
        result.push_back(value);
    }
    plant->bonus.tripea_angles.set(std::move(next));
    plant->bonus.tripea_targets.set(std::move(identities));
    return result;
}
bool BonusPlants::spawn_tripea(Point origin, double angle, bool upgraded) {
    const auto entities = world_.runtime.entities.list();
    const auto original_count = entities->size();
    const double speed = std::max(1., 200. * world_.runtime.plk), radians = angle * (pi / 180.);
    const double vx = std::cos(radians) * speed, vy = std::sin(radians) * speed;
    if (std::sqrt(vx * vx + vy * vy) <= .01) return false;
    const double x = origin.x + std::cos(radians) * world_.runtime.tile * .22;
    const double y = origin.y + std::sin(radians) * world_.runtime.tile * .22;
    std::string name = upgraded ? "蓝火豆" : "豌豆";
    if (upgraded && !assets_.prepare_blue_pea_atlas()) name = "火豆";
    assets_.stored_add_entity(name, vx >= 0. ? 1. : -1., {x, y, vx, vy});
    if (entities->size() > original_count) {
        entities->back()->facing = vx >= 0. ? 1. : -1.;
        if (upgraded) entities->back()->mortar.tripea_blue.set(true);
    }
    // NativeContent's wrapper uses the current roster after the stored
    // constructor returns, even if a synchronous callback replaced it.
    const auto current = world_.runtime.entities.list();
    for (size_t index = original_count; index < current->size(); ++index)
        if (yes(current->at(index)->mortar.tripea_blue)) MortarPlants::red_pea(current->at(index));
    return true;
}
void BonusPlants::tripea() {
    const auto plants = *world_.plant_roster;
    const auto& secrets = *world_.heroes.globals.secrets.get();
    const bool upgraded = std::find(secrets.begin(), secrets.end(), "三向蓝火") != secrets.end();
    for (const auto& plant : plants) try {
        if (plant->kind != "三向射手" || plant->dead.present() || plant->shovel_dead.present() || plant->sleep.present()) continue;
        if (!plant->shooting.present()) plant->shooting.set(0.);
        if (!plant->shoot_cd.present()) plant->shoot_cd.set(0.);
        const auto points = centers(plant);
        const auto targets = pick_tripea_targets(world_, chart_, plant, plant->facing, points);
        const auto directions = angles(plant, points, targets);
        const double cooldown = number(plant->shoot_cd);
        if (cooldown > 0.) { plant->shoot_cd.set(cooldown - 1.); continue; }
        if (std::none_of(targets.begin(), targets.end(), [](const auto& target) { return bool(target); })) {
            plant->shooting.set(0.);
            continue;
        }
        size_t fired = 0;
        for (size_t index = 0; index < targets.size() && index < points.size(); ++index)
            if (targets[index] && spawn_tripea(points[index], directions[index], upgraded)) ++fired;
        if (fired) { plant->shooting.set(1.); plant->shoot_cd.set(100.); ++tripea_shots; }
    } catch (const std::exception&) {}
}
void BonusPlants::cleanup_stones() {
    std::erase_if(*world_.plant_roster, [](const PlantRef& plant) { return yes(plant->bonus.stone_placeholder); });
}
bool BonusPlants::grave_touch(const ZombieRef& unit, const PlantRef& plant, double scale) const {
    if (plant->dead.present() || plant->shovel_dead.present() || number(plant->hp, 1.) <= 0.) return false;
    const auto& position = unit->body.motion.get();
    const auto touching = [&](int64_t row) {
        const double x = (plant->cell.x + .5) * world_.runtime.tile;
        const double y = row * world_.runtime.tile + world_.runtime.tile * .45;
        return std::abs(x - position.x) <= scale * .78 && std::abs(y - (position.y - scale * .35)) <= scale * .95;
    };
    if (touching(plant->cell.y)) return true;
    const auto lower_row = int64_t(plant->cell.y) + 1;
    if (lower_row < 0 || lower_row >= world_.terrain.rows()) return false;
    const auto& row = world_.terrain.grid.at(size_t(lower_row));
    const auto column = plant->cell.x < 0 ? plant->cell.x + int64_t(row.size()) : plant->cell.x;
    return row.at(size_t(column))->block.get() == "花盆块" && touching(lower_row);
}
void BonusPlants::grave_damage() {
    const auto zombies = world_.targets;
    const auto plants = world_.plant_roster;
    const std::array<std::string, 1> names{"墓碑吞噬者僵尸"};
    if (plants->empty() || !PlantZombieShooting::live(*zombies, std::span<const std::string>(names))) {
        grave_bites.clear();
        return;
    }
    std::vector<PlantRef> touching;
    const auto captured_zombies = *zombies;
    for (const auto& target : captured_zombies) try {
        const auto unit = target.unit;
        if (!unit || !BonusProjectiles::live(unit->body) || !unit->patch.plant_name.present() ||
            unit->patch.plant_name.is_null() || unit->patch.plant_name.get() != names[0]) continue;
        const auto captured_plants = *plants;
        for (const auto& plant : captured_plants)
            if (grave_touch(unit, plant, std::max(1., world_.runtime.tile)) && std::find(touching.begin(), touching.end(), plant) == touching.end()) touching.push_back(plant);
    } catch (const std::exception&) {}
    std::vector<std::pair<RecordId, double>> next;
    for (const auto& plant : touching) try {
        const double hp = number(plant->hp);
        const auto previous = std::find_if(grave_bites.begin(), grave_bites.end(), [&](const auto& entry) { return entry.first == plant->identity; });
        if (previous != grave_bites.end()) {
            const double delta = previous->second - hp;
            if (delta > 0. && delta < 6. && hp > 0.) {
                plant->hp.set(hp - (6. - delta));
                plant->hurt.set(1.);
                if (number(plant->hp) <= 0.) squash_.kill_plant(plant);
                ++grave_bite_hits;
            }
        }
        next.emplace_back(plant->identity, number(plant->hp, hp));
    } catch (const std::exception&) {}
    grave_bites = std::move(next);
}
} // namespace pvz::typed72
