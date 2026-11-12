#pragma once
#include "core/pymath.h"
namespace pvz::typed72 {
// rv_observation.wrap_delta intentionally chooses positive displacement at
// exactly half the world width; combat wrap_delta chooses the negative tie.
inline double ai_wrap_delta(double a,double b,double width){const auto delta=py::mod(b-a,width);return delta>width/2.?delta-width:delta;}
}
