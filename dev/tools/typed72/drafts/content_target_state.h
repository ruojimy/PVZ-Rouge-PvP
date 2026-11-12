#pragma once
#include "sim/typed/field.h"
#include <optional>
#include <string>
#include <vector>
namespace pvz::typed72 {
struct ContentTargetState {
    Field<std::vector<std::optional<std::string>>> ice_chili_hits;
};
} // namespace pvz::typed72
