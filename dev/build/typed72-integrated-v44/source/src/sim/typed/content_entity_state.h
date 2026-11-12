#pragma once
#include "sim/typed/field.h"
#include <string>
#include <vector>
namespace pvz::typed72 {
struct ContentEntityState {
    Field<bool> barrel_contact,dart;
    Field<bool> ready,returning,turned;
    Field<double> distance,speed,launch_direction;
    Field<std::vector<std::string>> leg_hits,primal_knock_hits;
};
} // namespace pvz::typed72
