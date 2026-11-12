#include "sim/pvp/shim/pm_pvp67_assets.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_pvp67_assets {
V f_taco(const Args& A) { return py::atlas_image(SV("taco")); }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_pvp67_assets
