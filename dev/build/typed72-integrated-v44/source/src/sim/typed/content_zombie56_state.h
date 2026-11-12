#pragma once
#include "sim/typed/allegiance.h"
#include "sim/typed/field.h"
#include <string>
namespace pvz::typed72 {
struct ContentZombie56State {
    Field<std::string> dance_owner,wild_parent,squad_owner;
    Field<double> dance_slot,saved_speed,dance_clock,dance_rate;
    Field<bool> dancing,impulse;
    Field<Seat> dance_side;
};
} // namespace pvz::typed72
