#include "sim/pvp/shim/pm_app.h"
#include "sim/pvp/hand/graphics.h"
#include <cmath>
#include <algorithm>
namespace pvz { namespace pm_app {
V f__pygame(const Args& A) { throw PyError("RuntimeError", "pygame is not available in the native build"); }
void init() { static bool done = false; if (done) return; done = true; }
}}  // namespace pvz::pm_app
