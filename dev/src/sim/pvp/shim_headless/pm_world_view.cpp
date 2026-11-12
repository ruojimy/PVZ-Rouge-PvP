#include "sim/pvp/shim/pm_world_view.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_world_view {
// world_view.sun_scale: 1 for <= 25 sun, else min(2.4, sqrt(amount/25))
V f_sun_scale(const Args& A) { double a = A.pos.at(0).num(); return V(a <= 25 ? 1.0 : std::min(2.4, std::sqrt(a / 25.0))); }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_world_view
