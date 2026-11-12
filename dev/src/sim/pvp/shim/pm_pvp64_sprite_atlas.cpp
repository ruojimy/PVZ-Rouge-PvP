#include "sim/pvp/shim/pm_pvp64_sprite_atlas.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_pvp64_sprite_atlas {
// transparent rows under the pose's lowest opaque pixel / canvas height, from the baked atlas
V f_ground_gap(const Args& A) { return py::atlas_ground_gap(A.pos.at(1)); }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_pvp64_sprite_atlas
