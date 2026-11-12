// Shim for modkit/pvp/native_assets.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_native_assets {
void init();
V f_load_original_assets(const Args& A);
}}  // namespace pvz::pm_native_assets
