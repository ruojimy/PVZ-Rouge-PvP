// Shim for modkit/pvp/native_bytecode.py (presentation/tooling module) - see tools/gen_shims.py
#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz { namespace pm_native_bytecode {
void init();
V f_instruction_window(const Args& A);
V f_instructions(const Args& A);
V f_decode(const Args& A);
}}  // namespace pvz::pm_native_bytecode
