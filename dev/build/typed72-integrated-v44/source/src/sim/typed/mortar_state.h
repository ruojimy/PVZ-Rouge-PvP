#pragma once
#include "sim/typed/field.h"
#include <string>
namespace pvz::typed72 {
struct MortarShotState {
    Field<bool> mortar,bonus_done,multi_red,tripea_blue;
    Field<double> speed;
    Field<std::string> target,umbrella_reflected;
};
} // namespace pvz::typed72
