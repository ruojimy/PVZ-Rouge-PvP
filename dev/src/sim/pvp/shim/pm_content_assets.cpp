#include "sim/pvp/shim/pm_content_assets.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_content_assets {
V SCALE_TILES;
V f_install(const Args& A) { return V::none(); }
static void load_() { SCALE_TILES = py::data_value("content_assets", "SCALE_TILES"); }
void init() { static bool done = false; if (done) return; done = true; load_(); }
}}  // namespace pvz::pm_content_assets
