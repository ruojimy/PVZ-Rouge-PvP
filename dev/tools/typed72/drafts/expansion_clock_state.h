#pragma once
#include "sim/typed/field.h"
#include <array>
#include <cstddef>

namespace pvz::typed72 {
enum class ExpansionTimer : size_t {
    shoot_cd, shooting, eating, cannon_cd, cannon_animation,
    buried, grave_eating, magnet, burst, lamp, count
};
using ExpansionClockValues = std::array<Field<double>, size_t(ExpansionTimer::count)>;
struct ExpansionClockState {
    Field<ExpansionClockValues> delta, credit, debt;
};
} // namespace pvz::typed72
