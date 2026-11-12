#pragma once
#include "sim/typed/field.h"
namespace pvz::typed72 {
// zombie_secrets.py per-unit bookkeeping kept on the authoritative body:
// _pvp_zs_control (不可撼动 seen control), _pvp_zs_timer (shot timers),
// _pvp_zs_converted, _pvp_zs_blasted and a grave's _pvp_zs_awake.
struct ZombieSecretUnitState {
    Field<double> control_ice,control_butter,control_stun;
    Field<double> timer_shot,timer_basket;
    // _fast_shots setdefault("_pvp_zs_timer", {}): the dict exists, possibly empty, once visited.
    Field<bool> timer_tracked;
    Field<bool> converted,blasted,awake;
};
// Avatar fields written by the same controller: _pvp_base_speedmax (汇流)
// and the 豌豆 head mark.
struct ZombieSecretHeroState {
    Field<double> base_speedmax;
    Field<bool> pea_head;
};
} // namespace pvz::typed72
