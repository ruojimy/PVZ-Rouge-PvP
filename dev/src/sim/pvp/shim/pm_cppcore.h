// Shim for modkit/pvp/cppcore.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_cppcore {
void init();
V module_ns();
V f_configure_final_regions(const Args& A);
V f_copy_module(const Args& A);
V f_fast_deepcopy(const Args& A);
V f_native(const Args& A);
V f_status(const Args& A);
V f_native_for(const Args& A);
}}  // namespace pvz::pm_cppcore
