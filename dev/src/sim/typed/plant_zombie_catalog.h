// Effective PvP plant-zombie definitions; generated from the installed source.
#pragma once
#include "sim/typed/projectile_rules.h"
#include <span>
namespace pvz::typed72 {
#define PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(X) X(hp) X(burst) X(burst_gap) X(cooldown) X(initial_cooldown_max) X(fire_anim) X(head_scale) X(head_x) X(head_y) X(duck_head_x) X(duck_head_y) X(armor_x) X(armor_y) X(knockback) X(move_speed) X(jump_speed) X(plant_damage) X(visual_tick) X(damage_tick) X(damage_pulses) X(range_tiles) X(attack_length) X(visual_bubbles) X(radius)
#define PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(X) X(shoot) X(doom) X(blover) X(lantern) X(squash) X(gravebuster) X(umbrella) X(gold_magnet) X(fumeshroom)
struct PlantZombieConfig {
    std::string_view kind;
    std::string head;
#define NUM(n) Field<double> n;
    PVZ72_PLANT_ZOMBIE_CONFIG_NUMBERS(NUM)
#undef NUM
#define FLAG(n) Field<bool> n;
    PVZ72_PLANT_ZOMBIE_CONFIG_FLAGS(FLAG)
#undef FLAG
};
std::span<const PlantZombieConfig> native_plant_zombie_catalog();
const PlantZombieConfig* native_plant_zombie_config(std::string_view);
void load_native_plant_zombie_heads(CollisionCatalog&);
} // namespace pvz::typed72
