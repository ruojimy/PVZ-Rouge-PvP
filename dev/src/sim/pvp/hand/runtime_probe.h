#pragma once
#include "sim/pyrt.h"

namespace pvz {
// Optional observation after a real physics region completes. Only cpp_tests installs a probe;
// the game has no environment switch that can alter a result.
using NativePhysicsResultProbe = void (*)(const V& world, const V& region);
void set_native_physics_result_probe(NativePhysicsResultProbe probe);
}
