#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <string>

namespace pvz::typed72 {
struct PathSnapshot;
struct ContentZombieState {
    Field<std::shared_ptr<Motion>> player_position;
    Field<double> saved_basketball_cd,summon_clock,cannon_rate;
    Field<double> cart_deadline,cannon_animation,cannon_recoil;
    Field<bool> cart_expired,cannon_loaded;
    Field<double> barrel_direction,barrel_remaining;
    Field<bool> barrel_broken,barrel_discarded,barrel_detached;
    Field<std::string> target;
    Field<bool> headhunt;
    Field<std::shared_ptr<PathSnapshot>> yeti_tracking;
};
} // namespace pvz::typed72
