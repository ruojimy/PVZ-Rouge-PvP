#pragma once
#include "sim/pvp/pvprt.h"
namespace pvz::pressure741 {
// One policy for desktop and Android. Only platform power hints remain separate.
void observe(const V& app,double elapsed,double work);
double now();
// Measure update + snapshot publication separately from drawing, at the UI boundary.
void record_advance(const V& app,double cost);
}
