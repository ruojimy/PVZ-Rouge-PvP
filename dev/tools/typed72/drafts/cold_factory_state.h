#pragma once
#include "sim/typed/field.h"
#include <string>
#include <vector>
namespace pvz::typed72 {
struct ColdFactoryZombieState {
    Field<std::string> plant_head,plant_base,plant_display;
    Field<bool> sunflower_boss;
    Field<std::vector<std::string>> dancer_pending;
};
} // namespace pvz::typed72
