#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include "sim/typed/allegiance.h"
#include <string>
#include <memory>
#include <vector>

namespace pvz::typed72 {
enum class GrenadierPhase { ready,wind,thrown,cancelled };
struct GrenadierState {
    Field<GrenadierPhase> phase;
    Field<double> clock,seen_hp,hold_x;
    Field<Motion> before;
};
struct Grenade {
    Field<std::string> kind;
    Motion motion;
    Seat owner=Seat::zombie;
    Field<Seat> seat;
    Field<double> direction;
    Field<std::string> source;
    std::string target;
    Cell cell;
    bool defused=false;
    Field<bool> instant;
    int64_t age=0;
};
using GrenadeRef=std::shared_ptr<Grenade>;
using GrenadeRoster=std::vector<GrenadeRef>;
} // namespace pvz::typed72
