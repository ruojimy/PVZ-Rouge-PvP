// Shim for modkit/pvp/content_assets.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_content_assets {
void init();
extern V SCALE_TILES;
V f_install(const Args& A);
}}  // namespace pvz::pm_content_assets
