#pragma once
#include "sim/typed/field.h"
#include <string>
namespace pvz::typed72 {
// pve.WaveDirector / coop_cycle.CoopCycle marks kept on the authoritative body:
// _pvp_spawn_grave (a grave that diverted this spawn), _pvp_coop_night_grave,
// _pvp_coop_just_slept (the wave a grave finished). _pvp_wave_index is
// AttackSource::wave_index and _pvp_coop_dormant is registration.coop_dormant.
struct PveZombieState {
    Field<std::string> spawn_grave;
    Field<bool> night_grave;
    Field<int64_t> just_slept;
};
// CoopCycle.mushrooms: coffee that woke a day sleeper stays permanent.
struct PvePlantState {
    Field<bool> coop_coffee;
};
} // namespace pvz::typed72
