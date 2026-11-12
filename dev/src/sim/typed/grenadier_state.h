#pragma once
#include "sim/typed/field.h"
#include "sim/typed/geometry.h"
#include <string>

namespace pvz::typed72 {
enum class GrenadierPhase { ready,wind,thrown,cancelled };
struct GrenadierState {
    Field<GrenadierPhase> phase;
    Field<double> clock,seen_hp,hold_x;
    Field<Motion> before;
};
} // namespace pvz::typed72
