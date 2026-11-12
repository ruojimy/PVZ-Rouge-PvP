// Shim for modkit/pvp/world_view.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_world_view {
void init();
V f_sun_scale(const Args& A);
}}  // namespace pvz::pm_world_view
