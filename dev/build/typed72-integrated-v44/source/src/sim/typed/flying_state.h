#pragma once
#include "sim/typed/field.h"
#include <string>
#include <vector>

namespace pvz::typed72 {
struct FlyingPlantState {
    Field<double> clock,rest,sweep_age,sweep_angle,sweep_facing,shots;
    Field<std::string> mode;
};
struct FlyingShotState {
    Field<double> angle,damage,distance;
    Field<bool> piercing;
    Field<std::vector<std::string>> hits;
};
} // namespace pvz::typed72
