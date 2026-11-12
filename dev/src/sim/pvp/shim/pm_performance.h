// Shim for modkit/pvp/performance.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_performance {
void init();
V f_enabled(const Args& A);
V cls_FramePixels();
}}  // namespace pvz::pm_performance
