// Shim for modkit/pvp/app.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_app {
void init();
V f__pygame(const Args& A);
}}  // namespace pvz::pm_app
