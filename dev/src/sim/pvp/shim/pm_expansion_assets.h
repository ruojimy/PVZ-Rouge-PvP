// Shim for modkit/pvp/expansion_assets.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_expansion_assets {
void init();
V f_install(const Args& A);
V cls_TemplateAtlas();
}}  // namespace pvz::pm_expansion_assets
