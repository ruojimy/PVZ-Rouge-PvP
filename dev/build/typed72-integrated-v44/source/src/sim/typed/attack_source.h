#pragma once
#include "sim/typed/borrowed_zombie_kind.h"
#include "sim/typed/allegiance.h"
#include "sim/typed/field.h"
#include "sim/typed/attack_identity.h"
#include "sim/typed/entity_source_link.h"
#include "sim/typed/zombie_source_link.h"
#include <memory>
namespace pvz::typed72 {
struct AttackSource {
    EntitySourceLink entity;
    ZombieSourceLink unit;
    Field<std::string> projectile, plant, zombie, plant_kind, content, variant;
    Field<std::string> fire_color, zombie_fire;
    Field<std::string> owner;
    std::optional<Seat> seat;
    // Presence alone, including None/zero, changes allegiance.
    Field<double> charmed;
    Field<bool> no_hero_attack, cattail, melon_splash, splash_done, area_damage;
    Field<std::string> id;
    Field<int64_t> wave_index;
    Field<std::string> original_owner, source_entity, root_source;
    Field<double> flight_limit_tiles, fire_lit;
    std::optional<AttackIdentity> instant_attack;
    Field<std::vector<std::string>> melon_hits;
    // A unit's native kind remains authoritative; this metadata only borrows
    // its address. source_ref retains the whole owning unit during callbacks.
    void bind_zombie_kind(const std::string& kind){zombie.erase();zombie_kind_.bind(kind);}
    std::string_view zombie_name() const {return zombie_kind_.present()?zombie_kind_.get():zombie.present()&&!zombie.is_null()?std::string_view(zombie.get()):std::string_view{};}
    bool has_zombie_name() const {return zombie_kind_.present()||zombie.present();}
private:
    BorrowedZombieKind zombie_kind_;
};
} // namespace pvz::typed72
