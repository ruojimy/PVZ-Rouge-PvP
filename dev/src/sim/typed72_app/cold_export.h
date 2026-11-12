#pragma once
// Cold boundary between the V-constructed NativeBattle and the typed battle: the battle's
// terrain, rules, setup globals, RNG states, director, simulation atlas pixels and draw atlas.
// Static/cold path only: it never steps the battle. The lazy plant-zombie art patch is run
// once on the installed atlas so its draw recipes can be exported (its pre-patch art too).
#include "sim/pvp/pvprt.h"
#include "sim/typed72_app/cold_data.h"
namespace pvz::typed72app {
ColdExport export_cold(const V& battle,double seed);
} // namespace pvz::typed72app
